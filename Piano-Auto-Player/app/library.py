from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from .performance_notes import clean_performance


class SongLibrary:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"songs": []})

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            return sorted(data.get("songs", []), key=lambda song: song.get("updated_at", 0), reverse=True)

    def get(self, song_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((song for song in self._read().get("songs", []) if str(song.get("id")) == str(song_id)), None)

    def save(self, song: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            songs = data.setdefault("songs", [])
            song_id = str(song.get("id") or f"song-{int(time.time() * 1000)}")
            performance = self._clean_performance(song.get("performance"))
            sheet = str(song.get("sheet") or "")
            kind = "performance" if performance and not sheet.strip() else str(song.get("kind") or "sheet")
            record = {
                "id": song_id,
                "title": str(song.get("title") or "Untitled").strip(),
                "artist": str(song.get("artist") or "").strip(),
                "kind": kind,
                "sheet": sheet,
                "performance": performance,
                "duration_ms": int(song.get("duration_ms") or self._duration(performance)),
                "source": str(song.get("source") or ("recorder" if performance else "manual")),
                "source_url": str(song.get("source_url") or ""),
                "timing_profile": str(song.get("timing_profile") or "expressive"),
                "transcription_diagnostics": song.get("transcription_diagnostics") if isinstance(song.get("transcription_diagnostics"), dict) else {},
                "updated_at": time.time(),
            }
            for index, existing in enumerate(songs):
                if existing.get("id") == song_id:
                    songs[index] = record
                    break
            else:
                songs.append(record)
            self._write(data)
            return record

    def delete(self, song_id: str) -> bool:
        with self._lock:
            data = self._read()
            songs = data.get("songs", [])
            filtered = [song for song in songs if song.get("id") != song_id]
            changed = len(filtered) != len(songs)
            if changed:
                data["songs"] = filtered
                self._write(data)
            return changed

    @staticmethod
    def _clean_performance(raw: Any) -> list[dict[str, Any]]:
        return clean_performance(raw)

    @staticmethod
    def _duration(events: list[dict[str, Any]]) -> int:
        if not events:
            return 0
        return int(max(event["at_ms"] + event["duration_ms"] for event in events))

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"songs": []}

    def _write(self, data: dict[str, Any]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
