import ast
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
from native_pos.config import DEFAULTS, load_config, save_config
from native_pos.data import ServerStore, Target, create_practice_database
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow

class NativeServerTests(unittest.TestCase):
    def test_server_client_uses_existing_login_and_me_with_bearer_token(self):
        response = Mock(ok=True)
        response.json.side_effect = [
            {'token':'test-token', 'user':{'id':7,'username':'staff','role':'Cashier'}},
            {'user':{'id':7,'username':'staff','role':'Cashier','permissions':['sales','receipts']}},
        ]
        with patch('lite_pos.api.requests.Session.request',return_value=response) as request:
            store=ServerStore(Target('Server',server_url=DEFAULTS['server_url'],insecure_tls=True))
            session=store.authenticate('staff','password')
            self.assertTrue(session.can('sales')); self.assertFalse(session.can('products'))
            self.assertEqual(request.call_args_list[0].args[:2],('POST','https://192.168.110.112:8000/api/login'))
            self.assertEqual(request.call_args_list[1].args[:2],('GET','https://192.168.110.112:8000/api/me'))
            self.assertEqual(request.call_args_list[1].kwargs['headers']['Authorization'],'Bearer test-token')
            self.assertFalse(request.call_args_list[0].kwargs['verify'])
            store.close(); self.assertEqual(store.client.token,'')

    def test_older_server_does_not_grant_unspecified_nonadmin_access(self):
        with patch('lite_pos.api.LiteApiClient') as client_type:
            client=client_type.return_value
            client.server_url=DEFAULTS['server_url']
            client.login.return_value={'id':1,'username':'staff','role':'Cashier'}
            client.current_user.return_value=client.login.return_value
            session=ServerStore(Target('Server',server_url=DEFAULTS['server_url'])).authenticate('staff','pw')
            self.assertFalse(session.can('sales'))

    def test_default_ip_and_display_baseline_migrate_old_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'
            path.write_text('{"backend":"SQLite","width":1100,"height":720}')
            config=load_config(path)
            self.assertEqual(config['backend'],'Server')
            self.assertEqual(config['server_url'],'https://192.168.110.112:8000')
            self.assertEqual((config['width'],config['height']),(1366,768))
            save_config(dict(config,token='secret',password='secret'),path)
            self.assertNotIn('secret',path.read_text())

    def test_server_auth_response_includes_role_and_user_permissions(self):
        # Execute the production function without importing the server's database
        # bootstrap, so this test never connects to a configured production DB.
        source=Path(__file__).resolve().parents[1]/'server'/'cashier_service.py'
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='verify_user')
        function.returns=None
        for arg in function.args.args: arg.annotation=None
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'test.db'
            create_practice_database(db,'staff','practice-password')
            conn=sqlite3.connect(db)
            conn.execute("UPDATE users SET role='Cashier',permissions='customers'")
            conn.execute("INSERT INTO user_roles(name,permissions) VALUES('Cashier','sales,receipts')")
            conn.commit();conn.close()
            scope={'hashlib':hashlib,'connect_db':lambda:sqlite3.connect(db)}
            exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),scope)
            user=scope['verify_user']('staff','practice-password')
            self.assertEqual(set(user['permissions']),{'sales','receipts','customers'})
            self.assertEqual(user['role'],'Cashier')
            self.assertIsNone(scope['verify_user']('staff','incorrect'))

class NativeServerWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
    def test_server_login_defaults_and_logout_close_session(self):
        with tempfile.TemporaryDirectory() as folder:
            w=NativeWindow(NativeTheme(self.app),Path(folder)/'settings.json')
            try:
                self.assertEqual(w.login_dialog.backend.currentText(),'Server')
                self.assertEqual(w.login_dialog.server.text(),DEFAULTS['server_url'])
                self.assertTrue(w.login_dialog.create.isHidden())
                available=w.screen().availableGeometry()
                self.assertLessEqual(w.height(),available.height())
                self.assertLessEqual(w.width(),available.width())
                client=Mock(server_url=DEFAULTS['server_url'])
                client.login.return_value={'id':1,'username':'admin','role':'Admin'}
                client.current_user.return_value=client.login.return_value
                w.login_dialog.username.setText('admin'); w.login_dialog.password.setText('pw')
                with patch('lite_pos.api.LiteApiClient',return_value=client):
                    w.login()
                    loop=QEventLoop();w.runner.idle.connect(loop.quit)
                    QTimer.singleShot(3000,loop.quit);loop.exec()
                self.assertFalse(w.runner.busy)
                from native_pos.routes import ROUTES
                self.assertEqual(w.navigation.count(),len(ROUTES))
                w.logout();client.close.assert_called_once()
                self.assertIsNone(w.session)
            finally:
                w.close()

if __name__=='__main__':unittest.main()
