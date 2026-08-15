"""Receipt template settings and render helpers."""

import html
import os

from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.receipt_images import resolve_receipt_image_path


DEFAULT_RECEIPT_TEMPLATE = {
    "receipt_show_logo": "1",
    "receipt_show_shop_phone": "1",
    "receipt_show_shop_address": "1",
    "receipt_show_invoice": "1",
    "receipt_show_payment_type": "1",
    "receipt_show_customer": "1",
    "receipt_show_item_prices": "1",
    "receipt_show_subtotal": "1",
    "receipt_show_discount": "1",
    "receipt_show_tax": "1",
    "receipt_show_payment_change": "1",
    "receipt_show_thank_you": "1",
    "receipt_thank_you_text": "THANK YOU",
    "receipt_line_width": "32",
}


def _as_bool(settings, key):
    return str(settings.get(key, DEFAULT_RECEIPT_TEMPLATE.get(key, "1"))) == "1"


def load_receipt_template_settings():
    settings = dict(DEFAULT_RECEIPT_TEMPLATE)
    try:
        conn = connect_db()
        cursor = conn.cursor()
        keys = list(DEFAULT_RECEIPT_TEMPLATE.keys())
        placeholders = ",".join("?" for _ in keys)
        cursor.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
        settings.update({key: value for key, value in cursor.fetchall()})
        conn.close()
    except Exception:
        pass
    return settings


def save_receipt_template_settings(settings):
    values = dict(DEFAULT_RECEIPT_TEMPLATE)
    values.update(settings or {})
    conn = connect_db()
    cursor = conn.cursor()
    for key, value in values.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_shop_settings():
    defaults = {
        "shop_name": "ZAY POS",
        "shop_phone": "",
        "shop_address": "",
        "shop_footer_message": "",
        "shop_logo": "",
        "receipt_header": "",
        "receipt_footer": "",
        "show_customer_name": "1",
    }
    try:
        conn = connect_db()
        cursor = conn.cursor()
        keys = list(defaults.keys())
        placeholders = ",".join("?" for _ in keys)
        cursor.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
        defaults.update({key: value for key, value in cursor.fetchall()})
        conn.close()
    except Exception:
        pass
    defaults["shop_logo"] = resolve_receipt_image_path("logo") or defaults.get("shop_logo", "")
    return defaults


def sample_receipt_data():
    return {
        "invoice_no": "INV202608020001",
        "created_at": "2026-08-02 10:30:00",
        "total": 17500,
        "payment": 20000,
        "change": 2500,
        "payment_type": "Cash",
        "discount_amt": 500,
        "customer_name": "Walk-in",
    }, [
        ("Sample Product A", 2, 5000, 10000),
        ("Sample Product B", 1, 8000, 8000),
    ]


def _receipt_item_value(item, index, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    try:
        return item[index]
    except (IndexError, TypeError):
        return default


def build_receipt_text_lines(sale, items, template_settings=None, shop_settings=None):
    template = template_settings or load_receipt_template_settings()
    shop = shop_settings or get_shop_settings()
    symbol = get_currency_symbol()
    width = int(template.get("receipt_line_width", "32") or 32)
    width = max(24, min(width, 64))

    invoice_no = sale.get("invoice_no", "")
    created_at = sale.get("created_at", "")
    total = sale.get("total", 0) or 0
    payment = sale.get("payment", 0) or 0
    change = sale.get("change", 0) or 0
    payment_type = sale.get("payment_type", "")
    discount_amt = sale.get("discount_amt", 0) or 0
    customer_name = sale.get("customer_name", "")

    lines = []
    lines.append("=" * width)
    if shop.get("shop_name"):
        lines.append(str(shop["shop_name"]).center(width))
    if _as_bool(template, "receipt_show_shop_phone") and shop.get("shop_phone"):
        lines.append(str(shop["shop_phone"]).center(width))
    if _as_bool(template, "receipt_show_shop_address") and shop.get("shop_address"):
        for line in str(shop["shop_address"]).splitlines():
            if line.strip():
                lines.append(line.strip())
    if shop.get("receipt_header"):
        for line in str(shop["receipt_header"]).splitlines():
            if line.strip():
                lines.append(line.strip())
    lines.append("=" * width)

    if _as_bool(template, "receipt_show_invoice"):
        lines.append(f"Invoice : {invoice_no}")
        lines.append(f"Date    : {created_at}")
    if _as_bool(template, "receipt_show_payment_type"):
        lines.append(f"Payment : {payment_type}")
    show_customer = _as_bool(template, "receipt_show_customer") and shop.get("show_customer_name", "1") == "1"
    if show_customer and customer_name:
        lines.append(f"Customer: {customer_name}")
    lines.append("-" * width)

    for item in items:
        name = _receipt_item_value(item, 0, "product_name", "")
        qty = _receipt_item_value(item, 1, "qty", 0) or 0
        price = _receipt_item_value(item, 2, "price", 0) or 0
        item_total = _receipt_item_value(item, 3, "total", 0) or 0
        wholesale_regular_price = float(_receipt_item_value(item, 4, "wholesale_regular_price", 0) or 0)
        wholesale_savings = float(_receipt_item_value(item, 5, "wholesale_savings", 0) or 0)
        lines.append(str(name))
        if _as_bool(template, "receipt_show_item_prices"):
            lines.append(f"  {qty} x {format_money(price, symbol)} = {format_money(item_total, symbol)}")
            if wholesale_regular_price > float(price or 0) and wholesale_savings > 0:
                lines.append(
                    f"  Wholesale: regular {format_money(wholesale_regular_price, symbol)}, "
                    f"saved {format_money(wholesale_savings, symbol)}"
                )
        else:
            lines.append(f"  Qty: {qty}")

    subtotal = sum((_receipt_item_value(item, 3, "total", 0) or 0) for item in items)
    discount = discount_amt if discount_amt else 0
    lines.append("-" * width)
    if _as_bool(template, "receipt_show_subtotal"):
        lines.append(f"{'Subtotal':<14} {format_money(subtotal, symbol):>{max(8, width - 15)}}")
    if _as_bool(template, "receipt_show_discount") and discount > 0:
        lines.append(f"{'Discount':<14} -{format_money(discount, symbol):>{max(8, width - 16)}}")
    if _as_bool(template, "receipt_show_tax"):
        lines.append(f"{'Tax':<14} {format_money(0, symbol):>{max(8, width - 15)}}")
    lines.append("=" * width)
    lines.append(f"{'GRAND TOTAL':<14} {format_money(total, symbol):>{max(8, width - 15)}}")
    lines.append("=" * width)
    if _as_bool(template, "receipt_show_payment_change"):
        lines.append(f"{'Payment':<14} {format_money(payment, symbol):>{max(8, width - 15)}}")
        lines.append(f"{'Change':<14} {format_money(change, symbol):>{max(8, width - 15)}}")
        lines.append("-" * width)

    if shop.get("receipt_footer"):
        for line in str(shop["receipt_footer"]).splitlines():
            if line.strip():
                lines.append(line.strip())
    if shop.get("shop_footer_message"):
        for line in str(shop["shop_footer_message"]).splitlines():
            if line.strip():
                lines.append(line.strip())
    if _as_bool(template, "receipt_show_thank_you"):
        thank_you = template.get("receipt_thank_you_text", "THANK YOU") or "THANK YOU"
        lines.append(str(thank_you).center(width))
    lines.append("=" * width)
    return lines


def build_receipt_html(sale, items, template_settings=None, shop_settings=None):
    template = template_settings or load_receipt_template_settings()
    shop = shop_settings or get_shop_settings()
    lines = build_receipt_text_lines(sale, items, template, shop)
    escaped_lines = "<br>".join(html.escape(str(line)) for line in lines)
    logo_html = ""
    logo_path = shop.get("shop_logo", "")
    if _as_bool(template, "receipt_show_logo") and logo_path and os.path.exists(logo_path):
        safe_path = html.escape(logo_path.replace("\\", "/"))
        logo_html = f'<img class="logo" src="{safe_path}" />'
    return f"""
    <html>
    <head>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            font-size: 9pt;
            margin: 0;
            padding: 10px;
            background-color: #ffffff;
            color: #000000;
        }}
        .receipt {{ white-space: nowrap; line-height: 1.35; }}
        .logo {{
            max-width: 120px;
            max-height: 80px;
            display: block;
            margin: 0 auto 8px auto;
        }}
    </style>
    </head>
    <body>
        {logo_html}
        <div class="receipt">{escaped_lines}</div>
    </body>
    </html>
    """
