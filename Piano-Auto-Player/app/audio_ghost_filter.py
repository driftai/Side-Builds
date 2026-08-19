from __future__ import annotations

from dataclasses import dataclass

Note = tuple[float, float, int, int]


@dataclass(frozen=True)
class GhostGuardConfig:
    strong_velocity: int = 34
    weak_velocity: int = 24
    short_note_ms: float = 92.0
    sustained_note_ms: float = 170.0
    sustained_velocity: int = 24
    neighbor_window_ms: float = 92.0
    chord_window_ms: float = 18.0
    chord_semitones: int = 127
    same_pitch_window_ms: float = 220.0
    nearby_semitones: int = 12
    outlier_semitones: int = 24
    two_sided_below_velocity: int = 24


def conservative_ghost_config() -> GhostGuardConfig:
    """Lower-recall guard for mixed audio while retaining fast piano attacks."""
    return GhostGuardConfig(
        strong_velocity=42,
        weak_velocity=28,
        short_note_ms=78.0,
        sustained_note_ms=210.0,
        sustained_velocity=38,
        neighbor_window_ms=86.0,
        chord_window_ms=13.0,
        chord_semitones=19,
        same_pitch_window_ms=180.0,
        nearby_semitones=9,
        outlier_semitones=19,
        two_sided_below_velocity=37,
    )


def filter_ghost_notes(notes: list[Note], config: GhostGuardConfig | None = None) -> tuple[list[Note], int]:
    """Drop weak, isolated AMT detections without flattening fast runs."""
    if not notes:
        return [], 0
    cfg = config or GhostGuardConfig()
    ordered = sorted(notes, key=lambda note: (note[0], note[2], -note[3]))
    keep: list[Note] = []
    dropped = 0
    for index, note in enumerate(ordered):
        if _keep_note(ordered, index, cfg):
            keep.append(note)
        else:
            dropped += 1
    return keep, dropped


def _keep_note(notes: list[Note], index: int, cfg: GhostGuardConfig) -> bool:
    start, end, pitch, velocity = notes[index]
    duration = max(0.0, end - start)
    if velocity >= cfg.strong_velocity:
        return True
    if velocity < cfg.weak_velocity:
        return False

    nearby = _neighbors(notes, index, cfg.neighbor_window_ms)
    if _is_register_outlier(nearby, start, pitch, cfg):
        return False
    if _same_pitch_support(nearby, start, pitch, cfg.same_pitch_window_ms):
        return True
    if _chord_support(nearby, start, pitch, velocity, cfg):
        return True
    if _run_support(nearby, start, pitch, velocity, cfg):
        return True
    if duration >= cfg.sustained_note_ms and velocity >= cfg.sustained_velocity:
        return True
    if velocity >= cfg.strong_velocity - 3 and duration >= cfg.short_note_ms:
        return True
    return False


def _neighbors(notes: list[Note], index: int, window_ms: float) -> list[Note]:
    start = notes[index][0]
    rows: list[Note] = []
    cursor = index - 1
    while cursor >= 0 and start - notes[cursor][0] <= max(window_ms, 240.0):
        rows.append(notes[cursor])
        cursor -= 1
    cursor = index + 1
    while cursor < len(notes) and notes[cursor][0] - start <= max(window_ms, 240.0):
        rows.append(notes[cursor])
        cursor += 1
    return rows


def _same_pitch_support(nearby: list[Note], start: float, pitch: int, window_ms: float) -> bool:
    return any(other[2] == pitch and abs(other[0] - start) <= window_ms for other in nearby)


def _chord_support(nearby: list[Note], start: float, pitch: int, velocity: int, cfg: GhostGuardConfig) -> bool:
    for other in nearby:
        if abs(other[0] - start) > cfg.chord_window_ms:
            continue
        if abs(other[2] - pitch) > cfg.chord_semitones:
            continue
        if other[3] >= cfg.strong_velocity or other[3] >= velocity + 7:
            return True
    return False


def _run_support(nearby: list[Note], start: float, pitch: int, velocity: int, cfg: GhostGuardConfig) -> bool:
    before = [
        other for other in nearby
        if 0 < start - other[0] <= cfg.neighbor_window_ms
        and abs(other[2] - pitch) <= cfg.nearby_semitones
    ]
    after = [
        other for other in nearby
        if 0 < other[0] - start <= cfg.neighbor_window_ms
        and abs(other[2] - pitch) <= cfg.nearby_semitones
    ]
    if before and after:
        return True
    if velocity >= cfg.two_sided_below_velocity and (before or after):
        return True
    return False


def _is_register_outlier(nearby: list[Note], start: float, pitch: int, cfg: GhostGuardConfig) -> bool:
    strong = [
        other for other in nearby
        if abs(other[0] - start) <= cfg.neighbor_window_ms
        and other[3] >= cfg.strong_velocity
    ]
    return bool(strong and min(abs(other[2] - pitch) for other in strong) > cfg.outlier_semitones)
