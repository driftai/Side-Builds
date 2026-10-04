#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
HARNESS_URL = "http://127.0.0.1:5180"


@dataclass
class ProbeResult:
    label: str
    ttft_s: float | None
    total_s: float
    prompt_tokens: int | None
    cached_tokens: int
    completion_tokens: int | None
    decode_tps: float | None
    text: str


def get_json(url: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def managed_runtime_failure(status: dict) -> str | None:
    """Return an actionable error once the managed runtime has actually died."""
    lifecycle = status.get("runtime_lifecycle") or {}
    stage = lifecycle.get("startup_stage")
    if lifecycle.get("managed_running") is False and stage in {
        "loading_weights",
        "checking_identity",
        "failed",
    }:
        detail = lifecycle.get("last_error") or "FreeToken process exited before readiness."
        return f"Managed FreeToken startup failed during {stage}: {detail}"
    return None


def wait_until_ready(timeout_s: int) -> dict:
    deadline = time.monotonic() + timeout_s
    last_phase = None
    while time.monotonic() < deadline:
        try:
            status = get_json(f"{HARNESS_URL}/api/status")
        except Exception:
            if last_phase != "harness-starting":
                print("[Warmup] Waiting for harness HTTP...", flush=True)
                last_phase = "harness-starting"
            time.sleep(2.0)
            continue

        runtime = status.get("runtime") or {}
        phase = runtime.get("phase") or runtime.get("health_status") or "unknown"
        if runtime.get("ready"):
            print(f"[Warmup] FreeToken ready ({phase}).", flush=True)
            return status
        failure = managed_runtime_failure(status)
        if failure:
            raise RuntimeError(failure)
        if phase != last_phase:
            print(f"[Warmup] FreeToken phase: {phase}", flush=True)
            last_phase = phase
        time.sleep(2.0)
    raise TimeoutError(f"FreeToken was not ready within {timeout_s} seconds")


def stream_probe(label: str, prompt: str, max_tokens: int, timeout_s: int) -> ProbeResult:
    payload = json.dumps(
        {
            "message": prompt,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "reasoning_effort": "none",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{HARNESS_URL}/api/chat/stream",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    first = None
    last = None
    usage: dict = {}
    pieces: list[str] = []

    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
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
                if first is None:
                    first = now
                last = now
                pieces.append(piece)

    ended = time.perf_counter()
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    decode_tps = None
    if (
        completion_tokens is not None
        and completion_tokens > 1
        and first is not None
        and last is not None
        and last > first
    ):
        decode_tps = (completion_tokens - 1) / (last - first)

    return ProbeResult(
        label=label,
        ttft_s=(first - started) if first is not None else None,
        total_s=ended - started,
        prompt_tokens=prompt_tokens,
        cached_tokens=cached_tokens,
        completion_tokens=completion_tokens,
        decode_tps=decode_tps,
        text="".join(pieces).strip(),
    )


def hardware_snapshot() -> dict:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=pstate,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu,clocks.sm,clocks.mem",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip()
    except Exception as exc:
        return {"nvidia_smi_error": str(exc)}
    fields = [part.strip() for part in output.split(",")]
    names = [
        "pstate",
        "gpu_util_pct",
        "vram_used_mb",
        "vram_total_mb",
        "power_w",
        "temperature_c",
        "sm_clock_mhz",
        "memory_clock_mhz",
    ]
    return dict(zip(names, fields))


def print_probe(result: ProbeResult) -> None:
    ttft = f"{result.ttft_s:.2f}s" if result.ttft_s is not None else "n/a"
    decode = f"{result.decode_tps:.2f} tok/s" if result.decode_tps is not None else "n/a"
    print(
        f"[Warmup] {result.label}: TTFT={ttft}, total={result.total_s:.2f}s, "
        f"decode={decode}, tokens={result.completion_tokens}",
        flush=True,
    )


def save_report(primer: ProbeResult | None, performance: ProbeResult | None, status: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "status": status,
        "primer": asdict(primer) if primer else None,
        "performance": asdict(performance) if performance else None,
        "hardware": hardware_snapshot(),
    }
    (STATE_DIR / "startup-performance.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wait for Local MoE readiness, warm it, and reject abnormally slow startup states."
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--request-timeout", type=int, default=45)
    parser.add_argument("--max-primer-total", type=float, default=20.0)
    parser.add_argument("--max-ttft", type=float, default=12.0)
    parser.add_argument("--min-decode-tps", type=float, default=4.0)
    parser.add_argument("--max-total", type=float, default=40.0)
    args = parser.parse_args()

    primer: ProbeResult | None = None
    performance: ProbeResult | None = None
    try:
        wait_until_ready(args.timeout)
        primer = stream_probe(
            "primer",
            "Reply with exactly READY.",
            max_tokens=8,
            timeout_s=args.request_timeout,
        )
        print_probe(primer)
        if not primer.text:
            raise RuntimeError("primer returned no model text")
        if primer.total_s > args.max_primer_total:
            save_report(primer, None, "degraded")
            print(
                f"[Warmup] PERFORMANCE GATE FAILED: primer took {primer.total_s:.2f}s "
                f"(limit {args.max_primer_total:.2f}s).",
                flush=True,
            )
            return 3

        performance = stream_probe(
            "performance probe",
            "Explain in two concise sentences why ice floats on liquid water.",
            max_tokens=64,
            timeout_s=args.request_timeout,
        )
        print_probe(performance)
        if not performance.text:
            raise RuntimeError("performance probe returned no model text")

        failures: list[str] = []
        if performance.ttft_s is None:
            failures.append("TTFT unavailable")
        elif performance.ttft_s > args.max_ttft:
            failures.append(f"TTFT {performance.ttft_s:.2f}s > {args.max_ttft:.2f}s")
        if performance.decode_tps is None:
            failures.append("decode tok/s unavailable")
        elif performance.decode_tps < args.min_decode_tps:
            failures.append(
                f"decode {performance.decode_tps:.2f} tok/s < {args.min_decode_tps:.2f} tok/s"
            )
        if performance.total_s > args.max_total:
            failures.append(f"total {performance.total_s:.2f}s > {args.max_total:.2f}s")

        if failures:
            save_report(primer, performance, "degraded")
            print("[Warmup] PERFORMANCE GATE FAILED: " + "; ".join(failures), flush=True)
            return 3

        save_report(primer, performance, "healthy")
        print("[Warmup] Performance gate PASS.", flush=True)
        return 0
    except Exception as exc:
        save_report(primer, performance, "error")
        print(f"[Warmup] ERROR: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
