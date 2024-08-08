import logging
from pydbus import SystemBus
from gi.repository import GLib
from config import dbus_prefix, verbose
from time import sleep

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
    hand = roboarm.hand

    roboarm.move('torso', '-0.429', opts)
    roboarm.move('shoulder', '18.799', opts)
    roboarm.move('elbow', '61.7', opts)
    roboarm.move('wrist_ud', '-5.632', opts)
    roboarm.move('wrist_lr', '0.282', opts)
    roboarm.move('hand', '0.03', opts)
    sleep(2)
    for i in range(5):
        roboarm.hand = '0'
        sleep(0.2)
        roboarm.hand = '0.03'
        sleep(0.2)

    roboarm.move('torso', torso, opts)
    roboarm.move('shoulder', shoulder, opts)
    roboarm.move('elbow', elbow, opts)
    roboarm.move('wrist_ud', wrist_ud, opts)
    roboarm.move('wrist_lr', wrist_lr, opts)
    roboarm.move('hand', hand, opts)


def on_utterance(text):
    text = text.strip().lower()
    print(f'Got utterance: "{text}"')
    if 'wake up' in text:
        roboarm.wakeup()
    elif 'sleep' in text:
        roboarm.sleep()
        roboarm.off()
    elif 'open' in text:
        roboarm.hand = str(float('+inf'))
    elif 'close' in text:
        roboarm.hand = str(float('-inf'))
    elif 'Hi-5' in text:
        high_five()


def main():
    global roboarm
    bus = SystemBus()

    roboarm = bus.get(f'{dbus_prefix}.RoboArm')

    stt = bus.get(f'{dbus_prefix}.SpeechToText')
    stt.onUtterance = on_utterance

    loop = GLib.MainLoop()
    loop.run()


logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
if __name__ == '__main__':
    main()
