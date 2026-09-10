#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("FREETOKEN_BASE_URL", "http://127.0.0.1:1919").rstrip("/")


def get_model_name() -> str:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{BASE_URL}/v1/models")
        response.raise_for_status()
        data = response.json().get("data", [])
    if not data:
        raise RuntimeError("FreeToken did not report a model.")
    return data[0]["id"]


def system_snapshot() -> dict:
    try:
        parts = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip().split(",")
        gpu, used, total, power = [float(x.strip()) for x in parts[:4]]
    except Exception:
        gpu = used = total = power = 0.0
    try:
        row = subprocess.check_output(["free", "-m"], text=True).splitlines()[1].split()
        ram_used = float(row[2])
    except Exception:
        ram_used = 0.0
    return {
        "gpu_util_pct": gpu,
        "vram_used_mb": used,
        "vram_total_mb": total,
        "power_w": power,
        "ram_used_mb": ram_used,
    }


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.samples: list[dict] = []

    def run(self) -> None:
        while self.running:
            self.samples.append(system_snapshot())
            time.sleep(0.2)

    def stop(self) -> dict:
        self.running = False
        self.join()
        if not self.samples:
            return {}
        return {
            "avg_gpu_pct": round(sum(x["gpu_util_pct"] for x in self.samples) / len(self.samples), 1),
            "max_gpu_pct": round(max(x["gpu_util_pct"] for x in self.samples), 1),
            "avg_vram_mb": round(sum(x["vram_used_mb"] for x in self.samples) / len(self.samples), 1),
            "max_vram_mb": round(max(x["vram_used_mb"] for x in self.samples), 1),
            "avg_power_w": round(sum(x["power_w"] for x in self.samples) / len(self.samples), 1),
            "avg_ram_mb": round(sum(x["ram_used_mb"] for x in self.samples) / len(self.samples), 1),
        }


def measure(model: str, prompt: str, max_tokens: int, reasoning_effort: str) -> dict:
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if reasoning_effort != "default":
        payload["reasoning_effort"] = reasoning_effort

    sampler = Sampler()
    sampler.start()
    start = time.perf_counter()
    first = None
    last = None
    usage: dict = {}
    pieces: list[str] = []
    try:
        with httpx.Client(timeout=600.0) as client:
            with client.stream("POST", f"{BASE_URL}/v1/chat/completions", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].lstrip()
                    if raw == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
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
    finally:
        end = time.perf_counter()
        hardware = sampler.stop()

    completion_tokens = usage.get("completion_tokens")
    if completion_tokens is None:
        raise RuntimeError(
            "FreeToken returned no usage.completion_tokens; refusing to report a fake token rate."
        )

    total = end - start
    ttft = first - start if first is not None else None
    decode_seconds = (last - first) if first is not None and last is not None and last > first else None
    decode_tps = (
        (completion_tokens - 1) / decode_seconds
        if completion_tokens > 1 and decode_seconds
        else None
    )
    cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return {
        "prompt": prompt,
        "max_tokens_requested": max_tokens,
        "reasoning_effort": reasoning_effort,
        "prompt_tokens": usage.get("prompt_tokens"),
        "cached_prompt_tokens": cached_tokens,
        "completion_tokens": completion_tokens,
        "token_count_source": "runtime_usage",
        "ttft_s": round(ttft, 3) if ttft is not None else None,
        "decode_seconds": round(decode_seconds, 3) if decode_seconds is not None else None,
        "decode_tps": round(decode_tps, 2) if decode_tps is not None else None,
        "total_latency_s": round(total, 3),
        "end_to_end_tps": round(completion_tokens / total, 2) if completion_tokens else 0.0,
        "hardware": hardware,
        "usage": usage,
        "sample_output": "".join(pieces)[:240],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Truthful Local MoE performance profile")
    parser.add_argument("--full", action="store_true", help="Run the longer four-case suite")
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "default"],
        default="none",
        help="Use none for low-latency chat; default omits the field and uses the model policy.",
    )
    args = parser.parse_args()

    health = httpx.get(f"{BASE_URL}/health", timeout=10.0).json()
    if health.get("status") != "ok":
        raise SystemExit(f"FreeToken is not ready: {health}")
    model = get_model_name()

    tests = [
        ("Short factual", "Name the three largest oceans on Earth in order.", 64),
        ("Reasoning", "Explain in two concise paragraphs why ice floats on liquid water.", 128),
    ]
    if args.full:
        tests += [
            ("Code", "Write a Python function that returns True if an integer is prime.", 192),
            ("Long explanation", "Explain mixture-of-experts CPU/GPU offload tradeoffs.", 256),
        ]

    print(f"Model: {model}")
    print(f"Reasoning effort: {args.reasoning_effort}")
    print("Token source: exact FreeToken usage.completion_tokens (not SSE chunk counts)")
    print("Prefix cache source: usage.prompt_tokens_details.cached_tokens")
    results = []
    for name, prompt, max_tokens in tests:
        print(f"\n==> {name} (max_tokens={max_tokens})", flush=True)
        result = measure(model, prompt, max_tokens, args.reasoning_effort)
        results.append({"test": name, "result": result})
        print(
            f"TTFT={result['ttft_s']}s  decode={result['decode_tps']} tok/s  "
            f"E2E={result['end_to_end_tps']} tok/s  tokens={result['completion_tokens']}  "
            f"cached={result['cached_prompt_tokens']}",
            flush=True,
        )
        print(f"Output: {result['sample_output']!r}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "data" / "benchmarks" / f"verified-performance-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "model": model,
                "measurement": {
                    "reasoning_effort": args.reasoning_effort,
                    "token_count_source": "runtime_usage",
                    "prefix_cache_source": "usage.prompt_tokens_details.cached_tokens",
                    "decode_tps_definition": "(completion_tokens - 1) / (last_output_time - first_output_time)",
                    "end_to_end_tps_definition": "completion_tokens / request_wall_time",
                },
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
