"""Business transactions use a disposable database, real SQL and no server sockets."""
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import uuid

from PyQt6.QtCore import QEventLoop, QTimer, QRect
from PyQt6.QtWidgets import QApplication, QDialog
from native_pos.business import BusinessPage, safe_csv
from native_pos.business_dialogs import FormDialog, CUSTOMER_FORM, OrderDialog, MenuLineDialog, CreditDialog
from native_pos.catalog import CatalogSession
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from server.native_business import BusinessRepository, install_routes
from tests import test_native_pos_phase4 as phase4
from tests.test_native_pos_phase3 import isolated_service, LocalApiClient
from utils.db_compat import ensure_column, table_columns


ROOT = Path(__file__).resolve().parents[1]


def isolated_restaurant():
    tree = ast.parse((ROOT / 'utils/restaurant_service.py').read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    scope = dict(json=json, uuid=uuid, hashlib=hashlib, datetime=datetime, is_postgres_backend=lambda: False,
        integer_primary_key_sql=lambda: 'INTEGER PRIMARY KEY AUTOINCREMENT', current_timestamp_sql=lambda: 'CURRENT_TIMESTAMP',
        ensure_column=ensure_column, table_columns=table_columns, connect_db=Mock(side_effect=AssertionError('Nested connection forbidden')))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'utils/restaurant_service.py', 'exec'), scope)
    return types.SimpleNamespace(**scope)


class BusinessDatabaseTests(unittest.TestCase):
    connect = phase4.CatalogDatabaseTests.connect
    count = phase4.CatalogDatabaseTests.count

    def setUp(self):
        phase4.CatalogDatabaseTests.setUp(self)
        with self.connect() as c:
            for field in ('phone', 'email', 'address', 'remarks'): c.execute(f'ALTER TABLE customers ADD COLUMN {field} TEXT')
            c.execute('ALTER TABLE customers ADD COLUMN credit_balance REAL DEFAULT 0')
            c.execute('ALTER TABLE products ADD COLUMN restaurant_modifiers TEXT')
            c.executescript('''
                CREATE TABLE credit_payments (id INTEGER PRIMARY KEY, credit_sale_id INTEGER, customer_id INTEGER, amount REAL,
                    payment_date TEXT NOT NULL, payment_method TEXT, reference_no TEXT, note TEXT);
                CREATE TABLE credit_adjustments (id INTEGER PRIMARY KEY, customer_id INTEGER, credit_sale_id INTEGER, amount REAL,
                    adjustment_type TEXT, reason TEXT, reference_no TEXT, created_by TEXT);
                CREATE TABLE expenses (id INTEGER PRIMARY KEY, expense_no TEXT NOT NULL UNIQUE, category TEXT NOT NULL,
                    description TEXT, amount REAL NOT NULL, expense_date TEXT NOT NULL, payment_method TEXT, reference_no TEXT,
                    notes TEXT, image TEXT, created_by TEXT, created_at TEXT);
                CREATE TABLE expense_categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, is_active INTEGER DEFAULT 1);
                CREATE TABLE expense_budgets (id INTEGER PRIMARY KEY, category TEXT NOT NULL, month INTEGER, year INTEGER,
                    budget_amount REAL, notes TEXT, updated_at TEXT, UNIQUE(category,month,year));
                INSERT INTO expense_categories(name) VALUES('Rent');
                INSERT INTO products(id,name,price,cost,stock,sold_by) VALUES(4,'Rice',100,30,0,'Restaurant');
                UPDATE customers SET current_balance=0;
            ''')
            c.execute('UPDATE products SET restaurant_modifiers=? WHERE id=4', (json.dumps([
                dict(group='Protein', name='Chicken', type='choice', price_delta=20),
                dict(group='Protein', name='Beef', type='choice', price_delta=40),
                dict(group='Taste', name='Less salt', type='note', price_delta=0)]),))
            isolated_restaurant().ensure_restaurant_schema(c.cursor())
        self.scope = isolated_service(self.connect)
        self.repo = BusinessRepository(types.SimpleNamespace(**self.scope), isolated_restaurant())
        self.sale = self.scope['create_sale']; self.user = dict(id=1, username='cashier')

    def command(self, operation, values, request_id=None): return self.repo.command(self.user, request_id or str(uuid.uuid4()), operation, values)
    def record(self, table, record_id):
        with self.connect() as c: return self.repo.record(c.cursor(), table, record_id)
    def credit_sale(self, payment=0):
        receipt = self.sale(items=[dict(product_id=1, qty=2)], payment=payment, payment_type='Credit', customer_id=1, request_id=str(uuid.uuid4()))
        return receipt, self.repo.read(self.user, 'credit', 1)['records'][0]
    def new_order(self, cart=None, **extra):
        result = self.command('restaurant.save', dict(cart=cart or [dict(id=4, qty=2, restaurant_modifiers=[dict(group='Protein', name='Chicken')])], **extra))
        return self.record('restaurant_orders', result['id'])

    def test_customer_crud_stale_revision_and_history_protection(self):
        row_id = self.command('customer.save', dict(name='New', phone='099', credit_limit=500))['customer_id']
        row = self.record('customers', row_id)
        self.command('customer.save', dict(row, name='Edited', current_balance=999))
        self.assertEqual(self.record('customers', row_id)['current_balance'], 0)
        with self.assertRaisesRegex(ValueError, 'changed'): self.command('customer.save', row)
        self.command('customer.delete', self.record('customers', row_id))
        self.credit_sale()
        with self.assertRaisesRegex(ValueError, 'history'): self.command('customer.delete', self.record('customers', 1))

    def test_payment_retry_concurrent_once_and_overpayment_rollback(self):
        _, credit = self.credit_sale(); values = dict(credit, amount=50, payment_date='2026-09-04'); request_id = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.command('credit.pay', values, request_id), range(2)))
        self.assertEqual(results[0], results[1]); self.assertEqual(self.count('credit_payments'), 1)
        self.assertEqual(self.record('customers', 1)['current_balance'], 160)
        credit = self.record('credit_sales', credit['id']); self.assertEqual(credit['paid_amount'], 50)
        for amount in (0, -1, 161, float('nan')):
            with self.assertRaises(ValueError): self.command('credit.pay', dict(credit, amount=amount))
        self.assertEqual(self.count('credit_payments'), 1)
        self.command('credit.pay', dict(credit, amount=160))
        self.assertEqual(self.record('customers', 1)['current_balance'], 0)

    def test_fresh_permission_checks_and_recovery_owner(self):
        _, credit = self.credit_sale(); values = dict(credit, amount=50); request_id = str(uuid.uuid4())
        with self.connect() as c: c.execute("UPDATE users SET role='Cashier',permissions='customers,credit' WHERE id=1")
        with self.assertRaises(PermissionError): self.command('credit.pay', values, request_id)
        with self.connect() as c: c.execute("UPDATE users SET permissions='customers,credit,payment_collection' WHERE id=1")
        self.command('credit.pay', values, request_id)
        with self.assertRaisesRegex(ValueError, 'another change'): self.command('credit.pay', dict(values, amount=40), request_id)
        with self.connect() as c: c.execute('UPDATE users SET is_active=0')
        with self.assertRaises(PermissionError): self.command('credit.pay', values, request_id)

    def test_cash_refund_variant_service_batch_stock_once(self):
        receipt = self.sale(items=[dict(product_id=1, qty=2), dict(product_id=2, variant_id=21, qty=1), dict(product_id=3, qty=2)], payment=1000)
        row = self.record('sales', receipt['id']); values = dict(row, reason='Return'); request_id = str(uuid.uuid4())
        self.command('receipt.refund', values, request_id); self.command('receipt.refund', values, request_id)
        self.assertEqual(self.record('products', 1)['stock'], 10); self.assertEqual(self.record('products', 2)['stock'], 3)
        self.assertEqual(self.record('product_variants', 21)['stock'], 3); self.assertEqual(self.record('products', 3)['stock'], 0)
        self.assertEqual(self.record('product_locations', 11)['quantity'], 10)
        with self.assertRaisesRegex(ValueError, 'already refunded'): self.command('receipt.refund', dict(self.record('sales', receipt['id']), reason='Again'))

    def test_credit_refund_unpaid_and_fully_paid_partial_rejected(self):
        receipt, credit = self.credit_sale()
        self.command('receipt.refund', dict(self.record('sales', receipt['id']), reason='Unpaid return'))
        self.assertEqual(self.record('customers', 1)['current_balance'], 0)
        self.assertEqual(self.record('credit_sales', credit['id'])['status'], 'refunded')
        receipt, credit = self.credit_sale(payment=20)
        before = self.record('products', 1)['stock']
        with self.assertRaisesRegex(ValueError, 'partially paid'): self.command('receipt.refund', dict(self.record('sales', receipt['id']), reason='Partial'))
        self.assertEqual(self.record('products', 1)['stock'], before)
        self.command('credit.pay', dict(credit, amount=190))
        self.command('receipt.refund', dict(self.record('sales', receipt['id']), reason='Paid return'))
        self.assertEqual(self.record('customers', 1)['current_balance'], 0)
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT amount FROM credit_payments WHERE payment_method='refund'").fetchone()[0], -210)
        self.assertEqual(self.count('credit_adjustments'), 2)

    def test_refund_failure_rolls_back_stock_and_claim(self):
        receipt, credit = self.credit_sale()
        with self.connect() as c: c.execute('UPDATE customers SET current_balance=0')
        before = self.record('products', 1)['stock']
        with self.assertRaisesRegex(ValueError, 'reconciliation'): self.command('receipt.refund', dict(self.record('sales', receipt['id']), reason='Bad balance'))
        self.assertEqual(self.record('products', 1)['stock'], before)
        self.assertEqual(self.record('sales', receipt['id'])['status'], 'completed')
        self.assertEqual(self.count('native_business_requests'), 0)

    def test_expense_filters_budget_comparison_rename_and_revision(self):
        one = self.command('expense.save', dict(category='Rent', amount=80, expense_date='2026-09-01', description='Shop rent'))['id']
        self.command('expense.save', dict(category='Rent', amount=50, expense_date='2026-08-31'))
        self.command('expense.save', dict(category='Rent', amount=900, expense_date='2026-10-01'))
        self.command('expense.budget', dict(category='Rent', budget_amount=100, year=2026, month=9))
        data = self.repo.read(self.user, 'expenses', start='2026-09-01', end='2026-09-30')
        self.assertEqual((data['total'], data['count']), (80, 1))
        self.assertEqual(data['comparison'], [dict(category='Rent', actual=80, previous=50, budget=100)])
        self.command('expense.category', dict(self.record('expense_categories', 1), name='Office'))
        self.assertEqual(self.record('expenses', one)['category'], 'Office')
        self.assertEqual(self.record('expense_budgets', 1)['category'], 'Office')
        old = self.record('expenses', one); self.command('expense.save', dict(old, amount=90))
        with self.assertRaisesRegex(ValueError, 'changed'): self.command('expense.delete', old)
        self.command('expense.delete', self.record('expenses', one))
        self.assertEqual(self.count('expenses'), 2)

    def test_restaurant_modifiers_kitchen_and_atomic_checkout_retry(self):
        order = self.new_order(); quote = self.repo.quote_order(self.user, order['id'])
        self.assertEqual(quote['total'], 252)
        sent = self.command('restaurant.send', order); self.assertTrue(sent['ticket_id'])
        self.assertEqual(self.count('restaurant_kitchen_tickets'), 1)
        self.command('restaurant.send', self.record('restaurant_orders', order['id']))
        self.assertEqual(self.count('restaurant_kitchen_tickets'), 1)
        for status in ('preparing', 'ready', 'served'):
            self.command('restaurant.kitchen', dict(self.record('restaurant_kitchen_tickets', sent['ticket_id']), status=status))
        quote = self.repo.quote_order(self.user, order['id'])
        values = dict(id=order['id'], revision=quote['revision'], expected_total=252, payment=300); request_id = str(uuid.uuid4())
        result = self.command('restaurant.checkout', values, request_id); replay = self.command('restaurant.checkout', values, request_id)
        self.assertEqual(result['receipt'], replay['receipt']); self.assertEqual(self.count('sales'), 1)
        self.assertEqual(self.record('restaurant_orders', order['id'])['sale_id'], result['receipt']['id'])
        self.assertEqual(self.record('products', 4)['stock'], 0); self.assertEqual(self.count('stock_movements'), 0)

    def test_restaurant_stock_credit_and_settlement_failure_roll_back_together(self):
        order = self.new_order([dict(id=1, qty=2), dict(id=4, qty=1)], customer_id=1)
        quote = self.repo.quote_order(self.user, order['id']); values = dict(id=order['id'], revision=quote['revision'], expected_total=quote['total'], payment=0, payment_type='Credit')
        original_update = self.repo.update
        def failing(c, table, record_id, data):
            if table == 'restaurant_orders' and data.get('status') == 'settled': raise RuntimeError('fixture failed before order settlement')
            return original_update(c, table, record_id, data)
        with patch.object(self.repo, 'update', side_effect=failing):
            with self.assertRaisesRegex(RuntimeError, 'fixture'): self.command('restaurant.checkout', values)
        self.assertEqual(self.count('sales'), 0); self.assertEqual(self.record('products', 1)['stock'], 10)
        self.assertEqual(self.count('credit_sales'), 0); self.assertEqual(self.record('customers', 1)['current_balance'], 0)
        result = self.command('restaurant.checkout', values)
        self.assertEqual(result['receipt']['total'], 315); self.assertEqual(self.record('products', 1)['stock'], 8)
        self.assertEqual(self.record('customers', 1)['current_balance'], 315)

    def test_restaurant_cancel_reopen_table_occupancy_and_stale_quote(self):
        self.command('restaurant.table', dict(table_no='T1', seats=4))
        order = self.new_order(table_id=1)
        with self.assertRaisesRegex(ValueError, 'open order'): self.new_order(table_id=1)
        sent = self.command('restaurant.send', order)
        self.command('restaurant.cancel', dict(self.record('restaurant_orders', order['id']), reason='Customer left'))
        self.assertEqual(self.record('restaurant_kitchen_tickets', sent['ticket_id'])['status'], 'cancelled')
        self.command('restaurant.reopen', self.record('restaurant_orders', order['id']))
        quote = self.repo.quote_order(self.user, order['id'])
        with self.connect() as c: c.execute('UPDATE products SET price=110 WHERE id=4')
        with self.assertRaisesRegex(ValueError, 'Prices'): self.command('restaurant.checkout', dict(quote, expected_total=quote['total'], payment=500))
        self.assertEqual(self.count('sales'), 0)

    def test_modifier_price_is_server_owned_and_invalid_choices_rejected(self):
        order = self.new_order([dict(id=4, qty=1, price=1, restaurant_modifiers=[dict(group='Protein', name='Chicken', price_delta=-99)])])
        self.assertEqual(self.repo.quote_order(self.user, order['id'])['total'], 126)
        for options in ([dict(name='Missing')], [dict(group='Protein', name='Chicken'), dict(group='Protein', name='Beef')]):
            with self.assertRaises(ValueError): self.new_order([dict(id=4, qty=1, restaurant_modifiers=options)])

    def test_sent_order_additions_legacy_cart_flags_and_modifier_receipt(self):
        order = self.new_order(); self.command('restaurant.send', order)
        order = self.repo.read(self.user, 'restaurant', order['id']); cart = order['cart']
        self.assertTrue(cart[0]['is_service']); self.assertTrue(cart[0]['is_restaurant'])
        self.assertEqual(cart[0]['modifier_key'], 'Chicken'); self.assertEqual(cart[0]['original_price'], 100)
        cart[0]['qty'] = 3
        self.command('restaurant.save', dict(order, cart=cart))
        self.command('restaurant.send', self.record('restaurant_orders', order['id']))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT SUM(quantity) FROM restaurant_kitchen_ticket_items').fetchone()[0], 3)
        old = self.repo.read(self.user, 'restaurant', order['id']); old['cart'][0]['qty'] = 1
        with self.assertRaisesRegex(ValueError, 'Sent items'): self.command('restaurant.save', old)
        quote = self.repo.quote_order(self.user, order['id']); self.assertIn('Chicken', quote['items'][0]['product_name'])
        result = self.command('restaurant.checkout', dict(quote, expected_total=quote['total'], payment=500))
        self.assertIn('Chicken', result['receipt']['items'][0]['product_name'])

    def test_native_menu_configuration_and_negative_modifier_roundtrip(self):
        from server.native_catalog import CatalogRepository
        from native_pos.catalog_dialogs import ProductDialog
        catalog = CatalogRepository(types.SimpleNamespace(**self.scope))
        product = catalog.read(self.user, 'products', 4)
        product['restaurant_modifiers'] = [dict(group='Size', name='Small', type='choice', price_delta=-20)]
        catalog.command(self.user, str(uuid.uuid4()), 'product.save', product)
        saved = catalog.read(self.user, 'products', 4)
        self.assertEqual(json.loads(saved['restaurant_modifiers'])[0]['price_delta'], -20)
        with self.assertRaisesRegex(ValueError, 'do not track stock'):
            catalog.command(self.user, str(uuid.uuid4()), 'stock.in', dict(product_id=4, stock_revision=saved['stock_revision'], quantity=1, reason='test'))

    def test_api_command_and_unauthorized_read(self):
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo)
        with LocalApiClient(app) as client:
            response = client.post('/api/native/business/commands', json=dict(request_id=str(uuid.uuid4()), operation='customer.save', values={'name': 'API'}))
            self.assertEqual(response.status_code, 200); self.assertIn('result', response.json())
            with self.connect() as c: c.execute("UPDATE users SET role='Cashier',permissions='sales'")
            response = client.post('/api/native/business/commands', json=dict(request_id=str(uuid.uuid4()), operation='customer.save', values={'name': 'Denied'}))
            self.assertEqual(response.status_code, 403)
        with self.assertRaises(PermissionError): self.repo.read(self.user, 'expenses')


class BusinessUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.window = NativeWindow(NativeTheme(self.app), Path(self.folder.name) / 'settings.json')
        self.window.session = Session(1, 'tester', 'Tester', 'Admin', frozenset())
        self.window.store = ServerStore(Target('Server', server_url='https://fixture.invalid'))
        self.api = Mock(); self.api.server_url = 'https://fixture.invalid'; self.window.store.client = self.api
        self.window.populate_routes(); self.addCleanup(self.window.close)
        for p in self.window.route_pages.values():
            if hasattr(p, 'loaded'): p.loaded = True

    def wait(self):
        if not self.window.runner.busy: return
        loop = QEventLoop(); self.window.runner.idle.connect(loop.quit); QTimer.singleShot(4000, loop.quit); loop.exec()
        self.assertFalse(self.window.runner.busy)

    def test_phase5_routes_permissions_stock_widgets_and_1366_layout(self):
        for route in (4, 6, 7, 10): self.assertIsInstance(self.window.route_pages[route], BusinessPage)
        with patch.object(self.window, 'screen') as screen:
            screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728)
            self.window._fit_display(); self.window.show(); self.app.processEvents()
        self.assertLessEqual(self.window.width(), 1366); self.assertLessEqual(self.window.height(), 728)
        for route in (4, 6, 7, 10):
            self.window.navigate(route); self.app.processEvents(); page = self.window.route_pages[route]
            self.assertLessEqual(page.minimumSizeHint().width(), 1160)
            self.assertLessEqual(self.window.minimumSizeHint().height(), 702)
            self.assertFalse(page.styleSheet())
        for fields in (CUSTOMER_FORM, [('amount', 'Amount', 'money', 0)]):
            dialog = FormDialog('Fixture', fields, parent=self.window); dialog.show(); self.app.processEvents()
            self.assertLess(dialog.height(), 650); dialog.reject()

    def test_pending_payment_restarts_and_reuses_payload(self):
        channel = self.window.business_session
        self.api._request.side_effect = RuntimeError('Lost reply')
        channel.submit('credit.pay', dict(id=3, revision='fixture', amount=50)); self.wait()
        payload = deepcopy(channel.pending['payload']); self.assertTrue(channel.pending)
        restored = CatalogSession(self.window, 'business'); self.assertEqual(restored.pending['payload'], payload)
        self.api._request.side_effect = None
        self.api._request.return_value = {'result': dict(request_id=payload['request_id'], operation='credit.pay', message='Paid')}
        restored.recover(); self.wait(); self.assertIsNone(restored.pending)
        self.assertEqual(self.api._request.call_args.kwargs['json'], payload)

    def test_cancelled_customer_form_sends_nothing_and_csv_escapes_formulas(self):
        page = self.window.route_pages[6]
        with patch.object(FormDialog, 'exec', return_value=QDialog.DialogCode.Rejected): page.customer(False)
        self.api._request.assert_not_called()
        self.assertEqual(safe_csv('=SUM(A1)'), "'=SUM(A1)")
        self.assertEqual(safe_csv('Myanmar'), 'Myanmar')


if __name__ == '__main__': unittest.main()
