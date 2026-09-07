/** Secure state bridge between the player page and its detached camera window. */
(() => {
  "use strict";
  const CHANNEL = "omnipad:mouse-camera-popout";
  let popup = null;

  function send(type, payload = {}) {
    if (popup && !popup.closed) popup.postMessage({ channel: CHANNEL, type, ...payload }, window.location.origin);
  }

  function preferences() {
    const value = window.OmniPadMouseCameraPreferences?.get?.() || {};
    return { sensitivity: value.sensitivity || 20, invertX: Boolean(value.invertX), invertY: Boolean(value.invertY) };
  }

  function render(rx, ry) {
    const safeRx = Math.max(-1, Math.min(1, Number(rx) || 0));
    const safeRy = Math.max(-1, Math.min(1, Number(ry) || 0));
    const left = `${((safeRx + 1) / 2) * 100}%`;
    const top = `${((-safeRy + 1) / 2) * 100}%`;
    for (const id of ["mouse-camera-center", "mouse-camera-puck"]) {
      const element = document.getElementById(id);
      if (element) { element.style.left = left; element.style.top = top; }
    }
    document.getElementById("mouse-camera-pad")?.classList.toggle("active", Math.hypot(safeRx, safeRy) > .02);
  }

  function open() {
    if (popup && !popup.closed) { popup.focus(); return; }
    popup = window.open("/static/mouse_camera_popout.html?v=1.7.0", "OmniPadMouseCamera", "width=720,height=540,menubar=no,toolbar=no,location=no,status=no");
    if (!popup) { alert("Allow popups for OmniPad to use the detached camera."); return; }
    window.mouseCameraPopout = popup;
  }

  window.addEventListener("message", event => {
    const data = event.data;
    if (event.origin !== window.location.origin || event.source !== popup || data?.channel !== CHANNEL) return;
    if (data.type === "ready") {
      send("preferences", preferences());
      const state = window.mouseCameraState || {};
      send("visual", { rx: state.rx || 0, ry: state.ry || 0 });
    } else if (data.type === "state") {
      const state = window.mouseCameraState;
      if (!state) return;
      state.rx = Math.max(-1, Math.min(1, Number(data.rx) || 0));
      state.ry = Math.max(-1, Math.min(1, Number(data.ry) || 0));
      state.active = Boolean(data.active);
      render(state.rx, state.ry);
      window.transmitCurrentInputState?.();
    } else if (data.type === "preferences") {
      const current = window.OmniPadMouseCameraPreferences?.get?.() || {};
      window.setMouseSensitivity?.(data.sensitivity);
      if (Boolean(current.invertX) !== Boolean(data.invertX) || Boolean(current.invertY) !== Boolean(data.invertY)) {
        window.OmniPadMouseCameraPreferences?.setDirections?.(data.invertX, data.invertY);
      }
    } else if (data.type === "key") {
      const action = data.pressed ? window.pressKeySource : window.releaseKeySource;
      action?.("popout_keyboard", data.code);
      window.transmitCurrentInputState?.();
    } else if (data.type === "release_keys") {
      window.releaseKeySource?.("popout_keyboard");
      window.transmitCurrentInputState?.();
    }
  });
  window.addEventListener("omnipad:mouse-camera-visual", event => send("visual", event.detail || {}));
  window.addEventListener("omnipad:mouse-camera-preferences", () => send("preferences", preferences()));
  window.addEventListener("beforeunload", () => { try { popup?.close(); } catch (_) {} });
  window.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("mouse-camera-popout-btn");
    if (button) button.onclick = open;
  });
  window.openMouseCameraPopout = open;
})();
