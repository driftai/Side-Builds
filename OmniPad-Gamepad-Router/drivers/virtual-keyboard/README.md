# OmniPad Virtual Keyboard HID

This folder now contains an **OmniPad-owned VHF/KMDF virtual keyboard implementation path**, not just a placeholder.

## Project status

This path is preserved for future Microsoft signing. It is on hold, not removed or discontinued, while OmniPad uses normal-mode output backends. Its sources, build helpers, package validation, and automated regression coverage remain maintained so development can resume without reconstructing the driver.

## Architecture

`Remote browser keyboard -> WebSocket -> OmniPad slot state -> DOM code -> USB HID usage -> IOCTL -> KMDF/VHF -> Windows HID keyboard`

The driver creates a separate virtual keyboard device. It does **not** filter or capture the host's physical keyboard.

Microsoft's Virtual HID Framework is the supported Windows architecture for a software HID source driver. The source driver provides a HID report descriptor, calls `VhfCreate`/`VhfStart`, and submits reports with `VhfReadReportSubmit`.

## Files

- `OmniPadVirtualKeyboard.c` — KMDF/VHF source driver.
- `OmniPadVirtualKeyboard.h` — device contract and private IOCTL.
- `OmniPadVirtualKeyboard.inf` — root-enumerated installation package with the `vhf` lower filter.
- `OmniPadVirtualKeyboard.vcxproj` — WDK build project.
- `build-driver.ps1` — Debug x64 build helper.
- `install-driver.ps1` — WDK `devcon` install helper.
- `remove-driver.ps1` — device removal helper.
- `router/vhf_keyboard.py` — user-mode IOCTL bridge and DOM→HID usage conversion.

## Keyboard report

The initial implementation uses a standard 8-byte boot-compatible keyboard report:

`[modifier, reserved, key0, key1, key2, key3, key4, key5]`

Modifier usages (`Control`, `Shift`, `Alt`, `GUI`) are packed into the first byte. Other HID usages occupy up to six simultaneous key slots.

This is deliberately simple for the first driver milestone. An NKRO descriptor can be added later if a target game needs more than six simultaneous non-modifier keys.

## Driver development requirements

- Windows 10/11 desktop host.
- Visual Studio 2022 Build Tools with the x64/x86 C++ tools.
- Matching Windows SDK and Windows Driver Kit (WDK) versions.
- The WDK Visual Studio build-tools component.
- Administrator access for driver installation.

The repository intentionally does not contain an unsigned `.sys` binary. Build it locally with the WDK and install it only on a development/test machine.

For x64 development, Windows requires signed kernel drivers. Microsoft documents Windows Test Mode for development signing and normal driver signing requirements for release distribution.

## Installation flow

1. Run `build-driver.ps1`. The complete package is written to `x64\Debug\OmniPadVirtualKeyboard`.
2. Sign the driver image and catalog with a certificate trusted by the target machine. The default build uses `SignMode=Off` for static verification and cannot be installed as-is.
3. If using a self/test-signed build, intentionally configure the machine's Secure Boot/Test Mode state and reboot as required by your development setup.
4. Run `install-driver.ps1` from an elevated PowerShell prompt. It refuses incomplete or untrusted packages.
5. Confirm the device exists in Device Manager.
6. Start/restart OmniPad from an elevated prompt. The driver's private report-injection
   endpoint is restricted to administrators and LocalSystem.
7. Select **Virtual Keyboard HID (VHF)** as the Player 2 backend.

OmniPad checks the device path at runtime, so the dashboard only marks the VHF backend as available when the host can actually open the virtual keyboard endpoint.

## Safety

The global OmniPad target gate still applies. When enabled, the slot releases its virtual keyboard report whenever the selected game window is not foreground.

To uninstall the development device, use `remove-driver.ps1` and reboot if Windows requests it.
