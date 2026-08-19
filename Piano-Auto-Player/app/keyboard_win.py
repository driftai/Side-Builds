from __future__ import annotations

import ctypes
import os
import string
import time
from ctypes import wintypes


IS_WINDOWS = os.name == "nt"
SHIFTED_PIANO_CHARS = set(string.ascii_uppercase + "!@$%^*(")


def key_message_lparam(scan: int, key_up: bool = False) -> int:
    value = 1 | ((int(scan) & 0xFF) << 16)
    if key_up:
        value |= (1 << 30) | (1 << 31)
    return value


if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_LSHIFT = 0xA0
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    ULONG_PTR = wintypes.WPARAM

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG), ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
    user32.VkKeyScanW.restype = ctypes.c_short
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.PostMessageW.restype = wintypes.BOOL
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.SetFocus.argtypes = (wintypes.HWND,)
    user32.SetFocus.restype = wintypes.HWND
    user32.GetKeyboardState.argtypes = (ctypes.POINTER(ctypes.c_ubyte),)
    user32.GetKeyboardState.restype = wintypes.BOOL
    user32.SetKeyboardState.argtypes = (ctypes.POINTER(ctypes.c_ubyte),)
    user32.SetKeyboardState.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.argtypes = ()
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def char_needs_shift(char: str) -> bool:
    return bool(char and char[0] in SHIFTED_PIANO_CHARS)


def _scan_code(vk: int) -> int:
    return int(user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))


def _make_input(scan: int, key_up: bool = False) -> INPUT:
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, scan, flags, 0, 0))


def _send_scans(scans: list[int], key_up: bool = False) -> None:
    if not scans:
        return
    events = (INPUT * len(scans))(*[_make_input(scan, key_up) for scan in scans])
    sent = user32.SendInput(len(events), events, ctypes.sizeof(INPUT))
    if sent != len(events):
        raise ctypes.WinError(ctypes.get_last_error())


def _describe_char(char: str) -> tuple[int, int, bool]:
    packed = int(user32.VkKeyScanW(char[0]))
    if packed == -1:
        raise ValueError(f"Cannot map keyboard character: {char!r}")
    vk = packed & 0xFF
    shift_state = (packed >> 8) & 0xFF
    if shift_state & ~1:
        raise ValueError(f"Unsupported modifier combination for piano character: {char!r}")
    scan = _scan_code(vk)
    if not scan:
        raise ValueError(f"No scan code for keyboard character: {char!r}")
    return vk, scan, bool(shift_state & 1)


class WindowsKeyboard:
    """Foreground physical-style scan-code injection via SendInput."""

    def __init__(self) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("Windows key injection is only available on Windows.")
        self.shift_scan = _scan_code(VK_SHIFT)
        self.ctrl_scan = _scan_code(VK_CONTROL)

    def tap_char(self, char: str, hold_ms: float = 18.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, cancel_check=None) -> None:
        if not char:
            return
        _vk, scan, shifted = _describe_char(char)
        shift_down = False
        try:
            if shifted:
                _send_scans([self.shift_scan]); shift_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
            _send_scans([scan])
            try: self._sleep_ms(hold_ms, cancel_check)
            finally: _send_scans([scan], True)
            if shifted: self._sleep_ms(modifier_tail_ms, cancel_check)
        finally:
            if shift_down:
                _send_scans([self.shift_scan], True)

    def tap_chord(self, chars: str, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0, cancel_check=None) -> None:
        descriptors = [_describe_char(char) for char in chars if char]
        if not descriptors:
            return
        black = [scan for _vk, scan, shifted in descriptors if shifted]
        white = [scan for _vk, scan, shifted in descriptors if not shifted]
        if black and not white:
            return self._shifted_chord(black, hold_ms, modifier_lead_ms, modifier_tail_ms, cancel_check)
        if white and not black:
            return self._plain_chord(white, hold_ms, cancel_check)
        shift_down = down_black = down_white = False
        try:
            _send_scans([self.shift_scan]); shift_down = True
            if not self._sleep_ms(modifier_lead_ms, cancel_check): return
            _send_scans(black); down_black = True
            if not self._sleep_ms(chord_spread_ms, cancel_check): return
            _send_scans([self.shift_scan], True); shift_down = False
            _send_scans(white); down_white = True; self._sleep_ms(hold_ms, cancel_check)
        finally:
            if down_white: _send_scans(list(reversed(white)), True)
            if down_black: _send_scans(list(reversed(black)), True)
            if shift_down: self._sleep_ms(modifier_tail_ms); _send_scans([self.shift_scan], True)


    def press_strokes(self, strokes, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0) -> None:
        descriptors = []
        for stroke in strokes or []:
            _vk, scan, shifted = _describe_char(stroke.char)
            descriptors.append((scan, bool(stroke.ctrl), shifted and not stroke.ctrl))
        if not descriptors:
            return
        ctrl = list(dict.fromkeys(scan for scan, is_ctrl, _shifted in descriptors if is_ctrl))
        shifted = list(dict.fromkeys(scan for scan, is_ctrl, is_shifted in descriptors if not is_ctrl and is_shifted))
        plain = list(dict.fromkeys(scan for scan, is_ctrl, is_shifted in descriptors if not is_ctrl and not is_shifted))
        ctrl_down = shift_down = False
        try:
            if ctrl:
                _send_scans([self.ctrl_scan]); ctrl_down = True
                self._sleep_ms(modifier_lead_ms)
                _send_scans(ctrl)
                _send_scans([self.ctrl_scan], True); ctrl_down = False
            if ctrl and (shifted or plain):
                self._sleep_ms(chord_spread_ms)
            if shifted:
                _send_scans([self.shift_scan]); shift_down = True
                self._sleep_ms(modifier_lead_ms)
                _send_scans(shifted)
                _send_scans([self.shift_scan], True); shift_down = False
            if shifted and plain:
                self._sleep_ms(chord_spread_ms)
            if plain:
                _send_scans(plain)
            if (ctrl or shifted) and modifier_tail_ms > 0:
                self._sleep_ms(modifier_tail_ms)
        finally:
            if shift_down: _send_scans([self.shift_scan], True)
            if ctrl_down: _send_scans([self.ctrl_scan], True)

    def release_strokes(self, strokes) -> None:
        scans = []
        for stroke in strokes or []:
            _vk, scan, _shifted = _describe_char(stroke.char)
            if scan not in scans:
                scans.append(scan)
        if scans:
            _send_scans(list(reversed(scans)), True)

    def tap_strokes(self, strokes, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0, cancel_check=None) -> None:
        descriptors = []
        for stroke in strokes or []:
            _vk, scan, shifted = _describe_char(stroke.char)
            descriptors.append((scan, bool(stroke.ctrl), shifted and not stroke.ctrl))
        if not descriptors:
            return
        ctrl = [scan for scan, is_ctrl, _shifted in descriptors if is_ctrl]
        shifted = [scan for scan, is_ctrl, is_shifted in descriptors if not is_ctrl and is_shifted]
        plain = [scan for scan, is_ctrl, is_shifted in descriptors if not is_ctrl and not is_shifted]
        down: list[int] = []
        ctrl_down = shift_down = False
        try:
            if ctrl:
                _send_scans([self.ctrl_scan]); ctrl_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
                _send_scans(ctrl); down.extend(ctrl)
                _send_scans([self.ctrl_scan], True); ctrl_down = False
            if ctrl and (shifted or plain) and not self._sleep_ms(chord_spread_ms, cancel_check): return
            if shifted:
                _send_scans([self.shift_scan]); shift_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
                _send_scans(shifted); down.extend(shifted)
                _send_scans([self.shift_scan], True); shift_down = False
            if shifted and plain and not self._sleep_ms(chord_spread_ms, cancel_check): return
            if plain:
                _send_scans(plain); down.extend(plain)
            self._sleep_ms(hold_ms, cancel_check)
        finally:
            if down: _send_scans(list(reversed(down)), True)
            if shift_down: _send_scans([self.shift_scan], True)
            if ctrl_down: _send_scans([self.ctrl_scan], True)
            if (ctrl or shifted) and modifier_tail_ms > 0: self._sleep_ms(modifier_tail_ms)

    def _plain_chord(self, scans: list[int], hold_ms: float, cancel_check=None) -> None:
        _send_scans(scans)
        try: self._sleep_ms(hold_ms, cancel_check)
        finally: _send_scans(list(reversed(scans)), True)

    def _shifted_chord(self, scans: list[int], hold_ms: float, lead_ms: float, tail_ms: float, cancel_check=None) -> None:
        _send_scans([self.shift_scan])
        try:
            if not self._sleep_ms(lead_ms, cancel_check): return
            _send_scans(scans)
            try: self._sleep_ms(hold_ms, cancel_check)
            finally: _send_scans(list(reversed(scans)), True)
            self._sleep_ms(tail_ms, cancel_check)
        finally: _send_scans([self.shift_scan], True)

    @staticmethod
    def _sleep_ms(milliseconds: float, cancel_check=None) -> bool:
        deadline = time.monotonic() + max(milliseconds, 0.0) / 1000.0
        while time.monotonic() < deadline:
            if cancel_check and cancel_check(): return False
            time.sleep(min(0.002, max(0.0, deadline - time.monotonic())))
        return not (cancel_check and cancel_check())


class BackgroundWindowsKeyboard:
    """Legacy best-effort WM_KEYDOWN/UP delivery to the selected top-level HWND."""

    def __init__(self, hwnd: int) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("Background key delivery is only available on Windows.")
        self.hwnd = int(hwnd)
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            raise RuntimeError("The selected background target window is no longer available.")
        self.shift_vk = VK_SHIFT
        self.shift_scan = _scan_code(VK_SHIFT)

    def _post(self, vk: int, scan: int, key_up: bool = False) -> None:
        message = WM_KEYUP if key_up else WM_KEYDOWN
        if not user32.PostMessageW(self.hwnd, message, vk, key_message_lparam(scan, key_up)):
            raise ctypes.WinError(ctypes.get_last_error())

    def tap_char(self, char: str, hold_ms: float = 18.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0) -> None:
        if not char:
            return
        vk, scan, shifted = _describe_char(char)
        shift_down = False
        try:
            if shifted:
                self._post(self.shift_vk, self.shift_scan); shift_down = True; self._sleep_ms(modifier_lead_ms)
            self._post(vk, scan); self._sleep_ms(hold_ms); self._post(vk, scan, True)
            if shifted: self._sleep_ms(modifier_tail_ms)
        finally:
            if shift_down: self._post(self.shift_vk, self.shift_scan, True)

    def tap_chord(self, chars: str, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0) -> None:
        descriptors = [_describe_char(char) for char in chars if char]
        if not descriptors:
            return
        black = [(vk, scan) for vk, scan, shifted in descriptors if shifted]
        white = [(vk, scan) for vk, scan, shifted in descriptors if not shifted]
        if black:
            self._post(self.shift_vk, self.shift_scan); self._sleep_ms(modifier_lead_ms)
            for vk, scan in black: self._post(vk, scan)
        if black and white:
            self._sleep_ms(chord_spread_ms); self._post(self.shift_vk, self.shift_scan, True)
        for vk, scan in white: self._post(vk, scan)
        self._sleep_ms(hold_ms)
        for vk, scan in reversed(white): self._post(vk, scan, True)
        for vk, scan in reversed(black): self._post(vk, scan, True)
        if black and not white:
            self._sleep_ms(modifier_tail_ms); self._post(self.shift_vk, self.shift_scan, True)

    @staticmethod
    def _sleep_ms(milliseconds: float) -> None:
        if milliseconds > 0:
            time.sleep(milliseconds / 1000.0)


class BackgroundWindowsKeyboardV2(BackgroundWindowsKeyboard):
    """Recipient-aware background route using the target GUI thread's retained focus/key state."""

    def __init__(self, target_hwnd: int, recipient_hwnd: int, target_thread_id: int) -> None:
        super().__init__(recipient_hwnd or target_hwnd)
        self.target_hwnd = int(target_hwnd)
        self.recipient_hwnd = int(recipient_hwnd or target_hwnd)
        self.target_thread_id = int(target_thread_id)
        self.current_thread_id = int(kernel32.GetCurrentThreadId())
        self.attached = False
        self.closed = False
        self.key_state = (ctypes.c_ubyte * 256)()

        # IsWindow is a USER call, so this thread has an input/message queue before attachment.
        if self.target_thread_id and self.current_thread_id != self.target_thread_id:
            if not user32.AttachThreadInput(self.current_thread_id, self.target_thread_id, True):
                raise ctypes.WinError(ctypes.get_last_error())
            self.attached = True

        # Establish the target thread's own focus window without SetForegroundWindow.
        user32.SetFocus(wintypes.HWND(self.recipient_hwnd))
        user32.GetKeyboardState(self.key_state)

    def _post(self, vk: int, scan: int, key_up: bool = False) -> None:
        message = WM_KEYUP if key_up else WM_KEYDOWN
        if not user32.PostMessageW(self.recipient_hwnd, message, vk, key_message_lparam(scan, key_up)):
            raise ctypes.WinError(ctypes.get_last_error())

    def _set_shift_state(self, down: bool) -> None:
        value = 0x80 if down else 0x00
        self.key_state[VK_SHIFT] = value
        self.key_state[VK_LSHIFT] = value
        if not user32.SetKeyboardState(self.key_state):
            raise ctypes.WinError(ctypes.get_last_error())

    def tap_char(self, char: str, hold_ms: float = 18.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0) -> None:
        if not char:
            return
        vk, scan, shifted = _describe_char(char)
        shift_down = False
        try:
            if shifted:
                self._set_shift_state(True); self._post(self.shift_vk, self.shift_scan); shift_down = True
                self._sleep_ms(modifier_lead_ms)
            self._post(vk, scan); self._sleep_ms(hold_ms); self._post(vk, scan, True)
            if shifted: self._sleep_ms(modifier_tail_ms)
        finally:
            if shift_down:
                self._post(self.shift_vk, self.shift_scan, True); self._set_shift_state(False)

    def tap_chord(self, chars: str, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0) -> None:
        descriptors = [_describe_char(char) for char in chars if char]
        if not descriptors:
            return
        black = [(vk, scan) for vk, scan, shifted in descriptors if shifted]
        white = [(vk, scan) for vk, scan, shifted in descriptors if not shifted]
        shift_down = False
        try:
            if black:
                self._set_shift_state(True); self._post(self.shift_vk, self.shift_scan); shift_down = True
                self._sleep_ms(modifier_lead_ms)
                for vk, scan in black: self._post(vk, scan)
            if black and white:
                self._sleep_ms(chord_spread_ms)
                self._post(self.shift_vk, self.shift_scan, True); self._set_shift_state(False); shift_down = False
            for vk, scan in white: self._post(vk, scan)
            self._sleep_ms(hold_ms)
            for vk, scan in reversed(white): self._post(vk, scan, True)
            for vk, scan in reversed(black): self._post(vk, scan, True)
            if black and not white:
                self._sleep_ms(modifier_tail_ms)
        finally:
            if shift_down:
                self._post(self.shift_vk, self.shift_scan, True); self._set_shift_state(False)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self._set_shift_state(False)
        except Exception:
            pass
        if self.attached:
            user32.AttachThreadInput(self.current_thread_id, self.target_thread_id, False)
            self.attached = False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def f7_is_down() -> bool:
    if not IS_WINDOWS:
        return False
    return bool(user32.GetAsyncKeyState(0x76) & 0x8000)
