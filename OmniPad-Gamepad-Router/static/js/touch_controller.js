/* OmniPad full touchscreen controller. */
(function () {
  "use strict";
  const STICK_DEADZONE = 0.04;
  const POINTERS = new Map();
  let installed = false;

  // play.js declares the canonical global lexical `touchState` and exports `window.touchState`.
  function state() { return (typeof window !== "undefined" && window.touchState) ? window.touchState : touchState; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  const TOUCH_LAYOUTS = {
    classic_landscape: {
      shellClass: "touch-layout-classic",
      description: "Balanced layout — sticks, center controls, and action buttons stay close to a traditional full controller."
    },
    twin_stick_landscape: {
      shellClass: "touch-layout-twin-stick",
      description: "Twin-stick gaming layout — LS and RS sit in opposite lower corners so both thumbs can steer and aim simultaneously."
    },
    playstation_landscape: {
      shellClass: "touch-layout-playstation",
      description: "PlayStation-style layout — parallel lower sticks, D-pad on the left, face buttons on the right, menus centered."
    },
    compact_thumbs: {
      shellClass: "touch-layout-compact",
      description: "Compact thumb-friendly layout — controls pulled inward for smaller phones and shorter thumb travel."
    }
  };

  function applyLayout(name) {
    const shell = document.getElementById("touch-controller-shell");
    const picker = document.getElementById("touch-layout-select");
    const description = document.getElementById("touch-layout-description");
    const preset = TOUCH_LAYOUTS[name] || TOUCH_LAYOUTS.classic_landscape;
    if (!shell) return;
    resetAll();
    Object.values(TOUCH_LAYOUTS).forEach(layout => shell.classList.remove(layout.shellClass));
    shell.classList.add(preset.shellClass);
    if (picker && picker.value !== name) picker.value = name;
    if (description) description.textContent = preset.description;

    document.querySelectorAll(".touch-pill-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.preset === name);
    });

    try { localStorage.setItem("omnipad.touchLayout", name); } catch (_) {}
  }

  function installLayoutPicker() {
    const picker = document.getElementById("touch-layout-select");
    if (picker && picker.dataset.bound !== "1") {
      picker.dataset.bound = "1";
      picker.addEventListener("change", e => applyLayout(e.target.value));
    }

    document.querySelectorAll(".touch-pill-btn").forEach(btn => {
      if (btn.dataset.bound !== "1") {
        btn.dataset.bound = "1";
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          if (btn.dataset.preset) applyLayout(btn.dataset.preset);
        });
      }
    });

    let saved = "classic_landscape";
    try { saved = localStorage.getItem("omnipad.touchLayout") || saved; } catch (_) {}
    if (!TOUCH_LAYOUTS[saved]) saved = "classic_landscape";
    applyLayout(saved);
  }

  if (typeof window !== "undefined") {
    window.applyTouchLayout = applyLayout;
    window.resetTouchAll = resetAll;
  }

  function setAxisPair(left, x, y) {
    const s = state();
    const xKey = left ? "lx" : "rx";
    const yKey = left ? "ly" : "ry";
    const mag = Math.hypot(x, y);
    if (mag <= STICK_DEADZONE) { s.axes[xKey] = 0; s.axes[yKey] = 0; return; }
    const norm = clamp((mag - STICK_DEADZONE) / (1 - STICK_DEADZONE), 0, 1);
    s.axes[xKey] = clamp((x / mag) * norm, -1, 1);
    s.axes[yKey] = clamp((y / mag) * norm, -1, 1);
  }

  function setKnob(stick, knob, x, y) {
    const max = Math.min(stick.clientWidth, stick.clientHeight) * 0.32;
    knob.style.transform = `translate(calc(-50% + ${x * max}px), calc(-50% + ${-y * max}px))`;
  }

  function bindStick(id, knobId, left) {
    const stick = document.getElementById(id), knob = document.getElementById(knobId);
    if (!stick || !knob) return;
    function sample(e) {
      const r = stick.getBoundingClientRect();
      const radius = Math.max(1, Math.min(r.width, r.height) * 0.28);
      const x = clamp((e.clientX - (r.left + r.width / 2)) / radius, -1, 1);
      const y = clamp((e.clientY - (r.top + r.height / 2)) / radius, -1, 1);
      setAxisPair(left, x, -y);
      setKnob(stick, knob, x, -y);
      return Math.hypot(x, -y);
    }
    const down = e => {
      e.preventDefault();
      try { stick.setPointerCapture(e.pointerId); } catch (_) {}
      POINTERS.set(e.pointerId, { left });
      stick.classList.add("active");
      sample(e);
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };
    const move = e => {
      if (!POINTERS.has(e.pointerId)) return;
      e.preventDefault();
      sample(e);
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };
    const up = e => {
      const p = POINTERS.get(e.pointerId);
      if (!p) return;
      e.preventDefault();
      state().axes[p.left ? "lx" : "rx"] = 0;
      state().axes[p.left ? "ly" : "ry"] = 0;
      setKnob(stick, knob, 0, 0);
      stick.classList.remove("active");
      POINTERS.delete(e.pointerId);
      try { stick.releasePointerCapture(e.pointerId); } catch (_) {}
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };
    stick.addEventListener("pointerdown", down);
    stick.addEventListener("pointermove", move);
    stick.addEventListener("pointerup", up);
    stick.addEventListener("pointercancel", up);
  }

  function bindButton(id, button) {
    const el = document.getElementById(id); if (!el) return;
    let isDown = false;
    let pressTime = 0;
    let releaseTimer = null;

    const press = e => {
      e.preventDefault();
      if (isDown) return;
      isDown = true;
      pressTime = performance.now();
      if (releaseTimer) { clearTimeout(releaseTimer); releaseTimer = null; }
      try { el.setPointerCapture(e.pointerId); } catch (_) {}
      state().buttons[button] = true;
      el.classList.add("active");
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };

    const doRelease = pointerId => {
      isDown = false;
      state().buttons[button] = false;
      el.classList.remove("active");
      if (pointerId !== undefined) {
        try { el.releasePointerCapture(pointerId); } catch (_) {}
      }
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };

    const release = e => {
      e.preventDefault();
      if (!isDown) return;
      const elapsed = performance.now() - pressTime;
      const minHoldMs = 60; // Guarantee at least ~3-4 frames at 60fps so game engines never miss a tap
      if (elapsed < minHoldMs) {
        releaseTimer = setTimeout(() => doRelease(e.pointerId), minHoldMs - elapsed);
      } else {
        doRelease(e.pointerId);
      }
    };

    el.addEventListener("pointerdown", press);
    el.addEventListener("pointerup", release);
    el.addEventListener("pointercancel", release);
  }

  function bindTrigger(id, axis) {
    const el = document.getElementById(id); if (!el) return;
    const btnName = axis === "lt" ? "LT" : "RT";
    let isDown = false;
    let pressTime = 0;
    let releaseTimer = null;
    let activePointerId = null;

    const press = e => {
      e.preventDefault();
      if (isDown) return;
      isDown = true;
      pressTime = performance.now();
      if (releaseTimer) { clearTimeout(releaseTimer); releaseTimer = null; }
      activePointerId = e.pointerId;
      try { el.setPointerCapture(e.pointerId); } catch (_) {}
      state().axes[axis] = 1.0;
      state().buttons[btnName] = true;
      el.classList.add("active");
      el.style.setProperty("--trigger-fill", "100%");
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };

    const doRelease = pointerId => {
      isDown = false;
      activePointerId = null;
      state().axes[axis] = 0.0;
      state().buttons[btnName] = false;
      el.classList.remove("active");
      el.style.setProperty("--trigger-fill", "0%");
      if (pointerId !== undefined) {
        try { el.releasePointerCapture(pointerId); } catch (_) {}
      }
      if (window.transmitCurrentInputState) window.transmitCurrentInputState();
    };

    const release = e => {
      e.preventDefault();
      if (!isDown) return;
      const elapsed = performance.now() - pressTime;
      const minHoldMs = 60; // Guarantee at least ~3-4 frames at 60fps so game engines never miss a tap
      if (elapsed < minHoldMs) {
        releaseTimer = setTimeout(() => doRelease(e.pointerId), minHoldMs - elapsed);
      } else {
        doRelease(e.pointerId);
      }
    };

    el.addEventListener("pointerdown", press);
    el.addEventListener("pointerup", release);
    el.addEventListener("pointercancel", release);
    el.addEventListener("lostpointercapture", () => {
      if (isDown) doRelease();
    });
  }

  function resetAll() {
    const s = state(); Object.keys(s.buttons).forEach(k => s.buttons[k] = false); Object.keys(s.axes).forEach(k => s.axes[k] = 0); POINTERS.clear();
    document.querySelectorAll("#touch-controller-shell .active, #touch-controller-shell .click-active").forEach(el => el.classList.remove("active", "click-active"));
    document.querySelectorAll("#touch-controller-shell .touch-stick-knob").forEach(el => el.style.transform = "translate(-50%, -50%)");
    document.querySelectorAll("#touch-controller-shell .touch-trigger").forEach(el => el.style.setProperty("--trigger-fill", "0%"));
    if (window.transmitCurrentInputState) window.transmitCurrentInputState();
  }

  function install() {
    if (installed) return; installed = true;
    installLayoutPicker();
    bindStick("touch-left-stick", "touch-left-stick-knob", true);
    bindStick("touch-right-stick", "touch-right-stick-knob", false);
    const buttons = {
      "touch-lb":"LB","touch-rb":"RB","touch-start-2":"START","touch-back-2":"BACK","touch-guide":"GUIDE","touch-touchpad":"TOUCHPAD","touch-l3-button":"L3","touch-r3-button":"R3","touch-a":"A","touch-b":"B","touch-x":"X","touch-y":"Y","touch-dpad-up":"DPAD_UP","touch-dpad-down":"DPAD_DOWN","touch-dpad-left":"DPAD_LEFT","touch-dpad-right":"DPAD_RIGHT"
    };
    Object.entries(buttons).forEach(([id, btn]) => bindButton(id, btn));
    bindTrigger("touch-lt", "lt"); bindTrigger("touch-rt", "rt");
    window.addEventListener("blur", resetAll); window.addEventListener("pagehide", resetAll); document.addEventListener("visibilitychange", () => document.hidden && resetAll());
  }
  if (typeof window !== "undefined") {
    window.isStickActiveLocally = function(left) {
      for (const p of POINTERS.values()) {
        if (p.left === left) return true;
      }
      return false;
    };
    window.isPointerActiveLocally = function() {
      return POINTERS.size > 0;
    };
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true }); else install();
})();
