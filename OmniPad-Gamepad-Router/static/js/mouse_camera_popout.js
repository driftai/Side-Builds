/** Detached camera UI; the opener remains the canonical input/transport owner. */
(() => {
  "use strict";
  const CHANNEL = "omnipad:mouse-camera-popout";
  const openerOrigin = window.location.origin;
  const pad = document.getElementById("camera-pad");
  const puck = document.getElementById("camera-puck");
  const label = document.getElementById("camera-label");
  const sensitivity = document.getElementById("sensitivity");
  const sensitivityValue = document.getElementById("sensitivity-value");
  const invertXInput = document.getElementById("invert-x");
  const invertYInput = document.getElementById("invert-y");
  let rx = 0, ry = 0, targetRx = 0, targetRy = 0;
  let invertX = false, invertY = false, pointerId = null, frame = 0, stateFrame = 0;

  function send(type, payload = {}) {
    window.opener?.postMessage({ channel: CHANNEL, type, ...payload }, openerOrigin);
  }

  function render() {
    puck.style.left = `${((rx + 1) / 2) * 100}%`;
    puck.style.top = `${((-ry + 1) / 2) * 100}%`;
    pad.classList.toggle("active", Math.hypot(rx, ry) > .02);
  }

  function emitState(force = false) {
    render();
    if (force) {
      if (stateFrame) cancelAnimationFrame(stateFrame);
      stateFrame = 0;
      send("state", { rx, ry, active: Math.hypot(rx, ry) > .01, force: true });
    } else if (!stateFrame) {
      stateFrame = requestAnimationFrame(() => {
        stateFrame = 0;
        send("state", { rx, ry, active: Math.hypot(rx, ry) > .01, force: false });
      });
    }
  }

  function neutral(force = true) {
    rx = ry = targetRx = targetRy = 0;
    pointerId = null;
    emitState(force);
  }

  function samplePointer(event) {
    const rect = pad.getBoundingClientRect();
    const radius = Math.max(1, Math.min(rect.width, rect.height) / 2);
    let x = (event.clientX - rect.left - rect.width / 2) / radius;
    let y = (event.clientY - rect.top - rect.height / 2) / radius;
    const magnitude = Math.hypot(x, y);
    if (magnitude > 1) { x /= magnitude; y /= magnitude; }
    const scale = Math.min(4, Number(sensitivity.value) / 50);
    rx = Math.max(-1, Math.min(1, x * scale * (invertX ? -1 : 1)));
    ry = Math.max(-1, Math.min(1, y * scale * (invertY ? 1 : -1)));
    targetRx = rx; targetRy = ry;
    emitState();
  }

  pad.addEventListener("pointerdown", event => {
    event.preventDefault();
    if (event.pointerType === "mouse" && pad.requestPointerLock) pad.requestPointerLock();
    else {
      pointerId = event.pointerId;
      try { pad.setPointerCapture(pointerId); } catch (_) {}
      samplePointer(event);
    }
  });
  pad.addEventListener("pointermove", event => {
    if (pointerId !== event.pointerId) return;
    event.preventDefault();
    samplePointer(event);
  });
  for (const eventName of ["pointerup", "pointercancel"]) pad.addEventListener(eventName, event => {
    if (pointerId === event.pointerId) neutral();
  });

  document.addEventListener("pointerlockchange", () => {
    const locked = document.pointerLockElement === pad;
    label.textContent = locked ? "Camera locked • move mouse • Esc releases" : "Click to lock mouse • drag on touch";
    neutral();
  });
  document.addEventListener("mousemove", event => {
    if (document.pointerLockElement !== pad) return;
    const scale = (event.buttons ? .0025 : .004) * (Number(sensitivity.value) / 100);
    targetRx = Math.max(-1, Math.min(1, targetRx + (event.movementX || 0) * scale * (invertX ? -1 : 1)));
    targetRy = Math.max(-1, Math.min(1, targetRy + (event.movementY || 0) * scale * (invertY ? 1 : -1)));
    rx = targetRx; ry = targetRy;
    emitState();
  });

  function decay() {
    if (document.pointerLockElement === pad) {
      const beforeRx = targetRx, beforeRy = targetRy;
      targetRx *= .68; targetRy *= .68;
      if (Math.abs(targetRx) < .003) targetRx = 0;
      if (Math.abs(targetRy) < .003) targetRy = 0;
      rx = targetRx; ry = targetRy;
      if (beforeRx !== targetRx || beforeRy !== targetRy) emitState();
    }
    frame = requestAnimationFrame(decay);
  }

  sensitivity.addEventListener("input", () => {
    sensitivityValue.textContent = `${sensitivity.value}%`;
    send("preferences", { sensitivity: Number(sensitivity.value), invertX, invertY });
  });
  invertXInput.addEventListener("change", () => { invertX = invertXInput.checked; neutral(); send("preferences", { sensitivity: Number(sensitivity.value), invertX, invertY }); });
  invertYInput.addEventListener("change", () => { invertY = invertYInput.checked; neutral(); send("preferences", { sensitivity: Number(sensitivity.value), invertX, invertY }); });
  window.addEventListener("keydown", event => send("key", { code: event.code, pressed: true }), true);
  window.addEventListener("keyup", event => send("key", { code: event.code, pressed: false }), true);
  window.addEventListener("message", event => {
    if (event.origin !== openerOrigin || event.source !== window.opener || event.data?.channel !== CHANNEL) return;
    if (event.data.type === "preferences") {
      sensitivity.value = event.data.sensitivity;
      sensitivityValue.textContent = `${event.data.sensitivity}%`;
      invertX = Boolean(event.data.invertX); invertY = Boolean(event.data.invertY);
      invertXInput.checked = invertX; invertYInput.checked = invertY;
    } else if (event.data.type === "visual" && document.pointerLockElement !== pad && pointerId === null) {
      rx = Number(event.data.rx) || 0; ry = Number(event.data.ry) || 0; render();
    }
  });
  window.addEventListener("beforeunload", () => { cancelAnimationFrame(frame); if (stateFrame) cancelAnimationFrame(stateFrame); neutral(); send("release_keys"); });
  if (!window.opener) document.getElementById("connection").textContent = "Player window unavailable";
  else { document.getElementById("connection").textContent = "Linked to player window"; send("ready"); }
  frame = requestAnimationFrame(decay);
})();
