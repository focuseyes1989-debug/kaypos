"""Telegram integration helpers for reports, backups, and remote product entry."""

from __future__ import annotations

import os
import json
import shlex
import sqlite3
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

import requests
from loguru import logger

from models.database import connect_db
from utils.currency import format_money


TELEGRAM_ENV_KEYS = {
    "TELEGRAM_ENABLED",
    "TELEGRAM_LISTENER_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
}
TELEGRAM_BACKUP_COMMANDS = {"/backup", "/db"}
TELEGRAM_ADD_ITEM_COMMANDS = {"/additem", "/addproduct"}
ADD_ITEM_USAGE = (
    'Usage: /additem name="Coffee" category=Drinks price=2500 '
    "barcode=123456 low_stock=5"
)
ADD_ITEM_FIELDS = {
    "name",
    "category",
    "price",
    "barcode",
    "low_stock",
    "description",
    "sold_by",
    "stock",
    "cost",
}
TELEGRAM_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
TELEGRAM_IMAGE_MAX_BYTES = 20 * 1024 * 1024


class TelegramError(RuntimeError):
    """Raised when Telegram configuration or API calls fail."""


@dataclass
class TelegramConfig:
    enabled: bool = False
    listener_enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


def get_app_base_dir() -> Path:
    """Return the writable app directory for source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_env_path() -> Path:
    return get_app_base_dir() / ".env"


def _parse_bool(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_env_file(path: Optional[Path] = None) -> Dict[str, str]:
    env_path = path or get_env_path()
    if not env_path.exists():
        return {}

    values: Dict[str, str] = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    except OSError as exc:
        logger.warning(f"Could not read Telegram .env settings: {exc}")
    return values


def load_telegram_config() -> TelegramConfig:
    file_values = _read_env_file()

    def get_value(key: str) -> str:
        return os.environ.get(key, file_values.get(key, "")).strip()

    return TelegramConfig(
        enabled=_parse_bool(get_value("TELEGRAM_ENABLED")),
        listener_enabled=_parse_bool(get_value("TELEGRAM_LISTENER_ENABLED")),
        bot_token=get_value("TELEGRAM_BOT_TOKEN"),
        chat_id=get_value("TELEGRAM_CHAT_ID"),
    )


def save_telegram_config(config: TelegramConfig) -> Path:
    """Save Telegram settings to the ignored local .env file."""
    env_path = get_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    existing_lines = []
    if env_path.exists():
        try:
            existing_lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            existing_lines = []

    preserved = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            preserved.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key not in TELEGRAM_ENV_KEYS:
            preserved.append(line)

    if preserved and preserved[-1].strip():
        preserved.append("")

    preserved.extend(
        [
            f"TELEGRAM_ENABLED={'1' if config.enabled else '0'}",
            f"TELEGRAM_LISTENER_ENABLED={'1' if config.listener_enabled else '0'}",
            f"TELEGRAM_BOT_TOKEN={config.bot_token.strip()}",
            f"TELEGRAM_CHAT_ID={config.chat_id.strip()}",
        ]
    )

    env_path.write_text("\n".join(preserved) + "\n", encoding="utf-8")
    logger.info(f"Telegram settings saved to {env_path}")
    return env_path


def _require_config() -> TelegramConfig:
    config = load_telegram_config()
    if not config.enabled:
        raise TelegramError("Telegram integration is disabled.")
    if not config.bot_token:
        raise TelegramError("Telegram bot token is missing.")
    if not config.chat_id:
        raise TelegramError("Telegram chat ID is missing.")
    return config


def _telegram_post(
    method: str,
    *,
    data: Optional[dict] = None,
    files: Optional[dict] = None,
    timeout: int = 30,
    config: Optional[TelegramConfig] = None,
) -> dict:
    config = config or _require_config()
    url = f"https://api.telegram.org/bot{config.bot_token}/{method}"
    payload = {"chat_id": config.chat_id}
    if data:
        payload.update(data)

    try:
        response = requests.post(url, data=payload, files=files, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning(f"Telegram request failed: {exc.__class__.__name__}")
        raise TelegramError(
            f"Network error while contacting Telegram ({exc.__class__.__name__})."
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramError(f"Telegram returned a non-JSON response ({response.status_code}).") from exc

    if not response.ok or not body.get("ok"):
        description = body.get("description") or response.reason or "Unknown error"
        raise TelegramError(f"Telegram API error {response.status_code}: {description}")

    return body.get("result", {})


def _telegram_bot_post(
    method: str,
    config: TelegramConfig,
    *,
    data: Optional[dict] = None,
    timeout: int = 30,
) -> dict:
    """Call a bot API method that does not need the configured chat_id payload."""
    url = f"https://api.telegram.org/bot{config.bot_token}/{method}"
    try:
        response = requests.post(url, data=data or {}, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning(f"Telegram request failed: {exc.__class__.__name__}")
        raise TelegramError(
            f"Network error while contacting Telegram ({exc.__class__.__name__})."
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramError(f"Telegram returned a non-JSON response ({response.status_code}).") from exc

    if not response.ok or not body.get("ok"):
        description = body.get("description") or response.reason or "Unknown error"
        raise TelegramError(f"Telegram API error {response.status_code}: {description}")

    return body.get("result", {})


def _normalize_chat_id(chat_id) -> str:
    return str(chat_id or "").strip()


def _get_message_command_text(message: dict) -> str:
    """Return text or caption content that can contain a Telegram command."""
    return (message.get("text") or message.get("caption") or "").strip()


def _get_message_image_file_id(message: dict) -> str:
    """Return the best Telegram file_id from an attached photo/image document."""
    photos = message.get("photo") or []
    if photos:
        best_photo = max(
            photos,
            key=lambda photo: (
                int(photo.get("file_size") or 0),
                int(photo.get("width") or 0) * int(photo.get("height") or 0),
            ),
        )
        return str(best_photo.get("file_id") or "").strip()

    document = message.get("document") or {}
    if not document:
        return ""

    mime_type = str(document.get("mime_type") or "").lower()
    filename = str(document.get("file_name") or "").lower()
    extension = Path(filename).suffix
    if mime_type.startswith("image/") or extension in TELEGRAM_IMAGE_EXTENSIONS:
        return str(document.get("file_id") or "").strip()
    return ""


def get_telegram_command(text: str) -> str:
    """Return the first Telegram command token, normalized for bot-name suffixes."""
    if not text:
        return ""
    first_token = text.strip().split(maxsplit=1)[0].lower()
    return first_token.split("@", 1)[0]


def is_database_backup_command(text: str) -> bool:
    return get_telegram_command(text) in TELEGRAM_BACKUP_COMMANDS


def is_add_item_command(text: str) -> bool:
    return get_telegram_command(text) in TELEGRAM_ADD_ITEM_COMMANDS


def _normalize_add_item_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _parse_money(value: str, field_name: str) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise TelegramError(f"{field_name} must be a number.") from exc


def _parse_int(value: str, field_name: str) -> int:
    try:
        parsed = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError) as exc:
        raise TelegramError(f"{field_name} must be a whole number.") from exc
    if parsed < 0:
        raise TelegramError(f"{field_name} cannot be negative.")
    return parsed


def _parse_sold_by(value: str) -> str:
    normalized = str(value or "Each").strip().lower()
    if normalized in {"each", "item", "unit", "pcs", "piece"}:
        return "Each"
    if normalized in {"service", "svc"}:
        return "Service"
    raise TelegramError("sold_by must be Each or Service.")


def parse_add_item_command(text: str) -> dict:
    """Parse a Telegram /additem command into validated product fields."""
    if not is_add_item_command(text):
        raise TelegramError("Unsupported add item command.")

    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        raise TelegramError(ADD_ITEM_USAGE)

    try:
        tokens = shlex.split(parts[1])
    except ValueError as exc:
        raise TelegramError(f"Could not parse command: {exc}") from exc

    fields: dict[str, str] = {}
    positional_name_parts: list[str] = []
    for token in tokens:
        if "=" not in token:
            positional_name_parts.append(token)
            continue

        key, value = token.split("=", 1)
        normalized_key = _normalize_add_item_key(key)
        if normalized_key not in ADD_ITEM_FIELDS:
            raise TelegramError(f"Unknown add item field: {key}")
        fields[normalized_key] = value.strip()

    if positional_name_parts and "name" not in fields:
        fields["name"] = " ".join(positional_name_parts).strip()
    elif positional_name_parts:
        raise TelegramError(f"Unexpected text after name field. {ADD_ITEM_USAGE}")

    name = fields.get("name", "").strip()
    if not name:
        raise TelegramError(f"Product name is required. {ADD_ITEM_USAGE}")

    category = fields.get("category", "").strip() or "General"
    barcode = fields.get("barcode", "").strip()
    description = fields.get("description", "").strip()
    sold_by = _parse_sold_by(fields.get("sold_by", "Each"))
    price = _parse_money(fields.get("price", "0"), "price")
    cost = _parse_money(fields.get("cost", "0"), "cost")
    stock = _parse_int(fields.get("stock", "0"), "stock")
    low_stock = _parse_int(fields.get("low_stock", "0"), "low_stock")

    if price < 0:
        raise TelegramError("price cannot be negative.")
    if cost < 0:
        raise TelegramError("cost cannot be negative.")
    if sold_by == "Service":
        stock = 0
        low_stock = 0

    return {
        "name": name,
        "category": category,
        "barcode": barcode,
        "description": description,
        "sold_by": sold_by,
        "price": price,
        "cost": cost,
        "stock": stock,
        "low_stock": low_stock,
    }


def _generate_product_sku(cursor) -> str:
    cursor.execute("SELECT id FROM products ORDER BY id DESC LIMIT 1")
    last = cursor.fetchone()
    next_id = int(last[0]) + 1 if last else 1
    return f"ITM-{next_id:05d}"


def add_product_from_telegram_command(text: str, image_path: str = "") -> str:
    """Create a product from a trusted Telegram /additem command."""
    product = parse_add_item_command(text)

    conn = connect_db()
    try:
        cursor = conn.cursor()
        if product["barcode"]:
            cursor.execute(
                "SELECT id, name FROM products WHERE barcode = ?",
                (product["barcode"],),
            )
            existing = cursor.fetchone()
            if existing:
                raise TelegramError(
                    f"Barcode {product['barcode']} already exists for product: {existing[1]}"
                )

        cursor.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            (product["category"],),
        )

        sku = _generate_product_sku(cursor)
        cursor.execute(
            """
            INSERT INTO products (name, category, description, sold_by, price, cost, sku,
                                  barcode, stock, low_stock, expire_date, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product["name"],
                product["category"],
                product["description"],
                product["sold_by"],
                product["price"],
                product["cost"],
                sku,
                product["barcode"],
                product["stock"],
                product["low_stock"],
                None,
                image_path,
            ),
        )
        product_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    price_text = format_money(product["price"])
    image_text = "\nImage: saved" if image_path else ""
    return (
        "Product added successfully.\n"
        f"Name: {product['name']}\n"
        f"SKU: {sku}\n"
        f"Category: {product['category']}\n"
        f"Price: {price_text}\n"
        f"Product ID: {product_id}"
        f"{image_text}"
    )


def send_message(text: str, *, disable_notification: bool = False) -> dict:
    data = {
        "text": text,
        "disable_notification": "true" if disable_notification else "false",
    }
    return _telegram_post("sendMessage", data=data, timeout=20)


def send_document(file_path: str | os.PathLike[str], caption: str = "") -> dict:
    path = Path(file_path)
    if not path.exists():
        raise TelegramError(f"File not found: {path}")

    with path.open("rb") as handle:
        files = {"document": (path.name, handle)}
        return _telegram_post("sendDocument", data={"caption": caption}, files=files, timeout=120)


def download_telegram_product_image(file_id: str, config: TelegramConfig) -> str:
    """Download a Telegram image and store it as a relative product image path."""
    if not file_id:
        return ""

    file_info = _telegram_bot_post(
        "getFile",
        config,
        data={"file_id": file_id},
        timeout=30,
    )
    telegram_file_path = str(file_info.get("file_path") or "").strip()
    if not telegram_file_path:
        raise TelegramError("Telegram image file path was not returned.")

    file_size = int(file_info.get("file_size") or 0)
    if file_size > TELEGRAM_IMAGE_MAX_BYTES:
        max_mb = TELEGRAM_IMAGE_MAX_BYTES // (1024 * 1024)
        raise TelegramError(f"Image is too large. Maximum size is {max_mb} MB.")

    extension = Path(telegram_file_path).suffix.lower()
    if extension not in TELEGRAM_IMAGE_EXTENSIONS:
        extension = ".jpg"

    temp_dir = get_app_base_dir() / "temp" / "telegram_images"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"telegram_product_{uuid.uuid4().hex}{extension}"
    url = f"https://api.telegram.org/file/bot{config.bot_token}/{telegram_file_path}"

    try:
        with requests.get(url, stream=True, timeout=60) as response:
            if not response.ok:
                raise TelegramError(
                    f"Telegram image download failed ({response.status_code})."
                )

            downloaded = 0
            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > TELEGRAM_IMAGE_MAX_BYTES:
                        raise TelegramError("Image is too large.")
                    handle.write(chunk)

        from utils.image_optimizer import ImageOptimizer
        from utils.paths import app_relative_path

        optimized_path = ImageOptimizer.optimize_image(
            str(temp_path),
            output_size=(400, 400),
            quality=80,
            output_format="JPEG",
        )
        return app_relative_path(optimized_path)
    except requests.RequestException as exc:
        logger.warning(f"Telegram image download failed: {exc.__class__.__name__}")
        raise TelegramError(
            f"Network error while downloading Telegram image ({exc.__class__.__name__})."
        ) from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"Could not remove Telegram temp image: {exc}")


def send_test_message() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_message(f"ZAY POS Telegram test message\nTime: {now}")
    return "Test message sent."


def _fetch_one(cursor, query: str, params: Iterable = ()):
    cursor.execute(query, tuple(params))
    return cursor.fetchone()


def build_today_sales_summary(today: Optional[str] = None) -> str:
    report_date = today or datetime.now().strftime("%Y-%m-%d")

    conn = connect_db()
    try:
        cursor = conn.cursor()
        sales = _fetch_one(
            cursor,
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(total), 0),
                COALESCE(SUM(discount_amount), 0),
                COALESCE(SUM(cogs), 0),
                COALESCE(SUM(gross_profit), 0),
                COALESCE(SUM(net_profit), 0)
            FROM sales
            WHERE status = 'completed' AND date(created_at) = ?
            """,
            (report_date,),
        )
        sale_count, total_sales, discounts, cogs, gross_profit, net_profit = sales

        cursor.execute(
            """
            SELECT COALESCE(payment_type, 'Unknown'), COUNT(*), COALESCE(SUM(total), 0)
            FROM sales
            WHERE status = 'completed' AND date(created_at) = ?
            GROUP BY COALESCE(payment_type, 'Unknown')
            ORDER BY SUM(total) DESC
            """,
            (report_date,),
        )
        payments = cursor.fetchall()

        cursor.execute(
            """
            SELECT si.product_name, COALESCE(SUM(si.qty), 0), COALESCE(SUM(si.total), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.status = 'completed' AND date(s.created_at) = ?
            GROUP BY si.product_name
            ORDER BY SUM(si.total) DESC
            LIMIT 5
            """,
            (report_date,),
        )
        top_items = cursor.fetchall()

        cursor.execute(
            """
            SELECT name, stock, low_stock
            FROM products
            WHERE low_stock > 0 AND stock <= low_stock
            ORDER BY stock ASC, name ASC
            LIMIT 5
            """
        )
        low_stock_items = cursor.fetchall()
    finally:
        conn.close()

    lines = [
        "ZAY POS Daily Sales Summary",
        f"Date: {report_date}",
        "",
        f"Receipts: {sale_count}",
        f"Total sales: {format_money(total_sales)}",
        f"Discounts: {format_money(discounts)}",
        f"COGS: {format_money(cogs)}",
        f"Gross profit: {format_money(gross_profit)}",
        f"Net profit: {format_money(net_profit)}",
    ]

    if payments:
        lines.extend(["", "Payment methods:"])
        for method, count, amount in payments:
            lines.append(f"- {method}: {count} sale(s), {format_money(amount)}")

    if top_items:
        lines.extend(["", "Top items:"])
        for name, qty, amount in top_items:
            lines.append(f"- {name}: {qty:g} qty, {format_money(amount)}")

    if low_stock_items:
        lines.extend(["", "Low stock:"])
        for name, stock, low_stock in low_stock_items:
            lines.append(f"- {name}: {stock}/{low_stock}")

    return "\n".join(lines)


def send_today_sales_summary() -> str:
    summary = build_today_sales_summary()
    send_message(summary)
    return "Today sales summary sent."


def get_sqlite_db_path() -> Path:
    from models.database.connection import DB_NAME

    db_path = Path(DB_NAME)
    if db_path.is_absolute():
        return db_path
    return get_app_base_dir() / db_path


def create_database_snapshot(output_dir: Optional[str | os.PathLike[str]] = None) -> Path:
    db_path = get_sqlite_db_path()
    if not db_path.exists():
        raise TelegramError(f"Database file not found: {db_path}")

    backup_dir = Path(output_dir) if output_dir else get_app_base_dir() / "temp" / "telegram_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pos_telegram_backup_{timestamp}.db"

    source = sqlite3.connect(str(db_path), timeout=60)
    try:
        try:
            source.execute("PRAGMA wal_checkpoint(FULL)")
        except sqlite3.DatabaseError as exc:
            logger.warning(f"SQLite checkpoint before Telegram backup failed: {exc}")

        destination = sqlite3.connect(str(backup_path))
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
    finally:
        source.close()

    return backup_path


def upload_database_backup(cleanup: bool = True) -> str:
    backup_path = create_database_snapshot()
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = f"ZAY POS SQLite backup\nCreated: {created_at}\nSize: {size_mb:.2f} MB"

    try:
        send_document(backup_path, caption=caption)
    finally:
        if cleanup:
            try:
                backup_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(f"Could not remove Telegram temp backup: {exc}")

    return f"Database backup uploaded ({size_mb:.2f} MB)."


class TelegramCommandListener:
    """Poll Telegram for trusted backup commands while the POS app is running."""

    def __init__(self, poll_timeout: int = 20, idle_interval: int = 10, stale_after: int = 180):
        self.poll_timeout = poll_timeout
        self.idle_interval = idle_interval
        self.stale_after = stale_after
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._restart_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._offset: Optional[int] = None
        self._config_key: Optional[tuple[str, str]] = None
        self._last_poll_at: float = 0.0
        self._last_success_at: float = 0.0
        self._last_update_at: float = 0.0
        self._last_error: str = ""
        self._consecutive_errors = 0
        self._active_task: str = ""
        self._active_task_started_at: float = 0.0
        self._state_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            if self._stop_event.is_set():
                self._restart_event.set()
            self._wake_event.set()
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._restart_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="TelegramCommandListener",
            daemon=True,
        )
        self._thread.start()
        logger.info("Telegram command listener started")

    def restart(self) -> None:
        logger.info("Restarting Telegram command listener")
        self.stop(timeout=5.0)
        self.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the Telegram command listener thread."""
        self._restart_event.clear()
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=timeout)
            # If still alive, set daemon flag and detach
            if self._thread.is_alive():
                logger.warning("Telegram thread still alive after timeout - detaching")
                self._thread.daemon = True
                self._thread = None
        else:
            self._thread = None
        logger.info("Telegram command listener stopped")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def is_healthy(self) -> bool:
        if not self.is_running():
            return False
        status = self.status()
        last_seen = max(status["last_poll_at"], status["last_success_at"], status["last_update_at"])
        if last_seen <= 0:
            return True
        return (time.monotonic() - last_seen) <= self.stale_after

    def status(self) -> dict:
        with self._state_lock:
            return {
                "running": self.is_running(),
                "last_poll_at": self._last_poll_at,
                "last_success_at": self._last_success_at,
                "last_update_at": self._last_update_at,
                "last_error": self._last_error,
                "consecutive_errors": self._consecutive_errors,
                "active_task": self._active_task,
                "active_task_started_at": self._active_task_started_at,
            }

    def _run(self) -> None:
        while True:
            while not self._stop_event.is_set():
                try:
                    config = load_telegram_config()
                    if not config.enabled or not config.bot_token or not config.chat_id:
                        if self._config_key is not None:
                            logger.info("Telegram command listener idle because Telegram is disabled")
                        self._config_key = None
                        self._offset = None
                        self._wait(self.idle_interval)
                        continue

                    config_key = (config.bot_token, config.chat_id)
                    if config_key != self._config_key:
                        self._config_key = config_key
                        self._offset = self._get_initial_offset(config)
                        logger.info(
                            f"Telegram command listener active for chat_id={config.chat_id}"
                        )

                    self._mark_poll_started()
                    updates = self._get_updates(config, self._offset, self.poll_timeout)
                    self._mark_poll_success()
                    if self._stop_event.is_set():
                        break

                    for update in updates:
                        update_id = update.get("update_id")
                        if isinstance(update_id, int):
                            self._offset = update_id + 1
                            self._mark_update_seen()
                        self._handle_update(update, config)
                except TelegramError as exc:
                    self._mark_error(str(exc))
                    logger.warning(f"Telegram command listener error: {exc}")
                    self._wait(self.idle_interval)
                except Exception as exc:
                    self._mark_error(str(exc))
                    logger.exception(f"Unexpected Telegram command listener error: {exc}")
                    self._wait(self.idle_interval)

            if not self._restart_event.is_set():
                break

            self._restart_event.clear()
            self._stop_event.clear()
            self._wake_event.clear()
            self._offset = None
            self._config_key = None

    def _mark_poll_started(self) -> None:
        with self._state_lock:
            self._last_poll_at = time.monotonic()

    def _mark_poll_success(self) -> None:
        with self._state_lock:
            self._last_success_at = time.monotonic()
            self._last_error = ""
            self._consecutive_errors = 0

    def _mark_update_seen(self) -> None:
        with self._state_lock:
            self._last_update_at = time.monotonic()

    def _mark_error(self, message: str) -> None:
        with self._state_lock:
            self._last_error = message
            self._consecutive_errors += 1

    def _set_active_task(self, message: str) -> None:
        with self._state_lock:
            self._active_task = message
            self._active_task_started_at = time.monotonic()

    def _clear_active_task(self) -> None:
        with self._state_lock:
            self._active_task = ""
            self._active_task_started_at = 0.0

    def _wait(self, seconds: int) -> None:
        self._wake_event.wait(seconds)
        self._wake_event.clear()

    def _get_initial_offset(self, config: TelegramConfig) -> Optional[int]:
        updates = self._get_updates(config, offset=None, timeout=0, limit=100)
        update_ids = [
            update.get("update_id")
            for update in updates
            if isinstance(update.get("update_id"), int)
        ]
        if not update_ids:
            return None
        return max(update_ids) + 1

    def _get_updates(
        self,
        config: TelegramConfig,
        offset: Optional[int],
        timeout: int,
        limit: int = 20,
    ) -> list[dict]:
        data = {
            "timeout": str(timeout),
            "limit": str(limit),
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            data["offset"] = str(offset)

        result = _telegram_bot_post(
            "getUpdates",
            config,
            data=data,
            timeout=timeout + 10,
        )
        return result if isinstance(result, list) else []

    def _handle_update(self, update: dict, config: TelegramConfig) -> None:
        message = update.get("message") or {}
        text = _get_message_command_text(message)
        if not is_database_backup_command(text) and not is_add_item_command(text):
            return

        chat = message.get("chat") or {}
        incoming_chat_id = _normalize_chat_id(chat.get("id"))
        configured_chat_id = _normalize_chat_id(config.chat_id)
        if incoming_chat_id != configured_chat_id:
            logger.warning(
                f"Ignored Telegram command from unauthorized chat_id={incoming_chat_id}"
            )
            return

        if is_add_item_command(text):
            self._handle_add_item_command(text, config, message)
            return

        self._handle_database_backup_command()

    def _handle_database_backup_command(self) -> None:
        logger.info("Telegram database backup command received")
        self._set_active_task("Telegram: preparing database backup")
        try:
            send_message("ZAY POS backup request received. Preparing database file...")
            self._set_active_task("Telegram: uploading database backup")
            result = upload_database_backup()
            self._set_active_task("Telegram: sending backup result")
            send_message(result, disable_notification=True)
            logger.info(result)
        except TelegramError as exc:
            logger.warning(f"Telegram database backup command failed: {exc}")
            self._send_failure_message(f"Database backup failed: {exc}")
        except Exception as exc:
            logger.exception(f"Telegram database backup command failed: {exc}")
            self._send_failure_message(
                "Database backup failed: Unexpected error while preparing database backup."
            )
        finally:
            self._clear_active_task()

    def _handle_add_item_command(
        self,
        text: str,
        config: TelegramConfig,
        message: Optional[dict] = None,
    ) -> None:
        logger.info("Telegram add item command received")
        self._set_active_task("Telegram: adding product")
        try:
            image_file_id = _get_message_image_file_id(message or {})
            image_path = ""
            if image_file_id:
                self._set_active_task("Telegram: downloading product image")
                image_path = download_telegram_product_image(image_file_id, config)
            self._set_active_task("Telegram: saving product")
            result = add_product_from_telegram_command(text, image_path=image_path)
            self._set_active_task("Telegram: sending product result")
            send_message(result, disable_notification=True)
            logger.info(result.replace("\n", " | "))
        except TelegramError as exc:
            logger.warning(f"Telegram add item command failed: {exc}")
            self._send_failure_message(f"Add item failed: {exc}")
        except Exception as exc:
            logger.exception(f"Telegram add item command failed: {exc}")
            self._send_failure_message("Add item failed: Unexpected error while saving product.")
        finally:
            self._clear_active_task()

    def _send_failure_message(self, message: str) -> None:
        try:
            send_message(message)
        except TelegramError as exc:
            logger.warning(f"Could not send Telegram failure message: {exc}")


_command_listener: Optional[TelegramCommandListener] = None


def start_telegram_command_listener() -> Optional[TelegramCommandListener]:
    global _command_listener
    config = load_telegram_config()
    if not config.enabled or not config.listener_enabled:
        logger.info("Telegram command listener is disabled by settings")
        stop_telegram_command_listener()
        return _command_listener
    if _command_listener is None:
        _command_listener = TelegramCommandListener()
    _command_listener.start()
    return _command_listener


def ensure_telegram_command_listener_running() -> Optional[TelegramCommandListener]:
    """Start or recover the Telegram listener if it becomes stale while the app is open."""
    config = load_telegram_config()
    if not config.enabled or not config.listener_enabled:
        stop_telegram_command_listener()
        return None
    listener = start_telegram_command_listener()
    status = listener.status()
    if not listener.is_healthy():
        logger.warning(
            "Telegram command listener appears stale; restarting "
            f"(errors={status['consecutive_errors']}, last_error={status['last_error']!r})"
        )
        listener.restart()
    elif status["consecutive_errors"] >= 6:
        logger.warning(
            "Telegram command listener has repeated errors; restarting "
            f"(last_error={status['last_error']!r})"
        )
        listener.restart()
    return listener


def stop_telegram_command_listener() -> None:
    """Stop the Telegram command listener."""
    global _command_listener
    if _command_listener is not None:
        _command_listener.stop()
        _command_listener = None
        logger.info("Telegram command listener reference cleared")


def get_masked_token() -> str:
    token = load_telegram_config().bot_token
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:6]}...{token[-4:]}"
