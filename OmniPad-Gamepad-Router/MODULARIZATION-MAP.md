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

## Current migration queue

### 1. server.py (COMPLETED - Phase 1)
**Status:** Thin composition root (**295 lines**).
- REST API routes extracted to `router/api_routes.py` (**252 lines**).
- Background keyboard helper lifecycle extracted to `router/background_helper.py` (**155 lines**).

### 2. router/controller.py (COMPLETED - Phase 1)
**Status:** Controller factory & registry (**128 lines**).
- Focused backend adapters extracted to `router/backends/`:
  - `base.py` (40 lines)
  - `xbox.py` (85 lines)
  - `ds4.py` (107 lines)
  - `keyboard.py` (219 lines)
  - `vhf.py` (20 lines)
  - `noop.py` (22 lines)

### 3. router/slot_manager.py (COMPLETED - Phase 1)
**Status:** Focused slot lifecycle & input routing (**394 lines**).
- `PlayerSlot` data structure extracted to `router/slot.py` (**56 lines**).
- Profile key mapping and normalization extracted to `router/key_mapping.py` (**80 lines**).

### 4. Browser UI Modules (COMPLETED - Phase 2)
- **`static/js/play.js` (COMPLETED)**: Reduced from **1140 lines to 354 lines**.
  - Keyboard layout definitions and controller badges extracted to `static/js/keyboard_layouts.js` (**261 lines**).
  - Gamepad profile configurations and keybinding grid extracted to `static/js/gamepad_profiles.js` (**113 lines**).
  - Virtual keyboard state engine and pointer tracking extracted to `static/js/virtual_keyboard.js` (**170 lines**).
  - Target scoping and background companion synchronization extracted to `static/js/target_routing.js` (**118 lines**).
  - Input capture aggregation extracted to `static/js/input_capture.js` (**83 lines**).
- **`static/js/dashboard.js` (COMPLETED)**: Reduced from **486 lines to 142 lines**.
  - Target enumeration and safety gating extracted to `static/js/dashboard_targets.js` (**103 lines**).
  - Cloudflare Quick Tunnel management extracted to `static/js/dashboard_tunnel.js` (**102 lines**).
  - Slot cards, visualizer synchronization, and controls extracted to `static/js/dashboard_slots.js` (**237 lines**).

## Rules for extraction

- Preserve public imports until a migration boundary is complete.
- Add targeted regression coverage before changing ownership behavior.
- Prefer one coherent responsibility per extracted module.
- Do not create circular imports to preserve old structure.
- Remove an entry from `MODULARIZATION-EXCEPTIONS.json` as soon as its file is below 450 lines.

## Success condition

The migration is complete: **ZERO legacy exceptions remain in `MODULARIZATION-EXCEPTIONS.json`**, and every covered source file in the repository (both Python and JavaScript) is at or below the 450-line maximum ceiling. All 13 test suites and the architecture checker are 100% green.
