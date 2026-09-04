from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import QApplication, QStyleFactory
from native_pos.config import load_config, save_config
from native_pos.data import ReadOnlyStore, Target, create_practice_database
from native_pos.routes import ROUTES
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow

@contextmanager
def update_database(path):
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()

class NativeDataTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root=Path(folder.name); self.db=self.root/'practice.db'
        create_practice_database(self.db,'tester','practice-password')
        self.store=ReadOnlyStore(Target(database=str(self.db)))

    def test_legacy_hash_login_and_database_stays_identical(self):
        before=self.db.read_bytes()
        self.assertIn('read-only',self.store.diagnose())
        session=self.store.authenticate('tester','practice-password')
        self.assertEqual(session.username,'tester')
        self.assertTrue(all(session.can(route.permission) for route in ROUTES))
        self.assertEqual(before,self.db.read_bytes())
        with self.store.connection() as conn:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute('DELETE FROM users')

    def test_permission_union_and_account_restrictions(self):
        with update_database(self.db) as conn:
            conn.execute("UPDATE users SET role='Cashier', permissions='customers'")
            conn.execute("INSERT INTO user_roles (name,permissions) VALUES ('Cashier','sales,receipts')")
        session=self.store.authenticate('tester','practice-password')
        self.assertEqual(session.permissions,frozenset({'sales','receipts','customers'}))
        self.assertFalse(session.can('products'))
        for field in ('is_active','force_password_change'):
            with update_database(self.db) as conn:
                conn.execute('UPDATE users SET is_active=1, force_password_change=0')
                conn.execute(f'UPDATE users SET {field}=?',(0 if field=='is_active' else 1,))
            with self.assertRaises(ValueError): self.store.authenticate('tester','practice-password')
        with self.assertRaises(ValueError): self.store.authenticate('tester','wrong')

    def test_missing_file_and_practice_no_overwrite(self):
        missing=self.root/'missing.db'
        with self.assertRaises(ValueError): ReadOnlyStore(Target(database=str(missing))).diagnose()
        self.assertFalse(missing.exists())
        before=self.db.read_bytes()
        with self.assertRaises(FileExistsError): create_practice_database(self.db,'another','other-password')
        self.assertEqual(before,self.db.read_bytes())

    def test_postgres_rejects_production_schema_and_missing_environment(self):
        with self.assertRaises(ValueError): ReadOnlyStore(Target('PostgreSQL',schema='public')).diagnose()
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'NATIVE_POS_TEST_DATABASE_URL'):
                ReadOnlyStore(Target('PostgreSQL')).diagnose()

    def test_postgres_connection_requests_read_only_schema_and_timeout(self):
        driver = Mock()
        with patch.dict(sys.modules, {'psycopg': driver}), patch.dict(os.environ, {'NATIVE_POS_TEST_DATABASE_URL': 'postgresql://test:example@localhost/isolated'}):
            store = ReadOnlyStore(Target('PostgreSQL', schema='practice_test'))
            with store.connection() as conn:
                self.assertIs(conn, driver.connect.return_value)
        kwargs = driver.connect.call_args.kwargs
        self.assertEqual(kwargs['connect_timeout'], 5)
        self.assertIn('default_transaction_read_only=on', kwargs['options'])
        self.assertIn('search_path=practice_test', kwargs['options'])
        self.assertIn('statement_timeout=5000', kwargs['options'])
        driver.connect.return_value.close.assert_called_once()

    def test_settings_whitelist_and_corrupt_file(self):
        path=self.root/'prefs.json'
        save_config({'style':'Fusion','font_size':12,'password':'secret','dsn':'secret'},path)
        text=path.read_text()
        self.assertNotIn('secret',text)
        self.assertEqual(load_config(path)['font_size'],12)
        path.write_text('[]')
        self.assertEqual(load_config(path)['style'],'System')
        path.write_text('{bad')
        self.assertEqual(load_config(path)['font_size'],10)

    def test_import_does_not_load_legacy_database_or_ui(self):
        result=subprocess.run([sys.executable,'-c',"import sys; import native_pos.window; assert not any(n.startswith(('models.database','ui.','server.')) for n in sys.modules)"],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

class NativeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        folder=tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root=Path(folder.name); self.db=self.root/'practice.db'; self.prefs=self.root/'prefs.json'
        create_practice_database(self.db,'tester','practice-password')
        self.theme=NativeTheme(self.app)
        self.window=NativeWindow(self.theme,self.prefs)
        self.addCleanup(self.window.close)
        self.window.login_dialog.backend.setCurrentText('SQLite')
        self.window.login_dialog.database.setText(str(self.db))
        self.window.login_dialog.username.setText('tester')
        self.window.login_dialog.password.setText('practice-password')
    def wait_idle(self):
        if not self.window.runner.busy: return
        loop=QEventLoop(); self.window.runner.idle.connect(loop.quit)
        timer=QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit); timer.start(5000)
        loop.exec(); timer.stop()
        self.window.runner.idle.disconnect(loop.quit)
        self.assertFalse(self.window.runner.busy)
    def test_login_navigation_logout_and_settings_isolation(self):
        self.window.show_login()
        self.window.login_dialog.password.setText('practice-password')
        self.window.login(); self.wait_idle()
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.login_dialog.isVisible())
        self.assertEqual(self.window.navigation.count(),len(ROUTES))
        self.assertEqual(self.window.login_dialog.password.text(),'')
        self.assertTrue(self.window.navigate(10))
        self.assertFalse(self.window.navigate(999))
        self.window.logout()
        self.assertIsNone(self.window.session)
        self.assertEqual(self.window.pages.count(),0)
        self.assertTrue(self.window.login_dialog.isVisible())
        self.assertNotIn('practice-password',self.prefs.read_text())
    def test_permissions_apply_to_navigation_and_direct_route(self):
        with update_database(self.db) as conn:
            conn.execute("UPDATE users SET role='Cashier', permissions='sales'")
        self.window.login(); self.wait_idle()
        self.assertEqual(set(self.window.route_pages),{5,10})
        self.assertFalse(self.window.navigate(2))
        self.assertTrue(self.window.navigate(5))
    def test_failed_login_and_connection_release_busy_state(self):
        self.window.login_dialog.password.setText('wrong')
        self.window.login(); self.wait_idle()
        self.assertIsNone(self.window.session)
        self.assertIn('Invalid',self.window.login_dialog.status.text())
        self.assertTrue(self.window.login_dialog.sign_in.isEnabled())
        self.window.test_connection(); self.wait_idle()
        self.assertIn('read-only',self.window.login_dialog.status.text())
    def test_native_styles_and_palette_without_stylesheet(self):
        for mode in ('System','Light','Dark'):
            self.theme.apply(dict(style='System',palette=mode,font_size=11))
            self.assertEqual(self.app.styleSheet(),'')
            self.assertEqual(self.window.styleSheet(),'')
            if mode!='System': self.assertEqual(self.app.style().objectName().lower(),'fusion')
        self.theme.apply(dict(style='missing-style',palette='System',font_size=10))
        self.assertTrue(self.app.style())
    def test_close_during_worker_defers_shutdown(self):
        release=threading.Event()
        self.window._task(lambda: release.wait(2),lambda value: self.fail('Closing window must not accept results'),'Waiting')
        self.window.close()
        self.assertTrue(self.window.closing)
        self.assertTrue(self.window.runner.busy)
        release.set(); self.wait_idle()
        self.assertFalse(self.window.isVisible())
    def test_launcher_preserves_original_and_resolves_native(self):
        import launcher
        old,_=launcher.resolve_launch_target(mode=launcher.LauncherMode.MAIN)
        native,_=launcher.resolve_launch_target(mode=launcher.LauncherMode.NATIVE)
        self.assertEqual(Path(old[-1]).name,'main.py')
        self.assertEqual(Path(native[-1]).name,'kay_pos_native.pyw')
        self.assertNotEqual(launcher.INSTANCE_MUTEXES['pos'],launcher.INSTANCE_MUTEXES['native'])

if __name__=='__main__': unittest.main()
