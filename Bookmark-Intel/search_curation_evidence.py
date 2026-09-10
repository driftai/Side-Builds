from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlparse


MAX_CURATED_LINKS = 12
MAX_CURATED_FACTS = 24

ALWAYS_SOURCE_METADATA_LABELS = {
    "published", "published date", "modified", "modified date", "reading time",
    "reading time minutes", "word count", "source page date", "page date",
    "date published", "date modified", "last modified",
}

SITE_OR_WIKI_AUTHORS_RE = re.compile(
    r"\b(?:contributors|wikimedia|wikipedia|wikihow|fandom|miraheze|wordpress|admin|staff|team|editor|editorial)\b",
    re.I,
)

ALWAYS_SOURCE_TAGS = {"article", "general-webpage", "general_webpage", "webpage"}

SUMMARY_BOILERPLATE = (
    "no meaningful page summary",
    "javascript is disabled",
    "from wikipedia, the free encyclopedia",
    "the wiki that anyone can edit",
    "this wiki is a encyclopedia-style wiki",
    "this wiki is an encyclopedia-style wiki",
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in", "is",
    "of", "on", "or", "the", "to", "with", "wiki", "official", "site",
}

SPECIALIZED_KINDS = {
    "anime_manga", "film_tv", "gaming", "github_repository", "software_tool",
    "product", "academic_paper", "video",
}

ROLE_LABELS = {
    "official": "Official / primary",
    "watch_stream": "Watch / stream",
    "database": "Database / catalog",
    "guide": "Guide / explainer",
    "reference": "Reference",
    "community_wiki": "Community wiki",
    "docs": "Documentation",
    "source_code": "Source code",
    "package": "Package / registry",
    "news": "News / updates",
    "store": "Store / purchase",
    "source": "Source",
}


def _clean(value: Any, limit: int = 1200) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _host(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _query_tokens(query: str) -> list[str]:
    return [token for token in _norm(query).split() if len(token) >= 2 and token not in STOPWORDS]


def _token_overlap(query: str, text: str) -> float:
    q = set(_query_tokens(query))
    if not q:
        return 0.0
    t = set(_norm(text).split())
    return len(q & t) / len(q)


def _quality(analysis: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float(analysis.get("quality_score") or 0.0)))
    except Exception:
        return 0.0


def _summary_is_boilerplate(summary: str | None) -> bool:
    low = str(summary or "").casefold()
    return any(marker in low for marker in SUMMARY_BOILERPLATE)


def _source_relevance(query: str, source: dict[str, Any]) -> float:
    analysis = source.get("analysis") or {}
    title = _clean(analysis.get("title") or source.get("title"), 300) or ""
    summary = _clean(analysis.get("summary"), 1400) or ""
    snippet = _clean(source.get("snippet"), 700) or ""
    url = str(source.get("url") or "")
    kind = str(analysis.get("kind") or "")
    corpus = " ".join([title, summary, snippet, _host(url), url])

    overlap = _token_overlap(query, corpus)
    exact = 1.0 if _norm(query) and _norm(query) in _norm(corpus) else 0.0
    score = 0.12 + 0.34 * overlap + 0.12 * exact + 0.20 * _quality(analysis)
    if kind in SPECIALIZED_KINDS:
        score += 0.14
    elif kind == "article":
        score += 0.04

    role = str(source.get("role") or "")
    if role == "wikipedia":
        score += 0.04
    elif role == "organic":
        score += 0.03

    low_title = title.casefold()
    low_summary = summary.casefold()
    if "javascript is disabled" in low_title or "no meaningful page summary" in low_summary:
        score -= 0.30
    if _summary_is_boilerplate(summary):
        score -= 0.16
    if re.search(r"\b(?:how to|complete guide|watch order|review|explained)\b", low_title):
        score -= 0.08
    if "wiki" in low_title and any(x in low_summary for x in ("anyone can edit", "editing and maintenance", "happy editing")):
        score -= 0.18
    return round(max(0.0, min(1.0, score)), 2)


def _source_role(source: dict[str, Any]) -> str:
    title = _clean((source.get("analysis") or {}).get("title") or source.get("title"), 300) or ""
    url = str(source.get("url") or "")
    host = _host(url)
    low = f"{title} {url}".casefold()
    if source.get("role") == "wikipedia" or "wikipedia.org" in host:
        return "reference"
    if "fandom.com" in host or "miraheze.org" in host or re.search(r"\bwiki\b", low):
        return "community_wiki"
    if re.search(r"(?:\b(?:official|oficial|officiel|offiziell|ufficiale)\b|公式|官方|官网|공식)", title, re.I):
        return "official"
    if any(x in low for x in ("crunchyroll", "netflix", "hulu", "disneyplus", "disney+", "primevideo", "prime video")) or re.search(r"\b(?:watch|stream)\b", low):
        return "watch_stream"
    if any(x in host for x in ("imdb.com", "anilist.co", "myanimelist.net", "themoviedb.org", "mangadex.org")) or "database" in low:
        return "database"
    if re.search(r"\b(?:how to|guide|watch order|explainer|explained)\b", low):
        return "guide"
    if "github.com" in host or "gitlab.com" in host:
        return "source_code"
    if any(x in host for x in ("pypi.org", "npmjs.com", "crates.io")):
        return "package"
    if host.startswith("docs.") or re.search(r"/(?:docs?|documentation|reference|guide)(?:/|$)", url, re.I):
        return "docs"
    if re.search(r"\b(?:news|latest|announcement|announces|release notes?)\b", low):
        return "news"
    if re.search(r"\b(?:store|shop|buy|purchase)\b", low):
        return "store"
    return "source"


def _best_summary(query: str, sources: list[dict[str, Any]]) -> tuple[str | None, float, str | None]:
    candidates: list[tuple[float, int, str, str]] = []
    for index, source in enumerate(sources):
        if source.get("status") != "ok":
            continue
        analysis = source.get("analysis") or {}
        summary = _clean(analysis.get("summary"), 1500)
        if not summary or _summary_is_boilerplate(summary):
            continue
        relevance = float(source.get("subject_relevance_score") or _source_relevance(query, source))
        score = relevance * 0.58 + _quality(analysis) * 0.18
        kind = str(analysis.get("kind") or "")
        if kind in SPECIALIZED_KINDS:
            score += 0.18
        if _token_overlap(query, summary) > 0:
            score += 0.08
        title = _clean(analysis.get("title") or source.get("title"), 300) or ""
        if re.search(r"\b(?:how to|complete guide|watch order|review)\b", title, re.I):
            score -= 0.18
        if "wiki" in title.casefold():
            score -= 0.04
        candidates.append((score, -index, summary, str(source.get("url") or "")))
    if not candidates:
        return None, 0.0, None
    candidates.sort(reverse=True)
    score, _neg_index, summary, url = candidates[0]
    return summary, round(max(0.0, min(1.0, score)), 2), url


def _source_index(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(source.get("url") or ""): source for source in sources if source.get("url")}


def _normalize_year_value(value: str) -> str | None:
    cleaned = _clean(value, 300)
    if not cleaned:
        return None
    years = re.findall(r"\b(?:18|19|20|21)\d{2}\b", cleaned)
    if not years:
        return cleaned
    return years[0]


def _curate_facts(compiled: list[dict[str, Any]], sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_by_url = _source_index(sources)
    out: list[dict[str, Any]] = []
    for fact in compiled:
        label = _clean(fact.get("label"), 120)
        if not label:
            continue
        norm_label = _norm(label)
        if norm_label in ALWAYS_SOURCE_METADATA_LABELS:
            continue
        values_out: list[dict[str, Any]] = []
        for value_row in fact.get("values") or []:
            value = _clean(value_row.get("value"), 700)
            urls = [str(x) for x in (value_row.get("sources") or []) if x]
            if not value:
                continue
            supporting = [source_by_url[u] for u in urls if u in source_by_url]
            specialized_support = any(
                str((source.get("analysis") or {}).get("kind") or "") in SPECIALIZED_KINDS
                and float(source.get("subject_relevance_score") or 0.0) >= 0.45
                for source in supporting
            )
            max_relevance = max((float(source.get("subject_relevance_score") or 0.0) for source in supporting), default=0.0)
            source_count = int(value_row.get("source_count") or len(urls))
            if norm_label in {"author", "authors", "publisher"}:
                if not specialized_support or SITE_OR_WIKI_AUTHORS_RE.search(value):
                    continue
            if norm_label in {"score", "rating", "average score"} and source_count < 2 and not specialized_support:
                continue
            if norm_label == "year":
                value = _normalize_year_value(value)
                if not value:
                    continue
            if source_count < 1:
                continue
            if max_relevance < 0.28 and not specialized_support and source_count < 2:
                continue
            values_out.append({
                "value": value,
                "source_count": source_count,
                "sources": urls[:7],
                "subject_support": "specialized" if specialized_support else "cross-source",
            })
        if not values_out:
            continue
        values_out.sort(key=lambda row: (-int(row["source_count"]), str(row["value"]).casefold()))
        out.append({"label": label, "values": values_out[:8], "scope": "subject"})
    out.sort(key=lambda row: (
        -max((int(v.get("source_count") or 0) for v in row.get("values") or []), default=0),
        str(row.get("label") or "").casefold(),
    ))
    return out[:MAX_CURATED_FACTS]


__all__ = [name for name in globals() if not name.startswith("__")]
