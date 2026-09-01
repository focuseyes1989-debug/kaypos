"""Database and domain service for POS Lite service orders.

Phase 1 deliberately has no HTTP or UI dependencies.  The repository owns the
schema and lifecycle rules so later API and desktop pages share one source of
truth.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Callable

from models.database import connect_db
from utils.db_compat import begin_transaction_sql, integer_primary_key_sql, is_postgres_backend


SERVICE_ORDER_STATUSES = (
    "received",
    "typing_designing",
    "waiting_approval",
    "ready_to_print",
    "printing",
    "ready_for_pickup",
    "assigned",
    "in_progress",
    "waiting_parts",
    "on_hold",
    "ready",
    "completed",
    "delivered",
    "cancelled",
)

STATUS_TRANSITIONS = {
    "received": {"typing_designing", "waiting_approval", "ready_to_print", "assigned", "in_progress", "on_hold", "cancelled"},
    "typing_designing": {"waiting_approval", "ready_to_print", "on_hold", "cancelled"},
    "waiting_approval": {"typing_designing", "ready_to_print", "on_hold", "cancelled"},
    "ready_to_print": {"printing", "on_hold", "cancelled"},
    "printing": {"ready_for_pickup", "on_hold", "cancelled"},
    "ready_for_pickup": {"printing", "completed", "delivered", "cancelled"},
    "assigned": {"in_progress", "on_hold", "cancelled"},
    "in_progress": {"waiting_parts", "on_hold", "ready", "completed", "cancelled"},
    "waiting_parts": {"in_progress", "on_hold", "cancelled"},
    "on_hold": {"typing_designing", "waiting_approval", "ready_to_print", "printing", "assigned", "in_progress", "waiting_parts", "cancelled"},
    "ready": {"in_progress", "completed", "delivered", "cancelled"},
    "completed": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}

ITEM_TYPES = {"service", "part", "custom"}
PRIORITIES = {"normal", "urgent"}
PRINT_PRICING_UNITS = {"per_page", "per_sheet", "per_copy", "per_job", "per_item"}
PRINT_COLOR_MODES = {"bw", "color", "photo", "not_applicable"}
PRINT_SIDES = {"single", "double", "not_applicable"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _rows(cursor) -> list[dict]:
    columns = [str(column[0]) for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _row(cursor) -> dict | None:
    columns = [str(column[0]) for column in cursor.description]
    value = cursor.fetchone()
    return dict(zip(columns, value)) if value else None


def _is_sqlite_cursor(cursor) -> bool:
    return type(cursor).__module__.split(".", 1)[0] == "sqlite3"


def _table_exists(cursor, name: str) -> bool:
    if _is_sqlite_cursor(cursor):
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    else:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = CURRENT_SCHEMA() AND table_name = ?",
            (name,),
        )
    return cursor.fetchone() is not None


def _ensure_column(cursor, table: str, column: str, definition: str) -> None:
    if _is_sqlite_cursor(cursor):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
    else:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = CURRENT_SCHEMA() AND table_name = ?",
            (table,),
        )
        columns = {row[0] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _sold_by_mode(value: object) -> str:
    mode = " ".join(str(value or "each").strip().lower().replace("_", " ").split())
    if mode in {"service", "services"} or mode.endswith(" service"):
        return "service"
    if mode in {"variant", "variants"} or mode.endswith(" variants"):
        return "variants"
    return "each"


def _insert_and_get_id(cursor, sql: str, params: tuple) -> int:
    if not _is_sqlite_cursor(cursor) and is_postgres_backend():
        cursor.execute(f"{sql} RETURNING id", params)
        return int(cursor.fetchone()[0])
    cursor.execute(sql, params)
    return int(cursor.lastrowid)


def ensure_service_order_schema(cursor) -> None:
    """Create the additive, SQLite/PostgreSQL-compatible Phase 1 schema."""
    pk_sql = "INTEGER PRIMARY KEY AUTOINCREMENT" if _is_sqlite_cursor(cursor) else integer_primary_key_sql()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS service_orders (
            id {pk_sql},
            order_no TEXT NOT NULL UNIQUE,
            customer_id INTEGER,
            customer_name TEXT,
            customer_phone TEXT,
            status TEXT NOT NULL DEFAULT 'received',
            priority TEXT NOT NULL DEFAULT 'normal',
            assigned_to TEXT,
            received_at TIMESTAMP NOT NULL,
            expected_at TIMESTAMP,
            completed_at TIMESTAMP,
            completed_by TEXT,
            delivered_at TIMESTAMP,
            item_name TEXT,
            item_model TEXT,
            job_title TEXT,
            file_source TEXT,
            file_reference TEXT,
            approval_status TEXT NOT NULL DEFAULT 'not_required',
            serial_no TEXT,
            accessories TEXT,
            condition_notes TEXT,
            complaint TEXT,
            diagnosis TEXT,
            internal_notes TEXT,
            deposit_amount REAL NOT NULL DEFAULT 0,
            sale_id INTEGER,
            checkout_started_at TIMESTAMP,
            sale_refunded_at TIMESTAMP,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS service_order_items (
            id {pk_sql},
            service_order_id INTEGER NOT NULL,
            product_id INTEGER,
            variant_id INTEGER,
            item_type TEXT NOT NULL DEFAULT 'service',
            description TEXT NOT NULL,
            qty REAL NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL DEFAULT 0,
            estimated_cost REAL NOT NULL DEFAULT 0,
            actual_cost REAL NOT NULL DEFAULT 0,
            warranty_days INTEGER NOT NULL DEFAULT 0,
            pricing_unit TEXT NOT NULL DEFAULT 'per_item',
            pages_per_copy INTEGER NOT NULL DEFAULT 1,
            copy_count INTEGER NOT NULL DEFAULT 1,
            total_sheets INTEGER NOT NULL DEFAULT 1,
            paper_size TEXT,
            paper_type TEXT,
            color_mode TEXT NOT NULL DEFAULT 'not_applicable',
            print_side TEXT NOT NULL DEFAULT 'not_applicable',
            finishing TEXT,
            file_name TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (service_order_id) REFERENCES service_orders(id) ON DELETE CASCADE
        )
    """)
    _ensure_column(cursor, "service_orders", "checkout_started_at", "TIMESTAMP")
    _ensure_column(cursor, "service_orders", "sale_refunded_at", "TIMESTAMP")
    _ensure_column(cursor, "service_orders", "completed_by", "TEXT")
    _ensure_column(cursor, "service_orders", "job_title", "TEXT")
    _ensure_column(cursor, "service_orders", "file_source", "TEXT")
    _ensure_column(cursor, "service_orders", "file_reference", "TEXT")
    _ensure_column(cursor, "service_orders", "approval_status", "TEXT NOT NULL DEFAULT 'not_required'")
    for column, definition in (
        ("pricing_unit", "TEXT NOT NULL DEFAULT 'per_item'"),
        ("pages_per_copy", "INTEGER NOT NULL DEFAULT 1"),
        ("copy_count", "INTEGER NOT NULL DEFAULT 1"),
        ("total_sheets", "INTEGER NOT NULL DEFAULT 1"),
        ("paper_size", "TEXT"), ("paper_type", "TEXT"),
        ("color_mode", "TEXT NOT NULL DEFAULT 'not_applicable'"),
        ("print_side", "TEXT NOT NULL DEFAULT 'not_applicable'"),
        ("finishing", "TEXT"), ("file_name", "TEXT"),
    ):
        _ensure_column(cursor, "service_order_items", column, definition)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS service_order_status_history (
            id {pk_sql},
            service_order_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            note TEXT,
            changed_by TEXT NOT NULL,
            changed_at TIMESTAMP NOT NULL,
            FOREIGN KEY (service_order_id) REFERENCES service_orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS service_order_payments (
            id {pk_sql},
            service_order_id INTEGER NOT NULL,
            payment_type TEXT NOT NULL,
            amount REAL NOT NULL,
            reference_no TEXT,
            note TEXT,
            received_by TEXT NOT NULL,
            received_at TIMESTAMP NOT NULL,
            sale_id INTEGER,
            FOREIGN KEY (service_order_id) REFERENCES service_orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS service_order_return_visits (
            id {pk_sql},
            service_order_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            resolution TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            handled_by TEXT,
            visited_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY (service_order_id) REFERENCES service_orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS service_order_notifications (
            id {pk_sql},
            service_order_id INTEGER NOT NULL,
            event TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'queue',
            recipient TEXT,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            sent_at TIMESTAMP,
            error_message TEXT,
            FOREIGN KEY (service_order_id) REFERENCES service_orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS print_service_presets (
            id {pk_sql},
            name TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL,
            description TEXT,
            pricing_unit TEXT NOT NULL DEFAULT 'per_item',
            unit_price REAL NOT NULL DEFAULT 0,
            pages_per_copy INTEGER NOT NULL DEFAULT 1,
            copy_count INTEGER NOT NULL DEFAULT 1,
            paper_size TEXT,
            paper_type TEXT,
            color_mode TEXT NOT NULL DEFAULT 'not_applicable',
            print_side TEXT NOT NULL DEFAULT 'not_applicable',
            finishing TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_orders_status ON service_orders(status, updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_orders_customer ON service_orders(customer_id, updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_orders_received ON service_orders(received_at, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_order_items_order ON service_order_items(service_order_id, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_order_history_order ON service_order_status_history(service_order_id, changed_at, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_order_payments_order ON service_order_payments(service_order_id, received_at, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_return_visits_order ON service_order_return_visits(service_order_id, visited_at, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_notifications_status ON service_order_notifications(status, created_at, id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_print_service_presets_sort ON print_service_presets(active, sort_order, name)")


class ServiceOrderRepository:
    """Transaction-safe persistence and lifecycle operations."""

    def __init__(self, connection_factory: Callable = connect_db):
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        conn = self._connection_factory()
        try:
            ensure_service_order_schema(conn.cursor())
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _prepare(conn, cursor) -> None:
        """Finish additive DDL before starting an order transaction.

        PostgreSQL starts a transaction for DDL automatically, while SQLite's
        explicit BEGIN IMMEDIATE is used below to serialize order numbering.
        """
        ensure_service_order_schema(cursor)
        conn.commit()

    @staticmethod
    def _validate_status(status: object) -> str:
        value = str(status or "").strip().lower()
        if value not in SERVICE_ORDER_STATUSES:
            raise ValueError(f"Invalid service order status: {status}")
        return value

    @staticmethod
    def _validate_priority(priority: object) -> str:
        value = str(priority or "normal").strip().lower()
        if value not in PRIORITIES:
            raise ValueError("Priority must be normal or urgent")
        return value

    @staticmethod
    def _next_order_no(cursor, received_at: str) -> str:
        try:
            day = datetime.fromisoformat(str(received_at)).strftime("%Y%m%d")
        except ValueError as exc:
            raise ValueError("received_at must be an ISO date or datetime") from exc
        prefix = f"SO-{day}-"
        cursor.execute(
            "SELECT order_no FROM service_orders WHERE order_no LIKE ? ORDER BY order_no DESC LIMIT 1",
            (f"{prefix}%",),
        )
        last = cursor.fetchone()
        sequence = 1
        if last:
            try:
                sequence = int(str(last[0]).rsplit("-", 1)[-1]) + 1
            except ValueError:
                sequence = 1
        return f"{prefix}{sequence:04d}"

    def create(self, values: dict, *, created_by: str) -> dict:
        actor = str(created_by or "").strip()
        if not actor:
            raise ValueError("created_by is required")
        received_at = str(values.get("received_at") or _now()).strip()
        status = self._validate_status(values.get("status") or "received")
        if status != "received":
            raise ValueError("New service orders must start as received")
        priority = self._validate_priority(values.get("priority"))
        deposit = max(0.0, float(values.get("deposit_amount") or 0))
        now = _now()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            if _is_sqlite_cursor(cursor):
                cursor.execute(begin_transaction_sql(immediate=True))
            order_no = self._next_order_no(cursor, received_at)
            columns = (
                "order_no", "customer_id", "customer_name", "customer_phone", "status", "priority",
                "assigned_to", "received_at", "expected_at", "item_name", "item_model", "serial_no",
                "job_title", "file_source", "file_reference", "approval_status",
                "accessories", "condition_notes", "complaint", "diagnosis", "internal_notes",
                "deposit_amount", "created_by", "created_at", "updated_at",
            )
            data = (
                order_no, values.get("customer_id"), str(values.get("customer_name") or "").strip(),
                str(values.get("customer_phone") or "").strip(), status, priority,
                str(values.get("assigned_to") or "").strip(), received_at,
                str(values.get("expected_at") or "").strip() or None,
                str(values.get("item_name") or "").strip(), str(values.get("item_model") or "").strip(),
                str(values.get("serial_no") or "").strip(),
                str(values.get("job_title") or "").strip(), str(values.get("file_source") or "").strip(),
                str(values.get("file_reference") or "").strip(), str(values.get("approval_status") or "not_required").strip(),
                str(values.get("accessories") or "").strip(), str(values.get("condition_notes") or "").strip(), str(values.get("complaint") or "").strip(),
                str(values.get("diagnosis") or "").strip(), str(values.get("internal_notes") or "").strip(),
                deposit, actor, now, now,
            )
            order_id = _insert_and_get_id(
                cursor,
                f"INSERT INTO service_orders ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                data,
            )
            cursor.execute(
                "INSERT INTO service_order_status_history (service_order_id, from_status, to_status, note, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, None, status, "Order created", actor, now),
            )
            conn.commit()
            return self.get(order_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, order_id: int) -> dict:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            cursor.execute("SELECT * FROM service_orders WHERE id = ?", (int(order_id),))
            order = _row(cursor)
            if not order:
                raise ValueError("Service order not found")
            cursor.execute("SELECT * FROM service_order_items WHERE service_order_id = ? ORDER BY id", (int(order_id),))
            order["items"] = _rows(cursor)
            cursor.execute("SELECT * FROM service_order_status_history WHERE service_order_id = ? ORDER BY changed_at, id", (int(order_id),))
            order["status_history"] = _rows(cursor)
            cursor.execute("SELECT * FROM service_order_payments WHERE service_order_id = ? ORDER BY received_at, id", (int(order_id),))
            order["payments"] = _rows(cursor)
            cursor.execute("SELECT * FROM service_order_return_visits WHERE service_order_id = ? ORDER BY visited_at DESC, id DESC", (int(order_id),))
            order["return_visits"] = _rows(cursor)
            cursor.execute("SELECT * FROM service_order_notifications WHERE service_order_id = ? ORDER BY created_at DESC, id DESC", (int(order_id),))
            order["notifications"] = _rows(cursor)
            return order
        finally:
            conn.close()

    def list(self, *, status: str = "", search: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(self._validate_status(status))
        if str(search or "").strip():
            clauses.append("(order_no LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ? OR job_title LIKE ? OR file_reference LIKE ? OR item_name LIKE ? OR serial_no LIKE ?)")
            pattern = f"%{str(search).strip()}%"
            params.extend([pattern] * 7)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([max(1, min(int(limit), 200)), max(0, int(offset))])
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            cursor.execute(f"SELECT * FROM service_orders{where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?", tuple(params))
            return _rows(cursor)
        finally:
            conn.close()

    def list_presets(self, *, include_inactive: bool = False) -> list[dict]:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            where = "" if include_inactive else " WHERE COALESCE(active, 1) = 1"
            cursor.execute(f"SELECT * FROM print_service_presets{where} ORDER BY sort_order, name, id")
            return _rows(cursor)
        finally:
            conn.close()

    def save_preset(self, values: dict, preset_id: int | None = None) -> dict:
        name = str(values.get("name") or "").strip()
        product_id = int(values.get("product_id") or 0)
        if not name:
            raise ValueError("Preset name is required")
        if not product_id:
            raise ValueError("Preset requires a Sold by Service product")
        options = self._print_job_options(values)
        now = _now(); conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            if _table_exists(cursor, "products"):
                cursor.execute("SELECT name, sold_by FROM products WHERE id = ?", (product_id,))
                product = cursor.fetchone()
                if not product:
                    raise ValueError("Preset product not found")
                if _sold_by_mode(product[1]) != "service":
                    raise ValueError("Preset product must be Sold by Service")
            data = (
                name, product_id, str(values.get("description") or name).strip(), options["pricing_unit"],
                max(0.0, float(values.get("unit_price") or 0)), options["pages_per_copy"], options["copy_count"],
                options["paper_size"], options["paper_type"], options["color_mode"], options["print_side"],
                options["finishing"], max(0, int(values.get("sort_order") or 0)), 1 if values.get("active", True) else 0,
            )
            if preset_id:
                cursor.execute("""
                    UPDATE print_service_presets SET
                        name = ?, product_id = ?, description = ?, pricing_unit = ?, unit_price = ?,
                        pages_per_copy = ?, copy_count = ?, paper_size = ?, paper_type = ?, color_mode = ?,
                        print_side = ?, finishing = ?, sort_order = ?, active = ?, updated_at = ?
                    WHERE id = ?
                """, data + (now, int(preset_id)))
                if cursor.rowcount != 1:
                    raise ValueError("Print service preset not found")
                saved_id = int(preset_id)
            else:
                saved_id = _insert_and_get_id(cursor, """
                    INSERT INTO print_service_presets
                        (name, product_id, description, pricing_unit, unit_price, pages_per_copy, copy_count,
                         paper_size, paper_type, color_mode, print_side, finishing, sort_order, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data + (now, now))
            conn.commit(); cursor.execute("SELECT * FROM print_service_presets WHERE id = ?", (saved_id,))
            return _row(cursor)
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def deactivate_preset(self, preset_id: int) -> None:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            cursor.execute("UPDATE print_service_presets SET active = 0, updated_at = ? WHERE id = ?", (_now(), int(preset_id)))
            if cursor.rowcount != 1:
                raise ValueError("Print service preset not found")
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def update(self, order_id: int, values: dict) -> dict:
        allowed = (
            "customer_id", "customer_name", "customer_phone", "priority", "assigned_to", "expected_at",
            "item_name", "item_model", "serial_no", "job_title", "file_source", "file_reference", "approval_status",
            "accessories", "condition_notes", "complaint",
            "diagnosis", "internal_notes", "deposit_amount",
        )
        changes, params = [], []
        for key in allowed:
            if key not in values:
                continue
            value = values[key]
            if key == "priority":
                value = self._validate_priority(value)
            elif key == "deposit_amount":
                value = max(0.0, float(value or 0))
            elif key != "customer_id":
                value = str(value or "").strip() or None
            changes.append(f"{key} = ?")
            params.append(value)
        if not changes:
            return self.get(order_id)
        changes.append("updated_at = ?")
        params.extend([_now(), int(order_id)])
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            cursor.execute(f"UPDATE service_orders SET {', '.join(changes)} WHERE id = ?", tuple(params))
            if cursor.rowcount != 1:
                raise ValueError("Service order not found")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(order_id)

    @staticmethod
    def _print_job_options(values: dict) -> dict:
        pricing_unit = str(values.get("pricing_unit") or "per_item").strip().lower()
        color_mode = str(values.get("color_mode") or "not_applicable").strip().lower()
        print_side = str(values.get("print_side") or "not_applicable").strip().lower()
        if pricing_unit not in PRINT_PRICING_UNITS:
            raise ValueError("Invalid print pricing unit")
        if color_mode not in PRINT_COLOR_MODES:
            raise ValueError("Invalid print color mode")
        if print_side not in PRINT_SIDES:
            raise ValueError("Invalid print side")
        pages = max(1, int(values.get("pages_per_copy") or 1))
        copies = max(1, int(values.get("copy_count") or 1))
        pages_per_sheet = 2 if print_side == "double" else 1
        total_sheets = math.ceil(pages / pages_per_sheet) * copies
        if pricing_unit == "per_page":
            qty = pages * copies
        elif pricing_unit == "per_sheet":
            qty = total_sheets
        elif pricing_unit == "per_copy":
            qty = copies
        elif pricing_unit == "per_job":
            qty = 1
        else:
            qty = float(values.get("qty", 1) if values.get("qty", 1) is not None else 1)
        return {
            "pricing_unit": pricing_unit, "pages_per_copy": pages, "copy_count": copies,
            "total_sheets": total_sheets, "qty": float(qty),
            "paper_size": str(values.get("paper_size") or "").strip(),
            "paper_type": str(values.get("paper_type") or "").strip(),
            "color_mode": color_mode, "print_side": print_side,
            "finishing": str(values.get("finishing") or "").strip(),
            "file_name": str(values.get("file_name") or "").strip(),
        }

    def add_item(self, order_id: int, values: dict) -> dict:
        item_type = str(values.get("item_type") or "service").strip().lower()
        description = str(values.get("description") or "").strip()
        print_options = self._print_job_options(values)
        qty = print_options["qty"]
        if item_type not in ITEM_TYPES:
            raise ValueError("Item type must be service, part or custom")
        if not description:
            raise ValueError("Item description is required")
        if qty <= 0:
            raise ValueError("Item quantity must be greater than zero")
        now = _now()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            cursor.execute("SELECT status FROM service_orders WHERE id = ?", (int(order_id),))
            order = cursor.fetchone()
            if not order:
                raise ValueError("Service order not found")
            if order[0] in {"completed", "delivered", "cancelled"}:
                raise ValueError("Closed service orders cannot be edited")
            self._validate_product_item(cursor, values, item_type=item_type, qty=qty)
            item_id = _insert_and_get_id(cursor, """
                INSERT INTO service_order_items
                    (service_order_id, product_id, variant_id, item_type, description, qty, unit_price,
                     estimated_cost, actual_cost, warranty_days, pricing_unit, pages_per_copy, copy_count,
                     total_sheets, paper_size, paper_type, color_mode, print_side, finishing, file_name,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(order_id), values.get("product_id"), values.get("variant_id"), item_type, description, qty,
                max(0.0, float(values.get("unit_price") or 0)), max(0.0, float(values.get("estimated_cost") or 0)),
                max(0.0, float(values.get("actual_cost") or 0)), max(0, int(values.get("warranty_days") or 0)),
                print_options["pricing_unit"], print_options["pages_per_copy"], print_options["copy_count"],
                print_options["total_sheets"], print_options["paper_size"], print_options["paper_type"],
                print_options["color_mode"], print_options["print_side"], print_options["finishing"],
                print_options["file_name"], now, now,
            ))
            cursor.execute("UPDATE service_orders SET updated_at = ? WHERE id = ?", (now, int(order_id)))
            conn.commit()
            cursor.execute("SELECT * FROM service_order_items WHERE id = ?", (item_id,))
            return _row(cursor)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_item(self, order_id: int, item_id: int, values: dict) -> dict:
        allowed = ("product_id", "variant_id", "item_type", "description", "qty", "unit_price", "estimated_cost", "actual_cost", "warranty_days", "pricing_unit", "pages_per_copy", "copy_count", "total_sheets", "paper_size", "paper_type", "color_mode", "print_side", "finishing", "file_name")
        changes, params = [], []
        for key in allowed:
            if key not in values:
                continue
            value = values[key]
            if key == "item_type":
                value = str(value or "").strip().lower()
                if value not in ITEM_TYPES:
                    raise ValueError("Item type must be service, part or custom")
            elif key == "description":
                value = str(value or "").strip()
                if not value:
                    raise ValueError("Item description is required")
            elif key == "qty":
                value = float(value or 0)
                if value <= 0:
                    raise ValueError("Item quantity must be greater than zero")
            elif key in {"unit_price", "estimated_cost", "actual_cost"}:
                value = max(0.0, float(value or 0))
            elif key == "warranty_days":
                value = max(0, int(value or 0))
            changes.append(f"{key} = ?")
            params.append(value)
        if not changes:
            return self._get_item(order_id, item_id)
        now = _now()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            self._assert_editable(cursor, order_id)
            cursor.execute(
                "SELECT product_id, variant_id, item_type, description, qty, unit_price, estimated_cost, actual_cost, warranty_days, pricing_unit, pages_per_copy, copy_count, total_sheets, paper_size, paper_type, color_mode, print_side, finishing, file_name FROM service_order_items WHERE id = ? AND service_order_id = ?",
                (int(item_id), int(order_id)),
            )
            existing = cursor.fetchone()
            if not existing:
                raise ValueError("Service order item not found")
            merged = dict(zip(("product_id", "variant_id", "item_type", "description", "qty", "unit_price", "estimated_cost", "actual_cost", "warranty_days", "pricing_unit", "pages_per_copy", "copy_count", "total_sheets", "paper_size", "paper_type", "color_mode", "print_side", "finishing", "file_name"), existing))
            merged.update(values)
            print_options = self._print_job_options(merged)
            self._validate_product_item(
                cursor, merged, item_type=str(merged.get("item_type") or "service"), qty=float(print_options["qty"]),
            )
            for key in ("pricing_unit", "pages_per_copy", "copy_count", "total_sheets", "paper_size", "paper_type", "color_mode", "print_side", "finishing", "file_name", "qty"):
                changes.append(f"{key} = ?"); params.append(print_options[key])
            changes.append("updated_at = ?")
            params.extend([now, int(item_id), int(order_id)])
            cursor.execute(
                f"UPDATE service_order_items SET {', '.join(changes)} WHERE id = ? AND service_order_id = ?",
                tuple(params),
            )
            if cursor.rowcount != 1:
                raise ValueError("Service order item not found")
            cursor.execute("UPDATE service_orders SET updated_at = ? WHERE id = ?", (now, int(order_id)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._get_item(order_id, item_id)

    def delete_item(self, order_id: int, item_id: int) -> None:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            self._assert_editable(cursor, order_id)
            cursor.execute(
                "DELETE FROM service_order_items WHERE id = ? AND service_order_id = ?",
                (int(item_id), int(order_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Service order item not found")
            cursor.execute("UPDATE service_orders SET updated_at = ? WHERE id = ?", (_now(), int(order_id)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_item(self, order_id: int, item_id: int) -> dict:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            cursor.execute(
                "SELECT * FROM service_order_items WHERE id = ? AND service_order_id = ?",
                (int(item_id), int(order_id)),
            )
            item = _row(cursor)
            if not item:
                raise ValueError("Service order item not found")
            return item
        finally:
            conn.close()

    @staticmethod
    def _assert_editable(cursor, order_id: int) -> None:
        cursor.execute("SELECT status FROM service_orders WHERE id = ?", (int(order_id),))
        order = cursor.fetchone()
        if not order:
            raise ValueError("Service order not found")
        if order[0] in {"completed", "delivered", "cancelled"}:
            raise ValueError("Closed service orders cannot be edited")

    @staticmethod
    def _validate_product_item(cursor, values: dict, *, item_type: str, qty: float) -> None:
        """Validate catalog mapping and availability without reserving stock."""
        product_id = int(values.get("product_id") or 0)
        variant_id = int(values.get("variant_id") or 0)
        if item_type == "custom":
            if product_id or variant_id:
                raise ValueError("Custom charges cannot reference a catalog product")
            return
        if not product_id:
            raise ValueError("Select a product for service and part items")
        # Isolated service-layer consumers may initialize before the main POS
        # schema; normal POS databases always have products.
        if not _table_exists(cursor, "products"):
            return
        cursor.execute("SELECT name, sold_by, COALESCE(stock, 0) FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        if not product:
            raise ValueError("Selected product not found")
        name, sold_by, stock = product
        mode = _sold_by_mode(sold_by)
        if item_type == "service":
            if mode != "service":
                raise ValueError(f"{name} is not a Sold by Service product")
            if variant_id:
                raise ValueError("Service products do not use variants")
            return
        if mode == "service":
            raise ValueError(f"{name} must be added as a service item")
        if mode == "variants":
            if not variant_id:
                raise ValueError(f"Select a variant for {name}")
            cursor.execute(
                "SELECT COALESCE(stock, 0) FROM product_variants WHERE id = ? AND product_id = ? AND COALESCE(active, 1) = 1",
                (variant_id, product_id),
            )
            variant = cursor.fetchone()
            if not variant:
                raise ValueError("Selected product variant not found")
            stock = float(variant[0] or 0)
        elif variant_id:
            raise ValueError("This product does not use variants")
        if float(stock or 0) < qty:
            raise ValueError(f"Only {float(stock or 0):g} currently available: {name}")

    def record_deposit(
        self, order_id: int, amount: float, *, payment_type: str, received_by: str,
        reference_no: str = "", note: str = "",
    ) -> dict:
        amount = float(amount or 0)
        actor = str(received_by or "").strip()
        if amount <= 0:
            raise ValueError("Deposit amount must be greater than zero")
        if not actor:
            raise ValueError("received_by is required")
        now = _now(); conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            self._assert_editable(cursor, order_id)
            _insert_and_get_id(cursor, """
                INSERT INTO service_order_payments
                    (service_order_id, payment_type, amount, reference_no, note, received_by, received_at, sale_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(order_id), str(payment_type or "Cash").strip(), amount, str(reference_no or "").strip(), str(note or "").strip(), actor, now, None))
            cursor.execute(
                "UPDATE service_orders SET deposit_amount = COALESCE(deposit_amount, 0) + ?, updated_at = ? WHERE id = ?",
                (amount, now, int(order_id)),
            )
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
        return self.get(order_id)

    def mark_sale_refunded(self, sale_id: int, *, refunded_by: str, note: str = "") -> dict | None:
        """Attach financial refund history while retaining the completed job lifecycle."""
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            cursor.execute("SELECT id, status FROM service_orders WHERE sale_id = ?", (int(sale_id),))
            linked = cursor.fetchone()
            if not linked:
                return None
            order_id, status = int(linked[0]), str(linked[1])
            now = _now()
            cursor.execute("UPDATE service_orders SET sale_refunded_at = ?, updated_at = ? WHERE id = ?", (now, now, order_id))
            cursor.execute(
                "INSERT INTO service_order_status_history (service_order_id, from_status, to_status, note, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, status, status, str(note or "POS sale refunded").strip(), str(refunded_by or "POS Lite"), now),
            )
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
        return self.get(order_id)

    def checkout(
        self, order_id: int, *, payment: float, payment_type: str, created_by: str,
        allow_credit_over_limit: bool = False,
    ) -> dict:
        """Claim an order, create its POS sale, then durably link the receipt."""
        actor = str(created_by or "").strip()
        if not actor:
            raise ValueError("created_by is required")
        payment = max(0.0, float(payment or 0)); payment_type = str(payment_type or "Cash").strip() or "Cash"
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            if _is_sqlite_cursor(cursor):
                cursor.execute(begin_transaction_sql(immediate=True))
            cursor.execute(
                "SELECT status, sale_id, customer_id, COALESCE(deposit_amount, 0) FROM service_orders WHERE id = ?",
                (int(order_id),),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Service order not found")
            status, sale_id, customer_id, deposit = order
            if int(sale_id or 0) > 0:
                raise ValueError("Service order has already been checked out")
            if int(sale_id or 0) == -1:
                raise ValueError("Service order checkout is already in progress")
            if str(status) not in {"ready", "ready_for_pickup", "completed"}:
                raise ValueError("Service order must be ready for pickup before checkout")
            cursor.execute("SELECT id, product_id, variant_id, item_type, description, qty, unit_price FROM service_order_items WHERE service_order_id = ? ORDER BY id", (int(order_id),))
            rows = cursor.fetchall()
            if not rows:
                raise ValueError("Add at least one item before checkout")
            sale_items = []
            total = 0.0
            for _item_id, product_id, variant_id, item_type, description, qty, unit_price in rows:
                quantity = float(qty or 0)
                if quantity <= 0 or not quantity.is_integer():
                    raise ValueError(f"Checkout requires a whole-number quantity: {description}")
                if str(item_type) == "custom" or not product_id:
                    raise ValueError("Map custom charges to a Sold by Service product before checkout")
                self._validate_product_item(cursor, {"product_id": product_id, "variant_id": variant_id}, item_type=str(item_type), qty=quantity)
                sale_items.append({
                    "product_id": int(product_id), "variant_id": int(variant_id or 0) or None,
                    "qty": int(quantity), "manual_price": float(unit_price or 0) if str(item_type) == "service" else None,
                })
                total += quantity * float(unit_price or 0)
            combined_payment = float(deposit or 0) + payment
            is_credit = payment_type.casefold() == "credit"
            if not is_credit and combined_payment < total:
                raise ValueError(f"Remaining payment is insufficient. Balance: {max(0.0, total - float(deposit or 0)):,.0f} Ks")
            cursor.execute(
                "UPDATE service_orders SET sale_id = -1, checkout_started_at = ?, updated_at = ? WHERE id = ? AND sale_id IS NULL",
                (_now(), _now(), int(order_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Service order checkout is already in progress")
            conn.commit()
        except Exception:
            conn.rollback(); conn.close(); raise
        conn.close()

        try:
            from server import cashier_service
            receipt = cashier_service.create_sale(
                items=sale_items, payment=combined_payment, payment_type=payment_type,
                sale_mode="Credit" if is_credit else "Cash", customer_id=customer_id,
                credit_notes=f"Service Order {order_id}", allow_credit_over_limit=allow_credit_over_limit,
                created_by=actor,
            )
        except Exception:
            release = self._connection_factory()
            try:
                release_cursor = release.cursor(); self._prepare(release, release_cursor)
                release_cursor.execute("UPDATE service_orders SET sale_id = NULL, checkout_started_at = NULL WHERE id = ? AND sale_id = -1", (int(order_id),))
                release.commit()
            finally:
                release.close()
            raise

        sale_id = int(receipt.get("id") or receipt.get("sale_id") or 0)
        if sale_id <= 0:
            raise ValueError("POS sale returned an invalid receipt")
        finish = self._connection_factory()
        try:
            cursor = finish.cursor(); self._prepare(finish, cursor); now = _now()
            cursor.execute(
                "UPDATE service_orders SET sale_id = ?, status = 'completed', completed_at = COALESCE(completed_at, ?), checkout_started_at = NULL, updated_at = ? WHERE id = ? AND sale_id = -1",
                (sale_id, now, now, int(order_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Could not link the completed service sale")
            _insert_and_get_id(cursor, """
                INSERT INTO service_order_payments
                    (service_order_id, payment_type, amount, reference_no, note, received_by, received_at, sale_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(order_id), payment_type, payment, str(receipt.get("invoice_no") or ""), "Checkout payment", actor, now, sale_id))
            if str(status) != "completed":
                cursor.execute("INSERT INTO service_order_status_history (service_order_id, from_status, to_status, note, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?)", (int(order_id), str(status), "completed", f"Checked out as {receipt.get('invoice_no') or sale_id}", actor, now))
            finish.commit()
        except Exception:
            finish.rollback(); raise
        finally:
            finish.close()
        result = self.get(order_id); result["receipt"] = receipt
        return result

    def add_return_visit(
        self, order_id: int, *, reason: str, created_by: str,
        visited_at: str = "", handled_by: str = "",
    ) -> dict:
        reason = str(reason or "").strip(); actor = str(created_by or "").strip()
        if not reason:
            raise ValueError("Return visit reason is required")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            cursor.execute("SELECT sale_id FROM service_orders WHERE id = ?", (int(order_id),))
            order = cursor.fetchone()
            if not order:
                raise ValueError("Service order not found")
            if int(order[0] or 0) <= 0:
                raise ValueError("Return visits require a completed service sale")
            now = _now()
            _insert_and_get_id(cursor, """
                INSERT INTO service_order_return_visits
                    (service_order_id, reason, resolution, status, handled_by, visited_at, closed_at, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(order_id), reason, "", "open", str(handled_by or "").strip(), str(visited_at or now), None, actor, now))
            cursor.execute("UPDATE service_orders SET updated_at = ? WHERE id = ?", (now, int(order_id)))
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
        return self.get(order_id)

    def close_return_visit(self, order_id: int, visit_id: int, *, resolution: str, handled_by: str) -> dict:
        resolution = str(resolution or "").strip()
        if not resolution:
            raise ValueError("Return visit resolution is required")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor); now = _now()
            cursor.execute("""
                UPDATE service_order_return_visits
                SET status = 'closed', resolution = ?, handled_by = ?, closed_at = ?
                WHERE id = ? AND service_order_id = ? AND status = 'open'
            """, (resolution, str(handled_by or "").strip(), now, int(visit_id), int(order_id)))
            if cursor.rowcount != 1:
                raise ValueError("Open return visit not found")
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
        return self.get(order_id)

    def analytics(self, from_date: str, to_date: str) -> dict:
        try:
            start = datetime.strptime(from_date, "%Y-%m-%d")
            end = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError as exc:
            raise ValueError("Report dates must use YYYY-MM-DD") from exc
        if end <= start:
            raise ValueError("Report end date must not be before start date")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            cursor.execute("""
                SELECT status, assigned_to, received_at, completed_at, delivered_at,
                       COALESCE(deposit_amount, 0), sale_id, sale_refunded_at
                FROM service_orders WHERE received_at >= ? AND received_at < ?
            """, (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")))
            orders = _rows(cursor)
            cursor.execute("""
                SELECT soi.description, soi.qty, soi.unit_price, soi.estimated_cost, soi.actual_cost,
                       soi.pricing_unit, soi.total_sheets, soi.paper_size, soi.paper_type,
                       soi.color_mode, soi.print_side, so.assigned_to
                FROM service_order_items soi JOIN service_orders so ON so.id = soi.service_order_id
                WHERE so.received_at >= ? AND so.received_at < ?
            """, (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")))
            items = _rows(cursor)
            cursor.execute("""
                SELECT status, COUNT(*) FROM service_order_return_visits
                WHERE visited_at >= ? AND visited_at < ? GROUP BY status
            """, (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")))
            returns = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
        finally:
            conn.close()
        status_counts = {status: 0 for status in SERVICE_ORDER_STATUSES}
        turnaround_hours = []
        technicians: dict[str, dict] = {}
        for order in orders:
            status_counts[str(order.get("status") or "received")] = status_counts.get(str(order.get("status") or "received"), 0) + 1
            tech = str(order.get("assigned_to") or "Unassigned")
            record = technicians.setdefault(tech, {"technician": tech, "orders": 0, "completed": 0, "revenue": 0.0})
            record["orders"] += 1
            if order.get("completed_at"):
                record["completed"] += 1
                try:
                    turnaround_hours.append((datetime.fromisoformat(str(order["completed_at"])) - datetime.fromisoformat(str(order["received_at"]))).total_seconds() / 3600)
                except ValueError:
                    pass
        revenue = 0.0; estimated_cost = 0.0; actual_cost = 0.0
        service_types: dict[str, dict] = {}; paper_sizes: dict[str, dict] = {}; color_modes: dict[str, dict] = {}
        for item in items:
            amount = float(item.get("qty") or 0) * float(item.get("unit_price") or 0); revenue += amount
            estimated_cost += float(item.get("estimated_cost") or 0); actual_cost += float(item.get("actual_cost") or 0)
            technicians.setdefault(str(item.get("assigned_to") or "Unassigned"), {"technician": str(item.get("assigned_to") or "Unassigned"), "orders": 0, "completed": 0, "revenue": 0.0})["revenue"] += amount
            for target, key, fallback in (
                (service_types, str(item.get("description") or "Unspecified"), "Unspecified"),
                (paper_sizes, str(item.get("paper_size") or "Not specified"), "Not specified"),
                (color_modes, str(item.get("color_mode") or "not_applicable"), "not_applicable"),
            ):
                name = key or fallback
                row = target.setdefault(name, {"name": name, "lines": 0, "quantity": 0.0, "sheets": 0, "revenue": 0.0})
                row["lines"] += 1; row["quantity"] += float(item.get("qty") or 0)
                row["sheets"] += int(item.get("total_sheets") or 0); row["revenue"] += amount
        def breakdown(values: dict[str, dict]) -> list[dict]:
            return sorted(values.values(), key=lambda row: (-row["revenue"], -row["quantity"], row["name"]))
        return {
            "from_date": from_date, "to_date": to_date, "orders": len(orders), "status_counts": status_counts,
            "revenue": revenue, "estimated_cost": estimated_cost, "actual_cost": actual_cost,
            "average_turnaround_hours": sum(turnaround_hours) / len(turnaround_hours) if turnaround_hours else 0,
            "return_visits": returns, "technicians": sorted(technicians.values(), key=lambda row: (-row["completed"], -row["revenue"], row["technician"])),
            "service_types": breakdown(service_types), "paper_sizes": breakdown(paper_sizes),
            "color_modes": breakdown(color_modes),
        }

    def warranty_items(self, *, days: int = 30) -> list[dict]:
        today = datetime.now(); cutoff = today + timedelta(days=max(0, int(days)))
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            cursor.execute("""
                SELECT so.id, so.order_no, so.customer_name, so.customer_phone, so.completed_at,
                       soi.description, soi.warranty_days
                FROM service_orders so JOIN service_order_items soi ON soi.service_order_id = so.id
                WHERE so.completed_at IS NOT NULL AND soi.warranty_days > 0
                ORDER BY so.completed_at DESC
            """)
            rows = _rows(cursor)
        finally:
            conn.close()
        result = []
        for row in rows:
            try:
                expires = datetime.fromisoformat(str(row["completed_at"])) + timedelta(days=int(row["warranty_days"] or 0))
            except ValueError:
                continue
            if expires >= today and expires <= cutoff:
                row["warranty_expires_at"] = expires.strftime("%Y-%m-%d")
                result.append(row)
        return result

    def notifications(self, *, status: str = "pending", limit: int = 100) -> list[dict]:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor)
            cursor.execute("SELECT * FROM service_order_notifications WHERE status = ? ORDER BY created_at, id LIMIT ?", (str(status or "pending"), max(1, min(int(limit), 200))))
            return _rows(cursor)
        finally:
            conn.close()

    def update_notification(self, notification_id: int, *, status: str, error_message: str = "") -> dict:
        status = str(status or "").strip().lower()
        if status not in {"sent", "failed"}:
            raise ValueError("Notification status must be sent or failed")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor(); self._prepare(conn, cursor); now = _now()
            cursor.execute("""
                UPDATE service_order_notifications
                SET status = ?, attempts = COALESCE(attempts, 0) + 1,
                    sent_at = ?, error_message = ? WHERE id = ?
            """, (status, now if status == "sent" else None, str(error_message or "").strip(), int(notification_id)))
            if cursor.rowcount != 1:
                raise ValueError("Notification not found")
            conn.commit()
            cursor.execute("SELECT * FROM service_order_notifications WHERE id = ?", (int(notification_id),))
            return _row(cursor)
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def change_status(self, order_id: int, to_status: str, *, changed_by: str, note: str = "") -> dict:
        target = self._validate_status(to_status)
        actor = str(changed_by or "").strip()
        if not actor:
            raise ValueError("changed_by is required")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            self._prepare(conn, cursor)
            if _is_sqlite_cursor(cursor):
                cursor.execute(begin_transaction_sql(immediate=True))
            cursor.execute("SELECT status FROM service_orders WHERE id = ?", (int(order_id),))
            record = cursor.fetchone()
            if not record:
                raise ValueError("Service order not found")
            current = str(record[0])
            if target == current:
                raise ValueError("Service order already has that status")
            # The simplified job board permits any open job to be completed
            # directly by a client workstation.
            if target == "completed" and current in {"completed", "delivered", "cancelled"}:
                raise ValueError("Closed service order cannot be completed")
            if target != "completed" and target not in STATUS_TRANSITIONS.get(current, set()):
                raise ValueError(f"Cannot change service order from {current} to {target}")
            now = _now()
            timestamps = ""
            if target == "completed":
                timestamps = ", completed_at = ?"
            elif target == "delivered":
                timestamps = ", delivered_at = ?"
            params = [target, now]
            if timestamps:
                params.append(now)
            params.extend([int(order_id), current])
            approval_sql = ""
            if target == "waiting_approval":
                approval_sql = ", approval_status = 'waiting_customer'"
            elif target == "ready_to_print":
                approval_sql = ", approval_status = 'approved'"
            completed_sql = ", completed_by = ?" if target == "completed" else ""
            if target == "completed":
                params.insert(-2, actor)
            cursor.execute(
                f"UPDATE service_orders SET status = ?, updated_at = ?{timestamps}{approval_sql}{completed_sql} WHERE id = ? AND status = ?",
                tuple(params),
            )
            if cursor.rowcount != 1:
                raise ValueError("Service order was already updated by another client")
            cursor.execute(
                "INSERT INTO service_order_status_history (service_order_id, from_status, to_status, note, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (int(order_id), current, target, str(note or "").strip(), actor, now),
            )
            if target in {"ready", "ready_for_pickup"}:
                cursor.execute("SELECT order_no, customer_name, customer_phone FROM service_orders WHERE id = ?", (int(order_id),))
                order_no, customer_name, phone = cursor.fetchone()
                _insert_and_get_id(cursor, """
                    INSERT INTO service_order_notifications
                        (service_order_id, event, channel, recipient, message, status, attempts, created_at, sent_at, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (int(order_id), "ready_for_pickup", "queue", str(phone or ""), f"{customer_name or 'Customer'}, service order {order_no} is ready for pickup.", "pending", 0, now, None, ""))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(order_id)
