"""LAN-only Car Management TCP service backed by the KAY POS database."""

from __future__ import annotations

import json
import os
import socket
import threading
from datetime import datetime
from typing import Callable

from loguru import logger

from models.database import connect_db
from utils.db_compat import integer_primary_key_sql, is_postgres_backend


CAR_COLUMNS = (
    "id", "car_number", "driver_name", "kind_of_car", "type_of_car", "age",
    "nrc_place", "nrc_number", "phone_number", "address", "engine_number",
    "frame_number", "timestamp",
)
EDITABLE_COLUMNS = CAR_COLUMNS[1:-1]
MAX_REQUEST_BYTES = 1024 * 1024


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
            cursor.execute("DELETE FROM cars WHERE id=?", (record_id,))
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise
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
