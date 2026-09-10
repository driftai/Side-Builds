from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

try:
    import trafilatura
except Exception:  # optional at import-time for fixture tests
    trafilatura = None


FIELD_ALIASES: dict[str, set[str]] = {
    "title": {"title", "headline", "seriesname", "mangatitle", "animetitle", "articletitle", "posttitle"},
    "description": {"description", "summary", "synopsis", "overview", "plot", "about", "contentdescription"},
    "authors": {"author", "authors", "writer", "writers", "creator", "creators", "storyauthor"},
    "artists": {"artist", "artists", "illustrator", "illustrators", "artby"},
    "genres": {"genre", "genres", "tags", "categories", "themes"},
    "status": {"status", "publicationstatus", "releasestatus", "serialstatus"},
    "chapters": {"chaptercount", "chapters", "numchapters", "numberofchapters"},
    "volumes": {"volumecount", "volumes", "numvolumes", "numberofvolumes"},
    "score": {"score", "rating", "ratingvalue", "averagerating", "userscore"},
    "year": {"year", "releaseyear", "startyear", "publishedyear"},
    "media_type": {"mediatype", "format", "kind"},
    "alternative_titles": {"alternativetitles", "alternativetitle", "alttitles", "aliases", "synonyms", "othernames"},
}

LABEL_ALIASES = {
    "title": {"title", "name"},
    "description": {"description", "summary", "synopsis", "overview", "plot"},
    "authors": {"author", "authors", "writer", "writers", "creator"},
    "artists": {"artist", "artists", "illustrator", "illustrators"},
    "genres": {"genre", "genres", "tags", "themes"},
    "status": {"status", "publication status", "release status"},
    "chapters": {"chapters", "chapter count"},
    "volumes": {"volumes", "volume count"},
    "score": {"score", "rating", "average rating"},
    "year": {"year", "release year", "published"},
    "media_type": {"type", "format", "media type"},
    "alternative_titles": {"alternative titles", "alternative title", "alt titles", "synonyms"},
}

ENTITY_FIELDS = {
    "authors": "Author",
    "artists": "Artist",
}

GENERIC_META = {
    "description": ("description", "og:description", "twitter:description"),
    "authors": ("author", "article:author", "twitter:creator"),
    "score": ("ratingValue",),
}


def _clean(value: Any, limit: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"none", "null", "undefined", "n/a"}:
        return None
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _canon_for_key(key: str) -> str | None:
    normalized = _norm_key(key)
    for canon, aliases in FIELD_ALIASES.items():
        if normalized in aliases:
            return canon
    return None


def _flatten_value(value: Any, *, max_items: int = 12) -> list[str]:
    out: list[str] = []

    def add(item: Any) -> None:
        if len(out) >= max_items:
            return
        if isinstance(item, (str, int, float)) and not isinstance(item, bool):
            cleaned = _clean(item, 500)
            if cleaned and cleaned not in out:
                out.append(cleaned)
        elif isinstance(item, dict):
            for candidate in ("name", "title", "label", "value", "text"):
                if candidate in item:
                    add(item[candidate])
                    if out:
                        return
        elif isinstance(item, list):
            for child in item:
                add(child)

    add(value)
    return out


def _parse_script_payloads(soup: BeautifulSoup) -> list[Any]:
    payloads: list[Any] = []
    decoder = json.JSONDecoder()
    assignment_markers = (
        "__NEXT_DATA__",
        "__NUXT_DATA__",
        "__APOLLO_STATE__",
        "__INITIAL_STATE__",
        "__PRELOADED_STATE__",
        "__INITIAL_DATA__",
    )

    for script in soup.find_all("script"):
        raw = script.string or script.get_text("", strip=False)
        if not raw or len(raw) > 4_000_000:
            continue
        script_type = str(script.get("type", "")).lower()
        script_id = str(script.get("id", ""))
        should_try_direct = "json" in script_type or script_id in assignment_markers
        if should_try_direct:
            try:
                payloads.append(json.loads(raw))
                continue
            except Exception:
                pass

        if not any(marker in raw for marker in assignment_markers):
            continue
        for marker in assignment_markers:
            pos = raw.find(marker)
            if pos < 0:
                continue
            tail = raw[pos + len(marker) :]
            starts = [idx for idx in (tail.find("{"), tail.find("[")) if idx >= 0]
            if not starts:
                continue
            start = min(starts)
            try:
                payload, _ = decoder.raw_decode(tail[start:].lstrip())
                payloads.append(payload)
            except Exception:
                continue
    return payloads


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


def _mine_structured_fields(payloads: Iterable[Any]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    visited = 0

    def walk(value: Any, depth: int = 0) -> None:
        nonlocal visited
        if visited > 9000 or depth > 12:
            return
        visited += 1
        if isinstance(value, dict):
            for key, child in value.items():
                norm_key = _norm_key(str(key))
                canon = _canon_for_key(str(key))
                if canon:
                    for item in _flatten_value(child):
                        if canon == "media_type":
                            if str(item).strip().lower() not in VALID_MEDIA_TYPES:
                                continue
                        if item not in found[canon]:
                            found[canon].append(item)
                if norm_key in SKIP_CONTAINER_KEYS:
                    continue
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:250]:
                walk(child, depth + 1)

    for payload in payloads:
        walk(payload)
    return dict(found)


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = (
            soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
            or soup.find("meta", attrs={"property": re.compile(f"^{re.escape(name)}$", re.I)})
            or soup.find("meta", attrs={"itemprop": re.compile(f"^{re.escape(name)}$", re.I)})
        )
        if tag and tag.get("content"):
            cleaned = _clean(tag.get("content"), 1200)
            if cleaned:
                return cleaned
    return None


def _label_pairs(soup: BeautifulSoup) -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    label_to_canon: dict[str, str] = {}
    for canon, aliases in LABEL_ALIASES.items():
        for label in aliases:
            label_to_canon[_norm_key(label)] = canon

    def add(label: str, value: Any) -> None:
        canon = label_to_canon.get(_norm_key(label.rstrip(":")))
        if not canon:
            return
        items = _flatten_value(value)
        for item in items:
            if len(item) <= 800 and item not in found[canon]:
                found[canon].append(item)

    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            add(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2:
            add(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))

    label_pattern = re.compile(
        r"^(?:title|name|description|summary|synopsis|overview|author|authors|writer|writers|creator|artist|artists|illustrator|genres?|tags?|themes?|status|chapters?|chapter count|volumes?|volume count|score|rating|year|release year|published|type|format|media type|alternative titles?|alt titles|synonyms)\s*:?$",
        re.I,
    )
    for element in soup.find_all(["span", "div", "p", "strong", "b", "h4", "h5"]):
        label = _clean(element.get_text(" ", strip=True), 80)
        if not label or not label_pattern.match(label):
            continue
        sibling = element.find_next_sibling()
        if sibling:
            value = _clean(sibling.get_text(" ", strip=True), 800)
            if value and value.lower() != label.lower():
                add(label, value)
                continue
        parent = element.parent
        if parent:
            full = _clean(parent.get_text(" ", strip=True), 900)
            if full and full.lower() != label.lower() and full.lower().startswith(label.lower().rstrip(":")):
                remainder = full[len(label.rstrip(":")) :].lstrip(" :–—-")
                if remainder:
                    add(label, remainder)
    return dict(found)


def _trafilatura_data(html: str, url: str) -> dict[str, Any]:
    if trafilatura is None:
        return {}
    try:
        raw = trafilatura.extract(
            html,
            url=url,
            output_format="json",
            with_metadata=True,
            include_comments=False,
            include_links=False,
            include_images=False,
            favor_precision=True,
        )
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merge_fields(*field_sets: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = defaultdict(list)
    for field_set in field_sets:
        for key, values in field_set.items():
            for value in values:
                cleaned = _clean(value, 1200)
                if cleaned and cleaned not in merged[key]:
                    merged[key].append(cleaned)
    return dict(merged)


__all__ = [name for name in globals() if not name.startswith("__")]
