import unittest
import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import patch

from utils.telegram_service import (
    TelegramCommandListener,
    _get_message_command_text,
    _get_message_image_file_id,
    add_product_from_telegram_command,
    get_telegram_command,
    is_add_item_command,
    is_database_backup_command,
    parse_add_item_command,
)


class TelegramServiceTests(unittest.TestCase):
    def test_backup_commands_accept_bot_suffix(self):
        self.assertEqual(get_telegram_command("/db@ZayPosBot extra"), "/db")
        self.assertTrue(is_database_backup_command("/backup"))
        self.assertTrue(is_database_backup_command("/db@ZayPosBot"))

    def test_non_backup_commands_are_ignored(self):
        self.assertFalse(is_database_backup_command(""))
        self.assertFalse(is_database_backup_command("/start"))
        self.assertFalse(is_database_backup_command("hello"))

    def test_add_item_commands_accept_bot_suffix(self):
        self.assertTrue(is_add_item_command("/additem"))
        self.assertTrue(is_add_item_command("/addproduct@ZayPosBot name=Tea"))

    def test_parse_add_item_command(self):
        product = parse_add_item_command(
            '/additem name="Coffee Bean" category=Drinks price=2,500 '
            "barcode=123456 low_stock=5 description=Hot"
        )

        self.assertEqual(product["name"], "Coffee Bean")
        self.assertEqual(product["category"], "Drinks")
        self.assertEqual(product["price"], 2500)
        self.assertEqual(product["barcode"], "123456")
        self.assertEqual(product["low_stock"], 5)
        self.assertEqual(product["description"], "Hot")

    def test_parse_add_item_requires_name(self):
        with self.assertRaisesRegex(Exception, "Product name is required"):
            parse_add_item_command("/additem category=Drinks price=2500")

    def test_add_item_can_be_read_from_photo_caption(self):
        message = {
            "caption": "/additem name=Coffee category=Drinks price=2500",
            "photo": [
                {"file_id": "small", "file_size": 10, "width": 50, "height": 50},
                {"file_id": "large", "file_size": 20, "width": 400, "height": 400},
            ],
        }

        self.assertEqual(
            _get_message_command_text(message),
            "/additem name=Coffee category=Drinks price=2500",
        )
        self.assertEqual(_get_message_image_file_id(message), "large")

    def test_add_product_from_telegram_command_creates_product_and_category(self):
        with TemporaryDirectory() as temp_dir:
            db_path = f"{temp_dir}/pos.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    category TEXT,
                    description TEXT,
                    sold_by TEXT DEFAULT 'Each',
                    price REAL DEFAULT 0,
                    cost REAL DEFAULT 0,
                    sku TEXT,
                    barcode TEXT,
                    stock INTEGER DEFAULT 0,
                    expire_date TEXT,
                    low_stock INTEGER DEFAULT 0,
                    image TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()

            with patch("utils.telegram_service.connect_db", lambda: sqlite3.connect(db_path)), patch(
                "utils.telegram_service.format_money", lambda value: f"Ks{int(value)}"
            ):
                result = add_product_from_telegram_command(
                    "/additem name=Coffee category=Drinks price=2500 barcode=123456 low_stock=5",
                    image_path="database/product_images/product_test.jpg",
                )

            conn = sqlite3.connect(db_path)
            product = conn.execute(
                "SELECT name, category, price, barcode, low_stock, sku, image FROM products"
            ).fetchone()
            category = conn.execute("SELECT name FROM categories").fetchone()
            conn.close()

        self.assertIn("Product added successfully", result)
        self.assertIn("Image: saved", result)
        self.assertEqual(
            product,
            (
                "Coffee",
                "Drinks",
                2500,
                "123456",
                5,
                "ITM-00001",
                "database/product_images/product_test.jpg",
            ),
        )
        self.assertEqual(category, ("Drinks",))

    def test_listener_reports_stale_after_poll_without_success(self):
        listener = TelegramCommandListener(stale_after=0)
        listener._mark_poll_started()
        self.assertFalse(listener.is_healthy())


if __name__ == "__main__":
    unittest.main()
