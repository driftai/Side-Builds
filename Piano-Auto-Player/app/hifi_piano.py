from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .hifi_diagnostics import hifi_diagnostics
from .hifi_onset import AcousticOnset, acoustic_pacing_delay
from .hifi_refine import refine_model_disagreements
from .hifi_sustain import stitch_consensus_sustain
from .hifi_sparse import rescue_sparse_attacks, sparse_cluster_timing
from .hifi_timing import stabilize_cluster_shifts

Note = tuple[float, float, int, int]


@dataclass(frozen=True)
class HifiFusionConfig:
    onset_tolerance_ms: float = 55.0
    end_blend_tolerance_ms: float = 220.0
    minimum_specialist_duration_ms: float = 28.0
    minimum_specialist_velocity: int = 4
    repeat_context_ms: float = 1800.0
    chord_context_ms: float = 28.0
    timing_cluster_ms: float = 14.0
    timing_blend_weight: float = 0.25
    timing_deadband_ms: float = 8.0
    timing_early_shift_max_ms: float = 1.0
    timing_max_shift_ms: float = 4.0
    release_disagreement_floor_ms: float = 10.0
    basic_rescue_velocity: int = 42
    basic_rescue_duration_ms: float = 70.0
    auto_min_f1: float = 0.30
    auto_min_count_ratio: float = 0.42
    auto_max_count_ratio: float = 2.15


def fuse_piano_models(
    specialist_notes: list[Note], basic_notes: list[Note], config: HifiFusionConfig | None = None,
    acoustic_onsets: list[AcousticOnset] | None = None,
) -> tuple[list[Note], dict[str, object]]:
    """Use an interval-level piano model as primary and Basic Pitch as evidence.

    v0.6.7 keeps model diagnostics tied to the untouched source predictions,
    then applies a conservative pitch/extra-note reconciliation before the
    existing exact-pitch fusion and Basic-only rescue rules.
    """
    cfg = config or HifiFusionConfig()
    specialist = _dedupe_specialist(specialist_notes, cfg)
    basic = sorted(basic_notes, key=lambda row: (row[0], row[2], -row[3]))
    raw_matches = _collect_matches(specialist, basic, cfg.onset_tolerance_ms)
    raw_agreements = len(raw_matches)
    raw_f1 = 2.0 * raw_agreements / max(1, len(specialist) + len(basic))

    refined, refine_stats = refine_model_disagreements(specialist, basic)
    matched_basic: set[int] = set()
    fused: list[Note] = []
    refined_agreements = 0
    by_pitch: dict[int, list[tuple[int, Note]]] = {}
    for index, note in enumerate(basic):
        by_pitch.setdefault(note[2], []).append((index, note))

    matches_by_index: dict[int, tuple[int, Note]] = {}
    for refined_index, note in enumerate(refined):
        match = _nearest_match(note, by_pitch.get(note[2], []), matched_basic, cfg.onset_tolerance_ms)
        if match is None:
            continue
        basic_index, _other = match
        matched_basic.add(basic_index)
        matches_by_index[refined_index] = match
        refined_agreements += 1

    timing_adjustments, timing_stats = _coherent_timing_adjustments(
        refined, matches_by_index, cfg, acoustic_onsets=acoustic_onsets
    )
    release_stats: dict[str, float | int] = {
        "hifi_release_secondary_shorter_ignored": 0,
        "hifi_release_secondary_tails_ignored": 0,
        "hifi_attack_release_overhang_guarded": 0,
        "hifi_attack_release_overhang_ms": 0.0,
    }
    for refined_index, note in enumerate(refined):
        adjustment = timing_adjustments.get(refined_index, 0.0)
        match = matches_by_index.get(refined_index)
        if match is None:
            fused.append(_shift_note(note, adjustment, release_stats))
            continue
        _basic_index, other = match
        fused.append(_blend(note, other, cfg, adjustment, release_stats))

    specialist_context = sorted(fused, key=lambda row: (row[0], row[2], -row[3]))
    rescued = 0
    for index, note in enumerate(basic):
        if index in matched_basic:
            continue
        if _basic_only_rescue(note, specialist_context, cfg):
            fused.append(note)
            specialist_context.append(note)
            specialist_context.sort(key=lambda row: (row[0], row[2], -row[3]))
            rescued += 1

    sparse_rescues, sparse_stats = rescue_sparse_attacks(
        basic, matched_basic, specialist_context, acoustic_onsets
    )
    fused.extend(sparse_rescues)

    fused, sustain_stats = stitch_consensus_sustain(
        fused, specialist, basic, acoustic_onsets=acoustic_onsets
    )
    fused = _dedupe_specialist(fused, cfg)
    count_ratio = len(specialist) / max(1, len(basic))
    refined_f1 = 2.0 * refined_agreements / max(1, len(refined) + len(basic))
    stats: dict[str, object] = {
        "hifi_specialist_notes": len(specialist),
        "hifi_basic_notes": len(basic),
        "hifi_model_agreements": raw_agreements,
        "hifi_agreement_f1": round(raw_f1, 4),
        "hifi_refined_model_agreements": refined_agreements,
        "hifi_refined_agreement_f1": round(refined_f1, 4),
        "hifi_count_ratio": round(count_ratio, 4),
        "hifi_basic_rescued_notes": rescued,
        "hifi_fused_notes": len(fused),
        **refine_stats,
        **timing_stats,
        **release_stats,
        **sparse_stats,
        **sustain_stats,
    }
    stats.update(hifi_diagnostics(specialist, basic, raw_matches, cfg.onset_tolerance_ms))
    return fused, stats


def _collect_matches(specialist: list[Note], basic: list[Note], tolerance: float) -> list[tuple[Note, Note]]:
    by_pitch: dict[int, list[tuple[int, Note]]] = {}
    for index, note in enumerate(basic):
        by_pitch.setdefault(note[2], []).append((index, note))
    used: set[int] = set()
    matches: list[tuple[Note, Note]] = []
    for note in specialist:
        match = _nearest_match(note, by_pitch.get(note[2], []), used, tolerance)
        if match is None:
            continue
        index, other = match
        used.add(index)
        matches.append((note, other))
    return matches

def auto_accept_specialist(stats: dict[str, object], config: HifiFusionConfig | None = None) -> bool:
    cfg = config or HifiFusionConfig()
    try:
        f1 = float(stats.get("hifi_agreement_f1", 0.0))
        ratio = float(stats.get("hifi_count_ratio", 0.0))
        count = int(stats.get("hifi_specialist_notes", 0))
    except (TypeError, ValueError):
        return False
    return count >= 12 and f1 >= cfg.auto_min_f1 and cfg.auto_min_count_ratio <= ratio <= cfg.auto_max_count_ratio


def _nearest_match(note: Note, rows: list[tuple[int, Note]], used: set[int], tolerance: float):
    best = None
    best_distance = tolerance + 1.0
    for index, other in rows:
        if index in used:
            continue
        distance = abs(other[0] - note[0])
        if distance <= tolerance and distance < best_distance:
            best = (index, other)
            best_distance = distance
        if other[0] > note[0] + tolerance:
            break
    return best


def _coherent_timing_adjustments(
    notes: list[Note], matches: dict[int, tuple[int, Note]], cfg: HifiFusionConfig,
    acoustic_onsets: list[AcousticOnset] | None = None,
) -> tuple[dict[int, float], dict[str, object]]:
    adjustments: dict[int, float] = {}
    clusters: list[list[int]] = []
    current: list[int] = []
    anchor = 0.0
    for index, note in enumerate(notes):
        if not current or note[0] - anchor <= cfg.timing_cluster_ms:
            if not current:
                anchor = note[0]
            current.append(index)
        else:
            clusters.append(current)
            current = [index]
            anchor = note[0]
    if current:
        clusters.append(current)

    capped_clusters = early_guarded = 0
    acoustic_clusters = acoustic_notes = acoustic_dense = acoustic_phrase = 0
    acoustic_max = 0.0
    sparse_clusters = sparse_acoustic_bypassed = 0
    raw_shifts: list[float] = []
    sparse_flags: list[bool] = []
    anchors: list[float] = []
    for cluster in clusters:
        cluster_anchor = sum(notes[index][0] for index in cluster) / len(cluster)
        anchors.append(cluster_anchor)
        deltas = [matches[index][1][0] - notes[index][0] for index in cluster if index in matches]
        model_shift = 0.0
        if deltas:
            ordered = sorted(deltas)
            middle = len(ordered) // 2
            median_delta = ordered[middle] if len(ordered) % 2 else 0.5 * (ordered[middle - 1] + ordered[middle])
            if abs(median_delta) > cfg.timing_deadband_ms:
                raw_shift = cfg.timing_blend_weight * median_delta
                lower = -max(0.0, cfg.timing_early_shift_max_ms)
                upper = max(0.0, cfg.timing_max_shift_ms)
                model_shift = max(lower, min(upper, raw_shift))
                capped_clusters += int(raw_shift < lower - 1e-9 or raw_shift > upper + 1e-9)
                early_guarded += int(raw_shift < lower - 1e-9)

        acoustic_shift, acoustic_reason = acoustic_pacing_delay(
            notes, cluster, matches, acoustic_onsets
        )
        sparse, sparse_shift = sparse_cluster_timing(notes, cluster, matches)
        sparse_flags.append(sparse)
        if sparse:
            shift = sparse_shift
            sparse_clusters += 1
            sparse_acoustic_bypassed += int(acoustic_shift > 0.0)
        else:
            shift = max(model_shift, acoustic_shift) if acoustic_shift > 0.0 else model_shift
            if acoustic_shift > 0.0 and acoustic_shift > model_shift + 0.001:
                acoustic_clusters += 1
                acoustic_notes += len(cluster)
                acoustic_dense += int(acoustic_reason == "dense")
                acoustic_phrase += int(acoustic_reason == "phrase")
                acoustic_max = max(acoustic_max, acoustic_shift)
        raw_shifts.append(shift)

    stable_shifts, relative_stats = stabilize_cluster_shifts(
        anchors, raw_shifts, independent=sparse_flags
    )
    adjusted_clusters = shifted_notes = 0
    max_shift = 0.0
    for cluster, shift in zip(clusters, stable_shifts):
        if abs(shift) < 0.001:
            continue
        adjusted_clusters += 1
        max_shift = max(max_shift, abs(shift))
        for index in cluster:
            adjustments[index] = shift
            shifted_notes += 1
    return adjustments, {
        "hifi_timing_clusters_adjusted": adjusted_clusters,
        "hifi_timing_notes_shifted": shifted_notes,
        "hifi_timing_adjustments_capped": capped_clusters,
        "hifi_timing_early_shifts_guarded": early_guarded,
        "hifi_timing_deadband_ms": round(cfg.timing_deadband_ms, 3),
        "hifi_timing_max_shift_ms": round(max_shift, 3),
        "hifi_acoustic_onset_peaks": len(acoustic_onsets or []),
        "hifi_acoustic_clusters_delayed": acoustic_clusters,
        "hifi_acoustic_notes_delayed": acoustic_notes,
        "hifi_acoustic_dense_delays": acoustic_dense,
        "hifi_acoustic_phrase_delays": acoustic_phrase,
        "hifi_acoustic_max_delay_ms": round(acoustic_max, 3),
        "hifi_sparse_timing_clusters": sparse_clusters,
        "hifi_sparse_acoustic_bypassed": sparse_acoustic_bypassed,
        **relative_stats,
    }


def _shift_note(
    note: Note, adjustment: float, release_stats: dict[str, float | int] | None = None,
) -> Note:
    """Move an attack without dragging its absolute release later.

    Onset refinements correct *when the key goes down*. Transkun's note-off is
    an independent absolute estimate and stays anchored to the source timeline.
    This avoids turning a later onset correction into artificial extra sustain.
    """
    if abs(adjustment) < 0.001:
        return note
    start = note[0] + adjustment
    end = note[1]
    minimum = min(12.0, max(1.0, note[1] - note[0]))
    if end < start + minimum:
        end = start + minimum
    if adjustment > 0.5 and release_stats is not None:
        release_stats["hifi_attack_release_overhang_guarded"] = int(
            release_stats.get("hifi_attack_release_overhang_guarded", 0)
        ) + 1
        release_stats["hifi_attack_release_overhang_ms"] = round(
            float(release_stats.get("hifi_attack_release_overhang_ms", 0.0)) + adjustment, 3
        )
    return (round(start, 3), round(end, 3), note[2], note[3])


def _blend(
    specialist: Note, basic: Note, cfg: HifiFusionConfig, adjustment: float = 0.0,
    release_stats: dict[str, float | int] | None = None,
) -> Note:
    """Refine attack timing while keeping the specialist's absolute note-off.

    v0.6.11 let Basic Pitch lengthen Transkun releases. In sustained/pedaled
    piano that can confuse lingering acoustic energy with a physically held key
    and make phrases smear into the next attack. v0.6.13 restores Transkun as
    the note-off authority. Cross-model sustain stitching remains the narrow
    mechanism for repairing a proven false release/repress split.
    """
    start = specialist[0] + adjustment
    end = specialist[1]
    specialist_duration = max(1.0, specialist[1] - specialist[0])
    basic_duration = max(1.0, basic[1] - basic[0])
    delta = basic[1] - specialist[1]

    if release_stats is not None:
        if delta < -cfg.release_disagreement_floor_ms:
            release_stats["hifi_release_secondary_shorter_ignored"] = int(
                release_stats.get("hifi_release_secondary_shorter_ignored", 0)
            ) + 1
        elif delta > cfg.release_disagreement_floor_ms:
            release_stats["hifi_release_secondary_tails_ignored"] = int(
                release_stats.get("hifi_release_secondary_tails_ignored", 0)
            ) + 1
        if adjustment > 0.5:
            release_stats["hifi_attack_release_overhang_guarded"] = int(
                release_stats.get("hifi_attack_release_overhang_guarded", 0)
            ) + 1
            release_stats["hifi_attack_release_overhang_ms"] = round(
                float(release_stats.get("hifi_attack_release_overhang_ms", 0.0)) + adjustment, 3
            )

    # A correction may move the onset toward the original release. Preserve a
    # tiny playable duration, but never inherit the secondary model's pedal tail.
    end = max(start + min(12.0, specialist_duration, basic_duration), end)
    velocity = specialist[3] if specialist[3] > 0 else basic[3]
    return (round(start, 3), round(end, 3), specialist[2], max(1, min(127, int(velocity))))

def _basic_only_rescue(note: Note, specialist: list[Note], cfg: HifiFusionConfig) -> bool:
    start, end, pitch, velocity = note
    duration = end - start
    if velocity < cfg.basic_rescue_velocity or duration < cfg.basic_rescue_duration_ms:
        return False
    before = after = None
    chord = 0
    for other in specialist:
        delta = other[0] - start
        distance = abs(delta)
        if other[2] == pitch and distance <= cfg.repeat_context_ms:
            if delta < 0 and (before is None or distance < before):
                before = distance
            elif delta > 0 and (after is None or distance < after):
                after = distance
        if other[2] != pitch and distance <= cfg.chord_context_ms:
            chord += 1
    if before is not None and after is not None and before + after <= 2600.0:
        return True
    return chord >= 2 and velocity >= 52 and duration >= 95.0


def _dedupe_specialist(notes: list[Note], cfg: HifiFusionConfig) -> list[Note]:
    ordered = sorted(notes, key=lambda row: (row[0], row[2], -row[3], -(row[1] - row[0])))
    kept: list[Note] = []
    last_by_pitch: dict[int, Note] = {}
    for note in ordered:
        start, end, pitch, velocity = note
        if end - start < cfg.minimum_specialist_duration_ms or velocity < cfg.minimum_specialist_velocity:
            continue
        prior = last_by_pitch.get(pitch)
        if prior and abs(start - prior[0]) <= 12.0:
            if (velocity, end - start) <= (prior[3], prior[1] - prior[0]):
                continue
            try:
                kept.remove(prior)
            except ValueError:
                pass
        kept.append(note)
        last_by_pitch[pitch] = note
    return sorted(kept, key=lambda row: (row[0], row[2], -row[3]))


def hifi_python(root: Path) -> str:
    env = Path(root) / ".piano-hifi-venv"
    for path in (env / "Scripts" / "python.exe", env / "bin" / "python"):
        if path.exists():
            return str(path)
    return ""

def probe_hifi(root: Path) -> dict[str, str | bool]:
    python = hifi_python(root)
    if not python:
        return {"ready": False, "python": "", "version": "", "device": "", "issue": "Run setup-hifi-piano.bat once."}
    version = _probe(python, "import importlib.metadata as m; import transkun.transcribe; print(m.version('transkun'))")
    if not version:
        return {"ready": False, "python": python, "version": "", "device": "", "issue": "Transkun runtime is incomplete. Re-run setup-hifi-piano.bat."}
    device = _probe(python, "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')") or "cpu"
    return {"ready": True, "python": python, "version": version, "device": device, "issue": ""}


def _probe(python: str, code: str) -> str:
    try:
        result = subprocess.run([python, "-c", code], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or "").strip() if result.returncode == 0 else ""

