"""Tests for the browser Receipts overview."""

import sqlite3
import os
import tempfile
import unittest
from unittest.mock import patch

from server import cashier_service


class ReceiptsOverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "receipts.db")
        self.conn = sqlite3.connect(self.database_path)
        self.conn.executescript(
            """
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE payment_types (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY, invoice_no TEXT, created_at TEXT,
                total REAL, payment REAL, change_amount REAL,
                discount_amount REAL DEFAULT 0, payment_type TEXT,
                status TEXT, customer_id INTEGER
            );
            CREATE TABLE sale_items (id INTEGER PRIMARY KEY, sale_id INTEGER);
            INSERT INTO customers VALUES (1, 'Alice');
            INSERT INTO payment_types VALUES (1, 'Cash'), (2, 'Credit');
            INSERT INTO sales VALUES
                (1, 'INV-1', '2026-08-20 09:00:00', 1000, 1000, 0, 100, 'Cash', 'completed', NULL),
                (2, 'INV-2', '2026-08-20 10:00:00', 2000, 0, 0, 0, 'Credit', 'completed', 1),
                (3, 'INV-3', '2026-08-20 11:00:00', 500, 500, 0, 0, 'Cash', 'refunded', 1);
            INSERT INTO sale_items VALUES (1, 1), (2, 1), (3, 2), (4, 3);
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def connect(self):
        return sqlite3.connect(self.database_path)

    def test_summary_and_tabs(self):
        with patch("server.cashier_service.connect_db", self.connect):
            receipts = cashier_service.get_receipts_overview("2026-08-20", "2026-08-20")
            refunded = cashier_service.get_receipts_overview("2026-08-20", "2026-08-20", tab="refunded")
            discounted = cashier_service.get_receipts_overview("2026-08-20", "2026-08-20", tab="discounted")
            credit = cashier_service.get_receipts_overview("2026-08-20", "2026-08-20", tab="credit")

        self.assertEqual(receipts["summary"], {
            "receipts": 2, "sales": 3000.0, "discount": 100.0,
            "refund": 500.0, "credit": 2000.0,
        })
        self.assertEqual(receipts["total_count"], 2)
        self.assertEqual(refunded["rows"][0]["invoice_no"], "INV-3")
        self.assertEqual(discounted["rows"][0]["invoice_no"], "INV-1")
        self.assertEqual(credit["rows"][0]["invoice_no"], "INV-2")


if __name__ == "__main__":
    unittest.main()
