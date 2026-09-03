# OmniPad Virtual Keyboard Port (UMDF 2)

This is OmniPad's normal-Windows virtual-port path. It creates a separately enumerable HID keyboard using a user-mode UMDF 2 driver and Microsoft's in-box HID stack. It does not filter, capture, or replace the physical keyboard.

The device exposes two top-level HID collections:

- Keyboard report ID `1`: a standard 8-byte keyboard state, visible to Windows, Raw Input, and compatible games.
- Vendor feature report ID `2`: a local control channel through which OmniPad submits the next 8-byte state.

The driver is latest-state-wins and has a 750 ms internal watchdog. Duplicate state frames refresh the watchdog without generating duplicate keyboard input. If OmniPad exits or stops reporting while keys are held, the driver publishes an all-keys-up state.

## Build

Requirements are intentionally limited to Visual Studio 2022 Build Tools, the x64 C++ tools, Windows SDK, and WDK:

```powershell
powershell -ExecutionPolicy Bypass -File .\drivers\virtual-keyboard-umdf\build-driver.ps1
```

The build creates a UMDF `.dll`, `.inf`, and `.cat`. It does not install anything or change Windows boot settings.

## Signing and installation boundary

Normal-mode installation still requires Windows to trust the package catalog. For private development, sign the generated catalog with a certificate that this machine explicitly trusts. For distribution, use Microsoft/Partner Center signing.

The preferred interactive entry point is `control.bat` → **Install/repair** or **Virtual keyboard management**. Standard install verifies the pinned package under `package/x64`, asks for explicit local trust, and creates or updates only the OmniPad root device through Windows SetupAPI and PnPUtil. It does not require Visual Studio, WDK, SDK tools, or DevCon. Exact device/certificate/package removal, the concise live smoke, developer rebuild, and preserved VHF build remain available from the keyboard menu.

The guarded local-development helper is:

```powershell
powershell -ExecutionPolicy Bypass -File .\drivers\virtual-keyboard-umdf\sign-local-package.ps1 -TrustLocalCertificate
```

That command deliberately requires an explicit switch because it creates a non-exportable local signing key and adds its public certificate to this machine's Root and TrustedPublisher stores. It does not change boot mode. Do not use the local certificate for public distribution.

After a developer rebuild/sign, install from an elevated prompt:

```powershell
powershell -ExecutionPolicy Bypass -File .\drivers\virtual-keyboard-umdf\install-driver.ps1
```

For a single elevated provisioning step, add `-InstallAfterSigning` to the signing command.

Run the installed-device smoke with bounded console output:

```powershell
.\tools\run_umdf_installed_smoke.bat
```

It performs 13 checks covering device/control-path discovery, Raw Input identity, factory availability, backend selection and lifecycle, WASD make/break, modifier release, six-key rollover, duplicate suppression, heartbeat behavior, driver-side watchdog release, 64 rapid state transitions ending neutral, and endpoint reopen. The console receives one summary line; structured details go to the ignored `logs/umdf_installed_smoke.json` file.

Exact rollback is available through `remove-driver.ps1 -RemoveDevice`. It uses in-box PnPUtil to remove only the matching device and its exact driver-store package. Pass recorded signing thumbprints through `-CertificateThumbprint` only when the corresponding OmniPad trust certificates should also be removed.

`install-driver.ps1` refuses unsigned or untrusted packages. It does not enable Test Mode, disable Secure Boot, edit BCD, create certificates, or change certificate stores. Those trust decisions remain a separate explicit step.

The preserved `drivers/virtual-keyboard` KMDF/VHF implementation remains available as the future Microsoft-signed kernel source path.

Architecture reference: Microsoft's `Windows-driver-samples/hid/vhidmini2` UMDF 2 sample and `MsHidUmdf.inf` integration model.
