#!/usr/bin/env python3
"""Quiet end-to-end smoke test for an installed OmniPad UMDF keyboard.

Success prints one bounded line. Full diagnostics are stored in logs so an
agent does not need to ingest verbose per-event output unless a check fails.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import traceback
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from router import ControllerFactory, _refresh_umdf_status
from router.umdf_keyboard import UmdfKeyboardDevice
from router.vhf_keyboard import build_keyboard_report
from tools.enumerate_raw_input_keyboards import enumerate_keyboards
from tools.umdf_raw_input_probe import RawKeyboardReceiver


def run_smoke() -> Dict[str, object]:
    started = time.monotonic()
    checks: List[str] = []
    device, error = UmdfKeyboardDevice.try_open()
    if device is None:
        raise AssertionError(f"control collection unavailable: {error}")
    receiver = RawKeyboardReceiver()

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def wait_event(start: int, vkey: int, is_down: bool, timeout: float = 1.0) -> Dict[str, object]:
        def match() -> bool:
            return any(
                event["vkey"] == vkey and event["down"] == is_down
                for event in receiver.events[start:]
            )

        if not receiver.pump(timeout, match):
            raise AssertionError(f"Raw Input {'make' if is_down else 'break'} missing for VK 0x{vkey:02X}")
        return next(
            event for event in receiver.events[start:]
            if event["vkey"] == vkey and event["down"] == is_down
        )

    try:
        device.submit_report(bytes(8))
        receiver.pump(0.05)
        keyboards = enumerate_keyboards()
        check("raw_input_device", any(item["is_omnipad"] for item in keyboards))
        available, status_error = _refresh_umdf_status(force=True)
        check("factory_availability", available and not status_error)
        backend = next(
            item for item in ControllerFactory.get_available_backends()
            if item["id"] == "virtual_keyboard_port"
        )
        check("backend_selectable", backend["available"] is True)

        runtime_backend = ControllerFactory.create("virtual_keyboard_port", 99)
        try:
            start = len(receiver.events)
            runtime_backend.apply({"key_codes": ["F20"]})
            wait_event(start, 0x83, True)
            runtime_backend.release_all()
            wait_event(start, 0x83, False)
            checks.append("backend_apply_release")
        finally:
            runtime_backend.close()

        start = len(receiver.events)
        device.submit_report(build_keyboard_report(["KeyW"]))
        wait_event(start, 0x57, True)
        device.submit_report(bytes(8))
        wait_event(start, 0x57, False)
        checks.append("wasd_make_break")

        start = len(receiver.events)
        device.submit_report(build_keyboard_report(["ShiftLeft", "KeyA"]))
        wait_event(start, 0x41, True)
        device.submit_report(bytes(8))
        wait_event(start, 0x41, False)
        checks.append("modifier_chord_release")

        start = len(receiver.events)
        six_keys = [f"F{number}" for number in range(13, 19)]
        device.submit_report(build_keyboard_report(six_keys))
        receiver.pump(0.25)
        down_vkeys = {
            int(event["vkey"]) for event in receiver.events[start:] if event["down"]
        }
        check("six_key_rollover", set(range(0x7C, 0x82)).issubset(down_vkeys))
        device.submit_report(bytes(8))
        receiver.pump(0.25)

        start = len(receiver.events)
        held = build_keyboard_report(["F24"])
        device.submit_report(held)
        wait_event(start, 0x87, True)
        for _ in range(6):
            device.submit_report(held)
            receiver.pump(0.12)
        premature_release = any(
            event["vkey"] == 0x87 and event["up"] for event in receiver.events[start:]
        )
        check("heartbeat_prevents_watchdog", not premature_release)
        device.submit_report(bytes(8))
        wait_event(start, 0x87, False)

        start = len(receiver.events)
        device.submit_report(build_keyboard_report(["F23"]))
        wait_event(start, 0x86, True)
        watchdog_started = time.monotonic()
        wait_event(start, 0x86, False, timeout=1.5)
        watchdog_elapsed = time.monotonic() - watchdog_started
        check("driver_watchdog_release", 0.45 <= watchdog_elapsed <= 1.4)

        start = len(receiver.events)
        held = build_keyboard_report(["F22"])
        device.submit_report(held)
        wait_event(start, 0x85, True)
        for _ in range(20):
            device.submit_report(held)
        receiver.pump(0.1)
        make_count = sum(
            1 for event in receiver.events[start:]
            if event["vkey"] == 0x85 and event["down"]
        )
        check("duplicate_suppression", make_count == 1)
        device.submit_report(bytes(8))
        wait_event(start, 0x85, False)

        start = len(receiver.events)
        for index in range(64):
            code = "F19" if index % 2 == 0 else "F20"
            device.submit_report(build_keyboard_report([code]))
        device.submit_report(bytes(8))
        receiver.pump(1.0)
        pressed = set()
        stress_events = 0
        for event in receiver.events[start:]:
            if event["vkey"] not in (0x82, 0x83):
                continue
            stress_events += 1
            if event["down"]:
                pressed.add(event["vkey"])
            elif event["up"]:
                pressed.discard(event["vkey"])
        check("rapid_transition_final_neutral", stress_events >= 64 and not pressed)

        reopened, reopen_error = UmdfKeyboardDevice.try_open()
        check("endpoint_reopen", reopened is not None and reopen_error is None)
        if reopened:
            reopened.close()

        check("control_path", bool(device.device_path))
        return {
            "status": "PASS",
            "checks": checks,
            "check_count": len(checks),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "raw_event_count": len(receiver.events),
            "control_path": device.device_path,
            "raw_device": receiver.events[0]["device"] if receiver.events else None,
        }
    finally:
        try:
            device.release_all()
        finally:
            receiver.pump(0.1)
            receiver.close()
            device.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    log_path = ROOT / "logs" / "umdf_installed_smoke.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_smoke()
        exit_code = 0
    except Exception as exc:
        result = {
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        exit_code = 1
    log_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if result["status"] == "PASS":
        print(
            f"UMDF_SMOKE PASS checks={result['check_count']} "
            f"events={result['raw_event_count']} duration_ms={result['duration_ms']}"
        )
        if not args.quiet:
            print(json.dumps(result, indent=2))
    else:
        print(f"UMDF_SMOKE FAIL error={result['error']} log={log_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
