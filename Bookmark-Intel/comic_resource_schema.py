from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

COMIC_SCHEMA_TYPES = {"ComicSeries", "ComicStory", "ComicIssue", "ComicCoverArt", "GraphicNovel"}
COMIC_PATH_SEGMENTS = {"manga", "manhwa", "manhua", "webtoon", "oel", "comic", "comics"}
COMIC_FORMATS = {"oel": "OEL", "manga": "Manga", "manhwa": "Manhwa", "manhua": "Manhua", "webtoon": "Webtoon", "comic": "Comic", "comics": "Comic"}
STATUS_WORDS = {"releasing": "Releasing", "ongoing": "Ongoing", "completed": "Completed", "complete": "Completed", "finished": "Finished", "hiatus": "Hiatus", "cancelled": "Cancelled", "canceled": "Cancelled"}
TECH_TAGS_TO_DROP = {"article", "programming", "python", "javascript", "rust", "go", "database", "devops", "documentation", "open-source"}


def _clean(value: Any, limit: int = 1800) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text[: limit - 1].rstrip() + "…" if limit and len(text) > limit else text


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _uniq(values: list[Any], limit: int = 80) -> list[str]:
    out, seen = [], set()
    for value in values:
        cleaned = _clean(value, 600)
        if not cleaned or cleaned.casefold() in seen:
            continue
        seen.add(cleaned.casefold())
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _jsonld_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            found.append(value)
            if isinstance(value.get("@graph"), list):
                for child in value["@graph"]:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=False)
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except Exception:
            continue
    return found


def _types(item: dict[str, Any]) -> set[str]:
    raw = item.get("@type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {str(x) for x in raw if isinstance(x, str)}
    return set()


def _as_names(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    names = []
    for item in values:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            candidate = item.get("name") or item.get("headline") or item.get("title")
            if isinstance(candidate, str):
                names.append(candidate)
    return _uniq(names)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return _uniq([x for x in value if not isinstance(x, (dict, list))])
    if isinstance(value, str):
        parts = [x.strip() for x in re.split(r"[,;|]", value) if x.strip()]
        return _uniq(parts or [value])
    return []


__all__ = [
    "COMIC_SCHEMA_TYPES",
    "COMIC_PATH_SEGMENTS",
    "COMIC_FORMATS",
    "STATUS_WORDS",
    "TECH_TAGS_TO_DROP",
    "_clean",
    "_norm",
    "_uniq",
    "_jsonld_items",
    "_types",
    "_as_names",
    "_as_list",
]
