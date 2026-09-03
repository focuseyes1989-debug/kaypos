import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import cashier_service


class StockLocationManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "locations.db"
        connection = sqlite3.connect(self.db_path)
        connection.executescript("""
            CREATE TABLE locations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE products (id INTEGER PRIMARY KEY, cost REAL, warehouse TEXT);
            CREATE TABLE product_locations (id INTEGER PRIMARY KEY, product_id INTEGER, location TEXT, quantity INTEGER, last_updated TIMESTAMP);
            CREATE TABLE stock_movements (id INTEGER PRIMARY KEY, location TEXT);
            INSERT INTO products VALUES (1, 250, 'Shop');
            INSERT INTO locations (name) VALUES ('Shop');
            INSERT INTO product_locations VALUES (1, 1, 'Shop', 4, '2026-09-03 10:00');
            INSERT INTO stock_movements VALUES (1, 'Shop');
        """)
        connection.close()
        cashier_service._TABLE_COLUMNS_CACHE.clear()

    def tearDown(self):
        self.temp_dir.cleanup()
        cashier_service._TABLE_COLUMNS_CACHE.clear()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def test_create_rename_and_list_location(self):
        with patch("server.cashier_service.connect_db", side_effect=self.connect), patch("server.cashier_service.is_postgres_backend", return_value=False):
            created = cashier_service.create_stock_location("Warehouse 2")
            renamed = cashier_service.rename_stock_location(created["id"], "Warehouse B")
            records = cashier_service.list_location_records()
            stock_in_choices = cashier_service.list_stock_locations()

        self.assertEqual(renamed["name"], "Warehouse B")
        self.assertEqual([row["name"] for row in records], ["Shop", "Warehouse B"])
        self.assertEqual(stock_in_choices, ["Shop", "Warehouse B"])
        shop = records[0]
        self.assertEqual((shop["product_count"], shop["quantity"], shop["stock_value"]), (1, 4, 1000))

    def test_rename_updates_stock_and_history_and_in_use_location_cannot_delete(self):
        with patch("server.cashier_service.connect_db", side_effect=self.connect):
            cashier_service.rename_stock_location(1, "Main Shop")
            with self.assertRaisesRegex(ValueError, "Move or remove"):
                cashier_service.delete_stock_location(1)

        connection = self.connect()
        self.assertEqual(connection.execute("SELECT location FROM product_locations").fetchone()[0], "Main Shop")
        self.assertEqual(connection.execute("SELECT location FROM stock_movements").fetchone()[0], "Main Shop")
        self.assertEqual(connection.execute("SELECT warehouse FROM products").fetchone()[0], "Main Shop")
        connection.close()

    def test_empty_location_can_be_deleted(self):
        connection = self.connect()
        connection.execute("INSERT INTO locations (name) VALUES ('Empty')")
        connection.commit()
        location_id = connection.execute("SELECT id FROM locations WHERE name='Empty'").fetchone()[0]
        connection.close()
        with patch("server.cashier_service.connect_db", side_effect=self.connect):
            cashier_service.delete_stock_location(location_id)
        connection = self.connect()
        self.assertIsNone(connection.execute("SELECT id FROM locations WHERE id=?", (location_id,)).fetchone())
        connection.close()


if __name__ == "__main__":
    unittest.main()
