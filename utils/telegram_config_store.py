"""Atomic .env storage and a shared Native configuration recovery guard."""
import hashlib
import os
import re
from pathlib import Path
import sys
import tempfile
from server.native_file_lock import file_lock

KEYS = ('TELEGRAM_ENABLED', 'TELEGRAM_LISTENER_ENABLED', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')


def env_path():
    return (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]) / '.env'


def digest(data): return hashlib.sha256(data).hexdigest()


def read(path): return path.read_bytes() if path.exists() else b''


def parse(data, keys=KEYS):
    result = {}
    for line in data.decode('utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            if key.strip() in keys: result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def render(data, values, keys=KEYS):
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) for key in keys): raise ValueError('Invalid environment setting name')
    lines = []
    for line in data.decode('utf-8-sig').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped or stripped.split('=', 1)[0].strip() not in keys:
            lines.append(line)
    if lines and lines[-1].strip(): lines.append('')
    for key in keys:
        value = str(values.get(key, '')).strip()
        if any(c in value for c in ('\r', '\n', '\x00')): raise ValueError('Telegram settings must not contain line breaks')
        lines.append(key + '=' + value)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def atomic_write(path, data):
    descriptor, name = tempfile.mkstemp(prefix='.env.telegram.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        Path(name).replace(path)
    finally: Path(name).unlink(missing_ok=True)


def marker_path(path): return path.with_name(path.name + '.telegram.pending')
def lock_path(path): return path.with_name(path.name + '.telegram.lock')


def save_legacy(path, values, keys=KEYS):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(lock_path(path)):
        if marker_path(path).exists():
            raise ValueError('A Native server configuration change needs recovery. Recover it in Native Integrations before editing here.')
        atomic_write(path, render(read(path), values, keys))
    return path
