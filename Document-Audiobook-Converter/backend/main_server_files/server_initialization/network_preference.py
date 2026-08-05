"""Control which IP family outbound connections use.

Google API keys are commonly restricted to an IPv4 address. A dual-stack machine
prefers IPv6 (RFC 6724), so the traffic actually leaving the machine is IPv6 and
the restriction rejects it - with a message naming an address the user never
allowlisted. That looks like a broken key rather than a routing preference, and
testing with a tool that happens to use IPv4 makes it look intermittently fine.

Forcing IPv4 resolution makes the connection match the address most people have
allowlisted. Turn it off in server_config if you are on an IPv6-only network.
"""

import socket

_original_getaddrinfo = None


def force_ipv4(enabled: bool = True) -> bool:
    """Restrict name resolution to IPv4. Returns True if the patch is active."""
    global _original_getaddrinfo

    if not enabled:
        if _original_getaddrinfo is not None:
            socket.getaddrinfo = _original_getaddrinfo
            _original_getaddrinfo = None
        return False

    if _original_getaddrinfo is not None:
        return True  # already applied

    _original_getaddrinfo = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        results = _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        if results:
            return results
        # Nothing on IPv4: fall back rather than making the host unreachable.
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = ipv4_only
    return True


def describe_local_ipv4() -> str:
    """The machine's LAN IPv4, for logging.

    Note this is *not* the address Google sees - that is whatever your router
    NATs to. Do not present it as the address to allowlist.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "unknown"
