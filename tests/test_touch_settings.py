from contextlib import closing
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from server import cashier_service as service


class TouchSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, 'settings.db')
        with closing(sqlite3.connect(self.db)) as conn:
            conn.executescript("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT); INSERT INTO settings VALUES('unrelated','keep'); CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,role TEXT,is_active INTEGER); INSERT INTO users VALUES(1,'admin','Admin','Admin',1);")
        self.mock = patch.object(service, 'connect_db', side_effect=lambda: sqlite3.connect(self.db))
        self.mock.start()
    def tearDown(self):
        self.mock.stop()
        self.tmp.cleanup()
    def test_shared_keys_partial_save(self):
        service.save_touch_settings({'shop_name':'Test Shop','tax_rate':'5','receipt_paper_size':'1','theme':'Dark'})
        self.assertEqual(service.get_lite_settings()['shop_name'],'Test Shop')
        self.assertEqual(service.get_touch_settings()['receipt_paper_size'],'1')
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT value FROM settings WHERE key='unrelated'").fetchone()[0],'keep')
    def test_validation_does_not_partially_write(self):
        for invalid in ({'tax_rate':'nan'}, {'discount_type':'percentage','discount_value':'101'}, {'theme':'bad'}, {'shop_logo_image':'data:image/svg+xml;base64,eA=='}, {'network_printer_api_key':'secret'}):
            with self.assertRaises(ValueError):service.save_touch_settings({'shop_name':'Must not save',**invalid})
        self.assertEqual(service.get_touch_settings()['shop_name'],'ZAY POS')
    def test_profile_image_validation_and_preservation(self):
        import base64
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (12, 12), 'blue').save(buf, format='PNG')
        avatar = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        values = {'username':'admin','role':'Admin','active':True,'profile_image':avatar}
        service.save_lite_user(values, 1)
        self.assertEqual(service.get_user_avatar_blob(1)['mime'], 'image/png')
        self.assertTrue(service.list_lite_users()[0]['profile_image'].startswith('data:image/png;base64,'))
        before = service.get_user_avatar_blob(1)['data']
        service.save_lite_user({'username':'admin','role':'Admin','active':True}, 1)
        self.assertEqual(service.get_user_avatar_blob(1)['data'], before)
        with self.assertRaises(ValueError):
            service.save_lite_user({**values, 'username':'changed', 'profile_image':'data:image/png;base64,bad'}, 1)
        self.assertEqual(service.list_lite_users()[0]['username'], 'admin')

    def test_legacy_avatar_without_sqlite_rowid(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(buf, format='PNG')
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("CREATE TABLE employees(id INTEGER PRIMARY KEY, user_id INTEGER, photo_data BLOB) WITHOUT ROWID")
            conn.execute("INSERT INTO employees VALUES(1,1,?)", (buf.getvalue(),))
            conn.commit()
        users = service.list_lite_users()
        self.assertEqual(users[0]['username'], 'admin')
        self.assertTrue(users[0]['profile_image'].startswith('data:image/png;base64,'))

    def test_last_admin_edit_is_blocked(self):
        with self.assertRaisesRegex(ValueError,'only active admin'):
            service.save_lite_user({'username':'admin','role':'Cashier','active':True},1)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT role FROM users').fetchone()[0],'Admin')
