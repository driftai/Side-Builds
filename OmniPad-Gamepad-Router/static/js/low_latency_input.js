/**
 * OmniPad — immediate digital input flush.
 * The normal render loop remains authoritative; key transitions are also
 * flushed immediately so a newly pressed key does not wait for the next frame.
 */

(() => {
  let scheduled = false;

  function flush() {
    scheduled = false;
    if ((window.currentMode || "keyboard") === "keyboard" &&
        typeof window.transmitCurrentInputState === "function") {
      // The underlying function owns the connection-state check.
      window.transmitCurrentInputState();
    }
  }

  function scheduleFlush() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(flush);
  }

  window.addEventListener("keydown", scheduleFlush, { capture: true });
  window.addEventListener("keyup", scheduleFlush, { capture: true });
})();
