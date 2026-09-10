from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from resource_coverage_media import *


def _safe_control_label(text: str) -> bool:
    text = _clean(text, 100) or ""
    if not text or len(text.split()) > 8:
        return False
    if UNSAFE_CONTROL_RE.search(text):
        return False
    return bool(SAFE_SECTION_RE.search(text))


def _interactive_candidates(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    selectors = ['[role="tab"]', 'button', 'a[href]', 'nav[aria-label]', '[data-tab]', '[aria-controls]']
    for selector in selectors:
        for element in soup.select(selector):
            if element.find_parent(["form", "footer", "header"]):
                continue
            text = _clean(element.get_text(" ", strip=True) or element.get("aria-label") or element.get("title"), 100)
            if not text or not _safe_control_label(text) or UNSAFE_CONTROL_RE.search(text):
                continue
            match = SAFE_SECTION_RE.search(text)
            label = match.group(0).capitalize() if match else text
            key = _norm(label)
            if key in seen:
                continue
            href = str(element.get("href") or "").strip()
            if href:
                absolute = urljoin(base_url, href)
                parsed_base = urlparse(base_url)
                parsed = urlparse(absolute)
                if parsed.hostname and (parsed.hostname or "").casefold() != (parsed_base.hostname or "").casefold():
                    continue
                if parsed.path and parsed.path != parsed_base.path:
                    continue
            seen.add(key)
            candidates.append({
                "label": label,
                "mechanism": "role_tab" if element.get("role") == "tab" else element.name,
                "href": href or None,
            })
            if len(candidates) >= 12:
                return candidates

    for element in soup.find_all(["h2", "h3", "h4", "link"]):
        if element.name == "link":
            hint = str(element.get("href") or "")
            match = SAFE_SECTION_RE.search(hint)
            if match:
                label = match.group(0).capitalize()
                key = _norm(label)
                if key not in seen:
                    seen.add(key)
                    candidates.append({"label": label, "mechanism": "resource_hint", "href": None})
            continue
        text = _clean(element.get_text(" ", strip=True), 100)
        if not text or UNSAFE_CONTROL_RE.search(text):
            continue
        for match in SAFE_SECTION_RE.finditer(text):
            label = match.group(0).capitalize()
            key = _norm(label)
            if key not in seen and not UNSAFE_CONTROL_RE.search(label):
                seen.add(key)
                candidates.append({"label": label, "mechanism": "section_heading", "href": None})
                if len(candidates) >= 12:
                    return candidates
    return candidates


def _collection_mentions(collections: list[dict[str, Any]], label: str) -> bool:
    target = _norm(label)
    target_stem = target.rstrip("s")
    target_words = set(target.split())
    for row in collections:
        path = _norm(row.get("path"))
        path_stem = path.rstrip("s")
        if target_stem in {"episode", "chapter", "track"} and int(row.get("count") or 0) < 1:
            continue
        if target == path or (target_words and target_words <= set(path.split())):
            return True
        if target_stem and (target_stem in path.split() or target_stem == path_stem):
            return True
    return False


def _group_mentions(groups: list[dict[str, Any]], label: str) -> bool:
    target = _norm(label)
    target_stem = target.rstrip("s")
    for group in groups:
        group_label = _norm(group.get("label"))
        group_stem = group_label.rstrip("s")
        if group_label == target or group_stem == target_stem:
            values = group.get("values") or []
            if target_stem in {"episode", "chapter", "track", "artwork", "image"} and (len(values) <= 1 or all(str(v).isdigit() for v in values)):
                continue
            if len(values) >= 2:
                return True
    return False


def _coverage_state(data: dict[str, Any], acquired: Any, soup: BeautifulSoup, groups: list[dict[str, Any]], collections: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = _interactive_candidates(soup, str(getattr(acquired, "final_url", "") or ""))
    covered: list[str] = []
    missing: list[str] = []
    archive = data.get("evidence_archive") or {}
    blocks = [str(x) for x in (archive.get("source_text_blocks") or [])]
    block_text = " ".join(blocks).casefold()
    group_labels = " ".join(str(x.get("label") or "") for x in groups).casefold()
    collection_paths = " ".join(str(x.get("path") or "") for x in collections if isinstance(x, dict)).casefold()
    links = archive.get("links") or []
    meaningful_images = [
        image for image in soup.find_all("img")
        if not str(image.get("src") or "").startswith("data:")
        and not re.search(r"\b(?:icon|avatar|logo)\b", str(image.get("alt") or ""), re.I)
    ]
    reconciled_visible = False

    for candidate in candidates:
        label = str(candidate["label"])
        norm = _norm(label)
        norm_stem = norm.rstrip("s")
        is_covered = _group_mentions(groups, label) or _collection_mentions(collections, label)
        if norm in {"overview", "detail", "details"} and data.get("summary"):
            is_covered = True
        if not is_covered:
            if norm_stem in {"image", "artwork", "gallery", "cover", "screenshot"}:
                if bool(meaningful_images) or any(x in collection_paths for x in ("image", "artwork", "cover", "gallery")):
                    is_covered = True
                    reconciled_visible = True
            elif norm_stem in {"link", "source"}:
                if len(links) >= 2 or len(soup.find_all("a", href=True)) >= 5:
                    is_covered = True
                    reconciled_visible = True
            elif norm_stem in {"similar", "recommendation", "related"}:
                if any(token in group_labels or token in block_text for token in ("similar", "recommendation", "readers also like", "related")):
                    is_covered = True
                    reconciled_visible = True
            elif norm_stem in {"episode", "chapter", "track"}:
                episode_blocks = [b for b in blocks if re.search(r"\b(?:EP|Episode|Chapter|Ch\.?)\s*\d+\b", b, re.I)]
                is_covered = len(episode_blocks) >= 2
            else:
                substantive = [b for b in blocks if (norm in _norm(b) or norm_stem in _norm(b)) and len(b) >= max(30, len(label) + 15)]
                is_covered = bool(substantive)
        (covered if is_covered else missing).append(label)

    score = 1.0 if not candidates else round(len(covered) / max(len(candidates), 1), 2)
    needs_deepening = bool(missing and candidates and not bool(getattr(acquired, "rendered", False)))
    result = {
        "html_health_score": round(float(getattr(acquired, "score", 0.0) or 0.0), 2),
        "resource_coverage_score": score,
        "interactive_sections_detected": candidates,
        "covered_sections": covered,
        "missing_sections": missing,
        "needs_deepening": needs_deepening,
        "principle": "HTML health and resource coverage are independent metrics.",
    }
    if reconciled_visible:
        result["coverage_reconciled_from_visible_evidence"] = True
    return result


def _snapshot_text_blocks(soup: BeautifulSoup) -> list[str]:
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    values: list[str] = []
    for element in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "article", "section", "div", "button"]):
        if element.find_parent(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]):
            continue
        if element.name in {"div", "section"} and element.find(["p", "li", "article", "section", "div", "h1", "h2", "h3", "h4", "button"], recursive=False):
            continue
        label_attr = _clean(element.get("aria-label") or element.get("title"), 500)
        raw_text = _clean(element.get_text(" ", strip=True), 1000)
        combined_text = raw_text
        if label_attr and label_attr not in (raw_text or ""):
            combined_text = f"{label_attr} - {raw_text}" if raw_text else label_attr
        if not combined_text:
            continue
        cleaned = re.sub(r"\bHIDDEN\s+SPOILER\b", "", combined_text, flags=re.I).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) < 8 and not re.search(r"\b(?:EP|Episode|Chapter|Season)\s*\d+\b", cleaned, re.I):
            continue
        values.append(cleaned)
        if len(values) >= MAX_INTERACTIVE_BLOCKS:
            break
    return _uniq(values, MAX_INTERACTIVE_BLOCKS)


def _snapshot_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    base_host = (urlparse(base_url).hostname or "").casefold()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "file:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        clean_url = parsed._replace(fragment="").geturl()
        if clean_url in seen:
            continue
        seen.add(clean_url)
        label = _clean(anchor.get_text(" ", strip=True) or anchor.get("aria-label") or anchor.get("title"), 160) or clean_url
        out.append({
            "label": label, "url": clean_url,
            "relationship": "internal" if (parsed.hostname or "").casefold() == base_host else "external",
        })
        if len(out) >= MAX_INTERACTIVE_LINKS:
            break
    return out


def _safe_same_resource_after_click(original_url: str, current_url: str) -> bool:
    try:
        original = urlparse(original_url)
        current = urlparse(current_url)
        return (
            current.scheme in {"http", "https"}
            and (current.hostname or "").casefold() == (original.hostname or "").casefold()
            and current.path == original.path
        )
    except Exception:
        return False


__all__ = [name for name in globals() if not name.startswith("__")]
