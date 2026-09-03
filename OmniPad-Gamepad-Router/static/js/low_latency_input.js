/**
 * OmniPad — low-latency remote input transport guard.
 *
 * Digital transitions are flushed immediately. High-frequency analog/mouse
 * snapshots are latest-state-wins: duplicate frames are suppressed and analog
 * frames are dropped while the browser WebSocket has queued data. This keeps a
 * Cloudflare/WAN session from replaying stale camera positions after the user
 * has already moved on.
 */

(() => {
  const nativeSend = WebSocket.prototype.send;
  const socketState = new WeakMap();

  // A normal OmniPad input packet is well below 1 KiB. If more than a few
  // packets are waiting in the browser, prefer the next fresh snapshot instead
  // of adding another stale analog position to the queue.
  const MAX_BUFFERED_BYTES = 8 * 1024;
  const MIN_ANALOG_SEND_MS = 12;
  const SAME_STATE_KEEPALIVE_MS = 90;

  const stats = {
    sentInputPackets: 0,
    droppedBackpressure: 0,
    droppedCoalesced: 0,
    droppedDuplicate: 0,
    lastBufferedAmount: 0,
  };
  window.OmniPadInputTransportStats = stats;

  function sortedKeys(value) {
    return Array.isArray(value) ? value.map(String).sort() : [];
  }

  function normalizedButtons(value) {
    const source = value && typeof value === "object" ? value : {};
    const result = {};
    Object.keys(source).sort().forEach(key => {
      if (source[key]) result[key] = true;
    });
    return result;
  }

  function normalizedAxes(value) {
    const source = value && typeof value === "object" ? value : {};
    const result = {};
    for (const key of ["lx", "ly", "rx", "ry", "lt", "rt"]) {
      const number = Number(source[key] || 0);
      result[key] = Number.isFinite(number) ? Math.round(number * 10000) / 10000 : 0;
    }
    return result;
  }

  function describeInput(message) {
    const keyCodes = sortedKeys(message.key_codes);
    const buttons = normalizedButtons(message.buttons);
    const axes = normalizedAxes(message.axes);
    const digitalSignature = JSON.stringify([keyCodes, buttons]);
    const signature = JSON.stringify([
      String(message.input_surface || "unknown"),
      String(message.mapping_profile || "universal"),
      message.background_routing !== false,
      keyCodes,
      buttons,
      axes,
    ]);
    const active = keyCodes.length > 0 ||
      Object.keys(buttons).length > 0 ||
      Object.values(axes).some(value => Math.abs(value) > 0.01);
    return { signature, digitalSignature, active };
  }

  WebSocket.prototype.send = function omnipadGuardedSend(data) {
    if (typeof data !== "string" || data.length < 2 || data[0] !== "{") {
      return nativeSend.call(this, data);
    }

    let message;
    try {
      message = JSON.parse(data);
    } catch (_) {
      return nativeSend.call(this, data);
    }
    if (!message || message.type !== "input") {
      return nativeSend.call(this, data);
    }

    const now = performance.now();
    const next = describeInput(message);
    const previous = socketState.get(this) || {
      signature: null,
      digitalSignature: null,
      active: false,
      lastSentAt: -Infinity,
    };

    const changed = next.signature !== previous.signature;
    const digitalChanged = next.digitalSignature !== previous.digitalSignature;
    const releasing = previous.active && !next.active;
    const urgent = previous.signature === null || digitalChanged || releasing;
    const elapsed = now - previous.lastSentAt;
    const buffered = Number(this.bufferedAmount || 0);
    stats.lastBufferedAmount = buffered;

    if (!urgent) {
      if (buffered > MAX_BUFFERED_BYTES) {
        stats.droppedBackpressure += 1;
        return;
      }
      if (changed && elapsed < MIN_ANALOG_SEND_MS) {
        stats.droppedCoalesced += 1;
        return;
      }
      if (!changed && elapsed < SAME_STATE_KEEPALIVE_MS) {
        stats.droppedDuplicate += 1;
        return;
      }
    } else if (!changed && elapsed < 4) {
      // The ordinary key handler and the microtask flush can observe the same
      // transition in the same turn. Keep one copy, not two.
      stats.droppedDuplicate += 1;
      return;
    }

    nativeSend.call(this, data);
    stats.sentInputPackets += 1;
    socketState.set(this, {
      signature: next.signature,
      digitalSignature: next.digitalSignature,
      active: next.active,
      lastSentAt: now,
    });
  };

  // Existing installs used 40% as the implicit default. Halve that default for
  // mouse-camera users while preserving any deliberate custom sensitivity.
  try {
    if (!localStorage.getItem("omnipad.mouseSensitivityScaleV2")) {
      const stored = localStorage.getItem("omnipad.mouseSensitivity");
      if (stored === null || stored === "40") {
        localStorage.setItem("omnipad.mouseSensitivity", "20");
      }
      localStorage.setItem("omnipad.mouseSensitivityScaleV2", "1");
    }
  } catch (_) {}

  let scheduled = false;

  function flushDigitalTransition() {
    scheduled = false;
    if ((window.currentMode || "keyboard") === "keyboard" &&
        typeof window.transmitCurrentInputState === "function") {
      window.transmitCurrentInputState();
    }
  }

  function scheduleDigitalFlush() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(flushDigitalTransition);
  }

  window.addEventListener("keydown", scheduleDigitalFlush, { capture: true });
  window.addEventListener("keyup", scheduleDigitalFlush, { capture: true });
})();
