"""Server-side cashier operations.

The browser cashier never opens SQLite directly. These helpers keep all writes
inside the server process and use explicit transactions for sale checkout.
"""

from __future__ import annotations

import hashlib
import os
import ctypes
import mimetypes
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from loguru import logger

from models.database import connect_db
from utils.db_compat import is_postgres_backend, quote_identifier, table_columns
from utils.image_optimizer import ImageOptimizer
from utils.paths import app_relative_path, get_product_images_dir
from utils.product_image_store import cached_product_image_path
from utils.wholesale_pricing import ensure_wholesale_schema, get_best_price_tier


_TABLE_COLUMNS_CACHE: Dict[str, set[str]] = {}


def _dict_from_row(cursor, row) -> Dict[str, Any]:
    return {description[0]: row[index] for index, description in enumerate(cursor.description)}


def _table_columns(cursor, table_name: str) -> set[str]:
    if table_name in _TABLE_COLUMNS_CACHE:
        return _TABLE_COLUMNS_CACHE[table_name]
    columns = table_columns(cursor, table_name)
    _TABLE_COLUMNS_CACHE[table_name] = columns
    return columns


def _execute_dynamic_insert(cursor, table_name: str, values: Dict[str, Any]) -> int:
    columns = _table_columns(cursor, table_name)
    filtered = {key: value for key, value in values.items() if key in columns}
    if not filtered:
        raise ValueError(f"No matching columns for {table_name}")

    names = list(filtered.keys())
    placeholders = ", ".join("?" for _ in names)
    cursor.execute(
        f"INSERT INTO {table_name} ({', '.join(names)}) VALUES ({placeholders})",
        [filtered[name] for name in names],
    )
    return int(cursor.lastrowid)


def _sync_postgres_id_sequences(cursor, table_names: Iterable[str]) -> None:
    """Keep SERIAL sequences ahead of restored/imported rows."""
    if not is_postgres_backend():
        return
    for table_name in table_names:
        safe_table = quote_identifier(table_name)
        try:
            cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", (safe_table,))
            row = cursor.fetchone()
            sequence_name = row[0] if row else None
            if not sequence_name:
                continue
            cursor.execute(
                f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {safe_table}), 0) + 1, false)",
                (sequence_name,),
            )
        except Exception as exc:
            logger.debug(f"Could not sync PostgreSQL sequence for {table_name}: {exc}")


def _try_dynamic_insert(cursor, table_name: str, values: Dict[str, Any]) -> Optional[int]:
    try:
        return _execute_dynamic_insert(cursor, table_name, values)
    except Exception as exc:
        logger.debug(f"Skipped optional insert into {table_name}: {exc}")
        return None


def _setting(cursor, key: str, default: str = "") -> str:
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return str(row[0]) if row and row[0] is not None else default


def _active_product_discount(cursor, product_id: int) -> Dict[str, Any]:
    try:
        cursor.execute(
            """
            SELECT discount_percent, COALESCE(discount_type, 'percentage'), COALESCE(manual_price, 0)
            FROM product_discounts
            WHERE product_id = ?
              AND active = 1
              AND date(start_date) <= date('now')
              AND date(end_date) >= date('now')
            ORDER BY
                CASE
                    WHEN COALESCE(discount_type, 'percentage') = 'manual_price' THEN 999999999 - COALESCE(manual_price, 0)
                    ELSE discount_percent
                END DESC,
                end_date ASC
            LIMIT 1
            """,
            (product_id,),
        )
        row = cursor.fetchone()
    except Exception:
        row = None

    if not row:
        return {"source": "", "percent": 0.0, "type": "percentage", "manual_price": 0.0}
    return {
        "source": "promo",
        "percent": float(row[0] or 0),
        "type": row[1] or "percentage",
        "manual_price": float(row[2] or 0),
    }


def _active_product_discounts(cursor, product_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not product_ids:
        return {}
    placeholders = ", ".join("?" for _ in product_ids)
    try:
        cursor.execute(
            f"""
            SELECT product_id, discount_percent, COALESCE(discount_type, 'percentage'),
                   COALESCE(manual_price, 0), end_date
            FROM product_discounts
            WHERE product_id IN ({placeholders})
              AND active = 1
              AND date(start_date) <= date('now')
              AND date(end_date) >= date('now')
            ORDER BY product_id,
                CASE
                    WHEN COALESCE(discount_type, 'percentage') = 'manual_price' THEN 999999999 - COALESCE(manual_price, 0)
                    ELSE discount_percent
                END DESC,
                end_date ASC
            """,
            product_ids,
        )
        discounts = {}
        for product_id, percent, discount_type, manual_price, _end_date in cursor.fetchall():
            pid = int(product_id or 0)
            if pid and pid not in discounts:
                discounts[pid] = {
                    "source": "promo",
                    "percent": float(percent or 0),
                    "type": discount_type or "percentage",
                    "manual_price": float(manual_price or 0),
                }
        return discounts
    except Exception:
        return {}


def _effective_price(price: float, discount: Dict[str, Any]) -> tuple[float, float]:
    original = float(price or 0)
    if discount.get("source") == "promo" and discount.get("type") == "manual_price":
        manual_price = float(discount.get("manual_price") or 0)
        if 0 < manual_price < original:
            percent = ((original - manual_price) / original) * 100 if original else 0.0
            return manual_price, percent
    percent = float(discount.get("percent") or 0)
    if percent > 0:
        return max(0.0, original * (1 - min(percent, 100) / 100.0)), percent
    return original, 0.0


def _price_tiers_for_products(cursor, product_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    if not product_ids:
        return {}
    try:
        ensure_wholesale_schema(cursor)
        placeholders = ", ".join("?" for _ in product_ids)
        cursor.execute(
            f"""
            SELECT product_id, id, min_qty, COALESCE(unit_label, ''), COALESCE(unit_multiplier, 1),
                   COALESCE(barcode, ''), unit_price, COALESCE(note, ''), COALESCE(active, 1)
            FROM product_price_tiers
            WHERE product_id IN ({placeholders})
            ORDER BY product_id, min_qty ASC, unit_price ASC
            """,
            product_ids,
        )
        tiers_by_product: Dict[int, List[Dict[str, Any]]] = {}
        for row in cursor.fetchall():
            product_id = int(row[0] or 0)
            tiers_by_product.setdefault(product_id, []).append({
                "id": row[1],
                "min_qty": int(row[2] or 1),
                "unit_label": row[3] or "",
                "unit_multiplier": int(row[4] or 1),
                "barcode": row[5] or "",
                "unit_price": float(row[6] or 0),
                "note": row[7] or "",
                "active": int(row[8] or 0),
            })
        return tiers_by_product
    except Exception as exc:
        logger.debug(f"Wholesale tier batch load skipped: {exc}")
        return {}


def _effective_stock_sql(alias: str = "p") -> str:
    return f"""
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM product_locations pl_stock_exists
                WHERE pl_stock_exists.product_id = {alias}.id
            )
            THEN
                CASE
                    WHEN COALESCE({alias}.stock, 0) <= COALESCE((
                        SELECT SUM(COALESCE(pl_stock.quantity, 0))
                        FROM product_locations pl_stock
                        WHERE pl_stock.product_id = {alias}.id
                    ), 0)
                    THEN COALESCE({alias}.stock, 0)
                    ELSE COALESCE((
                        SELECT SUM(COALESCE(pl_stock.quantity, 0))
                        FROM product_locations pl_stock
                        WHERE pl_stock.product_id = {alias}.id
                    ), 0)
                END
            ELSE COALESCE({alias}.stock, 0)
        END
    """


def _effective_stock(cursor, product_id: int) -> int:
    cursor.execute(f"SELECT {_effective_stock_sql('p')} FROM products p WHERE p.id = ?", (product_id,))
    row = cursor.fetchone()
    return int(row[0] or 0) if row else 0


def _resolve_product_image_file(image_path: str) -> str:
    raw_path = str(image_path or "").strip().strip('"')
    if not raw_path:
        return ""

    normalized = raw_path.replace("\\", os.sep).replace("/", os.sep)
    filename = os.path.basename(normalized)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_dir = get_product_images_dir()
    candidates = []

    if os.path.isabs(normalized):
        candidates.append(normalized)
    else:
        candidates.extend([
            os.path.join(base_dir, normalized),
            os.path.join(os.getcwd(), normalized),
        ])
    if filename:
        candidates.append(os.path.join(image_dir, filename))

    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            if os.path.exists(candidate):
                return os.path.abspath(candidate)
    return ""


def _product_thumbnail_url(image_path: str, product_id: Optional[int] = None) -> str:
    resolved_path = _resolve_product_image_file(image_path)
    if not resolved_path and product_id:
        resolved_path = cached_product_image_path(product_id, image_path)
    if not resolved_path:
        return ""

    try:
        thumbnail_path = ImageOptimizer.get_thumbnail_path(resolved_path, (80, 80))
    except Exception as exc:
        logger.debug(f"Cashier thumbnail generation skipped: {exc}")
        thumbnail_path = resolved_path

    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return ""

    try:
        relative_path = os.path.relpath(thumbnail_path, get_product_images_dir())
    except ValueError:
        return ""
    url_path = relative_path.replace(os.sep, "/")
    return f"/product-images/{quote(url_path)}"


def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, username, password_hash, role, full_name, salt, force_password_change, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        user_id, db_username, stored_hash, role, full_name, salt, force_change, is_active = row
        if is_active == 0 or force_change == 1:
            return None

        salt_bytes = bytes.fromhex(salt) if salt else b"salt_123"
        input_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, 100000).hex()
        if input_hash != stored_hash:
            return None

        return {
            "id": user_id,
            "username": db_username,
            "role": role,
            "full_name": full_name or db_username,
        }
    finally:
        conn.close()


def list_categories() -> List[str]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT DISTINCT TRIM(category) AS category
            FROM products
            WHERE category IS NOT NULL AND TRIM(category) != ''
            ORDER BY TRIM(category) COLLATE NOCASE
            """
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def barcode_exists(barcode: str, exclude_product_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    barcode = str(barcode or "").strip()
    if not barcode:
        return None
    conn = connect_db()
    cursor = conn.cursor()
    try:
        params: List[Any] = [barcode]
        sql = """
            SELECT id, name, barcode, sku
            FROM products
            WHERE barcode = ?
        """
        if exclude_product_id:
            sql += " AND id != ?"
            params.append(int(exclude_product_id))
        sql += " LIMIT 1"
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "barcode": row[2], "sku": row[3]}
    finally:
        conn.close()


def _save_mobile_product_image(image_bytes: bytes, filename: str, content_type: str) -> tuple[str, bytes, str, str]:
    if not image_bytes:
        return "", b"", "", ""

    image_dir = get_product_images_dir()
    os.makedirs(image_dir, exist_ok=True)

    guessed_extension = mimetypes.guess_extension(content_type or "") or os.path.splitext(filename or "")[1] or ".jpg"
    if guessed_extension.lower() == ".jpe":
        guessed_extension = ".jpg"
    safe_filename = f"mobile_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{guessed_extension}"
    image_path = os.path.join(image_dir, safe_filename)
    with open(image_path, "wb") as image_file:
        image_file.write(image_bytes)

    mime_type = content_type or mimetypes.guess_type(safe_filename)[0] or "image/jpeg"
    return app_relative_path(image_path), image_bytes, mime_type, safe_filename


def _generate_product_sku(cursor) -> str:
    cursor.execute("SELECT COALESCE(MAX(id), 0) FROM products")
    row = cursor.fetchone()
    next_id = int(row[0] or 0) + 1 if row else 1

    while True:
        sku = f"ITM-{next_id:05d}"
        cursor.execute("SELECT 1 FROM products WHERE sku = ? LIMIT 1", (sku,))
        if not cursor.fetchone():
            return sku
        next_id += 1


def create_mobile_product(
    *,
    name: str,
    barcode: str = "",
    sku: str = "",
    category: str = "",
    price: float = 0,
    cost: float = 0,
    stock: int = 0,
    low_stock: int = 0,
    unit: str = "",
    location: str = "Mobile Entry",
    image_bytes: bytes = b"",
    image_filename: str = "",
    image_content_type: str = "",
    created_by: str = "Mobile",
) -> Dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise ValueError("Product name is required.")

    barcode = str(barcode or "").strip()
    sku = str(sku or "").strip()
    category = str(category or "").strip()
    unit = str(unit or "").strip()
    location = str(location or "").strip() or "Mobile Entry"
    price = max(0.0, float(price or 0))
    cost = max(0.0, float(cost or 0))
    stock = max(0, int(stock or 0))
    low_stock = max(0, int(low_stock or 0))

    if barcode and barcode_exists(barcode):
        raise ValueError(f"Barcode already exists: {barcode}")

    image_path = ""
    image_data = b""
    image_mime = ""
    image_db_filename = ""
    if image_bytes:
        image_path, image_data, image_mime, image_db_filename = _save_mobile_product_image(
            image_bytes, image_filename, image_content_type
        )

    conn = connect_db()
    cursor = conn.cursor()
    try:
        if not is_postgres_backend():
            cursor.execute("BEGIN IMMEDIATE")
        _sync_postgres_id_sequences(cursor, ("products", "product_locations", "stock_movements"))
        if not sku:
            sku = _generate_product_sku(cursor)
        product_id = _execute_dynamic_insert(cursor, "products", {
            "name": name,
            "category": category,
            "description": "",
            "sold_by": "Each",
            "price": price,
            "cost": cost,
            "sku": sku,
            "barcode": barcode,
            "stock": stock,
            "low_stock": low_stock,
            "unit": unit,
            "image": image_path,
            "image_data": image_data if image_data else None,
            "image_mime": image_mime,
            "image_filename": image_db_filename,
            "warehouse": location,
        })

        if stock > 0:
            _try_dynamic_insert(cursor, "product_locations", {
                "product_id": product_id,
                "location": location,
                "quantity": stock,
                "batch_no": "",
                "expire_date": "",
            })
            _try_dynamic_insert(cursor, "stock_movements", {
                "product_id": product_id,
                "type": "in",
                "quantity": stock,
                "old_stock": 0,
                "new_stock": stock,
                "reason": "Mobile Product Entry",
                "reference": f"MOBILE-{product_id}",
                "created_by": created_by,
                "location": location,
                "notes": "Initial stock from mobile product entry",
            })

        conn.commit()
        return {
            "id": product_id,
            "name": name,
            "barcode": barcode,
            "sku": sku,
            "category": category,
            "price": price,
            "cost": cost,
            "stock": stock,
            "low_stock": low_stock,
            "unit": unit,
            "location": location,
            "image": image_path,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_products(search: str = "", category: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        where = []
        params: List[Any] = []
        if search:
            where.append("(name LIKE ? OR sku LIKE ? OR barcode LIKE ?)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        if category:
            where.append("TRIM(COALESCE(category, '')) = ?")
            params.append(category)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        params.extend([max(1, min(limit, 500)), max(0, offset)])
        stock_expr = _effective_stock_sql("p")
        cursor.execute(
            f"""
            SELECT p.id, p.name, p.category, p.price, p.cost, p.sku, p.barcode,
                   {stock_expr} as stock, p.image, p.sold_by, p.unit
            FROM products p
            {where_sql}
            ORDER BY p.is_favourite DESC, p.name COLLATE NOCASE
            LIMIT ? OFFSET ?
            """,
            params,
        )
        rows = cursor.fetchall()
        product_columns = [description[0] for description in cursor.description]
        product_ids = [int(row[0] or 0) for row in rows]
        discounts = _active_product_discounts(cursor, product_ids)
        tiers_by_product = _price_tiers_for_products(cursor, product_ids)
        products = []
        for row in rows:
            product = {product_columns[index]: row[index] for index in range(len(product_columns))}
            sold_by = str(product.get("sold_by") or "")
            product["is_service"] = sold_by.lower() == "service" or sold_by.lower() == "services"
            product["stock"] = int(product.get("stock") or 0)
            product["is_out_of_stock"] = not product["is_service"] and product["stock"] <= 0
            product_id = int(product["id"])
            discount = discounts.get(product_id, {"source": "", "percent": 0.0, "type": "percentage", "manual_price": 0.0})
            effective_price, discount_percent = _effective_price(float(product.get("price") or 0), discount)
            product["original_price"] = float(product.get("price") or 0)
            product["price"] = effective_price
            product["discount_source"] = discount.get("source", "")
            product["discount_percent"] = discount_percent
            product["thumbnail_url"] = _product_thumbnail_url(product.get("image") or "", product_id)
            product["wholesale_tiers"] = [
                tier for tier in tiers_by_product.get(product_id, [])
                if int(tier.get("active", 1)) == 1
            ]
            products.append(product)
        return products
    finally:
        conn.close()


def get_product_image_path(product_id: int) -> Optional[str]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT image FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return None

        image_path = str(row[0])
        candidates = [image_path]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(base_dir, image_path))
        candidates.append(os.path.join(base_dir, "database", "product_images", os.path.basename(image_path)))

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)
        return None
    finally:
        conn.close()


def get_product_image_blob(product_id: int) -> Optional[Dict[str, Any]]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT image_data, image_mime, image_filename
            FROM products
            WHERE id = ? AND image_data IS NOT NULL
            """,
            (product_id,),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return None
        image_data = row[0]
        if isinstance(image_data, memoryview):
            image_data = image_data.tobytes()
        elif not isinstance(image_data, bytes):
            image_data = bytes(image_data)
        return {
            "data": image_data,
            "mime": row[1] or "image/jpeg",
            "filename": row[2] or f"product_{product_id}.jpg",
        }
    finally:
        conn.close()


def list_customers(search: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        params: List[Any] = []
        where_sql = ""
        if search:
            where_sql = "WHERE name LIKE ? OR phone LIKE ?"
            pattern = f"%{search}%"
            params.extend([pattern, pattern])
        params.append(max(1, min(limit, 200)))
        cursor.execute(
            f"""
            SELECT id, name, phone, points, current_balance, credit_limit
            FROM customers
            {where_sql}
            ORDER BY name COLLATE NOCASE
            LIMIT ?
            """,
            params,
        )
        return [_dict_from_row(cursor, row) for row in cursor.fetchall()]
    finally:
        conn.close()


def list_payment_types() -> List[str]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        try:
            cursor.execute("SELECT name FROM payment_types ORDER BY name")
            rows = cursor.fetchall()
        except Exception:
            rows = []
        types = [str(row[0]) for row in rows if row and row[0]]
        return types or ["Cash", "Card", "Mobile Money"]
    finally:
        conn.close()


def get_cashier_settings() -> Dict[str, Any]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        return _cashier_settings_from_cursor(cursor)
    finally:
        conn.close()


def _cashier_settings_from_cursor(cursor) -> Dict[str, Any]:
    discount_enabled = _setting(cursor, "discount_enabled", "0") == "1"
    discount_type = _setting(cursor, "discount_type", "percentage") or "percentage"
    discount_value = float(_setting(cursor, "discount_value", "0") or 0)
    tax_enabled = _setting(cursor, "tax_enabled", "0") == "1"
    tax_rate = float(_setting(cursor, "tax_rate", "0") or 0)
    points_per_dollar = float(_setting(cursor, "loyalty_points_per_dollar", "0") or 0)
    points_dollar_value = float(_setting(cursor, "points_dollar_value", "0.01") or 0.01)
    points_expiry_months = int(float(_setting(cursor, "points_expiry_months", "12") or 12))
    try:
        cursor.execute("SELECT name FROM payment_types ORDER BY name")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    payment_types = [str(row[0]) for row in rows if row and row[0]] or ["Cash", "Card", "Mobile Money"]
    return {
        "discount_enabled": discount_enabled,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "tax_enabled": tax_enabled,
        "tax_rate": tax_rate,
        "points_per_dollar": points_per_dollar,
        "points_dollar_value": points_dollar_value,
        "points_expiry_months": points_expiry_months,
        "payment_types": payment_types,
    }


def _allocate_stock(cursor, product_id: int, qty_needed: int, invoice_no: str, created_by: str) -> List[Dict[str, Any]]:
    cursor.execute("SELECT name, stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        raise ValueError(f"Product not found: {product_id}")

    product_name, master_stock = product[0], int(product[1] or 0)

    allocations: List[Dict[str, Any]] = []
    cursor.execute(
        """
        SELECT id, location, batch_no, expire_date, quantity
        FROM product_locations
        WHERE product_id = ? AND quantity > 0
        ORDER BY
            CASE WHEN expire_date IS NULL OR expire_date = '' THEN 1 ELSE 0 END,
            expire_date ASC,
            last_updated ASC,
            id ASC
        """,
        (product_id,),
    )
    locations = cursor.fetchall()
    location_stock = sum(int(row[4] or 0) for row in locations)
    available_stock = min(master_stock, location_stock) if locations else master_stock
    if available_stock < qty_needed:
        raise ValueError(f"Only {available_stock} left: {product_name}")

    remaining = qty_needed
    for loc_id, location, batch_no, expire_date, available in locations:
        if remaining <= 0:
            break
        take = min(int(available or 0), remaining)
        if take <= 0:
            continue

        cursor.execute(
            "UPDATE product_locations SET quantity = quantity - ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
            (take, loc_id),
        )
        cursor.execute("SELECT quantity FROM product_locations WHERE id = ?", (loc_id,))
        updated_qty = int(cursor.fetchone()[0] or 0)
        if updated_qty <= 0:
            cursor.execute("DELETE FROM product_locations WHERE id = ?", (loc_id,))

        allocations.append(
            {
                "product_id": product_id,
                "qty": take,
                "location_id": loc_id,
                "location": location or "",
                "batch_no": batch_no or "",
                "expire_date": expire_date or "",
            }
        )
        remaining -= take

    if remaining > 0 and locations:
        raise ValueError(f"Not enough location stock for {product_name}")

    if not allocations:
        allocations.append(
            {
                "product_id": product_id,
                "qty": qty_needed,
                "location_id": None,
                "location": "",
                "batch_no": "",
                "expire_date": "",
            }
        )

    stock_before = available_stock
    for allocation in allocations:
        take = int(allocation["qty"])
        stock_after = stock_before - take
        cursor.execute("UPDATE products SET stock = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?", (stock_after, product_id))
        _execute_dynamic_insert(
            cursor,
            "stock_movements",
            {
                "product_id": product_id,
                "type": "sale",
                "quantity": take,
                "old_stock": stock_before,
                "new_stock": stock_after,
                "reason": "Sale",
                "reference": invoice_no,
                "created_by": created_by,
                "location": allocation.get("location") or "",
                "notes": f"Browser cashier sale. Expiry: {allocation.get('expire_date') or 'N/A'}",
            },
        )
        stock_before = stock_after

    return allocations


def create_sale(
    *,
    items: Iterable[Dict[str, Any]],
    payment: float,
    payment_type: str = "Cash",
    sale_mode: str = "Cash",
    discount_amount: float = 0,
    points_used: int = 0,
    customer_id: Optional[int] = None,
    created_by: str = "Browser Cashier",
) -> Dict[str, Any]:
    normalized_items = []
    for item in items:
        product_id = int(item.get("product_id") or item.get("id") or 0)
        qty = int(item.get("qty") or 0)
        manual_price = item.get("manual_price")
        if product_id <= 0 or qty <= 0:
            raise ValueError("Invalid cart item")
        normalized_items.append({"product_id": product_id, "qty": qty, "manual_price": manual_price})

    if not normalized_items:
        raise ValueError("Cart is empty")

    payment_type = payment_type or "Cash"
    sale_mode = sale_mode or "Cash"
    is_credit = sale_mode.lower() == "credit" or payment_type.lower() == "credit"

    conn = connect_db()
    cursor = conn.cursor()
    invoice_no = datetime.now().strftime("WEB%Y%m%d%H%M%S%f")[:-3]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if not is_postgres_backend():
            cursor.execute("BEGIN IMMEDIATE")
        _sync_postgres_id_sequences(
            cursor,
            (
                "sales",
                "sale_items",
                "stock_movements",
                "credit_sales",
                "customer_points_log",
            ),
        )

        sale_items: List[Dict[str, Any]] = []
        subtotal = 0.0
        cogs = 0.0
        for item in normalized_items:
            cursor.execute(
                "SELECT id, name, price, cost, stock, sold_by FROM products WHERE id = ?",
                (item["product_id"],),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Product not found: {item['product_id']}")

            product_id, name, price, cost, stock, sold_by = row
            qty = item["qty"]
            price = float(price or 0)
            cost = float(cost or 0)
            is_service = str(sold_by or "").lower() in ("service", "services")
            if is_service:
                if item.get("manual_price") is not None:
                    price = max(0.0, float(item.get("manual_price") or 0))
                allocations = [{"qty": qty, "location_id": None, "location": "", "batch_no": "", "expire_date": ""}]
            else:
                discount = _active_product_discount(cursor, int(product_id))
                price, _discount_percent = _effective_price(price, discount)
                tier = get_best_price_tier(cursor, int(product_id), qty)
                if tier and float(tier.get("unit_price") or 0) > 0:
                    price = float(tier["unit_price"])
                    name = f"{name} (Wholesale {tier.get('min_qty')}+)"
                available_stock = _effective_stock(cursor, int(product_id))
                if available_stock < qty:
                    raise ValueError(f"Only {available_stock} left: {name}")
                allocations = _allocate_stock(cursor, int(product_id), qty, invoice_no, created_by)

            for allocation in allocations:
                allocation_qty = int(allocation["qty"])
                sale_items.append(
                    {
                        "product_id": int(product_id),
                        "product_name": name,
                        "qty": allocation_qty,
                        "price": price,
                        "total": price * allocation_qty,
                        "cost": cost,
                        "location_id": allocation.get("location_id"),
                        "location": allocation.get("location") or "",
                        "batch_no": allocation.get("batch_no") or "",
                        "expire_date": allocation.get("expire_date") or "",
                    }
                )
            subtotal += price * qty
            cogs += cost * qty

        discount_amount = max(0.0, float(discount_amount or 0))
        settings = _cashier_settings_from_cursor(cursor)
        points_used = max(0, int(points_used or 0))
        points_discount = 0.0
        if customer_id and points_used > 0:
            cursor.execute("SELECT COALESCE(points, 0) FROM customers WHERE id = ?", (customer_id,))
            points_row = cursor.fetchone()
            available_points = int(points_row[0] or 0) if points_row else 0
            points_used = min(points_used, available_points)
            points_discount = min(points_used * float(settings.get("points_dollar_value") or 0.01), subtotal)
        else:
            points_used = 0

        after_discount = max(0.0, subtotal - discount_amount - points_discount)
        tax_amount = after_discount * (float(settings.get("tax_rate") or 0) / 100.0) if settings.get("tax_enabled") else 0.0
        total = max(0.0, after_discount + tax_amount)
        payment = 0.0 if is_credit else float(payment or 0)
        if not is_credit and payment < total:
            raise ValueError("Insufficient payment")
        if is_credit and not customer_id:
            raise ValueError("Customer is required for credit sale")

        change_amount = 0.0 if is_credit else payment - total
        gross_profit = subtotal - cogs
        net_profit = total - cogs

        sale_id = _execute_dynamic_insert(
            cursor,
            "sales",
            {
                "invoice_no": invoice_no,
                "total": total,
                "payment": payment,
                "change_amount": change_amount,
                "customer_id": customer_id,
                "status": "completed",
                "payment_type": payment_type,
                "discount_amount": discount_amount + points_discount,
                "created_at": created_at,
                "cogs": cogs,
                "gross_profit": gross_profit,
                "net_profit": net_profit,
            },
        )

        for sale_item in sale_items:
            sale_item["sale_id"] = sale_id
            _execute_dynamic_insert(cursor, "sale_items", sale_item)

        if customer_id and not is_credit:
            points_per_dollar = float(settings.get("points_per_dollar") or 0)
            points_expiry_months = int(settings.get("points_expiry_months") or 12)
            earned = int(total * points_per_dollar)
            if earned > 0:
                expiry_date = (datetime.now() + timedelta(days=points_expiry_months * 30)).strftime("%Y-%m-%d")
                _try_dynamic_insert(
                    cursor,
                    "customer_points_log",
                    {
                        "customer_id": customer_id,
                        "points": earned,
                        "type": "earn",
                        "reference": invoice_no,
                        "expiry_date": expiry_date,
                    },
                )
                cursor.execute("UPDATE customers SET points = COALESCE(points, 0) + ? WHERE id = ?", (earned, customer_id))
            if points_used > 0:
                cursor.execute("UPDATE customers SET points = COALESCE(points, 0) - ? WHERE id = ?", (points_used, customer_id))
                _try_dynamic_insert(
                    cursor,
                    "customer_points_log",
                    {
                        "customer_id": customer_id,
                        "points": points_used,
                        "type": "redeem",
                        "reference": invoice_no,
                    },
                )
            cursor.execute(
                """
                UPDATE customers
                SET total_visit = COALESCE(total_visit, 0) + 1,
                    total_spent = COALESCE(total_spent, 0) + ?
                WHERE id = ?
                """,
                (total, customer_id),
            )

        if customer_id and is_credit:
            _execute_dynamic_insert(
                cursor,
                "credit_sales",
                {
                    "customer_id": customer_id,
                    "sale_id": sale_id,
                    "invoice_no": invoice_no,
                    "total_amount": total,
                    "paid_amount": 0,
                    "balance_amount": total,
                    "status": "pending",
                    "sale_date": created_at,
                    "notes": "Browser cashier credit sale",
                },
            )
            cursor.execute(
                "UPDATE customers SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?",
                (total, customer_id),
            )

        receipt = _get_receipt_from_cursor(cursor, sale_id)
        conn.commit()
        logger.info(f"Browser cashier sale created: {invoice_no} ({sale_id})")
        return receipt
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_receipt(sale_id: int) -> Dict[str, Any]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        return _get_receipt_from_cursor(cursor, sale_id)
    finally:
        conn.close()


def _get_receipt_from_cursor(cursor, sale_id: int) -> Dict[str, Any]:
    cursor.execute(
        """
        SELECT s.*, c.name AS customer_name
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.id = ?
        """,
        (sale_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("Receipt not found")
    sale = _dict_from_row(cursor, row)

    item_columns = _table_columns(cursor, "sale_items")
    wanted_columns = [
        "product_id",
        "product_name",
        "qty",
        "price",
        "total",
        "cost",
        "location",
        "batch_no",
        "expire_date",
    ]
    select_columns = [column for column in wanted_columns if column in item_columns]
    cursor.execute(
        f"""
        SELECT {', '.join(select_columns)}
        FROM sale_items
        WHERE sale_id = ?
        ORDER BY id
        """,
        (sale_id,),
    )
    sale["items"] = [_dict_from_row(cursor, item) for item in cursor.fetchall()]
    return sale


def list_receipts(search: str = "", limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        where = ["COALESCE(s.status, 'completed') != 'deleted'"]
        params: List[Any] = []
        if search:
            where.append(
                """
                (
                    s.invoice_no LIKE ?
                    OR COALESCE(c.name, '') LIKE ?
                    OR COALESCE(s.payment_type, '') LIKE ?
                )
                """
            )
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])

        params.extend([max(1, min(limit, 200)), max(0, offset)])
        cursor.execute(
            f"""
            SELECT
                s.id,
                s.invoice_no,
                s.created_at,
                s.total,
                s.payment,
                s.change_amount,
                s.payment_type,
                s.status,
                COALESCE(c.name, 'Walk-in Customer') AS customer_name,
                COUNT(si.id) AS item_count
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN sale_items si ON si.sale_id = s.id
            WHERE {' AND '.join(where)}
            GROUP BY s.id
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )
        columns = [description[0] for description in cursor.description]
        return [{columns[index]: row[index] for index in range(len(columns))} for row in cursor.fetchall()]
    finally:
        conn.close()


def get_receipt_settings() -> Dict[str, str]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        keys = ["shop_name", "receipt_header", "receipt_footer", "shop_footer_message", "currency_symbol"]
        placeholders = ", ".join("?" for _ in keys)
        cursor.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
        settings = {key: value for key, value in cursor.fetchall()}
        settings.setdefault("shop_name", "ZAY POS")
        settings.setdefault("currency_symbol", "Ks")
        return settings
    finally:
        conn.close()


def list_expense_categories() -> List[str]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT name
            FROM expense_categories
            WHERE COALESCE(is_active, 1) = 1
            ORDER BY name COLLATE NOCASE
            """
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def add_expense(
    *,
    category: str,
    description: str,
    amount: float,
    expense_date: str,
    payment_method: str = "Cash",
    reference_no: str = "",
    notes: str = "",
    created_by: str = "Browser Cashier",
) -> Dict[str, Any]:
    category = category.strip()
    if not category:
        raise ValueError("Expense category is required")
    amount = float(amount or 0)
    if amount <= 0:
        raise ValueError("Expense amount must be greater than zero")
    if not expense_date:
        expense_date = datetime.now().strftime("%Y-%m-%d")

    conn = connect_db()
    cursor = conn.cursor()
    expense_no = datetime.now().strftime("EXP%Y%m%d%H%M%S%f")[:-3]
    try:
        if not is_postgres_backend():
            cursor.execute("BEGIN IMMEDIATE")
        _sync_postgres_id_sequences(cursor, ("expenses",))
        expense_id = _execute_dynamic_insert(
            cursor,
            "expenses",
            {
                "expense_no": expense_no,
                "category": category,
                "description": description.strip(),
                "amount": amount,
                "expense_date": expense_date,
                "payment_method": payment_method or "Cash",
                "reference_no": reference_no.strip(),
                "notes": notes.strip(),
                "created_by": created_by,
            },
        )
        conn.commit()
        return {
            "id": expense_id,
            "expense_no": expense_no,
            "category": category,
            "description": description.strip(),
            "amount": amount,
            "expense_date": expense_date,
            "payment_method": payment_method or "Cash",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _send_cash_drawer_pulse(printer_name: str) -> None:
    drawer_kick_command = b"\x1b\x70\x00\x19\xfa"
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [
            ("pDocName", ctypes.c_wchar_p),
            ("pOutputFile", ctypes.c_wchar_p),
            ("pDatatype", ctypes.c_wchar_p),
        ]

    h_printer = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(h_printer), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        doc_info = DOC_INFO_1("Open Cash Drawer", None, "RAW")
        if not winspool.StartDocPrinterW(h_printer, 1, ctypes.byref(doc_info)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not winspool.StartPagePrinter(h_printer):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                written = ctypes.c_ulong(0)
                buffer = ctypes.create_string_buffer(drawer_kick_command)
                if not winspool.WritePrinter(h_printer, buffer, len(drawer_kick_command), ctypes.byref(written)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                winspool.EndPagePrinter(h_printer)
        finally:
            winspool.EndDocPrinter(h_printer)
    finally:
        winspool.ClosePrinter(h_printer)


def open_cash_drawer() -> Dict[str, str]:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        printer_name = _setting(cursor, "receipt_printer_name", "").strip()
    finally:
        conn.close()

    if not printer_name:
        raise ValueError("Receipt printer is not configured on the Server PC")
    _send_cash_drawer_pulse(printer_name)
    return {"printer_name": printer_name, "status": "opened"}
