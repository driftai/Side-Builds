"""Low-noise regression checks for runtime polling and target gating."""

import logging
from pathlib import Path
import sys
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.access_logging import RoutineAccessFilter
from router.event_loop import install_disconnect_filter
from router import targeting


def access_record(method: str, path: str, status: int) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1234", method, path, "1.1", status),
        None,
    )


def test_access_log_filter():
    quiet = RoutineAccessFilter()
    assert quiet.filter(access_record("GET", "/api/status", 200)) is False
    assert quiet.filter(access_record("GET", "/api/target/status?x=1", 304)) is False
    assert quiet.filter(access_record("GET", "/api/status", 500)) is True
    assert quiet.filter(access_record("POST", "/api/target/status", 200)) is True
    assert quiet.filter(access_record("GET", "/play", 200)) is True


def test_target_checks_are_direct_and_cached():
    manager = targeting.TargetManager()
    manager.selected = targeting.WindowTarget(101, 202, "Game", "game.exe", None)
    fake_gui = Mock()
    fake_process = Mock()
    fake_api = Mock()
    fake_gui.IsWindow.return_value = True
    fake_gui.GetForegroundWindow.return_value = 101
    fake_process.GetWindowThreadProcessId.return_value = (1, 202)

    with (
        patch.object(targeting, "IS_WINDOWS", True),
        patch.object(targeting, "win32gui", fake_gui),
        patch.object(targeting, "win32process", fake_process),
        patch.object(targeting, "win32api", fake_api),
    ):
        manager.list_windows = Mock(side_effect=AssertionError("hot path enumerated all windows"))
        assert manager.is_target_running() is True
        assert manager.is_target_running() is True
        assert manager.is_target_foreground() is True
        assert manager.is_target_foreground() is True

    assert fake_gui.IsWindow.call_count == 1
    # One PID lookup for the running check and one for the foreground check.
    assert fake_process.GetWindowThreadProcessId.call_count == 2
    manager.list_windows.assert_not_called()


def test_idle_target_status_avoids_win32_foreground_lookup():
    manager = targeting.TargetManager()
    manager.foreground = Mock(side_effect=AssertionError("idle status opened foreground process"))
    status = manager.get_status()
    assert status["selected"] is None
    assert status["foreground"] is None
    manager.foreground.assert_not_called()


def test_browser_polling_is_demand_driven():
    player = (ROOT / "static" / "js" / "play.js").read_text(encoding="utf-8")
    routing = (ROOT / "static" / "js" / "target_routing.js").read_text(encoding="utf-8")
    dashboard = (ROOT / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
    targets = (ROOT / "static" / "js" / "dashboard_targets.js").read_text(encoding="utf-8")
    tunnel = (ROOT / "static" / "js" / "dashboard_tunnel.js").read_text(encoding="utf-8")
    index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert "backgroundCaptureStatusTimer" not in player
    assert "backgroundInputMirrorTimer = setInterval" not in player
    assert "startRoutingStatusMonitor" in player
    assert "isCloudflareRemoteSession() ? 30000 : 10000" in routing
    assert "if (document.hidden) return" in routing
    assert "setInterval(syncBackgroundInputMirror, 50)" in routing
    assert "!backgroundCaptureEnabled" in routing
    assert "!connected" in routing
    assert "window.hostWs = hostWs" in dashboard
    assert "msg.data.target" in dashboard
    assert "window.hostWs.readyState !== WebSocket.OPEN" in targets
    assert "}, 5000);" in targets
    assert "setInterval(refreshTargetStatus, 1000)" not in targets
    assert 'id="room-code-display">--<' in index
    assert "roomCodeReady" in tunnel
    assert "waiting for the current room code" in tunnel
    assert "encodeURIComponent(roomCode)" in tunnel
    assert "code=SF6-ROOM" not in tunnel
    assert "dashboard.js?v=1.4.0" in index


def test_event_loop_filter_is_exactly_scoped():
    loop = Mock()
    fallback = Mock()
    loop.get_exception_handler.return_value = fallback
    handler_logger = Mock()
    assert install_disconnect_filter(loop, handler_logger) is fallback
    handler = loop.set_exception_handler.call_args.args[0]

    reset = ConnectionResetError()
    reset.winerror = 10054
    handler(loop, {"exception": reset})
    handler_logger.debug.assert_called_once()
    fallback.assert_not_called()

    failure = RuntimeError("real failure")
    context = {"exception": failure, "message": "must remain visible"}
    handler(loop, context)
    fallback.assert_called_once_with(loop, context)


def main():
    tests = (
        test_access_log_filter,
        test_target_checks_are_direct_and_cached,
        test_idle_target_status_avoids_win32_foreground_lookup,
        test_browser_polling_is_demand_driven,
        test_event_loop_filter_is_exactly_scoped,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Runtime efficiency tests passed ({len(tests)}/{len(tests)}).")


if __name__ == "__main__":
    main()
