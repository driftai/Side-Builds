from __future__ import annotations

from dataclasses import dataclass
from statistics import median

Note = tuple[float, float, int, int]


@dataclass(frozen=True)
class StabilityConfig:
    """Adaptive pruning for heavily fragmented full-mix transcriptions."""

    activation_join_ratio: float = 0.18
    activation_min_joins: int = 80
    cluster_window_ms: float = 14.0
    neighbor_window_ms: float = 170.0
    chord_score_margin: float = 10.0
    max_dense_chord: int = 4
    max_wide_chord: int = 3
    wide_chord_semitones: int = 24
    singleton_velocity_ceiling: int = 55
    singleton_short_ms: float = 105.0
    singleton_outlier_semitones: int = 16


def consensus_stability_config() -> StabilityConfig:
    """Milder dense-chord pruning after multi-pass consensus agreement.

    The single-decode guard was intentionally strict for noisy full mixes.
    Consensus mode has already rejected threshold-unstable notes, so dense
    clusters get one extra voice before pruning to avoid damaging legitimate
    piano chords and fast expert passages.
    """
    return StabilityConfig(
        chord_score_margin=14.0,
        max_dense_chord=5,
        max_wide_chord=4,
        wide_chord_semitones=28,
    )


def reduce_unstable_notes(
    notes: list[Note], raw_count: int, sustain_joins: int, config: StabilityConfig | None = None
) -> tuple[list[Note], int, bool]:
    """Reduce phantom voices only when AMT fragmentation is unusually high.

    A very high same-pitch repair count is a useful signal that the source is
    acoustically difficult for the transcription model.  In that case we prune
    short register outliers and oversized onset stacks by local support instead
    of globally increasing thresholds, which would also delete real fast notes.
    """
    if not notes:
        return [], 0, False
    cfg = config or StabilityConfig()
    ratio = sustain_joins / max(1, int(raw_count))
    if sustain_joins < cfg.activation_min_joins or ratio < cfg.activation_join_ratio:
        return list(notes), 0, False

    ordered = sorted(notes, key=lambda row: (row[0], row[2], -row[3]))
    clusters = _clusters(ordered, cfg.cluster_window_ms)
    anchors = [_cluster_anchor(cluster) for cluster in clusters]
    kept: list[Note] = []
    dropped = 0

    for index, cluster in enumerate(clusters):
        if len(cluster) == 1:
            note = cluster[0]
            if _isolated_short_outlier(note, anchors, index, cfg):
                dropped += 1
            else:
                kept.append(note)
            continue

        chosen = _reduce_cluster(cluster, anchors, index, cfg)
        kept.extend(chosen)
        dropped += len(cluster) - len(chosen)

    return sorted(kept, key=lambda row: (row[0], row[2], -row[3])), dropped, True


def _clusters(notes: list[Note], window_ms: float) -> list[list[Note]]:
    rows: list[list[Note]] = []
    current: list[Note] = []
    anchor = 0.0
    for note in notes:
        if not current or note[0] - anchor <= window_ms:
            if not current:
                anchor = note[0]
            current.append(note)
        else:
            rows.append(current)
            current = [note]
            anchor = note[0]
    if current:
        rows.append(current)
    return rows


def _cluster_anchor(cluster: list[Note]) -> tuple[float, float, int]:
    start = min(note[0] for note in cluster)
    strongest = max(cluster, key=lambda row: (row[3], row[1] - row[0]))
    center = float(median(note[2] for note in cluster))
    return start, center, strongest[2]


def _reduce_cluster(
    cluster: list[Note], anchors: list[tuple[float, float, int]], index: int, cfg: StabilityConfig
) -> list[Note]:
    by_pitch: dict[int, Note] = {}
    for note in cluster:
        prior = by_pitch.get(note[2])
        if prior is None or (note[3], note[1] - note[0]) > (prior[3], prior[1] - prior[0]):
            by_pitch[note[2]] = note
    unique = list(by_pitch.values())
    if len(unique) <= 2:
        return sorted(unique, key=lambda row: row[2])

    span = max(note[2] for note in unique) - min(note[2] for note in unique)
    maximum = cfg.max_wide_chord if span > cfg.wide_chord_semitones else cfg.max_dense_chord
    scores = [(note, _note_score(note, anchors, index, cfg)) for note in unique]
    scores.sort(key=lambda item: item[1], reverse=True)
    top = scores[0][1]
    chosen = [note for note, score in scores if score >= top - cfg.chord_score_margin][:maximum]

    # Preserve at least the two strongest voices of a real multi-note attack.
    if len(chosen) < 2:
        chosen = [note for note, _score in scores[:2]]
    return sorted(chosen, key=lambda row: row[2])


def _note_score(note: Note, anchors: list[tuple[float, float, int]], index: int, cfg: StabilityConfig) -> float:
    start, end, pitch, velocity = note
    duration = max(0.0, end - start)
    score = float(velocity) + min(12.0, duration / 45.0)
    for offset in (-2, -1, 1, 2):
        other_index = index + offset
        if not 0 <= other_index < len(anchors):
            continue
        other_start, other_center, other_pitch = anchors[other_index]
        if abs(other_start - start) > cfg.neighbor_window_ms:
            continue
        if abs(other_pitch - pitch) <= 5:
            score += 7.0
        elif abs(other_center - pitch) <= 8:
            score += 4.0
    return score


def _isolated_short_outlier(
    note: Note, anchors: list[tuple[float, float, int]], index: int, cfg: StabilityConfig
) -> bool:
    start, end, pitch, velocity = note
    if velocity >= cfg.singleton_velocity_ceiling or end - start >= cfg.singleton_short_ms:
        return False
    nearby: list[float] = []
    for offset in (-2, -1, 1, 2):
        other_index = index + offset
        if not 0 <= other_index < len(anchors):
            continue
        other_start, center, _strongest = anchors[other_index]
        if abs(other_start - start) <= cfg.neighbor_window_ms:
            nearby.append(center)
    return bool(nearby and min(abs(center - pitch) for center in nearby) > cfg.singleton_outlier_semitones)
