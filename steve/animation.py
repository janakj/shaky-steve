import math
import contextvars
from datetime import datetime, timedelta
from asyncio import sleep


# This variable is used to keep track of the current layer within animation
# tasks. That way, there is no need for the animation coroutine to accept the
# layer_id via its parameters. The value is a tuple where the first item is the
# ID of the layer and the second item is the layer's value (array)
current_layer = contextvars.ContextVar('Layer for current task')


async def transition(color, duration, ease=lambda v: v, rate=25):
    _, layer, update_layer = current_layer.get()

    # Initialize the layer to the given color and set the layer's opacity to the
    # start value of the easing function.

    update_layer(color)
    alpha = layer[3]
    layer[3] = alpha * ease(0)

    start = datetime.now()
    stop = start + timedelta(seconds=duration)

    while True:
        now = datetime.now()

        step = min((now - start).total_seconds() / duration, 1)
        layer[3] = alpha * ease(step)

        if now > stop: break
        await sleep(1 / rate)


async def blink(color, on_duration, off_duration=None):
    _, layer, update_layer = current_layer.get()

    if off_duration is None:
        off_duration = on_duration

    update_layer(color)
    alpha = layer[3]

    while True:
        layer[3] = alpha
        await sleep(on_duration)
        layer[3] = 0
        await sleep(off_duration)


# Inspired by: https://makersportal.com/blog/2020/3/27/simple-breathing-led-in-arduino

async def breathe(color, period=4, gamma=0.12, rate=60):
    _, layer, update_layer = current_layer.get()
    update_layer(color)

    r, g, b = layer[0], layer[1], layer[2]
    n = rate * period
    while True:
        for i in range(n):
            v = math.exp(-(pow((i / n - 0.5) / gamma, 2)) / 2)
            layer[0] = r * v
            layer[1] = g * v
            layer[2] = b * v
            await sleep(1 / rate)
