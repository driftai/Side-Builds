#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request

HARNESS_URL = "http://127.0.0.1:5180"
history: list[dict[str, str]] = []


def ask(message: str) -> str:
    payload = json.dumps(
        {
            "message": message,
            "history": history,
            "temperature": 0.0,
            "max_tokens": 128,
        }
    ).encode()
    request = urllib.request.Request(
        f"{HARNESS_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        doc = json.load(response)
    reply = doc["choices"][0]["message"]
    content = reply.get("content") or ""
    reasoning = reply.get("reasoning_content") or ""
    visible = content or reasoning
    if not visible.strip():
        raise RuntimeError("Harness returned an empty assistant reply.")
    history.extend(
        [
            {"role": "user", "content": message},
            {"role": "assistant", "content": visible},
        ]
    )
    return visible


def main() -> None:
    first = "Remember this code word for our conversation: COBALT-17. Acknowledge it briefly."
    print("USER 1:", first)
    print("LOCAL MODEL 1:", ask(first))

    second = "What code word did I give you? Answer with the code word."
    print("\nUSER 2:", second)
    reply = ask(second)
    print("LOCAL MODEL 2:", reply)

    if "cobalt-17" not in reply.lower():
        raise SystemExit("FAIL: second turn did not preserve first-turn context.")
    print("\nPASS: multi-turn conversation context was preserved through the harness.")


if __name__ == "__main__":
    main()
