from __future__ import annotations

import json
import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


_SPOTIFY_HOSTS = {"open.spotify.com", "www.open.spotify.com", "spotify.link", "www.spotify.link"}
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "music.youtube.com", "youtu.be"}
_USER_AGENT = "Mozilla/5.0 PianoAutoPlayer/0.5.6 (+localhost media resolver)"


_NOISE_TOKENS = (
    "official music video", "official video", "official audio", "music video",
    "lyric video", "lyrics video", "lyrics", "full audio", "audio track", "visualizer",
    "best part", "edit version", "edit", "tiktok version", "tik tok version",
    "sped up", "slowed down", "slowed reverb", "slowed + reverb", "slowed", "reverb",
    "extended version", "extended", "1 hour", "1 hour loop", "loop",
    "original soundtrack", "soundtrack", "original song", "ost", "bgm",
    "theme song", "main theme", "opening theme", "ending theme", "opening", "ending",
    "remastered", "remaster", "4k", "hd", "hq",
    "piano cover", "piano tutorial", "piano version", "synthesia", "synthesia tutorial",
)
_NOISE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(tok) for tok in sorted(_NOISE_TOKENS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _clean_noise_text(text: str) -> str:
    cleaned = _NOISE_RE.sub(" ", str(text or ""))
    cleaned = re.sub(r"\b(?:op|ed)\s*\d*\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"[\(\[\{]\s*[\)\]\}]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -:|/•_~,\"'")


def media_kind(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower()
    if host in _SPOTIFY_HOSTS:
        return "spotify"
    if host in _YOUTUBE_HOSTS:
        return "youtube"
    return "public"


def is_spotify_url(url: str) -> bool:
    return media_kind(url) == "spotify"


class MediaReferenceResolver:
    """Resolve public media links to search metadata without ingesting audio.

    Spotify is metadata-only by design: its public oEmbed endpoint supplies a
    track/entity title that can drive sheet/MIDI lookup or alternate-source
    discovery. YouTube oEmbed is used as a lightweight title fallback when
    yt-dlp itself is blocked by an anti-bot challenge.
    """

    def resolve(self, url: str) -> dict:
        value = str(url or "").strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Paste a valid media URL.")
        kind = media_kind(value)
        if kind == "spotify":
            data = self._fetch_json(f"https://open.spotify.com/oembed?url={quote(value, safe='')}")
            title = self._clean_title(data.get("title"))
            return {
                "kind": kind,
                "title": title,
                "artist": "",
                "query": title,
                "provider": "Spotify",
                "direct_audio": False,
                "url": value,
            }
        if kind == "youtube":
            data = self._fetch_json(f"https://www.youtube.com/oembed?url={quote(value, safe='')}&format=json")
            title = self._clean_title(data.get("title"))
            artist = self._clean_title(data.get("author_name"))
            return {
                "kind": kind,
                "title": title,
                "artist": artist,
                "query": self._query(title, artist),
                "provider": "YouTube",
                "direct_audio": True,
                "url": value,
            }
        return {
            "kind": kind,
            "title": "",
            "artist": "",
            "query": "",
            "provider": parsed.hostname or "Public media",
            "direct_audio": True,
            "url": value,
        }

    @classmethod
    def reference_queries(cls, title: str, artist: str = "") -> list[str]:
        raw = str(title or "").strip()
        if not raw:
            return [artist] if artist else []

        queries: list[str] = []
        seen: set[str] = set()

        def push(q: str) -> None:
            val = re.sub(r"\s+", " ", str(q or "")).strip(" -:|/•_~,\"'")
            val_norm = cls._normalized(val)
            if val and len(val) >= 2 and val_norm and val_norm not in seen:
                seen.add(val_norm)
                queries.append(val)

        # 1. Raw title cleaned of extra spaces
        push(raw)

        # 2. Extract content inside brackets/parens if it looks like a subtitle/alternate title
        for m in re.finditer(r"[\(\[\{]([^\)\]\}]+)[\)\]\}]", raw):
            inside = _clean_noise_text(m.group(1))
            if inside and len(inside.split()) <= 6:
                push(inside)

        # 3. Strip all brackets/parens
        without_brackets = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", raw)
        push(without_brackets)

        # 4. Clean noise phrases from full raw and without_brackets
        push(_clean_noise_text(raw))
        push(_clean_noise_text(without_brackets))

        # 5. Handle separator splits (e.g. Artist - Song, Song - Anime OST, Song | Artist)
        for sep in [" - ", " – ", " — ", " | ", " // ", " : ", " / "]:
            if sep in raw:
                for part in raw.split(sep):
                    push(part)
                    push(_clean_noise_text(part))
                    without_p_brackets = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", part)
                    push(_clean_noise_text(without_p_brackets))

        # 6. Suffix / metadata stripping (e.g. 'In The Pool Chainsawman' -> 'In The Pool')
        for q in list(queries):
            words = q.split()
            if len(words) >= 3:
                for cut in range(2, len(words)):
                    prefix_candidate = " ".join(words[:cut])
                    push(prefix_candidate)

        # 7. Artist combination
        if artist:
            cleaned_artist = _clean_noise_text(artist)
            if cleaned_artist:
                push(f"{_clean_noise_text(without_brackets)} {cleaned_artist}")
                push(cleaned_artist)

        return queries

    @staticmethod
    def reference_confidence(query: str, row: dict, score: int = 0, candidate_queries: list[str] | None = None) -> tuple[str, int]:
        title = str(row.get("title") or "")
        artist = str(row.get("artist") or "")
        title_norm = MediaReferenceResolver._normalized(title)
        combo_norm = MediaReferenceResolver._normalized(f"{title} {artist}")
        title_tokens = [token for token in title_norm.split() if len(token) > 1]
        
        queries = candidate_queries or MediaReferenceResolver.reference_queries(query)
        best_confidence = "candidate"
        best_score = score

        for q in queries:
            q_norm = MediaReferenceResolver._normalized(q)
            q_tokens = [token for token in q_norm.split() if len(token) > 1]
            if not q_tokens or not title_tokens:
                continue

            token_ratio = sum(token in combo_norm.split() for token in q_tokens) / max(1, len(q_tokens))
            rev_token_ratio = sum(token in q_norm.split() for token in title_tokens) / max(1, len(title_tokens))
            exact_title = bool(q_norm and title_norm == q_norm)
            title_prefix = bool(q_norm and (title_norm.startswith(q_norm) or q_norm.startswith(title_norm)))
            compact_match = (token_ratio >= 0.85 or rev_token_ratio >= 0.85) and len(title_tokens) <= max(5, len(q_tokens) + 6)

            if exact_title or (title_prefix and (token_ratio >= 0.85 or rev_token_ratio >= 0.85)):
                best_confidence = "exact"
                best_score = max(best_score, score)
                break
            if compact_match and score >= 800:
                if best_confidence != "exact":
                    best_confidence = "strong"
                    best_score = max(best_score, score)

        return best_confidence, best_score

    @staticmethod
    def acceptable_reference(confidence: str, score: int, row: dict) -> bool:
        if row.get("importable") is False:
            return False
        if confidence == "exact":
            return True
        fidelity = str(row.get("fidelity") or "").lower()
        return confidence == "strong" and score >= (1100 if fidelity == "midi" else 1450)

    @staticmethod
    def _normalized(value: str) -> str:
        text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _query(title: str, artist: str) -> str:
        if not title:
            return artist
        # Title-only searches are less brittle against uploader/channel names.
        # Keep artist separately for UI and ranking instead of forcing it into
        # every provider's query string.
        return title

    @staticmethod
    def _clean_title(value) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()[:180]

    @staticmethod
    def _fetch_json(url: str) -> dict:
        request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise ValueError(f"Could not resolve media metadata: {exc}") from exc
