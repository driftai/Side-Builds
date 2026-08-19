from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class RuntimeState:
    status: str = "idle"
    message: str = "Ready"
    current_index: int = 0
    total_events: int = 0
    current_token: str = ""
    active_song: str = ""
    started_at: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._lock = RLock()

    def update(self, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                else:
                    self.extra[key] = value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = max(self.total_events, 0)
            index = min(max(self.current_index, 0), total) if total else 0
            progress = (index / total) if total else 0.0
            return {
                "status": self.status,
                "message": self.message,
                "current_index": index,
                "total_events": total,
                "progress": progress,
                "current_token": self.current_token,
                "active_song": self.active_song,
                "started_at": self.started_at,
                **self.extra,
            }
