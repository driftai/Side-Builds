from __future__ import annotations

from provider_atsu import *


PROVIDER_ADAPTERS: tuple[Callable[[str], ProviderEvidence], ...] = (_atsu_evidence,)


def probe_provider(url: str) -> ProviderEvidence | None:
    """Try known public structured endpoints before launching a browser.

    Adapters may only use public, unauthenticated endpoints. Authentication,
    CAPTCHA solving, challenge bypasses and private-network targets are not part
    of this layer.
    """
    validate_public_url(url)
    for adapter in PROVIDER_ADAPTERS:
        evidence = adapter(url)
        if evidence.matched:
            return evidence
    return None


def _oembed_candidates(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    out: list[str] = []
    for link in soup.find_all("link", href=True):
        rel = {str(item).lower() for item in (link.get("rel") or [])}
        media_type = str(link.get("type") or "").lower()
        if "alternate" not in rel or "oembed" not in media_type or "json" not in media_type:
            continue
        href = str(link.get("href") or "").strip()
        if not href:
            continue
        href = urljoin(base_url, href)
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        try:
            validate_public_url(href)
        except AcquisitionError:
            continue
        if href not in out:
            out.append(href)
    return out[:3]


def probe_oembed(html: str, page_url: str) -> ProviderEvidence | None:
    endpoints = _oembed_candidates(html, page_url)
    if not endpoints:
        return None
    evidence = ProviderEvidence(adapter="oembed", matched=True)
    for endpoint in endpoints:
        try:
            payload = _json_endpoint(endpoint)
        except Exception as exc:
            evidence.errors.append(re.sub(r"\s+", " ", str(exc)).strip()[:300])
            continue
        if not isinstance(payload, dict):
            continue
        evidence.sources.append(endpoint)
        fields: dict[str, Any] = {}
        mapping = {
            "title": "title",
            "author_name": "authors",
            "provider_name": "provider_name",
            "type": "media_type",
            "thumbnail_url": "poster",
        }
        for source_key, target_key in mapping.items():
            value = payload.get(source_key)
            if value in (None, "", [], {}):
                continue
            if target_key == "authors":
                vals = _uniq([value])
                if vals:
                    fields[target_key] = vals
            else:
                cleaned = _clean(value, 1000)
                if cleaned:
                    fields[target_key] = cleaned
        if payload.get("html"):
            fields["embed_available"] = True
        evidence.fields.update(fields)
    evidence.sufficient = bool(evidence.fields.get("title") and len(evidence.fields) >= 2)
    return evidence


def _add_entity(data: dict[str, Any], entity_type: str, name: str) -> None:
    normalized = name.strip().lower()
    if not normalized:
        return
    entities = data.setdefault("entities", [])
    for entity in entities:
        if str(entity.get("type", "")).lower() == entity_type.lower() and str(entity.get("name", "")).strip().lower() == normalized:
            return
    entities.append({"type": entity_type, "name": name})


def _merge_list(existing: Any, incoming: Any, limit: int = 20) -> list[str]:
    current = existing if isinstance(existing, list) else ([] if existing in (None, "") else [existing])
    addition = incoming if isinstance(incoming, list) else ([] if incoming in (None, "") else [incoming])
    return _uniq([*current, *addition], limit)


def _grade(score: float) -> str:
    if score >= 0.75:
        return "strong"
    if score >= 0.50:
        return "usable"
    if score >= 0.25:
        return "weak"
    return "minimal"


def apply_provider_evidence(data: dict[str, Any], evidence: ProviderEvidence | None) -> dict[str, Any]:
    if not evidence or not evidence.matched:
        return data

    data["provider_enrichment"] = evidence.diagnostics()
    if not evidence.fields:
        return data

    fields = evidence.fields
    identity = data.setdefault("identity", {})
    current_title = _clean(identity.get("title"), 300)
    input_url = str(data.get("input", {}).get("url") or data.get("fetch", {}).get("final_url") or "")
    provider_title = _clean(fields.get("title") or fields.get("english_title"), 300)
    title_is_fallback = not current_title or current_title == input_url or current_title.lower().startswith(("http://", "https://"))
    if provider_title and title_is_fallback:
        identity["title"] = provider_title
        bookmark = data.setdefault("bookmark", {})
        bookmark["suggested_title"] = provider_title

    provider_description = _clean(fields.get("description"), 1200)
    current_summary = _clean(data.get("summary"), 1200)
    if provider_description and (not current_summary or "no meaningful page summary" in current_summary.lower()):
        data["summary"] = provider_description

    kind = str(data.get("classification", {}).get("kind") or "")
    sections = data.setdefault("sections", {})
    resource = sections.setdefault("resource_details", {})
    for key, value in fields.items():
        if key in {"title", "description"}:
            continue
        if value not in (None, "", [], {}):
            resource[key] = value

    if kind == "anime_manga" or evidence.adapter == "atsu":
        media = sections.setdefault("anime_manga", {})
        media.setdefault("media_type", fields.get("media_type") or "Manga")
        for key in (
            "english_title", "alternative_titles", "authors", "artists", "genres",
            "status", "score", "year", "chapter_count", "chapter_record_count", "latest_chapter",
            "latest_chapter_title", "scanlation_group_count", "poster",
        ):
            value = fields.get(key)
            if value in (None, "", [], {}):
                continue
            if key in {"authors", "artists"}:
                media[key] = value if isinstance(value, list) else [value]
            elif key in {"genres", "alternative_titles"}:
                media[key] = _merge_list(media.get(key), value)
            else:
                media[key] = value

    if fields.get("authors"):
        provider_author_names = {a.lower() for a in fields["authors"]}
        provider_author_bases = {_norm_name(a) for a in fields["authors"]}
        data["entities"] = [
            e for e in data.get("entities", [])
            if not (
                str(e.get("type", "")).lower() in {"author", "person/author"}
                and (any(pa in str(e.get("name", "")).lower() for pa in provider_author_names) or _norm_name(str(e.get("name", ""))) in provider_author_bases)
                and str(e.get("name", "")).lower() not in provider_author_names
            )
        ]
        for name in fields["authors"]:
            _add_entity(data, "Author", name)
    if fields.get("artists"):
        provider_artist_names = {a.lower() for a in fields["artists"]}
        provider_artist_bases = {_norm_name(a) for a in fields["artists"]}
        provider_author_bases = {_norm_name(a) for a in fields.get("authors", [])}
        data["entities"] = [
            e for e in data.get("entities", [])
            if not (
                str(e.get("type", "")).lower() in {"author", "person/author"}
                and (any(pa in str(e.get("name", "")).lower() for pa in provider_artist_names) or _norm_name(str(e.get("name", ""))) in provider_artist_bases)
                and not any(ab == _norm_name(str(e.get("name", ""))) or ab in str(e.get("name", "")).lower() for ab in provider_author_bases)
            )
        ]
        for name in fields["artists"]:
            _add_entity(data, "Artist", name)

    tags = data.setdefault("tags", [])
    for genre in _merge_list([], fields.get("genres")):
        tag = _slug(genre)
        if tag and tag not in tags:
            tags.append(tag)
    if evidence.adapter != "oembed" and evidence.adapter not in tags:
        tags.append(evidence.adapter)
    data["tags"] = tags[:20]

    facts = data.setdefault("key_facts", [])
    known = {str(item.get("label", "")).lower() for item in facts if isinstance(item, dict)}
    for label, key in (
        ("Provider", "provider_name"),
        ("Status", "status"),
        ("Chapters", "chapter_count"),
        ("Chapter records", "chapter_record_count"),
        ("Latest chapter", "latest_chapter"),
        ("Score", "score"),
    ):
        value = fields.get(key)
        if value in (None, "", [], {}) or label.lower() in known:
            continue
        facts.append({"label": label, "value": str(value)})

    quality = data.setdefault("quality", {})
    recovered = set(quality.get("structured_fields_recovered") or [])
    recovered.update(key for key, value in fields.items() if value not in (None, "", [], {}))
    quality["structured_fields_recovered"] = sorted(recovered)

    old_score = float(quality.get("extraction_score") or 0.0)
    useful = sum(
        1 for key in (
            "title", "description", "authors", "artists", "genres", "status",
            "chapter_count", "media_type", "score", "year",
        )
        if fields.get(key)
    )
    provider_score = min(0.96, 0.38 + useful * 0.065 + (0.12 if evidence.sufficient else 0.0))
    score = max(old_score, provider_score)
    quality["extraction_score"] = round(score, 2)
    quality["extraction_grade"] = _grade(score)

    missing = list(quality.get("missing_or_uncertain") or [])
    field_to_missing = {
        "description": {"description", "summary"},
        "authors": {"author", "authors"},
        "title": {"title"},
        "status": {"status"},
    }
    recovered_missing = set()
    for key, labels in field_to_missing.items():
        if fields.get(key):
            recovered_missing.update(labels)
    quality["missing_or_uncertain"] = [item for item in missing if str(item).lower() not in recovered_missing]
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
