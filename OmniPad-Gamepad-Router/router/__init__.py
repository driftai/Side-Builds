"""
OmniPad Gamepad Router - Core Engine
Connect remote players to physical/virtual local controllers over LAN or Cloudflare Tunnel.
"""

import time

from .socd import SOCDCleaner, SOCDMode
from . import controller as _controller
from .controller import (
    BaseController,
    Xbox360Backend,
    DualShock4Backend,
    KeyboardInjectionBackend,
    NoopBackend,
    ControllerFactory,
    VIGEM_AVAILABLE
)
from .vhf_keyboard import VHFKeyboardDevice, build_keyboard_report
from .slot_manager import SlotManager, PlayerSlot
from .tunnel import TunnelManager, get_local_ips
from .profiles import ProfileManager


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
        self.last_error = None

    def apply(self, state):
        report = build_keyboard_report(state.get("key_codes") or [])
        self.device.submit_report(report)
        self.last_report = report
        self.last_error = None

    def release_all(self):
        if self.device:
            self.device.release_all()
            self.last_report = bytes(8)

    def close(self):
        if self.device:
            try:
                self.device.close()
            finally:
                self.device = None


_original_factory_create = ControllerFactory.create
_original_factory_backends = ControllerFactory.get_available_backends
_vhf_cache_available = False
_vhf_cache_error = "Not checked yet"
_vhf_cache_at = 0.0


def _refresh_vhf_status(force: bool = False):
    global _vhf_cache_available, _vhf_cache_error, _vhf_cache_at
    now = time.monotonic()
    if not force and (now - _vhf_cache_at) < 2.0:
        return _vhf_cache_available, _vhf_cache_error
    device, error = VHFKeyboardDevice.try_open()
    if device is not None:
        device.close()
        _vhf_cache_available = True
        _vhf_cache_error = ""
    else:
        _vhf_cache_available = False
        _vhf_cache_error = error or "Unknown VHF device error"
    _vhf_cache_at = now
    return _vhf_cache_available, _vhf_cache_error


def _factory_create(backend_id: str, slot_id: int):
    if backend_id.lower() == "virtual_keyboard":
        return VirtualKeyboardHIDBackend(slot_id)
    return _original_factory_create(backend_id, slot_id)


def _factory_backends():
    backends = _original_factory_backends()
    available, error = _refresh_vhf_status()
    for item in backends:
        if item.get("id") == "virtual_keyboard":
            item.update({
                "available": available,
                "recommended": True,
                "description": (
                    "True separate HID keyboard device via the OmniPad VHF/KMDF driver."
                    if available else
                    "Requires the OmniPad VHF/KMDF virtual keyboard driver."
                ),
            })
            break
    return backends


ControllerFactory.create = staticmethod(_factory_create)
ControllerFactory.get_available_backends = staticmethod(_factory_backends)

__all__ = [
    "SOCDCleaner",
    "SOCDMode",
    "BaseController",
    "Xbox360Backend",
    "DualShock4Backend",
    "KeyboardInjectionBackend",
    "VirtualKeyboardHIDBackend",
    "NoopBackend",
    "ControllerFactory",
    "VIGEM_AVAILABLE",
    "VHFKeyboardDevice",
    "build_keyboard_report",
    "_refresh_vhf_status",
    "SlotManager",
    "PlayerSlot",
    "TunnelManager",
    "get_local_ips",
    "ProfileManager"
]
