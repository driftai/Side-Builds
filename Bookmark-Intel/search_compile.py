from __future__ import annotations

from collections import Counter
from typing import Any

from search_discovery import *


def _find_reference(results: list[SearchResult], kind: str) -> SearchResult | None:
    for result in results:
        if _reference_kind(result.url) == kind:
            return result
    return None


def discover_reference(query: str, kind: str, preferred_engine: str | None) -> tuple[SearchResult | None, list[dict[str, Any]]]:
    domain = "wikipedia.org" if kind == "wikipedia" else "fandom.com"
    targeted_query = f"site:{domain} {query}"
    results, attempts = discover_results(targeted_query, preferred_engine, target_count=5)
    return _find_reference(results, kind), attempts


def _distill_source(data: dict[str, Any]) -> dict[str, Any]:
    c = data.get("classification") or {}
    i = data.get("identity") or {}
    q = data.get("quality") or {}
    return {
        "title": i.get("title"),
        "kind": c.get("kind"),
        "category": c.get("category"),
        "summary": data.get("summary"),
        "key_facts": list(data.get("key_facts") or [])[:20],
        "tags": list(data.get("tags") or [])[:30],
        "quality_score": q.get("extraction_score"),
        "quality_grade": q.get("extraction_grade"),
    }


def _render_value(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, list):
        simple = [_clean(x, 180) for x in value if not isinstance(x, (dict, list, tuple, set))]
        simple = [x for x in simple if x]
        return ", ".join(simple[:20]) if simple else None
    if isinstance(value, dict):
        return None
    return _clean(value, 500)


def _fact_rows_from_source(data: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(label: Any, value: Any) -> None:
        clean_label = _clean(label, 120)
        clean_value = _render_value(value)
        if not clean_label or not clean_value:
            return
        key = (clean_label.casefold().strip(" :"), clean_value.casefold())
        if key in seen:
            return
        seen.add(key)
        out.append((clean_label.strip(" :"), clean_value))

    for fact in data.get("key_facts") or []:
        if isinstance(fact, dict):
            add(fact.get("label"), fact.get("value"))

    sections = data.get("sections") or {}
    chosen_sections: list[dict[str, Any]] = []
    resource = sections.get("resource_details")
    if isinstance(resource, dict):
        chosen_sections.append(resource)
    for name, section in sections.items():
        if name == "resource_details" or not isinstance(section, dict):
            continue
        if name in {"anime_manga", "film_tv", "software", "product", "gaming", "academic", "editorial"}:
            chosen_sections.append(section)
            break

    skip = {
        "title", "synopsis", "description", "people", "similar_titles", "alternative_titles",
        "poster", "cover", "image", "images", "links", "chapters", "comments", "reviews",
    }
    for section in chosen_sections:
        for key, value in list(section.items())[:40]:
            if str(key).casefold() in skip:
                continue
            add(str(key).replace("_", " ").strip().title(), value)
    return out[:50]


def compile_facts(successful_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label: dict[str, dict[str, Any]] = {}
    for source in successful_sources:
        data = source.get("_full_data") or {}
        url = str(source.get("url") or "")
        for label, value in _fact_rows_from_source(data):
            norm_label = re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()
            slot = by_label.setdefault(norm_label, {"label": label, "values": {}})
            row = slot["values"].setdefault(value.casefold(), {"value": value, "sources": []})
            if url and url not in row["sources"]:
                row["sources"].append(url)

    compiled: list[dict[str, Any]] = []
    for slot in by_label.values():
        values = list(slot["values"].values())
        values.sort(key=lambda row: (-len(row["sources"]), row["value"].casefold()))
        compiled.append({
            "label": slot["label"],
            "values": [
                {"value": row["value"], "source_count": len(row["sources"]), "sources": row["sources"][:7]}
                for row in values[:8]
            ],
        })
    compiled.sort(key=lambda row: (
        -max((v.get("source_count", 0) for v in row.get("values") or []), default=0),
        str(row.get("label") or "").casefold(),
    ))
    return compiled[:50]


def _compiled_tags(successful_sources: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for source in successful_sources:
        analysis = source.get("analysis") or {}
        seen_source: set[str] = set()
        for tag in analysis.get("tags") or []:
            clean = _clean(tag, 80)
            if not clean:
                continue
            key = clean.casefold()
            if key in seen_source:
                continue
            seen_source.add(key)
            display.setdefault(key, clean)
            counts[key] += 1
    ordered = sorted(counts, key=lambda key: (-counts[key], display[key].casefold()))
    return [display[key] for key in ordered[:30]]


def _dominant_kind(successful_sources: list[dict[str, Any]]) -> str | None:
    kinds = [str((source.get("analysis") or {}).get("kind") or "") for source in successful_sources if (source.get("analysis") or {}).get("kind")]
    if not kinds:
        return None
    return Counter(kinds).most_common(1)[0][0]


def _best_source_summary(successful_sources: list[dict[str, Any]]) -> str | None:
    candidates: list[tuple[float, int, str]] = []
    for index, source in enumerate(successful_sources):
        analysis = source.get("analysis") or {}
        summary = _clean(analysis.get("summary"), 1200)
        if not summary or "no meaningful page summary" in summary.casefold():
            continue
        try:
            q = float(analysis.get("quality_score"))
        except Exception:
            q = 0.0
        candidates.append((q, -index, summary))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def _build_search_markdown(data: dict[str, Any]) -> str:
    research = data.get("search_research") or {}
    query = research.get("query") or "Search"
    lines = [f"# Search research: {query}", ""]
    lines.append(f"- **Input:** {data.get('input', {}).get('raw', query)}")
    lines.append(f"- **Type:** {data.get('classification', {}).get('kind', 'web_search_research')}")
    lines.append(f"- **Category:** {data.get('classification', {}).get('category', 'Research / Web Search')}")
    lines.append(f"- **Organic sources selected:** {research.get('organic_selected', 0)}/{ORGANIC_SOURCE_TARGET}")
    lines.append(f"- **Wikipedia supplemental reference:** {'selected' if research.get('wikipedia_selected') else 'attempted / unavailable'}")
    lines.append(f"- **Fandom supplemental reference:** {'selected' if research.get('fandom_selected') else 'attempted / unavailable'}")
    lines.append(f"- **Source analyses succeeded:** {research.get('sources_succeeded', 0)}/{research.get('sources_selected', 0)}")
    if research.get("dominant_source_kind"):
        lines.append(f"- **Dominant analyzed source type:** {research.get('dominant_source_kind')}")
    lines.extend(["", "## Compiled overview", str(data.get("summary") or "No source summary could be recovered.")])

    sources = research.get("sources") or []
    if sources:
        lines.extend(["", "## Sources"])
        for index, source in enumerate(sources, 1):
            role = source.get("role", "source")
            status = source.get("status", "unknown")
            title = (source.get("analysis") or {}).get("title") or source.get("title") or source.get("url")
            lines.append(f"### {index}. {title}")
            lines.append(f"- **Role:** {role}")
            lines.append(f"- **URL:** {source.get('url')}")
            lines.append(f"- **Analysis:** {status}")
            analysis = source.get("analysis") or {}
            if analysis.get("kind"):
                lines.append(f"- **Type:** {analysis.get('kind')}")
            if analysis.get("quality_score") is not None:
                lines.append(f"- **Extraction quality:** {analysis.get('quality_score')}")
            if analysis.get("summary"):
                lines.append(f"- **Summary:** {analysis.get('summary')}")
            if source.get("error"):
                lines.append(f"- **Error:** {source.get('error')}")

    compiled = research.get("compiled_facts") or []
    if compiled:
        lines.extend(["", "## Compiled facts"])
        for fact in compiled[:30]:
            rendered = [
                f"{value.get('value')} ({value.get('source_count')} source{'s' if value.get('source_count') != 1 else ''})"
                for value in (fact.get("values") or [])[:5]
            ]
            lines.append(f"- **{fact.get('label')}:** " + " | ".join(rendered))

    attempts = research.get("search_engine_attempts") or []
    if attempts:
        lines.extend(["", "## Search discovery"])
        for attempt in attempts:
            if attempt.get("ok"):
                lines.append(f"- **{attempt.get('engine')}:** {attempt.get('results_found', 0)} results via {attempt.get('method', 'unknown')} (page score {attempt.get('score', 'unknown')})")
            else:
                lines.append(f"- **{attempt.get('engine')}:** failed — {attempt.get('error', 'unknown error')}")

    quality = data.get("quality") or {}
    lines.extend(["", "## Extraction quality", f"- **Score:** {quality.get('extraction_score', 0)}", f"- **Grade:** {quality.get('extraction_grade', 'unknown')}"])
    missing = quality.get("missing_or_uncertain") or []
    if missing:
        lines.append("- **Still missing/uncertain:** " + ", ".join(str(x) for x in missing))
    return "\n".join(lines).rstrip() + "\n"


def render_search_markdown(data: dict[str, Any]) -> str:
    return _build_search_markdown(data)


__all__ = [name for name in globals() if not name.startswith("__")]
