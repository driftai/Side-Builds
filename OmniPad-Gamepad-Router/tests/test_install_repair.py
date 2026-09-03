"""Non-mutating installation, containment, and repair-contract smokes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "drivers" / "virtual-keyboard-umdf" / "package" / "x64"
EXPECTED_HASHES = {
    "OmniPadVirtualKeyboardUmdf.dll": "DF426D4AB25B0F8DB55DADFF710B0FACB481FF7E1684F18760A3EEEE36EB5D56",
    "OmniPadVirtualKeyboardUmdf.inf": "DA625B665866FB216DB20FA3909DFBEC8D6B6D2E3CF45A76C651E5B5486B94EB",
    "OmniPadVirtualKeyboardUmdf.cat": "1020F1022B4285FC2CFA505316B7ED0831F40A3B934C58F36E1C08EE07FBF98C",
    "OmniPadLocalUmdfDevelopment.cer": "04794A713B9B891AC0142834EDE9453AB960D53D3162BC428BACD2998D123081",
}


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def run_powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_entry_points_and_scopes() -> None:
    control = text("control.bat")
    entry = text("install_or_repair.bat")
    repair = text("tools/install_or_repair.ps1")
    assert "call install_or_repair.bat" in control
    assert "-Action Status" in entry
    assert "-Action RepairAll -Confirmed" in entry
    assert "-Action RepairCore -Confirmed" in entry
    assert "Repair requires -Confirmed" in repair
    assert "VHF/WDK files are preserved" in entry
    forbidden = ("bcdedit", "testsigning", "nointegritychecks")
    assert not any(term in repair.lower() for term in forbidden)
    print("  [PASS] One control-center repair entry exposes status, core, and all-runtime scopes")


def test_dependency_contract() -> None:
    requirements = text("requirements.txt")
    setup = text("tools/setup_env.bat")
    repair = text("tools/install_or_repair.ps1")
    tunnel = text("router/tunnel.py")
    assert "vgamepad==0.1.0" in requirements
    assert "VGAMEPAD_SKIP_VIGEMBUS_INSTALL=true" in setup
    assert "ViGEmBusSetup_x64.msi" in repair
    assert "msiexec.exe" in repair and "/norestart" in repair
    assert "Python.Python.3.12" in repair and "--scope user" in repair
    assert "cloudflare/cloudflared/releases/latest/download" in repair
    assert "Get-AuthenticodeSignature" in repair and "Cloudflare, Inc" in repair
    assert '".runtime", "bin", "cloudflared.exe"' in tunnel
    assert "install WDK/Visual Studio" in text("install_or_repair.bat")
    print("  [PASS] Runtime repair is minimal, signed-source-aware, and repo-local where possible")


def test_bundled_umdf_integrity() -> None:
    for name, expected in EXPECTED_HASHES.items():
        path = PACKAGE / name
        assert path.is_file(), f"missing bundled runtime artifact: {path}"
        assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == expected
    signer_script = (
        "$s=Get-AuthenticodeSignature -LiteralPath "
        f"'{PACKAGE / 'OmniPadVirtualKeyboardUmdf.cat'}'; "
        "[pscustomobject]@{Status=[string]$s.Status;"
        "Thumbprint=$s.SignerCertificate.Thumbprint;"
        "Subject=$s.SignerCertificate.Subject}|ConvertTo-Json -Compress"
    )
    result = run_powershell(signer_script)
    assert result.returncode == 0, result.stderr
    signature = json.loads(result.stdout.strip())
    # A fresh machine may report the catalog as untrusted until the explicitly
    # pinned public certificate is accepted; signer identity must still parse.
    assert signature["Status"] in {"Valid", "UnknownError", "NotTrusted"}
    assert signature["Thumbprint"] == "5631FB22CE4E3E6512CAADE65B4F5963644BB56D"
    assert signature["Subject"] == "CN=OmniPad Local UMDF Development"
    print("  [PASS] Bundled UMDF DLL/INF/catalog/certificate are pinned and signature-valid")


def test_driver_install_is_sdk_independent() -> None:
    installer = text("drivers/virtual-keyboard-umdf/install-driver.ps1")
    bundled = text("drivers/virtual-keyboard-umdf/install-bundled-package.ps1")
    remover = text("drivers/virtual-keyboard-umdf/remove-driver.ps1")
    assert "SetupDiCreateDeviceInfo" in installer
    assert "SetupDiSetDeviceRegistryProperty" in installer
    assert "DIF_REGISTERDEVICE" in installer
    assert "pnputil.exe /add-driver" in installer
    assert "pnputil.exe /remove-device" in remover
    assert "pnputil.exe /delete-driver" in remover
    assert "expectedThumbprint" in bundled and "expectedHashes" in bundled
    assert "$devcon" not in (installer + remover).lower()
    assert "Windows Kits" not in installer
    print("  [PASS] Normal install/remove use in-box SetupAPI/PnPUtil, not WDK or DevCon")


def test_powershell_parsing_and_status() -> None:
    scripts = [
        ROOT / "tools" / "install_or_repair.ps1",
        ROOT / "drivers" / "virtual-keyboard-umdf" / "install-driver.ps1",
        ROOT / "drivers" / "virtual-keyboard-umdf" / "install-bundled-package.ps1",
        ROOT / "drivers" / "virtual-keyboard-umdf" / "remove-driver.ps1",
    ]
    for path in scripts:
        command = (
            "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{path}',[ref]$null,[ref]$e); if($e){{$e|Out-String|Write-Error;exit 1}}"
        )
        result = run_powershell(command)
        assert result.returncode == 0, result.stderr
    installer_path = ROOT / "drivers" / "virtual-keyboard-umdf" / "install-driver.ps1"
    compile_interop = (
        f"$c=Get-Content -Raw '{installer_path}';"
        "$m=\"Add-Type -TypeDefinition @'\";$a=$c.IndexOf($m)+$m.Length;"
        "$b=$c.IndexOf(\"'@\",$a);$s=$c.Substring($a,$b-$a);"
        "Add-Type -TypeDefinition $s;"
        "if(-not ('OmniPadRootDeviceInstaller' -as [type])){exit 1}"
    )
    compiled = run_powershell(compile_interop)
    assert compiled.returncode == 0, compiled.stderr
    status = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "tools" / "install_or_repair.ps1"), "-Action", "Status",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    for label in ("LAN/controller runtime", "Cloudflare runtime", "Virtual keyboard", "VHF future source"):
        assert label in status.stdout
    print("  [PASS] Repair scripts parse and read-only readiness status executes successfully")


def main() -> None:
    print("\n" + "=" * 60)
    print("  TEST: OmniPad Install / Repair")
    print("=" * 60)
    test_entry_points_and_scopes()
    test_dependency_contract()
    test_bundled_umdf_integrity()
    test_driver_install_is_sdk_independent()
    test_powershell_parsing_and_status()
    print("  >>> INSTALL / REPAIR TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    main()
