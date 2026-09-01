from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_SERVER_URL = "https://127.0.0.1:8000"


def config_path() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "KAY" / "ServiceJobClient" / "config.json"


def load_config(path: Path | None = None) -> dict:
    target = path or config_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    return {
        "server_url": str(data.get("server_url") or DEFAULT_SERVER_URL).strip(),
        "insecure_tls": bool(data.get("insecure_tls", True)),
        "remember_username": str(data.get("remember_username") or "").strip(),
    }


def save_config(values: dict, path: Path | None = None) -> dict:
    target = path or config_path()
    current = load_config(target)
    current.update({key: values[key] for key in current if key in values})
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, indent=2), encoding="utf-8")
    temporary.replace(target)
    return current

