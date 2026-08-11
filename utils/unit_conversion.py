"""Helpers for product base/pack unit conversion."""


DEFAULT_BASE_UNIT = "pcs"


def ensure_unit_conversion_schema(cursor):
    """Add product unit conversion columns for existing databases."""
    cursor.execute("PRAGMA table_info(products)")
    cols = {row[1] for row in cursor.fetchall()}
    new_cols = {
        "base_unit": f"TEXT DEFAULT '{DEFAULT_BASE_UNIT}'",
        "pack_unit": "TEXT DEFAULT ''",
        "pack_size": "INTEGER DEFAULT 1",
    }
    for col, ddl in new_cols.items():
        if col not in cols:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col} {ddl}")


def normalize_unit_settings(base_unit=None, pack_unit=None, pack_size=None):
    base = (base_unit or DEFAULT_BASE_UNIT).strip() or DEFAULT_BASE_UNIT
    pack = (pack_unit or "").strip()
    try:
        size = int(pack_size or 1)
    except (TypeError, ValueError):
        size = 1
    return {
        "base_unit": base,
        "pack_unit": pack,
        "pack_size": max(1, size),
    }


def get_product_unit_settings(cursor, product_id):
    ensure_unit_conversion_schema(cursor)
    cursor.execute(
        """
        SELECT COALESCE(base_unit, ''), COALESCE(pack_unit, ''), COALESCE(pack_size, 1)
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    )
    row = cursor.fetchone()
    if not row:
        return normalize_unit_settings()
    return normalize_unit_settings(row[0], row[1], row[2])


def unit_combo_items(settings):
    items = [(settings["base_unit"], "base")]
    if settings["pack_unit"] and settings["pack_size"] > 1:
        items.append((f"{settings['pack_unit']} ({settings['pack_size']} {settings['base_unit']})", "pack"))
    return items


def to_base_quantity(quantity, selected_unit, settings):
    qty = int(quantity or 0)
    if selected_unit == "pack" and settings["pack_unit"] and settings["pack_size"] > 1:
        return qty * settings["pack_size"]
    return qty


def to_base_unit_cost(unit_cost, selected_unit, settings):
    cost = float(unit_cost or 0)
    if selected_unit == "pack" and settings["pack_unit"] and settings["pack_size"] > 1:
        return cost / settings["pack_size"]
    return cost
