from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from video_precision import _count, _find_count
from youtube_description_parse import *


def _flags(data: dict[str, Any], soup: BeautifulSoup) -> dict[str, Any]:
    text = soup.get_text(" ", strip=True)
    norm = text.casefold()
    flags: dict[str, Any] = {}
    facts = data.setdefault("key_facts", [])
    resource = data.setdefault("sections", {}).setdefault("resource_details", {})
    if "includes paid promotion" in norm:
        flags["paid_promotion"] = True
        resource["paid_promotion"] = True
        _set_fact(facts, "Paid promotion", "Yes")
    if re.search(r"\bpremiered\s+[a-z]{3,9}\s+\d{1,2},\s+\d{4}\b", text, re.I):
        flags["publication_mode"] = "Premiere"
        resource["publication_mode"] = "Premiere"
        _set_fact(facts, "Publication Mode", "Premiere")
    elif re.search(r"\bstreamed live\b", text, re.I):
        flags["publication_mode"] = "Live stream"
        resource["publication_mode"] = "Live stream"
        _set_fact(facts, "Publication Mode", "Live stream")
    if "show transcript" in norm or ("transcript" in norm and "follow along using the transcript" in norm):
        flags["transcript_available"] = True
        resource["transcript_available"] = True
        _set_fact(facts, "Transcript Available", "Yes")
    if "auto-dubbed" in norm or ("audio tracks" in norm and "automatically generated" in norm):
        flags["auto_dubbed_audio"] = True
        resource["auto_dubbed_audio"] = True
        _set_fact(facts, "Auto-dubbed Audio", "Yes")
    return flags


def _recover_comments(data: dict[str, Any], initial: dict[str, Any] | None, soup: BeautifulSoup) -> None:
    media = data.setdefault("sections", {}).setdefault("media", {})
    resource = data.setdefault("sections", {}).setdefault("resource_details", {})
    engagement = media.get("engagement") if isinstance(media.get("engagement"), dict) else {}
    if "comments" in engagement:
        return
    raw = _find_count(initial, "comments") if initial else None
    if not raw:
        text = soup.get_text(" ", strip=True)
        match = re.search(r"\bComments\s+([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\b", text, re.I)
        if not match:
            match = re.search(r"\b([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\s+Comments\b", text, re.I)
        raw = match.group(1) if match else None
    if not raw:
        return
    number, display, approximate = _count(raw)
    if number is None:
        return
    value = display or f"{number:,}"
    engagement["comments"] = value
    media["engagement"] = engagement
    resource["comments_count"] = number
    resource["comments_display"] = value
    resource["comments_approximate"] = approximate
    _set_fact(data.setdefault("key_facts", []), "Comments", value)


def _semantic_channel_key(row: dict[str, Any], creator: str | None) -> str | None:
    if str(row.get("curation_role") or row.get("relationship") or "") != "channel":
        return None
    return f"channel:{_norm(creator)}" if creator else "channel"


def _recurate_links(data: dict[str, Any], extracted: list[dict[str, Any]]) -> None:
    existing = [x for x in (data.get("links") or {}).get("important") or [] if isinstance(x, dict)]
    creator = _clean((((data.get("sections") or {}).get("media") or {}).get("creator")), 200)
    by_url: dict[str, dict[str, Any]] = {}
    for row in existing + extracted:
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        url = _canonical_description_url(url)
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme not in {"http", "https"} or not host or host in PLATFORM_HELP_HOSTS:
            continue
        item = {**row, "url": url}
        role = str(item.get("curation_role") or item.get("relationship") or "description_link")
        item["relationship"] = role
        item["curation_role"] = role
        score = float(item.get("curation_score") or 0.0)
        item["curation_score"] = score
        prior = by_url.get(url.casefold())
        if prior is None:
            by_url[url.casefold()] = item
            continue
        prior_score = float(prior.get("curation_score") or 0.0)
        prior_role = str(prior.get("curation_role") or prior.get("relationship") or "description_link")
        prior_label = str(prior.get("label") or "").strip()
        item_label = str(item.get("label") or "").strip()
        prior_is_url = prior_label.startswith(("http://", "https://")) or prior_label.endswith("...") or prior_label.casefold() == host
        item_is_url = item_label.startswith(("http://", "https://")) or item_label.endswith("...") or item_label.casefold() == host
        if score > prior_score:
            item_wins = True
        elif score < prior_score:
            item_wins = False
        else:
            item_priority = ROLE_PRIORITY.get(role, 99)
            prior_priority = ROLE_PRIORITY.get(prior_role, 99)
            if item_priority < prior_priority:
                item_wins = True
            elif item_priority > prior_priority:
                item_wins = False
            elif prior_is_url and not item_is_url:
                item_wins = True
            elif not prior_is_url and item_is_url:
                item_wins = False
            else:
                item_wins = bool(item.get("description_section"))
        if item_wins:
            for key in ("source_context", "unwrapped_from"):
                if not item.get(key) and prior.get(key):
                    item[key] = prior[key]
            by_url[url.casefold()] = item
        elif prior_is_url and not item_is_url:
            prior["label"] = item_label

    candidates = list(by_url.values())
    channel_rows = [row for row in candidates if _semantic_channel_key(row, creator)]
    if len(channel_rows) > 1:
        channel_rows.sort(key=lambda row: (0 if "/channel/" in str(row.get("url") or "") else 1, -float(row.get("curation_score") or 0.0)))
        keep = channel_rows[0]
        candidates = [row for row in candidates if not _semantic_channel_key(row, creator) or row is keep]
        if creator:
            keep["label"] = creator
    candidates.sort(key=lambda row: (
        ROLE_PRIORITY.get(str(row.get("curation_role") or row.get("relationship") or ""), 99),
        -float(row.get("curation_score") or 0.0), str(row.get("label") or "").casefold(),
    ))
    out: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in candidates:
        role = str(row.get("curation_role") or row.get("relationship") or "external")
        if counts[role] >= ROLE_CAPS.get(role, 1):
            continue
        counts[role] += 1
        out.append(row)
        if len(out) >= 12:
            break
    data.setdefault("links", {})["important"] = out


def _clean_coverage(data: dict[str, Any], chapters: list[dict[str, Any]]) -> None:
    coverage = data.get("resource_coverage")
    if not isinstance(coverage, dict):
        return
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in coverage.get("interactive_sections_detected") or []:
        if not isinstance(row, dict):
            continue
        label = _norm(row.get("label"))
        if label in COVERAGE_NOISE:
            continue
        if label in {"chapter", "chapters"} and chapters:
            label = "chapters"
            row = {**row, "label": "Chapters"}
        elif label in {"comment", "comments"}:
            label = "comments"
            row = {**row, "label": "Comments"}
        if label in seen:
            continue
        seen.add(label)
        kept.append(row)
    labels = {_norm(row.get("label")) for row in kept}
    covered_norm = {_norm(x) for x in (coverage.get("covered_sections") or [])}
    missing_norm = {_norm(x) for x in (coverage.get("missing_sections") or [])}
    if chapters:
        covered_norm.add("chapters")
        missing_norm.discard("chapters")
        missing_norm.discard("chapter")
    covered = [row.get("label") for row in kept if _norm(row.get("label")) in covered_norm]
    missing = [row.get("label") for row in kept if _norm(row.get("label")) in missing_norm]
    coverage["interactive_sections_detected"] = kept
    coverage["covered_sections"] = covered
    coverage["missing_sections"] = missing
    coverage["resource_coverage_score"] = round(len({_norm(x) for x in covered}) / len(labels), 2) if labels else 1.0
    coverage["needs_deepening"] = bool(missing)


__all__ = [name for name in globals() if not name.startswith("__")]
