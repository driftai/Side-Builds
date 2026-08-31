"""REST API and HTML page routes with local-only management boundaries."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import config
from .targeting import target_manager
from .tunnel import get_local_ips
from .controller import VIGEM_AVAILABLE
from . import _refresh_vhf_status
from .background_helper import (
    BackgroundCaptureRequest,
    background_helper_running,
    read_background_helper_status,
    start_background_helper,
)
from .security import public_target_status, require_local_request, is_public_tunnel_request

logger = logging.getLogger("OmniPad.Routes")
router = APIRouter()
_slot_manager = None
_tunnel_manager = None
_profile_manager = None
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def setup_routes(slot_manager, tunnel_manager, profile_manager, static_dir: Optional[str] = None):
    global _slot_manager, _tunnel_manager, _profile_manager, _static_dir
    _slot_manager = slot_manager
    _tunnel_manager = tunnel_manager
    _profile_manager = profile_manager
    if static_dir:
        _static_dir = static_dir
    return router


@router.get("/")
async def host_dashboard(request: Request):
    require_local_request(request)
    index_file = os.path.join(_static_dir, "index.html")
    if not os.path.exists(index_file):
        raise HTTPException(status_code=404, detail="Dashboard index.html missing")
    return FileResponse(index_file)


@router.get("/play")
@router.get("/join")
async def remote_player_page():
    play_file = os.path.join(_static_dir, "play.html")
    if not os.path.exists(play_file):
        raise HTTPException(status_code=404, detail="Player play.html missing")
    return FileResponse(play_file)


@router.get("/api/background-capture/status")
async def background_capture_status(request: Request):
    require_local_request(request)
    status = read_background_helper_status()
    return {
        "running": background_helper_running(),
        "ready": bool(status.get("state") == "ready"),
        "status": status,
        "mode": "server_host_native",
    }


@router.get("/api/background-capture/input-state")
async def background_capture_input_state(request: Request, slot_id: int = 1):
    require_local_request(request)
    if _slot_manager is None:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    slot = _slot_manager.slots.get(slot_id)
    status = read_background_helper_status()
    host_helper_ready = background_helper_running() and status.get("state") == "ready"
    if slot is None:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} does not exist.")
    last_state = slot.last_state or {}
    input_surface = str(last_state.get("input_surface") or "unknown")
    age_ms = max(0.0, (time.time() - float(slot.last_seen or 0.0)) * 1000.0)
    background_active = input_surface == "background_native" and bool(slot.is_active) and age_ms < 1000.0
    key_codes = last_state.get("key_codes") or []
    if not background_active:
        key_codes = []
    return {
        "running": background_helper_running(),
        "ready": host_helper_ready,
        "background_active": background_active,
        "input_surface": input_surface,
        "slot_id": slot_id,
        "active_keys": [str(code) for code in key_codes],
        "packet_count": slot.packet_count,
        "last_seen": slot.last_seen,
        "last_seen_age_ms": round(age_ms, 1),
    }


@router.post("/api/background-capture")
async def set_background_capture(req: BackgroundCaptureRequest, request: Request):
    require_local_request(request)
    return await start_background_helper(req, request, _slot_manager, _static_dir)


@router.get("/api/status")
async def get_server_status(request: Request):
    """Return full host status locally and a minimal non-sensitive view remotely."""
    room_code = _slot_manager.room_code if _slot_manager else config.room_code
    if is_public_tunnel_request(request):
        # Never disclose the room bearer secret through an unauthenticated status API.
        return {
            "title": config.title,
            "version": config.version,
            "vigem_available": VIGEM_AVAILABLE,
            "remote_session": True,
        }

    local_ips = get_local_ips()
    lan_urls = [f"http://{ip}:{config.port}/play?code={room_code}" for ip in local_ips]
    vhf_available, vhf_error = _refresh_vhf_status()
    return {
        "title": config.title,
        "version": config.version,
        "room_code": room_code,
        "vigem_available": VIGEM_AVAILABLE,
        "vhf_available": vhf_available,
        "vhf_error": vhf_error,
        "local_ips": local_ips,
        "primary_lan_url": lan_urls[0] if lan_urls else None,
        "all_lan_urls": lan_urls,
        "tunnel": _tunnel_manager.get_info() if _tunnel_manager else {},
        "target": {**target_manager.get_status(), "gate_enabled": config.target_gate_enabled},
        "summary": _slot_manager.get_summary() if _slot_manager else {},
    }


class ControllerTypeRequest(BaseModel):
    backend_id: str


@router.post("/api/slot/{slot_id}/controller")
async def set_slot_controller(slot_id: int, req: ControllerTypeRequest, request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    ok = await _slot_manager.set_controller_type(slot_id, req.backend_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid slot or failed to instantiate backend.")
    return {"ok": True, "slot_id": slot_id, "backend": req.backend_id}


class SOCDModeRequest(BaseModel):
    mode: str


@router.post("/api/slot/{slot_id}/socd")
async def set_slot_socd(slot_id: int, req: SOCDModeRequest, request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    ok = await _slot_manager.set_socd_mode(slot_id, req.mode)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid SOCD mode.")
    return {"ok": True, "slot_id": slot_id, "socd_mode": req.mode}


class DeadzoneRequest(BaseModel):
    deadzone: float


@router.post("/api/slot/{slot_id}/deadzone")
async def set_slot_deadzone(slot_id: int, req: DeadzoneRequest, request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    ok = await _slot_manager.set_deadzone(slot_id, req.deadzone)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid slot or deadzone.")
    return {"ok": True, "slot_id": slot_id, "deadzone": req.deadzone}


class MuteRequest(BaseModel):
    muted: bool


@router.post("/api/slot/{slot_id}/mute")
async def set_slot_mute(slot_id: int, req: MuteRequest, request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    ok = await _slot_manager.set_muted(slot_id, req.muted)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid slot.")
    return {"ok": True, "slot_id": slot_id, "muted": req.muted}


@router.post("/api/slot/{slot_id}/reset")
async def panic_reset_slot(slot_id: int, request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    await _slot_manager.panic_reset(slot_id)
    return {"ok": True, "slot_id": slot_id}


@router.post("/api/slot/{slot_id}/kick")
async def kick_slot_player(slot_id: int, request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    slot = _slot_manager.slots.get(slot_id)
    if slot and slot.websocket:
        try:
            await slot.websocket.send_json({"type": "kicked", "reason": "Host disconnected slot."})
            await slot.websocket.close()
        except Exception:
            pass
    await _slot_manager.detach_player(slot_id)
    return {"ok": True, "slot_id": slot_id}


@router.post("/api/panic")
async def panic_all(request: Request):
    require_local_request(request)
    if not _slot_manager:
        raise HTTPException(status_code=503, detail="SlotManager not initialized.")
    await _slot_manager.panic_reset(None)
    return {"ok": True, "message": "All virtual controller inputs released."}


@router.post("/api/tunnel/start")
async def start_tunnel(request: Request):
    require_local_request(request)
    if not _tunnel_manager:
        raise HTTPException(status_code=503, detail="TunnelManager not initialized.")
    started = _tunnel_manager.start(config.port)
    return {"ok": started, "tunnel": _tunnel_manager.get_info()}


@router.post("/api/tunnel/stop")
async def stop_tunnel(request: Request):
    require_local_request(request)
    if not _tunnel_manager:
        raise HTTPException(status_code=503, detail="TunnelManager not initialized.")
    _tunnel_manager.stop()
    return {"ok": True, "tunnel": _tunnel_manager.get_info()}


@router.get("/api/tunnel/status")
async def get_tunnel_status(request: Request):
    require_local_request(request)
    return _tunnel_manager.get_info() if _tunnel_manager else {}


@router.get("/api/targets")
async def list_targets(request: Request, include_empty_titles: bool = False):
    require_local_request(request)
    return {"targets": [t.public_dict() for t in target_manager.list_windows(include_empty_titles)]}


class TargetSelectRequest(BaseModel):
    hwnd: Optional[int] = None
    pid: Optional[int] = None


@router.post("/api/target/select")
async def select_target(req: TargetSelectRequest, request: Request):
    require_local_request(request)
    target = target_manager.select(hwnd=req.hwnd, pid=req.pid)
    if target is None:
        raise HTTPException(status_code=404, detail="Running target window not found.")
    return {"ok": True, "target": target.public_dict(), "status": target_manager.get_status()}


@router.post("/api/target/select-foreground")
async def select_foreground_target(request: Request):
    require_local_request(request)
    fg = target_manager.foreground()
    if fg is None:
        raise HTTPException(status_code=404, detail="No foreground window available.")
    target = target_manager.select(hwnd=fg.hwnd)
    if target is None:
        raise HTTPException(status_code=404, detail="Foreground window could not be selected.")
    return {"ok": True, "target": target.public_dict(), "status": target_manager.get_status()}


@router.post("/api/target/clear")
async def clear_target(request: Request):
    require_local_request(request)
    target_manager.clear()
    return {"ok": True, "status": target_manager.get_status()}


@router.get("/api/target/status")
async def target_status(request: Request):
    status = target_manager.get_status()
    if is_public_tunnel_request(request):
        return public_target_status(status)
    return status


class TargetGateRequest(BaseModel):
    enabled: bool


@router.post("/api/target/gate")
async def set_target_gate(req: TargetGateRequest, request: Request):
    require_local_request(request)
    config.target_gate_enabled = bool(req.enabled)
    return {"ok": True, "enabled": config.target_gate_enabled}


@router.get("/api/profiles")
async def list_profiles():
    return {"profiles": _profile_manager.get_all() if _profile_manager else []}
