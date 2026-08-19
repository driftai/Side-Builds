from __future__ import annotations

import struct
from collections import defaultdict

from ..midi_performance import MIDI_TO_TOKEN, fold_midi_note


# Field numbers come from Online Sequencer's current public sequence.proto.
SETTINGS_FIELD = 1
NOTES_FIELD = 2
MARKERS_FIELD = 3
PERCUSSION_INSTRUMENTS = {2, 31, 36, 39, 40, 42, 53}


def _varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while pos < len(data) and shift < 70:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
    raise ValueError("Invalid protobuf varint.")


def _fields(data: bytes):
    pos = 0
    while pos < len(data):
        key, pos = _varint(data, pos)
        field = key >> 3
        wire = key & 7
        if field == 0:
            raise ValueError("Invalid protobuf field number.")
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire == 1:
            if pos + 8 > len(data):
                raise ValueError("Truncated protobuf fixed64 field.")
            value = data[pos:pos + 8]
            pos += 8
        elif wire == 2:
            size, pos = _varint(data, pos)
            if pos + size > len(data):
                raise ValueError("Truncated protobuf message field.")
            value = data[pos:pos + size]
            pos += size
        elif wire == 5:
            if pos + 4 > len(data):
                raise ValueError("Truncated protobuf fixed32 field.")
            value = data[pos:pos + 4]
            pos += 4
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire}.")
        yield field, wire, value


def _float32(value: bytes) -> float:
    return struct.unpack("<f", value)[0]


def _parse_settings(data: bytes) -> float:
    bpm = 110.0
    for field, wire, value in _fields(data):
        if field == 1 and wire == 0:  # SequenceSettings.bpm
            bpm = float(value)
    return max(10.0, bpm)


def _parse_note(data: bytes) -> tuple[int, float, float, int] | None:
    note_type = None
    time = 0.0
    length = 1.0
    instrument = 0
    for field, wire, value in _fields(data):
        if field == 1 and wire == 0:  # Note.type (C0=0 ... B8=107)
            note_type = int(value)
        elif field == 2 and wire == 5:
            time = _float32(value)
        elif field == 3 and wire == 5:
            length = _float32(value)
        elif field == 4 and wire == 0:
            instrument = int(value)
    if note_type is None:
        return None
    return note_type, max(0.0, time), max(0.01, length), instrument


def _parse_marker(data: bytes) -> tuple[float, int, int, float, bool]:
    time = 0.0
    setting = instrument = 0
    value = 0.0
    blend = False
    for field, wire, raw in _fields(data):
        if field == 1 and wire == 5:
            time = _float32(raw)
        elif field == 2 and wire == 0:
            setting = int(raw)
        elif field == 3 and wire == 0:
            instrument = int(raw)
        elif field == 4 and wire == 5:
            value = _float32(raw)
        elif field == 5 and wire == 0:
            blend = bool(raw)
    return max(0.0, time), setting, instrument, value, blend


def _tempo_at(position: float, base_bpm: float, markers: list[tuple[float, float, bool]]) -> float:
    prior_index = -1
    for index, marker in enumerate(markers):
        if marker[0] > position:
            break
        prior_index = index
    if prior_index < 0:
        return base_bpm
    start_time, start_bpm, blend = markers[prior_index]
    if blend and prior_index + 1 < len(markers):
        end_time, end_bpm, _ = markers[prior_index + 1]
        if end_time > start_time and position < end_time:
            ratio = (position - start_time) / (end_time - start_time)
            return max(10.0, start_bpm + (end_bpm - start_bpm) * ratio)
    return max(10.0, start_bpm)


def proto_to_performance(data: bytes) -> tuple[list[dict], dict[str, int | float]]:
    if not data:
        raise ValueError("Online Sequencer returned an empty sequence payload.")
    bpm = 110.0
    notes: list[tuple[int, float, float, int]] = []
    tempo_markers: list[tuple[float, float, bool]] = []
    for field, wire, value in _fields(data):
        if wire != 2:
            continue
        if field == SETTINGS_FIELD:
            bpm = _parse_settings(value)
        elif field == NOTES_FIELD:
            note = _parse_note(value)
            if note is not None:
                notes.append(note)
        elif field == MARKERS_FIELD:
            time, setting, instrument, marker_value, blend = _parse_marker(value)
            # SequencePlayer treats marker setting 0/instrument 0 as BPM automation.
            if setting == 0 and instrument == 0 and marker_value >= 10:
                tempo_markers.append((time, marker_value, blend))
    if not notes:
        raise ValueError("Online Sequencer returned no playable note data.")
    tempo_markers.sort(key=lambda row: row[0])

    # Match Online Sequencer's current player semantics: the BPM at each note
    # position scales the gap from the previous note position.
    positions = sorted({row[1] for row in notes})
    position_ms: dict[float, int] = {}
    elapsed = 0.0
    previous = 0.0
    for position in positions:
        current_bpm = _tempo_at(position, bpm, tempo_markers)
        elapsed += max(0.0, position - previous) * (15000.0 / current_bpm)
        position_ms[position] = max(0, round(elapsed))
        previous = position

    grouped: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    folded = 0
    note_count = 0
    min_source = 127
    max_source = 0
    for source_note, position, length, instrument in notes:
        if instrument in PERCUSSION_INSTRUMENTS:
            continue
        min_source = min(min_source, source_note)
        max_source = max(max_source, source_note)
        midi_note, changed = fold_midi_note(source_note)
        folded += int(changed)
        token = MIDI_TO_TOKEN.get(midi_note)
        if not token:
            continue
        local_bpm = _tempo_at(position, bpm, tempo_markers)
        duration_ms = max(12, round(length * (15000.0 / local_bpm)))
        grouped[position_ms[position]].append((token, duration_ms, source_note))

    performance: list[dict] = []
    chord_count = 0
    for at_ms in sorted(grouped):
        keys: list[str] = []
        durations: list[int] = []
        midi_notes: list[int] = []
        seen: set[str] = set()
        seen_midi: set[int] = set()
        for token, duration, source_note in grouped[at_ms]:
            if source_note not in seen_midi:
                seen_midi.add(source_note); midi_notes.append(source_note)
            durations.append(duration)
            if token in seen: continue
            seen.add(token); keys.append(token)
        if not keys:
            continue
        note_count += len(midi_notes)
        chord_count += int(len(keys) > 1)
        performance.append({"key": "".join(keys), "at_ms": at_ms, "duration_ms": max(durations), "midi_notes": midi_notes})
    if not performance:
        raise ValueError("Online Sequencer returned no notes mappable to this piano.")
    return performance, {
        "note_count": note_count,
        "chord_count": chord_count,
        "folded_notes": folded,
        "source_min_midi": min_source,
        "source_max_midi": max_source,
        "source_bpm": bpm,
    }
