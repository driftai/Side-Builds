/**
 * OmniPad Host Dashboard — Cloudflare Quick Tunnel Management.
 */

function getActiveRoomCode() {
  const roomCodeEl = document.getElementById("room-code-display");
  const candidates = [window.currentRoomCode, roomCodeEl ? roomCodeEl.textContent : ""];
  for (const value of candidates) {
    const code = String(value || "").trim().toUpperCase();
    if (code && code !== "SF6-ROOM" && code !== "--") return code;
  }
  return "";
}

function updateTunnelUI(tunnel) {
  if (!tunnel) return;
  const badge = document.getElementById("tunnel-status-badge");
  const urlDisplay = document.getElementById("tunnel-url-display");
  const tunnelBtn = document.getElementById("tunnel-toggle-btn");
  const qrBtn = document.getElementById("tunnel-qr-btn");

  if (!tunnel.available) {
    if (badge) {
      badge.className = "badge badge-muted";
      badge.innerHTML = `<span class="status-dot"></span> cloudflared Missing`;
    }
    if (tunnelBtn) tunnelBtn.disabled = true;
    if (urlDisplay) urlDisplay.textContent = "cloudflared.exe not found";
    if (qrBtn) qrBtn.style.display = "none";
    return;
  }

  if (tunnel.status === "active" && tunnel.public_url) {
    const roomCode = getActiveRoomCode();
    const publicPlayUrl = roomCode
      ? `${tunnel.public_url}/play?code=${encodeURIComponent(roomCode)}`
      : "";

    if (badge) {
      badge.className = "badge badge-cyan";
      badge.innerHTML = `<span class="status-dot"></span> Quick Tunnel Active`;
    }
    if (urlDisplay) {
      if (publicPlayUrl) {
        urlDisplay.innerHTML = `<a href="${publicPlayUrl}" target="_blank" style="color: var(--accent-cyan); text-decoration: underline;">${publicPlayUrl}</a>`;
      } else {
        urlDisplay.textContent = "Tunnel ready — waiting for the active room code...";
      }
    }
    if (tunnelBtn) {
      tunnelBtn.textContent = "Stop Tunnel";
      tunnelBtn.className = "btn btn-danger btn-sm";
      tunnelBtn.disabled = false;
      tunnelBtn.onclick = stopTunnel;
    }
    if (qrBtn) {
      qrBtn.style.display = publicPlayUrl ? "inline-flex" : "none";
      qrBtn.onclick = publicPlayUrl ? () => {
        if (typeof showQR === "function") showQR(publicPlayUrl, "Public Cloudflare Link");
      } : null;
    }
  } else if (tunnel.status === "starting") {
    if (badge) {
      badge.className = "badge badge-yellow";
      badge.innerHTML = `<span class="status-dot"></span> Spawning Tunnel...`;
    }
    if (urlDisplay) urlDisplay.textContent = "Requesting trycloudflare.com URL...";
    if (tunnelBtn) tunnelBtn.disabled = true;
    if (qrBtn) qrBtn.style.display = "none";
  } else {
    if (badge) {
      badge.className = "badge badge-muted";
      badge.innerHTML = `<span class="status-dot"></span> Tunnel Offline`;
    }
    if (urlDisplay) urlDisplay.textContent = "Click 'Start Quick Tunnel' to enable public link";
    if (tunnelBtn) {
      tunnelBtn.textContent = "Start Quick Tunnel";
      tunnelBtn.className = "btn btn-primary btn-sm";
      tunnelBtn.disabled = false;
      tunnelBtn.onclick = startTunnel;
    }
    if (qrBtn) qrBtn.style.display = "none";
  }
}

async function startTunnel() {
  const btn = document.getElementById("tunnel-toggle-btn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Starting...";
  }
  try {
    const res = await fetch("/api/tunnel/start", { method: "POST" });
    const data = await res.json();
    updateTunnelUI(data.tunnel);
    pollTunnel();
  } catch (e) {
    console.error("Start tunnel failed:", e);
  }
}

async function stopTunnel() {
  try {
    const res = await fetch("/api/tunnel/stop", { method: "POST" });
    const data = await res.json();
    updateTunnelUI(data.tunnel);
  } catch (e) {
    console.error("Stop tunnel failed:", e);
  }
}

async function pollTunnel() {
  for (let i = 0; i < 15; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const res = await fetch("/api/tunnel/status");
    const data = await res.json();
    updateTunnelUI(data);
    if (data.status === "active" || data.status === "error") break;
  }
}

window.getActiveRoomCode = getActiveRoomCode;
window.updateTunnelUI = updateTunnelUI;
window.startTunnel = startTunnel;
window.stopTunnel = stopTunnel;
window.pollTunnel = pollTunnel;
