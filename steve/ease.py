from math import cos, pi, sin, pow, sqrt

# The following functions have been inspired by the easing functions over at
# https://easings.net

def in_sine(x):
    return 1 - cos((x * pi) / 2)

def out_sine(x):
    return sin((x * pi) / 2)

def in_out_sine(x):
    return -(cos(pi * x) - 1) / 2


def in_quad(x):
    return x * x

def out_quad(x):
    return 1 - (1 - x) * (1 - x)

def in_out_quad(x):
    if x < 0.5:
        return 2 * x * x
    else:
        return 1 - pow(-2 * x + 2, 2) / 2


def in_cubic(x):
    return x * x * x

def out_cubic(x):
    return 1 - pow(1 - x, 3)

def in_out_cubic(x):
    if x < 0.5:
        return 4 * x * x * x
    else:
        return 1 - pow(-2 * x + 2, 3) / 2


def in_quart(x):
    return x * x * x * x

def out_quart(x):
    return 1 - pow(1 - x, 4)

def in_out_quart(x):
    if x < 0.5:
        return 8 * x * x * x * x
    else:
        return 1 - pow(-2 * x + 2, 4) / 2


def in_quint(x):
    return x * x * x * x * x

def out_quint(x):
    return 1 - pow(1 - x, 5)

def in_out_quint(x):
    if x < 0.5:
        return 16 * x * x * x * x * x
    else:
        return 1 - pow(-2 * x + 2, 5) / 2


def in_expo(x):
    if x == 0:
        return 0
    else:
        return pow(2, 10 * x - 10)

def out_expo(x):
    if x == 1:
        return 1
    else:
        return 1 - pow(2, -10 * x)

def in_out_expo(x):
    if x == 0:
        return 0
    elif x == 1:
        return 1
    elif x < 0.5:
        return pow(2, 20 * x - 10) / 2
    else:
        return (2 - pow(2, -20 * x + 10)) / 2


def in_circ(x):
    return 1 - sqrt(1 - pow(x, 2))

def out_circ(x):
    return sqrt(1 - pow(x - 1, 2))

def in_out_circ(x):
    if x < 0.5:
        return (1 - sqrt(1 - pow(2 * x, 2))) / 2
    else:
        return (sqrt(1 - pow(-2 * x + 2, 2)) + 1) / 2


def in_back(x):
    c1 = 1.70158
    c3 = c1 + 1
    return c3 * x * x * x - c1 * x * x

def out_back(x):
    c1 = 1.70158
    c3 = c1 + 1

    return 1 + c3 * pow(x - 1, 3) + c1 * pow(x - 1, 2)

def in_out_back(x):
    c1 = 1.70158
    c2 = c1 * 1.525

    if x < 0.5:
        return (pow(2 * x, 2) * ((c2 + 1) * 2 * x - c2)) / 2
    else:
        return (pow(2 * x - 2, 2) * ((c2 + 1) * (x * 2 - 2) + c2) + 2) / 2


def in_elastic(x):
    c4 = (2 * pi) / 3

    if x == 0:
        return 0
    elif x == 1:
        return 1
    else:
        return -pow(2, 10 * x - 10) * sin((x * 10 - 10.75) * c4)

def out_elastic(x):
    c4 = (2 * pi) / 3

    if x == 0:
        return 0
    elif x == 1:
        return 1
    else:
        return pow(2, -10 * x) * sin((x * 10 - 0.75) * c4) + 1

def in_out_elastic(x):
    c5 = (2 * pi) / 4.5

    if x == 0:
        return 0
    elif x == 1:
        return 1
    elif x < 0.5:
        return -(pow(2, 20 * x - 10) * sin((20 * x - 11.125) * c5)) / 2
    else:
        return (pow(2, -20 * x + 10) * sin((20 * x - 11.125) * c5)) / 2 + 1


def in_bounce(x):
    return 1 - out_bounce(1 - x)

def out_bounce(x):
    n1 = 7.5625
    d1 = 2.75

    if x < 1 / d1:
        return n1 * x * x
    elif x < 2 / d1:
        x = x - 1.5
        return n1 * x / d1 * x + 0.75
    elif x < 2.5 / d1:
        x = x - 2.25
        return n1 * x / d1 * x + 0.9375
    else:
        x = x - 2.625
        return n1 * x / d1 * x + 0.984375

def in_out_bounce(x):
    if x < 0.5:
        return (1 - out_bounce(1 - 2 * x)) / 2
    else:
        return (1 + out_bounce(2 * x - 1)) / 2
