/**
 * OmniPad — Bounded Mouse Camera Pad with Pointer Lock, Fullscreen, Popout & Sensitivity Slider.
 * Maps mouse movement or pointer coordinates to the controller right stick.
 */

(() => {
  const state = { rx: 0, ry: 0, active: false, locked: false };
  window.mouseCameraState = state;

  let centerArmed = false;
  let isFullscreen = false;
  let popoutWindow = null;
  let activeTouchPointerId = null;
  let lockedFrameHandle = null;
  let transmitFrameHandle = null;
  let targetRx = 0;
  let targetRy = 0;
  let isClickHeld = false;
  let mouseSensitivity = parseInt(localStorage.getItem("omnipad.mouseSensitivity") || "20", 10);

  if (!Number.isFinite(mouseSensitivity)) mouseSensitivity = 20;
  mouseSensitivity = Math.max(1, Math.min(200, mouseSensitivity));

  function getSensMultiplier() {
    return mouseSensitivity / 100;
  }

  function setSensitivity(val) {
    mouseSensitivity = Math.max(1, Math.min(200, parseInt(val, 10) || 20));
    try { localStorage.setItem("omnipad.mouseSensitivity", mouseSensitivity); } catch (_) {}
    updateSensitivityUI();
  }

  function updateSensitivityUI() {
    const slider = document.getElementById("mouse-sens-slider");
    const valEl = document.getElementById("mouse-sens-val");
    if (slider) slider.value = mouseSensitivity;
    if (valEl) valEl.textContent = `${mouseSensitivity}%`;
  }

  function transmitMouseNow() {
    if (transmitFrameHandle) {
      cancelAnimationFrame(transmitFrameHandle);
      transmitFrameHandle = null;
    }
    if (typeof window.transmitCurrentInputState === "function") {
      window.transmitCurrentInputState();
    }
  }

  function scheduleMouseTransmit() {
    if (transmitFrameHandle) return;
    transmitFrameHandle = requestAnimationFrame(() => {
      transmitFrameHandle = null;
      if (typeof window.transmitCurrentInputState === "function") {
        window.transmitCurrentInputState();
      }
    });
  }

  function updateVisuals() {
    const center = document.getElementById("mouse-camera-center");
    const puck = document.getElementById("mouse-camera-puck");
    const left = `${((state.rx + 1) / 2) * 100}%`;
    const top = `${((-state.ry + 1) / 2) * 100}%`;
    if (center) { center.style.left = left; center.style.top = top; }
    if (puck) { puck.style.left = left; puck.style.top = top; }
  }

  function reset(emit = true) {
    const wasActive = state.active || Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    state.rx = 0;
    state.ry = 0;
    targetRx = 0;
    targetRy = 0;
    isClickHeld = false;
    state.active = false;
    centerArmed = false;
    activeTouchPointerId = null;
    const pad = document.getElementById("mouse-camera-pad");
    if (pad) {
      pad.classList.remove("active", "center-armed");
      updateVisuals();
      if (!state.locked) updateLabel("🖱️ CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)");
    }
    if (emit && wasActive) transmitMouseNow();
  }

  function updateLabel(text) {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad) return;
    const label = pad.querySelector(".mouse-camera-label");
    if (label) label.textContent = text;
  }

  function updateLockedFrame() {
    if (!state.locked) return;

    if (!isClickHeld) {
      const beforeRx = targetRx;
      const beforeRy = targetRy;
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
    if ((window.currentMode || "keyboard") !== "keyboard") return;

    if (event.buttons !== undefined) {
      const isDown = event.buttons > 0;
      if (isDown && !isClickHeld) {
        isClickHeld = true;
        updateLabel("🎯 CLICK-DRAG SUSTAIN AIMING (RELEASE TO CENTER)");
      } else if (!isDown && isClickHeld) {
        isClickHeld = false;
        targetRx = 0;
        targetRy = 0;
        updateLabel("🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
      }
    }

    const sens = (isClickHeld ? 0.0025 : 0.004) * getSensMultiplier();
    targetRx = Math.max(-1, Math.min(1, targetRx + (event.movementX || 0) * sens));
    targetRy = Math.max(-1, Math.min(1, targetRy - (event.movementY || 0) * sens));
    state.rx = targetRx;
    state.ry = targetRy;
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    updateVisuals();
    scheduleMouseTransmit();
  }

  function handleUnlockedPointerMove(event) {
    if (state.locked) return;
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad || (window.currentMode || "keyboard") !== "keyboard") return;
    const rect = pad.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const clampedX = Math.max(rect.left, Math.min(rect.right, event.clientX));
    const clampedY = Math.max(rect.top, Math.min(rect.bottom, event.clientY));
    const nx = ((clampedX - rect.left) / rect.width) * 2 - 1;
    const ny = ((clampedY - rect.top) / rect.height) * 2 - 1;
    const distFromCenter = Math.hypot(nx, ny);

    if (!centerArmed) {
      if (distFromCenter <= 0.28) {
        centerArmed = true;
        pad.classList.add("center-armed");
      } else {
        updateLabel("🎯 DRAG THROUGH CENTER TO ARM AIMING");
        return;
      }
    }

    // At 50% the full pad reaches full stick range. Lower values genuinely
    // reduce the box sensitivity instead of only changing pointer-lock mode.
    const boxScale = Math.min(4, mouseSensitivity / 50);
    const scaledX = Math.max(-1, Math.min(1, nx * boxScale));
    const scaledY = Math.max(-1, Math.min(1, ny * boxScale));
    const deadzone = 0.05;
    state.rx = Math.abs(scaledX) < deadzone ? 0 : scaledX;
    state.ry = Math.abs(scaledY) < deadzone ? 0 : -scaledY;
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    pad.classList.toggle("active", state.active);
    updateVisuals();
    updateLabel(state.active ? "🎯 AIMING ACTIVE" : "🖱️ DRAGGING IN CENTER");
    scheduleMouseTransmit();
  }

  function onPointerLockChange() {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad) return;

    if (document.pointerLockElement === pad) {
      state.locked = true;
      centerArmed = false;
      activeTouchPointerId = null;
      targetRx = 0;
      targetRy = 0;
      isClickHeld = false;
      pad.classList.add("locked");
      pad.classList.remove("active", "center-armed");
      updateLabel("🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
      document.addEventListener("mousemove", handleLockedMouseMove);
      if (lockedFrameHandle) cancelAnimationFrame(lockedFrameHandle);
      lockedFrameHandle = requestAnimationFrame(updateLockedFrame);
    } else {
      state.locked = false;
      if (lockedFrameHandle) cancelAnimationFrame(lockedFrameHandle);
      lockedFrameHandle = null;
      document.removeEventListener("mousemove", handleLockedMouseMove);
      pad.classList.remove("locked");
      reset(true);
    }
  }

  function toggleFullscreen(forceState) {
    const card = document.getElementById("mouse-camera-card");
    const btn = document.getElementById("mouse-camera-fullscreen-btn");
    if (!card) return;

    isFullscreen = typeof forceState === "boolean" ? forceState : !isFullscreen;
    card.classList.toggle("fullscreen-mode", isFullscreen);
    if (btn) btn.textContent = isFullscreen ? "✕ Exit Fullscreen" : "⛶ Fullscreen";

    const pad = document.getElementById("mouse-camera-pad");
    if (isFullscreen && pad && typeof pad.requestPointerLock === "function") {
      try { pad.requestPointerLock(); } catch (_) {}
    }
  }

  function openPopoutWindow() {
    if (popoutWindow && !popoutWindow.closed) {
      popoutWindow.focus();
      return;
    }
    popoutWindow = window.open("", "OmniPadMouseCamera", "width=720,height=540,menubar=no,toolbar=no,location=no,status=no");
    if (!popoutWindow) {
      alert("Pop-out window was blocked by browser. Please allow popups for OmniPad.");
      return;
    }
    window.mouseCameraPopout = popoutWindow;

    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>OmniPad — Detached Camera</title><style>*{box-sizing:border-box}body{margin:0;background:#0b0e14;color:#fff;font-family:system-ui;height:100vh;display:flex;flex-direction:column;padding:12px;overflow:hidden;user-select:none}.head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.pad{flex:1;position:relative;border:2px dashed #387080;border-radius:12px;background:#101721;cursor:crosshair;overflow:hidden}.pad.locked{border-style:solid;border-color:#00e5ff}.dot{position:absolute;left:50%;top:50%;width:40px;height:40px;transform:translate(-50%,-50%);border:2px solid #00e5ff;border-radius:50%}.label{position:absolute;bottom:16px;left:50%;transform:translateX(-50%);font-size:.8rem;color:#00e5ff;font-weight:700;white-space:nowrap}</style></head><body><div class="head"><strong>🖱️ OmniPad Detached Camera</strong><label>Sens <input type="range" id="sens" min="1" max="200" value="${mouseSensitivity}"> <span id="val">${mouseSensitivity}%</span></label></div><div class="pad" id="pad"><div class="dot" id="dot"></div><div class="label" id="label">CLICK TO LOCK CAMERA</div></div><script>
const pad=document.getElementById('pad'),dot=document.getElementById('dot'),label=document.getElementById('label'),slider=document.getElementById('sens'),val=document.getElementById('val');let rx=0,ry=0,targetRx=0,targetRy=0,down=false,sens=${mouseSensitivity},frame=0,prevRx=0,prevRy=0;function sync(force=false){const active=Math.abs(rx)>.01||Math.abs(ry)>.01;if(window.opener&&window.opener.mouseCameraState){window.opener.mouseCameraState.rx=rx;window.opener.mouseCameraState.ry=ry;window.opener.mouseCameraState.active=active;if(force||Math.abs(rx-prevRx)>.01||Math.abs(ry-prevRy)>.01||(prevRx!==0&&rx===0)||(prevRy!==0&&ry===0)){prevRx=rx;prevRy=ry;if(typeof window.opener.transmitCurrentInputState==='function')window.opener.transmitCurrentInputState();}}}function render(){dot.style.left=((rx+1)/2*100)+'%';dot.style.top=((-ry+1)/2*100)+'%'}function loop(){if(!down){targetRx*=.68;targetRy*=.68;if(Math.abs(targetRx)<.003)targetRx=0;if(Math.abs(targetRy)<.003)targetRy=0;rx=targetRx;ry=targetRy;sync();render()}frame=requestAnimationFrame(loop)}slider.oninput=e=>{sens=Math.max(1,Math.min(200,parseInt(e.target.value)||20));val.textContent=sens+'%';if(window.opener&&typeof window.opener.setMouseSensitivity==='function')window.opener.setMouseSensitivity(sens)};pad.onpointerdown=()=>{if(document.pointerLockElement!==pad)pad.requestPointerLock?.()};document.addEventListener('pointerlockchange',()=>{const locked=document.pointerLockElement===pad;pad.classList.toggle('locked',locked);label.textContent=locked?'CAMERA LOCKED — MOVE MOUSE':'CLICK TO LOCK CAMERA';targetRx=targetRy=rx=ry=0;down=false;sync(true);render()});document.addEventListener('mousemove',e=>{if(document.pointerLockElement!==pad)return;down=e.buttons>0;const scale=(down?.0025:.004)*(sens/100);targetRx=Math.max(-1,Math.min(1,targetRx+(e.movementX||0)*scale));targetRy=Math.max(-1,Math.min(1,targetRy-(e.movementY||0)*scale));rx=targetRx;ry=targetRy;sync();render()});window.addEventListener('keydown',e=>{if(window.opener?.pressKeySource){window.opener.pressKeySource('popout_keyboard',e.code);window.opener.transmitCurrentInputState?.()}},true);window.addEventListener('keyup',e=>{if(window.opener?.releaseKeySource){window.opener.releaseKeySource('popout_keyboard',e.code);window.opener.transmitCurrentInputState?.()}},true);window.addEventListener('beforeunload',()=>{cancelAnimationFrame(frame);window.opener?.releaseKeySource?.('popout_keyboard');rx=ry=0;sync(true)});frame=requestAnimationFrame(loop);
<\/script></body></html>`;
    popoutWindow.document.write(html);
    popoutWindow.document.close();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad) return;

    updateSensitivityUI();
    const sensSlider = document.getElementById("mouse-sens-slider");
    if (sensSlider) sensSlider.addEventListener("input", event => setSensitivity(event.target.value));

    const fsBtn = document.getElementById("mouse-camera-fullscreen-btn");
    if (fsBtn) fsBtn.onclick = () => toggleFullscreen();
    const popBtn = document.getElementById("mouse-camera-popout-btn");
    if (popBtn) popBtn.onclick = openPopoutWindow;

    window.addEventListener("contextmenu", event => { if (state.locked) event.preventDefault(); }, true);

    pad.addEventListener("pointerdown", event => {
      if ((window.currentMode || "keyboard") !== "keyboard") return;
      if (event.pointerType === "mouse") {
        if (!state.locked && typeof pad.requestPointerLock === "function") {
          try {
            const promise = pad.requestPointerLock();
            if (promise?.catch) promise.catch(() => {});
          } catch (_) {}
        }
      } else if (!state.locked) {
        activeTouchPointerId = event.pointerId;
        try { pad.setPointerCapture(event.pointerId); } catch (_) {}
        handleUnlockedPointerMove(event);
      }
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
      targetRx = 0;
      targetRy = 0;
      if (state.locked) updateLabel("🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
    }, true);

    pad.addEventListener("pointermove", event => {
      if (!state.locked && (event.pointerType !== "mouse" || activeTouchPointerId === event.pointerId)) {
        handleUnlockedPointerMove(event);
      }
    });

    const handleRelease = event => {
      if (!state.locked && activeTouchPointerId === event.pointerId) reset(true);
    };
    pad.addEventListener("pointerup", handleRelease);
    pad.addEventListener("pointercancel", handleRelease);
    pad.addEventListener("pointerleave", event => {
      if (!state.locked && !pad.hasPointerCapture?.(event.pointerId)) handleRelease(event);
    });

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
      if (document.pointerLockElement === pad) {
        try { document.exitPointerLock?.(); } catch (_) {}
      }
      reset(true);
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) return;
      if (document.pointerLockElement === pad) {
        try { document.exitPointerLock?.(); } catch (_) {}
      }
      reset(true);
    });
  });

  window.toggleMouseCameraFullscreen = toggleFullscreen;
  window.openMouseCameraPopout = openPopoutWindow;
  window.setMouseSensitivity = setSensitivity;
  window.resetMouseCameraState = reset;
})();
