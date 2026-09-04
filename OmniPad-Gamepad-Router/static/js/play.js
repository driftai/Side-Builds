/**
 * OmniPad Remote Player Client — Session & Input Streaming Engine.
 */

let playerWs = null, activeSlot = 1, friendName = "Player 2", roomCode = "", isConnected = false;
let packetSeq = 0, localVisualizer = null, inputLoopHandle = null, pingInterval = null;
let backgroundCaptureStatusTimer = null, backgroundInputMirrorTimer = null, backgroundHeartbeatTimer = null;
let manualDisconnect = false, reconnectTimer = null, currentMode = "keyboard";
window.currentMode = currentMode;
window.isConnected = isConnected;

const touchState = { buttons: {}, axes: { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0 } };
window.touchState = touchState;

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("code")) {
    const codeEl = document.getElementById("join-room-code");
    if (codeEl) codeEl.value = params.get("code").toUpperCase();
  }
  if (params.get("slot")) {
    const slotEl = document.getElementById("join-slot");
    if (slotEl) slotEl.value = params.get("slot");
  }
  if (params.get("name")) {
    const nameEl = document.getElementById("join-name");
    if (nameEl) nameEl.value = params.get("name");
  }

  setupEventListeners();
  if (typeof renderVirtualKeyboard === "function") renderVirtualKeyboard(window.currentKeyboardLayout || "xbox_controller");
  if (typeof loadProfiles === "function") loadProfiles();
  if (typeof refreshTargetStatus === "function") refreshTargetStatus();
  const isRemoteSession = typeof isCloudflareRemoteSession === "function" && isCloudflareRemoteSession();
  if (!isRemoteSession && typeof refreshBackgroundCaptureStatus === "function") {
    refreshBackgroundCaptureStatus();
  }
  if (typeof updateRoutingUI === "function") updateRoutingUI();

  // Relaxed background polling: remote players check every 30s; local players every 10s.
  // Polling is skipped entirely when the browser tab is hidden.
  const targetPollInterval = isRemoteSession ? 30000 : 10000;
  backgroundCaptureStatusTimer = setInterval(() => {
    if (typeof document !== "undefined" && document.hidden) return;
    if (typeof refreshTargetStatus === "function") refreshTargetStatus();
    if (!isRemoteSession && window.backgroundCaptureEnabled && typeof refreshBackgroundCaptureStatus === "function") {
      refreshBackgroundCaptureStatus();
    }
  }, targetPollInterval);

  window.addEventListener("focus", () => {
    if (typeof refreshTargetStatus === "function") refreshTargetStatus();
  });

  if (params.get("code")) setTimeout(connect, 150);
});

function setupEventListeners() {
  const joinBtn = document.getElementById("join-btn");
  if (joinBtn) joinBtn.onclick = connect;
  const dcBtn = document.getElementById("disconnect-btn");
  if (dcBtn) dcBtn.onclick = disconnect;

  const bgBtn = document.getElementById("background-input-btn");
  if (bgBtn && typeof toggleBackgroundRouting === "function") bgBtn.onclick = toggleBackgroundRouting;
  const touchRoutingBtn = document.getElementById("touch-routing-btn");
  if (touchRoutingBtn && typeof toggleBackgroundRouting === "function") touchRoutingBtn.onclick = toggleBackgroundRouting;

  ["join-name", "join-room-code", "join-slot"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); connect(); }
      });
    }
  });

  document.querySelectorAll(".mode-tab").forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll(".mode-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      switchDeviceMode(tab.dataset.mode);
    };
  });

  const vkSelect = document.getElementById("vk-layout-select");
  if (vkSelect) {
    vkSelect.onchange = (e) => {
      if (typeof releaseAllKeys === "function") releaseAllKeys();
      window.currentKeyboardLayout = e.target.value;
      if (typeof renderVirtualKeyboard === "function") renderVirtualKeyboard(window.currentKeyboardLayout);
    };
  }

  const releaseBtn = document.getElementById("vk-release-all-btn");
  if (releaseBtn) {
    releaseBtn.onclick = () => { if (typeof releaseAllKeys === "function") releaseAllKeys(); };
  }

  const profSelect = document.getElementById("profile-select");
  if (profSelect) {
    profSelect.onchange = (e) => { if (typeof selectGamepadProfile === "function") selectGamepadProfile(e.target.value); };
  }

  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab", "Escape", "F1"].includes(e.code)) e.preventDefault();
    if (typeof pressKeySource === "function") pressKeySource("physical_keyboard", e.code);
    transmitCurrentInputState();
  });

  window.addEventListener("keyup", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (typeof releaseKeySource === "function") releaseKeySource("physical_keyboard", e.code);
    transmitCurrentInputState();
  });

  window.addEventListener("blur", () => {
    if (window.mouseCameraPopout && !window.mouseCameraPopout.closed) return;
    if (typeof releaseKeySource === "function") releaseKeySource("physical_keyboard");
    if (window.pointerKeyMap) {
      for (const [pointerId, code] of Array.from(window.pointerKeyMap.entries())) {
        if (typeof releaseKeySource === "function") releaseKeySource(`pointer_${pointerId}`, code);
        window.pointerKeyMap.delete(pointerId);
      }
    }
  });
}

function switchDeviceMode(mode) {
  if (typeof releaseAllKeys === "function") releaseAllKeys();
  if (typeof window.resetTouchAll === "function") {
    window.resetTouchAll();
  } else if (window.touchState) {
    Object.keys(window.touchState.buttons).forEach(k => window.touchState.buttons[k] = false);
    Object.keys(window.touchState.axes).forEach(k => window.touchState.axes[k] = 0);
  }

  currentMode = mode;
  window.currentMode = mode;
  const secKb = document.getElementById("section-keyboard");
  const secGp = document.getElementById("section-gamepad");
  const secTc = document.getElementById("section-touch");
  const padNameBadge = document.getElementById("detected-pad-name");

  if (secKb) secKb.style.display = "none";
  if (secGp) secGp.style.display = "none";
  if (secTc) secTc.style.display = "none";

  document.querySelectorAll(".mode-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.mode === mode);
  });

  if (mode === "keyboard") {
    if (secKb) secKb.style.display = "flex";
    if (padNameBadge) padNameBadge.textContent = "Keyboard Active";
  } else if (mode === "gamepad") {
    if (secGp) secGp.style.display = "flex";
    if (padNameBadge) padNameBadge.textContent = "Gamepad Mode";
  } else if (mode === "touch") {
    if (secTc) secTc.style.display = "flex";
    if (padNameBadge) padNameBadge.textContent = "Touchscreen Mode";
    if (typeof window.applyTouchLayout === "function") {
      let saved = "classic_landscape";
      try { saved = localStorage.getItem("omnipad.touchLayout") || saved; } catch (_) {}
      window.applyTouchLayout(saved);
    }
  }
}

function connect() {
  manualDisconnect = false;
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }

  friendName = (document.getElementById("join-name")?.value.trim()) || "Player 2";
  roomCode = (document.getElementById("join-room-code")?.value.trim().toUpperCase()) || "";
  activeSlot = parseInt(document.getElementById("join-slot")?.value, 10) || 1;
  if (!roomCode) {
    alert("Please enter the pairing room code shown on the host dashboard.");
    return;
  }

  const btn = document.getElementById("join-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Connecting to Host..."; }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/player`;

  playerWs = new WebSocket(wsUrl);

  playerWs.onopen = () => {
    playerWs.send(JSON.stringify({ type: "join", slot_id: activeSlot, name: friendName, code: roomCode }));
  };

  window.isObserverMode = false;

  playerWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "joined" || msg.type === "join_ack") {
        window.isObserverMode = !!msg.observer;
        handleJoined(msg);
      } else if (msg.type === "demoted_to_observer") {
        window.isObserverMode = true;
        handleDemotedToObserver(msg);
      } else if (msg.type === "error") {
        if (!isConnected) {
          alert(`Connection error: ${msg.message || msg.error || "Failed to connect."}`);
          disconnect();
        }
      } else if (msg.type === "pong") {
        handlePong(msg);
      }
    } catch (e) {
      console.error("Failed to parse server message:", e);
    }
  };

  playerWs.onclose = () => {
    isConnected = false;
    window.isConnected = false;
    if (!manualDisconnect) {
      const statusBadge = document.getElementById("status-badge");
      if (statusBadge) {
        statusBadge.className = "badge badge-warning";
        statusBadge.innerHTML = `<span class="status-dot"></span> Reconnecting to Host...`;
      }
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          if (!manualDisconnect && !isConnected) connect();
        }, 1200);
      }
    } else {
      disconnect();
    }
  };
}

function handleDemotedToObserver(msg) {
  window.isObserverMode = true;
  const statusBadge = document.getElementById("status-badge");
  if (statusBadge) {
    statusBadge.className = "badge badge-info";
    statusBadge.innerHTML = `<span class="status-dot"></span> Live Monitor (Observing ${msg.title || "Player 2"})`;
  }
}

function handleJoined(msg) {
  isConnected = true;
  window.isConnected = true;
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  window.isObserverMode = !!msg.observer;
  const joinCard = document.getElementById("join-card");
  if (joinCard) joinCard.style.display = "none";
  const arena = document.getElementById("controller-arena");
  if (arena) arena.style.display = "flex";
  const dcBtn = document.getElementById("disconnect-btn");
  if (dcBtn) dcBtn.style.display = "inline-flex";

  const statusBadge = document.getElementById("status-badge");
  if (statusBadge) {
    if (msg.observer) {
      statusBadge.className = "badge badge-info";
      statusBadge.innerHTML = `<span class="status-dot"></span> Live Monitor (Observing ${msg.title || "Player 2"})`;
    } else {
      statusBadge.className = "badge badge-green";
      statusBadge.innerHTML = `<span class="status-dot"></span> Connected`;
    }
  }

  const slotBadge = document.getElementById("slot-indicator-badge");
  if (slotBadge) slotBadge.textContent = `Slot ${msg.slot_id} (${friendName})`;

  const modeSelect = document.getElementById("join-mode");
  let desiredMode = modeSelect ? modeSelect.value : "auto";
  if (desiredMode === "auto") {
    const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints && navigator.maxTouchPoints > 0) || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    desiredMode = isTouchDevice ? "touch" : "keyboard";
  }
  switchDeviceMode(desiredMode);
  if (typeof releaseAllKeys === "function") releaseAllKeys();
  if (typeof window.resetTouchAll === "function") window.resetTouchAll();

  if (!localVisualizer && typeof GamepadVisualizer !== "undefined") {
    localVisualizer = new GamepadVisualizer("local-viz-container", "player-viz");
  }

  if (pingInterval) clearInterval(pingInterval);
  pingInterval = setInterval(sendPing, 1000);
  sendPing();

  startInputLoop();
}

function disconnect() {
  manualDisconnect = true;
  isConnected = false;
  window.isConnected = false;
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  if (backgroundHeartbeatTimer) { clearInterval(backgroundHeartbeatTimer); backgroundHeartbeatTimer = null; }
  if (typeof stopBackgroundInputMirrorTimer === "function") stopBackgroundInputMirrorTimer();
  if (typeof releaseKeySource === "function") releaseKeySource(window.BACKGROUND_NATIVE_SOURCE || "background_native");
  if (inputLoopHandle) cancelAnimationFrame(inputLoopHandle);
  if (pingInterval) clearInterval(pingInterval);

  if (playerWs && playerWs.readyState === WebSocket.OPEN) {
    try { playerWs.send(JSON.stringify({ type: "leave" })); playerWs.close(); } catch (e) {}
  }
  playerWs = null;
  if (typeof releaseAllKeys === "function") releaseAllKeys();

  const joinCard = document.getElementById("join-card");
  if (joinCard) joinCard.style.display = "flex";
  const arena = document.getElementById("controller-arena");
  if (arena) arena.style.display = "none";
  const joinBtn = document.getElementById("join-btn");
  if (joinBtn) { joinBtn.disabled = false; joinBtn.textContent = "Connect to Host"; }
  const statusBadge = document.getElementById("status-badge");
  if (statusBadge) {
    statusBadge.className = "badge badge-muted";
    statusBadge.innerHTML = `<span class="status-dot"></span> Disconnected`;
  }
}

function sendPing() {
  if (playerWs && playerWs.readyState === WebSocket.OPEN) {
    playerWs.send(JSON.stringify({ type: "ping", t: performance.now() }));
  }
}

function handlePong(msg) {
  const rtt = Math.max(1, Math.round(performance.now() - msg.t));
  const pingEl = document.getElementById("ping-val");
  if (pingEl) {
    pingEl.textContent = `${rtt} ms`;
    pingEl.className = rtt < 30 ? "ping-green" : (rtt < 80 ? "ping-yellow" : "ping-red");
  }
}

function startInputLoop() {
  let hadActiveInput = false;
  let lastIdlePacketTime = 0;

  function loop() {
    if (!isConnected) return;

    const state = typeof captureState === "function" ? captureState() : { buttons: {}, axes: {} };
    const activeKeysSet = window.activeKeys || new Set();
    const hasActiveInput = Object.values(state.buttons).some(Boolean) ||
                          (state.axes && (Math.abs(state.axes.lx || 0) > 0.02 || Math.abs(state.axes.ly || 0) > 0.02 || Math.abs(state.axes.rx || 0) > 0.02 || Math.abs(state.axes.ry || 0) > 0.02 || (state.axes.lt || 0) > 0.02 || (state.axes.rt || 0) > 0.02)) ||
                          activeKeysSet.size > 0;

    const now = performance.now();
    if (!hasActiveInput && !hadActiveInput) {
      if (now - lastIdlePacketTime < 300) {
        inputLoopHandle = requestAnimationFrame(loop);
        return;
      }
      lastIdlePacketTime = now;
    }
    hadActiveInput = hasActiveInput;

    if (playerWs && playerWs.readyState === WebSocket.OPEN) {
      packetSeq++;
      playerWs.send(JSON.stringify({
        type: "input",
        seq: packetSeq,
        input_surface: currentMode,
        mapping_profile: window.currentGamepadProfile || "universal",
        background_routing: typeof isRoutingActive === "function" ? isRoutingActive() : true,
        buttons: state.buttons,
        axes: state.axes,
        key_codes: Array.from(activeKeysSet),
        client_time: performance.now()
      }));
    }

    if (localVisualizer && currentMode === "gamepad" && hasActiveInput) {
      localVisualizer.update(state);
    }

    inputLoopHandle = requestAnimationFrame(loop);
  }
  inputLoopHandle = requestAnimationFrame(loop);
}

function transmitCurrentInputState() {
  if (!isConnected) return;
  const state = typeof captureState === "function" ? captureState() : { buttons: {}, axes: {} };
  const activeKeysSet = window.activeKeys || new Set();
  if (playerWs && playerWs.readyState === WebSocket.OPEN) {
    packetSeq++;
    playerWs.send(JSON.stringify({
      type: "input",
      seq: packetSeq,
      input_surface: currentMode,
      mapping_profile: window.currentGamepadProfile || "universal",
      background_routing: typeof isRoutingActive === "function" ? isRoutingActive() : true,
      buttons: state.buttons,
      axes: state.axes,
      key_codes: Array.from(activeKeysSet),
      client_time: performance.now()
    }));
  }
}

window.connect = connect;
window.disconnect = disconnect;
window.transmitCurrentInputState = transmitCurrentInputState;
