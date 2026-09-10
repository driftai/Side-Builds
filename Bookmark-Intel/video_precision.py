from __future__ import annotations

from collections import Counter
from typing import Any

from video_precision_extract import *
from video_resource import _canonical_youtube_video, _unwrap_link, _youtube_host


def _title_tokens(data: dict[str, Any]) -> set[str]:
    title = _norm((data.get("identity") or {}).get("title"))
    creator_tokens = set(_norm((((data.get("sections") or {}).get("media") or {}).get("creator"))).split())
    return {x for x in title.split() if len(x) >= 3 and x not in LINK_GENERIC and x not in creator_tokens}


def _recure_links(data: dict[str, Any]) -> None:
    archive = [x for x in (data.get("evidence_archive") or {}).get("links") or [] if isinstance(x, dict)]
    existing = [x for x in (data.get("links") or {}).get("important") or [] if isinstance(x, dict)]
    title_tokens = _title_tokens(data)
    creator = _clean((((data.get("sections") or {}).get("media") or {}).get("creator")), 200)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    role_counts: Counter[str] = Counter()
    for raw in archive + existing:
        original = str(raw.get("url") or "").strip()
        if not original:
            continue
        dest, _event = _unwrap_link(original)
        dest = _canonical_youtube_video(dest)
        parsed = urlparse(dest)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or dest.casefold() in seen:
            continue
        label = _clean(raw.get("label"), 320) or parsed.hostname or dest
        label = re.sub(r"^(?:\d{1,2}:)?\d{1,2}:\d{2}\s+", "", label).strip()
        label = re.sub(r"\s+[0-9][0-9,.]*[KMB]?\s+views\b.*$", "", label, flags=re.I).strip()
        label = re.sub(r"\s+Live Playlist.*$", "", label, flags=re.I).strip()
        context = _norm(raw.get("source_context"))
        host = (parsed.hostname or "").casefold()
        role = None
        score = 0.0
        if _youtube_host(host) and (parsed.path.startswith("/@") or parsed.path.startswith("/channel/") or parsed.path.startswith("/c/")):
            role, score = "channel", 0.96
            if creator and _norm(label) in {"www youtube com", "youtube com", "about", "videos"}:
                label = creator if _norm(label) not in {"about", "videos"} else f"{creator} ({label.capitalize()})"
        elif "description" in context:
            role, score = "description_link", 0.98
            summary_norm = _norm(data.get("summary"))
            if any(summary_norm.startswith(p) for p in ("credit", "credits", "original", "source", "cover of")) and title_tokens & set(_norm(label).split()):
                role, score = "credited_source", 1.0
        elif not _youtube_host(host):
            previous = next((x for x in existing if str(x.get("url") or "") == original), None)
            if previous:
                role, score = str(previous.get("curation_role") or previous.get("relationship") or "external"), 0.70
        elif parsed.path == "/watch":
            matched = title_tokens & set(_norm(label).split())
            needed = 1 if len(title_tokens) <= 2 else 2
            if len(matched) >= needed:
                role, score = "related_video", min(0.92, 0.60 + 0.08 * len(matched))
        if not role:
            continue
        seen.add(dest.casefold())
        candidates.append({"label": label, "url": dest, "relationship": role, "curation_role": role, "curation_score": round(score, 2), "source_context": _clean(raw.get("source_context"), 160), "unwrapped_from": original if dest != original else None})
    priority = {"credited_source": 0, "channel": 1, "description_link": 2, "social": 3, "playlist": 4, "related_video": 5, "external": 6}
    candidates.sort(key=lambda x: (priority.get(str(x.get("curation_role")), 9), -float(x.get("curation_score") or 0.0)))
    out: list[dict[str, Any]] = []
    caps = {"credited_source": 3, "channel": 2, "description_link": 4, "social": 3, "playlist": 2, "related_video": 3, "external": 2}
    for row in candidates:
        role = str(row.get("curation_role") or "external")
        if role_counts[role] >= caps.get(role, 2):
            continue
        role_counts[role] += 1
        out.append(row)
        if len(out) >= 10:
            break
    if out:
        data.setdefault("links", {})["important"] = out


def _slug(value: Any) -> str | None:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-") or None


def _title_tags(title: str) -> list[str]:
    words = [x for x in _norm(title).split() if x]
    out: list[str] = []
    for word in words:
        if len(word) >= 4 and (word not in LINK_GENERIC or word in TITLE_TAG_ALLOW):
            out.append(word)
    for left, right in zip(words, words[1:]):
        if left in {"my", "no", "of", "in", "at"} and len(right) >= 4:
            out.append(f"{left}-{right}")
        elif len(left) >= 4 and len(right) >= 4 and (left not in LINK_GENERIC or left in TITLE_TAG_ALLOW) and (right not in LINK_GENERIC or right in TITLE_TAG_ALLOW):
            out.append(f"{left}-{right}")
    return out


def _retag(data: dict[str, Any], fields: dict[str, Any]) -> None:
    category = _slug((((data.get("sections") or {}).get("media") or {}).get("platform_category")))
    raw = list(data.get("tags") or []) + list(fields.get("keywords") or []) + _title_tags(str((data.get("identity") or {}).get("title") or ""))
    out = ["video"]
    seen = {"video"}
    for value in raw:
        tag = _slug(value)
        if not tag or tag in seen or tag in TAG_NOISE or tag == category or len(tag) > 48:
            continue
        if tag == "music" and "music" not in _norm((data.get("identity") or {}).get("title")):
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= 18:
            break
    data["tags"] = out
    data.setdefault("bookmark", {})["suggested_tags"] = list(out)


def _coverage(data: dict[str, Any]) -> None:
    coverage = data.get("resource_coverage")
    if not isinstance(coverage, dict):
        return
    kept = [x for x in (coverage.get("interactive_sections_detected") or []) if isinstance(x, dict) and _norm(x.get("label")) not in COVERAGE_NOISE]
    labels = {_norm(x.get("label")) for x in kept}
    covered = [x for x in (coverage.get("covered_sections") or []) if _norm(x) in labels]
    missing = [x for x in (coverage.get("missing_sections") or []) if _norm(x) in labels]
    coverage.update(interactive_sections_detected=kept, covered_sections=covered, missing_sections=missing)
    coverage["resource_coverage_score"] = round(len({_norm(x) for x in covered}) / len(labels), 2) if labels else 1.0
    coverage["needs_deepening"] = bool(missing)


def finalize_video_precision(data: dict[str, Any], acquired: Any) -> dict[str, Any]:
    kind = str((data.get("classification") or {}).get("kind") or "").casefold()
    media_type = str((((data.get("sections") or {}).get("resource_details") or {}).get("media_type") or "")).casefold()
    if kind != "video" and media_type != "video":
        return data
    if not _youtube_host((urlparse(_page_url(data, acquired)).hostname or "").casefold()):
        return data
    html = str(getattr(acquired, "text", "") or "")
    soup = BeautifulSoup(html, "html.parser")
    player, initial = _youtube_state(html)
    fields = _player_fields(player)
    counts = {k: v for k, v in {"likes": _find_count(initial, "likes"), "comments": _find_count(initial, "comments"), "channel_subscribers": _find_subscribers(initial)}.items() if v is not None}
    _promote_player_state(data, soup, fields, counts)
    _clean_entities(data, fields)
    _recure_links(data)
    _retag(data, fields)
    _coverage(data)
    quality = data.setdefault("quality", {})
    recovered = set(str(x) for x in (quality.get("structured_fields_recovered") or []))
    if fields: recovered.add("video_player_state")
    if fields.get("description"): recovered.add("video_description")
    if fields.get("duration_seconds"): recovered.add("video_duration")
    if fields.get("views") or counts: recovered.add("video_engagement")
    quality["structured_fields_recovered"] = sorted(recovered)
    data["video_precision"] = {"version": PRECISION_VERSION, "youtube_player_state_used": bool(player), "youtube_initial_data_used": bool(initial), "sparse_player_fields_recovered": sorted(fields), "initial_engagement_fields_recovered": sorted(counts), "network_requests_added": 0}
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
