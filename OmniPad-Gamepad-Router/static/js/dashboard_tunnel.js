/**
 * OmniPad Host Dashboard — Cloudflare Quick Tunnel Management.
 */

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
    const roomCodeEl = document.getElementById("room-code-display");
    const roomCode = roomCodeEl ? roomCodeEl.textContent.trim() : "";
    const roomCodeReady = roomCode && roomCode !== "--" && roomCode !== "SF6-ROOM";
    if (badge) {
      badge.className = "badge badge-cyan";
      badge.innerHTML = `<span class="status-dot"></span> Quick Tunnel Active`;
    }
    if (tunnelBtn) {
      tunnelBtn.textContent = "Stop Tunnel";
      tunnelBtn.className = "btn btn-danger btn-sm";
      tunnelBtn.disabled = false;
      tunnelBtn.onclick = stopTunnel;
    }
    if (!roomCodeReady) {
      if (urlDisplay) urlDisplay.textContent = "Tunnel ready; waiting for the current room code...";
      if (qrBtn) qrBtn.style.display = "none";
      return;
    }
    const publicPlayUrl = `${tunnel.public_url}/play?code=${encodeURIComponent(roomCode)}`;
    if (urlDisplay) {
      urlDisplay.innerHTML = `<a href="${publicPlayUrl}" target="_blank" rel="noopener" style="color: var(--accent-cyan); text-decoration: underline;">${publicPlayUrl}</a>`;
    }
    if (qrBtn) {
      qrBtn.style.display = "inline-flex";
      qrBtn.onclick = () => {
        if (typeof showQR === "function") showQR(publicPlayUrl, "Public Cloudflare Link");
      };
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

window.updateTunnelUI = updateTunnelUI;
window.startTunnel = startTunnel;
window.stopTunnel = stopTunnel;
window.pollTunnel = pollTunnel;
