#!/usr/bin/env python3
"""Fail-fast, low-noise aggregator for the complete OmniPad smoke suite."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RESULT_PATH = ROOT / "test-results" / "smoke.json"
SUITES = (
    ("architecture", "tools/check_architecture.py"),
    ("architecture_gate", "tests/test_architecture_gate.py"),
    ("smoke_runner", "tests/test_smoke_runner.py"),
    ("control_center", "tests/test_control_center.py"),
    ("install_repair", "tests/test_install_repair.py"),
    ("security", "tests/test_security.py"),
    ("security_boundaries", "tests/test_security_boundaries.py"),
    ("websocket_security", "tests/test_websocket_security.py"),
    ("targeting", "tests/test_targeting.py"),
    ("runtime_efficiency", "tests/test_runtime_efficiency.py"),
    ("keyboard_bridge", "tests/test_keyboard_bridge.py"),
    ("background_keyboard_helper", "tests/test_background_keyboard_helper.py"),
    ("vhf_keyboard", "tests/test_vhf_keyboard.py"),
    ("umdf_keyboard", "tests/test_umdf_keyboard.py"),
    ("raw_input_keyboards", "tests/test_raw_input_keyboards.py"),
    ("backend_transitions", "tests/test_backend_transitions.py"),
    ("surface_output_routing", "tests/test_surface_output_routing.py"),
    ("input_pipeline", "tests/test_input_pipeline.py"),
    ("surface_combinations_e2e", "tests/test_surface_combinations_e2e.py"),
    ("touch_controller", "tests/test_touch_controller.py"),
    ("touch_controller_layouts", "tests/test_touch_controller_layouts.py"),
    ("remote_player_input", "tests/test_remote_player_input_features.py"),
    ("player_websocket_join", "tests/test_player_websocket_join.py"),
    ("server_live", "tests/test_server_live.py"),
    ("core", "tests/smoke_test.py"),
)
ACTIONABLE_MARKERS = ("warning", "traceback", "[error]", " error:", "deprecated")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="show complete passing output")
    parser.add_argument("--timeout", type=float, default=300.0, help="per-stage timeout in seconds")
    return parser.parse_args()


def run_stage(stage_id: str, script: str, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    command = [sys.executable, str(ROOT / script)]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=timeout,
            check=False,
        )
        return {
            "id": stage_id,
            "script": script,
            "status": "pass" if result.returncode == 0 else "fail",
            "returncode": result.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "id": stage_id,
            "script": script,
            "status": "timeout",
            "returncode": None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout": stdout,
            "stderr": stderr,
        }


def write_result(payload: dict[str, Any]) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def relevant_lines(stage: dict[str, Any], limit: int = 40) -> list[str]:
    combined = "\n".join((stage.get("stdout", ""), stage.get("stderr", ""))).strip()
    lines = combined.splitlines()
    return lines[-limit:]


def actionable_lines(stage: dict[str, Any]) -> list[str]:
    combined = "\n".join((stage.get("stdout", ""), stage.get("stderr", "")))
    return [line for line in combined.splitlines() if any(marker in line.casefold() for marker in ACTIONABLE_MARKERS)]


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    stages: list[dict[str, Any]] = []

    for stage_id, script in SUITES:
        stage = run_stage(stage_id, script, args.timeout)
        stages.append(stage)
        if args.verbose:
            print(f"[{stage['status'].upper()}] {stage_id} ({stage['elapsed_seconds']:.3f}s)")
            if stage["stdout"]:
                print(stage["stdout"], end="" if stage["stdout"].endswith("\n") else "\n")
            if stage["stderr"]:
                print(stage["stderr"], file=sys.stderr, end="" if stage["stderr"].endswith("\n") else "\n")
        if stage["status"] != "pass":
            break

    elapsed = round(time.monotonic() - started, 3)
    passed = sum(stage["status"] == "pass" for stage in stages)
    failed = next((stage for stage in stages if stage["status"] != "pass"), None)
    alerts = [
        {"stage": stage["id"], "lines": actionable_lines(stage)}
        for stage in stages
        if actionable_lines(stage)
    ]
    payload = {
        "status": "fail" if failed else "pass",
        "passed": passed,
        "total": len(SUITES),
        "elapsed_seconds": elapsed,
        "alerts": alerts,
        "stages": stages,
    }
    write_result(payload)

    if failed:
        print(
            f"FAIL smoke: {passed}/{len(SUITES)} stages; "
            f"stage={failed['id']} status={failed['status']}; details: {RESULT_PATH}"
        )
        if not args.verbose:
            for line in relevant_lines(failed):
                print(line)
        return 1

    alert_text = f", {sum(len(item['lines']) for item in alerts)} alert line(s)" if alerts else ""
    print(
        f"PASS smoke: {passed}/{len(SUITES)} stages in {elapsed:.3f}s{alert_text}; "
        f"details: {RESULT_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
