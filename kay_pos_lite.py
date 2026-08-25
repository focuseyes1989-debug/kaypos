"""Source entry point for KAY POS Lite."""

from __future__ import annotations

import signal
import sys

from utils.single_instance import SingleInstanceGuard, show_already_running_message


def main() -> int:
    guard = SingleInstanceGuard(r"Global\KAY_POS_Lite_SingleInstance_v1")
    if not guard.acquire():
        show_already_running_message("KAY POS Lite", "KAY POS Lite is already running on this computer.")
        return 0
    signal.signal(signal.SIGINT, lambda *_args: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_args: sys.exit(0))
    from lite_pos.application import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
