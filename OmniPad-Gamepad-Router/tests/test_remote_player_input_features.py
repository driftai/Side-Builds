"""Regression checks for remote player input UX additions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> None:
    play = read("static/play.html")
    index = read("static/index.html")
    routing = read("static/js/target_routing.js")
    keyboard = read("static/js/keyboard_type_adapter.js")
    profiles = read("static/js/gamepad_profiles.js")
    mouse = read("static/js/mouse_camera.js")
    latency = read("static/js/low_latency_input.js")
    room_code = read("static/js/room_code.js")
    tunnel = read("static/js/dashboard_tunnel.js")
    virtual_keyboard = read("static/js/virtual_keyboard.js")
    pipeline = read("router/input_pipeline.py")
    css = read("static/css/input_extensions.css")

    assert "isCloudflareRemoteSession" in routing
    assert 'controls.style.display = "none"' in routing
    assert 'touchBtn.style.display = "none"' in routing

    assert 'id="mouse-camera-pad"' in play
    assert 'id="keyboard-type-select"' in play
    assert "mouse_camera.js?v=1.3.3" in play
    assert "keyboard_type_adapter.js?v=1.3.3" in play
    assert "low_latency_input.js?v=1.3.3" in play
    assert "input_extensions.css?v=1.3.3" in play

    # Join URLs are the source of truth for remote room pairing. A stale HTML
    # placeholder must never override ?code= from LAN/Cloudflare/QR links.
    assert 'id="join-room-code"' in play
    assert 'value="SF6-ROOM"' not in play
    assert 'maxlength="256"' in play
    assert "room_code.js?v=1.3.4" in play
    assert "play.js?v=1.3.4" in play
    assert "roomCodeFromLocation" in room_code
    assert "resolveForJoin" in room_code
    assert 'new URLSearchParams(window.location.search).get("code")' in room_code
    assert "A code embedded in the link always wins" in room_code
    assert 'event.target?.closest?.("#join-btn")' in room_code
    assert 'hostname.endsWith(".trycloudflare.com")' in room_code
    assert 'fetch("/api/status", { cache: "no-store" })' in room_code
    assert 'id="room-code-display">--<' in index
    assert "dashboard_tunnel.js?v=1.3.4" in index
    assert "getActiveRoomCode" in tunnel
    assert 'code !== "SF6-ROOM"' in tunnel
    assert "encodeURIComponent(roomCode)" in tunnel
    assert 'waiting for the active room code' in tunnel

    for key_type in ("standard", "compact65", "arrowless", "esdf", "vim_camera"):
        assert key_type in keyboard

    assert "Xbox-Labeled Key Map (Any Output)" in play
    assert "PlayStation-Labeled Key Map (Any Output)" in play
    assert "does not choose the host output" in play
    assert "Xbox 360, DualShock 4, or the virtual keyboard port" in play
    assert "Physical Keyboard Type:" in play

    # Physical keyboard semantics and clickable preset semantics are separate.
    assert "FIXED_LAYOUTS" in keyboard
    assert "wasd_fighter" in keyboard and "arrow_numpad" in keyboard
    assert "sourceKeySets" in keyboard
    assert 'startsWith("pointer_")' in keyboard
    assert "pointerResolved" in keyboard and "physicalResolved" in keyboard
    assert "window.keyboardLayoutSemantics" in keyboard

    assert "resetKeyboardAnalogState" in keyboard
    assert "window.resetKeyboardAnalogState" in keyboard
    assert "window.releaseAllKeys" in keyboard
    assert "resetKeyboardAnalogState" in virtual_keyboard
    assert 'input_surface: window.currentMode || "keyboard"' in virtual_keyboard

    # Keyboard mode is resolved once in the browser. The host keeps raw key
    # identity for keyboard backends but must not turn RS keys into movement or
    # face buttons a second time.
    assert 'input_surface not in {"background_native", "keyboard"}' in pipeline
    assert "trust the resolved controller" in pipeline

    # Profile selection must update the global value consumed by play.js.
    assert "window.currentGamepadProfile = currentGamepadProfile" in profiles
    assert "window.gamepadKeymap = gamepadKeymap" in profiles
    assert 'localStorage.setItem("omnipad.gamepadProfile"' in profiles

    assert "window.mouseCameraState" in mouse
    assert "requestPointerLock" in mouse
    assert "pointerlockchange" in mouse
    assert "exitPointerLock" in mouse
    assert "setPointerCapture" in mouse
    assert "pointerleave" in mouse
    assert "scheduleMouseTransmit" in mouse
    assert "requestAnimationFrame" in mouse
    assert "boxScale" in mouse
    assert '|| "20"' in mouse
    assert "Math.max(1, Math.min(200" in mouse
    assert 'id="mouse-sens-slider" min="1" max="200" value="20"' in play
    assert "resetMouseCameraState" in mouse

    assert "queueMicrotask" in latency
    assert "keydown" in latency and "keyup" in latency
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
    assert "#vk-layout-select, #keyboard-type-select, #profile-select, #join-mode" in latency
    assert "target.blur()" in latency

    assert "mouse-camera-pad.active" in css
    assert "mouse-camera-pad.locked" in css
    assert "mouse-camera-card.fullscreen-mode" in css
    assert "layout-preset-hint" in css
    assert "@media (max-width: 768px)" in css
    assert ".vk-toolbar-left select" in css
    assert ".mouse-sensitivity-container" in css
    assert "white-space: normal" in css

    assert 'id="mouse-camera-fullscreen-btn"' in play
    assert 'id="mouse-camera-popout-btn"' in play
    assert "toggleFullscreen" in mouse
    assert "openPopoutWindow" in mouse
    assert "centerArmed" in mouse

    assert "mouseSensitivityScaleV2" in latency
    assert "if (stored === null)" in latency
    assert 'stored === "40"' not in latency
    assert 'localStorage.setItem("omnipad.mouseSensitivity", "20")' in latency
    assert "smoothLx" in keyboard and "smoothLy" in keyboard

    assert "getActiveControllerBadges" in keyboard
    assert "getActiveControllerBadges" in virtual_keyboard

    print(
        "Remote player input feature checks passed "
        "(authoritative room-code links, physical/layout separation, keyboard-surface isolation, "
        "backend-independent presets, gameplay focus recovery, profile synchronization, "
        "Cloudflare backlog control, lower/coalesced mouse camera, and mobile controls)."
    )


if __name__ == "__main__":
    main()
