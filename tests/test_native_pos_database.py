"""Read-only diagnostics using disposable SQLite and a PostgreSQL protocol stub."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from server.native_database import DatabaseRepository, TABLES, install_routes
from tests import test_native_pos_phase7 as phase7
from tests.test_native_pos_phase3 import LocalApiClient


class DatabaseDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.repo = DatabaseRepository(types.SimpleNamespace(**self.fixture.scope))

    def snapshot(self):
        with self.fixture.connect() as conn: return list(conn.iterdump())

    def test_sqlite_integrity_no_mutation_or_secret_content(self):
        with self.fixture.connect() as conn:
            conn.execute("INSERT INTO settings(key,value) VALUES('private_fixture','secret-connection-string')")
        before = self.snapshot()
        report = self.repo.read(self.fixture.user, True)
        self.assertEqual(report['backend'], 'SQLite'); self.assertEqual(report['integrity']['status'], 'OK')
        self.assertEqual(report['schema_status'], 'Ready')
        self.assertEqual(before, self.snapshot())
        self.assertNotIn('secret-connection-string', json.dumps(report))
        self.assertNotIn('Test Employee', json.dumps(report))
        self.assertEqual(next(r for r in report['records'] if r['table'] == 'network_print_jobs')['status'], 'Not initialized')

    def test_missing_core_column_is_reported_without_repair(self):
        with self.fixture.connect() as conn: conn.execute('ALTER TABLE products DROP COLUMN price')
        report = self.repo.read(self.fixture.user)
        self.assertEqual(report['schema_status'], 'Needs attention')
        row = next(r for r in report['records'] if r['table'] == 'products')
        self.assertIn('price', row['missing_columns'])
        self.assertEqual(report['integrity']['status'], 'Not run')
        with self.fixture.connect() as conn:
            self.assertNotIn('price', [r[1] for r in conn.execute('PRAGMA table_info(products)')])

    def test_api_fresh_permissions_and_sanitized_failure(self):
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.fixture.user, self.repo); client = LocalApiClient(app)
        self.assertEqual(client.get('/api/native/database/diagnostics?integrity=true').status_code, 200)
        with self.fixture.connect() as conn: conn.execute('UPDATE users SET is_active=0 WHERE id=1')
        self.assertEqual(client.get('/api/native/database/diagnostics').status_code, 403)
        with patch.object(self.repo, 'read', side_effect=RuntimeError('secret-connection-string')):
            response = client.get('/api/native/database/diagnostics')
            self.assertEqual(response.status_code, 503); self.assertNotIn('secret-connection-string', str(response.json()))

    def test_quick_check_timeout_releases_connection(self):
        connection = Mock(); cursor = connection.cursor.return_value
        cursor.fetchone.return_value = (1,)
        def execute(sql, args=()):
            if sql.startswith('PRAGMA quick_check'): raise RuntimeError('interrupted')
        cursor.execute.side_effect = execute; cursor.fetchall.return_value = []
        service = types.SimpleNamespace(connect_db=lambda: connection, is_postgres_backend=lambda: False)
        repo = DatabaseRepository(service)
        with patch.object(repo, 'authorize'):
            with self.assertRaisesRegex(RuntimeError, 'interrupted'): repo.read(self.fixture.user, True)
        connection.set_progress_handler.assert_called_with(None, 0)
        connection.rollback.assert_called_once(); connection.close.assert_called_once()

    def test_postgres_read_only_metadata_protocol(self):
        connection = Mock(); cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [(1,), ('16.4',)]
        cursor.fetchall.return_value = [(table, column) for table, (_, columns) in TABLES.items() for column in columns]
        repo = DatabaseRepository(types.SimpleNamespace(connect_db=lambda: connection, is_postgres_backend=lambda: True))
        with patch.object(repo, 'authorize'): report = repo.read(self.fixture.user, True)
        self.assertEqual(report['backend'], 'PostgreSQL'); self.assertEqual(report['integrity']['status'], 'Not supported')
        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(sql[0], 'SET TRANSACTION READ ONLY')
        self.assertTrue(any('statement_timeout' in command for command in sql))
        self.assertFalse(any('PRAGMA' in command for command in sql))
        connection.commit.assert_not_called(); connection.rollback.assert_called_once()


class DatabaseDiagnosticUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_export_snapshot_and_view_only_role(self):
        from native_pos.database_diagnostics import DatabaseDiagnosticsDialog
        from native_pos.data import Session
        host = types.SimpleNamespace(session=Session(1, 'viewer', 'Viewer', 'Viewer', frozenset({'settings'})))
        dialog = DatabaseDiagnosticsDialog(host); self.addCleanup(dialog.close)
        self.assertFalse(dialog.run_button.isEnabled()); self.assertFalse(dialog.export_button.isEnabled())
        report = dict(backend='SQLite', version='fixture', schema_status='Ready', checked_at='2026-09-04', journal_mode='WAL', records=[dict(table='sales', scope='Core', status='Ready', missing_columns='', columns_found=5)], integrity=dict(status='OK', details=['ok']), notes=['Fixture only'])
        dialog.received(report)
        self.assertEqual(dialog.table.rowCount(), 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'diagnostics.json'
            with patch('native_pos.database_diagnostics.QFileDialog.getSaveFileName', return_value=(str(path), 'JSON')): dialog.export()
            self.assertEqual(json.loads(path.read_text()), report)


if __name__ == '__main__': unittest.main()
