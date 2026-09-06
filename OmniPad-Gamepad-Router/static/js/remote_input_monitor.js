(() => {
  "use strict";

  let observerWs = null;
  let observerSlot = 1;
  let observerConnected = false;
  let lastKeySet = new Set();

  const style = document.createElement("style");
  style.textContent = `
    .vk-key.remote-pressed {
      outline: 2px solid #22d3ee !important;
      box-shadow: 0 0 14px rgba(34, 211, 238, .75), inset 0 0 8px rgba(34, 211, 238, .18) !important;
      transform: translateY(-1px);
    }
    .vk-controller-label {
      display: block;
      margin-top: 2px;
      font-size: .48rem;
      line-height: 1;
      letter-spacing: -.01em;
      opacity: .88;
      white-space: nowrap;
      pointer-events: none;
    }
    .omnipad-camera-hint {
      margin: 8px 0 0;
      padding: 7px 10px;
      border-radius: 9px;
      border: 1px solid rgba(34, 211, 238, .16);
      background: rgba(15, 23, 42, .28);
      color: var(--text-muted);
      text-align: center;
      font-size: .72rem;
    }
  `;
  document.head.appendChild(style);

  function updateKeyboardControllerLabels() {
    const layout = document.getElementById("vk-layout-select")?.value || "xbox_controller";
    const labels = window.getActiveControllerBadges?.(layout, window.currentKeyboardType || "standard") || {};
    document.querySelectorAll(".vk-key[data-code]").forEach((keyEl) => {
      const code = keyEl.dataset.code;
      const label = labels[code]?.badge;
      keyEl.querySelectorAll(".vk-controller-label").forEach(badge => badge.remove());
      if (!label) {
        keyEl.removeAttribute("data-controller-action");
        keyEl.removeAttribute("title");
        return;
      }
      keyEl.dataset.controllerAction = label;
      keyEl.title = label;
    });

    const keyboardCard = document.querySelector("#section-keyboard .virtual-keyboard-card");
    if (keyboardCard && !document.getElementById("omnipad-controller-camera-hint")) {
      const hint = document.createElement("div");
      hint.id = "omnipad-controller-camera-hint";
      hint.className = "omnipad-camera-hint";
      hint.textContent = "Controller terms: LS/L3 = movement + stick click • RS/R3 = camera + stick click • Mouse/touchpad movement = RS camera";
      keyboardCard.appendChild(hint);
    }
  }

  window.updateKeyboardControllerLabels = updateKeyboardControllerLabels;

  const TOUCH_BUTTON_ELEMENTS = {
    "A": "touch-a",
    "B": "touch-b",
    "X": "touch-x",
    "Y": "touch-y",
    "LB": "touch-lb",
    "RB": "touch-rb",
    "DPAD_UP": "touch-dpad-up",
    "DPAD_DOWN": "touch-dpad-down",
    "DPAD_LEFT": "touch-dpad-left",
    "DPAD_RIGHT": "touch-dpad-right",
    "START": "touch-start-2",
    "BACK": "touch-back-2",
    "GUIDE": "touch-guide",
    "TOUCHPAD": "touch-touchpad",
    "L3": "touch-l3-button",
    "R3": "touch-r3-button"
  };

  function renderRemoteTouchState(buttons, axes) {
    buttons = buttons || {};
    axes = axes || {};

    // 1. Digital & action buttons
    for (const [btnName, elemId] of Object.entries(TOUCH_BUTTON_ELEMENTS)) {
      const el = document.getElementById(elemId);
      if (el) {
        el.classList.toggle("active", !!buttons[btnName]);
      }
    }

    // 2. Analog / digital triggers
    const ltEl = document.getElementById("touch-lt");
    if (ltEl) {
      const ltVal = Number(axes.lt || 0) || (buttons["LT"] ? 1.0 : 0.0);
      ltEl.classList.toggle("active", ltVal > 0.03 || !!buttons["LT"]);
      ltEl.style.setProperty("--trigger-fill", `${Math.round(ltVal * 100)}%`);
    }

    const rtEl = document.getElementById("touch-rt");
    if (rtEl) {
      const rtVal = Number(axes.rt || 0) || (buttons["RT"] ? 1.0 : 0.0);
      rtEl.classList.toggle("active", rtVal > 0.03 || !!buttons["RT"]);
      rtEl.style.setProperty("--trigger-fill", `${Math.round(rtVal * 100)}%`);
    }

    // 3. Left Stick (only update if user is not actively dragging LS locally)
    const leftStick = document.getElementById("touch-left-stick");
    const leftKnob = document.getElementById("touch-left-stick-knob");
    const lsLocalActive = window.isStickActiveLocally && window.isStickActiveLocally(true);
    if (leftStick && leftKnob && !lsLocalActive) {
      const lx = Number(axes.lx || 0);
      const ly = Number(axes.ly || 0);
      const mag = Math.hypot(lx, ly);
      const max = (Math.min(leftStick.clientWidth, leftStick.clientHeight) * 0.27) || 28;
      if (mag > 0.05 || !!buttons["L3"]) {
        leftKnob.style.transform = `translate(calc(-50% + ${lx * max}px), calc(-50% + ${-ly * max}px))`;
        leftStick.classList.add("active");
        leftStick.classList.toggle("click-active", !!buttons["L3"]);
      } else {
        leftKnob.style.transform = "translate(-50%, -50%)";
        leftStick.classList.remove("active", "click-active");
      }
    }

    // 4. Right Stick (only update if user is not actively dragging RS locally)
    const rightStick = document.getElementById("touch-right-stick");
    const rightKnob = document.getElementById("touch-right-stick-knob");
    const rsLocalActive = window.isStickActiveLocally && window.isStickActiveLocally(false);
    if (rightStick && rightKnob && !rsLocalActive) {
      const rx = Number(axes.rx || 0);
      const ry = Number(axes.ry || 0);
      const mag = Math.hypot(rx, ry);
      const max = (Math.min(rightStick.clientWidth, rightStick.clientHeight) * 0.27) || 28;
      if (mag > 0.05 || !!buttons["R3"]) {
        rightKnob.style.transform = `translate(calc(-50% + ${rx * max}px), calc(-50% + ${-ry * max}px))`;
        rightStick.classList.add("active");
        rightStick.classList.toggle("click-active", !!buttons["R3"]);
      } else {
        rightKnob.style.transform = "translate(-50%, -50%)";
        rightStick.classList.remove("active", "click-active");
      }
    }
  }

  function clearRemoteHighlights() {
    for (const code of lastKeySet) {
      document.querySelectorAll(`.vk-key.remote-pressed[data-code="${CSS.escape(code)}"]`).forEach((el) => {
        el.classList.remove("remote-pressed");
      });
    }
    lastKeySet.clear();
    renderRemoteTouchState({}, {});
    if (typeof localVisualizer !== "undefined" && localVisualizer) {
      localVisualizer.update({ buttons: {}, axes: {} });
    }
  }

  function renderRemoteState(state) {
    state = state || {};
    const keyCodes = Array.isArray(state.key_codes) ? state.key_codes.map(String) : [];
    const buttons = state.buttons && typeof state.buttons === "object" ? state.buttons : {};
    const axes = state.axes && typeof state.axes === "object" ? state.axes : {};
    const pressedButtons = Object.entries(buttons).filter(([, value]) => !!value).map(([name]) => name);

    // Diff active keys smoothly without blanket DOM clearing
    const nextKeySet = new Set(keyCodes);
    for (const code of lastKeySet) {
      if (!nextKeySet.has(code)) {
        document.querySelectorAll(`.vk-key.remote-pressed[data-code="${CSS.escape(code)}"]`).forEach((el) => {
          el.classList.remove("remote-pressed");
        });
      }
    }
    for (const code of nextKeySet) {
      if (!lastKeySet.has(code)) {
        document.querySelectorAll(`.vk-key[data-code="${CSS.escape(code)}"]`).forEach((el) => {
          el.classList.add("remote-pressed");
        });
      }
    }
    lastKeySet = nextKeySet;

    // Update Touchscreen Controller mirroring
    renderRemoteTouchState(buttons, axes);

    // Update Gamepad visualizer with correct object structure
    if (typeof localVisualizer !== "undefined" && localVisualizer) {
      localVisualizer.update({ buttons, axes });
    }

    // Update held keys / buttons / sticks list
    const listEl = document.getElementById("vk-active-keys-list");
    if (listEl) {
      const keyPills = keyCodes.map((code) => `<span class="active-key-pill">${code.replace("Key", "").replace("Digit", "")}</span>`).join("");
      const buttonPills = pressedButtons.map((name) => `<span class="active-key-pill">${name}</span>`).join("");
      const axisPills = [];
      const lx = Number(axes.lx || 0), ly = Number(axes.ly || 0), rx = Number(axes.rx || 0), ry = Number(axes.ry || 0);
      const lt = Number(axes.lt || 0), rt = Number(axes.rt || 0);
      if (Math.abs(lx) > 0.05 || Math.abs(ly) > 0.05) axisPills.push(`<span class="active-key-pill">L-Stick (${lx > 0 ? "+" : ""}${lx.toFixed(1)}, ${ly > 0 ? "+" : ""}${ly.toFixed(1)})</span>`);
      if (Math.abs(rx) > 0.05 || Math.abs(ry) > 0.05) axisPills.push(`<span class="active-key-pill">R-Stick (${rx > 0 ? "+" : ""}${rx.toFixed(1)}, ${ry > 0 ? "+" : ""}${ry.toFixed(1)})</span>`);
      if (lt > 0.05) axisPills.push(`<span class="active-key-pill">LT (${lt.toFixed(1)})</span>`);
      if (rt > 0.05) axisPills.push(`<span class="active-key-pill">RT (${rt.toFixed(1)})</span>`);
      listEl.innerHTML = [keyPills, buttonPills, ...axisPills].filter(Boolean).join("") || `<span style="font-size: 0.75rem; color: var(--text-muted);">None (Press any key or click below)</span>`;
    }
  }

  function connectObserver() {
    const params = new URLSearchParams(window.location.search);
    const code = (params.get("code") || "").trim().toUpperCase();
    if (!code) return;
    observerSlot = parseInt(params.get("slot") || "1", 10) || 1;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    observerWs = new WebSocket(`${protocol}//${window.location.host}/ws/player`);
    observerWs.onopen = () => {
      observerWs.send(JSON.stringify({ type: "join", slot_id: observerSlot, name: "UI Monitor", code, source: "observer" }));
    };
    observerWs.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "joined" || msg.type === "join_ack") {
          observerConnected = true;
          if (msg.current_state && (Object.keys(msg.current_state.buttons || {}).length > 0 || (msg.current_state.key_codes && msg.current_state.key_codes.length > 0))) {
            renderRemoteState(msg.current_state);
          } else {
            clearRemoteHighlights();
          }
        } else if (msg.type === "input_state") {
          renderRemoteState(msg.state || {});
        }
      } catch (err) {
        console.debug("Remote input monitor message error", err);
      }
    };
    observerWs.onclose = () => {
      observerConnected = false;
      clearRemoteHighlights();
      setTimeout(connectObserver, 1000);
    };
  }

  window.addEventListener("DOMContentLoaded", () => {
    updateKeyboardControllerLabels();
    const layoutSelect = document.getElementById("vk-layout-select");
    if (layoutSelect) layoutSelect.addEventListener("change", () => updateKeyboardControllerLabels());
    connectObserver();
  });
})();
