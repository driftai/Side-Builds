/**
 * OmniPad — Target Scoping & Background Input Routing Synchronization.
 */

let backgroundRoutingActive = true;
let selectedTargetInfo = null;
let backgroundCaptureEnabled = false;
let backgroundInputMirrorInFlight = false;
let backgroundInputMirrorTimer = null;
let routingStatusTimer = null;
let routingFocusBound = false;
const BACKGROUND_NATIVE_SOURCE = "background_native";

function isCloudflareRemoteSession() {
  return window.location.hostname.toLowerCase().endsWith(".trycloudflare.com");
}

function isRoutingActive() {
  return backgroundRoutingActive;
}

async function refreshTargetStatus() {
  const nameEl = document.getElementById("current-target-name");
  if (!nameEl || document.hidden) return;
  try {
    const res = await fetch("/api/target/status", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    selectedTargetInfo = data.selected
      ? (typeof data.selected === "object" ? data.selected : { title: "Host-selected game" })
      : null;
    window.selectedTargetInfo = selectedTargetInfo;
    if (data.selected) {
      const title = selectedTargetInfo.title || selectedTargetInfo.process_name || selectedTargetInfo.label || "Host-selected game";
      nameEl.textContent = title;
      nameEl.title = selectedTargetInfo.pid
        ? `PID ${selectedTargetInfo.pid} — ${selectedTargetInfo.process_name || "selected application"}`
        : "The host selected this game. Process details stay private.";
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
    window.backgroundCaptureEnabled = false;
    stopBackgroundInputMirrorTimer();
    updateRoutingUI();
    return;
  }
  try {
    const res = await fetch("/api/background-capture/status", { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      backgroundCaptureEnabled = !!(data.running && data.ready);
      if (backgroundCaptureEnabled) {
        backgroundRoutingActive = true;
      }
      window.backgroundCaptureEnabled = backgroundCaptureEnabled;
    }
  } catch (_) {}
  if (backgroundCaptureEnabled) startBackgroundInputMirrorTimer();
  else stopBackgroundInputMirrorTimer();
  updateRoutingUI();
}

function startBackgroundInputMirrorTimer() {
  const connected = typeof isConnected !== "undefined" ? isConnected : false;
  if (backgroundInputMirrorTimer || !backgroundCaptureEnabled || !connected || isCloudflareRemoteSession()) return;
  backgroundInputMirrorTimer = setInterval(syncBackgroundInputMirror, 50);
}

function stopBackgroundInputMirrorTimer() {
  if (backgroundInputMirrorTimer) {
    clearInterval(backgroundInputMirrorTimer);
    backgroundInputMirrorTimer = null;
  }
  if (typeof releaseKeySource === "function") releaseKeySource(BACKGROUND_NATIVE_SOURCE);
}

function startRoutingStatusMonitor() {
  refreshTargetStatus();
  if (!isCloudflareRemoteSession()) refreshBackgroundCaptureStatus();

  if (routingStatusTimer) clearInterval(routingStatusTimer);
  const intervalMs = isCloudflareRemoteSession() ? 30000 : 10000;
  routingStatusTimer = setInterval(() => {
    if (document.hidden) return;
    refreshTargetStatus();
    if (!isCloudflareRemoteSession() && backgroundCaptureEnabled) {
      refreshBackgroundCaptureStatus();
    }
  }, intervalMs);

  if (!routingFocusBound) {
    window.addEventListener("focus", () => {
      refreshTargetStatus();
      if (!isCloudflareRemoteSession() && backgroundCaptureEnabled) {
        refreshBackgroundCaptureStatus();
      }
    });
    routingFocusBound = true;
  }
}

function updateRoutingUI() {
  const controls = document.getElementById("background-input-controls");
  const btn = document.getElementById("background-input-btn");
  const status = document.getElementById("background-input-status");
  const touchBtn = document.getElementById("touch-routing-btn");
  const focusBtn = document.getElementById("focus-target-btn");

  if (isCloudflareRemoteSession()) {
    if (controls) controls.style.display = "none";
    if (touchBtn) touchBtn.style.display = "none";
  }

  if (focusBtn) focusBtn.disabled = !selectedTargetInfo || !window.isConnected || Boolean(window.isObserverMode);

  if (btn) {
    if (backgroundRoutingActive || backgroundCaptureEnabled) {
      btn.textContent = backgroundCaptureEnabled
        ? "🪟 Native Background Capture: Active (OS-Wide)"
        : "Host Keyboard Capture: On";
      btn.classList.add("background-input-on", "routing-on");
    } else {
      btn.textContent = "Host Keyboard Capture: Off";
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

function handleTargetFocusResult(message) {
  const status = document.getElementById("focus-target-status");
  const button = document.getElementById("focus-target-btn");
  if (button) button.disabled = !selectedTargetInfo || !window.isConnected || Boolean(window.isObserverMode);
  if (!status) return;
  const messages = {
    focused: "Game focused on the host.",
    no_target: "Select a target on the host dashboard first.",
    target_closed: "The selected game is closed.",
    windows_blocked: "Windows blocked focus; click the game once on the host.",
    rate_limited: "Focus request already sent.",
    not_controller: "Only the active player can focus the game.",
    unsupported: "Host focus is unavailable on this platform.",
  };
  status.textContent = messages[message.reason] || (message.ok ? "Game focused on the host." : "Game focus request failed.");
  if (message.ok) refreshTargetStatus();
}

function requestTargetFocus() {
  const status = document.getElementById("focus-target-status");
  if (!selectedTargetInfo) {
    if (status) status.textContent = "Select a target on the host dashboard first.";
    return;
  }
  const sent = window.sendPlayerControlMessage?.({ type: "focus_target" });
  if (status) status.textContent = sent ? "Requesting host focus…" : "Connect as the active player first.";
}

async function toggleBackgroundRouting() {
  if (isCloudflareRemoteSession()) return;
  const btn = document.getElementById("background-input-btn");
  const status = document.getElementById("background-input-status");
  const isKb = ["keyboard", "hybrid"].includes(window.currentMode || "keyboard");

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
      if (!data.ok && targetState) throw new Error(data.detail || "Host keyboard capture failed");
      backgroundCaptureEnabled = !!(data.ok && data.running && data.ready);
      backgroundRoutingActive = targetState ? backgroundCaptureEnabled : false;
      window.backgroundCaptureEnabled = backgroundCaptureEnabled;
      window.backgroundRoutingActive = backgroundRoutingActive;
      if (backgroundCaptureEnabled) startBackgroundInputMirrorTimer();
      else stopBackgroundInputMirrorTimer();
    } catch (err) {
      if (status) status.textContent = "Host keyboard capture unavailable; routing was not changed.";
      return;
    } finally {
      if (btn) btn.disabled = false;
    }
  } else {
    backgroundRoutingActive = !backgroundRoutingActive;
    window.backgroundRoutingActive = backgroundRoutingActive;
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
window.startRoutingStatusMonitor = startRoutingStatusMonitor;
window.isCloudflareRemoteSession = isCloudflareRemoteSession;
window.requestTargetFocus = requestTargetFocus;
window.handleTargetFocusResult = handleTargetFocusResult;

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("focus-target-btn");
  if (button && button.dataset.bound !== "1") {
    button.dataset.bound = "1";
    button.addEventListener("click", requestTargetFocus);
  }
});
