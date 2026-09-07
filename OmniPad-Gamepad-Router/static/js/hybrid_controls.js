/** OmniPad hybrid keyboard/touch presentation controls. */

(() => {
  "use strict";

  const STORAGE_KEY = "omnipad.hybridPreset";
  const PARTS = ["keyboard", "mouse", "left-stick", "right-stick", "dpad", "actions", "shoulders", "center"];
  const PRESETS = {
    keyboard_touch_camera: {
      label: "Keyboard + Touch Camera",
      parts: ["keyboard", "right-stick", "actions"],
      touchLayout: "camera_actions",
    },
    keyboard_mouse_camera: {
      label: "Keyboard + Mouse Camera",
      parts: ["keyboard", "mouse"],
    },
    keyboard_actions: {
      label: "Keyboard + Action Buttons",
      parts: ["keyboard", "actions", "shoulders", "center"],
      touchLayout: "phone_reach",
    },
    phone_split: {
      label: "Phone Split Controls",
      parts: ["keyboard", "right-stick", "actions", "shoulders"],
      touchLayout: "phone_reach",
    },
    landscape_companion: {
      label: "Landscape WASD + Camera + Actions",
      parts: ["keyboard", "right-stick", "actions", "shoulders"],
      touchLayout: "camera_actions",
      keyboardView: "essential",
    },
    full_hybrid: {
      label: "Everything",
      parts: PARTS,
      touchLayout: "classic_landscape",
      keyboardView: "full-fit",
    },
  };

  let active = false;
  let selectedPreset = "keyboard_touch_camera";
  let visibleParts = new Set(PRESETS[selectedPreset].parts);
  let keyboardView = "standard";

  function notifyShared() {
    window.dispatchEvent(new CustomEvent("omnipad:shared-config-change", { detail: { patch: {
      hybrid_preset: selectedPreset,
      hybrid_parts: Array.from(visibleParts),
      hybrid_keyboard_view: keyboardView,
    } } }));
  }

  function releaseHiddenInputs(part) {
    if (part === "keyboard" || part === "mouse") window.releaseAllKeys?.();
    else window.resetTouchAll?.();
  }

  function renderVisibility() {
    for (const element of document.querySelectorAll("[data-hybrid-part]")) {
      const part = element.dataset.hybridPart;
      element.classList.toggle("hybrid-part-hidden", active && !visibleParts.has(part));
    }
    for (const input of document.querySelectorAll("[data-hybrid-toggle]")) {
      input.checked = visibleParts.has(input.dataset.hybridToggle);
    }
    const description = document.getElementById("hybrid-preset-description");
    if (description) {
      const count = visibleParts.size;
      description.textContent = `${PRESETS[selectedPreset]?.label || "Custom"}: ${count} control group${count === 1 ? "" : "s"} visible.`;
    }
    const arena = document.getElementById("controller-arena");
    if (arena) arena.dataset.hybridKeyboardView = keyboardView;
    document.querySelectorAll("[data-hybrid-keyboard-view]").forEach(input => {
      input.checked = input.dataset.hybridKeyboardView === keyboardView;
    });
  }

  function selectPreset(name, persist = true, broadcast = true) {
    const preset = PRESETS[name] || PRESETS.keyboard_touch_camera;
    window.releaseEveryInputSurface?.();
    selectedPreset = PRESETS[name] ? name : "keyboard_touch_camera";
    visibleParts = new Set(preset.parts);
    keyboardView = preset.keyboardView || "standard";
    const picker = document.getElementById("hybrid-preset-select");
    if (picker) picker.value = selectedPreset;
    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, selectedPreset); } catch (_) {}
    }
    renderVisibility();
    if (active && preset.touchLayout) window.applyTouchLayout?.(preset.touchLayout, { broadcast });
    if (broadcast) notifyShared();
  }

  function togglePart(part, visible) {
    if (!PARTS.includes(part)) return;
    if (!visible) releaseHiddenInputs(part);
    if (visible) visibleParts.add(part); else visibleParts.delete(part);
    selectedPreset = "custom";
    const picker = document.getElementById("hybrid-preset-select");
    if (picker) picker.value = "custom";
    renderVisibility();
    window.transmitCurrentInputState?.();
    notifyShared();
  }

  function setKeyboardView(view, broadcast = true) {
    keyboardView = ["standard", "full-fit", "essential"].includes(view) ? view : "standard";
    selectedPreset = "custom";
    const picker = document.getElementById("hybrid-preset-select");
    if (picker) picker.value = "custom";
    renderVisibility();
    if (broadcast) notifyShared();
  }

  function applyShared(config) {
    if (!config || typeof config !== "object") return;
    if (config.hybrid_preset && PRESETS[config.hybrid_preset]) {
      selectPreset(config.hybrid_preset, false, false);
    }
    if (Array.isArray(config.hybrid_parts)) visibleParts = new Set(config.hybrid_parts.filter(part => PARTS.includes(part)));
    if (config.hybrid_keyboard_view) keyboardView = config.hybrid_keyboard_view;
    renderVisibility();
  }

  function setActive(nextActive) {
    active = Boolean(nextActive);
    renderVisibility();
    const preset = PRESETS[selectedPreset];
    if (active && preset?.touchLayout) window.applyTouchLayout?.(preset.touchLayout);
  }

  function install() {
    let saved = selectedPreset;
    try { saved = localStorage.getItem(STORAGE_KEY) || saved; } catch (_) {}
    selectPreset(PRESETS[saved] ? saved : selectedPreset, false);

    document.getElementById("hybrid-preset-select")?.addEventListener("change", event => {
      if (event.target.value !== "custom") selectPreset(event.target.value);
      event.target.blur();
    });
    document.querySelectorAll("[data-hybrid-toggle]").forEach(input => {
      input.addEventListener("change", () => togglePart(input.dataset.hybridToggle, input.checked));
    });
    document.querySelectorAll("[data-hybrid-keyboard-view]").forEach(input => {
      input.addEventListener("change", () => input.checked && setKeyboardView(input.dataset.hybridKeyboardView));
    });
  }

  window.OmniPadHybridControls = {
    PRESETS, PARTS, selectPreset, setActive, togglePart, setKeyboardView, applyShared,
    getState: () => ({ preset: selectedPreset, parts: Array.from(visibleParts), keyboardView }),
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
