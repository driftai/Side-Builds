import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.security import (
    is_local_client_host,
    is_public_tunnel_request,
    is_local_request,
    public_target_status,
)


def request(host: str, client: str):
    return SimpleNamespace(
        headers={"host": host},
        client=SimpleNamespace(host=client),
    )


def test_public_tunnel_detection():
    assert is_public_tunnel_request(request("example.trycloudflare.com", "203.0.113.10"))
    assert not is_public_tunnel_request(request("192.168.1.209:8000", "192.168.1.42"))


def test_local_client_detection():
    assert is_local_client_host("127.0.0.1")
    assert is_local_client_host("192.168.1.42")
    assert not is_local_client_host("203.0.113.10")


def test_public_tunnel_never_counts_as_local_management():
    remote = request("example.trycloudflare.com", "192.168.1.42")
    assert not is_local_request(remote)


def test_remote_target_status_is_redacted():
    status = {
        "selected": {"pid": 1234, "exe_path": r"C:\Users\Secret\game.exe"},
        "target_foreground": True,
        "target_running": True,
        "selection_mode": "target-process",
        "platform_windows": True,
    }
    safe = public_target_status(status)
    assert safe == {
        "selected": True,
        "target_foreground": True,
        "target_running": True,
        "selection_mode": "target-process",
        "platform_windows": True,
    }
    assert "pid" not in safe
    assert "exe_path" not in safe


if __name__ == "__main__":
    test_public_tunnel_detection()
    test_local_client_detection()
    test_public_tunnel_never_counts_as_local_management()
    test_remote_target_status_is_redacted()
    print("Security boundary tests passed.")
