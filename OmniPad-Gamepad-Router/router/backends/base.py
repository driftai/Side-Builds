"""
Base Controller Interface and Driver Availability Flags.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger("OmniPad.Controller")

# Check ViGEm / vgamepad availability
VIGEM_AVAILABLE = False
try:
    import vgamepad as vg
    VIGEM_AVAILABLE = True
except Exception as e:
    vg = None
    logger.warning("vgamepad is not available: %s", e)

# Check Windows keybd_event / Win32 availability
WIN32_AVAILABLE = False
try:
    import win32api
    import win32con
    WIN32_AVAILABLE = True
except Exception:
    win32api = None
    win32con = None


class BaseController(ABC):
    """Abstract interface for all controller backends."""
    backend_id: str = "base"
    display_name: str = "Base Controller"

    @abstractmethod
    def apply(self, state: Dict[str, Any]) -> None:
        """Apply a normalized controller state snapshot."""
        pass

    @abstractmethod
    def release_all(self) -> None:
        """Release all pressed buttons and center all axes immediately."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Unplug or destroy the virtual controller device."""
        pass
