import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.backends.umdf_keyboard import VirtualKeyboardPortBackend
from router.umdf_keyboard import (
    CONTROL_REPORT_ID,
    CONTROL_REPORT_SIZE,
    CONTROL_USAGE,
    CONTROL_USAGE_PAGE,
    OMNIPAD_UMDF_PID,
    OMNIPAD_UMDF_VID,
    UmdfKeyboardDevice,
    build_control_feature_report,
    is_omnipad_hid_path,
)
from router.vhf_keyboard import build_keyboard_report

ROOT = Path(__file__).resolve().parents[1]


def test_control_report_contract():
    keyboard = build_keyboard_report(["ControlLeft", "ShiftLeft", "KeyW"])
    control = build_control_feature_report(keyboard)
    assert len(keyboard) == 8
    assert len(control) == CONTROL_REPORT_SIZE == 9
    assert control == bytes([CONTROL_REPORT_ID]) + keyboard
    assert OMNIPAD_UMDF_VID == 0x0F0F
    assert OMNIPAD_UMDF_PID == 0x0303
    assert CONTROL_USAGE_PAGE == 0xFF00
    assert CONTROL_USAGE == 0x0001
    print("  [PASS] UMDF vendor feature report wraps the tested 8-byte keyboard state")


def test_device_discovery_contract():
    device, error = UmdfKeyboardDevice.try_open()
    if device is None:
        assert error
        print(f"  [INFO] UMDF keyboard port is not installed: {error}")
    else:
        assert device.available
        assert device.device_path
        assert is_omnipad_hid_path(device.device_path)
        print(f"  [PASS] UMDF keyboard control collection opened at {device.device_path}")
        device.close()


def test_backend_lifecycle():
    class FakeDevice:
        def __init__(self):
            self.reports = []
            self.release_count = 0
            self.closed = False

        def submit_report(self, report):
            self.reports.append(report)

        def release_all(self):
            self.release_count += 1

        def close(self):
            self.closed = True

    device = FakeDevice()
    backend = VirtualKeyboardPortBackend.__new__(VirtualKeyboardPortBackend)
    backend.slot_id = 1
    backend.device = device
    backend.last_report = bytes(8)

    backend.apply({"key_codes": ["AltLeft", "KeyD"]})
    assert device.reports == [bytes([0x04, 0, 0x07, 0, 0, 0, 0, 0])]
    assert backend.last_report == device.reports[-1]

    backend.release_all()
    assert device.release_count == 1
    assert backend.last_report == bytes(8)

    backend.close()
    assert device.closed
    assert backend.device is None
    print("  [PASS] UMDF backend apply, all-keys-up, and close lifecycle")


def test_driver_source_contract():
    folder = ROOT / "drivers" / "virtual-keyboard-umdf"
    lifecycle_source = (folder / "OmniPadVirtualKeyboardUmdf.c").read_text(encoding="utf-8")
    hid_source = (folder / "OmniPadVirtualKeyboardHid.c").read_text(encoding="utf-8")
    descriptor_source = (folder / "OmniPadVirtualKeyboardDescriptors.c").read_text(encoding="utf-8")
    source = "\n".join((lifecycle_source, hid_source, descriptor_source))
    header = (folder / "OmniPadVirtualKeyboardUmdf.h").read_text(encoding="utf-8")
    inf = (folder / "OmniPadVirtualKeyboardUmdf.inx").read_text(encoding="utf-8")
    project = (folder / "OmniPadVirtualKeyboardUmdf.vcxproj").read_text(encoding="utf-8")
    installer = (folder / "install-driver.ps1").read_text(encoding="utf-8")
    signer = (folder / "sign-local-package.ps1").read_text(encoding="utf-8")
    remover = (folder / "remove-driver.ps1").read_text(encoding="utf-8")
    installed_smoke = (ROOT / "tools" / "umdf_installed_smoke.py").read_text(encoding="utf-8")
    slots = (ROOT / "router" / "slot_manager.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "static" / "js" / "dashboard_slots.js").read_text(encoding="utf-8")

    assert "OMNIPAD_KEYBOARD_REPORT_ID 0x01" in header
    assert "OMNIPAD_CONTROL_REPORT_ID 0x02" in header
    assert "OMNIPAD_WATCHDOG_TIMEOUT_MS 750" in header
    assert "0x06, 0x00, 0xFF" in source
    assert "OmniPadEvtWatchdog" in source
    assert "RtlCompareMemory" in source
    assert "WdfRequestForwardToIoQueue" in source
    assert "WdfIoQueueRetrieveNextRequest" in source
    assert "Class=HIDClass" in inf
    assert "Root\\OmniPadVirtualKeyboardUmdf" in inf
    assert "Include=MsHidUmdf.inf" in inf
    assert "Include=WUDFRD.inf" in inf
    assert "UmdfService=\"OmniPadVirtualKeyboardUmdf\"" in inf
    assert "WindowsUserModeDriver10.0" in project
    assert "<DriverType>UMDF</DriverType>" in project
    assert 'ClCompile Include="OmniPadVirtualKeyboardDescriptors.c"' in project
    assert 'ClCompile Include="OmniPadVirtualKeyboardHid.c"' in project
    assert "OmniPadGetHidDescriptor" in lifecycle_source
    assert "OmniPadEvtIoDeviceControl" in hid_source
    assert "g_ReportDescriptor" in descriptor_source
    assert "Get-AuthenticodeSignature" in installer
    assert "signature.Status -ne 'Valid'" in installer
    assert "bcdedit" not in installer.lower()
    assert "testsigning" not in installer.lower()
    assert "TrustLocalCertificate" in signer
    assert "InstallAfterSigning" in signer
    assert "KeyExportPolicy NonExportable" in signer
    assert "Cert:\\LocalMachine\\TrustedPublisher" in signer
    assert "Cert:\\LocalMachine\\Root" in signer
    assert "bcdedit" not in signer.lower()
    assert "testsigning" not in signer.lower()
    assert "Root\\OmniPadVirtualKeyboardUmdf" in remover
    assert "CertificateThumbprint" in remover
    assert "--quiet" in (ROOT / "tools" / "run_umdf_installed_smoke.bat").read_text(encoding="utf-8")
    assert "duplicate_suppression" in installed_smoke
    assert "driver_watchdog_release" in installed_smoke
    assert "heartbeat_prevents_watchdog" in installed_smoke
    assert "backend_apply_release" in installed_smoke
    assert "rapid_transition_final_neutral" in installed_smoke
    assert "endpoint_reopen" in installed_smoke
    assert '"virtual_keyboard_port"' in slots
    assert 'backendId === "virtual_keyboard_port"' in dashboard
    print("  [PASS] UMDF descriptor, sideband, watchdog, INF, and normal-mode boundaries")


def main():
    print("\n" + "=" * 60)
    print("  TEST: OmniPad Normal-Mode UMDF Virtual Keyboard Port")
    print("=" * 60)
    test_control_report_contract()
    test_device_discovery_contract()
    test_backend_lifecycle()
    test_driver_source_contract()
    print("  >>> UMDF VIRTUAL KEYBOARD TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    main()
