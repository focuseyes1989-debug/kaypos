"""Lightweight entry point for the standalone Cashier Mode executable."""

import os
import signal
import sys
import traceback

from PyQt6.QtCore import qInstallMessageHandler


def qt_message_handler(_msg_type, _context, message):
    if "Unknown property cursor" in message:
        return
    if "QPropertyAnimation::setTargetObject" in message:
        return
    if "QPropertyAnimation::setPropertyName" in message:
        return
    print(f"Qt: {message}")


def signal_handler(_signum, _frame):
    sys.exit(0)


def main():
    qInstallMessageHandler(qt_message_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        from app.cashier_application import CashierApplication

        return_code = CashierApplication().run()
        if getattr(sys, "frozen", False):
            os._exit(return_code)
        return return_code
    except Exception as exc:
        print(f"Cashier Mode fatal error: {exc}")
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            os._exit(1)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
