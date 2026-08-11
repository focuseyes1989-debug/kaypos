"""Run a live PostgreSQL smoke test for the Restaurant schema.

Usage:
    set ZAY_POS_DB_BACKEND=postgres
    set ZAY_POS_DATABASE_URL=postgresql://user:pass@localhost:5432/zay_pos
    python scripts/postgres_restaurant_smoke.py

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


def main():
    if not _configure_postgres_env():
        return 0

    from models.database import connect_db, safe_initialize_postgres_app_database
    from utils.restaurant_service import (
        close_order,
        get_kitchen_ticket,
        get_restaurant_database_audit,
        send_to_kitchen,
        update_kitchen_ticket_item_status,
        upsert_order,
    )

    marker = f"__pg_restaurant_smoke_{int(time.time() * 1000)}"
    order_id = None
    product_id = None
    sale_id = None

    if not safe_initialize_postgres_app_database():
        raise RuntimeError("PostgreSQL schema initialization failed.")

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (name, category, price, cost, stock, sold_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (marker, "PostgreSQL Smoke", 1500, 700, 99, "Restaurant"))
        product_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    try:
        cart = [{
            "id": product_id,
            "name": marker,
            "base_name": marker,
            "qty": 1,
            "price": 1500,
            "original_price": 1500,
            "restaurant_modifiers": [{"group": "Taste", "name": "less spicy", "type": "note"}],
            "kitchen_note": "no onion",
        }]
        order_id = upsert_order(
            None,
            None,
            "Takeaway",
            cart,
            customer_name="PostgreSQL Smoke",
            total_amount=1500,
        )
        assert cart[0].get("restaurant_line_id"), cart

        ticket_id = send_to_kitchen(order_id)
        assert ticket_id, "Kitchen ticket was not created."
        ticket = get_kitchen_ticket(ticket_id)
        assert ticket and len(ticket["items"]) == 1, ticket

        item_id = ticket["items"][0]["id"]
        update_kitchen_ticket_item_status(item_id, "ready")
        update_kitchen_ticket_item_status(item_id, "served")

        conn = connect_db()
        cursor = conn.cursor()
        try:
            invoice_no = f"PGSMOKE{int(time.time())}"
            cursor.execute("""
                INSERT INTO sales (invoice_no, total, payment, change_amount, status, payment_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_no, 1500, 2000, 500, "completed", "Cash"))
            sale_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        close_order(order_id, "settled", {
            "sale_id": sale_id,
            "invoice_no": invoice_no,
            "grand_total": 1500,
            "payment": 2000,
            "change": 500,
            "payment_type": "Cash",
        })

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT status, sale_id, invoice_no, settled_total, payment_amount, change_amount, payment_type
                FROM restaurant_orders
                WHERE id = ?
            """, (order_id,))
            row = cursor.fetchone()
        finally:
            conn.close()

        assert row, "Settled order was not found."
        assert row[0] == "settled", row
        assert row[1] == sale_id and row[2] == invoice_no, row
        assert float(row[3] or 0) == 1500 and float(row[4] or 0) == 2000, row
        assert float(row[5] or 0) == 500 and row[6] == "Cash", row

        report = get_restaurant_database_audit()
        assert not report["missing_columns"], report
        print("OK: PostgreSQL Restaurant smoke passed.")
        print({"order_id": order_id, "ticket_id": ticket_id, "sale_id": sale_id})
        return 0
    finally:
        conn = connect_db()
        cursor = conn.cursor()
        try:
            if order_id:
                cursor.execute("DELETE FROM restaurant_orders WHERE id = ?", (order_id,))
            if sale_id:
                cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
            if product_id:
                cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
