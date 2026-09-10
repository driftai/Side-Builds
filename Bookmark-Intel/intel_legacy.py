from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; BookmarkIntel/0.10; +https://github.com/driftai/Side-Builds)"
MAX_BODY_BYTES = 3_000_000
MAX_REDIRECTS = 6
TIMEOUT_SECONDS = 18.0
CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")

SCHEMA_TYPES = {
    "article": {"Article", "NewsArticle", "BlogPosting", "TechArticle", "Report"},
    "video": {"VideoObject", "Movie", "TVEpisode", "TVSeries"},
    "product": {"Product", "Offer", "IndividualProduct"},
    "software": {"SoftwareApplication", "WebApplication", "MobileApplication"},
    "paper": {"ScholarlyArticle", "MedicalScholarlyArticle"},
    "game": {"VideoGame"},
    "person": {"Person"},
    "organization": {"Organization", "Corporation", "LocalBusiness"},
}

TAG_PATTERNS: dict[str, list[str]] = {
    "ai": [r"\b(?:artificial intelligence|machine learning|deep learning|llm|llms|neural network|generative ai|transformer|embeddings?)\b"],
    "programming": [r"\b(?:programming|developer|source code|api|sdk|library|framework|repo|repository|git)\b"],
    "python": [r"\b(?:python|pypi|cpython|fastapi|django|flask|pytorch)\b"],
    "javascript": [r"\b(?:javascript|typescript|nodejs|npm|react|vue|angular|svelte|nextjs)\b"],
    "rust": [r"\b(?:rust|cargo|crates\.io)\b"],
    "go": [r"\b(?:golang|go language)\b"],
    "database": [r"\b(?:database|sql|nosql|postgres|postgresql|sqlite|redis|mongodb)\b"],
    "security": [r"\b(?:security|vulnerability|cve|exploit|cryptography|authentication|auth)\b"],
    "documentation": [r"\b(?:documentation|docs|api reference|guide|tutorial|manual)\b"],
    "open-source": [r"\b(?:open source|open-source|oss|github\.com|gitlab\.com)\b"],
    "video": [r"\b(?:video|youtube|vimeo|twitch)\b"],
    "news": [r"\b(?:breaking news|investigative report|dispatch|journalism)\b"],
    "shopping": [r"\b(?:shopping|ecommerce|add to cart|checkout|buy now)\b"],
    "social": [r"\b(?:social media|tweet|instagram|tiktok|threads\.net)\b"],
    "gaming": [r"\b(?:video game|gameplay|steam|playstation|xbox|nintendo|rpg)\b"],
    "anime": [r"\b(?:anime|crunchyroll|myanimelist|anilist|animation studio)\b"],
    "manga": [r"\b(?:manga|manhwa|manhua|webtoon|chapter)\b"],
    "music": [r"\b(?:music|album|artist|discography|track|spotify|soundcloud)\b"],
    "research": [r"\b(?:research paper|arxiv|abstract|citation|academic|peer-reviewed)\b"],
    "devops": [r"\b(?:devops|docker|kubernetes|ci/cd|infrastructure|cloud)\b"],
}

RESERVED_GITHUB_ROOTS = {
    "about", "account", "actions", "blog", "collections", "contact", "enterprise",
    "events", "explore", "features", "issues", "login", "marketplace", "mobile",
    "organizations", "orgs", "pricing", "pulls", "readme", "search", "security",
    "settings", "signup", "site-policy", "sponsors", "topics", "trending",
}

BOILERPLATE_LINK_TERMS = {
    "terms", "privacy", "cookie", "cookies", "signup", "sign-up", "sign_up",
    "login", "signin", "sign-in", "pricing", "whitepaper", "whitepapers",
    "sponsors", "sponsor", "contact", "report-content", "about", "careers",
    "help", "site-policy", "legal", "subscribe", "newsletter",
}


class AnalyzeError(RuntimeError):
    pass


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    redirects: list[str]
    status_code: int
    content_type: str
    text: str
    byte_count: int


def _clean_text(value: Any, limit: int | None = None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", unescape(str(value))).strip()
    text = re.sub(r"\s+([,.:;?!])", r"\1", text)
    if not text:
        return None
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _first(*values: Any) -> str | None:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return None


def _safe_network_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url:
        raise AnalyzeError("URL is empty.")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AnalyzeError("Only absolute http:// or https:// URLs are supported.")
    if parsed.username or parsed.password:
        raise AnalyzeError("Credentials in URLs are not allowed.")
    host = parsed.hostname.rstrip(".")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AnalyzeError(f"Could not resolve host: {host}") from exc
    for info in infos:
        ip_str = info[4][0].split("%")[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise AnalyzeError(f"Invalid resolved IP for host {host}: {ip_str}")
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if ip in CGNAT_NET or any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_reserved, ip.is_multicast, ip.is_unspecified)):
            raise AnalyzeError(f"Refusing non-public address for host: {host}")
    return raw_url


def fetch_url(raw_url: str) -> FetchResult:
    current = _safe_network_url(raw_url)
    redirects: list[str] = []
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    deadline = time.monotonic() + TIMEOUT_SECONDS
    with httpx.Client(headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if time.monotonic() > deadline:
                raise AnalyzeError(f"Request exceeded total fetch deadline of {TIMEOUT_SECONDS}s.")
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise AnalyzeError(f"Redirect {response.status_code} had no Location header.")
                    next_url = _safe_network_url(urljoin(current, location))
                    if next_url in redirects:
                        raise AnalyzeError(f"Circular redirect detected: {next_url}")
                    redirects.append(next_url)
                    current = next_url
                    continue
                if response.status_code >= 400:
                    raise AnalyzeError(f"Remote server returned HTTP {response.status_code}.")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise AnalyzeError(f"Streaming exceeded total fetch deadline of {TIMEOUT_SECONDS}s.")
                    total += len(chunk)
                    if total > MAX_BODY_BYTES:
                        raise AnalyzeError(f"Page body exceeded {MAX_BODY_BYTES:,} bytes; refusing oversized fetch.")
                    chunks.append(chunk)
                body = b"".join(chunks)

                encoding = response.encoding
                if not encoding or encoding.lower() in {"iso-8859-1", "ascii"}:
                    head_sample = body[:2048].decode("ascii", errors="ignore")
                    charset_match = re.search(r'''<meta[^>]+charset=["']?([a-zA-Z0-9_-]+)''', head_sample, re.I)
                    if charset_match:
                        encoding = charset_match.group(1)
                    else:
                        encoding = "utf-8"

                try:
                    text = body.decode(encoding, errors="replace")
                except Exception:
                    text = body.decode("utf-8", errors="replace")

                return FetchResult(
                    requested_url=raw_url,
                    final_url=current,
                    redirects=redirects,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", "").split(";", 1)[0].lower(),
                    text=text,
                    byte_count=len(body),
                )
    raise AnalyzeError(f"Too many redirects (>{MAX_REDIRECTS}).")


def _meta(soup: BeautifulSoup, *keys: str) -> str | None:
    for key in keys:
        tag = (
            soup.find("meta", attrs={"property": re.compile(f"^{re.escape(key)}$", re.I)})
            or soup.find("meta", attrs={"name": re.compile(f"^{re.escape(key)}$", re.I)})
            or soup.find("meta", attrs={"itemprop": re.compile(f"^{re.escape(key)}$", re.I)})
        )
        if tag and tag.get("content"):
            cleaned = _clean_text(tag.get("content"))
            if cleaned:
                return cleaned
    return None


def _meta_all(soup: BeautifulSoup, *keys: str) -> list[str]:
    results: list[str] = []
    for key in keys:
        tags = soup.find_all(
            "meta",
            attrs={"name": re.compile(f"^{re.escape(key)}$", re.I)},
        ) + soup.find_all(
            "meta",
            attrs={"property": re.compile(f"^{re.escape(key)}$", re.I)},
        )
        for tag in tags:
            content = tag.get("content")
            if content:
                cleaned = _clean_text(content)
                if cleaned and cleaned not in results:
                    results.append(cleaned)
    return results


def _jsonld_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            found.append(value)
            graph = value.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return found


def _types(items: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for item in items:
        value = item.get("@type")
        if isinstance(value, str):
            out.add(value)
        elif isinstance(value, list):
            out.update(str(v) for v in value if isinstance(v, str))
    return out


def _main_text(soup: BeautifulSoup) -> tuple[str, list[str], list[str]]:
    candidates = [
        soup.find("main"),
        soup.find(attrs={"role": "main"}),
        soup.find(id=re.compile(r"^(?:content|main-content|article|post|readme)$", re.I)),
        soup.find(class_=re.compile(r"(?:markdown-body|entry-content|post-content|article-content|main-content)", re.I)),
        soup.find("article"),
    ]
    valid_candidates = [c for c in candidates if c and len(c.get_text(strip=True)) >= 150]
    root = valid_candidates[0] if valid_candidates else (soup.body or soup)

    headings: list[str] = []
    for h in root.find_all(["h1", "h2", "h3", "h4"]):
        t = _clean_text(h.get_text(" ", strip=True), 180)
        if t and t not in headings:
            headings.append(t)

    blocks: list[str] = []
    seen_blocks: set[str] = set()

    for el in root.find_all(["p", "blockquote", "li", "pre", "div", "section"]):
        if el.find_parent(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]):
            continue
        if el.name == "pre":
            pre_text = el.get_text()
            chunks = [c.strip() for c in pre_text.split("\n\n") if len(c.strip()) >= 35]
            for chunk in chunks:
                cleaned = _clean_text(chunk, 1200)
                if cleaned:
                    norm = cleaned[:80].lower()
                    if norm not in seen_blocks:
                        seen_blocks.add(norm)
                        blocks.append(cleaned)
            continue
        if el.name in {"div", "section"}:
            nested_block_children = el.find_all(["p", "blockquote", "div", "section", "pre"])
            if len(nested_block_children) > 1:
                continue

        cleaned = _clean_text(el.get_text(" ", strip=True), 1200)
        if not cleaned or len(cleaned) < 35:
            continue
        norm = cleaned[:80].lower()
        if norm in seen_blocks:
            continue
        seen_blocks.add(norm)
        blocks.append(cleaned)
        if len(blocks) >= 35:
            break

    if not blocks:
        for script_id in ("__NEXT_DATA__", "__NUXT_DATA__"):
            script = soup.find("script", id=script_id)
            if script and script.string:
                try:
                    js_data = json.loads(script.string)
                    props = js_data.get("props", {}).get("pageProps", {})
                    for candidate_key in ("description", "content", "summary", "overview", "body"):
                        candidate_val = props.get(candidate_key)
                        if isinstance(candidate_val, str) and len(candidate_val) >= 40:
                            cleaned = _clean_text(candidate_val, 1200)
                            if cleaned:
                                blocks.append(cleaned)
                except Exception:
                    pass

    full_text = _clean_text(" ".join(blocks[:25]), 12_000) or ""
    return full_text, blocks[:35], headings[:30]


def _entity_name(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean_text(value, 180)
    if isinstance(value, dict):
        return _clean_text(value.get("name") or value.get("headline") or value.get("title"), 180)
    return None


def _extract_entities(items: list[dict[str, Any]], soup: BeautifulSoup, url: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_entity(kind: str, name: str | None) -> None:
        if not name:
            return
        cleaned = _clean_text(name, 180)
        if not cleaned or len(cleaned) < 2:
            return
        key = (kind.lower(), cleaned.lower())
        if key not in seen and kind not in {"WebPage", "WebSite", "BreadcrumbList", "ListItem"}:
            seen.add(key)
            entities.append({"type": kind, "name": cleaned})

    for item in items:
        raw_type = item.get("@type")
        types = [raw_type] if isinstance(raw_type, str) else raw_type if isinstance(raw_type, list) else []
        name = _clean_text(item.get("name") or item.get("headline"), 180)
        if name and types:
            add_entity(str(types[0]), name)
        for field, kind in (
            ("author", "Person/Author"),
            ("creator", "Creator"),
            ("publisher", "Organization/Publisher"),
            ("brand", "Brand"),
            ("director", "Director"),
            ("actor", "Actor"),
        ):
            candidate = _entity_name(item.get(field))
            if candidate:
                add_entity(kind, candidate)

    site_name = _meta(soup, "og:site_name", "application-name")
    if site_name:
        add_entity("Publisher/Site", site_name)

    author = _meta(soup, "author", "article:author", "citation_author", "twitter:creator")
    if not author:
        author_link = soup.find("a", attrs={"rel": re.compile(r"\bauthor\b", re.I)}) or soup.find("a", href=re.compile(r"/(?:user|author|profile)/", re.I))
        if author_link:
            author = _clean_text(author_link.get_text(strip=True), 80)
    if author:
        if author.startswith("@"):
            add_entity("Social/Creator", author)
        else:
            parts = list(dict.fromkeys(p.strip() for p in author.split(",") if len(p.strip()) >= 2))
            for part in parts:
                add_entity("Person/Author", part)

    for cit_author in _meta_all(soup, "citation_author"):
        add_entity("Person/Author", cit_author)

    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if "github.com" in domain and len(path_parts) >= 2 and path_parts[0] not in RESERVED_GITHUB_ROOTS:
        add_entity("Software/Repository", f"{path_parts[0]}/{path_parts[1]}")
        add_entity("Organization/Owner", path_parts[0])

    if "arxiv.org" in domain:
        paper_title = _meta(soup, "citation_title")
        if paper_title:
            add_entity("Academic/Paper", paper_title)

    if "store.steampowered.com" in domain and len(path_parts) >= 2:
        game_title = _meta(soup, "twitter:title", "og:title")
        if not game_title and soup.title:
            game_title = soup.title.get_text(strip=True)
        if not game_title:
            h1 = soup.find("h1")
            if h1:
                game_title = h1.get_text(strip=True)
        if game_title:
            cleaned_title = re.sub(r"\s+on Steam$", "", game_title, flags=re.I)
            add_entity("Game", cleaned_title)

    if "myanimelist.net" in domain and len(path_parts) >= 2:
        title_tag = soup.find("h1", class_="title-name")
        if title_tag:
            add_entity("Anime/Manga", title_tag.get_text(strip=True))

    return entities[:40]


def _classification(url: str, title: str, description: str, text: str, schema_types: set[str], soup: BeautifulSoup) -> dict[str, Any]:
    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    corpus = " ".join([domain, path, title, description, text[:6000]]).lower()

    scores: dict[str, int] = {
        "github_repository": 0,
        "academic_paper": 0,
        "documentation": 0,
        "software_tool": 0,
        "forum_discussion": 0,
        "anime_manga": 0,
        "gaming": 0,
        "video": 0,
        "article": 0,
        "product": 0,
        "social_post": 0,
        "general_webpage": 1,
    }
    reasons: dict[str, list[str]] = {key: [] for key in scores}

    def add(kind: str, points: int, reason: str) -> None:
        scores[kind] += points
        reasons[kind].append(reason)

    path_parts = [p for p in path.split("/") if p]

    if domain in {"github.com", "www.github.com"}:
        if len(path_parts) >= 2 and path_parts[0] not in RESERVED_GITHUB_ROOTS:
            add("github_repository", 12, "GitHub owner/repository URL pattern")
    elif "gitlab.com" in domain and len(path_parts) >= 2:
        add("github_repository", 10, "GitLab repository URL pattern")
    elif "huggingface.co" in domain and len(path_parts) >= 2 and path_parts[0] not in {"models", "datasets", "spaces", "docs", "blog", "pricing"}:
        add("github_repository", 9, "Hugging Face model repository pattern")

    if any(host in domain for host in ("arxiv.org", "openreview.net", "biorxiv.org", "medrxiv.org", "semanticscholar.org", "doi.org")):
        add("academic_paper", 12, "academic preprint or journal domain")
    elif any(t in schema_types for t in SCHEMA_TYPES["paper"]):
        add("academic_paper", 10, "scholarly article schema type")
    elif _meta(soup, "citation_title") or _meta(soup, "citation_author") or _meta(soup, "citation_pdf_url"):
        add("academic_paper", 10, "Highwire Press academic citation metadata")

    if any(host in domain for host in ("myanimelist.net", "anilist.co", "mangadex.org", "crunchyroll.com", "webtoons.com", "mangaupdates.com")):
        add("anime_manga", 12, "anime/manga database domain")
    elif any(p in path for p in ("/anime/", "/manga/", "/manhwa/", "/webtoon/")):
        add("anime_manga", 8, "anime/manga path structure")
    elif any(re.search(pat, corpus) for pat in TAG_PATTERNS["anime"] + TAG_PATTERNS["manga"]):
        add("anime_manga", 3, "anime/manga terminology")

    if any(host in domain for host in ("store.steampowered.com", "gog.com", "itch.io", "epicgames.com", "playstation.com", "nintendo.com")):
        add("gaming", 12, "game store/platform domain")
    elif any(t in schema_types for t in SCHEMA_TYPES["game"]):
        add("gaming", 10, "video game schema.org type")
    elif "/app/" in path and "steam" in domain:
        add("gaming", 10, "Steam application/game URL")

    if any(host in domain for host in ("news.ycombinator.com", "reddit.com", "old.reddit.com", "lobste.rs", "stackoverflow.com", "stackexchange.com")):
        add("forum_discussion", 12, "discussion platform domain")
    elif domain.startswith("forum.") or any(p in path for p in ("/comments/", "/discussion/", "/threads/", "/item?id=")):
        add("forum_discussion", 9, "discussion path/subdomain signal")

    if any(host in domain for host in ("youtube.com", "youtu.be", "vimeo.com", "twitch.tv", "bilibili.com")):
        add("video", 12, "video platform domain")
    elif any(t in schema_types for t in SCHEMA_TYPES["video"]):
        add("video", 9, "video/media schema.org type")

    if domain.startswith("docs.") or any(p in path for p in ("/docs", "/documentation", "/api-reference", "/reference", "/guide", "/tutorial")):
        add("documentation", 8, "documentation URL structure")
    elif any(term in corpus for term in ("developer guide", "api reference", "getting started tutorial")):
        add("documentation", 5, "documentation content signals")

    if any(host in domain for host in ("pypi.org", "npmjs.com", "crates.io")):
        add("software_tool", 11, "package registry domain")
    elif any(t in schema_types for t in SCHEMA_TYPES["software"]):
        add("software_tool", 9, "software schema.org type")
    elif re.search(r"\b(?:download\s+(?:v?[\d.]+|app|installer|release)|pip install|npm install|cargo add)\b", corpus):
        add("software_tool", 4, "software package installation syntax")

    if any(t in schema_types for t in SCHEMA_TYPES["article"]):
        add("article", 9, "article schema.org type")
    else:
        has_author = bool(_meta(soup, "author", "article:author", "twitter:creator")) or bool(soup.find("a", attrs={"rel": re.compile(r"\bauthor\b", re.I)})) or bool(soup.find("a", href=re.compile(r"/(?:user|author|profile)/", re.I)))
        has_published = bool(_meta(soup, "article:published_time", "date", "datePublished"))
        has_body_text = len(text) > 450
        has_article_path = any(p in path for p in ("/essay/", "/article/", "/story/", "/blog/", "/posts/", "/p/")) or domain.startswith("blog.")
        if has_article_path:
            if len(text) >= 120:
                add("article", 8, "article/essay URL path structure and reading text")
            else:
                add("article", 4, "article/essay URL path structure")
        elif has_author and has_published and has_body_text:
            add("article", 8, "byline, date, and substantial article text")
        elif has_author and len(text) >= 150:
            add("article", 6, "author byline and editorial text")
        elif len(text) >= 1200:
            add("article", 6, "substantial long-form reading text")
        elif has_body_text and any(term in corpus for term in ("published", "read time", "words", "essay")):
            add("article", 3, "editorial vocabulary")

    if any(t in schema_types for t in SCHEMA_TYPES["product"]):
        add("product", 9, "product schema.org type")
    elif re.search(r"[$€£¥]\s?\d+(?:\.\d{2})?", corpus) and any(term in corpus for term in ("add to cart", "checkout", "in stock", "free shipping")):
        add("product", 8, "verified price currency and shopping actions")

    if any(host in domain for host in ("instagram.com", "tiktok.com", "x.com", "twitter.com", "threads.net", "bsky.app")):
        add("social_post", 10, "social network domain")

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    kind, top = ordered[0]
    runner = ordered[1][1]
    confidence = round(min(0.99, 0.50 + (top - runner) * 0.06 + min(top, 10) * 0.025), 2)

    category_map = {
        "github_repository": "Technology / Source Code",
        "academic_paper": "Research / Paper",
        "documentation": "Technology / Documentation",
        "software_tool": "Technology / Tool",
        "forum_discussion": "Community / Discussion",
        "anime_manga": "Media / Anime & Manga",
        "gaming": "Gaming / Game",
        "video": "Media / Video",
        "article": "Reading / Article",
        "product": "Shopping / Product",
        "social_post": "Social / Post",
        "general_webpage": "Web / General",
    }

    return {
        "kind": kind,
        "category": category_map[kind],
        "confidence": confidence,
        "signals": reasons[kind][:6],
        "alternatives": [{"kind": k, "score": v} for k, v in ordered[1:4] if v > 1],
    }


def _extract_tags(corpus: str, classification: dict[str, Any], soup: BeautifulSoup) -> list[str]:
    low = corpus.lower()
    tags: list[str] = [classification["kind"].replace("_", "-")]

    raw_keywords = _meta(soup, "keywords")
    if raw_keywords:
        for kw in re.split(r"[,;]+", raw_keywords):
            cleaned = _clean_text(kw.strip().lower(), 32)
            if cleaned and 2 <= len(cleaned) <= 28 and cleaned not in tags:
                tags.append(cleaned.replace(" ", "-"))

    for tag_name, patterns in TAG_PATTERNS.items():
        if tag_name == "shopping" and classification["kind"] not in {"product"}:
            continue
        if tag_name == "video" and classification["kind"] not in {"video"}:
            if not any(h in low for h in ("youtube.com", "vimeo.com")):
                continue
        if any(re.search(pat, low) for pat in patterns):
            if tag_name not in tags:
                tags.append(tag_name)

    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:16]


def _important_links(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    parsed_base = urlparse(base_url)
    base_domain = (parsed_base.hostname or "").lower()
    scored: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    internal = external = 0

    main_container = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_=re.compile(r"markdown-body|entry-content", re.I))
    )

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        clean = parsed._replace(fragment="").geturl()
        if clean in seen:
            continue
        seen.add(clean)

        label = _clean_text(a.get_text(" ", strip=True) or a.get("aria-label") or a.get("title"), 120) or parsed.hostname
        link_domain = (parsed.hostname or "").lower()
        is_external = link_domain != base_domain
        external += int(is_external)
        internal += int(not is_external)

        low = f"{label} {clean}".lower()

        if any(term in low for term in BOILERPLATE_LINK_TERMS):
            continue

        if "github.com" in base_domain:
            if any(host in link_domain for host in ("docs.github.com", "github.blog", "archiveprogram.github.com", "support.github.com")):
                continue
            if link_domain in {"github.com", "www.github.com"}:
                parts = [p for p in parsed.path.split("/") if p]
                if not parts or parts[0] in RESERVED_GITHUB_ROOTS or len(parts) == 1:
                    continue

        score = 1
        if main_container and a.find_parent(lambda tag: tag == main_container):
            score += 4

        if any(k in low for k in ("github.com", "gitlab.com", "crates.io", "pypi.org", "npmjs.com")):
            score += 5
        if any(k in low for k in ("docs", "documentation", "readthedocs.io", "api")):
            score += 4
        if any(k in low for k in ("paper", "arxiv.org", "pdf", "doi.org")):
            score += 5
        if any(k in low for k in ("demo", "live preview", "official site", "release", "download")):
            score += 4

        if score >= 3:
            scored.append((score, {"label": label, "url": clean, "relationship": "external" if is_external else "internal"}))

    scored.sort(key=lambda item: (-item[0], item[1]["url"]))
    return {"internal_count": internal, "external_count": external, "important": [item[1] for item in scored[:20]]}


def _special_sections(
    items: list[dict[str, Any]],
    soup: BeautifulSoup,
    classification: dict[str, Any],
    final_url: str,
    main_text: str,
) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    kind = classification["kind"]
    parsed = urlparse(final_url)
    domain = (parsed.hostname or "").lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if kind in {"github_repository", "documentation", "software_tool"}:
        technical: dict[str, Any] = {}
        generator = _meta(soup, "generator")
        if generator:
            technical["generator"] = generator

        if "github.com" in domain and len(path_parts) >= 2 and path_parts[0] not in RESERVED_GITHUB_ROOTS:
            owner, repo = path_parts[0], path_parts[1]
            technical["repository_owner"] = owner
            technical["repository_name"] = repo
            technical["repository_url"] = f"https://github.com/{owner}/{repo}"

            ecosystem = None
            if soup.find("a", href=re.compile(r"setup\.py|pyproject\.toml|requirements\.txt")):
                ecosystem = "Python"
            elif soup.find("a", href=re.compile(r"Cargo\.toml")):
                ecosystem = "Rust"
            elif soup.find("a", href=re.compile(r"package\.json")):
                ecosystem = "JavaScript/TypeScript"
            elif soup.find("a", href=re.compile(r"go\.mod")):
                ecosystem = "Go"
            if ecosystem:
                technical["detected_ecosystem"] = ecosystem

            license_tag = soup.find("a", href=lambda h: h and "LICENSE" in h.upper())
            if license_tag:
                technical["license"] = license_tag.get_text(strip=True) or "Repository License"

        if technical:
            sections["technical"] = technical

    if kind == "academic_paper" or "arxiv.org" in domain:
        academic: dict[str, Any] = {}
        paper_title = _meta(soup, "citation_title") or _meta(soup, "og:title")
        if paper_title:
            academic["paper_title"] = paper_title
        authors = _meta_all(soup, "citation_author")
        if authors:
            academic["authors"] = authors[:8]
        date = _meta(soup, "citation_date", "citation_publication_date")
        if date:
            academic["publication_date"] = date
        pdf = _meta(soup, "citation_pdf_url")
        if pdf:
            academic["pdf_url"] = pdf
        doi = _meta(soup, "citation_doi")
        if doi:
            academic["doi"] = doi
        if academic:
            sections["academic"] = academic

    if kind == "article":
        editorial: dict[str, Any] = {}
        author = _first(_meta(soup, "author", "article:author", "twitter:creator"), *[_entity_name(i.get("author")) for i in items])
        if not author:
            author_link = soup.find("a", attrs={"rel": re.compile(r"\bauthor\b", re.I)}) or soup.find("a", href=re.compile(r"/(?:user|author|profile)/", re.I))
            if author_link:
                author = _clean_text(author_link.get_text(strip=True), 80)
        published = _first(_meta(soup, "article:published_time", "date", "datePublished"), *[i.get("datePublished") for i in items])
        modified = _first(_meta(soup, "article:modified_time", "last-modified", "dateModified"), *[i.get("dateModified") for i in items])
        if author:
            editorial["author"] = author
        if published:
            editorial["published_date"] = published
        if modified:
            editorial["modified_date"] = modified
        words = len(main_text.split()) if main_text else 0
        if words > 20:
            editorial["word_count"] = words
            editorial["reading_time_minutes"] = max(1, round(words / 220))
        if editorial:
            sections["editorial"] = editorial

    if kind in {"video", "media_page"}:
        media: dict[str, Any] = {}
        upload_date = _first(_meta(soup, "uploadDate", "article:published_time"), *[i.get("uploadDate") for i in items])
        if upload_date:
            media["upload_date"] = upload_date
        duration = _first(_meta(soup, "video:duration"), *[i.get("duration") for i in items])
        if duration:
            media["duration"] = duration
        creator = _first(_meta(soup, "author", "twitter:creator"), *[_entity_name(i.get("author") or i.get("creator")) for i in items])
        if creator:
            media["creator"] = creator
        if media:
            sections["media"] = media

    if kind == "anime_manga":
        anime_data: dict[str, Any] = {}
        score_tag = soup.find(class_=re.compile(r"score-label|ratingValue", re.I))
        if score_tag:
            anime_data["score"] = score_tag.get_text(strip=True)
        if "/anime/" in final_url:
            anime_data["media_type"] = "Anime"
        elif "/manga/" in final_url:
            anime_data["media_type"] = "Manga"
        if anime_data:
            sections["anime_manga"] = anime_data

    if kind == "gaming":
        gaming: dict[str, Any] = {}
        dev_tag = soup.find(class_=re.compile(r"dev_row|developer", re.I))
        if dev_tag:
            gaming["developer"] = dev_tag.get_text(" ", strip=True)
        release_tag = soup.find(class_=re.compile(r"release_date|date", re.I))
        if release_tag:
            gaming["release_date"] = release_tag.get_text(" ", strip=True)
        if gaming:
            sections["gaming"] = gaming

    if kind == "forum_discussion":
        comm: dict[str, Any] = {}
        comm["platform"] = "Hacker News" if "news.ycombinator.com" in domain else "Reddit" if "reddit.com" in domain else domain
        comm["thread_url"] = final_url
        sections["community"] = comm

    commercial: dict[str, Any] = {}
    for item in items:
        offer = item.get("offers")
        offers = offer if isinstance(offer, list) else [offer] if isinstance(offer, dict) else []
        for entry in offers:
            price = entry.get("price") or entry.get("lowPrice")
            if price is not None:
                commercial["price"] = str(price)
            if entry.get("priceCurrency"):
                commercial["currency"] = str(entry["priceCurrency"])
            if entry.get("availability"):
                commercial["availability"] = str(entry["availability"]).rsplit("/", 1)[-1]
    if commercial and kind == "product":
        sections["commercial"] = commercial

    return sections


def _key_facts(items: list[dict[str, Any]], meta: dict[str, Any], sections: dict[str, Any]) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(label: str, value: Any, source: str) -> None:
        text = _clean_text(value, 240)
        if text and (label, text) not in seen:
            seen.add((label, text))
            facts.append({"label": label, "value": text, "source": source})

    add("Author", meta.get("author"), "metadata")
    add("Published", meta.get("published"), "metadata")
    add("Modified", meta.get("modified"), "metadata")

    tech = sections.get("technical", {})
    if tech.get("detected_ecosystem"):
        add("Ecosystem / Language", tech["detected_ecosystem"], "analysis")
    if tech.get("license"):
        add("License", tech["license"], "repository")

    acad = sections.get("academic", {})
    if acad.get("publication_date"):
        add("Preprint / Paper Date", acad["publication_date"], "citation")
    if acad.get("pdf_url"):
        add("PDF Fulltext", acad["pdf_url"], "citation")

    med = sections.get("media", {})
    if med.get("upload_date"):
        add("Upload Date", med["upload_date"], "media")
    if med.get("duration"):
        add("Duration", med["duration"], "media")

    for item in items:
        add("Creator", _entity_name(item.get("creator")), "json-ld")
        add("Publisher", _entity_name(item.get("publisher")), "json-ld")
        add("Version", item.get("softwareVersion"), "json-ld")
        add("Operating system", item.get("operatingSystem"), "json-ld")
        add("Application category", item.get("applicationCategory"), "json-ld")
        add("Genre", item.get("genre"), "json-ld")

    return facts[:24]


def _suggest_bookmark(
    classification: dict[str, Any],
    title: str,
    final_url: str,
    tags: list[str],
    sections: dict[str, Any],
) -> dict[str, Any]:
    kind = classification["kind"]
    parsed = urlparse(final_url)
    domain = (parsed.hostname or "").lower()

    folder = classification["category"]
    if kind == "github_repository":
        eco = sections.get("technical", {}).get("detected_ecosystem")
        folder = f"Technology / Source Code / {eco}" if eco else "Technology / Source Code"
    elif kind == "academic_paper":
        if "ai" in tags or "research" in tags:
            folder = "Research / Papers / AI & ML"
        else:
            folder = "Research / Papers"
    elif kind == "forum_discussion":
        if "news.ycombinator.com" in domain:
            folder = "Community / Discussions / Hacker News"
        elif "reddit.com" in domain:
            folder = "Community / Discussions / Reddit"
        else:
            folder = "Community / Discussions"
    elif kind == "anime_manga":
        folder = "Media / Anime & Manga"
    elif kind == "gaming":
        folder = "Gaming / Games"
    elif kind == "article":
        if "programming" in tags or "ai" in tags:
            folder = "Reading / Tech Essays & Blogs"
        else:
            folder = "Reading / Articles"

    if kind == "github_repository":
        repo_name = sections.get("technical", {}).get("repository_name", title)
        eco_note = f" ({sections.get('technical', {}).get('detected_ecosystem')} ecosystem)" if sections.get("technical", {}).get("detected_ecosystem") else ""
        why = f"Developer reference and source code repository for {repo_name}{eco_note}."
    elif kind == "academic_paper":
        paper_name = sections.get("academic", {}).get("paper_title", title)
        why = f"Scientific research paper on {paper_name}."
    elif kind == "forum_discussion":
        platform = sections.get("community", {}).get("platform", "online community")
        why = f"Community discussion thread on {platform} concerning {title}."
    elif kind == "anime_manga":
        why = f"Media database entry and reference tracking for {title}."
    elif kind == "gaming":
        why = f"Store page and release reference for video game {title}."
    elif kind == "documentation":
        why = f"Technical documentation and reference manual for {title}."
    elif kind == "video":
        why = f"Streaming video content covering {title}."
    else:
        why = f"Reference bookmark classified under {folder} for {title}."

    return {
        "suggested_folder": folder,
        "suggested_title": title,
        "suggested_tags": tags,
        "why_it_might_matter": why,
    }


def analyze_html(fetch: FetchResult) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    if fetch.content_type and not any(token in fetch.content_type for token in ("html", "xml", "json", "text")):
        return {
            "schema_version": 1,
            "input": {"url": fetch.requested_url},
            "fetch": {
                "final_url": fetch.final_url,
                "status_code": fetch.status_code,
                "content_type": fetch.content_type,
                "bytes": fetch.byte_count,
                "redirects": fetch.redirects,
                "fetched_at": now,
            },
            "identity": {"domain": urlparse(fetch.final_url).hostname, "content_type": fetch.content_type},
            "classification": {
                "kind": "non_html_resource",
                "category": "Web / File",
                "confidence": 0.98,
                "signals": ["non-HTML response"],
                "alternatives": [],
            },
            "summary": "The URL resolves to a non-HTML resource. This proof of concept records the resource but does not inspect binary contents yet.",
            "tags": ["non-html-resource"],
            "key_facts": [],
            "entities": [],
            "links": {"internal_count": 0, "external_count": 0, "important": []},
            "sections": {},
            "bookmark": {
                "suggested_folder": "Web / Files",
                "suggested_title": urlparse(fetch.final_url).path.rsplit("/", 1)[-1] or fetch.final_url,
                "why_it_might_matter": "Direct file/resource bookmark; binary analysis is intentionally out of scope for v0.1.",
            },
            "quality": {
                "extraction_mode": "deterministic",
                "warnings": ["Binary/non-HTML body was not semantically analyzed."],
                "missing": ["page text", "structured metadata"],
            },
        }

    soup = BeautifulSoup(fetch.text, "html.parser")
    items = _jsonld_items(soup)
    schema_types = _types(items)
    main_text, paragraphs, headings = _main_text(soup)

    title = (
        _first(
            _meta(soup, "citation_title", "og:title", "twitter:title"),
            soup.title.get_text(strip=True) if soup.title else None,
            headings[0] if headings else None,
        )
        or fetch.final_url
    )

    description = _first(_meta(soup, "description", "og:description", "twitter:description"), paragraphs[0] if paragraphs else None) or ""
    site_name = _first(_meta(soup, "og:site_name", "application-name"), urlparse(fetch.final_url).hostname)

    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = urljoin(fetch.final_url, canonical_tag.get("href")) if canonical_tag and canonical_tag.get("href") else None

    author = _first(_meta(soup, "author", "article:author", "citation_author", "twitter:creator"), *[_entity_name(i.get("author")) for i in items])
    if not author:
        byline_tag = (
            soup.find("a", href=re.compile(r"^/(?:user|author|profile|by)/", re.I))
            or soup.find(attrs={"rel": "author"})
            or soup.find(class_=re.compile(r"\b(?:author|byline)\b", re.I))
        )
        if byline_tag:
            cand_author = _clean_text(byline_tag.get_text(" ", strip=True), 50)
            if cand_author and len(cand_author) < 40 and not any(k in cand_author.lower() for k in ("reply", "comment", "share", "login", "home")):
                author = cand_author

    published = _first(_meta(soup, "article:published_time", "citation_date", "citation_publication_date", "date", "datePublished"), *[i.get("datePublished") for i in items])
    modified = _first(_meta(soup, "article:modified_time", "last-modified", "dateModified"), *[i.get("dateModified") for i in items])
    language = _first(soup.html.get("lang") if soup.html else None, _meta(soup, "content-language"))

    meta = {"author": author, "published": published, "modified": modified}
    classification = _classification(fetch.final_url, title, description, main_text, schema_types, soup)
    corpus = " ".join([title, description, " ".join(headings[:20]), main_text[:8000], fetch.final_url])
    tags = _extract_tags(corpus, classification, soup)

    summary_source = description if len(description) >= 60 else " ".join(paragraphs[:3])
    summary = _clean_text(summary_source, 900) or "No meaningful page summary could be extracted."

    entities = _extract_entities(items, soup, fetch.final_url)
    if author and not any(e["name"].lower() == author.lower() for e in entities):
        entities.append({"type": "Person/Author", "name": author})
    links = _important_links(soup, fetch.final_url)
    sections = _special_sections(items, soup, classification, fetch.final_url, main_text)
    bookmark = _suggest_bookmark(classification, title, fetch.final_url, tags, sections)

    missing = [
        name
        for name, value in (
            ("description", description),
            ("author", author),
            ("published date", published),
            ("structured entities", entities),
        )
        if not value
    ]

    return {
        "schema_version": 1,
        "input": {"url": fetch.requested_url},
        "fetch": {
            "final_url": fetch.final_url,
            "status_code": fetch.status_code,
            "content_type": fetch.content_type,
            "bytes": fetch.byte_count,
            "redirects": fetch.redirects,
            "fetched_at": now,
        },
        "identity": {
            "domain": urlparse(fetch.final_url).hostname,
            "title": title,
            "site_name": site_name,
            "description": description or None,
            "language": language,
            "canonical_url": canonical,
            "schema_types": sorted(schema_types),
        },
        "classification": classification,
        "summary": summary,
        "tags": tags,
        "key_facts": _key_facts(items, meta, sections),
        "entities": entities,
        "links": links,
        "sections": sections,
        "bookmark": bookmark,
        "quality": {
            "extraction_mode": "deterministic-html+jsonld",
            "warnings": [],
            "missing": missing,
            "content_text_chars_considered": len(main_text),
        },
    }


def analyze_url(url: str) -> dict[str, Any]:
    return analyze_html(fetch_url(url))


def render_markdown(data: dict[str, Any]) -> str:
    identity = data.get("identity", {})
    classification = data.get("classification", {})
    bookmark = data.get("bookmark", {})
    lines = [
        f"# {identity.get('title') or data['input']['url']}",
        "",
        f"- **URL:** {data.get('fetch', {}).get('final_url') or data['input']['url']}",
        f"- **Type:** {classification.get('kind', 'unknown')}",
        f"- **Category:** {classification.get('category', 'unknown')}",
        f"- **Classification confidence:** {classification.get('confidence', 0):.0%}",
        f"- **Suggested bookmark folder:** {bookmark.get('suggested_folder', 'Unsorted')}",
        f"- **Tags:** {', '.join(data.get('tags', [])) or 'none'}",
        "",
        "## Summary",
        data.get("summary") or "No summary extracted.",
    ]
    if data.get("key_facts"):
        lines += ["", "## Key facts"] + [f"- **{fact['label']}:** {fact['value']}" for fact in data["key_facts"]]
    if data.get("entities"):
        lines += ["", "## Entities"] + [f"- {entity['type']}: {entity['name']}" for entity in data["entities"]]
    if data.get("sections"):
        lines += ["", "## Dynamic sections"]
        for name, section in data["sections"].items():
            lines.append(f"### {name.title()}")
            for key, value in section.items():
                if isinstance(value, list):
                    lines.append(f"- **{key.replace('_', ' ').title()}:** {', '.join(str(v) for v in value)}")
                else:
                    lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
    important = data.get("links", {}).get("important", [])
    if important:
        lines += ["", "## Important links"] + [f"- [{link['label']}]({link['url']}) — {link['relationship']}" for link in important]
    lines += [
        "",
        "## Why keep it?",
        bookmark.get("why_it_might_matter", "No bookmark interpretation available."),
        "",
        "## Extraction quality",
    ]
    missing = data.get("quality", {}).get("missing", [])
    lines.append(f"- Missing/uncertain: {', '.join(missing) if missing else 'nothing obvious'}")
    for warning in data.get("quality", {}).get("warnings", []):
        lines.append(f"- Warning: {warning}")
    return "\n".join(lines).strip() + "\n"
