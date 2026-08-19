from __future__ import annotations

import struct
from collections import defaultdict

from .piano_layout import MIDI_TO_TOKEN, fold_midi_note

TickNote = tuple[int, int, int, int]
Note = tuple[float, float, int, int]


def _vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise ValueError("Truncated MIDI variable-length value.")
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos
    raise ValueError("Invalid MIDI variable-length value.")


def _read_tracks(data: bytes) -> tuple[int, list[TickNote], list[tuple[int, int]]]:
    """Read note intervals, velocity, tempo, and sustain-pedal extension.

    The parser intentionally stays dependency-free so external AMT engines can
    return Standard MIDI Files without adding their Python packages to the main
    Piano Auto Player environment.
    """
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("That download is not a Standard MIDI File.")
    header_len = struct.unpack(">I", data[4:8])[0]
    if header_len < 6 or len(data) < 8 + header_len:
        raise ValueError("Invalid MIDI header.")
    _fmt, track_count, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise ValueError("SMPTE-timed MIDI files are not supported yet.")
    ppqn = division or 480
    pos = 8 + header_len
    notes: list[TickNote] = []
    tempos: list[tuple[int, int]] = [(0, 500000)]

    for _ in range(track_count):
        if pos + 8 > len(data) or data[pos:pos + 4] != b"MTrk":
            raise ValueError("Invalid or truncated MIDI track.")
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        track = data[pos + 8:pos + 8 + length]
        pos += 8 + length
        tick = 0
        cursor = 0
        running = None
        active: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        sustained: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        pedal_down: dict[int, bool] = defaultdict(bool)

        def close_sustained(channel: int, end_tick: int) -> None:
            for key in [key for key in sustained if key[0] == channel]:
                for start, velocity in sustained.pop(key, []):
                    notes.append((start, max(start + 1, end_tick), key[1], velocity))

        while cursor < len(track):
            delta, cursor = _vlq(track, cursor)
            tick += delta
            if cursor >= len(track):
                break
            status = track[cursor]
            if status < 0x80:
                if running is None:
                    raise ValueError("Invalid MIDI running status.")
                status = running
            else:
                cursor += 1
                if status < 0xF0:
                    running = status

            if status == 0xFF:
                running = None
                if cursor >= len(track):
                    break
                meta_type = track[cursor]
                cursor += 1
                size, cursor = _vlq(track, cursor)
                payload = track[cursor:cursor + size]
                cursor += size
                if meta_type == 0x51 and len(payload) == 3:
                    tempos.append((tick, int.from_bytes(payload, "big")))
                continue
            if status in (0xF0, 0xF7):
                running = None
                size, cursor = _vlq(track, cursor)
                cursor += size
                continue

            event_type = status & 0xF0
            channel = status & 0x0F
            needed = 1 if event_type in (0xC0, 0xD0) else 2
            if cursor + needed > len(track):
                break
            first = track[cursor]
            second = track[cursor + 1] if needed == 2 else 0
            cursor += needed
            if channel == 9:  # percussion is not useful on the target piano
                continue

            if event_type == 0xB0 and first == 64:
                was_down = pedal_down[channel]
                pedal_down[channel] = second >= 64
                if was_down and not pedal_down[channel]:
                    close_sustained(channel, tick)
                continue

            key = (channel, first)
            if event_type == 0x90 and second > 0:
                active[key].append((tick, second))
            elif event_type == 0x80 or (event_type == 0x90 and second == 0):
                starts = active.get(key)
                if not starts:
                    continue
                start, velocity = starts.pop(0)
                if not starts:
                    active.pop(key, None)
                if pedal_down[channel]:
                    sustained[key].append((start, velocity))
                else:
                    notes.append((start, max(start + 1, tick), first, velocity))

        fallback_end = tick + max(1, ppqn // 4)
        for (channel, note), starts in active.items():
            for start, velocity in starts:
                notes.append((start, max(start + 1, fallback_end), note, velocity))
        for (channel, note), starts in sustained.items():
            for start, velocity in starts:
                notes.append((start, max(start + 1, fallback_end), note, velocity))
    return ppqn, notes, tempos


def _tick_converter(ppqn: int, tempos: list[tuple[int, int]]):
    by_tick: dict[int, int] = {}
    for tick, tempo in tempos:
        by_tick[max(0, int(tick))] = max(1, int(tempo))
    ordered = sorted(by_tick.items())
    if not ordered or ordered[0][0] != 0:
        ordered.insert(0, (0, 500000))
    segments: list[tuple[int, float, int]] = []
    elapsed_ms = 0.0
    last_tick, last_tempo = ordered[0]
    segments.append((last_tick, elapsed_ms, last_tempo))
    for tick, tempo in ordered[1:]:
        elapsed_ms += (tick - last_tick) * last_tempo / ppqn / 1000.0
        last_tick, last_tempo = tick, tempo
        segments.append((last_tick, elapsed_ms, last_tempo))

    def to_ms(tick: int) -> float:
        chosen = segments[0]
        for segment in segments[1:]:
            if segment[0] > tick:
                break
            chosen = segment
        start_tick, start_ms, tempo = chosen
        return start_ms + (tick - start_tick) * tempo / ppqn / 1000.0

    return to_ms


def midi_to_note_events(data: bytes) -> list[Note]:
    """Return exact MIDI note intervals in milliseconds, including velocity."""
    ppqn, notes, tempos = _read_tracks(data)
    if not notes:
        raise ValueError("The MIDI did not contain playable note events.")
    to_ms = _tick_converter(ppqn, tempos)
    rows = [
        (max(0.0, to_ms(start)), max(to_ms(start) + 1.0, to_ms(end)), note, velocity)
        for start, end, note, velocity in notes
    ]
    return sorted(rows, key=lambda row: (row[0], row[2], -row[3]))


def midi_to_performance(data: bytes) -> tuple[list[dict], dict[str, int]]:
    notes = midi_to_note_events(data)
    grouped: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    folded_count = 0
    min_source = 127
    max_source = 0
    for start_ms, end_ms, source_note, _velocity in notes:
        min_source = min(min_source, source_note)
        max_source = max(max_source, source_note)
        note, folded = fold_midi_note(source_note)
        folded_count += int(folded)
        token = MIDI_TO_TOKEN.get(note)
        if not token:
            continue
        at_ms = max(0, round(start_ms))
        duration = max(12, round(end_ms - start_ms))
        grouped[at_ms].append((token, duration, source_note))

    performance: list[dict] = []
    chord_count = 0
    note_count = 0
    for at_ms in sorted(grouped):
        items = grouped[at_ms]
        seen: set[str] = set()
        seen_midi: set[int] = set()
        ordered: list[str] = []
        durations: list[int] = []
        midi_notes: list[int] = []
        for token, duration, source_note in items:
            if source_note not in seen_midi:
                seen_midi.add(source_note)
                midi_notes.append(source_note)
            durations.append(duration)
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        if not ordered:
            continue
        note_count += len(midi_notes)
        chord_count += int(len(ordered) > 1)
        performance.append({
            "key": "".join(ordered),
            "at_ms": at_ms,
            "duration_ms": max(durations),
            "midi_notes": midi_notes,
        })
    if not performance:
        raise ValueError("The MIDI did not contain notes that can be mapped to this piano.")
    return performance, {
        "note_count": note_count,
        "chord_count": chord_count,
        "folded_notes": folded_count,
        "source_min_midi": min_source,
        "source_max_midi": max_source,
    }
