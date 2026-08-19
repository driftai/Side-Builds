from urllib.parse import quote_plus, urlparse

from .common import NETWORK_ERRORS, dedupe_rank, get_html, links_matching
from .extractor import extract_sheet_from_html, sheet_links_from_html


class PlayPianoSheetsProvider:
    id = "playpianosheets"
    name = "PlayPianoSheets"
    BASE = "https://playpianosheets.com"
    ALLOWED_HOSTS = {"playpianosheets.com", "www.playpianosheets.com"}

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        results: list[dict] = []

        # The site's search page has changed behavior more than once. Try it,
        # then fall back to catalog pages so a client-rendering change does not
        # make the local finder appear empty.
        for url in (
            f"{self.BASE}/search?q={quote_plus(query)}",
            f"{self.BASE}/category/all?q={quote_plus(query)}",
        ):
            try:
                page, final_url = get_html(url, timeout=8)
                results.extend(sheet_links_from_html(page, final_url))
            except NETWORK_ERRORS:
                pass

        ranked = dedupe_rank(query, results, limit)
        if len(ranked) >= min(limit, 4):
            return self._tag(ranked)

        slug = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in query).split())
        if slug:
            try:
                _page, final_url = get_html(f"{self.BASE}/sheets/{slug}", timeout=6)
                results.append({"title": query, "artist": "", "url": final_url})
                ranked = dedupe_rank(query, results, limit)
            except NETWORK_ERRORS:
                pass

        # Catalog fallback. Current catalog is paginated; cap work to avoid a
        # dead host tying up the whole multi-provider search.
        for page_no in range(1, 17):
            try:
                suffix = "" if page_no == 1 else f"?page={page_no}"
                page, final_url = get_html(f"{self.BASE}/category/all{suffix}", timeout=6)
                results.extend(links_matching(page, final_url, "/sheets/"))
            except NETWORK_ERRORS:
                break
            ranked = dedupe_rank(query, results, limit)
            if len(ranked) >= limit:
                break
        return self._tag(ranked)

    def fetch(self, url: str) -> dict[str, str]:
        self._validate_url(url)
        page_html, final_url = get_html(url, timeout=15)
        title, artist, sheet = extract_sheet_from_html(page_html)
        return {"title": title, "artist": artist, "sheet": sheet, "source": self.name, "source_url": final_url}

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/sheets/" in parsed.path

    def _validate_url(self, url: str) -> None:
        if not self.accepts(url):
            raise ValueError("Not a PlayPianoSheets sheet URL.")

    def _tag(self, rows: list[dict]) -> list[dict]:
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in rows]
