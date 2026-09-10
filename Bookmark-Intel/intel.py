from __future__ import annotations

import re
from typing import Any

from acquisition import AcquisitionError, acquire_url
from analysis_pipeline import run_concrete_resource_pipeline
from enrichment import enrich_analysis
from provider_enrichment import apply_provider_evidence, probe_oembed
from source_capture import probe_provider_extended
from search_curation import finalize_search_research, render_search_curation_markdown
from search_precision import finalize_search_precision
from search_research import (
    SearchResearchError,
    analyze_search_input,
    parse_input_target,
    render_search_markdown,
)
from intel_legacy import *  # noqa: F401,F403 - preserve the v0.1 public surface
from intel_legacy import AnalyzeError, FetchResult, analyze_html as _legacy_analyze_html, render_markdown as _legacy_render_markdown


def fetch_url(url: str) -> FetchResult:
    """Compatibility fetch entry point backed by the progressive acquisition pipeline."""
    try:
        acquired = acquire_url(url)
    except AcquisitionError as exc:
        raise AnalyzeError(str(exc)) from exc
    return FetchResult(
        requested_url=acquired.requested_url,
        final_url=acquired.final_url,
        redirects=acquired.redirects,
        status_code=acquired.status_code,
        content_type=acquired.content_type,
        text=acquired.text,
        byte_count=acquired.byte_count,
    )


def analyze_html(fetch: FetchResult) -> dict[str, Any]:
    """Keep deterministic fixture behavior unchanged for regression tests."""
    return _legacy_analyze_html(fetch)


def _analyze_concrete_url(url: str) -> dict[str, Any]:
    """Analyze one concrete public resource URL without search-fanout recursion."""
    try:
        provider = probe_provider_extended(url)
    except AcquisitionError as exc:
        raise AnalyzeError(str(exc)) from exc
    except Exception:
        provider = None

    try:
        acquired = acquire_url(url, allow_browsers=not bool(provider and provider.sufficient))
    except AcquisitionError as exc:
        raise AnalyzeError(str(exc)) from exc

    fetch = FetchResult(
        requested_url=acquired.requested_url,
        final_url=acquired.final_url,
        redirects=acquired.redirects,
        status_code=acquired.status_code,
        content_type=acquired.content_type,
        text=acquired.text,
        byte_count=acquired.byte_count,
    )
    data = _legacy_analyze_html(fetch)
    data = enrich_analysis(data, acquired)
    data = apply_provider_evidence(data, provider)

    try:
        oembed = probe_oembed(acquired.text, acquired.final_url)
    except Exception:
        oembed = None
    data = apply_provider_evidence(data, oembed)

    provenance = []
    if provider and provider.matched:
        provenance.append(provider.diagnostics())
    if oembed and oembed.matched:
        provenance.append(oembed.diagnostics())
    if provenance:
        data["provider_enrichments"] = provenance
        data["provider_enrichment"] = provenance[0]

    return run_concrete_resource_pipeline(data, acquired, provider)


def _analyze_search_bundle(raw_input: str) -> dict[str, Any]:
    """Run bounded search research, then curate and precision-clean subject evidence."""
    data = analyze_search_input(raw_input, _analyze_concrete_url)
    data = finalize_search_research(data)
    return finalize_search_precision(data)


def analyze_url(url: str) -> dict[str, Any]:
    """Analyze one concrete public URL or recognized browser-search URL."""
    try:
        target = parse_input_target(url)
    except SearchResearchError as exc:
        raise AnalyzeError(str(exc)) from exc
    if target.mode == "search" and target.query:
        try:
            return _analyze_search_bundle(url)
        except SearchResearchError as exc:
            raise AnalyzeError(str(exc)) from exc
    return _analyze_concrete_url(url)


def analyze_input(raw_input: str) -> dict[str, Any]:
    """Analyze either one public URL or one browser-search phrase/search-engine URL.

    Search mode deliberately fans one user input out to at most five organic result sources
    plus supplemental Wikipedia and Fandom reference attempts. Concrete result URLs still
    run through the normal one-URL analyzer and retain all of its safety boundaries.
    """
    try:
        target = parse_input_target(raw_input)
    except SearchResearchError as exc:
        raise AnalyzeError(str(exc)) from exc
    if target.mode == "url" and target.url:
        return _analyze_concrete_url(target.url)
    try:
        return _analyze_search_bundle(raw_input)
    except SearchResearchError as exc:
        raise AnalyzeError(str(exc)) from exc


def _without_legacy_quality_block(markdown: str) -> str:
    return re.sub(
        r"\n## Extraction quality\n(?:- [^\n]*\n?)+(?=\n## |\Z)",
        "\n",
        markdown,
        count=1,
    ).rstrip()


def render_markdown(data: dict[str, Any]) -> str:
    if data.get("search_research"):
        base = render_search_markdown(data).rstrip()
        curation = render_search_curation_markdown(data).strip()
        return base + ("\n\n" + curation if curation else "") + "\n"

    base = _without_legacy_quality_block(_legacy_render_markdown(data))
    acquisition = data.get("acquisition") or {}
    quality = data.get("quality") or {}
    provider = data.get("provider_enrichment") or {}
    archive = data.get("evidence_archive") or {}
    profile = data.get("resource_profile") or {}
    coverage = data.get("resource_coverage") or {}

    extra: list[str] = []

    if profile and any(profile.get(k) for k in ("media_family", "format", "source_material")):
        extra.extend(["", "## Resource profile"])
        if profile.get("media_family"):
            extra.append(f"- **Media family:** {profile.get('media_family')}")
        if profile.get("format"):
            extra.append(f"- **Format:** {profile.get('format')}")
        if profile.get("source_material"):
            extra.append(f"- **Source material:** {profile.get('source_material')}")
        signals = profile.get("signals") or []
        if signals:
            extra.append("- **Facet signals:** " + ", ".join(str(x) for x in signals))

    if acquisition:
        extra.extend(
            [
                "",
                "## Acquisition",
                f"- **Method:** {acquisition.get('method', 'unknown')}",
                f"- **JavaScript-rendered fallback used:** {'yes' if acquisition.get('rendered') else 'no'}",
                f"- **Coverage-rendered same-resource sections used:** {'yes' if acquisition.get('coverage_rendered_fallback_used') else 'no'}",
                f"- **Raw page acquisition score:** {acquisition.get('acquisition_score', 'unknown')}",
            ]
        )
        attempts = acquisition.get("attempts") or []
        if attempts:
            compact = []
            for attempt in attempts:
                state = "ok" if attempt.get("ok") else "failed"
                detail = f"score={attempt.get('score')}" if attempt.get("ok") else attempt.get("error", "unknown error")
                compact.append(f"{attempt.get('method')}: {state} ({detail})")
            extra.append("- **Fallback path:** " + " → ".join(compact))

    if coverage:
        extra.extend(
            [
                "",
                "## Resource coverage",
                f"- **HTML health score:** {coverage.get('html_health_score', 'unknown')}",
                f"- **Resource coverage score:** {coverage.get('resource_coverage_score', 'unknown')}",
                f"- **Further same-resource deepening still needed:** {'yes' if coverage.get('needs_deepening') else 'no'}",
            ]
        )
        detected = coverage.get("interactive_sections_detected") or []
        if detected:
            extra.append(
                "- **Interactive sections detected:** "
                + ", ".join(str(x.get("label")) for x in detected if isinstance(x, dict))
            )
        covered = coverage.get("covered_sections") or []
        if covered:
            extra.append("- **Covered sections:** " + ", ".join(str(x) for x in covered))
        missing = coverage.get("missing_sections") or []
        if missing:
            extra.append("- **Still missing sections:** " + ", ".join(str(x) for x in missing))
        attempt = coverage.get("deepening_attempt") or {}
        if attempt:
            state = "ok" if attempt.get("ok") else "not completed"
            extra.append(f"- **Passive tab deepening:** {state}")
            if attempt.get("sections_captured"):
                extra.append(
                    "- **Sections captured through passive tab interaction:** "
                    + ", ".join(str(x) for x in attempt.get("sections_captured") or [])
                )
            if attempt.get("error"):
                extra.append(f"- **Deepening note:** {attempt.get('error')}")

    if provider:
        extra.extend(
            [
                "",
                "## Provider enrichment",
                f"- **Adapter:** {provider.get('adapter', 'unknown')}",
                f"- **Structured result sufficient:** {'yes' if provider.get('sufficient') else 'no'}",
            ]
        )
        fields = provider.get("fields") or []
        if fields:
            extra.append("- **Provider fields recovered:** " + ", ".join(str(x) for x in fields))
        sources = provider.get("sources") or []
        if sources:
            extra.append("- **Public structured sources:** " + ", ".join(str(x) for x in sources))
        errors = provider.get("errors") or []
        if errors:
            extra.append("- **Provider warnings:** " + " | ".join(str(x) for x in errors))

    if archive:
        stats = archive.get("capture_stats") or {}
        extra.extend(
            [
                "",
                "## Evidence archive",
                "- **Purpose:** preserve useful source evidence even when it is not yet organized into the curated schema.",
                f"- **Labeled facts retained:** {stats.get('labeled_facts_retained', len(archive.get('labeled_facts') or []))}",
                f"- **Grouped value sets retained:** {stats.get('grouped_value_sets_retained', len(archive.get('grouped_values') or []))}",
                f"- **Readable source text blocks retained:** {stats.get('source_text_blocks_retained', len(archive.get('source_text_blocks') or []))}",
                f"- **Structured collections retained:** {stats.get('structured_collections_retained', len(archive.get('structured_collections') or []))}",
                f"- **Interactive sections retained:** {stats.get('interactive_sections_retained', len(archive.get('interactive_sections') or []))}",
                f"- **Links retained:** {stats.get('links_retained', len(archive.get('links') or []))}",
                f"- **Metadata entries retained:** {stats.get('metadata_entries_retained', len(archive.get('metadata') or []))}",
            ]
        )
        facts = archive.get("labeled_facts") or []
        if facts:
            extra.append("")
            extra.append("### Archived labeled facts")
            for fact in facts[:40]:
                extra.append(
                    f"- **{fact.get('label', 'Fact')}:** {fact.get('value', '')} "
                    f"_(source: {fact.get('source', 'page')})_"
                )
            if len(facts) > 40:
                extra.append(f"- … {len(facts) - 40} more retained in Raw JSON")

        groups = archive.get("grouped_values") or []
        if groups:
            extra.append("")
            extra.append("### Archived grouped values")
            for group in groups[:25]:
                values = group.get("values") or []
                preview = ", ".join(str(x) for x in values[:16])
                extra.append(f"- **{group.get('label', 'Group')}:** {preview}")
            if len(groups) > 25:
                extra.append(f"- … {len(groups) - 25} more retained in Raw JSON")

        collections = archive.get("structured_collections") or []
        if collections:
            extra.append("")
            extra.append("### Archived structured collections")
            for collection in collections[:20]:
                context = collection.get("source_context")
                suffix = f" · source context: {context}" if context else ""
                extra.append(
                    f"- **{collection.get('path', 'collection')}** — "
                    f"{collection.get('kind', 'collection')} / {collection.get('count', '?')} items{suffix}"
                )
            if len(collections) > 20:
                extra.append(f"- … {len(collections) - 20} more retained in Raw JSON")

        interactive = archive.get("interactive_sections") or []
        if interactive:
            extra.append("")
            extra.append("### Archived interactive sections")
            for section in interactive[:10]:
                extra.append(
                    f"- **{section.get('label', 'Section')}** — "
                    f"{len(section.get('text_blocks') or [])} text blocks, "
                    f"{len(section.get('links') or [])} links, "
                    f"{len(section.get('structured_collections') or [])} structured collections"
                )

        text_blocks = archive.get("source_text_blocks") or []
        if text_blocks:
            extra.append("")
            extra.append("### Archived readable source text")
            for block in text_blocks[:20]:
                extra.append(f"- {block}")
            if len(text_blocks) > 20:
                extra.append(f"- … {len(text_blocks) - 20} more retained in Raw JSON")

        links = archive.get("links") or []
        if links:
            extra.append("")
            extra.append("### Archived links")
            for link in links[:35]:
                context = link.get("source_context")
                context_suffix = f" · source context: {context}" if context else ""
                extra.append(
                    f"- [{link.get('label', link.get('url', 'link'))}]({link.get('url', '')}) "
                    f"— {link.get('relationship', 'unknown')} / {link.get('region', 'body')}{context_suffix}"
                )
            if len(links) > 35:
                extra.append(f"- … {len(links) - 35} more retained in Raw JSON")

    if "extraction_score" in quality:
        extra.extend(
            [
                "",
                "## Extraction quality",
                f"- **Score:** {quality.get('extraction_score')}",
                f"- **Grade:** {quality.get('extraction_grade', 'unknown')}",
            ]
        )
        recovered = quality.get("structured_fields_recovered") or []
        if recovered:
            extra.append("- **Recovered structured fields:** " + ", ".join(str(x) for x in recovered))
        missing = quality.get("missing_or_uncertain") or []
        if missing:
            extra.append("- **Still missing/uncertain:** " + ", ".join(str(x) for x in missing))

    return base + "\n" + "\n".join(extra).rstrip() + "\n"
