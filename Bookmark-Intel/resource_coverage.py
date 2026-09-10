from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from resource_coverage_browser import *


def finalize_resource_coverage(
    data: dict[str, Any],
    acquired: Any,
    provider: Any = None,
    *,
    allow_interactive: bool = True,
) -> dict[str, Any]:
    """Preserve resource information and deepen safe passive same-resource sections."""
    html = str(getattr(acquired, "text", "") or "")
    content_type = str(getattr(acquired, "content_type", "") or "")
    if not html or (content_type and not any(x in content_type for x in ("html", "xml", "text"))):
        data["resource_coverage"] = {
            "html_health_score": round(float(getattr(acquired, "score", 0.0) or 0.0), 2),
            "resource_coverage_score": None,
            "needs_deepening": False,
            "reason": "non-HTML resource",
        }
        return data

    soup = BeautifulSoup(html, "html.parser")
    groups = _grouped_values(soup)
    collections = _structured_collections(soup)
    _merge_archive_static(data, groups, collections)

    mapping = _fact_map(data, groups)
    facets = _infer_media_facets(data, soup, mapping)
    data["resource_profile"] = {
        "primary_kind": data.get("classification", {}).get("kind"),
        "media_family": facets.get("media_family"),
        "format": facets.get("format"),
        "source_material": facets.get("source_material"),
        "signals": facets.get("signals") or [],
    }

    if facets.get("media_family") == "Anime":
        _promote_anime(data, mapping, facets)
        data["resource_profile"]["primary_kind"] = "anime_manga"

    coverage = _coverage_state(data, acquired, soup, groups, collections)
    data["resource_coverage"] = coverage

    provider_sufficient = bool(provider and getattr(provider, "sufficient", False))
    if (
        allow_interactive
        and coverage.get("needs_deepening")
        and not provider_sufficient
        and not bool(getattr(acquired, "rendered", False))
    ):
        labels = [str(x) for x in (coverage.get("missing_sections") or [])]
        snapshots, attempt = _capture_interactive_sections(
            str(getattr(acquired, "final_url", "") or data.get("input", {}).get("url") or ""),
            labels,
        )
        coverage["deepening_attempt"] = attempt
        if snapshots:
            _merge_interactive_snapshots(data, acquired, snapshots)
            combined_soup = BeautifulSoup(_all_snapshot_html(acquired, snapshots), "html.parser")
            combined_groups = list(data.get("evidence_archive", {}).get("grouped_values") or [])
            combined_mapping = _fact_map(data, combined_groups)
            combined_facets = _infer_media_facets(data, combined_soup, combined_mapping)
            if combined_facets.get("media_family") == "Anime":
                _promote_anime(data, combined_mapping, combined_facets)
                data["resource_profile"] = {
                    "primary_kind": "anime_manga",
                    "media_family": "Anime",
                    "format": combined_facets.get("format"),
                    "source_material": combined_facets.get("source_material"),
                    "signals": combined_facets.get("signals") or [],
                }

            captured_labels = {str(x.get("label")) for x in snapshots}
            captured_stems = {_norm(str(x.get("label"))).rstrip("s") for x in snapshots}
            previously_covered = list(coverage.get("covered_sections") or [])
            matched_candidates = [
                str(candidate.get("label"))
                for candidate in (coverage.get("interactive_sections_detected") or [])
                if _norm(str(candidate.get("label"))).rstrip("s") in captured_stems
            ]
            coverage["covered_sections"] = _uniq(previously_covered + list(captured_labels) + matched_candidates, 30)
            coverage["missing_sections"] = [
                item for item in (coverage.get("missing_sections") or [])
                if str(item) not in captured_labels and _norm(str(item)).rstrip("s") not in captured_stems
            ]
            total = len(coverage.get("interactive_sections_detected") or [])
            covered_set = set(coverage["covered_sections"])
            num_covered_candidates = len([
                candidate for candidate in (coverage.get("interactive_sections_detected") or [])
                if str(candidate.get("label")) in covered_set
            ])
            coverage["resource_coverage_score"] = round(num_covered_candidates / total, 2) if total else 1.0
            coverage["needs_deepening"] = False
            data.setdefault("acquisition", {})["coverage_rendered_fallback_used"] = True

    quality = data.setdefault("quality", {})
    media_section = (
        data.get("sections", {}).get("anime_manga", {})
        if data.get("classification", {}).get("kind") == "anime_manga"
        else {}
    )
    present = {
        "year": bool(media_section.get("year") or _extract_year(_first(_values_for(mapping, "start_date")))),
        "genres": bool(media_section.get("genres") or _values_for(mapping, "genres")),
        "status": bool(media_section.get("status") or _values_for(mapping, "status")),
    }
    quality["missing_or_uncertain"] = [
        str(item) for item in (quality.get("missing_or_uncertain") or [])
        if not present.get(str(item).casefold(), False)
    ]
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
