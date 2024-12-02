from collections import namedtuple


RGB  = namedtuple('RGB', 'r g b')
RGBA = namedtuple('RGBA', 'r g b alpha')
HSL  = namedtuple('HSL', 'h s l')
PQT  = namedtuple('PQT', 'p q t')


color = {
    'lightRed'      : RGB(239,  41,  41),
    'red'           : RGB(204,   0,   0),
    'darkRed'       : RGB(164,   0,   0),
    'lightOrange'   : RGB(252, 175,  62),
    'orange'        : RGB(245, 121,   0),
    'darkOrange'    : RGB(206,  92,   0),
    'lightYellow'   : RGB(255, 233,  79),
    'yellow'        : RGB(237, 212,   0),
    'darkYellow'    : RGB(196, 160,   0),
    'lightGreen'    : RGB(138, 226,  52),
    'green'         : RGB(115, 210,  22),
    'darkGreen'     : RGB( 78, 154,   6),
    'lightBlue'     : RGB(114, 159, 207),
    'blue'          : RGB( 52, 101, 164),
    'darkBlue'      : RGB( 32,  74, 135),
    'lightPurple'   : RGB(173, 127, 168),
    'purple'        : RGB(117,  80, 123),
    'darkPurple'    : RGB( 92,  53, 102),
    'lightBrown'    : RGB(233, 185, 110),
    'brown'         : RGB(193, 125,  17),
    'darkBrown'     : RGB(143,  89,   2),
    'black'         : RGB(  0,   0,   0),
    'white'         : RGB(255, 255, 255),
    'lightGrey'     : RGB(238, 238, 236),
    'grey'          : RGB(211, 215, 207),
    'darkGrey'      : RGB(186, 189, 182),
    'lightGray'     : RGB(238, 238, 236),
    'lightCharcoal' : RGB(136, 138, 133),
    'charcoal'      : RGB( 85,  87,  83),
    'darkCharcoal'  : RGB( 46,  52,  54)
}


# Convert the given RGB color into an array of hue, saturation, and lightness
# values.
def rgb_to_hsl(rgb: RGB) -> HSL:
    r = rgb.r / 255
    g = rgb.g / 255
    b = rgb.b / 255

    high = max(r, g, b)
    low = min(r, g, b)
    l = (high + low) / 2

    if high == low:
        h = s = 0.0
    else:
        d = high - low
        s = d / (2 - high - low) if l > 0.5 else d / (high + low)

        if high == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif high == g:
            h = (b - r) / d + 2
        elif high == b:
            h = (r - g) / d + 4
        else:
            raise Exception('Bug in rgb_to_hsl')

        h /= 6

    return HSL(h, s, l)


def hue_to_rgb(pqt: PQT) -> float:
    p = pqt.p
    q = pqt.q
    t = pqt.t

    if t < 0: t += 1
    if t > 1: t -= 1
    if t < 1 / 6: return p + (q - p) * 6 * t
    if t < 1 / 2: return q
    if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
    return p


# Convert the given HSL color into an array of red, green, and blue values.
def hsl_to_rgb(hsl: HSL) -> RGB:
    if hsl.s == 0:
        r = g = b = hsl.l
    else:
        if hsl.l < 0.5:
            q = hsl.l * (1 + hsl.s)
        else:
            q = hsl.l + hsl.s - hsl.l * hsl.s

        p = 2 * hsl.l - q
        r = hue_to_rgb(PQT(p, q, hsl.h + 1 / 3))
        g = hue_to_rgb(PQT(p, q, hsl.h))
        b = hue_to_rgb(PQT(p, q, hsl.h - 1 / 3))

    return RGB(round(r * 255), round(g * 255), round(b * 255))


# Scale the given value into a range (min, max)
def scale(minimum: float, maximum: float, val: float):
    return (maximum - minimum) * val + minimum


# Dim the RGB color by the given ratio. Ratio 0 means completely dark, ratio 1.0
# would return the color unmodified.
def dim(rgb: RGB, ratio: float):
    hsl = rgb_to_hsl(rgb)
    return hsl_to_rgb(HSL(hsl.h, hsl.s, scale(0.15, hsl.l, ratio)))


def blend(dst: RGB, src: RGBA):
    ia = 1 - src.alpha
    dst.r = src.alpha * src.r + ia * dst.r
    dst.g = src.alpha * src.g + ia * dst.g
    dst.b = src.alpha * src.b + ia * dst.b


def rgb_to_float(src: RGB | RGBA):
    if isinstance(src, RGB):
        return RGB(src.r / 255, src.g / 255, src.b / 255)
    elif isinstance(src, RGBA):
        return RGBA(src.r / 255, src.g / 255, src.b / 255, src.alpha)
    else:
        raise Exception('Unsupported source value type')


def rgb_to_css(rgb: RGB) -> str:
    return f'#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}'
