from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

from ..midi_performance import midi_to_performance
from ..parser import parse_sheet
from ..performance_notation import performance_to_sheet
from .common import get_bytes, get_html
from .extractor import extract_sheet_from_html, extract_sheet_metadata
from .roblox_current import extract_button_notation, find_midi_download
from .sitecatalog import CachedSiteCatalog


class RobloxPianoSheetProvider:
    id = "robloxpianosheet"
    name = "RobloxPianoSheet"
    BASE = "https://robloxpianosheet.com"
    ALLOWED_HOSTS = {"robloxpianosheet.com", "www.robloxpianosheet.com"}

    def __init__(self) -> None:
        self.catalog = CachedSiteCatalog(self.BASE, "/sheets/")

    def search(self, query: str, limit: int = 12) -> list[dict]:
        q = quote_plus(query.strip())
        if not q:
            return []
        rows = self.catalog.search_pages(query, [
            f"/all-roblox-piano-sheets?q={q}", f"/all-roblox-piano-sheets?search={q}", f"/?q={q}",
        ], limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in rows]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url):
            raise ValueError("Not a RobloxPianoSheet sheet URL.")
        page_html, final_url = get_html(url, timeout=15)
        metadata = extract_sheet_metadata(page_html)
        title, artist = self._title_artist(page_html)

        midi_url = find_midi_download(page_html, final_url)
        if midi_url:
            try:
                data, downloaded = get_bytes(midi_url, timeout=20, accept="audio/midi,audio/x-midi,application/octet-stream,*/*")
                if data[:4] == b"MThd":
                    performance, stats = midi_to_performance(data)
                    return {
                        "title": title, "artist": artist, "sheet": performance_to_sheet(performance),
                        "performance": performance, "source": self.name, "source_url": final_url,
                        "midi_url": downloaded, "timing_profile": "midi", "fidelity": "midi", **metadata, **stats,
                    }
            except (OSError, ValueError):
                pass

        expected_tokens = int(metadata.get("token_count") or 0) or None
        try:
            sheet = extract_button_notation(page_html, expected_tokens)
        except ValueError:
            # Legacy pages may still embed a dedicated notation payload. The
            # generic extractor is now contamination-guarded and host-counted.
            _found_title, _found_artist, sheet = extract_sheet_from_html(
                page_html, expected_tokens=expected_tokens
            )
        result: dict[str, object] = {
            "title": title, "artist": artist, "sheet": sheet, "source": self.name,
            "source_url": final_url, "timing_profile": "roblox_grid",
        }
        result.update(metadata)
        bpm = float(metadata.get("bpm") or 0.0)
        if bpm > 0:
            result["recommended_interval_ms"] = round(max(25.0, min(30000.0 / bpm, 1000.0)), 1)
        result["parsed_events"] = len(parse_sheet(sheet, "roblox_grid"))
        return result

    @staticmethod
    def _title_artist(page_html: str) -> tuple[str, str]:
        title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", page_html, re.I | re.S)
        raw = re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "")
        title = " ".join(raw.split()) or "Imported Roblox piano sheet"
        artist = ""
        match = re.match(r"(.+?)\s+Roblox\s+Piano\s+Sheet\s+by\s+(.+)$", title, re.I)
        if match:
            title, artist = match.group(1).strip(), match.group(2).strip()
        return title, artist

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/sheets/" in parsed.path
