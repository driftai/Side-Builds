"""Noise control for routine OmniPad HTTP status requests."""

import logging
from typing import Optional, Tuple


_QUIET_GET_PATHS = frozenset({
    "/api/status",
    "/api/target/status",
    "/api/background-capture/status",
    "/api/background-capture/input-state",
})


def _request_details(record: logging.LogRecord) -> Optional[Tuple[str, str, int]]:
    args = record.args
    if isinstance(args, tuple) and len(args) >= 5:
        try:
            return str(args[1]), str(args[2]).split("?", 1)[0], int(args[4])
        except (TypeError, ValueError):
            return None
    return None


class RoutineAccessFilter(logging.Filter):
    """Hide successful routine polling while retaining errors and real traffic."""

    def filter(self, record: logging.LogRecord) -> bool:
        details = _request_details(record)
        if details is None:
            return True
        method, path, status = details
        return not (method == "GET" and path in _QUIET_GET_PATHS and status in {200, 304})


def install_access_log_filter() -> None:
    """Install exactly one filter on Uvicorn's access logger."""
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RoutineAccessFilter) for item in logger.filters):
        logger.addFilter(RoutineAccessFilter())
