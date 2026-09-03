"""
Slot Manager and Input Routing Engine.
Handles:
- Up to 4 remote player slots (P2, P3, P4, P5)
- Real-time input routing & SOCD processing
- 250ms Input Watchdog (auto-neutralizes stuck inputs upon network dropout)
- Telemetry streaming (latency, jitter, packet rate, button visualizer)
- Dynamic controller type switching (Xbox 360 <-> DS4 <-> Keyboard)
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket

from .controller import ControllerFactory, VIGEM_AVAILABLE
from .input_pipeline import build_normalized_input_state
from .key_mapping import map_key_codes_to_gamepad  # Backward-compatible import surface.
from .socd import SOCDCleaner, SOCDMode
from .targeting import target_manager
from .slot import PlayerSlot
from config import config

logger = logging.getLogger("OmniPad.SlotManager")


class SlotManager:
    def __init__(self, max_slots: int = 3, watchdog_timeout: float = 1.0):
        """
        max_slots: 3 slots by default (representing P2, P3, P4).
        watchdog_timeout: timeout in seconds before releasing stuck inputs (default 1.0s).
        """
        self.max_slots = max_slots
        self.watchdog_timeout = watchdog_timeout
        self.room_code = "SF6-ROOM"
        self.slots: Dict[int, PlayerSlot] = {}
        self.host_websockets: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._watchdog_task: Optional[asyncio.Task] = None
        self._telemetry_task: Optional[asyncio.Task] = None

        default_backend = "xbox360" if VIGEM_AVAILABLE else "noop"
        for i in range(1, max_slots + 1):
            slot = PlayerSlot(
                slot_id=i,
                display_title=f"Player {i + 1}",
                controller_type=default_backend,
                socd_cleaner=SOCDCleaner(SOCDMode.NEUTRAL)
            )
            self.slots[i] = slot

    async def start(self) -> None:
        """Start the background watchdog and telemetry broadcast loops."""
        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        if not self._telemetry_task or self._telemetry_task.done():
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        logger.info("SlotManager loops started (Watchdog: %dms)", int(self.watchdog_timeout * 1000))

    async def stop(self) -> None:
        """Stop all loops and close all controllers."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._telemetry_task:
            self._telemetry_task.cancel()

        for slot in self.slots.values():
            if slot.controller:
                slot.controller.close()
                slot.controller = None

    async def _watchdog_loop(self) -> None:
        """Continuously checks for stuck inputs or dropped connections."""
        while True:
            try:
                await asyncio.sleep(0.03) # 33Hz watchdog check
                now = time.time()
                for slot in self.slots.values():
                    if slot.friend_name and slot.is_active:
                        if (now - slot.last_seen) > self.watchdog_timeout:
                            # Watchdog trigger: neutralize controls
                            if slot.controller:
                                slot.controller.release_all()
                            slot.is_active = False
                            slot.last_state = {
                                "buttons": {},
                                "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
                            }
                            logger.debug("[Slot %d] Watchdog neutralized inputs (timeout > %.2fs)", slot.slot_id, self.watchdog_timeout)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Watchdog loop error: %s", e)

    async def _telemetry_loop(self) -> None:
        """Streams state telemetry to connected host management dashboards at ~30Hz."""
        while True:
            try:
                await asyncio.sleep(0.033)
                if self.host_websockets:
                    payload = self.get_summary()
                    to_remove = set()
                    for ws in self.host_websockets:
                        try:
                            await ws.send_json({"type": "telemetry", "data": payload})
                        except Exception:
                            to_remove.add(ws)
                    self.host_websockets -= to_remove
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Telemetry broadcast error: %s", e)

    def register_host_ws(self, ws: WebSocket) -> None:
        self.host_websockets.add(ws)

    def unregister_host_ws(self, ws: WebSocket) -> None:
        self.host_websockets.discard(ws)

    async def attach_player(self, slot_id: int, friend_name: str, ws: WebSocket) -> bool:
        """Attach a remote player WebSocket to a slot."""
        async with self._lock:
            if slot_id not in self.slots:
                return False

            slot = self.slots[slot_id]
            # If slot already had a controller open, release inputs
            if slot.controller is None:
                try:
                    slot.controller = ControllerFactory.create(slot.controller_type, slot_id)
                except Exception as e:
                    logger.error("Failed to create controller for slot %d: %s", slot_id, e)

            slot.friend_name = friend_name[:24]
            slot.websocket = ws
            slot.connected_at = time.time()
            slot.last_seen = time.time()
            slot.last_seq = -1
            slot.packet_count = 0
            slot.is_active = True
            slot.client_packets.clear()
            slot.client_last_seen.clear()
            slot.last_state = {
                "buttons": {},
                "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                "key_codes": []
            }
            if slot.controller:
                try:
                    slot.controller.release_all()
                except Exception:
                    pass
            logger.info(">>> [Slot %d] Player '%s' connected (Backend: %s) <<<", slot_id, slot.friend_name, slot.controller_type)
            return True

    async def detach_player(self, slot_id: int, ws: Optional[WebSocket] = None) -> None:
        """Detach a player from a slot and reset inputs."""
        async with self._lock:
            if slot_id not in self.slots:
                return
            slot = self.slots[slot_id]
            if ws is not None:
                slot.client_packets.pop(ws, None)
                slot.client_last_seen.pop(ws, None)
            if ws is not None and slot.websocket is not ws:
                # Slot was handed off to a newer connection; do not detach
                return
            slot.friend_name = None
            slot.websocket = None
            slot.is_active = False
            slot.latency_ms = None
            slot.jitter_ms = None
            slot._recent_latencies.clear()
            slot.client_packets.clear()
            slot.client_last_seen.clear()
            slot.last_state = {
                "buttons": {},
                "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
            }
            if slot.controller:
                slot.controller.release_all()
            logger.info("[Slot %d] Player detached", slot_id)

    async def update_latency(self, slot_id: int, rtt_ms: float) -> None:
        """Records latency and jitter metrics from round-trip ping."""
        if slot_id not in self.slots:
            return
        slot = self.slots[slot_id]
        slot.latency_ms = rtt_ms
        slot._recent_latencies.append(rtt_ms)
        if len(slot._recent_latencies) > 20:
            slot._recent_latencies.pop(0)

        # Calculate jitter (mean absolute deviation)
        if len(slot._recent_latencies) >= 2:
            diffs = [abs(slot._recent_latencies[i] - slot._recent_latencies[i - 1]) for i in range(1, len(slot._recent_latencies))]
            slot.jitter_ms = sum(diffs) / len(diffs)

    async def process_input_packet(self, slot_id: int, packet: Dict[str, Any], client_id: Optional[Any] = None) -> None:
        """Process incoming input snapshot packet from remote player with multi-client fusion."""
        if slot_id not in self.slots:
            return
        slot = self.slots[slot_id]

        if slot.muted:
            return

        seq = int(packet.get("seq", -1))
        # Drop stale / out-of-order packets if seq is provided
        if seq != -1 and seq <= slot.last_seq and (slot.last_seq - seq) < 1000:
            return
        if seq != -1:
            slot.last_seq = seq

        now = time.time()
        slot.last_seen = now
        slot.packet_count += 1
        slot.is_active = True

        cid = client_id or "default"
        slot.client_packets[cid] = packet
        slot.client_last_seen[cid] = now

        # Prune dead client sessions
        stale_clients = [c for c, t in slot.client_last_seen.items() if now - t > 3.0]
        for c in stale_clients:
            slot.client_packets.pop(c, None)
            slot.client_last_seen.pop(c, None)

        state = build_normalized_input_state(
            slot.client_packets,
            packet,
            slot.socd_cleaner,
            slot.deadzone,
        )
        slot.last_state = state
        input_surface = state["input_surface"]
        mapping_profile = state["mapping_profile"]

        # Background Routing Gating:
        # If background_routing is disabled (False), inputs stay confined to the browser
        # site alone and are not routed to Windows virtual controllers / keyboard.
        background_routing = packet.get("background_routing", True)
        if not background_routing:
            if slot.controller:
                try:
                    slot.controller.release_all()
                except Exception:
                    pass
            return

        # Target Scoping & Safety Gate:
        #   * Keyboard injection must stay foreground-gated (SendInput safety).
        #   * Virtual controllers (Xbox 360 / DualShock 4) only route when target is running.
        keyboard_backend = slot.controller_type in {
            "keyboard_target", "keyboard", "virtual_keyboard", "virtual_keyboard_port"
        }
        if config.target_gate_enabled and target_manager.selected:
            allowed = target_manager.is_target_foreground() if keyboard_backend else target_manager.is_target_running()
            if not allowed:
                if slot.controller:
                    try:
                        slot.controller.release_all()
                    except Exception:
                        pass
                slot.last_state = {
                    "buttons": {},
                    "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                    "key_codes": [],
                    "input_surface": input_surface,
                    "mapping_profile": mapping_profile,
                }
                slot.is_active = False
                return

        # Apply to virtual hardware controller
        if slot.controller:
            try:
                slot.controller.apply(state)
            except Exception as e:
                logger.error("[Slot %d] Controller apply error: %s", slot_id, e)

    async def set_controller_type(self, slot_id: int, new_type: str) -> bool:
        """Switch controller emulation backend dynamically."""
        async with self._lock:
            if slot_id not in self.slots:
                return False
            slot = self.slots[slot_id]
            old_type = slot.controller_type
            old_controller = slot.controller

            # Build the replacement first. This avoids leaving a connected player
            # with no backend (or a misleading selected mode) when an optional
            # driver-backed backend such as VHF is unavailable.
            try:
                new_controller = ControllerFactory.create(new_type, slot_id)
            except Exception as e:
                logger.error("Failed to create %s for slot %d: %s", new_type, slot_id, e)
                return False

            if old_controller:
                old_controller.close()

            slot.controller = new_controller
            slot.controller_type = new_type
            logger.info("[Slot %d] Switched backend from %s to: %s", slot_id, old_type, new_type)
            return True

    async def set_socd_mode(self, slot_id: int, mode_str: str) -> bool:
        if slot_id not in self.slots:
            return False
        try:
            mode = SOCDMode(mode_str.lower())
            self.slots[slot_id].socd_mode = mode
            self.slots[slot_id].socd_cleaner.mode = mode
            return True
        except ValueError:
            return False

    async def set_deadzone(self, slot_id: int, deadzone: float) -> bool:
        if slot_id not in self.slots:
            return False
        self.slots[slot_id].deadzone = max(0.0, min(0.5, float(deadzone)))
        return True

    async def set_muted(self, slot_id: int, muted: bool) -> bool:
        if slot_id not in self.slots:
            return False
        slot = self.slots[slot_id]
        slot.muted = bool(muted)
        if slot.muted and slot.controller:
            slot.controller.release_all()
        return True

    async def panic_reset(self, slot_id: Optional[int] = None) -> None:
        """Panic release for a specific slot or all slots."""
        async with self._lock:
            if slot_id is not None:
                if slot_id in self.slots and self.slots[slot_id].controller:
                    self.slots[slot_id].controller.release_all()
                    logger.info("[Slot %d] Panic reset executed", slot_id)
            else:
                for s in self.slots.values():
                    if s.controller:
                        s.controller.release_all()
                logger.info("Global panic reset executed across all slots")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "room_code": self.room_code,
            "vigem_available": VIGEM_AVAILABLE,
            "max_slots": self.max_slots,
            "slots": [s.get_public_state() for s in self.slots.values()],
            "available_backends": ControllerFactory.get_available_backends(),
            "target": {**target_manager.get_status(), "gate_enabled": config.target_gate_enabled},
        }
