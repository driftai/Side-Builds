from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from .keyboard_win import _describe_char, key_message_lparam
from .window_focus import background_target_info


IS_WINDOWS = os.name == "nt"

WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WM_KILLFOCUS = 0x0008
WM_ACTIVATEAPP = 0x001C
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WA_ACTIVE = 1
WA_INACTIVE = 0
VK_SHIFT = 0x10
VK_CONTROL = 0x11

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.PostMessageW.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT


def virtual_focus_messages(previous_hwnd: int = 0, previous_thread: int = 0) -> list[tuple[int, int, int]]:
    """Messages used to mirror an activation/focus transition inside the target queue.

    They intentionally do not call SetForegroundWindow or SetFocus. The actual
    Windows foreground remains untouched; this only gives message-driven apps
    a chance to update the same internal state they normally update on focus.
    """
    return [
        (WM_ACTIVATEAPP, 1, int(previous_thread)),
        (WM_ACTIVATE, WA_ACTIVE, int(previous_hwnd)),
        (WM_SETFOCUS, int(previous_hwnd), 0),
    ]


class VirtualTargetWindowsKeyboard:
    """Best-effort window-scoped keyboard messages without foreground stealing.

    Roblox may still reject this route if it relies on Raw Input or an explicit
    OS foreground check. Unlike focus-pulse modes, however, this class never
    changes the real foreground window, so the user's keyboard/mouse lane stays
    with whatever app they are actually using.
    """

    def __init__(self, target_hwnd: int, activation_lead_ms: float = 2.0) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("Virtual-target keyboard delivery is only available on Windows.")
        info = background_target_info(int(target_hwnd))
        self.target_hwnd = int(info.get("target_hwnd") or 0)
        self.recipient_hwnd = int(info.get("recipient_hwnd") or self.target_hwnd)
        self.activation_lead_ms = max(0.0, float(activation_lead_ms))
        self.closed = False
        if not self.target_hwnd or not user32.IsWindow(wintypes.HWND(self.target_hwnd)):
            raise RuntimeError("The selected virtual-target window is no longer available.")
        if not self.recipient_hwnd or not user32.IsWindow(wintypes.HWND(self.recipient_hwnd)):
            self.recipient_hwnd = self.target_hwnd

    def _post(self, hwnd: int, message: int, wparam: int = 0, lparam: int = 0) -> None:
        if not user32.PostMessageW(wintypes.HWND(int(hwnd)), message, wintypes.WPARAM(int(wparam)), wintypes.LPARAM(int(lparam))):
            raise ctypes.WinError(ctypes.get_last_error())

    def _foreground_context(self) -> tuple[int, int]:
        hwnd = int(user32.GetForegroundWindow() or 0)
        if not hwnd:
            return 0, 0
        thread_id = int(user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None))
        return hwnd, thread_id

    def _arm(self) -> None:
        previous_hwnd, previous_thread = self._foreground_context()
        messages = virtual_focus_messages(previous_hwnd, previous_thread)
        # Activation messages belong to the top-level window; WM_SETFOCUS is
        # aimed at the target thread's retained keyboard recipient when known.
        for message, wparam, lparam in messages[:2]:
            self._post(self.target_hwnd, message, wparam, lparam)
        message, wparam, lparam = messages[2]
        self._post(self.recipient_hwnd, message, wparam, lparam)
        self._sleep_ms(self.activation_lead_ms)

    def _key(self, vk: int, scan: int, key_up: bool = False) -> None:
        self._post(self.recipient_hwnd, WM_KEYUP if key_up else WM_KEYDOWN, vk, key_message_lparam(scan, key_up))

    def tap_char(self, char: str, hold_ms: float = 18.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, cancel_check=None) -> None:
        if not char:
            return
        vk, scan, shifted = _describe_char(char)
        self._arm()
        shift_scan = int(user32.MapVirtualKeyW(VK_SHIFT, 0)) if shifted else 0
        shift_down = False
        try:
            if shifted:
                self._key(VK_SHIFT, shift_scan); shift_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
            self._key(vk, scan)
            try: self._sleep_ms(hold_ms, cancel_check)
            finally: self._key(vk, scan, True)
            if shifted: self._sleep_ms(modifier_tail_ms, cancel_check)
        finally:
            if shift_down:
                self._key(VK_SHIFT, shift_scan, True)

    def tap_chord(self, chars: str, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0, cancel_check=None) -> None:
        descriptors = [_describe_char(char) for char in chars if char]
        if not descriptors:
            return
        self._arm()
        black = [(vk, scan) for vk, scan, shifted in descriptors if shifted]
        white = [(vk, scan) for vk, scan, shifted in descriptors if not shifted]
        shift_scan = int(user32.MapVirtualKeyW(VK_SHIFT, 0))
        shift_down = False
        down_black: list[tuple[int, int]] = []
        down_white: list[tuple[int, int]] = []
        try:
            if black:
                self._key(VK_SHIFT, shift_scan); shift_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
                for vk, scan in black:
                    self._key(vk, scan); down_black.append((vk, scan))
            if black and white:
                if not self._sleep_ms(chord_spread_ms, cancel_check): return
                self._key(VK_SHIFT, shift_scan, True); shift_down = False
            for vk, scan in white:
                self._key(vk, scan); down_white.append((vk, scan))
            self._sleep_ms(hold_ms, cancel_check)
        finally:
            for vk, scan in reversed(down_white):
                self._key(vk, scan, True)
            for vk, scan in reversed(down_black):
                self._key(vk, scan, True)
            if shift_down:
                self._sleep_ms(modifier_tail_ms)
                self._key(VK_SHIFT, shift_scan, True)


    def press_strokes(self, strokes, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0) -> None:
        descriptors = []
        for stroke in strokes or []:
            vk, scan, shifted = _describe_char(stroke.char)
            descriptors.append((vk, scan, bool(stroke.ctrl), shifted and not stroke.ctrl))
        if not descriptors:
            return
        self._arm()
        ctrl = [(vk, scan) for vk, scan, is_ctrl, _shifted in descriptors if is_ctrl]
        shifted = [(vk, scan) for vk, scan, is_ctrl, is_shifted in descriptors if not is_ctrl and is_shifted]
        plain = [(vk, scan) for vk, scan, is_ctrl, is_shifted in descriptors if not is_ctrl and not is_shifted]
        ctrl_scan = int(user32.MapVirtualKeyW(VK_CONTROL, 0))
        shift_scan = int(user32.MapVirtualKeyW(VK_SHIFT, 0))
        ctrl_down = shift_down = False
        try:
            if ctrl:
                self._key(VK_CONTROL, ctrl_scan); ctrl_down = True
                self._sleep_ms(modifier_lead_ms)
                for vk, scan in ctrl: self._key(vk, scan)
                self._key(VK_CONTROL, ctrl_scan, True); ctrl_down = False
            if ctrl and (shifted or plain): self._sleep_ms(chord_spread_ms)
            if shifted:
                self._key(VK_SHIFT, shift_scan); shift_down = True
                self._sleep_ms(modifier_lead_ms)
                for vk, scan in shifted: self._key(vk, scan)
                self._key(VK_SHIFT, shift_scan, True); shift_down = False
            if shifted and plain: self._sleep_ms(chord_spread_ms)
            for vk, scan in plain: self._key(vk, scan)
            if (ctrl or shifted) and modifier_tail_ms > 0: self._sleep_ms(modifier_tail_ms)
        finally:
            if shift_down: self._key(VK_SHIFT, shift_scan, True)
            if ctrl_down: self._key(VK_CONTROL, ctrl_scan, True)

    def release_strokes(self, strokes) -> None:
        descriptors = []
        seen = set()
        for stroke in strokes or []:
            vk, scan, _shifted = _describe_char(stroke.char)
            if scan in seen: continue
            seen.add(scan); descriptors.append((vk, scan))
        for vk, scan in reversed(descriptors):
            self._key(vk, scan, True)

    def tap_strokes(self, strokes, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0, cancel_check=None) -> None:
        descriptors = []
        for stroke in strokes or []:
            vk, scan, shifted = _describe_char(stroke.char)
            descriptors.append((vk, scan, bool(stroke.ctrl), shifted and not stroke.ctrl))
        if not descriptors:
            return
        self._arm()
        ctrl = [(vk, scan) for vk, scan, is_ctrl, _shifted in descriptors if is_ctrl]
        shifted = [(vk, scan) for vk, scan, is_ctrl, is_shifted in descriptors if not is_ctrl and is_shifted]
        plain = [(vk, scan) for vk, scan, is_ctrl, is_shifted in descriptors if not is_ctrl and not is_shifted]
        ctrl_scan = int(user32.MapVirtualKeyW(VK_CONTROL, 0))
        shift_scan = int(user32.MapVirtualKeyW(VK_SHIFT, 0))
        down = []
        ctrl_down = shift_down = False
        try:
            if ctrl:
                self._key(VK_CONTROL, ctrl_scan); ctrl_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
                for vk, scan in ctrl: self._key(vk, scan); down.append((vk, scan))
                self._key(VK_CONTROL, ctrl_scan, True); ctrl_down = False
            if ctrl and (shifted or plain) and not self._sleep_ms(chord_spread_ms, cancel_check): return
            if shifted:
                self._key(VK_SHIFT, shift_scan); shift_down = True
                if not self._sleep_ms(modifier_lead_ms, cancel_check): return
                for vk, scan in shifted: self._key(vk, scan); down.append((vk, scan))
                self._key(VK_SHIFT, shift_scan, True); shift_down = False
            if shifted and plain and not self._sleep_ms(chord_spread_ms, cancel_check): return
            for vk, scan in plain: self._key(vk, scan); down.append((vk, scan))
            self._sleep_ms(hold_ms, cancel_check)
        finally:
            for vk, scan in reversed(down): self._key(vk, scan, True)
            if shift_down: self._key(VK_SHIFT, shift_scan, True)
            if ctrl_down: self._key(VK_CONTROL, ctrl_scan, True)
            if (ctrl or shifted) and modifier_tail_ms > 0: self._sleep_ms(modifier_tail_ms)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        foreground, foreground_thread = self._foreground_context()
        if foreground == self.target_hwnd:
            return
        try:
            self._post(self.recipient_hwnd, WM_KILLFOCUS, foreground, 0)
            self._post(self.target_hwnd, WM_ACTIVATE, WA_INACTIVE, foreground)
            self._post(self.target_hwnd, WM_ACTIVATEAPP, 0, foreground_thread)
        except Exception:
            pass

    @staticmethod
    def _sleep_ms(milliseconds: float, cancel_check=None) -> bool:
        deadline = time.monotonic() + max(milliseconds, 0.0) / 1000.0
        while time.monotonic() < deadline:
            if cancel_check and cancel_check(): return False
            time.sleep(min(0.002, max(0.0, deadline - time.monotonic())))
        return not (cancel_check and cancel_check())

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
