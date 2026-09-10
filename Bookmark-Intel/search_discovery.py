from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from acquisition import acquire_url

MAX_QUERY_CHARS = 500
MAX_DISCOVERED_RESULTS = 30
ORGANIC_SOURCE_TARGET = 5
REFERENCE_DOMAINS = ("wikipedia.org", "fandom.com")


class SearchResearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class InputTarget:
    mode: str
    raw: str
    url: str | None = None
    query: str | None = None
    preferred_engine: str | None = None


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str | None = None
    engine: str | None = None
    rank: int | None = None


SEARCH_ENGINES = {
    "google": lambda q: f"https://www.google.com/search?q={quote_plus(q)}&num=10&hl=en",
    "bing": lambda q: f"https://www.bing.com/search?q={quote_plus(q)}&count=10&setlang=en-us",
    "duckduckgo": lambda q: f"https://html.duckduckgo.com/html/?q={quote_plus(q)}",
}


def _clean(value: Any, limit: int = 1000) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().lstrip("www.")


def _is_domain_or_subdomain(host: str, domain: str) -> bool:
    host = host.casefold().rstrip(".")
    domain = domain.casefold().rstrip(".")
    return host == domain or host.endswith("." + domain)


def _engine_for_url(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    query = parse_qs(parsed.query).get("q", [None])[0]
    if not query:
        return None, None
    query = unquote(str(query)).strip()
    if not query:
        return None, None
    if _is_domain_or_subdomain(host, "bing.com"):
        return "bing", query
    if _is_domain_or_subdomain(host, "duckduckgo.com"):
        return "duckduckgo", query
    if host == "google.com" or host.startswith("www.google.") or ".google." in host:
        return "google", query
    return None, None


def _looks_like_bare_url(value: str) -> bool:
    if " " in value or "\t" in value or "\n" in value:
        return False
    if re.match(r"^localhost(?::\d+)?(?:[/#?].*)?$", value, re.I):
        return True
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?(?:[/#?].*)?$", value):
        return True
    return bool(re.match(r"^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?::\d+)?(?:[/#?].*)?$", value, re.I))


def parse_input_target(raw: str) -> InputTarget:
    raw = str(raw or "").strip()
    if not raw:
        raise SearchResearchError("Enter a public URL or a search phrase.")
    is_host_port = bool(re.match(r"^[a-zA-Z0-9.-]+:\d+(?:[/#?].*)?$", raw))
    scheme_match = None if is_host_port else re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", raw)
    if scheme_match:
        scheme = scheme_match.group(1).casefold()
        if scheme not in {"http", "https"}:
            raise SearchResearchError(f"Unsupported URL protocol '{scheme}:'. Only http/https URLs are supported.")
        parsed = urlparse(raw)
        if not parsed.hostname:
            raise SearchResearchError(f"Malformed URL '{raw}': missing valid hostname.")
        engine, query = _engine_for_url(raw)
        if engine and query:
            if len(query) > MAX_QUERY_CHARS:
                raise SearchResearchError(f"Search phrase is too long (>{MAX_QUERY_CHARS} characters).")
            return InputTarget(mode="search", raw=raw, query=query, preferred_engine=engine)
        return InputTarget(mode="url", raw=raw, url=raw)

    candidate = raw
    if _looks_like_bare_url(candidate):
        candidate = "https://" + candidate
        parsed = urlparse(candidate)
        if not parsed.hostname:
            raise SearchResearchError(f"Malformed URL '{raw}'.")
        engine, query = _engine_for_url(candidate)
        if engine and query:
            if len(query) > MAX_QUERY_CHARS:
                raise SearchResearchError(f"Search phrase is too long (>{MAX_QUERY_CHARS} characters).")
            return InputTarget(mode="search", raw=raw, query=query, preferred_engine=engine)
        return InputTarget(mode="url", raw=raw, url=candidate)

    if len(raw) > MAX_QUERY_CHARS:
        raise SearchResearchError(f"Search phrase is too long (>{MAX_QUERY_CHARS} characters).")
    return InputTarget(mode="search", raw=raw, query=raw, preferred_engine="google")


def _unwrap_search_href(href: str, base_url: str) -> str | None:
    href = str(href or "").strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    host = (parsed.hostname or "").casefold()
    if (host == "google.com" or host.startswith("www.google.") or ".google." in host) and parsed.path == "/url":
        qs = parse_qs(parsed.query)
        target = (qs.get("q") or qs.get("url") or [None])[0]
        if target:
            absolute = unquote(str(target))
            parsed = urlparse(absolute)
            host = (parsed.hostname or "").casefold()
    if _is_domain_or_subdomain(host, "duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            absolute = unquote(str(target))
            parsed = urlparse(absolute)
            host = (parsed.hostname or "").casefold()
    if _is_domain_or_subdomain(host, "bing.com") and "/ck/" in parsed.path:
        target = parse_qs(parsed.query).get("u", [None])[0]
        if target and len(target) > 2:
            try:
                raw_b64 = target[2:] if target.startswith(("a0", "a1")) else target
                raw_b64 += "=" * ((4 - len(raw_b64) % 4) % 4)
                decoded = base64.urlsafe_b64decode(raw_b64).decode("utf-8", errors="ignore")
                if decoded.startswith(("http://", "https://")):
                    absolute = decoded
                    parsed = urlparse(absolute)
            except Exception:
                pass
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return parsed._replace(fragment="").geturl()


def _is_search_internal(url: str) -> bool:
    host = _host(url)
    if not host:
        return True
    if _is_domain_or_subdomain(host, "bing.com") or _is_domain_or_subdomain(host, "duckduckgo.com"):
        return True
    return host == "google.com" or host.startswith("google.") or ".google." in host


def _snippet_for_anchor(anchor: Any, title: str) -> str | None:
    parent = anchor
    for _ in range(4):
        parent = getattr(parent, "parent", None)
        if parent is None:
            break
        text = _clean(parent.get_text(" ", strip=True), 700) if hasattr(parent, "get_text") else None
        if text and len(text) >= len(title) + 20:
            if title in text:
                text = text.replace(title, "", 1).strip(" -–—|·")
            if len(text) >= 20:
                return text[:500]
    return None


def extract_search_results(html: str, engine: str, search_url: str) -> list[SearchResult]:
    soup = BeautifulSoup(html or "", "html.parser")
    anchors: list[Any] = []
    if engine == "google":
        for h in soup.find_all(["h3"]):
            parent = h.find_parent("a", href=True)
            if parent:
                anchors.append(parent)
    elif engine == "bing":
        anchors.extend(soup.select("li.b_algo h2 a[href]"))
        if not anchors:
            anchors.extend(soup.select("h2 a[href]"))
    elif engine == "duckduckgo":
        anchors.extend(soup.select("a.result__a[href]"))
        anchors.extend(soup.select('a[data-testid="result-title-a"][href]'))
    if not anchors:
        for a in soup.find_all("a", href=True):
            if a.find(["h2", "h3"]):
                anchors.append(a)

    out: list[SearchResult] = []
    seen: set[str] = set()
    for anchor in anchors:
        url = _unwrap_search_href(str(anchor.get("href") or ""), search_url)
        if not url or _is_search_internal(url) or url in seen:
            continue
        title = _clean(anchor.get_text(" ", strip=True), 280)
        if not title or title.casefold() in {"cached", "translate", "more results", "images", "videos"}:
            continue
        seen.add(url)
        out.append(SearchResult(title=title, url=url, snippet=_snippet_for_anchor(anchor, title), engine=engine, rank=len(out) + 1))
        if len(out) >= MAX_DISCOVERED_RESULTS:
            break
    return out


def _engine_order(preferred: str | None) -> list[str]:
    order: list[str] = []
    for name in (preferred, "duckduckgo", "bing", "google"):
        if name in SEARCH_ENGINES and name not in order:
            order.append(str(name))
    return order


def discover_results(query: str, preferred_engine: str | None = None, *, target_count: int = 10) -> tuple[list[SearchResult], list[dict[str, Any]]]:
    merged: list[SearchResult] = []
    seen: set[str] = set()
    attempts: list[dict[str, Any]] = []
    for engine in _engine_order(preferred_engine):
        search_url = SEARCH_ENGINES[engine](query)
        try:
            page = acquire_url(search_url, allow_browsers=True)
            results = extract_search_results(page.text, engine, page.final_url)
            attempts.append({
                "engine": engine, "query": query, "url": search_url, "ok": True,
                "method": page.method, "rendered": bool(page.rendered), "score": round(float(page.score), 2),
                "results_found": len(results),
                "acquisition_attempts": [
                    {"method": a.method, "ok": a.ok, "score": round(float(a.score), 2), "error": a.error, "elapsed_ms": a.elapsed_ms}
                    for a in page.attempts
                ],
            })
            for result in results:
                if result.url in seen:
                    continue
                seen.add(result.url)
                result.rank = len(merged) + 1
                merged.append(result)
                if len(merged) >= MAX_DISCOVERED_RESULTS:
                    break
            if len(merged) >= target_count:
                break
        except Exception as exc:
            attempts.append({"engine": engine, "query": query, "url": search_url, "ok": False, "error": _clean(exc, 500) or "search acquisition failed", "results_found": 0})
    return merged, attempts


def _reference_kind(url: str) -> str | None:
    host = _host(url)
    if _is_domain_or_subdomain(host, "wikipedia.org"):
        return "wikipedia"
    if _is_domain_or_subdomain(host, "fandom.com"):
        return "fandom"
    return None


def select_source_candidates(results: list[SearchResult], wikipedia: SearchResult | None = None, fandom: SearchResult | None = None) -> list[dict[str, Any]]:
    organic: list[SearchResult] = []
    discovered_wikipedia = wikipedia
    discovered_fandom = fandom
    for result in results:
        ref_kind = _reference_kind(result.url)
        if ref_kind == "wikipedia":
            discovered_wikipedia = discovered_wikipedia or result
            continue
        if ref_kind == "fandom":
            discovered_fandom = discovered_fandom or result
            continue
        organic.append(result)
        if len(organic) >= ORGANIC_SOURCE_TARGET:
            break
    selected: list[dict[str, Any]] = []
    for index, result in enumerate(organic, 1):
        selected.append({"role": "organic", "rank": index, "title": result.title, "url": result.url, "snippet": result.snippet, "engine": result.engine})
    for role, result in (("wikipedia", discovered_wikipedia), ("fandom", discovered_fandom)):
        if result:
            selected.append({"role": role, "rank": getattr(result, "rank", None), "title": result.title, "url": result.url, "snippet": result.snippet, "engine": result.engine})
    return selected


__all__ = [name for name in globals() if not name.startswith("__")]
