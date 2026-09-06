/** Translate touch-controller state into the canonical keyboard fallback. */

(() => {
  "use strict";

  const BUTTON_CODES = Object.freeze({
    DPAD_UP: "KeyW", DPAD_DOWN: "KeyS", DPAD_LEFT: "KeyA", DPAD_RIGHT: "KeyD",
    A: "KeyJ", B: "KeyK", X: "KeyU", Y: "KeyI",
    LB: "KeyQ", RB: "KeyE", LT: "KeyZ", RT: "KeyC",
    START: "Enter", BACK: "Backspace", SELECT: "Backspace",
    GUIDE: "F1", TOUCHPAD: "Tab", L3: "CapsLock", R3: "KeyG",
  });
  const STICK_THRESHOLD = 0.32;

  function addStickCodes(codes, x, y, negativeX, positiveX, positiveY, negativeY) {
    if (x <= -STICK_THRESHOLD) codes.add(negativeX);
    if (x >= STICK_THRESHOLD) codes.add(positiveX);
    if (y >= STICK_THRESHOLD) codes.add(positiveY);
    if (y <= -STICK_THRESHOLD) codes.add(negativeY);
  }

  function captureTouchKeyboardFallbackCodes() {
    const mode = window.currentMode || "keyboard";
    if (mode !== "touch" && mode !== "hybrid") return [];

    const state = window.touchState || { buttons: {}, axes: {} };
    const codes = new Set();
    for (const [button, pressed] of Object.entries(state.buttons || {})) {
      if (pressed && BUTTON_CODES[button]) codes.add(BUTTON_CODES[button]);
    }

    const axes = state.axes || {};
    addStickCodes(codes, Number(axes.lx) || 0, Number(axes.ly) || 0,
      "KeyA", "KeyD", "KeyW", "KeyS");
    addStickCodes(codes, Number(axes.rx) || 0, Number(axes.ry) || 0,
      "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown");
    return Array.from(codes);
  }

  window.captureTouchKeyboardFallbackCodes = captureTouchKeyboardFallbackCodes;
  window.OmniPadTouchKeyboardBridge = { BUTTON_CODES, STICK_THRESHOLD };
})();
