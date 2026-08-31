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
  let targetRx = 0;
  let targetRy = 0;
  let isClickHeld = false;
  let mouseSensitivity = parseInt(localStorage.getItem("omnipad.mouseSensitivity") || "40", 10);

  function getSensMultiplier() {
    return mouseSensitivity / 100;
  }

  function setSensitivity(val) {
    mouseSensitivity = Math.max(10, Math.min(200, parseInt(val, 10) || 40));
    try { localStorage.setItem("omnipad.mouseSensitivity", mouseSensitivity); } catch (_) {}
    updateSensitivityUI();
  }

  function updateSensitivityUI() {
    const slider = document.getElementById("mouse-sens-slider");
    const valEl = document.getElementById("mouse-sens-val");
    if (slider) slider.value = mouseSensitivity;
    if (valEl) valEl.textContent = `${mouseSensitivity}%`;
  }

  function reset() {
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
      const center = document.getElementById("mouse-camera-center");
      if (center) { center.style.left = "50%"; center.style.top = "50%"; }
      const puck = document.getElementById("mouse-camera-puck");
      if (puck) { puck.style.left = "50%"; puck.style.top = "50%"; }
      if (!state.locked) {
        updateLabel("🖱️ CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)");
      }
    }
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
      targetRx *= 0.72;
      targetRy *= 0.72;
      if (Math.abs(targetRx) < 0.004) targetRx = 0;
      if (Math.abs(targetRy) < 0.004) targetRy = 0;
      state.rx = targetRx;
      state.ry = targetRy;
    }

    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;

    const center = document.getElementById("mouse-camera-center");
    if (center) {
      center.style.left = `${((state.rx + 1) / 2) * 100}%`;
      center.style.top = `${((-state.ry + 1) / 2) * 100}%`;
    }
    const puck = document.getElementById("mouse-camera-puck");
    if (puck) {
      puck.style.left = `${((state.rx + 1) / 2) * 100}%`;
      puck.style.top = `${((-state.ry + 1) / 2) * 100}%`;
    }

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

    const mult = getSensMultiplier();
    const baseSens = isClickHeld ? 0.005 : 0.008;
    const sens = baseSens * mult;
    const dx = (event.movementX || 0) * sens;
    const dy = (event.movementY || 0) * sens;

    targetRx = Math.max(-1, Math.min(1, targetRx + dx));
    targetRy = Math.max(-1, Math.min(1, targetRy - dy));

    state.rx = targetRx;
    state.ry = targetRy;
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;

    const center = document.getElementById("mouse-camera-center");
    if (center) {
      center.style.left = `${((state.rx + 1) / 2) * 100}%`;
      center.style.top = `${((-state.ry + 1) / 2) * 100}%`;
    }
    const puck = document.getElementById("mouse-camera-puck");
    if (puck) {
      puck.style.left = `${((state.rx + 1) / 2) * 100}%`;
      puck.style.top = `${((-state.ry + 1) / 2) * 100}%`;
    }

    if (typeof window.transmitCurrentInputState === "function") {
      window.transmitCurrentInputState();
    }
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

    const center = document.getElementById("mouse-camera-center");
    if (center) {
      center.style.left = `${((nx + 1) / 2) * 100}%`;
      center.style.top = `${((ny + 1) / 2) * 100}%`;
    }
    const puck = document.getElementById("mouse-camera-puck");
    if (puck) {
      puck.style.left = `${((nx + 1) / 2) * 100}%`;
      puck.style.top = `${((ny + 1) / 2) * 100}%`;
    }

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

    const deadzone = 0.08;
    state.rx = Math.abs(nx) < deadzone ? 0 : nx;
    state.ry = Math.abs(ny) < deadzone ? 0 : -ny;
    state.active = Math.abs(state.rx) > 0.01 || Math.abs(state.ry) > 0.01;
    pad.classList.toggle("active", state.active);
    updateLabel(state.active ? "🎯 AIMING ACTIVE" : "🖱️ DRAGGING IN CENTER");

    if (typeof window.transmitCurrentInputState === "function") {
      window.transmitCurrentInputState();
    }
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
      if (lockedFrameHandle) {
        cancelAnimationFrame(lockedFrameHandle);
        lockedFrameHandle = null;
      }
      targetRx = 0;
      targetRy = 0;
      isClickHeld = false;
      pad.classList.remove("locked");
      updateLabel("🖱️ CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)");
      document.removeEventListener("mousemove", handleLockedMouseMove);
      reset();
      if (typeof window.transmitCurrentInputState === "function") {
        window.transmitCurrentInputState();
      }
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

    popoutWindow.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>OmniPad — Detached Camera</title><style>*{box-sizing:border-box;margin:0;padding:0;}body{background:#0b0e14;color:#fff;font-family:-apple-system,sans-serif;height:100vh;display:flex;flex-direction:column;padding:12px;overflow:hidden;user-select:none;}.popout-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:.85rem;}.sens-box{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.05);padding:2px 8px;border-radius:6px;border:1px solid rgba(255,255,255,.1);font-size:.75rem;}.pad{flex:1;position:relative;border-radius:12px;border:2px dashed rgba(0,229,255,.3);background:radial-gradient(circle at center,rgba(0,229,255,.08),rgba(0,0,0,.6));cursor:crosshair;overflow:hidden;}.pad.locked{border-style:solid;border-color:#00e5ff;box-shadow:0 0 30px rgba(0,229,255,.25);}.target-ring{position:absolute;left:50%;top:50%;width:56px;height:56px;transform:translate(-50%,-50%);border:1px dashed rgba(255,255,255,.3);border-radius:50%;pointer-events:none;}.center-ring{position:absolute;left:50%;top:50%;width:44px;height:44px;transform:translate(-50%,-50%);border:2px solid #00e5ff;border-radius:50%;background:radial-gradient(circle at center,rgba(0,229,255,.3),transparent);box-shadow:0 0 16px rgba(0,229,255,.6);pointer-events:none;}.label{position:absolute;bottom:16px;left:50%;transform:translateX(-50%);font-size:.8rem;color:#00e5ff;font-weight:700;pointer-events:none;white-space:nowrap;}</style></head><body><div class="popout-header"><strong>🖱️ OmniPad Detached Camera</strong><div class="sens-box"><label>Sens:</label><input type="range" id="pop-sens" min="10" max="200" value="${mouseSensitivity}" style="width:75px;height:4px;"><span id="pop-sens-val">${mouseSensitivity}%</span></div></div><div class="pad" id="pop-pad"><div class="target-ring"></div><div class="center-ring" id="pop-center"></div><div class="label" id="pop-label">CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)</div></div><script>const pad=document.getElementById("pop-pad"),label=document.getElementById("pop-label"),centerEl=document.getElementById("pop-center"),popSens=document.getElementById("pop-sens"),popSensVal=document.getElementById("pop-sens-val");let targetRx=0,targetRy=0,rx=0,ry=0,prevRx=0,prevRy=0,isDown=false,sens=${mouseSensitivity},frameHandle=null;popSens.addEventListener("input",e=>{sens=parseInt(e.target.value,10)||40;popSensVal.textContent=sens+"%";if(window.opener&&typeof window.opener.setMouseSensitivity==="function")window.opener.setMouseSensitivity(sens);});function sync(outRx,outRy,active){if(window.opener&&window.opener.mouseCameraState){window.opener.mouseCameraState.rx=outRx;window.opener.mouseCameraState.ry=outRy;window.opener.mouseCameraState.active=active;if((Math.abs(outRx-prevRx)>0.01||Math.abs(outRy-prevRy)>0.01||(prevRx!==0&&outRx===0)||(prevRy!==0&&outRy===0))&&typeof window.opener.transmitCurrentInputState==="function"){prevRx=outRx;prevRy=outRy;window.opener.transmitCurrentInputState();}}}function frameLoop(){if(!isDown){targetRx*=0.72;targetRy*=0.72;if(Math.abs(targetRx)<0.004)targetRx=0;if(Math.abs(targetRy)<0.004)targetRy=0;rx=targetRx;ry=targetRy;}else{rx=targetRx;ry=targetRy;}if(centerEl){centerEl.style.left=((rx+1)/2*100)+"%";centerEl.style.top=(( -ry+1)/2*100)+"%";}sync(rx,ry,Math.abs(rx)>0.01||Math.abs(ry)>0.01);frameHandle=requestAnimationFrame(frameLoop);}window.addEventListener("contextmenu",e=>{if(document.pointerLockElement===pad)e.preventDefault();},true);window.addEventListener("pointerdown",e=>{if(document.pointerLockElement!==pad)try{pad.requestPointerLock();}catch(_){}},true);window.addEventListener("mousedown",e=>{if(document.pointerLockElement===pad){if(e.button===2)e.preventDefault();isDown=true;label.textContent="🎯 CLICK-DRAG SUSTAIN AIMING (RELEASE TO CENTER)";}},true);window.addEventListener("mouseup",()=>{isDown=false;targetRx=0;targetRy=0;if(document.pointerLockElement===pad)label.textContent="🎯 CAMERA LOCKED — MOVE MOUSE TO AIM (ESC TO UNLOCK)";},true);document.addEventListener("pointerlockchange",()=>{const locked=document.pointerLockElement===pad;pad.classList.toggle("locked",locked);label.textContent=locked?"🎯 CAMERA LOCKED — MOVE MOUSE TO AIM (ESC TO UNLOCK)":"CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)";targetRx=0;targetRy=0;rx=0;ry=0;prevRx=0;prevRy=0;isDown=false;if(centerEl){centerEl.style.left="50%";centerEl.style.top="50%";}if(locked){if(frameHandle)cancelAnimationFrame(frameHandle);frameHandle=requestAnimationFrame(frameLoop);}else{if(frameHandle)cancelAnimationFrame(frameHandle);sync(0,0,false);}});document.addEventListener("mousemove",e=>{if(document.pointerLockElement!==pad)return;if(e.buttons!==undefined)isDown=e.buttons>0;const mult=sens/100;const baseSens=isDown?0.005:0.008;const currentSens=baseSens*mult;targetRx=Math.max(-1,Math.min(1,targetRx+(e.movementX||0)*currentSens));targetRy=Math.max(-1,Math.min(1,targetRy-(e.movementY||0)*currentSens));rx=targetRx;ry=targetRy;sync(rx,ry,Math.abs(rx)>0.01||Math.abs(ry)>0.01);});window.addEventListener("keydown",e=>{if(e.repeat)return;if(window.opener&&typeof window.opener.pressKeySource==="function"){window.opener.pressKeySource("physical_keyboard",e.code);if(typeof window.opener.transmitCurrentInputState==="function")window.opener.transmitCurrentInputState();}},true);window.addEventListener("keyup",e=>{if(window.opener&&typeof window.opener.releaseKeySource==="function"){window.opener.releaseKeySource("physical_keyboard",e.code);if(typeof window.opener.transmitCurrentInputState==="function")window.opener.transmitCurrentInputState();}},true);window.addEventListener("beforeunload",()=>{if(frameHandle)cancelAnimationFrame(frameHandle);if(window.opener&&typeof window.opener.releaseKeySource==="function")window.opener.releaseKeySource("physical_keyboard");sync(0,0,false);});window.addEventListener("blur",()=>{if(document.pointerLockElement===pad)try{document.exitPointerLock();}catch(_){}if(window.opener&&typeof window.opener.releaseKeySource==="function")window.opener.releaseKeySource("physical_keyboard");sync(0,0,false);});</script></body></html>`);
    popoutWindow.document.close();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const pad = document.getElementById("mouse-camera-pad");
    if (!pad) return;

    updateLabel("🖱️ CLICK TO LOCK MOUSE CAMERA (ESC TO UNLOCK)");
    updateSensitivityUI();

    const sensSlider = document.getElementById("mouse-sens-slider");
    if (sensSlider) {
      sensSlider.value = mouseSensitivity;
      sensSlider.addEventListener("input", event => {
        setSensitivity(event.target.value);
      });
    }

    const fsBtn = document.getElementById("mouse-camera-fullscreen-btn");
    if (fsBtn) fsBtn.onclick = () => toggleFullscreen();

    const popBtn = document.getElementById("mouse-camera-popout-btn");
    if (popBtn) popBtn.onclick = openPopoutWindow;

    window.addEventListener("contextmenu", event => {
      if (state.locked) event.preventDefault();
    }, true);

    pad.addEventListener("pointerdown", event => {
      if ((window.currentMode || "keyboard") !== "keyboard") return;
      if (event.pointerType === "mouse") {
        if (!state.locked && typeof pad.requestPointerLock === "function") {
          try {
            const promise = pad.requestPointerLock();
            if (promise && typeof promise.catch === "function") promise.catch(() => {});
          } catch (_) {}
        }
      } else {
        if (!state.locked) {
          activeTouchPointerId = event.pointerId;
          try { pad.setPointerCapture(event.pointerId); } catch (_) {}
          handleUnlockedPointerMove(event);
        }
      }
    });

    window.addEventListener("mousedown", event => {
      if (state.locked) {
        if (event.button === 2) event.preventDefault();
        isClickHeld = true;
        updateLabel("🎯 CLICK-DRAG SUSTAIN AIMING (RELEASE TO CENTER)");
      }
    }, true);

    window.addEventListener("mouseup", () => {
      if (isClickHeld) {
        isClickHeld = false;
        targetRx = 0;
        targetRy = 0;
        if (state.locked) {
          updateLabel("🎯 CAMERA LOCKED (MOVE MOUSE • ESC TO UNLOCK)");
        }
      }
    }, true);

    pad.addEventListener("pointermove", event => {
      if (!state.locked && (event.pointerType !== "mouse" || activeTouchPointerId === event.pointerId)) {
        handleUnlockedPointerMove(event);
      }
    });

    const handleRelease = event => {
      if (!state.locked && activeTouchPointerId === event.pointerId) {
        reset();
      }
    };

    pad.addEventListener("pointerup", handleRelease);
    pad.addEventListener("pointercancel", handleRelease);
    pad.addEventListener("pointerleave", event => {
      if (!state.locked && !pad.hasPointerCapture?.(event.pointerId)) {
        handleRelease(event);
      }
    });

    document.addEventListener("pointerlockchange", onPointerLockChange);
    document.addEventListener("pointerlockerror", () => {
      state.locked = false;
      pad.classList.remove("locked");
    });

    window.addEventListener("keydown", event => {
      if (event.key === "Escape" && isFullscreen) toggleFullscreen(false);
    });

    window.addEventListener("blur", () => {
      if (document.pointerLockElement === pad) {
        try { document.exitPointerLock?.(); } catch (_) {}
      }
      reset();
    });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        if (document.pointerLockElement === pad) {
          try { document.exitPointerLock?.(); } catch (_) {}
        }
        reset();
      }
    });
  });

  window.toggleMouseCameraFullscreen = toggleFullscreen;
  window.openMouseCameraPopout = openPopoutWindow;
  window.setMouseSensitivity = setSensitivity;
})();
