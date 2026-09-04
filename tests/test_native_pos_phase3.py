"""Native transaction tests use an isolated SQLite fixture; never production bootstrap."""
import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox
from PyQt6.QtCore import QEventLoop, QTimer, QRect
from PyQt6.QtGui import QFont, QFontDatabase
from native_pos.data import Session, ServerStore, Target
from native_pos.sales_state import CheckoutJournal
from native_pos.receipt import receipt_html
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from utils.wholesale_pricing import ensure_wholesale_schema, get_best_price_tier

ROOT = Path(__file__).resolve().parents[1]


class FixtureConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class LocalApiClient:
    """Exercise the ASGI app without a socket or an optional HTTP test package."""
    def __init__(self, app): self.app = app
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, path): return self.request('GET', path)
    def post(self, path, json): return self.request('POST', path, json)
    def request(self, method, path, payload=None):
        from urllib.parse import urlsplit
        target = urlsplit(path)
        async def execute():
            body = json.dumps(payload).encode() if payload is not None else b''
            messages = []
            async def receive(): return {'type': 'http.request', 'body': body, 'more_body': False}
            async def send(message): messages.append(message)
            await self.app(dict(type='http', asgi={'version': '3.0'}, http_version='1.1', method=method,
                                scheme='http', path=target.path, raw_path=target.path.encode(), query_string=target.query.encode(), root_path='',
                                headers=[(b'content-type', b'application/json')], client=('test', 1), server=('test', 80)), receive, send)
            status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
            data = json.loads(b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body'))
            return types.SimpleNamespace(status_code=status, json=lambda: data)
        return asyncio.run(execute())


def isolated_service(connect):
    names = {'create_sale', '_dict_from_row', '_table_columns', '_execute_dynamic_insert',
             '_try_dynamic_insert', '_sync_postgres_id_sequences', '_setting', '_active_product_discount',
             '_effective_price', '_sold_by_mode', '_effective_stock_sql', '_effective_stock',
             '_allocate_stock', '_cashier_settings_from_cursor', '_get_receipt_from_cursor', 'get_receipt'}
    tree = ast.parse((ROOT / 'server/cashier_service.py').read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    scope = dict(connect_db=connect, is_postgres_backend=lambda: False, hashlib=hashlib, json=json, math=math,
                 datetime=datetime, timedelta=timedelta, logger=Mock(), _TABLE_COLUMNS_CACHE={},
                 table_columns=lambda c, t: [row[1] for row in c.execute(f'PRAGMA table_info({t})')],
                 get_best_price_tier=get_best_price_tier, get_credit_settings=lambda: {'credit_limit_enabled': True})
    exec(compile(module, 'server/cashier_service.py', 'exec'), scope)
    return scope


class NativeSaleTransactionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'sales.db'
        with self.connect() as conn:
            conn.executescript('''
                CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, cost REAL, stock INTEGER, sold_by TEXT, last_updated TEXT);
                CREATE TABLE product_variants (id INTEGER PRIMARY KEY, product_id INTEGER, size TEXT, color TEXT, price REAL, cost REAL, stock INTEGER, active INTEGER, updated_at TEXT);
                CREATE TABLE product_locations (id INTEGER PRIMARY KEY, product_id INTEGER, location TEXT, batch_no TEXT, expire_date TEXT, quantity INTEGER, last_updated TEXT);
                CREATE TABLE stock_movements (id INTEGER PRIMARY KEY, product_id INTEGER, variant_id INTEGER, type TEXT, quantity INTEGER, old_stock INTEGER, new_stock INTEGER, reason TEXT, reference TEXT, created_by TEXT, location TEXT, notes TEXT);
                CREATE TABLE sales (id INTEGER PRIMARY KEY, invoice_no TEXT, total REAL, payment REAL, change_amount REAL, customer_id INTEGER, status TEXT, payment_type TEXT, discount_amount REAL, created_at TEXT, created_by TEXT);
                CREATE TABLE sale_items (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, variant_id INTEGER, product_name TEXT, qty INTEGER, price REAL, total REAL, cost REAL, location_id INTEGER, location TEXT, batch_no TEXT, expire_date TEXT);
                CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, credit_limit REAL, current_balance REAL, points INTEGER DEFAULT 0, total_visit INTEGER DEFAULT 0, total_spent REAL DEFAULT 0);
                CREATE TABLE credit_sales (id INTEGER PRIMARY KEY, customer_id INTEGER, sale_id INTEGER, invoice_no TEXT, total_amount REAL, paid_amount REAL, balance_amount REAL, status TEXT, sale_date TEXT, due_date TEXT, notes TEXT);
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE payment_types (name TEXT);
                CREATE TABLE product_discounts (product_id INTEGER, discount_percent REAL, discount_type TEXT, manual_price REAL, active INTEGER, start_date TEXT, end_date TEXT);
                CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, permissions TEXT, is_active INTEGER, force_password_change INTEGER);
                CREATE TABLE user_roles (name TEXT, permissions TEXT);
                INSERT INTO users VALUES (1, 'cashier', 'Cashier', 'sales,create_sale,credit_sale', 1, 0);
                INSERT INTO products VALUES (1, 'Paper', 100, 50, 10, 'Each', ''), (2, 'Shirt', 200, 100, 3, 'Variants', ''), (3, 'Print service', 20, 0, 0, 'Service', '');
                INSERT INTO product_variants VALUES (21, 2, 'M', 'Blue', 250, 100, 3, 1, '');
                INSERT INTO product_locations VALUES (11, 1, 'Shop', 'B1', '', 10, '');
                INSERT INTO settings VALUES ('tax_enabled', '1'), ('tax_rate', '5');
                INSERT INTO customers (id, name, credit_limit, current_balance) VALUES (1, 'Customer', 500, 100);
            ''')
            ensure_wholesale_schema(conn.cursor())
            conn.execute('INSERT INTO product_price_tiers (product_id, min_qty, unit_price) VALUES (1, 3, 80)')
        self.scope = isolated_service(self.connect); self.sale = self.scope['create_sale']

    def connect(self):
        return sqlite3.connect(self.path, timeout=10, factory=FixtureConnection)

    def count(self, table):
        with self.connect() as conn: return conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def request(self, **changes):
        values = dict(items=[{'product_id': 1, 'qty': 2}], payment=300, created_by='cashier', request_id=str(uuid4()), expected_total=210)
        values.update(changes); return values

    def test_quote_wholesale_discount_tax_and_rollback(self):
        with self.connect() as conn: before = list(conn.iterdump())
        quote = self.sale(items=[{'product_id': 1, 'qty': 3}], payment=0, discount_amount=40, preview_only=True)
        self.assertEqual((quote['subtotal'], quote['tax_amount'], quote['total']), (240, 10, 210))
        with self.connect() as conn: self.assertEqual(list(conn.iterdump()), before)

    def test_percentage_discount_and_existing_checkout_parity(self):
        quote = self.sale(items=[{'product_id': 1, 'qty': 2}], payment=0, discount_percent=10, preview_only=True)
        self.assertEqual((quote['discount_amount'], quote['tax_amount'], quote['total']), (20, 9, 189))
        native = self.sale(**self.request(discount_percent=10, expected_total=189))
        legacy = self.sale(items=[{'product_id': 1, 'qty': 2}], payment=300, discount_amount=20, created_by='cashier')
        for key in ['total', 'payment', 'change_amount', 'discount_amount', 'items', 'created_by']:
            self.assertEqual(native[key], legacy[key])

    def test_repeat_and_concurrent_checkout_commits_stock_once(self):
        payload = self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda _: self.sale(**payload), range(2)))
        self.assertEqual(receipts[0]['id'], receipts[1]['id'])
        self.assertEqual(self.count('sales'), 1); self.assertEqual(self.count('stock_movements'), 1)
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0], 8)
            self.assertEqual(conn.execute('SELECT quantity FROM product_locations WHERE id=11').fetchone()[0], 8)
        self.assertEqual(self.sale(**payload)['id'], receipts[0]['id'])
        with self.assertRaisesRegex(ValueError, 'different sale'):
            self.sale(**dict(payload, payment=400))
        with self.assertRaisesRegex(ValueError, 'different sale'):
            self.sale(**dict(payload, created_by='another-user'))

    def test_stale_total_payment_and_stock_fail_without_side_effects(self):
        for changes, error in [({'expected_total': 100}, 'Prices'), ({'payment': 100}, 'Insufficient'),
                               ({'items': [{'product_id': 1, 'qty': 20}]}, 'Only')]:
            with self.assertRaisesRegex(ValueError, error): self.sale(**self.request(**changes))
            self.assertEqual(self.count('sales'), 0); self.assertEqual(self.count('stock_movements'), 0)
        with self.connect() as conn: self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0], 10)

    def test_variant_and_service_prices_and_stock(self):
        items = [{'product_id': 2, 'variant_id': 21, 'qty': 2}, {'product_id': 3, 'qty': 2, 'manual_price': 35}]
        quote = self.sale(items=items, payment=0, preview_only=True)
        self.assertEqual(quote['total'], 598.5)
        self.sale(**self.request(items=items, payment=600, expected_total=598.5))
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT stock FROM product_variants WHERE id=21').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=3').fetchone()[0], 0)

    def test_credit_balance_due_date_limit_and_idempotency(self):
        payload = self.request(payment_type='Credit', sale_mode='Credit', customer_id=1, payment=50, due_date='2026-10-01')
        receipt = self.sale(**payload); self.sale(**payload)
        self.assertEqual(receipt['balance_amount'], 160)
        self.assertEqual(self.count('credit_sales'), 1)
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT current_balance FROM customers').fetchone()[0], 260)
        with self.assertRaisesRegex(ValueError, 'Credit limit'):
            self.sale(**self.request(items=[{'product_id': 1, 'qty': 4}], expected_total=336, payment=0,
                                     payment_type='Credit', customer_id=1))
        self.assertEqual(self.count('sales'), 1)

    def test_http_routes_permissions_quote_and_recovery(self):
        from fastapi import FastAPI
        from pydantic import BaseModel, Field
        from typing import List, Optional
        from server.native_sales import install_routes
        tree = ast.parse((ROOT / 'server/api.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in {'CartItem', 'SaleRequest'}]
        scope = dict(BaseModel=BaseModel, Field=Field, List=List, Optional=Optional)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'sale_models', 'exec'), scope)
        app = FastAPI()
        service = types.ModuleType('server.cashier_service'); service.__dict__.update(self.scope)
        with patch.dict('sys.modules', {'server.cashier_service': service}), patch('server.cashier_service', service, create=True):
            install_routes(app, lambda: {'id': 1, 'username': 'cashier'}, scope['SaleRequest'])
        with LocalApiClient(app) as client:
            payload = self.request(); payload.pop('created_by')
            self.assertEqual(client.get('/api/native/sales/capabilities').status_code, 200)
            quote = client.post('/api/native/sales/quote', json=payload)
            self.assertEqual(quote.status_code, 200); self.assertEqual(self.count('sales'), 0)
            receipt = client.post('/api/native/sales', json=payload).json()['receipt']
            self.assertEqual(client.post('/api/native/sales', json=payload).json()['receipt']['id'], receipt['id'])
            with self.connect() as conn: conn.execute("UPDATE users SET permissions='sales'")
            self.assertEqual(client.post('/api/native/sales', json=self.request()).status_code, 403)
            self.assertEqual(self.count('sales'), 1)


class NativeSalesWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([]); cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.window = NativeWindow(NativeTheme(self.app), Path(self.folder.name) / 'config.json')
        self.window.session = Session(1, 'cashier', 'Cashier', 'Admin', frozenset())
        self.window.store = ServerStore(Target('Server', server_url='https://fixture.invalid'))
        self.api = self.window.store.client
        self.window.populate_routes(); self.page = self.window.route_pages[5]
        self.page.loaded = True; self.page.ready = True; self.page.update_enabled()
        self.addCleanup(self.close_window)

    def close_window(self):
        self.page.cart.clear(); self.window.close()
        self.app.processEvents()

    def wait(self):
        if not self.window.runner.busy: return
        loop = QEventLoop(); self.window.runner.idle.connect(loop.quit)
        QTimer.singleShot(3000, loop.quit); loop.exec()
        self.assertFalse(self.window.runner.busy)

    def test_cart_scan_variant_service_and_quantity_limit(self):
        with patch.object(self.api, 'scan_product', return_value={'id': 1, 'name': 'Shirt', 'stock': 2, 'sold_by': 'Variants',
                           'matched_variant_id': 21, 'variants': [{'variant_id': 21, 'color': 'Blue', 'size': 'M', 'stock': 2, 'price': 200}]}):
            self.page.barcode.setText('barcode'); self.page.scan(); self.wait()
        self.assertEqual(next(iter(self.page.cart.items.values()))['variant_id'], 21)
        self.page.change(1); self.page.change(1); self.assertEqual(self.page.cart.count(), 2)
        with patch('native_pos.sales.QInputDialog.getDouble', return_value=(50, True)):
            self.page.add_product({'id': 3, 'name': 'Print', 'sold_by': 'Service'})
        self.assertEqual(self.page.payload()['items'][1]['manual_price'], 50)

    def test_network_failure_restart_retries_same_request_and_preserves_receipt(self):
        pending = {'payload': {'request_id': str(uuid4())}, 'cart': {}}
        self.page.journal.write(pending); self.page.pending = pending
        with patch.object(self.api, '_request', side_effect=RuntimeError('Connection lost')):
            self.page.recover(); self.wait()
        self.assertEqual(self.page.journal.read(), pending)
        self.assertFalse(self.page.controls.isEnabled())
        from native_pos.sales import SalesPage
        restored = SalesPage(self.window)
        self.assertEqual(restored.pending['payload'], pending['payload']); restored.deleteLater()
        receipt = {'id': 12, 'invoice_no': 'TEST-12', 'total': 210, 'items': []}
        with patch.object(self.api, '_request', return_value={'receipt': receipt}) as request, patch.object(self.page, 'show_receipt'):
            self.page.recover(); self.wait()
        self.assertEqual(request.call_args.kwargs['json']['request_id'], pending['payload']['request_id'])
        self.assertIsNone(self.page.pending); self.assertEqual(self.page.journal.read()['receipt'], receipt)
        from native_pos.sales import SalesPage
        reopened = SalesPage(self.window)
        self.assertEqual(reopened.last_receipt, receipt); self.assertIsNone(reopened.pending); reopened.deleteLater()

    def test_rejected_checkout_keeps_cart_and_cancel_review_sends_no_sale(self):
        self.page.add_product({'id': 1, 'name': 'Paper', 'price': 100, 'stock': 10})
        self.page.pending = {'payload': {'request_id': str(uuid4())}, 'cart': self.page.cart.items}
        self.page.journal.write(self.page.pending)
        self.page.checkout_result({'rejected': 'Insufficient stock'})
        self.assertEqual(self.page.cart.count(), 1); self.assertIsNone(self.page.pending)
        self.page.update_enabled()
        with patch('native_pos.sales.QDialog.exec', return_value=QDialog.DialogCode.Rejected), patch.object(self.api, '_request') as request:
            self.page.confirm_quote(self.page.payload(), {'total': 100, 'items': []})
        request.assert_not_called(); self.assertEqual(self.page.cart.count(), 1)

    def test_receipt_escapes_product_and_customer_text(self):
        html = receipt_html({'items': [{'product_name': '<script>x</script>', 'qty': 1, 'price': 1, 'total': 1}], 'customer_name': '<b>Name</b>'})
        self.assertNotIn('<script>', html); self.assertIn('&lt;script&gt;', html); self.assertIn('&lt;b&gt;Name', html)

    def test_closing_during_checkout_still_saves_receipt_without_dialog(self):
        import time
        pending = {'payload': {'request_id': str(uuid4())}, 'cart': {}}
        self.page.pending = pending; self.page.journal.write(pending)
        receipt = {'id': 13, 'invoice_no': 'TEST-13', 'items': []}
        def checkout(*args, **kwargs):
            time.sleep(0.04)
            return {'receipt': receipt}
        with patch.object(self.api, '_request', side_effect=checkout), patch.object(self.page, 'show_receipt') as show:
            self.page.recover(); self.window.close(); self.wait()
        show.assert_not_called()
        self.assertEqual(self.page.journal.read()['receipt'], receipt)

    def test_read_only_account_and_old_server_do_not_enable_checkout(self):
        self.page.ready = False
        with patch.object(self.api, '_request', side_effect=RuntimeError('Not Found')):
            self.page.initialize(); self.wait()
        self.assertFalse(self.page.controls.isEnabled())
        self.assertIn('Update/restart', self.page.message.text())
        self.page.session = Session(2, 'viewer', 'Viewer', 'Cashier', frozenset({'sales'}))
        with patch.object(self.api, '_request') as request:
            self.page.initialize()
        request.assert_not_called(); self.assertFalse(self.page.controls.isEnabled())

    def test_layout_fits_minimum_display_and_pending_journal_is_scoped(self):
        with patch.object(self.window, 'screen') as screen:
            screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728)
            self.window._fit_display()
        self.window.show(); self.app.processEvents()
        self.assertLessEqual(self.window.sizeHint().height(), 728)
        self.assertLessEqual(self.window.width(), 1366)
        self.assertGreater(self.page.checkout_button.height(), 0)
        other = CheckoutJournal(self.api.server_url, 2, self.folder.name)
        self.assertNotEqual(other.path, self.page.journal.path)


if __name__ == '__main__':
    unittest.main()
