/**
 * OmniPad — bounded mouse/touch camera control for the right stick.
 * Motion is coalesced to animation frames; neutral releases transmit immediately.
 */

(() => {
  const state = { rx: 0, ry: 0, active: false, locked: false };
  window.mouseCameraState = state;

  let centerArmed = false;
  let isFullscreen = false;
  let popoutWindow = null;
  let activePointerId = null;
  let lockedFrameHandle = null;
  let transmitFrameHandle = null;
  let targetRx = 0;
  let targetRy = 0;
  let isClickHeld = false;
  let mouseSensitivity = 20;
  let invertX = false;
  let invertY = false;
  try { mouseSensitivity = parseInt(localStorage.getItem("omnipad.mouseSensitivity") || "20", 10); } catch (_) {}
  try {
    invertX = localStorage.getItem("omnipad.mouseInvertX") === "1";
    invertY = localStorage.getItem("omnipad.mouseInvertY") === "1";
  } catch (_) {}
  if (!Number.isFinite(mouseSensitivity)) mouseSensitivity = 20;
  mouseSensitivity = Math.max(1, Math.min(200, mouseSensitivity));

  function getSensMultiplier() {
    return mouseSensitivity / 100;
  }

  function notifyShared(patch, options) {
    if (options?.broadcast === false) return;
    window.dispatchEvent(new CustomEvent("omnipad:shared-config-change", { detail: { patch } }));
  }

  function setSensitivity(value, options = {}) {
    mouseSensitivity = Math.max(1, Math.min(200, parseInt(value, 10) || 20));
    try { localStorage.setItem("omnipad.mouseSensitivity", mouseSensitivity); } catch (_) {}
    updateSensitivityUI();
    notifyShared({ mouse_sensitivity: mouseSensitivity }, options);
  }

  function updateSensitivityUI() {
    const slider = document.getElementById("mouse-sens-slider");
    const value = document.getElementById("mouse-sens-val");
    if (slider) slider.value = mouseSensitivity;
    if (value) value.textContent = `${mouseSensitivity}%`;
    const invertXInput = document.getElementById("mouse-invert-x");
    const invertYInput = document.getElementById("mouse-invert-y");
    if (invertXInput) invertXInput.checked = invertX;
    if (invertYInput) invertYInput.checked = invertY;
  }

  function setDirections(nextInvertX, nextInvertY, options = {}) {
    reset(true);
    invertX = Boolean(nextInvertX);
    invertY = Boolean(nextInvertY);
    try {
      localStorage.setItem("omnipad.mouseInvertX", invertX ? "1" : "0");
      localStorage.setItem("omnipad.mouseInvertY", invertY ? "1" : "0");
    } catch (_) {}
    updateSensitivityUI();
    notifyShared({ mouse_invert_x: invertX, mouse_invert_y: invertY }, options);
  }

  function transmitMouseNow() {
    if (transmitFrameHandle) cancelAnimationFrame(transmitFrameHandle);
    transmitFrameHandle = null;
    window.transmitCurrentInputState?.();
  }

  function scheduleMouseTransmit() {
    if (transmitFrameHandle) return;
    transmitFrameHandle = requestAnimationFrame(() => {
      transmitFrameHandle = null;
      window.transmitCurrentInputState?.();
    });
  }

  function updateVisuals() {
    const left = `${((state.rx + 1) / 2) * 100}%`;
    const top = `${((-state.ry + 1) / 2) * 100}%`;
    for (const id of ["mouse-camera-center", "mouse-camera-puck"]) {
      const element = document.getElementById(id);
      if (element) { element.style.left = left; element.style.top = top; }
    }
  }

  function renderRemoteState(rx, ry) {
    if (state.active || state.locked || activePointerId !== null) return;
    const safeRx = Math.max(-1, Math.min(1, Number(rx) || 0));
    const safeRy = Math.max(-1, Math.min(1, Number(ry) || 0));
    const pad = document.getElementById("mouse-camera-pad");
    const left = `${((safeRx + 1) / 2) * 100}%`;
    const top = `${((-safeRy + 1) / 2) * 100}%`;
    for (const id of ["mouse-camera-center", "mouse-camera-puck"]) {
      const element = document.getElementById(id);
      if (element) { element.style.left = left; element.style.top = top; }
    }
    pad?.classList.toggle("remote-active", Math.hypot(safeRx, safeRy) > 0.04);
  }

  function updateLabel(text) {
    const label = document.querySelector("#mouse-camera-pad .mouse-camera-label");
    if (label) label.textContent = text;
  }

  function reset(emit = true) {
    const wasActive = state.active || Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    state.rx = state.ry = targetRx = targetRy = 0;
    state.active = false;
    centerArmed = false;
    activePointerId = null;
    isClickHeld = false;
    const pad = document.getElementById("mouse-camera-pad");
    if (pad) {
      pad.classList.remove("active", "center-armed");
      updateVisuals();
      if (!state.locked) updateLabel("🖱️ CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)");
    }
    if (emit && wasActive) transmitMouseNow();
  }

  function updateLockedFrame() {
    if (!state.locked) return;
    if (!isClickHeld) {
      const beforeRx = targetRx, beforeRy = targetRy;
      targetRx *= 0.68;
      targetRy *= 0.68;
      if (Math.abs(targetRx) < 0.003) targetRx = 0;
      if (Math.abs(targetRy) < 0.003) targetRy = 0;
      state.rx = targetRx;
      state.ry = targetRy;
      if (beforeRx !== targetRx || beforeRy !== targetRy) scheduleMouseTransmit();
    }
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    updateVisuals();
    lockedFrameHandle = requestAnimationFrame(updateLockedFrame);
  }

  function handleLockedMouseMove(event) {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad || !state.locked || document.pointerLockElement !== pad) return;
    if (!["keyboard", "hybrid"].includes(window.currentMode || "keyboard")) return;

    if (event.buttons !== undefined) {
      const isDown = event.buttons > 0;
      if (isDown !== isClickHeld) {
        isClickHeld = isDown;
        if (!isDown) targetRx = targetRy = 0;
        updateLabel(isDown
          ? "🎯 CLICK-DRAG SUSTAIN AIMING (RELEASE TO CENTER)"
          : "🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
      }
    }

    const sensitivity = (isClickHeld ? 0.0025 : 0.004) * getSensMultiplier();
    const directionX = invertX ? -1 : 1;
    const directionY = invertY ? 1 : -1;
    targetRx = Math.max(-1, Math.min(1, targetRx + (event.movementX || 0) * sensitivity * directionX));
    targetRy = Math.max(-1, Math.min(1, targetRy + (event.movementY || 0) * sensitivity * directionY));
    state.rx = targetRx;
    state.ry = targetRy;
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    updateVisuals();
    scheduleMouseTransmit();
  }

  function handleBoundedPointerMove(event) {
    if (state.locked || activePointerId !== event.pointerId) return;
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad || !["keyboard", "hybrid"].includes(window.currentMode || "keyboard")) return;
    const rect = pad.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const radius = Math.max(1, Math.min(rect.width, rect.height) / 2);
    let normalizedX = (event.clientX - (rect.left + rect.width / 2)) / radius;
    let normalizedY = (event.clientY - (rect.top + rect.height / 2)) / radius;
    const magnitude = Math.hypot(normalizedX, normalizedY);
    if (magnitude > 1) {
      normalizedX /= magnitude;
      normalizedY /= magnitude;
    }
    if (!centerArmed) {
      if (Math.hypot(normalizedX, normalizedY) > 0.28) {
        updateLabel("🎯 DRAG THROUGH CENTER TO ARM AIMING");
        return;
      }
      centerArmed = true;
      pad.classList.add("center-armed");
    }

    // Fifty percent spans the full pad. Lower settings reduce the bounded
    // output range as well as pointer-lock delta sensitivity.
    const boxScale = Math.min(4, mouseSensitivity / 50);
    const scaledX = Math.max(-1, Math.min(1, normalizedX * boxScale));
    const scaledY = Math.max(-1, Math.min(1, normalizedY * boxScale));
    const directedX = scaledX * (invertX ? -1 : 1);
    const directedY = scaledY * (invertY ? 1 : -1);
    state.rx = Math.abs(directedX) < 0.05 ? 0 : directedX;
    state.ry = Math.abs(directedY) < 0.05 ? 0 : directedY;
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    pad.classList.toggle("active", state.active);
    updateVisuals();
    updateLabel(state.active ? "🎯 AIMING ACTIVE" : "🖱️ DRAGGING IN CENTER");
    scheduleMouseTransmit();
  }

  function onPointerLockChange() {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad) return;
    const locked = document.pointerLockElement === pad;
    state.locked = locked;
    activePointerId = null;
    if (locked) {
      state.rx = state.ry = targetRx = targetRy = 0;
      centerArmed = false;
      isClickHeld = false;
      pad.classList.add("locked");
      pad.classList.remove("active", "center-armed");
      updateLabel("🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
      document.addEventListener("mousemove", handleLockedMouseMove);
      if (lockedFrameHandle) cancelAnimationFrame(lockedFrameHandle);
      lockedFrameHandle = requestAnimationFrame(updateLockedFrame);
      return;
    }
    if (lockedFrameHandle) cancelAnimationFrame(lockedFrameHandle);
    lockedFrameHandle = null;
    document.removeEventListener("mousemove", handleLockedMouseMove);
    pad.classList.remove("locked");
    reset(true);
  }

  function toggleFullscreen(forceState) {
    const card = document.getElementById("mouse-camera-card");
    const button = document.getElementById("mouse-camera-fullscreen-btn");
    if (!card) return;
    isFullscreen = typeof forceState === "boolean" ? forceState : !isFullscreen;
    card.classList.toggle("fullscreen-mode", isFullscreen);
    if (button) button.textContent = isFullscreen ? "✕ Exit Fullscreen" : "⛶ Fullscreen";
    if (isFullscreen) document.getElementById("mouse-camera-pad")?.requestPointerLock?.();
  }

  function openPopoutWindow() {
    if (popoutWindow && !popoutWindow.closed) { popoutWindow.focus(); return; }
    popoutWindow = window.open("", "OmniPadMouseCamera", "width=720,height=540,menubar=no,toolbar=no,location=no,status=no");
    if (!popoutWindow) { alert("Allow popups for OmniPad to use the detached camera."); return; }
    window.mouseCameraPopout = popoutWindow;
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>OmniPad — Detached Camera</title><style>*{box-sizing:border-box}body{margin:0;background:#0b0e14;color:#fff;font-family:system-ui;height:100vh;display:flex;flex-direction:column;padding:12px;overflow:hidden;user-select:none}.head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.pad{flex:1;position:relative;border:2px dashed #387080;border-radius:12px;background:#101721;cursor:crosshair;overflow:hidden}.pad.locked{border-style:solid;border-color:#00e5ff}.dot{position:absolute;left:50%;top:50%;width:40px;height:40px;transform:translate(-50%,-50%);border:2px solid #00e5ff;border-radius:50%}.label{position:absolute;bottom:16px;left:50%;transform:translateX(-50%);font-size:.8rem;color:#00e5ff;font-weight:700;white-space:nowrap}</style></head><body><div class="head"><strong>🖱️ OmniPad Detached Camera</strong><label>Sens <input type="range" id="sens" min="1" max="200" value="${mouseSensitivity}"> <span id="val">${mouseSensitivity}%</span></label></div><div class="pad" id="pad"><div class="dot" id="dot"></div><div class="label" id="label">CLICK TO LOCK CAMERA</div></div><script>
const pad=document.getElementById('pad'),dot=document.getElementById('dot'),label=document.getElementById('label'),slider=document.getElementById('sens'),val=document.getElementById('val');let rx=0,ry=0,targetRx=0,targetRy=0,down=false,sens=${mouseSensitivity},frame=0,sendFrame=0;function sync(force=false){const active=Math.abs(rx)>.01||Math.abs(ry)>.01;if(!window.opener?.mouseCameraState)return;window.opener.mouseCameraState.rx=rx;window.opener.mouseCameraState.ry=ry;window.opener.mouseCameraState.active=active;if(force){if(sendFrame)cancelAnimationFrame(sendFrame);sendFrame=0;window.opener.transmitCurrentInputState?.();return}if(!sendFrame)sendFrame=requestAnimationFrame(()=>{sendFrame=0;window.opener?.transmitCurrentInputState?.()})}function render(){dot.style.left=((rx+1)/2*100)+'%';dot.style.top=((-ry+1)/2*100)+'%'}function loop(){if(!down){targetRx*=.68;targetRy*=.68;if(Math.abs(targetRx)<.003)targetRx=0;if(Math.abs(targetRy)<.003)targetRy=0;rx=targetRx;ry=targetRy;sync();render()}frame=requestAnimationFrame(loop)}slider.oninput=e=>{sens=Math.max(1,Math.min(200,parseInt(e.target.value)||20));val.textContent=sens+'%';window.opener?.setMouseSensitivity?.(sens)};pad.onpointerdown=()=>{if(document.pointerLockElement!==pad)pad.requestPointerLock?.()};document.addEventListener('pointerlockchange',()=>{const locked=document.pointerLockElement===pad;pad.classList.toggle('locked',locked);label.textContent=locked?'CAMERA LOCKED — MOVE MOUSE':'CLICK TO LOCK CAMERA';targetRx=targetRy=rx=ry=0;down=false;sync(true);render()});document.addEventListener('mousemove',e=>{if(document.pointerLockElement!==pad)return;down=e.buttons>0;const scale=(down ? 0.0025 : 0.004)*(sens/100),prefs=window.opener?.OmniPadMouseCameraPreferences?.get?.()||{},dx=prefs.invertX?-1:1,dy=prefs.invertY?1:-1;targetRx=Math.max(-1,Math.min(1,targetRx+(e.movementX||0)*scale*dx));targetRy=Math.max(-1,Math.min(1,targetRy+(e.movementY||0)*scale*dy));rx=targetRx;ry=targetRy;sync();render()});window.addEventListener('keydown',e=>{window.opener?.pressKeySource?.('popout_keyboard',e.code);window.opener?.transmitCurrentInputState?.()},true);window.addEventListener('keyup',e=>{window.opener?.releaseKeySource?.('popout_keyboard',e.code);window.opener?.transmitCurrentInputState?.()},true);window.addEventListener('beforeunload',()=>{cancelAnimationFrame(frame);window.opener?.releaseKeySource?.('popout_keyboard');rx=ry=0;sync(true)});frame=requestAnimationFrame(loop);
<\/script></body></html>`;
    popoutWindow.document.write(html);
    popoutWindow.document.close();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad) return;
    updateSensitivityUI();
    document.getElementById("mouse-sens-slider")?.addEventListener("input", event => setSensitivity(event.target.value));
    document.getElementById("mouse-invert-x")?.addEventListener("change", event => setDirections(event.target.checked, invertY));
    document.getElementById("mouse-invert-y")?.addEventListener("change", event => setDirections(invertX, event.target.checked));
    const fullscreenButton = document.getElementById("mouse-camera-fullscreen-btn");
    if (fullscreenButton) fullscreenButton.onclick = () => toggleFullscreen();
    const popoutButton = document.getElementById("mouse-camera-popout-btn");
    if (popoutButton) popoutButton.onclick = openPopoutWindow;

    window.addEventListener("contextmenu", event => { if (state.locked) event.preventDefault(); }, true);
    pad.addEventListener("pointerdown", event => {
      if (!["keyboard", "hybrid"].includes(window.currentMode || "keyboard")) return;
      activePointerId = event.pointerId;
      try { pad.setPointerCapture(event.pointerId); } catch (_) {}
      if (event.pointerType === "mouse" && pad.requestPointerLock) {
        try { pad.requestPointerLock(); } catch (_) {}
      }
      if (!state.locked) handleBoundedPointerMove(event);
    });
    pad.addEventListener("pointermove", handleBoundedPointerMove);
    const releasePointer = event => {
      if (!state.locked && activePointerId === event.pointerId) reset(true);
    };
    pad.addEventListener("pointerup", releasePointer);
    pad.addEventListener("pointercancel", releasePointer);
    pad.addEventListener("pointerleave", event => {
      if (!state.locked && !pad.hasPointerCapture?.(event.pointerId)) releasePointer(event);
    });

    window.addEventListener("mousedown", event => {
      if (!state.locked) return;
      if (event.button === 2) event.preventDefault();
      isClickHeld = true;
      updateLabel("🎯 CLICK-DRAG SUSTAIN AIMING (RELEASE TO CENTER)");
    }, true);
    window.addEventListener("mouseup", () => {
      if (!isClickHeld) return;
      isClickHeld = false;
      targetRx = targetRy = 0;
      if (state.locked) updateLabel("🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
    }, true);

    document.addEventListener("pointerlockchange", onPointerLockChange);
    document.addEventListener("pointerlockerror", () => {
      state.locked = false;
      pad.classList.remove("locked");
      reset(true);
    });
    window.addEventListener("keydown", event => {
      if (event.key === "Escape" && isFullscreen) toggleFullscreen(false);
    });
    window.addEventListener("blur", () => {
      if (document.pointerLockElement === pad) document.exitPointerLock?.();
      reset(true);
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) return;
      if (document.pointerLockElement === pad) document.exitPointerLock?.();
      reset(true);
    });
  });

  window.toggleMouseCameraFullscreen = toggleFullscreen;
  window.openMouseCameraPopout = openPopoutWindow;
  window.setMouseSensitivity = setSensitivity;
  window.resetMouseCameraState = reset;
  window.renderRemoteMouseCameraState = renderRemoteState;
  window.OmniPadMouseCameraPreferences = {
    get: () => ({ sensitivity: mouseSensitivity, invertX, invertY }),
    setDirections,
  };
})();
