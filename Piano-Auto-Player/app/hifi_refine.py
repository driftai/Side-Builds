from __future__ import annotations

from dataclasses import dataclass

Note = tuple[float, float, int, int]


@dataclass(frozen=True)
class HifiRefineConfig:
    cluster_window_ms: float = 28.0
    pair_window_ms: float = 42.0
    adjacent_pitch_semitones: int = 2
    correction_min_velocity: int = 42
    correction_min_duration_ms: float = 70.0
    repeat_context_ms: float = 1200.0
    extra_max_velocity: int = 52
    extra_max_duration_ms: float = 135.0
    extra_min_agreed_chord_tones: int = 3


def refine_model_disagreements(
    specialist: list[Note], basic: list[Note], config: HifiRefineConfig | None = None
) -> tuple[list[Note], dict[str, int]]:
    """Conservatively repair obvious pitch disagreements before model fusion.

    The piano specialist remains primary. We only change a specialist note when
    the two models describe essentially the same onset/chord and disagree on a
    single nearby pitch, or when one weak/short specialist-only chord tone sits
    on top of a chord whose other tones are independently confirmed.
    """
    cfg = config or HifiRefineConfig()
    source = sorted(specialist, key=lambda row: (row[0], row[2], -row[3]))
    other = sorted(basic, key=lambda row: (row[0], row[2], -row[3]))
    if not source or not other:
        return source, {"hifi_pitch_corrections": 0, "hifi_precision_pruned_notes": 0}

    corrections: dict[int, int] = {}
    pruned: set[int] = set()
    spec_clusters = _clusters(source, cfg.cluster_window_ms)
    basic_clusters = _clusters(other, cfg.cluster_window_ms)
    pairs = pair_cluster_indexes(source, other, spec_clusters, basic_clusters, cfg.pair_window_ms)

    for s_cluster_index, s_cluster in enumerate(spec_clusters):
        b_index = pairs.get(s_cluster_index)
        if b_index is None:
            continue
        b_cluster = basic_clusters[b_index]
        s_pitches = {source[index][2] for index in s_cluster}
        b_pitches = {other[index][2] for index in b_cluster}
        common = s_pitches & b_pitches
        s_only = [index for index in s_cluster if source[index][2] not in common]
        b_only = [index for index in b_cluster if other[index][2] not in common]

        if len(s_only) == 1 and len(b_only) == 1 and len(s_cluster) == len(b_cluster):
            s_index, b_note_index = s_only[0], b_only[0]
            s_note, b_note = source[s_index], other[b_note_index]
            if _safe_pitch_correction(source, other, s_note, b_note, len(common), cfg):
                corrections[s_index] = b_note[2]
                continue

        if len(s_only) == 1 and not b_only and len(common) >= cfg.extra_min_agreed_chord_tones:
            s_index = s_only[0]
            if _safe_extra_prune(source, source[s_index], cfg):
                pruned.add(s_index)

    refined: list[Note] = []
    for index, note in enumerate(source):
        if index in pruned:
            continue
        replacement = corrections.get(index)
        if replacement is None:
            refined.append(note)
        else:
            refined.append((note[0], note[1], replacement, note[3]))
    refined = _dedupe(refined)
    return refined, {
        "hifi_pitch_corrections": len(corrections),
        "hifi_precision_pruned_notes": len(pruned),
    }


def _safe_pitch_correction(
    specialist: list[Note], basic: list[Note], source: Note, alternate: Note,
    agreed_tones: int, cfg: HifiRefineConfig,
) -> bool:
    if abs(source[2] - alternate[2]) > cfg.adjacent_pitch_semitones:
        return False
    if alternate[3] < cfg.correction_min_velocity:
        return False
    if alternate[1] - alternate[0] < cfg.correction_min_duration_ms:
        return False
    if agreed_tones >= 2:
        return True
    # Solo-note corrections need continuity evidence so a chromatic melody is
    # not rewritten merely because the two models disagree on one attack.
    basic_repeat = _same_pitch_neighbors(basic, alternate, cfg.repeat_context_ms)
    specialist_repeat = _same_pitch_neighbors(specialist, source, cfg.repeat_context_ms)
    return basic_repeat >= 1 and specialist_repeat == 0


def _safe_extra_prune(notes: list[Note], note: Note, cfg: HifiRefineConfig) -> bool:
    duration = max(0.0, note[1] - note[0])
    if note[3] > cfg.extra_max_velocity or duration > cfg.extra_max_duration_ms:
        return False
    return _same_pitch_neighbors(notes, note, cfg.repeat_context_ms) == 0


def _same_pitch_neighbors(notes: list[Note], note: Note, window_ms: float) -> int:
    count = 0
    for other in notes:
        if other is note or other == note:
            continue
        distance = abs(other[0] - note[0])
        if distance > window_ms:
            continue
        if distance > 40.0 and other[2] == note[2]:
            count += 1
    return count


def _clusters(notes: list[Note], window_ms: float) -> list[list[int]]:
    clusters: list[list[int]] = []
    current: list[int] = []
    anchor = 0.0
    for index, note in enumerate(notes):
        if not current or note[0] - anchor <= window_ms:
            if not current:
                anchor = note[0]
            current.append(index)
        else:
            clusters.append(current)
            current = [index]
            anchor = note[0]
    if current:
        clusters.append(current)
    return clusters


def pair_cluster_indexes(
    specialist: list[Note], basic: list[Note], spec_clusters: list[list[int]],
    basic_clusters: list[list[int]], pair_window_ms: float,
) -> dict[int, int]:
    used: set[int] = set()
    pairs: dict[int, int] = {}
    for s_index, cluster in enumerate(spec_clusters):
        anchor = min(specialist[i][0] for i in cluster)
        best = None
        best_distance = pair_window_ms + 1.0
        for b_index, b_cluster in enumerate(basic_clusters):
            if b_index in used:
                continue
            other_anchor = min(basic[i][0] for i in b_cluster)
            distance = abs(other_anchor - anchor)
            if distance <= pair_window_ms and distance < best_distance:
                best = b_index
                best_distance = distance
            if other_anchor > anchor + pair_window_ms:
                break
        if best is not None:
            pairs[s_index] = best
            used.add(best)
    return pairs


def _dedupe(notes: list[Note]) -> list[Note]:
    ordered = sorted(notes, key=lambda row: (row[0], row[2], -row[3], -(row[1] - row[0])))
    kept: list[Note] = []
    for note in ordered:
        duplicate = next((row for row in reversed(kept) if note[0] - row[0] <= 14.0 and row[2] == note[2]), None)
        if duplicate is None:
            kept.append(note)
            continue
        if (note[3], note[1] - note[0]) > (duplicate[3], duplicate[1] - duplicate[0]):
            kept.remove(duplicate)
            kept.append(note)
    return sorted(kept, key=lambda row: (row[0], row[2], -row[3]))
