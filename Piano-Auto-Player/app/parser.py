from dataclasses import dataclass
import string


@dataclass(frozen=True)
class SheetEvent:
    kind: str
    value: str
    units: float = 1.0
    hold_units: float = 0.0


# Virtual Piano's published notation is expressive: adjacency, spaces, bars,
# and paragraph breaks carry different timing weights.
QUICK_UNITS = 0.42
FAST_UNITS = 0.18
SPACE_UNITS = 0.58
BAR_UNITS = 1.35
PARAGRAPH_UNITS = 2.75
PLAYABLE_CHARS = set(string.ascii_letters + string.digits + "!@$%^*(")
GRID_PROFILES = {"grid", "vpsheet", "roblox_grid"}
LETTER_ADJACENT_UNITS = 0.45


def _safe_payload(value: str) -> str:
    return "".join(char for char in value if char in PLAYABLE_CHARS)


def _append_pause(events: list[SheetEvent], value: str, units: float) -> None:
    if units <= 0:
        return
    if events and events[-1].kind == "pause" and events[-1].value == value:
        previous = events.pop()
        events.append(SheetEvent("pause", value, previous.units + units))
    else:
        events.append(SheetEvent("pause", value, units))


def _consume_whitespace(text: str, start: int) -> tuple[int, float, str]:
    i, spaces, newlines = start, 0, 0
    while i < len(text) and text[i] in " \t\r\n":
        ch = text[i]
        if ch == "\n": newlines += 1
        elif ch in " \t": spaces += 1
        i += 1
    if newlines >= 2:
        return i, PARAGRAPH_UNITS + min(spaces, 3) * SPACE_UNITS, "paragraph"
    if newlines == 1:
        return i, SPACE_UNITS + min(spaces, 2) * SPACE_UNITS, "space"
    return i, min(max(spaces, 1), 4) * SPACE_UNITS, "space"


def _parse_expressive(text: str) -> list[SheetEvent]:
    events: list[SheetEvent] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in " \t\r\n":
            i, units, label = _consume_whitespace(text, i)
            _append_pause(events, label, units)
            continue
        if ch == "[":
            end = text.find("]", i + 1)
            if end != -1:
                raw = text[i + 1:end]
                payload = _safe_payload(raw)
                if payload:
                    if any(char.isspace() for char in raw):
                        for key in payload: events.append(SheetEvent("fast", key, FAST_UNITS))
                    else:
                        events.append(SheetEvent("chord", payload, QUICK_UNITS))
                i = end + 1
                continue
        if ch == "{":
            end = text.find("}", i + 1)
            if end != -1:
                for key in _safe_payload(text[i + 1:end]):
                    events.append(SheetEvent("fast", key, FAST_UNITS))
                i = end + 1
                continue
        if ch == "-":
            run = 1
            while i + run < len(text) and text[i + run] == "-": run += 1
            _append_pause(events, "-", float(run)); i += run; continue
        if ch == "|":
            run = 1
            while i + run < len(text) and text[i + run] == "|": run += 1
            _append_pause(events, "|", BAR_UNITS * run); i += run; continue
        if ch in PLAYABLE_CHARS:
            events.append(SheetEvent("note", ch, QUICK_UNITS))
        i += 1
    while events and events[0].kind == "pause" and events[0].value in {"space", "paragraph"}: events.pop(0)
    while events and events[-1].kind == "pause" and events[-1].value in {"space", "paragraph"}: events.pop()
    return events


def _parse_grid(text: str, sustain_dashes: bool = False) -> list[SheetEvent]:
    """Parse token/grid notation used by VPsheet and several Roblox sheet hosts.

    Whitespace separates tokens but does not itself add time. Each ordinary note
    or chord advances one grid unit; '-', '_' and '|' are explicit rests.
    Brackets are always simultaneous chords, even when the site prints spaces
    inside them. Curly braces remain an explicit fast-run extension.
    """
    events: list[SheetEvent] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace(): i += 1; continue
        if ch == "[":
            end = text.find("]", i + 1)
            if end != -1:
                payload = _safe_payload(text[i + 1:end])
                if payload: events.append(SheetEvent("chord", payload, 1.0))
                i = end + 1; continue
        if ch == "{":
            end = text.find("}", i + 1)
            if end != -1:
                payload = _safe_payload(text[i + 1:end])
                for key in payload: events.append(SheetEvent("fast", key, 0.25))
                i = end + 1; continue
        if ch in "-_|":
            run = 1
            while i + run < len(text) and text[i + run] == ch: run += 1
            if ch == "-" and sustain_dashes and events and events[-1].kind in {"note", "fast", "chord"}:
                previous = events[-1]
                events[-1] = SheetEvent(previous.kind, previous.value, previous.units, previous.hold_units + float(run))
            _append_pause(events, ch, float(run)); i += run; continue
        if ch in PLAYABLE_CHARS:
            events.append(SheetEvent("note", ch, 1.0))
        i += 1
    return events



def _parse_letter_grid(text: str) -> list[SheetEvent]:
    """Parse Piano Letter Notes' horizontal dash clock.

    On this host the dashes *between* letters carry the timing. A note/chord is
    therefore an onset marker with no extra full beat of its own. If two onsets
    are printed directly adjacent with no dash, give them only a short transition
    rather than making them simultaneous.
    """
    events: list[SheetEvent] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "[":
            end = text.find("]", i + 1)
            if end != -1:
                payload = _safe_payload(text[i + 1:end])
                if payload:
                    events.append(SheetEvent("chord", payload, 0.0))
                i = end + 1
                continue
        if ch in "-_|":
            run = 1
            while i + run < len(text) and text[i + run] == ch:
                run += 1
            _append_pause(events, ch, float(run))
            i += run
            continue
        if ch in PLAYABLE_CHARS:
            events.append(SheetEvent("note", ch, 0.0))
        i += 1

    # Rare adjacent letters mean "play quickly", not a chord. Give only the
    # preceding onset a short step; dash-delimited notes keep exact dash timing.
    for index in range(len(events) - 1):
        event = events[index]
        if event.kind not in {"note", "chord", "fast"}:
            continue
        if events[index + 1].kind in {"note", "chord", "fast"}:
            events[index] = SheetEvent(event.kind, event.value, LETTER_ADJACENT_UNITS, event.hold_units)
    return events

def parse_sheet(text: str, profile: str = "expressive") -> list[SheetEvent]:
    profile = str(profile or "expressive").lower()
    if profile == "vpsheet":
        return _parse_grid(text, sustain_dashes=True)
    if profile == "letter_grid":
        return _parse_letter_grid(text)
    return _parse_grid(text) if profile in GRID_PROFILES else _parse_expressive(text)


def total_timing_units(text: str, profile: str = "expressive") -> float:
    return sum(event.units for event in parse_sheet(text, profile))


def summarize_sheet(text: str, profile: str = "expressive") -> dict[str, int | float | str]:
    events = parse_sheet(text, profile)
    return {
        "events": len(events),
        "notes": sum(1 for e in events if e.kind in {"note", "fast"}),
        "chords": sum(1 for e in events if e.kind == "chord"),
        "pauses": sum(1 for e in events if e.kind == "pause"),
        "timing_units": round(sum(e.units for e in events), 2),
        "timing_profile": str(profile or "expressive"),
    }
