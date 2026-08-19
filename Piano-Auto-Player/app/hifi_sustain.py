from __future__ import annotations

from dataclasses import dataclass

from .hifi_onset import AcousticOnset

Note = tuple[float, float, int, int]


@dataclass(frozen=True)
class SustainConsensusConfig:
    """Cross-model + waveform guard against false same-pitch re-articulation."""

    onset_tolerance_ms: float = 38.0
    max_join_gap_ms: float = 65.0
    max_join_overlap_ms: float = 140.0
    continuity_before_ms: float = 45.0
    continuity_after_ms: float = 28.0
    chord_context_ms: float = 36.0
    chord_context_min_confirmed_tones: int = 2
    continuity_origin_tolerance_ms: float = 72.0
    strong_reattack_velocity_jump: int = 18
    acoustic_window_ms: float = 28.0
    acoustic_min_strength: float = 0.30
    acoustic_strong_strength: float = 0.55
    micro_gap_ms: float = 24.0
    micro_overlap_ms: float = 35.0
    micro_velocity_jump: int = 10


def stitch_consensus_sustain(
    fused_notes: list[Note], specialist_notes: list[Note], basic_notes: list[Note],
    config: SustainConsensusConfig | None = None,
    acoustic_onsets: list[AcousticOnset] | None = None,
) -> tuple[list[Note], dict[str, int]]:
    """Join false same-key jumps while keeping acoustically real reattacks.

    v0.6.8 showed that cross-model continuity is the best cure for the audible
    release/repress "jump" caused by AMT sustain fragmentation. Later builds
    became too conservative because pedal/chord heuristics could veto that join.
    This version restores the continuity-first rule, but gives a source-waveform
    attack peak the deciding vote when a repeated strike is physically audible.
    """
    cfg = config or SustainConsensusConfig()
    ordered = sorted(fused_notes, key=lambda row: (row[2], row[0], row[1], -row[3]))
    by_pitch: dict[int, list[Note]] = {}
    for note in ordered:
        by_pitch.setdefault(note[2], []).append(note)

    result: list[Note] = []
    stitches = protected = acoustic_protected = continuity_stitches = 0
    context_protected = pedal_protected = weak_context_stitches = micro_stitches = 0
    for pitch, rows in by_pitch.items():
        merged: list[Note] = []
        for note in rows:
            if not merged:
                merged.append(note)
                continue
            left = merged[-1]
            decision = _stitch_decision(
                left, note, pitch, specialist_notes, basic_notes,
                acoustic_onsets or [], cfg,
            )
            if decision.startswith("stitch"):
                merged[-1] = (
                    left[0], max(left[1], note[1]), pitch,
                    max(left[3], note[3]),
                )
                stitches += 1
                continuity_stitches += int(decision in {"stitch", "stitch_context"})
                weak_context_stitches += int(decision == "stitch_context")
                micro_stitches += int(decision == "stitch_micro")
            else:
                if decision.startswith("protect"):
                    protected += 1
                acoustic_protected += int(decision == "protect_acoustic")
                context_protected += int(decision == "protect_context")
                pedal_protected += int(decision == "protect_pedal")
                merged.append(note)
        result.extend(merged)

    return sorted(result, key=lambda row: (row[0], row[2], -row[3])), {
        "hifi_sustain_stitches": stitches,
        "hifi_sustain_reattacks_protected": protected,
        "hifi_sustain_context_reattacks_protected": context_protected,
        "hifi_sustain_pedal_reattacks_protected": pedal_protected,
        "hifi_sustain_weak_context_stitches": weak_context_stitches,
        "hifi_sustain_acoustic_reattacks_protected": acoustic_protected,
        "hifi_sustain_continuity_stitches": continuity_stitches,
        "hifi_sustain_microgap_stitches": micro_stitches,
    }


def _stitch_decision(
    left: Note, right: Note, pitch: int, specialist: list[Note], basic: list[Note],
    acoustic_onsets: list[AcousticOnset], cfg: SustainConsensusConfig,
) -> str:
    if right[0] <= left[0]:
        return "keep"
    gap = right[0] - left[1]
    if gap > cfg.max_join_gap_ms or gap < -cfg.max_join_overlap_ms:
        return "keep"

    spec_onset = _has_onset(specialist, pitch, right[0], cfg.onset_tolerance_ms)
    basic_onset = _has_onset(basic, pitch, right[0], cfg.onset_tolerance_ms)
    if spec_onset and basic_onset:
        return "protect"
    if right[3] - left[3] >= cfg.strong_reattack_velocity_jump:
        return "protect"

    acoustic_strength = _acoustic_strength(
        acoustic_onsets, right[0], cfg.acoustic_window_ms
    )
    spec_cont = _continuous_note(specialist, pitch, right[0], cfg)
    basic_cont = _continuous_note(basic, pitch, right[0], cfg)
    context_tones = _confirmed_chord_attack_count(
        specialist, basic, pitch, right[0], cfg.chord_context_ms
    )

    # Without waveform evidence, retain the approved v0.6.9/v0.6.10 pedal and
    # chord guards. This keeps non-Hi-Fi/unit callers deterministic. When the
    # real source waveform is available, it becomes the tie-breaker instead of
    # those broad heuristics.
    has_waveform = bool(acoustic_onsets)
    strong_context = context_tones >= cfg.chord_context_min_confirmed_tones

    if spec_onset and not basic_onset and basic_cont is not None:
        if has_waveform:
            if acoustic_strength >= cfg.acoustic_min_strength:
                return "protect_acoustic"
            return "stitch_context" if context_tones else "stitch"
        if not _same_hold_origin(left, basic_cont, cfg.continuity_origin_tolerance_ms):
            return "protect_pedal"
        if strong_context:
            return "protect_context"
        return "stitch_context" if context_tones else "stitch"

    if basic_onset and not spec_onset and spec_cont is not None:
        if has_waveform:
            if acoustic_strength >= cfg.acoustic_min_strength:
                return "protect_acoustic"
            return "stitch_context" if context_tones else "stitch"
        if not _same_hold_origin(left, spec_cont, cfg.continuity_origin_tolerance_ms):
            return "protect_pedal"
        if strong_context:
            return "protect_context"
        return "stitch_context" if context_tones else "stitch"

    if spec_cont is not None and basic_cont is not None:
        if has_waveform:
            if acoustic_strength >= cfg.acoustic_strong_strength and context_tones:
                return "protect_acoustic"
            return "stitch_context" if context_tones else "stitch"
        same_origin = (
            _same_hold_origin(left, spec_cont, cfg.continuity_origin_tolerance_ms)
            or _same_hold_origin(left, basic_cont, cfg.continuity_origin_tolerance_ms)
        )
        if same_origin:
            if strong_context:
                return "protect_context"
            return "stitch_context" if context_tones else "stitch"

    # Last-resort deglitch for a tiny same-key release/repress boundary. It is
    # deliberately narrow and disabled by any credible acoustic reattack.
    if (
        -cfg.micro_overlap_ms <= gap <= cfg.micro_gap_ms
        and acoustic_strength < cfg.acoustic_min_strength
        and not (spec_onset and basic_onset)
        and right[3] - left[3] < cfg.micro_velocity_jump
    ):
        return "stitch_micro"
    return "keep"


def _same_hold_origin(left: Note, continuous: Note, tolerance_ms: float) -> bool:
    return abs(continuous[0] - left[0]) <= tolerance_ms


def _acoustic_strength(onsets: list[AcousticOnset], at_ms: float, window_ms: float) -> float:
    nearby = [float(strength) for onset_ms, strength in onsets if abs(float(onset_ms) - at_ms) <= window_ms]
    return max(nearby, default=0.0)


def _confirmed_chord_attack_count(
    specialist: list[Note], basic: list[Note], pitch: int, at_ms: float, tolerance_ms: float,
) -> int:
    specialist_pitches = {
        note[2] for note in specialist
        if note[2] != pitch and abs(note[0] - at_ms) <= tolerance_ms
    }
    if not specialist_pitches:
        return 0
    basic_pitches = {
        note[2] for note in basic
        if note[2] != pitch and abs(note[0] - at_ms) <= tolerance_ms
    }
    return len(specialist_pitches & basic_pitches)


def _has_onset(notes: list[Note], pitch: int, at_ms: float, tolerance_ms: float) -> bool:
    return any(note[2] == pitch and abs(note[0] - at_ms) <= tolerance_ms for note in notes)


def _continuous_note(
    notes: list[Note], pitch: int, at_ms: float, cfg: SustainConsensusConfig,
) -> Note | None:
    candidates = [
        note for note in notes
        if note[2] == pitch
        and note[0] <= at_ms - cfg.continuity_before_ms
        and note[1] >= at_ms + cfg.continuity_after_ms
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row[1] - row[0], row[3]))
