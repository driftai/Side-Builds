from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from acquisition import acquire_url
from search_discovery import SEARCH_ENGINES, SearchResult, _clean, _engine_order, extract_search_results

RRF_K = 60
TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "ref", "ref_", "source", "campaign", "campaignid",
}


def canonical_search_url(value: str) -> str:
    """Normalize result URLs for cross-engine identity without changing the fetched URL."""
    raw = str(value or "").strip()
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return raw
    host = parsed.hostname.casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    port = f":{parsed.port}" if parsed.port else ""
    query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        low = key.casefold()
        if low.startswith("utm_") or low in TRACKING_PARAMS:
            continue
        query.append((key, val))
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    normalized = parsed._replace(netloc=host + port, path=path, query=urlencode(query, doseq=True), fragment="")
    return urlunparse(normalized).rstrip("/") if path != "/" else urlunparse(normalized)


def _attempt(engine: str, query: str) -> tuple[list[SearchResult], dict[str, Any]]:
    search_url = SEARCH_ENGINES[engine](query)
    try:
        page = acquire_url(search_url, allow_browsers=True)
        results = extract_search_results(page.text, engine, page.final_url)
        return results, {
            "engine": engine,
            "query": query,
            "url": search_url,
            "ok": True,
            "method": page.method,
            "rendered": bool(page.rendered),
            "score": round(float(page.score), 2),
            "results_found": len(results),
            "acquisition_attempts": [
                {
                    "method": item.method,
                    "ok": item.ok,
                    "score": round(float(item.score), 2),
                    "error": item.error,
                    "elapsed_ms": item.elapsed_ms,
                }
                for item in page.attempts
            ],
        }
    except Exception as exc:
        return [], {
            "engine": engine,
            "query": query,
            "url": search_url,
            "ok": False,
            "error": _clean(exc, 500) or "search acquisition failed",
            "results_found": 0,
        }


def discover_results_fused(
    query: str,
    preferred_engine: str | None = None,
    *,
    target_count: int = 10,
) -> tuple[list[SearchResult], list[dict[str, Any]]]:
    """Search each engine independently and fuse rankings with Reciprocal Rank Fusion."""
    engines = _engine_order(preferred_engine)
    attempts: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[str, int, SearchResult]]] = defaultdict(list)
    result_engines = 0

    for engine in engines:
        results, attempt = _attempt(engine, query)
        attempts.append(attempt)
        if results:
            result_engines += 1
        for local_rank, result in enumerate(results, 1):
            canonical = canonical_search_url(result.url)
            if canonical:
                grouped[canonical].append((engine, local_rank, result))

    fused_rows: list[tuple[float, int, int, str, SearchResult, dict[str, Any]]] = []
    denom = max(1, result_engines) / (RRF_K + 1)
    for canonical, appearances in grouped.items():
        engine_ranks = {engine: rank for engine, rank, _ in appearances}
        rrf = sum(1.0 / (RRF_K + rank) for rank in engine_ranks.values())
        _best_engine, best_rank, representative = min(
            appearances,
            key=lambda row: (row[1], engines.index(row[0])),
        )
        consensus = len(engine_ranks)
        normalized = min(1.0, rrf / denom) if denom else 0.0
        metadata = {
            "canonical_url": canonical,
            "rrf_score": round(rrf, 6),
            "fusion_score": round(normalized, 4),
            "engine_consensus": consensus,
            "engines_with_results": result_engines,
            "engine_ranks": engine_ranks,
            "best_engine_rank": best_rank,
        }
        fused_rows.append((rrf, consensus, -best_rank, canonical, representative, metadata))

    fused_rows.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
    output: list[SearchResult] = []
    for fused_rank, row in enumerate(fused_rows[: max(1, target_count)], 1):
        _rrf, _consensus, _neg_rank, _canonical, representative, metadata = row
        result = SearchResult(
            title=representative.title,
            url=representative.url,
            snippet=representative.snippet,
            engine=representative.engine,
            rank=fused_rank,
        )
        setattr(result, "fusion_metadata", metadata)
        output.append(result)
    return output, attempts


def fusion_metadata(result: SearchResult | Any) -> dict[str, Any]:
    metadata = getattr(result, "fusion_metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


__all__ = ["RRF_K", "canonical_search_url", "discover_results_fused", "fusion_metadata"]
