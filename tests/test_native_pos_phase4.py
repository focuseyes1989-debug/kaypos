"""Phase 4 uses disposable databases and socket-free/mocked clients only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import base64
import io
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from PyQt6.QtCore import QEventLoop, QTimer, QRect
from PyQt6.QtWidgets import QApplication, QDialog
from native_pos.catalog import CatalogSession, CatalogPage
from native_pos.catalog_dialogs import ProductDialog, PricingDialog, StockDialog, CategoryDialog
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from native_pos.catalog_transfer import read_products, write_products
from native_pos.barcode import code128, label_geometry, PATTERNS, paint_label
from server.native_catalog import CatalogRepository, install_routes
from tests import test_native_pos_phase3 as phase3
from tests.test_native_pos_phase3 import isolated_service, LocalApiClient


class CatalogDatabaseTests(unittest.TestCase):
    connect = phase3.NativeSaleTransactionTests.connect
    count = phase3.NativeSaleTransactionTests.count

    def setUp(self):
        phase3.NativeSaleTransactionTests.setUp(self)
        with self.connect() as c:
            for name, kind in [('category', 'TEXT'), ('category_id', 'INTEGER'), ('description', 'TEXT'), ('sku', 'TEXT'), ('barcode', 'TEXT'),
                               ('low_stock', 'INTEGER DEFAULT 0'), ('unit', 'TEXT'), ('base_unit', 'TEXT'), ('pack_unit', 'TEXT'), ('pack_size', 'INTEGER DEFAULT 1'),
                               ('image', 'TEXT'), ('image_data', 'BLOB'), ('image_filename', 'TEXT'), ('image_mime', 'TEXT')]:
                c.execute(f'ALTER TABLE products ADD COLUMN {name} {kind}')
            for name, kind in [('sku', 'TEXT'), ('barcode', 'TEXT'), ('low_stock', 'INTEGER DEFAULT 0')]:
                c.execute(f'ALTER TABLE product_variants ADD COLUMN {name} {kind}')
            c.executescript('''
                CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, description TEXT, parent_id INTEGER, status TEXT DEFAULT 'active', is_system INTEGER DEFAULT 0);
                INSERT INTO categories(id,name) VALUES(1,'Stationery'),(2,'Clothes');
                UPDATE products SET category='Stationery',category_id=1 WHERE id=1;
                UPDATE users SET role='Admin';
                DROP TABLE product_discounts;
                CREATE TABLE product_discounts (id INTEGER PRIMARY KEY, product_id INTEGER, discount_percent REAL, discount_type TEXT, manual_price REAL, active INTEGER, start_date TEXT, end_date TEXT, note TEXT);
                ALTER TABLE stock_movements ADD COLUMN created_at TEXT;
            ''')
        self.scope = isolated_service(self.connect)
        self.repo = CatalogRepository(types.SimpleNamespace(**self.scope))
        self.user = {'id': 1, 'username': 'cashier'}

    def detail(self, product_id=1): return self.repo.read(self.user, 'products', product_id)
    def command(self, operation, values, request_id=None): return self.repo.command(self.user, request_id or str(uuid4()), operation, values)
    def stock_values(self, product_id=1, **changes):
        p = self.detail(product_id)
        return dict(product_id=product_id, stock_revision=p['stock_revision'], reason='Fixture test', quantity=2, location='Shop', **changes)

    def test_product_edit_preserves_variant_identity_stock_and_history(self):
        product = self.detail(2)
        product['variants'][0].update(price=275, stock=999)
        product.update(name='Blue shirt', stock=999)
        self.command('product.save', product)
        saved = self.detail(2)
        self.assertEqual((saved['stock'], saved['variants'][0]['id'], saved['variants'][0]['stock']), (3, 21, 3))
        self.assertEqual(saved['variants'][0]['price'], 275)
        bad = deepcopy(saved); bad['variants'] = []
        with self.assertRaises(ValueError): self.command('product.save', bad)
        self.assertEqual(self.detail(2)['variants'][0]['id'], 21)

    def test_product_save_does_not_restore_stock_after_a_sale(self):
        product = self.detail(); product['name'] = 'Renamed paper'
        self.scope['create_sale'](items=[{'product_id': 1, 'qty': 1}], payment=105)
        self.command('product.save', product)
        self.assertEqual(self.detail()['stock'], 9)
        self.assertEqual(self.detail()['locations'][0]['quantity'], 9)
        with self.assertRaisesRegex(ValueError, 'changed'): self.command('product.save', product)

    def test_new_product_duplicate_codes_and_safe_delete(self):
        values = dict(name='New service', sold_by='Service', sku='PRINT-1', price=50, category='Stationery')
        result = self.command('product.save', values)
        product = self.detail(result['product_id']); self.assertEqual(product['stock'], 0)
        with self.assertRaisesRegex(ValueError, 'already exists'): self.command('product.save', values)
        self.command('product.delete', {'id': product['id'], 'revision': product['revision']})
        with self.assertRaises(ValueError): self.detail(product['id'])
        with self.assertRaisesRegex(ValueError, 'stocked'): self.command('product.delete', {'id': 1, 'revision': self.detail()['revision']})
        with self.connect() as c:
            c.execute('UPDATE products SET stock=0 WHERE id=1'); c.execute('UPDATE product_locations SET quantity=0 WHERE product_id=1')
            c.execute("INSERT INTO stock_movements(product_id,type) VALUES(1,'stock_out')")
        with self.assertRaisesRegex(ValueError, 'history'): self.command('product.delete', {'id': 1, 'revision': self.detail()['revision']})

    def test_image_blob_save_and_invalid_image_rollback(self):
        from PIL import Image
        image = Image.new('RGB', (4, 4), 'blue'); stream = io.BytesIO(); image.save(stream, format='PNG')
        product = self.detail(); product['image_base64'] = base64.b64encode(stream.getvalue()).decode()
        self.command('product.save', product)
        with self.connect() as c:
            blob, mime = c.execute('SELECT image_data,image_mime FROM products WHERE id=1').fetchone()
        self.assertEqual(blob, stream.getvalue()); self.assertEqual(mime, 'image/png')
        product = self.detail(); product.update(name='Should rollback', image_base64=base64.b64encode(b'bad').decode())
        with self.assertRaises(ValueError): self.command('product.save', product)
        self.assertEqual(self.detail()['name'], 'Paper')

    def test_category_rename_hierarchy_cycles_and_used_delete(self):
        categories = self.repo.read(self.user, 'products')['categories']
        category = next(r for r in categories if r['id'] == 1); category['name'] = 'Paper goods'
        self.command('category.save', category)
        self.assertEqual(self.detail()['category'], 'Paper goods')
        result = self.command('category.save', {'name': 'Child', 'parent_id': 1})
        categories = self.repo.read(self.user, 'products')['categories']
        category = next(r for r in categories if r['id'] == 1)
        with self.assertRaisesRegex(ValueError, 'cycle'): self.command('category.save', dict(category, parent_id=result['category_id']))
        with self.assertRaisesRegex(ValueError, 'contains'): self.command('category.delete', category)

    def test_pricing_rules_match_native_sales_quote_and_invalid_dates_rollback(self):
        product = self.detail()
        values = dict(product_id=1, pricing_revision=product['pricing_revision'], discounts=[dict(discount_type='percentage', discount_percent=10,
                      start_date='2020-01-01', end_date='2099-12-31', active=True)], tiers=[])
        self.command('pricing.save', values)
        quote = self.scope['create_sale'](items=[{'product_id': 1, 'qty': 1}], payment=0, preview_only=True)
        self.assertEqual(quote['total'], 94.5)
        product = self.detail()
        values.update(pricing_revision=product['pricing_revision'], discounts=product['discounts'], tiers=[{'min_qty': 3, 'unit_price': 70}])
        self.command('pricing.save', values)
        quote = self.scope['create_sale'](items=[{'product_id': 1, 'qty': 3}], payment=0, preview_only=True)
        self.assertEqual(quote['total'], 220.5)
        product = self.detail(); values.update(pricing_revision=product['pricing_revision'])
        values['discounts'][0]['end_date'] = '2019-01-01'
        with self.assertRaises(ValueError): self.command('pricing.save', values)
        self.assertEqual(self.detail()['discounts'][0]['end_date'], '2099-12-31')

    def test_stock_in_weighted_cost_duplicate_and_concurrent_retry(self):
        values = self.stock_values(unit_cost=80, batch_no='B2', expire_date='2027-01-01')
        request_id = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.command('stock.in', values, request_id), range(2)))
        self.assertEqual(results[0], results[1])
        product = self.detail(); self.assertEqual(product['stock'], 12); self.assertEqual(product['cost'], 55)
        self.assertEqual(sum(r['quantity'] for r in product['locations']), 12)
        self.assertEqual(self.count('stock_movements'), 1)
        with self.assertRaisesRegex(ValueError, 'different change'): self.command('stock.in', dict(values, quantity=4), request_id)
        with self.assertRaisesRegex(ValueError, 'changed'): self.command('stock.in', values)

    def test_transfer_preserves_batches_expiry_and_out_is_location_specific(self):
        with self.connect() as c: c.execute("UPDATE product_locations SET expire_date='2027-04-01' WHERE id=11")
        values = self.stock_values(to_location='Warehouse'); values['quantity'] = 4
        self.command('stock.transfer', values)
        product = self.detail(); self.assertEqual(product['stock'], 10)
        target = next(r for r in product['locations'] if r['location'] == 'Warehouse')
        self.assertEqual((target['quantity'], target['batch_no'], target['expire_date']), (4, 'B1', '2027-04-01'))
        values = self.stock_values(); values.update(location='Warehouse', quantity=5)
        with self.assertRaisesRegex(ValueError, 'Insufficient stock in'): self.command('stock.out', values)
        self.assertEqual(self.detail()['stock'], 10); self.assertEqual(self.count('stock_movements'), 2)
        values['quantity'] = 2; self.command('stock.out', values)
        self.assertEqual(self.detail()['stock'], 8); self.assertEqual(self.detail()['locations'][0]['quantity'], 6)

    def test_adjust_variant_service_guard_and_legacy_unallocated_stock(self):
        values = self.stock_values(2, variant_id=21); values['quantity'] = 5
        self.command('stock.set', values)
        product = self.detail(2); self.assertEqual((product['stock'], product['variants'][0]['stock']), (5, 5))
        with self.assertRaisesRegex(ValueError, 'Services'): self.command('stock.in', self.stock_values(3))
        with self.connect() as c: c.execute('DELETE FROM product_locations WHERE product_id=1')
        self.command('stock.in', self.stock_values(unit_cost=50, batch_no='NEW'))
        product = self.detail(); self.assertEqual(sum(r['quantity'] for r in product['locations']), 12)

    def test_permission_recheck_and_http_request_recovery(self):
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo)
        client = LocalApiClient(app)
        self.assertEqual(client.get('/api/native/catalog').status_code, 200)
        payload = dict(request_id=str(uuid4()), operation='stock.in', values=self.stock_values(unit_cost=50))
        first = client.post('/api/native/catalog/commands', json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertIn('result', first.json())
        self.assertEqual(client.post('/api/native/catalog/commands', json=payload).json(), first.json())
        with self.connect() as c: c.execute("UPDATE users SET role='Cashier',permissions='products,inventory'")
        denied = client.post('/api/native/catalog/commands', json=dict(payload, request_id=str(uuid4())))
        self.assertEqual(denied.status_code, 403); self.assertEqual(self.count('stock_movements'), 1)

    def test_stock_reversal_restores_batch_cost_and_variant_and_rejects_repeat(self):
        before = self.detail(); values = self.stock_values(unit_cost=80, batch_no='NEW')
        original = self.command('stock.in', values)
        product = self.detail()
        values = dict(product_id=1, stock_revision=product['stock_revision'], original_request_id=original['request_id'], reason='Mistake')
        request_id = str(uuid4())
        self.command('stock.reverse', values, request_id); self.command('stock.reverse', values, request_id)
        restored = self.detail()
        self.assertEqual((restored['stock'], restored['cost'], restored['locations']), (before['stock'], before['cost'], before['locations']))
        with self.assertRaisesRegex(ValueError, 'already been reversed'):
            self.command('stock.reverse', dict(values, stock_revision=restored['stock_revision']))
        original = self.command('stock.in', self.stock_values(2, variant_id=21, unit_cost=125))
        self.command('stock.reverse', dict(product_id=2, stock_revision=self.detail(2)['stock_revision'], original_request_id=original['request_id'], reason='Mistake'))
        self.assertEqual((self.detail(2)['stock'], self.detail(2)['variants'][0]['cost']), (3, 100))

    def test_reversal_refuses_to_overwrite_later_stock_and_import_rolls_back(self):
        original = self.command('stock.in', self.stock_values(unit_cost=50))
        self.command('stock.out', self.stock_values())
        with self.assertRaisesRegex(ValueError, 'changed after'):
            self.command('stock.reverse', dict(product_id=1, stock_revision=self.detail()['stock_revision'], original_request_id=original['request_id'], reason='Mistake'))
        count = self.count('products')
        with self.assertRaisesRegex(ValueError, 'CSV row 3'):
            self.command('products.import', {'rows': [dict(name='Valid', sold_by='Each'), dict(name='', sold_by='Each')]})
        self.assertEqual(self.count('products'), count)

    def test_native_csv_round_trip_and_row_errors(self):
        path = Path(self.folder.name) / 'products.csv'
        before = self.detail(); before['name'] = '=SUM(A1)'
        self.command('product.save', before); before = self.detail()
        write_products(path, [before, self.detail(2), self.detail(3)])
        rows = read_products(path)
        self.assertEqual(rows[0]['name'], '=SUM(A1)'); self.assertIn("'=SUM(A1)", path.read_text(encoding='utf-8-sig'))
        self.command('products.import', {'rows': rows})
        after = self.detail()
        for key in ('name', 'price', 'stock', 'locations'): self.assertEqual(before[key], after[key])
        self.assertEqual(self.detail(2)['variants'][0]['id'], 21)
        path.write_text('name,sold_by,price\nBad,Each,nan\n,Service,1\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Row 2.*Invalid price') as error: read_products(path)
        self.assertIn('Row 3', str(error.exception))


class CatalogWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([]); cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.window = NativeWindow(NativeTheme(self.app), Path(self.folder.name) / 'config.json')
        self.window.session = Session(1, 'admin', 'Admin', 'Admin', frozenset())
        self.window.store = ServerStore(Target('Server', server_url='https://fixture.invalid'))
        self.window.populate_routes()
        self.pages = [self.window.route_pages[i] for i in (2, 9, 3)]
        self.window.route_pages[5].loaded = True
        for page in self.pages: page.loaded = page.ready = True
        self.page = self.pages[0]; self.channel = self.window.catalog_session
        self.product = dict(id=1, name='Paper', price=100, cost=50, stock=10, sold_by='Each', revision='meta', stock_revision='stock', pricing_revision='pricing',
                            variants=[], locations=[], discounts=[], tiers=[], category='Stationery', pack_size=1)
        self.page.records = [self.product]; self.page.render()
        self.addCleanup(self.close)

    def close(self):
        self.window.route_pages[5].cart.clear(); self.window.close(); self.app.processEvents()

    def wait(self):
        if self.window.runner.busy:
            loop = QEventLoop(); self.window.runner.idle.connect(loop.quit); QTimer.singleShot(3000, loop.quit); loop.exec()
        self.assertFalse(self.window.runner.busy)

    def test_editors_preserve_ids_validate_dates_and_do_not_edit_stock(self):
        product = dict(self.product, sold_by='Variants', variants=[dict(id=21, color='Blue', size='M', price=100, cost=50, stock=10, active=True)])
        dialog = ProductDialog(product, [{'name': 'Stationery'}]); values = dialog.values()
        self.assertNotIn('stock', {k: v for k, v in values.items() if k != 'variants'})
        self.assertEqual(values['variants'][0]['id'], 21); self.assertFalse(dialog.mode.isEnabled())
        pricing = PricingDialog(self.product); pricing.discounts.add({'start_date': '2026-12-01', 'end_date': '2026-01-01'})
        with self.assertRaises(ValueError): pricing.values()
        stock = StockDialog(self.product, 'stock.in', 'Admin')
        with self.assertRaisesRegex(ValueError, 'Reason'): stock.values()
        for widget in (dialog, pricing, stock): widget.close()

    def test_cancel_editor_sends_nothing_and_old_server_stays_read_only(self):
        with patch('native_pos.catalog_dialogs.ProductDialog.exec', return_value=QDialog.DialogCode.Rejected), patch.object(self.channel.api, '_request') as request:
            self.page.new_product()
        request.assert_not_called()
        self.page.ready = False
        with patch.object(self.channel.api, '_request', side_effect=RuntimeError('Not Found')):
            self.page.refresh(); self.wait()
        self.assertFalse(self.page.ready); self.assertIn('Update/restart', self.page.status.text())

    def test_pending_operation_locks_all_pages_and_retries_exact_request(self):
        with patch.object(self.channel.api, '_request', side_effect=RuntimeError('Network lost')):
            self.channel.submit('stock.in', {'product_id': 1, 'quantity': 2}); self.wait()
        payload = deepcopy(self.channel.pending['payload'])
        for page in self.pages:
            page.update_enabled(); self.assertTrue(all(not b.isEnabled() for b, _, _ in page.action_buttons))
        restored = CatalogSession(self.window); self.assertEqual(restored.pending['payload'], payload); restored.deleteLater()
        response = {'result': {'message': 'Saved', 'request_id': payload['request_id'], 'operation': 'stock.in'}}
        with patch.object(self.channel.api, '_request', return_value=response) as request:
            self.channel.recover(); self.wait()
        self.assertEqual(request.call_args.kwargs['json'], payload); self.assertIsNone(self.channel.pending)
        self.assertEqual(self.channel.journal.read()['result'], response['result'])
        self.assertFalse(self.window.route_pages[5].loaded)

    def test_close_during_command_persists_result(self):
        def operation(*args, **kwargs):
            time.sleep(.04)
            return {'result': {'message': 'Saved', 'request_id': kwargs['json']['request_id'], 'operation': 'product.save'}}
        with patch.object(self.channel.api, '_request', side_effect=operation):
            self.channel.submit('product.save', {'name': 'Fixture'}); self.window.close(); self.wait()
        self.assertIn('result', self.channel.journal.read())

    def test_native_routes_permissions_and_minimum_display(self):
        with patch.object(self.window, 'screen') as screen:
            screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728); self.window._fit_display()
        self.window.navigate(3); self.window.show(); self.app.processEvents()
        self.assertLessEqual(self.window.sizeHint().height(), 728)
        self.assertLessEqual(self.window.width(), 1366)
        self.assertIsInstance(self.window.route_pages[9], CatalogPage)
        self.window.session = Session(1, 'viewer', 'Viewer', 'Cashier', frozenset({'products'}))
        self.page.update_enabled()
        self.assertFalse(self.page.action_buttons[0][0].isEnabled())

    def test_barcode_checksum_patterns_quiet_zone_and_print_document(self):
        import ast
        from PyQt6.QtGui import QImage, QPainter
        legacy = ast.parse((Path(__file__).resolve().parents[1] / 'ui/print_barcode_dialog.py').read_text(encoding='utf-8-sig'))
        patterns = next(node.value for node in legacy.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CODE128_PATTERNS' for t in node.targets))
        self.assertEqual(PATTERNS, ast.literal_eval(patterns))
        self.assertEqual(code128('AB'), [104, 33, 34, 102, 106])
        values, module = label_geometry('1234567890123', 60, 30)
        self.assertGreaterEqual(module, .25)
        with self.assertRaises(ValueError): label_geometry('123456789012345678901234567890', 40, 30)
        with self.assertRaises(ValueError): code128('မြန်မာ')
        image = QImage(720, 360, QImage.Format.Format_RGB32); image.fill(0xFFFFFF)
        painter = QPainter(image); paint_label(painter, 'Fixture', '1234567890123', 60, 30, 304.8); painter.end()
        self.assertEqual(image.pixelColor(24, 120).name(), '#ffffff')
        self.assertTrue(any(image.pixelColor(x, 120).name() == '#000000' for x in range(50, 650)))


if __name__ == '__main__': unittest.main()
