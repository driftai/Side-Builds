"""
Controller Emulation Backends & Factory.
Supports:
1. Virtual Xbox 360 Controller (XInput via ViGEmBus)
2. Virtual DualShock 4 Controller (DirectInput/DS4 via ViGEmBus)
3. Direct Windows Scan-Code Injection & Target-Locked SendInput
4. Diagnostic Noop Controller
"""

import logging
from typing import Dict, Any, List

from .backends import (
    BaseController,
    Xbox360Backend,
    DualShock4Backend,
    TargetLockedKeyboardBackend,
    KeyboardInjectionBackend,
    VirtualKeyboardHIDBackend,
    NoopBackend,
    VIGEM_AVAILABLE,
    WIN32_AVAILABLE,
    _dom_code_to_vk,
    _DOM_CODE_TO_VK,
)

logger = logging.getLogger("OmniPad.Controller")


class ControllerFactory:
    """Factory to instantiate and discover controller backends."""

    @staticmethod
    def get_available_backends() -> List[Dict[str, Any]]:
        backends = []
        if VIGEM_AVAILABLE:
            backends.append({
                "id": "xbox360",
                "name": "Xbox 360 (ViGEmBus)",
                "description": "Recommended. Full XInput support for Steam, SF6, Tekken 8, and modern PC games.",
                "available": True,
                "recommended": True
            })
            backends.append({
                "id": "ds4",
                "name": "DualShock 4 (ViGEmBus)",
                "description": "PlayStation layout emulation for DirectInput & PS Remote Play.",
                "available": True,
                "recommended": False
            })
        else:
            backends.append({
                "id": "xbox360",
                "name": "Xbox 360 (ViGEmBus)",
                "description": "Driver not installed. Virtual gamepad disabled.",
                "available": False,
                "recommended": False
            })
            backends.append({
                "id": "ds4",
                "name": "DualShock 4 (ViGEmBus)",
                "description": "Driver not installed.",
                "available": False,
                "recommended": False
            })

        if WIN32_AVAILABLE:
            backends.append({
                "id": "keyboard_target",
                "name": "Keyboard 2 (Target-Locked Scan-Code)",
                "description": "Normal-mode scan-code compatibility bridge. Preserves remote key positions and only runs while the selected game window is foreground.",
                "available": True,
                "recommended": False
            })
            backends.append({
                "id": "keyboard",
                "name": "Keyboard Key Injection (Legacy)",
                "description": "Legacy system keyboard injection. Use Target-Locked for safer game-only routing.",
                "available": True,
                "recommended": False
            })
            backends.append({
                "id": "virtual_keyboard",
                "name": "Virtual Keyboard HID (VHF)",
                "description": "Preserved future Microsoft-signed path for a true separate HID keyboard device.",
                "available": False,
                "recommended": False
            })

        backends.append({
            "id": "noop",
            "name": "Noop / Diagnostic Simulation",
            "description": "Inspect inputs without creating a Windows device.",
            "available": True,
            "recommended": False
        })

        return backends

    @staticmethod
    def create(backend_id: str, slot_id: int) -> BaseController:
        backend_id = backend_id.lower()
        if backend_id == "xbox360":
            if VIGEM_AVAILABLE:
                return Xbox360Backend(slot_id)
            logger.warning("ViGEmBus unavailable, falling back to Noop for slot %d", slot_id)
            return NoopBackend(slot_id)
        elif backend_id == "ds4":
            if VIGEM_AVAILABLE:
                return DualShock4Backend(slot_id)
            logger.warning("ViGEmBus unavailable, falling back to Noop for slot %d", slot_id)
            return NoopBackend(slot_id)
        elif backend_id in ("keyboard_target", "keyboard"):
            if WIN32_AVAILABLE:
                return TargetLockedKeyboardBackend(slot_id) if backend_id == "keyboard_target" else KeyboardInjectionBackend(slot_id)
            return NoopBackend(slot_id)
        elif backend_id == "virtual_keyboard":
            return VirtualKeyboardHIDBackend(slot_id)
        elif backend_id == "noop":
            return NoopBackend(slot_id)
        else:
            if VIGEM_AVAILABLE:
                return Xbox360Backend(slot_id)
            return NoopBackend(slot_id)


__all__ = [
    "BaseController",
    "Xbox360Backend",
    "DualShock4Backend",
    "TargetLockedKeyboardBackend",
    "KeyboardInjectionBackend",
    "VirtualKeyboardHIDBackend",
    "NoopBackend",
    "ControllerFactory",
    "VIGEM_AVAILABLE",
    "WIN32_AVAILABLE",
    "_dom_code_to_vk",
    "_DOM_CODE_TO_VK",
]
