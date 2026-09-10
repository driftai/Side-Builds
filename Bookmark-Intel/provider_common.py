from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any, Callable
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from acquisition import AcquisitionError, acquire_url, validate_public_url


@dataclass
class ProviderEvidence:
    adapter: str
    matched: bool
    sufficient: bool = False
    fields: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "matched": self.matched,
            "sufficient": self.sufficient,
            "fields": sorted(self.fields),
            "sources": self.sources,
            "errors": self.errors,
        }


def _clean(value: Any, limit: int = 1600) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return None
    text = re.sub(r"\s+", " ", unescape(str(value))).strip()
    if not text or text.lower() in {"null", "none", "undefined", "n/a"}:
        return None
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _slug(value: str) -> str | None:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug if 2 <= len(slug) <= 40 else None


def _norm_name(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", str(value or "")).strip().lower()


def _uniq(values: list[Any], limit: int = 20) -> list[str]:
    out: list[str] = []
    for value in values:
        if isinstance(value, dict):
            for key in ("name", "title", "label", "value"):
                if key in value:
                    value = value[key]
                    break
            else:
                continue
        if isinstance(value, (list, tuple, set)):
            for child in value:
                for item in _uniq([child], limit):
                    if item not in out:
                        out.append(item)
                        if len(out) >= limit:
                            return out
            continue
        cleaned = _clean(value, 500)
        if cleaned and cleaned not in out:
            out.append(cleaned)
            if len(out) >= limit:
                break
    return out


FIELD_ALIASES: dict[str, set[str]] = {
    "title": {"title", "headline", "seriesname", "mangatitle", "animetitle"},
    "english_title": {"englishtitle", "titleenglish"},
    "alternative_titles": {"othernames", "alternativetitles", "alttitles", "aliases", "synonyms"},
    "description": {"description", "summary", "synopsis", "overview", "plot", "about"},
    "authors": {"author", "authors", "writer", "writers", "creator", "creators", "storyauthor"},
    "artists": {"artist", "artists", "illustrator", "illustrators", "artby"},
    "genres": {"genre", "genres", "tags", "categories", "themes"},
    "status": {"status", "publicationstatus", "releasestatus", "serialstatus"},
    "media_type": {"mediatype", "format", "kind"},
    "score": {"score", "rating", "ratingvalue", "averagerating", "userscore"},
    "year": {"year", "releaseyear", "startyear", "publishedyear"},
    "chapters": {"chaptercount", "totalchaptercount", "numchapters", "numberofchapters"},
    "volumes": {"volumecount", "totalvolumecount", "numvolumes", "numberofvolumes"},
    "poster": {"poster", "posterurl", "cover", "coverimage", "image"},
}
_ALIAS_TO_FIELD = {
    re.sub(r"[^a-z0-9]+", "", alias.lower()): field_name
    for field_name, aliases in FIELD_ALIASES.items()
    for alias in aliases
}

SKIP_CONTAINER_KEYS: set[str] = {
    "comments", "commenters", "reviews", "topreviews", "mangacommenters",
    "recommendations", "similarmanga", "relations", "related", "relatedposts",
    "similar", "badges", "roles", "achievements", "user", "currentuser",
    "account", "auth", "session", "navigation", "nav", "menu", "footer",
    "header", "routes", "ads", "analytics", "tracking", "sidebar", "trending",
    "popular", "chapters", "episodes", "scanlators",
}

VALID_MEDIA_TYPES: set[str] = {
    "manga", "manhwa", "manhua", "novel", "light novel", "anime",
    "webtoon", "comic", "book", "movie", "series", "tv", "ova", "ona",
    "special", "music", "game", "software", "article",
}


def _mine_fields(value: Any, *, max_nodes: int = 12000) -> dict[str, Any]:
    buckets: dict[str, list[Any]] = {}
    seen_nodes = 0

    def add(name: str, raw: Any) -> None:
        if isinstance(raw, (dict, list, tuple)):
            if name in {"authors", "artists", "genres", "alternative_titles"}:
                buckets.setdefault(name, []).extend(_uniq(list(raw) if isinstance(raw, (list, tuple)) else [raw]))
            elif isinstance(raw, dict):
                for key in ("url", "src", "image", "smallImage", "mediumImage", "largeImage"):
                    if key in raw:
                        cleaned = _clean(raw[key], 1000)
                        if cleaned:
                            buckets.setdefault(name, []).append(cleaned)
                            break
            return
        cleaned = _clean(raw)
        if cleaned:
            buckets.setdefault(name, []).append(cleaned)

    def walk(node: Any, depth: int = 0) -> None:
        nonlocal seen_nodes
        if depth > 14 or seen_nodes >= max_nodes:
            return
        seen_nodes += 1
        if isinstance(node, dict):
            for key, child in node.items():
                normalized = re.sub(r"[^a-z0-9]+", "", str(key).lower())
                field_name = _ALIAS_TO_FIELD.get(normalized)
                if field_name:
                    if field_name == "media_type":
                        clean_media = str(child).strip().lower()
                        if clean_media not in VALID_MEDIA_TYPES:
                            continue
                    add(field_name, child)
                if normalized in SKIP_CONTAINER_KEYS:
                    continue
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node[:400]:
                walk(child, depth + 1)

    walk(value)

    out: dict[str, Any] = {}
    for name, values in buckets.items():
        unique = _uniq(values, 20)
        if not unique:
            continue
        if name in {"authors", "artists", "genres", "alternative_titles"}:
            out[name] = unique
        else:
            out[name] = unique[0]
    return out


def _json_endpoint(url: str) -> Any:
    validate_public_url(url)
    acquired = acquire_url(url, allow_browsers=False)
    if acquired.status_code >= 400:
        raise AcquisitionError(f"Provider endpoint returned HTTP {acquired.status_code}.")
    if len(acquired.text) > 3_000_000:
        raise AcquisitionError("Provider JSON response exceeded the acquisition limit.")
    try:
        return json.loads(acquired.text)
    except json.JSONDecodeError as exc:
        raise AcquisitionError("Provider endpoint did not return valid JSON.") from exc


__all__ = [name for name in globals() if not name.startswith("__")]
