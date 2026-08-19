from __future__ import annotations

import html
import re
import time
from urllib.parse import urljoin, urlparse

from .common import NETWORK_ERRORS, LinkCollector, dedupe_rank, get_html


class CachedSiteCatalog:
    def __init__(self, base: str, sheet_fragment: str = "/sheets/") -> None:
        self.base = base.rstrip("/")
        self.sheet_fragment = sheet_fragment
        self._items: list[dict[str, str]] = []
        self._loaded_at = 0.0

    def search_pages(self, query: str, paths: list[str], limit: int) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for path in paths:
            try:
                page, final_url = get_html(urljoin(self.base + "/", path.lstrip("/")), timeout=7)
                items.extend(self._links(page, final_url))
            except NETWORK_ERRORS:
                pass
        ranked = dedupe_rank(query, items, limit)
        if len(ranked) >= min(3, limit):
            return ranked
        return dedupe_rank(query, items + self._sitemap_items(), limit)

    def _sitemap_items(self) -> list[dict[str, str]]:
        if self._items and time.time() - self._loaded_at < 1800:
            return self._items
        urls: list[str] = []
        locs: list[str] = []
        # WordPress/Next sites vary between a plain sitemap and a sitemap index.
        # Try the common entry points before giving up on catalog discovery.
        for sitemap_path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-0.xml"):
            try:
                xml, _ = get_html(self.base + sitemap_path, timeout=10)
            except NETWORK_ERRORS:
                continue
            locs = [html.unescape(value.strip()) for value in re.findall(r"<loc>(.*?)</loc>", xml, re.I | re.S)]
            if locs:
                break

        child_maps = [url for url in locs if url.lower().endswith(".xml")][:16]
        urls.extend(url for url in locs if self.sheet_fragment in url)
        for child in child_maps:
            try:
                body, _ = get_html(child, timeout=8)
                urls.extend(
                    html.unescape(value.strip())
                    for value in re.findall(r"<loc>(.*?)</loc>", body, re.I | re.S)
                    if self.sheet_fragment in value
                )
            except NETWORK_ERRORS:
                continue
        self._items = [self._url_item(url) for url in dict.fromkeys(urls) if self._valid_url(url)]
        self._loaded_at = time.time()
        return self._items

    def _links(self, page_html: str, base_url: str) -> list[dict[str, str]]:
        parser = LinkCollector(); parser.feed(page_html)
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for link in parser.links:
            href = html.unescape(link.get("href", ""))
            if self.sheet_fragment not in href:
                continue
            url = urljoin(base_url, href)
            if url in seen or not self._valid_url(url):
                continue
            seen.add(url)
            title = " ".join(link.get("text", "").split()) or self._slug_title(url)
            items.append({"title": title, "artist": "", "url": url})
        return items

    def _valid_url(self, url: str) -> bool:
        parsed = urlparse(url)
        base_host = urlparse(self.base).hostname or ""
        host = parsed.hostname or ""
        return (host == base_host or host.endswith("." + base_host)) and self.sheet_fragment in parsed.path

    def _url_item(self, url: str) -> dict[str, str]:
        return {"title": self._slug_title(url), "artist": "", "url": url}

    @staticmethod
    def _slug_title(url: str) -> str:
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        return slug.replace("-", " ").replace("_", " ").title()
