"""Local-management boundary and public-session security helpers."""

from __future__ import annotations

import ipaddress
from typing import Mapping

from fastapi import HTTPException, Request, WebSocket


PUBLIC_TUNNEL_SUFFIX = ".trycloudflare.com"
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "[::1]", "::1"}


def _host_header(headers: Mapping[str, str]) -> str:
    forwarded = headers.get("x-forwarded-host") or headers.get("host") or ""
    return forwarded.split(",", 1)[0].strip().split(":", 1)[0].lower().strip("[]")


def is_public_tunnel_request(request: Request) -> bool:
    """Return True when the request arrived through a Cloudflare quick tunnel."""
    host = _host_header(request.headers)
    return host.endswith(PUBLIC_TUNNEL_SUFFIX) or host == PUBLIC_TUNNEL_SUFFIX.lstrip(".")


def is_public_tunnel_websocket(websocket: WebSocket) -> bool:
    """WebSocket equivalent of :func:`is_public_tunnel_request`."""
    host = _host_header(websocket.headers)
    return host.endswith(PUBLIC_TUNNEL_SUFFIX) or host == PUBLIC_TUNNEL_SUFFIX.lstrip(".")


_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def is_local_client_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip("[]").lower()
    if normalized in LOCAL_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(normalized)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def is_local_request(request: Request) -> bool:
    """Allow management only from a directly connected local/private client."""
    if is_public_tunnel_request(request):
        return False
    return is_local_client_host(request.client.host if request.client else None)


def require_local_request(request: Request) -> None:
    if not is_local_request(request):
        raise HTTPException(
            status_code=403,
            detail="This management endpoint is available only from the local OmniPad host/LAN.",
        )


def require_host_request(request: Request) -> None:
    """Restrict high-impact management to this Windows host's loopback client."""
    host = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        is_loopback = host.lower() in LOCAL_HOSTNAMES
    if is_public_tunnel_request(request) or not is_loopback:
        raise HTTPException(
            status_code=403,
            detail="This control endpoint is available only on the OmniPad host.",
        )


def require_local_websocket(websocket: WebSocket) -> None:
    host = websocket.client.host if websocket.client else None
    if not is_local_client_host(host):
        raise HTTPException(status_code=1008, detail="Host telemetry is local-only.")


def public_target_status(target_status: dict) -> dict:
    """Return only routing health, never process/window identity, to remote players."""
    return {
        "selected": bool(target_status.get("selected")),
        "target_foreground": target_status.get("target_foreground"),
        "target_running": target_status.get("target_running"),
        "selection_mode": target_status.get("selection_mode"),
        "platform_windows": target_status.get("platform_windows"),
        "remote_focus_enabled": bool(target_status.get("remote_focus_enabled")),
    }
