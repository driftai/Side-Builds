from __future__ import annotations

from typing import Any

from source_archive import *


def _slug(value: str) -> str | None:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug if 2 <= len(slug) <= 40 else None


def _set_fact(data: dict[str, Any], label: str, value: Any) -> None:
    if value in (None, "", [], {}):
        return
    facts = data.setdefault("key_facts", [])
    rendered = ", ".join(str(x) for x in value) if isinstance(value, list) else str(value)
    for item in facts:
        if isinstance(item, dict) and str(item.get("label", "")).casefold() == label.casefold():
            item["value"] = rendered
            return
    facts.append({"label": label, "value": rendered})


def _norm_entity_name(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", str(name or "")).strip().casefold()


def _dedupe_entities(data: dict[str, Any]) -> None:
    entities = data.get("entities") or []
    canonical: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    author_names = {str(e.get("name", "")).strip().casefold() for e in entities if str(e.get("type", "")).casefold() == "author"}
    author_bases = {_norm_entity_name(str(e.get("name", ""))) for e in entities if str(e.get("type", "")).casefold() == "author"}
    artist_names = {str(e.get("name", "")).strip().casefold() for e in entities if str(e.get("type", "")).casefold() == "artist"}
    artist_bases = {_norm_entity_name(str(e.get("name", ""))) for e in entities if str(e.get("type", "")).casefold() == "artist"}

    for entity in entities:
        if not isinstance(entity, dict):
            continue
        kind = str(entity.get("type", "")).strip()
        name = str(entity.get("name", "")).strip()
        if not kind or not name:
            continue
        base = _norm_entity_name(name)
        if kind.casefold() in {"person/author", "person", "creator"}:
            if name.casefold() in author_names or base in author_bases or name.casefold() in artist_names or base in artist_bases:
                continue
        if kind.casefold() in {"author", "artist"} and (base in author_bases or base in artist_bases):
            if "(" not in name and any(base == _norm_entity_name(c["name"]) and "(" in c["name"] and c["type"].casefold() == kind.casefold() for c in canonical):
                continue
            if "(" in name:
                canonical = [c for c in canonical if not (c["type"].casefold() == kind.casefold() and _norm_entity_name(c["name"]) == base and "(" not in c["name"])]
        key = (kind.casefold(), name.casefold())
        if key in seen:
            continue
        seen.add(key)
        canonical.append({"type": kind, "name": name})
    data["entities"] = canonical


def _merge_provider_fields_into_sections(data: dict[str, Any], provider: ProviderEvidence | None) -> None:
    if not provider or not provider.fields:
        return
    fields = provider.fields
    sections = data.setdefault("sections", {})
    resource = sections.setdefault("resource_details", {})
    media = sections.setdefault("anime_manga", {}) if str(data.get("classification", {}).get("kind")) == "anime_manga" else None

    canonical_title = _clean(fields.get("title"), 300)
    if canonical_title and provider.adapter in {"atsu", "mangadex"}:
        data.setdefault("identity", {})["title"] = canonical_title
        data.setdefault("bookmark", {})["suggested_title"] = canonical_title
    if fields.get("description"):
        data["summary"] = fields["description"]
    for key, value in fields.items():
        if key not in {"title", "description"} and value not in (None, "", [], {}):
            resource[key] = value
    if media is not None:
        for key, value in fields.items():
            if key in {"provider_id", "external_ids", "source_created_at", "source_updated_at", "title", "description"} or value in (None, "", [], {}):
                continue
            media[key] = value
        if canonical_title:
            media["title"] = canonical_title
        if fields.get("description"):
            media["synopsis"] = fields["description"]


def _normalize_resource_fields(data: dict[str, Any]) -> None:
    sections = data.setdefault("sections", {})
    kind = str(data.get("classification", {}).get("kind", ""))
    for section_name in ("resource_details", "anime_manga"):
        section = sections.get(section_name)
        if not isinstance(section, dict):
            continue
        media = _clean(section.get("media_type"), 80)
        if media:
            canonical = CANONICAL_MEDIA_TYPES.get(media.casefold())
            if canonical:
                section["media_type"] = canonical
            elif kind == "anime_manga":
                formats = section.get("formats")
                if not isinstance(formats, list):
                    formats = [] if formats in (None, "") else [formats]
                if media not in formats:
                    formats.append(media)
                section["formats"] = formats
                section["media_type"] = "Manga"
        year = _clean(section.get("year"), 40)
        if year and re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:.*)?", year):
            section.setdefault("source_page_date", year)
            section.pop("year", None)
        if section.get("chapter_count") is not None and section.get("latest_chapter") is not None:
            ambiguous = section.get("chapters")
            if ambiguous not in (None, "", [], {}):
                section["raw_chapters_candidate"] = ambiguous
                section.pop("chapters", None)


def _provider_tags(data: dict[str, Any], provider: ProviderEvidence | None) -> None:
    if not provider or not provider.fields:
        return
    tags = list(data.get("tags") or [])
    for key in ("genres", "themes", "formats", "source_tags"):
        values = provider.fields.get(key)
        if not isinstance(values, list):
            values = [] if values in (None, "") else [values]
        for value in values:
            tag = _slug(str(value))
            if tag and tag not in tags:
                tags.append(tag)
    for key in ("demographic", "content_rating"):
        value = provider.fields.get(key)
        tag = _slug(str(value)) if value else None
        if tag and tag not in tags:
            tags.append(tag)
    if provider.adapter not in tags:
        tags.append(provider.adapter)
    data["tags"] = tags[:30]
    data.setdefault("bookmark", {})["suggested_tags"] = data["tags"]


def _reconcile_quality(data: dict[str, Any], provider: ProviderEvidence | None) -> None:
    quality = data.setdefault("quality", {})
    media = data.get("sections", {}).get("anime_manga", {})
    missing = [str(x) for x in (quality.get("missing_or_uncertain") or [])]
    present = {
        "title": bool(data.get("identity", {}).get("title")),
        "specific title": bool(data.get("identity", {}).get("title")),
        "description": bool(data.get("summary")),
        "summary": bool(data.get("summary")),
        "description/synopsis": bool(data.get("summary")),
        "author": bool(media.get("authors")), "authors": bool(media.get("authors")),
        "genres": bool(media.get("genres")), "status": bool(media.get("status")), "year": bool(media.get("year")),
    }
    missing = [item for item in missing if not present.get(item.casefold(), False)]
    quality["missing_or_uncertain"] = missing
    current = float(quality.get("extraction_score") or 0.0)
    if provider and provider.sufficient:
        useful = sum(1 for key in ("title", "description", "authors", "artists", "genres", "themes", "status", "year", "demographic", "formats", "final_chapter", "score") if provider.fields.get(key))
        current = max(current, min(0.98, 0.55 + useful * 0.04))
    current = min(current, 0.98)
    if missing:
        current = min(current, 0.89)
    quality["extraction_score"] = round(current, 2)
    quality["extraction_grade"] = "strong" if current >= 0.75 else "usable" if current >= 0.50 else "weak" if current >= 0.25 else "minimal"


def finalize_analysis(data: dict[str, Any], acquired: Any, provider: ProviderEvidence | None) -> dict[str, Any]:
    """Normalize the curated result and preserve evidence that was not promoted."""
    _merge_provider_fields_into_sections(data, provider)
    _normalize_resource_fields(data)
    _provider_tags(data, provider)
    if provider and provider.fields:
        fields = provider.fields
        if fields.get("authors"):
            _set_fact(data, "Author", fields["authors"])
        if fields.get("artists"):
            _set_fact(data, "Artist", fields["artists"])
        for label, key in (
            ("Status", "status"), ("Year", "year"), ("Final chapter", "final_chapter"),
            ("Latest chapter", "latest_chapter"), ("Chapters", "chapter_count"),
            ("Chapter records", "chapter_record_count"), ("Score", "score"),
            ("Demographic", "demographic"), ("Format", "formats"),
        ):
            if fields.get(key) not in (None, "", [], {}):
                _set_fact(data, label, fields[key])
    _dedupe_entities(data)
    _reconcile_quality(data, provider)
    archive = build_evidence_archive(data, acquired, provider)
    if provider and provider.matched:
        archive["provider_fields_snapshot"] = provider.fields
        archive["provider_sources"] = list(provider.sources)
        archive["provider_warnings"] = list(provider.errors)
    data["evidence_archive"] = archive
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
