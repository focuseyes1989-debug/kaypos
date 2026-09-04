"""Phase 7: disposable database, no production bootstrap, network or devices."""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
import types
from collections import defaultdict
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from server.native_admin import AdminRepository, install_routes
from services.employee_transaction import connect as employee_connect
from services.employee_transaction import active as transaction_active
from tests import test_native_pos_phase5 as phase5
from tests.test_native_pos_phase3 import LocalApiClient
from utils.db_compat import ensure_column

ROOT = Path(__file__).resolve().parents[1]


def isolated_employee(connect):
    tree = ast.parse((ROOT / 'services/employee_service.py').read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    scope = dict(_connect_db=connect, _employee_connect=employee_connect,
                 date=date, datetime=datetime, ensure_column=ensure_column, is_postgres_backend=lambda: False)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])), 'isolated_employee.py', 'exec'), scope)
    return types.SimpleNamespace(**scope)


class AdminDatabaseTests(unittest.TestCase):
    connect = phase5.BusinessDatabaseTests.connect
    count = phase5.BusinessDatabaseTests.count

    def setUp(self):
        phase5.BusinessDatabaseTests.setUp(self)
        with self.connect() as c:
            c.execute("ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''")
            c.execute('ALTER TABLE users ADD COLUMN salt TEXT')
            c.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
            roles = c.execute('SELECT name,permissions FROM user_roles').fetchall()
            c.execute('DROP TABLE user_roles')
            c.execute("CREATE TABLE user_roles(id INTEGER PRIMARY KEY,name TEXT UNIQUE,permissions TEXT,description TEXT DEFAULT '',is_system INTEGER DEFAULT 0)")
            c.executemany('INSERT INTO user_roles(name,permissions) VALUES(?,?)', roles)
            c.execute("INSERT INTO user_roles(name,permissions) VALUES('Admin','')")
        self.employee = isolated_employee(self.connect)
        self.repo = AdminRepository(types.SimpleNamespace(**self.scope), self.employee)
        self.command('employee.employees.save', dict(employee_no='EMP-1', full_name='Test Employee', hire_date='2026-01-01', user_id=1))

    def command(self, op, values, request_id=None):
        return self.repo.command(self.user, request_id or str(uuid4()), op, values)

    def read(self, section):
        return self.repo.read(self.user, section, '2026-01-01', '2026-12-31')

    def test_employee_stale_and_preserved_photo(self):
        with self.connect() as c: c.execute("UPDATE employees SET photo_data=X'1234',photo_path='kept.jpg',zkteco_user_id='9' WHERE id=1")
        row = self.read('employees')['records'][0]
        self.assertNotIn('photo_data', row)
        self.command('employee.employees.save', dict(row, full_name='Changed'))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT photo_data,photo_path,zkteco_user_id FROM employees').fetchone(), (b'\x12\x34', 'kept.jpg', '9'))
        with self.assertRaisesRegex(ValueError, 'changed'): self.command('employee.employees.save', row)

    def test_salary_atomic_replay_and_expense(self):
        self.command('employee.payroll.save', dict(employee_id=1, period_month='2026-09', basic_salary=1000, allowance=100, late_deduction=50))
        row = self.read('payroll')['records'][0]; self.assertEqual(row['net_salary'], 1050)
        request_id = str(uuid4()); values = dict(row, paid_date='2026-09-04', payment_method='Cash')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.command('employee.payroll.pay', values, request_id), range(2)))
        self.assertEqual(results[0], results[1]); self.assertEqual(self.count('expenses'), 1)
        with self.assertRaisesRegex(ValueError, 'draft'): self.command('employee.payroll.pay', dict(self.read('payroll')['records'][0], paid_date='2026-09-04', payment_method='Cash'))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT expense_id FROM payrolls').fetchone()[0], c.execute('SELECT id FROM expenses').fetchone()[0])

    def test_audit_failure_rolls_back_employee_and_receipt(self):
        before = self.count('employees')
        original = self.repo.insert
        def fail(c, table, values):
            if table == 'user_activity_log': raise RuntimeError('Audit unavailable')
            return original(c, table, values)
        with patch.object(self.repo, 'insert', fail):
            with self.assertRaisesRegex(RuntimeError, 'Audit'):
                self.command('employee.employees.save', dict(employee_no='EMP-2', full_name='New', hire_date='2026-01-01'))
        self.assertEqual(self.count('employees'), before)

    def test_attendance_correction_and_duplicate_guard(self):
        values = dict(employee_id=1, attendance_date='2026-09-04', check_in='09:30', check_out='17:00', correction_reason='Supervisor confirmed', status='Late')
        self.command('employee.attendance.save', values)
        with self.assertRaisesRegex(ValueError, 'exists'): self.command('employee.attendance.save', values)
        row = self.read('attendance')['records'][0]
        self.assertEqual(row['corrected_by'], 1)
        self.command('employee.attendance.save', dict(row, status='Present'))
        self.employee.recalculate_attendance_categories(1)
        self.assertEqual(self.read('attendance')['records'][0]['status'], 'Present')
        with self.assertRaises(ValueError): self.command('employee.attendance.save', dict(values, attendance_date='2026-09-05', check_in='25:01'))

    def test_advance_bounds_and_cash_once(self):
        self.command('employee.advances.save', dict(employee_id=1, advance_date='2026-09-04', amount=100))
        row = self.read('advances')['records'][0]
        with self.assertRaisesRegex(ValueError, 'exceeds'): self.command('employee.advances.repay', dict(row, amount=101))
        request_id = str(uuid4())
        self.command('employee.advances.repay', dict(row, amount=100), request_id)
        self.command('employee.advances.repay', dict(row, amount=100), request_id)
        self.assertEqual(self.read('advances')['records'][0]['repaid_amount'], 100)
        self.command('employee.cash.save', dict(employee_id=1, opening_cash=100))
        with self.assertRaisesRegex(ValueError, 'already'): self.command('employee.cash.save', dict(employee_id=1))
        row = self.read('cash')['records'][0]
        self.command('employee.cash.close', dict(row, actual_cash=90))
        self.assertEqual(self.read('cash')['records'][0]['difference'], -10)

    def test_settings_stale_and_unknown_keys_ignored(self):
        data = self.read('general')
        values = dict(data['values'], section='general', revision=data['revision'], tax_rate=10, database_url='bad')
        self.command('settings.save', values)
        with self.assertRaisesRegex(ValueError, 'changed'): self.command('settings.save', values)
        with self.connect() as c: self.assertIsNone(c.execute("SELECT value FROM settings WHERE key='database_url'").fetchone())

    def test_permissions_fresh_and_schema_does_not_grant_roles(self):
        with self.connect() as c:
            c.execute("UPDATE users SET role='Restricted',permissions='employees,attendance' WHERE id=1")
            c.execute("INSERT INTO user_roles(name,permissions) VALUES('Restricted','')")
        self.read('attendance')
        with self.assertRaises(PermissionError): self.read('payroll')
        with self.assertRaises(PermissionError): self.command('employee.attendance.save', {})
        with self.connect() as c: self.assertEqual(c.execute("SELECT permissions FROM user_roles WHERE name='Restricted'").fetchone()[0], '')

    def test_api_auth_and_validation(self):
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo); client = LocalApiClient(app)
        self.assertEqual(client.get('/api/native/admin?section=employees').status_code, 200)
        result = client.post('/api/native/admin/commands', dict(request_id=str(uuid4()), operation='employee.payroll.save', values=dict(employee_id=1, period_month='bad')))
        self.assertIn('rejected', result.json())
        with self.connect() as c: c.execute('UPDATE users SET is_active=0 WHERE id=1')
        self.assertEqual(client.get('/api/native/admin?section=employees').status_code, 403)

    def test_all_employee_sections(self):
        from native_pos.admin_schema import EMPLOYEE_SECTIONS
        for section in EMPLOYEE_SECTIONS:
            with self.subTest(section=section): self.assertIn('records', self.read(section))

    def test_leave_shift_document_commission(self):
        self.command('employee.assignments.save', dict(employee_id=1, shift_id=1, effective_from='2026-01-01', weekly_off_days='5,6'))
        assignment = self.read('assignments')['records'][0]
        self.command('employee.assignments.save', dict(assignment, weekly_off_days='6'))
        self.command('employee.leave.save', dict(employee_id=1, leave_type='Annual', start_date='2026-09-04', end_date='2026-09-05', days=2))
        row = self.read('leave')['records'][0]
        self.command('employee.leave.review', dict(row, status='Approved', review_notes='Confirmed'))
        self.assertEqual(self.read('leave')['records'][0]['reviewed_by'], 1)
        self.command('employee.documents.save', dict(employee_id=1, document_type='ID', document_no='ABC'))
        self.command('employee.commission.save', dict(employee_id=1, rate_percent=5, target_amount=100))
        self.assertEqual(len(self.read('documents')['records']), 1)
        self.assertEqual(self.read('commission')['records'][0]['rate_percent'], 5)

    def test_users_password_hash_and_admin_recovery(self):
        result = self.command('user.save', dict(username='new-user', full_name='New', role='Admin', password='fixture-password', is_active=True))
        with self.connect() as c:
            salt, hashed = c.execute('SELECT salt,password_hash FROM users WHERE id=?', (result['id'],)).fetchone()
            self.assertNotIn('fixture-password', str(c.execute('SELECT * FROM native_admin_requests').fetchall()))
            self.assertEqual(len(salt), 64); self.assertEqual(len(hashed), 64)
        row = next(r for r in self.read('users')['records'] if r['id'] == 1)
        with self.assertRaisesRegex(ValueError, 'own administrator'): self.command('user.save', dict(row, is_active=False))

    def test_custom_role_round_trip_and_builtin_protection(self):
        result = self.command('role.save', dict(name='Attendance Viewer', permissions='employees,attendance', description='Custom role'))
        row = next(r for r in self.read('roles')['records'] if r['id'] == result['id'])
        self.command('role.save', dict(row, permissions='employees,attendance,shifts'))
        saved = next(r for r in self.read('roles')['records'] if r['id'] == result['id'])
        self.assertIn('shifts', saved['permissions'])
        admin = next(r for r in self.read('roles')['records'] if r['name'] == 'Admin')
        with self.assertRaisesRegex(ValueError, 'Built-in'): self.command('role.save', admin)

    def test_backup_wal_replay_restore_clone_and_path_guard(self):
        from server.native_backup import BackupRepository
        with tempfile.TemporaryDirectory() as folder:
            repo = BackupRepository(types.SimpleNamespace(**self.scope), folder)
            connection = self.connect()
            try:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute("UPDATE employees SET phone='WAL-data' WHERE id=1"); connection.commit()
                request_id = str(uuid4()); backup = repo.create(self.user, request_id)
                connection.execute("UPDATE employees SET phone='newer' WHERE id=1"); connection.commit()
                self.assertEqual(repo.create(self.user, request_id)['sha256'], backup['sha256'])
                restored = repo.rehearse(self.user, backup['name'], backup['sha256'])
                import sqlite3
                copied = sqlite3.connect(Path(folder) / restored['copy_name'])
                try: self.assertEqual(copied.execute('SELECT phone FROM employees').fetchone()[0], 'WAL-data')
                finally: copied.close()
                self.assertEqual(connection.execute('SELECT phone FROM employees').fetchone()[0], 'newer')
                with self.assertRaises(ValueError): repo.path('../pos.db')
                with self.assertRaisesRegex(ValueError, 'changed'): repo.rehearse(self.user, backup['name'], 'bad')
            finally: connection.close()

    def test_device_sync_deduplicates_and_retains_manual_correction(self):
        from server.native_operations import OperationsRepository
        tree = ast.parse((ROOT / 'services/zkteco_service.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        device = Mock()
        device.get_time.return_value = datetime(2026, 9, 4, 20)
        device.get_users.return_value = [types.SimpleNamespace(user_id='5', name='Device User')]
        device.get_attendance.return_value = [types.SimpleNamespace(user_id='5', timestamp=datetime(2026, 9, 4, h), status=0, punch=p) for h, p in ((8, 0), (17, 1))]
        logs = device.get_attendance.return_value
        def device_read_with_concurrent_writer():
            with self.connect() as c:
                c.execute('PRAGMA busy_timeout=100')
                c.execute('BEGIN IMMEDIATE')
                c.execute("UPDATE employees SET phone='Concurrent writer succeeded' WHERE id=1")
            return logs
        device.get_attendance.side_effect = device_read_with_concurrent_writer
        device.get_serialnumber.return_value = 'TEST-SERIAL'
        scope = dict(_connect_db=self.connect, _employee_connect=employee_connect, _transaction_active=transaction_active,
                     ensure_employee_schema=self.employee.ensure_employee_schema, recalculate_attendance_categories=self.employee.recalculate_attendance_categories,
                     is_postgres_backend=lambda: False, datetime=datetime, timedelta=timedelta, defaultdict=defaultdict, sys=sys,
                     DEFAULT_DEVICE=dict(device_no=1, name='Fixture', ip_address='127.0.0.1', port=4370, comm_key=0))
        module = ast.Module(body=[*ast.parse('from __future__ import annotations').body, *nodes], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), 'isolated_zkteco.py', 'exec'), scope)
        scope['_connect'] = Mock(return_value=device)
        repo = OperationsRepository(types.SimpleNamespace(**self.scope), self.employee, types.SimpleNamespace(**scope))
        first = repo.read(self.user)['devices'][0]
        repo.command(self.user, str(uuid4()), 'mapping.save', dict(device_id=first['id'], employee_id=1, device_user_id='5'))
        request_id = str(uuid4())
        result = repo.command(self.user, request_id, 'device.sync', first)
        self.assertEqual(result['details'][0]['inserted'], 2)
        with patch.object(repo.device, 'read_device_data', side_effect=RuntimeError('Device offline')):
            self.assertEqual(repo.command(self.user, request_id, 'device.sync', first), result)
        row = self.read('attendance')['records'][0]
        self.command('employee.attendance.save', dict(row, check_in='09:00', correction_reason='Manual correction'))
        updated = repo.read(self.user)['devices'][0]
        result = repo.command(self.user, str(uuid4()), 'device.sync', updated)
        self.assertEqual(result['details'][0]['duplicates'], 2)
        self.assertEqual(self.read('attendance')['records'][0]['check_in'], '09:00')
        device.disconnect.assert_called()
        self.assertNotIn('comm_key', updated)

    def test_assistant_navigation_and_permission_enforcement(self):
        from server.native_assistant import AssistantRepository
        repo = AssistantRepository(types.SimpleNamespace(**self.scope), self.employee)
        self.assertEqual(repo.ask(self.user, 'open attendance')['route_id'], 11)
        with self.connect() as c: c.execute("UPDATE users SET role='Cashier',permissions='ai_pages,employees' WHERE id=1")
        with self.assertRaises(PermissionError): repo.ask(self.user, 'open payroll')
        with self.assertRaises(PermissionError): repo.ask(self.user, 'today sales')

    def test_integration_checks_use_configured_adapter_and_fresh_access(self):
        from server.native_integrations import IntegrationRepository
        adapter = Mock(); adapter.status.return_value = [dict(service='Telegram', configured=True)]
        adapter.test.return_value = dict(message='Connection OK')
        repo = IntegrationRepository(types.SimpleNamespace(**self.scope), adapter)
        self.assertEqual(repo.read(self.user)['records'][0]['service'], 'Telegram')
        self.assertEqual(repo.test(self.user, 'Telegram')['message'], 'Connection OK')
        with self.connect() as c: c.execute("UPDATE users SET role='Restricted',permissions='settings' WHERE id=1")
        with self.assertRaises(PermissionError): repo.test(self.user, 'Telegram')
        adapter.test.assert_called_once_with('Telegram')

    def test_duplicate_account_is_confirmed_rejection_and_receipt_settings(self):
        from fastapi import FastAPI
        from native_pos.receipt import receipt_html
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo); client = LocalApiClient(app)
        response = client.post('/api/native/admin/commands', dict(request_id=str(uuid4()), operation='user.save',
            values=dict(username='cashier', role='Admin', password='fixture-password')))
        self.assertIn('already exists', response.json()['rejected'])
        data = self.read('receipt')
        self.command('settings.save', dict(data['values'], section='receipt', revision=data['revision'], shop_name='<Fixture Shop>', receipt_footer='Thanks'))
        receipt = self.sale(items=[dict(product_id=1, qty=1)], payment=105, request_id=str(uuid4()))
        self.assertIn('&lt;Fixture Shop&gt;', receipt_html(receipt))
        self.assertIn('Thanks', receipt_html(receipt))


class AdminUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_assistant_import_never_bootstraps_database_or_qt(self):
        import subprocess
        code = '''import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('models.database', 'PyQt6')):
            raise RuntimeError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, Block())
import server.native_assistant
from ui.ai_pages import NLProcessor
assert NLProcessor.detect_intent('today sales')['intent'] == 'sales_today'
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_windows_credential_recovery_is_encrypted(self):
        from native_pos.protected_journal import ProtectedJournal
        with tempfile.TemporaryDirectory() as folder:
            journal = ProtectedJournal('https://fixture.invalid/admin', 1, folder)
            data = dict(payload=dict(request_id=str(uuid4()), operation='user.save', values=dict(password='secret-fixture-password')))
            journal.write(data)
            self.assertNotIn('secret-fixture-password', journal.path.read_text())
            self.assertEqual(journal.read(), data)
            journal.write(dict(data, result={'message': 'Saved'}))
            self.assertNotIn('password', journal.path.read_text())

    def test_native_admin_layout_and_reference_form(self):
        from PyQt6.QtCore import QRect
        from native_pos.data import Session, ServerStore, Target
        from native_pos.window import NativeWindow
        from native_pos.theme import NativeTheme
        from native_pos.admin import EmployeeForm
        from native_pos.admin_schema import EMPLOYEE_FIELDS
        with tempfile.TemporaryDirectory() as folder:
            window = NativeWindow(NativeTheme(self.app), Path(folder) / 'config.json')
            with patch.object(window, 'screen') as screen:
                screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728); window._fit_display()
            window.session = Session(1, 'admin', 'Admin', 'Admin', frozenset())
            window.store = ServerStore(Target('Server', server_url='https://fixture.invalid'))
            window.store.client = Mock(server_url='https://fixture.invalid')
            window.populate_routes()
            for page in window.route_pages.values():
                if hasattr(page, 'loaded'): page.loaded = True
            window.show(); window.navigate(11); self.app.processEvents()
            self.assertLessEqual(window.frameGeometry().height(), 728)
            self.assertLessEqual(window.frameGeometry().width(), 1366)
            form = EmployeeForm('Employee', EMPLOYEE_FIELDS, {'users': [dict(id=1, username='admin', full_name='Admin')]}, {'user_id': 1}, window)
            self.assertEqual(form.values()['user_id'], 1); form.close()
            form = EmployeeForm('Employee', EMPLOYEE_FIELDS, {'users': []}, {'user_id': 42}, window)
            self.assertEqual(form.values()['user_id'], 42); form.close()
            page = window.route_pages[11]; page.received(dict(records=[], employees=[], users=[], shifts=[]))
            self.assertTrue(page.new_button.isEnabled())
            window.close(); self.app.processEvents()


if __name__ == '__main__': unittest.main()
