from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

from ..parser import parse_sheet, total_timing_units
from .common import get_html
from .extractor import extract_sheet_from_html, extract_sheet_metadata
from .sitecatalog import CachedSiteCatalog


class GamePianoSheetsProvider:
    id = "gamepianosheets"
    name = "Game Piano Sheets"
    BASE = "https://gamepianosheets.com"
    ALLOWED_HOSTS = {"gamepianosheets.com", "www.gamepianosheets.com"}

    def __init__(self) -> None:
        self.catalog = CachedSiteCatalog(self.BASE, "/sheets/")

    def search(self, query: str, limit: int = 12) -> list[dict]:
        q = quote_plus(query.strip())
        if not q:
            return []
        rows = self.catalog.search_pages(query, [f"/?s={q}", f"/?q={q}", f"/search?q={q}"], limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in rows]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url):
            raise ValueError("Not a Game Piano Sheets URL.")
        page_html, final_url = get_html(url, timeout=15)
        metadata = extract_sheet_metadata(page_html)
        expected_notes = int(metadata.get("note_count") or 0) or None
        title, artist, sheet = extract_sheet_from_html(page_html, expected_notes=expected_notes)
        title, artist = self._clean_title_artist(title, artist)
        result: dict[str, object] = {
            "title": title,
            "artist": artist,
            "sheet": sheet,
            "source": self.name,
            "source_url": final_url,
            # This host uses '-' after notes as real sustain/time spacing.
            "timing_profile": "vpsheet",
            **metadata,
        }
        events = parse_sheet(sheet, "vpsheet")
        result["parsed_events"] = len(events)
        duration = float(metadata.get("duration_seconds") or 0.0)
        units = total_timing_units(sheet, "vpsheet")
        if duration > 0 and units > 0:
            result["recommended_interval_ms"] = round(duration * 1000.0 / units, 1)
        return result

    @staticmethod
    def _clean_title_artist(title: str, artist: str) -> tuple[str, str]:
        cleaned = re.sub(r"\s+Roblox\s+Piano\s+Sheet.*$", "", title, flags=re.I).strip()
        if " - " in cleaned and not artist:
            left, right = cleaned.rsplit(" - ", 1)
            if len(right.split()) <= 6:
                cleaned, artist = left.strip(), right.strip()
        return cleaned or "Imported Game Piano sheet", artist

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/sheets/" in parsed.path
