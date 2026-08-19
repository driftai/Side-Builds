from __future__ import annotations

from urllib.parse import quote_plus, urlparse

from .common import get_html
from .extractor import extract_sheet_from_html, extract_sheet_metadata
from .sitecatalog import CachedSiteCatalog


class VirtualPianoSheetProvider:
    id = "virtualpianosheet"
    name = "VirtualPianoSheet"
    BASE = "https://virtualpianosheet.com"
    ALLOWED_HOSTS = {"virtualpianosheet.com", "www.virtualpianosheet.com"}

    def __init__(self) -> None:
        self.catalog = CachedSiteCatalog(self.BASE, "/sheets/")

    def search(self, query: str, limit: int = 12) -> list[dict]:
        q = quote_plus(query.strip())
        if not q: return []
        rows = self.catalog.search_pages(query, [f"/search?q={q}", f"/?q={q}", f"/?s={q}", "/category/all"], limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in rows]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url): raise ValueError("Not a VirtualPianoSheet URL.")
        page_html, final_url = get_html(url, timeout=15)
        metadata = extract_sheet_metadata(page_html)
        title, artist, sheet = extract_sheet_from_html(page_html)
        result: dict[str, object] = {
            "title": title, "artist": artist, "sheet": sheet, "source": self.name,
            "source_url": final_url, "timing_profile": "roblox_grid",
        }
        result.update(metadata)
        bpm = float(metadata.get("bpm") or 0.0)
        if bpm > 0:
            result["recommended_interval_ms"] = round(max(25.0, min(30000.0 / bpm, 1000.0)), 1)
        return result

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/sheets/" in parsed.path
