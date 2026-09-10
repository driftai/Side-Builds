from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from comic_resource_schema import *
from comic_resource_schema import __all__ as _schema_exports


def _series_item(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in items if _types(item) & COMIC_SCHEMA_TYPES), None)


def _entity_has_comic_series(data: dict[str, Any]) -> bool:
    return any(isinstance(e, dict) and (str(e.get("type") or "") in COMIC_SCHEMA_TYPES or "comicseries" in _norm(e.get("type"))) for e in (data.get("entities") or []))


def _groups(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for x in ((data.get("evidence_archive") or {}).get("grouped_values") or []) if isinstance(x, dict)]


def _group_values(data: dict[str, Any], labels: set[str]) -> list[str]:
    wanted = {_norm(x) for x in labels}
    values: list[str] = []
    for group in _groups(data):
        if _norm(group.get("label")) in wanted:
            values.extend(group.get("values") or [])
    return _uniq(values)


def _visible_text(soup: BeautifulSoup) -> str:
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    return re.sub(r"\s+", " ", root.get_text(" ", strip=True)).strip()


def _path_format(url: str, text: str) -> str | None:
    for segment in [x.casefold() for x in urlparse(url).path.split("/") if x]:
        if segment in COMIC_FORMATS:
            return COMIC_FORMATS[segment]
    low = text.casefold()
    for key, display in COMIC_FORMATS.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            return display
    return None


def _status(text: str, data: dict[str, Any]) -> str | None:
    for candidate in _group_values(data, {"Status", "Meta"}) + [text[:4000]]:
        low = str(candidate).casefold()
        for key, display in STATUS_WORDS.items():
            if re.search(rf"\b{re.escape(key)}\b", low):
                return display
    return None


def _chapter_count(text: str, data: dict[str, Any]) -> int | None:
    for pattern in (r"\b(\d{1,5})\s*(?:ch(?:apter)?s?\.?)\b", r"\bchapters?\s*[:\-]?\s*(\d{1,5})\b"):
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    for group in _groups(data):
        if "chapter" in str(group.get("label") or "").casefold():
            for value in group.get("values") or []:
                match = re.search(r"\d{1,5}", str(value))
                if match:
                    return int(match.group(0))
    return None


def _rank(text: str, data: dict[str, Any]) -> str | None:
    for value in _group_values(data, {"Rank", "Meta"}) + [text[:5000]]:
        match = re.search(r"(?<!\w)#(\d{1,6})\b", str(value))
        if match:
            return f"#{match.group(1)}"
    return None


def _year(*values: Any) -> str | None:
    for value in values:
        text = _clean(value, 160)
        if text:
            match = re.search(r"\b(18|19|20|21)\d{2}\b", text)
            if match:
                return match.group(0)
    return None


def _publisher_from_dom(soup: BeautifulSoup) -> str | None:
    label_node = soup.find(string=re.compile(r"^\s*Publisher\s*$", re.I))
    if not label_node:
        return None
    label_el = getattr(label_node, "parent", None)
    if not label_el:
        return None
    for el in label_el.find_all_next(["a", "span", "div", "p"], limit=12):
        text = _clean(el.get_text(" ", strip=True), 120)
        if text and not re.fullmatch(r"(?:Publisher|Fav icon|Links?|Tags?)", text, re.I):
            return text
    return None


def _description_candidate(data: dict[str, Any], series: dict[str, Any] | None) -> str | None:
    if series:
        candidate = _clean(series.get("description"), 3000)
        if candidate and len(candidate) >= 80:
            return candidate
    current = _clean(data.get("summary"), 3000) or ""
    prefix = current.rstrip("…. ").casefold()[:90]
    blocks = [_clean(x, 3000) for x in ((data.get("evidence_archive") or {}).get("source_text_blocks") or [])]
    blocks = [x for x in blocks if x and 100 <= len(x) <= 2600]
    matching = [x for x in blocks if prefix and x.casefold().startswith(prefix[:55])]
    if matching:
        return max(matching, key=len)
    sentence_like = [x for x in blocks if x.count(".") >= 2 and not re.search(r"\b(?:sign in|sign up|privacy|discord|cookie|navigation)\b", x, re.I)]
    return max(sentence_like, key=len) if sentence_like else None


def _site_names(data: dict[str, Any]) -> list[str]:
    names = []
    for entity in data.get("entities") or []:
        if isinstance(entity, dict) and str(entity.get("type") or "").casefold() in {"publisher/site", "website", "site"}:
            name = _clean(entity.get("name"), 100)
            if name:
                names.append(name)
    return _uniq(names)


def _site_like_author(name: str, data: dict[str, Any]) -> bool:
    cleaned = _clean(name, 120) or ""
    if not cleaned.startswith("@"):
        return False
    n = _norm(cleaned.lstrip("@"))
    for site in _site_names(data):
        s = _norm(site)
        if s and (n.startswith(s) or s.startswith(n.removesuffix("org"))):
            return True
    for entity in data.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        if str(entity.get("type") or "").casefold() != "social/creator":
            continue
        if _norm(entity.get("name")) == _norm(cleaned):
            return True
    return False


def _set_fact(data: dict[str, Any], label: str, value: Any) -> None:
    if value in (None, "", [], {}):
        return
    rendered = ", ".join(str(x) for x in value) if isinstance(value, list) else str(value)
    facts = data.setdefault("key_facts", [])
    for row in facts:
        if isinstance(row, dict) and str(row.get("label") or "").casefold() == label.casefold():
            row["value"] = rendered
            return
    facts.append({"label": label, "value": rendered})


def _remove_fact(data: dict[str, Any], label: str, exact_value: str | None = None) -> None:
    kept = []
    for row in data.get("key_facts") or []:
        if not isinstance(row, dict) or str(row.get("label") or "").casefold() != label.casefold():
            kept.append(row)
        elif exact_value is not None and str(row.get("value") or "") != str(exact_value):
            kept.append(row)
    data["key_facts"] = kept


def _series_signals(data: dict[str, Any], url: str, series: dict[str, Any] | None, text: str) -> tuple[int, list[str]]:
    score, signals = 0, []
    if series:
        score += 10
        signals.append("structured comic-series schema")
    if _entity_has_comic_series(data):
        score += 8
        signals.append("existing ComicSeries entity")
    segments = {x.casefold() for x in urlparse(url).path.split("/") if x}
    if segments & COMIC_PATH_SEGMENTS:
        score += 4
        signals.append("comic/OEL resource path")
    fmt = _path_format(url, text)
    if fmt:
        score += 2
        signals.append(f"comic-family format signal ({fmt})")
    if _chapter_count(text, data) is not None:
        score += 2
        signals.append("chapter-count evidence")
    if _status(text, data):
        score += 1
        signals.append("series-status evidence")
    return score, signals[:8]


def _reconcile_coverage(data: dict[str, Any], soup: BeautifulSoup) -> None:
    coverage = data.get("resource_coverage")
    if not isinstance(coverage, dict) or not (coverage.get("interactive_sections_detected") or []):
        return
    archive = data.get("evidence_archive") or {}
    groups, collections, links = _groups(data), archive.get("structured_collections") or [], archive.get("links") or []
    block_text = " ".join(str(x) for x in (archive.get("source_text_blocks") or [])).casefold()
    group_labels = " ".join(str(x.get("label") or "") for x in groups).casefold()
    collection_paths = " ".join(str(x.get("path") or "") for x in collections if isinstance(x, dict)).casefold()
    meaningful_images = [img for img in soup.find_all("img") if not str(img.get("src") or "").startswith("data:") and not re.search(r"\b(?:icon|avatar|logo)\b", str(img.get("alt") or ""), re.I)]

    def visible(label: str) -> bool:
        stem = re.sub(r"[^a-z0-9]+", "", label.casefold()).rstrip("s")
        if stem in {"image", "artwork", "gallery", "cover"}:
            return bool(meaningful_images) or any(x in collection_paths for x in ("image", "artwork", "cover", "gallery"))
        if stem == "link":
            return len(links) >= 2
        if stem in {"similar", "recommendation", "related"}:
            return any(token in group_labels or token in block_text for token in ("similar", "recommendation", "readers also like", "related"))
        return False

    covered = [str(x) for x in (coverage.get("covered_sections") or [])]
    missing = [str(x) for x in (coverage.get("missing_sections") or [])]
    newly = [label for label in missing if visible(label)]
    if not newly:
        return
    covered = _uniq(covered + newly, 40)
    remaining = [label for label in missing if label not in newly]
    coverage["covered_sections"] = covered
    coverage["missing_sections"] = remaining
    candidate_labels = [str(x.get("label")) for x in coverage.get("interactive_sections_detected") or [] if isinstance(x, dict)]
    covered_keys = {x.casefold() for x in covered}
    coverage["resource_coverage_score"] = round(sum(1 for x in candidate_labels if x.casefold() in covered_keys) / len(candidate_labels), 2) if candidate_labels else 1.0
    coverage["needs_deepening"] = bool(remaining)
    coverage["coverage_reconciled_from_visible_evidence"] = True


def finalize_comic_resource(data: dict[str, Any], acquired: Any) -> dict[str, Any]:
    """Promote strongly evidenced comic/OEL series resources without site-specific rules."""
    if (data.get("provider_enrichment") or {}).get("sufficient"):
        return data
    html = str(getattr(acquired, "text", "") or "")
    content_type = str(getattr(acquired, "content_type", "") or "")
    if not html or (content_type and not any(x in content_type for x in ("html", "xml", "text"))):
        return data

    soup = BeautifulSoup(html, "html.parser")
    series = _series_item(_jsonld_items(soup))
    text = _visible_text(soup)
    url = str(getattr(acquired, "final_url", "") or data.get("input", {}).get("url") or "")
    score, signals = _series_signals(data, url, series, text)
    if score < 8:
        return data

    classification = data.setdefault("classification", {})
    previous_kind = str(classification.get("kind") or "")
    if previous_kind != "anime_manga":
        alternatives = list(classification.get("alternatives") or [])
        if previous_kind:
            alternatives.insert(0, {"kind": previous_kind, "score": "comic-series resource evidence"})
        classification["alternatives"] = alternatives[:4]
    classification.update({"kind": "anime_manga", "category": "Media / Anime & Manga", "confidence": max(float(classification.get("confidence") or 0.0), 0.95)})

    fmt = _path_format(url, text) or "Comic"
    classification["facets"] = {"media_family": "Comics", "format": fmt, "source_material": None}
    classification["signals"] = _uniq(list(classification.get("signals") or []) + signals, 8)

    title = _clean(series.get("name") if series else None, 220)
    h1 = soup.find("h1")
    h1_text = _clean(h1.get_text(" ", strip=True), 220) if h1 else None
    current_title = _clean(data.get("identity", {}).get("title"), 260)
    if not title and h1_text and (not current_title or h1_text.casefold() in current_title.casefold()):
        title = h1_text
    if title:
        data.setdefault("identity", {})["title"] = title

    description = _description_candidate(data, series)
    current_summary = _clean(data.get("summary"), 3000)
    if description and (not current_summary or current_summary.endswith(("…", "...")) or len(description) > len(current_summary) + 80):
        data["summary"] = description

    alternate_titles = _as_list(series.get("alternateName")) if series else []
    genres = _as_list(series.get("genre")) if series else []
    keywords = _as_list(series.get("keywords")) if series else []
    creators = _as_names(series.get("author") or series.get("creator")) if series else []
    publisher_names = _as_names(series.get("publisher")) if series else []
    publisher = publisher_names[0] if publisher_names else _publisher_from_dom(soup)
    start_date = _clean(series.get("datePublished"), 80) if series else None
    last_update = _clean(series.get("dateModified"), 80) if series else None
    status = _status(text, data)
    chapters = _chapter_count(text, data)
    rank = _rank(text, data)
    year = _year(start_date, " ".join(_group_values(data, {"Meta", "Year"})), text[:5000])
    licensed = bool(re.search(r"\bLicensed\b", text, re.I))

    sections = data.setdefault("sections", {})
    sections.pop("editorial", None)
    media, resource = sections.setdefault("anime_manga", {}), sections.setdefault("resource_details", {})
    media.update({"media_type": "Comic", "format": fmt})
    resource.update({"media_type": "Comic", "format": fmt})
    for key, value in {"title": title, "synopsis": data.get("summary"), "status": status, "chapters": chapters, "licensed": "Yes" if licensed else None, "publisher": publisher, "start_date": start_date, "last_update": last_update, "year": year, "rank": rank}.items():
        if value not in (None, "", [], {}):
            media[key] = value
            resource[key] = value
    if alternate_titles:
        media["alternate_titles"] = alternate_titles
        resource["alternate_titles"] = alternate_titles
    if genres:
        media["genres"] = genres
        resource["genres"] = genres
    if keywords:
        media["tags"] = keywords
        resource["tags"] = keywords
    if creators:
        media["authors"] = creators
        resource["authors"] = creators
    else:
        authors = resource.get("authors")
        author_values = authors if isinstance(authors, list) else [authors] if authors else []
        if author_values and all(_site_like_author(str(x), data) for x in author_values):
            resource.pop("authors", None)

    if start_date:
        _set_fact(data, "Start date", start_date)
        _remove_fact(data, "Published", exact_value=start_date)
    if last_update:
        _set_fact(data, "Last update", last_update)
        _remove_fact(data, "Modified", exact_value=last_update)
    for label, value in (("Status", status), ("Chapters", chapters), ("Year", year), ("Licensed", "Yes" if licensed else None), ("Rank", rank), ("Publisher", publisher), ("Genres", genres), ("Alternate titles", alternate_titles)):
        _set_fact(data, label, value)
    if genres:
        _remove_fact(data, "Genre")

    if not creators:
        data["key_facts"] = [row for row in (data.get("key_facts") or []) if not (isinstance(row, dict) and str(row.get("label") or "").casefold() == "author" and _site_like_author(str(row.get("value") or ""), data))]
        data["entities"] = [entity for entity in (data.get("entities") or []) if not (isinstance(entity, dict) and "author" in str(entity.get("type") or "").casefold() and _site_like_author(str(entity.get("name") or ""), data))]

    resource.pop("source_page_date", None)
    tags = [str(x) for x in (data.get("tags") or []) if str(x).casefold() not in TECH_TAGS_TO_DROP and str(x).casefold() != "anime"]
    for tag in ("comic", re.sub(r"[^a-z0-9]+", "-", fmt.casefold()).strip("-")):
        if tag and tag not in {x.casefold() for x in tags}:
            tags.insert(0, tag)
    for value in genres + keywords:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        if 2 <= len(slug) <= 40 and slug not in {x.casefold() for x in tags}:
            tags.append(slug)
    data["tags"] = tags[:35]

    bookmark = data.setdefault("bookmark", {})
    bookmark["suggested_folder"] = "Media / Anime & Manga"
    bookmark["suggested_tags"] = data["tags"]
    display_title = title or current_title or "this series"
    if title:
        bookmark["suggested_title"] = title
    bookmark["why_it_might_matter"] = f"Comic series reference for {display_title} with source details preserved for later organization."

    profile = data.setdefault("resource_profile", {})
    profile.update({"primary_kind": "anime_manga", "media_family": "Comics", "format": fmt, "source_material": profile.get("source_material"), "signals": _uniq(list(profile.get("signals") or []) + signals, 8)})

    quality = data.setdefault("quality", {})
    recovered = set(str(x) for x in (quality.get("structured_fields_recovered") or []))
    for key, value in {"title": title, "description": data.get("summary"), "media_type": "Comic", "format": fmt, "status": status, "chapters": chapters, "licensed": licensed, "publisher": publisher, "start_date": start_date, "last_update": last_update, "year": year, "alternate_titles": alternate_titles, "genres": genres, "tags": keywords, "authors": creators}.items():
        if value not in (None, "", [], {}, False):
            recovered.add(key)
    quality["structured_fields_recovered"] = sorted(recovered)
    present = {"year": bool(year), "genres": bool(genres or resource.get("genres")), "status": bool(status), "description": bool(data.get("summary")), "summary": bool(data.get("summary"))}
    quality["missing_or_uncertain"] = [str(x) for x in (quality.get("missing_or_uncertain") or []) if not present.get(str(x).casefold(), False)]

    _reconcile_coverage(data, soup)
    return data


__all__ = [*_schema_exports, "finalize_comic_resource"]
