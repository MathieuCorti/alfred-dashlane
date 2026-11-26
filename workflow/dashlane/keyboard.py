"""Type text into the frontmost app with Quartz keyboard events.

Each character is sent as a Unicode string instead of a key code, so the
keyboard layout (AZERTY, QWERTZ…) doesn't matter and any character can be
typed, accents and symbols included. Events come from a private event source
with no modifier flags, so a modifier key still held down (such as the ⇧ of
⇧↩) can't change what is typed. Nothing goes through the clipboard.
"""

import ctypes
import time

_cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
_cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

_cg.CGPreflightPostEventAccess.restype = ctypes.c_bool
_cg.CGEventSourceFlagsState.restype = ctypes.c_uint64
_cg.CGEventSourceFlagsState.argtypes = [ctypes.c_int32]
_cg.CGEventSourceCreate.restype = ctypes.c_void_p
_cg.CGEventSourceCreate.argtypes = [ctypes.c_int32]
_cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
_cg.CGEventKeyboardSetUnicodeString.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_uint16)]
_cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_cf.CFRelease.argtypes = [ctypes.c_void_p]

PRIVATE_STATE = -1  # kCGEventSourceStatePrivate
HID_STATE = 1  # kCGEventSourceStateHIDSystemState
HID_TAP = 0  # kCGHIDEventTap
# Shift, Control, Option, Command.
MODIFIERS = 0x20000 | 0x40000 | 0x80000 | 0x100000

TAB = 48
RETURN = 36
CHARACTER_DELAY = 0.008


def can_post():
    """True when this process (through Alfred) may send keyboard events."""
    return bool(_cg.CGPreflightPostEventAccess())


def wait_for_modifiers_release(timeout=2.0):
    """Wait until ⇧ ⌃ ⌥ ⌘ are all released, so typing starts once the user lets go."""
    deadline = time.monotonic() + timeout
    while _cg.CGEventSourceFlagsState(HID_STATE) & MODIFIERS and time.monotonic() < deadline:
        time.sleep(0.02)


class Keyboard:
    def __init__(self):
        self.source = _cg.CGEventSourceCreate(PRIVATE_STATE)

    def close(self):
        if self.source:
            _cf.CFRelease(self.source)
            self.source = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _post(self, key_code, units=None):
        for down in (True, False):
            event = _cg.CGEventCreateKeyboardEvent(self.source, key_code, down)
            if not event:
                raise RuntimeError("Could not create a keyboard event")
            try:
                _cg.CGEventSetFlags(event, 0)
                if units:
                    buffer = (ctypes.c_uint16 * len(units))(*units)
                    _cg.CGEventKeyboardSetUnicodeString(event, len(units), buffer)
                _cg.CGEventPost(HID_TAP, event)
            finally:
                _cf.CFRelease(event)

    def type_text(self, text):
        for character in text:
            data = character.encode("utf-16-le")
            units = [int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)]
            self._post(0, units)
            time.sleep(CHARACTER_DELAY)

    def press(self, key_code):
        self._post(key_code)
        time.sleep(CHARACTER_DELAY)
