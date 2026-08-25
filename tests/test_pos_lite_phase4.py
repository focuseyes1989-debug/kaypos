import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from server import cashier_service


class PosLitePhase4RefundTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "refund.db")
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY, invoice_no TEXT, created_at TEXT, total REAL,
                payment REAL, change_amount REAL, payment_type TEXT, status TEXT,
                customer_id INTEGER
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY, name TEXT, stock INTEGER, last_updated TEXT, sold_by TEXT
            );
            CREATE TABLE product_variants (
                id INTEGER PRIMARY KEY, product_id INTEGER, stock INTEGER, updated_at TEXT, active INTEGER DEFAULT 1
            );
            CREATE TABLE product_locations (
                id INTEGER PRIMARY KEY, product_id INTEGER, location TEXT, batch_no TEXT,
                expire_date TEXT, quantity INTEGER, last_updated TEXT
            );
            CREATE TABLE sale_items (
                id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, variant_id INTEGER,
                product_name TEXT, qty INTEGER, price REAL, total REAL, cost REAL,
                location_id INTEGER, location TEXT, batch_no TEXT, expire_date TEXT
            );
            CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY, product_id INTEGER, variant_id INTEGER, type TEXT,
                quantity INTEGER, old_stock INTEGER, new_stock INTEGER, reason TEXT,
                reference TEXT, created_by TEXT, location TEXT, notes TEXT
            );
            INSERT INTO sales VALUES (1, 'INV-1', '2026-08-25 12:00:00', 8000, 10000, 2000, 'Cash', 'completed', NULL);
            INSERT INTO products VALUES (1, 'Normal', 3, NULL, 'Each'), (2, 'Variant Product', 1, NULL, 'Each');
            INSERT INTO product_variants VALUES (20, 2, 1, NULL, 1);
            INSERT INTO product_locations VALUES (10, 1, 'Shop', 'B1', '', 3, NULL);
            INSERT INTO sale_items VALUES (1, 1, 1, NULL, 'Normal', 2, 1000, 2000, 500, 10, 'Shop', 'B1', '');
            INSERT INTO sale_items VALUES (2, 1, 2, 20, 'Variant Product (Black)', 1, 6000, 6000, 3000, NULL, 'Variant', '', '');
        """)
        conn.commit()
        conn.close()
        cashier_service._TABLE_COLUMNS_CACHE.clear()

    @patch("server.cashier_service.is_postgres_backend", return_value=False)
    def test_stock_adjustment_updates_locations_variants_and_audit(self, _backend):
        with patch("server.cashier_service.connect_db", self.connect), patch(
            "server.cashier_service.list_products", return_value=[{"id": 1}]
        ):
            cashier_service.adjust_stock(product_id=1, adjustment=2, location="Shop", reason="Receive")
            cashier_service.adjust_stock(product_id=1, adjustment=-1, location="Shop", reason="Damage")
            cashier_service.adjust_stock(product_id=2, variant_id=20, adjustment=3, reason="Receive")
            cashier_service.adjust_stock(product_id=2, variant_id=20, adjustment=-2, reason="Damage")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT stock FROM products WHERE id=1").fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT quantity FROM product_locations WHERE id=10").fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT stock FROM product_variants WHERE id=20").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0], 4)
        conn.close()

    def tearDown(self):
        cashier_service._TABLE_COLUMNS_CACHE.clear()
        self.folder.cleanup()

    def connect(self):
        return sqlite3.connect(self.path)

    @patch("server.cashier_service.is_postgres_backend", return_value=False)
    def test_full_refund_restores_product_variant_and_location_stock_once(self, _backend):
        with patch("server.cashier_service.connect_db", self.connect):
            receipt = cashier_service.refund_sale(1, "Returned", "tester")
            with self.assertRaisesRegex(ValueError, "already been refunded"):
                cashier_service.refund_sale(1, "Again", "tester")
        self.assertEqual(receipt["status"], "refunded")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT stock FROM products WHERE id=1").fetchone()[0], 5)
        self.assertEqual(conn.execute("SELECT quantity FROM product_locations WHERE id=10").fetchone()[0], 5)
        self.assertEqual(conn.execute("SELECT stock FROM products WHERE id=2").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT stock FROM product_variants WHERE id=20").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM stock_movements WHERE type='refund'").fetchone()[0], 2)
        conn.close()


if __name__ == "__main__":
    unittest.main()
