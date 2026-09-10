from __future__ import annotations

from universal_extract import *


def _media_signals(final_url: str, soup: BeautifulSoup, facts: list[dict[str, str]], blocks: list[str]) -> tuple[int, list[str], str | None]:
    parsed = urlparse(final_url)
    path = parsed.path
    score = 0
    signals: list[str] = []
    resource_type: str | None = None
    for pattern, candidate_type, points in MEDIA_PATH_PATTERNS:
        if pattern.search(path):
            score += points
            resource_type = candidate_type
            signals.append(f"{candidate_type.lower()} URL pattern")
            break
    schema_types = _jsonld_types(soup)
    if schema_types & {"TVSeries", "TVEpisode", "TVSeason"}:
        score += 9
        resource_type = "TV Series"
        signals.append("TV schema.org type")
    elif "Movie" in schema_types:
        score += 9
        resource_type = "Movie"
        signals.append("Movie schema.org type")
    elif "VideoObject" in schema_types:
        score += 2
        signals.append("video schema.org type")
    labels = {_norm_label(f.get("label", "")) for f in facts}
    strong_label_weights = {
        "show status": 3, "series status": 3, "year started": 2, "certificate": 2,
        "credits": 2, "cast": 2, "director": 2, "runtime": 1, "country": 1,
        "language": 1, "genre": 1, "genres": 1, "keywords": 1,
    }
    for label, points in strong_label_weights.items():
        if label in labels:
            score += points
            signals.append(f"labeled {label}")
    flat = "\n".join(blocks[:100]) + "\n" + soup.get_text("\n", strip=True)[:20000]
    seasons = {int(x) for x in re.findall(r"\bSeason\s+(\d{1,3})\b", flat, flags=re.I)}
    if seasons:
        score += 2
        resource_type = resource_type or "TV Series"
        signals.append("season markers")
    if len(seasons) >= 2:
        score += 2
        signals.append("multiple seasons")
    title_text = _clean(soup.title.get_text(" ", strip=True), 240) if soup.title else None
    if title_text and re.search(r"\b(?:series|tv show|movie|film)\b", title_text, re.I):
        score += 1
        signals.append("media title wording")
    return score, signals[:8], resource_type


def _best_title(data: dict[str, Any], soup: BeautifulSoup, resource_type: str | None) -> str | None:
    current = _clean(data.get("identity", {}).get("title"), 300)
    h1s = _uniq([h.get_text(" ", strip=True) for h in soup.find_all("h1")], 8)
    for candidate in h1s:
        if 1 <= len(candidate.split()) <= 10 and len(candidate) <= 120:
            if not current or candidate.casefold() in current.casefold() or len(current) > len(candidate) + 12:
                return candidate
    if current:
        for pattern in (r"^(.+?)\s+(?:Series|TV Show|Movie|Film)\s+(?:Online|Streaming|Watch)\b", r"^(.+?)\s*[-|]\s*(?:Watch|Stream)\b"):
            match = re.search(pattern, current, re.I)
            if match:
                candidate = _clean(match.group(1), 160)
                if candidate and 1 <= len(candidate.split()) <= 12:
                    return candidate
    return current


def _description_score(text: str, position: int) -> float:
    low = text.casefold()
    if len(text) < 55:
        return -10
    score = 4.0 if 80 <= len(text) <= 700 else 2.0 if len(text) <= 1000 else 0.0
    if re.search(r"[.!?]", text): score += 1
    if position < 12: score += 1.5
    elif position < 30: score += 0.5
    boilerplate = ("watch now", "watch online", "free streaming", "no signup", "click and watch", "sign up", "register", "copyright", "terms of service", "disclaimer", "all contents are provided", "this site does not store")
    score -= 3 * sum(1 for term in boilerplate if term in low)
    if low.count("http") > 0: score -= 2
    return score


def _best_description(data: dict[str, Any], soup: BeautifulSoup, blocks: list[str]) -> str | None:
    current = _clean(data.get("summary"), 1200)
    candidates: list[tuple[float, str]] = []
    if current:
        candidates.append((_description_score(current, 999), current))
    raw: list[str] = []
    for p in soup.find_all(["p", "blockquote"]):
        if p.find_parent(SKIP_TEXT_PARENTS | GENERIC_NAV_PARENTS):
            continue
        text = _clean(p.get_text(" ", strip=True), 1200)
        if text: raw.append(text)
    raw.extend(blocks[:50])
    for idx, text in enumerate(_uniq(raw, 80)):
        candidates.append((_description_score(text, idx), text))
    if not candidates:
        return current
    candidates.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    best_score, best = candidates[0]
    return best if best_score >= 3 else current


def _person_names(soup: BeautifulSoup) -> list[str]:
    names: list[str] = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        if not re.search(r"/(?:person|people|cast|actor|director)/", href, re.I):
            continue
        label = _clean(a.get_text(" ", strip=True) or a.get("title") or a.get("aria-label"), 180)
        if not label: continue
        label = re.sub(r"^\s*watch\s+", "", label, flags=re.I)
        label = re.sub(r"\s+(?:movies?|series|shows?)\s+online.*$", "", label, flags=re.I)
        label = re.sub(r"\s+online\s+hd.*$", "", label, flags=re.I)
        label = _clean(label, 120)
        if label and 1 <= len(label.split()) <= 8: names.append(label)
    return _uniq(names, 40)


SECTION_HEADING_RE = re.compile(r"\b(?:similar|related|recommend(?:ed|ations)?|more like(?: this)?|cast|credits?|crew|seasons?|episodes?|chapters?|characters?|actors?|directors?|reviews?|comments?|external links?|sources?|downloads?|trailers?)\b", re.I)


def _source_context_for_anchor(anchor: Any) -> str | None:
    if anchor.find_parent(GENERIC_NAV_PARENTS): return None
    for prev in anchor.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6", "b", "strong", "header"]):
        if prev.find_parent(GENERIC_NAV_PARENTS): continue
        text = _clean(prev.get_text(" ", strip=True), 120)
        if not text: continue
        if prev.name in {"h1", "h2", "h3", "h4", "h5", "h6", "header"}:
            if 1 <= len(text.split()) <= 10 and len(text) <= 120: return text
        elif prev.name in {"b", "strong"}:
            clean_t = text.rstrip(":").strip()
            if 1 <= len(clean_t.split()) <= 8 and len(clean_t) <= 60:
                classes = " ".join(prev.get("class", []) + [str(prev.get("name") or ""), str(prev.get("id") or "")])
                if SECTION_HEADING_RE.search(clean_t) or re.search(r"\b(?:head|heading|title|header|caption)\b", classes, re.I):
                    return clean_t
    return None


def _annotate_archive_links(archive: dict[str, Any], soup: BeautifulSoup, base_url: str) -> None:
    by_url: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")): continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname: continue
        clean_url = parsed._replace(fragment="").geturl()
        context = _source_context_for_anchor(a)
        if context and clean_url not in by_url: by_url[clean_url] = context
    for row in archive.get("links") or []:
        if isinstance(row, dict) and by_url.get(str(row.get("url") or "")):
            row["source_context"] = by_url[str(row.get("url") or "")]


def _merge_generic_archive(data: dict[str, Any], facts: list[dict[str, str]], blocks: list[str], soup: BeautifulSoup, final_url: str) -> None:
    archive = data.setdefault("evidence_archive", {})
    existing = archive.setdefault("labeled_facts", [])
    seen = {(_norm_label(str(row.get("label", ""))), str(row.get("value", "")).casefold()) for row in existing if isinstance(row, dict)}
    for fact in facts:
        key = (_norm_label(fact.get("label", "")), str(fact.get("value", "")).casefold())
        if key in seen: continue
        seen.add(key)
        existing.append(fact)
        if len(existing) >= MAX_GENERIC_FACTS: break
    archive["source_text_blocks"] = blocks[:MAX_TEXT_BLOCKS]
    stats = archive.setdefault("capture_stats", {})
    stats["labeled_facts_retained"] = len(existing)
    stats["source_text_blocks_retained"] = len(archive["source_text_blocks"])
    _annotate_archive_links(archive, soup, final_url)
    archive["capture_note"] = "Bounded evidence archive: preserves labeled facts, readable source text, metadata and HTTP(S) links even when Bookmark Intel cannot confidently organize them yet. Scripts/styles, unsafe protocols and duplicate noise are not dumped."


def _add_key_fact(data: dict[str, Any], label: str, value: Any) -> None:
    if value in (None, "", [], {}): return
    rendered = ", ".join(str(x) for x in value) if isinstance(value, list) else str(value)
    facts = data.setdefault("key_facts", [])
    for item in facts:
        if isinstance(item, dict) and str(item.get("label", "")).casefold() == label.casefold():
            item["value"] = rendered
            return
    facts.append({"label": label, "value": rendered})


def _add_entity(data: dict[str, Any], kind: str, name: str) -> None:
    name = _clean(name, 160)
    if not name: return
    for entity in data.setdefault("entities", []):
        if str(entity.get("type", "")).casefold() == kind.casefold() and str(entity.get("name", "")).casefold() == name.casefold(): return
    data["entities"].append({"type": kind, "name": name})


def _promote_film_tv(data: dict[str, Any], soup: BeautifulSoup, facts: list[dict[str, str]], blocks: list[str], score: int, signals: list[str], resource_type: str | None) -> None:
    mapping = _fact_map(facts)
    current_kind = str(data.get("classification", {}).get("kind") or "")
    classification = data.setdefault("classification", {})
    if current_kind != "film_tv":
        alternatives = list(classification.get("alternatives") or [])
        if current_kind: alternatives.insert(0, {"kind": current_kind, "score": "legacy"})
        classification["alternatives"] = alternatives[:4]
    classification.update({"kind": "film_tv", "category": "Media / Film & TV", "confidence": round(min(0.99, 0.78 + min(score, 8) * 0.025), 2), "signals": signals})
    title = _best_title(data, soup, resource_type)
    if title:
        data.setdefault("identity", {})["title"] = title
        data.setdefault("bookmark", {})["suggested_title"] = title
    description = _best_description(data, soup, blocks)
    if description: data["summary"] = description
    sections = data.setdefault("sections", {})
    sections.pop("editorial", None)
    media = sections.setdefault("film_tv", {})
    resource = sections.setdefault("resource_details", {})
    media["media_type"] = resource_type or "Film / TV"
    if title: media["title"] = title
    if description: media["synopsis"] = description
    normalized: dict[str, Any] = {}
    for target, aliases in MEDIA_FACT_ALIASES.items():
        value = _lookup_fact(mapping, aliases)
        if value: normalized[target] = _split_multi(value) if target in {"genres", "keywords"} else value
    if normalized.get("year"):
        match = re.search(r"\b(18|19|20|21)\d{2}\b", str(normalized["year"]))
        if match: normalized["year"] = match.group(0)
    flat = "\n".join(blocks[:120]) + "\n" + soup.get_text("\n", strip=True)[:30000]
    seasons = sorted({int(x) for x in re.findall(r"\bSeason\s+(\d{1,3})\b", flat, flags=re.I)})
    if seasons:
        normalized["seasons"] = seasons
        normalized["season_count_visible"] = len(seasons)
    vote_match = re.search(r"\b([\d,]+)\s+Votes?\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*\)", flat, flags=re.I)
    if vote_match:
        normalized["vote_count"] = int(vote_match.group(1).replace(",", ""))
        normalized["score"] = vote_match.group(2)
    comment_match = re.search(r"\b([\d,]+)\s+comments?\b", flat, flags=re.I)
    if comment_match: normalized["comment_count_visible"] = int(comment_match.group(1).replace(",", ""))
    people = _person_names(soup)
    if people:
        normalized["people"] = people
        for person in people[:20]: _add_entity(data, "Person/Credit", person)
    directors: list[str] = []
    if normalized.get("director"): directors.extend(_split_multi(normalized["director"], 12))
    for person in people:
        if re.search(rf"\b{re.escape(person)}\b.{{0,80}}\bdirector\b", flat, re.I | re.S): directors.append(person)
    directors = _uniq(directors, 12)
    if directors:
        normalized["directors"] = directors
        for director in directors: _add_entity(data, "Director", director)
    similar_titles: list[str] = []
    boilerplate_anchor_re = re.compile(r"^(?:faq|terms(?: of service)?|privacy(?: policy)?|contact(?: us)?|dmca|disclaimer|telegram|discord|twitter|support)$", re.I)
    boilerplate_href_re = re.compile(r"/(?:faq|terms|privacy|contact|dmca|disclaimer|abuse|rules|help|about|domains)(?:/|$)", re.I)
    for a in soup.find_all("a", href=True):
        if a.find_parent(GENERIC_NAV_PARENTS): continue
        href = str(a.get("href") or "")
        if boilerplate_href_re.search(href): continue
        context = _source_context_for_anchor(a)
        if not context or not re.search(r"\bsimilar\b", context, re.I): continue
        label = _clean(a.get_text(" ", strip=True), 120) or _clean(a.get("title"), 120)
        if label and not boilerplate_anchor_re.match(label) and 1 <= len(label.split()) <= 12: similar_titles.append(label)
    similar_titles = _uniq(similar_titles, 30)
    if similar_titles: normalized["similar_titles"] = similar_titles
    for key, value in normalized.items():
        if value not in (None, "", [], {}):
            media[key] = value
            resource[key] = value
    for label, key in (("Year", "year"), ("Status", "status"), ("Certificate", "certificate"), ("Country", "country"), ("Language", "language"), ("Genres", "genres"), ("Score", "score"), ("Votes", "vote_count"), ("Seasons visible", "season_count_visible")):
        if normalized.get(key) not in (None, "", [], {}): _add_key_fact(data, label, normalized[key])
    tags = [str(tag) for tag in (data.get("tags") or []) if str(tag).casefold() != "article"]
    if "film-tv" not in tags: tags.insert(0, "film-tv")
    for key in ("genres", "keywords"):
        for value in normalized.get(key) or []:
            slug = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
            if 2 <= len(slug) <= 40 and slug not in tags: tags.append(slug)
    data["tags"] = tags[:30]
    bookmark = data.setdefault("bookmark", {})
    bookmark["suggested_folder"] = "Media / Film & TV"
    bookmark["suggested_tags"] = data["tags"]
    if title:
        noun = "TV series" if resource_type == "TV Series" else "movie" if resource_type == "Movie" else "TV/film"
        bookmark["why_it_might_matter"] = f"{noun.capitalize()} reference for {title} with source details preserved for later organization."
    weights = {"title": .14, "summary": .14, "year": .08, "status": .08, "certificate": .06, "country": .05, "language": .05, "genres": .08, "keywords": .05, "seasons": .08, "people": .07, "score": .05, "similar_titles": .03}
    completeness = .16 + (weights["title"] if title else 0) + (weights["summary"] if description else 0)
    for key in ("year", "status", "certificate", "country", "language", "genres", "keywords", "seasons", "people", "score", "similar_titles"):
        if normalized.get(key) not in (None, "", [], {}): completeness += weights[key]
    completeness = round(min(.96, completeness), 2)
    quality = data.setdefault("quality", {})
    quality["extraction_score"] = completeness
    quality["extraction_grade"] = "strong" if completeness >= .75 else "usable" if completeness >= .50 else "weak" if completeness >= .25 else "minimal"
    recovered = set(quality.get("structured_fields_recovered") or [])
    recovered.update(key for key, value in normalized.items() if value not in (None, "", [], {}))
    if title: recovered.add("title")
    if description: recovered.add("description")
    quality["structured_fields_recovered"] = sorted(recovered)
    missing: list[str] = []
    if not title: missing.append("specific title")
    if not description: missing.append("description/synopsis")
    for key in ("year", "status", "genres"):
        if normalized.get(key) in (None, "", [], {}): missing.append(key)
    quality["missing_or_uncertain"] = missing


def universal_finalize(data: dict[str, Any], acquired: Any) -> dict[str, Any]:
    html = str(getattr(acquired, "text", "") or "")
    content_type = str(getattr(acquired, "content_type", "") or "")
    if content_type and not any(token in content_type for token in ("html", "xml", "text")): return data
    if not html: return data
    soup = BeautifulSoup(html, "html.parser")
    facts = _generic_labeled_facts(soup)
    blocks = _visible_text_blocks(soup)
    final_url = str(getattr(acquired, "final_url", "") or data.get("fetch", {}).get("final_url") or "")
    _merge_generic_archive(data, facts, blocks, soup, final_url)
    media_score, signals, resource_type = _media_signals(final_url, soup, facts, blocks)
    if media_score >= 8: _promote_film_tv(data, soup, facts, blocks, media_score, signals, resource_type)
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
