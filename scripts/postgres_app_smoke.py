"""Run a live PostgreSQL smoke test for the app-wide POS schema.

Usage:
    set ZAY_POS_DB_BACKEND=postgres
    set ZAY_POS_DATABASE_URL=postgresql://user:pass@localhost:5432/zay_pos
    python scripts/postgres_app_smoke.py

The script exits cleanly without doing anything when no PostgreSQL URL is set.
"""

import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.env_loader import load_project_env


def _configure_postgres_env():
    load_project_env()
    os.environ["ZAY_POS_DB_BACKEND"] = "postgres"
    if not (os.getenv("ZAY_POS_DATABASE_URL") or os.getenv("DATABASE_URL")):
        print("SKIP: ZAY_POS_DATABASE_URL/DATABASE_URL is not configured.")
        return False
    return True


def _insert(cursor, sql, params):
    cursor.execute(sql, params)
    if not cursor.lastrowid:
        raise RuntimeError(f"Insert did not return an id: {sql.splitlines()[0].strip()}")
    return cursor.lastrowid


def main():
    if not _configure_postgres_env():
        return 0

    from models.database import connect_db, safe_initialize_database

    marker = f"__pg_app_smoke_{int(time.time() * 1000)}"
    ids = {}

    if not safe_initialize_database():
        raise RuntimeError("PostgreSQL app schema initialization failed.")

    conn = connect_db()
    cursor = conn.cursor()
    try:
        ids["category"] = _insert(
            cursor,
            "INSERT INTO categories (name, slug) VALUES (?, ?)",
            (marker, marker),
        )
        ids["supplier"] = _insert(
            cursor,
            "INSERT INTO suppliers (name, contact_person, status) VALUES (?, ?, ?)",
            (marker, "Smoke", "Active"),
        )
        ids["product"] = _insert(
            cursor,
            """
            INSERT INTO products (name, category, price, cost, stock, supplier_id, category_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (marker, marker, 1500, 700, 25, ids["supplier"], ids["category"]),
        )
        ids["customer"] = _insert(
            cursor,
            "INSERT INTO customers (name, phone, points) VALUES (?, ?, ?)",
            (marker, "099999999", 0),
        )
        ids["sale"] = _insert(
            cursor,
            """
            INSERT INTO sales (invoice_no, customer_id, total, payment, change_amount, status, payment_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (marker, ids["customer"], 1500, 2000, 500, "completed", "Cash"),
        )
        ids["sale_item"] = _insert(
            cursor,
            """
            INSERT INTO sale_items (sale_id, product_id, product_name, qty, price, total, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ids["sale"], ids["product"], marker, 1, 1500, 1500, 700),
        )
        ids["stock_movement"] = _insert(
            cursor,
            """
            INSERT INTO stock_movements (product_id, type, quantity, old_stock, new_stock, reason, supplier_id, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ids["product"], "sale", 1, 25, 24, "PostgreSQL smoke", ids["supplier"], ids["customer"]),
        )
        ids["purchase_order"] = _insert(
            cursor,
            """
            INSERT INTO purchase_orders (po_no, supplier_id, order_date, total_amount, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (marker, ids["supplier"], "2026-08-11", 700, "received"),
        )
        ids["purchase_order_item"] = _insert(
            cursor,
            """
            INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_price, total)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ids["purchase_order"], ids["product"], 1, 700, 700),
        )
        ids["expense"] = _insert(
            cursor,
            """
            INSERT INTO expenses (expense_no, category, amount, expense_date, payment_method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (marker, "Other", 100, "2026-08-11", "Cash"),
        )
        ids["credit_sale"] = _insert(
            cursor,
            """
            INSERT INTO credit_sales (invoice_no, customer_id, total_amount, paid_amount, balance_amount, sale_date, sale_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"{marker}_credit", ids["customer"], 1500, 500, 1000, "2026-08-11", ids["sale"]),
        )
        ids["credit_payment"] = _insert(
            cursor,
            """
            INSERT INTO credit_payments (credit_sale_id, customer_id, amount, payment_date, payment_method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ids["credit_sale"], ids["customer"], 500, "2026-08-11", "Cash"),
        )
        ids["held_sale"] = _insert(
            cursor,
            """
            INSERT INTO held_sales (hold_no, cart_json, customer_id, customer_name, total_amount, item_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (marker, "[]", ids["customer"], marker, 0, 0),
        )
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM sales WHERE invoice_no = ?", (marker,))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        assert cursor.fetchone()[0] >= 40
        print("OK: PostgreSQL app-wide smoke passed.")
        print(ids)
        return 0
    finally:
        for table, key in (
            ("held_sales", "held_sale"),
            ("credit_payments", "credit_payment"),
            ("credit_sales", "credit_sale"),
            ("expenses", "expense"),
            ("purchase_order_items", "purchase_order_item"),
            ("purchase_orders", "purchase_order"),
            ("stock_movements", "stock_movement"),
            ("sale_items", "sale_item"),
            ("sales", "sale"),
            ("customers", "customer"),
            ("products", "product"),
            ("suppliers", "supplier"),
            ("categories", "category"),
        ):
            if key in ids:
                cursor.execute(f"DELETE FROM {table} WHERE id = ?", (ids[key],))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
