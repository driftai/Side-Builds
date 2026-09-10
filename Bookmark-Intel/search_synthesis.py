from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in", "is",
    "of", "on", "or", "the", "to", "with", "best", "latest", "wiki", "official",
}
NATIVE_VIDEO_HOSTS = {
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "twitch.tv", "tiktok.com",
}
STREAMING_HOSTS = {
    "crunchyroll.com", "netflix.com", "hulu.com", "disneyplus.com", "primevideo.com",
    "max.com", "hidive.com", "peacocktv.com", "paramountplus.com",
}
ROLE_BONUS = {
    "official": 0.10, "docs": 0.09, "source_code": 0.09, "reference": 0.07,
    "database": 0.06, "package": 0.06, "news": 0.05, "guide": 0.04,
    "source": 0.03, "community_wiki": 0.02, "watch_stream": 0.01,
}
BOILERPLATE = (
    "no meaningful page summary", "javascript is disabled", "from wikipedia, the free encyclopedia",
    "the wiki that anyone can edit", "these cookies", "we use cookies", "cookie settings",
)
VIDEO_FACTS = {
    "channel uploader", "channel name", "uploader", "duration", "duration iso",
    "duration seconds", "upload date", "video id",
}
SOURCE_METADATA = {
    "published", "published date", "modified", "modified date", "reading time", "word count",
    "provider", "provider name",
}
AMBIGUOUS_FACTS = {
    "score", "rating", "average score", "volumes", "volume count", "chapters", "chapter count",
    "episodes", "episode count", "runtime", "rank", "year",
}
PAGE_AUTHOR_KINDS = {"article", "forum_discussion", "general_webpage", "news_article"}


def _text(value: Any, limit: int = 1400) -> str:
    out = re.sub(r"\s+", " ", str(value or "")).strip()
    return out[:limit]


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _tokens(value: Any) -> list[str]:
    return [x for x in _norm(value).split() if len(x) >= 2 and x not in STOPWORDS]


def _match(query: str, text: str) -> float:
    q = set(_tokens(query))
    if not q:
        return 0.0
    hay = set(_norm(text).split())
    overlap = len(q & hay) / len(q)
    if _norm(query) and _norm(query) in _norm(text):
        overlap = max(overlap, 0.98)
    return round(min(1.0, overlap), 3)


def _host(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _host_in(url: str, domains: set[str]) -> bool:
    host = _host(url)
    return any(host == item or host.endswith("." + item) for item in domains)


def _native_video(url: str) -> bool:
    return _host_in(url, NATIVE_VIDEO_HOSTS)


def _boilerplate(value: Any) -> bool:
    low = str(value or "").casefold()
    return any(marker in low for marker in BOILERPLATE)


def _quality(source: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float((source.get("analysis") or {}).get("quality_score") or 0.0)))
    except Exception:
        return 0.0


def _primary_profile(query: str, source: dict[str, Any]) -> tuple[float, bool, list[str]]:
    analysis = source.get("analysis") or {}
    title = _text(analysis.get("title") or source.get("title"), 300)
    summary = _text(analysis.get("summary"), 1400)
    kind = str(analysis.get("kind") or "")
    role = str(source.get("curation_role") or source.get("role") or "source")
    url = str(source.get("url") or "")
    title_match = _match(query, f"{title} {source.get('snippet') or ''} {url}")
    summary_match = _match(query, summary)
    reasons: list[str] = []

    if not summary or _boilerplate(summary) or _boilerplate(title):
        return 0.18, False, ["boilerplate/interstitial content"]
    confidence = 0.82
    embedded_risk = False
    if kind == "video" and not _native_video(url):
        if role == "watch_stream" and _host_in(url, STREAMING_HOSTS):
            confidence = 0.70
            reasons.append("streaming title page; usable as subject evidence but not native-video metadata")
        else:
            confidence = 0.38
            if title_match >= 0.35 or summary_match < 0.35:
                confidence = 0.18
                embedded_risk = True
                reasons.append("embedded media appears to have replaced the page's primary article/topic identity")
    elif kind == "video" and _native_video(url):
        confidence = 0.92
        reasons.append("native video resource")
    if summary_match < 0.15 and title_match >= 0.55:
        confidence = min(confidence, 0.48)
        reasons.append("summary has weak query coverage despite a matching result title")
    if title_match >= 0.75 and summary_match >= 0.35:
        confidence = max(confidence, 0.88)
    return round(confidence, 2), embedded_risk, reasons


def _profile_source(query: str, source: dict[str, Any]) -> dict[str, Any]:
    analysis = source.get("analysis") or {}
    title = _text(analysis.get("title") or source.get("title"), 300)
    summary = _text(analysis.get("summary"), 1400)
    url = str(source.get("url") or "")
    role = str(source.get("curation_role") or source.get("role") or "source")
    title_match = _match(query, f"{title} {source.get('snippet') or ''} {url}")
    summary_match = _match(query, summary)
    prior = float(source.get("subject_relevance_score") or 0.0)
    fusion = float(source.get("fusion_score") or (source.get("retrieval") or {}).get("fusion_score") or 0.0)
    primary, embedded_risk, reasons = _primary_profile(query, source)
    score = (
        0.24 * title_match + 0.14 * summary_match + 0.16 * prior + 0.13 * _quality(source)
        + 0.11 * fusion + 0.16 * primary + ROLE_BONUS.get(role, 0.02)
    )
    score = round(max(0.0, min(1.0, score)), 3)
    prior_note = _text(source.get("curation_note"), 500)
    prior_quarantine = "not synthesis" in prior_note.casefold() or "exclude page evidence" in prior_note.casefold()
    synthesis_eligible = (
        source.get("status") == "ok" and primary >= 0.45 and score >= 0.45
        and not _boilerplate(summary) and not prior_quarantine
    )
    summary_eligible = synthesis_eligible and primary >= 0.60 and score >= 0.52 and bool(summary)
    if prior_quarantine:
        reasons.append("earlier precision pass quarantined this page from synthesis")
    if not synthesis_eligible and not reasons:
        reasons.append("insufficient primary/query evidence for synthesis")
    if source.get("engine_consensus") and int(source.get("engine_consensus") or 0) >= 2:
        reasons.append(f"found by {int(source.get('engine_consensus'))} search engines")
    return {
        "evidence_score": score,
        "title_query_match": title_match,
        "summary_query_match": summary_match,
        "primary_content_confidence": primary,
        "embedded_content_risk": embedded_risk,
        "synthesis_eligible": synthesis_eligible,
        "summary_eligible": summary_eligible,
        "evidence_reasons": reasons,
    }


def _apply_profiles(query: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for source in sources:
        source["pre_synthesis_relevance_score"] = source.get("subject_relevance_score")
        profile = _profile_source(query, source)
        source.update(profile)
        source["subject_relevance_score"] = profile["evidence_score"]
        source["subject_relevance_grade"] = (
            "high" if profile["evidence_score"] >= 0.70 else "medium" if profile["evidence_score"] >= 0.45 else "low"
        )
        if profile["embedded_content_risk"]:
            note = "Embedded-media identity mismatch; retained for provenance but excluded from subject synthesis."
            prior_note = _text(source.get("curation_note"), 500)
            source["curation_note"] = f"{prior_note} {note}".strip()
    return sorted(
        sources,
        key=lambda row: (-float(row.get("evidence_score") or 0.0), -int(row.get("engine_consensus") or 0), int(row.get("rank") or 999)),
    )


def _select_overview(ranked: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    for source in ranked:
        if not source.get("summary_eligible"):
            continue
        summary = _text((source.get("analysis") or {}).get("summary"), 1500)
        if summary:
            return summary, source
    return None, None


def _video_intent(query: str) -> bool:
    terms = set(_tokens(query))
    return bool(terms & {"video", "trailer", "clip", "youtube", "song", "music", "channel", "stream"})


def _page_author_metadata(label: str, sources: list[dict[str, Any]]) -> bool:
    if label not in {"author", "authors", "creator", "creators"}:
        return False
    kinds = {str((source.get("analysis") or {}).get("kind") or "") for source in sources}
    return bool(kinds) and kinds <= PAGE_AUTHOR_KINDS


def _rebuild_facts(query: str, facts: list[dict[str, Any]], sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url = {str(source.get("url") or ""): source for source in sources if source.get("url")}
    out: list[dict[str, Any]] = []
    for fact in facts:
        label = _text(fact.get("label"), 120)
        normalized = _norm(label)
        if not label or normalized in SOURCE_METADATA:
            continue
        values = []
        for value in fact.get("values") or []:
            urls = [str(x) for x in value.get("sources") or [] if x]
            eligible = [by_url[url] for url in urls if url in by_url and by_url[url].get("synthesis_eligible")]
            if not eligible or _page_author_metadata(normalized, eligible):
                continue
            unique_urls = list(dict.fromkeys(str(row.get("url") or "") for row in eligible if row.get("url")))
            count = len(unique_urls)
            top = max(eligible, key=lambda row: float(row.get("evidence_score") or 0.0))
            top_score = float(top.get("evidence_score") or 0.0)
            top_primary = float(top.get("primary_content_confidence") or 0.0)
            if normalized in VIDEO_FACTS and not (_video_intent(query) and _native_video(str(top.get("url") or ""))):
                continue
            if count < 2 and normalized in AMBIGUOUS_FACTS and top_score < 0.82:
                continue
            if count < 2 and (top_score < 0.68 or top_primary < 0.68):
                continue
            values.append({**value, "source_count": count, "sources": unique_urls[:7], "evidence_score": round(top_score, 3)})
        if values:
            values.sort(key=lambda row: (-int(row.get("source_count") or 0), -float(row.get("evidence_score") or 0.0)))
            out.append({**fact, "values": values[:8], "scope": "subject"})
    out.sort(key=lambda row: (-max((int(v.get("source_count") or 0) for v in row.get("values") or []), default=0), _norm(row.get("label"))))
    return out[:24]


def _rebuild_tags(query: str, sources: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    strong: set[str] = set()
    query_terms = set(_tokens(query))
    for source in sources:
        if not source.get("synthesis_eligible"):
            continue
        seen = set()
        for raw in (source.get("analysis") or {}).get("tags") or []:
            clean = _text(raw, 80)
            key = re.sub(r"[^a-z0-9]+", "-", clean.casefold()).strip("-")
            if len(key) < 2 or key in seen or key in {"article", "general-webpage", "webpage", "video"}:
                continue
            seen.add(key)
            counts[key] += 1
            display.setdefault(key, clean)
            if float(source.get("evidence_score") or 0.0) >= 0.74:
                strong.add(key)
    ranked = []
    for key, count in counts.items():
        related = bool(query_terms & set(_norm(key).split()))
        if count >= 2 or related or key in strong:
            ranked.append(key)
    ranked.sort(key=lambda key: (-counts[key], key))
    return [display[key] for key in ranked[:24]]


def _rebuild_key_facts(data: dict[str, Any], research: dict[str, Any], facts: list[dict[str, Any]]) -> None:
    keep = []
    protected = {
        "organic sources selected", "sources analyzed successfully", "wikipedia reference",
        "fandom reference", "inferred subject type",
    }
    for row in data.get("key_facts") or []:
        if _norm(row.get("label")) in protected:
            keep.append(row)
    synthesis = research.get("synthesis") or {}
    keep.extend([
        {"label": "Synthesis confidence", "value": f"{round(float(synthesis.get('confidence') or 0.0) * 100)}%"},
        {"label": "Evidence-eligible sources", "value": f"{synthesis.get('eligible_sources', 0)}/{research.get('sources_succeeded', 0)}"},
    ])
    if synthesis.get("top_source_title"):
        keep.append({"label": "Top research source", "value": synthesis["top_source_title"]})
    if synthesis.get("warning_count"):
        keep.append({"label": "Source quality warnings", "value": str(synthesis["warning_count"])})
    for fact in facts[:5]:
        values = fact.get("values") or []
        if values:
            first = values[0]
            keep.append({"label": fact.get("label"), "value": f"{first.get('value')} ({first.get('source_count')} source{'s' if first.get('source_count') != 1 else ''})"})
    data["key_facts"] = keep[:14]


def finalize_search_synthesis(data: dict[str, Any]) -> dict[str, Any]:
    """Unify retrieval, relevance, page-primary evidence and synthesis for every search result."""
    research = data.get("search_research")
    if not isinstance(research, dict):
        return data
    query = _text(research.get("query") or (data.get("input") or {}).get("query"), 500)
    sources = list(research.get("sources") or [])
    ranked = _apply_profiles(query, sources)
    eligible_ranked = [row for row in ranked if row.get("synthesis_eligible")]
    summary, summary_source = _select_overview(eligible_ranked)
    facts = _rebuild_facts(query, list(research.get("compiled_facts") or []), sources)
    tags = _rebuild_tags(query, sources)
    warnings = []
    for row in ranked:
        if row.get("status") != "ok" or row.get("synthesis_eligible"):
            continue
        reasons = []
        prior_note = _text(row.get("curation_note"), 500)
        if prior_note:
            reasons.append(prior_note)
        reasons.extend(row.get("evidence_reasons") or [])
        warnings.append({
            "url": row.get("url"),
            "title": (row.get("analysis") or {}).get("title") or row.get("title"),
            "reason": "; ".join(dict.fromkeys(reasons)) or "weak synthesis evidence",
        })
    top_scores = [float(row.get("evidence_score") or 0.0) for row in eligible_ranked[:3]]
    confidence = round(sum(top_scores) / len(top_scores), 2) if top_scores else 0.0
    top_source = eligible_ranked[0] if eligible_ranked else (ranked[0] if ranked else None)

    if summary:
        data["summary"] = summary
    elif eligible_ranked:
        data["summary"] = f"Bookmark Intel found {len(eligible_ranked)} synthesis-eligible sources for “{query}”, but none had a reliable query-focused overview."
    else:
        data["summary"] = f"Search discovery for “{query}” found sources, but none passed the evidence threshold for a reliable synthesized overview."

    research["sources"] = sources
    research["compiled_facts"] = facts
    research["subject_facts"] = facts
    research["compiled_tags"] = tags
    research["source_ranking"] = [
        {
            "rank": index,
            "url": row.get("url"),
            "title": (row.get("analysis") or {}).get("title") or row.get("title"),
            "role": row.get("curation_role") or row.get("role"),
            "evidence_score": row.get("evidence_score"),
            "primary_content_confidence": row.get("primary_content_confidence"),
            "engine_consensus": row.get("engine_consensus") or 0,
            "synthesis_eligible": bool(row.get("synthesis_eligible")),
            "summary_eligible": bool(row.get("summary_eligible")),
        }
        for index, row in enumerate(ranked, 1)
    ]
    research["overview_source"] = summary_source.get("url") if summary_source else None
    research["overview_subject_relevance"] = summary_source.get("evidence_score") if summary_source else 0.0
    research["synthesis"] = {
        "version": 1,
        "strategy": "RRF retrieval + query-focused evidence reranking + page-primary filtering",
        "confidence": confidence,
        "eligible_sources": len(eligible_ranked),
        "summary_eligible_sources": sum(1 for row in sources if row.get("summary_eligible")),
        "top_source_url": top_source.get("url") if top_source else None,
        "top_source_title": ((top_source.get("analysis") or {}).get("title") or top_source.get("title")) if top_source else None,
        "overview_source": summary_source.get("url") if summary_source else None,
        "warning_count": len(warnings),
        "warnings": warnings[:12],
    }
    research["synthesis_version"] = 1
    research["precision_policy"] = "shared evidence score drives overview, subject facts, tags and workspace provenance"

    final_tags = ["web-search", "research"]
    for tag in tags:
        slug = re.sub(r"[^a-z0-9]+", "-", str(tag).casefold()).strip("-")
        if 2 <= len(slug) <= 40 and slug not in final_tags:
            final_tags.append(slug)
    data["tags"] = final_tags[:26]
    data.setdefault("bookmark", {})["suggested_tags"] = data["tags"]

    section = data.setdefault("sections", {}).setdefault("search_research", {})
    section["retrieval_ranking"] = research.get("retrieval_ranking") or "reciprocal_rank_fusion"
    section["synthesis_version"] = 1
    section["synthesis_confidence"] = confidence
    section["evidence_eligible_sources"] = len(eligible_ranked)
    section["source_quality_warnings"] = len(warnings)

    _rebuild_key_facts(data, research, facts)
    quality = data.setdefault("quality", {})
    quality["pre_synthesis_score"] = quality.get("extraction_score")
    quality["semantic_synthesis_score"] = confidence
    quality["extraction_score"] = confidence
    quality["extraction_grade"] = "strong" if confidence >= 0.75 else "usable" if confidence >= 0.50 else "weak" if confidence >= 0.25 else "minimal"
    quality["quality_basis"] = "fused retrieval + shared source evidence + page-primary filtering + query-focused synthesis"
    return data


def render_search_synthesis_markdown(data: dict[str, Any]) -> str:
    research = data.get("search_research") or {}
    synthesis = research.get("synthesis") or {}
    if not synthesis.get("version"):
        return ""
    lines = ["", "## Search synthesis", f"- **Strategy:** {synthesis.get('strategy')}"]
    lines.append(f"- **Synthesis confidence:** {synthesis.get('confidence', 0)}")
    lines.append(f"- **Evidence-eligible sources:** {synthesis.get('eligible_sources', 0)}/{research.get('sources_succeeded', 0)}")
    if synthesis.get("overview_source"):
        lines.append(f"- **Overview source:** {synthesis.get('overview_source')}")
    ranking = research.get("source_ranking") or []
    if ranking:
        lines.extend(["", "### Evidence-ranked sources"])
        for row in ranking[:7]:
            state = "eligible" if row.get("synthesis_eligible") else "provenance only"
            lines.append(
                f"- **{row.get('rank')}. {row.get('title')}:** evidence {row.get('evidence_score')} · "
                f"primary {row.get('primary_content_confidence')} · engines {row.get('engine_consensus', 0)} · {state}"
            )
    warnings = synthesis.get("warnings") or []
    if warnings:
        lines.extend(["", "### Source quality warnings"])
        for row in warnings:
            lines.append(f"- **{row.get('title')}:** {row.get('reason')}")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["finalize_search_synthesis", "render_search_synthesis_markdown"]
