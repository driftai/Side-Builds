from __future__ import annotations

from browser_route_cleanup import settle_page_routes


class _ModernPage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def unroute_all(self, **kwargs: object) -> None:
        self.calls.append(("unroute_all", kwargs))


class _LegacyPage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def unroute(self, pattern: str) -> None:
        self.calls.append(("unroute", pattern))


def test_settle_page_routes_prefers_ignore_errors_unroute_all() -> None:
    page = _ModernPage()

    settle_page_routes(page)

    assert page.calls == [("unroute_all", {"behavior": "ignoreErrors"})]


def test_settle_page_routes_falls_back_to_unroute() -> None:
    page = _LegacyPage()

    settle_page_routes(page)

    assert page.calls == [("unroute", "**/*")]


def test_settle_page_routes_accepts_none() -> None:
    settle_page_routes(None)
