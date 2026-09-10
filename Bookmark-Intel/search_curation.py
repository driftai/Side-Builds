from __future__ import annotations

from search_curation_evidence import *


def _curate_tags(query: str, sources: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    max_relevance: dict[str, float] = defaultdict(float)
    specialized: set[str] = set()

    for source in sources:
        if source.get("status") != "ok":
            continue
        analysis = source.get("analysis") or {}
        relevance = float(source.get("subject_relevance_score") or 0.0)
        kind = str(analysis.get("kind") or "")
        seen: set[str] = set()
        for raw in analysis.get("tags") or []:
            clean = _clean(raw, 80)
            if not clean:
                continue
            key = re.sub(r"[^a-z0-9]+", "-", clean.casefold()).strip("-")
            if len(key) < 2 or key in seen or key in ALWAYS_SOURCE_TAGS:
                continue
            seen.add(key)
            display.setdefault(key, clean)
            counts[key] += 1
            max_relevance[key] = max(max_relevance[key], relevance)
            if kind in SPECIALIZED_KINDS and relevance >= 0.45:
                specialized.add(key)

    query_tokens = set(_query_tokens(query))
    kept: list[str] = []
    for key in counts:
        tag_tokens = set(_norm(key).split())
        query_related = bool(query_tokens & tag_tokens)
        if counts[key] >= 2 or query_related or key in specialized or max_relevance[key] >= 0.78:
            kept.append(key)
    kept.sort(key=lambda key: (-counts[key], -max_relevance[key], key))
    return [display[key] for key in kept[:28]]


def _link_role_from_text(title: str, url: str, selected_source: dict[str, Any] | None) -> str:
    if selected_source:
        return _source_role(selected_source)
    pseudo = {"title": title, "url": url, "analysis": {"title": title}, "role": "discovered"}
    return _source_role(pseudo)


def _curate_links(query: str, data: dict[str, Any], sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    archive_links = list((data.get("evidence_archive") or {}).get("links") or [])
    selected_by_url = _source_index(sources)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in archive_links:
        url = str(raw.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        title = _clean(raw.get("label"), 300) or url
        selected_source = selected_by_url.get(url)
        role = _link_role_from_text(title, url, selected_source)
        overlap = _token_overlap(query, f"{title} {url}")
        try:
            rank = int(raw.get("search_rank") or 99)
        except Exception:
            rank = 99
        selected = bool(raw.get("selected_for_research")) or selected_source is not None
        relevance = float(selected_source.get("subject_relevance_score") or 0.0) if selected_source else 0.0

        score = 0.12 + 0.28 * overlap + 0.18 * relevance
        if selected:
            score += 0.22
        if rank < 99:
            score += max(0.0, 0.16 - min(rank - 1, 15) * 0.01)
        if role == "official":
            score += 0.16
        elif role in {"watch_stream", "database", "reference", "docs", "source_code", "package"}:
            score += 0.08
        elif role in {"guide", "community_wiki", "news"}:
            score += 0.04

        reason_bits = ["analyzed source" if selected else "discovered result"]
        if role != "source":
            reason_bits.append(ROLE_LABELS[role].casefold())
        if overlap >= 0.5:
            reason_bits.append("strong query match")
        if relevance >= 0.65:
            reason_bits.append("high subject relevance")

        relationship = str(selected_source.get("role") or "organic") if selected_source else "discovered"
        candidates.append({
            "label": f"{ROLE_LABELS[role]} — {title}",
            "original_label": title,
            "url": url,
            "relationship": relationship,
            "curation_role": role,
            "curation_score": round(min(1.0, score), 2),
            "reason": ", ".join(reason_bits),
            "selected_for_research": selected,
            "search_rank": None if rank == 99 else rank,
            "source_relevance_score": relevance if selected_source else None,
            "source_kind": (selected_source.get("analysis") or {}).get("kind") if selected_source else None,
        })

    candidates.sort(key=lambda row: (
        -float(row.get("curation_score") or 0.0),
        int(row.get("search_rank") or 999),
        str(row.get("label") or "").casefold(),
    ))

    out: list[dict[str, Any]] = []
    host_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    for row in candidates:
        host = _host(str(row.get("url") or ""))
        role = str(row.get("curation_role") or "source")
        if host_counts[host] >= 2 or role_counts[role] >= 3:
            continue
        host_counts[host] += 1
        role_counts[role] += 1
        out.append(row)
        if len(out) >= MAX_CURATED_LINKS:
            break
    return out


def _infer_subject_type(sources: list[dict[str, Any]], tags: list[str]) -> tuple[str | None, list[str]]:
    weighted: Counter[str] = Counter()
    for source in sources:
        if source.get("status") != "ok":
            continue
        kind = str((source.get("analysis") or {}).get("kind") or "")
        relevance = float(source.get("subject_relevance_score") or 0.0)
        if kind in SPECIALIZED_KINDS and relevance >= 0.35:
            weighted[kind] += max(1, int(round(relevance * 10)))

    tag_set = {re.sub(r"[^a-z0-9]+", "-", str(x).casefold()).strip("-") for x in tags}
    signals: list[str] = []
    if weighted:
        signals.append("specialized analyzed source types")
    if {"anime", "manga", "anime-manga", "film-tv"} & tag_set or weighted.get("anime_manga") or weighted.get("film_tv"):
        signals.append("media-oriented cross-source tags")
        return "media", signals
    if weighted.get("gaming"):
        return "gaming", signals
    if weighted.get("product"):
        return "product", signals
    if weighted.get("academic_paper"):
        return "research", signals
    if weighted.get("github_repository") or weighted.get("software_tool"):
        return "technology", signals
    if weighted.get("video"):
        return "video", signals
    return None, signals


def _top_fact_key_rows(facts: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for fact in facts:
        values = fact.get("values") or []
        if not values:
            continue
        best = values[0]
        value = _clean(best.get("value"), 500)
        if not value:
            continue
        count = int(best.get("source_count") or 0)
        suffix = f" ({count} source{'s' if count != 1 else ''})" if count else ""
        rows.append({"label": str(fact.get("label") or "Fact"), "value": value + suffix})
        if len(rows) >= limit:
            break
    return rows


def _semantic_quality(sources: list[dict[str, Any]], summary_score: float, facts: list[dict[str, Any]], links: list[dict[str, Any]]) -> tuple[float, str]:
    if not sources:
        return 0.2, "minimal"
    success = [s for s in sources if s.get("status") == "ok"]
    success_ratio = len(success) / len(sources)
    relevant_ratio = (
        sum(1 for s in success if float(s.get("subject_relevance_score") or 0.0) >= 0.45) / len(success)
        if success else 0.0
    )
    fact_score = min(1.0, len(facts) / 8)
    link_score = min(1.0, len(links) / 8)
    score = min(0.95, 0.12 + 0.20 * success_ratio + 0.22 * relevant_ratio + 0.22 * summary_score + 0.14 * fact_score + 0.10 * link_score)
    score = round(score, 2)
    grade = "strong" if score >= 0.75 else "usable" if score >= 0.50 else "weak" if score >= 0.25 else "minimal"
    return score, grade


def finalize_search_research(data: dict[str, Any]) -> dict[str, Any]:
    """Curate a completed deterministic search bundle around the searched subject."""
    research = data.get("search_research")
    if not isinstance(research, dict):
        return data

    query = _clean(research.get("query") or (data.get("input") or {}).get("query"), 500) or ""
    sources = list(research.get("sources") or [])

    for source in sources:
        relevance = _source_relevance(query, source)
        source["subject_relevance_score"] = relevance
        source["subject_relevance_grade"] = "high" if relevance >= 0.70 else "medium" if relevance >= 0.45 else "low"
        source["curation_role"] = _source_role(source)
        if source.get("status") != "ok":
            source["curation_note"] = "Selected source failed analysis; retained for provenance."
        elif relevance < 0.35:
            source["curation_note"] = "Low subject relevance; retained as source provenance, not trusted for synthesis."
        elif _summary_is_boilerplate((source.get("analysis") or {}).get("summary")):
            source["curation_note"] = "Page summary is boilerplate; excluded from compiled overview."
        else:
            source["curation_note"] = "Eligible subject source."

    research["sources"] = sources
    subject_facts = _curate_facts(list(research.get("compiled_facts") or []), sources)
    subject_tags = _curate_tags(query, sources)
    curated_links = _curate_links(query, data, sources)
    summary, summary_score, summary_source = _best_summary(query, sources)
    subject_type, subject_signals = _infer_subject_type(sources, subject_tags)

    if summary:
        data["summary"] = summary
    research["compiled_facts_raw"] = list(research.get("compiled_facts") or [])
    research["compiled_facts"] = subject_facts
    research["subject_facts"] = subject_facts
    research["compiled_tags_raw"] = list(research.get("compiled_tags") or [])
    research["compiled_tags"] = subject_tags
    research["curated_links"] = curated_links
    research["overview_source"] = summary_source
    research["overview_subject_relevance"] = summary_score
    research["subject_type"] = subject_type
    research["subject_signals"] = subject_signals
    research["curation_version"] = 1

    tags = ["web-search", "research"]
    for tag in subject_tags:
        slug = re.sub(r"[^a-z0-9]+", "-", str(tag).casefold()).strip("-")
        if 2 <= len(slug) <= 40 and slug not in tags:
            tags.append(slug)
        if len(tags) >= 30:
            break
    data["tags"] = tags
    data.setdefault("bookmark", {})["suggested_tags"] = tags

    if curated_links:
        data.setdefault("links", {})["important"] = curated_links

    section = data.setdefault("sections", {}).setdefault("search_research", {})
    section["subject_type"] = subject_type
    section["subject_fact_groups"] = len(subject_facts)
    section["curated_link_count"] = len(curated_links)
    section["overview_source"] = summary_source
    section["overview_subject_relevance"] = summary_score

    existing_key_facts = []
    for row in data.get("key_facts") or []:
        if not isinstance(row, dict):
            continue
        label = _norm(row.get("label"))
        if label in {"organic sources selected", "sources analyzed successfully", "wikipedia reference", "fandom reference"}:
            existing_key_facts.append(row)
    if subject_type:
        existing_key_facts.append({"label": "Inferred subject type", "value": subject_type})
    existing_key_facts.extend(_top_fact_key_rows(subject_facts))
    data["key_facts"] = existing_key_facts[:14]

    score, grade = _semantic_quality(sources, summary_score, subject_facts, curated_links)
    quality = data.setdefault("quality", {})
    quality["pipeline_execution_score"] = quality.get("extraction_score")
    quality["extraction_score"] = score
    quality["extraction_grade"] = grade
    quality["semantic_curation_score"] = score
    quality["quality_basis"] = "search source coverage + subject relevance + overview + subject facts + curated links"
    recovered = set(str(x) for x in (quality.get("structured_fields_recovered") or []))
    recovered.update({"search_sources", "curated_links"})
    if subject_facts:
        recovered.add("subject_facts")
    if summary:
        recovered.add("curated_overview")
    quality["structured_fields_recovered"] = sorted(recovered)
    return data


def render_search_curation_markdown(data: dict[str, Any]) -> str:
    research = data.get("search_research") or {}
    if not research.get("curation_version"):
        return ""

    lines: list[str] = ["", "## Research curation"]
    if research.get("subject_type"):
        lines.append(f"- **Inferred subject type:** {research.get('subject_type')}")
    if research.get("overview_source"):
        lines.append(f"- **Overview source:** {research.get('overview_source')}")
    if research.get("overview_subject_relevance") is not None:
        lines.append(f"- **Overview subject relevance:** {research.get('overview_subject_relevance')}")

    sources = research.get("sources") or []
    if sources:
        lines.extend(["", "### Source relevance"])
        for source in sources:
            title = (source.get("analysis") or {}).get("title") or source.get("title") or source.get("url")
            lines.append(
                f"- **{title}:** {source.get('subject_relevance_grade', 'unknown')} "
                f"({source.get('subject_relevance_score', 0)}) · {ROLE_LABELS.get(source.get('curation_role'), 'Source')}"
            )

    links = research.get("curated_links") or []
    if links:
        lines.extend(["", "## Curated links"])
        for link in links:
            lines.append(f"- [{link.get('label')}]({link.get('url')}) — {link.get('reason', 'curated search result')}")

    return "\n".join(lines).rstrip() + "\n"


__all__ = [name for name in globals() if not name.startswith("__")]
