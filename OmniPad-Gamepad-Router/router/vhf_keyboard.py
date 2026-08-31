"""Native OmniPad VHF keyboard bridge.

The Python host communicates with the OmniPad Virtual Keyboard KMDF/VHF source driver
via standard buffered IOCTL. The driver publishes a real second HID keyboard device to
Windows; it does not filter or capture the physical keyboard.
"""

import ctypes
from ctypes import wintypes
import logging
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("OmniPad.VHFKeyboard")

IS_WINDOWS = hasattr(ctypes, "windll")

# HID keyboard usage IDs for Keyboard/Keypad usage page (0x07).
_DOM_CODE_TO_HID: Dict[str, int] = {
    # Letters (A-Z -> 0x04-0x1D)
    **{f"Key{chr(65+i)}": 0x04 + i for i in range(26)},
    # Digits (1-9 -> 0x1E-0x26, 0 -> 0x27)
    **{f"Digit{i}": (0x27 if i == 0 else 0x1D + i) for i in range(10)},
    # Standard Controls
    "Enter": 0x28, "Escape": 0x29, "Backspace": 0x2A, "Tab": 0x2B, "Space": 0x2C,
    "Minus": 0x2D, "Equal": 0x2E, "BracketLeft": 0x2F, "BracketRight": 0x30,
    "Backslash": 0x31, "NonUSHash": 0x32, "Semicolon": 0x33, "Quote": 0x34,
    "Backquote": 0x35, "Comma": 0x36, "Period": 0x37, "Slash": 0x38,
    "CapsLock": 0x39,
    # Function Keys (F1-F24)
    **{f"F{i}": 0x3A + (i - 1) for i in range(1, 13)},
    **{f"F{i}": 0x68 + (i - 13) for i in range(13, 25)},
    # Navigation & Edit
    "PrintScreen": 0x46, "ScrollLock": 0x47, "Pause": 0x48,
    "Insert": 0x49, "Home": 0x4A, "PageUp": 0x4B, "Delete": 0x4C,
    "End": 0x4D, "PageDown": 0x4E, "ArrowRight": 0x4F, "ArrowLeft": 0x50,
    "ArrowDown": 0x51, "ArrowUp": 0x52, "ContextMenu": 0x65,
    # Keypad / Numpad
    "NumLock": 0x53, "NumpadDivide": 0x54, "NumpadMultiply": 0x55, "NumpadSubtract": 0x56,
    "NumpadAdd": 0x57, "NumpadEnter": 0x58,
    "Numpad1": 0x59, "Numpad2": 0x5A, "Numpad3": 0x5B, "Numpad4": 0x5C,
    "Numpad5": 0x5D, "Numpad6": 0x5E, "Numpad7": 0x5F, "Numpad8": 0x60,
    "Numpad9": 0x61, "Numpad0": 0x62, "NumpadDecimal": 0x63,
    "NumpadEqual": 0x67, "NumpadComma": 0x85,
    # International & Extended Keys
    "IntlBackslash": 0x64, "IntlRo": 0x87, "IntlYen": 0x89,
    "KanaMode": 0x88, "Convert": 0x8A, "NonConvert": 0x8B,
    "Lang1": 0x90, "Lang2": 0x91, "Lang3": 0x92, "Lang4": 0x93, "Lang5": 0x94,
    # Media & App Controls
    "AudioVolumeMute": 0x7F, "AudioVolumeUp": 0x80, "AudioVolumeDown": 0x81,
    # Modifier keys -> 0xE0-0xE7
    "ControlLeft": 0xE0, "ShiftLeft": 0xE1, "AltLeft": 0xE2, "MetaLeft": 0xE3, "OSLeft": 0xE3,
    "ControlRight": 0xE4, "ShiftRight": 0xE5, "AltRight": 0xE6, "MetaRight": 0xE7, "OSRight": 0xE7,
    "AltGraph": 0xE6,
}

# Modifier bit masks (USB HID standard)
_MODIFIER_BITS: Dict[int, int] = {
    0xE0: 1 << 0,  # Left Control
    0xE1: 1 << 1,  # Left Shift
    0xE2: 1 << 2,  # Left Alt
    0xE3: 1 << 3,  # Left GUI (Meta / Win)
    0xE4: 1 << 4,  # Right Control
    0xE5: 1 << 5,  # Right Shift
    0xE6: 1 << 6,  # Right Alt
    0xE7: 1 << 7,  # Right GUI (Meta / Win)
}

# Primary IOCTL: CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS) = 0x00222004
IOCTL_OMNIPAD_SET_KEYBOARD_REPORT = 0x00222004
# Legacy IOCTL: CTL_CODE(FILE_DEVICE_KEYBOARD, 0x800, METHOD_BUFFERED, FILE_WRITE_DATA) = 0x000B2000
IOCTL_OMNIPAD_LEGACY_KEYBOARD_REPORT = 0x000B2000

DEVICE_PATHS = [
    r"\\.\OmniPadVirtualKeyboard",
    r"\\.\OmniPadKbd0"
]
REPORT_SIZE = 8
MAX_KEYS = 6


def dom_code_to_hid_usage(code: Any) -> Optional[int]:
    """Translate browser KeyboardEvent.code to a USB HID keyboard usage."""
    return _DOM_CODE_TO_HID.get(str(code or "").strip())


def build_keyboard_report(codes: Iterable[str]) -> bytes:
    """Build an 8-byte boot keyboard report from DOM KeyboardEvent.code values."""
    modifiers = 0
    keys: List[int] = []
    seen: Set[int] = set()

    for raw_code in codes:
        usage = dom_code_to_hid_usage(raw_code)
        if usage is None:
            continue
        if usage in _MODIFIER_BITS:
            modifiers |= _MODIFIER_BITS[usage]
            continue
        if usage not in seen and len(keys) < MAX_KEYS:
            seen.add(usage)
            keys.append(usage)

    return bytes([modifiers, 0, *keys, *([0] * (MAX_KEYS - len(keys)))])


class VHFKeyboardDevice:
    """User-mode handle for the OmniPad virtual keyboard source driver."""

    def __init__(self, device_path: Optional[str] = None) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("OmniPad VHF keyboard is Windows-only.")

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._CreateFileW = kernel32.CreateFileW
        self._CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        self._CreateFileW.restype = wintypes.HANDLE

        self._DeviceIoControl = kernel32.DeviceIoControl
        self._DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
        ]
        self._DeviceIoControl.restype = wintypes.BOOL

        self._CloseHandle = kernel32.CloseHandle
        self._CloseHandle.argtypes = [wintypes.HANDLE]
        self._CloseHandle.restype = wintypes.BOOL

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

        paths_to_try = [device_path] if device_path else DEVICE_PATHS
        self._handle = None
        self._active_path = None
        self._active_ioctl = IOCTL_OMNIPAD_SET_KEYBOARD_REPORT

        last_error = 0
        for path in paths_to_try:
            if not path:
                continue
            h = self._CreateFileW(
                path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None,
            )
            if h and h != INVALID_HANDLE_VALUE:
                self._handle = h
                self._active_path = path
                break
            else:
                last_error = ctypes.get_last_error()

        if not self._handle:
            raise OSError(last_error, f"Could not open OmniPad VHF keyboard device at {paths_to_try}")

    @classmethod
    def try_open(cls) -> Tuple[Optional["VHFKeyboardDevice"], Optional[str]]:
        try:
            dev = cls()
            return dev, None
        except Exception as exc:
            return None, str(exc)

    @property
    def available(self) -> bool:
        return bool(self._handle)

    @property
    def device_path(self) -> Optional[str]:
        return self._active_path

    def submit_report(self, report: bytes) -> None:
        if len(report) != REPORT_SIZE:
            raise ValueError(f"Keyboard report must be exactly {REPORT_SIZE} bytes")
        if not self._handle:
            raise RuntimeError("OmniPad VHF keyboard handle is closed")

        buf = (ctypes.c_ubyte * REPORT_SIZE).from_buffer_copy(report)
        returned = wintypes.DWORD(0)

        ok = self._DeviceIoControl(
            self._handle,
            self._active_ioctl,
            ctypes.byref(buf),
            REPORT_SIZE,
            None,
            0,
            ctypes.byref(returned),
            None,
        )
        if not ok:
            # Try legacy IOCTL fallback
            if self._active_ioctl == IOCTL_OMNIPAD_SET_KEYBOARD_REPORT:
                ok_legacy = self._DeviceIoControl(
                    self._handle,
                    IOCTL_OMNIPAD_LEGACY_KEYBOARD_REPORT,
                    ctypes.byref(buf),
                    REPORT_SIZE,
                    None,
                    0,
                    ctypes.byref(returned),
                    None,
                )
                if ok_legacy:
                    self._active_ioctl = IOCTL_OMNIPAD_LEGACY_KEYBOARD_REPORT
                    return

            err = ctypes.get_last_error()
            raise OSError(err, "OmniPad VHF keyboard report submission failed")

    def release_all(self) -> None:
        if self._handle:
            try:
                self.submit_report(bytes(REPORT_SIZE))
            except Exception as e:
                logger.debug("Error during VHF release_all: %s", e)

    def close(self) -> None:
        if self._handle:
            try:
                self.release_all()
            finally:
                self._CloseHandle(self._handle)
                self._handle = None

    def __enter__(self) -> "VHFKeyboardDevice":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

