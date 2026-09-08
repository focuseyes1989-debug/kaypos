import sqlite3
import unittest
from unittest.mock import patch
from server import cashier_service


class MovementFilterTests(unittest.TestCase):
    def query(self, **kwargs):
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE product_variants(id INTEGER, color TEXT, size TEXT);
            CREATE TABLE stock_movements(id INTEGER, product_id INTEGER, variant_id INTEGER,
                created_at TEXT, type TEXT, quantity INTEGER, old_stock INTEGER, new_stock INTEGER,
                reason TEXT, reference TEXT, created_by TEXT, location TEXT, notes TEXT);
            INSERT INTO stock_movements VALUES
                (1,1,NULL,'2026-09-01 08:00','in',2,0,2,'','','A','Shop',''),
                (2,1,NULL,'2026-09-02 08:00','stock_in',3,2,5,'','','B','Shop',''),
                (3,1,NULL,'2026-09-02 08:00','out',1,5,4,'','','A','Shop',''),
                (4,2,NULL,'2026-09-02 08:00','in',9,0,9,'','','A','Shop','');
        """)
        with patch.object(cashier_service, 'connect_db', return_value=conn):
            return cashier_service.list_stock_movements(1, **kwargs)

    def test_dates_types_and_product_scope(self):
        self.assertEqual([r['id'] for r in self.query(movement_type='in')], [2,1])
        self.assertEqual([r['id'] for r in self.query(from_date='2026-09-02', to_date='2026-09-02')], [3,2])

    def test_stable_pagination_and_empty(self):
        self.assertEqual([r['id'] for r in self.query(limit=1, offset=1)], [2])
        self.assertEqual(self.query(offset=10), [])
        self.assertEqual(self.query(movement_type="in' OR 1=1 --"), [])

    def test_invalid_dates(self):
        with self.assertRaises(ValueError):
            self.query(from_date='bad')
        with self.assertRaises(ValueError):
            self.query(from_date='2026-09-03', to_date='2026-09-01')
