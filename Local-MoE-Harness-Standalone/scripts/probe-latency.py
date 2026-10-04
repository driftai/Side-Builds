#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

BASE_URL = "http://127.0.0.1:1919"


@dataclass
class Result:
    label: str
    ttft_s: float | None
    total_s: float
    prompt_tokens: int | None
    cached_tokens: int
    completion_tokens: int | None
    decode_tps: float | None
    output: str


def model_id() -> str:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{BASE_URL}/v1/models")
        response.raise_for_status()
        models = response.json().get("data", [])
    if not models:
        raise RuntimeError("FreeToken reported no served model")
    return models[0]["id"]


def run(label: str, messages: list[dict[str, str]], reasoning_effort: str | None) -> Result:
    payload: dict = {
        "model": model_id(),
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 48,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort

    start = time.perf_counter()
    first = None
    last = None
    usage: dict = {}
    pieces: list[str] = []

    with httpx.Client(timeout=600.0) as client:
        with client.stream("POST", f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].lstrip()
                if raw == "[DONE]":
                    break
                chunk = json.loads(raw)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                if chunk.get("usage"):
                    usage = chunk["usage"]
                choices = chunk.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                piece = delta.get("content") or delta.get("reasoning_content") or ""
                if piece:
                    now = time.perf_counter()
                    first = first or now
                    last = now
                    pieces.append(piece)

    end = time.perf_counter()
    completion_tokens = usage.get("completion_tokens")
    cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    decode_tps = None
    if completion_tokens and completion_tokens > 1 and first is not None and last and last > first:
        decode_tps = (completion_tokens - 1) / (last - first)

    return Result(
        label=label,
        ttft_s=(first - start) if first is not None else None,
        total_s=end - start,
        prompt_tokens=usage.get("prompt_tokens"),
        cached_tokens=cached_tokens,
        completion_tokens=completion_tokens,
        decode_tps=decode_tps,
        output="".join(pieces),
    )


def show(result: Result) -> None:
    ttft = f"{result.ttft_s:.3f}s" if result.ttft_s is not None else "n/a"
    decode = f"{result.decode_tps:.2f} tok/s" if result.decode_tps is not None else "n/a"
    print(f"\n[{result.label}]")
    print(f"TTFT: {ttft}")
    print(f"Total: {result.total_s:.3f}s")
    print(f"Prompt tokens: {result.prompt_tokens}")
    print(f"Cached prompt tokens: {result.cached_tokens}")
    print(f"Completion tokens: {result.completion_tokens}")
    print(f"Decode: {decode}")
    print(f"Output: {result.output[:180]!r}")


def main() -> None:
    health = httpx.get(f"{BASE_URL}/health", timeout=10.0).json()
    if health.get("status") != "ok":
        raise SystemExit(f"FreeToken is not ready: {health}")

    base_messages = [
        {"role": "system", "content": "You are a concise local AI assistant."},
        {"role": "user", "content": "Give one sentence explaining why the sky appears blue."},
    ]

    default = run("model-default reasoning", base_messages, None)
    show(default)

    fast_first = run("fast chat / first request", base_messages, "none")
    show(fast_first)

    # Exact repeat: with radix cache + cache reporting, this should expose whether
    # the common prompt prefix is actually being reused.
    fast_repeat = run("fast chat / repeated prompt", base_messages, "none")
    show(fast_repeat)

    followup_messages = base_messages + [
        {"role": "assistant", "content": "The sky appears blue because air molecules scatter shorter blue wavelengths of sunlight more strongly than longer red wavelengths."},
        {"role": "user", "content": "What color did you just explain, and what physical effect causes it?"},
    ]
    followup = run("fast chat / cached follow-up", followup_messages, "none")
    show(followup)

    print("\n=== TTFT summary ===")
    for item in (default, fast_first, fast_repeat, followup):
        ttft = f"{item.ttft_s:.3f}" if item.ttft_s is not None else "n/a"
        print(f"{item.label:30} TTFT={ttft}s cached={item.cached_tokens}")

    if fast_repeat.cached_tokens <= 0:
        print("\nWARNING: repeated prompt reported zero cached tokens; inspect radix cache configuration.")
    elif fast_first.ttft_s and fast_repeat.ttft_s:
        improvement = (fast_first.ttft_s - fast_repeat.ttft_s) / fast_first.ttft_s * 100
        print(f"\nRepeated-prefix TTFT improvement: {improvement:.1f}%")


if __name__ == "__main__":
    main()
