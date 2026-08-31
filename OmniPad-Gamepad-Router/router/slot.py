"""
Player Slot Data Structure & State Serialization.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from fastapi import WebSocket

from .controller import BaseController
from .socd import SOCDCleaner, SOCDMode


@dataclass
class PlayerSlot:
    slot_id: int                           # 1 = Player 2, 2 = Player 3, etc.
    display_title: str                     # "Player 2", "Player 3"
    controller_type: str = "xbox360"       # "xbox360", "ds4", "keyboard", "noop"
    controller: Optional[BaseController] = None
    friend_name: Optional[str] = None
    websocket: Optional[WebSocket] = None
    connected_at: float = 0.0
    last_seen: float = 0.0
    last_seq: int = -1
    packet_count: int = 0
    latency_ms: Optional[float] = None
    jitter_ms: Optional[float] = None
    _recent_latencies: List[float] = field(default_factory=list)
    socd_mode: SOCDMode = SOCDMode.NEUTRAL
    socd_cleaner: SOCDCleaner = field(default_factory=SOCDCleaner)
    deadzone: float = 0.15
    muted: bool = False
    is_active: bool = False
    last_state: Dict[str, Any] = field(default_factory=lambda: {
        "buttons": {},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
    })
    client_packets: Dict[Any, Dict[str, Any]] = field(default_factory=dict)
    client_last_seen: Dict[Any, float] = field(default_factory=dict)

    def get_public_state(self) -> Dict[str, Any]:
        now = time.time()
        is_alive = bool(self.friend_name and (now - self.last_seen < 2.0))
        return {
            "slot_id": self.slot_id,
            "title": self.display_title,
            "controller_type": self.controller_type,
            "backend_name": getattr(self.controller, "display_name", "None") if self.controller else "None",
            "connected": self.friend_name is not None,
            "friend_name": self.friend_name,
            "is_alive": is_alive,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "jitter_ms": round(self.jitter_ms, 1) if self.jitter_ms is not None else None,
            "packet_count": self.packet_count,
            "socd_mode": self.socd_mode.value,
            "deadzone": self.deadzone,
            "muted": self.muted,
            "input_surface": self.last_state.get("input_surface", "unknown"),
            "mapping_profile": self.last_state.get("mapping_profile", "universal"),
            "last_state": self.last_state,
        }
