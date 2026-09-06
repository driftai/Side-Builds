"""Separate virtual keyboard backend for the normal-mode UMDF HID driver."""

from typing import Any, Dict

from .base import BaseController
from ..umdf_keyboard import UmdfKeyboardDevice, build_keyboard_report


class VirtualKeyboardPortBackend(BaseController):
    """Real second keyboard backed by the OmniPad UMDF virtual HID port."""

    backend_id = "virtual_keyboard_port"
    display_name = "Virtual Keyboard Port (UMDF)"

    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.device, error = UmdfKeyboardDevice.try_open()
        if self.device is None:
            raise RuntimeError(
                "OmniPad UMDF keyboard port is unavailable. "
                "Build, sign, and install drivers/virtual-keyboard-umdf first. "
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
