"""User-mode bridge for the OmniPad UMDF virtual keyboard port.

The bridge opens only the device's vendor-defined HID collection and submits
feature report 2. Windows owns the separate keyboard collection (report 1).
"""

import ctypes
from ctypes import wintypes
import logging
from typing import Iterator, Optional, Tuple

from .vhf_keyboard import REPORT_SIZE, build_keyboard_report

logger = logging.getLogger("OmniPad.UmdfKeyboard")

IS_WINDOWS = hasattr(ctypes, "windll")
OMNIPAD_UMDF_VID = 0x0F0F
OMNIPAD_UMDF_PID = 0x0303
CONTROL_USAGE_PAGE = 0xFF00
CONTROL_USAGE = 0x0001
CONTROL_REPORT_ID = 0x02
CONTROL_REPORT_SIZE = REPORT_SIZE + 1


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


def build_control_feature_report(keyboard_report: bytes) -> bytes:
    """Wrap one 8-byte keyboard state in the vendor feature report."""
    if len(keyboard_report) != REPORT_SIZE:
        raise ValueError(f"Keyboard report must be exactly {REPORT_SIZE} bytes")
    return bytes([CONTROL_REPORT_ID]) + keyboard_report


class UmdfKeyboardDevice:
    """Handle to the control collection of OmniPad's UMDF HID device."""

    def __init__(self) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("OmniPad UMDF virtual keyboard is Windows-only.")

        self._hid = ctypes.WinDLL("hid", use_last_error=True)
        self._cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_functions()
        self._handle = None
        self._active_path: Optional[str] = None
        self._open_control_collection()

    def _configure_functions(self) -> None:
        self._hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
        self._hid.HidD_GetHidGuid.restype = None
        self._hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
        self._hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
        self._hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
        self._hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
        self._hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
        self._hid.HidD_FreePreparsedData.restype = wintypes.BOOLEAN
        self._hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
        self._hid.HidP_GetCaps.restype = ctypes.c_long
        self._hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
        self._hid.HidD_SetFeature.restype = wintypes.BOOLEAN

        self._cfgmgr32.CM_Get_Device_Interface_List_SizeW.argtypes = [
            ctypes.POINTER(wintypes.ULONG), ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.ULONG
        ]
        self._cfgmgr32.CM_Get_Device_Interface_List_SizeW.restype = wintypes.ULONG
        self._cfgmgr32.CM_Get_Device_Interface_ListW.argtypes = [
            ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG
        ]
        self._cfgmgr32.CM_Get_Device_Interface_ListW.restype = wintypes.ULONG

        self._kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        self._kernel32.CreateFileW.restype = wintypes.HANDLE
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def _iter_hid_paths(self) -> Iterator[str]:
        hid_guid = GUID()
        self._hid.HidD_GetHidGuid(ctypes.byref(hid_guid))
        length = wintypes.ULONG(0)
        flags = 0  # CM_GET_DEVICE_INTERFACE_LIST_PRESENT
        result = self._cfgmgr32.CM_Get_Device_Interface_List_SizeW(
            ctypes.byref(length), ctypes.byref(hid_guid), None, flags
        )
        if result != 0 or length.value <= 1:
            return

        buffer = ctypes.create_unicode_buffer(length.value)
        result = self._cfgmgr32.CM_Get_Device_Interface_ListW(
            ctypes.byref(hid_guid), None, buffer, length.value, flags
        )
        if result != 0:
            return
        for path in buffer[:length.value].split("\0"):
            if path:
                yield path

    def _matches_control_collection(self, handle: int) -> bool:
        attributes = HIDD_ATTRIBUTES()
        attributes.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
        if not self._hid.HidD_GetAttributes(handle, ctypes.byref(attributes)):
            return False
        if attributes.VendorID != OMNIPAD_UMDF_VID or attributes.ProductID != OMNIPAD_UMDF_PID:
            return False

        preparsed = ctypes.c_void_p()
        if not self._hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
            return False
        try:
            caps = HIDP_CAPS()
            status = self._hid.HidP_GetCaps(preparsed, ctypes.byref(caps))
            return (
                status == 0x00110000
                and caps.UsagePage == CONTROL_USAGE_PAGE
                and caps.Usage == CONTROL_USAGE
                and caps.FeatureReportByteLength >= CONTROL_REPORT_SIZE
            )
        finally:
            self._hid.HidD_FreePreparsedData(preparsed)

    def _open_control_collection(self) -> None:
        generic_read = 0x80000000
        generic_write = 0x40000000
        share_read = 0x00000001
        share_write = 0x00000002
        open_existing = 3
        invalid_handle = wintypes.HANDLE(-1).value
        last_error = 0

        for path in self._iter_hid_paths():
            normalized_path = path.lower()
            if "vid_0f0f" not in normalized_path or "pid_0303" not in normalized_path:
                continue
            handle = self._kernel32.CreateFileW(
                path,
                generic_read | generic_write,
                share_read | share_write,
                None,
                open_existing,
                0,
                None,
            )
            if not handle or handle == invalid_handle:
                last_error = ctypes.get_last_error()
                continue
            if self._matches_control_collection(handle):
                self._handle = handle
                self._active_path = path
                return
            self._kernel32.CloseHandle(handle)

        raise OSError(
            last_error or 2,
            "OmniPad UMDF virtual keyboard control collection was not found",
        )

    @classmethod
    def try_open(cls) -> Tuple[Optional["UmdfKeyboardDevice"], Optional[str]]:
        try:
            return cls(), None
        except Exception as exc:
            return None, str(exc)

    @property
    def available(self) -> bool:
        return bool(self._handle)

    @property
    def device_path(self) -> Optional[str]:
        return self._active_path

    def submit_report(self, report: bytes) -> None:
        if not self._handle:
            raise RuntimeError("OmniPad UMDF virtual keyboard handle is closed")
        control = build_control_feature_report(report)
        buffer = (ctypes.c_ubyte * len(control)).from_buffer_copy(control)
        if not self._hid.HidD_SetFeature(self._handle, ctypes.byref(buffer), len(control)):
            error = ctypes.get_last_error()
            raise OSError(error, "OmniPad UMDF keyboard report submission failed")

    def release_all(self) -> None:
        if self._handle:
            try:
                self.submit_report(bytes(REPORT_SIZE))
            except Exception as exc:
                logger.debug("Error during UMDF release_all: %s", exc)

    def close(self) -> None:
        if self._handle:
            try:
                self.release_all()
            finally:
                self._kernel32.CloseHandle(self._handle)
                self._handle = None

    def __enter__(self) -> "UmdfKeyboardDevice":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


__all__ = [
    "UmdfKeyboardDevice",
    "build_control_feature_report",
    "build_keyboard_report",
    "OMNIPAD_UMDF_VID",
    "OMNIPAD_UMDF_PID",
    "CONTROL_USAGE_PAGE",
    "CONTROL_USAGE",
    "CONTROL_REPORT_ID",
    "CONTROL_REPORT_SIZE",
]
