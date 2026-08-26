"""Small, user-local configuration store for KAY POS Lite."""

from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_SERVER_URL = "https://127.0.0.1:8000"


def config_path() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    return base / "KAY" / "POSLite" / "config.json"


def load_config(path: Path | None = None) -> dict:
    target = path or config_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    return {
        "server_url": str(data.get("server_url") or DEFAULT_SERVER_URL).strip(),
        # KAY Server Manager generates a self-signed LAN certificate by default.
        "insecure_tls": bool(data.get("insecure_tls", True)),
        "remember_username": str(data.get("remember_username") or ""),
        "receipt_printer_name": str(data.get("receipt_printer_name") or "").strip(),
        "print_receipt_after_sale": bool(data.get("print_receipt_after_sale", False)),
        "open_cash_drawer_after_sale": bool(data.get("open_cash_drawer_after_sale", False)),
    }


def save_config(values: dict, path: Path | None = None) -> dict:
    target = path or config_path()
    current = load_config(target)
    current.update({key: values[key] for key in current if key in values})
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return current
