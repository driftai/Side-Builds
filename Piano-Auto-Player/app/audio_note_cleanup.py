from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .audio_ghost_filter import GhostGuardConfig, conservative_ghost_config, filter_ghost_notes
from .audio_sustain_repair import SustainRepairConfig, repair_sustain_fragments_detailed
from .audio_stability_reducer import consensus_stability_config, reduce_unstable_notes
from .piano_layout import FULL_MAX_MIDI, FULL_MIN_MIDI, MIDI_TO_TOKEN, STANDARD_MAX_MIDI, STANDARD_MIN_MIDI, fold_midi_note, normalize_layout


@dataclass(frozen=True)
class TranscriptionPreset:
    key: str
    label: str
    onset_threshold: float
    frame_threshold: float
    minimum_note_length_ms: float
    use_melodia: bool
    min_velocity: int
    chord_window_ms: float
    max_chord_notes: int
    sustain_ratio: float
    retrigger_window_ms: float


_PRESETS = {
    "hifi_piano": TranscriptionPreset(
        "hifi_piano", "Hi-Fi piano specialist", 0.0, 0.0, 25.0, False, 1, 14.0, 10, 0.0, 0.0,
    ),
    "rhythm_accurate": TranscriptionPreset(
        "rhythm_accurate", "Rhythm accurate · precision consensus", 0.50, 0.30, 55.0, False, 28, 12.0, 5, 0.46, 18.0,
    ),
    "rhythm_clean": TranscriptionPreset(
        "rhythm_clean", "Rhythm clean · lower sensitivity", 0.50, 0.30, 55.0, False, 28, 12.0, 5, 0.46, 18.0,
    ),
    "rhythm_clean_sensitive": TranscriptionPreset(
        "rhythm_clean_sensitive", "Rhythm clean · v0.5.0 sensitivity", 0.44, 0.28, 55.0, False, 22, 14.0, 6, 0.50, 18.0,
    ),
    "rhythm": TranscriptionPreset(
        "rhythm", "Rhythm preserve", 0.44, 0.28, 55.0, True, 22, 14.0, 10, 0.50, 18.0,
    ),
    "piano_clean": TranscriptionPreset(
        "piano_clean", "Piano clean", 0.56, 0.25, 80.0, False, 36, 24.0, 7, 0.68, 30.0,
    ),
    "balanced": TranscriptionPreset(
        "balanced", "Balanced", 0.50, 0.28, 75.0, True, 26, 18.0, 9, 0.58, 24.0,
    ),
    "raw": TranscriptionPreset(
        "raw", "Raw Basic Pitch", 0.50, 0.30, 127.7, True, 1, 2.0, 16, 0.0, 0.0,
    ),
}


def preset_for(value: str | None) -> TranscriptionPreset:
    return _PRESETS.get(str(value or "").strip().lower(), _PRESETS["rhythm_clean"])


def preset_keys() -> set[str]:
    return set(_PRESETS)


def basic_pitch_args(preset: TranscriptionPreset, layout: str = "88") -> list[str]:
    args = [
        "--save-note-events",
        "--onset-threshold", f"{preset.onset_threshold:.3f}",
        "--frame-threshold", f"{preset.frame_threshold:.3f}",
        "--minimum-note-length", f"{preset.minimum_note_length_ms:.1f}",
        "--minimum-frequency", "65.406" if normalize_layout(layout) == "61" else "27.5",
        "--maximum-frequency", "2093.005" if normalize_layout(layout) == "61" else "4186.01",
    ]
    if not preset.use_melodia:
        args.append("--no-melodia")
    return args


def performance_from_note_events(path: Path, preset: TranscriptionPreset, layout: str = "88") -> tuple[list[dict], dict[str, object]]:
    return performance_from_notes(read_note_events(path), preset, layout)


def performance_from_notes(
    notes: list[tuple[float, float, int, int]],
    preset: TranscriptionPreset,
    layout: str = "88",
    extra_stats: dict[str, object] | None = None,
) -> tuple[list[dict], dict[str, object]]:
    if not notes:
        raise ValueError("Audio transcription did not contain playable notes.")
    raw_count = len(notes)
    layout = normalize_layout(layout)
    low_midi, high_midi = (STANDARD_MIN_MIDI, STANDARD_MAX_MIDI) if layout == "61" else (FULL_MIN_MIDI, FULL_MAX_MIDI)
    layout_drops = sum(1 for note in notes if not low_midi <= note[2] <= high_midi)
    notes = [note for note in notes if low_midi <= note[2] <= high_midi and note[3] >= preset.min_velocity]
    ghost_drops = 0
    if preset.key in {"rhythm_clean", "rhythm_accurate"}:
        notes, ghost_drops = filter_ghost_notes(notes, conservative_ghost_config())
    elif preset.key == "rhythm_clean_sensitive":
        notes, ghost_drops = filter_ghost_notes(notes, GhostGuardConfig())
    if not notes:
        raise ValueError("Transcription cleanup removed every detected note; try Balanced or Raw Basic Pitch.")
    notes = _dedupe_retriggers(notes, preset.retrigger_window_ms)
    sustain_joins = 0
    if preset.key in {"rhythm_accurate", "rhythm_clean", "rhythm_clean_sensitive", "piano_clean"}:
        accurate_clean = preset.key in {"rhythm_accurate", "rhythm_clean"}
        repair_cfg = SustainRepairConfig(
            join_gap_ms=70.0 if accurate_clean else 42.0,
            min_left_duration_ms=170.0 if accurate_clean else 190.0,
            min_right_duration_ms=70.0,
            reattack_velocity_jump=12,
        )
        notes, sustain_joins, dense_reattacks = repair_sustain_fragments_detailed(notes, repair_cfg)
    else:
        dense_reattacks = 0
    stability_drops = 0
    stability_active = False
    if preset.key in {"rhythm_clean", "rhythm_accurate"}:
        stability_cfg = consensus_stability_config() if preset.key == "rhythm_accurate" else None
        notes, stability_drops, stability_active = reduce_unstable_notes(
            notes, raw_count, sustain_joins, stability_cfg
        )
    clusters = _cluster_notes(notes, preset.chord_window_ms)
    performance = []
    dropped_polyphony = 0
    folded_count = 0
    source_min = 127
    source_max = 0

    for cluster in clusters:
        kept, dropped = _limit_polyphony(cluster, preset.max_chord_notes)
        dropped_polyphony += dropped
        if not kept:
            continue
        source_notes = sorted({note[2] for note in kept})
        source_min = min(source_min, min(source_notes))
        source_max = max(source_max, max(source_notes))
        tokens = []
        seen_tokens = set()
        for source_note in source_notes:
            mapped, folded = (source_note, False) if layout == "61" else fold_midi_note(source_note)
            folded_count += int(folded)
            token = MIDI_TO_TOKEN.get(mapped)
            if token and token not in seen_tokens:
                seen_tokens.add(token)
                tokens.append(token)
        if not tokens:
            continue
        starts = [note[0] for note in kept]
        anchor = min(starts)
        spans = [{
            "midi": note[2],
            "offset_ms": round(max(0.0, note[0] - anchor), 3),
            "duration_ms": round(max(1.0, note[1] - note[0]), 3),
            "velocity": note[3],
        } for note in sorted(kept, key=lambda row: (row[0], row[2]))]
        span_end = max(span["offset_ms"] + span["duration_ms"] for span in spans)
        performance.append({
            "key": "".join(tokens),
            "at_ms": round(anchor, 3),
            "duration_ms": round(max(45.0, span_end), 3),
            "midi_notes": source_notes,
            "note_spans": spans,
        })

    if not performance:
        raise ValueError("Transcription cleanup did not leave any playable piano events.")
    _bridge_short_sustains(performance, preset.sustain_ratio)
    note_count = sum(len(row["midi_notes"]) for row in performance)
    chord_count = sum(1 for row in performance if len(row["midi_notes"]) > 1)
    return performance, {
        "note_count": note_count,
        "chord_count": chord_count,
        "folded_notes": folded_count,
        "source_min_midi": source_min,
        "source_max_midi": source_max,
        "raw_transcribed_notes": raw_count,
        "cleanup_dropped_notes": raw_count - note_count,
        "cleanup_polyphony_drops": dropped_polyphony,
        "cleanup_ghost_drops": ghost_drops,
        "cleanup_layout_drops": layout_drops,
        "cleanup_sustain_joins": sustain_joins,
        "cleanup_dense_reattacks_preserved": dense_reattacks,
        "cleanup_stability_drops": stability_drops,
        "cleanup_stability_active": int(stability_active),
        "transcription_layout": layout,
        "transcription_quality": preset.key,
        "transcription_quality_label": preset.label,
        **(extra_stats or {}),
    }


def read_note_events(path: Path) -> list[tuple[float, float, int, int]]:
    rows = []
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                start_ms = max(0.0, float(row.get("start_time_s") or 0.0) * 1000.0)
                end_ms = max(start_ms + 1.0, float(row.get("end_time_s") or 0.0) * 1000.0)
                pitch = int(float(row.get("pitch_midi") or -1))
                velocity = max(0, min(127, int(float(row.get("velocity") or 0))))
            except (TypeError, ValueError):
                continue
            rows.append((start_ms, end_ms, pitch, velocity))
    return sorted(rows, key=lambda note: (note[0], note[2], -note[3]))


def _dedupe_retriggers(
    notes: list[tuple[float, float, int, int]], window_ms: float = 38.0
) -> list[tuple[float, float, int, int]]:
    kept = []
    last_by_pitch: dict[int, tuple[float, int]] = {}
    for note in notes:
        start, _end, pitch, velocity = note
        prior = last_by_pitch.get(pitch)
        if prior and window_ms > 0 and start - prior[0] < window_ms and velocity <= prior[1] + 5:
            continue
        kept.append(note)
        last_by_pitch[pitch] = (start, velocity)
    return kept


def _cluster_notes(notes: list[tuple[float, float, int, int]], window_ms: float) -> list[list[tuple[float, float, int, int]]]:
    if not notes:
        return []
    clusters = []
    current = [notes[0]]
    anchor = notes[0][0]
    for note in notes[1:]:
        if note[0] - anchor <= max(0.0, window_ms):
            current.append(note)
        else:
            clusters.append(current)
            current = [note]
            anchor = note[0]
    clusters.append(current)
    return clusters


def _limit_polyphony(cluster: list[tuple[float, float, int, int]], maximum: int) -> tuple[list[tuple[float, float, int, int]], int]:
    maximum = max(1, int(maximum))
    by_pitch: dict[int, tuple[float, float, int, int]] = {}
    for note in cluster:
        existing = by_pitch.get(note[2])
        if existing is None or (note[3], note[1] - note[0]) > (existing[3], existing[1] - existing[0]):
            by_pitch[note[2]] = note
    unique = list(by_pitch.values())
    if len(unique) <= maximum:
        return sorted(unique, key=lambda note: note[2]), 0

    # Never force the lowest/highest pitch to survive. In mixed audio those
    # extremes are often percussion/harmonic leakage; preserving them
    # unconditionally was a direct route for obvious phantom keys. Keep the
    # strongest, longest-supported note candidates instead.
    ranked = sorted(
        unique,
        key=lambda note: (note[3], note[1] - note[0]),
        reverse=True,
    )
    chosen = ranked[:maximum]
    return sorted(chosen, key=lambda note: note[2]), len(unique) - len(chosen)


def _bridge_short_sustains(performance: list[dict], ratio: float) -> None:
    if ratio <= 0:
        return
    for index, event in enumerate(performance[:-1]):
        gap = max(1.0, float(performance[index + 1]["at_ms"]) - float(event["at_ms"]))
        desired = min(520.0, gap * max(0.25, min(float(ratio), 0.90)))
        event["duration_ms"] = round(max(float(event["duration_ms"]), desired), 3)
