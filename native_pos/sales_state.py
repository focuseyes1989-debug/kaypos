"""Durable checkout recovery, scoped to one server and signed-in account."""
import hashlib
import json
import os
from pathlib import Path

from native_pos.config import config_path


class CheckoutJournal:
    def __init__(self, server, user_id, directory=None):
        key = hashlib.sha256(f'{server.rstrip("/")}\n{user_id}'.encode()).hexdigest()
        self.path = Path(directory or config_path().parent) / f'checkout-{key}.json'

    def read(self):
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not data.get('payload', {}).get('request_id'):
            raise ValueError('Invalid saved checkout. Keep this file and contact your administrator: ' + str(self.path))
        return data

    def write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def clear(self):
        self.path.unlink(missing_ok=True)
