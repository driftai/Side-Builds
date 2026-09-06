"""Windows asyncio noise filtering for expected peer disconnects."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional


ExceptionHandler = Callable[[asyncio.AbstractEventLoop, Dict[str, Any]], None]
_BENIGN_WINDOWS_DISCONNECTS = frozenset({10053, 10054})


def _is_benign_windows_disconnect(context: Dict[str, Any]) -> bool:
    exception = context.get("exception")
    return (
        isinstance(exception, (ConnectionAbortedError, ConnectionResetError))
        and getattr(exception, "winerror", None) in _BENIGN_WINDOWS_DISCONNECTS
    )


def install_disconnect_filter(
    loop: asyncio.AbstractEventLoop,
    logger: logging.Logger,
) -> Optional[ExceptionHandler]:
    """Suppress only Windows peer-reset callback noise; preserve all other errors."""
    previous = loop.get_exception_handler()

    def handle(loop_: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
        if _is_benign_windows_disconnect(context):
            logger.debug("Remote socket closed during transport cleanup")
        elif previous is not None:
            previous(loop_, context)
        else:
            loop_.default_exception_handler(context)

    loop.set_exception_handler(handle)
    return previous
