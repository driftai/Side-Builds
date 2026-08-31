"""
Simulation and Diagnostic Noop Controller Backend.
"""

import logging
from typing import Dict, Any

from .base import BaseController

logger = logging.getLogger("OmniPad.Controller.Noop")


class NoopBackend(BaseController):
    """Headless Diagnostic and Simulation Backend."""
    backend_id = "noop"
    display_name = "Simulation / Diagnostic Noop"

    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.last_state: Dict[str, Any] = {}
        logger.info("[Slot %d] Created Noop Backend", self.slot_id)

    def apply(self, state: Dict[str, Any]) -> None:
        self.last_state = state

    def release_all(self) -> None:
        self.last_state = {}

    def close(self) -> None:
        self.last_state = {}
        logger.info("[Slot %d] Noop Backend closed", self.slot_id)
