/**
 * OmniPad Host Dashboard — Controller Slots & Visualizer Management.
 */

let visualizers = {};
let currentSummary = null;

function isKeyboardBackend(backendId) {
  return backendId === "keyboard" || backendId === "keyboard_target" || backendId === "virtual_keyboard";
}

function updateDashboard(summary) {
  if (!summary || !summary.slots) return;
  currentSummary = summary;

  const container = document.getElementById("slots-container");
  if (!container) return;

  summary.slots.forEach((slot) => {
    let card = document.getElementById(`slot-card-${slot.slot_id}`);
    if (!card) {
      card = createSlotCard(slot, summary.available_backends || []);
      container.appendChild(card);
    }
    updateSlotCard(slot);
  });
}

function createSlotCard(slot, backends) {
  const card = document.createElement("div");
  card.id = `slot-card-${slot.slot_id}`;
  card.className = "slot-card glass";

  const backendOptions = (backends || []).map(b => {
    const isAvail = b.available !== false;
    const suffix = isAvail ? "" : " (Driver Not Installed)";
    const dis = isAvail ? "" : "disabled";
    return `<option value="${b.id}" ${b.id === slot.controller_type ? "selected" : ""} ${dis}>${b.name}${suffix}</option>`;
  }).join("");

  card.innerHTML = `
    <div class="slot-header">
      <div class="slot-title-wrap">
        <span class="slot-title">${slot.title}</span>
        <span id="slot-${slot.slot_id}-tag" class="player-tag">Waiting...</span>
      </div>
      <div class="slot-metrics">
        <span id="slot-${slot.slot_id}-ping" class="metric-pill">-- ms</span>
        <span id="slot-${slot.slot_id}-pkts" class="metric-pill">0 pkts</span>
      </div>
    </div>

    <div class="viz-container" id="viz-container-${slot.slot_id}">
      <!-- Vector Gamepad SVG rendered here -->
    </div>

    <div class="slot-routing-note" id="slot-${slot.slot_id}-routing-note">Remote control surface and host output device are independent.</div>

    <div class="slot-controls">
      <div class="control-row">
        <label class="control-label">Output Device</label>
        <select id="slot-${slot.slot_id}-backend" onchange="changeBackend(${slot.slot_id}, this.value)">
          ${backendOptions}
        </select>
      </div>

      <div class="control-row">
        <label class="control-label">SOCD Cleaner</label>
        <select id="slot-${slot.slot_id}-socd" onchange="changeSOCD(${slot.slot_id}, this.value)">
          <option value="neutral" ${slot.socd_mode === "neutral" ? "selected" : ""}>Neutral (CPT Standard)</option>
          <option value="up_priority" ${slot.socd_mode === "up_priority" ? "selected" : ""}>Up Priority (Hitbox)</option>
          <option value="last_win" ${slot.socd_mode === "last_win" ? "selected" : ""}>Last Win</option>
          <option value="raw" ${slot.socd_mode === "raw" ? "selected" : ""}>Raw (Pass-through)</option>
        </select>
      </div>

      <div class="control-row">
        <label class="control-label">Analog Deadzone</label>
        <div class="control-input-group">
          <input type="range" min="0" max="0.4" step="0.01" value="${slot.deadzone}" 
                 id="slot-${slot.slot_id}-deadzone" 
                 oninput="updateDeadzoneDisplay(${slot.slot_id}, this.value)"
                 onchange="changeDeadzone(${slot.slot_id}, this.value)">
          <span id="slot-${slot.slot_id}-dz-val" class="slider-val">${Math.round(slot.deadzone * 100)}%</span>
        </div>
      </div>

      <div class="slot-actions">
        <button class="btn btn-secondary btn-sm" id="slot-${slot.slot_id}-mute-btn" onclick="toggleMute(${slot.slot_id})">
          ${slot.muted ? "Unmute" : "Mute"}
        </button>
        <button class="btn btn-secondary btn-sm" onclick="panicResetSlot(${slot.slot_id})">
          Panic Reset
        </button>
        <button class="btn btn-danger btn-sm" onclick="kickSlot(${slot.slot_id})">
          Kick
        </button>
      </div>
    </div>
  `;

  setTimeout(() => ensureSlotVisualizer(slot), 10);
  return card;
}

function ensureSlotVisualizer(slot) {
  const container = document.getElementById(`viz-container-${slot.slot_id}`);
  if (!container) return;

  const wantKeyboard = isKeyboardBackend(slot.controller_type);
  const currentType = container.dataset.vizType || "";

  if (wantKeyboard) {
    if (currentType !== "keyboard") {
      delete visualizers[slot.slot_id];
      container.dataset.vizType = "keyboard";
      const rows = [
        ["Escape", "Digit1", "Digit2", "Digit3", "Digit4", "Digit5", "Digit6", "Digit7", "Digit8", "Digit9", "Digit0", "Backspace"],
        ["Tab", "KeyQ", "KeyW", "KeyE", "KeyR", "KeyT", "KeyY", "KeyU", "KeyI", "KeyO", "KeyP", "Enter"],
        ["ShiftLeft", "KeyA", "KeyS", "KeyD", "KeyF", "KeyG", "KeyH", "KeyJ", "KeyK", "KeyL", "ShiftRight"],
        ["ControlLeft", "AltLeft", "Space", "AltRight", "ArrowLeft", "ArrowDown", "ArrowUp", "ArrowRight"]
      ];
      const label = code => ({
        Escape: "Esc", Backspace: "Bksp", ShiftLeft: "Shift", ShiftRight: "Shift",
        ControlLeft: "Ctrl", AltLeft: "Alt", AltRight: "Alt", Space: "Space",
        ArrowLeft: "←", ArrowRight: "→", ArrowUp: "↑", ArrowDown: "↓"
      }[code] || code.replace("Key", "").replace("Digit", "").replace("Left", "").replace("Right", ""));
      container.innerHTML = `<div class="keyboard-viz" aria-label="Keyboard input visualizer">${rows.map(row =>
        `<div class="keyboard-viz-row">${row.map(code => `<span class="keyboard-viz-key${code === "Space" ? " key-wide" : ""}" data-code="${code}">${label(code)}</span>`).join("")}</div>`
      ).join("")}</div>`;
    }
    const active = new Set((slot.last_state && slot.last_state.key_codes) || []);
    container.querySelectorAll(".keyboard-viz-key").forEach(key => {
      key.classList.toggle("active", active.has(key.dataset.code));
    });
    return;
  }

  if (currentType !== "gamepad") {
    container.innerHTML = "";
    container.dataset.vizType = "gamepad";
    if (typeof GamepadVisualizer !== "undefined") {
      visualizers[slot.slot_id] = new GamepadVisualizer(`viz-container-${slot.slot_id}`, `slot${slot.slot_id}`);
    }
  }
}

function updateSlotCard(slot) {
  const card = document.getElementById(`slot-card-${slot.slot_id}`);
  if (!card) return;

  const tag = document.getElementById(`slot-${slot.slot_id}-tag`);
  const ping = document.getElementById(`slot-${slot.slot_id}-ping`);
  const pkts = document.getElementById(`slot-${slot.slot_id}-pkts`);
  const routingNote = document.getElementById(`slot-${slot.slot_id}-routing-note`);

  if (routingNote) {
    const surface = slot.input_surface && slot.input_surface !== "unknown" ? slot.input_surface : "waiting";
    const profile = slot.mapping_profile || "universal";
    routingNote.textContent = `Surface: ${surface} → Output: ${slot.backend_name || slot.controller_type} • Mapping: ${profile}`;
  }

  if (slot.connected) {
    card.classList.add("connected");
    if (tag) {
      tag.textContent = slot.friend_name;
      tag.style.color = "var(--accent-cyan)";
    }
    if (ping) {
      if (slot.latency_ms !== null) {
        ping.textContent = `${slot.latency_ms} ms`;
        ping.style.color = slot.latency_ms < 30 ? "var(--accent-green)" : (slot.latency_ms < 80 ? "var(--accent-yellow)" : "var(--accent-red)");
      } else {
        ping.textContent = "-- ms";
      }
    }
    if (pkts) pkts.textContent = `${slot.packet_count} pkts`;
  } else {
    card.classList.remove("connected");
    if (tag) {
      tag.textContent = "Waiting...";
      tag.style.color = "var(--text-muted)";
    }
    if (ping) ping.textContent = "-- ms";
    if (pkts) pkts.textContent = "0 pkts";
  }

  ensureSlotVisualizer(slot);
  if (!isKeyboardBackend(slot.controller_type) && visualizers[slot.slot_id]) {
    visualizers[slot.slot_id].update(slot.last_state);
  }
}

async function changeBackend(slotId, backendId) {
  const res = await fetch(`/api/slot/${slotId}/controller`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ backend_id: backendId })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    alert(data.detail || "Could not switch emulation backend.");
    if (currentSummary) updateDashboard(currentSummary);
    return;
  }

  if (currentSummary && currentSummary.slots) {
    const slot = currentSummary.slots.find(s => s.slot_id === slotId);
    if (slot) {
      slot.controller_type = backendId;
      if (data.backend_name) slot.backend_name = data.backend_name;
      ensureSlotVisualizer(slot);
    }
  }
}

async function changeSOCD(slotId, mode) {
  await fetch(`/api/slot/${slotId}/socd`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode })
  });
}

function updateDeadzoneDisplay(slotId, val) {
  const el = document.getElementById(`slot-${slotId}-dz-val`);
  if (el) el.textContent = `${Math.round(val * 100)}%`;
}

async function changeDeadzone(slotId, val) {
  await fetch(`/api/slot/${slotId}/deadzone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deadzone: parseFloat(val) })
  });
}

async function toggleMute(slotId) {
  const btn = document.getElementById(`slot-${slotId}-mute-btn`);
  if (!btn) return;
  const isMuted = btn.textContent.trim() === "Unmute";
  const newMuted = !isMuted;
  await fetch(`/api/slot/${slotId}/mute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ muted: newMuted })
  });
  btn.textContent = newMuted ? "Unmute" : "Mute";
}

async function panicResetSlot(slotId) {
  await fetch(`/api/slot/${slotId}/reset`, { method: "POST" });
}

async function kickSlot(slotId) {
  await fetch(`/api/slot/${slotId}/kick`, { method: "POST" });
}

window.visualizers = visualizers;
window.updateDashboard = updateDashboard;
window.createSlotCard = createSlotCard;
window.ensureSlotVisualizer = ensureSlotVisualizer;
window.updateSlotCard = updateSlotCard;
window.changeBackend = changeBackend;
window.changeSOCD = changeSOCD;
window.updateDeadzoneDisplay = updateDeadzoneDisplay;
window.changeDeadzone = changeDeadzone;
window.toggleMute = toggleMute;
window.panicResetSlot = panicResetSlot;
window.kickSlot = kickSlot;
