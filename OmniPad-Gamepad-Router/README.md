# 🎮 OmniPad Gamepad Router

**OmniPad** is a lightweight Windows server and real-time web controller engine for turning a PC game into a remotely playable local multiplayer session. A friend can connect from a browser on another PC, phone, or tablet and control a dedicated Player 2 virtual controller while Player 1 continues using the host's own keyboard or controller.

The project is designed as a **barebones server + web UI**, not a monolithic compiled application.

---

## 🎛️ Control center

Run `control.bat` for the single host control surface. It keeps the menu available while a managed router runs hidden, and provides explicit controls for start, status/URLs, dashboard, Cloudflare start/stop, panic release, full router shutdown, diagnostics, and UMDF keyboard management.

Managed PID, port, mode, and log paths are written under the ignored `.runtime/` directory. Stop and cleanup validate the exact repository `server.py` command line before touching a process, and cleanup affects only that server and its children. A normal stop calls the host-loopback-only shutdown API, releases every output, closes the background helper and tunnel, and then removes its runtime state. Exiting only the control menu deliberately leaves the router in its current state.

The installed UMDF keyboard remains enumerated but idle when the router is stopped; its independent 750 ms watchdog releases keys if the host process disappears unexpectedly.

---

## 🚀 What OmniPad does

- Remote 2-player local co-op / versus over **LAN or the Internet**.
- Browser-based **keyboard, touchscreen, and gamepad** control.
- Native **Xbox 360 and DualShock 4** virtual controllers through ViGEmBus.
- Optional **separate virtual keyboard HID** using a normal-mode UMDF 2 virtual port, with KMDF/VHF preserved for future Microsoft signing.
- Running-game discovery and target attachment using Windows HWND/PID APIs, without DLL injection or game-memory patching.
- **Cloudflare Quick Tunnel** support for cross-city play without manual port forwarding.
- Low-latency keyboard and mouse-camera input transport.
- Touchscreen virtual gamepad with multiple ergonomic layouts.
- Physical keyboard-type presets for keyboards that do not match the default key arrangement.
- Background keyboard helper for local/LAN unfocused gameplay.
- Stuck-input watchdog, panic release, SOCD cleaning, target liveness gating, and remote-player isolation.
- Live observer/monitor mode so another browser tab can watch authoritative remote input state without stealing control.

---

## 🧩 Control surfaces

OmniPad separates the **input surface** from the **output backend**. A remote user can therefore use a keyboard, browser touchscreen, or real gamepad while the host chooses how that input appears to the game.

### Keyboard

The browser preserves `KeyboardEvent.code` identities and translates them through the selected keyboard/profile mapping.

Supported physical keyboard schemes currently include:

- **Standard PC**
- **65% Compact**
- **Arrowless / 60%**
- **ESDF + IJKL**
- **WASD + HJKL Camera**

Keyboard movement uses progressive analog ramping for WASD-style movement rather than only instant digital snaps. Keydown/keyup transitions are flushed immediately in addition to the regular transport loop to reduce perceived input latency.

### Touchscreen

Mobile browsers can use a full virtual gamepad directly in the `/play` page.

The controller exposes:

- **LS / L3** — movement and left-stick click
- **RS / R3** — camera and right-stick click
- **A / ✕**
- **B / ○**
- **X / □**
- **Y / △**
- **LB / L1**
- **RB / R1**
- **LT / L2**
- **RT / R2**
- **D-Pad**
- **START / OPTIONS**
- **BACK / SHARE**
- **GUIDE / PS**
- **TOUCHPAD**

Four touchscreen layouts are available and can be changed live:

1. **Classic Landscape**
2. **Twin-Stick Landscape**
3. **PlayStation Landscape**
4. **Compact Thumbs**

Layouts persist locally in the browser, and switching layouts resets active pointers/sticks so a layout change cannot leave stuck input behind.

### Mouse camera

When camera control is enabled, the browser provides a dedicated right-stick camera pad. Pointer-lock support allows mouse movement to drive the virtual **RS** while staying confined to the camera-control surface.

The camera pad includes:

- bounded movement area
- dynamic reticle/stick visualization
- adjustable sensitivity
- safe release back to center
- detached/pop-out camera control support
- direct low-latency dispatch rather than slow multi-frame decay

This makes mouse camera movement usable for games whose Player 2 camera is represented by the controller's right stick.

---

## 🎮 Output backends

| Mode | Backend | Purpose | Status |
|---|---|---|---|
| Xbox 360 | ViGEmBus | Native XInput Player 2 controller | ✅ Working |
| DualShock 4 | ViGEmBus | Native DS4 / DirectInput Player 2 controller | ✅ Working |
| Keyboard 2 | Windows scan-code `SendInput` | Target-locked normal-mode keyboard bridge | ✅ Working |
| Virtual Keyboard Port | UMDF 2 + Windows HID stack | Normal-mode separate HID / Raw Input keyboard | ✅ Implemented and runtime-verified |
| Virtual Keyboard HID (VHF) | KMDF + VHF | Future Microsoft-signed separate HID path | 📦 Preserved / on hold |
| Noop | Diagnostic | Input-pipeline testing without hardware | ✅ Working |

### Controller naming parity

The web UI uses dual Xbox / PlayStation terminology so users can understand either controller family:

- **LT / L2**, **RT / R2**
- **LB / L1**, **RB / R1**
- **A / ✕**, **B / ○**, **X / □**, **Y / △**
- **START / OPTIONS**, **BACK / SHARE**, **GUIDE / PS**
- **LS / L3**, **RS / R3**

The keyboard overlay also shows these controller labels directly on mapped keys, making it obvious what a keyboard key becomes on the virtual controller.

---

## 🛡️ Target attachment and safety

1. Open the host dashboard at `http://localhost:8000/`.
2. Use **Refresh Running Apps** or **Select Foreground** to discover the running game.
3. Select the game and attach it as the target.
4. OmniPad continuously checks target process liveness.
5. If the selected game exits, controller output is immediately neutralized.

For virtual gamepad output, the target only needs to be **running**; the game does not have to remain the foreground application. This allows the host to screen-share, use Discord, OBS, or another window without the remote controller stopping.

Keyboard injection remains stricter and requires the selected target to be the **foreground window**.

OmniPad does not inject DLLs, patch game memory, or modify the target game's executable.

---

## 🌐 Remote play

### LAN

Start `start_router.bat`, then share the generated `/play?code=...` URL with the other player.

### Internet / Cloudflare

Start `start_with_tunnel.bat`, then share the generated:

`https://<temporary-tunnel>.trycloudflare.com/play?code=<ROOM>`

The remote player only needs a modern browser. Their Bluetooth/USB controller can be exposed through the browser Gamepad API, or they can use the built-in keyboard/touch surfaces.

> [!WARNING]
> Cloudflare Quick Tunnels create temporary public URLs without account authentication. Treat the tunnel URL and room code as bearer credentials, share them only with intended players, and stop the tunnel when finished.

### Remote-player security boundary

Cloudflare/player sessions are intentionally limited to the public player surface:

- `/play` and the player WebSocket are remotely accessible.
- Host management, target discovery/selection, tunnel management, background-helper APIs, and slot-management mutations are restricted to local/private-network clients.
- Remote status responses redact local IPs, process IDs, executable paths, window titles, tunnel paths, and room-management details.
- Observer browser tabs are read-only and cannot inject input.
- Attempts to spoof the privileged background-helper source from a remote client are rejected.
- When no room code is supplied, OmniPad generates a fresh cryptographically random room code for the server session.

For the complete security boundary and rationale, see [`SECURITY.md`](SECURITY.md).

---

## 🪟 Local background keyboard helper

A normal browser page cannot continue capturing the host's physical keyboard after another application takes focus. OmniPad therefore includes an optional Windows background helper for local/LAN use.

The helper is located at:

`static/tools/background_keyboard_helper.py`

It forwards only OmniPad-supported gameplay keys and does not suppress the host keyboard or record general typing. The helper can send the same key identities and controller mappings used by the browser keyboard surface.

Example:

`python static/tools/background_keyboard_helper.py --play-url "http://HOST:8000/play?code=YOUR-ROOM"`

For an HTTPS Cloudflare player URL, the helper automatically derives the correct `wss://` WebSocket endpoint.

Hotkeys:

- `Ctrl+Alt+F8` — pause/resume capture
- `Ctrl+C` — stop the helper

> [!NOTE]
> Background-routing controls are intentionally hidden from public Cloudflare player sessions. The native helper is a local/LAN capability.

---

## 🧪 Testing and verification

OmniPad includes a dedicated regression ring covering routing, networking, target safety, touchscreen, keyboard surfaces, background capture, VHF, security boundaries, and live server behavior.

Current verification baseline:

- **19 / 19 test suites passing**
- **0 security-test failures** in the dedicated security suites
- **47 covered source files** within the strict **450-line modularization limit**
- Full historical secret scan reported **0 secret/token/private-key matches** in the audited history

Important suites include:

- `tests/test_security.py`
- `tests/test_security_boundaries.py`
- `tests/test_websocket_security.py`
- `tests/test_targeting.py`
- `tests/test_player_websocket_join.py`
- `tests/test_touch_controller.py`
- `tests/test_touch_controller_layouts.py`
- `tests/test_surface_output_routing.py`
- `tests/test_surface_combinations_e2e.py`
- `tests/test_backend_transitions.py`
- `tests/test_background_keyboard_helper.py`
- `tests/test_server_live.py`
- `tests/test_vhf_keyboard.py`
- `tests/smoke_test.py`

Run `run_tests.bat` for the standard local test sequence.

The UMDF and VHF driver paths additionally require a real Windows WDK environment for native compilation and package testing.

---

## ⌨️ Virtual Keyboard Port / VHF

The primary separate-device implementation is now the normal-mode UMDF 2 package under:

`drivers/virtual-keyboard-umdf/`

It exposes a standard keyboard collection plus a vendor-defined local control collection. OmniPad writes its tested 8-byte keyboard states to the control collection, and Windows exposes the keyboard collection as a distinct HID/Raw Input device. The driver suppresses duplicate state publications and forces all keys up after a 750 ms host-silence timeout.

This path does not require Test Mode, Secure Boot changes, BCD edits, or a custom kernel binary. Windows still requires the package catalog to be signed and trusted before installation; the build performs no certificate-store or driver-state changes. The installed-device smoke verifies the separate Raw Input identity, real make/break events, backend lifecycle, rollover, duplicate suppression, heartbeat/watchdog behavior, rapid transitions ending neutral, and endpoint reopen.

The preserved VHF path remains intended for future Microsoft signing work and for games or software that distinguish keyboard devices through Raw Input/HID:

Source lives under:

`drivers/virtual-keyboard/`

The stack is:

`Remote Keyboard → WebSocket → OmniPad → HID usage translation → KMDF/VHF → Windows HID keyboard`

The driver creates an additional virtual keyboard device; it does **not** capture, inspect, or replace the host's physical keyboard.

The current report format is an 8-byte boot-keyboard report:

`[modifiers, reserved, key0, key1, key2, key3, key4, key5]`

The VHF implementation and its regression/build coverage are intentionally preserved for future Microsoft signing. It is on hold rather than discontinued; normal OmniPad operation does not require changing Windows boot mode. Real game compatibility will still depend on whether the target game supports multiple keyboard devices through Raw Input/HID.

The normal-mode **Keyboard 2** fallback now submits physical scan-code events rather than layout-dependent virtual-key events. It remains Windows-injected input rather than a separately enumerable HID device.

---

## 🧱 Architecture

OmniPad uses a modular pipeline:

`Control Surface → WebSocket / local input → SlotManager → Profile / Key Mapping → Output Backend → Target Game`

The main components are:

- `server.py` — FastAPI/Uvicorn server and lifecycle.
- `router/slot_manager.py` — player slots, state normalization, watchdogs and routing.
- `router/targeting.py` — running-game discovery and target safety predicates.
- `router/security.py` — local/private request gates and public-session containment.
- `router/controller.py` — virtual controller lifecycle.
- `router/backends/` — Xbox 360, DS4, scan-code keyboard, UMDF keyboard port, VHF and diagnostic backends.
- `router/profiles.py` — game/profile mappings.
- `router/tunnel.py` — Cloudflare Quick Tunnel lifecycle.
- `static/js/` — browser controller, layouts, mouse camera, touch controller, monitoring and transport.
- `drivers/virtual-keyboard/` — optional KMDF/VHF keyboard device source.
- `drivers/virtual-keyboard-umdf/` — normal-mode UMDF 2 virtual keyboard port source and build scripts.
- `tests/` — regression and security test ring.

The project enforces a strict source-file size ceiling to keep individual modules reviewable and maintainable. See [`MODULARIZATION.md`](MODULARIZATION.md) and [`MODULARIZATION-MAP.md`](MODULARIZATION-MAP.md).

---

## 🔧 Requirements

Typical Windows host requirements:

- Windows 10/11
- Python 3.x
- Node.js for browser/JavaScript checks
- ViGEmBus for Xbox 360 / DS4 virtual controllers
- Modern browser for remote players
- Optional Visual Studio Build Tools + Windows Driver Kit for UMDF/VHF development
- Optional `cloudflared` for Internet play through Quick Tunnels

See the repository launcher scripts and `requirements.txt` for the current setup path.

---

## 📁 Repository layout

```text
OmniPad-Gamepad-Router/
├── server.py
├── config.py
├── VERSION
├── requirements.txt
├── control.bat
├── start_router.bat
├── start_with_tunnel.bat
├── router/
├── static/
├── profiles/
├── drivers/
├── tests/
├── tools/
├── SECURITY.md
├── LAST-VERIFICATION.md
├── MODULARIZATION.md
└── MODULARIZATION-MAP.md
```

Runtime directories, virtual environments, caches, logs and machine-specific tunnel state are intentionally excluded from version control.

---

## 📌 Current status

**OmniPad Gamepad Router is a working Windows remote-input router with a public-ready, security-hardened player path.**

The main tested path is:

`Remote browser / controller / touchscreen / keyboard → WebSocket → OmniPad Slot 1 → ViGEm Xbox 360 / DS4 → Player 2`

The host keeps their normal Player 1 input independent from the remote Player 2 slot.

For the latest verified security and regression status, see [`LAST-VERIFICATION.md`](LAST-VERIFICATION.md).
