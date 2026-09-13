"""Lightweight offline sale queue for KAY POS Lite."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


def offline_dir() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home())
    return base / "KAY" / "POSLite"


def offline_db_path() -> Path:
    return offline_dir() / "offline_sales.sqlite3"


def product_cache_path() -> Path:
    return offline_dir() / "product_cache.json"


def _connect() -> sqlite3.Connection:
    path = offline_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_sales (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL,
            receipt TEXT NOT NULL,
            sync_attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    return connection


def save_product_cache(products: list[dict]) -> None:
    product_cache_path().parent.mkdir(parents=True, exist_ok=True)
    product_cache_path().write_text(
        json.dumps({"saved_at": datetime.now().isoformat(timespec="seconds"), "products": products}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_product_cache() -> list[dict]:
    try:
        data = json.loads(product_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return list(data.get("products") or [])


def pending_count() -> int:
    with _connect() as connection:
        row = connection.execute("SELECT COUNT(*) FROM pending_sales").fetchone()
    return int(row[0] or 0) if row else 0


def create_offline_sale(
    items: list[dict],
    payment: float,
    payment_type: str,
    discount_amount: float = 0,
    receipt_settings: dict | None = None,
) -> dict:
    sale_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")
    subtotal = sum(
        float(item.get("manual_price") if item.get("manual_price") is not None else item.get("price") or 0)
        * int(item.get("qty") or 0)
        for item in items
    )
    total = max(0.0, subtotal - max(0.0, float(discount_amount or 0)))
    payload = {
        "items": items,
        "payment": float(payment),
        "payment_type": payment_type or "Cash",
        "discount_amount": max(0.0, float(discount_amount or 0)),
        "offline_sale_id": sale_id,
        "offline_created_at": created_at,
    }
    receipt = {
        "id": 0,
        "offline_sale_id": sale_id,
        "invoice_no": f"OFFLINE-{datetime.now():%Y%m%d-%H%M%S}",
        "created_at": created_at.replace("T", " "),
        "status": "offline pending sync",
        "payment_type": payment_type or "Cash",
        "payment": float(payment),
        "paid_amount": float(payment),
        "change_amount": max(0.0, float(payment) - total),
        "discount_amount": max(0.0, float(discount_amount or 0)),
        "subtotal": subtotal,
        "total": total,
        "items": [
            {
                "product_name": item.get("name") or f"Product {item.get('product_id')}",
                "name": item.get("name") or f"Product {item.get('product_id')}",
                "variant_label": item.get("variant_label") or "",
                "qty": int(item.get("qty") or 0),
                "price": float(item.get("manual_price") if item.get("manual_price") is not None else item.get("price") or 0),
                "total": (
                    float(item.get("manual_price") if item.get("manual_price") is not None else item.get("price") or 0)
                    * int(item.get("qty") or 0)
                ),
            }
            for item in items
        ],
        "receipt_note": "Offline sale. Sync when POS Server is available.",
        "shop_name": (receipt_settings or {}).get("shop_name") or "KAY POS",
    }
    with _connect() as connection:
        connection.execute(
            "INSERT INTO pending_sales (id, created_at, payload, receipt) VALUES (?, ?, ?, ?)",
            (sale_id, created_at, json.dumps(payload, ensure_ascii=False), json.dumps(receipt, ensure_ascii=False)),
        )
    return receipt


def pending_sales() -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, payload, receipt, sync_attempts FROM pending_sales ORDER BY created_at"
        ).fetchall()
    return [
        {
            "id": row[0],
            "payload": json.loads(row[1]),
            "receipt": json.loads(row[2]),
            "sync_attempts": int(row[3] or 0),
        }
        for row in rows
    ]


def mark_synced(sale_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM pending_sales WHERE id = ?", (sale_id,))


def mark_failed(sale_id: str, error: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE pending_sales SET sync_attempts = sync_attempts + 1, last_error = ? WHERE id = ?",
            (str(error or "")[:500], sale_id),
        )
