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
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY, invoice_no TEXT, created_at TEXT, total REAL,
                payment REAL, change_amount REAL, payment_type TEXT, status TEXT,
                customer_id INTEGER
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY, name TEXT, stock INTEGER, last_updated TEXT, sold_by TEXT, cost REAL DEFAULT 0
            );
            CREATE TABLE product_variants (
                id INTEGER PRIMARY KEY, product_id INTEGER, stock INTEGER, updated_at TEXT, active INTEGER DEFAULT 1, cost REAL DEFAULT 0
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
            INSERT INTO products(id,name,stock,last_updated,sold_by) VALUES (1, 'Normal', 3, NULL, 'Each'), (2, 'Variant Product', 1, NULL, 'Each');
            INSERT INTO product_variants(id,product_id,stock,updated_at,active) VALUES (20, 2, 1, NULL, 1);
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
        self.assertEqual(conn.execute("SELECT SUM(quantity) FROM product_locations WHERE product_id=1").fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT stock FROM product_variants WHERE id=20").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0], 4)
        conn.close()

    def tearDown(self):
        cashier_service._TABLE_COLUMNS_CACHE.clear()
        self.folder.cleanup()

    def connect(self):
        return sqlite3.connect(self.path)

    def test_desktop_sale_and_api_refund_preserve_variant_batch_expiry(self):
        import ast
        from pathlib import Path
        from models import variant_batches
        # Execute the real desktop deduction method without starting a GUI.
        tree=ast.parse(Path('ui/sales_page/checkout_handler/checkout_helpers.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='process_stock_deduction')
        namespace={'variant_batches':variant_batches}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<desktop deduction>','exec'),namespace)
        with patch('server.cashier_service.connect_db',self.connect),patch('server.cashier_service.is_postgres_backend',return_value=False),patch('server.cashier_service.list_products',return_value=[]):
            cashier_service.adjust_stock(product_id=2,variant_id=20,adjustment=3,unit_cost=100,location='Shop',batch_no='EXP',expire_date='2027-09-08')
        conn=self.connect();cursor=conn.cursor()
        item={'id':2,'variant_id':20,'qty':2,'name':'Variant'}
        namespace['process_stock_deduction'](None,cursor,[item],'INV-1')
        self.assertEqual(item['stock_allocations'][0]['batch_no'],'EXP')
        self.assertEqual(item['stock_allocations'][0]['expire_date'],'2027-09-08')
        cursor.execute('DELETE FROM sale_items')
        for a in item['stock_allocations']:
            cursor.execute('INSERT INTO sale_items(sale_id,product_id,variant_id,qty,product_name,location,batch_no,expire_date) VALUES(1,2,20,?,?,?,?,?)',(a['qty'],'Variant',a['location'],a['batch_no'],a['expire_date']))
        conn.commit();conn.close()
        with patch('server.cashier_service.connect_db',self.connect),patch('server.cashier_service.is_postgres_backend',return_value=False):
            cashier_service.refund_sale(1)
        conn=self.connect()
        self.assertEqual(conn.execute("SELECT quantity FROM variant_stock_batches WHERE batch_no='EXP'").fetchone()[0],3)
        self.assertEqual(conn.execute('SELECT stock FROM product_variants WHERE id=20').fetchone()[0],4)
        conn.close()

    def test_variant_transfer_and_count_correction_preserve_batch_ledger(self):
        with patch('server.cashier_service.connect_db',self.connect),patch('server.cashier_service.is_postgres_backend',return_value=False),patch('server.cashier_service.list_products',return_value=[]):
            cashier_service.adjust_stock(product_id=2,variant_id=20,adjustment=3,location='Shop',batch_no='EXP',expire_date='2027-09-08')
            cashier_service.transfer_stock(product_id=2,variant_id=20,quantity=2,from_location='Shop',to_location='Warehouse',reason='Move')
            cashier_service.set_stock_quantity(product_id=2,variant_id=20,new_quantity=3,expected_stock=4,location='Warehouse',reason='Count',adjusted_by='Tester')
        conn=self.connect()
        rows=conn.execute("SELECT location,expire_date,quantity FROM variant_stock_batches WHERE batch_no='EXP' ORDER BY location").fetchall()
        self.assertEqual(rows,[('Shop','2027-09-08',1),('Warehouse','2027-09-08',1)])
        self.assertEqual(conn.execute('SELECT SUM(quantity) FROM variant_stock_batches WHERE variant_id=20').fetchone()[0],3)
        conn.close()

    def test_two_clients_receive_without_duplicating_legacy_opening(self):
        from concurrent.futures import ThreadPoolExecutor
        with patch('server.cashier_service.connect_db',self.connect),patch('server.cashier_service.is_postgres_backend',return_value=False),patch('server.cashier_service.list_products',return_value=[]):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(cashier_service.adjust_stock,product_id=2,variant_id=20,adjustment=2,location='Shop',batch_no=f'CLIENT-{i}',expire_date='2027-09-08') for i in range(2)]
                for future in futures:future.result()
        conn=self.connect()
        self.assertEqual(conn.execute('SELECT stock FROM product_variants WHERE id=20').fetchone()[0],5)
        self.assertEqual(conn.execute('SELECT SUM(quantity) FROM variant_stock_batches WHERE variant_id=20').fetchone()[0],5)
        self.assertEqual(conn.execute("SELECT quantity FROM variant_stock_batches WHERE batch_no='LEGACY-OPENING'").fetchone()[0],1)
        conn.close()

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

    @patch("server.cashier_service.is_postgres_backend", return_value=False)
    def test_refund_restores_blank_location_sale_item_to_shop_stock(self, _backend):
        conn = self.connect()
        conn.executescript(
            """
            INSERT INTO sales VALUES (2, 'INV-2', '2026-08-25 13:00:00', 1000, 1000, 0, 'Cash', 'completed', NULL);
            INSERT INTO products(id,name,stock,last_updated,sold_by) VALUES (3, 'Legacy Item', 0, NULL, 'Each');
            INSERT INTO sale_items VALUES (3, 2, 3, NULL, 'Legacy Item', 1, 1000, 1000, 0, NULL, '', '', '');
            """
        )
        conn.commit()
        conn.close()
        cashier_service._TABLE_COLUMNS_CACHE.clear()

        with patch("server.cashier_service.connect_db", self.connect):
            cashier_service.refund_sale(2, "Returned", "tester")

        conn = self.connect()
        self.assertEqual(conn.execute("SELECT stock FROM products WHERE id=3").fetchone()[0], 1)
        self.assertEqual(
            conn.execute("SELECT location, quantity FROM product_locations WHERE product_id=3").fetchone(),
            ("Shop", 1),
        )
        conn.close()


if __name__ == "__main__":
    unittest.main()
