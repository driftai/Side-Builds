#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
HARNESS_URL = "http://127.0.0.1:5180"
RUNTIME_URL = "http://127.0.0.1:1919"
SYSTEM_PROMPT = "You are a helpful local AI assistant."
PASS_TEXT = "LONG_CONTEXT_OK"


def request_json(url: str, *, payload: dict | None = None, timeout: float = 10.0) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def runtime_commit() -> str:
    try:
        data = json.loads((ROOT / "config" / "runtime-lock.json").read_text(encoding="utf-8"))
        return str((data.get("freetoken") or {}).get("source_commit") or "unknown")
    except Exception:
        return "unknown"


def gpu_identity() -> dict:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
            timeout=5,
        ).strip()
        name, driver = [part.strip() for part in output.split(",", 1)]
        return {"name": name, "driver": driver}
    except Exception as exc:
        return {"name": "unknown", "driver": f"unknown:{exc}"}


def served_model() -> str:
    status = request_json(f"{HARNESS_URL}/api/status", timeout=5)
    models = ((status.get("runtime") or {}).get("models") or [])
    model = models[0].get("id") if models else None
    if not model:
        raise RuntimeError("Harness is online but no served model was reported")
    return str(model)


def count_prompt(model: str, message: str) -> int:
    doc = request_json(
        f"{RUNTIME_URL}/v1/messages/count_tokens",
        payload={
            "model": model,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": message}],
        },
        timeout=20,
    )
    value = doc.get("input_tokens")
    if not isinstance(value, int) or value <= 0:
        raise RuntimeError(f"invalid token-count response: {doc!r}")
    return value


def build_target_message(model: str, target_tokens: int) -> tuple[str, int]:
    repeats = max(64, target_tokens // 3)
    suffix = f"\n\nReply with exactly {PASS_TEXT}."
    message = ""
    counted = 0
    for _ in range(6):
        message = ("context safety checkpoint " * repeats) + suffix
        counted = count_prompt(model, message)
        if abs(counted - target_tokens) <= 96:
            break
        repeats = max(1, int(repeats * target_tokens / max(counted, 1)))
    if counted > target_tokens + 128:
        scale = max(0.5, target_tokens / counted)
        repeats = max(1, int(repeats * scale))
        message = ("context safety checkpoint " * repeats) + suffix
        counted = count_prompt(model, message)
    return message, counted


def stream_chat(
    message: str,
    timeout_s: int,
    *,
    max_tokens: int,
    reasoning_effort: str,
) -> dict:
    body = json.dumps(
        {
            "message": message,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{HARNESS_URL}/api/chat/stream",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first = None
    content_pieces: list[str] = []
    reasoning_pieces: list[str] = []
    metadata: dict = {}
    usage: dict = {}
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
                raise RuntimeError(str(chunk["error"]))
            if chunk.get("harness_context"):
                metadata = chunk["harness_context"]
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            delta = choices[0].get("delta", {}) if choices else {}
            content_piece = delta.get("content") or ""
            reasoning_piece = delta.get("reasoning_content") or ""
            if content_piece or reasoning_piece:
                if first is None:
                    first = time.perf_counter()
                if content_piece:
                    content_pieces.append(content_piece)
                if reasoning_piece:
                    reasoning_pieces.append(reasoning_piece)
    ended = time.perf_counter()
    return {
        "text": "".join(content_pieces).strip(),
        "reasoning": "".join(reasoning_pieces).strip(),
        "ttft_s": (first - started) if first is not None else None,
        "total_s": ended - started,
        "context": metadata,
        "usage": usage,
    }


def write_report(path: Path, payload: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that the extended Local MoE profile survives a large cold prefill."
    )
    parser.add_argument("--target-tokens", type=int, default=6800)
    parser.add_argument("--kv-reserve", type=int, required=True)
    parser.add_argument("--max-prefill", type=int, required=True)
    parser.add_argument("--d2d", type=int, choices=(0, 1), required=True)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--reasoning-effort", default="none")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    report_path = STATE_DIR / "context-safety.json"
    pass_path = STATE_DIR / "context-safety-pass.json"

    key = {
        "runtime_commit": runtime_commit(),
        "gpu": gpu_identity(),
        "kv_reserve": args.kv_reserve,
        "max_prefill": args.max_prefill,
        "d2d": args.d2d,
        "target_tokens": args.target_tokens,
        "max_tokens": args.max_tokens,
        "reasoning_effort": args.reasoning_effort,
    }

    if not args.force and pass_path.exists():
        try:
            cached = json.loads(pass_path.read_text(encoding="utf-8"))
        except Exception:
            cached = {}
        if cached.get("key") == key and cached.get("status") == "healthy":
            result = cached.get("result") or {}
            print(
                "[ContextGate] Cached PASS "
                f"(cold prompt={result.get('counted_prompt_tokens', 'unknown')} tokens, "
                f"total={result.get('total_s', 'unknown')}s).",
                flush=True,
            )
            return 0

    model = served_model()
    message, counted = build_target_message(model, args.target_tokens)
    print(
        f"[ContextGate] Cold-prefill safety test: target={args.target_tokens}, "
        f"counted={counted}, chunk={args.max_prefill}.",
        flush=True,
    )

    payload = {"key": key, "status": "error", "result": None, "timestamp": time.time()}
    try:
        result = stream_chat(
            message,
            args.timeout,
            max_tokens=args.max_tokens,
            reasoning_effort=args.reasoning_effort,
        )
        text = result["text"]
        health = request_json(f"{RUNTIME_URL}/health", timeout=5)
        if health.get("status") != "ok":
            raise RuntimeError(f"FreeToken health failed after long prefill: {health!r}")
        if PASS_TEXT not in text:
            raise RuntimeError(f"long-context probe returned unexpected text: {text[:200]!r}")
        harness_prompt = (result.get("context") or {}).get("prompt_tokens")
        payload["status"] = "healthy"
        payload["result"] = {
            "counted_prompt_tokens": counted,
            "harness_prompt_tokens": harness_prompt,
            "ttft_s": result["ttft_s"],
            "total_s": result["total_s"],
            "completion_tokens": (result.get("usage") or {}).get("completion_tokens"),
            "text": text,
            "reasoning_chars": len(result.get("reasoning") or ""),
        }
        write_report(report_path, payload)
        write_report(pass_path, payload)
        ttft = f"{result['ttft_s']:.2f}s" if result["ttft_s"] is not None else "n/a"
        print(
            f"[ContextGate] PASS: {counted} token cold prompt survived; "
            f"TTFT={ttft}, total={result['total_s']:.2f}s.",
            flush=True,
        )
        return 0
    except Exception as exc:
        payload["error"] = str(exc)
        write_report(report_path, payload)
        print(f"[ContextGate] FAILED: {exc}", flush=True)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
