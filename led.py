import logging
from collections import OrderedDict

import click
import board   # adafruit-blinka
import busio   # adafruit-blinka
from pydbus import SystemBus
import asyncio
import adafruit_tlc59711

from color import RGB, RGBA
from config import dbus_prefix
from animation import current_layer, blink, breathe
from utils import init_logging
from dbus import DBusAPI

log = logging.getLogger(__name__)

BUS_NAME = f'{dbus_prefix}.LED'

# This variable is used to generate unique layer IDs
layer_id = 0

# An ordered set of LED layers. Each layer is a list of four values: red, green,
# blue, alpha. All values are in the range from 0 to 1.
layers = OrderedDict()

# A dictionary per-layer animation tasks, keyed by layer id. Animations are
# optional. There is no need for constant layers to have an animation task.
animations = {}

# A reference to the layer that is used to indicate that the servos are moving.
# This layer exists if and only if at least one servo is moving.
moving_layer = None

# Indicates whether the Speech-to-Text module has the microphone active and
# whether voice activity has been detected.
stt_layer = None
stt_vad_layer = None

# A reference to the persistant layer that reflects whether or not any of the
# robot servos are turned on. This layer shows a "breathing" effect as long as
# at least one servo is on.
actuator_layer = None

old_active = None

asyncio_loop = asyncio.new_event_loop()
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
tlc = adafruit_tlc59711.TLC59711(spi, pixel_count=16)


def blend(dst, c):
    ia = 1 - c[3]
    dst[0] = c[3] * c[0] + ia * dst[0]
    dst[1] = c[3] * c[1] + ia * dst[1]
    dst[2] = c[3] * c[2] + ia * dst[2]


def update_leds():
    c = [0, 0, 0]
    for l in layers.values():
        blend(c, l)

    tlc.set_pixel_all(c)
    tlc.show()


async def led_updater(rate=100):
    while True:
        update_leds()
        await asyncio.sleep(1 / rate)


def add_layer(v=None, alpha=1.0):
    global layer_id
    id = layer_id
    layer_id += 1

    layers[id] = [0, 0, 0, alpha]
    if v is not None:
        update_layer(v, id)
    return id


def set_animation(layer_id, coro):
    remove_animation(layer_id)
    current_layer.set((layer_id, layers[layer_id], update_layer))
    animations[layer_id] = asyncio.run_coroutine_threadsafe(coro, asyncio_loop)


def remove_animation(layer_id):
    animation = animations.get(layer_id, None)
    if animation is not None:
        animation.cancel()
        del animations[layer_id]


def remove_layer(id):
    remove_animation(id)

    try:
        del layers[id]
    except KeyError:
        pass


def update_layer(v, id=None):
    if id is None:
        id, layer, _ = current_layer.get()
    else:
        layer = layers[id]

    if isinstance(v, RGB):
        layer[0] = v.r / 255
        layer[1] = v.g / 255
        layer[2] = v.b / 255
    elif isinstance(v, RGBA):
        layer[0] = v.r / 255
        layer[1] = v.g / 255
        layer[2] = v.b / 255
        layer[3] = v.alpha
    elif isinstance(v, list) or isinstance(v, tuple):
        if len(v) < 3:
            raise Exception('Invalid value, at least 3 items expected')

        layer[0] = v[0]
        layer[1] = v[1]
        layer[2] = v[2]

        if len(v) >= 4:
            layer[3] = v[3]

    elif asyncio.iscoroutine(v):
        set_animation(id, v)
    else:
        raise Exception('Bug: Unsupported value type')


def off():
    for layer in list(layers.keys()):
        remove_layer(layer)


class LEDDBusAPI(DBusAPI):
    def _invoke_coro(self, coro):
        f = asyncio.run_coroutine_threadsafe(coro, asyncio_loop)
        return f.result()

    def add_layer(self, opacity):
        return add_layer(opacity)

    def remove_layer(self, id):
        remove_layer(id)

    def off(self):
        off()


LEDDBusAPI.__doc__ = f'''
<node>
    <interface name='{BUS_NAME}'>
        <method name='off'></method>
        <method name='add_layer'>
            <arg type='d' name='red' direction='in'/>
            <arg type='d' name='green' direction='in'/>
            <arg type='d' name='blue' direction='in'/>
            <arg type='d' name='opacity' direction='in'/>
            <arg type='i' name='id' direction='out'/>
        </method>
        <method name='remove_layer'>
            <arg type='i' name='id' direction='in'/>
        </method>
    </interface>
</node>
'''


def sync_moving_layer(props):
    global moving_layer
    try:
        moving = props['moving']
    except KeyError:
        pass
    else:
        if moving:
            if moving_layer is None:
                moving_layer = add_layer(blink(RGB(255, 0, 0), 0.1))
        else:
            if moving_layer is not None:
                remove_layer(moving_layer)
                moving_layer = None


def sync_actuator_layer(props):
    global actuator_layer, old_active

    try:
        active = props['active']
    except KeyError:
        pass
    else:
        if old_active is None or old_active ^ active:
            old_active = active
            if active:
                update_layer(breathe(RGB(0, 64, 0), period=3, gamma=0.14), actuator_layer)
            else:
                update_layer(breathe(RGB(103, 46, 0), period=6, gamma=0.08), actuator_layer)


def on_roboarm_props_change(name, props, opts):
    sync_moving_layer(props)
    sync_actuator_layer(props)


def on_stt_props_change(name, props, opts):
    global stt_layer, stt_vad_layer
    try:
        active = props['active']
    except KeyError:
        pass
    else:
        if active:
            if stt_layer is None:
                stt_layer = add_layer(RGB(0, 0, 255))
        else:
            if stt_layer is not None:
                remove_layer(stt_layer)
                stt_layer = None

    try:
        voice_activity = props['voice_activity']
    except KeyError:
        pass
    else:
        if voice_activity:
            if stt_vad_layer is None:
                stt_vad_layer = add_layer(blink(RGB(0, 0, 127), 0.1))
        else:
            if stt_vad_layer is not None:
                remove_layer(stt_vad_layer)
                stt_vad_layer = None


@click.command()
@click.option('--verbose', '-v', envvar='VERBOSE', count=True, help='Increase logging verbosity')
def main(verbose):
    global actuator_layer

    init_logging(verbose)

    updater = asyncio_loop.create_task(led_updater())
    actuator_layer = add_layer(breathe(RGB(103, 46, 0), period=6, gamma=0.08))

    bus = SystemBus()

    roboarm = bus.get(f'{dbus_prefix}.RoboArm')
    roboarm['org.freedesktop.DBus.Properties'].onPropertiesChanged = on_roboarm_props_change

    stt = bus.get(f'{dbus_prefix}.SpeechToText')
    stt['org.freedesktop.DBus.Properties'].onPropertiesChanged = on_stt_props_change

    sync_moving_layer({ 'moving': roboarm.moving })
    sync_actuator_layer({ 'active': roboarm.active })

    api = LEDDBusAPI(BUS_NAME)
    try:
        api.start()
        try:
            asyncio_loop.run_forever()
        finally:
            updater.cancel()
            asyncio_loop.stop()
    finally:
        api.quit()
        off()


if __name__ == '__main__':
    main()


