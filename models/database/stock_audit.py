"""Stock audit and reconciliation helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from models.database.connection import DBContext


def find_master_location_mismatches() -> List[Dict[str, Any]]:
    """Return products where products.stock differs from product_locations sum."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id,
                p.name,
                COALESCE(p.stock, 0) AS product_stock,
                COALESCE(SUM(pl.quantity), 0) AS location_stock,
                COALESCE(p.stock, 0) - COALESCE(SUM(pl.quantity), 0) AS diff
            FROM products p
            LEFT JOIN product_locations pl ON pl.product_id = p.id
            WHERE COALESCE(p.sold_by, 'Each') != 'Service'
            GROUP BY p.id
            HAVING diff != 0
            ORDER BY ABS(diff) DESC, p.name
        """)
        return [
            {
                "product_id": row[0],
                "name": row[1],
                "product_stock": int(row[2] or 0),
                "location_stock": int(row[3] or 0),
                "diff": int(row[4] or 0),
            }
            for row in cursor.fetchall()
        ]


def reconcile_master_stock_from_locations(created_by: str = "System") -> List[Dict[str, Any]]:
    """Set products.stock to the sum of active product_locations rows and log changes."""
    with DBContext() as conn:
        cursor = conn.cursor()
        mismatches = find_master_location_mismatches()
        for row in mismatches:
            product_id = row["product_id"]
            old_stock = row["product_stock"]
            new_stock = row["location_stock"]
            cursor.execute("""
                UPDATE products
                SET stock = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_stock, product_id))
            cursor.execute("""
                INSERT INTO stock_movements
                    (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes)
                VALUES (?, 'adjustment', ?, ?, ?, 'Stock Reconciliation', 'AUTO_RECONCILE', ?, ?)
            """, (
                product_id,
                abs(new_stock - old_stock),
                old_stock,
                new_stock,
                created_by,
                "Reconciled products.stock from product_locations total",
            ))
        conn.commit()
        return mismatches
