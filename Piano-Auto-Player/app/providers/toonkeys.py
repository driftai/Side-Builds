from __future__ import annotations

import html
import re
import time
from urllib.parse import urljoin

from .common import get_html, score_match


_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)


class ToonKeysProvider:
    """Discovery-only catalog for Toon Keys sheet/MIDI arrangements.

    The public catalog is valuable for finding arrangements that the Roblox-sheet
    hosts miss, but its MIDI links may lead to Patreon or other access-controlled
    pages. Those results are deliberately source-only unless a future importer can
    verify a directly downloadable file.
    """

    id = "toonkeys"
    name = "Toon Keys Catalog"
    BASE = "https://toonkeyssheets.netlify.app/"

    def __init__(self) -> None:
        self._rows: list[dict] = []
        self._loaded_at = 0.0

    def _catalog(self) -> list[dict]:
        if self._rows and time.time() - self._loaded_at < 1800:
            return self._rows
        page, final_url = get_html(self.BASE, timeout=12)
        rows: list[dict] = []
        for raw in _ROW.findall(page):
            links = [(urljoin(final_url, html.unescape(href)), _TAG.sub("", label).strip()) for href, label in _HREF.findall(raw)]
            plain = html.unescape(_TAG.sub(" ", raw))
            plain = " ".join(plain.split())
            if not plain or not links:
                continue
            title = re.sub(r"\s+(?:Sheet|MIDI|YouTube)\b.*$", "", plain, flags=re.I).strip()
            if not title:
                continue
            sheet_url = next((url for url, label in links if label.lower() == "sheet"), links[0][0])
            midi_url = next((url for url, label in links if "midi" in label.lower()), "")
            video_url = next((url for url, label in links if "youtube" in label.lower()), "")
            rows.append({"title": title, "url": sheet_url, "midi_url": midi_url, "video_url": video_url})
        self._rows = rows
        self._loaded_at = time.time()
        return rows

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        ranked = []
        for row in self._catalog():
            score = score_match(query, row["title"], "")
            if score <= 0:
                continue
            ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["title"].lower()))
        return [
            {
                **row,
                "artist": "",
                "provider": self.id,
                "provider_name": self.name,
                "importable": False,
                "reference_only": True,
            }
            for _score, row in ranked[:limit]
        ]

    def fetch(self, _url: str) -> dict:
        raise ValueError("Toon Keys is a discovery source; use its source link or the YouTube-to-Piano converter.")

    def accepts(self, _url: str) -> bool:
        return False
