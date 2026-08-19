from typing import Any

from .parser import parse_sheet
from .playback import PlaybackController, PlaybackOptions
from .piano_layout import target_midi_notes
from .performance_notes import target_note_spans


def _row(index: int, kind: str, token: str, at_ms: float, duration_ms: float, midi_notes=None) -> dict[str, Any]:
    row = {
        "event_index": index,
        "kind": kind,
        "key": token if kind != "pause" else "",
        "token": token,
        "at_ms": round(max(0.0, at_ms), 3),
        "duration_ms": round(max(0.0, duration_ms), 3),
    }
    if midi_notes: row["midi_notes"] = list(midi_notes)
    return row


def build_sheet_preview(sheet: str, options: PlaybackOptions) -> dict[str, Any]:
    events = parse_sheet(sheet, options.timing_profile)
    if not events:
        raise ValueError("The sheet did not contain playable events.")

    speed = PlaybackController._speed(options)
    unit_ms = max(options.interval_ms, 1.0) / speed
    timeline_units = 0.0
    rows: list[dict[str, int | float | str]] = []
    duration_ms = 0.0

    for zero_index, event in enumerate(events):
        at_ms = timeline_units * unit_ms
        if event.kind == "pause":
            pause_ms = max(0.0, event.units) * unit_ms
            rows.append(_row(zero_index + 1, "pause", event.value, at_ms, pause_ms))
            timeline_units += event.units
            duration_ms = max(duration_ms, at_ms + pause_ms)
            continue

        gap_units = PlaybackController._gap_to_next_onset(events, zero_index)
        hold_ms = PlaybackController._sheet_hold_ms(event, gap_units, options, speed)
        rows.append(_row(zero_index + 1, event.kind, event.value, at_ms, hold_ms))
        timeline_units += event.units
        duration_ms = max(duration_ms, at_ms + hold_ms)

    return {
        "events": rows,
        "total_events": len(events),
        "duration_ms": round(duration_ms, 3),
        "timing_profile": options.timing_profile,
    }


def build_performance_preview(raw_events: list[dict[str, Any]], options: PlaybackOptions) -> dict[str, Any]:
    events = PlaybackController._clean_performance(raw_events)
    if not events:
        raise ValueError("The recording has no playable notes.")

    speed = PlaybackController._speed(options)
    base_at_ms = float(events[0]["at_ms"])
    rows: list[dict[str, int | float | str]] = []
    duration_ms = 0.0
    for zero_index, event in enumerate(events):
        at_ms = (float(event["at_ms"]) - base_at_ms) / speed
        spans = target_note_spans(event, options.piano_layout)
        if spans:
            scaled_spans = [{
                "midi": span["midi"],
                "offset_ms": round(float(span["offset_ms"]) / speed, 3),
                "duration_ms": round(float(span["duration_ms"]) / speed, 3),
                "velocity": span["velocity"],
            } for span in spans]
            hold_ms = max(span["offset_ms"] + span["duration_ms"] for span in scaled_spans)
            mapped_midi = list(dict.fromkeys(span["midi"] for span in scaled_spans))
        else:
            if str(options.timing_profile).lower() == "midi":
                hold_ms = max(1.0, float(event["duration_ms"]) / speed)
                if zero_index + 1 < len(events):
                    gap_ms = max(1.0, (float(events[zero_index + 1]["at_ms"]) - float(event["at_ms"])) / speed)
                    gate = max(0.10, min(options.gate_percent / 100.0, 0.90))
                    hold_ms = min(hold_ms, max(10.0, gap_ms * gate))
            else:
                hold_ms = PlaybackController._performance_hold_ms(events, zero_index, options, speed)
            mapped_midi = target_midi_notes(event.get("midi_notes") or [], options.piano_layout)
        token = str(event["key"])
        note_total = len(mapped_midi) if mapped_midi else len(token)
        row = _row(zero_index + 1, "chord" if note_total > 1 else "note", token, at_ms, hold_ms, mapped_midi)
        if spans:
            row["note_spans"] = scaled_spans
        rows.append(row)
        duration_ms = max(duration_ms, at_ms + hold_ms)

    return {
        "events": rows,
        "total_events": len(events),
        "duration_ms": round(duration_ms, 3),
        "timing_profile": options.timing_profile,
    }
