from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

Note = tuple[float, float, int, int]


@dataclass(frozen=True)
class SustainRepairConfig:
    """Conservative repair for AMT note-off/on fragmentation on one pitch."""

    join_gap_ms: float = 70.0
    min_left_duration_ms: float = 170.0
    min_right_duration_ms: float = 70.0
    reattack_velocity_jump: int = 12
    hard_join_gap_ms: float = 18.0
    overlap_join_ms: float = 90.0
    context_window_ms: float = 18.0
    context_min_other_pitches: int = 2
    context_velocity_floor: int = 34
    context_overlap_floor_ms: float = -18.0


def repair_sustain_fragments(
    notes: list[Note], config: SustainRepairConfig | None = None
) -> tuple[list[Note], int]:
    """Join likely fragments of one held piano note without flattening repeats."""
    repaired, joins, _protected = repair_sustain_fragments_detailed(notes, config)
    return repaired, joins


def repair_sustain_fragments_detailed(
    notes: list[Note], config: SustainRepairConfig | None = None
) -> tuple[list[Note], int, int]:
    """Return repaired notes, join count, and dense re-attacks protected.

    Basic Pitch can split a held pitch when frame confidence dips, but a new
    same-pitch attack that lands with the rest of a chord is often a genuine
    articulation.  Dense-passage context protects those re-attacks while the
    original sparse/dropout sustain repair remains unchanged.
    """
    if not notes:
        return [], 0, 0
    cfg = config or SustainRepairConfig()
    ordered = sorted(notes, key=lambda row: (row[0], row[2], -row[3]))
    starts = [row[0] for row in ordered]
    by_pitch: dict[int, list[Note]] = {}
    for note in ordered:
        by_pitch.setdefault(note[2], []).append(note)

    repaired: list[Note] = []
    joins = 0
    protected = 0
    for pitch_notes in by_pitch.values():
        rows = sorted(pitch_notes, key=lambda row: (row[0], row[1], -row[3]))
        merged: list[Note] = []
        for note in rows:
            if not merged:
                merged.append(note)
                continue
            prior = merged[-1]
            contextual_reattack = _has_reattack_context(note, ordered, starts, cfg)
            if _should_join(prior, note, cfg, contextual_reattack):
                merged[-1] = (
                    prior[0],
                    max(prior[1], note[1]),
                    prior[2],
                    max(prior[3], note[3]),
                )
                joins += 1
            else:
                if contextual_reattack and _would_join_without_context(prior, note, cfg):
                    protected += 1
                merged.append(note)
        repaired.extend(merged)
    return sorted(repaired, key=lambda row: (row[0], row[2], -row[3])), joins, protected


def _has_reattack_context(
    note: Note, ordered: list[Note], starts: list[float], cfg: SustainRepairConfig
) -> bool:
    window = max(0.0, cfg.context_window_ms)
    left = bisect_left(starts, note[0] - window)
    right = bisect_right(starts, note[0] + window)
    velocity_floor = max(cfg.context_velocity_floor, note[3] - 10)
    pitches = {
        other[2]
        for other in ordered[left:right]
        if other[2] != note[2] and other[3] >= velocity_floor
    }
    return len(pitches) >= max(1, cfg.context_min_other_pitches)


def _would_join_without_context(left: Note, right: Note, cfg: SustainRepairConfig) -> bool:
    return _should_join(left, right, cfg, False)


def _should_join(left: Note, right: Note, cfg: SustainRepairConfig, contextual_reattack: bool = False) -> bool:
    if left[2] != right[2] or right[0] <= left[0]:
        return False
    left_duration = max(0.0, left[1] - left[0])
    right_duration = max(0.0, right[1] - right[0])
    gap = right[0] - left[1]
    if gap < -cfg.overlap_join_ms or gap > cfg.join_gap_ms:
        return False
    if left_duration < cfg.min_left_duration_ms or right_duration < cfg.min_right_duration_ms:
        return False

    # A same-pitch onset that arrives with a new chord/beat is a strong signal
    # of deliberate re-articulation.  Only deep overlaps remain eligible to be
    # treated as segmentation fragments.
    if contextual_reattack and gap >= cfg.context_overlap_floor_ms:
        return False

    velocity_jump = right[3] - left[3]
    if gap < 0 and velocity_jump >= cfg.reattack_velocity_jump + 6:
        return False
    if gap > cfg.hard_join_gap_ms and velocity_jump >= cfg.reattack_velocity_jump:
        return False
    return True
