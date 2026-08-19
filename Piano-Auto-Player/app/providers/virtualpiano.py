from urllib.parse import quote_plus, urlparse

from ..parser import parse_sheet
from .common import NETWORK_ERRORS, dedupe_rank, get_html, links_matching
from .extractor import extract_sheet_metadata, extract_virtual_piano_sheet


class VirtualPianoProvider:
    id = "virtualpiano"
    name = "Virtual Piano"
    BASE = "https://virtualpiano.net"
    ALLOWED_HOSTS = {"virtualpiano.net", "www.virtualpiano.net"}

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        results: list[dict] = []
        for url in (f"{self.BASE}/?s={quote_plus(query)}", f"{self.BASE}/music-sheets/?s={quote_plus(query)}"):
            try:
                page, final_url = get_html(url, timeout=8)
                results.extend(links_matching(page, final_url, "/music-sheet/"))
            except NETWORK_ERRORS:
                pass
        ranked = dedupe_rank(query, results, limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in ranked]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url):
            raise ValueError("Not a Virtual Piano music-sheet URL.")
        page_html, final_url = get_html(url, timeout=15)
        metadata = extract_sheet_metadata(page_html)
        title, artist, sheet = extract_virtual_piano_sheet(page_html)

        result: dict[str, object] = {
            "title": title,
            "artist": artist,
            "sheet": sheet,
            "source": self.name,
            "source_url": final_url,
            "timing_profile": "expressive",
        }
        result.update(metadata)

        duration = float(metadata.get("duration_seconds") or 0.0)
        total_units = sum(event.units for event in parse_sheet(sheet))
        if duration > 0 and total_units > 0:
            interval_ms = duration * 1000.0 / total_units
            result["recommended_interval_ms"] = round(max(25.0, min(interval_ms, 1000.0)), 1)
        return result

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/music-sheet/" in parsed.path
