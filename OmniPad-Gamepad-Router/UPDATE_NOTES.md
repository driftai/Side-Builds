# OmniPad 1.1.2-dev

## Added — True Virtual Keyboard HID path
- Added an OmniPad-owned KMDF/VHF virtual keyboard source driver under `drivers/virtual-keyboard/`.
- Added a root-enumerated INF, WDK project/solution, build helper, install helper, and removal helper.
- Added a Python user-mode IOCTL bridge in `router/vhf_keyboard.py`.
- Added browser `KeyboardEvent.code` -> USB HID usage translation so remote physical key identity reaches the virtual device.
- The backend now reports itself as available only when the virtual keyboard device can actually be opened.
- Added standalone tests for HID report construction, modifiers, duplicate keys, and the six-key boot-report limit.

## Why this exists
`SendInput` is still the practical no-driver fallback, but it injects into Windows' normal keyboard stream rather than creating a distinct keyboard identity. The VHF backend is intended for games/apps that need a genuinely separate keyboard device through the HID/Raw Input stack.

## Current limitations
- The driver source must be built and installed on Windows with the WDK.
- Development may require Windows Test Mode/test signing; release distribution needs proper driver signing.
- The initial report is boot-compatible and carries up to six simultaneous non-modifier keys. NKRO can be added later if needed.
- A separate HID keyboard does not guarantee that every game supports two keyboards; the game must actually use an input path that distinguishes devices.

## Existing 1.1.1 behavior retained
- Remote gamepad -> ViGEmBus continues to work.
- Target-locked SendInput remains available.
- Running-game targeting and the foreground safety gate remain unchanged.
