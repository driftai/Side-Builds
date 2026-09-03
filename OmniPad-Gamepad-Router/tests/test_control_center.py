"""Control-center ownership, scoping, and graceful-shutdown smoke tests."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys

from fastapi import HTTPException
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_control_surface_contract():
    control = (ROOT / "control.bat").read_text(encoding="utf-8")
    manager = (ROOT / "tools" / "manage_router.ps1").read_text(encoding="utf-8")
    cleanup = (ROOT / "tools" / "cleanup_stragglers.bat").read_text(encoding="utf-8")
    lan = (ROOT / "tools" / "start_router.bat").read_text(encoding="utf-8")
    tunnel = (ROOT / "tools" / "start_with_tunnel.bat").read_text(encoding="utf-8")

    for action in ("StartTunnel", "StopTunnel", "Panic", "OpenDashboard", "Cleanup"):
        assert action in manager
    assert ".runtime" in manager and "omnipad-control.json" in manager
    assert "Test-ManagedProcess" in manager
    assert "Test-ServerCommandLine" in manager
    assert "StringComparison]::OrdinalIgnoreCase" in manager
    assert "/api/control/shutdown" in manager
    assert "Get-DescendantProcessIds" in manager
    assert "taskkill /F /IM" not in control
    assert "taskkill /F /IM" not in cleanup
    assert "REMOVE UMDF" in control
    assert "leave current router state unchanged" in control
    assert "manage_router.ps1" in lan and "-Mode lan" in lan
    assert "manage_router.ps1" in tunnel and "-Mode tunnel" in tunnel
    print("  [PASS] Control center owns start/status/tunnel/panic/stop and scoped cleanup")


def test_driver_management_contract():
    folder = ROOT / "drivers" / "virtual-keyboard-umdf"
    manager = (folder / "manage-driver.ps1").read_text(encoding="utf-8")
    installer = (folder / "install-driver.ps1").read_text(encoding="utf-8")

    assert "Root\\OmniPadVirtualKeyboardUmdf" in manager
    assert "CN=OmniPad Local UMDF Development" in manager
    assert "-Confirmed" in manager
    assert "-Verb RunAs" in manager
    assert "remove-driver.ps1" in manager
    assert "bcdedit" not in manager.lower()
    assert "testsigning" not in manager.lower()
    assert "Invoke-Expression" not in installer
    assert "& $devcon update $InfPath $hardwareId" in installer
    assert "& $devcon install $InfPath $hardwareId" in installer
    print("  [PASS] UMDF install/update/removal controls retain explicit scope and confirmation")


def test_graceful_shutdown_contract():
    import router.api_routes as api_routes

    class FakeSlots:
        def __init__(self):
            self.released = False

        async def panic_reset(self, slot_id):
            assert slot_id is None
            self.released = True

    old_slots = api_routes._slot_manager
    old_callback = api_routes._shutdown_callback
    slots = FakeSlots()
    called = {"shutdown": False}

    async def callback():
        called["shutdown"] = True
        return True

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/control/shutdown",
        "headers": [(b"host", b"localhost")],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "query_string": b"",
    }
    try:
        api_routes._slot_manager = slots
        api_routes._shutdown_callback = callback
        lan_scope = {**scope, "client": ("192.168.1.50", 12345)}
        try:
            asyncio.run(api_routes.shutdown_router(Request(lan_scope)))
            raise AssertionError("LAN client unexpectedly reached host shutdown")
        except HTTPException as exc:
            assert exc.status_code == 403
        result = asyncio.run(api_routes.shutdown_router(Request(scope)))
        assert result["ok"] is True
        assert slots.released and called["shutdown"]
    finally:
        api_routes._slot_manager = old_slots
        api_routes._shutdown_callback = old_callback
    print("  [PASS] Host-only controlled shutdown releases outputs before requesting exit")


def test_manager_status_command():
    if os.name != "nt":
        return
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "tools" / "manage_router.ps1"), "-Action", "Status",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Router:" in result.stdout
    print("  [PASS] Managed status command runs with bounded output")


def main():
    print("\n" + "=" * 60)
    print("  TEST: OmniPad Control Center")
    print("=" * 60)
    test_control_surface_contract()
    test_driver_management_contract()
    test_graceful_shutdown_contract()
    test_manager_status_command()
    print("  >>> CONTROL CENTER TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    main()
