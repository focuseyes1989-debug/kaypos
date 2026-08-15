"""Helpers for storing receipt logo and QR images in settings."""

import base64
import mimetypes
import os
import shutil

from loguru import logger

from models.database import connect_db
from utils.paths import get_db_dir


RECEIPT_IMAGE_SETTINGS = {
    "logo": {
        "path_key": "shop_logo",
        "data_key": "shop_logo_image",
        "filename": "shop_logo",
        "default_ext": ".png",
    },
    "qr": {
        "path_key": "shop_qr_code",
        "data_key": "shop_qr_code_image",
        "filename": "shop_qr",
        "default_ext": ".png",
    },
}


def _image_config(image_type):
    config = RECEIPT_IMAGE_SETTINGS.get(image_type)
    if not config:
        raise ValueError(f"Unsupported receipt image type: {image_type}")
    return config


def _receipt_images_dir():
    directory = os.path.join(get_db_dir(), "images")
    os.makedirs(directory, exist_ok=True)
    return directory


def _managed_image_path(image_type, source_path=None, mime_type=None):
    config = _image_config(image_type)
    ext = os.path.splitext(source_path or "")[1].lower()
    if not ext and mime_type:
        ext = mimetypes.guess_extension(mime_type) or ""
    if ext == ".jpe":
        ext = ".jpg"
    if not ext:
        ext = config["default_ext"]
    return os.path.join(_receipt_images_dir(), f"{config['filename']}{ext}")


def _image_to_data_url(image_path):
    mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _data_url_to_bytes(data_url):
    if not data_url:
        return None, None
    header, separator, payload = data_url.partition(",")
    if not separator:
        return None, None
    mime_type = "image/png"
    if header.startswith("data:") and ";base64" in header:
        mime_type = header[5:].split(";", 1)[0] or mime_type
    try:
        return base64.b64decode(payload), mime_type
    except Exception as exc:
        logger.error(f"Failed to decode receipt image data: {exc}")
        return None, None


def save_receipt_image(image_type, source_path):
    """Copy an image into the app data folder and store its bytes in settings."""
    config = _image_config(image_type)
    dest_path = _managed_image_path(image_type, source_path)
    if os.path.abspath(source_path) != os.path.abspath(dest_path):
        shutil.copyfile(source_path, dest_path)
    data_url = _image_to_data_url(dest_path)

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (config["path_key"], dest_path),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (config["data_key"], data_url),
    )
    conn.commit()
    conn.close()
    return dest_path


def clear_receipt_image(image_type, remove_file=False):
    """Clear the stored image path and image data from settings."""
    config = _image_config(image_type)
    current_path = resolve_receipt_image_path(image_type, restore_missing=False)

    conn = connect_db()
    cursor = conn.cursor()
    for key in (config["path_key"], config["data_key"]):
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, ""))
    conn.commit()
    conn.close()

    if remove_file and current_path:
        try:
            managed_dir = os.path.abspath(_receipt_images_dir())
            abs_path = os.path.abspath(current_path)
            if os.path.commonpath([managed_dir, abs_path]) == managed_dir and os.path.exists(abs_path):
                os.remove(abs_path)
        except Exception as exc:
            logger.warning(f"Could not remove receipt image file: {exc}")


def resolve_receipt_image_path(image_type, restore_missing=True):
    """Return a usable local path, restoring it from DB image bytes if needed."""
    config = _image_config(image_type)
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, value FROM settings WHERE key IN (?, ?)",
            (config["path_key"], config["data_key"]),
        )
        settings = dict(cursor.fetchall())
        conn.close()
    except Exception as exc:
        logger.error(f"Failed to load receipt image settings: {exc}")
        return ""

    path = settings.get(config["path_key"], "") or ""
    if path and os.path.exists(path):
        return path
    if not restore_missing:
        return ""

    image_bytes, mime_type = _data_url_to_bytes(settings.get(config["data_key"], ""))
    if not image_bytes:
        return ""

    dest_path = _managed_image_path(image_type, path, mime_type)
    try:
        with open(dest_path, "wb") as image_file:
            image_file.write(image_bytes)
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (config["path_key"], dest_path),
        )
        conn.commit()
        conn.close()
        return dest_path
    except Exception as exc:
        logger.error(f"Failed to restore receipt image file: {exc}")
        return ""
