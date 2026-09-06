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
    full_hybrid: {
      label: "Everything",
      parts: PARTS,
      touchLayout: "classic_landscape",
    },
  };

  let active = false;
  let selectedPreset = "keyboard_touch_camera";
  let visibleParts = new Set(PRESETS[selectedPreset].parts);

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
  }

  function selectPreset(name, persist = true) {
    const preset = PRESETS[name] || PRESETS.keyboard_touch_camera;
    window.releaseEveryInputSurface?.();
    selectedPreset = PRESETS[name] ? name : "keyboard_touch_camera";
    visibleParts = new Set(preset.parts);
    const picker = document.getElementById("hybrid-preset-select");
    if (picker) picker.value = selectedPreset;
    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, selectedPreset); } catch (_) {}
    }
    renderVisibility();
    if (active && preset.touchLayout) window.applyTouchLayout?.(preset.touchLayout);
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
  }

  window.OmniPadHybridControls = { PRESETS, PARTS, selectPreset, setActive, togglePart };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
