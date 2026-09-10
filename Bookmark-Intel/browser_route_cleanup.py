from __future__ import annotations

from typing import Any


def settle_page_routes(page: Any) -> None:
    """Detach page routes before browser teardown without surfacing cancellation noise.

    Playwright can still have route callbacks in flight when a page/browser closes. Newer
    Playwright versions expose ``unroute_all(behavior='ignoreErrors')`` specifically for
    this teardown case. Fall back to ``unroute`` for older compatible builds.
    """
    if page is None:
        return

    unroute_all = getattr(page, "unroute_all", None)
    if callable(unroute_all):
        try:
            unroute_all(behavior="ignoreErrors")
            return
        except TypeError:
            # Older wrappers may expose unroute_all without the behavior keyword.
            try:
                unroute_all()
                return
            except Exception:
                pass
        except Exception:
            pass

    unroute = getattr(page, "unroute", None)
    if callable(unroute):
        try:
            unroute("**/*")
        except Exception:
            pass
