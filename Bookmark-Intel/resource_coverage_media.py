from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from resource_coverage_structured import *


def _fact_map(data: dict[str, Any], groups: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    archive = data.get("evidence_archive") or {}
    for row in archive.get("labeled_facts") or []:
        if not isinstance(row, dict):
            continue
        label = _norm(row.get("label"))
        value = _clean(row.get("value"), 1400)
        if label and value and value not in mapping[label]:
            mapping[label].append(value)
    for group in groups:
        label = _norm(group.get("label"))
        for value in group.get("values") or []:
            cleaned = _clean(value, 900)
            if label and cleaned and cleaned not in mapping[label]:
                mapping[label].append(cleaned)
    return dict(mapping)


def _values_for(mapping: dict[str, list[str]], field: str) -> list[str]:
    values: list[str] = []
    for alias in FIELD_ALIASES.get(field, {field}):
        for value in mapping.get(_norm(alias), []):
            if value not in values:
                values.append(value)
    return values


def _split_values(values: list[str], *, limit: int = 80) -> list[str]:
    out: list[str] = []
    for value in values:
        pieces = [piece.strip().lstrip("#").strip() for piece in re.split(r"\s*[|;,]\s*", value) if piece.strip()]
        out.extend(pieces if len(pieces) > 1 else [value])
    return _clean_container_concatenations(_uniq(out, limit))


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


def _extract_year(*values: Any) -> str | None:
    for value in values:
        text = _clean(value, 120)
        if not text:
            continue
        match = re.search(r"\b(18|19|20|21)\d{2}\b", text)
        if match:
            return match.group(0)
    return None


def _canonical_date(value: Any) -> str | None:
    text = _clean(value, 120)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"\b(18|19|20|21)\d{2}-\d{2}-\d{2}\b", text)
    return match.group(0) if match else None


def _set_key_fact(data: dict[str, Any], label: str, value: Any) -> None:
    if value in (None, "", [], {}):
        return
    rendered = ", ".join(str(x) for x in value) if isinstance(value, list) else str(value)
    facts = data.setdefault("key_facts", [])
    for row in facts:
        if isinstance(row, dict) and str(row.get("label") or "").casefold() == label.casefold():
            row["value"] = rendered
            return
    facts.append({"label": label, "value": rendered})


def _remove_key_fact(data: dict[str, Any], label: str, *, exact_value: str | None = None) -> None:
    kept = []
    target_date = _canonical_date(exact_value) if exact_value is not None else None
    for row in data.get("key_facts") or []:
        if not isinstance(row, dict):
            kept.append(row)
            continue
        if str(row.get("label") or "").casefold() != label.casefold():
            kept.append(row)
            continue
        if exact_value is not None:
            row_value = str(row.get("value") or "")
            same = row_value == exact_value
            if not same and target_date:
                same = _canonical_date(row_value) == target_date
            if not same:
                kept.append(row)
    data["key_facts"] = kept


def _resource_text(soup: BeautifulSoup) -> str:
    pieces: list[str] = []
    if soup.title:
        pieces.append(soup.title.get_text(" ", strip=True))
    for element in soup.find_all(["h1", "h2", "h3", "h4"], limit=30):
        pieces.append(element.get_text(" ", strip=True))
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    pieces.append(root.get_text(" ", strip=True)[:12000])
    return "\n".join(pieces)


def _infer_media_facets(data: dict[str, Any], soup: BeautifulSoup, mapping: dict[str, list[str]]) -> dict[str, Any]:
    current_kind = str(data.get("classification", {}).get("kind") or "")
    text = _resource_text(soup)
    low = text.casefold()
    href_text = " ".join(str(a.get("href") or "") for a in soup.find_all("a", href=True)[:250]).casefold()
    tags = {str(x).casefold() for x in (data.get("tags") or [])}
    fmt = _first(_values_for(mapping, "format"))
    source_material = _first(_values_for(mapping, "source_material"))
    episodes = _first(_values_for(mapping, "episodes"))
    status = _first(_values_for(mapping, "status"))
    start_date = _first(_values_for(mapping, "start_date"))
    existing_media = None
    for section_name in ("anime_manga", "film_tv", "resource_details"):
        section = data.get("sections", {}).get(section_name) or {}
        if isinstance(section, dict) and section.get("media_type"):
            existing_media = _clean(section.get("media_type"), 80)
            if existing_media:
                break
    manga_types = {"manga", "manhwa", "manhua", "webtoon", "comic"}
    if existing_media and existing_media.casefold() in manga_types:
        return {"media_family": existing_media, "format": fmt or existing_media, "source_material": source_material, "signals": ["existing manga-family media type"]}
    anime_score = 0
    signals: list[str] = []
    if current_kind == "anime_manga":
        anime_score += 5
        signals.append("existing anime/manga classification")
    if "anime" in tags:
        anime_score += 4
        signals.append("anime tag")
    if re.search(r"\banime\s+(?:details?|episodes?|information|info)\b", low):
        anime_score += 5
        signals.append("anime resource heading")
    if "type=anime" in href_text or "type%3danime" in href_text:
        anime_score += 3
        signals.append("anime-filter resource links")
    if source_material and source_material.casefold() in {"manga", "light novel", "novel", "visual novel", "game", "original"}:
        anime_score += 2
        signals.append("adaptation source material")
    if fmt and fmt.casefold() in {"tv", "tv series", "ova", "ona", "special", "movie", "music"}:
        anime_score += 1
        signals.append("anime-compatible format")
    resource_level = bool(episodes or (fmt and status) or (start_date and status) or re.search(r"\bepisodes?\b", low))
    if anime_score >= 6 and resource_level:
        return {"media_family": "Anime", "format": fmt or existing_media, "source_material": source_material, "signals": signals[:8]}
    if current_kind == "film_tv":
        return {"media_family": "Film & TV", "format": fmt or existing_media, "source_material": source_material, "signals": ["existing film/tv classification"]}
    return {"media_family": None, "format": fmt or existing_media, "source_material": source_material, "signals": signals[:8]}


def _promote_anime(data: dict[str, Any], mapping: dict[str, list[str]], facets: dict[str, Any]) -> None:
    classification = data.setdefault("classification", {})
    previous_kind = str(classification.get("kind") or "")
    if previous_kind != "anime_manga":
        alternatives = list(classification.get("alternatives") or [])
        if previous_kind:
            alternatives.insert(0, {"kind": previous_kind, "score": "hierarchical media facet"})
        classification["alternatives"] = alternatives[:4]
    classification["kind"] = "anime_manga"
    classification["category"] = "Media / Anime & Manga"
    classification["confidence"] = max(float(classification.get("confidence") or 0.0), 0.94)
    classification["signals"] = _uniq(list(classification.get("signals") or []) + list(facets.get("signals") or []), 8)
    classification["facets"] = {"media_family": "Anime", "format": facets.get("format"), "source_material": facets.get("source_material")}

    bookmark = data.setdefault("bookmark", {})
    bookmark["suggested_folder"] = "Media / Anime & Manga"
    sections = data.setdefault("sections", {})
    previous_film = sections.pop("film_tv", None)
    anime = sections.setdefault("anime_manga", {})
    resource = sections.setdefault("resource_details", {})
    if isinstance(previous_film, dict):
        for key in ("title", "synopsis", "status", "country", "runtime", "score", "genres"):
            if previous_film.get(key) not in (None, "", [], {}) and anime.get(key) in (None, "", [], {}):
                anime[key] = previous_film[key]
    anime["media_type"] = "Anime"
    resource["media_type"] = "Anime"

    scalar_fields = {
        "format": _first(_values_for(mapping, "format")), "status": _first(_values_for(mapping, "status")),
        "episodes": _first(_values_for(mapping, "episodes")), "season": _first(_values_for(mapping, "season")),
        "start_date": _first(_values_for(mapping, "start_date")), "end_date": _first(_values_for(mapping, "end_date")),
        "country": _first(_values_for(mapping, "country")), "adult": _first(_values_for(mapping, "adult")),
        "romaji": _first(_values_for(mapping, "romaji")), "native_title": _first(_values_for(mapping, "native_title")),
        "last_update": _first(_values_for(mapping, "last_update")), "source_material": _first(_values_for(mapping, "source_material")),
        "score": _first(_values_for(mapping, "score")), "runtime": _first(_values_for(mapping, "runtime")),
        "language": _first(_values_for(mapping, "language")), "certificate": _first(_values_for(mapping, "certificate")),
    }
    list_fields = {
        "studios": _split_values(_values_for(mapping, "studios")),
        "genres": _split_values(_values_for(mapping, "genres")),
        "tags": _split_values(_values_for(mapping, "tags")),
    }
    for key, value in scalar_fields.items():
        if value not in (None, ""):
            anime[key] = value
            resource[key] = value
    for key, values in list_fields.items():
        if values:
            anime[key] = values
            resource[key] = values
    explicit_year = _first(_values_for(mapping, "year"))
    year = _extract_year(explicit_year, scalar_fields.get("start_date"), scalar_fields.get("season"))
    if year:
        anime["year"] = year
        resource["year"] = year
    start_date = scalar_fields.get("start_date")
    if start_date:
        _set_key_fact(data, "Start date", start_date)
        _remove_key_fact(data, "Published", exact_value=start_date)
    if scalar_fields.get("end_date"):
        _set_key_fact(data, "End date", scalar_fields["end_date"])
    if year:
        _set_key_fact(data, "Year", year)
    if scalar_fields.get("episodes"):
        _set_key_fact(data, "Episodes", scalar_fields["episodes"])
    if scalar_fields.get("status"):
        _set_key_fact(data, "Status", scalar_fields["status"])
    if scalar_fields.get("country"):
        _set_key_fact(data, "Country", scalar_fields["country"])
    if list_fields["genres"]:
        _set_key_fact(data, "Genres", list_fields["genres"])
    if list_fields["studios"]:
        _set_key_fact(data, "Studios", list_fields["studios"])

    tags = [str(x) for x in (data.get("tags") or []) if str(x).casefold() not in {"film-tv", "article"}]
    if "anime" not in {x.casefold() for x in tags}:
        tags.insert(0, "anime")
    for value in list_fields["genres"] + list_fields["tags"]:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        if 2 <= len(slug) <= 40 and slug not in tags:
            tags.append(slug)
    data["tags"] = tags[:35]
    bookmark["suggested_tags"] = data["tags"]
    title = _clean(data.get("identity", {}).get("title"), 200) or "this title"
    bookmark["why_it_might_matter"] = f"Anime reference for {title} with source details preserved for later organization."

    quality = data.setdefault("quality", {})
    recovered = set(str(x) for x in (quality.get("structured_fields_recovered") or []))
    for key, value in {**scalar_fields, **list_fields, "year": year}.items():
        if value not in (None, "", [], {}):
            recovered.add(key)
    recovered.update({"media_type", "title"} if data.get("identity", {}).get("title") else {"media_type"})
    if data.get("summary"):
        recovered.add("description")
    quality["structured_fields_recovered"] = sorted(recovered)
    present_names = {
        "year": bool(year), "genres": bool(list_fields["genres"] or anime.get("genres")),
        "status": bool(scalar_fields.get("status") or anime.get("status")), "description": bool(data.get("summary")),
        "summary": bool(data.get("summary")), "specific title": bool(data.get("identity", {}).get("title")),
        "description/synopsis": bool(data.get("summary")),
    }
    missing = [str(x) for x in (quality.get("missing_or_uncertain") or []) if not present_names.get(str(x).casefold(), False)]
    quality["missing_or_uncertain"] = missing
    weights = {
        "title": 0.11, "description": 0.11, "format": 0.05, "status": 0.06, "episodes": 0.07,
        "season": 0.04, "start_date": 0.06, "end_date": 0.04, "country": 0.04, "adult": 0.03,
        "romaji": 0.04, "native_title": 0.04, "studios": 0.08, "genres": 0.07, "tags": 0.07,
        "source_material": 0.05, "score": 0.04,
    }
    score = 0.18
    if data.get("identity", {}).get("title"):
        score += weights["title"]
    if data.get("summary"):
        score += weights["description"]
    for key, value in scalar_fields.items():
        if value not in (None, "") and key in weights:
            score += weights[key]
    for key, value in list_fields.items():
        if value and key in weights:
            score += weights[key]
    score = min(0.96, max(float(quality.get("extraction_score") or 0.0), score))
    if missing:
        score = min(score, 0.89)
    quality["extraction_score"] = round(score, 2)
    quality["extraction_grade"] = "strong" if score >= 0.75 else "usable" if score >= 0.50 else "weak" if score >= 0.25 else "minimal"


__all__ = [name for name in globals() if not name.startswith("__")]
