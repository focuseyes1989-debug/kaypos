"""Database helpers for the Restaurant Mode MVP."""

import hashlib
import json
import uuid
from datetime import datetime

from models.database import connect_db
from utils.db_compat import current_timestamp_sql, ensure_column, integer_primary_key_sql, is_postgres_backend, table_columns


def ensure_restaurant_schema(cursor):
    pk_sql = integer_primary_key_sql()
    now_sql = current_timestamp_sql()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS restaurant_tables (
            id {pk_sql},
            table_no TEXT UNIQUE NOT NULL,
            display_name TEXT,
            seats INTEGER DEFAULT 4,
            status TEXT DEFAULT 'available',
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT {now_sql}
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS restaurant_orders (
            id {pk_sql},
            order_no TEXT UNIQUE NOT NULL,
            table_id INTEGER,
            order_type TEXT DEFAULT 'Dine-in',
            status TEXT DEFAULT 'open',
            kitchen_status TEXT DEFAULT 'draft',
            cart_json TEXT NOT NULL,
            customer_id INTEGER,
            customer_name TEXT,
            note TEXT,
            total_amount REAL DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            opened_at TIMESTAMP DEFAULT {now_sql},
            sent_to_kitchen_at TIMESTAMP,
            settled_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            sale_id INTEGER,
            invoice_no TEXT,
            settled_total REAL DEFAULT 0,
            payment_amount REAL DEFAULT 0,
            change_amount REAL DEFAULT 0,
            payment_type TEXT,
            created_at TIMESTAMP DEFAULT {now_sql},
            updated_at TIMESTAMP DEFAULT {now_sql},
            FOREIGN KEY (table_id) REFERENCES restaurant_tables(id) ON DELETE SET NULL
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS restaurant_order_items (
            id {pk_sql},
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            base_price REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            note TEXT,
            line_id TEXT,
            status TEXT DEFAULT 'active',
            kitchen_status TEXT DEFAULT 'draft',
            sent_quantity REAL DEFAULT 0,
            cancelled_quantity REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT {now_sql},
            updated_at TIMESTAMP DEFAULT {now_sql},
            FOREIGN KEY (order_id) REFERENCES restaurant_orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS restaurant_order_modifiers (
            id {pk_sql},
            order_item_id INTEGER NOT NULL,
            group_name TEXT,
            modifier_name TEXT NOT NULL,
            modifier_type TEXT DEFAULT 'note',
            price_delta REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT {now_sql},
            FOREIGN KEY (order_item_id) REFERENCES restaurant_order_items(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS restaurant_kitchen_tickets (
            id {pk_sql},
            ticket_no TEXT UNIQUE NOT NULL,
            order_id INTEGER NOT NULL,
            status TEXT DEFAULT 'sent',
            ticket_signature TEXT NOT NULL,
            printed INTEGER DEFAULT 0,
            note TEXT,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT {now_sql},
            updated_at TIMESTAMP DEFAULT {now_sql},
            FOREIGN KEY (order_id) REFERENCES restaurant_orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS restaurant_kitchen_ticket_items (
            id {pk_sql},
            ticket_id INTEGER NOT NULL,
            order_item_id INTEGER,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            modifier_summary TEXT,
            quantity REAL DEFAULT 0,
            note TEXT,
            status TEXT DEFAULT 'sent',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT {now_sql},
            updated_at TIMESTAMP DEFAULT {now_sql},
            preparing_at TIMESTAMP,
            ready_at TIMESTAMP,
            served_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES restaurant_kitchen_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (order_item_id) REFERENCES restaurant_order_items(id) ON DELETE SET NULL
        )
    """)
    _ensure_restaurant_columns(cursor, now_sql)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_orders_table ON restaurant_orders(table_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_orders_status ON restaurant_orders(status, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_orders_type_status ON restaurant_orders(order_type, status, updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_order_items_order ON restaurant_order_items(order_id, sort_order)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_order_items_status ON restaurant_order_items(order_id, status, kitchen_status)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_order_items_line ON restaurant_order_items(order_id, line_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_order_modifiers_item ON restaurant_order_modifiers(order_item_id)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_signature ON restaurant_kitchen_tickets(order_id, ticket_signature)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_tickets_status ON restaurant_kitchen_tickets(status, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_items_ticket ON restaurant_kitchen_ticket_items(ticket_id, sort_order)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_items_status ON restaurant_kitchen_ticket_items(ticket_id, status)")


def _ensure_restaurant_columns(cursor, now_sql):
    ensure_column(cursor, "restaurant_orders", "opened_at", "TIMESTAMP")
    ensure_column(cursor, "restaurant_orders", "cancelled_at", "TIMESTAMP")
    ensure_column(cursor, "restaurant_orders", "sale_id", "INTEGER")
    ensure_column(cursor, "restaurant_orders", "invoice_no", "TEXT")
    ensure_column(cursor, "restaurant_orders", "settled_total", "REAL DEFAULT 0")
    ensure_column(cursor, "restaurant_orders", "payment_amount", "REAL DEFAULT 0")
    ensure_column(cursor, "restaurant_orders", "change_amount", "REAL DEFAULT 0")
    ensure_column(cursor, "restaurant_orders", "payment_type", "TEXT")
    ensure_column(cursor, "restaurant_order_items", "status", "TEXT DEFAULT 'active'")
    ensure_column(cursor, "restaurant_order_items", "kitchen_status", "TEXT DEFAULT 'draft'")
    ensure_column(cursor, "restaurant_order_items", "sent_quantity", "REAL DEFAULT 0")
    ensure_column(cursor, "restaurant_order_items", "cancelled_quantity", "REAL DEFAULT 0")
    ensure_column(cursor, "restaurant_order_items", "updated_at", "TIMESTAMP")
    ensure_column(cursor, "restaurant_order_items", "line_id", "TEXT")
    _backfill_missing_order_item_line_ids(cursor)
    ensure_column(cursor, "restaurant_kitchen_ticket_items", "preparing_at", "TIMESTAMP")
    ensure_column(cursor, "restaurant_kitchen_ticket_items", "ready_at", "TIMESTAMP")
    ensure_column(cursor, "restaurant_kitchen_ticket_items", "served_at", "TIMESTAMP")
    ensure_column(cursor, "restaurant_kitchen_ticket_items", "cancelled_at", "TIMESTAMP")


def _backfill_missing_order_item_line_ids(cursor):
    cursor.execute("""
        SELECT id
        FROM restaurant_order_items
        WHERE TRIM(COALESCE(line_id, '')) = ''
    """)
    rows = cursor.fetchall()
    for row in rows:
        cursor.execute(
            "UPDATE restaurant_order_items SET line_id = ? WHERE id = ?",
            (uuid.uuid4().hex, row[0]),
        )


def ensure_default_tables(count=12):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("SELECT COUNT(*) FROM restaurant_tables")
    existing = cursor.fetchone()[0]
    if existing == 0:
        rows = [(f"T{i}", f"Table {i}", 4, i) for i in range(1, count + 1)]
        cursor.executemany("""
            INSERT INTO restaurant_tables (table_no, display_name, seats, sort_order)
            VALUES (?, ?, ?, ?)
        """, rows)
    conn.commit()
    conn.close()


def list_restaurant_tables(include_inactive=True):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    if include_inactive:
        cursor.execute("""
            SELECT id, table_no, COALESCE(display_name, table_no), seats,
                   COALESCE(status, 'available'), COALESCE(sort_order, 0),
                   COALESCE(active, 1)
            FROM restaurant_tables
            ORDER BY COALESCE(sort_order, 0), id
        """)
    else:
        cursor.execute("""
            SELECT id, table_no, COALESCE(display_name, table_no), seats,
                   COALESCE(status, 'available'), COALESCE(sort_order, 0),
                   COALESCE(active, 1)
            FROM restaurant_tables
            WHERE COALESCE(active, 1) = 1
            ORDER BY COALESCE(sort_order, 0), id
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_restaurant_table(table_id, table_no, display_name, seats=4, sort_order=0, active=1):
    table_no = str(table_no or "").strip()
    display_name = str(display_name or table_no).strip() or table_no
    if not table_no:
        raise ValueError("Table number is required.")
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    if table_id:
        cursor.execute("""
            UPDATE restaurant_tables
            SET table_no = ?, display_name = ?, seats = ?, sort_order = ?, active = ?
            WHERE id = ?
        """, (table_no, display_name, int(seats or 0), int(sort_order or 0), int(active or 0), table_id))
    else:
        cursor.execute("""
            INSERT INTO restaurant_tables (table_no, display_name, seats, sort_order, active)
            VALUES (?, ?, ?, ?, ?)
        """, (table_no, display_name, int(seats or 0), int(sort_order or 0), int(active or 0)))
        table_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return table_id


def set_restaurant_table_active(table_id, active):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("UPDATE restaurant_tables SET active = ? WHERE id = ?", (1 if active else 0, table_id))
    conn.commit()
    conn.close()


def get_restaurant_setting(key, default=""):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


def save_restaurant_setting(key, value):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    if is_postgres_backend():
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, str(value)))
    else:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_restaurant_database_audit():
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    conn.commit()

    required_columns = {
        "restaurant_orders": {
            "opened_at",
            "cancelled_at",
            "sent_to_kitchen_at",
            "settled_at",
            "updated_at",
            "sale_id",
            "invoice_no",
            "settled_total",
            "payment_amount",
            "change_amount",
            "payment_type",
        },
        "restaurant_order_items": {
            "line_id",
            "status",
            "kitchen_status",
            "sent_quantity",
            "cancelled_quantity",
            "updated_at",
        },
        "restaurant_kitchen_ticket_items": {
            "status",
            "preparing_at",
            "ready_at",
            "served_at",
            "cancelled_at",
            "updated_at",
        },
    }
    missing_columns = {}
    for table_name, columns in required_columns.items():
        existing = table_columns(cursor, table_name)
        missing = sorted(columns - existing)
        if missing:
            missing_columns[table_name] = missing

    metrics_sql = {
        "open_orders": "SELECT COUNT(*) FROM restaurant_orders WHERE status = 'open'",
        "empty_open_orders": """
            SELECT COUNT(*) FROM restaurant_orders
            WHERE status = 'open'
              AND (COALESCE(item_count, 0) <= 0 OR TRIM(COALESCE(cart_json, '[]')) IN ('', '[]'))
        """,
        "active_kitchen_tickets": "SELECT COUNT(*) FROM restaurant_kitchen_tickets WHERE status IN ('sent', 'preparing', 'ready')",
        "stale_ticket_item_links": """
            SELECT COUNT(*)
            FROM restaurant_kitchen_ticket_items kti
            LEFT JOIN restaurant_order_items roi ON roi.id = kti.order_item_id
            WHERE kti.order_item_id IS NOT NULL AND roi.id IS NULL
        """,
        "order_items_without_line_id": """
            SELECT COUNT(*)
            FROM restaurant_order_items
            WHERE status != 'removed' AND TRIM(COALESCE(line_id, '')) = ''
        """,
        "open_takeaway_orders": """
            SELECT COUNT(*) FROM restaurant_orders
            WHERE status = 'open' AND table_id IS NULL AND order_type = 'Takeaway'
        """,
        "occupied_tables": """
            SELECT COUNT(DISTINCT table_id) FROM restaurant_orders
            WHERE status = 'open' AND table_id IS NOT NULL
        """,
        "settled_orders_without_sale_link": """
            SELECT COUNT(*) FROM restaurant_orders
            WHERE status = 'settled' AND sale_id IS NULL
        """,
    }
    metrics = {}
    for key, sql in metrics_sql.items():
        cursor.execute(sql)
        metrics[key] = int(cursor.fetchone()[0] or 0)

    conn.close()
    return {
        "missing_columns": missing_columns,
        "metrics": metrics,
        "ok": (
            not missing_columns
            and metrics.get("empty_open_orders", 0) == 0
            and metrics.get("order_items_without_line_id", 0) == 0
        ),
    }


def list_tables_with_status():
    ensure_default_tables()
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    _close_empty_open_orders(cursor)
    conn.commit()
    cursor.execute("""
        SELECT
            t.id,
            t.table_no,
            COALESCE(t.display_name, t.table_no) AS display_name,
            t.seats,
            CASE WHEN o.id IS NULL THEN 'available' ELSE 'occupied' END AS live_status,
            o.id AS order_id,
            o.order_no,
            COALESCE(o.total_amount, 0),
            COALESCE(o.item_count, 0),
            COALESCE(o.kitchen_status, 'draft')
        FROM restaurant_tables t
        LEFT JOIN restaurant_orders o
            ON o.table_id = t.id AND o.status = 'open'
        WHERE COALESCE(t.active, 1) = 1
        ORDER BY t.sort_order, t.id
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_open_order_for_table(table_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    _close_empty_open_orders(cursor)
    conn.commit()
    cursor.execute("""
        SELECT id, order_no, table_id, order_type, status, kitchen_status,
               cart_json, customer_id, customer_name, note, total_amount, item_count
        FROM restaurant_orders
        WHERE table_id = ? AND status = 'open'
        ORDER BY id DESC
        LIMIT 1
    """, (table_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_order(row)


def get_order(order_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("""
        SELECT id, order_no, table_id, order_type, status, kitchen_status,
               cart_json, customer_id, customer_name, note, total_amount, item_count
        FROM restaurant_orders
        WHERE id = ?
    """, (order_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_order(row)


def list_open_takeaway_orders():
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    _close_empty_open_orders(cursor)
    conn.commit()
    cursor.execute("""
        SELECT id, order_no, table_id, order_type, status, kitchen_status,
               cart_json, customer_id, customer_name, note, total_amount, item_count
        FROM restaurant_orders
        WHERE table_id IS NULL AND order_type = 'Takeaway' AND status = 'open'
        ORDER BY updated_at DESC, id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_order(row) for row in rows]


def upsert_order(order_id, table_id, order_type, cart, customer_id=None, customer_name="", note="", total_amount=0):
    _ensure_cart_line_ids(cart)
    item_count = sum(int(item.get("qty", 0) or 0) for item in cart)
    payload = json.dumps(cart, ensure_ascii=False)
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    if order_id:
        cursor.execute("""
            UPDATE restaurant_orders
            SET table_id = ?, order_type = ?, cart_json = ?, customer_id = ?,
                customer_name = ?, note = ?, total_amount = ?, item_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (table_id, order_type, payload, customer_id, customer_name, note,
              float(total_amount or 0), item_count, order_id))
    else:
        order_no = datetime.now().strftime("RO%Y%m%d%H%M%S%f")
        cursor.execute("""
            INSERT INTO restaurant_orders
            (order_no, table_id, order_type, cart_json, customer_id, customer_name,
             note, total_amount, item_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_no, table_id, order_type, payload, customer_id, customer_name,
              note, float(total_amount or 0), item_count))
        order_id = cursor.lastrowid
    _sync_order_items(cursor, order_id, cart)
    conn.commit()
    conn.close()
    return order_id


def send_to_kitchen(order_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    ticket_id = _create_kitchen_ticket(cursor, order_id)
    if ticket_id:
        _sync_order_item_kitchen_statuses(cursor, ticket_id)
        cursor.execute("""
            UPDATE restaurant_orders
            SET kitchen_status = 'sent',
                sent_to_kitchen_at = COALESCE(sent_to_kitchen_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (order_id,))
    conn.commit()
    conn.close()
    return ticket_id


def list_kitchen_tickets(statuses=None, limit=50):
    statuses = statuses or ("sent", "preparing", "ready")
    placeholders = ",".join("?" for _ in statuses)
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute(f"""
        SELECT
            kt.id,
            kt.ticket_no,
            kt.order_id,
            kt.status,
            kt.created_at,
            COALESCE(t.display_name, ro.order_type, 'Order') AS source_name,
            ro.order_no,
            ro.order_type,
            COUNT(kti.id) AS item_lines,
            COALESCE(SUM(kti.quantity), 0) AS item_count
        FROM restaurant_kitchen_tickets kt
        JOIN restaurant_orders ro ON ro.id = kt.order_id
        LEFT JOIN restaurant_tables t ON t.id = ro.table_id
        LEFT JOIN restaurant_kitchen_ticket_items kti ON kti.ticket_id = kt.id
        WHERE kt.status IN ({placeholders})
        GROUP BY kt.id, kt.ticket_no, kt.order_id, kt.status, kt.created_at,
                 t.display_name, ro.order_no, ro.order_type
        ORDER BY kt.created_at ASC, kt.id ASC
        LIMIT ?
    """, tuple(statuses) + (int(limit),))
    rows = cursor.fetchall()
    tickets = []
    for row in rows:
        ticket = {
            "id": row[0],
            "ticket_no": row[1],
            "order_id": row[2],
            "status": row[3] or "sent",
            "created_at": row[4] or "",
            "source_name": row[5] or "Order",
            "order_no": row[6] or "",
            "order_type": row[7] or "",
            "item_lines": int(row[8] or 0),
            "item_count": _safe_float(row[9], 0),
            "items": [],
        }
        ticket["items"] = _load_ticket_items(cursor, ticket["id"])
        tickets.append(ticket)
    conn.close()
    return tickets


def get_kitchen_ticket(ticket_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("""
        SELECT
            kt.id,
            kt.ticket_no,
            kt.order_id,
            kt.status,
            kt.created_at,
            COALESCE(t.display_name, ro.order_type, 'Order') AS source_name,
            ro.order_no,
            ro.order_type,
            kt.printed,
            kt.note
        FROM restaurant_kitchen_tickets kt
        JOIN restaurant_orders ro ON ro.id = kt.order_id
        LEFT JOIN restaurant_tables t ON t.id = ro.table_id
        WHERE kt.id = ?
    """, (ticket_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    ticket = {
        "id": row[0],
        "ticket_no": row[1],
        "order_id": row[2],
        "status": row[3] or "sent",
        "created_at": row[4] or "",
        "source_name": row[5] or "Order",
        "order_no": row[6] or "",
        "order_type": row[7] or "",
        "printed": int(row[8] or 0),
        "note": row[9] or "",
        "items": _load_ticket_items(cursor, row[0]),
    }
    conn.close()
    return ticket


def build_kitchen_ticket_lines(ticket, width=32):
    width = max(24, min(int(width or 32), 48))
    lines = [
        "=" * width,
        "KITCHEN TICKET".center(width),
        "=" * width,
        f"Ticket : {ticket.get('ticket_no', '')}",
        f"Order  : {ticket.get('order_no', '')}",
        f"Source : {ticket.get('source_name', '')}",
        f"Type   : {ticket.get('order_type', '')}",
        f"Time   : {ticket.get('created_at', '')}",
        "-" * width,
    ]
    for item in ticket.get("items") or []:
        quantity = item.get("quantity", 0)
        qty = int(quantity) if float(quantity).is_integer() else quantity
        item_status = str(item.get("status") or "sent").lower()
        prefix = "" if item_status == "sent" else f"[{item_status.upper()}] "
        lines.append(f"{prefix}{qty} x {item.get('product_name') or item.get('display_name') or 'Item'}")
        if item.get("modifier_summary"):
            lines.append(f"  {item['modifier_summary']}")
        if item.get("note"):
            lines.append(f"  Note: {item['note']}")
    lines.append("-" * width)
    lines.append(f"Status : {str(ticket.get('status', '')).title()}")
    lines.append("=" * width)
    return lines


def mark_kitchen_ticket_printed(ticket_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("""
        UPDATE restaurant_kitchen_tickets
        SET printed = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (ticket_id,))
    conn.commit()
    conn.close()


def update_kitchen_ticket_status(ticket_id, status):
    allowed = {"sent", "preparing", "ready", "served", "cancelled"}
    status = str(status or "").strip().lower()
    if status not in allowed:
        raise ValueError(f"Unsupported kitchen ticket status: {status}")
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("SELECT order_id FROM restaurant_kitchen_tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    order_id = row[0] if row else None
    completed_sql = "CURRENT_TIMESTAMP" if status in {"served", "cancelled"} else "completed_at"
    cursor.execute(f"""
        UPDATE restaurant_kitchen_tickets
        SET status = ?,
            completed_at = {completed_sql},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, ticket_id))
    item_timestamp_sql = _kitchen_item_timestamp_assignments(status)
    cursor.execute("""
        UPDATE restaurant_kitchen_ticket_items
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
            {item_timestamp_sql}
        WHERE ticket_id = ?
    """.format(item_timestamp_sql=item_timestamp_sql), (status, ticket_id))
    _sync_order_item_kitchen_statuses(cursor, ticket_id)
    if order_id:
        _sync_order_kitchen_status(cursor, order_id)
    conn.commit()
    conn.close()


def update_kitchen_ticket_item_status(ticket_item_id, status):
    allowed = {"sent", "preparing", "ready", "served"}
    status = str(status or "").strip().lower()
    if status not in allowed:
        raise ValueError(f"Unsupported kitchen item status: {status}")

    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("""
        SELECT kti.ticket_id, kt.order_id
        FROM restaurant_kitchen_ticket_items kti
        JOIN restaurant_kitchen_tickets kt ON kt.id = kti.ticket_id
        WHERE kti.id = ?
    """, (ticket_item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Kitchen ticket item not found.")

    ticket_id, order_id = row
    timestamp_sql = _kitchen_item_timestamp_assignments(status)
    cursor.execute("""
        UPDATE restaurant_kitchen_ticket_items
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
            {timestamp_sql}
        WHERE id = ?
    """.format(timestamp_sql=timestamp_sql), (status, ticket_item_id))
    _sync_ticket_status_from_items(cursor, ticket_id)
    _sync_order_item_kitchen_statuses(cursor, ticket_id)
    if order_id:
        _sync_order_kitchen_status(cursor, order_id)
    conn.commit()
    conn.close()
    return order_id


def cancel_kitchen_ticket_item(ticket_item_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("""
        SELECT kti.ticket_id, kt.order_id, kti.order_item_id, kti.sort_order
        FROM restaurant_kitchen_ticket_items kti
        JOIN restaurant_kitchen_tickets kt ON kt.id = kti.ticket_id
        WHERE kti.id = ?
    """, (ticket_item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Kitchen ticket item not found.")
    ticket_id, order_id, order_item_id, sort_order = row

    cursor.execute("""
        UPDATE restaurant_kitchen_ticket_items
        SET status = 'cancelled',
            updated_at = CURRENT_TIMESTAMP,
            cancelled_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (ticket_item_id,))

    cursor.execute("SELECT cart_json FROM restaurant_orders WHERE id = ?", (order_id,))
    order_row = cursor.fetchone()
    cart = json.loads(order_row[0] or "[]") if order_row else []
    remove_index = _cart_index_for_order_item(cursor, order_item_id, sort_order, cart)
    if remove_index is not None and 0 <= remove_index < len(cart):
        cart.pop(remove_index)

    total_amount = sum(_safe_float(item.get("price"), 0) * _safe_float(item.get("qty"), 0) for item in cart)
    item_count = sum(int(_safe_float(item.get("qty"), 0)) for item in cart)
    cursor.execute("""
        UPDATE restaurant_orders
        SET cart_json = ?,
            total_amount = ?,
            item_count = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (json.dumps(cart, ensure_ascii=False), total_amount, item_count, order_id))
    _sync_order_items(cursor, order_id, cart)
    _sync_ticket_status_from_items(cursor, ticket_id)
    _sync_order_item_kitchen_statuses(cursor, ticket_id)
    _sync_order_kitchen_status(cursor, order_id)
    conn.commit()
    conn.close()
    return order_id


def close_order(order_id, status="settled", sale_result=None):
    sale_result = sale_result or {}
    conn = connect_db()
    cursor = conn.cursor()
    ensure_restaurant_schema(cursor)
    cursor.execute("""
        UPDATE restaurant_orders
        SET status = ?,
            settled_at = CASE WHEN ? = 'settled' THEN CURRENT_TIMESTAMP ELSE settled_at END,
            cancelled_at = CASE WHEN ? = 'cancelled' THEN CURRENT_TIMESTAMP ELSE cancelled_at END,
            sale_id = COALESCE(?, sale_id),
            invoice_no = COALESCE(?, invoice_no),
            settled_total = CASE WHEN ? = 'settled' THEN COALESCE(?, settled_total, total_amount, 0) ELSE settled_total END,
            payment_amount = CASE WHEN ? = 'settled' THEN COALESCE(?, payment_amount, 0) ELSE payment_amount END,
            change_amount = CASE WHEN ? = 'settled' THEN COALESCE(?, change_amount, 0) ELSE change_amount END,
            payment_type = CASE WHEN ? = 'settled' THEN COALESCE(?, payment_type) ELSE payment_type END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        status,
        status,
        status,
        sale_result.get("sale_id"),
        sale_result.get("invoice_no"),
        status,
        sale_result.get("grand_total"),
        status,
        sale_result.get("payment"),
        status,
        sale_result.get("change"),
        status,
        sale_result.get("payment_type"),
        order_id,
    ))
    conn.commit()
    conn.close()


def _close_empty_open_orders(cursor):
    cursor.execute("""
        UPDATE restaurant_orders
        SET status = 'cancelled',
            cancelled_at = COALESCE(cancelled_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'open'
          AND (
              COALESCE(item_count, 0) <= 0
              OR TRIM(COALESCE(cart_json, '[]')) IN ('', '[]')
          )
    """)


def _row_to_order(row):
    if not row:
        return None
    return {
        "id": row[0],
        "order_no": row[1],
        "table_id": row[2],
        "order_type": row[3],
        "status": row[4],
        "kitchen_status": row[5],
        "cart": json.loads(row[6] or "[]"),
        "customer_id": row[7],
        "customer_name": row[8] or "",
        "note": row[9] or "",
        "total_amount": float(row[10] or 0),
        "item_count": int(row[11] or 0),
    }


def _sync_order_items(cursor, order_id, cart):
    _ensure_cart_line_ids(cart)
    cursor.execute("""
        SELECT id, line_id
        FROM restaurant_order_items
        WHERE order_id = ? AND TRIM(COALESCE(line_id, '')) != ''
    """, (order_id,))
    existing_by_line_id = {row[1]: row[0] for row in cursor.fetchall()}
    active_order_item_ids = []

    for index, item in enumerate(cart or []):
        line_id = _cart_line_id(item)
        product_id = item.get("id")
        display_name = str(item.get("name") or "").strip() or "Item"
        product_name = str(item.get("base_name") or display_name).strip() or display_name
        quantity = _safe_float(item.get("qty"), 0)
        unit_price = _safe_float(item.get("price"), 0)
        base_price = _safe_float(item.get("original_price") or item.get("base_unit_price") or unit_price, unit_price)
        line_total = quantity * unit_price
        note = str(item.get("note") or item.get("kitchen_note") or "").strip()
        order_item_id = existing_by_line_id.get(line_id)
        if order_item_id:
            cursor.execute("""
                UPDATE restaurant_order_items
                SET product_id = ?,
                    product_name = ?,
                    display_name = ?,
                    quantity = ?,
                    unit_price = ?,
                    base_price = ?,
                    line_total = ?,
                    note = ?,
                    status = 'active',
                    sort_order = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                product_id,
                product_name,
                display_name,
                quantity,
                unit_price,
                base_price,
                line_total,
                note,
                index,
                order_item_id,
            ))
        else:
            cursor.execute("""
                INSERT INTO restaurant_order_items
                (order_id, product_id, product_name, display_name, quantity, unit_price,
                 base_price, line_total, note, line_id, status, kitchen_status, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 'draft', ?)
            """, (
                order_id,
                product_id,
                product_name,
                display_name,
                quantity,
                unit_price,
                base_price,
                line_total,
                note,
                line_id,
                index,
            ))
            order_item_id = cursor.lastrowid
        active_order_item_ids.append(order_item_id)
        cursor.execute("DELETE FROM restaurant_order_modifiers WHERE order_item_id = ?", (order_item_id,))
        for modifier in item.get("restaurant_modifiers") or []:
            modifier_name = str(modifier.get("name") or "").strip()
            if not modifier_name:
                continue
            cursor.execute("""
                INSERT INTO restaurant_order_modifiers
                (order_item_id, group_name, modifier_name, modifier_type, price_delta)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_item_id,
                str(modifier.get("group") or "Options").strip() or "Options",
                modifier_name,
                str(modifier.get("type") or "note").strip() or "note",
                _safe_float(modifier.get("price_delta"), 0),
            ))
    if active_order_item_ids:
        placeholders = ",".join("?" for _ in active_order_item_ids)
        cursor.execute(f"""
            UPDATE restaurant_order_items
            SET status = 'removed',
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
              AND id NOT IN ({placeholders})
              AND status != 'removed'
        """, (order_id, *active_order_item_ids))
    else:
        cursor.execute("""
            UPDATE restaurant_order_items
            SET status = 'removed',
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ? AND status != 'removed'
        """, (order_id,))


def _ensure_cart_line_ids(cart):
    seen = set()
    for item in cart or []:
        line_id = str(item.get("restaurant_line_id") or item.get("line_id") or "").strip()
        if not line_id or line_id in seen:
            line_id = uuid.uuid4().hex
        item["restaurant_line_id"] = line_id
        seen.add(line_id)


def _cart_line_id(item):
    line_id = str(item.get("restaurant_line_id") or item.get("line_id") or "").strip()
    if not line_id:
        line_id = uuid.uuid4().hex
        item["restaurant_line_id"] = line_id
    return line_id


def _safe_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _create_kitchen_ticket(cursor, order_id):
    all_items = _load_order_items_for_ticket(cursor, order_id)
    items = _items_for_new_kitchen_ticket(cursor, order_id, all_items)
    if not items:
        return None

    ticket_signature = _kitchen_ticket_signature(items)
    cursor.execute("""
        SELECT id, status
        FROM restaurant_kitchen_tickets
        WHERE order_id = ? AND ticket_signature = ?
        ORDER BY id DESC
        LIMIT 1
    """, (order_id, ticket_signature))
    existing = cursor.fetchone()
    if existing:
        existing_id, existing_status = existing
        if str(existing_status or "").lower() == "cancelled":
            cursor.execute("""
                UPDATE restaurant_kitchen_tickets
                SET status = 'sent',
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (existing_id,))
            cursor.execute("""
                UPDATE restaurant_kitchen_ticket_items
                SET status = 'sent',
                    updated_at = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (existing_id,))
        return existing_id

    ticket_no = datetime.now().strftime("KT%Y%m%d%H%M%S%f")
    cursor.execute("""
        INSERT INTO restaurant_kitchen_tickets (ticket_no, order_id, ticket_signature)
        VALUES (?, ?, ?)
    """, (ticket_no, order_id, ticket_signature))
    ticket_id = cursor.lastrowid

    for item in items:
        cursor.execute("""
            INSERT INTO restaurant_kitchen_ticket_items
            (ticket_id, order_item_id, product_id, product_name, display_name,
             modifier_summary, quantity, note, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            item["id"],
            item["product_id"],
            item["product_name"],
            item["display_name"],
            item["modifier_summary"],
            item["quantity"],
            item["note"],
            item["sort_order"],
        ))
    return ticket_id


def _sync_order_kitchen_status(cursor, order_id):
    cursor.execute("""
        SELECT status
        FROM restaurant_kitchen_tickets
        WHERE order_id = ?
          AND status NOT IN ('served', 'cancelled')
    """, (order_id,))
    active_statuses = {str(row[0] or "").lower() for row in cursor.fetchall()}
    if not active_statuses:
        kitchen_status = "served"
    elif active_statuses <= {"ready"}:
        kitchen_status = "ready"
    elif "ready" in active_statuses or "preparing" in active_statuses:
        kitchen_status = "preparing"
    else:
        kitchen_status = "sent"
    cursor.execute("""
        UPDATE restaurant_orders
        SET kitchen_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (kitchen_status, order_id))


def _kitchen_item_timestamp_assignments(status):
    if status == "preparing":
        return ", preparing_at = COALESCE(preparing_at, CURRENT_TIMESTAMP)"
    if status == "ready":
        return ", ready_at = COALESCE(ready_at, CURRENT_TIMESTAMP)"
    if status == "served":
        return ", served_at = COALESCE(served_at, CURRENT_TIMESTAMP)"
    return ""


def _sync_order_item_kitchen_statuses(cursor, ticket_id):
    cursor.execute("""
        SELECT DISTINCT order_item_id
        FROM restaurant_kitchen_ticket_items
        WHERE ticket_id = ? AND order_item_id IS NOT NULL
    """, (ticket_id,))
    order_item_ids = [row[0] for row in cursor.fetchall()]
    for order_item_id in order_item_ids:
        cursor.execute("""
            SELECT status, COALESCE(SUM(quantity), 0)
            FROM restaurant_kitchen_ticket_items
            WHERE order_item_id = ?
              AND status != 'cancelled'
            GROUP BY status
        """, (order_item_id,))
        quantities_by_status = {str(row[0] or "").lower(): _safe_float(row[1], 0) for row in cursor.fetchall()}
        total_sent = sum(quantities_by_status.values())
        if not quantities_by_status:
            kitchen_status = "draft"
        elif set(quantities_by_status) <= {"served"}:
            kitchen_status = "served"
        elif set(quantities_by_status) <= {"ready", "served"}:
            kitchen_status = "ready"
        elif "ready" in quantities_by_status or "preparing" in quantities_by_status:
            kitchen_status = "preparing"
        else:
            kitchen_status = "sent"

        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM restaurant_kitchen_ticket_items
            WHERE order_item_id = ?
              AND status = 'cancelled'
        """, (order_item_id,))
        cancelled_quantity = _safe_float(cursor.fetchone()[0], 0)
        cursor.execute("""
            UPDATE restaurant_order_items
            SET kitchen_status = ?,
                sent_quantity = ?,
                cancelled_quantity = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (kitchen_status, total_sent, cancelled_quantity, order_item_id))


def _sync_ticket_status_from_items(cursor, ticket_id):
    cursor.execute("""
        SELECT status
        FROM restaurant_kitchen_ticket_items
        WHERE ticket_id = ?
    """, (ticket_id,))
    statuses = {str(row[0] or "").lower() for row in cursor.fetchall()}
    if not statuses:
        return
    active_statuses = statuses - {"cancelled"}
    if not active_statuses:
        ticket_status = "cancelled"
    elif active_statuses <= {"served"}:
        ticket_status = "served"
    elif active_statuses <= {"ready", "served"}:
        ticket_status = "ready"
    elif "ready" in active_statuses or "preparing" in active_statuses:
        ticket_status = "preparing"
    else:
        ticket_status = "sent"
    completed_sql = "CURRENT_TIMESTAMP" if ticket_status in {"served", "cancelled"} else "completed_at"
    cursor.execute(f"""
        UPDATE restaurant_kitchen_tickets
        SET status = ?,
            completed_at = {completed_sql},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (ticket_status, ticket_id))


def _load_order_items_for_ticket(cursor, order_id):
    cursor.execute("""
        SELECT roi.id, roi.product_id, roi.product_name, roi.display_name,
               roi.quantity, roi.note, roi.sort_order
        FROM restaurant_order_items roi
        LEFT JOIN products p ON p.id = roi.product_id
        WHERE roi.order_id = ?
          AND COALESCE(roi.status, 'active') = 'active'
          AND LOWER(COALESCE(p.sold_by, '')) = 'restaurant'
        ORDER BY roi.sort_order, roi.id
    """, (order_id,))
    rows = cursor.fetchall()
    items = []
    for row in rows:
        order_item_id = row[0]
        cursor.execute("""
            SELECT group_name, modifier_name, modifier_type, price_delta
            FROM restaurant_order_modifiers
            WHERE order_item_id = ?
            ORDER BY id
        """, (order_item_id,))
        modifiers = [
            {
                "group": mod[0] or "Options",
                "name": mod[1] or "",
                "type": mod[2] or "note",
                "price_delta": _safe_float(mod[3], 0),
            }
            for mod in cursor.fetchall()
        ]
        items.append({
            "id": order_item_id,
            "product_id": row[1],
            "product_name": row[2] or "",
            "display_name": row[3] or "",
            "quantity": _safe_float(row[4], 0),
            "note": row[5] or "",
            "sort_order": int(row[6] or 0),
            "modifiers": modifiers,
            "modifier_summary": ", ".join(mod["name"] for mod in modifiers if mod["name"]),
        })
    return items


def _items_for_new_kitchen_ticket(cursor, order_id, items):
    sent_quantities = _load_sent_kitchen_quantities(cursor, order_id)
    new_items = []
    for item in items or []:
        key = _kitchen_item_key(item)
        covered_quantity = sent_quantities.get(key, 0)
        item_quantity = _safe_float(item.get("quantity"), 0)
        if covered_quantity >= item_quantity:
            sent_quantities[key] = covered_quantity - item_quantity
            continue

        remaining_quantity = item_quantity - covered_quantity
        sent_quantities[key] = 0
        new_item = dict(item)
        new_item["quantity"] = remaining_quantity
        new_item["sent_before"] = covered_quantity
        new_items.append(new_item)
    return new_items


def _load_sent_kitchen_quantities(cursor, order_id):
    cursor.execute("""
        SELECT
            kti.order_item_id,
            COALESCE(SUM(kti.quantity), 0)
        FROM restaurant_kitchen_ticket_items kti
        JOIN restaurant_kitchen_tickets kt ON kt.id = kti.ticket_id
        WHERE kt.order_id = ?
          AND kti.order_item_id IS NOT NULL
          AND kt.status != 'cancelled'
          AND kti.status != 'cancelled'
        GROUP BY kti.order_item_id
    """, (order_id,))
    quantities = {}
    for row in cursor.fetchall():
        quantities[str(row[0])] = _safe_float(row[1], 0)
    return quantities


def _load_ticket_items(cursor, ticket_id):
    cursor.execute("""
        SELECT id, order_item_id, product_name, display_name, modifier_summary, quantity, note, status, sort_order
        FROM restaurant_kitchen_ticket_items
        WHERE ticket_id = ?
        ORDER BY sort_order, id
    """, (ticket_id,))
    return [
        {
            "id": row[0],
            "order_item_id": row[1],
            "product_name": row[2] or "",
            "display_name": row[3] or "",
            "modifier_summary": row[4] or "",
            "quantity": _safe_float(row[5], 0),
            "note": row[6] or "",
            "status": row[7] or "sent",
            "sort_order": int(row[8] or 0),
        }
        for row in cursor.fetchall()
    ]


def _cart_index_for_order_item(cursor, order_item_id, sort_order, cart):
    if order_item_id:
        cursor.execute("""
            SELECT product_id, display_name, sort_order, line_id
            FROM restaurant_order_items
            WHERE id = ?
        """, (order_item_id,))
        row = cursor.fetchone()
        if row:
            product_id, display_name, item_sort, line_id = row
            for index, item in enumerate(cart):
                same_line = str(item.get("restaurant_line_id") or item.get("line_id") or "") == str(line_id or "")
                same_product = item.get("id") == product_id
                same_name = str(item.get("name") or "") == str(display_name or "")
                same_sort = index == int(item_sort or 0)
                if same_line or same_sort or (same_product and same_name):
                    return index
    if sort_order is not None:
        return int(sort_order)
    return None


def _kitchen_ticket_signature(items):
    payload = []
    for item in items:
        payload.append({
            "order_item_id": item["id"],
            "product_id": item["product_id"],
            "display_name": item["display_name"],
            "quantity": item["quantity"],
            "note": item["note"],
            "modifiers": item["modifiers"],
            "sort_order": item["sort_order"],
            "sent_before": item.get("sent_before", 0),
        })
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _kitchen_item_key(item):
    if item.get("id"):
        return str(item.get("id"))
    if item.get("order_item_id"):
        return str(item.get("order_item_id"))
    return (
        str(item.get("product_id") or ""),
        str(item.get("display_name") or ""),
        str(item.get("modifier_summary") or ""),
        str(item.get("note") or ""),
    )
