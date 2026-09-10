from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


SEMANTIC_REGIONS = {"Read or Buy", "Track", "Official source", "Alternative source"}
SEMANTIC_RELATIONSHIPS = {"read_or_buy", "track", "official_source", "alternative_source"}
# These adapters explicitly define the meaning of their external IDs/links.
# Generic DOM pages must not inherit these vocabularies from nearby words.
EXPLICIT_SEMANTIC_PROVIDERS = {"mangadex"}


def _neutral_relationship(page_url: str, link_url: str) -> str:
    try:
        page_host = (urlparse(page_url).hostname or "").casefold()
        link_host = (urlparse(link_url).hostname or "").casefold()
        if page_host and link_host:
            return "internal" if page_host == link_host else "external"
    except Exception:
        pass
    return "external"


def normalize_link_semantics(data: dict[str, Any]) -> dict[str, Any]:
    """Prevent resource-specific link vocabularies from leaking into generic URLs.

    The archive still preserves every HTTP(S) link, its internal/external relation,
    and any exact nearby source heading captured as ``source_context``. Labels such
    as "Read or Buy" or "Track" are retained only when a structured provider has
    explicitly assigned that meaning.
    """
    provider = data.get("provider_enrichment") or {}
    adapter = str(provider.get("adapter") or "").casefold()
    explicit = adapter in EXPLICIT_SEMANTIC_PROVIDERS

    archive = data.get("evidence_archive") or {}
    links = archive.get("links") or []
    if not explicit:
        for row in links:
            if not isinstance(row, dict):
                continue
            if row.get("region") in SEMANTIC_REGIONS:
                row["region"] = "body"
            relationship = str(row.get("relationship") or "").casefold()
            if relationship in SEMANTIC_RELATIONSHIPS:
                page_url = str(data.get("fetch", {}).get("final_url") or data.get("input", {}).get("url") or "")
                row["relationship"] = _neutral_relationship(page_url, str(row.get("url") or ""))

        for row in (data.get("links", {}).get("important") or []):
            if not isinstance(row, dict):
                continue
            relationship = str(row.get("relationship") or "").casefold()
            if relationship in SEMANTIC_RELATIONSHIPS:
                page_url = str(data.get("fetch", {}).get("final_url") or data.get("input", {}).get("url") or "")
                row["relationship"] = _neutral_relationship(page_url, str(row.get("url") or ""))

    data["link_semantics"] = {
        "mode": "provider_explicit" if explicit else "neutral_generic",
        "provider": adapter or None,
    }
    return data
