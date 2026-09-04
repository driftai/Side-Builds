/**
 * OmniPad Host Dashboard — Target Process Discovery & Safety Gating.
 */

async function loadTargets() {
  try {
    const res = await fetch("/api/targets");
    const data = await res.json();
    const select = document.getElementById("target-select");
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">Select a running game...</option>`;
    (data.targets || []).forEach(t => {
      const opt = document.createElement("option");
      opt.value = String(t.hwnd);
      opt.textContent = t.label;
      opt.dataset.pid = String(t.pid);
      select.appendChild(opt);
    });
    if (current) select.value = current;
  } catch (e) {
    console.error("Failed to enumerate targets:", e);
  }
}

function renderTargetStatus(status) {
  const el = document.getElementById("target-status");
  if (!el) return;
  if (!status || !status.selected) {
    el.textContent = "No game target selected. Keyboard 2 is unrestricted until you select one.";
    el.title = "";
    return;
  }
  const t = status.selected;
  let stateLabel = "";
  if (!status.target_running) {
    stateLabel = " • CLOSED / NOT RUNNING";
    el.title = "Target game process is closed. Controller routing and keyboard injection are paused until the target is running.";
  } else if (status.target_foreground) {
    stateLabel = " • FOREGROUND";
    el.title = "Target window is in foreground. All controller and keyboard backends active.";
  } else {
    stateLabel = " • RUNNING (Controllers Active, Keyboard 2 Paused)";
    el.title = "Target is running in the background. Virtual controllers (Xbox 360 / DualShock 4) route freely unfocused. Target-Locked Keyboard injection requires game focus.";
  }
  el.textContent = `Target: ${t.title || t.process_name} • ${t.process_name || "unknown.exe"} • PID ${t.pid}${stateLabel}`;
}

async function refreshTargetStatus() {
  try {
    const res = await fetch("/api/target/status");
    const data = await res.json();
    renderTargetStatus(data);
  } catch (e) {
    console.debug("Failed to refresh target status:", e);
  }
}

async function attachTarget() {
  const select = document.getElementById("target-select");
  if (!select) return;
  const option = select.options[select.selectedIndex];
  if (!option || !option.value) return;
  const res = await fetch("/api/target/select", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hwnd: Number(option.value), pid: Number(option.dataset.pid) })
  });
  const data = await res.json();
  if (!res.ok) { alert(data.detail || "Target selection failed"); return; }
  renderTargetStatus(data.status);
}

async function selectForegroundTarget() {
  const res = await fetch("/api/target/select-foreground", { method: "POST" });
  const data = await res.json();
  if (!res.ok) { alert(data.detail || "Could not select foreground window"); return; }
  renderTargetStatus(data.status);
  await loadTargets();
}

async function setTargetGate(enabled) {
  await fetch("/api/target/gate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  });
}

async function clearTarget() {
  const res = await fetch("/api/target/clear", { method: "POST" });
  const data = await res.json();
  renderTargetStatus(data.status);
}

function setupTargetEvents() {
  const refreshBtn = document.getElementById("target-refresh-btn");
  if (refreshBtn) refreshBtn.onclick = async () => { await loadTargets(); await refreshTargetStatus(); };
  const attachBtn = document.getElementById("target-attach-btn");
  if (attachBtn) attachBtn.onclick = attachTarget;
  const fgBtn = document.getElementById("target-foreground-btn");
  if (fgBtn) fgBtn.onclick = selectForegroundTarget;
  const clearBtn = document.getElementById("target-clear-btn");
  if (clearBtn) clearBtn.onclick = clearTarget;
  const gateCheckbox = document.getElementById("target-gate-checkbox");
  if (gateCheckbox) gateCheckbox.onchange = (e) => setTargetGate(e.target.checked);

  // Live target status is streamed at 30Hz over WebSocket telemetry.
  // Polling via HTTP is only used as a relaxed fallback if the WebSocket is disconnected.
  setInterval(() => {
    if (!window.hostWs || window.hostWs.readyState !== WebSocket.OPEN) {
      refreshTargetStatus();
    }
  }, 5000);
  loadTargets();
}

window.loadTargets = loadTargets;
window.renderTargetStatus = renderTargetStatus;
window.refreshTargetStatus = refreshTargetStatus;
window.setupTargetEvents = setupTargetEvents;
