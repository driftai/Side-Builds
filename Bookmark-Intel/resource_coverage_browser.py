from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from acquisition import AcquisitionError, BROWSER_TIMEOUT_MS, validate_public_url
from browser_route_cleanup import settle_page_routes
from resource_coverage_sections import *


def _capture_interactive_sections(url: str, labels: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labels = [x for x in _uniq(labels, MAX_INTERACTIVE_SECTIONS) if _safe_control_label(x)]
    if not labels:
        return [], {"attempted": False, "reason": "no safe missing interactive sections"}
    validate_public_url(url)
    try:
        from camoufox.sync_api import Camoufox
    except Exception as exc:
        return [], {"attempted": True, "ok": False, "error": f"Camoufox unavailable: {exc}"[:300]}

    validated_hosts: dict[tuple[str, int], bool] = {}

    def route_request(route: Any, request: Any) -> None:
        req_url = str(request.url)
        parsed = urlparse(req_url)
        if parsed.scheme not in {"http", "https"}:
            route.continue_()
            return
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        key = (host.casefold(), port)
        try:
            if key not in validated_hosts:
                validate_public_url(req_url)
                validated_hosts[key] = True
        except AcquisitionError:
            route.abort()
            return
        route.continue_()

    snapshots: list[dict[str, Any]] = []
    started = time.monotonic()
    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            try:
                page.route("**/*", route_request)
                page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception:
                    page.wait_for_timeout(700)

                live_elements = page.locator('[role="tab"], button, a[href]')
                live_count = min(live_elements.count(), 160)
                live_tab_map: dict[str, tuple[str, Any]] = {}
                for idx in range(live_count):
                    element = live_elements.nth(idx)
                    try:
                        text = _clean(element.inner_text(timeout=300), 100)
                    except Exception:
                        continue
                    if not text or not _safe_control_label(text) or UNSAFE_CONTROL_RE.search(text):
                        continue
                    match = SAFE_SECTION_RE.search(text)
                    canonical_label = match.group(0).capitalize() if match else text
                    stem = _norm(canonical_label).rstrip("s")
                    if stem not in live_tab_map:
                        live_tab_map[stem] = (canonical_label, element)

                targets_to_click: list[tuple[str, Any]] = []
                for label in labels:
                    stem = _norm(label).rstrip("s")
                    if stem in live_tab_map:
                        item = live_tab_map[stem]
                        if not any(target[0] == item[0] for target in targets_to_click):
                            targets_to_click.append(item)
                for stem, (live_text, element) in live_tab_map.items():
                    if not any(target[0] == live_text for target in targets_to_click):
                        if any(_norm(x).rstrip("s") == stem for x in labels):
                            targets_to_click.append((live_text, element))

                for target_text, target_element in targets_to_click[:MAX_INTERACTIVE_SECTIONS]:
                    if not _safe_same_resource_after_click(url, str(page.url)):
                        page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
                    try:
                        target_element.click(timeout=2_000)
                        try:
                            page.wait_for_load_state("networkidle", timeout=1_500)
                        except Exception:
                            pass
                        page.wait_for_timeout(900)
                        current_url = str(page.url)
                        if not _safe_same_resource_after_click(url, current_url):
                            page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
                            continue
                        html = page.content()
                        if len(html) < 80:
                            continue
                        snapshots.append({"label": target_text, "url": current_url, "html": html})
                    except Exception:
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
                        except Exception:
                            pass
                        continue
            finally:
                settle_page_routes(page)
    except Exception as exc:
        return snapshots, {
            "attempted": True, "ok": bool(snapshots),
            "error": re.sub(r"\s+", " ", str(exc)).strip()[:400],
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    return snapshots, {
        "attempted": True, "ok": bool(snapshots),
        "sections_captured": [x["label"] for x in snapshots],
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


def _merge_archive_static(data: dict[str, Any], groups: list[dict[str, Any]], collections: list[dict[str, Any]]) -> None:
    archive = data.setdefault("evidence_archive", {})
    archive["grouped_values"] = groups[:MAX_GROUPS]
    archive["structured_collections"] = collections[:MAX_STRUCTURED_COLLECTIONS]
    stats = archive.setdefault("capture_stats", {})
    stats["grouped_value_sets_retained"] = len(archive["grouped_values"])
    stats["structured_collections_retained"] = len(archive["structured_collections"])


def _merge_interactive_snapshots(data: dict[str, Any], acquired: Any, snapshots: list[dict[str, Any]]) -> None:
    archive = data.setdefault("evidence_archive", {})
    baseline = {_norm(x) for x in (archive.get("source_text_blocks") or []) if isinstance(x, str)}
    interactive: list[dict[str, Any]] = []
    merged_groups = list(archive.get("grouped_values") or [])
    merged_collections = list(archive.get("structured_collections") or [])
    group_seen = {
        (_norm(group.get("label")), tuple(str(v).casefold() for v in (group.get("values") or [])[:20]))
        for group in merged_groups if isinstance(group, dict)
    }
    collection_seen = {
        (str(collection.get("path") or "").casefold(), int(collection.get("count") or 0))
        for collection in merged_collections if isinstance(collection, dict)
    }

    for snapshot in snapshots:
        soup = BeautifulSoup(str(snapshot.get("html") or ""), "html.parser")
        blocks = [block for block in _snapshot_text_blocks(soup) if _norm(block) not in baseline]
        groups = _grouped_values(soup)
        collections = _structured_collections(soup)
        links = _snapshot_links(soup, str(snapshot.get("url") or getattr(acquired, "final_url", "") or ""))

        episodes: list[dict[str, Any]] = []
        for card in soup.find_all(["button", "article", "li", "div"]):
            label = card.get("aria-label") or card.get("title") or ""
            match = re.search(r"EP\s*(\d+)(?:\s*[:\-]\s*(.+))?", label, re.I)
            if not match:
                card_text = card.get_text(" ", strip=True)
                match = re.search(r"\bEP\s*(\d+)\s+([A-Za-z0-9\s\',!?-]+?)(?=\s+(?:On\b|Kaburagi\b|The\b|With\b|It\b|A\b|Akira\b|\d{4}\b)|$)", card_text)
            if match:
                episode_number = int(match.group(1))
                episode_title = match.group(2).strip() if match.group(2) else ""
                date_element = card.find(class_=re.compile(r"airDate", re.I)) or card.find("time")
                date_string = date_element.get_text(strip=True) if date_element else None
                description_element = card.find(class_=re.compile(r"description", re.I)) or card.find("p")
                description = description_element.get_text(" ", strip=True) if description_element else None
                if not any(item["number"] == episode_number for item in episodes):
                    episodes.append({
                        "number": episode_number, "title": episode_title or f"Episode {episode_number}",
                        "date": date_string, "description": description[:250] if description else None,
                    })
        if episodes:
            episodes.sort(key=lambda item: item["number"])
            collections.append({"path": "interactive.episodes", "kind": "list", "count": len(episodes), "sample": episodes[:MAX_STRUCTURED_SAMPLE_ITEMS]})

        if any(key in str(snapshot.get("label", "")).lower() for key in ("art", "gallery", "image")):
            artwork_items: list[dict[str, str]] = []
            for image in soup.find_all("img"):
                src = image.get("src") or image.get("data-src")
                if not src or src.startswith("data:") or any(key in src.lower() for key in ("icon", "logo.svg", "avatar")):
                    continue
                alt = _clean(image.get("alt"), 100) or "Artwork image"
                if not any(item["url"] == src for item in artwork_items):
                    artwork_items.append({"url": src, "label": alt})
            if artwork_items:
                collections.append({"path": "interactive.artwork", "kind": "list", "count": len(artwork_items), "sample": artwork_items[:MAX_STRUCTURED_SAMPLE_ITEMS]})

        for group in groups:
            key = (_norm(group.get("label")), tuple(str(v).casefold() for v in (group.get("values") or [])[:20]))
            if key not in group_seen:
                group_seen.add(key)
                enriched = dict(group)
                enriched["source_context"] = snapshot.get("label")
                merged_groups.append(enriched)
        for collection in collections:
            key = (str(collection.get("path") or "").casefold(), int(collection.get("count") or 0))
            if key not in collection_seen:
                collection_seen.add(key)
                enriched = dict(collection)
                enriched["source_context"] = snapshot.get("label")
                if str(collection.get("path") or "").startswith("interactive."):
                    merged_collections.insert(0, enriched)
                else:
                    merged_collections.append(enriched)
        interactive.append({
            "label": snapshot.get("label"), "url": snapshot.get("url"),
            "text_blocks": blocks[:MAX_INTERACTIVE_BLOCKS], "grouped_values": groups[:40],
            "structured_collections": collections[:30], "links": links[:MAX_INTERACTIVE_LINKS],
        })

    archive["interactive_sections"] = interactive
    archive["grouped_values"] = merged_groups[:MAX_GROUPS]
    archive["structured_collections"] = merged_collections[:MAX_STRUCTURED_COLLECTIONS]
    stats = archive.setdefault("capture_stats", {})
    stats["interactive_sections_retained"] = len(interactive)
    stats["grouped_value_sets_retained"] = len(archive["grouped_values"])
    stats["structured_collections_retained"] = len(archive["structured_collections"])


def _all_snapshot_html(acquired: Any, snapshots: list[dict[str, Any]]) -> str:
    parts = [str(getattr(acquired, "text", "") or "")]
    for snapshot in snapshots:
        label = _clean(snapshot.get("label"), 100) or "interactive section"
        parts.append(f'<section data-bookmark-intel-context="{label}">' + str(snapshot.get("html") or "") + "</section>")
    return "\n".join(parts)


__all__ = [name for name in globals() if not name.startswith("__")]
