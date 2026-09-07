"""
OmniPad Gamepad Router - FastAPI Server & WebSocket Input Engine.
Main server composition root connecting remote friends via WebSockets to virtual Windows game controllers.
"""

import argparse
import asyncio
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from config import config
from router import SlotManager, TunnelManager, ProfileManager, get_local_ips, VIGEM_AVAILABLE
from router.api_routes import setup_routes
from router.access_logging import install_access_log_filter
from router.event_loop import install_disconnect_filter
from router.background_helper import (
    background_helper_running,
    shutdown_background_helper as _shutdown_background_helper,
)
from router.player_sync import sanitize_shared_config
from router.security import is_local_client_host, is_public_tunnel_websocket
from router.targeting import target_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OmniPad.Server")
install_access_log_filter()

slot_manager = SlotManager(max_slots=config.max_slots, watchdog_timeout=config.watchdog_timeout)
tunnel_manager = TunnelManager(local_port=config.port)
profile_manager = ProfileManager()
_player_observers: Dict[int, set[WebSocket]] = {}
_uvicorn_server: Optional[uvicorn.Server] = None


async def _request_server_shutdown() -> bool:
    if _uvicorn_server is None:
        return False
    _uvicorn_server.should_exit = True
    return True


async def _register_player_observer(slot_id: int, websocket: WebSocket) -> None:
    _player_observers.setdefault(slot_id, set()).add(websocket)


async def _unregister_player_observer(slot_id: int, websocket: WebSocket) -> None:
    observers = _player_observers.get(slot_id)
    if not observers:
        return
    observers.discard(websocket)
    if not observers:
        _player_observers.pop(slot_id, None)


async def _broadcast_player_input_state(slot_id: int, state: Dict[str, Any]) -> None:
    observers = list(_player_observers.get(slot_id, set()))
    if not observers:
        return
    payload = {"type": "input_state", "slot_id": slot_id, "state": state or {}, "server_time": time.time()}
    stale = []
    for observer in observers:
        try:
            await observer.send_json(payload)
        except Exception:
            stale.append(observer)
    for observer in stale:
        await _unregister_player_observer(slot_id, observer)


async def _broadcast_slot_message(slot_id: int, payload: Dict[str, Any]) -> None:
    stale = []
    for observer in list(_player_observers.get(slot_id, set())):
        try:
            await observer.send_json(payload)
        except Exception:
            stale.append(observer)
    for observer in stale:
        await _unregister_player_observer(slot_id, observer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing OmniPad Gamepad Router v%s...", config.version)
    event_loop = asyncio.get_running_loop()
    previous_exception_handler = install_disconnect_filter(event_loop, logger)
    await slot_manager.start()
    if config.enable_tunnel:
        logger.info("Auto-starting Cloudflare Quick Tunnel...")
        tunnel_manager.start(config.port)
    try:
        yield
    finally:
        event_loop.set_exception_handler(previous_exception_handler)
        logger.info("Shutting down OmniPad Gamepad Router...")
        _shutdown_background_helper()
        tunnel_manager.stop()
        await slot_manager.stop()


app = FastAPI(title=config.title, version=config.version, lifespan=lifespan)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(
    setup_routes(
        slot_manager,
        tunnel_manager,
        profile_manager,
        STATIC_DIR,
        shutdown_callback=_request_server_shutdown,
    )
)


@app.websocket("/ws/host")
async def host_websocket_endpoint(websocket: WebSocket):
    """Local-only telemetry/control channel for the host dashboard."""
    if not is_local_client_host(websocket.client.host if websocket.client else None):
        await websocket.close(code=1008, reason="Host telemetry is local-only.")
        return
    await websocket.accept()
    slot_manager.register_host_ws(websocket)
    try:
        await websocket.send_json({"type": "initial_status", "data": slot_manager.get_summary()})
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "t": msg.get("t")})
            elif msg.get("type") == "panic":
                await slot_manager.panic_reset(None)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Host WS closed: %s", exc)
    finally:
        slot_manager.unregister_host_ws(websocket)


@app.websocket("/ws/player")
async def player_websocket_endpoint(websocket: WebSocket):
    """Public player input channel; room-code validation gates control ownership."""
    await websocket.accept()
    attached_slot: Optional[int] = None
    observer_slot: Optional[int] = None
    friend_name = "Player"
    client_is_local = is_local_client_host(websocket.client.host if websocket.client else None)
    last_focus_request_at = 0.0
    try:
        while True:
            try:
                raw_text = await websocket.receive_text()
                msg = json.loads(raw_text)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                logger.debug("Malformed player websocket frame: %s", exc)
                continue
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            if mtype == "join":
                slot_id = int(msg.get("slot_id", 1))
                friend_name = str(msg.get("name") or msg.get("friend_name") or "Player 2")[:24]
                code = str(msg.get("code") or msg.get("room_code") or "").strip().upper()
                requested_source = str(msg.get("source") or "browser")
                if requested_source == "background_keyboard_helper":
                    source = "background_keyboard_helper" if client_is_local else "browser"
                elif requested_source == "observer":
                    source = "observer"
                else:
                    source = "browser"
                if code != slot_manager.room_code:
                    await websocket.send_json({"type": "error", "error": "Invalid room code.", "message": "Invalid room code."})
                    continue
                if slot_id not in slot_manager.slots:
                    await websocket.send_json({"type": "error", "error": "Invalid slot.", "message": "Invalid slot."})
                    continue
                slot = slot_manager.slots[slot_id]
                if source == "observer":
                    await _register_player_observer(slot_id, websocket)
                    observer_slot = slot_id
                    await websocket.send_json({
                        "type": "joined", "status": "ok", "slot_id": slot_id,
                        "title": slot.display_title, "backend": slot.controller_type,
                        "socd_mode": slot.socd_mode.value, "deadzone": slot.deadzone,
                        "vigem_available": VIGEM_AVAILABLE, "observer": True,
                        "current_state": slot.last_state,
                        "shared_config": slot.shared_config,
                    })
                    continue
                helper_active = background_helper_running()
                if helper_active and source != "background_keyboard_helper" and slot.websocket is not None:
                    await _register_player_observer(slot_id, websocket)
                    observer_slot = slot_id
                    await websocket.send_json({
                        "type": "joined", "status": "ok", "slot_id": slot_id,
                        "title": slot.display_title, "backend": slot.controller_type,
                        "socd_mode": slot.socd_mode.value, "deadzone": slot.deadzone,
                        "vigem_available": VIGEM_AVAILABLE, "background_helper_active": True,
                        "observer": True, "current_state": slot.last_state,
                        "shared_config": slot.shared_config,
                    })
                    continue
                exclusive = source == "background_keyboard_helper"
                if exclusive:
                    for old_ws in list(slot.controller_websockets):
                        await _register_player_observer(slot_id, old_ws)
                        try:
                            await old_ws.send_json({"type": "demoted_to_observer", "observer": True, "current_state": slot.last_state})
                        except Exception:
                            pass
                attached = await slot_manager.attach_player(slot_id, friend_name, websocket, exclusive=exclusive)
                if attached:
                    attached_slot = slot_id
                    slot = slot_manager.slots[slot_id]
                    await websocket.send_json({
                        "type": "joined", "status": "ok", "slot_id": slot_id,
                        "title": slot.display_title, "backend": slot.controller_type,
                        "socd_mode": slot.socd_mode.value, "deadzone": slot.deadzone,
                        "vigem_available": VIGEM_AVAILABLE,
                        "shared_config": slot.shared_config,
                    })
                else:
                    await websocket.send_json({"type": "error", "error": "Failed to attach to slot.", "message": "Failed to attach to slot."})
            elif mtype == "input":
                # Explicit observers are read-only; authenticated browser peers collaborate.
                if attached_slot is None:
                    continue
                slot = slot_manager.slots.get(attached_slot)
                if slot is not None and slot_manager.is_controller_peer(attached_slot, websocket):
                    await slot_manager.process_input_packet(attached_slot, msg, client_id=websocket)
                    await _broadcast_player_input_state(attached_slot, slot.last_state)
            elif mtype == "shared_config":
                slot = slot_manager.slots.get(attached_slot) if attached_slot is not None else None
                if slot is None or not slot_manager.is_controller_peer(attached_slot, websocket):
                    continue
                patch = sanitize_shared_config(msg.get("patch"))
                if patch:
                    slot.shared_config.update(patch)
                    await _broadcast_slot_message(attached_slot, {
                        "type": "shared_config", "slot_id": attached_slot,
                        "config": slot.shared_config,
                        "source_id": str(msg.get("source_id") or "")[:80],
                    })
            elif mtype == "focus_target":
                slot = slot_manager.slots.get(attached_slot) if attached_slot is not None else None
                if slot is None or not slot_manager.is_controller_peer(attached_slot, websocket):
                    await websocket.send_json({"type": "focus_result", "ok": False, "reason": "not_controller"})
                    continue
                if is_public_tunnel_websocket(websocket) and not config.remote_focus_enabled:
                    await slot_manager.broadcast_host_event({
                        "type": "focus_request", "slot_id": attached_slot,
                        "name": friend_name,
                    })
                    await websocket.send_json({"type": "focus_result", "ok": False, "reason": "host_approval_required"})
                    continue
                now = time.monotonic()
                if now - last_focus_request_at < 0.75:
                    await websocket.send_json({"type": "focus_result", "ok": False, "reason": "rate_limited"})
                    continue
                last_focus_request_at = now
                focused, reason = target_manager.focus_selected()
                await websocket.send_json({"type": "focus_result", "ok": focused, "reason": reason})
            elif mtype == "ping":
                client_t = msg.get("t", 0)
                now_ms = time.time() * 1000
                reported_rtt = msg.get("rtt_ms")
                if attached_slot is not None and isinstance(reported_rtt, (int, float)):
                    await slot_manager.update_latency(attached_slot, max(1.0, min(60000.0, float(reported_rtt))))
                await websocket.send_json({"type": "pong", "t": client_t, "server_t": now_ms})
            elif mtype == "leave":
                if attached_slot is not None:
                    await slot_manager.detach_player(attached_slot, websocket)
                    attached_slot = None
                await websocket.send_json({"type": "left"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("Player WS error: %s", exc)
    finally:
        if observer_slot is not None:
            await _unregister_player_observer(observer_slot, websocket)
        if attached_slot is not None:
            await slot_manager.detach_player(attached_slot, websocket)
            logger.info("Cleaned up disconnected player '%s' from slot %d", friend_name, attached_slot)


def main():
    global _uvicorn_server
    parser = argparse.ArgumentParser(description="OmniPad Gamepad Router")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tunnel", action="store_true")
    parser.add_argument("--code", default=None, help="Optional room code; a random 64-bit code is generated when omitted")
    args = parser.parse_args()
    config.host, config.port = args.host, args.port
    config.enable_tunnel = args.tunnel
    room_code = (args.code or secrets.token_hex(8)).upper()
    slot_manager.room_code = room_code
    local_ips = get_local_ips()
    primary_ip = local_ips[0] if local_ips else "127.0.0.1"
    print("\n" + "=" * 70)
    print("  OMNIPAD GAMEPAD ROUTER — ONLINE")
    print("=" * 70)
    print(f"  [>] Host Dashboard:     http://localhost:{config.port}/")
    print(f"  [>] Local LAN Play:     http://{primary_ip}:{config.port}/play?code={slot_manager.room_code}")
    print(f"  [>] Room Pairing Code:  {slot_manager.room_code}")
    print(f"  [>] ViGEmBus Driver:    {'ACTIVE (Native Virtual Controllers)' if VIGEM_AVAILABLE else 'UNAVAILABLE (Simulation Mode)'}")
    if args.tunnel:
        print("  [>] Cloudflare Tunnel:  Starting trycloudflare.com link...")
    print("=" * 70 + "\n")
    server_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
        ws_max_size=65536,
    )
    _uvicorn_server = uvicorn.Server(server_config)
    try:
        _uvicorn_server.run()
    finally:
        _uvicorn_server = None


if __name__ == "__main__":
    main()
