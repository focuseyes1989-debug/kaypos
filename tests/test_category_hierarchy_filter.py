import sqlite3
import unittest
from unittest.mock import patch

from ui.products_page.product_service import ProductService
from utils.category_hierarchy import expand_category_scope, product_category_filter


class CategoryHierarchyFilterTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        cursor = self.connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, parent_id INTEGER);
            CREATE TABLE products (
                id INTEGER PRIMARY KEY, name TEXT, category TEXT, category_id INTEGER,
                price REAL, stock INTEGER, low_stock INTEGER, sold_by TEXT, image TEXT,
                sku TEXT, barcode TEXT
            );
            INSERT INTO categories VALUES (1, 'Electronics', NULL);
            INSERT INTO categories VALUES (2, 'Phones', 1);
            INSERT INTO categories VALUES (3, 'Android', 2);
            INSERT INTO categories VALUES (4, 'Snacks', NULL);
            INSERT INTO products VALUES (1, 'Parent item', 'Electronics', 1, 1, 1, 0, 'Each', '', '', '');
            INSERT INTO products VALUES (2, 'Child item', 'Phones', 2, 1, 1, 0, 'Each', '', '', '');
            INSERT INTO products VALUES (3, 'Sub-child item', 'Android', 3, 1, 1, 0, 'Each', '', '', '');
            INSERT INTO products VALUES (4, 'Unrelated item', 'Snacks', 4, 1, 1, 0, 'Each', '', '', '');
            """
        )

    def tearDown(self):
        self.connection.close()

    def test_scope_includes_all_descendants(self):
        rows = [(1, "Electronics", None), (2, "Phones", 1), (3, "Android", 2)]
        self.assertEqual(expand_category_scope("Electronics", rows), (["Android", "Electronics", "Phones"], [1, 2, 3]))

    def test_product_service_parent_filter_returns_descendant_products(self):
        with patch("ui.products_page.product_service.connect_db", return_value=self.connection):
            rows, total = ProductService().load_products(category="Electronics")

        self.assertEqual(total, 3)
        self.assertEqual({row[1] for row in rows}, {"Parent item", "Child item", "Sub-child item"})

    def test_inventory_filter_sql_supports_table_alias(self):
        sql, params = product_category_filter(self.connection.cursor(), "Electronics", "p")
        self.assertIn("p.category", sql)
        self.assertIn("p.category_id", sql)
        self.assertEqual(set(params), {"android", "electronics", "phones", 1, 2, 3})


if __name__ == "__main__":
    unittest.main()
