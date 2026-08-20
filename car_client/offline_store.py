"""Local cache and durable operation queue for the hybrid Car client."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


CAR_COLUMNS = (
    "id", "car_number", "driver_name", "kind_of_car", "type_of_car", "age",
    "nrc_place", "nrc_number", "phone_number", "address", "engine_number",
    "frame_number", "timestamp",
)
_LOCK = threading.RLock()


def default_store_path() -> Path:
    override = os.getenv("ZAY_CAR_OFFLINE_DB", "").strip()
    if override:
        return Path(override)
    base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return base / "KAY POS" / "Car Management" / "offline.db"


class OfflineCarStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with _LOCK, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_cars (
                    id INTEGER PRIMARY KEY, car_number TEXT NOT NULL, driver_name TEXT NOT NULL,
                    kind_of_car TEXT, type_of_car TEXT, age TEXT, nrc_place TEXT,
                    nrc_number TEXT NOT NULL, phone_number TEXT, address TEXT,
                    engine_number TEXT, frame_number TEXT, timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_operations (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def replace_cache(self, records: list[dict]):
        with _LOCK, self._connect() as conn:
            conn.execute("DELETE FROM cached_cars")
            placeholders = ",".join("?" for _ in CAR_COLUMNS)
            for record in records:
                conn.execute(
                    f"INSERT OR REPLACE INTO cached_cars ({','.join(CAR_COLUMNS)}) VALUES ({placeholders})",
                    tuple(record.get(column) for column in CAR_COLUMNS),
                )

    def all(self) -> list[dict]:
        with _LOCK, self._connect() as conn:
            rows = conn.execute("SELECT * FROM cached_cars ORDER BY timestamp DESC, id DESC").fetchall()
            return [dict(row) for row in rows]

    def search(self, term: str) -> list[dict]:
        value = str(term or "").strip().casefold()
        if not value:
            return self.all()
        fields = ("car_number", "driver_name", "nrc_number", "phone_number", "address")
        return [row for row in self.all() if any(value in str(row.get(key) or "").casefold() for key in fields)]

    def queue_save(self, record: dict) -> int:
        with _LOCK, self._connect() as conn:
            next_id = int(conn.execute("SELECT COALESCE(MIN(id), 0) - 1 FROM cached_cars").fetchone()[0])
            cached = dict(record)
            cached["id"] = next_id
            cached["timestamp"] = cached.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._upsert(conn, cached)
            self._queue(conn, "SAVE_DATA", cached)
            return next_id

    def queue_update(self, record: dict):
        with _LOCK, self._connect() as conn:
            cached = dict(record)
            cached["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._upsert(conn, cached)
            self._queue(conn, "UPDATE_DATA", cached)

    def queue_delete(self, record_id: int):
        with _LOCK, self._connect() as conn:
            conn.execute("DELETE FROM cached_cars WHERE id=?", (int(record_id),))
            self._queue(conn, "DELETE_DATA", {"id": int(record_id)})

    def pending(self) -> list[dict]:
        with _LOCK, self._connect() as conn:
            rows = conn.execute("SELECT * FROM pending_operations ORDER BY queue_id").fetchall()
            return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def complete(self, queue_id: int):
        with _LOCK, self._connect() as conn:
            conn.execute("DELETE FROM pending_operations WHERE queue_id=?", (int(queue_id),))

    def pending_count(self) -> int:
        with _LOCK, self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM pending_operations").fetchone()[0])

    @staticmethod
    def _queue(conn, operation: str, payload: dict):
        conn.execute(
            "INSERT INTO pending_operations(operation,payload,created_at) VALUES (?,?,?)",
            (operation, json.dumps(payload, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )

    @staticmethod
    def _upsert(conn, record: dict):
        placeholders = ",".join("?" for _ in CAR_COLUMNS)
        conn.execute(
            f"INSERT OR REPLACE INTO cached_cars ({','.join(CAR_COLUMNS)}) VALUES ({placeholders})",
            tuple(record.get(column) for column in CAR_COLUMNS),
        )
