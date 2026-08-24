import sqlite3
import unittest
from unittest.mock import patch

from models.database.queries import reverse_stock_movement


class _Context:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False


class VariantMovementReversalTests(unittest.TestCase):
    def test_stock_in_reversal_updates_product_and_selected_variant(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript("""
            CREATE TABLE products (id INTEGER PRIMARY KEY, stock REAL, last_updated TEXT);
            CREATE TABLE product_variants (
                id INTEGER PRIMARY KEY, product_id INTEGER, stock REAL, updated_at TEXT
            );
            CREATE TABLE product_locations (
                product_id INTEGER, location TEXT, quantity REAL,
                UNIQUE(product_id, location)
            );
            CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, type TEXT,
                quantity REAL, old_stock REAL, new_stock REAL, reason TEXT,
                reference TEXT, created_by TEXT, notes TEXT, location TEXT,
                supplier_id INTEGER, variant_id INTEGER
            );
            INSERT INTO products VALUES (1, 12, NULL);
            INSERT INTO product_variants VALUES (10, 1, 11, NULL);
            INSERT INTO product_variants VALUES (11, 1, 1, NULL);
            INSERT INTO product_locations VALUES (1, 'Shop', 12);
            INSERT INTO stock_movements
                (id, product_id, type, quantity, old_stock, new_stock, reason,
                 reference, created_by, notes, location, supplier_id, variant_id)
            VALUES (5, 1, 'in', 11, 1, 12, 'Stock In', 'SIN-5', 'user', '', 'Shop', NULL, 10);
        """)
        with patch("models.database.queries.DBContext", return_value=_Context(connection)):
            result = reverse_stock_movement(5, created_by="tester")
        self.assertTrue(result["success"])
        self.assertEqual(connection.execute("SELECT stock FROM products WHERE id=1").fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT stock FROM product_variants WHERE id=10").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT stock FROM product_variants WHERE id=11").fetchone()[0], 1)
        self.assertEqual(
            connection.execute("SELECT variant_id FROM stock_movements WHERE id<>5").fetchone()[0], 10
        )
        connection.close()


if __name__ == "__main__":
    unittest.main()
