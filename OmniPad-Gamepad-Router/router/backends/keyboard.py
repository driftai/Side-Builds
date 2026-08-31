"""
Windows Keyboard Injection & Target-Locked Compatibility Backends.
"""

import logging
import ctypes
import time
from typing import Dict, Any, Optional, Set

from .base import BaseController, WIN32_AVAILABLE
from ..targeting import IS_WINDOWS, target_manager

logger = logging.getLogger("OmniPad.Controller.Keyboard")

# Win32 SendInput Structures
if IS_WINDOWS:
    ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT)]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", ctypes.c_ulong), ("u", _INPUT_UNION)]

    _SendInput = ctypes.windll.user32.SendInput
    _SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int]
    _SendInput.restype = ctypes.c_uint
    _INPUT_KEYBOARD = 1
    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_SCANCODE = 0x0008
    _KEYEVENTF_EXTENDEDKEY = 0x0001
else:  # pragma: no cover
    _INPUT = None
    _SendInput = None
    _INPUT_KEYBOARD = 1
    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_SCANCODE = 0x0008
    _KEYEVENTF_EXTENDEDKEY = 0x0001

# Common DOM KeyboardEvent.code -> Windows virtual-key mapping.
_DOM_CODE_TO_VK = {
    **{f"Key{chr(65+i)}": 0x41+i for i in range(26)},
    **{f"Digit{i}": 0x30+i for i in range(10)},
    "Space": 0x20, "Enter": 0x0D, "Backspace": 0x08, "Tab": 0x09,
    "Escape": 0x1B, "ShiftLeft": 0xA0, "ShiftRight": 0xA1,
    "ControlLeft": 0xA2, "ControlRight": 0xA3,
    "AltLeft": 0xA4, "AltRight": 0xA5,
    "Minus": 0xBD, "Equal": 0xBB, "BracketLeft": 0xDB, "BracketRight": 0xDD,
    "Backslash": 0xDC, "Semicolon": 0xBA, "Quote": 0xDE, "Backquote": 0xC0,
    "Comma": 0xBC, "Period": 0xBE, "Slash": 0xBF,
    "CapsLock": 0x14, "Insert": 0x2D, "Delete": 0x2E,
    "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "ArrowUp": 0x26, "ArrowDown": 0x28, "ArrowLeft": 0x25, "ArrowRight": 0x27,
    "PrintScreen": 0x2C, "ScrollLock": 0x91, "Pause": 0x13,
    "ContextMenu": 0x5D,
    "Numpad0": 0x60, "Numpad1": 0x61, "Numpad2": 0x62, "Numpad3": 0x63,
    "Numpad4": 0x64, "Numpad5": 0x65, "Numpad6": 0x66, "Numpad7": 0x67,
    "Numpad8": 0x68, "Numpad9": 0x69, "NumpadDecimal": 0x6E,
    "NumpadAdd": 0x6B, "NumpadSubtract": 0x6D, "NumpadMultiply": 0x6A,
    "NumpadDivide": 0x6F, "NumpadEnter": 0x0D, "NumpadEqual": 0x92, "NumpadComma": 0x6C,
    "IntlBackslash": 0xE2,
    "AudioVolumeMute": 0xAD, "AudioVolumeDown": 0xAE, "AudioVolumeUp": 0xAF,
    "MediaTrackNext": 0xB0, "MediaTrackPrevious": 0xB1, "MediaStop": 0xB2, "MediaPlayPause": 0xB3,
    "BrowserBack": 0xA6, "BrowserForward": 0xA7, "BrowserRefresh": 0xA8, "BrowserHome": 0xAC,
    **{f"F{i}": 0x70 + (i - 1) for i in range(1, 13)},
    **{f"F{i}": 0x7C + (i - 13) for i in range(13, 25)},
}


def _dom_code_to_vk(code: Any) -> Optional[int]:
    code = str(code or "").strip()
    if code in _DOM_CODE_TO_VK:
        return _DOM_CODE_TO_VK[code]
    if len(code) == 1 and code.isalpha():
        return ord(code.upper())
    if len(code) == 1 and code.isdigit():
        return ord(code)
    if IS_WINDOWS and len(code) == 1:
        try:
            res = ctypes.windll.user32.VkKeyScanW(ord(code))
            if res != -1:
                return res & 0xFF
        except Exception:
            pass
    return None


class TargetLockedKeyboardBackend(BaseController):
    """Target-locked Windows keyboard compatibility backend."""
    backend_id = "keyboard_target"
    display_name = "Keyboard 2 (Target-Locked SendInput)"

    DEFAULT_KEY_MAP = {
        "DPAD_UP": 0x57, "DPAD_DOWN": 0x53, "DPAD_LEFT": 0x41, "DPAD_RIGHT": 0x44,
        "A": 0x4A, "B": 0x4B, "X": 0x55, "Y": 0x49,
        "LB": 0x51, "RB": 0x45, "LT": 0x5A, "RT": 0x43,
        "START": 0x0D, "BACK": 0x08, "SELECT": 0x08,
    }

    def __init__(self, slot_id: int, keymap: Optional[Dict[str, int]] = None):
        if not IS_WINDOWS or _SendInput is None:
            raise RuntimeError("Windows SendInput is not available on this platform.")
        self.slot_id = slot_id
        self.keymap = keymap or dict(self.DEFAULT_KEY_MAP)
        self._down_keys: Set[int] = set()
        self.last_guarded: bool = True
        self.last_apply_at: float = 0.0
        logger.info("[Slot %d] Created target-locked keyboard backend", self.slot_id)

    def _emit_key(self, vk: int, down: bool) -> None:
        scan = 0
        if IS_WINDOWS:
            try:
                scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
            except Exception:
                scan = 0

        flags = 0 if down else _KEYEVENTF_KEYUP
        if vk in (0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0xA3, 0xA5):
            flags |= _KEYEVENTF_EXTENDEDKEY

        inp = _INPUT()
        inp.type = _INPUT_KEYBOARD
        inp.ki = _KEYBDINPUT(
            wVk=vk,
            wScan=scan,
            dwFlags=flags,
            time=0,
            dwExtraInfo=None,
        )
        sent = _SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
        if sent != 1:
            raise ctypes.WinError()

    def _release_local(self) -> None:
        for vk in tuple(self._down_keys):
            try:
                self._emit_key(vk, False)
            except Exception:
                pass
        self._down_keys.clear()

    def apply(self, state: Dict[str, Any]) -> None:
        self.last_apply_at = time.time()
        guarded = bool(target_manager.is_target_foreground())
        self.last_guarded = guarded
        if not guarded:
            self._release_local()
            return

        key_codes = state.get("key_codes") or []
        target_keys = set()
        if key_codes:
            target_keys = {_dom_code_to_vk(code) for code in key_codes}
            target_keys.discard(None)
            target_keys = {int(vk) for vk in target_keys}
        else:
            buttons = state.get("buttons", {})
            target_keys = {vk for btn, vk in self.keymap.items() if buttons.get(btn, False)}

        for vk in self._down_keys - target_keys:
            try:
                self._emit_key(vk, False)
            except Exception:
                pass
        for vk in target_keys - self._down_keys:
            try:
                self._emit_key(vk, True)
            except Exception:
                pass
        self._down_keys = target_keys

    def release_all(self) -> None:
        self._release_local()

    def close(self) -> None:
        self.release_all()
        logger.info("[Slot %d] Target-locked keyboard backend closed", self.slot_id)


class KeyboardInjectionBackend(BaseController):
    """Legacy system-wide keyboard injection backend."""
    backend_id = "keyboard"
    display_name = "Keyboard Key Injection (legacy)"
    DEFAULT_KEY_MAP = TargetLockedKeyboardBackend.DEFAULT_KEY_MAP

    def __init__(self, slot_id: int, keymap: Optional[Dict[str, int]] = None):
        if not IS_WINDOWS or _SendInput is None:
            raise RuntimeError("Windows SendInput is not available on this platform.")
        self.slot_id = slot_id
        self.keymap = keymap or dict(self.DEFAULT_KEY_MAP)
        self._down_keys: Set[int] = set()

    def _emit_key(self, vk: int, down: bool) -> None:
        scan = 0
        if IS_WINDOWS:
            try:
                scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
            except Exception:
                scan = 0

        flags = 0 if down else _KEYEVENTF_KEYUP
        if vk in (0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0xA3, 0xA5):
            flags |= _KEYEVENTF_EXTENDEDKEY

        inp = _INPUT()
        inp.type = _INPUT_KEYBOARD
        inp.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
        if _SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) != 1:
            raise ctypes.WinError()

    def apply(self, state: Dict[str, Any]) -> None:
        key_codes = state.get("key_codes") or []
        if key_codes:
            target_keys = {_dom_code_to_vk(code) for code in key_codes}
            target_keys.discard(None)
            target_keys = {int(vk) for vk in target_keys}
        else:
            buttons = state.get("buttons", {})
            target_keys = {vk for btn, vk in self.keymap.items() if buttons.get(btn, False)}

        for vk in self._down_keys - target_keys:
            try:
                self._emit_key(vk, False)
            except Exception:
                pass
        for vk in target_keys - self._down_keys:
            try:
                self._emit_key(vk, True)
            except Exception:
                pass
        self._down_keys = target_keys

    def release_all(self) -> None:
        for vk in tuple(self._down_keys):
            try:
                self._emit_key(vk, False)
            except Exception:
                pass
        self._down_keys.clear()

    def close(self) -> None:
        self.release_all()
