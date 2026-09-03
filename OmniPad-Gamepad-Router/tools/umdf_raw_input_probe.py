"""Small Win32 Raw Input receiver used by the installed UMDF smoke."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import time
from typing import Callable, Dict, List

WM_INPUT = 0x00FF
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
RIM_TYPEKEYBOARD = 1
RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIDEV_INPUTSINK = 0x00000100
PM_REMOVE = 0x0001
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_EX_TOOLWINDOW = 0x00000080
SW_SHOW = 5


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]


class WNDCLASSW(ctypes.Structure):
    pass


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
        ("lPrivate", wintypes.DWORD),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

WNDCLASSW._fields_ = [
    ("style", wintypes.UINT),
    ("lpfnWndProc", WNDPROC),
    ("cbClsExtra", ctypes.c_int),
    ("cbWndExtra", ctypes.c_int),
    ("hInstance", wintypes.HINSTANCE),
    ("hIcon", wintypes.HICON),
    ("hCursor", wintypes.HANDLE),
    ("hbrBackground", wintypes.HBRUSH),
    ("lpszMenuName", wintypes.LPCWSTR),
    ("lpszClassName", wintypes.LPCWSTR),
]


class RawKeyboardReceiver:
    """Receive keyboard Raw Input and retain only OmniPad's HID identity."""

    def __init__(self) -> None:
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_functions()
        self.events: List[Dict[str, object]] = []
        self._device_names: Dict[int, str] = {}
        self._previous_foreground = self.user32.GetForegroundWindow()
        self._wndproc = WNDPROC(self._window_proc)
        self.class_name = f"OmniPadUmdfSmoke{os.getpid()}"
        self.hinstance = self.kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = self.hinstance
        window_class.lpszClassName = self.class_name
        if not self.user32.RegisterClassW(ctypes.byref(window_class)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = self.user32.CreateWindowExW(
            WS_EX_TOOLWINDOW, self.class_name, "OmniPad HID Smoke Receiver",
            WS_OVERLAPPEDWINDOW, 100, 100, 360, 90, None, None, self.hinstance, None,
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        raw_device = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, self.hwnd)
        if not self.user32.RegisterRawInputDevices(
            ctypes.byref(raw_device), 1, ctypes.sizeof(RAWINPUTDEVICE)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        self.user32.ShowWindow(self.hwnd, SW_SHOW)
        self.user32.SetForegroundWindow(self.hwnd)
        self.user32.SetFocus(self.hwnd)
        self.pump(0.1)

    def _configure_functions(self) -> None:
        self.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
            wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
        ]
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT,
        ]
        self.user32.RegisterRawInputDevices.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.SetFocus.argtypes = [wintypes.HWND]
        self.user32.SetFocus.restype = wintypes.HWND
        self.user32.PeekMessageW.argtypes = [
            ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
        ]
        self.user32.PeekMessageW.restype = wintypes.BOOL
        self.user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
        self.user32.TranslateMessage.restype = wintypes.BOOL
        self.user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
        self.user32.DispatchMessageW.restype = ctypes.c_ssize_t
        self.user32.DestroyWindow.argtypes = [wintypes.HWND]
        self.user32.DestroyWindow.restype = wintypes.BOOL
        self.user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        self.user32.UnregisterClassW.restype = wintypes.BOOL
        self.user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        ]
        self.user32.DefWindowProcW.restype = ctypes.c_ssize_t
        self.user32.GetRawInputData.argtypes = [
            wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
            ctypes.POINTER(wintypes.UINT), wintypes.UINT,
        ]
        self.user32.GetRawInputData.restype = wintypes.UINT
        self.user32.GetRawInputDeviceInfoW.argtypes = [
            wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT),
        ]
        self.user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

    def _device_name(self, handle: int) -> str:
        if handle in self._device_names:
            return self._device_names[handle]
        length = wintypes.UINT(0)
        self.user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, None, ctypes.byref(length))
        name = ""
        if length.value:
            buffer = ctypes.create_unicode_buffer(length.value + 1)
            self.user32.GetRawInputDeviceInfoW(
                handle, RIDI_DEVICENAME, buffer, ctypes.byref(length)
            )
            name = buffer.value
        self._device_names[handle] = name
        return name

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_INPUT:
            size = wintypes.UINT(0)
            header_size = ctypes.sizeof(RAWINPUTHEADER)
            self.user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), header_size)
            if size.value:
                buffer = ctypes.create_string_buffer(size.value)
                result = self.user32.GetRawInputData(
                    lparam, RID_INPUT, buffer, ctypes.byref(size), header_size
                )
                if result == size.value:
                    header = RAWINPUTHEADER.from_buffer_copy(buffer.raw[:header_size])
                    if header.dwType == RIM_TYPEKEYBOARD:
                        keyboard = RAWKEYBOARD.from_buffer_copy(
                            buffer.raw[header_size:header_size + ctypes.sizeof(RAWKEYBOARD)]
                        )
                        handle = int(header.hDevice or 0)
                        name = self._device_name(handle)
                        if "VID_0F0F" in name.upper() and "PID_0303" in name.upper():
                            self.events.append({
                                "at": time.monotonic(), "device": name,
                                "make_code": int(keyboard.MakeCode), "flags": int(keyboard.Flags),
                                "vkey": int(keyboard.VKey), "message": int(keyboard.Message),
                                "down": keyboard.Message in (WM_KEYDOWN, WM_SYSKEYDOWN),
                                "up": keyboard.Message in (WM_KEYUP, WM_SYSKEYUP),
                            })
        return self.user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def pump(self, seconds: float, until: Callable[[], bool] | None = None) -> bool:
        deadline = time.monotonic() + seconds
        message = MSG()
        while time.monotonic() < deadline:
            while self.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                self.user32.TranslateMessage(ctypes.byref(message))
                self.user32.DispatchMessageW(ctypes.byref(message))
            if until and until():
                return True
            time.sleep(0.005)
        return bool(until and until())

    def close(self) -> None:
        if getattr(self, "hwnd", None):
            self.user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        self.user32.UnregisterClassW(self.class_name, self.hinstance)
        if self._previous_foreground:
            self.user32.SetForegroundWindow(self._previous_foreground)


__all__ = ["RawKeyboardReceiver"]
