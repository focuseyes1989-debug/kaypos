"""Tests for browser cashier product listing stock state."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from server import cashier_service


class CashierProductListingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "pos.db")
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                price REAL,
                cost REAL,
                sku TEXT,
                barcode TEXT,
                stock INTEGER,
                image TEXT,
                sold_by TEXT,
                unit TEXT,
                low_stock INTEGER DEFAULT 0,
                is_favourite INTEGER DEFAULT 0
            );
            CREATE TABLE product_locations (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                location TEXT DEFAULT '',
                batch_no TEXT DEFAULT '',
                expire_date TEXT DEFAULT '',
                quantity INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                type TEXT,
                quantity INTEGER,
                old_stock INTEGER,
                new_stock INTEGER,
                reason TEXT,
                reference TEXT,
                created_by TEXT,
                notes TEXT
            );
            """
        )
        cursor.executemany(
            """
            INSERT INTO products
                (id, name, category, price, cost, sku, barcode, stock, image, sold_by, unit, is_favourite)
            VALUES (?, ?, 'Snacks', 1000, 0, '', '', ?, '', ?, '', 0)
            """,
            [
                (1, "Zero Stock", 0, "Each"),
                (2, "Location Stock", 5, "Each"),
                (3, "Service Item", 0, "Service"),
                (4, "Phantom Location Stock", 0, "Each"),
            ],
        )
        cursor.execute("INSERT INTO product_locations (product_id, quantity) VALUES (2, 3)")
        cursor.execute("INSERT INTO product_locations (product_id, quantity) VALUES (4, 3)")
        self.conn.commit()
        cashier_service._TABLE_COLUMNS_CACHE.clear()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()
        cashier_service._TABLE_COLUMNS_CACHE.clear()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    @patch("server.cashier_service._active_product_discounts", return_value={})
    @patch("server.cashier_service._price_tiers_for_products", return_value={})
    @patch("server.cashier_service._product_thumbnail_url", return_value="/product-images/thumbnails/thumb.jpg")
    def test_list_products_marks_only_sale_unavailable_products_out_of_stock(self, *_mocks) -> None:
        with patch("server.cashier_service.connect_db", self._connect):
            products = {row["name"]: row for row in cashier_service.list_products(limit=10)}

        self.assertEqual(products["Zero Stock"]["stock"], 0)
        self.assertTrue(products["Zero Stock"]["is_out_of_stock"])
        self.assertEqual(products["Zero Stock"]["thumbnail_url"], "/product-images/thumbnails/thumb.jpg")
        self.assertEqual(products["Location Stock"]["stock"], 3)
        self.assertFalse(products["Location Stock"]["is_out_of_stock"])
        self.assertEqual(products["Phantom Location Stock"]["stock"], 0)
        self.assertTrue(products["Phantom Location Stock"]["is_out_of_stock"])
        self.assertTrue(products["Service Item"]["is_service"])
        self.assertFalse(products["Service Item"]["is_out_of_stock"])

    @patch("server.cashier_service._active_product_discounts", return_value={})
    @patch("server.cashier_service._price_tiers_for_products", return_value={})
    def test_list_products_filters_selected_category_only(self, *_mocks) -> None:
        cursor = self.conn.cursor()
        cursor.execute("UPDATE products SET category = 'Drinks ' WHERE id = 2")
        self.conn.commit()

        with patch("server.cashier_service.connect_db", self._connect):
            products = cashier_service.list_products(category="Drinks", limit=10)

        self.assertEqual([product["name"] for product in products], ["Location Stock"])

    @patch("server.cashier_service._active_product_discounts", return_value={})
    @patch("server.cashier_service._price_tiers_for_products", return_value={})
    @patch("server.cashier_service._product_thumbnail_url", return_value="")
    def test_list_products_search_is_case_insensitive(self, *_mocks) -> None:
        with patch("server.cashier_service.connect_db", self._connect):
            products = cashier_service.list_products(search="location stock", limit=10)

        self.assertEqual(
            [product["name"] for product in products],
            ["Location Stock", "Phantom Location Stock"],
        )

    def test_clamp_location_stock_removes_phantom_quantity_above_master_stock(self) -> None:
        from models.database.stock_audit import clamp_location_stock_to_master

        cursor = self.conn.cursor()
        fixed = clamp_location_stock_to_master(cursor, product_id=4, created_by="Test")
        self.conn.commit()

        cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM product_locations WHERE product_id = 4")
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor.execute("SELECT stock FROM products WHERE id = 4")
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor.execute("SELECT reason, quantity, old_stock, new_stock FROM stock_movements WHERE product_id = 4")
        self.assertEqual(cursor.fetchone(), ("Location Stock Clamp", 3, 3, 0))
        self.assertEqual(fixed[0]["removed"], 3)

    @patch("server.cashier_service.is_postgres_backend", return_value=False)
    def test_create_mobile_product_generates_sku_when_blank(self, _mock_backend) -> None:
        with patch("server.cashier_service.connect_db", self._connect):
            product = cashier_service.create_mobile_product(
                name="Mobile Added",
                sku="",
                price=1500,
            )

        self.assertEqual(product["sku"], "ITM-00005")

        cursor = self.conn.cursor()
        cursor.execute("SELECT sku FROM products WHERE id = ?", (product["id"],))
        self.assertEqual(cursor.fetchone()[0], "ITM-00005")

    @patch("server.cashier_service.is_postgres_backend", return_value=False)
    def test_create_mobile_product_keeps_manual_sku(self, _mock_backend) -> None:
        with patch("server.cashier_service.connect_db", self._connect):
            product = cashier_service.create_mobile_product(
                name="Manual SKU",
                sku="CUSTOM-001",
                price=1500,
            )

        self.assertEqual(product["sku"], "CUSTOM-001")

        cursor = self.conn.cursor()
        cursor.execute("SELECT sku FROM products WHERE id = ?", (product["id"],))
        self.assertEqual(cursor.fetchone()[0], "CUSTOM-001")


if __name__ == "__main__":
    unittest.main()
