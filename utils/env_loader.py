"""Minimal .env loader for source and frozen app runs."""

import os
import sys
from pathlib import Path


def _candidate_env_paths(path=None):
    if path:
        return [Path(path)]

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS).resolve().parent / ".env")

    candidates.extend([
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ])

    unique = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def load_project_env(path=None, override=False):
    env_path = next((candidate for candidate in _candidate_env_paths(path) if candidate.exists()), None)
    if env_path is None:
        return {}

    loaded = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded
