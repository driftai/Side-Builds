from __future__ import annotations

import html
from urllib.parse import quote_plus, urljoin, urlparse

from .common import NETWORK_ERRORS, LinkCollector, dedupe_rank, get_html
from .extractor import extract_sheet_from_html


class DynShiiProvider:
    id = "dynshii"
    name = "Dyn Shii Archive"
    BASE = "https://virtualpianoitzdyn.blogspot.com"
    ALLOWED_HOSTS = {"virtualpianoitzdyn.blogspot.com"}

    def search(self, query: str, limit: int = 12) -> list[dict]:
        if not query.strip(): return []
        try:
            page, final_url = get_html(f"{self.BASE}/search?q={quote_plus(query)}", timeout=9)
        except NETWORK_ERRORS:
            return []
        parser = LinkCollector(); parser.feed(page)
        rows, seen = [], set()
        for link in parser.links:
            href = html.unescape(link.get("href", ""))
            url = urljoin(final_url, href)
            parsed = urlparse(url)
            if parsed.hostname not in self.ALLOWED_HOSTS or not parsed.path.endswith(".html") or url in seen:
                continue
            seen.add(url)
            title = " ".join(link.get("text", "").split()) or parsed.path.rsplit("/", 1)[-1].replace("-", " ")
            rows.append({"title": title, "artist": "", "url": url})
        ranked = dedupe_rank(query, rows, limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in ranked]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url): raise ValueError("Not a Dyn Shii sheet URL.")
        page_html, final_url = get_html(url, timeout=15)
        title, artist, sheet = extract_sheet_from_html(page_html)
        title = title.replace("Virtual Piano Sheets by Dyn Shii:", "").strip()
        return {
            "title": title or "Imported sheet", "artist": artist, "sheet": sheet,
            "source": self.name, "source_url": final_url, "timing_profile": "roblox_grid",
        }

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and parsed.path.endswith(".html")
