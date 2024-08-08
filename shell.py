#!/usr/bin/env python3
import os
import logging
from pydbus import SystemBus
from gi.repository import GLib
from cmd import Cmd
from config import dbus_prefix, verbose


def parse_actuator_state(v):
    to = v.lower().strip()
    if v == 'min': return str(float('-inf'))
    elif v == 'max': return str(float('+inf'))
    elif v == 'off': return ''
    return str(float(to))


class Shell(Cmd):
    prompt = 'Shaky Steve> '
    intro = "Shaky Steve is pleased to make your acquitance! Type ? to list commands"

    def __init__(self, roboarm, stt):
        super().__init__()
        self.roboarm = roboarm
        self.stt = stt

    def prop(self, name, arg):
        arg = arg.lower().strip()

        if len(arg) == 0:
            print(f'Usage: {name} <?,min,max,off,angle,length>')
            return

        if arg == '?':
            try:
                v = self.roboarm.get(name)
                v = v if len(v) else 'off'
                print(v)
            except Exception as e:
                print(e.message)
        else:
            try:
                to = parse_actuator_state(arg)
            except ValueError:
                print('Error: Actuator state must be a floating point number, min, max, or off')
                return
            else:
                try:
                    self.roboarm.set(name, to)
                except Exception as e:
                    print(e.message)


    def emptyline(self):
        pass

    def do_hand(self, arg):
        'Get or set the hand (clamp) actuator'
        self.prop('hand', arg)

    def do_torso(self, arg):
        'Get or set the torso actuator'
        self.prop('torso', arg)

    def do_shoulder(self, arg):
        'Get or set the shoulder actuator'
        self.prop('shoulder', arg)

    def do_elbow(self, arg):
        'Get or set the elbow actuator'
        self.prop('elbow', arg)

    def do_wrist_lr(self, arg):
        'Get or set the actuator that turns the wrist left or right'
        self.prop('wrist_lr', arg)

    def do_wrist_ud(self, arg):
        'Get or set the actuator that turns the wrist up or down'
        self.prop('wrist_ud', arg)

    def do_wakeup(self, arg):
        'Turn all acuators on and move the robot into a standby position'
        try:
            self.roboarm.wakeup()
        except Exception as e:
            print(e.message)

    def do_off(self, arg):
        'Turn all robot actuators off'
        try:
            self.roboarm.off()
        except Exception as e:
            print(e.message)

    def do_stop(self, arg):
        'Stop all pending movement tasks'
        try:
            self.roboarm.stop()
        except Exception as e:
            print(e.message)

    def do_listen(self, arg):
        'Activate the embedded Google Speech-to-Text module'
        try:
            self.stt.activate()
        except Exception as e:
            print(e.message)

    def do_sleep(self, arg):
        'Move the robot into a sleep position and turn off all actuators'
        try:
            self.roboarm.sleep()
            self.roboarm.off()
        except Exception as e:
            print(e.message)

    def do_move(self, arg):
        'Move selected actuator to the given position'
        args = arg.lower().strip().split()
        if len(args) < 2:
            print('Usage: move <actuator> <angle|length|min|max|off> [<speed>]')
            return

        opts = { 'block': GLib.Variant('b', False) }
        if len(args) == 3:
            try:
                speed = float(args[2])
            except ValueError:
                print('Error: Speed must be a number')
                return

            opts['speed'] = GLib.Variant('d', speed)

        try:
            to = parse_actuator_state(args[1])
        except ValueError:
            print('Error: Actuator state must be a number, min, max, or off')
            return
        else:
            try:
                self.roboarm.move(args[0], to, opts)
            except Exception as e:
                print(e.message)

    def do_reboot(self, arg):
        'Reboot the robot'
        os.system('sudo systemctl reboot')

    def do_exit(self, arg):
        'Exit Shaky Steve command shell'
        print('Bye!')
        return True

    def do_is_moving(self, arg):
        'Show whether the robot is moving'
        print('yes' if self.roboarm.moving else 'no')

    def do_is_active(self, arg):
        "Show whether any robot's actuators are active"
        print('yes' if self.roboarm.active else 'no')

    def do_EOF(self, arg):
        return self.do_exit(arg)


bus = SystemBus()
roboarm = bus.get(f'{dbus_prefix}.RoboArm')
stt = bus.get(f'{dbus_prefix}.SpeechToText')

logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
try:
    Shell(roboarm, stt).cmdloop()
except KeyboardInterrupt:
    pass
