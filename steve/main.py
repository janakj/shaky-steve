import logging
import click
import logging
from time import sleep

from pydbus import SystemBus
from gi.repository import GLib

from steve.utils import init_logging
from steve.config import dbus_prefix

log = logging.getLogger(__name__)

roboarm = None


def high_five():
    opts = {
        'block': GLib.Variant('b', False),
        'speed': GLib.Variant('d', 1.0)
    }

    torso = roboarm.torso
    shoulder = roboarm.shoulder
    elbow = roboarm.elbow
    wrist_ud = roboarm.wrist_ud
    wrist_lr = roboarm.wrist_lr
    clamp = roboarm.clamp

    roboarm.move('torso', '-0.429', opts)
    roboarm.move('shoulder', '18.799', opts)
    roboarm.move('elbow', '61.7', opts)
    roboarm.move('wrist_ud', '-5.632', opts)
    roboarm.move('wrist_lr', '0.282', opts)
    roboarm.move('clamp', '0.03', opts)
    sleep(2)
    for i in range(5):
        roboarm.clamp = '0'
        sleep(0.2)
        roboarm.clamp = '0.03'
        sleep(0.2)

    roboarm.move('torso', torso, opts)
    roboarm.move('shoulder', shoulder, opts)
    roboarm.move('elbow', elbow, opts)
    roboarm.move('wrist_ud', wrist_ud, opts)
    roboarm.move('wrist_lr', wrist_lr, opts)
    roboarm.move('clamp', clamp, opts)


def on_utterance(text):
    text = text.strip().lower()
    print(f'Got utterance: "{text}"')
    if 'wake up' in text:
        roboarm.wakeup()
    elif 'sleep' in text:
        roboarm.sleep()
        roboarm.off()
    elif 'open' in text:
        roboarm.clamp = str(float('+inf'))
    elif 'close' in text:
        roboarm.clamp = str(float('-inf'))
    elif 'hi-5' in text or 'high 5' in text or 'hi 5' in text:
        high_five()


@click.command()
@click.option('--verbose', '-v', envvar='VERBOSE', count=True, help='Increase logging verbosity')
def main(verbose):
    init_logging(verbose)

    global roboarm
    bus = SystemBus()

    roboarm = bus.get(f'{dbus_prefix}.RoboArm')

    stt = bus.get(f'{dbus_prefix}.SpeechToText')
    stt.onUtterance = on_utterance

    loop = GLib.MainLoop()
    loop.run()


if __name__ == '__main__':
    main()
