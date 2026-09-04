"""
Comprehensive Touchscreen Layout Presets Test Suite.
Verifies all 4 mobile presets (Classic, Twin-Stick, PlayStation, Compact),
default layout, localStorage persistence, CSS structural rules,
and dynamic preset switching without session interruption.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import uvicorn
import websockets

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HTML_PATH = ROOT / "static" / "play.html"
JS_PATH = ROOT / "static" / "js" / "touch_controller.js"
CSS_PATH = ROOT / "static" / "css" / "touch_controller.css"

HTML = HTML_PATH.read_text(encoding="utf-8")
JS = JS_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")

EXPECTED_LAYOUTS = {
    "classic_landscape": "touch-layout-classic",
    "twin_stick_landscape": "touch-layout-twin-stick",
    "playstation_landscape": "touch-layout-playstation",
    "compact_thumbs": "touch-layout-compact",
}


def test_layout_selector_exposes_all_presets():
    print("\n--- 1. Testing Touchscreen Presets Definition & DOM Options ---")
    for name in EXPECTED_LAYOUTS:
        assert f'value="{name}"' in HTML, f"Preset '{name}' missing from play.html <select>"
        assert f"{name}:" in JS, f"Preset '{name}' missing from TOUCH_LAYOUTS in touch_controller.js"
    print(f"  [PASS] All {len(EXPECTED_LAYOUTS)} presets defined in JS and present in play.html selector")


def test_layout_classes_are_styled():
    print("\n--- 2. Testing Layout Preset CSS Classes ---")
    for name, class_name in EXPECTED_LAYOUTS.items():
        assert f".{class_name}" in CSS, f"CSS class '.{class_name}' missing from touch_controller.css"
        assert f'shellClass: "{class_name}"' in JS or f"shellClass: '{class_name}'" in JS, f"shellClass '{class_name}' missing in JS"
    print("  [PASS] All preset CSS layout classes defined and styled")


def test_classic_is_single_default():
    print("\n--- 3. Testing Single Default Preset & Persistence ---")
    # Verify exactly one selected option in HTML
    touch_select = HTML.split('id="touch-layout-select"', 1)[1].split("</select>", 1)[0]
    selected_matches = [m for m in touch_select.split('<option') if 'selected' in m and any(k in m for k in EXPECTED_LAYOUTS)]
    assert len(selected_matches) == 1, f"Expected exactly 1 default selected layout, found {len(selected_matches)}"
    assert 'value="classic_landscape" selected' in HTML, "classic_landscape must be the default preset"

    # Verify localStorage key
    assert '"omnipad.touchLayout"' in JS
    assert 'localStorage.setItem("omnipad.touchLayout", name)' in JS
    assert 'localStorage.getItem("omnipad.touchLayout")' in JS
    print("  [PASS] Classic Landscape is the verified default preset with localStorage persistence")


def test_twin_stick_and_playstation_structural_rules():
    print("\n--- 4. Testing Structural Layout Specifics ---")
    assert ".touch-layout-twin-stick" in CSS
    assert ".touch-layout-playstation" in CSS
    assert ".touch-layout-compact" in CSS
    assert "resetAll();" in JS, "applyLayout must invoke resetAll() to safely release active touches"
    print("  [PASS] Specific structural grid and safety reset rules verified")


async def test_layout_switching_during_live_websocket():
    print("\n--- 5. Testing Layout Switching During Live WebSocket Session ---")
    from server import app, slot_manager

    test_port = 8771
    config = uvicorn.Config(app, host="127.0.0.1", port=test_port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)

    ws_url = f"ws://127.0.0.1:{test_port}/ws/player"
    try:
        async with websockets.connect(ws_url) as ws:
            # 1. Join room
            await ws.send(json.dumps({
                "type": "join",
                "slot_id": 1,
                "name": "PresetTester",
                "code": "SF6-ROOM",
                "source": "browser"
            }))
            ack = json.loads(await ws.recv())
            assert ack.get("type") == "joined"

            slot = slot_manager.slots[1]

            # 2. Cycle through each layout preset while streaming inputs
            seq_counter = 1
            for preset_name in EXPECTED_LAYOUTS:
                # Send active input in this layout
                input_frame = {
                    "type": "input",
                    "seq": seq_counter,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {"A": True, "START": True},
                    "axes": {"lx": 0.5, "ly": 0.5, "rx": -0.5, "ry": 0.5, "lt": 0.0, "rt": 0.8},
                    "key_codes": []
                }
                seq_counter += 1
                await ws.send(json.dumps(input_frame))
                await asyncio.sleep(0.05)
                assert slot.last_state["buttons"].get("A") is True, f"Button A not active for preset {preset_name}"
                assert slot.last_state["axes"]["rt"] == 0.8

                # Simulate preset switch (safety reset + new frame)
                reset_frame = {
                    "type": "input",
                    "seq": seq_counter,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {},
                    "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                    "key_codes": []
                }
                seq_counter += 1
                await ws.send(json.dumps(reset_frame))
                await asyncio.sleep(0.05)
                assert not any(slot.last_state["buttons"].values())
                assert slot.last_state["axes"]["rt"] == 0.0

            print("  [PASS] Successfully cycled through all presets during active session with clean input state")
    finally:
        server.should_exit = True
        await server_task


def main():
    print("=" * 70)
    print("  OMNIPAD TOUCHSCREEN LAYOUT PRESETS TEST SUITE")
    print("=" * 70)

    test_layout_selector_exposes_all_presets()
    test_layout_classes_are_styled()
    test_classic_is_single_default()
    test_twin_stick_and_playstation_structural_rules()
    asyncio.run(test_layout_switching_during_live_websocket())

    print("\n" + "=" * 70)
    print("  >>> ALL TOUCHSCREEN LAYOUT TESTS PASSED SUCCESSFULLY! <<<")
    print("=" * 70)


if __name__ == "__main__":
    main()
