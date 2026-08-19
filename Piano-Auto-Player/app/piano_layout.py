from __future__ import annotations

from dataclasses import dataclass

WHITE = "1234567890qwertyuiopasdfghjklzxcvbnm"
BLACK = "!@$%^*(QWETYIOPSDGHJLZCVB"
BLACK_AFTER = {0, 1, 3, 4, 5}
STANDARD_MIN_MIDI = 36  # C2
STANDARD_MAX_MIDI = 96  # C7
FULL_MIN_MIDI = 21      # A0
FULL_MAX_MIDI = 108     # C8
CTRL_RANGE_KEYS = "1234567890qwertyuiopasdfghj"  # Piano Gardens' 27 out-of-range keys.


@dataclass(frozen=True)
class PianoStroke:
    char: str
    ctrl: bool = False
    midi: int = 0


def _build_standard_map() -> dict[int, str]:
    result: dict[int, str] = {}
    white_index = black_index = 0
    naturals = [0, 2, 4, 5, 7, 9, 11]
    for octave in range(5):
        base = STANDARD_MIN_MIDI + octave * 12
        for index, semitone in enumerate(naturals):
            result[base + semitone] = WHITE[white_index]
            white_index += 1
            if index in BLACK_AFTER:
                result[base + semitone + 1] = BLACK[black_index]
                black_index += 1
    result[STANDARD_MAX_MIDI] = WHITE[white_index]
    return result


MIDI_TO_TOKEN = _build_standard_map()
TOKEN_TO_MIDI = {token: midi for midi, token in MIDI_TO_TOKEN.items()}


def normalize_layout(value: str | None) -> str:
    text = str(value or "61").strip().lower().replace("-", "").replace("_", "")
    return "88" if text in {"88", "88key", "full88", "full"} else "61"


def fold_midi_note(note: int) -> tuple[int, bool]:
    original = int(note)
    folded = original
    while folded < STANDARD_MIN_MIDI:
        folded += 12
    while folded > STANDARD_MAX_MIDI:
        folded -= 12
    return folded, folded != original


def fold_full_midi_note(note: int) -> tuple[int, bool]:
    original = int(note)
    folded = original
    while folded < FULL_MIN_MIDI:
        folded += 12
    while folded > FULL_MAX_MIDI:
        folded -= 12
    return folded, folded != original


def stroke_for_midi(note: int, layout: str = "61") -> PianoStroke | None:
    mode = normalize_layout(layout)
    if mode == "61":
        midi, _changed = fold_midi_note(note)
        token = MIDI_TO_TOKEN.get(midi)
        return PianoStroke(token, False, midi) if token else None

    midi, _changed = fold_full_midi_note(note)
    if STANDARD_MIN_MIDI <= midi <= STANDARD_MAX_MIDI:
        token = MIDI_TO_TOKEN.get(midi)
        return PianoStroke(token, False, midi) if token else None
    if FULL_MIN_MIDI <= midi < STANDARD_MIN_MIDI:
        return PianoStroke(CTRL_RANGE_KEYS[midi - FULL_MIN_MIDI], True, midi)
    if STANDARD_MAX_MIDI < midi <= FULL_MAX_MIDI:
        return PianoStroke(CTRL_RANGE_KEYS[15 + midi - STANDARD_MAX_MIDI - 1], True, midi)
    return None


def strokes_for_midi(notes: list[int] | tuple[int, ...], layout: str = "61") -> list[PianoStroke]:
    result: list[PianoStroke] = []
    seen: set[tuple[str, bool]] = set()
    for note in notes:
        stroke = stroke_for_midi(int(note), layout)
        if not stroke:
            continue
        identity = (stroke.char, stroke.ctrl)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(stroke)
    return result


def target_midi_notes(notes: list[int] | tuple[int, ...], layout: str = "61") -> list[int]:
    return [stroke.midi for stroke in strokes_for_midi(notes, layout)]


def display_strokes(strokes: list[PianoStroke]) -> str:
    return "+".join((f"Ctrl+{stroke.char}" if stroke.ctrl else stroke.char) for stroke in strokes)
