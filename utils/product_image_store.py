"""Shared product image storage for multi-client PostgreSQL deployments."""

from __future__ import annotations

import mimetypes
import os
from typing import Optional

from loguru import logger

from models.database import connect_db
from utils.db_compat import ensure_column, is_postgres_backend
from utils.paths import app_path, get_product_images_dir


def ensure_product_image_blob_schema(cursor) -> None:
    """Ensure product image binary columns exist."""
    image_data_type = "BYTEA" if is_postgres_backend() else "BLOB"
    ensure_column(cursor, "products", "image_data", image_data_type)
    ensure_column(cursor, "products", "image_mime", "TEXT")
    ensure_column(cursor, "products", "image_filename", "TEXT")


def save_product_image_blob(cursor, product_id: int, image_path: str) -> None:
    """Store a product image file in the database for client PCs."""
    if not product_id or not image_path:
        return

    resolved_path = _resolve_local_image_path(image_path)
    if not resolved_path or not os.path.exists(resolved_path):
        return

    try:
        ensure_product_image_blob_schema(cursor)
        with open(resolved_path, "rb") as image_file:
            image_data = image_file.read()

        filename = os.path.basename(resolved_path)
        mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        cursor.execute(
            """
            UPDATE products
            SET image_data = ?, image_mime = ?, image_filename = ?
            WHERE id = ?
            """,
            (image_data, mime_type, filename, product_id),
        )
    except Exception as exc:
        logger.warning(f"Could not store product image in database: {exc}")


def cached_product_image_path(product_id: Optional[int] = None, image_path: str = "") -> str:
    """Return a local cache path for image bytes stored in the database."""
    row = _fetch_image_row(product_id, image_path)
    if not row:
        return ""

    db_product_id, image_filename, db_image_path, image_mime, image_data = row
    if not image_data:
        return ""

    if isinstance(image_data, memoryview):
        image_data = image_data.tobytes()
    elif not isinstance(image_data, bytes):
        image_data = bytes(image_data)

    filename = image_filename or os.path.basename(str(db_image_path or image_path or ""))
    if not filename:
        extension = mimetypes.guess_extension(str(image_mime or "")) or ".jpg"
        filename = f"product_{db_product_id}{extension}"

    safe_filename = f"{db_product_id}_{os.path.basename(filename)}"
    cache_dir = app_path("database", "product_images", "db_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, safe_filename)

    try:
        if not os.path.exists(cache_path) or os.path.getsize(cache_path) != len(image_data):
            with open(cache_path, "wb") as cache_file:
                cache_file.write(image_data)
        return cache_path
    except Exception as exc:
        logger.warning(f"Could not cache database product image: {exc}")
        return ""


def _fetch_image_row(product_id: Optional[int], image_path: str):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        ensure_product_image_blob_schema(cursor)
        if product_id:
            cursor.execute(
                """
                SELECT id, image_filename, image, image_mime, image_data
                FROM products
                WHERE id = ? AND image_data IS NOT NULL
                """,
                (product_id,),
            )
        else:
            filename = os.path.basename(str(image_path or ""))
            cursor.execute(
                """
                SELECT id, image_filename, image, image_mime, image_data
                FROM products
                WHERE image_data IS NOT NULL
                  AND (image = ? OR image_filename = ? OR image LIKE ?)
                ORDER BY id
                LIMIT 1
                """,
                (image_path, filename, f"%{filename}") if filename else (image_path, "", ""),
            )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as exc:
        logger.debug(f"Product image database lookup skipped: {exc}")
        return None


def _resolve_local_image_path(image_path: str) -> str:
    raw_path = str(image_path or "").strip().strip('"')
    if not raw_path:
        return ""

    normalized = raw_path.replace("\\", os.sep).replace("/", os.sep)
    filename = os.path.basename(normalized)
    candidates = []

    if os.path.isabs(normalized):
        candidates.append(normalized)
    else:
        candidates.extend([
            app_path(normalized),
            os.path.join(os.getcwd(), normalized),
        ])

    if filename:
        candidates.append(os.path.join(get_product_images_dir(), filename))

    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            if os.path.exists(candidate):
                return candidate
    return ""
