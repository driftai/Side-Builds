"""
Virtual Keyboard HID (VHF / KMDF) Placeholder Backend.
"""

from typing import Dict, Any

from .base import BaseController


class VirtualKeyboardHIDBackend(BaseController):
    """Placeholder for a true second keyboard HID implementation."""
    backend_id = "virtual_keyboard"
    display_name = "Virtual Keyboard HID (VHF)"

    def __init__(self, slot_id: int):
        raise RuntimeError(
            "OmniPad Virtual Keyboard HID driver is not installed. "
            "See drivers/virtual-keyboard/README.md."
        )

    def apply(self, state: Dict[str, Any]) -> None:
        pass

    def release_all(self) -> None:
        pass

    def close(self) -> None:
        pass
