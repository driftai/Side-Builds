"""
OmniPad Gamepad Router - Background Keyboard Helper Companion Manager.
Manages the host-local native keyboard capture companion process for LAN and remote players.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from typing import Dict, Any, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from config import config
from .tunnel import get_local_ips

logger = logging.getLogger("OmniPad.BackgroundHelper")

# Global background helper companion process state
_background_helper_process: Optional[subprocess.Popen] = None
_background_helper_status_file: Optional[str] = None
_background_helper_lock = threading.Lock()


class BackgroundCaptureRequest(BaseModel):
    play_url: Optional[str] = None
    slot_id: int = 1
    name: str = "Player 2"
    enabled: bool = True


def background_helper_running() -> bool:
    return _background_helper_process is not None and _background_helper_process.poll() is None


def read_background_helper_status() -> Dict[str, Any]:
    if not _background_helper_status_file:
        return {"state": "off"}
    try:
        with open(_background_helper_status_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {"state": "unknown"}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "starting" if background_helper_running() else "off"}


def cleanup_background_helper_status_file() -> None:
    global _background_helper_status_file
    if _background_helper_status_file:
        try:
            os.remove(_background_helper_status_file)
        except OSError:
            pass
    _background_helper_status_file = None


def shutdown_background_helper() -> None:
    global _background_helper_process, _background_helper_status_file
    with _background_helper_lock:
        if background_helper_running():
            _background_helper_process.terminate()
            try:
                _background_helper_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _background_helper_process.kill()
        _background_helper_process = None
        cleanup_background_helper_status_file()


def background_helper_allowed(request: Request) -> bool:
    client = request.client.host if request.client else ""
    return client in {"127.0.0.1", "::1", *get_local_ips()}


async def start_background_helper(req: BackgroundCaptureRequest, request: Request, slot_manager, static_dir: str) -> Dict[str, Any]:
    global _background_helper_process, _background_helper_status_file
    if not background_helper_allowed(request):
        raise HTTPException(status_code=403, detail="Background capture must be enabled from the OmniPad host machine.")

    helper_path = os.path.join(static_dir, "tools", "background_keyboard_helper.py")
    if not os.path.exists(helper_path):
        raise HTTPException(status_code=404, detail="Background keyboard helper is missing.")

    with _background_helper_lock:
        if req.enabled:
            if background_helper_running():
                status = read_background_helper_status()
                return {
                    "ok": True,
                    "running": True,
                    "ready": bool(status.get("state") == "ready"),
                    "already_running": True,
                    "status": status,
                }

            cleanup_background_helper_status_file()
            status_dir = os.path.join(tempfile.gettempdir(), "OmniPad")
            os.makedirs(status_dir, exist_ok=True)
            _background_helper_status_file = os.path.join(
                status_dir, f"background-keyboard-{os.getpid()}-{int(time.time() * 1000)}.json"
            )

            local_port = config.port
            if req.play_url:
                try:
                    parsed = urlsplit(req.play_url)
                    if parsed.port and parsed.hostname in {"localhost", "127.0.0.1", "::1", *get_local_ips()}:
                        local_port = parsed.port
                except Exception:
                    pass
            elif request and request.url.port:
                local_port = request.url.port

            room_code = slot_manager.room_code if slot_manager else "SF6-ROOM"
            local_ws_url = f"ws://127.0.0.1:{local_port}/ws/player"
            command = [
                sys.executable, helper_path,
                "--ws-url", local_ws_url,
                "--code", room_code,
                "--slot", str(max(1, int(req.slot_id))),
                "--name", str(req.name or "Player 2")[:24],
                "--ready-file", _background_helper_status_file,
            ]
            _background_helper_process = subprocess.Popen(
                command,
                cwd=os.path.dirname(os.path.dirname(__file__)),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )

            deadline = time.monotonic() + 5.0
            last_status: Dict[str, Any] = {"state": "starting"}
            while time.monotonic() < deadline:
                if not background_helper_running():
                    last_status = read_background_helper_status()
                    _background_helper_process = None
                    cleanup_background_helper_status_file()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Background helper exited during startup: {last_status.get('error', 'unknown error')}"
                    )
                last_status = read_background_helper_status()
                if last_status.get("state") == "ready":
                    logger.info("Background keyboard capture is ready for slot %d", req.slot_id)
                    return {
                        "ok": True,
                        "running": True,
                        "ready": True,
                        "status": last_status,
                    }
                await asyncio.sleep(0.05)

            if background_helper_running():
                _background_helper_process.terminate()
                try:
                    _background_helper_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _background_helper_process.kill()
            _background_helper_process = None
            cleanup_background_helper_status_file()
            raise HTTPException(
                status_code=504,
                detail=f"Background helper did not become ready: {last_status.get('error', last_status.get('state', 'startup timeout'))}"
            )

        if background_helper_running():
            _background_helper_process.terminate()
            try:
                _background_helper_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _background_helper_process.kill()
        _background_helper_process = None
        cleanup_background_helper_status_file()

    if slot_manager:
        await slot_manager.panic_reset(req.slot_id)
    return {"ok": True, "running": False, "ready": False}
