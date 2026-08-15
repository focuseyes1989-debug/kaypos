"""Asyncio error handling for expected Windows network disconnects."""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable, Mapping, Optional


ExceptionHandler = Callable[[asyncio.AbstractEventLoop, Mapping[str, Any]], None]


def is_expected_windows_client_reset(context: Mapping[str, Any]) -> bool:
    """Return whether *context* is the noisy Proactor client-close callback."""
    if sys.platform != "win32":
        return False

    exception = context.get("exception")
    if not isinstance(exception, ConnectionResetError):
        return False
    if getattr(exception, "winerror", None) != 10054:
        return False

    # Suppress only the callback Python runs while closing a Proactor socket.
    # Other connection resets remain visible so real request failures are logged.
    handle = context.get("handle")
    return "_ProactorBasePipeTransport._call_connection_lost" in repr(handle)


def install_windows_disconnect_handler(
    loop: asyncio.AbstractEventLoop,
) -> Optional[ExceptionHandler]:
    """Hide harmless Windows client disconnect tracebacks on *loop*.

    The previous handler is returned so the caller can restore it at shutdown.
    """
    previous = loop.get_exception_handler()

    def handle_exception(
        current_loop: asyncio.AbstractEventLoop,
        context: Mapping[str, Any],
    ) -> None:
        if is_expected_windows_client_reset(context):
            return
        if previous is not None:
            previous(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(handle_exception)
    return previous
