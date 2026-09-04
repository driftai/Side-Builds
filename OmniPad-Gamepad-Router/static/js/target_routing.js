/**
 * OmniPad — Target Scoping & Background Input Routing Synchronization.
 */

let backgroundRoutingActive = true;
let selectedTargetInfo = null;
let backgroundCaptureEnabled = false;
let backgroundInputMirrorInFlight = false;
const BACKGROUND_NATIVE_SOURCE = "background_native";

let backgroundInputMirrorTimer = null;

function startBackgroundInputMirrorTimer() {
  if (backgroundInputMirrorTimer) return;
  backgroundInputMirrorTimer = setInterval(() => {
    if (typeof syncBackgroundInputMirror === "function") syncBackgroundInputMirror();
  }, 50);
}

function stopBackgroundInputMirrorTimer() {
  if (backgroundInputMirrorTimer) {
    clearInterval(backgroundInputMirrorTimer);
    backgroundInputMirrorTimer = null;
  }
  if (typeof releaseKeySource === "function") {
    releaseKeySource(BACKGROUND_NATIVE_SOURCE);
  }
}

function isCloudflareRemoteSession() {
  return window.location.hostname.toLowerCase().endsWith(".trycloudflare.com");
}

function isRoutingActive() {
  return backgroundRoutingActive;
}

async function refreshTargetStatus() {
  const nameEl = document.getElementById("current-target-name");
  if (!nameEl) return;
  if (typeof document !== "undefined" && document.hidden) return;
  try {
    const res = await fetch("/api/target/status", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    selectedTargetInfo = data.selected;
    if (data.selected) {
      const title = data.selected.title || data.selected.process_name || data.selected.label;
      nameEl.textContent = title;
      nameEl.title = `PID ${data.selected.pid} — ${data.selected.process_name}`;
      if (!data.target_running) {
        nameEl.className = "target-name-badge badge-danger";
        nameEl.textContent += " (Closed)";
      } else if (data.target_foreground) {
        nameEl.className = "target-name-badge badge-green";
        nameEl.textContent += " (Focused)";
      } else {
        nameEl.className = "target-name-badge badge-cyan";
        nameEl.textContent += " (Background)";
      }
    } else {
      nameEl.textContent = "None (Site-Only)";
      nameEl.className = "target-name-badge badge-muted";
      nameEl.title = "No target application locked. Inputs stay on the site when routing is off.";
    }
    updateRoutingUI();
  } catch (_) {}
}

async function refreshBackgroundCaptureStatus() {
  if (isCloudflareRemoteSession()) {
    backgroundCaptureEnabled = false;
    stopBackgroundInputMirrorTimer();
    return;
  }
  try {
    const res = await fetch("/api/background-capture/status", { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      backgroundCaptureEnabled = !!(data.running && data.ready);
      if (backgroundCaptureEnabled) {
        backgroundRoutingActive = true;
        startBackgroundInputMirrorTimer();
      } else {
        stopBackgroundInputMirrorTimer();
      }
    }
  } catch (_) {}
  updateRoutingUI();
}

function updateRoutingUI() {
  const controls = document.getElementById("background-input-controls");
  const btn = document.getElementById("background-input-btn");
  const status = document.getElementById("background-input-status");
  const touchBtn = document.getElementById("touch-routing-btn");

  if (isCloudflareRemoteSession()) {
    if (controls) controls.style.display = "none";
    if (touchBtn) touchBtn.style.display = "none";
    return;
  }

  if (btn) {
    if (backgroundRoutingActive || backgroundCaptureEnabled) {
      btn.textContent = backgroundCaptureEnabled
        ? "🪟 Native Background Capture: Active (OS-Wide)"
        : "🪟 Background Routing: On (Route to Target)";
      btn.classList.add("background-input-on", "routing-on");
    } else {
      btn.textContent = "🪟 Background Routing: Off (Site Only)";
      btn.classList.remove("background-input-on", "routing-on");
    }
  }

  if (touchBtn) {
    touchBtn.textContent = backgroundRoutingActive ? "🪟 Touch Routing: On" : "🪟 Touch Routing: Off";
    touchBtn.classList.toggle("routing-on", backgroundRoutingActive);
  }

  if (status) {
    if (backgroundCaptureEnabled) {
      status.textContent = "Native Background RawInput active — keys captured OS-wide";
    } else if (backgroundRoutingActive) {
      if (selectedTargetInfo) {
        status.textContent = `Routing to: ${selectedTargetInfo.title || selectedTargetInfo.process_name}`;
      } else {
        status.textContent = "Routing active — inputs sent to game controller";
      }
    } else {
      status.textContent = "Site-Only Mode — inputs stay in browser";
    }
  }
}

async function toggleBackgroundRouting() {
  if (isCloudflareRemoteSession()) return;
  const btn = document.getElementById("background-input-btn");
  const isKb = (window.currentMode || "keyboard") === "keyboard";

  if (isKb && typeof isConnected !== "undefined" && isConnected) {
    if (btn) btn.disabled = true;
    try {
      const targetState = !backgroundCaptureEnabled;
      const playUrl = new URL(window.location.href);
      if (typeof roomCode !== "undefined") playUrl.searchParams.set("code", roomCode);
      const res = await fetch("/api/background-capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: targetState,
          play_url: playUrl.toString(),
          slot_id: typeof activeSlot !== "undefined" ? activeSlot : 1,
          name: typeof friendName !== "undefined" ? friendName : "Player 2"
        })
      });
      const data = await res.json();
      backgroundCaptureEnabled = !!(data.ok && data.running && data.ready);
      if (backgroundCaptureEnabled) {
        startBackgroundInputMirrorTimer();
        backgroundRoutingActive = true;
      } else {
        stopBackgroundInputMirrorTimer();
        backgroundRoutingActive = !backgroundRoutingActive;
      }
    } catch (err) {
      backgroundRoutingActive = !backgroundRoutingActive;
      stopBackgroundInputMirrorTimer();
    } finally {
      if (btn) btn.disabled = false;
    }
  } else {
    backgroundRoutingActive = !backgroundRoutingActive;
  }

  updateRoutingUI();
  if (typeof window.transmitCurrentInputState === "function") {
    window.transmitCurrentInputState();
  }
}

async function syncBackgroundInputMirror() {
  if (backgroundInputMirrorInFlight) return;
  const isConn = typeof isConnected !== "undefined" ? isConnected : false;
  const slot = typeof activeSlot !== "undefined" ? activeSlot : 1;
  if (!backgroundCaptureEnabled || !isConn) {
    if (typeof releaseKeySource === "function") releaseKeySource(BACKGROUND_NATIVE_SOURCE);
    return;
  }

  backgroundInputMirrorInFlight = true;
  try {
    const res = await fetch(
      `/api/background-capture/input-state?slot_id=${encodeURIComponent(slot)}`,
      { cache: "no-store" }
    );
    if (!res.ok) throw new Error("Background input state unavailable");
    const data = await res.json();

    if (!data.background_active) {
      if (typeof releaseKeySource === "function") releaseKeySource(BACKGROUND_NATIVE_SOURCE);
      return;
    }

    const next = new Set(Array.isArray(data.active_keys) ? data.active_keys.map(String) : []);
    const previous = new Set((window.srcHolds && window.srcHolds.get(BACKGROUND_NATIVE_SOURCE)) || []);

    for (const code of previous) {
      if (!next.has(code) && typeof releaseKeySource === "function") releaseKeySource(BACKGROUND_NATIVE_SOURCE, code);
    }
    for (const code of next) {
      if (!previous.has(code) && typeof pressKeySource === "function") pressKeySource(BACKGROUND_NATIVE_SOURCE, code);
    }
  } catch (_) {
  } finally {
    backgroundInputMirrorInFlight = false;
  }
}

window.backgroundRoutingActive = backgroundRoutingActive;
window.selectedTargetInfo = selectedTargetInfo;
window.isRoutingActive = isRoutingActive;
window.refreshTargetStatus = refreshTargetStatus;
window.refreshBackgroundCaptureStatus = refreshBackgroundCaptureStatus;
window.updateRoutingUI = updateRoutingUI;
window.toggleBackgroundRouting = toggleBackgroundRouting;
window.syncBackgroundInputMirror = syncBackgroundInputMirror;
window.startBackgroundInputMirrorTimer = startBackgroundInputMirrorTimer;
window.stopBackgroundInputMirrorTimer = stopBackgroundInputMirrorTimer;
window.isCloudflareRemoteSession = isCloudflareRemoteSession;
