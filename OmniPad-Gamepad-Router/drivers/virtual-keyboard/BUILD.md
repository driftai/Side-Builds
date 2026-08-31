# OmniPad Virtual Keyboard HID — Development Build

This folder contains the first OmniPad-owned VHF/KMDF virtual keyboard implementation path. It is intentionally source-first: no unsigned `.sys` binary is committed.

## What this adds

- A Windows 10/11 KMDF source driver using Microsoft's Virtual HID Framework (VHF).
- A standard boot-protocol-style 8-byte keyboard input report (modifier, reserved, six HID key usages).
- A private OmniPad IOCTL for submitting the current keyboard report from the host process.
- A root-enumerated device installation path via INF.
- A small native bridge executable source that can send reports to the driver.

## Build prerequisites

Install Visual Studio 2022 with Desktop development with C++ and the Windows Driver Kit (WDK) matching the installed Windows SDK. Build the `OmniPadVirtualKeyboard.sln` solution as x64 Debug first.

The development machine can use Windows test signing. Microsoft documents that x64 kernel drivers must be signed to load; test-signing is the development path, while release distribution requires proper driver signing. See the links in the project README.

## Driver install

Run the generated installer commands from an elevated PowerShell prompt after building. The exact output directory depends on the Visual Studio/WDK configuration.

Do not use `bcdedit /set testsigning on` on a production machine unless you intentionally want Windows Test Mode. Rebooting is required after changing test-signing state.

## Device contract

The user-mode bridge opens the OmniPad device interface and sends a fixed 8-byte keyboard report:

`[modifiers, reserved, key0, key1, key2, key3, key4, key5]`

The driver converts that report into a HID input report and submits it through `VhfReadReportSubmit`.

The report uses HID usage IDs, not Windows virtual-key codes. The OmniPad Python server therefore converts browser `KeyboardEvent.code` values into USB HID keyboard usage IDs before calling the bridge.

## Security boundary

Only the host process should have access to the device interface. The driver does not capture the physical keyboard and does not install a keyboard filter. It creates an additional virtual keyboard device specifically for OmniPad's remote-player output.
