"""Managed item writes use an isolated database, never the shop database."""
import base64
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from server import cashier_service as service


class ItemEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'items.db')
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript('''
                CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT,
                    description TEXT, sold_by TEXT, price REAL, cost REAL, sku TEXT,
                    barcode TEXT, stock INTEGER, low_stock INTEGER, unit TEXT,
                    base_unit TEXT, pack_unit TEXT, pack_size INTEGER, image TEXT,
                    image_data BLOB, image_mime TEXT, image_filename TEXT, last_updated TEXT);
                CREATE TABLE product_variants (id INTEGER PRIMARY KEY, product_id INTEGER,
                    color TEXT, size TEXT, sku TEXT, barcode TEXT, price REAL, cost REAL,
                    stock INTEGER, low_stock INTEGER, active INTEGER);
            ''')
        service._TABLE_COLUMNS_CACHE.clear()
        self.patches = [patch.object(service, 'connect_db', lambda: sqlite3.connect(self.path)),
                        patch.object(service, 'is_postgres_backend', return_value=False),
                        patch('utils.db_compat.is_postgres_backend', return_value=False),
                        patch.object(service, 'list_products', return_value=[])]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        service._TABLE_COLUMNS_CACHE.clear()
        self.temp.cleanup()

    def rows(self, sql):
        with closing(sqlite3.connect(self.path)) as conn: return conn.execute(sql).fetchall()

    def test_wholesale_create_edit_clear_and_legacy_preservation(self):
        values = dict(name='Bottle', sold_by='Each', pack_unit='Box', pack_size=12,
                      wholesale_tiers=[dict(min_qty=12, unit_price=800, unit_multiplier=12, barcode='BOX')])
        pid = service.save_managed_product(values)['id']
        self.assertEqual(self.rows('SELECT min_qty, unit_price, barcode FROM product_price_tiers'), [(12, 800, 'BOX')])
        service.save_managed_product(dict(name='Bottle'), pid)
        self.assertEqual(len(self.rows('SELECT * FROM product_price_tiers')), 1)
        values['wholesale_tiers'][0]['unit_price'] = 750
        service.save_managed_product(values, pid)
        self.assertEqual(self.rows('SELECT unit_price FROM product_price_tiers'), [(750,)])
        values['wholesale_tiers'] = []
        service.save_managed_product(values, pid)
        self.assertEqual(self.rows('SELECT * FROM product_price_tiers'), [])

    def test_variants_and_service(self):
        values = dict(name='Shirt', sold_by='Variants', wholesale_tiers=[], variants=[
            dict(color='Red', size='M', price=2000, stock=3), dict(color='Blue', size='L', price=2500, stock=4)])
        pid = service.save_managed_product(values)['id']
        self.assertEqual(self.rows('SELECT stock FROM products'), [(7,)])
        values['variants'] = [dict(color='Green', size='S', price=3000, stock=2)]
        service.save_managed_product(values, pid)
        self.assertEqual(self.rows('SELECT color, price, stock FROM product_variants'), [('Green', 3000, 2)])
        service.save_managed_product(dict(name='Repair', sold_by='Service', price=5000, wholesale_tiers=[]), pid)
        self.assertEqual(self.rows('SELECT sold_by, price FROM products'), [('Service', 5000)])
        self.assertEqual(self.rows('SELECT * FROM product_variants'), [])

    def test_image_replacement_and_preservation(self):
        with patch.object(service, '_save_mobile_product_image', return_value=('image.png', b'png', 'image/png', 'image.png')) as save:
            pid = service.save_managed_product(dict(name='Image', image_base64=base64.b64encode(b'png').decode()))['id']
            save.assert_called_once()
        service.save_managed_product(dict(name='Renamed'), pid)
        self.assertEqual(self.rows('SELECT image_data FROM products'), [(b'png',)])

    def test_duplicate_tiers_and_barcodes_rejected_without_partial_write(self):
        tier = dict(min_qty=6, unit_price=100, barcode='BOX')
        service.save_managed_product(dict(name='First', wholesale_tiers=[tier]))
        with self.assertRaisesRegex(ValueError, 'Barcode already exists'):
            service.save_managed_product(dict(name='Second', wholesale_tiers=[tier]))
        with self.assertRaisesRegex(ValueError, 'unique'):
            service.save_managed_product(dict(name='Third', wholesale_tiers=[tier, tier]))
        self.assertEqual(self.rows('SELECT name FROM products'), [('First',)])


if __name__ == '__main__': unittest.main()
