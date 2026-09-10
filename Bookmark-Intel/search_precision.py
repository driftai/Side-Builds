from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from search_curation import ROLE_LABELS


MAX_LINKS = 12
NOISE_TAGS = {"article", "general-webpage", "general_webpage", "webpage", "social-post", "r2"}
GENERIC_QUERY = {
    "app", "book", "code", "data", "database", "download", "game", "guide", "library",
    "media", "movie", "news", "online", "review", "series", "site", "software", "tool",
    "tv", "video", "watch", "web", "website", "wiki",
}
PROMO_TAG_RE = re.compile(
    r"(?:^|[-_])(?:watch|stream|streaming|online|download|downloads|full-length|instant-streaming)(?:$|[-_])"
    r"|^(?:movies?-online|tv-online|no-download|watch-movies|watch-tv|stream-movies|stream-tv)$",
    re.I,
)
BOILERPLATE = (
    "no meaningful page summary", "javascript is disabled", "from wikipedia, the free encyclopedia",
    "the wiki that anyone can edit", "these cookies", "we use cookies", "cookie settings",
    "cookie preferences", "privacy information", "customize and enhance your online experience",
    "deletion of these types of cookies", "third-party cookies",
)
STREAM_HOSTS = (
    "crunchyroll.com", "netflix.com", "hulu.com", "disneyplus.com", "primevideo.com",
    "max.com", "hidive.com", "peacocktv.com", "paramountplus.com",
)
DATABASE_HOSTS = (
    "imdb.com", "anilist.co", "myanimelist.net", "themoviedb.org", "mangadex.org",
    "goodreads.com", "igdb.com",
)
SPECIALIZED = {
    "anime_manga", "film_tv", "gaming", "github_repository", "software_tool",
    "product", "academic_paper", "video",
}
AMBIGUOUS = {
    "score", "rating", "average score", "volumes", "volume count", "chapters",
    "chapter count", "episodes", "episode count", "runtime", "rank",
}
SCOPE_HINTS = {
    "volumes": {"manga", "comic", "book", "novel", "volume"},
    "volume count": {"manga", "comic", "book", "novel", "volume"},
    "chapters": {"manga", "comic", "webtoon", "manhwa", "manhua", "chapter"},
    "chapter count": {"manga", "comic", "webtoon", "manhwa", "manhua", "chapter"},
    "episodes": {"anime", "show", "season", "episode", "tv"},
    "episode count": {"anime", "show", "season", "episode", "tv"},
    "runtime": {"movie", "film", "episode", "runtime"},
}


def _clean(v: Any, limit: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(v or "")).strip()
    return text[:limit]


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").casefold()).strip()


def _host(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _tokens(query: str) -> list[str]:
    return [x for x in _norm(query).split() if len(x) >= 2]


def _match(query: str, text: str) -> tuple[float, bool, bool]:
    q = _tokens(query)
    if not q:
        return 0.0, False, False
    text_tokens = set(_norm(text).split())
    max_len = max(len(x) for x in q)
    weights = {}
    distinctive = set()
    for token in q:
        w = 1.0 + min(len(token), 12) / 8
        if token in GENERIC_QUERY:
            w *= 0.30
        if any(ch.isdigit() for ch in token):
            w += 0.8
        if len(token) == max_len and token not in GENERIC_QUERY:
            w += 0.35
        weights[token] = w
        if token not in GENERIC_QUERY and (len(token) >= 4 or any(ch.isdigit() for ch in token)):
            distinctive.add(token)
    if not distinctive:
        distinctive = {x for x in q if x not in GENERIC_QUERY}
    matched = {x for x in q if x in text_tokens}
    score = sum(weights[x] for x in matched) / max(sum(weights.values()), 0.001)
    exact = bool(_norm(query) and _norm(query) in _norm(text))
    if exact:
        score = max(score, 0.98)
    return min(1.0, score), bool(distinctive & matched), exact


def _boilerplate(summary: Any) -> bool:
    low = str(summary or "").casefold()
    return any(x in low for x in BOILERPLATE)


def _stream_host(host: str) -> bool:
    return any(host == x or host.endswith("." + x) for x in STREAM_HOSTS)


def _role(title: str, url: str, relationship: str = "", existing: str = "") -> str:
    host, low = _host(url), f"{title} {url}".casefold()
    if relationship == "wikipedia" or host.endswith("wikipedia.org"):
        return "reference"
    if host.endswith("fandom.com") or host.endswith("miraheze.org") or re.search(r"\bwiki\b", low):
        return "community_wiki"
    if re.search(r"(?:\b(?:official|oficial|officiel|offiziell|ufficiale)\b|公式|官方|官网|공식)", title, re.I):
        return "official"
    if any(host == x or host.endswith("." + x) for x in DATABASE_HOSTS):
        return "database"
    if _stream_host(host):
        return "watch_stream"
    # Intent beats the generic word "watch" when this is not a real streaming host.
    if re.search(r"\b(?:how to|guide|watch order|explainer|explained|tutorial|walkthrough)\b", low):
        return "guide"
    if host == "github.com" or host.endswith(".github.com") or host == "gitlab.com" or host.endswith(".gitlab.com"):
        return "source_code"
    if host in {"pypi.org", "npmjs.com", "crates.io"}:
        return "package"
    if host.startswith("docs.") or re.search(r"/(?:docs?|documentation|reference)(?:/|$)", url, re.I):
        return "docs"
    if re.search(r"\b(?:news|latest|announcement|announces|release notes?)\b", low):
        return "news"
    if re.search(r"\b(?:store|shop|buy|purchase|price|retailer)\b", low):
        return "store"
    if re.search(r"\b(?:watch|stream)\b", low):
        return "watch_stream"
    return existing if existing in ROLE_LABELS else "source"


def _tighten_sources(query: str, sources: list[dict[str, Any]]) -> None:
    for source in sources:
        analysis = source.get("analysis") or {}
        raw_title = _clean(source.get("title") or analysis.get("title"))
        title = _clean(analysis.get("title") or raw_title)
        url = str(source.get("url") or "")
        role = _role(raw_title, url, str(source.get("role") or ""), str(source.get("curation_role") or ""))
        source["curation_role"] = role
        match_score, distinctive, _ = _match(query, f"{raw_title} {title} {url}")
        source["query_match_score"] = round(match_score, 3)
        source["distinctive_query_match"] = distinctive
        relevance = float(source.get("subject_relevance_score") or 0.0)
        if _boilerplate(analysis.get("summary")) and role != "reference":
            relevance = min(relevance, 0.34)
            source["curation_note"] = "Boilerplate/interstitial page content; keep the link but exclude page evidence from synthesis."
        elif len(_tokens(query)) >= 2 and not distinctive and match_score < 0.60:
            relevance = min(relevance, 0.34)
            source["curation_note"] = "Partial query-token match only; retained for provenance, not synthesis."
        source["subject_relevance_score"] = round(relevance, 2)
        source["subject_relevance_grade"] = "high" if relevance >= 0.70 else "medium" if relevance >= 0.45 else "low"


def _source_map(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(x.get("url") or ""): x for x in sources if x.get("url")}


def _supported(source: dict[str, Any]) -> bool:
    a = source.get("analysis") or {}
    return (
        str(a.get("kind") or "") in SPECIALIZED
        and float(source.get("subject_relevance_score") or 0.0) >= 0.45
        and not _boilerplate(a.get("summary"))
    )


def _scope_explicit(query: str, label: str) -> bool:
    return bool(set(_tokens(query)) & SCOPE_HINTS.get(label, set()))


def _tighten_facts(query: str, research: dict[str, Any], sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url = _source_map(sources)
    out = []
    for fact in list(research.get("compiled_facts") or []):
        label = _clean(fact.get("label"), 120)
        norm = _norm(label)
        kept = []
        for row in fact.get("values") or []:
            urls = [str(x) for x in row.get("sources") or [] if x]
            supporting = [by_url[x] for x in urls if x in by_url]
            count = int(row.get("source_count") or len(urls))
            specialized = any(_supported(x) for x in supporting)
            max_rel = max((float(x.get("subject_relevance_score") or 0.0) for x in supporting), default=0.0)

            # A bare rating in a multi-source dossier is too ambiguous without agreement.
            if norm in {"score", "rating", "average score"} and count < 2:
                continue
            # Quantities like volumes/episodes need either cross-source agreement or an explicit scoped query.
            if norm in AMBIGUOUS and count < 2 and not (specialized and _scope_explicit(query, norm)):
                continue
            # A lone year from an article/reference page is usually a page/adaptation date, not canonical subject year.
            if norm == "year" and count < 2 and not specialized:
                continue
            if max_rel < 0.35 and count < 2 and not specialized:
                continue

            value = _clean(row.get("value"), 700)
            if norm in {"genre", "genres"}:
                value = re.sub(r"\[\s*\d+\s*\]", "", value)
                value = re.sub(r"\s+", " ", value)
                value = re.sub(r"\s+,", ",", value)
                value = re.sub(r",\s*,+", ",", value).strip(" ,")
            kept.append({**row, "value": value})
        if kept:
            out.append({**fact, "values": kept})
    return out


def _tighten_tags(query: str, sources: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    semantic_specialized: set[str] = set()
    for source in sources:
        if source.get("status") != "ok":
            continue
        a, seen = source.get("analysis") or {}, set()
        role = str(source.get("curation_role") or "")
        for raw in a.get("tags") or []:
            clean = _clean(raw, 80)
            key = re.sub(r"[^a-z0-9]+", "-", clean.casefold()).strip("-")
            if len(key) < 2 or key in seen or key in NOISE_TAGS:
                continue
            seen.add(key)
            counts[key] += 1
            display.setdefault(key, clean)
            if _supported(source) and not (role == "watch_stream" and PROMO_TAG_RE.search(key)):
                semantic_specialized.add(key)
    q = set(_tokens(query))
    kept = []
    for key, count in counts.items():
        if PROMO_TAG_RE.search(key) and count < 2:
            continue
        query_related = bool(q & set(_norm(key).split()))
        if count >= 2 or key in semantic_specialized or query_related:
            kept.append(key)
    kept.sort(key=lambda x: (-counts[x], x))
    return [display[x] for x in kept[:26]]


def _tighten_links(query: str, data: dict[str, Any], sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_url = _source_map(sources)
    rows = []
    seen = set()
    q_len = len(_tokens(query))
    for raw in (data.get("evidence_archive") or {}).get("links") or []:
        url = str(raw.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        title = _clean(raw.get("label") or url, 300)
        source = by_url.get(url)
        selected = bool(raw.get("selected_for_research")) or source is not None
        relationship = str(source.get("role") or "organic") if source else "discovered"
        role = _role(title, url, relationship, str(source.get("curation_role") or "") if source else "")
        match_score, distinctive, exact = _match(query, f"{title} {url}")
        relevance = float(source.get("subject_relevance_score") or 0.0) if source else 0.0

        # "Code" alone must not make Visual Studio Code relevant to "Code Geass".
        if q_len >= 2 and not selected and not distinctive and match_score < 0.72:
            continue
        if not selected and match_score < 0.28:
            continue

        try:
            rank = int(raw.get("search_rank") or 99)
        except Exception:
            rank = 99
        score = 0.10 + 0.34 * match_score + 0.16 * relevance + (0.20 if selected else 0.0)
        if rank < 99:
            score += max(0.0, 0.15 - min(rank - 1, 15) * 0.01)
        score += 0.16 if role == "official" else 0.08 if role in {
            "watch_stream", "database", "reference", "docs", "source_code", "package"
        } else 0.05 if role in {"guide", "community_wiki", "news"} else 0.0
        if role == "source" and not selected and score < 0.50:
            continue

        reason = ["analyzed source" if selected else "discovered result"]
        if role != "source":
            reason.append(ROLE_LABELS[role].casefold())
        if exact:
            reason.append("exact query phrase")
        elif distinctive:
            reason.append("distinctive query match")
        if relevance >= 0.65:
            reason.append("high subject relevance")
        rows.append({
            "label": f"{ROLE_LABELS[role]} — {title}",
            "original_label": title,
            "url": url,
            "relationship": relationship,
            "curation_role": role,
            "curation_score": round(min(1.0, score), 2),
            "reason": ", ".join(reason),
            "selected_for_research": selected,
            "search_rank": None if rank == 99 else rank,
            "source_relevance_score": relevance if source else None,
            "source_kind": (source.get("analysis") or {}).get("kind") if source else None,
            "query_match_score": round(match_score, 3),
            "distinctive_query_match": distinctive,
        })
    rows.sort(key=lambda x: (-float(x["curation_score"]), int(x.get("search_rank") or 999), x["label"].casefold()))

    out, host_counts, role_counts = [], Counter(), Counter()
    for row in rows:
        host, role = _host(row["url"]), row["curation_role"]
        host_cap = 2 if row["selected_for_research"] else 1
        if host_counts[host] >= host_cap or role_counts[role] >= 3:
            continue
        host_counts[host] += 1
        role_counts[role] += 1
        out.append(row)
        if len(out) >= MAX_LINKS:
            break
    return out


def _rebuild_key_facts(data: dict[str, Any], facts: list[dict[str, Any]]) -> None:
    keep = []
    for row in data.get("key_facts") or []:
        if _norm(row.get("label")) in {
            "organic sources selected", "sources analyzed successfully", "wikipedia reference",
            "fandom reference", "inferred subject type",
        }:
            keep.append(row)
    for fact in facts[:7]:
        vals = fact.get("values") or []
        if not vals:
            continue
        first = vals[0]
        count = int(first.get("source_count") or 0)
        suffix = f" ({count} source{'s' if count != 1 else ''})" if count else ""
        keep.append({"label": fact.get("label"), "value": f"{first.get('value')}{suffix}"})
    data["key_facts"] = keep[:13]


def finalize_search_precision(data: dict[str, Any]) -> dict[str, Any]:
    """Precision pass for an already-curated search bundle; performs zero network requests."""
    research = data.get("search_research")
    if not isinstance(research, dict):
        return data
    query = _clean(research.get("query") or (data.get("input") or {}).get("query"), 500)
    sources = list(research.get("sources") or [])
    _tighten_sources(query, sources)

    facts = _tighten_facts(query, research, sources)
    tags = _tighten_tags(query, sources)
    links = _tighten_links(query, data, sources)

    research["sources"] = sources
    research["subject_facts"] = facts
    research["compiled_facts"] = facts
    research["compiled_tags"] = tags
    research["curated_links"] = links
    research["curation_version"] = 2
    research["precision_version"] = 1
    research["precision_policy"] = "distinctive query matching + interstitial quarantine + scoped facts + role-aware tag/link cleanup"

    final_tags = ["web-search", "research"]
    for tag in tags:
        slug = re.sub(r"[^a-z0-9]+", "-", str(tag).casefold()).strip("-")
        if 2 <= len(slug) <= 40 and slug not in final_tags:
            final_tags.append(slug)
    data["tags"] = final_tags[:28]
    data.setdefault("bookmark", {})["suggested_tags"] = data["tags"]
    if links:
        data.setdefault("links", {})["important"] = links

    section = data.setdefault("sections", {}).setdefault("search_research", {})
    section["subject_fact_groups"] = len(facts)
    section["curated_link_count"] = len(links)
    section["precision_version"] = 1
    _rebuild_key_facts(data, facts)

    # Keep the earlier semantic score as provenance, but make final quality reflect the tighter evidence set.
    quality = data.setdefault("quality", {})
    previous = quality.get("semantic_curation_score")
    relevant = [x for x in sources if x.get("status") == "ok" and float(x.get("subject_relevance_score") or 0.0) >= 0.45]
    success = [x for x in sources if x.get("status") == "ok"]
    relevant_ratio = len(relevant) / len(success) if success else 0.0
    link_signal = min(1.0, sum(1 for x in links if float(x.get("curation_score") or 0.0) >= 0.55) / 8)
    fact_signal = min(1.0, len(facts) / 6)
    summary_signal = 0.0 if _boilerplate(data.get("summary")) else 1.0
    score = round(min(0.94, 0.18 + 0.30 * relevant_ratio + 0.22 * summary_signal + 0.15 * fact_signal + 0.15 * link_signal), 2)
    quality["pre_precision_semantic_score"] = previous
    quality["semantic_precision_score"] = score
    quality["semantic_curation_score"] = score
    quality["extraction_score"] = score
    quality["extraction_grade"] = "strong" if score >= 0.75 else "usable" if score >= 0.50 else "weak" if score >= 0.25 else "minimal"
    quality["quality_basis"] = "relevant analyzed sources + non-boilerplate overview + scoped facts + precision-curated links"
    return data
