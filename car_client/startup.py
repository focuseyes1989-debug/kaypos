"""Windows startup support for the background Car Management print agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def startup_shortcut_path() -> Path:
    appdata = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "KAY Car Management.cmd"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'@start "" /min "{sys.executable}" --tray\n'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.is_file() else Path(sys.executable)
    script = Path(__file__).resolve().parents[1] / "car_client_main.py"
    return f'@start "" /min "{executable}" "{script}" --tray\n'


def set_windows_startup(enabled: bool) -> Path:
    path = startup_shortcut_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(startup_command(), encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return path
