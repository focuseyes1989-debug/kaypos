"""Helpers for held/suspended POS sales."""

import json
from datetime import datetime

from models.database import connect_db


def ensure_held_sales_schema(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS held_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hold_no TEXT UNIQUE,
            cart_json TEXT NOT NULL,
            customer_id INTEGER,
            customer_name TEXT,
            payment_type TEXT,
            note TEXT,
            total_amount REAL DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_held_sales_created_at ON held_sales(created_at)")


def create_held_sale(cart, customer_id=None, customer_name="", payment_type="Cash", note="", total_amount=0):
    hold_no = datetime.now().strftime("HOLD%Y%m%d%H%M%S%f")
    item_count = sum(int(item.get("qty", 0) or 0) for item in cart)
    payload = json.dumps(cart, ensure_ascii=False)
    conn = connect_db()
    cursor = conn.cursor()
    ensure_held_sales_schema(cursor)
    cursor.execute("""
        INSERT INTO held_sales
        (hold_no, cart_json, customer_id, customer_name, payment_type, note, total_amount, item_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (hold_no, payload, customer_id, customer_name, payment_type, note, float(total_amount or 0), item_count))
    held_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return held_id, hold_no


def list_held_sales():
    conn = connect_db()
    cursor = conn.cursor()
    ensure_held_sales_schema(cursor)
    cursor.execute("""
        SELECT id, hold_no, customer_name, item_count, total_amount, note, created_at
        FROM held_sales
        ORDER BY datetime(created_at) DESC, id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_held_sale(held_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_held_sales_schema(cursor)
    cursor.execute("""
        SELECT id, hold_no, cart_json, customer_id, customer_name, payment_type, note, total_amount
        FROM held_sales
        WHERE id = ?
    """, (held_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    cart = json.loads(row[2] or "[]")
    return {
        "id": row[0],
        "hold_no": row[1],
        "cart": cart,
        "customer_id": row[3],
        "customer_name": row[4],
        "payment_type": row[5] or "Cash",
        "note": row[6] or "",
        "total_amount": float(row[7] or 0),
    }


def delete_held_sale(held_id):
    conn = connect_db()
    cursor = conn.cursor()
    ensure_held_sales_schema(cursor)
    cursor.execute("DELETE FROM held_sales WHERE id = ?", (held_id,))
    conn.commit()
    conn.close()
