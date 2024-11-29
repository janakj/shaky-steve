import logging
import math
import asyncio
import logging
from copy     import deepcopy
from typing   import Union
from datetime import datetime, timedelta

import click
from pymitter          import EventEmitter
from adafruit_servokit import ServoKit

import steve.ease as ease
from steve.config import dbus_prefix
from steve.dbus   import DBusAPI
from steve.utils  import init_logging

log = logging.getLogger(__name__)

BUS_NAME = f'{dbus_prefix}.RoboArm'

State = Union[float, None]


class RoboArm(EventEmitter):
    def __init__(self, kit, model):
        super().__init__(wildcard=True)
        self.servo = kit.servo
        self.actuator = deepcopy(model['actuators'])
        self.set_map = {}
        self.get_map = {}
        self.task = {}

        # First check that all parameters within each actuator definition have
        # the correct format.
        for name, actuator in self.actuator.items():
            try:
                type_ = actuator['type']
                if type_ != 'linear' and type_ != 'angular':
                    raise Exception(f'Unsupported type {type_} for actuator {name}')
            except KeyError as e:
                raise Exception(f'Missing type for actuator {name}') from e

            if len(actuator['pulse']) != 2 or (
                not isinstance(actuator['pulse'][0], (int, float)) or
                not isinstance(actuator['pulse'][1], (int, float))):
                raise Exception(f'Invalid servo pulse widths in actuator {name}')

            try:
                if len(actuator['range']) != 2 or (
                    not isinstance(actuator['range'][0], (int, float)) or
                    not isinstance(actuator['range'][1], (int, float))):
                    raise Exception(f'Invalid range in actuator {name}')
            except KeyError:
                pass

            # If the actuator has a map attribute, convert it into a sorted list
            # of tuples where the first element in each tuple is the input
            # coordinate and the second element is the target value in the 0-1
            # range. The tuples are sorted in an ascending order of their input
            # coordinates.
            try:
                if type(actuator['map']) is not dict:
                    raise Exception(f'Invalid map in actuator {name}')

                l = list(map(lambda v: (float(v[0]), float(v[1])), actuator['map'].items()))
                self.set_map[name] = sorted(l, key=lambda v: v[0])
                self.get_map[name] = sorted(l, key=lambda v: v[1])
            except KeyError:
                pass
            except ValueError as e:
                raise Exception(f'Invalid map in actuator {name}') from e

        # If everything appears correct, apply the settings to the servos
        self.power_off()
        for actuator in self.actuator.values():
            self.servo[actuator['servo']].set_pulse_width_range(
                actuator['pulse'][0], actuator['pulse'][1])

        self.emit('moving', False)

    def stop(self):
        '''Stop all currently active movement tasks'''
        for task in self.task.values():
            task.cancel()

    def power_off(self):
        '''Stop any movement tasks and turn off all actuators'''
        self.stop()
        for name, actuator in self.actuator.items():
            self.servo[actuator['servo']].fraction = None
            self.emit('actuator.%s' % name, name, None)

    def get(self, name: str) -> State:
        actuator = self.actuator[name]
        state = self.servo[actuator['servo']].fraction
        if state is None: return None

        try:
            r = actuator['range']
        except KeyError:
            pass
        else:
            state = (state - r[0]) / (r[1] - r[0])

        try:
            m = self.get_map[name]
            m_ = self.set_map[name]
        except KeyError:
            if state < 0: state = 0.0
            if state > 1: state = 1.0
        else:
            for i in range(1, len(m)):
                if state <= m[i][1]:
                    break

            min = m[i - 1]
            max = m[i]
            state = (state - min[1]) / (max[1] - min[1])
            state = min[0] + (max[0] - min[0]) * state

            if state < m_[0][0]: state = m_[0][0]
            if state > m_[-1][0]: state = m_[-1][0]

        return state

    def _get_range(self, name: str) -> tuple[float, float]:
        try:
            m = self.set_map[name]
            return (m[0][0], m[-1][0])
        except KeyError:
            return (0.0, 1.0)

    def set(self, name: str, state: State, emit=True):
        actuator = self.actuator[name]

        v = state
        if v is not None:
            mm = self._get_range(name)
            if v == float('-inf'): v = mm[0]
            if v == float('+inf'): v = mm[1]

            # If the actuator has a map element, map input coordinates to the
            # 0.0-1.0 range using the map element.
            try:
                m = self.set_map[name]
            except KeyError:
                if v < 0 or v > 1:
                    raise ValueError(f'State {v} for actuator {name} out of the range <0, 1>')
            else:
                if v < m[0][0] or v > m[-1][0]:
                    raise ValueError(f'State {v} for actuator {name} is out of the range <{m[0][0]}, {m[-1][0]}>')

                for i in range(1, len(m)):
                    if v <= m[i][0]:
                        break

                min = m[i - 1]
                max = m[i]
                v = (v - min[0]) / (max[0] - min[0])
                v = min[1] + (max[1] - min[1]) * v

            # If the actuator has a physical range limit, scale the range 0-1 to
            # the more restricted range.
            try:
                r = actuator['range']
            except KeyError:
                pass
            else:
                v = r[0] + (r[1] - r[0]) * v

        self.servo[actuator['servo']].fraction = v
        if emit:
            self.emit('actuator.%s' % name, name, state)

    # Speed is in radians per second for angular actuators and meters per second
    # for linear actuators. 180 degrees is PI radians. None means maximum speed
    # supported by the servo.
    async def _move(self, name: str, to: float, speed: Union[float, None] = None, rate: int = 50, ease=None, moving_threshold=0.2) -> float:
        if speed is not None and speed < 0:
            raise Exception('Speed must be >= 0')

        from_ = self.get(name)
        if from_ is None:
            raise Exception(f'Current state of actuator {name} is unknown')

        # If speed is zero, do not move, just return the current state
        if speed == 0: return from_

        mm = self._get_range(name)
        if to == float('-inf'): to = mm[0]
        if to == float('+inf'): to = mm[1]

        if speed is not None:
            type_ = self.actuator[name]['type']
            if type_ == 'linear':
                duration = abs(to - from_) / speed
            elif type_ == 'angular':
                duration = abs(to - from_) / 180 * math.pi / speed
            else:
                raise Exception(f'Unsupported type {type_} in actuator {name}')

            if duration > moving_threshold:
                self.emit('moving', True)
        else:
            # If speed is unset, move as quickly as the actuator allows. With
            # duration of 0 the code below will simply degrade to a single set
            # operation.
            duration = 0

        start = datetime.now()
        stop = start + timedelta(seconds=duration)
        while True:
            now = datetime.now()
            if now >= stop:
                self.set(name, to)
                return to

            i = (now - start).total_seconds() / duration
            if i > 1: i = 1

            v = ease(i) if ease is not None else i
            self.set(name, (to - from_) * v + from_, emit=False)
            await asyncio.sleep(1 / rate)

    @property
    def moving(self):
        return len(list(filter(lambda t: not t.done(), self.task.values()))) != 0

    async def move(self, name: str, to: State, speed: Union[float, None] = None, rate: int = 50, ease=None, block=True):
        try:
            self.actuator[name]
        except KeyError:
            raise Exception(f'Unknown actuator name {name}')

        task = self.task.get(name, None)
        if task is not None:
            task.cancel()

        if to is not None:
            coro = self._move(name, to, speed=speed, rate=rate, ease=ease)
            task = asyncio.create_task(coro, name=name)
            self.task[name] = task

            def cb(future):
                if not self.moving:
                    self.emit('moving', False)

            task.add_done_callback(cb)
            if block:
                return await task
            else:
                return task

    async def wakeup(self):
        self.shoulder = 30
        self.elbow = 0
        await asyncio.sleep(0.3)
        self.wrist_ud = -90
        self.wrist_lr = 0
        self.hand = float('+inf')
        self.torso = 0

    async def sleep(self):
        await self.move('wrist_lr', 0, 2)

        await asyncio.gather(
            self.move('hand', float('-inf'), 2),
            self.move('torso', 0, 2),
            self.move('shoulder', 60, 1),
            self.move('elbow', -39, 1))

        await self.move('wrist_ud', -90, 2)

    @property
    def hand(self):
        return self.get('hand')

    @hand.setter
    def hand(self, value: Union[float, None]):
        return self.set('hand', value)

    @property
    def wrist_lr(self):
        return self.get('wrist_lr')

    @wrist_lr.setter
    def wrist_lr(self, value):
        return self.set('wrist_lr', value)

    @property
    def torso(self):
        return self.get('torso')

    @torso.setter
    def torso(self, value):
        return self.set('torso', value)

    @property
    def wrist_ud(self):
        return self.get('wrist_ud')

    @wrist_ud.setter
    def wrist_ud(self, value):
        return self.set('wrist_ud', value)

    @property
    def elbow(self):
        return self.get('elbow')

    @elbow.setter
    def elbow(self, value):
        return self.set('elbow', value)

    @property
    def shoulder(self):
        return self.get('shoulder')

    @shoulder.setter
    def shoulder(self, value):
        return self.set('shoulder', value)


class RoboArmDBusAPI(DBusAPI):
    def __init__(self, roboarm, asyncio_loop):
        super().__init__(BUS_NAME)
        self.roboarm = roboarm
        self.asyncio_loop = asyncio_loop

        self._old_moving = None
        self._old_active = None

    def run(self):
        self.roboarm.on('moving', self.on_moving)
        self.on_moving(self.roboarm.moving)

        self.roboarm.on('actuator.*', self.on_actuator)
        for name in self.roboarm.actuator.keys():
            self.on_actuator(name, getattr(self.roboarm, name))

        super().run()

    def quit(self):
        self.roboarm.off('moving', self.on_moving)
        self.roboarm.off('actuator.*', self.on_actuator)
        super().quit()

    def _invoke_coro(self, coro):
        f = asyncio.run_coroutine_threadsafe(coro, self.asyncio_loop)
        return f.result()

    def stop(self):   self.roboarm.stop()
    def off(self):    self.roboarm.power_off()
    def wakeup(self): self._invoke_coro(self.roboarm.wakeup())
    def sleep(self):  self._invoke_coro(self.roboarm.sleep())

    def get(self, name):
        v = self.roboarm.get(name)
        return str(v) if v is not None else ''

    def set(self, name, state):
        if not isinstance(state, str):
            raise Exception('Actuator state argument must be a string')

        self.roboarm.set(name, float(state) if len(state) else None)

    def move(self, name, state, opts):
        if not isinstance(state, str):
            raise Exception('State argument must be a string')
        state = float(state) if len(state) else None

        kw = {}
        if 'speed' in opts: kw['speed'] = opts['speed']
        if 'rate'  in opts: kw['rate']  = opts['rate']
        if 'ease'  in opts: kw['ease']  = getattr(ease, opts['ease'])
        if 'block' in opts: kw['block'] = opts['block']

        self._invoke_coro(self.roboarm.move(name, state, **kw))

    @property
    def moving(self): return self.roboarm.moving

    @property
    def active(self):
        for name in self.roboarm.actuator.keys():
            if getattr(self.roboarm, name) != None:
                return True
        return False

    @property
    def hand(self): return self.get('hand')

    @hand.setter
    def hand(self, state): return self.set('hand', state)

    @property
    def wrist_ud(self): return self.get('wrist_ud')

    @wrist_ud.setter
    def wrist_ud(self, state): return self.set('wrist_ud', state)

    @property
    def wrist_lr(self): return self.get('wrist_lr')

    @wrist_lr.setter
    def wrist_lr(self, state): return self.set('wrist_lr', state)

    @property
    def elbow(self): return self.get('elbow')

    @elbow.setter
    def elbow(self, state): return self.set('elbow', state)

    @property
    def shoulder(self): return self.get('shoulder')

    @shoulder.setter
    def shoulder(self, state): return self.set('shoulder', state)

    @property
    def torso(self): return self.get('torso')

    @torso.setter
    def torso(self, state): return self.set('torso', state)

    def on_moving(self, state):
        if self._old_moving == state: return

        self._old_moving = state
        self.PropertiesChanged(f'{dbus_prefix}.RoboArm', {
            'moving': state
        }, [])

    def on_actuator(self, name, state):
        self.PropertiesChanged(f'{dbus_prefix}.RoboArm', {
            name: str(state) if state is not None else ''
        }, [])

        active = self.active
        if self._old_active == active: return
        self._old_active = active

        self.PropertiesChanged(f'{dbus_prefix}.RoboArm', {
            'active': active
        }, [])


RoboArmDBusAPI.__doc__ = f'''
<node>
    <interface name='{BUS_NAME}'>
        <method name='stop'></method>
        <method name='off'></method>
        <method name='wakeup'></method>
        <method name='sleep'></method>

        <method name='get'>
            <arg type='s' name='name' direction='in'/>
            <arg type='s' name='state' direction='out'/>
        </method>
        <method name='set'>
            <arg type='s' name='name' direction='in'/>
            <arg type='s' name='state' direction='in'/>
        </method>
        <method name='move'>
            <arg type='s' name='name' direction='in'/>
            <arg type='s' name='state' direction='in'/>
            <arg type='a{{sv}}' name='opts' direction='in'/>
        </method>

        <property name='active' type='b' access='read'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>

        <property name='moving' type='b' access='read'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='hand' type='s' access='readwrite'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='wrist_ud' type='s' access='readwrite'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='wrist_lr' type='s' access='readwrite'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='elbow' type='s' access='readwrite'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='shoulder' type='s' access='readwrite'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='torso' type='s' access='readwrite'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
    </interface>
</node>
'''


# How to calibrate the robot
#
# Map joint names to servo numbers depending on how the servos are wired to the
# PWM controller.
#
# Find out the minimum and maximum pulse width for each servo. Each servo is
# different and this step needs to be repeated individually for each servo. Find
# the range by listening to the servo. It will make sound if you get too far.
# This is best done before the servos are mounted onto the robot.
#
# Set the servos to 90 degrees, i.e., half of the range. Mount it on the chassis
#
# Map a custom servo angle range to the range 0 to 1 via a piece-wise linear
# function.
#
# Pulse widths are in microseconds. Dimensions are in millimeters.

@click.command()
@click.option('--verbose', '-v', envvar='VERBOSE', count=True, help='Increase logging verbosity')
def main(verbose):
    init_logging(verbose)

    roboarm = RoboArm(ServoKit(channels=16), {
        'actuators': {
            'torso': {
                'type' : 'angular',
                'servo': 0,
                'pulse': [ 460, 2450 ],
                'map'  : { -90: 0.01, 0: 0.47, 90: 0.97 }
            },
            'hand': {
                'type' : 'linear',
                'servo': 1,               # Servo number on the 16-port PWM chip
                'pulse': [ 590, 2590 ],   # Minimum and maximum usable pulse width for this servo
                'range': [ 0.16, 0.78 ],  # The servo can only operate within this physical range (maps to <0, 1>)
                'map'  : {                # The keys are the width of the open clamp in meters
                    0     : 1.0,  0.01  : 0.65, 0.02  : 0.42, 0.021 : 0.40,
                    0.022 : 0.38, 0.023 : 0.37, 0.024 : 0.35, 0.025 : 0.32,
                    0.026 : 0.30, 0.027 : 0.25, 0.028 : 0.22, 0.029 : 0.15,
                    0.03  : 0.0
                }
            },
            'wrist_lr': {
                'type' : 'angular',
                'servo': 2,
                'pulse': [ 580, 2580 ],
                'map'  : { -90: 0.93, 90: 0.04 },
            },
            'wrist_ud': {
                'type' : 'angular',
                'servo': 3,
                'pulse': [ 470, 2450 ],
                'map'  : { -90: 0, 0: 0.42, 90: 0.92 }
            },
            'elbow': {
                'type' : 'angular',
                'servo': 4,
                'pulse': [ 460, 2550 ],
                'range': [ 0.29, 0.89 ],
                'map'  : { -58.4: 1, 0: 0.51, 61.7: 0 }
            },
            'shoulder': {
                'type' : 'angular',
                'servo': 5,
                'pulse': [ 460, 2580 ],
                'range': [ 0.11, 0.96 ],
                'map'  : { -90: 1, 0: 0.51, 90: 0 }
            }
        },
        'dimensions': { # Dimensions of the robot's parts in millimeters
            'torso_height'  : 122,
            'arm_length'    : 100,
            'forearm_length': 98,
            'palm_length'   : 92,
            'palm_height'   : 10,
            'fingers_width' : 30
        }
    })

    loop = asyncio.new_event_loop()

    api = RoboArmDBusAPI(roboarm, loop)
    try:
        api.start()
        try:
            loop.run_forever()
        finally:
            log.debug("Waiting for asyncio event loop to stop")
            loop.stop()
    finally:
        api.quit()
        roboarm.power_off()


if __name__ == "__main__":
    main()
