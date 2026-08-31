/**
 * OmniPad — Alternate Physical Keyboard Profiles & Dynamic Badge Adapter.
 * Remaps both analog sticks and action buttons according to physical keyboard type.
 */

(() => {
  const TYPES = {
    standard: {
      label: "Standard PC (WASD + Arrows)",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight" },
      buttons: {
        "Space": "A", "KeyE": "X", "KeyQ": "Y", "KeyR": "B",
        "KeyZ": "LB", "KeyC": "RB", "ShiftLeft": "LT", "ControlLeft": "RT",
        "ShiftRight": "LT", "ControlRight": "RT",
        "Escape": "BACK", "Enter": "START", "F1": "GUIDE",
        "CapsLock": "L3", "KeyF": "L3", "KeyG": "R3",
        "Digit1": "DPAD_UP", "Digit2": "DPAD_DOWN", "Digit3": "DPAD_LEFT", "Digit4": "DPAD_RIGHT"
      }
    },
    compact65: {
      label: "65% Compact (WASD + Arrows / Fn Layer)",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight" },
      buttons: {
        "Space": "A", "KeyE": "X", "KeyQ": "Y", "KeyR": "B",
        "KeyZ": "LB", "KeyC": "RB", "ShiftLeft": "LT", "ControlLeft": "RT",
        "ShiftRight": "LT", "ControlRight": "RT",
        "Escape": "BACK", "Enter": "START", "Backquote": "GUIDE",
        "CapsLock": "L3", "KeyF": "L3", "KeyG": "R3",
        "Digit1": "DPAD_UP", "Digit2": "DPAD_DOWN", "Digit3": "DPAD_LEFT", "Digit4": "DPAD_RIGHT"
      }
    },
    arrowless: {
      label: "Arrowless / 60% (WASD + IJKL)",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "KeyI", down: "KeyK", left: "KeyJ", right: "KeyL" },
      buttons: {
        "Space": "A", "KeyE": "X", "KeyQ": "Y", "KeyR": "B",
        "KeyU": "X", "KeyO": "Y", "KeyP": "B", "Semicolon": "A",
        "KeyZ": "LB", "KeyC": "RB", "ShiftLeft": "LT", "ControlLeft": "RT",
        "ShiftRight": "LT", "BracketLeft": "LB", "BracketRight": "RB",
        "Escape": "BACK", "Enter": "START", "Backquote": "GUIDE",
        "CapsLock": "L3", "KeyF": "L3", "KeyH": "R3",
        "Digit1": "DPAD_UP", "Digit2": "DPAD_DOWN", "Digit3": "DPAD_LEFT", "Digit4": "DPAD_RIGHT"
      }
    },
    esdf: {
      label: "ESDF + IJKL",
      move: { up: "KeyE", down: "KeyD", left: "KeyS", right: "KeyF" },
      camera: { up: "KeyI", down: "KeyK", left: "KeyJ", right: "KeyL" },
      buttons: {
        "Space": "A", "KeyR": "X", "KeyW": "Y", "KeyT": "B",
        "KeyU": "X", "KeyO": "Y", "KeyP": "B", "Semicolon": "A",
        "KeyZ": "LB", "KeyX": "RB", "ShiftLeft": "LT", "ControlLeft": "RT",
        "ShiftRight": "LT", "Escape": "BACK", "Enter": "START", "F1": "GUIDE",
        "KeyA": "L3", "KeyG": "R3", "KeyH": "R3",
        "Digit1": "DPAD_UP", "Digit2": "DPAD_DOWN", "Digit3": "DPAD_LEFT", "Digit4": "DPAD_RIGHT"
      }
    },
    vim_camera: {
      label: "WASD + HJKL Camera",
      move: { up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD" },
      camera: { up: "KeyK", down: "KeyJ", left: "KeyH", right: "KeyL" },
      buttons: {
        "Space": "A", "KeyE": "X", "KeyQ": "Y", "KeyR": "B",
        "KeyU": "A", "KeyI": "B", "KeyO": "Y", "KeyP": "X",
        "KeyZ": "LB", "KeyC": "RB", "ShiftLeft": "LT", "ControlLeft": "RT",
        "ShiftRight": "LT", "Escape": "BACK", "Enter": "START", "F1": "GUIDE",
        "CapsLock": "L3", "KeyF": "L3", "KeyN": "R3", "KeyM": "R3",
        "Digit1": "DPAD_UP", "Digit2": "DPAD_DOWN", "Digit3": "DPAD_LEFT", "Digit4": "DPAD_RIGHT"
      }
    }
  };

  window.keyboardTypes = TYPES;
  window.currentKeyboardType = localStorage.getItem("omnipad.keyboardType") || "standard";

  function getActiveControllerBadges(layoutName, keyboardType) {
    const isPS = layoutName && layoutName.includes("playstation");
    const type = TYPES[keyboardType] || TYPES.standard;
    const badgeMap = {};

    // 1. Move stick badges
    badgeMap[type.move.up] = { badge: "LS ↑", highlight: "vk-highlight-move" };
    badgeMap[type.move.down] = { badge: "LS ↓", highlight: "vk-highlight-move" };
    badgeMap[type.move.left] = { badge: "LS ←", highlight: "vk-highlight-move" };
    badgeMap[type.move.right] = { badge: "LS →", highlight: "vk-highlight-move" };

    // 2. Camera stick badges
    badgeMap[type.camera.up] = { badge: "RS ↑", highlight: "vk-highlight-move" };
    badgeMap[type.camera.down] = { badge: "RS ↓", highlight: "vk-highlight-move" };
    badgeMap[type.camera.left] = { badge: "RS ←", highlight: "vk-highlight-move" };
    badgeMap[type.camera.right] = { badge: "RS →", highlight: "vk-highlight-move" };

    // 3. Action button labels
    const btnLabels = isPS ? {
      "A": { badge: "✕ / A", highlight: "vk-highlight-action" },
      "B": { badge: "○ / B", highlight: "vk-highlight-action" },
      "X": { badge: "□ / X", highlight: "vk-highlight-action" },
      "Y": { badge: "△ / Y", highlight: "vk-highlight-action" },
      "LB": { badge: "L1 / LB", highlight: "vk-highlight-modifier" },
      "RB": { badge: "R1 / RB", highlight: "vk-highlight-modifier" },
      "LT": { badge: "L2 / LT", highlight: "vk-highlight-modifier" },
      "RT": { badge: "R2 / RT", highlight: "vk-highlight-modifier" },
      "BACK": { badge: "SHARE", highlight: "vk-highlight-action" },
      "START": { badge: "OPTIONS", highlight: "vk-highlight-action" },
      "GUIDE": { badge: "PS", highlight: "vk-highlight-action" },
      "L3": { badge: "L3", highlight: "vk-highlight-action" },
      "R3": { badge: "R3", highlight: "vk-highlight-action" },
      "DPAD_UP": { badge: "D↑", highlight: "vk-highlight-move" },
      "DPAD_DOWN": { badge: "D↓", highlight: "vk-highlight-move" },
      "DPAD_LEFT": { badge: "D←", highlight: "vk-highlight-move" },
      "DPAD_RIGHT": { badge: "D→", highlight: "vk-highlight-move" }
    } : {
      "A": { badge: "A / ✕", highlight: "vk-highlight-action" },
      "B": { badge: "B / ○", highlight: "vk-highlight-action" },
      "X": { badge: "X / □", highlight: "vk-highlight-action" },
      "Y": { badge: "Y / △", highlight: "vk-highlight-action" },
      "LB": { badge: "LB / L1", highlight: "vk-highlight-modifier" },
      "RB": { badge: "RB / R1", highlight: "vk-highlight-modifier" },
      "LT": { badge: "LT / L2", highlight: "vk-highlight-modifier" },
      "RT": { badge: "RT / R2", highlight: "vk-highlight-modifier" },
      "BACK": { badge: "BACK", highlight: "vk-highlight-action" },
      "START": { badge: "START", highlight: "vk-highlight-action" },
      "GUIDE": { badge: "GUIDE", highlight: "vk-highlight-action" },
      "L3": { badge: "L3", highlight: "vk-highlight-action" },
      "R3": { badge: "R3", highlight: "vk-highlight-action" },
      "DPAD_UP": { badge: "D↑", highlight: "vk-highlight-move" },
      "DPAD_DOWN": { badge: "D↓", highlight: "vk-highlight-move" },
      "DPAD_LEFT": { badge: "D←", highlight: "vk-highlight-move" },
      "DPAD_RIGHT": { badge: "D→", highlight: "vk-highlight-move" }
    };

    for (const [code, btn] of Object.entries(type.buttons || {})) {
      // Don't overwrite LS or RS badges if keys share code
      if (!badgeMap[code] && btnLabels[btn]) {
        badgeMap[code] = btnLabels[btn];
      }
    }

    return badgeMap;
  }
  window.getActiveControllerBadges = getActiveControllerBadges;

  function setKeyboardType(type) {
    if (!TYPES[type]) type = "standard";
    window.currentKeyboardType = type;
    try { localStorage.setItem("omnipad.keyboardType", type); } catch (_) {}
    const hint = document.getElementById("keyboard-type-hint");
    if (hint) hint.textContent = TYPES[type].label;

    if (typeof window.renderVirtualKeyboard === "function") {
      window.renderVirtualKeyboard(window.currentKeyboardLayout || "xbox_controller");
    }
    if (typeof window.transmitCurrentInputState === "function") {
      window.transmitCurrentInputState();
    }
  }

  let smoothLx = 0;
  let smoothLy = 0;
  let smoothRx = 0;
  let smoothRy = 0;

  const originalCaptureState = window.captureState;
  window.captureState = function captureStateWithKeyboardType() {
    const state = originalCaptureState ? originalCaptureState() : { buttons: {}, axes: { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0 } };
    if ((window.currentMode || "keyboard") !== "keyboard") return state;

    const type = TYPES[window.currentKeyboardType] || TYPES.standard;
    const keys = window.activeKeys || new Set();
    const { move, camera, buttons } = type;

    // Movement axes (Left Stick SOCD Neutral with progressive analog ramping)
    const moveUp = keys.has(move.up), moveDown = keys.has(move.down);
    const moveLeft = keys.has(move.left), moveRight = keys.has(move.right);
    const targetLy = moveUp && !moveDown ? 1.0 : (moveDown && !moveUp ? -1.0 : 0.0);
    const targetLx = moveRight && !moveLeft ? 1.0 : (moveLeft && !moveRight ? -1.0 : 0.0);

    if (targetLx !== 0) {
      smoothLx += (targetLx - smoothLx) * 0.35;
      if (Math.abs(targetLx - smoothLx) < 0.03) smoothLx = targetLx;
    } else {
      smoothLx *= 0.65;
      if (Math.abs(smoothLx) < 0.02) smoothLx = 0;
    }

    if (targetLy !== 0) {
      smoothLy += (targetLy - smoothLy) * 0.35;
      if (Math.abs(targetLy - smoothLy) < 0.03) smoothLy = targetLy;
    } else {
      smoothLy *= 0.65;
      if (Math.abs(smoothLy) < 0.02) smoothLy = 0;
    }

    state.axes.lx = parseFloat(smoothLx.toFixed(4));
    state.axes.ly = parseFloat(smoothLy.toFixed(4));

    // Camera axes (Right Stick SOCD Neutral with progressive analog ramping)
    const camUp = keys.has(camera.up), camDown = keys.has(camera.down);
    const camLeft = keys.has(camera.left), camRight = keys.has(camera.right);
    const targetRy = camUp && !camDown ? 1.0 : (camDown && !camUp ? -1.0 : 0.0);
    const targetRx = camRight && !camLeft ? 1.0 : (camLeft && !camRight ? -1.0 : 0.0);

    if (targetRx !== 0) {
      smoothRx += (targetRx - smoothRx) * 0.35;
      if (Math.abs(targetRx - smoothRx) < 0.03) smoothRx = targetRx;
    } else {
      smoothRx *= 0.65;
      if (Math.abs(smoothRx) < 0.02) smoothRx = 0;
    }

    if (targetRy !== 0) {
      smoothRy += (targetRy - smoothRy) * 0.35;
      if (Math.abs(targetRy - smoothRy) < 0.03) smoothRy = targetRy;
    } else {
      smoothRy *= 0.65;
      if (Math.abs(smoothRy) < 0.02) smoothRy = 0;
    }

    state.axes.rx = parseFloat(smoothRx.toFixed(4));
    state.axes.ry = parseFloat(smoothRy.toFixed(4));

    // Buttons mapping for current keyboard type
    for (const code of keys) {
      const btn = buttons[code];
      if (btn) {
        state.buttons[btn] = true;
        if (btn === "LT") state.axes.lt = 1;
        if (btn === "RT") state.axes.rt = 1;
      }
    }

    // Mouse camera pad override if active
    const mouse = window.mouseCameraState;
    if (mouse && mouse.active) {
      state.axes.rx = mouse.rx;
      state.axes.ry = mouse.ry;
    }
    return state;
  };

  document.addEventListener("DOMContentLoaded", () => {
    const select = document.getElementById("keyboard-type-select");
    if (select) {
      select.value = window.currentKeyboardType;
      setKeyboardType(select.value);
      select.addEventListener("change", event => {
        setKeyboardType(event.target.value);
      });
    }
  });

  window.setKeyboardType = setKeyboardType;
})();
