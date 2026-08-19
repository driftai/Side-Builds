from __future__ import annotations

from .notation_quality import sheet_contamination_reason


def validate_sheet_text(text: str) -> None:
    candidate = str(text or "").strip()
    if not candidate:
        raise ValueError("Sheet is empty.")
    reason = sheet_contamination_reason(candidate)
    if reason:
        raise ValueError(
            f"Rejected non-piano data ({reason}). Re-import the song instead of playing this extracted payload."
        )
