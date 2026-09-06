/** OmniPad control-surface switching and cross-surface release safety. */

(() => {
  "use strict";

  const VALID_MODES = new Set(["keyboard", "gamepad", "touch", "hybrid"]);

  function releaseEverySurface() {
    window.releaseAllKeys?.();
    window.resetTouchAll?.();
    window.resetMouseCameraState?.(false);
  }

  function showSection(id, visible) {
    const section = document.getElementById(id);
    if (section) section.style.display = visible ? "flex" : "none";
  }

  function restoreTouchLayout() {
    if (typeof window.applyTouchLayout !== "function") return;
    let saved = "classic_landscape";
    try { saved = localStorage.getItem("omnipad.touchLayout") || saved; } catch (_) {}
    window.applyTouchLayout(saved);
  }

  function switchDeviceMode(requestedMode) {
    const mode = VALID_MODES.has(requestedMode) ? requestedMode : "keyboard";
    releaseEverySurface();
    window.setCurrentInputMode?.(mode);
    window.currentMode = mode;

    const hybrid = mode === "hybrid";
    showSection("section-hybrid", hybrid);
    showSection("section-keyboard", mode === "keyboard" || hybrid);
    showSection("section-gamepad", mode === "gamepad");
    showSection("section-touch", mode === "touch" || hybrid);

    const arena = document.getElementById("controller-arena");
    arena?.classList.toggle("hybrid-active", hybrid);
    document.querySelectorAll(".mode-tab").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.mode === mode);
    });

    const badge = document.getElementById("detected-pad-name");
    if (badge) {
      badge.textContent = {
        keyboard: "Keyboard Active",
        gamepad: "Gamepad Mode",
        touch: "Touchscreen Mode",
        hybrid: "Keyboard + Touch",
      }[mode];
    }

    if (mode === "touch" || hybrid) restoreTouchLayout();
    window.OmniPadHybridControls?.setActive(hybrid);
    window.transmitCurrentInputState?.();
  }

  window.switchDeviceMode = switchDeviceMode;
  window.releaseEveryInputSurface = releaseEverySurface;
})();
