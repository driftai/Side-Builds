from __future__ import annotations

from typing import Any

from .piano_layout import PianoStroke, stroke_for_midi

_ALLOWED_KEYS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@$%^*(")
_SHIFT_BASE = {"!": "1", "@": "2", "$": "4", "%": "5", "^": "6", "*": "8", "(": "9"}


def clean_performance(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in raw[:20000]:
        event = clean_performance_event(item)
        if event:
            cleaned.append(event)
    return sorted(cleaned, key=lambda row: float(row["at_ms"]))


def clean_performance_event(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    key = "".join(char for char in str(item.get("key") or "") if char in _ALLOWED_KEYS)[:16]
    midi_notes = _clean_midi_notes(item.get("midi_notes"))
    spans = _clean_note_spans(item.get("note_spans"))
    for span in spans:
        if span["midi"] not in midi_notes:
            midi_notes.append(span["midi"])
    if not key and not midi_notes:
        return None
    try:
        at_ms = max(0.0, float(item.get("at_ms", 0)))
        duration_ms = max(1.0, min(5000.0, float(item.get("duration_ms", 35))))
    except (TypeError, ValueError):
        return None
    if spans:
        duration_ms = max(duration_ms, max(span["offset_ms"] + span["duration_ms"] for span in spans))
    row: dict[str, Any] = {
        "key": key,
        "at_ms": round(at_ms, 3),
        "duration_ms": round(min(duration_ms, 5000.0), 3),
        "midi_notes": midi_notes,
    }
    if spans:
        row["note_spans"] = spans
    return row


def target_note_spans(event: dict[str, Any], layout: str) -> list[dict[str, Any]]:
    raw_spans = event.get("note_spans")
    if not isinstance(raw_spans, list) or not raw_spans:
        return []
    mapped: dict[tuple[str, bool], dict[str, Any]] = {}
    for span in raw_spans:
        try:
            source_midi = int(span.get("midi"))
            offset_ms = max(0.0, min(5000.0, float(span.get("offset_ms", 0.0))))
            duration_ms = max(1.0, min(5000.0, float(span.get("duration_ms", event.get("duration_ms", 35.0)))))
            velocity = max(0, min(127, int(float(span.get("velocity", 0)))))
        except (AttributeError, TypeError, ValueError):
            continue
        stroke = stroke_for_midi(source_midi, layout)
        if not stroke:
            continue
        identity = (stroke.char, bool(stroke.ctrl))
        candidate = {
            "source_midi": source_midi,
            "midi": stroke.midi,
            "char": stroke.char,
            "ctrl": bool(stroke.ctrl),
            "offset_ms": round(offset_ms, 3),
            "duration_ms": round(duration_ms, 3),
            "velocity": velocity,
            "physical_id": physical_key_id(stroke),
        }
        prior = mapped.get(identity)
        if prior is None or _prefer_span(candidate, prior):
            mapped[identity] = candidate
    return sorted(mapped.values(), key=lambda span: (span["offset_ms"], span["midi"], -span["velocity"]))


def physical_key_id(stroke: PianoStroke | dict[str, Any]) -> str:
    char = stroke.char if isinstance(stroke, PianoStroke) else str(stroke.get("char") or "")
    if not char:
        return ""
    base = _SHIFT_BASE.get(char, char.lower())
    return base[:1].lower()


def span_stroke(span: dict[str, Any]) -> PianoStroke:
    return PianoStroke(str(span["char"]), bool(span.get("ctrl")), int(span.get("midi") or 0))


def _prefer_span(candidate: dict[str, Any], prior: dict[str, Any]) -> bool:
    if candidate["velocity"] != prior["velocity"]:
        return candidate["velocity"] > prior["velocity"]
    return candidate["duration_ms"] > prior["duration_ms"]


def _clean_midi_notes(raw: Any) -> list[int]:
    result: list[int] = []
    if not isinstance(raw, list):
        return result
    for note in raw[:16]:
        try:
            value = int(note)
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 127 and value not in result:
            result.append(value)
    return result


def _clean_note_spans(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[int, float]] = set()
    for item in raw[:32]:
        if not isinstance(item, dict):
            continue
        try:
            midi = int(item.get("midi"))
            offset = max(0.0, min(5000.0, float(item.get("offset_ms", 0.0))))
            duration = max(1.0, min(5000.0, float(item.get("duration_ms", 35.0))))
            velocity = max(0, min(127, int(float(item.get("velocity", 0)))))
        except (TypeError, ValueError):
            continue
        if not 0 <= midi <= 127:
            continue
        identity = (midi, round(offset, 3))
        if identity in seen:
            continue
        seen.add(identity)
        result.append({
            "midi": midi,
            "offset_ms": round(offset, 3),
            "duration_ms": round(duration, 3),
            "velocity": velocity,
        })
    return sorted(result, key=lambda span: (span["offset_ms"], span["midi"], -span["velocity"]))
