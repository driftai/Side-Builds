"""Windows Raw Input Keyboard Enumeration & Diagnostic Utility.

Enumerates all keyboard devices registered with Windows Raw Input (user32.GetRawInputDeviceList),
identifying device names, handles, hardware IDs, and checking for OmniPad Virtual Keyboard presence.
"""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from router.umdf_keyboard import is_omnipad_hid_path

IS_WINDOWS = os.name == "nt"

RIM_TYPEMOUSE = 0
RIM_TYPEKEYBOARD = 1
RIM_TYPEHID = 2

RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000B


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [
        ("hDevice", wintypes.HANDLE),
        ("dwType", wintypes.DWORD),
    ]


class RID_DEVICE_INFO_KEYBOARD(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSubType", wintypes.DWORD),
        ("dwKeyboardMode", wintypes.DWORD),
        ("dwNumberOfFunctionKeys", wintypes.DWORD),
        ("dwNumberOfIndicators", wintypes.DWORD),
        ("dwNumberOfKeysTotal", wintypes.DWORD),
    ]


class RID_DEVICE_INFO(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [
            ("keyboard", RID_DEVICE_INFO_KEYBOARD),
            ("dummy", ctypes.c_byte * 32),
        ]
    _anonymous_ = ("u",)
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("u", _U),
    ]


def enumerate_keyboards():
    if not IS_WINDOWS:
        return []

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    GetRawInputDeviceList = user32.GetRawInputDeviceList
    GetRawInputDeviceList.argtypes = [ctypes.POINTER(RAWINPUTDEVICELIST), ctypes.POINTER(wintypes.UINT), wintypes.UINT]
    GetRawInputDeviceList.restype = wintypes.UINT

    GetRawInputDeviceInfoW = user32.GetRawInputDeviceInfoW
    GetRawInputDeviceInfoW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT)]
    GetRawInputDeviceInfoW.restype = wintypes.UINT

    num_devices = wintypes.UINT(0)
    struct_size = ctypes.sizeof(RAWINPUTDEVICELIST)

    res = GetRawInputDeviceList(None, ctypes.byref(num_devices), struct_size)
    if res == wintypes.UINT(-1).value or num_devices.value == 0:
        return []

    device_array = (RAWINPUTDEVICELIST * num_devices.value)()
    res = GetRawInputDeviceList(device_array, ctypes.byref(num_devices), struct_size)
    if res == wintypes.UINT(-1).value:
        return []

    keyboards = []
    for i in range(num_devices.value):
        item = device_array[i]
        if item.dwType != RIM_TYPEKEYBOARD:
            continue

        name_len = wintypes.UINT(0)
        GetRawInputDeviceInfoW(item.hDevice, RIDI_DEVICENAME, None, ctypes.byref(name_len))
        name = "Unknown"
        if name_len.value > 0:
            name_buf = ctypes.create_unicode_buffer(name_len.value)
            GetRawInputDeviceInfoW(item.hDevice, RIDI_DEVICENAME, name_buf, ctypes.byref(name_len))
            name = name_buf.value

        info = RID_DEVICE_INFO()
        info.cbSize = ctypes.sizeof(RID_DEVICE_INFO)
        info_size = wintypes.UINT(info.cbSize)
        num_keys = 0
        fn_keys = 0
        if GetRawInputDeviceInfoW(item.hDevice, RIDI_DEVICEINFO, ctypes.byref(info), ctypes.byref(info_size)) != wintypes.UINT(-1).value:
            num_keys = info.keyboard.dwNumberOfKeysTotal
            fn_keys = info.keyboard.dwNumberOfFunctionKeys

        is_omnipad = is_omnipad_hid_path(name)
        keyboards.append({
            "handle": hex(item.hDevice or 0),
            "name": name,
            "total_keys": num_keys,
            "function_keys": fn_keys,
            "is_omnipad": is_omnipad
        })

    return keyboards


def main():
    print("\n" + "=" * 75)
    print("  WINDOWS RAW INPUT KEYBOARD ENUMERATION")
    print("=" * 75)

    keyboards = enumerate_keyboards()
    print(f"  Total Raw Input Keyboards Detected: {len(keyboards)}\n")

    omnipad_found = False
    for idx, kbd in enumerate(keyboards, 1):
        tag = " [OMNIPAD VIRTUAL KEYBOARD]" if kbd["is_omnipad"] else " [PHYSICAL / SYSTEM KEYBOARD]"
        if kbd["is_omnipad"]:
            omnipad_found = True
        print(f"  [{idx}] Device Handle: {kbd['handle']}{tag}")
        print(f"      Path: {kbd['name']}")
        print(f"      Keys: {kbd['total_keys']} total, {kbd['function_keys']} function keys\n")

    print("-" * 75)
    if omnipad_found:
        print("  STATUS: [ACTIVE] OmniPad Virtual Keyboard is enumerated as a separate Raw Input device!")
    else:
        print("  STATUS: [FALLBACK] OmniPad Virtual Keyboard is not currently active on this machine.")
        print("          SendInput / Target-Locked compatibility mode is active for 2P play.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
