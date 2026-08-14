"""One-way offline-first sync from the local POS database to cloud PostgreSQL."""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Sequence

from loguru import logger

from models.database import connect_db
from models.database.postgres_adapter import connect_postgres
from models.database.postgres_schema import ensure_postgres_app_schema
from utils.db_compat import database_url, is_postgres_backend, quote_identifier, table_columns
from utils.env_loader import load_project_env


DEFAULT_SYNC_TABLES = (
    "category_groups",
    "categories",
    "suppliers",
    "customers",
    "products",
    "product_variants",
    "product_locations",
    "product_discounts",
    "payment_types",
    "sales",
    "sale_items",
    "payments",
    "credit_sales",
    "credit_payments",
    "credit_transactions",
    "stock_movements",
)


@dataclass
class CloudSyncResult:
    ok: bool
    synced_tables: int = 0
    synced_rows: int = 0
    message: str = ""
    backup_path: str = ""


def cloud_sync_enabled() -> bool:
    load_project_env()
    return str(os.getenv("ZAY_POS_CLOUD_SYNC_ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}


def cloud_database_url() -> str:
    load_project_env()
    return os.getenv("ZAY_POS_CLOUD_DATABASE_URL", "").strip()


def _metadata_sql(table: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(table)} (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """


def _ensure_cloud_schema(cursor) -> None:
    previous_backend = os.getenv("ZAY_POS_DB_BACKEND")
    os.environ["ZAY_POS_DB_BACKEND"] = "postgres"
    try:
        ensure_postgres_app_schema(cursor)
    finally:
        if previous_backend is None:
            os.environ.pop("ZAY_POS_DB_BACKEND", None)
        else:
            os.environ["ZAY_POS_DB_BACKEND"] = previous_backend
    cursor.execute(_metadata_sql("cloud_sync_metadata"))


def _local_table_exists(cursor, table_name: str) -> bool:
    try:
        cursor.execute(f"PRAGMA table_info({quote_identifier(table_name)})")
        return bool(cursor.fetchall())
    except Exception:
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = CURRENT_SCHEMA()
              AND table_name = ?
        """, (table_name,))
        return cursor.fetchone() is not None


def _local_columns(cursor, table_name: str) -> List[str]:
    return list(table_columns(cursor, table_name))


def _cloud_columns(cursor, table_name: str) -> List[str]:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = CURRENT_SCHEMA()
          AND table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return [str(row[0]) for row in cursor.fetchall()]


def _row_count(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}")
    row = cursor.fetchone()
    return int(row[0] or 0) if row else 0


def _fetch_local_rows(cursor, table_name: str, columns: Sequence[str], limit: int, offset: int) -> List[tuple]:
    col_sql = ", ".join(quote_identifier(column) for column in columns)
    order_sql = "id" if "id" in columns else columns[0]
    cursor.execute(
        f"""
        SELECT {col_sql}
        FROM {quote_identifier(table_name)}
        ORDER BY {quote_identifier(order_sql)}
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return cursor.fetchall()


def _fetch_cloud_rows(cursor, table_name: str, columns: Sequence[str], limit: int, offset: int) -> List[tuple]:
    col_sql = ", ".join(quote_identifier(column) for column in columns)
    order_sql = "id" if "id" in columns else columns[0]
    cursor.execute(
        f"""
        SELECT {col_sql}
        FROM {quote_identifier(table_name)}
        ORDER BY {quote_identifier(order_sql)}
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )
    return cursor.fetchall()


def _normalize_local_value(value: Any) -> Any:
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    return value


def _upsert_cloud_rows(cursor, table_name: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0

    quoted_columns = ", ".join(quote_identifier(column) for column in columns)
    row_placeholders = f"({', '.join('%s' for _ in columns)})"
    values_placeholders = ", ".join(row_placeholders for _ in rows)
    conflict_column = "id" if "id" in columns else columns[0]
    update_columns = [column for column in columns if column != conflict_column]
    if update_columns:
        update_sql = ", ".join(
            f"{quote_identifier(column)} = EXCLUDED.{quote_identifier(column)}"
            for column in update_columns
        )
        conflict_sql = f"DO UPDATE SET {update_sql}"
    else:
        conflict_sql = "DO NOTHING"

    sql = f"""
        INSERT INTO {quote_identifier(table_name)} ({quoted_columns})
        VALUES {values_placeholders}
        ON CONFLICT ({quote_identifier(conflict_column)}) {conflict_sql}
    """
    params = [value for row in rows for value in row]
    cursor.execute(sql, params)
    return len(rows)


def _upsert_local_rows(cursor, table_name: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    rows = [tuple(_normalize_local_value(value) for value in row) for row in rows]
    if not rows:
        return 0

    quoted_columns = ", ".join(quote_identifier(column) for column in columns)
    row_placeholders = f"({', '.join('?' for _ in columns)})"
    values_placeholders = ", ".join(row_placeholders for _ in rows)
    conflict_column = "id" if "id" in columns else columns[0]
    update_columns = [column for column in columns if column != conflict_column]
    if update_columns:
        update_sql = ", ".join(
            f"{quote_identifier(column)} = excluded.{quote_identifier(column)}"
            for column in update_columns
        )
        conflict_sql = f"DO UPDATE SET {update_sql}"
    else:
        conflict_sql = "DO NOTHING"

    sql = f"""
        INSERT INTO {quote_identifier(table_name)} ({quoted_columns})
        VALUES {values_placeholders}
        ON CONFLICT ({quote_identifier(conflict_column)}) {conflict_sql}
    """
    params = [value for row in rows for value in row]
    cursor.execute(sql, params)
    return len(rows)


def _upsert_category_rows(cursor, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    rows = list(rows)
    if not rows or "parent_id" not in columns or "id" not in columns:
        return _upsert_cloud_rows(cursor, "categories", columns, rows)

    parent_index = columns.index("parent_id")
    id_index = columns.index("id")
    insert_rows = []
    parent_updates = []
    for row in rows:
        row_values = list(row)
        parent_id = row_values[parent_index]
        if parent_id:
            parent_updates.append((parent_id, row_values[id_index]))
            row_values[parent_index] = None
        insert_rows.append(tuple(row_values))

    synced = _upsert_cloud_rows(cursor, "categories", columns, insert_rows)
    for parent_id, category_id in parent_updates:
        cursor.execute("""
            UPDATE categories
            SET parent_id = %s
            WHERE id = %s
              AND EXISTS (SELECT 1 FROM categories parent WHERE parent.id = %s)
        """, (parent_id, category_id, parent_id))
    return synced


def _upsert_local_category_rows(cursor, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    rows = list(rows)
    if not rows or "parent_id" not in columns or "id" not in columns:
        return _upsert_local_rows(cursor, "categories", columns, rows)

    parent_index = columns.index("parent_id")
    id_index = columns.index("id")
    insert_rows = []
    parent_updates = []
    for row in rows:
        row_values = list(row)
        parent_id = row_values[parent_index]
        if parent_id:
            parent_updates.append((parent_id, row_values[id_index]))
            row_values[parent_index] = None
        insert_rows.append(tuple(row_values))

    synced = _upsert_local_rows(cursor, "categories", columns, insert_rows)
    for parent_id, category_id in parent_updates:
        cursor.execute("""
            UPDATE categories
            SET parent_id = ?
            WHERE id = ?
              AND EXISTS (SELECT 1 FROM categories parent WHERE parent.id = ?)
        """, (parent_id, category_id, parent_id))
    return synced


def _backup_local_sqlite_database() -> str:
    if is_postgres_backend():
        return ""
    try:
        from models.database.connection import DB_NAME
    except Exception:
        DB_NAME = os.path.join("database", "pos.db")

    db_path = Path(DB_NAME)
    if not db_path.exists():
        return ""

    backup_dir = db_path.parent / "cloud_pull_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pos_before_cloud_pull_{stamp}.db"
    shutil.copy2(db_path, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, backup_dir / f"{backup_path.name}{suffix}")
    return str(backup_path)


def _normalize_database_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _set_metadata(cursor, key: str, value: str) -> None:
    cursor.execute("""
        INSERT INTO cloud_sync_metadata (key, value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            updated_at = CURRENT_TIMESTAMP
    """, (key, value))


def _metadata_value(cursor, key: str) -> str | None:
    try:
        cursor.execute("SELECT value FROM cloud_sync_metadata WHERE key = %s", (key,))
        row = cursor.fetchone()
        return str(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


class CloudSyncService:
    """Push local operational tables to Aiven/PostgreSQL without blocking local sales."""

    def __init__(self, database_url: str | None = None, tables: Sequence[str] | None = None, batch_size: int = 500):
        self.database_url = database_url or cloud_database_url()
        self.tables = tuple(tables or DEFAULT_SYNC_TABLES)
        self.batch_size = max(50, int(batch_size or 500))

    def test_connection(self) -> CloudSyncResult:
        if not self.database_url:
            return CloudSyncResult(False, message="ZAY_POS_CLOUD_DATABASE_URL is not configured.")
        try:
            conn = connect_postgres(self.database_url)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            return CloudSyncResult(True, message="Cloud PostgreSQL connection OK.")
        except Exception as exc:
            return CloudSyncResult(False, message=str(exc))

    def initialize_cloud(self) -> CloudSyncResult:
        if not self.database_url:
            return CloudSyncResult(False, message="ZAY_POS_CLOUD_DATABASE_URL is not configured.")
        try:
            conn = connect_postgres(self.database_url)
            cursor = conn.cursor()
            _ensure_cloud_schema(cursor)
            _set_metadata(cursor, "schema_initialized", "1")
            conn.commit()
            conn.close()
            return CloudSyncResult(True, message="Cloud schema initialized.")
        except Exception as exc:
            logger.warning(f"Cloud schema initialization failed: {exc}")
            return CloudSyncResult(False, message=str(exc))

    def sync_once(self) -> CloudSyncResult:
        if not self.database_url:
            return CloudSyncResult(False, message="ZAY_POS_CLOUD_DATABASE_URL is not configured.")

        local_conn = None
        cloud_conn = None
        synced_tables = 0
        synced_rows = 0
        started = time.time()
        try:
            local_conn = connect_db()
            local_cursor = local_conn.cursor()
            cloud_conn = connect_postgres(self.database_url)
            cloud_cursor = cloud_conn.cursor()
            if _metadata_value(cloud_cursor, "schema_initialized") != "1":
                _ensure_cloud_schema(cloud_cursor)
                _set_metadata(cloud_cursor, "schema_initialized", "1")
                cloud_conn.commit()

            for table_name in self.tables:
                if not _local_table_exists(local_cursor, table_name):
                    continue
                local_columns = _local_columns(local_cursor, table_name)
                cloud_columns = _cloud_columns(cloud_cursor, table_name)
                columns = [
                    column for column in local_columns
                    if column in cloud_columns and column != "image_data"
                ]
                if not columns or ("id" not in columns and not columns[0]):
                    continue

                total_rows = _row_count(local_cursor, table_name)
                offset = 0
                table_rows = 0
                while offset < total_rows:
                    rows = _fetch_local_rows(local_cursor, table_name, columns, self.batch_size, offset)
                    if table_name == "categories":
                        table_rows += _upsert_category_rows(cloud_cursor, columns, rows)
                    else:
                        table_rows += _upsert_cloud_rows(cloud_cursor, table_name, columns, rows)
                    offset += self.batch_size
                if table_rows or total_rows == 0:
                    synced_tables += 1
                    synced_rows += table_rows
                    cloud_conn.commit()
                    logger.info(f"Cloud synced {table_name}: {table_rows} row(s)")

            _set_metadata(cloud_cursor, "last_sync_at", time.strftime("%Y-%m-%d %H:%M:%S"))
            _set_metadata(cloud_cursor, "last_sync_rows", str(synced_rows))
            _set_metadata(cloud_cursor, "source_backend", "postgres" if is_postgres_backend() else "sqlite")
            cloud_conn.commit()
            elapsed = time.time() - started
            return CloudSyncResult(
                True,
                synced_tables=synced_tables,
                synced_rows=synced_rows,
                message=f"Synced {synced_rows} row(s) from {synced_tables} table(s) in {elapsed:.1f}s.",
            )
        except Exception as exc:
            if cloud_conn:
                try:
                    cloud_conn.rollback()
                except Exception:
                    pass
            logger.warning(f"Cloud sync failed: {exc}")
            return CloudSyncResult(False, synced_tables=synced_tables, synced_rows=synced_rows, message=str(exc))
        finally:
            for conn in (cloud_conn, local_conn):
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def pull_once(self) -> CloudSyncResult:
        """Pull cloud data into the local POS database.

        Cloud rows win on id conflicts. This is intended for server-PC recovery
        after clients used the cloud database while the local server was down.
        """
        if not self.database_url:
            return CloudSyncResult(False, message="ZAY_POS_CLOUD_DATABASE_URL is not configured.")
        if is_postgres_backend() and _normalize_database_url(database_url()) == _normalize_database_url(self.database_url):
            return CloudSyncResult(
                False,
                message=(
                    "Cloud pull refused because the primary database URL is the same as the cloud URL. "
                    "Set the local server database as ZAY_POS_DATABASE_URL before pulling from cloud."
                ),
            )

        local_conn = None
        cloud_conn = None
        synced_tables = 0
        synced_rows = 0
        backup_path = ""
        started = time.time()
        try:
            backup_path = _backup_local_sqlite_database()
            previous_failover = os.getenv("ZAY_POS_DATABASE_FAILOVER_ENABLED")
            os.environ["ZAY_POS_DATABASE_FAILOVER_ENABLED"] = "0"
            try:
                local_conn = connect_db()
            finally:
                if previous_failover is None:
                    os.environ.pop("ZAY_POS_DATABASE_FAILOVER_ENABLED", None)
                else:
                    os.environ["ZAY_POS_DATABASE_FAILOVER_ENABLED"] = previous_failover
            local_cursor = local_conn.cursor()
            cloud_conn = connect_postgres(self.database_url)
            cloud_cursor = cloud_conn.cursor()
            if _metadata_value(cloud_cursor, "schema_initialized") != "1":
                _ensure_cloud_schema(cloud_cursor)
                _set_metadata(cloud_cursor, "schema_initialized", "1")
                cloud_conn.commit()

            for table_name in self.tables:
                if not _local_table_exists(local_cursor, table_name):
                    continue
                local_columns = _local_columns(local_cursor, table_name)
                cloud_columns = _cloud_columns(cloud_cursor, table_name)
                columns = [
                    column for column in cloud_columns
                    if column in local_columns
                ]
                if not columns or ("id" not in columns and not columns[0]):
                    continue

                total_rows = _row_count(cloud_cursor, table_name)
                offset = 0
                table_rows = 0
                while offset < total_rows:
                    rows = _fetch_cloud_rows(cloud_cursor, table_name, columns, self.batch_size, offset)
                    if table_name == "categories":
                        table_rows += _upsert_local_category_rows(local_cursor, columns, rows)
                    else:
                        table_rows += _upsert_local_rows(local_cursor, table_name, columns, rows)
                    offset += self.batch_size
                if table_rows or total_rows == 0:
                    synced_tables += 1
                    synced_rows += table_rows
                    local_conn.commit()
                    logger.info(f"Pulled {table_name} from cloud: {table_rows} row(s)")

            elapsed = time.time() - started
            backup_note = f" Backup: {backup_path}" if backup_path else ""
            return CloudSyncResult(
                True,
                synced_tables=synced_tables,
                synced_rows=synced_rows,
                backup_path=backup_path,
                message=f"Pulled {synced_rows} row(s) from {synced_tables} table(s) in {elapsed:.1f}s.{backup_note}",
            )
        except Exception as exc:
            if local_conn:
                try:
                    local_conn.rollback()
                except Exception:
                    pass
            logger.warning(f"Cloud pull failed: {exc}")
            return CloudSyncResult(
                False,
                synced_tables=synced_tables,
                synced_rows=synced_rows,
                backup_path=backup_path,
                message=str(exc),
            )
        finally:
            for conn in (cloud_conn, local_conn):
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass


class CloudSyncManager:
    """Small background runner used by the desktop app."""

    def __init__(self, interval_seconds: int | None = None):
        load_project_env()
        self.interval_seconds = max(60, int(interval_seconds or os.getenv("ZAY_POS_CLOUD_SYNC_INTERVAL_SECONDS", 300)))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running or not cloud_sync_enabled():
            return
        if not cloud_database_url():
            logger.warning("Cloud sync is enabled but ZAY_POS_CLOUD_DATABASE_URL is empty.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="CloudSyncManager", daemon=True)
        self._thread.start()
        logger.info("Cloud sync manager started")

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False

    def _run(self) -> None:
        service = CloudSyncService()
        while not self._stop_event.is_set():
            result = service.sync_once()
            if result.ok:
                logger.info(f"Cloud sync complete: {result.message}")
            else:
                logger.warning(f"Cloud sync skipped/failed: {result.message}")
            self._stop_event.wait(self.interval_seconds)


def start_cloud_sync_manager() -> CloudSyncManager | None:
    if not cloud_sync_enabled():
        return None
    manager = CloudSyncManager()
    manager.start()
    return manager
