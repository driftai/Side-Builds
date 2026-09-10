from __future__ import annotations

from typing import Any, Callable

from search_compile import *
from search_fusion import canonical_search_url, discover_results_fused, fusion_metadata


def discover_results(
    query: str,
    preferred_engine: str | None = None,
    *,
    target_count: int = 10,
):
    """Compatibility seam: all search inputs now use the same fused retrieval path."""
    return discover_results_fused(query, preferred_engine, target_count=target_count)


def _attach_fusion_metadata(selected: list[dict[str, Any]], main_results: list[SearchResult]) -> None:
    by_url = {
        canonical_search_url(result.url): fusion_metadata(result)
        for result in main_results
        if fusion_metadata(result)
    }
    for source in selected:
        metadata = by_url.get(canonical_search_url(str(source.get("url") or "")), {})
        source["retrieval"] = metadata
        source["fusion_score"] = metadata.get("fusion_score")
        source["engine_consensus"] = metadata.get("engine_consensus")
        source["engine_ranks"] = metadata.get("engine_ranks") or {}


def analyze_search_input(
    raw_input: str,
    analyze_url_fn: Callable[[str], dict[str, Any]],
    *,
    preferred_engine: str | None = None,
) -> dict[str, Any]:
    target = parse_input_target(raw_input)
    if target.mode != "search" or not target.query:
        raise SearchResearchError("Input is not a browser search query.")
    query = target.query
    preferred = preferred_engine or target.preferred_engine or "google"

    main_results, main_attempts = discover_results(query, preferred, target_count=12)
    wikipedia = _find_reference(main_results, "wikipedia")
    fandom = _find_reference(main_results, "fandom")
    reference_attempts: list[dict[str, Any]] = []

    if wikipedia is None:
        wikipedia, attempts = discover_reference(query, "wikipedia", preferred)
        reference_attempts.extend(attempts)
    if fandom is None:
        fandom, attempts = discover_reference(query, "fandom", preferred)
        reference_attempts.extend(attempts)

    selected = select_source_candidates(main_results, wikipedia=wikipedia, fandom=fandom)
    _attach_fusion_metadata(selected, main_results)
    sources: list[dict[str, Any]] = []
    successful: list[dict[str, Any]] = []

    for candidate in selected:
        row = dict(candidate)
        try:
            full = analyze_url_fn(str(candidate["url"]))
            row["status"] = "ok"
            row["analysis"] = _distill_source(full)
            row["_full_data"] = full
            successful.append(row)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = _clean(exc, 500) or "source analysis failed"
            row["analysis"] = {}
        sources.append(row)

    compiled_facts = compile_facts(successful)
    compiled_tags = _compiled_tags(successful)
    dominant_kind = _dominant_kind(successful)
    best_summary = _best_source_summary(successful)

    organic_selected = sum(1 for source in selected if source.get("role") == "organic")
    wikipedia_selected = any(source.get("role") == "wikipedia" for source in selected)
    fandom_selected = any(source.get("role") == "fandom" for source in selected)
    selected_count = len(selected)
    success_count = len(successful)

    success_ratio = success_count / selected_count if selected_count else 0.0
    organic_ratio = organic_selected / ORGANIC_SOURCE_TARGET
    score = round(min(0.96, 0.25 + 0.45 * success_ratio + 0.25 * organic_ratio), 2)
    grade = "strong" if score >= 0.75 else "usable" if score >= 0.50 else "weak" if score >= 0.25 else "minimal"

    missing: list[str] = []
    if organic_selected < ORGANIC_SOURCE_TARGET:
        missing.append("five organic search sources")
    if not wikipedia_selected:
        missing.append("Wikipedia supplemental reference")
    if not fandom_selected:
        missing.append("Fandom supplemental reference")
    if success_count < selected_count:
        missing.append("one or more selected source analyses")

    discovery_attempts = main_attempts + reference_attempts
    any_rendered = any(bool(a.get("rendered")) for a in discovery_attempts if a.get("ok"))
    avg_score_values = [float(a.get("score")) for a in discovery_attempts if a.get("ok") and a.get("score") is not None]
    avg_search_score = round(sum(avg_score_values) / len(avg_score_values), 2) if avg_score_values else 0.0

    discovered_links: list[dict[str, Any]] = []
    selected_urls = {canonical_search_url(str(source.get("url") or "")) for source in selected}
    for result in main_results[:MAX_DISCOVERED_RESULTS]:
        metadata = fusion_metadata(result)
        discovered_links.append({
            "label": result.title,
            "url": result.url,
            "relationship": "external",
            "region": "search_result",
            "search_engine": result.engine,
            "search_rank": result.rank,
            "selected_for_research": canonical_search_url(result.url) in selected_urls,
            "fusion_score": metadata.get("fusion_score"),
            "engine_consensus": metadata.get("engine_consensus"),
            "engine_ranks": metadata.get("engine_ranks") or {},
        })

    source_rows_public = [{key: value for key, value in source.items() if key != "_full_data"} for source in sources]

    tags = ["web-search", "research"]
    for tag in compiled_tags:
        slug = re.sub(r"[^a-z0-9]+", "-", tag.casefold()).strip("-")
        if 2 <= len(slug) <= 40 and slug not in tags:
            tags.append(slug)
        if len(tags) >= 30:
            break

    if best_summary:
        summary = best_summary
    elif successful:
        summary = f"Compiled {success_count} analyzed web sources for the search phrase “{query}”."
    else:
        summary = f"Search discovery for “{query}” did not yield a source that Bookmark Intel could successfully analyze."

    data: dict[str, Any] = {
        "input": {"raw": raw_input, "mode": "search", "query": query, "preferred_engine": preferred},
        "classification": {
            "kind": "web_search_research",
            "category": "Research / Web Search",
            "confidence": 0.99,
            "signals": ["explicit search phrase or recognized browser search URL"],
            "alternatives": [],
        },
        "identity": {"title": query},
        "summary": summary,
        "tags": tags,
        "key_facts": [
            {"label": "Organic sources selected", "value": f"{organic_selected}/{ORGANIC_SOURCE_TARGET}"},
            {"label": "Sources analyzed successfully", "value": f"{success_count}/{selected_count}"},
            {"label": "Wikipedia reference", "value": "selected" if wikipedia_selected else "attempted / unavailable"},
            {"label": "Fandom reference", "value": "selected" if fandom_selected else "attempted / unavailable"},
        ] + ([{"label": "Dominant source type", "value": dominant_kind}] if dominant_kind else []),
        "entities": [],
        "sections": {
            "search_research": {
                "query": query,
                "organic_source_target": ORGANIC_SOURCE_TARGET,
                "organic_sources_selected": organic_selected,
                "supplemental_reference_policy": "Wikipedia + Fandom attempted separately from the five organic sources",
                "sources_selected": selected_count,
                "sources_succeeded": success_count,
                "dominant_source_kind": dominant_kind,
                "compiled_fact_groups": len(compiled_facts),
                "retrieval_ranking": "reciprocal_rank_fusion",
            }
        },
        "links": {
            "important": [
                {"label": source.get("title") or source.get("url"), "url": source.get("url"), "relationship": source.get("role")}
                for source in selected
            ]
        },
        "bookmark": {
            "suggested_folder": "Research / Web Search",
            "suggested_title": query,
            "suggested_tags": tags,
            "why_it_might_matter": f"Compiled browser-search research bundle for {query} using fused search discovery plus analyzed source evidence.",
        },
        "acquisition": {
            "method": "search_aggregation",
            "rendered": any_rendered,
            "acquisition_score": avg_search_score,
            "attempts": [
                {
                    "method": f"search:{attempt.get('engine')}/{attempt.get('method', 'failed')}",
                    "ok": bool(attempt.get("ok")),
                    "score": attempt.get("score", 0),
                    "error": attempt.get("error"),
                    "results_found": attempt.get("results_found", 0),
                }
                for attempt in discovery_attempts
            ],
        },
        "resource_coverage": {
            "html_health_score": avg_search_score,
            "resource_coverage_score": round((organic_ratio * 0.65) + (success_ratio * 0.35), 2) if selected_count else 0.0,
            "needs_deepening": False,
            "search_mode": True,
            "organic_source_target": ORGANIC_SOURCE_TARGET,
            "organic_sources_selected": organic_selected,
            "supplemental_references_selected": int(wikipedia_selected) + int(fandom_selected),
            "sources_analyzed_successfully": success_count,
        },
        "evidence_archive": {
            "capture_note": "Search research evidence preserves fused ranked discovery and the selected source set. Individual source pages use the normal Bookmark Intel URL pipeline.",
            "labeled_facts": [], "grouped_values": [], "structured_collections": [], "interactive_sections": [],
            "source_text_blocks": [], "metadata": [], "links": discovered_links,
            "capture_stats": {
                "labeled_facts_retained": 0, "grouped_value_sets_retained": 0, "source_text_blocks_retained": 0,
                "structured_collections_retained": 0, "interactive_sections_retained": 0,
                "links_retained": len(discovered_links), "metadata_entries_retained": 0,
            },
        },
        "quality": {
            "extraction_score": score,
            "extraction_grade": grade,
            "structured_fields_recovered": ["search_sources", "compiled_facts"] if successful else ["search_sources"],
            "missing_or_uncertain": missing,
        },
        "search_research": {
            "query": query,
            "preferred_engine": preferred,
            "organic_target": ORGANIC_SOURCE_TARGET,
            "organic_selected": organic_selected,
            "wikipedia_selected": wikipedia_selected,
            "fandom_selected": fandom_selected,
            "sources_selected": selected_count,
            "sources_succeeded": success_count,
            "dominant_source_kind": dominant_kind,
            "search_engine_attempts": discovery_attempts,
            "sources": source_rows_public,
            "compiled_facts": compiled_facts,
            "compiled_tags": compiled_tags,
            "retrieval_ranking": "reciprocal_rank_fusion",
            "reference_policy": "Wikipedia and Fandom are supplemental references and never consume one of the five organic slots.",
        },
    }
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
