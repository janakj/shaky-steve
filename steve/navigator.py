import logging
from contextlib import suppress

import steve.spnav as spnav
import click
from gi.repository import GLib
from pydbus import SystemBus

from steve.config import dbus_prefix
from steve.utils import init_logging

log = logging.getLogger(__name__)

MIN = str(float('-inf'))
MAX = str(float('+inf'))


def print_dev_info():
    proto = spnav.protocol()
    log.debug(f'Using spacenavd AF_UNIX protocol version {proto}')

    if proto >= 1:
        log.debug(f'Found {spnav.dev_name()} at {spnav.dev_path()} with {spnav.dev_axes()} axes and {spnav.dev_buttons()} buttons')


def _move(name, value, speed=1, deadband=0.4):
    if abs(value) <= deadband: value = 0

    if   value < 0 : to = MIN
    elif value > 0 : to = MAX
    elif value == 0: to = ''
    else: to = str(value)

    roboarm.move(name, to, {
        'block': GLib.Variant('b', False),
        'speed': GLib.Variant('d', speed * abs(value))
    })


def hand(state):
    roboarm.move('hand', MIN if state else MAX, {
        'block': GLib.Variant('b', False),
        'speed': GLib.Variant('d', 0.1)
    })

def wrist_ud(v): return _move('wrist_ud', v, speed=2.5)
def wrist_lr(v): return _move('wrist_lr', v, deadband=0.5, speed=2)
def elbow(v):    return _move('elbow', v, speed=2)
def shoulder(v): return _move('shoulder', v, speed=2)
def torso(v):    return _move('torso', v, speed=2.5)


bus = SystemBus()
roboarm = bus.get(f'{dbus_prefix}.RoboArm')
stt = bus.get(f'{dbus_prefix}.SpeechToText')


def main_loop():
    try:
        spnav.dev_type()
    except spnav.SpnavError:
        log.info('No device found, exiting')
        return

    spnav.client_name('steve')
    print_dev_info()

    old = [ 0 ] * 6
    while True:
        event = spnav.wait_event()
        if event is None: break
        type_ = spnav.EventType(event.type)
        if  type_ == spnav.EventType.MOTION:
            v = [
                round(event.motion.x / 350, 1),
                round(event.motion.y / 350, 1),
                round(event.motion.z / 350, 1),
                round(event.motion.rx / 350, 1),
                round(event.motion.ry / 350, 1),
                round(event.motion.rz / 350, 1)]
            if old[1] != v[1]: elbow(v[1])
            if old[2] != v[2]: shoulder(-v[2])
            if old[3] != v[3]: wrist_ud(v[3])
            if old[4] != v[4]: torso(-v[4])
            if old[5] != v[5]: wrist_lr(v[5])
            old = v
        elif type_ == spnav.EventType.BUTTON:
            if event.button.bnum == 0:
                hand(event.button.press == 1)
            if event.button.bnum == 1:
                if event.button.press == 1:
                    stt.toggle()
        elif type_ == spnav.EventType.DEV:
            if event.dev.op == spnav.ActionType.DEV_RM.value:
                log.info('Device removed, terminating')
                break


@click.command()
@click.option('--verbose', '-v', envvar='VERBOSE', count=True, help='Increase logging verbosity')
def main(verbose):
    init_logging(verbose)

    try:
        spnav.open()
        main_loop()
    finally:
        with suppress(Exception):
            spnav.close()


if __name__ == "__main__":
    main()
