"""Focused contracts for same-slot browser collaboration and shared preferences."""

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from router.player_sync import sanitize_shared_config
from router.slot_manager import SlotManager


class Peer:
    pass


def packet(seq, button, axis=0.0):
    return {
        "type": "input", "seq": seq, "input_surface": "keyboard",
        "mapping_profile": "universal", "buttons": {button: True},
        "axes": {"lx": axis, "ly": 0, "rx": 0, "ry": 0, "lt": 0, "rt": 0},
        "key_codes": [],
    }


async def collaboration_contract():
    manager = SlotManager(max_slots=1)
    slot = manager.slots[1]
    slot.controller_type = "noop"
    laptop, phone = Peer(), Peer()
    assert await manager.attach_player(1, "Laptop", laptop)
    assert await manager.attach_player(1, "Phone", phone)
    assert len(slot.controller_websockets) == 2

    await manager.process_input_packet(1, packet(1, "Y", -0.6), laptop)
    await manager.process_input_packet(1, packet(1, "A", 0.0), phone)
    assert slot.last_state["buttons"] == {"Y": True, "A": True}
    assert slot.last_state["axes"]["lx"] == -0.6
    await manager.detach_player(1, phone)
    assert slot.friend_name == "Laptop" and slot.last_state["buttons"] == {"Y": True}
    await manager.detach_player(1, laptop)
    assert slot.websocket is None and slot.last_state["buttons"] == {}


def main():
    clean = sanitize_shared_config({
        "mouse_sensitivity": 0, "mouse_invert_y": True,
        "touch_layout": "phone_reach", "keyboard_type": "compact65",
        "hybrid_preset": "landscape_companion",
        "hybrid_parts": ["keyboard", "right-stick", "bad"],
        "hybrid_keyboard_view": "essential", "bad": "discard",
    })
    assert clean["mouse_sensitivity"] == 1 and "bad" not in clean
    assert clean["hybrid_parts"] == ["keyboard", "right-stick"]
    asyncio.run(collaboration_contract())

    html = (ROOT / "static/play.html").read_text(encoding="utf-8")
    shared = (ROOT / "static/js/shared_controller_state.js").read_text(encoding="utf-8")
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    assert 'id="sync-keyboard-type" checked' in html
    assert 'id="sync-hybrid-layout" checked' in html
    assert "source_id: sourceId" in shared and "meta.source_id === sourceId" in shared
    assert "if (!syncKeyboardEnabled()) delete clean.keyboard_type" in shared
    assert "delete clean.hybrid_parts" in shared
    assert 'mtype == "shared_config"' in server and "sanitize_shared_config" in server
    print("Shared controller state passed: collaborative peers, bounded config, opt-out sync, and safe detach.")


if __name__ == "__main__":
    main()
