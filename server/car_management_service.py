"""LAN-only Car Management TCP service backed by the KAY POS database."""

from __future__ import annotations

import json
import os
import socket
import secrets
import threading
from datetime import datetime, timedelta
from typing import Callable

from loguru import logger

from models.database import connect_db
from utils.db_compat import ensure_column, integer_primary_key_sql, is_postgres_backend


CAR_COLUMNS = (
    "id", "car_number", "driver_name", "kind_of_car", "type_of_car", "age",
    "nrc_place", "nrc_number", "phone_number", "address", "engine_number",
    "frame_number", "timestamp",
)
EDITABLE_COLUMNS = CAR_COLUMNS[1:-1]
MAX_REQUEST_BYTES = 1024 * 1024
QR_TOKEN_BYTES = 32
DEFAULT_PRINT_SEQUENCE = (1, 2, 3, 4, 2, 3, 2, 3, 4)
PRINT_JOB_STATUSES = {"pending", "printing", "completed", "failed"}


class CarRepository:
    """Database operations shared by the TCP service and migration tooling."""

    def __init__(self, connection_factory: Callable = connect_db):
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS cars (
                    id {integer_primary_key_sql()},
                    car_number TEXT NOT NULL,
                    driver_name TEXT NOT NULL,
                    kind_of_car TEXT,
                    type_of_car TEXT,
                    age TEXT,
                    nrc_place TEXT,
                    nrc_number TEXT NOT NULL,
                    phone_number TEXT,
                    address TEXT,
                    engine_number TEXT,
                    frame_number TEXT,
                    timestamp TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_car_number ON cars(car_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_driver_name ON cars(driver_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nrc_number ON cars(nrc_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_car_timestamp ON cars(timestamp)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS car_qr_tokens (
                    car_id INTEGER PRIMARY KEY,
                    token TEXT NOT NULL UNIQUE,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_car_qr_token ON car_qr_tokens(token)")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS car_print_jobs (
                    id {integer_primary_key_sql()},
                    public_id TEXT NOT NULL UNIQUE,
                    request_key TEXT NOT NULL UNIQUE,
                    car_id INTEGER NOT NULL,
                    page_sequence TEXT NOT NULL,
                    copies INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    requested_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
                )
            """)
            ensure_column(cursor, "car_print_jobs", "printer_name", "TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_car_print_job_status ON car_print_jobs(status, requested_at)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS car_print_printers (
                    printer_name TEXT PRIMARY KEY,
                    client_name TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    last_seen TEXT NOT NULL
                )
            """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS car_print_audit (
                    id {integer_primary_key_sql()},
                    job_public_id TEXT,
                    event TEXT NOT NULL,
                    detail TEXT,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_car_print_audit_job ON car_print_audit(job_public_id, created_at)")
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _record(data) -> tuple:
        data = data if isinstance(data, dict) else {}
        return tuple(str(data.get(column) or "").strip() for column in EDITABLE_COLUMNS)

    @staticmethod
    def _validate(data) -> str | None:
        if not isinstance(data, dict):
            return "Record data must be an object."
        missing = [
            label for key, label in (
                ("car_number", "Car Number"),
                ("driver_name", "Driver Name"),
                ("nrc_number", "NRC Number"),
            )
            if not str(data.get(key) or "").strip()
        ]
        return f"Required fields: {', '.join(missing)}" if missing else None

    @staticmethod
    def _rows(cursor) -> list[dict]:
        columns = [str(column[0]) for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def all(self) -> list[dict]:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cars ORDER BY timestamp DESC, id DESC")
            return self._rows(cursor)
        finally:
            conn.close()

    def search(self, term) -> list[dict]:
        pattern = f"%{str(term or '').strip()}%"
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cars
                WHERE LOWER(COALESCE(car_number, '')) LIKE LOWER(?)
                   OR LOWER(COALESCE(driver_name, '')) LIKE LOWER(?)
                   OR LOWER(COALESCE(nrc_number, '')) LIKE LOWER(?)
                   OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(?)
                   OR LOWER(COALESCE(address, '')) LIKE LOWER(?)
                ORDER BY timestamp DESC, id DESC
            """, (pattern,) * 5)
            return self._rows(cursor)
        finally:
            conn.close()

    def insert(self, data, explicit_id=None) -> int | None:
        error = self._validate(data)
        if error:
            raise ValueError(error)
        values = self._record(data)
        stamp = str(data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            if explicit_id is None:
                cursor.execute(f"""
                    INSERT INTO cars ({', '.join(EDITABLE_COLUMNS)}, timestamp)
                    VALUES ({', '.join('?' for _ in range(len(EDITABLE_COLUMNS) + 1))})
                """, (*values, stamp))
            else:
                cursor.execute(f"""
                    INSERT INTO cars (id, {', '.join(EDITABLE_COLUMNS)}, timestamp)
                    VALUES ({', '.join('?' for _ in range(len(EDITABLE_COLUMNS) + 2))})
                    ON CONFLICT (id) DO NOTHING
                """, (int(explicit_id), *values, stamp))
            inserted = cursor.rowcount > 0
            conn.commit()
            if explicit_id is not None:
                return int(explicit_id) if inserted else None
            return getattr(cursor, "lastrowid", None)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update(self, data) -> bool:
        error = self._validate(data)
        if error:
            raise ValueError(error)
        record_id = int(data.get("id") or 0)
        if record_id <= 0:
            raise ValueError("A valid record ID is required.")
        assignments = ", ".join(f"{column}=?" for column in EDITABLE_COLUMNS)
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE cars SET {assignments}, timestamp=? WHERE id=?",
                (*self._record(data), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), record_id),
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id) -> bool:
        record_id = int(record_id or 0)
        if record_id <= 0:
            raise ValueError("A valid record ID is required.")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM car_print_jobs WHERE car_id=?", (record_id,))
            cursor.execute("DELETE FROM car_qr_tokens WHERE car_id=?", (record_id,))
            cursor.execute("DELETE FROM cars WHERE id=?", (record_id,))
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _public_qr_record(row: dict) -> dict:
        """Return only the fields an owner-facing QR lookup may disclose."""
        vehicle = " ".join(
            part for part in (
                str(row.get("kind_of_car") or "").strip(),
                str(row.get("type_of_car") or "").strip(),
            ) if part
        )
        return {
            "id": row.get("id"),
            "car_number": str(row.get("car_number") or "").strip(),
            "driver_name": str(row.get("driver_name") or "").strip(),
            "vehicle": vehicle,
        }

    def issue_qr_token(self, record_id, rotate=False) -> dict:
        record_id = int(record_id or 0)
        if record_id <= 0:
            raise ValueError("A valid record ID is required.")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cars WHERE id=?", (record_id,))
            rows = self._rows(cursor)
            if not rows:
                raise ValueError("Record not found.")
            record = rows[0]
            cursor.execute(
                "SELECT token FROM car_qr_tokens WHERE car_id=? AND is_active=1",
                (record_id,),
            )
            existing = cursor.fetchone()
            if existing and not rotate:
                token = str(existing[0])
            else:
                token = secrets.token_urlsafe(QR_TOKEN_BYTES)
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO car_qr_tokens (car_id, token, is_active, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT (car_id) DO UPDATE SET
                        token=excluded.token,
                        is_active=1,
                        updated_at=excluded.updated_at
                """, (record_id, token, stamp, stamp))
                conn.commit()
            return {"token": token, "record": self._public_qr_record(record)}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def resolve_qr_token(self, token) -> dict | None:
        token = str(token or "").strip()
        if len(token) < 32 or len(token) > 128:
            return None
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.* FROM cars c
                JOIN car_qr_tokens q ON q.car_id=c.id
                WHERE q.token=? AND q.is_active=1
            """, (token,))
            rows = self._rows(cursor)
            return self._public_qr_record(rows[0]) if rows else None
        finally:
            conn.close()

    def search_public_records(self, query, limit=10) -> list[dict]:
        """Return privacy-limited records for the mobile self-service search."""
        query = str(query or "").strip()
        if len(query) < 2 or len(query) > 100:
            raise ValueError("Enter at least 2 characters to search.")
        limit = max(1, min(int(limit or 10), 20))
        pattern = f"%{query}%"
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, car_number, driver_name, kind_of_car, type_of_car
                FROM cars
                WHERE LOWER(COALESCE(car_number, '')) LIKE LOWER(?)
                   OR LOWER(COALESCE(driver_name, '')) LIKE LOWER(?)
                   OR LOWER(COALESCE(phone_number, '')) LIKE LOWER(?)
                ORDER BY car_number, driver_name, id
                LIMIT ?
            """, (pattern, pattern, pattern, limit))
            rows = self._rows(cursor)
            return [{
                "id": int(row["id"]),
                "car_number": str(row.get("car_number") or "").strip(),
                "driver_name": str(row.get("driver_name") or "").strip(),
                "vehicle": " · ".join(value for value in (
                    str(row.get("kind_of_car") or "").strip(),
                    str(row.get("type_of_car") or "").strip(),
                ) if value) or "—",
            } for row in rows]
        finally:
            conn.close()

    def revoke_qr_token(self, record_id) -> bool:
        record_id = int(record_id or 0)
        if record_id <= 0:
            raise ValueError("A valid record ID is required.")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE car_qr_tokens SET is_active=0, updated_at=? WHERE car_id=? AND is_active=1",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), record_id),
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _public_print_job(row: dict) -> dict:
        try:
            sequence = [int(page) for page in json.loads(str(row.get("page_sequence") or "[]"))]
        except (TypeError, ValueError, json.JSONDecodeError):
            sequence = list(DEFAULT_PRINT_SEQUENCE)
        return {
            "job_id": str(row.get("public_id") or ""),
            "car_number": str(row.get("car_number") or "").strip(),
            "page_sequence": sequence,
            "copies": int(row.get("copies") or 1),
            "printer_name": str(row.get("printer_name") or ""),
            "status": str(row.get("status") or "pending"),
            "error_message": str(row.get("error_message") or ""),
            "requested_at": str(row.get("requested_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        }

    def _find_print_job(self, cursor, field: str, value) -> dict | None:
        if field not in {"public_id", "request_key"}:
            raise ValueError("Unsupported print-job lookup.")
        cursor.execute(f"""
            SELECT j.*, c.car_number FROM car_print_jobs j
            JOIN cars c ON c.id=j.car_id
            WHERE j.{field}=?
        """, (value,))
        rows = self._rows(cursor)
        return rows[0] if rows else None

    def _agent_print_job(self, row: dict) -> dict:
        job = self._public_print_job(row)
        job["record"] = {column: row.get(column) for column in CAR_COLUMNS}
        return job

    @staticmethod
    def _audit(cursor, job_id, event, detail="", actor="system") -> None:
        cursor.execute("""
            INSERT INTO car_print_audit (job_public_id, event, detail, actor, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(job_id or ""), str(event or "")[:80], str(detail or "")[:1000],
            str(actor or "system")[:80], datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

    def create_print_job(self, qr_token, request_key, copies=1, printer_name="") -> dict:
        qr_token = str(qr_token or "").strip()
        request_key = str(request_key or "").strip()
        copies = int(copies or 1)
        if len(qr_token) < 32 or len(qr_token) > 128:
            raise ValueError("QR code is invalid or disabled.")
        if len(request_key) < 16 or len(request_key) > 128:
            raise ValueError("A valid request key is required.")
        if not 1 <= copies <= 99:
            raise ValueError("Copies must be between 1 and 99.")
        printer_name = str(printer_name or "").strip()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            existing = self._find_print_job(cursor, "request_key", request_key)
            if existing:
                return self._public_print_job(existing)
            cursor.execute("""
                SELECT c.id, c.car_number FROM cars c
                JOIN car_qr_tokens q ON q.car_id=c.id
                WHERE q.token=? AND q.is_active=1
            """, (qr_token,))
            qr_rows = self._rows(cursor)
            if not qr_rows:
                raise ValueError("QR code is invalid or disabled.")
            car = qr_rows[0]
            cursor.execute("""
                SELECT j.*, c.car_number FROM car_print_jobs j
                JOIN cars c ON c.id=j.car_id
                WHERE j.car_id=? ORDER BY j.requested_at DESC, j.id DESC LIMIT 1
            """, (int(car["id"]),))
            latest_rows = self._rows(cursor)
            latest = latest_rows[0] if latest_rows else None
            if latest and str(latest.get("status")) in {"pending", "printing"}:
                return self._public_print_job(latest)
            online_printers = self._available_print_printers(cursor)
            online_names = {item["printer_name"] for item in online_printers}
            if not printer_name:
                default = next((item for item in online_printers if item["is_default"]), None)
                printer_name = str((default or (online_printers[0] if online_printers else {})).get("printer_name") or "")
            if not printer_name or printer_name not in online_names:
                raise ValueError("Select an available printer.")
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            public_id = secrets.token_urlsafe(24)
            cursor.execute("""
                INSERT INTO car_print_jobs
                    (public_id, request_key, car_id, page_sequence, copies, printer_name, status, error_message, requested_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', '', ?, ?)
                ON CONFLICT (request_key) DO NOTHING
            """, (
                public_id, request_key, int(car["id"]),
                json.dumps(DEFAULT_PRINT_SEQUENCE, separators=(",", ":")), copies, printer_name, stamp, stamp,
            ))
            if cursor.rowcount > 0:
                self._audit(cursor, public_id, "job_created", f"car_id={car['id']}; copies={copies}; printer={printer_name}", "owner_web")
            conn.commit()
            job = self._find_print_job(cursor, "request_key", request_key)
            return self._public_print_job(job or {})
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_print_job(self, public_id) -> dict | None:
        public_id = str(public_id or "").strip()
        if len(public_id) < 16 or len(public_id) > 128:
            return None
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            job = self._find_print_job(cursor, "public_id", public_id)
            return self._public_print_job(job) if job else None
        finally:
            conn.close()

    @staticmethod
    def _available_print_printers(cursor) -> list[dict]:
        cutoff = (datetime.now() - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT printer_name, client_name, is_default, last_seen
            FROM car_print_printers WHERE last_seen>=?
            ORDER BY is_default DESC, printer_name
        """, (cutoff,))
        columns = [str(column[0]) for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def register_print_printers(self, client_name, printer_names, default_printer="") -> list[dict]:
        client_name = str(client_name or "Car Client").strip()[:120]
        names = list(dict.fromkeys(str(name or "").strip() for name in (printer_names or []) if str(name or "").strip()))[:50]
        default_printer = str(default_printer or "").strip()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            for name in names:
                cursor.execute("""
                    INSERT INTO car_print_printers (printer_name, client_name, is_default, last_seen)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (printer_name) DO UPDATE SET
                        client_name=excluded.client_name,
                        is_default=excluded.is_default,
                        last_seen=excluded.last_seen
                """, (name, client_name, 1 if name == default_printer else 0, stamp))
            conn.commit()
            return self._available_print_printers(cursor)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def available_print_printers(self) -> list[dict]:
        conn = self._connection_factory()
        try:
            return self._available_print_printers(conn.cursor())
        finally:
            conn.close()

    def pending_print_jobs(self, limit=20, printer_names=None) -> list[dict]:
        limit = max(1, min(int(limit or 20), 100))
        printer_names = [str(name).strip() for name in (printer_names or []) if str(name).strip()]
        if not printer_names:
            return []
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT j.*, {columns} FROM car_print_jobs j
                JOIN cars c ON c.id=j.car_id
                WHERE j.status='pending'
                  AND (COALESCE(j.printer_name, '')='' OR j.printer_name IN ({printer_placeholders}))
                ORDER BY j.requested_at, j.id
                LIMIT ?
            """.format(
                columns=", ".join(f"c.{column} AS {column}" for column in CAR_COLUMNS),
                printer_placeholders=", ".join("?" for _ in printer_names),
            ), (*printer_names, limit))
            return [self._agent_print_job(row) for row in self._rows(cursor)]
        finally:
            conn.close()

    def claim_print_job(self, public_id, printer_names=None) -> dict:
        public_id = str(public_id or "").strip()
        printer_names = [str(name).strip() for name in (printer_names or []) if str(name).strip()]
        if not printer_names:
            raise ValueError("No printers are available on this Print Agent.")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE car_print_jobs SET status='printing', error_message='', updated_at=?
                WHERE public_id=? AND status='pending'
                  AND (COALESCE(printer_name, '')='' OR printer_name IN ({printer_placeholders}))
            """.format(printer_placeholders=", ".join("?" for _ in printer_names)), (stamp, public_id, *printer_names))
            if cursor.rowcount <= 0:
                conn.rollback()
                raise ValueError("Print job is no longer pending.")
            self._audit(cursor, public_id, "job_claimed", "Print Agent claimed the job.", "car_client")
            conn.commit()
            cursor.execute("""
                SELECT j.*, {columns} FROM car_print_jobs j
                JOIN cars c ON c.id=j.car_id WHERE j.public_id=?
            """.format(columns=", ".join(f"c.{column} AS {column}" for column in CAR_COLUMNS)), (public_id,))
            rows = self._rows(cursor)
            if not rows:
                raise ValueError("Print job not found.")
            return self._agent_print_job(rows[0])
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_print_job_status(self, public_id, status, error_message="") -> dict:
        public_id = str(public_id or "").strip()
        status = str(status or "").strip().lower()
        if status not in PRINT_JOB_STATUSES:
            raise ValueError("Invalid print-job status.")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            current = self._find_print_job(cursor, "public_id", public_id)
            if not current:
                raise ValueError("Print job not found.")
            allowed = {
                "pending": {"printing", "failed"},
                "printing": {"completed", "failed"},
                "failed": {"pending"},
                "completed": set(),
            }
            old_status = str(current.get("status") or "pending")
            if status != old_status and status not in allowed.get(old_status, set()):
                raise ValueError(f"Cannot change print job from {old_status} to {status}.")
            cursor.execute("""
                UPDATE car_print_jobs SET status=?, error_message=?, updated_at=? WHERE public_id=?
            """, (
                status, str(error_message or "")[:1000],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), public_id,
            ))
            if status != old_status:
                self._audit(cursor, public_id, f"status_{status}", str(error_message or ""), "car_client")
            conn.commit()
            return self._public_print_job(self._find_print_job(cursor, "public_id", public_id) or {})
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def recover_stale_print_jobs(self, minutes=10) -> int:
        minutes = max(1, min(int(minutes or 10), 1440))
        cutoff = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT public_id FROM car_print_jobs WHERE status='printing' AND updated_at<?", (cutoff,))
            job_ids = [str(row[0]) for row in cursor.fetchall()]
            for job_id in job_ids:
                cursor.execute("""
                    UPDATE car_print_jobs SET status='failed', error_message=?, updated_at=? WHERE public_id=?
                """, ("Print Agent stopped before completion.", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id))
                self._audit(cursor, job_id, "status_failed", "Recovered stale printing job.", "server")
            conn.commit()
            return len(job_ids)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def print_audit(self, limit=100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT job_public_id, event, detail, actor, created_at
                FROM car_print_audit ORDER BY created_at DESC, id DESC LIMIT ?
            """, (limit,))
            return self._rows(cursor)
        finally:
            conn.close()

    def sync_id_sequence(self) -> None:
        """Advance PostgreSQL's serial sequence after legacy explicit-ID imports."""
        if not is_postgres_backend():
            return
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('cars', 'id'),
                    COALESCE((SELECT MAX(id) FROM cars), 1),
                    EXISTS (SELECT 1 FROM cars)
                )
            """)
            conn.commit()
        finally:
            conn.close()


class CarRequestHandler:
    def __init__(self, repository: CarRepository | None = None):
        self.repository = repository or CarRepository()

    def process(self, request) -> dict:
        if not isinstance(request, dict):
            return {"status": "ERROR", "message": "Request must be a JSON object."}
        request_type = str(request.get("type") or "").upper()
        data = request.get("data")
        try:
            if request_type == "GET_DATA":
                return {"status": "SUCCESS", "data": self.repository.all()}
            if request_type == "SEARCH_DATA":
                return {"status": "SUCCESS", "data": self.repository.search(data)}
            if request_type == "SAVE_DATA":
                self.repository.insert(data)
                return {"status": "SUCCESS"}
            if request_type == "UPDATE_DATA":
                if not self.repository.update(data):
                    return {"status": "ERROR", "message": "Record not found."}
                return {"status": "SUCCESS"}
            if request_type == "DELETE_DATA":
                record_id = data.get("id") if isinstance(data, dict) else None
                if not self.repository.delete(record_id):
                    return {"status": "ERROR", "message": "Record not found."}
                return {"status": "SUCCESS"}
            if request_type == "ISSUE_QR":
                record_id = data.get("id") if isinstance(data, dict) else None
                rotate = bool(data.get("rotate")) if isinstance(data, dict) else False
                return {"status": "SUCCESS", "data": self.repository.issue_qr_token(record_id, rotate)}
            if request_type == "RESOLVE_QR":
                token = data.get("token") if isinstance(data, dict) else data
                record = self.repository.resolve_qr_token(token)
                if not record:
                    return {"status": "ERROR", "message": "QR code is invalid or disabled."}
                return {"status": "SUCCESS", "data": record}
            if request_type == "REVOKE_QR":
                record_id = data.get("id") if isinstance(data, dict) else None
                if not self.repository.revoke_qr_token(record_id):
                    return {"status": "ERROR", "message": "Active QR code not found."}
                return {"status": "SUCCESS"}
            if request_type == "GET_PRINT_JOBS":
                self.repository.recover_stale_print_jobs(10)
                limit = data.get("limit", 20) if isinstance(data, dict) else 20
                printers = data.get("printers", []) if isinstance(data, dict) else []
                return {"status": "SUCCESS", "data": self.repository.pending_print_jobs(limit, printers)}
            if request_type == "UPDATE_PRINT_JOB":
                if not isinstance(data, dict):
                    raise ValueError("Print-job data must be an object.")
                job = self.repository.update_print_job_status(
                    data.get("job_id"), data.get("status"), data.get("error_message", "")
                )
                return {"status": "SUCCESS", "data": job}
            if request_type == "CLAIM_PRINT_JOB":
                job_id = data.get("job_id") if isinstance(data, dict) else None
                printers = data.get("printers", []) if isinstance(data, dict) else []
                return {"status": "SUCCESS", "data": self.repository.claim_print_job(job_id, printers)}
            if request_type == "REGISTER_PRINT_AGENT":
                if not isinstance(data, dict):raise ValueError("Printer registration must be an object.")
                printers = self.repository.register_print_printers(data.get("client_name"), data.get("printers"), data.get("default_printer"))
                return {"status": "SUCCESS", "data": printers}
            if request_type == "GET_PRINT_AUDIT":
                limit = data.get("limit", 100) if isinstance(data, dict) else 100
                return {"status": "SUCCESS", "data": self.repository.print_audit(limit)}
            return {"status": "ERROR", "message": "Unknown request type."}
        except (TypeError, ValueError) as exc:
            return {"status": "ERROR", "message": str(exc)}
        except Exception as exc:
            logger.exception(f"Car request failed ({request_type}): {exc}")
            return {"status": "ERROR", "message": "Database operation failed."}


class CarManagementTCPService:
    """Small line-terminated JSON TCP server compatible with the existing client."""

    def __init__(self, host="0.0.0.0", port=12345, handler=None):
        self.host = host
        self.port = int(port)
        self.handler = handler or CarRequestHandler()
        self._socket = None
        self._thread = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.handler.repository.ensure_schema()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        self.port = int(server_socket.getsockname()[1])
        server_socket.listen(20)
        server_socket.settimeout(1.0)
        self._socket = server_socket
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._serve, name="CarManagementTCP", daemon=True)
        self._thread.start()
        logger.info(f"Car Management service listening on {self.host}:{self.port}")

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                client, address = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_client,
                args=(client, address),
                name=f"CarClient-{address[0]}",
                daemon=True,
            ).start()

    def _handle_client(self, client, address) -> None:
        try:
            client.settimeout(10.0)
            chunks = []
            total = 0
            while total < MAX_REQUEST_BYTES:
                part = client.recv(min(65536, MAX_REQUEST_BYTES - total))
                if not part:
                    break
                chunks.append(part)
                total += len(part)
                if b"\n" in part or len(part) < 65536:
                    break
            if total >= MAX_REQUEST_BYTES:
                response = {"status": "ERROR", "message": "Request is too large."}
            else:
                payload = b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")
                response = self.handler.process(json.loads(payload))
            client.sendall((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            client.sendall(b'{"status":"ERROR","message":"Invalid JSON request."}\n')
        except Exception as exc:
            logger.warning(f"Car client {address[0]} failed: {exc}")
        finally:
            try:
                client.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None


def car_server_enabled() -> bool:
    return str(os.getenv("ZAY_CAR_SERVER_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "on"}


def create_configured_car_service() -> CarManagementTCPService:
    return CarManagementTCPService(
        host=os.getenv("ZAY_CAR_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("ZAY_CAR_SERVER_PORT", "12345")),
    )
