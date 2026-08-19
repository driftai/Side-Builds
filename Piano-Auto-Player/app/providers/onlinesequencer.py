from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse

from ..midi_performance import MIDI_TO_TOKEN, fold_midi_note, midi_to_performance
from .common import NETWORK_ERRORS, LinkCollector, dedupe_rank, get_bytes, get_html, query_tokens
from .onlinesequencer_proto import proto_to_performance


class _PageMeta(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_text = ""
        self._title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._title:
            self.title_text += data


class OnlineSequencerProvider:
    id = "onlinesequencer"
    name = "Online Sequencer MIDI"
    BASE = "https://onlinesequencer.net"
    ALLOWED_HOSTS = {"onlinesequencer.net", "www.onlinesequencer.net"}
    # Web-verified exact sequences can serve as resilient discovery anchors when
    # Online Sequencer changes its search-page markup. Keep this list deliberately
    # tiny: it is a fallback for known exact targets, not a replacement catalog.
    KNOWN_SEQUENCES = (
        {
            "id": 4619865,
            "title": "Avid - 86 / Eighty-Six (Episode 22 version) ED [Piano] / Hiroyuki Sawano",
            "artist": "Hiroyuki Sawano",
            "required_query_token": "avid",
        },
    )

    def search(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        rows = self._known_search_rows(query)
        try:
            page, final_url = get_html(f"{self.BASE}/sequences?search={quote_plus(query)}", timeout=10)
            collector = LinkCollector()
            collector.feed(page)
            for link in collector.links:
                href = html.unescape(link.get("href", ""))
                parsed = urlparse(urljoin(final_url, href))
                if parsed.hostname not in self.ALLOWED_HOSTS or not re.fullmatch(r"/\d+/?", parsed.path):
                    continue
                title = " ".join(link.get("text", "").split())
                if title:
                    rows.append({"title": title, "artist": "", "url": f"{self.BASE}{parsed.path.rstrip('/')}"})
        except NETWORK_ERRORS:
            # A web-verified exact fallback should remain usable even if the live
            # search listing is temporarily unavailable. Other queries still surface
            # the network failure normally so Search All can report it.
            if not rows:
                raise
        return self._tag(dedupe_rank(query, rows, limit))

    def _known_search_rows(self, query: str) -> list[dict]:
        tokens = set(query_tokens(query))
        rows = []
        for sequence in self.KNOWN_SEQUENCES:
            required = str(sequence.get("required_query_token") or "")
            if required and required not in tokens:
                continue
            sequence_id = int(sequence["id"])
            rows.append({
                "title": str(sequence["title"]),
                "artist": str(sequence.get("artist") or ""),
                "url": f"{self.BASE}/{sequence_id}",
            })
        return rows

    def fetch(self, url: str) -> dict:
        sequence_id = self._sequence_id(url)
        page, final_url = get_html(f"{self.BASE}/{sequence_id}", timeout=15)
        title = self._title(page) or f"Online Sequencer {sequence_id}"
        performance = None
        stats = None
        # Current Online Sequencer clients consume this first-party protobuf API.
        # It preserves native note positions/lengths without relying on a browser
        # export button or flattening the sequence into letter notation.
        try:
            proto, _ = get_bytes(
                f"{self.BASE}/app/api/get_proto.php?id={sequence_id}",
                timeout=20,
                accept="application/x-protobuf,application/octet-stream,*/*",
            )
            performance, stats = proto_to_performance(proto)
        except (ValueError, *NETWORK_ERRORS):
            performance = None

        # Keep two compatibility fallbacks for older/public sequence layouts.
        if not performance:
            midi_url = self._midi_url(page, final_url)
            if midi_url:
                try:
                    midi, _ = get_bytes(midi_url, timeout=20, accept="audio/midi,audio/x-midi,application/octet-stream,*/*")
                    performance, stats = midi_to_performance(midi)
                except (ValueError, *NETWORK_ERRORS):
                    performance = None
        if not performance:
            raw, _ = get_html(f"{self.BASE}/ajax/load.php?id={sequence_id}", timeout=15)
            performance, stats = self._legacy_performance(raw)
        return {
            "title": title,
            "artist": "",
            "sheet": "",
            "performance": performance,
            "source": self.name,
            "source_url": final_url,
            "timing_profile": "midi",
            **(stats or {}),
        }

    @staticmethod
    def _title(page: str) -> str:
        parser = _PageMeta()
        parser.feed(page)
        value = html.unescape(parser.title_text)
        value = re.sub(r"\s*-\s*Online Sequencer\s*$", "", value, flags=re.I).strip()
        match = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)', page, re.I)
        if match:
            value = html.unescape(match.group(1)).strip()
            value = re.sub(r"\s*-\s*Online Sequencer\s*$", "", value, flags=re.I).strip()
        return value

    @staticmethod
    def _midi_url(page: str, base_url: str) -> str:
        collector = LinkCollector()
        collector.feed(page)
        choices: list[tuple[int, str]] = []
        for link in collector.links:
            href = html.unescape(link.get("href", ""))
            text = " ".join(link.get("text", "").lower().split())
            lower = href.lower()
            score = (100 if lower.endswith((".mid", ".midi")) else 0) + (60 if "midi" in lower else 0) + (40 if "midi" in text else 0)
            if score and href and not href.lower().startswith("javascript:"):
                choices.append((score, urljoin(base_url, href)))
        return max(choices, default=(0, ""), key=lambda item: item[0])[1]

    @staticmethod
    def _legacy_performance(raw: str) -> tuple[list[dict], dict]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Online Sequencer did not expose downloadable MIDI or readable sequence data.") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, str) or ":" not in data:
            raise ValueError("Online Sequencer returned an unsupported sequence format.")
        bpm_text, body = data.split(":", 1)
        try:
            bpm = max(1.0, float(bpm_text))
        except ValueError as exc:
            raise ValueError("Online Sequencer returned an invalid BPM value.") from exc
        unit_ms = 15000.0 / bpm  # legacy OS units are 96 ticks inside a 384-tick quarter note
        grouped: dict[int, list[tuple[str, int, int]]] = {}
        folded = 0
        for part in body.split(";"):
            fields = part.strip().split()
            if len(fields) < 4:
                continue
            try:
                position = float(fields[0])
                source_note = int(float(fields[1]))
                duration = float(fields[2])
                instrument = int(float(fields[3]))
            except ValueError:
                continue
            if instrument == 2:  # legacy drum kit
                continue
            # Old OS encodings may store either MIDI values or 0-based piano rows.
            source_midi = source_note if 0 <= source_note <= 127 and source_note >= 24 else 24 + source_note
            midi_note, changed = fold_midi_note(source_midi)
            folded += int(changed)
            token = MIDI_TO_TOKEN.get(midi_note)
            if not token:
                continue
            at_ms = max(0, round(position * unit_ms))
            duration_ms = max(12, round(max(0.25, duration) * unit_ms))
            grouped.setdefault(at_ms, []).append((token, duration_ms, source_midi))
        performance = []
        notes = chords = 0
        for at_ms in sorted(grouped):
            seen = set()
            seen_midi = set()
            keys = []
            durations = []
            midi_notes = []
            for token, duration, source_midi in grouped[at_ms]:
                if source_midi not in seen_midi:
                    seen_midi.add(source_midi); midi_notes.append(source_midi)
                durations.append(duration)
                if token in seen: continue
                seen.add(token); keys.append(token)
            if keys:
                notes += len(midi_notes)
                chords += int(len(keys) > 1)
                performance.append({"key": "".join(keys), "at_ms": at_ms, "duration_ms": max(durations), "midi_notes": midi_notes})
        if not performance:
            raise ValueError("Online Sequencer returned no playable piano notes.")
        return performance, {"note_count": notes, "chord_count": chords, "folded_notes": folded}

    def accepts(self, url: str) -> bool:
        try:
            self._sequence_id(url)
            return True
        except ValueError:
            return False

    def _sequence_id(self, url: str) -> int:
        parsed = urlparse(url)
        if parsed.hostname not in self.ALLOWED_HOSTS:
            raise ValueError("Not an Online Sequencer sequence URL.")
        match = re.fullmatch(r"/(\d+)/?", parsed.path)
        if not match:
            raise ValueError("Not an Online Sequencer sequence URL.")
        return int(match.group(1))

    def _tag(self, rows: list[dict]) -> list[dict]:
        return [{**row, "provider": self.id, "provider_name": self.name, "importable": True, "fidelity": "midi"} for row in rows]
