#!/usr/bin/env python3
"""Smoke test the narration path against a running server.

Checks the things that have actually broken here before:

  * every turn reaches its boundary - a turn that never does is heard as
    silence, and used to sit for the full client timeout before anything retried
  * the transcript comes back with the audio, which the saved-audio markers
    depend on to judge a passage
  * both of the above still hold with two sessions running at once, which is how
    the reader generates

Needs the backend up (python main.py) and a working API key. Run from the
backend directory:

    python tests/smoke_turns.py

Exits non-zero if any turn stalls, so it can gate a change.
"""
import asyncio
import base64
import json
import sys

import websockets

URL = "ws://localhost:9083"
MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
PER_TURN_TIMEOUT = 45
LANES = 2
TURNS_PER_LANE = 2

PASSAGES = [
    "The lighthouse blinked twice across the bay tonight.",
    "Someone was already awake inside the cottage on the hill.",
    "A gull settled on the iron railing and watched the boats.",
    "Nobody spoke until the tide had finally started to turn.",
    "Salt hung in the air thick enough to taste on the tongue.",
    "The fishermen gathered their nets in the grey morning light.",
]


async def open_session(ws) -> None:
    await ws.send(json.dumps({
        "type": "init", "voice": "Aoede", "model": MODEL,
        "allowModelOverride": True, "instructions": "", "sequentialAudioPlay": False,
    }))
    while True:
        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
        if message.get("is_system_message") and "Connected to Gemini API" in (message.get("text") or ""):
            return


async def run_turn(ws, passage: str) -> dict:
    """Send one passage and wait for the server's end-of-turn."""
    await ws.send(json.dumps({"realtime_input": {
        "media_chunks": [{"mime_type": "text/plain", "data": passage}],
        "turn_complete": True,
    }}))
    loop = asyncio.get_event_loop()
    started = loop.time()
    audio = 0
    try:
        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=PER_TURN_TIMEOUT))
            if message.get("audio"):
                audio += len(base64.b64decode(message["audio"]))
                continue
            if message.get("is_transcription"):
                return {
                    "seconds": round(loop.time() - started, 1),
                    "audio_seconds": round(audio / 48000, 1),
                    "transcript": len(message.get("text") or ""),
                    "stalled": False,
                }
    except asyncio.TimeoutError:
        return {"seconds": PER_TURN_TIMEOUT, "audio_seconds": round(audio / 48000, 1),
                "transcript": 0, "stalled": True}


async def lane(lane_id: int, passages: list, results: list) -> None:
    async with websockets.connect(URL, max_size=None) as ws:
        await open_session(ws)
        for turn, passage in enumerate(passages):
            results.append((lane_id, turn, await run_turn(ws, passage)))


def report(title: str, results: list) -> tuple:
    print(f"\n{title}")
    stalls = thin = 0
    for lane_id, turn, r in sorted(results, key=lambda x: (x[0], x[1])):
        note = ""
        if r["stalled"]:
            note, stalls = "  STALLED - no end of turn", stalls + 1
        elif r["transcript"] == 0:
            note, thin = "  (no transcript - marker will read 'incomplete')", thin + 1
        print(f"  lane {lane_id} turn {turn}: {r['seconds']:5.1f}s  "
              f"audio {r['audio_seconds']:4.1f}s  transcript {r['transcript']:3d}{note}")
    return stalls, thin


async def main() -> None:
    sequential: list = []
    await lane(0, PASSAGES[:3], sequential)
    seq_stalls, seq_thin = report("sequential, one session", sequential)

    concurrent: list = []
    await asyncio.gather(*(
        lane(i, PASSAGES[i * TURNS_PER_LANE:(i + 1) * TURNS_PER_LANE], concurrent)
        for i in range(LANES)
    ))
    con_stalls, con_thin = report(f"{LANES} sessions at once", concurrent)

    total = len(sequential) + len(concurrent)
    stalls = seq_stalls + con_stalls
    print(f"\n{total - stalls}/{total} turns completed, {stalls} stalled, "
          f"{seq_thin + con_thin} without a transcript")
    if stalls:
        print("FAIL: a turn never reached its boundary")
    sys.exit(1 if stalls else 0)


asyncio.run(main())
