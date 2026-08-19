from __future__ import annotations

from dataclasses import dataclass

Note = tuple[float, float, int, int]
AcousticOnset = tuple[float, float]


@dataclass(frozen=True)
class AcousticPacingConfig:
    """Delay-only acoustic guard for model onsets that arrive perceptually early."""

    search_after_ms: float = 44.0
    minimum_delay_ms: float = 6.0
    maximum_delay_ms: float = 20.0
    minimum_peak_strength: float = 0.16
    basic_later_floor_ms: float = 4.0
    dense_radius_ms: float = 95.0
    dense_note_floor: int = 4
    phrase_gap_ms: float = 115.0


def acoustic_pacing_delay(
    notes: list[Note],
    cluster: list[int],
    matches: dict[int, tuple[int, Note]],
    acoustic_onsets: list[AcousticOnset] | None,
    config: AcousticPacingConfig | None = None,
) -> tuple[float, str]:
    """Return a conservative later-only shift for one onset cluster.

    A cluster is delayed only when the waveform has a nearby later onset peak and
    Basic Pitch independently trends later than the specialist. Dense passages
    and phrase starts are eligible because they are where tiny anticipations are
    most audible; sparse expressive timing is otherwise left untouched.
    """
    if not cluster or not acoustic_onsets:
        return 0.0, ""
    cfg = config or AcousticPacingConfig()
    starts = [notes[index][0] for index in cluster]
    anchor = sum(starts) / len(starts)
    deltas = [matches[index][1][0] - notes[index][0] for index in cluster if index in matches]
    if not deltas:
        return 0.0, ""
    ordered = sorted(deltas)
    middle = len(ordered) // 2
    median_delta = ordered[middle] if len(ordered) % 2 else 0.5 * (ordered[middle - 1] + ordered[middle])
    later_votes = sum(delta >= cfg.basic_later_floor_ms for delta in deltas)
    if median_delta < cfg.basic_later_floor_ms and later_votes * 2 < len(deltas):
        return 0.0, ""

    peak = _later_peak(anchor, acoustic_onsets, cfg)
    if peak is None:
        return 0.0, ""
    peak_ms, strength = peak
    peak_delta = peak_ms - anchor
    if peak_delta < cfg.minimum_delay_ms:
        return 0.0, ""

    nearby = sum(abs(note[0] - anchor) <= cfg.dense_radius_ms for note in notes)
    dense = len(cluster) >= 2 or nearby >= cfg.dense_note_floor
    phrase = _phrase_start(notes, anchor, cfg.phrase_gap_ms)
    if not dense and not phrase:
        return 0.0, ""

    # Trust the waveform most when it and the second model both say "later".
    support = max(cfg.basic_later_floor_ms, median_delta)
    blended = 0.72 * peak_delta + 0.28 * min(peak_delta, support)
    if strength >= 0.55 and later_votes == len(deltas):
        blended = max(blended, 0.82 * peak_delta)
    delay = min(cfg.maximum_delay_ms, max(0.0, blended))
    if delay < cfg.minimum_delay_ms:
        return 0.0, ""
    return round(delay, 3), "dense" if dense else "phrase"


def _later_peak(anchor: float, onsets: list[AcousticOnset], cfg: AcousticPacingConfig) -> AcousticOnset | None:
    candidates = [
        onset for onset in onsets
        if cfg.minimum_delay_ms <= onset[0] - anchor <= cfg.search_after_ms
        and onset[1] >= cfg.minimum_peak_strength
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda onset: (onset[1] - 0.008 * (onset[0] - anchor), -onset[0]))


def _phrase_start(notes: list[Note], anchor: float, gap_ms: float) -> bool:
    previous = [note[0] for note in notes if note[0] < anchor - 1.0]
    if not previous:
        return True
    return anchor - max(previous) >= gap_ms
