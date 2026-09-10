from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from acquisition_base import *
from acquisition_browser import *


def _http_fetch(raw_url: str) -> AcquiredPage:
    current = validate_public_url(raw_url)
    redirects: list[str] = []
    deadline = time.monotonic() + HTTP_TIMEOUT_SECONDS
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
        # Do not advertise br unless a decoder is guaranteed in the environment.
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "no-cache",
    }

    with httpx.Client(headers=headers, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if time.monotonic() > deadline:
                raise AcquisitionError(f"Request exceeded total fetch deadline of {HTTP_TIMEOUT_SECONDS}s.")
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise AcquisitionError(f"Redirect {response.status_code} had no Location header.")
                    next_url = validate_public_url(urljoin(current, location))
                    if next_url == current or next_url in redirects:
                        raise AcquisitionError(f"Circular redirect detected: {next_url}")
                    redirects.append(next_url)
                    current = next_url
                    continue

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise AcquisitionError(f"Streaming exceeded total fetch deadline of {HTTP_TIMEOUT_SECONDS}s.")
                    total += len(chunk)
                    if total > MAX_BODY_BYTES:
                        raise AcquisitionError(
                            f"Page body exceeded {MAX_BODY_BYTES:,} bytes; refusing oversized fetch."
                        )
                    chunks.append(chunk)
                body = b"".join(chunks)
                text = _decode_body(response, body)
                score, _ = html_quality(text, current, _content_type(response.headers), response.status_code)
                return AcquiredPage(
                    requested_url=raw_url,
                    final_url=current,
                    redirects=redirects,
                    status_code=response.status_code,
                    content_type=_content_type(response.headers),
                    text=text,
                    byte_count=len(body),
                    method="httpx",
                    score=score,
                    rendered=False,
                )
    raise AcquisitionError(f"Too many redirects (>{MAX_REDIRECTS}).")


def _attempt(method: str, fn: Any, url: str) -> tuple[AcquiredPage | None, AcquisitionAttempt]:
    started = time.monotonic()
    try:
        page = fn(url)
        elapsed = int((time.monotonic() - started) * 1000)
        return page, AcquisitionAttempt(
            method=method,
            ok=True,
            score=page.score,
            status_code=page.status_code,
            content_chars=len(page.text),
            elapsed_ms=elapsed,
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return None, AcquisitionAttempt(
            method=method,
            ok=False,
            error=re.sub(r"\s+", " ", str(exc)).strip()[:500],
            elapsed_ms=elapsed,
        )


def acquire_url(url: str, *, allow_browsers: bool = True) -> AcquiredPage:
    """Acquire one public URL, escalating only when the cheap path is insufficient.

    Order: bounded HTTP -> Lightpanda (when installed) -> Camoufox. The best successful
    candidate wins, so a weak browser render cannot replace a stronger server response.
    """
    validate_public_url(url)
    attempts: list[AcquisitionAttempt] = []
    candidates: list[AcquiredPage] = []

    static, attempt = _attempt("httpx", _http_fetch, url)
    attempts.append(attempt)
    if static:
        candidates.append(static)

    render_needed = static is None or _needs_render(static)
    if allow_browsers and render_needed:
        lightpanda, attempt = _attempt("lightpanda", _lightpanda_fetch, url)
        attempts.append(attempt)
        if lightpanda:
            candidates.append(lightpanda)

        best_after_lightpanda = max(candidates, key=lambda item: item.score, default=None)
        if best_after_lightpanda is None or best_after_lightpanda.score < 0.72:
            camoufox, attempt = _attempt("camoufox", _camoufox_fetch, url)
            attempts.append(attempt)
            if camoufox:
                candidates.append(camoufox)

    if not candidates:
        errors = "; ".join(f"{a.method}: {a.error}" for a in attempts if a.error)
        raise AcquisitionError(errors or "No acquisition method returned a usable response.")

    best = max(candidates, key=lambda item: (item.score, int(item.rendered), len(item.text)))
    best.attempts = attempts

    if best.status_code >= 400:
        raise AcquisitionError(f"Remote server returned HTTP {best.status_code} and no successful public page was recovered.")
    return best


__all__ = [name for name in globals() if not name.startswith("__")]
