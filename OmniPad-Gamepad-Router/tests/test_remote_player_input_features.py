"""Regression checks for remote player input UX additions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> None:
    play = read("static/play.html")
    routing = read("static/js/target_routing.js")
    keyboard = read("static/js/keyboard_type_adapter.js")
    mouse = read("static/js/mouse_camera.js")
    latency = read("static/js/low_latency_input.js")
    css = read("static/css/input_extensions.css")

    assert "isCloudflareRemoteSession" in routing
    assert 'controls.style.display = "none"' in routing
    assert 'touchBtn.style.display = "none"' in routing

    assert 'id="mouse-camera-pad"' in play
    assert 'id="keyboard-type-select"' in play
    assert "mouse_camera.js" in play
    assert "keyboard_type_adapter.js" in play
    assert "low_latency_input.js" in play
    assert "input_extensions.css" in play

    for key_type in ("standard", "compact65", "arrowless", "esdf", "vim_camera"):
        assert key_type in keyboard

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

    assert 'id="mouse-camera-fullscreen-btn"' in play
    assert 'id="mouse-camera-popout-btn"' in play
    assert "toggleFullscreen" in mouse
    assert "openPopoutWindow" in mouse
    assert "centerArmed" in mouse

    assert 'id="mouse-sens-slider"' in play
    assert "mouseSensitivity" in mouse
    assert "setMouseSensitivity" in mouse
    assert "mouseSensitivityScaleV2" in latency
    assert 'localStorage.setItem("omnipad.mouseSensitivity", "20")' in latency
    assert "smoothLx" in keyboard and "smoothLy" in keyboard

    vk = read("static/js/virtual_keyboard.js")
    assert "getActiveControllerBadges" in keyboard
    assert "getActiveControllerBadges" in vk

    print(
        "Remote player input feature checks passed "
        "(Cloudflare routing UI, bounded WebSocket backlog, latest-state analog transport, "
        "lower mouse default, keyboard variants, pointer lock, fullscreen/pop-out, and badges)."
    )


if __name__ == "__main__":
    main()
