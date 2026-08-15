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
                quantity INTEGER
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
    def test_list_products_marks_only_sale_unavailable_products_out_of_stock(self, *_mocks) -> None:
        with patch("server.cashier_service.connect_db", self._connect):
            products = {row["name"]: row for row in cashier_service.list_products(limit=10)}

        self.assertEqual(products["Zero Stock"]["stock"], 0)
        self.assertTrue(products["Zero Stock"]["is_out_of_stock"])
        self.assertEqual(products["Location Stock"]["stock"], 3)
        self.assertFalse(products["Location Stock"]["is_out_of_stock"])
        self.assertEqual(products["Phantom Location Stock"]["stock"], 0)
        self.assertTrue(products["Phantom Location Stock"]["is_out_of_stock"])
        self.assertTrue(products["Service Item"]["is_service"])
        self.assertFalse(products["Service Item"]["is_out_of_stock"])


if __name__ == "__main__":
    unittest.main()
