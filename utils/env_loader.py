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


def project_env_path(path=None):
    """Return the existing project .env path, or the preferred writable path."""
    candidates = _candidate_env_paths(path)
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def save_project_env_values(values, path=None):
    """Update selected .env values while preserving unrelated lines and comments."""
    env_path = project_env_path(path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines() if env_path.exists() else []
    pending = {str(key): str(value) for key, value in values.items()}
    output = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in pending:
            output.append(f"{key}={pending.pop(key)}")
        else:
            output.append(line)

    if pending and output and output[-1].strip():
        output.append("")
    output.extend(f"{key}={value}" for key, value in pending.items())
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.environ.update({str(key): str(value) for key, value in values.items()})
    return env_path
