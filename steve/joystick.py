import os
import logging

import click
import pygame
from gi.repository import GLib
from pydbus import SystemBus

from steve.config import dbus_prefix
from steve.utils import init_logging

log = logging.getLogger(__name__)

os.environ["SDL_VIDEODRIVER"] = "dummy"

MIN = str(float('-inf'))
MAX = str(float('+inf'))

buttons = [None] * 12
axes = [ None ] * 4


def hand(state):
    v = MIN if state else MAX
    roboarm.move('hand', v, {
        'speed': GLib.Variant('d', 0.1),
        'block': GLib.Variant('b', False)
    })

def _move(name, value, speed=1, deadband=0.1):
    if abs(value) <= deadband: value = 0

    if   value < 0 : to = MIN
    elif value > 0 : to = MAX
    elif value == 0: to = ''

    roboarm.move(name, to, {
        'block': GLib.Variant('b', False),
        'speed': GLib.Variant('d', speed * abs(value))
    })

def wrist_ud(v): return _move('wrist_ud', v, speed=2.5)
def wrist_lr(v): return _move('wrist_lr', v, speed=4)
def elbow(v):    return _move('elbow', v, speed=2)
def shoulder(v): return _move('shoulder', v, speed=2)
def torso(v):    return _move('torso', v, speed=2.5)

buttons[6] = lambda v: roboarm.sleep()
buttons[7] = lambda v: roboarm.wakeup()

buttons[0] = hand
axes[2] = torso
axes[1] = shoulder
#axes[1] = wrist_ud
axes[0] = wrist_lr


@click.command()
@click.option('--verbose', '-v', envvar='VERBOSE', count=True, help='Increase logging verbosity')
def main(verbose):
    global roboarm

    init_logging(verbose)

    bus = SystemBus()
    roboarm = bus.get(f'{dbus_prefix}.RoboArm')

    pygame.init()
    pygame.joystick.init()
    try:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()

        log.debug("Axes: {}".format(joystick.get_numaxes()))
        log.debug("Buttons: {}".format(joystick.get_numbuttons()))

        axes_last = [ 0 ] * 4

        while True:
            event = pygame.event.wait()
            if event.type == pygame.JOYAXISMOTION:
                if axes[event.axis] is not None:
                    v = round(event.value, 1)
                    if axes_last[event.axis] != v:
                        axes[event.axis](v)
                        axes_last[event.axis] = v
            elif event.type == pygame.JOYBUTTONDOWN:
                if buttons[event.button] is not None:
                    buttons[event.button](True)
            elif event.type == pygame.JOYBUTTONUP:
                if buttons[event.button] is not None:
                    buttons[event.button](False)
            elif event.type == pygame.JOYHATMOTION:
                pass
    finally:
        pygame.joystick.quit()
        pygame.quit()


if __name__ == '__main__':
    main()
