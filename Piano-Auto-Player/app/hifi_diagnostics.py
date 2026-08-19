from __future__ import annotations

from math import ceil, floor
from statistics import median

Note = tuple[float, float, int, int]
Match = tuple[Note, Note]


def hifi_diagnostics(
    specialist: list[Note],
    basic: list[Note],
    matches: list[Match],
    onset_tolerance_ms: float,
    window_ms: float = 5000.0,
) -> dict[str, object]:
    """Build model-family agreement sensors without changing any note decisions."""
    spec_count = len(specialist)
    basic_count = len(basic)
    match_count = len(matches)
    deltas = [other[0] - note[0] for note, other in matches]
    abs_deltas = [abs(value) for value in deltas]
    windows = _window_rows(specialist, basic, matches, onset_tolerance_ms, window_ms)
    review = [row for row in windows if row["level"] == "review"]
    scored = [row for row in windows if isinstance(row.get("confidence_proxy"), (int, float))]
    dense_scored = [row for row in scored if row.get("level") != "sparse"]
    worst = min(dense_scored or scored, key=lambda row: float(row["confidence_proxy"]), default=None)
    return {
        "hifi_specialist_coverage": round(match_count / max(1, spec_count), 4),
        "hifi_basic_coverage": round(match_count / max(1, basic_count), 4),
        "hifi_onset_median_offset_ms": round(float(median(deltas)), 3) if deltas else 0.0,
        "hifi_onset_median_abs_ms": round(float(median(abs_deltas)), 3) if abs_deltas else 0.0,
        "hifi_onset_p95_abs_ms": round(_percentile(abs_deltas, 0.95), 3) if abs_deltas else 0.0,
        "hifi_onset_max_abs_ms": round(max(abs_deltas), 3) if abs_deltas else 0.0,
        "hifi_window_ms": round(max(1000.0, float(window_ms)), 3),
        "hifi_window_count": len(windows),
        "hifi_review_window_count": len(review),
        "hifi_worst_window_start_ms": int(worst["start_ms"]) if worst else 0,
        "hifi_worst_window_confidence": round(float(worst["confidence_proxy"]), 4) if worst else 0.0,
        "hifi_windows": windows,
    }


def _window_rows(
    specialist: list[Note],
    basic: list[Note],
    matches: list[Match],
    tolerance_ms: float,
    window_ms: float,
) -> list[dict[str, object]]:
    width = max(1000.0, float(window_ms))
    duration = max([note[1] for note in specialist + basic], default=0.0)
    window_count = max(1, int(ceil(max(duration, 1.0) / width)))
    matched_spec = {id(note) for note, _other in matches}
    matched_basic = {id(other) for _note, other in matches}
    rows: list[dict[str, object]] = []
    for index in range(window_count):
        start = index * width
        end = min(duration, (index + 1) * width) if duration else (index + 1) * width
        spec = [note for note in specialist if start <= note[0] < start + width]
        base = [note for note in basic if start <= note[0] < start + width]
        spec_matches = sum(1 for note in spec if id(note) in matched_spec)
        basic_matches = sum(1 for note in base if id(note) in matched_basic)
        local_deltas = [other[0] - note[0] for note, other in matches if start <= note[0] < start + width]
        total = len(spec) + len(base)
        agreement = (spec_matches + basic_matches) / total if total else None
        timing_p95 = _percentile([abs(value) for value in local_deltas], 0.95) if local_deltas else None
        confidence = _confidence_proxy(agreement, timing_p95, tolerance_ms) if agreement is not None else None
        level = _level(confidence, total)
        rows.append({
            "start_ms": int(round(start)),
            "end_ms": int(round(max(start, end))),
            "specialist_notes": len(spec),
            "basic_notes": len(base),
            "matched_specialist": spec_matches,
            "matched_basic": basic_matches,
            "agreement_f1": round(float(agreement), 4) if agreement is not None else None,
            "onset_p95_abs_ms": round(float(timing_p95), 3) if timing_p95 is not None else None,
            "confidence_proxy": round(float(confidence), 4) if confidence is not None else None,
            "level": level,
        })
    return rows


def _confidence_proxy(agreement: float, timing_p95: float | None, tolerance_ms: float) -> float:
    timing = 0.0 if timing_p95 is None else max(0.0, 1.0 - timing_p95 / max(1.0, tolerance_ms))
    return max(0.0, min(1.0, 0.82 * agreement + 0.18 * timing))


def _level(confidence: float | None, note_total: int) -> str:
    if confidence is None:
        return "silent"
    if note_total < 6:
        return "sparse"
    if confidence >= 0.72:
        return "strong"
    if confidence >= 0.50:
        return "mixed"
    return "review"


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * max(0.0, min(1.0, float(quantile)))
    lower = floor(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction
