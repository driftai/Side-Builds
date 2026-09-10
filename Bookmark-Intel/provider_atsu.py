from __future__ import annotations

from provider_common import *


def _atsu_evidence(url: str, fetch_json: Callable[[str], Any] | None = None) -> ProviderEvidence:
    fetcher = fetch_json or _json_endpoint
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    match = re.match(r"^/manga/([^/?#]+)", parsed.path)
    if host not in {"atsu.moe", "www.atsu.moe"} or not match:
        return ProviderEvidence(adapter="atsu", matched=False)

    manga_id = match.group(1)
    evidence = ProviderEvidence(adapter="atsu", matched=True)
    payloads: list[Any] = []

    endpoints = [
        f"https://atsu.moe/api/manga/page?{urlencode({'id': manga_id})}",
        f"https://atsu.moe/api/manga/info?{urlencode({'mangaId': manga_id})}",
    ]
    for endpoint in endpoints:
        try:
            payload = fetcher(endpoint)
            payloads.append(payload)
            evidence.sources.append(endpoint)
        except Exception as exc:
            evidence.errors.append(re.sub(r"\s+", " ", str(exc)).strip()[:300])

    if not payloads:
        return evidence

    rich_record: dict[str, Any] = {}
    chapter_payload: dict[str, Any] = {}
    for payload in payloads:
        if isinstance(payload, dict) and isinstance(payload.get("mangaPage"), dict):
            rich_record = payload["mangaPage"]
        if isinstance(payload, dict) and isinstance(payload.get("chapters"), list):
            chapter_payload = payload

    merged: dict[str, Any] = {}
    if rich_record:
        mined = _mine_fields(rich_record)
        for key, value in mined.items():
            if key not in merged or not merged[key]:
                merged[key] = value

    if rich_record:
        if rich_record.get("title"):
            merged["title"] = _clean(rich_record.get("title"), 300)
        if rich_record.get("englishTitle"):
            merged["english_title"] = _clean(rich_record.get("englishTitle"), 300)
        if rich_record.get("otherNames"):
            merged["alternative_titles"] = _uniq(rich_record.get("otherNames"))
        synopsis = rich_record.get("synopsis") or rich_record.get("description")
        if synopsis:
            merged["description"] = _clean(synopsis, 1600)
        if rich_record.get("status"):
            merged["status"] = _clean(rich_record.get("status"))
        media_type = rich_record.get("type") or rich_record.get("medium")
        if media_type:
            merged["media_type"] = _clean(media_type)
        if rich_record.get("genres"):
            merged["genres"] = _uniq(rich_record.get("genres"))

        raw_authors = rich_record.get("authors") or []
        author_names: list[str] = []
        artist_names: list[str] = []
        if isinstance(raw_authors, list):
            for entry in raw_authors:
                if isinstance(entry, dict):
                    name = _clean(entry.get("name"))
                    role = str(entry.get("type") or "").strip().lower()
                    if name:
                        if role == "artist":
                            if name not in artist_names:
                                artist_names.append(name)
                        elif name not in author_names:
                            author_names.append(name)
                else:
                    name = _clean(entry)
                    if name and name not in author_names:
                        author_names.append(name)
        if author_names:
            merged["authors"] = author_names
        if artist_names:
            merged["artists"] = artist_names
        elif rich_record.get("artists"):
            merged["artists"] = _uniq(rich_record.get("artists"))

        raw_rating = rich_record.get("avgRating") or rich_record.get("score")
        if raw_rating not in (None, "", 0, "0"):
            try:
                merged["score"] = str(round(float(raw_rating), 2))
            except (ValueError, TypeError):
                cleaned_score = _clean(raw_rating)
                if cleaned_score:
                    merged["score"] = cleaned_score

        raw_released = rich_record.get("released") or rich_record.get("year")
        if raw_released:
            if isinstance(raw_released, (int, float)) and raw_released > 10_000_000:
                from datetime import datetime, timezone
                try:
                    dt = datetime.fromtimestamp(raw_released / 1000, tz=timezone.utc)
                    merged["year"] = str(dt.year)
                except Exception:
                    pass
            else:
                cleaned_year = _clean(raw_released)
                if cleaned_year and re.match(r"^\d{4}$", cleaned_year):
                    merged["year"] = cleaned_year

        poster_raw = rich_record.get("poster")
        poster_val = None
        if isinstance(poster_raw, dict):
            poster_val = poster_raw.get("largeImage") or poster_raw.get("image") or poster_raw.get("smallImage") or poster_raw.get("id")
        elif isinstance(poster_raw, str):
            poster_val = poster_raw
        if poster_val:
            cleaned_poster = _clean(poster_val, 500)
            if cleaned_poster:
                if not cleaned_poster.startswith(("http://", "https://")):
                    cleaned_poster = f"https://atsu.moe/{cleaned_poster.lstrip('/')}"
                merged["poster"] = cleaned_poster

    chapters = chapter_payload.get("chapters") if chapter_payload else None
    if isinstance(chapters, list):
        merged["chapter_record_count"] = len(chapters)
        total_cnt = rich_record.get("totalChapterCount") if rich_record else None
        if total_cnt is not None:
            try:
                cnt = float(total_cnt)
                merged["chapter_count"] = int(cnt) if cnt.is_integer() else cnt
            except (ValueError, TypeError):
                pass
        numbers: list[float] = []
        scan_ids: set[str] = set()
        best_num: float | None = None
        best_title: str | None = None
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            number = chapter.get("number")
            num: float | None = None
            try:
                num = float(number)
                numbers.append(num)
            except (TypeError, ValueError):
                pass
            title = _clean(chapter.get("title"), 300)
            if num is not None and (best_num is None or num >= best_num):
                best_num = num
                if title:
                    best_title = title
            scan_id = _clean(chapter.get("scanId"), 200)
            if scan_id:
                scan_ids.add(scan_id)
        if numbers:
            latest = max(numbers)
            merged["latest_chapter"] = int(latest) if latest.is_integer() else latest
            if "chapter_count" not in merged:
                merged["chapter_count"] = len({n for n in numbers})
        elif "chapter_count" not in merged:
            merged["chapter_count"] = len(chapters)
        if best_title:
            merged["latest_chapter_title"] = best_title
        if scan_ids:
            merged["scanlation_group_count"] = len(scan_ids)
    elif rich_record and rich_record.get("totalChapterCount"):
        try:
            cnt = float(rich_record["totalChapterCount"])
            merged["chapter_count"] = int(cnt) if cnt.is_integer() else cnt
        except (ValueError, TypeError):
            pass

    merged["provider_id"] = manga_id
    evidence.fields = merged

    title = _clean(merged.get("title") or merged.get("english_title"), 300)
    useful_detail_count = sum(
        1 for key in ("description", "authors", "artists", "genres", "status", "chapter_count", "media_type", "score")
        if merged.get(key)
    )
    evidence.sufficient = bool(title and (useful_detail_count >= 2 or merged.get("chapter_count")))
    return evidence


__all__ = [name for name in globals() if not name.startswith("__")]
