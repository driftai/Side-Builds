"""Server configuration and settings."""

from pydantic import BaseModel


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    max_slots: int = 3
    watchdog_timeout: float = 0.25
    enable_tunnel: bool = False
    # Empty means server.py will generate a fresh per-run room code.
    room_code: str = ""
    target_gate_enabled: bool = True
    remote_focus_enabled: bool = False
    title: str = "OmniPad - Remote Gamepad Router"
    version: str = "1.1.2-dev"


config = AppConfig()
