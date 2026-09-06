# OmniPad Gamepad Router — Modularization Map

## Architecture target

OmniPad should converge on focused modules with explicit ownership:

- **server composition** — application creation, dependency wiring, route registration, lifecycle startup.
- **HTTP/API routes** — dashboard/player/REST handlers grouped by surface.
- **WebSocket transport** — join, ownership handoff, malformed-frame handling, broadcast.
- **controller domain** — normalized input state and backend-neutral operations.
- **output adapters** — Xbox 360, DualShock 4, keyboard, VHF/HID.
- **slot lifecycle** — ownership, watchdogs, disconnect cleanup, observer state.
- **targeting** — process discovery and foreground/background routing predicates.
- **tunnel** — Cloudflare process lifecycle and public URL state.
- **touch UI** — layout presets, pointer isolation, state reset.
- **keyboard UI** — layout rendering, labels, interaction wiring.
- **hybrid UI** — composition presets, component visibility, and cross-surface releases.

## Current migration queue

### 1. server.py (COMPLETED - Phase 1)
**Status:** Thin composition root (**302 lines**).
- REST API routes extracted to `router/api_routes.py` (**353 lines**).
- Background keyboard helper lifecycle extracted to `router/background_helper.py` (**183 lines**).
- Routine access-log filtering extracted to `router/access_logging.py` (**40 lines**).
- Benign Windows transport-disconnect filtering extracted to `router/event_loop.py` (**38 lines**).

### 2. router/controller.py (COMPLETED - Phase 1)
**Status:** Controller factory & registry (**151 lines**).
- Focused backend adapters extracted to `router/backends/`:
  - `base.py` (49 lines)
  - `xbox.py` (103 lines)
  - `ds4.py` (127 lines)
  - `keyboard.py` (273 lines)
  - `vhf.py` (40 lines)
  - `noop.py` (31 lines)

### 3. router/slot_manager.py (COMPLETED - Phase 1)
**Status:** Focused slot lifecycle, output gating, and backend routing (**357 lines**).
- `PlayerSlot` data structure extracted to `router/slot.py` (**61 lines**).
- Profile key mapping extracted to `router/key_mapping.py` (**89 lines**).
- Multi-client packet fusion, SOCD application, and input normalization extracted to `router/input_pipeline.py` (**99 lines**).

### 4. Browser UI Modules (COMPLETED - Phase 2)
- **`static/js/play.js` (COMPLETED)**: Reduced from **1140 lines to 375 lines**.
  - Keyboard layout definitions and controller badges extracted to `static/js/keyboard_layouts.js` (**268 lines**).
  - Gamepad profile configurations and keybinding grid extracted to `static/js/gamepad_profiles.js` (**126 lines**).
  - Virtual keyboard state engine and pointer tracking extracted to `static/js/virtual_keyboard.js` (**205 lines**).
  - Target scoping, best-effort selected-game focus, and demand-driven background companion synchronization extracted to `static/js/target_routing.js` (**301 lines**).
  - Input capture aggregation extracted to `static/js/input_capture.js` (**59 lines**).
  - Device/tab switching and cross-surface release ownership extracted to `static/js/device_modes.js` (**61 lines**).
  - Hybrid presets and component visibility extracted to `static/js/hybrid_controls.js` (**108 lines**).
  - Touch-to-keyboard fallback translation extracted to `static/js/touch_keyboard_bridge.js` (**42 lines**).
- **`static/js/dashboard.js` (COMPLETED)**: Reduced from **486 lines to 182 lines**.
  - Target enumeration and safety gating extracted to `static/js/dashboard_targets.js` (**119 lines**).
  - Cloudflare Quick Tunnel management extracted to `static/js/dashboard_tunnel.js` (**115 lines**).
  - Slot cards, visualizer synchronization, and controls extracted to `static/js/dashboard_slots.js` (**271 lines**).

### 5. Player Stylesheets (COMPLETED - Phase 3)
- **`static/css/play.css`**: Player shell, connection, touch-overlay, and routing controls (**303 lines**).
- Keyboard chassis, keycaps, bindings, badges, and responsive rules extracted to `static/css/virtual_keyboard.css` (**276 lines**).
- **`static/css/touch_controller.css`**: Shared touchscreen controller structure and controls (**377 lines**).
- Preset-specific grids and responsive overrides extracted to `static/css/touch_controller_layouts.css` (**228 lines**).
- Hybrid composition and phone breakpoints extracted to `static/css/hybrid_controls.css` (**91 lines**).

### 6. UMDF Virtual Keyboard Driver (COMPLETED - Phase 3)
- **`OmniPadVirtualKeyboardUmdf.c`**: UMDF device creation and driver lifecycle (**79 lines**).
- HID request handling, feature reports, pending reads, and watchdog extracted to `OmniPadVirtualKeyboardHid.c` (**381 lines**).
- HID keyboard/vendor report descriptors extracted to `OmniPadVirtualKeyboardDescriptors.c` (**73 lines**).

### 7. Runtime Control and Smoke Infrastructure (COMPLETED - Phase 3)
- **`tools/manage_router.ps1`**: Control actions and dispatch facade (**293 lines**).
- Runtime state, process validation, local API access, and visible viewer startup extracted to `tools/router_runtime_helpers.ps1` (**119 lines**).
- Live WebSocket/target journeys extracted from `tests/smoke_test.py` to `tests/smoke_runtime_flows.py`.
- `tools/run_smoke_tests.py` captures complete diagnostics while keeping default success output to one stable line.
- The architecture gate now covers all first-party Python/JS/TS/CSS/HTML/native-driver/launcher/test source and validates exception debt.

## Rules for extraction

- Preserve public imports until a migration boundary is complete.
- Add targeted regression coverage before changing ownership behavior.
- Prefer one coherent responsibility per extracted module.
- Do not create circular imports to preserve old structure.
- Remove an entry from `MODULARIZATION-EXCEPTIONS.json` as soon as its file is below 450 lines.

## Success condition

The migration is complete: **ZERO legacy exceptions remain in `MODULARIZATION-EXCEPTIONS.json`**, and all 125 covered first-party source files are at or below the 450-line maximum ceiling. The 26-stage smoke gate includes architecture and 25 focused test suites.
