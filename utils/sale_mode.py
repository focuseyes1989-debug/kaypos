"""Helpers for choosing between retail Sales and Restaurant POS flows."""

from models.database import connect_db


SALE_MODE_RETAIL = "retail"
SALE_MODE_RESTAURANT = "restaurant"
SALE_MODE_BOTH = "both"
SALE_MODE_SETTING_KEY = "pos_sale_mode"
VALID_SALE_MODES = {SALE_MODE_RETAIL, SALE_MODE_RESTAURANT, SALE_MODE_BOTH}


def normalize_sale_mode(value):
    mode = str(value or "").strip().lower()
    return mode if mode in VALID_SALE_MODES else SALE_MODE_RETAIL


def get_sale_mode(default=SALE_MODE_RETAIL):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (SALE_MODE_SETTING_KEY, normalize_sale_mode(default)),
    )
    cursor.execute("SELECT value FROM settings WHERE key = ?", (SALE_MODE_SETTING_KEY,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return normalize_sale_mode(row[0] if row else default)


def save_sale_mode(mode):
    mode = normalize_sale_mode(mode)
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (SALE_MODE_SETTING_KEY, mode),
    )
    conn.commit()
    conn.close()
    return mode


def is_sale_page_enabled(page_index, mode=None):
    mode = normalize_sale_mode(mode if mode is not None else get_sale_mode())
    if mode == SALE_MODE_BOTH:
        return True
    if int(page_index) == 5:
        return mode == SALE_MODE_RETAIL
    if int(page_index) == 10:
        return mode == SALE_MODE_RESTAURANT
    return True
