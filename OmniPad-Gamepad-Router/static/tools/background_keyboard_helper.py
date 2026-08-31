"""
OmniPad Background Keyboard Helper (Windows)

Native, opt-in global keyboard capture for the case where the browser /play page
is connected but no longer the foreground window. The helper does not suppress
keys and does not log text; it forwards only OmniPad control keys.
"""
from __future__ import annotations
import argparse, asyncio, json, os, signal, threading, time
from typing import Optional
from urllib.parse import parse_qs, urlsplit

import websockets
from pynput import keyboard

SPECIAL_CODES = {
    keyboard.Key.space: "Space", keyboard.Key.enter: "Enter",
    keyboard.Key.tab: "Tab", keyboard.Key.backspace: "Backspace",
    keyboard.Key.esc: "Escape",
    keyboard.Key.shift: "ShiftLeft", keyboard.Key.shift_l: "ShiftLeft",
    keyboard.Key.shift_r: "ShiftRight",
    keyboard.Key.ctrl: "ControlLeft", keyboard.Key.ctrl_l: "ControlLeft",
    keyboard.Key.ctrl_r: "ControlRight",
    keyboard.Key.alt: "AltLeft", keyboard.Key.alt_l: "AltLeft",
    keyboard.Key.alt_r: "AltRight",
    keyboard.Key.caps_lock: "CapsLock",
    keyboard.Key.up: "ArrowUp", keyboard.Key.down: "ArrowDown",
    keyboard.Key.left: "ArrowLeft", keyboard.Key.right: "ArrowRight",
}
for i in range(1, 13):
    SPECIAL_CODES[getattr(keyboard.Key, f"f{i}")] = f"F{i}"

ALLOWED_CODES = {
    *(f"Key{chr(c)}" for c in range(ord("A"), ord("Z") + 1)),
    *(f"Digit{i}" for i in range(10)),
    "Space", "Enter", "Tab", "Backspace", "Escape",
    "ShiftLeft", "ShiftRight", "ControlLeft", "ControlRight",
    "AltLeft", "AltRight", "CapsLock",
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
    *(f"F{i}" for i in range(1, 13)),
    "Backquote", "Minus", "Equal",
    "BracketLeft", "BracketRight", "Backslash",
    "Semicolon", "Quote", "Comma", "Period", "Slash",
}

def key_to_code(key) -> Optional[str]:
    if key in SPECIAL_CODES:
        return SPECIAL_CODES[key]
    char = getattr(key, "char", None)
    if not char or len(char) != 1:
        return None
    if char.isalpha() and char.isascii():
        return f"Key{char.upper()}"
    if char.isdigit():
        return f"Digit{char}"
    punctuation = {
        "`": "Backquote", "-": "Minus", "=": "Equal",
        "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash",
        ";": "Semicolon", "'": "Quote", ",": "Comma", ".": "Period", "/": "Slash",
    }
    return punctuation.get(char)

def websocket_url_from_play_url(play_url: str) -> tuple[str, str]:
    parsed = urlsplit(play_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Play URL must start with http:// or https:// and include a host.")
    code = parse_qs(parsed.query).get("code", [""])[0].strip().upper()
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/ws/player", code

def build_packet(active: set[str], seq: int) -> dict:
    buttons = {}
    axes = {"lx": 0, "ly": 0, "rx": 0, "ry": 0, "lt": 0, "rt": 0}

    up, down = "KeyW" in active, "KeyS" in active
    left, right = "KeyA" in active, "KeyD" in active
    axes["ly"] = 1 if up and not down else (-1 if down and not up else 0)
    axes["lx"] = 1 if right and not left else (-1 if left and not right else 0)

    up, down = "ArrowUp" in active, "ArrowDown" in active
    left, right = "ArrowLeft" in active, "ArrowRight" in active
    axes["ry"] = 1 if up and not down else (-1 if down and not up else 0)
    axes["rx"] = 1 if right and not left else (-1 if left and not right else 0)

    mapping = {
        "KeyQ":"Y", "KeyE":"X", "KeyR":"B", "Space":"A",
        "KeyZ":"LB", "KeyC":"RB", "ShiftLeft":"LT", "ControlLeft":"RT",
        "Escape":"BACK", "Enter":"START", "F1":"GUIDE",
        "KeyF":"L3", "KeyG":"R3",
        "Digit1":"DPAD_UP", "Digit2":"DPAD_DOWN",
        "Digit3":"DPAD_LEFT", "Digit4":"DPAD_RIGHT",
    }
    for code in active:
        button = mapping.get(code)
        if button:
            buttons[button] = True
    axes["lt"] = 1 if "ShiftLeft" in active else 0
    axes["rt"] = 1 if "ControlLeft" in active else 0
    return {
        "type":"input", "seq":seq, "buttons":buttons, "axes":axes,
        "key_codes":sorted(active), "client_time":time.time() * 1000,
        "input_surface":"background_native",
        "mapping_profile":"background_native",
        "source":"background_keyboard_helper",
    }

class BackgroundKeyboardClient:
    def __init__(self, ws_url: str, room_code: str, slot_id: int, name: str, ready_file: Optional[str] = None):
        self.ws_url, self.room_code = ws_url, room_code
        self.slot_id, self.name = slot_id, name
        self.ready_file = ready_file
        self.active: set[str] = set()
        self.lock = threading.Lock()
        self.running = True
        self.capture_enabled = True
        self.hotkey_pressed: set[str] = set()
        self.toggle_latched = False
        self.seq = 0

    def _write_status(self, state: str, **extra) -> None:
        if not self.ready_file:
            return
        payload = {
            "state": state,
            "pid": os.getpid(),
            "timestamp": time.time(),
            **extra,
        }
        directory = os.path.dirname(os.path.abspath(self.ready_file)) or "."
        os.makedirs(directory, exist_ok=True)
        tmp = f"{self.ready_file}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.replace(tmp, self.ready_file)

    def _is_hotkey_combo(self) -> bool:
        has_ctrl = "ControlLeft" in self.hotkey_pressed or "ControlRight" in self.hotkey_pressed
        has_alt = "AltLeft" in self.hotkey_pressed or "AltRight" in self.hotkey_pressed
        has_f8 = "F8" in self.hotkey_pressed
        return has_ctrl and has_alt and has_f8

    def _toggle_capture_if_needed(self) -> bool:
        combo = self._is_hotkey_combo()
        if combo and not self.toggle_latched:
            self.toggle_latched = True
            self.capture_enabled = not self.capture_enabled
            with self.lock:
                self.active.clear()
            print(f"[OmniPad] Background capture {'ENABLED' if self.capture_enabled else 'PAUSED'} (Ctrl+Alt+F8)")
            return True
        if not combo:
            self.toggle_latched = False
        return False

    def on_press(self, key):
        code = key_to_code(key)
        if not code:
            return
        self.hotkey_pressed.add(code)
        if self._toggle_capture_if_needed():
            return
        if self.capture_enabled and code in ALLOWED_CODES:
            with self.lock:
                self.active.add(code)

    def on_release(self, key):
        code = key_to_code(key)
        if not code:
            return
        self.hotkey_pressed.discard(code)
        if not self._is_hotkey_combo():
            self.toggle_latched = False
        if code in ALLOWED_CODES:
            with self.lock:
                self.active.discard(code)

    async def run(self):
        listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release, suppress=False
        )
        listener.start()
        # Wait until pynput's low-level hook is actually installed. This raises
        # startup errors here instead of letting the server/UI falsely report
        # background input as active.
        listener.wait()
        self._write_status("listener_ready")
        print("[OmniPad] Background Keyboard Helper started.")
        print("[OmniPad] Global capture is ON. Ctrl+Alt+F8 pauses/resumes it.")
        print("[OmniPad] Keep the helper running; the browser /play page may be in the background.")
        try:
            while self.running:
                try:
                    async with websockets.connect(
                        self.ws_url, ping_interval=20, ping_timeout=20, max_size=2**20
                    ) as ws:
                        await ws.send(json.dumps({
                            "type": "join", "slot_id": self.slot_id,
                            "name": self.name, "code": self.room_code,
                            "source": "background_keyboard_helper",
                        }))
                        joined = False
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline:
                            raw = await asyncio.wait_for(
                                ws.recv(), timeout=max(0.1, deadline - time.monotonic())
                            )
                            message = json.loads(raw)
                            if message.get("type") == "joined":
                                joined = True
                                break
                            if message.get("type") == "error":
                                raise RuntimeError(message.get("error") or message.get("message") or "Join rejected")
                        if not joined:
                            raise RuntimeError("Timed out waiting for OmniPad join confirmation")
                        self._write_status("ready", connected=True, room_code=self.room_code, slot_id=self.slot_id)
                        print("[OmniPad] Connected. Background keyboard input is streaming.")
                        while self.running:
                            with self.lock:
                                active = set(self.active) if self.capture_enabled else set()
                            self.seq += 1
                            await ws.send(json.dumps(build_packet(active, self.seq)))
                            await asyncio.sleep(1 / 60)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._write_status("error", error=str(exc))
                    print(f"[OmniPad] Connection retry: {exc}")
                    await asyncio.sleep(2)
        finally:
            self.running = False
            self._write_status("stopped")
            listener.stop()

def parse_args():
    parser = argparse.ArgumentParser(
        description="OmniPad global background keyboard helper (Windows)."
    )
    parser.add_argument("--play-url", default=None,
        help="Full OmniPad /play URL, including ?code=ROOM.")
    parser.add_argument("--ws-url", default=None,
        help="Direct OmniPad WebSocket endpoint (e.g. ws://127.0.0.1:8000/ws/player).")
    parser.add_argument("--code", default=None,
        help="Room pairing code (e.g. SF6-ROOM).")
    parser.add_argument("--slot", type=int, default=1,
        help="OmniPad slot ID (default: 1).")
    parser.add_argument("--name", default="Player 2",
        help="Player name shown on the host.")
    parser.add_argument("--ready-file", default=None,
        help="Optional JSON status file used by the OmniPad server to verify listener and WebSocket readiness.")
    return parser.parse_args()

def main():
    args = parse_args()
    if args.ws_url and args.code:
        ws_url = args.ws_url
        room_code = args.code.strip().upper()
    elif args.play_url:
        ws_url, room_code = websocket_url_from_play_url(args.play_url)
    else:
        raise SystemExit("Either --play-url or both --ws-url and --code must be specified.")

    if not room_code:
        raise SystemExit("The play URL or --code must specify a valid room code.")
    client = BackgroundKeyboardClient(ws_url, room_code, args.slot, args.name[:24], args.ready_file)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    def stop(*_):
        client.running = False
    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    try:
        loop.run_until_complete(client.run())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
