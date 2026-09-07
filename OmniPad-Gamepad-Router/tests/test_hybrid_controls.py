"""Low-noise contracts for the combined keyboard/touch player surface."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.input_pipeline import build_normalized_input_state
from router.socd import SOCDCleaner, SOCDMode


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_hybrid_dom_and_module_contract() -> None:
    html = text("static/play.html")
    script = text("static/js/hybrid_controls.js")
    bridge = text("static/js/touch_keyboard_bridge.js")
    modes = text("static/js/device_modes.js")
    css = text("static/css/hybrid_controls.css")

    assert 'data-mode="hybrid"' in html and 'id="section-hybrid"' in html
    assert "hybrid_controls.js?v=" in html and "hybrid_controls.css?v=" in html
    assert "touch_keyboard_bridge.js?v=" in html
    for preset in ("keyboard_touch_camera", "keyboard_mouse_camera", "keyboard_actions", "phone_split", "landscape_companion", "full_hybrid"):
        assert f'value="{preset}"' in html and f"{preset}:" in script
    for part in ("keyboard", "mouse", "left-stick", "right-stick", "dpad", "actions", "shoulders", "center"):
        assert f'data-hybrid-toggle="{part}"' in html
        assert f'data-hybrid-part="{part}"' in html
    assert "releaseEveryInputSurface" in script
    assert "hybrid-part-hidden" in script and ".hybrid-part-hidden" in css
    assert 'showSection("section-keyboard", mode === "keyboard" || hybrid)' in modes
    assert 'showSection("section-touch", mode === "touch" || hybrid)' in modes
    assert "captureTouchKeyboardFallbackCodes" in bridge
    assert 'A: "KeyJ"' in bridge and '"ArrowLeft", "ArrowRight"' in bridge
    assert 'touchLayout: "camera_actions"' in script
    assert 'id="sync-hybrid-layout"' in html and 'data-hybrid-keyboard-view="essential"' in html
    assert "shared_controller_state.js?v=" in html


def test_hybrid_packet_is_not_double_mapped() -> None:
    packet = {
        "input_surface": "hybrid",
        "mapping_profile": "it_takes_two",
        "buttons": {"X": True},
        "axes": {"lx": 0.55, "ly": 0.0, "rx": -0.7, "ry": 0.2},
        "key_codes": ["KeyW", "KeyE"],
        "keyboard_fallback_codes": ["ArrowLeft", "KeyJ"],
    }
    state = build_normalized_input_state(
        {"hybrid": packet}, packet, SOCDCleaner(SOCDMode.NEUTRAL), 0.15
    )
    assert state["input_surface"] == "hybrid"
    assert state["key_codes"] == ["KeyW", "KeyE"]
    assert state["keyboard_fallback_codes"] == ["ArrowLeft", "KeyJ"]
    assert state["buttons"] == {"X": True}
    assert state["axes"]["lx"] == 0.55
    assert state["axes"]["rx"] == -0.7


def test_keyboard_shapes_and_single_platform_labels() -> None:
    html = text("static/play.html")
    adapter = text("static/js/keyboard_type_adapter.js")
    renderer = text("static/js/virtual_keyboard.js")
    monitor = text("static/js/remote_input_monitor.js")
    layouts = text("static/js/keyboard_layouts.js")

    label_select = html.split('id="vk-layout-select"', 1)[1].split("</select>", 1)[0]
    type_select = html.split('id="keyboard-type-select"', 1)[1].split("</select>", 1)[0]
    assert 'value="standard_full"' not in label_select
    assert 'value="compact_60"' not in label_select
    assert 'value="arrow_numpad"' not in label_select
    assert 'value="arrow_numpad"' in type_select
    assert 'shape: "compact_arrowless"' in adapter
    assert "keyboardType?.shape" in renderer
    assert "getActiveControllerBadges" in renderer
    assert 'A: "A"' in adapter and 'A: "✕"' in adapter
    assert 'A: "A / ✕"' not in adapter and 'A: "✕ / A"' not in adapter
    assert 'badge: "A / ✕"' not in layouts and 'badge: "✕ / A"' not in layouts
    assert 'createElement("span")' not in monitor.split("function updateKeyboardControllerLabels", 1)[1].split("window.updateKeyboardControllerLabels", 1)[0]


def test_camera_and_phone_contracts() -> None:
    html = text("static/play.html")
    mouse = text("static/js/mouse_camera.js")
    touch = text("static/js/touch_controller.js")
    layouts = text("static/css/touch_controller_layouts.css")
    keyboard_css = text("static/css/virtual_keyboard.css")

    assert 'id="mouse-invert-y"' in html and 'id="mouse-invert-x"' in html
    assert "omnipad.mouseInvertY" in mouse and "omnipad.mouseInvertX" in mouse
    assert "directedX" in mouse and "directedY" in mouse
    assert "Math.min(rect.width, rect.height) / 2" in mouse
    assert '["keyboard", "hybrid"]' in mouse
    for preset, class_name in (("phone_reach", "touch-layout-phone-reach"), ("camera_actions", "touch-layout-camera-actions")):
        assert f"{preset}:" in touch
        assert f".{class_name}" in layouts
    assert "MIN_TAP_HOLD_MS = 34" in touch
    assert "min-width: 36px" in keyboard_css and "height: 40px" in keyboard_css


def test_remote_focus_is_narrow_and_best_effort() -> None:
    html = text("static/play.html")
    client = text("static/js/target_routing.js")
    server = text("server.py")
    targeting = text("router/targeting.py")

    assert 'id="focus-target-btn"' in html
    assert '{ type: "focus_target" }' in client
    assert 'mtype == "focus_target"' in server
    assert "slot_manager.is_controller_peer" in server
    assert "host_approval_required" in server
    assert "last_focus_request_at < 0.75" in server
    assert "def focus_selected" in targeting
    assert "SetForegroundWindow" in targeting and "SW_RESTORE" in targeting
    assert "AttachThreadInput" not in targeting
    assert "synthetic Alt input" in targeting


def test_same_slot_shared_config_is_bounded() -> None:
    from router.player_sync import sanitize_shared_config

    config = sanitize_shared_config({
        "mouse_sensitivity": 500,
        "mouse_invert_y": True,
        "touch_layout": "phone_reach",
        "keyboard_type": "compact65",
        "hybrid_preset": "landscape_companion",
        "hybrid_parts": ["keyboard", "right-stick", "unknown"],
        "hybrid_keyboard_view": "essential",
        "untrusted": "discard-me",
    })
    assert config["mouse_sensitivity"] == 200
    assert config["hybrid_parts"] == ["keyboard", "right-stick"]
    assert "untrusted" not in config


def test_keyboard_backends_merge_touch_fallback_without_controller_remap() -> None:
    play = text("static/js/play.js")
    pipeline = text("router/input_pipeline.py")
    transport = text("static/js/low_latency_input.js")
    for backend_path in (
        "router/backends/keyboard.py",
        "router/backends/umdf_keyboard.py",
        "router/backends/vhf.py",
    ):
        backend = text(backend_path)
        assert 'state.get("keyboard_fallback_codes")' in backend
    assert "keyboard_fallback_codes: captureKeyboardFallbackCodes()" in play
    assert '"keyboard_fallback_codes": keyboard_fallback_codes' in pipeline
    assert "map_key_codes_to_gamepad(keyboard_fallback_codes" not in pipeline
    assert "fallbackCodes = sortedKeys(message.keyboard_fallback_codes)" in transport
    assert "[keyCodes, fallbackCodes, buttons]" in transport


def main() -> None:
    test_hybrid_dom_and_module_contract()
    test_hybrid_packet_is_not_double_mapped()
    test_keyboard_shapes_and_single_platform_labels()
    test_camera_and_phone_contracts()
    test_remote_focus_is_narrow_and_best_effort()
    test_keyboard_backends_merge_touch_fallback_without_controller_remap()
    test_same_slot_shared_config_is_bounded()
    print("Hybrid controls passed: shared input, safe focus, labels, camera preferences, and mobile presets.")


if __name__ == "__main__":
    main()
