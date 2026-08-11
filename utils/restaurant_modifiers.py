"""Product-level restaurant modifier settings."""

import json

from utils.db_compat import ensure_column

DEFAULT_RESTAURANT_MODIFIERS = [
    {"group": "Protein", "name": "Chicken", "type": "choice", "price_delta": 0},
    {"group": "Protein", "name": "Pork", "type": "choice", "price_delta": 0},
    {"group": "Protein", "name": "Beef", "type": "choice", "price_delta": 0},
    {"group": "Taste", "name": "Less salt", "type": "note", "price_delta": 0},
    {"group": "Taste", "name": "Less spicy", "type": "note", "price_delta": 0},
    {"group": "Taste", "name": "Less sweet", "type": "note", "price_delta": 0},
]


def ensure_restaurant_modifier_schema(cursor):
    ensure_column(cursor, "products", "restaurant_modifiers", "TEXT")


def normalize_modifiers(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        group = str(item.get("group") or "Options").strip() or "Options"
        mod_type = str(item.get("type") or "note").strip().lower()
        if mod_type not in {"choice", "note"}:
            mod_type = "note"
        try:
            price_delta = float(item.get("price_delta") or 0)
        except (TypeError, ValueError):
            price_delta = 0.0
        normalized.append({
            "group": group,
            "name": name,
            "type": mod_type,
            "price_delta": price_delta,
        })
    return normalized


def dumps_modifiers(modifiers):
    return json.dumps(normalize_modifiers(modifiers), ensure_ascii=False)


def get_product_restaurant_modifiers(cursor, product_id):
    ensure_restaurant_modifier_schema(cursor)
    cursor.execute("SELECT COALESCE(restaurant_modifiers, '') FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    return normalize_modifiers(row[0] if row else "")
