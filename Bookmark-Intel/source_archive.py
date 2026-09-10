from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from source_provider_mangadex import *

MAX_ARCHIVE_LINKS = 250
MAX_ARCHIVE_FACTS = 140
MAX_ARCHIVE_META = 100

EVIDENCE_LABELS = {
    "publication", "status", "year", "author", "authors", "artist", "artists",
    "genres", "genre", "themes", "theme", "demographic", "format", "formats",
    "content rating", "rating", "score", "alternative titles", "alternate titles",
    "synonyms", "official english", "official raw", "read or buy", "track",
    "final chapter", "final volume", "chapters", "volumes", "language",
    "original language", "publisher", "serialization", "magazine",
}


def _all_links(soup: BeautifulSoup, base_url: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    base_host = (urlparse(base_url).hostname or "").lower()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = unsafe = duplicate = 0
    for a in soup.find_all("a", href=True):
        total += 1
        href = str(a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            unsafe += 1
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            unsafe += 1
            continue
        clean = parsed._replace(fragment="").geturl()
        if clean in seen:
            duplicate += 1
            continue
        seen.add(clean)
        label = _clean(a.get_text(" ", strip=True) or a.get("aria-label") or a.get("title") or parsed.hostname, 180) or parsed.hostname or clean
        host = (parsed.hostname or "").lower()
        region = "body"
        if a.find_parent(["nav", "header", "footer", "aside"]):
            region = "navigation"
        else:
            found_region = None
            curr = a.parent
            for _ in range(4):
                if not curr or curr == soup:
                    break
                text_prefix = curr.get_text(" ", strip=True)[:60].lower()
                for keyword, cat in (
                    ("read or buy", "Read or Buy"), ("track", "Track"),
                    ("official", "Official source"), ("alternative", "Alternative source"),
                ):
                    if keyword in text_prefix:
                        found_region = cat
                        break
                if found_region:
                    break
                curr = curr.parent
            if found_region:
                region = found_region
            elif a.find_parent(["main", "article"]):
                region = "main"
        rows.append({"label": label, "url": clean, "relationship": "external" if host != base_host else "internal", "region": region})
        if len(rows) >= MAX_ARCHIVE_LINKS:
            break
    return rows, {"anchors_seen": total, "links_retained": len(rows), "duplicates_skipped": duplicate, "unsafe_or_non_http_skipped": unsafe}


def _archive_meta(soup: BeautifulSoup) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for meta in soup.find_all("meta"):
        key = _clean(meta.get("name") or meta.get("property") or meta.get("itemprop"), 120)
        value = _clean(meta.get("content"), 1200)
        if not key or not value:
            continue
        fingerprint = (key.casefold(), value.casefold())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append({"key": key, "value": value})
        if len(out) >= MAX_ARCHIVE_META:
            break
    return out


def _fact_value_from_element(element: Any, label: str) -> str | None:
    parts: list[str] = []
    for sib in element.next_siblings:
        name = getattr(sib, "name", None)
        if name in {"br", "hr", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}:
            if not parts and hasattr(sib, "get_text"):
                t = sib.get_text(" ", strip=True)
                if t and not t.endswith(":"):
                    return _clean(t, 1200)
            break
        text = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
        if not text:
            continue
        if name in {"b", "strong", "dt", "th"} and text.endswith(":"):
            break
        parts.append(text)
        if len(" ".join(parts)) > 1200:
            break
    if parts:
        joined = _clean(" ".join(parts), 1200)
        if joined and joined.casefold() != label.casefold():
            return joined
    sibling = element.find_next_sibling()
    if sibling:
        text = _clean(sibling.get_text(" ", strip=True), 1200)
        if text and text.casefold() != label.casefold():
            return text
    parent = element.parent
    if parent:
        full = _clean(parent.get_text(" ", strip=True), 1400)
        if full:
            norm_label = label.rstrip(":").strip()
            if full.casefold().startswith(norm_label.casefold()):
                remainder = full[len(norm_label):].lstrip(" :–—-\t")
                if remainder:
                    return _clean(remainder, 1200)
    return None


def _labeled_facts(soup: BeautifulSoup) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(label: Any, value: Any, source: str) -> None:
        clean_label = _clean(label, 120)
        clean_value = _clean(value, 1200)
        if not clean_label or not clean_value or clean_label.casefold() == clean_value.casefold():
            return
        key = (clean_label.casefold(), clean_value.casefold())
        if key in seen:
            return
        seen.add(key)
        out.append({"label": clean_label, "value": clean_value, "source": source})

    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            add(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True), "definition_list")
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2:
            add(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True), "table")
    for element in soup.find_all(["span", "div", "p", "strong", "b", "h3", "h4", "h5"]):
        label = _clean(element.get_text(" ", strip=True), 120)
        if not label or label.rstrip(":").strip().casefold() not in EVIDENCE_LABELS:
            continue
        value = _fact_value_from_element(element, label)
        if value:
            add(label, value, "label_value")
    return out[:MAX_ARCHIVE_FACTS]


MANGADEX_LINK_MAPPING: dict[str, tuple[str, str, bool]] = {
    "raw": ("Official Raw", "Official source", True), "engtl": ("Official English", "Read or Buy", True),
    "bw": ("Book☆Walker", "Read or Buy", False), "bl": ("BookLive", "Read or Buy", False),
    "amz": ("Amazon", "Read or Buy", False), "ebj": ("eBookJapan", "Read or Buy", False),
    "cdj": ("CDJapan", "Read or Buy", False), "mal": ("MyAnimeList", "Track", False),
    "al": ("AniList", "Track", False), "mu": ("MangaUpdates", "Track", False),
    "ap": ("Anime-Planet", "Track", False), "kt": ("Kitsu", "Track", False),
}


def _resolve_mangadex_external_links(external_ids: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, raw_val in (external_ids or {}).items():
        if not raw_val:
            continue
        val = str(raw_val).strip()
        label, region, is_curated = MANGADEX_LINK_MAPPING.get(key, (key.upper(), "external", False))
        url: str | None = None
        if val.startswith(("http://", "https://")):
            url = val
        elif key == "al": url = f"https://anilist.co/manga/{val}"
        elif key == "ap": url = f"https://www.anime-planet.com/manga/{val}"
        elif key == "bw": url = "https://bookwalker.jp/" + val.lstrip("/")
        elif key == "mu": url = f"https://www.mangaupdates.com/series/{val}" if (val.isalnum() and not val.isdigit()) else f"https://www.mangaupdates.com/series.html?id={val}"
        elif key == "mal": url = f"https://myanimelist.net/manga/{val}"
        elif key == "kt": url = f"https://kitsu.io/manga/{val}"
        elif key == "bl": url = f"https://booklive.jp/product/index/title_id/{val}"
        elif key == "amz": url = f"https://www.amazon.co.jp/dp/{val}"
        if url:
            try:
                validate_public_url(url)
                out.append({"label": label, "url": url, "relationship": "external", "region": region, "curated_important": is_curated})
            except Exception:
                continue
    return out


def build_evidence_archive(data: dict[str, Any], acquired: Any, provider: ProviderEvidence | None = None) -> dict[str, Any]:
    html = str(getattr(acquired, "text", "") or "")
    content_type = str(getattr(acquired, "content_type", "") or "")
    if content_type and not any(x in content_type for x in ("html", "xml", "text")):
        return {"version": 1, "capture_note": "Non-HTML resource; no DOM evidence archive was produced.", "links": [], "labeled_facts": [], "metadata": [], "headings": [], "capture_stats": {}}

    soup = BeautifulSoup(html, "html.parser")
    links, stats = _all_links(soup, str(getattr(acquired, "final_url", "") or ""))
    if provider and provider.fields and provider.fields.get("external_ids"):
        provider_links = _resolve_mangadex_external_links(provider.fields["external_ids"])
        existing_urls = {row["url"] for row in links}
        curated_important_list = data.setdefault("links", {}).setdefault("important", [])
        curated_important_urls = {str(x.get("url")) for x in curated_important_list if isinstance(x, dict) and x.get("url")}
        for pl in provider_links:
            if pl["url"] not in existing_urls:
                existing_urls.add(pl["url"])
                links.append(pl)
            if pl.get("curated_important") and pl["url"] not in curated_important_urls:
                curated_important_urls.add(pl["url"])
                curated_important_list.append({"label": pl["label"], "url": pl["url"], "relationship": pl["region"].lower().replace(" ", "_")})

    important_urls = {str(x.get("url")) for x in (data.get("links", {}).get("important") or []) if isinstance(x, dict) and x.get("url")}
    for row in links:
        row["curated_important"] = row["url"] in important_urls
    headings = _uniq([h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4"])], 60)
    facts = _labeled_facts(soup)
    meta = _archive_meta(soup)
    stats.update({"labeled_facts_retained": len(facts), "links_retained": len(links), "metadata_entries_retained": len(meta), "headings_retained": len(headings)})
    return {
        "version": 1,
        "capture_note": "Bounded evidence archive: keeps useful page facts and discovered HTTP(S) links even when they are not promoted into the curated bookmark summary. Repeated chapter rows, scripts/styles, unsafe protocols and duplicate URLs are not dumped.",
        "labeled_facts": facts, "links": links, "metadata": meta, "headings": headings, "capture_stats": stats,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
