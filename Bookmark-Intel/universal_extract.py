from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

MAX_GENERIC_FACTS = 180
MAX_TEXT_BLOCKS = 120
SKIP_TEXT_PARENTS = {"script", "style", "noscript", "svg", "canvas", "template", "form"}
GENERIC_NAV_PARENTS = {"nav", "header", "footer", "aside"}
MEDIA_SCHEMA_TYPES = {"Movie", "TVSeries", "TVEpisode", "TVSeason", "VideoObject"}
MEDIA_PATH_PATTERNS = (
    (re.compile(r"/(?:watchseries|tv-shows?|shows?|series)(?:/|$)", re.I), "TV Series", 6),
    (re.compile(r"/(?:watchmovie|movies?|films?)(?:/|$)", re.I), "Movie", 6),
)
MEDIA_FACT_ALIASES = {
    "year": {"year started", "release year", "year", "released", "premiere year", "premiered"},
    "status": {"show status", "series status", "status"},
    "certificate": {"certificate", "content rating", "age rating", "rated"},
    "country": {"country", "country of origin", "origin"},
    "language": {"language", "original language"},
    "genres": {"genre", "genres"}, "keywords": {"keyword", "keywords"},
    "runtime": {"runtime", "duration"}, "network": {"network", "networks", "channel"},
    "studio": {"studio", "studios", "production company", "production companies"},
    "director": {"director", "directors"},
}


def _clean(value: Any, limit: int = 1800) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"none", "null", "undefined", "n/a"}:
        return None
    return text[: limit - 1].rstrip() + "…" if limit and len(text) > limit else text


def _uniq(values: list[Any], limit: int = 120) -> list[str]:
    out: list[str] = []
    seen: dict[str, int] = {}
    for value in values:
        cleaned = _clean(value, 1200)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            idx = seen[key]
            if not any(c.isupper() for c in out[idx]) and any(c.isupper() for c in cleaned):
                out[idx] = cleaned
            continue
        seen[key] = len(out)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _norm_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().rstrip(":")).casefold()


def _valid_generic_label(label: str) -> bool:
    label = label.strip().rstrip(":")
    if not (1 <= len(label) <= 72) or label.count(" ") > 10:
        return False
    if "://" in label or "/" in label and len(label.split("/")) > 4:
        return False
    if sum(ch.isalnum() for ch in label) < 2 or re.search(r"[.!?]{2,}", label):
        return False
    return True


def _add_fact(out: list[dict[str, str]], seen: set[tuple[str, str]], label: Any, value: Any, source: str) -> None:
    clean_label = _clean(label, 120)
    clean_value = _clean(value, 1400)
    if not clean_label or not clean_value:
        return
    clean_label = clean_label.rstrip(":").strip()
    if not _valid_generic_label(clean_label) or clean_label.casefold() == clean_value.casefold():
        return
    key = (clean_label.casefold(), clean_value.casefold())
    if key in seen:
        return
    seen.add(key)
    out.append({"label": clean_label, "value": clean_value, "source": source})


def _collect_element_siblings(element: Any) -> str | None:
    parts: list[str] = []
    for sib in element.next_siblings:
        name = getattr(sib, "name", None)
        if name in {"br", "hr", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}:
            if not parts and hasattr(sib, "get_text"):
                t = sib.get_text(" ", strip=True)
                if t and not t.endswith(":"):
                    return _clean(t, 1400)
            break
        text = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
        if not text:
            continue
        if name in {"b", "strong", "dt", "th"} and text.endswith(":"):
            break
        parts.append(text)
        if len(" ".join(parts)) > 1400:
            break
    if parts:
        return _clean(" ".join(parts), 1400)
    sibling = element.find_next_sibling()
    return _clean(sibling.get_text(" ", strip=True), 1400) if sibling else None


def _generic_labeled_facts(soup: BeautifulSoup) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            _add_fact(out, seen, dt.get_text(" ", strip=True), dd.get_text(" ", strip=True), "definition_list")
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2:
            _add_fact(out, seen, cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True), "table")
    colon_re = re.compile(r"^\s*([^:\n]{1,72})\s*:\s*(.{1,1400})\s*$", re.S)
    for element in soup.find_all(["span", "p", "li", "div", "strong", "b", "small"]):
        if element.find_parent(SKIP_TEXT_PARENTS):
            continue
        if element.name in {"span", "p", "div", "li", "section"} and any(c.name in {"b", "strong", "dt", "th"} and c.get_text(" ", strip=True).endswith(":") for c in element.find_all(["b", "strong", "dt", "th"])):
            continue
        text = _clean(element.get_text(" ", strip=True), 1600)
        if not text or len(text) > 1500:
            continue
        match = colon_re.match(text)
        if match:
            _add_fact(out, seen, match.group(1), match.group(2), "inline_colon")
        if text.endswith(":") and len(text) <= 80:
            val = _collect_element_siblings(element)
            if val:
                _add_fact(out, seen, text, val, "label_sibling")
        if len(out) >= MAX_GENERIC_FACTS:
            break
    if len(out) < MAX_GENERIC_FACTS:
        for line in soup.get_text("\n", strip=True).splitlines():
            line = _clean(line, 1500)
            if not line:
                continue
            match = colon_re.match(line)
            if match:
                _add_fact(out, seen, match.group(1), match.group(2), "visible_text")
            if len(out) >= MAX_GENERIC_FACTS:
                break
    return out[:MAX_GENERIC_FACTS]


def _visible_text_blocks(soup: BeautifulSoup) -> list[str]:
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    out: list[str] = []
    seen: set[str] = set()
    for element in root.find_all(["h1", "h2", "h3", "h4", "p", "blockquote", "li", "div", "section"]):
        if element.find_parent(SKIP_TEXT_PARENTS | GENERIC_NAV_PARENTS):
            continue
        if element.name in {"div", "section"} and element.find_all(["p", "blockquote", "li", "div", "section", "h1", "h2", "h3", "h4"], recursive=False):
            continue
        text = _clean(element.get_text(" ", strip=True), 1200)
        if not text:
            continue
        if len(text) < 18 and element.name not in {"h1", "h2", "h3", "h4"} and not re.search(r"\b(?:Season\s+\d+|[\d,]+\s+Votes?|[\d,]+\s+comments?)\b", text, re.I):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= MAX_TEXT_BLOCKS:
            break
    return out


def _jsonld_types(soup: BeautifulSoup) -> set[str]:
    out: set[str] = set()
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            raw = value.get("@type")
            if isinstance(raw, str): out.add(raw)
            elif isinstance(raw, list): out.update(str(x) for x in raw if isinstance(x, str))
            graph = value.get("@graph")
            if isinstance(graph, list):
                for child in graph: walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=False)
        if not raw:
            continue
        try: walk(json.loads(raw))
        except Exception: continue
    return out


def _fact_map(facts: list[dict[str, str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for fact in facts:
        label = _norm_label(fact.get("label", ""))
        value = _clean(fact.get("value"), 1400)
        if label and value and value not in out[label]: out[label].append(value)
    return dict(out)


def _lookup_fact(mapping: dict[str, list[str]], aliases: set[str]) -> str | None:
    for alias in aliases:
        values = mapping.get(alias.casefold())
        if values: return values[0]
    return None


def _split_multi(value: Any, limit: int = 40) -> list[str]:
    cleaned = _clean(value, 1600)
    if not cleaned: return []
    parts = [part.strip().lstrip("#").strip() for part in re.split(r"\s*[|;,]\s*", cleaned) if part.strip()]
    return _uniq(parts, limit)


__all__ = [name for name in globals() if not name.startswith("__")]
