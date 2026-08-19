from __future__ import annotations


def performance_to_sheet(events: list[dict], events_per_line: int = 16) -> str:
    """Render a timed performance as readable QWERTY notation.

    The timed performance remains authoritative for playback. This transcript is
    primarily a visible/copyable representation for the sheet editor, so it does
    not attempt to flatten millisecond timing into approximate rest characters.
    """
    tokens: list[str] = []
    for event in events or []:
        key = str(event.get("key") or "").strip()
        if not key:
            continue
        token = f"[{key}]" if len(key) > 1 else key
        tokens.append(token)
    if not tokens:
        return ""
    width = max(1, int(events_per_line or 16))
    return "\n".join(" ".join(tokens[i:i + width]) for i in range(0, len(tokens), width))
