from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Callable
from urllib.parse import urlencode, urlparse

from acquisition import AcquisitionError, acquire_url, validate_public_url
from provider_enrichment import ProviderEvidence, probe_provider

CANONICAL_MEDIA_TYPES = {
    "manga": "Manga", "manhwa": "Manhwa", "manwha": "Manhwa", "manhua": "Manhua",
    "webtoon": "Webtoon", "anime": "Anime", "novel": "Novel", "light novel": "Light Novel",
    "comic": "Comic", "book": "Book", "movie": "Movie", "series": "Series", "tv": "TV",
    "game": "Game", "software": "Software", "article": "Article",
}


def _clean(value: Any, limit: int = 1800) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"none", "null", "undefined", "n/a"}:
        return None
    return text[: limit - 1].rstrip() + "…" if len(text) > limit else text


def _uniq(values: list[Any], limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            for child in value.values():
                if isinstance(child, (str, int, float)):
                    value = child
                    break
            else:
                continue
        if isinstance(value, (list, tuple, set)):
            for child in value:
                for item in _uniq([child], limit):
                    key = item.casefold()
                    if key not in seen:
                        seen.add(key)
                        out.append(item)
                        if len(out) >= limit:
                            return out
            continue
        cleaned = _clean(value, 800)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            out.append(cleaned)
            if len(out) >= limit:
                break
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


def _localized_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        preferred: list[Any] = []
        if value.get("en"):
            preferred.append(value["en"])
        preferred.extend(v for k, v in value.items() if k != "en")
        return _uniq(preferred, 80)
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            out.extend(_localized_values(item) if isinstance(item, dict) else [item])
        return _uniq(out, 80)
    return _uniq([value], 80)


def _title_case_token(value: Any) -> str | None:
    cleaned = _clean(value, 120)
    return cleaned.replace("_", " ").replace("-", " ").title() if cleaned else None


def _relationship_names(relationships: list[Any], rel_type: str) -> list[str]:
    names: list[str] = []
    for rel in relationships:
        if not isinstance(rel, dict) or str(rel.get("type", "")).lower() != rel_type:
            continue
        attrs = rel.get("attributes") if isinstance(rel.get("attributes"), dict) else {}
        name = _clean(attrs.get("name"), 300)
        if name:
            names.append(name)
    return _uniq(names, 30)


def _mangadex_evidence(url: str, fetch_json: Callable[[str], Any] | None = None) -> ProviderEvidence:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    match = re.match(r"^/title/([0-9a-fA-F-]{36})(?:/|$)", parsed.path)
    if host not in {"mangadex.org", "www.mangadex.org"} or not match:
        return ProviderEvidence(adapter="mangadex", matched=False)

    manga_id = match.group(1).lower()
    fetcher = fetch_json or _json_endpoint
    evidence = ProviderEvidence(adapter="mangadex", matched=True)
    fields: dict[str, Any] = {"provider_id": manga_id, "media_type": "Manga"}
    info_endpoint = f"https://api.mangadex.org/manga/{manga_id}?" + urlencode([("includes[]", "author"), ("includes[]", "artist"), ("includes[]", "cover_art")])
    stats_endpoint = f"https://api.mangadex.org/statistics/manga/{manga_id}"

    payload: Any = None
    try:
        payload = fetcher(info_endpoint)
        evidence.sources.append(info_endpoint)
    except Exception as exc:
        evidence.errors.append(re.sub(r"\s+", " ", str(exc)).strip()[:300])

    if isinstance(payload, dict):
        record = payload.get("data")
        if isinstance(record, dict):
            attrs = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
            relationships = record.get("relationships") if isinstance(record.get("relationships"), list) else []
            titles = _localized_values(attrs.get("title"))
            if titles:
                fields["title"] = titles[0]
            alt_titles = titles[1:] + _localized_values(attrs.get("altTitles"))
            if fields.get("title"):
                alt_titles = [x for x in _uniq(alt_titles, 80) if x.casefold() != str(fields["title"]).casefold()]
            if alt_titles:
                fields["alternative_titles"] = alt_titles
            descriptions = _localized_values(attrs.get("description"))
            if descriptions:
                fields["description"] = descriptions[0]
            status = _title_case_token(attrs.get("status"))
            if status:
                fields["status"] = status
            year = attrs.get("year")
            if isinstance(year, int) and 1000 <= year <= 9999:
                fields["year"] = str(year)
            else:
                cleaned_year = _clean(year, 20)
                if cleaned_year and re.fullmatch(r"\d{4}", cleaned_year):
                    fields["year"] = cleaned_year
            for source_key, target_key in (("publicationDemographic", "demographic"), ("contentRating", "content_rating"), ("originalLanguage", "original_language")):
                value = _title_case_token(attrs.get(source_key))
                if value:
                    fields[target_key] = value
            for source_key, target_key in (("lastVolume", "final_volume"), ("lastChapter", "final_chapter"), ("createdAt", "source_created_at"), ("updatedAt", "source_updated_at")):
                value = _clean(attrs.get(source_key), 120)
                if value:
                    fields[target_key] = value
            languages = _uniq(list(attrs.get("availableTranslatedLanguages") or []), 40)
            if languages:
                fields["available_languages"] = languages

            tag_groups: dict[str, list[str]] = defaultdict(list)
            all_tags: list[str] = []
            for tag in attrs.get("tags") or []:
                if not isinstance(tag, dict):
                    continue
                tag_attrs = tag.get("attributes") if isinstance(tag.get("attributes"), dict) else {}
                names = _localized_values(tag_attrs.get("name"))
                if not names:
                    continue
                name = names[0]
                group = str(tag_attrs.get("group") or "tag").lower()
                tag_groups[group].append(name)
                all_tags.append(name)
            if tag_groups.get("genre"):
                fields["genres"] = _uniq(tag_groups["genre"], 40)
            if tag_groups.get("theme"):
                fields["themes"] = _uniq(tag_groups["theme"], 40)
            if tag_groups.get("format"):
                fields["formats"] = _uniq(tag_groups["format"], 40)
            if all_tags:
                fields["source_tags"] = _uniq(all_tags, 80)

            authors = _relationship_names(relationships, "author")
            artists = _relationship_names(relationships, "artist")
            if authors:
                fields["authors"] = authors
            if artists:
                fields["artists"] = artists
            for rel in relationships:
                if not isinstance(rel, dict) or str(rel.get("type", "")).lower() != "cover_art":
                    continue
                rel_attrs = rel.get("attributes") if isinstance(rel.get("attributes"), dict) else {}
                filename = _clean(rel_attrs.get("fileName"), 500)
                if filename:
                    fields["poster"] = f"https://uploads.mangadex.org/covers/{manga_id}/{filename}.512.jpg"
                    break
            links = attrs.get("links")
            if isinstance(links, dict):
                clean_links = {str(k): _clean(v, 500) for k, v in links.items() if _clean(v, 500)}
                if clean_links:
                    fields["external_ids"] = clean_links

    try:
        stats_payload = fetcher(stats_endpoint)
        evidence.sources.append(stats_endpoint)
        stats_root = stats_payload.get("statistics") if isinstance(stats_payload, dict) else None
        stats = stats_root.get(manga_id) if isinstance(stats_root, dict) else None
        if isinstance(stats, dict):
            rating = stats.get("rating") if isinstance(stats.get("rating"), dict) else {}
            avg = rating.get("average")
            if isinstance(avg, (int, float)):
                fields["score"] = str(round(float(avg), 2))
            follows = stats.get("follows")
            if isinstance(follows, int):
                fields["follow_count"] = follows
            comments = stats.get("comments") if isinstance(stats.get("comments"), dict) else {}
            replies = comments.get("repliesCount")
            if isinstance(replies, int):
                fields["comment_count"] = replies
    except Exception as exc:
        evidence.errors.append(re.sub(r"\s+", " ", str(exc)).strip()[:300])

    evidence.fields = fields
    useful = sum(1 for key in ("title", "description", "authors", "artists", "genres", "status", "year", "demographic", "formats", "final_chapter", "score") if fields.get(key))
    evidence.sufficient = bool(fields.get("title") and useful >= 4)
    return evidence


def probe_provider_extended(url: str) -> ProviderEvidence | None:
    base = probe_provider(url)
    if base and base.matched:
        return base
    mangadex = _mangadex_evidence(url)
    return mangadex if mangadex.matched else None


__all__ = [name for name in globals() if not name.startswith("__")]
