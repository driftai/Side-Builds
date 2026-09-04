/**
 * OmniPad — Gamepad Profile Definitions & Reference Grid Renderer.
 */

let currentGamepadProfile = localStorage.getItem("omnipad.gamepadProfile") || "street_fighter_6";

let gamepadKeymap = {
  "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN", "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
  "KeyJ": "X", "KeyK": "Y", "KeyL": "RB", "KeyU": "A", "KeyI": "B", "KeyO": "RT",
  "Space": "LB", "ShiftLeft": "LT", "Enter": "START", "Backspace": "BACK",
};

async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    const data = await res.json();
    const select = document.getElementById("profile-select");
    if (!select) return;
    select.innerHTML = "";
    (data.profiles || []).forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      select.appendChild(opt);
    });
    const available = Array.from(select.options).some(opt => opt.value === currentGamepadProfile);
    if (!available) currentGamepadProfile = "street_fighter_6";
    select.value = currentGamepadProfile;
    selectGamepadProfile(select.value);
  } catch (e) {
    console.error("Failed to load profiles:", e);
  }
}

function selectGamepadProfile(profileId) {
  currentGamepadProfile = profileId;
  if (profileId === "street_fighter_6") {
    gamepadKeymap = {
      "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN", "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
      "KeyJ": "X", "KeyK": "Y", "KeyL": "RB", "KeyU": "A", "KeyI": "B", "KeyO": "RT",
      "Space": "LB", "ShiftLeft": "LT", "Enter": "START", "Backspace": "BACK"
    };
  } else if (profileId === "tekken_8") {
    gamepadKeymap = {
      "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN", "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
      "KeyJ": "X", "KeyI": "Y", "KeyK": "A", "KeyO": "B", "KeyU": "RB", "KeyL": "RT",
      "Space": "LB", "ShiftLeft": "LT", "Enter": "START", "Backspace": "BACK"
    };
  } else if (profileId === "platform_fighter") {
    gamepadKeymap = {
      "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN", "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
      "KeyJ": "A", "KeyK": "B", "Space": "X", "KeyI": "Y", "ShiftLeft": "RT", "KeyU": "LB", "KeyL": "RB",
      "Enter": "START", "Backspace": "BACK"
    };
  } else if (profileId === "retro_arcade") {
    gamepadKeymap = {
      "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN", "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
      "KeyJ": "A", "KeyK": "B", "KeyU": "X", "KeyI": "Y", "KeyQ": "LB", "KeyE": "RB",
      "Enter": "START", "Backspace": "BACK"
    };
  } else if (profileId === "it_takes_two") {
    gamepadKeymap = {
      "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN", "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
      "Space": "A", "KeyE": "X", "KeyQ": "Y", "KeyR": "B",
      "KeyZ": "LB", "KeyC": "RB", "ShiftLeft": "LT", "ControlLeft": "RT",
      "CapsLock": "L3", "KeyF": "L3", "KeyG": "R3",
      "Enter": "START", "Escape": "BACK", "F1": "GUIDE"
    };
  } else if (profileId === "arrow_keys_player2") {
    gamepadKeymap = {
      "ArrowUp": "DPAD_UP", "ArrowDown": "DPAD_DOWN", "ArrowLeft": "DPAD_LEFT", "ArrowRight": "DPAD_RIGHT",
      "Numpad1": "X", "Numpad2": "Y", "Numpad3": "RB", "Numpad4": "A", "Numpad5": "B", "Numpad6": "RT",
      "Numpad0": "LB", "NumpadDecimal": "LT", "NumpadEnter": "START", "NumpadAdd": "BACK"
    };
  }
  window.currentGamepadProfile = currentGamepadProfile;
  window.gamepadKeymap = gamepadKeymap;
  try { localStorage.setItem("omnipad.gamepadProfile", currentGamepadProfile); } catch (_) {}
  renderKeybindingsGrid();
}

function getDualActionLabel(btn) {
  const dualMap = {
    "A": "A / ✕ (Cross)",
    "B": "B / ○ (Circle)",
    "X": "X / □ (Square)",
    "Y": "Y / △ (Triangle)",
    "LB": "LB / L1",
    "RB": "RB / R1",
    "LT": "LT / L2",
    "RT": "RT / R2",
    "BACK": "BACK / SHARE",
    "START": "START / OPTIONS",
    "GUIDE": "GUIDE / PS",
    "L3": "L3 (LS Click)",
    "R3": "R3 (RS Click)",
    "DPAD_UP": "D-PAD ↑",
    "DPAD_DOWN": "D-PAD ↓",
    "DPAD_LEFT": "D-PAD ←",
    "DPAD_RIGHT": "D-PAD →"
  };
  return dualMap[btn] || btn;
}

function renderKeybindingsGrid() {
  const container = document.getElementById("key-bindings-grid");
  if (!container) return;
  container.innerHTML = "";
  for (const [code, btn] of Object.entries(gamepadKeymap)) {
    const item = document.createElement("div");
    item.className = "key-bind-item";
    item.innerHTML = `
      <span class="key-action-name">${getDualActionLabel(btn)}</span>
      <span class="key-badge">${code.replace("Key", "")}</span>
    `;
    container.appendChild(item);
  }
}

window.currentGamepadProfile = currentGamepadProfile;
window.gamepadKeymap = gamepadKeymap;
window.loadProfiles = loadProfiles;
window.selectGamepadProfile = selectGamepadProfile;
window.getDualActionLabel = getDualActionLabel;
window.renderKeybindingsGrid = renderKeybindingsGrid;
