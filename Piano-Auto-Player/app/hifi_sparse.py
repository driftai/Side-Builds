from __future__ import annotations

from dataclasses import dataclass
from statistics import median

Note = tuple[float, float, int, int]
AcousticOnset = tuple[float, float]


@dataclass(frozen=True)
class SparseFidelityConfig:
    """Conservative rules for exposed, low-density piano passages."""

    texture_radius_ms: float = 105.0
    texture_note_ceiling: int = 4
    cluster_note_ceiling: int = 2
    passage_radius_ms: float = 420.0
    passage_note_floor: int = 5
    passage_note_ceiling: int = 14
    legacy_timing_weight: float = 0.25
    legacy_timing_max_ms: float = 9.0
    rescue_min_velocity: int = 48
    rescue_min_duration_ms: float = 85.0
    rescue_acoustic_window_ms: float = 18.0
    rescue_min_peak_strength: float = 0.42
    rescue_onset_clearance_ms: float = 34.0
    rescue_neighbor_window_ms: float = 850.0
    rescue_max_interval: int = 24
    rescue_spacing_ms: float = 72.0


def sparse_cluster_timing(
    notes: list[Note], cluster: list[int], matches: dict[int, tuple[int, Note]],
    config: SparseFidelityConfig | None = None,
) -> tuple[bool, float]:
    """Use the proven light 75/25-era timing blend for exposed passages.

    Dense/chordal material keeps the newer acoustic/relative timing solver. In
    sparse material, each audible attack is exposed, so a false waveform peak
    can be more damaging than a small model offset. We therefore fall back to
    the older conservative quarter-weight Basic Pitch timing that tested well.
    """
    if not cluster:
        return False, 0.0
    cfg = config or SparseFidelityConfig()
    anchor = sum(notes[index][0] for index in cluster) / len(cluster)
    nearby = sum(abs(note[0] - anchor) <= cfg.texture_radius_ms for note in notes)
    passage = sum(abs(note[0] - anchor) <= cfg.passage_radius_ms for note in notes)
    sparse = (
        len(cluster) <= cfg.cluster_note_ceiling
        and nearby <= cfg.texture_note_ceiling
        and cfg.passage_note_floor <= passage <= cfg.passage_note_ceiling
    )
    if not sparse:
        return False, 0.0

    deltas = [matches[index][1][0] - notes[index][0] for index in cluster if index in matches]
    if not deltas:
        return True, 0.0
    shift = cfg.legacy_timing_weight * float(median(deltas))
    shift = max(-cfg.legacy_timing_max_ms, min(cfg.legacy_timing_max_ms, shift))
    return True, round(shift, 3)


def rescue_sparse_attacks(
    basic: list[Note], matched_basic: set[int], fused: list[Note],
    acoustic_onsets: list[AcousticOnset] | None,
    config: SparseFidelityConfig | None = None,
) -> tuple[list[Note], dict[str, int]]:
    """Recover a missing exposed attack only with independent waveform proof.

    The ordinary rescue path is intentionally chord/repetition oriented. That
    can miss a single melody/arpeggio attack when Transkun drops the onset
    entirely. Here Basic Pitch must provide a strong, sustained candidate and
    the source waveform must contain a strong onset at the same moment. We also
    require the specialist/fused stream to have no competing onset there.
    """
    cfg = config or SparseFidelityConfig()
    if not acoustic_onsets:
        return [], {"hifi_sparse_attack_rescues": 0, "hifi_sparse_rescue_candidates": 0}

    context = sorted(fused, key=lambda row: (row[0], row[2], -row[3]))
    rescued: list[Note] = []
    candidates = 0
    for index, note in enumerate(basic):
        if index in matched_basic:
            continue
        start, end, pitch, velocity = note
        if velocity < cfg.rescue_min_velocity or end - start < cfg.rescue_min_duration_ms:
            continue
        if any(abs(other[0] - start) <= cfg.rescue_onset_clearance_ms for other in context):
            continue
        strength = _acoustic_strength(acoustic_onsets, start, cfg.rescue_acoustic_window_ms)
        if strength < cfg.rescue_min_peak_strength:
            continue
        if any(abs(other[0] - start) < cfg.rescue_spacing_ms for other in rescued):
            continue
        candidates += 1
        if not _melodically_plausible(context, note, cfg):
            continue
        rescued.append(note)
        context.append(note)
        context.sort(key=lambda row: (row[0], row[2], -row[3]))

    return rescued, {
        "hifi_sparse_attack_rescues": len(rescued),
        "hifi_sparse_rescue_candidates": candidates,
    }


def _acoustic_strength(onsets: list[AcousticOnset], at_ms: float, window_ms: float) -> float:
    nearby = [float(strength) for onset_ms, strength in onsets if abs(float(onset_ms) - at_ms) <= window_ms]
    return max(nearby, default=0.0)


def _melodically_plausible(context: list[Note], note: Note, cfg: SparseFidelityConfig) -> bool:
    before = [row for row in context if 0.0 < note[0] - row[0] <= cfg.rescue_neighbor_window_ms]
    after = [row for row in context if 0.0 < row[0] - note[0] <= cfg.rescue_neighbor_window_ms]
    neighbors: list[Note] = []
    if before:
        neighbors.append(max(before, key=lambda row: row[0]))
    if after:
        neighbors.append(min(after, key=lambda row: row[0]))
    if not neighbors:
        return False
    return min(abs(row[2] - note[2]) for row in neighbors) <= cfg.rescue_max_interval
