from urllib.parse import quote_plus, urlparse

from .common import NETWORK_ERRORS, dedupe_rank, get_html, links_matching
from .extractor import extract_sheet_from_html


class MyVirtualPianoSheetsProvider:
    id = "myvirtualpiano"
    name = "My Virtual Piano Sheets"
    BASE = "https://myvirtualpianosheets.com"
    ALLOWED_HOSTS = {"myvirtualpianosheets.com", "www.myvirtualpianosheets.com"}

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        try:
            page, final_url = get_html(f"{self.BASE}/?s={quote_plus(query)}", timeout=8)
            rows = links_matching(page, final_url, "/sheet")
        except NETWORK_ERRORS:
            rows = []
        ranked = dedupe_rank(query, rows, limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in ranked]

    def fetch(self, url: str) -> dict[str, str]:
        if not self.accepts(url):
            raise ValueError("Not a My Virtual Piano Sheets URL.")
        page_html, final_url = get_html(url, timeout=15)
        title, artist, sheet = extract_sheet_from_html(page_html)
        return {"title": title, "artist": artist, "sheet": sheet, "source": self.name, "source_url": final_url}

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "sheet" in parsed.path.lower()
