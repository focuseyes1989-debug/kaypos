"""Wholesale price tier helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def ensure_wholesale_schema(cursor) -> None:
    """Create wholesale tier tables/columns when missing."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_price_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            min_qty INTEGER NOT NULL DEFAULT 1,
            unit_label TEXT,
            unit_multiplier INTEGER DEFAULT 1,
            barcode TEXT,
            unit_price REAL NOT NULL DEFAULT 0,
            note TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("PRAGMA table_info(product_price_tiers)")
    columns = {row[1] for row in cursor.fetchall()}
    for column, definition in {
        "unit_label": "TEXT",
        "unit_multiplier": "INTEGER DEFAULT 1",
        "barcode": "TEXT",
        "unit_price": "REAL NOT NULL DEFAULT 0",
        "note": "TEXT",
        "active": "INTEGER DEFAULT 1",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }.items():
        if column not in columns:
            cursor.execute(f"ALTER TABLE product_price_tiers ADD COLUMN {column} {definition}")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_price_tiers_product_qty
        ON product_price_tiers(product_id, min_qty, active)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_price_tiers_barcode
        ON product_price_tiers(barcode)
    """)


def ensure_wholesale_sale_item_columns(cursor) -> None:
    """Add optional receipt/audit columns for wholesale sale lines."""
    cursor.execute("PRAGMA table_info(sale_items)")
    columns = {row[1] for row in cursor.fetchall()}
    for column, definition in {
        "wholesale_regular_price": "REAL DEFAULT 0",
        "wholesale_savings": "REAL DEFAULT 0",
        "wholesale_tier_min_qty": "INTEGER",
        "wholesale_unit_label": "TEXT",
    }.items():
        if column not in columns:
            cursor.execute(f"ALTER TABLE sale_items ADD COLUMN {column} {definition}")


def get_price_tiers(cursor, product_id: int) -> List[Dict[str, Any]]:
    ensure_wholesale_schema(cursor)
    cursor.execute("""
        SELECT id, min_qty, COALESCE(unit_label, ''), COALESCE(unit_multiplier, 1),
               COALESCE(barcode, ''), unit_price, COALESCE(note, ''), COALESCE(active, 1)
        FROM product_price_tiers
        WHERE product_id = ?
        ORDER BY min_qty ASC, unit_price ASC
    """, (product_id,))
    tiers = []
    for row in cursor.fetchall():
        tiers.append({
            "id": row[0],
            "min_qty": int(row[1] or 1),
            "unit_label": row[2] or "",
            "unit_multiplier": int(row[3] or 1),
            "barcode": row[4] or "",
            "unit_price": float(row[5] or 0),
            "note": row[6] or "",
            "active": int(row[7] or 0),
        })
    return tiers


def get_best_price_tier(cursor, product_id: int, qty: int) -> Optional[Dict[str, Any]]:
    ensure_wholesale_schema(cursor)
    cursor.execute("""
        SELECT id, min_qty, COALESCE(unit_label, ''), COALESCE(unit_multiplier, 1),
               COALESCE(barcode, ''), unit_price, COALESCE(note, '')
        FROM product_price_tiers
        WHERE product_id = ?
          AND COALESCE(active, 1) = 1
          AND min_qty <= ?
          AND unit_price > 0
        ORDER BY min_qty DESC, unit_price ASC, id DESC
        LIMIT 1
    """, (product_id, max(1, int(qty or 1))))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "min_qty": int(row[1] or 1),
        "unit_label": row[2] or "",
        "unit_multiplier": int(row[3] or 1),
        "barcode": row[4] or "",
        "unit_price": float(row[5] or 0),
        "note": row[6] or "",
    }


def get_price_tier_by_barcode(cursor, barcode: str) -> Optional[Dict[str, Any]]:
    ensure_wholesale_schema(cursor)
    cursor.execute("""
        SELECT id, product_id, min_qty, COALESCE(unit_label, ''), COALESCE(unit_multiplier, 1),
               COALESCE(barcode, ''), unit_price, COALESCE(note, '')
        FROM product_price_tiers
        WHERE COALESCE(active, 1) = 1
          AND TRIM(COALESCE(barcode, '')) = ?
          AND unit_price > 0
        LIMIT 1
    """, (str(barcode or "").strip(),))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "product_id": int(row[1] or 0),
        "min_qty": int(row[2] or 1),
        "unit_label": row[3] or "",
        "unit_multiplier": int(row[4] or 1),
        "barcode": row[5] or "",
        "unit_price": float(row[6] or 0),
        "note": row[7] or "",
    }


def save_price_tiers(cursor, product_id: int, tiers: List[Dict[str, Any]]) -> None:
    ensure_wholesale_schema(cursor)
    cursor.execute("DELETE FROM product_price_tiers WHERE product_id = ?", (product_id,))
    for tier in tiers:
        min_qty = max(1, int(tier.get("min_qty") or 1))
        unit_price = max(0.0, float(tier.get("unit_price") or 0))
        if unit_price <= 0:
            continue
        cursor.execute("""
            INSERT INTO product_price_tiers
            (product_id, min_qty, unit_label, unit_multiplier, barcode, unit_price, note, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            min_qty,
            str(tier.get("unit_label") or "").strip(),
            max(1, int(tier.get("unit_multiplier") or min_qty)),
            str(tier.get("barcode") or "").strip(),
            unit_price,
            str(tier.get("note") or "").strip(),
            int(tier.get("active", 1) or 0),
        ))
