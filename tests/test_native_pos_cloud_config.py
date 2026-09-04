"""Cloud file configuration only; no cloud service import or connection."""
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from server.native_cloud_config import CloudConfigRepository, destination, install_routes
from server.native_telegram import TelegramRepository, install_routes as install_telegram
from utils import telegram_config_store as store
from utils.env_loader import save_project_env_values
from tests import test_native_pos_phase7 as phase7
from tests.test_native_pos_phase3 import LocalApiClient

CLOUD = 'postgresql://cloud-user:cloud-secret@cloud.invalid/pos?sslmode=require'
PRIMARY = 'postgresql://source-user:source-secret@local.invalid/pos'


class CloudConfigTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / '.env'
        self.path.write_text('# Preserve this\nZAY_POS_DATABASE_URL=' + PRIMARY + '\nTELEGRAM_BOT_TOKEN=telegram-fixture\nZAY_POS_CLOUD_SYNC_ENABLED=0\nZAY_POS_CLOUD_SYNC_INTERVAL_SECONDS=300\nZAY_POS_CLOUD_DATABASE_URL=' + CLOUD + '\n')
        self.service = types.SimpleNamespace(**self.fixture.scope)
        self.repo = CloudConfigRepository(self.service, self.path, {})
        self.user = self.fixture.user

    def values(self):
        return dict(revision=self.repo.read(self.user)['revision'], enabled=True, interval_seconds=600, cloud_url='', clear_url=False)

    def command(self, values, identifier=None): return self.repo.command(self.user, identifier or str(uuid4()), 'cloud.save', values)

    def test_masked_read_preserved_credentials_and_replay(self):
        data = self.repo.read(self.user)
        self.assertEqual(data['destination'], 'cloud.invalid:5432 / pos')
        self.assertNotIn('cloud-user', json.dumps(data)); self.assertNotIn('cloud-secret', json.dumps(data))
        before_environment = dict(os.environ)
        values = self.values(); identifier = str(uuid4()); result = self.command(values, identifier)
        self.assertEqual(result, self.command(values, identifier))
        text = self.path.read_text()
        for keep in (CLOUD, PRIMARY, '# Preserve this', 'TELEGRAM_BOT_TOKEN=telegram-fixture'): self.assertIn(keep, text)
        self.assertIn('ZAY_POS_CLOUD_SYNC_INTERVAL_SECONDS=600', text)
        self.assertEqual(before_environment, dict(os.environ))
        with self.fixture.connect() as conn:
            rows = conn.execute("SELECT details FROM user_activity_log WHERE action='cloud.save'").fetchall()
            self.assertEqual(len(rows), 1); self.assertNotIn('cloud-secret', str(rows))

    def test_shared_pending_guard_and_audit_failure_recovery(self):
        values = self.values(); identifier = str(uuid4())
        with patch.object(self.repo, 'insert', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError): self.command(values, identifier)
        self.assertTrue(store.marker_path(self.path).exists())
        self.assertNotIn('cloud-secret', store.marker_path(self.path).read_text())
        telegram = TelegramRepository(self.service, self.path, {})
        self.assertTrue(telegram.read(self.user)['pending'])
        with self.assertRaisesRegex(ValueError, 'recovery'):
            save_project_env_values({'UNRELATED': 'value'}, self.path)
        self.command(values, identifier)
        self.assertFalse(store.marker_path(self.path).exists())

    def test_url_replacement_clear_stale_and_interval_validation(self):
        old = self.values(); values = dict(old, cloud_url='postgres://new-user:new-secret@other.invalid/archive', interval_seconds=60)
        self.command(values)
        self.assertNotIn('cloud-secret', self.path.read_text())
        with self.assertRaisesRegex(ValueError, 'changed'): self.command(old)
        for interval in (59, 86401, 1.5, True):
            values = self.values(); values['interval_seconds'] = interval
            with self.assertRaises(ValueError): self.command(values)
        values = self.values(); values.update(enabled=False, clear_url=True); self.command(values)
        self.assertFalse(self.repo.read(self.user)['url_configured'])

    def test_known_primary_destination_and_url_override_rejected(self):
        values = self.values(); values['cloud_url'] = 'postgres://different:credentials@LOCAL.invalid:5432/pos'
        with self.assertRaisesRegex(ValueError, 'primary'): self.command(values)
        for url in ('https://cloud.invalid/pos', 'postgresql://host/', 'postgresql://host:0/db', CLOUD + '&host=', CLOUD + '&password=other', CLOUD + '\nBAD=1'):
            with self.subTest(url=url), self.assertRaises(ValueError): destination(url)
        self.assertEqual(destination('postgresql://u:p%40ss@cloud.invalid/db?sslmode=require'), ('cloud.invalid', 5432, 'db'))

    def test_malformed_existing_settings_can_be_disabled(self):
        self.path.write_text('ZAY_POS_CLOUD_SYNC_ENABLED=1\nZAY_POS_CLOUD_DATABASE_URL=invalid-existing-url\nZAY_POS_CLOUD_SYNC_INTERVAL_SECONDS=99999999999999999999\n')
        data = self.repo.read(self.user)
        self.assertEqual(data['interval_seconds'], 300); self.assertIn('not supported', data['message'])
        values = self.values(); values['enabled'] = False; self.command(values)
        self.assertFalse(self.repo.read(self.user)['enabled'])

    def test_cloud_and_telegram_routes_and_fresh_permissions(self):
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo)
        install_telegram(app, lambda: self.user, TelegramRepository(self.service, self.path, {}))
        self.assertIn('/api/native/cloud_config', app.openapi()['paths'])
        client = LocalApiClient(app)
        self.assertEqual(client.get('/api/native/cloud_config').status_code, 200)
        payload = dict(request_id=str(uuid4()), operation='cloud.save', values=self.values())
        self.assertIn('result', client.post('/api/native/cloud_config/commands', json=payload).json())
        with self.fixture.connect() as conn: conn.execute("UPDATE users SET role='Manager',permissions='settings,edit_settings' WHERE id=1")
        self.assertEqual(client.get('/api/native/cloud_config').status_code, 403)


class CloudConfigUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_password_field_and_encrypted_url_recovery(self):
        from PyQt6.QtWidgets import QLineEdit
        from native_pos.integrations import CloudSettingsDialog
        from native_pos.protected_journal import ProtectedJournal
        dialog = CloudSettingsDialog(dict(revision='fixture', url_configured=True, destination='cloud.invalid / pos', environment_overrides=[], message='Fixture only', interval_seconds=300))
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.fields['cloud_url'].echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(dialog.fields['cloud_url'].text(), '')
        dialog.fields['cloud_url'].setText(CLOUD)
        with tempfile.TemporaryDirectory() as folder:
            journal = ProtectedJournal('https://fixture.invalid/cloud_config', 1, folder)
            pending = dict(payload=dict(request_id=str(uuid4()), operation='cloud.save', values=dialog.values()))
            journal.write(pending); self.assertNotIn('cloud-secret', journal.path.read_text()); self.assertEqual(journal.read(), pending)
            journal.write(dict(pending, result={'message': 'Saved'})); self.assertNotIn('cloud_url', journal.path.read_text())


if __name__ == '__main__': unittest.main()
