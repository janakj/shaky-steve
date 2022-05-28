from enum import Enum, unique, auto
from typing import List
from ctypes import *


class SpnavError(Exception):
    def __init__(self, message, errno):
        super().__init__(message)
        self.errno = errno


class CLangEnum(Enum):
    def _generate_next_value_(name, start, count, last_values):
        if len(last_values) == 0: return 0
        return last_values[-1] + 1


@unique
class EventType(CLangEnum):
    ANY       = auto()
    MOTION    = auto()
    BUTTON    = auto()
    DEV       = auto()
    CFG       = auto()
    RAWAXIS   = auto()
    RAWBUTTON = auto()


@unique
class ActionType(CLangEnum):
    DEV_ADD = auto()
    DEV_RM  = auto()


@unique
class EventMask(CLangEnum):
    MOTION    = 0x01
    BUTTON    = 0x02
    DEV       = 0x04
    CFG       = 0x08
    RAWAXIS   = 0x10
    RAWBUTTON = 0x20
    INPUT     = MOTION | BUTTON
    DEFAULT   = INPUT | DEV
    ALL       = 0xffff


@unique
class DeviceType(CLangEnum):
    UNKNOWN   = auto()
    SB2003    = 0x100
    SB3003    = auto()
    SB4000    = auto()
    SM        = auto()
    SM5000    = auto()
    SMCADMAN  = auto()
    PLUSXT    = 0x200
    CADMAN    = auto()
    SMCLASSIC = auto()
    SB5000    = auto()
    STRAVEL   = auto()
    SPILOT    = auto()
    SNAV      = auto()
    SEXP      = auto()
    SNAVNB    = auto()
    SPILOTPRO = auto()
    SMPRO     = auto()
    NULOOQ    = auto()
    SMW       = auto()
    SMPROW    = auto()
    SMENT     = auto()
    SMCOMP    = auto()
    SMMOD     = auto()


@unique
class LEDConfig(CLangEnum):
    OFF = auto()
    ON  = auto()
    AUTO = auto()


@unique
class ButtonAction(CLangEnum):
    NONE          = auto()
    SENS_RESET    = auto()
    SENS_INC      = auto()
    SENS_DEC      = auto()
    DISABLE_ROT   = auto()
    DISABLE_TRANS = auto()
    MAX           = auto()


class MotionEvent(Structure):
    _fields_ = [
        ('type', c_int),
        ('x', c_int),
        ('y', c_int),
        ('z', c_int),
        ('rx', c_int),
        ('ry', c_int),
        ('rz', c_int),
        ('period', c_uint),
        ('data', POINTER(c_int))]


class ButtonEvent(Structure):
    _fields_ = [
        ('type', c_int),
        ('press', c_int),
        ('bnum', c_int)]


class DevEvent(Structure):
    _fields_ = [
        ('type', c_int),
        ('op', c_int),
        ('id', c_int),
        ('devtype', c_int),
        ('usbhid', c_int * 2)]


class CfgEvent(Structure):
    _fields_ = [
        ('type', c_int),
        ('cfg', c_int),
        ('data', c_int * 6)]


class AxisEvent(Structure):
    _fields_ = [
        ('type', c_int),
        ('idx', c_int),
        ('value', c_int)]


class Event(Union):
    _fields_ = [
        ('type', c_int),
        ('motion', MotionEvent),
        ('button', ButtonEvent),
        ('dev', DevEvent),
        ('cfg', CfgEvent),
        ('axis', AxisEvent)]


class PosRot(Structure):
    _fields_ = [
        ('pos', c_float * 3),
        ('rot', c_float * 4)]


lib = CDLL("libspnav.so.0")


def open():
    rc = lib.spnav_open()
    if rc < 0:
        raise SpnavError('Error in spnav_open', rc)


def close():
    rc = lib.spnav_close()
    if rc < 0:
        raise SpnavError('Error in spnav_close', rc)


fd = lib.spnav_fd


def sensitivity(sens: float):
    rc = lib.spnav_sensitivity(c_double(sens))
    if rc < 0:
        raise SpnavError('Error in spnav_sensitivity', rc)


def wait_event() -> Event:
    event = Event()
    if lib.spnav_wait_event(pointer(event)) == 0:
        raise SpnavError('Error in spnav_wait_event', 0)
    return event


def poll_event() -> Event | None:
    event = Event()
    if lib.spnav_poll_event(pointer(event)) == 0:
        return None
    return event


def remove_events(type_: int) -> int:
    return lib.spnav_remove_events(c_int(type_))


def protocol() -> int:
    rc = lib.spnav_protocol()
    if rc == -1:
        raise SpnavError('Error in spnav_protocol', rc)
    return rc


def client_name(name: str):
    rc = lib.spnav_client_name(c_char_p(name.encode('ascii')))
    if rc < 0:
        raise SpnavError('Error in spnav_client_name', rc)


def evmask(mask: int):
    rc = lib.spnav_evmask(c_uint(mask))
    if rc < 0:
        raise SpnavError('Error in spnav_evmask', rc)


def dev_name() -> str:
    size = 256
    buf = create_string_buffer(b'\000' * size)

    rc = lib.spnav_dev_name(buf, sizeof(buf))
    if rc >= size:
        raise SpnavError('Buffer too small', rc)

    return buf.value.decode('ascii')


def dev_path() -> str:
    size = 256
    buf = create_string_buffer(b'\000' * size)

    rc = lib.spnav_dev_path(buf, sizeof(buf))
    if rc >= size:
        raise SpnavError('Buffer too small', rc)

    return buf.value.decode('ascii')


dev_buttons = lib.spnav_dev_buttons


dev_axes = lib.spnav_dev_axes


def dev_usbhid() -> tuple[int, int]:
    vend = c_int()
    prod = c_int()

    rc = lib.spnav_dev_usbhid(pointer(vend), pointer(prod))
    if rc < 0:
        raise SpnavError("Error in spnav_dev_usbhid", rc)

    return (vend.value, prod.value)


def dev_type() -> DeviceType:
    rc = lib.spnav_dev_type()
    if rc < 0:
        raise SpnavError('Error in spnav_dev_type', rc)

    return DeviceType(rc)


def posrot_init(pr: PosRot):
    lib.spnav_posrot_init(pointer(pr))


def posrot_moveobj(pr: PosRot, ev: MotionEvent):
    lib.spnav_posrot_moveobj(pointer(pr), pointer(ev))


def posrot_moveview(pr: PosRot, ev: MotionEvent):
    lib.spnav_posrot_moveview(pointer(pr), pointer(ev))


def matrix_obj(pr: PosRot) -> list[float]:
    mat = (c_float * 16)()
    lib.spnav_matrix_obj(pointer(mat), pointer(pr))
    return [mat[i] for i in range(len(mat))]


def matrix_view(pr: PosRot) -> list[float]:
    mat = (c_float * 16)()
    lib.spnav_matrix_view(pointer(mat), pointer(pr))
    return [mat[i] for i in range(len(mat))]


def cfg_reset():
    rc = lib.spnav_cfg_reset()
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_reset', rc)


def cfg_restore():
    rc = lib.spnav_cfg_restore()
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_restore', rc)


def cfg_save():
    rc = lib.spnav_cfg_save()
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_save', rc)


def cfg_set_sens(s: float):
    rc = lib.spnav_cfg_set_senv(s)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_senv', rc)


cfg_get_sens = lib.spnav_cfg_get_sens
cfg_get_sens.restype = c_float


def cfg_set_axis_sens(svec: list[float]):
    if len(svec) != 6:
        raise ValueError('Parameter length must be 6')

    val = (c_float * 6)(*svec)
    rc = lib.spnav_cfg_set_axis_sens(pointer(val))
    if rc < 0:
        raise SpnavError('Error in spnav_set_axis_sens', rc)


def cfg_get_axis_sens() -> list[float]:
    val = (c_float * 6)()
    rc = lib.spnav_get_axis_sens(pointer(val))
    if rc < 0:
        raise SpnavError('Error in spnav_get_axis_sens', rc)
    return [val[i] for i in range(len(val))]


def cfg_set_deadzone(devaxis: int, delta: int):
    rc = lib.spnav_cfg_set_deadzone(devaxis, delta)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_deadzone', rc)


def cfg_get_deadzone(devaxis: int) -> int:
    v = lib.spnav_cfg_get_deadzone(devaxis)
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_deadzone', v)
    return v


# Set the axis invert state
# 0: normal, 1: inverted. order: MSB [ ... RZ|RY|RX|TZ|TY|TX] LSB
# cfgfile options: invert-trans, invert-rot

def cfg_set_invert(invbits: int):
    rc = lib.spnav_cfg_set_invert(invbits)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_invert', rc)


def cfg_get_invert() -> int:
    v = lib.spnav_cfg_get_invert()
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_invert', v)
    return v


def cfg_set_axismap(devaxis: int, map: int):
    rc = lib.spnav_cfg_set_axismap(devaxis, map)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_axismap', rc)


def cfg_get_axismap(devaxis: int) -> int:
    v = lib.spnav_cfg_get_axismap(devaxis)
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_axismap', v)
    return v


def cfg_set_bnmap(devbn: int, map: int):
    rc = lib.spnav_cfg_set_bnmap(devbn, map)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_bnmap', rc)


def cfg_get_bnmap(devbn: int) -> int:
    v = lib.spnav_cfg_get_axismap(devbn)
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_bnmap', v)
    return v


def cfg_set_bnaction(devbn: int, act: int):
    rc = lib.spnav_cfg_set_bnaction(devbn, act)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_bnaction', rc)


def cfg_get_bnaction(devbn: int) -> int:
    v = lib.spnav_cfg_get_bnaction(devbn)
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_bnaction', v)
    return v


def cfg_set_kbmap(devbn: int, key: int):
    rc = lib.spnav_cfg_set_kbmap(devbn, key)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_kbmap', rc)


def cfg_get_kbmap(devbn: int) -> int:
    v = lib.spnav_cfg_get_kbmap(devbn)
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_kbmap', v)
    return v


def cfg_set_swapyz(swap: int):
    rc = lib.spnav_cfg_set_swapyz(swap)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_swapyz', rc)


def cfg_get_swapyz() -> int:
    v = lib.spnav_cfg_get_swapyz()
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_swapyz', v)
    return v


def cfg_set_led(state: int):
    rc = lib.spnav_cfg_set_led(state)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_led', rc)


def cfg_get_led() -> int:
    v = lib.spnav_cfg_get_led()
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_led', v)
    return v


def cfg_set_grab(state: int):
    rc = lib.spnav_cfg_set_grab(state)
    if rc < 0:
        raise SpnavError('Error in spnav_cfg_set_grab', rc)


def cfg_get_grab() -> int:
    v = lib.spnav_cfg_get_grab()
    if v == -1:
        raise SpnavError('Error in spnav_cfg_get_grab', v)
    return v


def cfg_set_serial(name: str):
    rc = lib.spnav_cfg_set_serial(c_char_p(name.encode('ascii')))
    if rc < 0:
        raise SpnavError('Error in spnav_set_serial', rc)


def cfg_get_serial() -> str:
    size = 512
    buf = create_string_buffer(b'\000' * size)

    rc = lib.spnav_cfg_get_serial(buf, sizeof(buf))
    if rc >= size:
        raise SpnavError('Buffer too small', rc)

    return buf.value.decode('ascii')
