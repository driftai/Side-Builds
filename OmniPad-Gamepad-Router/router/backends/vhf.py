"""Virtual Keyboard HID backend for the OmniPad KMDF/VHF source driver."""

from typing import Dict, Any

from .base import BaseController
from ..vhf_keyboard import VHFKeyboardDevice, build_keyboard_report


class VirtualKeyboardHIDBackend(BaseController):
    """True second keyboard backed by the OmniPad VHF/KMDF device."""
    backend_id = "virtual_keyboard"
    display_name = "Virtual Keyboard HID (VHF)"

    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.device, error = VHFKeyboardDevice.try_open()
        if self.device is None:
            raise RuntimeError(
                "OmniPad VHF keyboard driver is unavailable. "
                "Build/install drivers/virtual-keyboard/OmniPadVirtualKeyboard.inf first. "
                f"Details: {error}"
            )
        self.last_report = bytes(8)

    def apply(self, state: Dict[str, Any]) -> None:
        key_codes = list(state.get("key_codes") or [])
        key_codes.extend(state.get("keyboard_fallback_codes") or [])
        report = build_keyboard_report(dict.fromkeys(key_codes))
        self.device.submit_report(report)
        self.last_report = report

    def release_all(self) -> None:
        if self.device:
            self.device.release_all()
            self.last_report = bytes(8)

    def close(self) -> None:
        if self.device:
            try:
                self.device.close()
            finally:
                self.device = None
