from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse


from .media_reference import MediaReferenceResolver


SUPPORTED_MEDIA_HOSTS = {
    "youtube.com": "YouTube",
    "www.youtube.com": "YouTube",
    "music.youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "audio.com": "Audio.com",
    "www.audio.com": "Audio.com",
    "soundcloud.com": "SoundCloud",
    "www.soundcloud.com": "SoundCloud",
    "vimeo.com": "Vimeo",
    "www.vimeo.com": "Vimeo",
    "dailymotion.com": "Dailymotion",
    "www.dailymotion.com": "Dailymotion",
    "archive.org": "Internet Archive",
    "www.archive.org": "Internet Archive",
    "bandcamp.com": "Bandcamp",
}


def is_supported_media_url(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in SUPPORTED_MEDIA_HOSTS or host.endswith(".bandcamp.com")


class AlternateSourceFinder:
    """Searches public web indexes for alternate audio/video copies.

    DDGS lives in the optional transcription venv so the core application keeps
    its zero-dependency startup path. Results are only actionable when the host
    is on the small public-media allowlist above.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.venv = self.root / ".youtube-piano-venv"

    def dependencies(self) -> dict:
        python = self._venv_python()
        return {"ready": bool(python and self._has_ddgs(python)), "ddgs": bool(python and self._has_ddgs(python))}

    def search(self, query: str) -> list[dict]:
        value = re.sub(r"\s+", " ", str(query or "")).strip()[:180]
        if len(value) < 3:
            raise ValueError("Enter a song title for alternate-source search.")
        python = self._venv_python()
        if not python or not self._has_ddgs(python):
            raise ValueError("Alternate-source search is not installed. Run setup-youtube-piano.bat once, then restart start.bat.")
        commands = self._queries(value)
        found: dict[str, dict] = {}
        for search_query in commands:
            completed = subprocess.run(
                [python, "-m", "app.ddgs_helper", search_query],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if completed.returncode:
                continue
            try:
                rows = json.loads(completed.stdout or "[]")
            except json.JSONDecodeError:
                continue
            for row in rows if isinstance(rows, list) else []:
                href = str(row.get("href") or row.get("url") or "").strip()
                if not href or href in found or not is_supported_media_url(href):
                    continue
                host = (urlparse(href).hostname or "").lower()
                title = str(row.get("title") or value).strip()[:180]
                score, confidence = self._score(value, row, host)
                found[href] = {
                    "title": title,
                    "url": href,
                    "snippet": str(row.get("body") or row.get("description") or "").strip()[:260],
                    "host": SUPPORTED_MEDIA_HOSTS.get(host, "Bandcamp" if host.endswith(".bandcamp.com") else host),
                    "score": score,
                    "confidence": confidence,
                }
        return sorted(found.values(), key=lambda row: (-row["score"], row["title"].lower()))[:8]

    @classmethod
    def _score(cls, query: str, row: dict, host: str) -> tuple[float, str]:
        preferred = {"audio.com": 4.0, "www.audio.com": 4.0, "archive.org": 3.0, "www.archive.org": 3.0, "soundcloud.com": 2.5, "www.soundcloud.com": 2.5, "youtube.com": 2.2, "www.youtube.com": 2.2, "music.youtube.com": 2.2, "youtu.be": 2.2}
        title = cls._normalized_title(str(row.get("title") or ""))
        wanted = cls._normalized_title(query)
        haystack = f"{row.get('title', '')} {row.get('body', '')}".lower()
        tokens = [token for token in re.findall(r"[a-z0-9]+", wanted) if len(token) > 2]
        overlap = sum(1 for token in tokens if token in haystack) / max(1, len(tokens)) if tokens else 0.0
        title_overlap = sum(1 for token in tokens if token in title) / max(1, len(tokens)) if tokens else 0.0
        exact = bool(wanted and title and (title == wanted or title.startswith(wanted) or wanted.startswith(title)))
        score = preferred.get(host, 1.0) + overlap * 4.0 + title_overlap * 2.0 + (2.0 if exact else 0.0)
        confidence = "exact" if exact and title_overlap >= 0.75 else "strong" if title_overlap >= 0.85 else "candidate"
        return score, confidence

    @staticmethod
    def _normalized_title(value: str) -> str:
        text = re.sub(r"https?://\S+", " ", str(value or "").lower())
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _queries(cls, value: str) -> list[str]:
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            host = (parsed.hostname or "").lower()
            video_id = ""
            if host == "youtu.be":
                video_id = parsed.path.strip("/").split("/")[0]
            elif host.endswith("youtube.com"):
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            needle = video_id or value
            return [f'"{needle}"', f'"{needle}" audio', f'"{needle}" music']
        cleaned = MediaReferenceResolver.reference_queries(value)
        search_terms = []
        for q in cleaned[:3]:
            search_terms.append(f'"{q}"')
            search_terms.append(f'"{q}" YouTube')
            search_terms.append(f"{q} audio")
            search_terms.append(f"{q} music")
        return search_terms[:8] or [f'"{value}" music', f'"{value}" YouTube', f'"{value}" audio download', f'"{value}" mp3 OR wav']

    def _venv_python(self) -> str:
        candidates = [self.venv / "Scripts" / "python.exe", self.venv / "bin" / "python"]
        return next((str(path) for path in candidates if path.exists()), "")

    @staticmethod
    def _has_ddgs(python: str) -> bool:
        completed = subprocess.run(
            [python, "-m", "app.ddgs_helper", ""], capture_output=True, text=True, timeout=8, check=False
        )
        return completed.returncode == 0
