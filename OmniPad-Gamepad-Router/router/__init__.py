"""
OmniPad Gamepad Router - Core Engine
Connect remote players to physical/virtual local controllers over LAN or Cloudflare Tunnel.
"""

import time

from .socd import SOCDCleaner, SOCDMode
from .controller import (
    BaseController,
    Xbox360Backend,
    DualShock4Backend,
    KeyboardInjectionBackend,
    VirtualKeyboardHIDBackend,
    NoopBackend,
    ControllerFactory,
    VIGEM_AVAILABLE
)
from .vhf_keyboard import VHFKeyboardDevice, build_keyboard_report
from .slot_manager import SlotManager, PlayerSlot
from .tunnel import TunnelManager, get_local_ips
from .profiles import ProfileManager


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


def _factory_backends():
    backends = _original_factory_backends()
    available, error = _refresh_vhf_status()
    for item in backends:
        if item.get("id") == "virtual_keyboard":
            item.update({
                "available": available,
                "recommended": available,
                "description": (
                    "True separate HID keyboard device via the OmniPad VHF/KMDF driver."
                    if available else
                    "Preserved future Microsoft-signed path for a true separate HID keyboard."
                ),
            })
            break
    return backends


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
