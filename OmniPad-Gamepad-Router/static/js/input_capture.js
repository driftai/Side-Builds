/**
 * OmniPad — Input State Capture & Multi-Device Aggregator.
 */

function captureState() {
  const buttons = {};
  const axes = { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0 };
  const currentMode = window.currentMode || "keyboard";
  const touchState = window.touchState || { buttons: {}, axes: {} };

  let padActive = false;
  if (currentMode === "gamepad") {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (let i = 0; i < pads.length; i++) {
      const gp = pads[i];
      if (!gp || !gp.connected) continue;
      padActive = true;
      const padName = document.getElementById("detected-pad-name");
      if (padName) padName.textContent = gp.id.slice(0, 32);

      const btnMap = [
        "A", "B", "X", "Y", "LB", "RB", "LT", "RT",
        "BACK", "START", "L3", "R3", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "GUIDE"
      ];
      gp.buttons.forEach((btn, idx) => {
        if (idx < btnMap.length) buttons[btnMap[idx]] = btn.pressed || btn.value > 0.5;
      });

      if (gp.axes.length >= 2) {
        axes.lx = gp.axes[0];
        axes.ly = -gp.axes[1];
      }
      if (gp.axes.length >= 4) {
        axes.rx = gp.axes[2];
        axes.ry = -gp.axes[3];
      }
      break;
    }
  }

  // Touchscreen overlay input aggregation
  if (currentMode === "touch" || Object.values(touchState.buttons || {}).some(Boolean) || (touchState.axes && Object.values(touchState.axes).some(v => Math.abs(v) > 0.01))) {
    for (const [btn, pressed] of Object.entries(touchState.buttons || {})) {
      if (pressed) buttons[btn] = true;
    }
    if (touchState.axes) {
      if (typeof touchState.axes.lx === "number") axes.lx = touchState.axes.lx;
      if (typeof touchState.axes.ly === "number") axes.ly = touchState.axes.ly;
      if (typeof touchState.axes.rx === "number") axes.rx = touchState.axes.rx;
      if (typeof touchState.axes.ry === "number") axes.ry = touchState.axes.ry;
      if (typeof touchState.axes.lt === "number") axes.lt = touchState.axes.lt;
      if (typeof touchState.axes.rt === "number") axes.rt = touchState.axes.rt;
    }
  }

  return { buttons, axes };
}

window.captureState = captureState;
