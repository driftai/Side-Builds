/**
 * OmniPad Host Management Dashboard Entry Point & Telemetry Connection.
 */

let hostWs = null;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  fetchInitialStatus();
  setupGlobalEvents();
  if (typeof setupTargetEvents === "function") {
    setupTargetEvents();
  }
});

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/host`;

  hostWs = new WebSocket(wsUrl);
  window.hostWs = hostWs;

  hostWs.onopen = () => {
    const badge = document.getElementById("server-status-badge");
    if (badge) {
      badge.innerHTML = `<span class="status-dot"></span> Online`;
      badge.className = "badge badge-green";
    }
  };

  hostWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "telemetry" || msg.type === "initial_status") {
        if (typeof updateDashboard === "function") {
          updateDashboard(msg.data);
        }
        if (msg.data && msg.data.target && typeof renderTargetStatus === "function") {
          renderTargetStatus(msg.data.target);
        }
      }
    } catch (e) {
      console.error("Failed to parse telemetry:", e);
    }
  };

  hostWs.onclose = () => {
    if (window.hostWs === hostWs) window.hostWs = null;
    const badge = document.getElementById("server-status-badge");
    if (badge) {
      badge.innerHTML = `<span class="status-dot"></span> Disconnected`;
      badge.className = "badge badge-red";
    }
    setTimeout(initWebSocket, 2000);
  };
}

async function fetchInitialStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    // Set Room Code
    const roomEl = document.getElementById("room-code-display");
    if (roomEl) roomEl.textContent = data.room_code;

    // ViGEm Driver Status
    const vigemBadge = document.getElementById("vigem-status-badge");
    if (vigemBadge) {
      if (data.vigem_available) {
        vigemBadge.className = "badge badge-green";
        vigemBadge.innerHTML = `<span class="status-dot"></span> ViGEmBus Active`;
        vigemBadge.title = "Native virtual gamepads (Xbox 360 / DS4) active";
      } else {
        vigemBadge.className = "badge badge-yellow";
        vigemBadge.innerHTML = `<span class="status-dot"></span> No ViGEm (Simulation)`;
        vigemBadge.title = "ViGEmBus driver not detected. Operating in simulation mode.";
      }
    }

    // Separate virtual keyboard status (normal-mode UMDF first, preserved VHF second).
    const vhfBadge = document.getElementById("vhf-status-badge");
    if (vhfBadge) {
      if (data.umdf_keyboard_available) {
        vhfBadge.className = "badge badge-green";
        vhfBadge.innerHTML = `<span class="status-dot"></span> Virtual Keyboard Port Active`;
        vhfBadge.title = "OmniPad UMDF virtual keyboard is active as a separate Raw Input device";
      } else if (data.vhf_available) {
        vhfBadge.className = "badge badge-green";
        vhfBadge.innerHTML = `<span class="status-dot"></span> VHF Keyboard Active`;
        vhfBadge.title = "OmniPad Virtual Keyboard HID (VHF) driver active as separate hardware keyboard";
      } else {
        vhfBadge.className = "badge badge-yellow";
        vhfBadge.innerHTML = `<span class="status-dot"></span> Virtual Keyboard Port Not Installed`;
        vhfBadge.title = "The normal-mode UMDF virtual keyboard can be installed after package signing. KMDF/VHF remains preserved for future Microsoft signing.";
      }
    }

    // LAN URL
    if (data.primary_lan_url) {
      const lanEl = document.getElementById("lan-url-display");
      if (lanEl) {
        lanEl.textContent = "";
        const link = document.createElement("a");
        link.href = data.primary_lan_url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = data.primary_lan_url;
        link.style.color = "var(--accent-cyan)";
        lanEl.appendChild(link);
      }
      const lanQrBtn = document.getElementById("lan-qr-btn");
      if (lanQrBtn) lanQrBtn.onclick = () => showQR(data.primary_lan_url, "Local LAN Join Link");
    }

    // Tunnel & Target Info
    if (typeof updateTunnelUI === "function") updateTunnelUI(data.tunnel);
    if (typeof renderTargetStatus === "function") renderTargetStatus(data.target || data.summary?.target);

    const gateCheckbox = document.getElementById("target-gate-checkbox");
    if (gateCheckbox && data.target && typeof data.target.gate_enabled === "boolean") {
      gateCheckbox.checked = data.target.gate_enabled;
    }

    if (data.summary && typeof updateDashboard === "function") {
      updateDashboard(data.summary);
    }
  } catch (e) {
    console.error("Failed to fetch initial status:", e);
  }
}

function setupGlobalEvents() {
  const panicBtn = document.getElementById("global-panic-btn");
  if (panicBtn) {
    panicBtn.onclick = async () => {
      await fetch("/api/panic", { method: "POST" });
    };
  }

  const copyBtn = document.getElementById("copy-room-code-btn");
  if (copyBtn) {
    copyBtn.onclick = () => {
      const code = document.getElementById("room-code-display").textContent;
      navigator.clipboard.writeText(code);
      alert(`Copied Room Code: ${code}`);
    };
  }

  const closeBtn = document.getElementById("modal-close-btn");
  if (closeBtn) closeBtn.onclick = hideQR;

  const modal = document.getElementById("qr-modal");
  if (modal) {
    modal.onclick = (e) => {
      if (e.target.id === "qr-modal") hideQR();
    };
  }
}

function showQR(url, title) {
  const titleEl = document.getElementById("qr-modal-title");
  if (titleEl) titleEl.textContent = title;
  const urlEl = document.getElementById("qr-url-text");
  if (urlEl) urlEl.textContent = url;
  const container = document.getElementById("qr-canvas-container");
  if (container && typeof QRCode !== "undefined") {
    container.innerHTML = "";
    new QRCode("qr-canvas-container", url, { size: 200 });
  }
  const modal = document.getElementById("qr-modal");
  if (modal) modal.classList.add("open");
}

function hideQR() {
  const modal = document.getElementById("qr-modal");
  if (modal) modal.classList.remove("open");
}

window.showQR = showQR;
window.hideQR = hideQR;
