/**
 * OmniPad — Physical Keyboard Types + On-Screen Layout Semantics.
 * Physical keyboard type and clickable layout preset are intentionally separate.
 */

(() => {
  const commonDpad = {
    Digit1: "DPAD_UP", Digit2: "DPAD_DOWN",
    Digit3: "DPAD_LEFT", Digit4: "DPAD_RIGHT"
  };
  const TYPES = {
    standard: {
      label: "Standard PC (WASD + Arrows)",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight" },
      buttons: {
        Space: "A", KeyE: "X", KeyQ: "Y", KeyR: "B",
        KeyZ: "LB", KeyC: "RB", ShiftLeft: "LT", ControlLeft: "RT",
        ShiftRight: "LT", ControlRight: "RT", Escape: "BACK", Enter: "START", F1: "GUIDE",
        CapsLock: "L3", KeyF: "L3", KeyG: "R3", ...commonDpad
      }
    },
    compact65: {
      label: "65% Compact (WASD + Arrows / Fn Layer)",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight" },
      buttons: {
        Space: "A", KeyE: "X", KeyQ: "Y", KeyR: "B",
        KeyZ: "LB", KeyC: "RB", ShiftLeft: "LT", ControlLeft: "RT",
        ShiftRight: "LT", ControlRight: "RT", Escape: "BACK", Enter: "START", Backquote: "GUIDE",
        CapsLock: "L3", KeyF: "L3", KeyG: "R3", ...commonDpad
      }
    },
    arrowless: {
      label: "Arrowless / 60% (WASD + IJKL)",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "KeyI", down: "KeyK", left: "KeyJ", right: "KeyL" },
      buttons: {
        Space: "A", KeyE: "X", KeyQ: "Y", KeyR: "B",
        KeyU: "X", KeyO: "Y", KeyP: "B", Semicolon: "A",
        KeyZ: "LB", KeyC: "RB", ShiftLeft: "LT", ControlLeft: "RT",
        ShiftRight: "LT", BracketLeft: "LB", BracketRight: "RB",
        Escape: "BACK", Enter: "START", Backquote: "GUIDE",
        CapsLock: "L3", KeyF: "L3", KeyH: "R3", ...commonDpad
      }
    },
    esdf: {
      label: "ESDF + IJKL",
      move: { up: "KeyE", down: "KeyD", left: "KeyS", right: "KeyF" },
      camera: { up: "KeyI", down: "KeyK", left: "KeyJ", right: "KeyL" },
      buttons: {
        Space: "A", KeyR: "X", KeyW: "Y", KeyT: "B",
        KeyU: "X", KeyO: "Y", KeyP: "B", Semicolon: "A",
        KeyZ: "LB", KeyX: "RB", ShiftLeft: "LT", ControlLeft: "RT",
        ShiftRight: "LT", Escape: "BACK", Enter: "START", F1: "GUIDE",
        KeyA: "L3", KeyG: "R3", KeyH: "R3", ...commonDpad
      }
    },
    vim_camera: {
      label: "WASD + HJKL Camera",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "KeyK", down: "KeyJ", left: "KeyH", right: "KeyL" },
      buttons: {
        Space: "A", KeyE: "X", KeyQ: "Y", KeyR: "B",
        KeyU: "A", KeyI: "B", KeyO: "Y", KeyP: "X",
        KeyZ: "LB", KeyC: "RB", ShiftLeft: "LT", ControlLeft: "RT",
        ShiftRight: "LT", Escape: "BACK", Enter: "START", F1: "GUIDE",
        CapsLock: "L3", KeyF: "L3", KeyN: "R3", KeyM: "R3", ...commonDpad
      }
    }
  };

  // These two clickable layouts advertise fixed controls. Other layouts use
  // the selected physical keyboard type while remaining backend-independent.
  const FIXED_LAYOUTS = {
    wasd_fighter: {
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight" },
      buttons: {
        KeyJ: "X", KeyK: "Y", KeyL: "RB", KeyU: "A", KeyI: "B", KeyO: "RT",
        Space: "LB", ShiftLeft: "LT", ShiftRight: "LT", ControlLeft: "RT", ControlRight: "RT",
        CapsLock: "L3", Enter: "START", Backspace: "BACK", Escape: "BACK"
      }
    },
    arrow_numpad: {
      move: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight" },
      camera: {},
      buttons: {
        Numpad1: "X", Numpad2: "Y", Numpad3: "RB", Numpad4: "A", Numpad5: "B", Numpad6: "RT",
        Numpad0: "LB", NumpadDecimal: "LT", NumpadEnter: "START", NumpadAdd: "BACK"
      }
    }
  };

  let savedType = "standard";
  try { savedType = localStorage.getItem("omnipad.keyboardType") || savedType; } catch (_) {}
  window.keyboardTypes = TYPES;
  window.keyboardLayoutSemantics = FIXED_LAYOUTS;
  window.currentKeyboardType = TYPES[savedType] ? savedType : "standard";

  function buttonLabels(playstation) {
    const pairs = playstation ? {
      A: "✕ / A", B: "○ / B", X: "□ / X", Y: "△ / Y",
      LB: "L1 / LB", RB: "R1 / RB", LT: "L2 / LT", RT: "R2 / RT",
      BACK: "SHARE", START: "OPTIONS", GUIDE: "PS"
    } : {
      A: "A / ✕", B: "B / ○", X: "X / □", Y: "Y / △",
      LB: "LB / L1", RB: "RB / R1", LT: "LT / L2", RT: "RT / R2",
      BACK: "BACK", START: "START", GUIDE: "GUIDE"
    };
    const labels = {};
    for (const [action, badge] of Object.entries(pairs)) labels[action] = { badge, highlight: "vk-highlight-action" };
    for (const action of ["LB", "RB", "LT", "RT"]) labels[action].highlight = "vk-highlight-modifier";
    for (const action of ["L3", "R3"]) labels[action] = { badge: action, highlight: "vk-highlight-action" };
    for (const [action, badge] of Object.entries({
      DPAD_UP: "D↑", DPAD_DOWN: "D↓", DPAD_LEFT: "D←", DPAD_RIGHT: "D→"
    })) labels[action] = { badge, highlight: "vk-highlight-move" };
    return labels;
  }

  function getActiveControllerBadges(layoutName, keyboardType) {
    const type = TYPES[keyboardType] || TYPES.standard;
    const spec = FIXED_LAYOUTS[layoutName] || type;
    const badgeMap = {};
    const labels = buttonLabels(Boolean(layoutName && layoutName.includes("playstation")));
    for (const [direction, badge] of Object.entries({ up: "LS ↑", down: "LS ↓", left: "LS ←", right: "LS →" })) {
      if (spec.move[direction]) badgeMap[spec.move[direction]] = { badge, highlight: "vk-highlight-move" };
    }
    for (const [direction, badge] of Object.entries({ up: "RS ↑", down: "RS ↓", left: "RS ←", right: "RS →" })) {
      if (spec.camera[direction]) badgeMap[spec.camera[direction]] = { badge, highlight: "vk-highlight-move" };
    }
    for (const [code, action] of Object.entries(spec.buttons || {})) {
      if (!badgeMap[code] && labels[action]) badgeMap[code] = labels[action];
    }
    return badgeMap;
  }

  let smoothLx = 0, smoothLy = 0, smoothRx = 0, smoothRy = 0;
  function resetKeyboardAnalogState() {
    smoothLx = smoothLy = smoothRx = smoothRy = 0;
  }

  function setKeyboardType(type) {
    if (!TYPES[type]) type = "standard";
    if (type !== window.currentKeyboardType) window.releaseAllKeys?.();
    resetKeyboardAnalogState();
    window.currentKeyboardType = type;
    try { localStorage.setItem("omnipad.keyboardType", type); } catch (_) {}
    const hint = document.getElementById("keyboard-type-hint");
    if (hint) hint.textContent = TYPES[type].label;
    window.renderVirtualKeyboard?.(window.currentKeyboardLayout || "xbox_controller");
    window.transmitCurrentInputState?.();
  }

  function sourceKeySets() {
    const pointer = new Set();
    const physical = new Set();
    const holds = window.srcHolds;
    if (holds?.size) {
      for (const [source, codes] of holds.entries()) {
        const destination = String(source).startsWith("pointer_") ? pointer : physical;
        for (const code of codes) destination.add(code);
      }
    } else {
      for (const code of (window.activeKeys || [])) physical.add(code);
    }
    return { pointer, physical };
  }

  function resolve(keys, spec) {
    const move = spec.move || {}, camera = spec.camera || {}, buttons = spec.buttons || {};
    const resolved = {
      moveUp: Boolean(move.up && keys.has(move.up)), moveDown: Boolean(move.down && keys.has(move.down)),
      moveLeft: Boolean(move.left && keys.has(move.left)), moveRight: Boolean(move.right && keys.has(move.right)),
      camUp: Boolean(camera.up && keys.has(camera.up)), camDown: Boolean(camera.down && keys.has(camera.down)),
      camLeft: Boolean(camera.left && keys.has(camera.left)), camRight: Boolean(camera.right && keys.has(camera.right)),
      buttons: {}
    };
    for (const code of keys) {
      const action = buttons[code];
      if (action) resolved.buttons[action] = true;
    }
    return resolved;
  }

  function approach(current, target) {
    if (target !== 0) {
      const next = current + (target - current) * 0.35;
      return Math.abs(target - next) < 0.03 ? target : next;
    }
    const next = current * 0.65;
    return Math.abs(next) < 0.02 ? 0 : next;
  }

  const originalCaptureState = window.captureState;
  window.captureState = function captureStateWithKeyboardType() {
    const state = originalCaptureState ? originalCaptureState() : {
      buttons: {}, axes: { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0 }
    };
    if ((window.currentMode || "keyboard") !== "keyboard") return state;

    const type = TYPES[window.currentKeyboardType] || TYPES.standard;
    const { pointer, physical } = sourceKeySets();
    const physicalResolved = resolve(physical, type);
    const pointerResolved = resolve(pointer, FIXED_LAYOUTS[window.currentKeyboardLayout] || type);
    const combined = {};
    for (const key of ["moveUp", "moveDown", "moveLeft", "moveRight", "camUp", "camDown", "camLeft", "camRight"]) {
      combined[key] = physicalResolved[key] || pointerResolved[key];
    }

    const targetLx = combined.moveRight !== combined.moveLeft ? (combined.moveRight ? 1 : -1) : 0;
    const targetLy = combined.moveUp !== combined.moveDown ? (combined.moveUp ? 1 : -1) : 0;
    const targetRx = combined.camRight !== combined.camLeft ? (combined.camRight ? 1 : -1) : 0;
    const targetRy = combined.camUp !== combined.camDown ? (combined.camUp ? 1 : -1) : 0;
    smoothLx = approach(smoothLx, targetLx);
    smoothLy = approach(smoothLy, targetLy);
    smoothRx = approach(smoothRx, targetRx);
    smoothRy = approach(smoothRy, targetRy);
    state.axes.lx = Number(smoothLx.toFixed(4));
    state.axes.ly = Number(smoothLy.toFixed(4));
    state.axes.rx = Number(smoothRx.toFixed(4));
    state.axes.ry = Number(smoothRy.toFixed(4));

    Object.assign(state.buttons, physicalResolved.buttons, pointerResolved.buttons);
    if (state.buttons.LT) state.axes.lt = 1;
    if (state.buttons.RT) state.axes.rt = 1;
    const mouse = window.mouseCameraState;
    if (mouse?.active) {
      state.axes.rx = mouse.rx;
      state.axes.ry = mouse.ry;
    }
    return state;
  };

  document.addEventListener("DOMContentLoaded", () => {
    const select = document.getElementById("keyboard-type-select");
    if (!select) return;
    select.value = window.currentKeyboardType;
    setKeyboardType(select.value);
    select.addEventListener("change", event => setKeyboardType(event.target.value));
  });

  window.getActiveControllerBadges = getActiveControllerBadges;
  window.setKeyboardType = setKeyboardType;
  window.resetKeyboardAnalogState = resetKeyboardAnalogState;
  window.OmniPadKeyboardSemantics = { TYPES, FIXED_LAYOUTS, resolve };
})();
