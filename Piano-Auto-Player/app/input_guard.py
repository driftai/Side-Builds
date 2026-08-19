from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes


IS_WINDOWS = os.name == "nt"

# Low-level hooks let the focus-pulse route momentarily quarantine *physical*
# input while Roblox owns foreground focus. Injected piano events are never
# blocked. The quarantined input is replayed as soon as the user's window is
# restored, which keeps real keyboard/mouse work from leaking into Roblox.

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14
    HC_ACTION = 0
    WM_QUIT = 0x0012
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105
    WM_MOUSEMOVE = 0x0200
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_MBUTTONDOWN = 0x0207
    WM_MBUTTONUP = 0x0208
    WM_MOUSEWHEEL = 0x020A
    WM_XBUTTONDOWN = 0x020B
    WM_XBUTTONUP = 0x020C
    WM_MOUSEHWHEEL = 0x020E

    LLKHF_EXTENDED = 0x01
    LLKHF_INJECTED = 0x10
    LLMHF_INJECTED = 0x01
    VK_F7 = 0x76

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    MOUSEEVENTF_XDOWN = 0x0080
    MOUSEEVENTF_XUP = 0x0100
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_HWHEEL = 0x1000
    ULONG_PTR = wintypes.WPARAM

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

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

    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class PhysicalInputGuard:
    """Buffers physical keyboard/click input during a short focus pulse.

    The hooks stay installed for the lifetime of Background Assist, but only
    suppress input while ``begin_pulse`` is active. Between pulses they are
    passive and simply remember recent user activity so playback can choose
    the least disruptive pulse style.
    """

    def __init__(self) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("Physical input isolation is only available on Windows.")
        self._lock = threading.RLock()
        self._active = False
        self._buffer: list[tuple] = []
        self._last_activity = 0.0
        self._activity = threading.Event()
        self._ready = threading.Event()
        self._closed = False
        self._error: BaseException | None = None
        self._thread_id = 0
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_proc = HOOKPROC(self._keyboard_callback)
        self._mouse_proc = HOOKPROC(self._mouse_callback)
        self._thread = threading.Thread(target=self._hook_loop, daemon=True, name="piano-input-guard")
        self._thread.start()
        if not self._ready.wait(1.5):
            raise RuntimeError("Input isolation hook did not start in time.")
        if self._error:
            raise RuntimeError(f"Input isolation hook failed: {self._error}")

    def begin_pulse(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._activity.clear()
            self._active = True

    def recent_activity(self, within_ms: float = 220.0) -> bool:
        with self._lock:
            return (time.monotonic() - self._last_activity) * 1000.0 <= max(0.0, within_ms)

    def wait_for_activity(self, timeout_seconds: float) -> bool:
        return self._activity.wait(max(0.0, timeout_seconds))

    def end_pulse_and_replay(self) -> int:
        with self._lock:
            self._active = False
            buffered = list(self._buffer)
            self._buffer.clear()
            self._activity.clear()
        if buffered:
            self._replay(buffered)
        return len(buffered)

    def cancel_pulse(self) -> None:
        # A failed focus transition should never eat user input.
        self.end_pulse_and_replay()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._lock:
            self._active = False
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _hook_loop(self) -> None:
        try:
            self._thread_id = int(kernel32.GetCurrentThreadId())
            module = kernel32.GetModuleHandleW(None)
            self._keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._keyboard_proc, module, 0)
            self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, module, 0)
            if not self._keyboard_hook or not self._mouse_hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            if self._keyboard_hook:
                user32.UnhookWindowsHookEx(self._keyboard_hook)
            if self._mouse_hook:
                user32.UnhookWindowsHookEx(self._mouse_hook)

    def _keyboard_callback(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code < HC_ACTION:
            return user32.CallNextHookEx(None, n_code, w_param, l_param)
        data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if data.flags & LLKHF_INJECTED:
            return user32.CallNextHookEx(None, n_code, w_param, l_param)
        with self._lock:
            self._last_activity = time.monotonic()
            active = self._active
            if active and int(data.vkCode) != VK_F7:
                self._buffer.append(("keyboard", int(w_param), int(data.vkCode), int(data.scanCode), int(data.flags)))
                self._activity.set()
                return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _mouse_callback(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code < HC_ACTION:
            return user32.CallNextHookEx(None, n_code, w_param, l_param)
        data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if data.flags & LLMHF_INJECTED:
            return user32.CallNextHookEx(None, n_code, w_param, l_param)
        with self._lock:
            self._last_activity = time.monotonic()
            if not self._active:
                return user32.CallNextHookEx(None, n_code, w_param, l_param)
            self._activity.set()
            if int(w_param) != WM_MOUSEMOVE:
                self._buffer.append(("mouse", int(w_param), int(data.mouseData)))
            # Mouse movement is intentionally dropped only for the few ms that
            # Roblox owns focus; the next physical move resumes immediately.
            return 1

    @staticmethod
    def _keyboard_input(message: int, vk: int, scan: int, hook_flags: int) -> INPUT:
        flags = 0
        if scan:
            flags |= KEYEVENTF_SCANCODE
        if hook_flags & LLKHF_EXTENDED:
            flags |= KEYEVENTF_EXTENDEDKEY
        if message in (WM_KEYUP, WM_SYSKEYUP):
            flags |= KEYEVENTF_KEYUP
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0 if scan else vk, scan, flags, 0, 0))

    @staticmethod
    def _mouse_input(message: int, mouse_data: int) -> INPUT | None:
        flag_map = {
            WM_LBUTTONDOWN: MOUSEEVENTF_LEFTDOWN, WM_LBUTTONUP: MOUSEEVENTF_LEFTUP,
            WM_RBUTTONDOWN: MOUSEEVENTF_RIGHTDOWN, WM_RBUTTONUP: MOUSEEVENTF_RIGHTUP,
            WM_MBUTTONDOWN: MOUSEEVENTF_MIDDLEDOWN, WM_MBUTTONUP: MOUSEEVENTF_MIDDLEUP,
            WM_XBUTTONDOWN: MOUSEEVENTF_XDOWN, WM_XBUTTONUP: MOUSEEVENTF_XUP,
            WM_MOUSEWHEEL: MOUSEEVENTF_WHEEL, WM_MOUSEHWHEEL: MOUSEEVENTF_HWHEEL,
        }
        flags = flag_map.get(message)
        if not flags:
            return None
        return INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, mouse_data, flags, 0, 0))

    def _replay(self, events: list[tuple]) -> None:
        inputs: list[INPUT] = []
        for event in events:
            if event[0] == "keyboard":
                inputs.append(self._keyboard_input(*event[1:]))
            else:
                mouse_input = self._mouse_input(*event[1:])
                if mouse_input is not None:
                    inputs.append(mouse_input)
        if not inputs:
            return
        array = (INPUT * len(inputs))(*inputs)
        sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            # Never raise from replay: failing playback is preferable to losing
            # control of the user's desktop because cleanup threw an exception.
            return

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
