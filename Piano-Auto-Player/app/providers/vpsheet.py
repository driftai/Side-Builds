from urllib.parse import quote_plus, urlparse

from .common import NETWORK_ERRORS, dedupe_rank, get_html, links_matching
from .extractor import extract_sheet_from_html, extract_sheet_metadata
from ..parser import parse_sheet


class VPSheetProvider:
    id = "vpsheet"
    name = "VPsheet"
    BASE = "https://vpsheet.com"
    ALLOWED_HOSTS = {"vpsheet.com", "www.vpsheet.com"}

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        results: list[dict] = []
        urls = [
            f"{self.BASE}/search?q={quote_plus(query)}",
            f"{self.BASE}/genre?q={quote_plus(query)}",
            f"{self.BASE}/?s={quote_plus(query)}",
        ]
        for url in urls:
            try:
                page, final_url = get_html(url, timeout=7)
                results.extend(links_matching(page, final_url, "/sheet/"))
            except NETWORK_ERRORS:
                pass
        ranked = dedupe_rank(query, results, limit)
        if not ranked:
            slug = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in query).split())
            if slug:
                guessed = f"{self.BASE}/sheet/{slug}"
                try:
                    _page, final_url = get_html(guessed, timeout=6)
                    results.append({"title": query, "artist": "", "url": final_url})
                    ranked = dedupe_rank(query, results, limit)
                except NETWORK_ERRORS:
                    pass
        if not ranked:
            for page_no in range(1, 8):
                try:
                    suffix = "" if page_no == 1 else f"?page={page_no}"
                    page, final_url = get_html(f"{self.BASE}/genre{suffix}", timeout=6)
                    results.extend(links_matching(page, final_url, "/sheet/"))
                except NETWORK_ERRORS:
                    break
                ranked = dedupe_rank(query, results, limit)
                if len(ranked) >= limit:
                    break
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in ranked]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url):
            raise ValueError("Not a VPsheet sheet URL.")
        page_html, final_url = get_html(url, timeout=15)
        metadata = extract_sheet_metadata(page_html)
        expected_notes = int(metadata.get("note_count") or 0) or None
        # Current VPsheet pages frequently client-load the actual notation. If the
        # host publishes a note total, require our extracted payload to agree with
        # it closely; performance-tip snippets and page chrome are not a song.
        title, artist, sheet = extract_sheet_from_html(page_html, expected_notes=expected_notes)
        if "loading sheet" in page_html.lower() and not expected_notes:
            raise ValueError("VPsheet did not expose enough verifiable notation in the server response; refusing to guess from page data.")

        events = parse_sheet(sheet, "vpsheet")
        total_units = sum(event.units for event in events)
        duration = float(metadata.get("duration_seconds") or 0.0)
        bpm = float(metadata.get("bpm") or 0.0)
        interval_ms = 0.0
        if duration > 0 and total_units > 0:
            interval_ms = duration * 1000.0 / total_units
        elif bpm > 0:
            interval_ms = 30000.0 / bpm  # eighth-note grid at the source tempo

        result: dict[str, object] = {
            "title": title,
            "artist": artist,
            "sheet": sheet,
            "source": self.name,
            "source_url": final_url,
            "timing_profile": "vpsheet",
        }
        result.update(metadata)
        if interval_ms > 0:
            result["recommended_interval_ms"] = round(max(25.0, min(interval_ms, 1000.0)), 1)
        return result

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/sheet/" in parsed.path
