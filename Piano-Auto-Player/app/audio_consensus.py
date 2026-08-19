from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median

Note = tuple[float, float, int, int]
Row = tuple[int, str, Note, float, float]
CORE_PASSES = {"sensitive", "primary", "strict"}


@dataclass(frozen=True)
class ConsensusConfig:
    onset_tolerance_ms: float = 34.0
    minimum_passes: int = 2
    strong_primary_velocity: int = 58
    strong_primary_duration_ms: float = 95.0
    rescue_tonal_floor: float = 0.72
    rescue_spectral_floor: float = 0.52
    rescue_velocity_floor: int = 32
    rescue_duration_ms: float = 65.0
    repeat_context_ms: float = 1900.0
    repeat_span_ms: float = 2800.0
    repeat_symmetry_ratio: float = 2.4
    chord_context_ms: float = 30.0
    rescue_fraction: float = 0.045
    rescue_absolute_cap: int = 64
    prune_tonal_ceiling: float = 0.34
    prune_spectral_ceiling: float = 0.10


def load_consensus_notes(path: Path, config: ConsensusConfig | None = None) -> tuple[list[Note], dict[str, int | float]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    passes = payload.get("passes") if isinstance(payload, dict) else None
    if not isinstance(passes, list) or len(passes) < 2:
        raise ValueError("Basic Pitch consensus output did not contain enough decode passes.")
    rows: list[Row] = []
    for pass_index, item in enumerate(passes):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"pass{pass_index}")
        for raw in item.get("notes") or []:
            if not isinstance(raw, list) or len(raw) < 4:
                continue
            try:
                note = (float(raw[0]), float(raw[1]), int(raw[2]), int(raw[3]))
                tonal = float(raw[4]) if len(raw) >= 5 else 0.5
                spectral = float(raw[5]) if len(raw) >= 6 else tonal
            except (TypeError, ValueError):
                continue
            rows.append((
                pass_index, name, note,
                max(0.0, min(1.0, tonal)),
                max(0.0, min(1.0, spectral)),
            ))
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    analysis_dict = analysis if isinstance(analysis, dict) else None
    notes, stats = merge_consensus_detections(rows, len(passes), config, analysis_dict)
    if analysis_dict is not None:
        acoustic = _clean_acoustic_onsets(analysis_dict.get("acoustic_onsets"))
        if acoustic:
            stats["_acoustic_onsets"] = acoustic
            stats["acoustic_onset_peaks"] = len(acoustic)
    return notes, stats



def _clean_acoustic_onsets(raw) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    if not isinstance(raw, list):
        return result
    for item in raw[:12000]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            at_ms = max(0.0, float(item[0]))
            strength = max(0.0, min(1.0, float(item[1])))
        except (TypeError, ValueError):
            continue
        result.append((round(at_ms, 3), round(strength, 4)))
    return sorted(result)

def merge_consensus_detections(
    rows, pass_count: int, config: ConsensusConfig | None = None, analysis: dict | None = None
) -> tuple[list[Note], dict[str, int | float]]:
    cfg = config or ConsensusConfig()
    normalized = [_normalize_row(row) for row in rows]
    by_pitch: dict[int, list[Row]] = {}
    for row in normalized:
        by_pitch.setdefault(row[2][2], []).append(row)

    candidates = []
    for pitch_rows in by_pitch.values():
        for group in _onset_groups(pitch_rows, cfg.onset_tolerance_ms):
            candidates.append(_candidate(group, cfg))
    candidates.sort(key=lambda item: (item["start"], item["pitch"]))

    strong_context = [item for item in candidates if item["keep"]]
    evidence = {id(item): _context_evidence(item, strong_context, cfg) for item in candidates}
    initial_kept = len(strong_context)
    rescue_budget = min(
        cfg.rescue_absolute_cap,
        max(4, int(round(initial_kept * cfg.rescue_fraction))),
    ) if initial_kept else 0
    rescue_candidates = []
    for item in candidates:
        if item["keep"]:
            continue
        score = _rescue_score(item, evidence[id(item)], cfg)
        if score is not None:
            rescue_candidates.append((score, item))
    rescue_candidates.sort(key=lambda pair: pair[0], reverse=True)
    for _score, item in rescue_candidates[:rescue_budget]:
        item["keep"] = True
        item["rescued"] = True

    percussive_ratio = _float_stat(analysis, "percussive_ratio")
    pruned = 0
    for item in candidates:
        if not item["keep"] or item["rescued"]:
            continue
        if _should_prune(item, evidence[id(item)], cfg, percussive_ratio):
            item["keep"] = False
            item["pruned"] = True
            pruned += 1

    merged = [
        (item["start"], max(item["end"], item["start"] + 1.0), item["pitch"], item["velocity"])
        for item in candidates if item["keep"]
    ]
    merged.sort(key=lambda row: (row[0], row[2], -row[3]))
    supported_all = sum(1 for item in candidates if item["initial_keep"] and item["support"] >= 3)
    supported_two = sum(1 for item in candidates if item["initial_keep"] and item["support"] == 2)
    strong_single = sum(1 for item in candidates if item["strong_single"])
    recovery_candidates = sum(1 for item in candidates if item["recovery"] and item["support"] < 2)
    rescued = sum(1 for item in candidates if item["rescued"])
    final_rejected = sum(1 for item in candidates if not item["keep"])
    stats: dict[str, int | float] = {
        "consensus_candidate_notes": len(candidates),
        "consensus_kept_notes": len(merged),
        "consensus_rejected_notes": final_rejected,
        "consensus_all_pass_notes": supported_all,
        "consensus_two_pass_notes": supported_two,
        "consensus_strong_single_notes": strong_single,
        "consensus_recovery_candidates": recovery_candidates,
        "consensus_rescue_candidates": len(rescue_candidates),
        "consensus_rescue_budget": rescue_budget,
        "consensus_rescue_suppressed": max(0, len(rescue_candidates) - rescued),
        "consensus_precision_rescued_notes": rescued,
        "consensus_context_rescued_notes": rescued,
        "consensus_spectral_pruned_notes": pruned,
        "consensus_tonal_pruned_notes": pruned,
    }
    if percussive_ratio is not None:
        stats["consensus_percussive_ratio"] = round(percussive_ratio, 4)
    return merged, stats


def _float_stat(analysis: dict | None, key: str) -> float | None:
    if not analysis:
        return None
    try:
        return max(0.0, min(1.0, float(analysis.get(key))))
    except (TypeError, ValueError):
        return None


def _normalize_row(row) -> Row:
    tonal = float(row[3]) if len(row) >= 4 and isinstance(row[3], (int, float)) else 0.5
    spectral = float(row[4]) if len(row) >= 5 and isinstance(row[4], (int, float)) else tonal
    return (
        int(row[0]), str(row[1]), row[2],
        max(0.0, min(1.0, tonal)), max(0.0, min(1.0, spectral)),
    )


def _candidate(group: list[Row], cfg: ConsensusConfig) -> dict:
    best = _best_per_pass(group)
    names = set(best)
    core_names = names & CORE_PASSES
    if not core_names and "recovery" not in names:
        core_names = names
    core = [best[name] for name in core_names]
    merge_rows = core or list(best.values())
    notes = [row[2] for row in merge_rows]
    start = float(median(note[0] for note in notes))
    end = float(median(note[1] for note in notes))
    velocity = int(round(median(note[3] for note in notes)))
    support = len(core_names)
    primary = best.get("primary")
    strong_single = False
    keep = support >= cfg.minimum_passes
    if not keep and support == 1 and primary is not None:
        duration = max(0.0, primary[2][1] - primary[2][0])
        strong_single = primary[2][3] >= cfg.strong_primary_velocity and duration >= cfg.strong_primary_duration_ms
        keep = strong_single
    return {
        "start": start, "end": end, "pitch": notes[0][2], "velocity": velocity,
        "tonal": float(median(row[3] for row in best.values())),
        "spectral": float(median(row[4] for row in best.values())),
        "names": core_names, "support": support, "recovery": "recovery" in names,
        "keep": keep, "initial_keep": keep, "strong_single": strong_single,
        "rescued": False, "pruned": False,
    }


def _context_evidence(item: dict, strong: list[dict], cfg: ConsensusConfig) -> dict:
    start, pitch = item["start"], item["pitch"]
    before = after = None
    same_pc = 0
    chord = []
    for other in strong:
        if other is item:
            continue
        delta = other["start"] - start
        distance = abs(delta)
        if other["pitch"] == pitch and distance <= cfg.repeat_context_ms:
            if delta < 0 and (before is None or distance < before[0]):
                before = (distance, other)
            elif delta > 0 and (after is None or distance < after[0]):
                after = (distance, other)
        if distance <= 900.0 and other["pitch"] % 12 == pitch % 12:
            same_pc += 1
        if distance <= cfg.chord_context_ms:
            chord.append(other)
    repeat_hole = False
    symmetry = 99.0
    if before and after:
        left, right = before[0], after[0]
        smaller = max(1.0, min(left, right))
        symmetry = max(left, right) / smaller
        repeat_hole = left + right <= cfg.repeat_span_ms and symmetry <= cfg.repeat_symmetry_ratio
    return {
        "before": before, "after": after, "repeat_hole": repeat_hole,
        "symmetry": symmetry, "same_pc": same_pc, "chord": chord,
    }


def _rescue_score(item: dict, evidence: dict, cfg: ConsensusConfig) -> float | None:
    duration = max(0.0, item["end"] - item["start"])
    if not item["recovery"] or item["support"] != 1 or item["names"] != {"sensitive"}:
        return None
    if (
        item["tonal"] < cfg.rescue_tonal_floor
        or item["spectral"] < cfg.rescue_spectral_floor
        or item["velocity"] < cfg.rescue_velocity_floor
        or duration < cfg.rescue_duration_ms
    ):
        return None
    if evidence["repeat_hole"]:
        before = evidence["before"][1]
        after = evidence["after"][1]
        neighbor_floor = min(before["velocity"], after["velocity"])
        if item["velocity"] + 20 < neighbor_floor:
            return None
        return (
            2.2 * item["spectral"] + 1.2 * item["tonal"]
            + max(0.0, 1.4 - 0.45 * evidence["symmetry"])
            + min(0.8, duration / 300.0)
        )
    # Chord completion is allowed only with unusually strong exact-pitch evidence
    # and recurring pitch-class support. This is intentionally harder than a repeat-hole rescue.
    if len(evidence["chord"]) >= 2 and evidence["same_pc"] >= 2:
        if item["spectral"] >= 0.78 and item["tonal"] >= 0.84 and item["velocity"] >= 38 and duration >= 85.0:
            chord_pitches = [other["pitch"] for other in evidence["chord"]]
            if min(chord_pitches) - 12 <= item["pitch"] <= max(chord_pitches) + 12:
                return 2.0 * item["spectral"] + item["tonal"] + min(1.0, len(chord_pitches) * 0.2)
    return None


def _should_prune(item: dict, evidence: dict, cfg: ConsensusConfig, percussive_ratio: float | None) -> bool:
    duration = max(0.0, item["end"] - item["start"])
    if item["support"] != 2 or item["names"] != {"sensitive", "primary"}:
        return False
    if evidence["repeat_hole"] or len(evidence["chord"]) >= 2:
        return False
    extra = 0.0 if percussive_ratio is None else max(0.0, percussive_ratio - 0.30) * 0.18
    spectral_ceiling = min(0.16, cfg.prune_spectral_ceiling + extra)
    weak_exact_pitch = item["spectral"] <= spectral_ceiling and item["tonal"] <= cfg.prune_tonal_ceiling + 0.08
    octave_alias = item["spectral"] <= 0.045 and item["tonal"] >= 0.45
    return (
        (weak_exact_pitch and item["velocity"] <= 48 and duration <= 145.0 and evidence["same_pc"] <= 1)
        or (octave_alias and item["velocity"] <= 44 and duration <= 120.0)
    )


def _onset_groups(rows: list[Row], tolerance_ms: float) -> list[list[Row]]:
    ordered = sorted(rows, key=lambda row: (row[2][0], row[0], -row[2][3]))
    groups: list[list[Row]] = []
    current: list[Row] = []
    anchor = 0.0
    for row in ordered:
        start = row[2][0]
        if not current or start - anchor <= tolerance_ms:
            if not current:
                anchor = start
            current.append(row)
        else:
            groups.append(current)
            current = [row]
            anchor = start
    if current:
        groups.append(current)
    return groups


def _best_per_pass(group: list[Row]) -> dict[str, Row]:
    chosen: dict[str, Row] = {}
    for row in group:
        prior = chosen.get(row[1])
        note = row[2]
        if prior is None or (note[3], note[1] - note[0]) > (prior[2][3], prior[2][1] - prior[2][0]):
            chosen[row[1]] = row
    return chosen
