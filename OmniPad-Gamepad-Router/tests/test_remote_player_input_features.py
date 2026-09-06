"""Regression checks for remote player input UX additions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> None:
    play = read("static/play.html")
    player = read("static/js/play.js")
    routing = read("static/js/target_routing.js")
    keyboard = read("static/js/keyboard_type_adapter.js")
    mouse = read("static/js/mouse_camera.js")
    latency = read("static/js/low_latency_input.js")
    virtual_keyboard = read("static/js/virtual_keyboard.js")
    profiles = read("static/js/gamepad_profiles.js")
    css = read("static/css/input_extensions.css")

    assert "isCloudflareRemoteSession" in routing
    assert 'controls.style.display = "none"' in routing
    assert 'touchBtn.style.display = "none"' in routing
    assert "startRoutingStatusMonitor" in routing
    assert "isCloudflareRemoteSession() ? 30000 : 10000" in routing
    assert "if (document.hidden) return" in routing
    assert "startBackgroundInputMirrorTimer" in routing
    assert "if (backgroundInputMirrorTimer" in routing
    assert "setInterval(syncBackgroundInputMirror, 50)" in routing
    assert "setInterval(() => { if (typeof syncBackgroundInputMirror" not in player

    assert 'id="mouse-camera-pad"' in play
    assert 'id="keyboard-type-select"' in play
    assert "mouse_camera.js" in play
    assert "keyboard_type_adapter.js" in play
    assert "low_latency_input.js" in play
    assert "input_extensions.css" in play
    assert "virtual_keyboard.css?v=" in play
    assert "touch_controller_layouts.css?v=" in play
    assert 'placeholder="Code from the current join link"' in play
    assert 'value="SF6-ROOM"' not in play
    assert 'params.get("code")' in player

    for asset in (
        "gamepad_viz.js", "keyboard_layouts.js", "gamepad_profiles.js",
        "virtual_keyboard.js", "target_routing.js", "input_capture.js",
        "keyboard_type_adapter.js", "play.js", "low_latency_input.js",
        "mouse_camera.js", "remote_input_monitor.js", "touch_controller.js",
    ):
        assert f'{asset}?v=' in play

    for key_type in ("standard", "compact65", "arrowless", "arrow_numpad", "esdf", "vim_camera"):
        assert key_type in keyboard

    # Physical keyboard types and clickable fixed layouts are separate. Camera
    # keys must never appear in their type's button map and cause cross-talk.
    assert "const FIXED_LAYOUTS" in keyboard
    assert "sourceKeySets" in keyboard and 'startsWith("pointer_")' in keyboard
    assert "const pointerResolved = resolve(pointer, FIXED_LAYOUTS" in keyboard
    assert "const spec = FIXED_LAYOUTS[layoutName] || type" in keyboard
    assert 'camera: { up: "ArrowUp"' in keyboard
    assert 'camera: { up: "KeyI"' in keyboard
    assert 'camera: { up: "KeyK"' in keyboard
    assert "smoothLx = approach" in keyboard and "smoothRx = approach" in keyboard
    assert "resetKeyboardAnalogState" in keyboard
    assert "window.OmniPadKeyboardSemantics" in keyboard

    assert "Xbox Controls (Any Output)" in play
    assert "PlayStation Controls (Any Output)" in play
    assert "not the output backend" in play
    assert "Physical Keyboard Type:" in play

    assert "65% Compact" in play
    assert "window.mouseCameraState" in mouse
    assert "requestPointerLock" in mouse
    assert "pointerlockchange" in mouse
    assert "exitPointerLock" in mouse
    assert "transmitCurrentInputState" in mouse
    assert "setPointerCapture" in mouse
    assert "pointerleave" in mouse
    assert "queueMicrotask" in latency
    assert "keydown" in latency and "keyup" in latency
    assert "mouse-camera-pad.active" in css
    assert "mouse-camera-pad.locked" in css
    assert "mouse-camera-card.fullscreen-mode" in css

    # WAN / Cloudflare transport guard: input snapshots are latest-state-wins,
    # while digital key transitions keep their immediate microtask flush.
    assert "WebSocket.prototype.send" in latency
    assert "bufferedAmount" in latency
    assert "MAX_BUFFERED_BYTES" in latency
    assert "MIN_ANALOG_SEND_MS" in latency
    assert "SAME_STATE_KEEPALIVE_MS" in latency
    assert "droppedBackpressure" in latency
    assert "droppedCoalesced" in latency
    assert "droppedDuplicate" in latency
    assert "OmniPadInputTransportStats" in latency
    assert 'message.type !== "input"' in latency
    assert "hasAxisRelease" in latency
    assert "axisReleased" in latency
    assert "axes: next.axes" in latency

    assert 'id="mouse-camera-fullscreen-btn"' in play
    assert 'id="mouse-camera-popout-btn"' in play
    assert "toggleFullscreen" in mouse
    assert "openPopoutWindow" in mouse
    assert "centerArmed" in mouse

    assert 'id="mouse-sens-slider"' in play
    assert "mouseSensitivity" in mouse
    assert "setMouseSensitivity" in mouse
    assert 'min="1" max="200" value="20"' in play
    assert "Math.max(1, Math.min(200" in mouse
    assert "scheduleMouseTransmit" in mouse
    assert "requestAnimationFrame" in mouse
    assert "const boxScale = Math.min(4, mouseSensitivity / 50)" in mouse
    assert "resetMouseCameraState" in mouse
    assert "mouseSensitivityScaleV2" in latency
    assert "if (stored === null)" in latency
    assert 'stored === "40"' not in latency
    assert 'localStorage.setItem("omnipad.mouseSensitivity", "20")' in latency
    assert "smoothLx" in keyboard and "smoothLy" in keyboard

    assert "getActiveControllerBadges" in keyboard
    assert "getActiveControllerBadges" in virtual_keyboard
    assert "resetKeyboardAnalogState" in virtual_keyboard
    assert "resetMouseCameraState" in virtual_keyboard
    assert "input_surface" in virtual_keyboard and "mapping_profile" in virtual_keyboard
    assert "window.currentGamepadProfile = currentGamepadProfile" in profiles
    assert 'localStorage.setItem("omnipad.gamepadProfile", currentGamepadProfile)' in profiles

    # Dropdowns relinquish focus so the next gameplay key is not swallowed.
    assert "target.blur()" in latency
    for selector in ("#vk-layout-select", "#keyboard-type-select", "#profile-select", "#join-mode"):
        assert selector in latency

    # Narrow/mobile keyboard controls retain usable target sizes and wrapping.
    assert "@media (max-width: 768px)" in css
    assert "min-height: 40px" in css
    assert ".mouse-camera-actions" in css
    assert "touch-action: pan-x pan-y" in css
    assert "overscroll-behavior-x: contain" in css

    print(
        "Remote player input feature checks passed "
        "(Cloudflare routing UI, bounded WebSocket backlog, latest-state analog transport, "
        "lower mouse default, keyboard variants, pointer lock, fullscreen/pop-out, and badges)."
    )


if __name__ == "__main__":
    main()
