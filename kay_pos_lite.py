"""Source entry point for KAY POS Lite."""

from __future__ import annotations

import signal
import sys


def main() -> int:
    # POS Lite is a cashier client. Multiple cashiers may connect to the same
    # server from separate windows, including on one shared workstation.
    signal.signal(signal.SIGINT, lambda *_args: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_args: sys.exit(0))
    from lite_pos.application import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
