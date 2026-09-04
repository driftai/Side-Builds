/**
 * OmniPad remote room-code resolver.
 *
 * The join URL is authoritative when it carries ?code=. This keeps Cloudflare
 * links, QR links, and LAN links bound to the exact active router session even
 * if the form contains stale text or another script touches the field later.
 */

(() => {
  const INPUT_ID = "join-room-code";
  const STALE_PLACEHOLDERS = new Set(["SF6-ROOM", "--"]);
  let installed = false;

  function normalizeRoomCode(value) {
    let text = String(value ?? "").trim();
    if (!text) return "";

    // Accept a full join link or any URL-ish value carrying ?code=.
    try {
      const parsed = new URL(text, window.location.origin);
      const fromUrl = parsed.searchParams.get("code");
      if (fromUrl) text = fromUrl;
    } catch (_) {}

    // Also accept pasted query fragments such as "?code=ABC123".
    if (/code=/i.test(text) && /[?&]/.test(text)) {
      try {
        const query = text.includes("?") ? text.slice(text.indexOf("?") + 1) : text.replace(/^&/, "");
        const fromQuery = new URLSearchParams(query).get("code");
        if (fromQuery) text = fromQuery;
      } catch (_) {}
    }

    try { text = decodeURIComponent(text); } catch (_) {}
    text = text.trim().replace(/\s+/g, "").toUpperCase();
    if (!text || STALE_PLACEHOLDERS.has(text)) return "";
    return text.slice(0, 128);
  }

  function roomCodeFromLocation() {
    try {
      return normalizeRoomCode(new URLSearchParams(window.location.search).get("code"));
    } catch (_) {
      return "";
    }
  }

  function roomCodeInput() {
    return document.getElementById(INPUT_ID);
  }

  function setRoomCodeField(value) {
    const code = normalizeRoomCode(value);
    const input = roomCodeInput();
    if (input && code) {
      input.value = code;
      input.defaultValue = code;
      input.dataset.omnipadResolvedCode = code;
    }
    return code;
  }

  function resolveForJoin() {
    // A code embedded in the link always wins over form state. This is the
    // important invariant for Cloudflare/QR links.
    const urlCode = roomCodeFromLocation();
    if (urlCode) return setRoomCodeField(urlCode);

    const input = roomCodeInput();
    const fieldCode = normalizeRoomCode(input ? input.value : "");
    if (input) input.value = fieldCode;
    return fieldCode;
  }

  async function fillLocalCodeIfMissing() {
    if (resolveForJoin()) return;

    // Public /api/status intentionally redacts the room code. LAN/localhost can
    // safely use it as a one-time convenience when /play was opened directly.
    const hostname = String(window.location.hostname || "").toLowerCase();
    if (hostname.endsWith(".trycloudflare.com")) return;

    try {
      const response = await fetch("/api/status", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      if (data && data.room_code) setRoomCodeField(data.room_code);
    } catch (_) {}
  }

  function install() {
    if (installed) {
      // Even on pageshow/history restore, refresh the URL-owned code immediately.
      const code = roomCodeFromLocation();
      if (code) setRoomCodeField(code);
      return;
    }
    installed = true;

    // The player form is above this script in play.html, so do not wait for
    // DOMContentLoaded when the input already exists. This guarantees the
    // ?code= value is present before play.js can auto-connect.
    const initialCode = roomCodeFromLocation();
    if (initialCode) setRoomCodeField(initialCode);
    else fillLocalCodeIfMissing();

    const input = roomCodeInput();
    if (input) {
      input.addEventListener("paste", event => {
        const pasted = event.clipboardData?.getData("text") || "";
        const code = normalizeRoomCode(pasted);
        if (!code) return;
        event.preventDefault();
        setRoomCodeField(code);
      });
      input.addEventListener("change", () => {
        input.value = normalizeRoomCode(input.value);
      });
    }

    // Capture before the existing onclick / Enter handlers so the player client
    // always sees the URL's active room code, even if the visible field went stale.
    document.addEventListener("click", event => {
      if (event.target?.closest?.("#join-btn")) resolveForJoin();
    }, true);
    document.addEventListener("keydown", event => {
      if (event.key !== "Enter") return;
      const id = event.target?.id || "";
      if (["join-name", "join-room-code", "join-slot", "join-mode"].includes(id)) {
        resolveForJoin();
      }
    }, true);

    window.addEventListener("pageshow", () => {
      const code = roomCodeFromLocation();
      if (code) setRoomCodeField(code);
    });
    window.addEventListener("popstate", () => {
      const code = roomCodeFromLocation();
      if (code) setRoomCodeField(code);
    });
  }

  window.OmniPadRoomCode = {
    normalize: normalizeRoomCode,
    fromLocation: roomCodeFromLocation,
    setField: setRoomCodeField,
    resolveForJoin,
  };

  if (roomCodeInput()) {
    install();
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
