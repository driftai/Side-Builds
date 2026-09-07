/** Same-slot controller preferences shared across phone/laptop browser peers. */
(() => {
  "use strict";

  let latest = {};
  let publishTimer = null;
  const sourceId = globalThis.crypto?.randomUUID?.() || `browser-${Date.now()}-${Math.random()}`;

  function syncKeyboardEnabled() {
    return document.getElementById("sync-keyboard-type")?.checked !== false;
  }

  function syncHybridEnabled() {
    return document.getElementById("sync-hybrid-layout")?.checked !== false;
  }

  function collect() {
    const mouse = window.OmniPadMouseCameraPreferences?.get?.() || {};
    const hybrid = window.OmniPadHybridControls?.getState?.() || {};
    return {
      mouse_sensitivity: mouse.sensitivity,
      mouse_invert_x: Boolean(mouse.invertX),
      mouse_invert_y: Boolean(mouse.invertY),
      touch_layout: document.getElementById("touch-layout-select")?.value,
      keyboard_type: window.currentKeyboardType,
      hybrid_preset: hybrid.preset,
      hybrid_parts: hybrid.parts,
      hybrid_keyboard_view: hybrid.keyboardView,
    };
  }

  function send(patch) {
    const clean = Object.fromEntries(Object.entries(patch || {}).filter(([, value]) => value !== undefined));
    if (!syncKeyboardEnabled()) delete clean.keyboard_type;
    if (!syncHybridEnabled()) {
      delete clean.hybrid_preset;
      delete clean.hybrid_parts;
      delete clean.hybrid_keyboard_view;
    }
    if (Object.keys(clean).length) window.sendPlayerControlMessage?.({ type: "shared_config", source_id: sourceId, patch: clean });
  }

  function publish(patch) {
    if (publishTimer) clearTimeout(publishTimer);
    publishTimer = setTimeout(() => {
      publishTimer = null;
      send(patch || collect());
    }, 35);
  }

  function apply(config, meta = {}) {
    if (!config || typeof config !== "object") return;
    if (meta.source_id && meta.source_id === sourceId) return;
    latest = { ...latest, ...config };
    if (config.mouse_sensitivity !== undefined) window.setMouseSensitivity?.(config.mouse_sensitivity, { broadcast: false });
    if (config.mouse_invert_x !== undefined || config.mouse_invert_y !== undefined) {
      const current = window.OmniPadMouseCameraPreferences?.get?.() || {};
      window.OmniPadMouseCameraPreferences?.setDirections?.(
        config.mouse_invert_x ?? current.invertX,
        config.mouse_invert_y ?? current.invertY,
        { broadcast: false },
      );
    }
    if (config.touch_layout) window.applyTouchLayout?.(config.touch_layout, { broadcast: false });
    if (config.keyboard_type && syncKeyboardEnabled()) window.setKeyboardType?.(config.keyboard_type, { broadcast: false });
    if (syncHybridEnabled()) window.OmniPadHybridControls?.applyShared?.(config);
  }

  function joined(config) {
    if (config && Object.keys(config).length) apply(config);
    else setTimeout(() => send(collect()), 0);
  }

  function install() {
    for (const id of ["sync-keyboard-type", "sync-hybrid-layout"]) {
      const input = document.getElementById(id);
      if (!input) continue;
      try { input.checked = localStorage.getItem(`omnipad.${id}`) !== "0"; } catch (_) { input.checked = true; }
      input.addEventListener("change", () => {
        try { localStorage.setItem(`omnipad.${id}`, input.checked ? "1" : "0"); } catch (_) {}
        if (input.checked) apply(latest);
      });
    }
    window.addEventListener("omnipad:shared-config-change", event => publish(event.detail?.patch));
  }

  window.OmniPadSharedControllerState = { apply, joined, publish, collect };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
