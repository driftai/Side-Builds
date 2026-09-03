"""
Controller Backend Adapters Package.
"""

from .base import BaseController, VIGEM_AVAILABLE, WIN32_AVAILABLE
from .xbox import Xbox360Backend
from .ds4 import DualShock4Backend
from .keyboard import (
    TargetLockedKeyboardBackend,
    KeyboardInjectionBackend,
    _dom_code_to_vk,
    _DOM_CODE_TO_VK,
)
from .vhf import VirtualKeyboardHIDBackend
from .umdf_keyboard import VirtualKeyboardPortBackend
from .noop import NoopBackend

__all__ = [
    "BaseController",
    "Xbox360Backend",
    "DualShock4Backend",
    "TargetLockedKeyboardBackend",
    "KeyboardInjectionBackend",
    "VirtualKeyboardHIDBackend",
    "VirtualKeyboardPortBackend",
    "NoopBackend",
    "VIGEM_AVAILABLE",
    "WIN32_AVAILABLE",
    "_dom_code_to_vk",
    "_DOM_CODE_TO_VK",
]
