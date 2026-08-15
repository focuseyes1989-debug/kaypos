"""Stock audit and reconciliation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.database.connection import DBContext


def _location_stock_sum_sql() -> str:
    return "COALESCE(SUM(COALESCE(pl.quantity, 0)), 0)"


def find_master_location_mismatches() -> List[Dict[str, Any]]:
    """Return products where products.stock differs from product_locations sum."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id,
                p.name,
                COALESCE(p.stock, 0) AS product_stock,
                COALESCE(SUM(COALESCE(pl.quantity, 0)), 0) AS location_stock,
                COALESCE(p.stock, 0) - COALESCE(SUM(COALESCE(pl.quantity, 0)), 0) AS diff
            FROM products p
            LEFT JOIN product_locations pl ON pl.product_id = p.id
            WHERE LOWER(COALESCE(p.sold_by, 'each')) NOT IN ('service', 'services')
            GROUP BY p.id, p.name, p.stock
            HAVING COALESCE(p.stock, 0) - COALESCE(SUM(COALESCE(pl.quantity, 0)), 0) != 0
            ORDER BY ABS(COALESCE(p.stock, 0) - COALESCE(SUM(COALESCE(pl.quantity, 0)), 0)) DESC, p.name
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


def clamp_location_stock_to_master(
    cursor,
    product_id: Optional[int] = None,
    created_by: str = "System",
) -> List[Dict[str, Any]]:
    """Trim product_locations that exceed products.stock.

    products.stock is the inventory screen source of truth. If stale location rows
    exceed it, cashier grids can see phantom stock unless the excess is removed.
    """
    where = ["LOWER(COALESCE(p.sold_by, 'each')) NOT IN ('service', 'services')"]
    params: List[Any] = []
    if product_id is not None:
        where.append("p.id = ?")
        params.append(int(product_id))

    cursor.execute(f"""
        SELECT
            p.id,
            p.name,
            COALESCE(p.stock, 0) AS product_stock,
            {_location_stock_sum_sql()} AS location_stock
        FROM products p
        JOIN product_locations pl ON pl.product_id = p.id
        WHERE {" AND ".join(where)}
        GROUP BY p.id, p.name, p.stock
        HAVING {_location_stock_sum_sql()} > COALESCE(p.stock, 0)
        ORDER BY p.name
    """, params)
    mismatches = cursor.fetchall()
    fixed: List[Dict[str, Any]] = []

    for pid, name, product_stock, location_stock in mismatches:
        pid = int(pid)
        target_stock = max(0, int(product_stock or 0))
        current_location_stock = max(0, int(location_stock or 0))
        excess = current_location_stock - target_stock
        if excess <= 0:
            continue

        cursor.execute("""
            SELECT id, COALESCE(quantity, 0)
            FROM product_locations
            WHERE product_id = ? AND COALESCE(quantity, 0) > 0
            ORDER BY
                CASE WHEN expire_date IS NULL OR expire_date = '' THEN 1 ELSE 0 END DESC,
                expire_date DESC,
                last_updated DESC,
                id DESC
        """, (pid,))
        for location_id, quantity in cursor.fetchall():
            if excess <= 0:
                break
            quantity = int(quantity or 0)
            take = min(quantity, excess)
            if take >= quantity:
                cursor.execute("DELETE FROM product_locations WHERE id = ?", (location_id,))
            else:
                cursor.execute("""
                    UPDATE product_locations
                    SET quantity = quantity - ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (take, location_id))
            excess -= take

        removed = current_location_stock - target_stock - max(0, excess)
        cursor.execute("""
            INSERT INTO stock_movements
                (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes)
            VALUES (?, 'adjustment', ?, ?, ?, 'Location Stock Clamp', 'AUTO_CLAMP_LOCATIONS', ?, ?)
        """, (
            pid,
            removed,
            current_location_stock,
            target_stock,
            created_by,
            "Removed stale product_locations quantity above products.stock",
        ))
        fixed.append({
            "product_id": pid,
            "name": name,
            "product_stock": target_stock,
            "old_location_stock": current_location_stock,
            "new_location_stock": target_stock,
            "removed": removed,
        })

    return fixed


def clamp_all_location_stock_to_master(created_by: str = "System") -> List[Dict[str, Any]]:
    """Clamp stale location stock for all products and commit the cleanup."""
    with DBContext() as conn:
        cursor = conn.cursor()
        fixed = clamp_location_stock_to_master(cursor, created_by=created_by)
        conn.commit()
        return fixed


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
