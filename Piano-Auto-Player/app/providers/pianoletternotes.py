from __future__ import annotations

import html
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse

from ..midi_performance import MIDI_TO_TOKEN
from ..parser import parse_sheet
from .common import NETWORK_ERRORS, LinkCollector, dedupe_rank, get_html


NOTE_PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
STAFF_RE = re.compile(r"^\s*(?:(RH|LH)\s*:?\s*)?(\d)\s*\|(.*?)\|\s*$", re.I)


class _PageCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.code_parts: list[str] = []
        self._in_h1 = False
        self._in_code = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "h1":
            self._in_h1 = True
        if tag in {"code", "pre"}:
            self._in_code = True
            self.code_parts.append("")
        elif tag == "br" and self._in_code and self.code_parts:
            self.code_parts[-1] += "\n"

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._in_h1 = False
        if tag in {"code", "pre"}:
            self._in_code = False

    def handle_data(self, data: str) -> None:
        if self._in_h1:
            self.title_parts.append(data)
        if self._in_code and self.code_parts:
            self.code_parts[-1] += data


def _pitch_to_token(letter: str, octave: int) -> tuple[int, str] | None:
    lower = letter.lower()
    if lower not in NOTE_PC:
        return None
    midi = 12 * (octave + 1) + NOTE_PC[lower]
    if letter.isupper():
        midi += 1
    token = MIDI_TO_TOKEN.get(midi)
    return (midi, token) if token else None


def convert_letter_staff(source: str) -> tuple[str, dict[str, int]]:
    """Convert octave/RH/LH letter-grid notation into QWERTY piano tokens.

    Each source column is one timing slot. Notes that line up vertically across
    RH/LH rows become a simultaneous chord; empty columns become grid rests.
    """
    groups: list[list[tuple[str, int, str]]] = []
    current: list[tuple[str, int, str]] = []
    for raw_line in source.replace("\r", "").split("\n"):
        line = raw_line.strip("\ufeff ")
        match = STAFF_RE.match(line)
        if match:
            hand = str(match.group(1) or "").upper()
            octave = int(match.group(2))
            # Dashes are the site's timing grid. Ignore incidental HTML/formatting
            # whitespace inside a staff body so it cannot create fake beats.
            body = re.sub(r"\s+", "", match.group(3))
            lane = (hand, octave)
            used_lanes = {(row_hand, row_octave) for row_hand, row_octave, _body in current}
            # A printed block may contain RH rows at different octaves plus LH rows.
            # Blogger sometimes strips the blank line between blocks, so detect a
            # new block when RH starts again after LH *or* the same hand/octave lane
            # repeats. Repeated lanes cannot be vertically aligned voices on this
            # notation; they are the next sequential group.
            starts_new_group = bool(current) and (
                lane in used_lanes
                or (hand == "RH" and any(row_hand == "LH" for row_hand, _oct, _body in current))
            )
            if starts_new_group:
                groups.append(current)
                current = []
            current.append((hand, octave, body))
            continue
        if current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        raise ValueError("Could not find RH/LH octave-grid letter notes on that page.")

    output: list[str] = []
    onsets = chords = dropped = 0
    min_midi = 999
    max_midi = -1
    for rows in groups:
        width = max(len(body) for _hand, _octave, body in rows)
        for column in range(width):
            notes: list[tuple[int, str]] = []
            for _hand, octave, body in rows:
                if column >= len(body):
                    continue
                char = body[column]
                if char.lower() not in NOTE_PC:
                    continue
                converted = _pitch_to_token(char, octave)
                if converted is None:
                    dropped += 1
                    continue
                notes.append(converted)
            if not notes:
                output.append("-")
                continue
            ordered: list[tuple[int, str]] = []
            seen: set[int] = set()
            for midi, token in sorted(notes):
                if midi in seen:
                    continue
                seen.add(midi)
                ordered.append((midi, token))
            min_midi = min(min_midi, *(midi for midi, _token in ordered))
            max_midi = max(max_midi, *(midi for midi, _token in ordered))
            onsets += 1
            if len(ordered) == 1:
                output.append(ordered[0][1])
            else:
                chords += 1
                output.append("[" + "".join(token for _midi, token in ordered) + "]")

    sheet = "".join(output).strip("-")
    if not sheet:
        raise ValueError("The letter-note grid did not contain notes inside this piano's C2-C7 range.")
    return sheet, {
        "note_count": onsets,
        "chord_count": chords,
        "dropped_notes": dropped,
        "min_midi": min_midi if min_midi != 999 else 0,
        "max_midi": max_midi if max_midi >= 0 else 0,
    }


def extract_letter_staff(page_html: str) -> tuple[str, str]:
    collector = _PageCollector()
    collector.feed(page_html)
    candidates = [
        html.unescape(block).strip()
        for block in collector.code_parts
        if any(STAFF_RE.match(line.strip()) for line in block.splitlines())
    ]
    if not candidates:
        text = html.unescape(re.sub(r"<br\s*/?>", "\n", page_html, flags=re.I))
        text = re.sub(r"<[^>]+>", "", text)
        lines = [line for line in text.splitlines() if STAFF_RE.match(line.strip())]
        if lines:
            candidates = ["\n".join(lines)]
    if not candidates:
        raise ValueError("Could not find Piano Letter Notes staff data on that page.")
    source = max(candidates, key=lambda value: sum(bool(STAFF_RE.match(line.strip())) for line in value.splitlines()))
    title = " ".join(" ".join(collector.title_parts).split())
    title = re.sub(r"\s*\|\s*Piano Letter Notes.*$", "", title, flags=re.I).strip()
    return title or "Imported letter notes", source


class PianoLetterNotesProvider:
    id = "pianoletternotes"
    name = "Piano Letter Notes"
    BASE = "https://pianoletternotes.blogspot.com"
    ALLOWED_HOSTS = {"pianoletternotes.blogspot.com", "www.pianoletternotes.blogspot.com"}

    def __init__(self) -> None:
        self._feed_items: list[dict[str, str]] = []
        self._feed_loaded_at = 0.0

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        rows: list[dict[str, str]] = []
        for variant in self._query_variants(query):
            try:
                page, final_url = get_html(f"{self.BASE}/search?q={quote_plus(variant)}", timeout=8)
                rows.extend(self._post_links(page, final_url))
            except NETWORK_ERRORS:
                continue
        ranked = dedupe_rank(query, rows, limit)
        if len(ranked) < min(3, limit):
            ranked = dedupe_rank(query, rows + self._feed_catalog(), limit)
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True} for row in ranked]

    def fetch(self, url: str) -> dict[str, object]:
        if not self.accepts(url):
            raise ValueError("Not a Piano Letter Notes post URL.")
        page_html, final_url = get_html(url, timeout=15)
        title, source = extract_letter_staff(page_html)
        sheet, stats = convert_letter_staff(source)
        result: dict[str, object] = {
            "title": title,
            "artist": "",
            "sheet": sheet,
            "source": self.name,
            "source_url": final_url,
            "timing_profile": "letter_grid",
            # The host says roughly 5-6 dashes ≈ 1 second. v0.3.1 treats
            # dashes themselves as the inter-onset clock (notes no longer add
            # an extra full grid unit), so 1000 / 5.5 is the neutral midpoint.
            "recommended_interval_ms": 182.0,
            "source_format": "octave_letter_grid",
            "source_rows": sum(bool(STAFF_RE.match(line.strip())) for line in source.splitlines()),
        }
        result.update(stats)
        result["parsed_events"] = len(parse_sheet(sheet, "letter_grid"))
        return result

    def accepts(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.ALLOWED_HOSTS and bool(re.search(r"/20\d{2}/\d{2}/[^/]+\.html$", parsed.path))

    @staticmethod
    def _query_variants(query: str) -> list[str]:
        values = [query]
        for separator in (" — ", " – ", " - "):
            if separator in query:
                values.append(query.split(separator, 1)[0].strip())
        compact = " ".join(dict.fromkeys(re.findall(r"[A-Za-z0-9]+", query)))
        if compact:
            values.append(compact)
        return list(dict.fromkeys(value for value in values if value))[:3]

    def _post_links(self, page_html: str, base_url: str) -> list[dict[str, str]]:
        parser = LinkCollector()
        parser.feed(page_html)
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for link in parser.links:
            url = urljoin(base_url, html.unescape(link.get("href", "")))
            if url in seen or not self.accepts(url):
                continue
            seen.add(url)
            title = " ".join(link.get("text", "").split())
            if not title:
                title = urlparse(url).path.rsplit("/", 1)[-1].removesuffix(".html").replace("-", " ").title()
            rows.append({"title": title, "artist": "", "url": url})
        return rows

    def _feed_catalog(self) -> list[dict[str, str]]:
        if self._feed_items and time.time() - self._feed_loaded_at < 1800:
            return self._feed_items
        rows: list[dict[str, str]] = []
        for start in (1, 501, 1001, 1501):
            try:
                body, _ = get_html(
                    f"{self.BASE}/feeds/posts/default?alt=json&max-results=500&start-index={start}", timeout=10
                )
                data = json.loads(body)
            except (NETWORK_ERRORS, json.JSONDecodeError, TypeError, ValueError):
                break
            entries = data.get("feed", {}).get("entry", []) or []
            if not entries:
                break
            for entry in entries:
                title = str(entry.get("title", {}).get("$t", "")).strip()
                url = ""
                for link in entry.get("link", []) or []:
                    if link.get("rel") == "alternate":
                        url = str(link.get("href") or "")
                        break
                if title and url and self.accepts(url):
                    rows.append({"title": title, "artist": "", "url": url})
            if len(entries) < 500:
                break
        self._feed_items = rows
        self._feed_loaded_at = time.time()
        return rows
