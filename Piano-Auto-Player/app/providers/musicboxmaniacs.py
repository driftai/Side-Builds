from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse

from ..midi_performance import midi_to_performance
from .common import LinkCollector, dedupe_rank, get_bytes, get_html


class _TitleCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self._h1 = False

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self._h1 = True

    def handle_endtag(self, tag):
        if tag == "h1":
            self._h1 = False

    def handle_data(self, data):
        if self._h1:
            self.title.append(data)


class MusicBoxManiacsProvider:
    id = "musicboxmaniacs"
    name = "Music Box Maniacs MIDI"
    BASE = "https://musicboxmaniacs.com"
    ALLOWED_HOSTS = {"musicboxmaniacs.com", "www.musicboxmaniacs.com"}

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        page, final_url = get_html(f"{self.BASE}/explore/?q={quote_plus(query)}", timeout=10)
        collector = LinkCollector()
        collector.feed(page)
        rows = []
        for link in collector.links:
            href = html.unescape(link.get("href", ""))
            if "/explore/melody/" not in href:
                continue
            title = " ".join(link.get("text", "").split())
            if title:
                rows.append({"title": title, "artist": "", "url": urljoin(final_url, href)})
        return self._tag(dedupe_rank(query, rows, limit))

    def fetch(self, url: str) -> dict:
        self._validate_url(url)
        page, final_url = get_html(url, timeout=15)
        title_parser = _TitleCollector()
        title_parser.feed(page)
        title = " ".join(title_parser.title).strip() or "Music Box melody"
        midi_url = self._midi_url(page, final_url)
        if not midi_url:
            raise ValueError("Music Box Maniacs did not expose a MIDI download link for this melody.")
        midi, _download_url = get_bytes(midi_url, timeout=20, accept="audio/midi,audio/x-midi,application/octet-stream,*/*")
        performance, stats = midi_to_performance(midi)
        return {
            "title": title,
            "artist": "",
            "sheet": "",
            "performance": performance,
            "source": self.name,
            "source_url": final_url,
            "timing_profile": "midi",
            **stats,
        }

    @staticmethod
    def _midi_url(page: str, base_url: str) -> str:
        collector = LinkCollector()
        collector.feed(page)
        candidates: list[tuple[int, str]] = []
        for link in collector.links:
            href = html.unescape(link.get("href", ""))
            text = " ".join(link.get("text", "").lower().split())
            lower = href.lower()
            score = 0
            if lower.endswith((".mid", ".midi")):
                score += 100
            if "midi" in lower:
                score += 60
            if "midi" in text:
                score += 40
            if score and href:
                candidates.append((score, urljoin(base_url, href)))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
        # Some versions render the export control with no useful anchor text.
        match = re.search(r'''(?:href|data-url)=["']([^"']*(?:midi|\.mid)[^"']*)["']''', page, re.I)
        return urljoin(base_url, html.unescape(match.group(1))) if match else ""

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and "/explore/melody/" in parsed.path

    def _validate_url(self, url: str) -> None:
        if not self.accepts(url):
            raise ValueError("Not a Music Box Maniacs melody URL.")

    def _tag(self, rows: list[dict]) -> list[dict]:
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True, "fidelity": "midi"} for row in rows]
