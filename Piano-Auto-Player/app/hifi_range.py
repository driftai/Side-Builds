from __future__ import annotations

from dataclasses import dataclass

from .piano_layout import STANDARD_MAX_MIDI, STANDARD_MIN_MIDI, fold_midi_note, normalize_layout

Note = tuple[float, float, int, int]
_NATURAL_PCS = {0, 2, 4, 5, 7, 9, 11}
_COLLISION_ONSET_MS = 18.0
_ALIAS_TRANSITION_MS = 24.0
_MIN_TARGET_HOLD_MS = 12.0


@dataclass(frozen=True)
class _ProjectedNote:
    start: float
    end: float
    source_midi: int
    mapped_midi: int
    velocity: int
    folded: bool

    def note(self) -> Note:
        return (self.start, self.end, self.mapped_midi, self.velocity)


def compact_specialist_for_layout(notes: list[Note], layout: str) -> tuple[list[Note], dict[str, int]]:
    """Project a finished 88-key transcription onto a 61-key target safely.

    Folding an edge octave onto C2-C7 can make *different* source piano keys
    become the same target key. The old collision merge unioned their note-off
    times, which could make a target key hang too long, while nearby folded
    aliases could also force an audible release/repress jump. Target adaptation
    now chooses one representative instead of inventing sustain, gives genuine
    in-range notes priority, and suppresses only alias transitions that cannot
    be represented faithfully on a 61-key keyboard.
    """
    ordered = sorted(notes, key=lambda row: (row[0], row[2], -row[3], -(row[1] - row[0])))
    if normalize_layout(layout) != "61":
        return ordered, _empty_stats()

    projected: list[_ProjectedNote] = []
    compacted = 0
    for start, end, pitch, velocity in ordered:
        mapped = int(pitch)
        folded = not STANDARD_MIN_MIDI <= mapped <= STANDARD_MAX_MIDI
        if folded:
            mapped, _ = fold_midi_note(mapped)
            compacted += 1
        projected.append(_ProjectedNote(
            float(start), float(end), int(pitch), mapped, int(velocity), folded
        ))

    collapsed, collision_stats = _collapse_onset_aliases(projected)
    normalized, transition_stats = _normalize_alias_transitions(collapsed)
    stats = {
        "hifi_range_compacted_notes": compacted,
        **collision_stats,
        **transition_stats,
    }
    return sorted((row.note() for row in normalized), key=lambda row: (row[0], row[2], -row[3])), stats


def _collapse_onset_aliases(rows: list[_ProjectedNote]) -> tuple[list[_ProjectedNote], dict[str, int]]:
    by_pitch: dict[int, list[_ProjectedNote]] = {}
    for row in rows:
        by_pitch.setdefault(row.mapped_midi, []).append(row)

    kept: list[_ProjectedNote] = []
    merges = white = black = tail_ignored = 0
    for pitch, pitch_rows in by_pitch.items():
        pitch_rows.sort(key=lambda row: (row.start, row.folded, -row.velocity, row.source_midi))
        group: list[_ProjectedNote] = []
        anchor = 0.0
        for row in pitch_rows:
            if not group or row.start - anchor <= _COLLISION_ONSET_MS:
                if not group:
                    anchor = row.start
                group.append(row)
                continue
            winner, dropped = _choose_onset_representative(group)
            kept.append(winner)
            if dropped:
                merges += len(dropped)
                white += len(dropped) if pitch % 12 in _NATURAL_PCS else 0
                black += len(dropped) if pitch % 12 not in _NATURAL_PCS else 0
                tail_ignored += sum(1 for item in dropped if item.end > winner.end + 6.0)
            group = [row]
            anchor = row.start
        if group:
            winner, dropped = _choose_onset_representative(group)
            kept.append(winner)
            if dropped:
                merges += len(dropped)
                white += len(dropped) if pitch % 12 in _NATURAL_PCS else 0
                black += len(dropped) if pitch % 12 not in _NATURAL_PCS else 0
                tail_ignored += sum(1 for item in dropped if item.end > winner.end + 6.0)

    return kept, {
        "hifi_range_collision_merges": merges,
        "hifi_range_white_collision_merges": white,
        "hifi_range_black_collision_merges": black,
        "hifi_range_alias_tails_ignored": tail_ignored,
    }


def _choose_onset_representative(group: list[_ProjectedNote]) -> tuple[_ProjectedNote, list[_ProjectedNote]]:
    if len(group) == 1:
        return group[0], []
    # A note that really belongs to the 61-key instrument outranks an octave
    # alias. Within the same class, favor the stronger attack and then duration.
    winner = max(
        group,
        key=lambda row: (not row.folded, row.velocity, row.end - row.start, -abs(row.source_midi - row.mapped_midi)),
    )
    return winner, [row for row in group if row is not winner]


def _normalize_alias_transitions(rows: list[_ProjectedNote]) -> tuple[list[_ProjectedNote], dict[str, int]]:
    by_pitch: dict[int, list[_ProjectedNote]] = {}
    for row in rows:
        by_pitch.setdefault(row.mapped_midi, []).append(row)

    result: list[_ProjectedNote] = []
    suppressed = trims = white = black = 0
    for pitch, pitch_rows in by_pitch.items():
        pitch_rows.sort(key=lambda row: (row.start, row.folded, -row.velocity))
        normalized: list[_ProjectedNote] = []
        for row in pitch_rows:
            if not normalized:
                normalized.append(row)
                continue
            left = normalized[-1]
            alias_conflict = (
                left.source_midi != row.source_midi
                and (left.folded or row.folded)
                and row.start - left.end <= _ALIAS_TRANSITION_MS
            )
            if not alias_conflict:
                normalized.append(row)
                continue

            is_white = pitch % 12 in _NATURAL_PCS
            if left.folded and not row.folded:
                # Hand control back to the real in-range note without allowing
                # the folded alias to remain held underneath it.
                new_end = max(left.start + _MIN_TARGET_HOLD_MS, row.start - 3.0)
                if new_end < left.end - 0.5:
                    normalized[-1] = _ProjectedNote(
                        left.start, new_end, left.source_midi, left.mapped_midi,
                        left.velocity, left.folded,
                    )
                    trims += 1
                normalized.append(row)
                white += int(is_white)
                black += int(not is_white)
                continue

            if row.folded and not left.folded:
                # The target key is already occupied by its native note. A
                # folded octave cannot be represented independently here, so do
                # not manufacture a second press or extend the native release.
                suppressed += 1
                white += int(is_white)
                black += int(not is_white)
                continue

            # Two folded source octaves collided on one target key. Preserve the
            # stronger existing gesture unless the new attack is clearly stronger.
            if row.velocity <= left.velocity + 8:
                suppressed += 1
                white += int(is_white)
                black += int(not is_white)
                continue
            new_end = min(left.end, max(left.start + _MIN_TARGET_HOLD_MS, row.start - 3.0))
            normalized[-1] = _ProjectedNote(
                left.start, new_end, left.source_midi, left.mapped_midi,
                left.velocity, left.folded,
            )
            trims += 1
            normalized.append(row)
            white += int(is_white)
            black += int(not is_white)
        result.extend(normalized)

    return result, {
        "hifi_range_alias_retriggers_suppressed": suppressed,
        "hifi_range_alias_holds_trimmed": trims,
        "hifi_range_white_alias_conflicts": white,
        "hifi_range_black_alias_conflicts": black,
    }


def _empty_stats() -> dict[str, int]:
    return {
        "hifi_range_compacted_notes": 0,
        "hifi_range_collision_merges": 0,
        "hifi_range_white_collision_merges": 0,
        "hifi_range_black_collision_merges": 0,
        "hifi_range_alias_tails_ignored": 0,
        "hifi_range_alias_retriggers_suppressed": 0,
        "hifi_range_alias_holds_trimmed": 0,
        "hifi_range_white_alias_conflicts": 0,
        "hifi_range_black_alias_conflicts": 0,
    }
