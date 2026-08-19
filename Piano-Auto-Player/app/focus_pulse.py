from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from .input_guard import PhysicalInputGuard
from .keyboard_win import WindowsKeyboard, _describe_char, _send_scans


IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ShowWindow.restype = wintypes.BOOL
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def _thread_id(hwnd: int) -> int:
    if not IS_WINDOWS or not hwnd:
        return 0
    return int(user32.GetWindowThreadProcessId(wintypes.HWND(int(hwnd)), None))


def _force_foreground(hwnd: int) -> bool:
    if not IS_WINDOWS or not hwnd or not user32.IsWindow(wintypes.HWND(int(hwnd))):
        return False
    target = wintypes.HWND(int(hwnd))
    user32.ShowWindow(target, 9)  # SW_RESTORE
    if user32.SetForegroundWindow(target):
        return True
    current_thread = int(kernel32.GetCurrentThreadId())
    foreground = int(user32.GetForegroundWindow() or 0)
    thread_ids = {tid for tid in (_thread_id(foreground), _thread_id(hwnd)) if tid and tid != current_thread}
    attached: list[int] = []
    try:
        for thread_id in thread_ids:
            if user32.AttachThreadInput(current_thread, thread_id, True):
                attached.append(thread_id)
        return bool(user32.SetForegroundWindow(target))
    finally:
        for thread_id in reversed(attached):
            user32.AttachThreadInput(current_thread, thread_id, False)


class FocusPulseWindowsKeyboard(WindowsKeyboard):
    """Focus-virtualized SendInput for Roblox multitasking.

    Windows still has one real foreground focus. This class makes the focus
    pulses behave like two input lanes: piano scan codes go to Roblox, while a
    low-level guard quarantines physical keyboard/click input during each tiny
    pulse and replays it after the user's previous window is restored.
    """

    def __init__(self, target_hwnd: int, focus_lead_ms: float = 3.0, restore_tail_ms: float = 0.8) -> None:
        super().__init__()
        self.target_hwnd = int(target_hwnd)
        if not self.target_hwnd or not user32.IsWindow(wintypes.HWND(self.target_hwnd)):
            raise RuntimeError("The selected background-assist target is no longer available.")
        self.focus_lead_ms = max(0.0, float(focus_lead_ms))
        self.restore_tail_ms = max(0.0, float(restore_tail_ms))
        self.guard = PhysicalInputGuard()
        self.closed = False

    def _enter_target(self) -> tuple[int, bool]:
        previous = int(user32.GetForegroundWindow() or 0)
        if previous == self.target_hwnd:
            return previous, False
        self.guard.begin_pulse()
        try:
            if not _force_foreground(self.target_hwnd):
                raise RuntimeError("Windows refused the Roblox focus pulse.")
            self._sleep_ms(self.focus_lead_ms)
            return previous, True
        except Exception:
            self.guard.cancel_pulse()
            raise

    def _restore(self, previous: int, guarded: bool) -> None:
        if not guarded:
            return
        if previous and previous != self.target_hwnd and user32.IsWindow(wintypes.HWND(previous)):
            _force_foreground(previous)
            self._sleep_ms(self.restore_tail_ms)
        self.guard.end_pulse_and_replay()

    def _quick_pulse(self, callback) -> None:
        previous, guarded = self._enter_target()
        try:
            callback()
        finally:
            self._restore(previous, guarded)

    def _hold_with_yield(self, previous: int, guarded: bool, hold_ms: float, release_callback) -> None:
        if not guarded:
            self._sleep_ms(hold_ms)
            release_callback()
            return
        started = time.monotonic()
        user_active = self.guard.recent_activity(220.0)
        interrupted = user_active or self.guard.wait_for_activity(max(0.0, hold_ms) / 1000.0)
        if not interrupted:
            release_callback()
            self._restore(previous, guarded)
            return

        # A physical key/click arrived while Roblox had focus. Yield to the
        # user's window immediately, replay that input there, then finish the
        # piano key-up with a second micro-pulse after the musical hold expires.
        elapsed_ms = (time.monotonic() - started) * 1000.0
        self._restore(previous, guarded)
        self._sleep_ms(max(0.0, hold_ms - elapsed_ms))
        self._quick_pulse(release_callback)

    def tap_char(self, char: str, hold_ms: float = 18.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0) -> None:
        if not char:
            return
        _vk, scan, shifted = _describe_char(char)
        previous, guarded = self._enter_target()
        key_down = False
        try:
            if shifted:
                _send_scans([self.shift_scan])
                self._sleep_ms(modifier_lead_ms)
            _send_scans([scan])
            key_down = True
            if shifted:
                self._sleep_ms(modifier_tail_ms)
                _send_scans([self.shift_scan], True)
            self._hold_with_yield(previous, guarded, hold_ms, lambda: _send_scans([scan], True))
            key_down = False
        except Exception:
            if key_down:
                try:
                    self._quick_pulse(lambda: _send_scans([scan], True))
                except Exception:
                    pass
            try:
                _send_scans([self.shift_scan], True)
            except Exception:
                pass
            self._restore(previous, guarded)
            raise

    def tap_chord(self, chars: str, hold_ms: float = 22.0, modifier_lead_ms: float = 6.0, modifier_tail_ms: float = 2.0, chord_spread_ms: float = 4.0) -> None:
        descriptors = [_describe_char(char) for char in chars if char]
        if not descriptors:
            return
        black = [scan for _vk, scan, shifted in descriptors if shifted]
        white = [scan for _vk, scan, shifted in descriptors if not shifted]
        all_down: list[int] = []
        previous, guarded = self._enter_target()
        try:
            if black:
                _send_scans([self.shift_scan])
                self._sleep_ms(modifier_lead_ms)
                _send_scans(black)
                all_down.extend(black)
                if white:
                    self._sleep_ms(chord_spread_ms)
                else:
                    self._sleep_ms(modifier_tail_ms)
                _send_scans([self.shift_scan], True)
            if white:
                _send_scans(white)
                all_down.extend(white)

            release = lambda: _send_scans(list(reversed(all_down)), True)
            self._hold_with_yield(previous, guarded, hold_ms, release)
            all_down.clear()
        except Exception:
            if all_down:
                try:
                    self._quick_pulse(lambda: _send_scans(list(reversed(all_down)), True))
                except Exception:
                    pass
            try:
                _send_scans([self.shift_scan], True)
            except Exception:
                pass
            self._restore(previous, guarded)
            raise

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.guard.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
