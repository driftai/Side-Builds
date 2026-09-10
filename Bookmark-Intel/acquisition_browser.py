from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

from acquisition_base import (
    AcquiredPage,
    AcquisitionError,
    BROWSER_TIMEOUT_MS,
    MAX_BODY_BYTES,
    html_quality,
    validate_public_url,
)
from browser_route_cleanup import settle_page_routes


def _lightpanda_fetch(url: str) -> AcquiredPage:
    executable = shutil.which("lightpanda")
    if not executable:
        raise AcquisitionError("Lightpanda executable is not available on PATH.")
    validate_public_url(url)
    command = [
        executable,
        "fetch",
        "--dump",
        "html",
        "--block-private-networks",
        "--http-max-response-size",
        str(MAX_BODY_BYTES),
        "--log-level",
        "error",
        "--wait-until",
        "networkalmostidle",
        "--terminate-ms",
        "15000",
        url,
    ]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=22,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AcquisitionError("Lightpanda render timed out.") from exc
    html = proc.stdout.strip()
    if len(html) < 40 or "<" not in html:
        detail = proc.stderr.strip()[-400:] if proc.stderr else f"exit {proc.returncode}"
        raise AcquisitionError(f"Lightpanda returned no usable rendered HTML ({detail}).")
    score, _ = html_quality(html, url, "text/html", 200)
    return AcquiredPage(
        requested_url=url,
        final_url=url,
        redirects=[],
        status_code=200,
        content_type="text/html",
        text=html,
        byte_count=len(html.encode("utf-8")),
        method="lightpanda",
        score=score,
        rendered=True,
    )


def _camoufox_fetch(url: str) -> AcquiredPage:
    validate_public_url(url)
    try:
        from camoufox.sync_api import Camoufox
    except Exception as exc:
        raise AcquisitionError("Camoufox Python package is unavailable in this environment.") from exc

    validated_hosts: dict[tuple[str, int], bool] = {}

    def route_request(route: Any, request: Any) -> None:
        req_url = str(request.url)
        parsed = urlparse(req_url)
        if parsed.scheme not in {"http", "https"}:
            route.continue_()
            return
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        key = (host.lower(), port)
        try:
            if key not in validated_hosts:
                validate_public_url(req_url)
                validated_hosts[key] = True
        except AcquisitionError:
            route.abort()
            return
        route.continue_()

    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            try:
                page.route("**/*", route_request)
                response = page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception:
                    page.wait_for_timeout(1_000)
                final_url = str(page.url)
                validate_public_url(final_url)
                html = page.content()
                status = response.status if response else 200
            finally:
                settle_page_routes(page)
    except AcquisitionError:
        raise
    except Exception as exc:
        message = re.sub(r"\s+", " ", str(exc)).strip()
        raise AcquisitionError(f"Camoufox render failed: {message[:300]}") from exc

    score, _ = html_quality(html, final_url, "text/html", status)
    return AcquiredPage(
        requested_url=url,
        final_url=final_url,
        redirects=[final_url] if final_url != url else [],
        status_code=status,
        content_type="text/html",
        text=html,
        byte_count=len(html.encode("utf-8")),
        method="camoufox",
        score=score,
        rendered=True,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
