from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path


class BenchmarkStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, result: dict) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.root / f"benchmark-{stamp}.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return path


def summarize_completion(started: float, response: dict, prompt: str) -> dict:
    elapsed = max(time.perf_counter() - started, 1e-9)
    usage = response.get("usage", {}) or {}
    completion_tokens = usage.get("completion_tokens")
    token_count_source = "runtime_usage"

    if completion_tokens is None:
        # Compatibility fallback only. Keep it explicitly labeled so estimated
        # word counts cannot be mistaken for real model token throughput.
        try:
            message = response["choices"][0]["message"]
            text = (message.get("content") or "") + (message.get("reasoning_content") or "")
        except Exception:
            text = ""
        completion_tokens = max(1, round(len(text.split()) * 1.33)) if text else 0
        token_count_source = "word_estimate"

    end_to_end_tps = completion_tokens / elapsed if completion_tokens else 0.0
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "elapsed_seconds": round(elapsed, 4),
        "completion_tokens": completion_tokens,
        "token_count_source": token_count_source,
        "end_to_end_tps": round(end_to_end_tps, 2),
        # Backward compatibility for old consumers.
        "approx_tps": round(end_to_end_tps, 2),
        "usage": usage,
        "response": response,
    }
