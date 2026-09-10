from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

MAX_GROUPS = 120
MAX_GROUP_VALUES = 80
MAX_STRUCTURED_COLLECTIONS = 100
MAX_STRUCTURED_SAMPLE_ITEMS = 16
MAX_INTERACTIVE_SECTIONS = 6
MAX_INTERACTIVE_BLOCKS = 160
MAX_INTERACTIVE_LINKS = 100

SCRIPT_STATE_MARKERS = {
    "__NEXT_DATA__", "__NUXT_DATA__", "__NUXT__", "__APOLLO_STATE__",
    "__INITIAL_STATE__", "__PRELOADED_STATE__", "__INITIAL_DATA__", "__SSR_DATA__",
    "__SSR_CONFIG__", "__STATE__", "__DATA__", "__PAGE_DATA__", "__APP_DATA__",
}

NOISE_JSON_KEYS = {
    "webpack", "chunks", "chunk", "manifest", "buildmanifest", "reactloadablemanifest",
    "css", "styles", "scripts", "assets", "analytics", "tracking", "translations",
    "i18n", "locales", "icons", "routes", "navigation", "nav", "footer", "header",
    "session", "auth", "currentuser", "featureflags", "experiments",
}

SAFE_SECTION_RE = re.compile(
    r"\b(?:overview|details?|characters?|cast|crew|artworks?|gallery|images?|episodes?|"
    r"chapters?|seasons?|reviews?|comments?|specifications?|specs?|features?|"
    r"ingredients?|nutrition|menu|schedule|history|versions?|releases?|files?|"
    r"downloads?|related|recommendations?|similar|faq|sources?|links?)\b",
    re.I,
)
UNSAFE_CONTROL_RE = re.compile(
    r"\b(?:login|log in|sign in|register|sign up|buy|checkout|pay|subscribe|"
    r"delete|remove|submit|send|post|upload|download|install|watch now|play|"
    r"logout|log out|report|block|follow|unfollow|like|share|profile|close|toggle|open|dismiss)\b",
    re.I,
)
LABEL_CLASS_RE = re.compile(r"\b(?:label|field|term|key|heading|header|title|caption|name)\b", re.I)

FIELD_ALIASES: dict[str, set[str]] = {
    "format": {"format", "media type", "type"},
    "status": {"status", "show status", "series status", "release status"},
    "episodes": {"episodes", "episode count", "number of episodes", "total episodes", "numberofepisodes"},
    "season": {"season", "release season", "seasonyear"},
    "start_date": {"start date", "start_date", "startdate", "premiere date", "aired from", "release date", "datepublished", "published"},
    "end_date": {"end date", "end_date", "enddate", "aired to", "finale date"},
    "country": {"country", "country of origin", "countryoforigin", "origin"},
    "adult": {"adult", "is adult", "isadult", "adult content", "nsfw"},
    "romaji": {"romaji", "romanized", "romanized title", "romaji title", "title romaji"},
    "native_title": {"native", "native title", "original title", "title native", "alternatename", "alternate name"},
    "last_update": {"last update", "updated", "last updated", "updatedat", "datemodified"},
    "studios": {"studio", "studios", "production company", "production companies", "productioncompany"},
    "genres": {"genre", "genres"},
    "tags": {"tag", "tags", "themes", "keywords"},
    "source_material": {"source", "source material", "based on", "adapted from"},
    "score": {"score", "rating", "user score", "averagescore", "meanscore"},
    "year": {"year", "release year", "year started"},
    "runtime": {"runtime", "duration"},
    "language": {"language", "original language", "inlanguage"},
    "certificate": {"certificate", "content rating", "age rating", "rated"},
}


def _clean(value: Any, limit: int = 1800) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.casefold() in {"none", "null", "undefined", "n/a"}:
        return None
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _uniq(values: list[Any], limit: int = 120) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value, 900)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _clean_container_concatenations(values: list[str]) -> list[str]:
    atomic_terms = {v.casefold() for v in values if " " not in v or re.search(r"^[A-Z][a-z]+(?: [A-Z][a-z]+)?$", v)}
    cleaned: list[str] = []
    for val in values:
        words = val.split()
        if len(words) > 1 and all(w.casefold() in atomic_terms for w in words):
            continue
        cleaned.append(val)
    return cleaned


def _flatten_entity_name(value: Any) -> str | None:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return _clean(value, 300)
    if isinstance(value, dict):
        for key in ("full", "userPreferred", "romaji", "name", "title", "english", "native", "label"):
            child = value.get(key)
            if isinstance(child, (str, int, float)) and not isinstance(child, bool):
                cleaned = _clean(child, 300)
                if cleaned:
                    return cleaned
    return None


def _format_date_obj(value: Any) -> str | None:
    if isinstance(value, dict) and value.get("year"):
        return f"{value['year']}-{int(value.get('month') or 1):02d}-{int(value.get('day') or 1):02d}"
    if isinstance(value, (int, float)) and value > 100_000_000:
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return None
    return _clean(value, 60)


def _is_labelish(element: Any) -> bool:
    if not getattr(element, "name", None):
        return False
    text = _clean(element.get_text(" ", strip=True), 100)
    if not text or len(text) > 72 or len(text.split()) > 10:
        return False
    if element.name in {"dt", "th", "legend", "h1", "h2", "h3", "h4", "h5", "h6", "b", "strong"}:
        return True
    classes = " ".join(str(x) for x in (element.get("class") or []))
    marker = " ".join([classes, str(element.get("id") or ""), str(element.get("name") or "")])
    return bool(LABEL_CLASS_RE.search(marker))


def _leaf_values(container: Any, *, limit: int = MAX_GROUP_VALUES) -> list[str]:
    values: list[str] = []
    if container is None:
        return values
    for tag_name in ["a", "li", "dd", "span", "p", "small"]:
        for element in container.find_all(tag_name):
            if element.find(["a", "li", "dd", "span", "p", "div"], recursive=False):
                continue
            text = _clean(element.get_text(" ", strip=True), 500)
            if text and len(text) <= 500:
                values.append(text)
                if len(values) >= limit:
                    return _uniq(values, limit)
    if not values:
        text = _clean(container.get_text(" | ", strip=True), 1400)
        if text:
            pieces = [piece.strip() for piece in re.split(r"\s*[|•·]\s*", text) if piece.strip()]
            values.extend(pieces if len(pieces) > 1 else [text])
    return _uniq(values, limit)


def _following_group_values(label_el: Any) -> list[str]:
    if label_el.name == "dt":
        values: list[str] = []
        sibling = label_el.find_next_sibling()
        while sibling is not None:
            if getattr(sibling, "name", None) == "dt":
                break
            if getattr(sibling, "name", None) == "dd":
                values.extend(_leaf_values(sibling))
            sibling = getattr(sibling, "find_next_sibling", lambda: None)()
        return _uniq(values, MAX_GROUP_VALUES)
    if label_el.name == "th":
        row = label_el.find_parent("tr")
        if row:
            cells = row.find_all(["th", "td"], recursive=False)
            try:
                idx = cells.index(label_el)
            except ValueError:
                idx = 0
            values: list[str] = []
            for cell in cells[idx + 1:]:
                values.extend(_leaf_values(cell))
            return _uniq(values, MAX_GROUP_VALUES)
    values: list[str] = []
    parent = label_el.parent
    if parent:
        direct = [x for x in parent.children if getattr(x, "name", None)]
        if label_el in direct:
            for sibling in direct[direct.index(label_el) + 1:]:
                if _is_labelish(sibling):
                    break
                if sibling.name in {"br", "hr"}:
                    continue
                vals = _leaf_values(sibling)
                if vals:
                    values.extend(vals)
                else:
                    text = _clean(sibling.get_text(" ", strip=True), 500)
                    if text:
                        values.append(text)
                if len(values) >= MAX_GROUP_VALUES:
                    break
    if values:
        return _uniq(values, MAX_GROUP_VALUES)
    sibling = label_el.find_next_sibling()
    if sibling is not None and not _is_labelish(sibling):
        return _leaf_values(sibling)
    return []


__all__ = [name for name in globals() if not name.startswith("__")]
