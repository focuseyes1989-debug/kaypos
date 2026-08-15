"""Tests for Windows asyncio disconnect filtering."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import Mock, patch

from server.asyncio_errors import (
    install_windows_disconnect_handler,
    is_expected_windows_client_reset,
)


class _ClientLostHandle:
    def __repr__(self) -> str:
        return "<Handle _ProactorBasePipeTransport._call_connection_lost()>"


class WindowsDisconnectHandlerTests(unittest.TestCase):
    def _reset(self, winerror: int = 10054) -> ConnectionResetError:
        error = ConnectionResetError("connection reset")
        error.winerror = winerror
        return error

    @patch("server.asyncio_errors.sys.platform", "win32")
    def test_identifies_expected_proactor_disconnect(self) -> None:
        context = {"exception": self._reset(), "handle": _ClientLostHandle()}
        self.assertTrue(is_expected_windows_client_reset(context))

    @patch("server.asyncio_errors.sys.platform", "win32")
    def test_does_not_hide_other_connection_resets(self) -> None:
        context = {"exception": self._reset(), "handle": "request callback"}
        self.assertFalse(is_expected_windows_client_reset(context))

    @patch("server.asyncio_errors.sys.platform", "win32")
    def test_handler_delegates_unexpected_errors(self) -> None:
        loop = Mock(spec=asyncio.AbstractEventLoop)
        previous = Mock()
        loop.get_exception_handler.return_value = previous

        returned = install_windows_disconnect_handler(loop)
        handler = loop.set_exception_handler.call_args.args[0]
        context = {"exception": RuntimeError("boom")}
        handler(loop, context)

        self.assertIs(returned, previous)
        previous.assert_called_once_with(loop, context)

    @patch("server.asyncio_errors.sys.platform", "win32")
    def test_handler_suppresses_expected_disconnect(self) -> None:
        loop = Mock(spec=asyncio.AbstractEventLoop)
        previous = Mock()
        loop.get_exception_handler.return_value = previous
        install_windows_disconnect_handler(loop)
        handler = loop.set_exception_handler.call_args.args[0]

        handler(loop, {"exception": self._reset(), "handle": _ClientLostHandle()})

        previous.assert_not_called()


if __name__ == "__main__":
    unittest.main()
