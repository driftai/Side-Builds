from __future__ import annotations

from enrichment_extract import *


def _specific_title(data: dict[str, Any], soup: BeautifulSoup, fields: dict[str, list[str]]) -> str | None:
    current = _clean(data.get("identity", {}).get("title"), 300)
    final_url = str(data.get("fetch", {}).get("final_url") or data.get("input", {}).get("url") or "")
    host = (urlparse(final_url).hostname or "").lower()

    def useful(value: str | None) -> bool:
        if not value:
            return False
        low = value.lower().strip()
        return low not in {final_url.lower(), host, f"www.{host}"} and not low.startswith("http://") and not low.startswith("https://")

    candidates = [
        current,
        _meta(soup, "og:title", "twitter:title"),
        _clean(soup.title.get_text(" ", strip=True), 300) if soup.title else None,
        _clean(soup.find("h1").get_text(" ", strip=True), 300) if soup.find("h1") else None,
    ]
    candidates.extend(fields.get("title", [])[:6])
    for candidate in candidates:
        if useful(candidate):
            return candidate
    return None


def _summary(data: dict[str, Any], soup: BeautifulSoup, fields: dict[str, list[str]], trafi: dict[str, Any]) -> str | None:
    current = _clean(data.get("summary"), 1200)
    if current and "no meaningful page summary" not in current.lower():
        return current
    for candidate in (
        _meta(soup, "description", "og:description", "twitter:description"),
        *(fields.get("description", [])[:8]),
        _clean(trafi.get("description"), 1200),
    ):
        cleaned = _clean(candidate, 1200)
        if cleaned and len(cleaned) >= 35:
            return cleaned
    text = _clean(trafi.get("text"), 1600)
    if text and len(text) >= 80:
        return text[:700].rstrip() + ("…" if len(text) > 700 else "")
    return None


def _unique_entity(data: dict[str, Any], entity_type: str, name: str) -> None:
    entities = data.setdefault("entities", [])
    normalized = name.lower().strip()
    if not normalized:
        return
    for entity in entities:
        if str(entity.get("type", "")).lower() == entity_type.lower() and str(entity.get("name", "")).lower().strip() == normalized:
            return
    entities.append({"type": entity_type, "name": name})


def _slug_tag(value: str) -> str | None:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if 2 <= len(value) <= 36:
        return value
    return None


def _meaningful_fields(fields: dict[str, list[str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "alternative_titles",
        "authors",
        "artists",
        "genres",
        "status",
        "chapters",
        "volumes",
        "score",
        "year",
        "media_type",
    ):
        values = fields.get(key, [])
        if not values:
            continue
        if key in {"authors", "artists", "genres", "alternative_titles"}:
            result[key] = values[:12]
        else:
            result[key] = values[0]
    return result


def enrich_analysis(data: dict[str, Any], acquired: Any) -> dict[str, Any]:
    html = str(acquired.text or "")
    content_type = str(acquired.content_type or "")
    diagnostics = acquired.diagnostics() if hasattr(acquired, "diagnostics") else {}
    data["acquisition"] = diagnostics

    if content_type and not any(token in content_type for token in ("html", "xml", "json", "text")):
        quality = data.setdefault("quality", {})
        quality["extraction_score"] = 0.2
        quality["extraction_grade"] = "limited"
        return data

    soup = BeautifulSoup(html, "html.parser")
    payloads = _parse_script_payloads(soup)
    structured = _mine_structured_fields(payloads)
    labels = _label_pairs(soup)

    meta_fields: dict[str, list[str]] = defaultdict(list)
    for canon, names in GENERIC_META.items():
        value = _meta(soup, *names)
        if value:
            meta_fields[canon].append(value)

    trafi = _trafilatura_data(html, str(acquired.final_url))
    if trafi.get("author"):
        meta_fields["authors"].append(str(trafi["author"]))
    if trafi.get("title"):
        meta_fields["title"].append(str(trafi["title"]))
    if trafi.get("date"):
        meta_fields["year"].append(str(trafi["date"])[:10])

    fields = _merge_fields(structured, labels, dict(meta_fields))
    title = _specific_title(data, soup, fields)
    summary = _summary(data, soup, fields, trafi)

    if title:
        data.setdefault("identity", {})["title"] = title
        data.setdefault("bookmark", {})["suggested_title"] = title
    if summary:
        data["summary"] = summary

    details = _meaningful_fields(fields)
    sections = data.setdefault("sections", {})
    if details:
        sections["resource_details"] = details

    kind = str(data.get("classification", {}).get("kind", ""))
    if kind == "anime_manga":
        media = dict(sections.get("anime_manga", {}))
        if title:
            media["title"] = title
        if summary:
            media["synopsis"] = summary
        for key, value in details.items():
            media.setdefault(key, value)
        path = urlparse(str(acquired.final_url)).path.lower()
        if "media_type" not in media:
            if "/manga/" in path or "/manhwa/" in path or "/webtoon/" in path:
                media["media_type"] = "Manga"
            elif "/anime/" in path:
                media["media_type"] = "Anime"
        sections["anime_manga"] = media

    for field_name, entity_type in ENTITY_FIELDS.items():
        for value in fields.get(field_name, [])[:12]:
            candidates = [value]
            if ";" in value or value.count(",") >= 2:
                candidates = [part.strip() for part in re.split(r"[;|]", value) if part.strip()]
            elif "," in value:
                parts = [part.strip() for part in value.split(",") if part.strip()]
                if len(parts) == 2 and parts[0].lower() == parts[1].lower():
                    candidates = [parts[0]]
            for candidate in candidates:
                if 1 < len(candidate) <= 180:
                    _unique_entity(data, entity_type, candidate)

    tags = data.setdefault("tags", [])
    for genre in fields.get("genres", [])[:12]:
        for piece in re.split(r"[,;/|]", genre):
            tag = _slug_tag(piece.strip())
            if tag and tag not in tags:
                tags.append(tag)
    deduped: list[str] = []
    for tag in tags:
        normalized = _slug_tag(str(tag)) or str(tag)
        if normalized not in deduped:
            deduped.append(normalized)
    data["tags"] = deduped[:24]
    if data.get("bookmark") is not None:
        data["bookmark"]["suggested_tags"] = data["tags"]

    identity_title = _clean(data.get("identity", {}).get("title"))
    final_url = str(acquired.final_url)
    title_specific = bool(identity_title and identity_title != final_url and not identity_title.startswith("http"))
    summary_good = bool(_clean(data.get("summary")) and "no meaningful page summary" not in str(data.get("summary", "")).lower())
    field_count = sum(1 for value in details.values() if value)
    entity_count = len(data.get("entities", []))
    text_chars = int(data.get("quality", {}).get("content_text_chars_considered", 0) or 0)
    trafi_chars = len(str(trafi.get("text", "")))

    score = 0.0
    score += 0.25 if title_specific else 0.0
    score += 0.25 if summary_good else 0.0
    score += min(0.22, field_count * 0.055)
    score += min(0.14, entity_count * 0.04)
    if max(text_chars, trafi_chars) >= 1000:
        score += 0.14
    elif max(text_chars, trafi_chars) >= 250:
        score += 0.08
    if diagnostics.get("rendered") and title_specific:
        score += 0.04
    score = round(min(1.0, score), 2)

    if score >= 0.75:
        grade = "strong"
    elif score >= 0.50:
        grade = "usable"
    elif score >= 0.25:
        grade = "weak"
    else:
        grade = "minimal"

    quality = data.setdefault("quality", {})
    quality["extraction_score"] = score
    quality["extraction_grade"] = grade
    quality["structured_payloads_seen"] = len(payloads)
    quality["structured_fields_recovered"] = sorted(details.keys())
    quality["trafilatura_text_chars"] = trafi_chars

    missing: list[str] = []
    if not title_specific:
        missing.append("specific title")
    if not summary_good:
        missing.append("description/synopsis")
    if kind == "anime_manga":
        for field in ("authors", "genres", "status"):
            if field not in sections.get("anime_manga", {}):
                missing.append(field)
    quality["missing_or_uncertain"] = missing

    bookmark = data.setdefault("bookmark", {})
    if title_specific:
        if kind == "anime_manga":
            bookmark["why_it_might_matter"] = f"Series reference for {title} with recovered page-specific metadata."
        elif grade in {"strong", "usable"}:
            bookmark["why_it_might_matter"] = f"Structured reference for {title}; enough page-specific information was recovered for later organization and rediscovery."
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
