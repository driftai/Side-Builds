from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse
import warnings

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

HTTP_TIMEOUT_SECONDS = 18.0
BROWSER_TIMEOUT_MS = 20_000
MAX_BODY_BYTES = 3_000_000
MAX_REDIRECTS = 6
CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)

BLOCK_MARKERS = (
    "just a moment",
    "attention required",
    "access denied",
    "verify you are human",
    "checking your browser",
    "enable javascript and cookies",
    "captcha",
)
SPA_MARKERS = (
    'id="__next"',
    "id='__next'",
    'id="__nuxt"',
    "id='__nuxt'",
    "data-reactroot",
    "data-react-helmet",
    "ng-version=",
)


class AcquisitionError(RuntimeError):
    pass


@dataclass
class AcquisitionAttempt:
    method: str
    ok: bool
    score: float = 0.0
    status_code: int | None = None
    content_chars: int = 0
    reason: str | None = None
    error: str | None = None
    elapsed_ms: int | None = None


@dataclass
class AcquiredPage:
    requested_url: str
    final_url: str
    redirects: list[str]
    status_code: int
    content_type: str
    text: str
    byte_count: int
    method: str
    score: float
    rendered: bool = False
    attempts: list[AcquisitionAttempt] = field(default_factory=list)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "rendered": self.rendered,
            "acquisition_score": round(self.score, 2),
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }


def validate_public_url(raw_url: str) -> str:
    raw_url = str(raw_url).strip()
    if not raw_url:
        raise AcquisitionError("URL is empty.")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AcquisitionError("Only absolute http:// or https:// URLs are supported.")
    if parsed.username or parsed.password:
        raise AcquisitionError("Credentials embedded in URLs are not allowed.")

    host = parsed.hostname.rstrip(".")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AcquisitionError(f"Could not resolve host: {host}") from exc

    if not infos:
        raise AcquisitionError(f"Host resolved to no addresses: {host}")

    for info in infos:
        ip_text = info[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError as exc:
            raise AcquisitionError(f"Invalid resolved IP for host {host}: {ip_text}") from exc
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if ip in CGNAT_NET or any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_reserved,
                ip.is_multicast,
                ip.is_unspecified,
            )
        ):
            raise AcquisitionError(f"Refusing non-public address for host: {host}")
    return raw_url


def _content_type(headers: httpx.Headers) -> str:
    return headers.get("content-type", "").split(";", 1)[0].strip().lower()


def _decode_body(response: httpx.Response, body: bytes) -> str:
    encoding = response.encoding
    if not encoding or encoding.lower() in {"iso-8859-1", "ascii"}:
        sample = body[:4096].decode("ascii", errors="ignore")
        match = re.search(r'''<meta[^>]+charset=["']?([a-zA-Z0-9_-]+)''', sample, re.I)
        encoding = match.group(1) if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


def html_quality(html: str, url: str, content_type: str = "text/html", status_code: int = 200) -> tuple[float, list[str]]:
    if content_type and not any(token in content_type for token in ("html", "xml", "json", "text")):
        return 0.9, ["non-HTML resource; browser rendering not useful"]

    low = (html or "").lower()
    reasons: list[str] = []
    if not html:
        return 0.0, ["empty response body"]

    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript", "svg", "template"]):
        bad.decompose()
    visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    title = ""
    if soup.title:
        title = re.sub(r"\s+", " ", soup.title.get_text(" ", strip=True)).strip()
    if not title:
        meta_title = soup.find("meta", attrs={"property": re.compile(r"^og:title$", re.I)})
        if meta_title and meta_title.get("content"):
            title = str(meta_title.get("content")).strip()
    description = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}) or soup.find(
        "meta", attrs={"property": re.compile(r"^og:description$", re.I)}
    )
    description_text = str(description.get("content", "")).strip() if description else ""
    hostname = (urlparse(url).hostname or "").lower()

    blocked = status_code in {403, 503} or any(marker in low for marker in BLOCK_MARKERS)
    shell = any(marker in low for marker in SPA_MARKERS)
    script_count = len(BeautifulSoup(html, "html.parser").find_all("script"))

    score = 0.0
    if title and title.lower() not in {url.lower(), hostname, f"www.{hostname}"}:
        score += 0.22
        reasons.append("specific title present")
    if description_text and len(description_text) >= 40:
        score += 0.16
        reasons.append("description metadata present")
    if len(visible) >= 1200:
        score += 0.34
        reasons.append("substantial visible text")
    elif len(visible) >= 400:
        score += 0.25
        reasons.append("useful visible text")
    elif len(visible) >= 140:
        score += 0.12
        reasons.append("limited visible text")
    if soup.find("h1"):
        score += 0.08
    if soup.find(["main", "article"]):
        score += 0.08
    if re.search(r"application/(?:ld\+json|json)", low) or "__next_data__" in low or "__nuxt_data__" in low:
        score += 0.08
        reasons.append("structured/embedded state present")
    if len(html) > 5000 and len(visible) / max(len(html), 1) > 0.06:
        score += 0.05

    if shell and len(visible) < 300:
        score -= 0.25
        reasons.append("SPA shell detected")
    if script_count >= 5 and len(visible) < 180:
        score -= 0.15
        reasons.append("script-heavy page with little server-rendered content")
    if blocked:
        score -= 0.45
        reasons.append("challenge/access-block page detected")

    return max(0.0, min(1.0, score)), reasons


def _needs_render(page: AcquiredPage) -> bool:
    if page.content_type and not any(token in page.content_type for token in ("html", "xml", "json", "text")):
        return False
    low = page.text.lower()
    if page.status_code >= 400:
        return True
    if any(marker in low for marker in BLOCK_MARKERS):
        return True
    return page.score < 0.58


__all__ = [name for name in globals() if not name.startswith("__")]
