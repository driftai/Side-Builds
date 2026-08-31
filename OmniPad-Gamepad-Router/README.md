# 🎮 OmniPad Gamepad Router (v1.1.2-dev)

**OmniPad** is a lightweight Windows server and real-time web controller engine for **remote 2-player local multiplayer**. A friend can connect from a browser on another PC, phone, or tablet and stream controller or keyboard input into a game already running on the host PC.

---

## 🚀 Core capabilities

- Remote 2-player local co-op / versus over LAN or the Internet.
- Browser controller with USB/Bluetooth gamepad support through the Gamepad API.
- Keyboard Fighter mode with raw `KeyboardEvent.code` preservation.
- Native Xbox 360 and DualShock 4 virtual controllers through ViGEmBus.
- Running-game window targeting using HWND/PID discovery; no DLL/process injection.
- Cloudflare Quick Tunnel for cross-city sessions without port forwarding.
- 250 ms stuck-input watchdog and panic release.
- SOCD cleaning for fighting-game inputs.
- **True Virtual Keyboard HID development path:** OmniPad now includes an initial Windows KMDF/VHF source driver and a Python IOCTL bridge so the host can expose a genuinely separate virtual keyboard device.

---

## 🕹️ Output modes

| Mode | Backend | Purpose | Status |
|---|---|---|---|
| Xbox 360 | ViGEmBus | Native XInput Player 2 controller | Working |
| DualShock 4 | ViGEmBus | Native DS4/DirectInput Player 2 controller | Working |
| Keyboard 2 (Target-Locked) | Windows `SendInput` | Compatibility keyboard bridge | Working |
| **Virtual Keyboard HID (VHF)** | **KMDF + VHF** | **Separate Windows HID keyboard device** | **Development / test** |
| Noop | Diagnostic | Input pipeline testing without hardware | Working |

### Why the VHF backend matters

`SendInput` injects keyboard events into Windows' normal keyboard path. It does not create another physical-looking keyboard identity. For software that distinguishes devices through Raw Input/HID, that can prevent a remote keyboard from behaving as Player 2.

Microsoft's Virtual HID Framework is the supported architecture for a software HID source driver. A KMDF driver supplies a HID report descriptor, creates a VHF device, and submits input reports through `VhfReadReportSubmit`. Windows then exposes the virtual device through the normal HID stack. See Microsoft's VHF documentation for the framework and report-submission model.

OmniPad's new VHF backend uses a standard 8-byte boot keyboard report:

`[modifiers, reserved, key0, key1, key2, key3, key4, key5]`

The browser continues to transmit physical `KeyboardEvent.code` values. The host converts those DOM codes to USB HID usage IDs and sends the resulting report to the VHF driver.

---

## 🧩 Virtual Keyboard HID — current implementation

The source lives under `drivers/virtual-keyboard/`:

- `OmniPadVirtualKeyboard.c` — KMDF/VHF source driver.
- `OmniPadVirtualKeyboard.h` — IOCTL and report contract.
- `OmniPadVirtualKeyboard.inf` — root-enumerated HID installation package.
- `OmniPadVirtualKeyboard.vcxproj` / `.sln` — WDK build project.
- `build-driver.ps1` — Debug x64 build helper.
- `install-driver.ps1` — WDK `devcon` installation helper.
- `remove-driver.ps1` — clean removal helper.
- `router/vhf_keyboard.py` — Python user-mode bridge and DOM→HID translation.
- `tests/test_vhf_keyboard.py` — descriptor-independent report construction tests.

The driver does **not** capture or filter the host's physical keyboard. It creates an additional virtual HID keyboard specifically for OmniPad's remote-player output.

### Development installation

The driver is source-first and no unsigned `.sys` is committed to the repository.

1. Install Visual Studio 2022 with C++ desktop development and a matching WDK.
2. Build `drivers/virtual-keyboard/OmniPadVirtualKeyboard.sln` as x64 Debug, or run `build-driver.ps1`.
3. Windows x64 requires kernel driver signing. For development, Microsoft documents test-signing as the development path. Test mode requires administrator access and a reboot.
4. From an elevated PowerShell prompt, run `install-driver.ps1` after the driver has been built.
5. Verify the device appears in Device Manager and then restart OmniPad.
6. In the OmniPad dashboard, select **Virtual Keyboard HID (VHF)** for Player 2. The backend is advertised as available only when the device handle can actually be opened.

Do not enable Windows Test Mode on a production machine unless you intentionally accept the development-driver tradeoffs.

### Driver protocol

The host opens:

`\\.\OmniPadVirtualKeyboard`

and sends `IOCTL_OMNIPAD_SET_KEYBOARD_REPORT` with one 8-byte keyboard report. The KMDF driver passes that report to `VhfReadReportSubmit` using report ID `0`.

This keeps the network protocol unchanged: browser → WebSocket → slot state → output backend.

---

## 🎯 Running-game target attachment

1. Open the dashboard at `http://localhost:8000/`.
2. Click **Refresh Running Apps** or **Select Foreground** with the game focused.
3. Select the running game and click **Attach**.
4. With the foreground gate enabled, remote output is released automatically whenever the selected target is not foreground.
5. This is an OS-level window guard. OmniPad does not inject DLLs or patch game memory.

The target gate applies to the VHF keyboard backend as well as virtual gamepads and the SendInput backend.

---

## 🌐 Remote connection

### LAN

Start `start_router.bat`, then share the generated `/play?code=...` LAN URL.

### Internet

Start `start_with_tunnel.bat`, then share the generated `https://*.trycloudflare.com/play?code=...` URL.

The remote user needs only a modern browser for keyboard/touch control. A browser gamepad can be a Bluetooth or USB controller connected to their device.

> [!WARNING]
> Cloudflare Quick Tunnels create temporary public URLs without account authentication. Share the tunnel URL and room code only with intended players and stop the tunnel when the session ends.

---


## 🪟 Background keyboard capture while the browser is unfocused

A normal browser page cannot keep receiving physical keyboard events after another application takes keyboard focus. OmniPad therefore includes an optional Windows companion for screen-share/gameplay setups where the /play page should remain open in the background.

The helper is located at:

`static/tools/background_keyboard_helper.py`

It uses a native global keyboard listener and forwards only OmniPad's supported game-control keys. It does **not** suppress local key delivery and does not log typed text. It sends the same raw key codes plus the WASD/arrow/action controller mapping used by OmniPad's controller-keyboard presets.

On the computer whose keyboard should control the remote slot:

`python -m pip install -r requirements.txt`

`python static/tools/background_keyboard_helper.py --play-url "http://HOST:8000/play?code=YOUR-ROOM"`

For a Cloudflare HTTPS play URL, pass that full URL and the helper automatically uses `wss://`.

The browser may stay open in the background while the helper runs. Press `Ctrl+Alt+F8` to pause/resume global capture, or `Ctrl+C` to stop the helper.

---

## 🧪 Testing

Run `run_tests.bat` for the existing smoke suite and the driver-independent VHF report tests.

The VHF driver itself must be built and tested on Windows with the WDK. The Python report tests can run without a driver because they validate the browser-code → HID-usage conversion independently.

Important game-compatibility note: a separate HID device is **necessary but not sufficient** for every game. Whether a game exposes multiple keyboard devices to Player 1/Player 2 depends on that game's input architecture. Raw Input is the Windows API that can identify distinct keyboard devices; games must still choose to use that capability.

---

## 📌 Development status

**v1.1.2-dev** is the first OmniPad release where the VHF path is wired through the full stack instead of being only a placeholder:

`Remote Keyboard → WebSocket → OmniPad → HID usage translation → KMDF/VHF → Windows HID keyboard`

The remaining validation is native Windows driver compilation/installation and real multi-keyboard game testing. The existing SendInput backend remains available as the no-driver fallback.
