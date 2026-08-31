/**
 * OmniPad — Interactive Virtual Keyboard Engine & Key State Management.
 */

let currentKeyboardLayout = "xbox_controller";

const activeKeys = new Set();
const srcHolds = new Map();     // sourceId -> Set<keyCode>
const codeCount = new Map();    // keyCode -> number of holding sources
const pointerKeyMap = new Map(); // pointerId -> keyCode

function pressKeySource(sourceId, code) {
  if (!code) return;
  let s = srcHolds.get(sourceId);
  if (!s) {
    s = new Set();
    srcHolds.set(sourceId, s);
  }
  if (s.has(code)) return;
  s.add(code);
  const count = (codeCount.get(code) || 0) + 1;
  codeCount.set(code, count);
  if (count === 1) {
    activeKeys.add(code);
    highlightVirtualKey(code, true);
    updateActiveKeysDisplay();
  }
}

function releaseKeySource(sourceId, code) {
  const s = srcHolds.get(sourceId);
  if (!s) return;

  if (code) {
    if (!s.has(code)) return;
    s.delete(code);
    const count = (codeCount.get(code) || 1) - 1;
    if (count <= 0) {
      codeCount.delete(code);
      activeKeys.delete(code);
      highlightVirtualKey(code, false);
    } else {
      codeCount.set(code, count);
    }
  } else {
    for (const c of Array.from(s)) {
      s.delete(c);
      const count = (codeCount.get(c) || 1) - 1;
      if (count <= 0) {
        codeCount.delete(c);
        activeKeys.delete(c);
        highlightVirtualKey(c, false);
      } else {
        codeCount.set(c, count);
      }
    }
  }
  updateActiveKeysDisplay();
}

function highlightVirtualKey(code, isPressed) {
  const keys = document.querySelectorAll(`.vk-key[data-code="${code}"]`);
  keys.forEach(k => {
    if (isPressed) {
      k.classList.add("pressed");
    } else {
      k.classList.remove("pressed");
    }
  });
}

function updateActiveKeysDisplay() {
  const listEl = document.getElementById("vk-active-keys-list");
  if (!listEl) return;

  if (activeKeys.size === 0) {
    listEl.innerHTML = `<span style="font-size: 0.75rem; color: var(--text-muted);">None (Press any key or click above)</span>`;
    return;
  }

  listEl.innerHTML = "";
  activeKeys.forEach(code => {
    const pill = document.createElement("span");
    pill.className = "active-key-pill";
    pill.textContent = code.replace("Key", "").replace("Digit", "");
    listEl.appendChild(pill);
  });
}

function releaseAllKeys() {
  srcHolds.clear();
  codeCount.clear();
  activeKeys.clear();
  pointerKeyMap.clear();
  document.querySelectorAll(".vk-key.pressed").forEach(k => k.classList.remove("pressed"));
  updateActiveKeysDisplay();

  if (typeof playerWs !== "undefined" && playerWs && playerWs.readyState === WebSocket.OPEN) {
    if (typeof packetSeq !== "undefined") packetSeq++;
    playerWs.send(JSON.stringify({
      type: "input",
      seq: typeof packetSeq !== "undefined" ? packetSeq : 1,
      buttons: {},
      axes: { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0 },
      key_codes: [],
      client_time: performance.now()
    }));
  }
}

function renderVirtualKeyboard(layoutName) {
  const chassis = document.getElementById("vk-chassis");
  if (!chassis) return;
  chassis.innerHTML = "";

  const isControllerPreset = layoutName === "xbox_controller" ||
                             layoutName === "playstation_controller" ||
                             layoutName === "xbox_overlay" ||
                             layoutName === "playstation_overlay";
  const layouts = window.KEYBOARD_LAYOUTS || {};
  const badges = window.CONTROLLER_BADGES || {};
  const layout = isControllerPreset ? layouts.standard_full : (layouts[layoutName] || layouts.standard_full || []);
  const badgeMap = (typeof window.getActiveControllerBadges === "function" && isControllerPreset)
    ? window.getActiveControllerBadges(layoutName, window.currentKeyboardType || "standard")
    : (badges[layoutName] || (layoutName.includes("playstation") ? badges.playstation_controller : (layoutName.includes("xbox") ? badges.xbox_controller : {})));

  layout.forEach(rowDef => {
    const rowEl = document.createElement("div");
    rowEl.className = "vk-row";

    rowDef.forEach(keyDef => {
      if (keyDef.spacer) {
        const spacerEl = document.createElement("div");
        spacerEl.className = "vk-spacer";
        rowEl.appendChild(spacerEl);
        return;
      }

      const badgeInfo = badgeMap[keyDef.code];
      const badgeText = badgeInfo ? badgeInfo.badge : (keyDef.badge || "");
      const highlightClass = badgeInfo ? badgeInfo.highlight : "";

      const keyEl = document.createElement("div");
      keyEl.className = `vk-key ${keyDef.class || ""} ${highlightClass}`.trim();
      keyEl.dataset.code = keyDef.code;
      keyEl.innerHTML = `
        <span>${keyDef.label}</span>
        ${keyDef.sub ? `<span class="vk-key-sub">${keyDef.sub}</span>` : ""}
        ${badgeText ? `<span class="vk-badge">${badgeText}</span>` : ""}
      `;

      keyEl.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        try { keyEl.setPointerCapture(e.pointerId); } catch (_) {}
        pointerKeyMap.set(e.pointerId, keyDef.code);
        pressKeySource(`pointer_${e.pointerId}`, keyDef.code);
      });

      const handlePointerRelease = (e) => {
        const code = pointerKeyMap.get(e.pointerId) || keyDef.code;
        pointerKeyMap.delete(e.pointerId);
        releaseKeySource(`pointer_${e.pointerId}`, code);
      };

      keyEl.addEventListener("pointerup", handlePointerRelease);
      keyEl.addEventListener("pointercancel", handlePointerRelease);
      keyEl.addEventListener("pointerleave", (e) => {
        if (!keyEl.hasPointerCapture(e.pointerId)) {
          handlePointerRelease(e);
        }
      });

      rowEl.appendChild(keyEl);
    });

    chassis.appendChild(rowEl);
  });

  activeKeys.forEach(code => highlightVirtualKey(code, true));
  updateActiveKeysDisplay();

  if (typeof window !== "undefined" && typeof window.updateKeyboardControllerLabels === "function") {
    window.updateKeyboardControllerLabels();
  }
}

window.currentKeyboardLayout = currentKeyboardLayout;
window.activeKeys = activeKeys;
window.srcHolds = srcHolds;
window.codeCount = codeCount;
window.pointerKeyMap = pointerKeyMap;
window.pressKeySource = pressKeySource;
window.releaseKeySource = releaseKeySource;
window.highlightVirtualKey = highlightVirtualKey;
window.updateActiveKeysDisplay = updateActiveKeysDisplay;
window.releaseAllKeys = releaseAllKeys;
window.renderVirtualKeyboard = renderVirtualKeyboard;
