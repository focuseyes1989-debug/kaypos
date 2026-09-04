"""Telegram configuration using temporary env files and disposable databases."""
import ast
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from server.native_telegram import TelegramRepository, install_routes
from server.native_file_lock import file_lock
from utils import telegram_config_store as store
from tests import test_native_pos_phase7 as phase7
from tests.test_native_pos_phase3 import LocalApiClient

TOKEN = '123456789:' + 'a' * 35


class TelegramConfigTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / '.env'
        self.path.write_text('# Keep this comment\nZAY_POS_DATABASE_URL=private-fixture\nTELEGRAM_ENABLED=0\nTELEGRAM_BOT_TOKEN=' + TOKEN + '\nTELEGRAM_CHAT_ID=12345\n')
        self.repo = TelegramRepository(types.SimpleNamespace(**self.fixture.scope), self.path, {'TELEGRAM_BOT_TOKEN': 'private-override'})
        self.user = self.fixture.user

    def values(self, **extra):
        data = self.repo.read(self.user)
        return dict(revision=data['revision'], enabled=True, listener_enabled=False, chat_id='-10012345', bot_token='', clear_token=False, **extra)

    def command(self, values, identifier=None): return self.repo.command(self.user, identifier or str(uuid4()), 'telegram.save', values)

    def audit_count(self):
        with self.fixture.connect() as conn: return conn.execute("SELECT COUNT(*) FROM user_activity_log WHERE action='telegram.save'").fetchone()[0]

    def test_public_config_preserve_token_other_settings_and_replay(self):
        data = self.repo.read(self.user)
        self.assertTrue(data['token_configured']); self.assertNotIn(TOKEN, json.dumps(data)); self.assertNotIn('private-override', json.dumps(data))
        self.assertEqual(data['environment_overrides'], ['TELEGRAM_BOT_TOKEN'])
        values = self.values(); identifier = str(uuid4()); result = self.command(values, identifier)
        self.assertEqual(self.command(values, identifier), result); self.assertEqual(self.audit_count(), 1)
        text = self.path.read_text(); self.assertIn('# Keep this comment', text); self.assertIn('ZAY_POS_DATABASE_URL=private-fixture', text); self.assertIn(TOKEN, text)
        self.assertFalse(store.marker_path(self.path).exists())
        with self.fixture.connect() as conn:
            requests = conn.execute("SELECT payload_hash,result_json FROM native_admin_requests WHERE operation='telegram.save'").fetchall()
            audit = conn.execute("SELECT details FROM user_activity_log WHERE action='telegram.save'").fetchall()
        self.assertNotIn(TOKEN, str(requests) + str(audit))

    def test_audit_failure_after_file_write_recovers_once(self):
        values = self.values(); identifier = str(uuid4())
        with patch.object(self.repo, 'insert', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError): self.command(values, identifier)
        self.assertTrue(store.marker_path(self.path).exists()); self.assertIn('TELEGRAM_ENABLED=1', self.path.read_text())
        self.assertEqual(self.audit_count(), 0)
        with self.assertRaisesRegex(ValueError, 'needs recovery'): store.save_legacy(self.path, store.parse(self.path.read_bytes()))
        with self.assertRaisesRegex(ValueError, 'Another Telegram'): self.command(self.values())
        self.command(values, identifier); self.assertEqual(self.audit_count(), 1); self.assertFalse(store.marker_path(self.path).exists())

    def test_committed_result_with_leftover_marker_does_not_repeat_audit(self):
        values = self.values(); identifier = str(uuid4()); unlink = Path.unlink
        def fail(path, *args, **kwargs):
            if path == store.marker_path(self.path): raise OSError('Fixture cleanup failure')
            return unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail):
            with self.assertRaises(OSError): self.command(values, identifier)
        self.assertEqual(self.audit_count(), 1); self.assertTrue(store.marker_path(self.path).exists())
        self.command(values, identifier)
        self.assertEqual(self.audit_count(), 1); self.assertFalse(store.marker_path(self.path).exists())

    def test_file_failure_and_manual_edit_during_recovery(self):
        values = self.values(); identifier = str(uuid4()); original = store.atomic_write
        def fail(path, data):
            if path == self.path: raise OSError('Fixture disk full')
            return original(path, data)
        with patch.object(store, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError): self.command(values, identifier)
        self.assertIn('TELEGRAM_ENABLED=0', self.path.read_text()); self.assertTrue(store.marker_path(self.path).exists())
        self.command(values, identifier); self.assertEqual(self.audit_count(), 1)
        values = self.values(); identifier = str(uuid4())
        with patch.object(self.repo, 'insert', side_effect=RuntimeError()):
            with self.assertRaises(RuntimeError): self.command(values, identifier)
        self.path.write_text(self.path.read_text() + 'EXTERNAL_EDIT=1\n')
        with self.assertRaisesRegex(RuntimeError, 'outside'): self.command(values, identifier)
        self.assertIn('EXTERNAL_EDIT=1', self.path.read_text())

    def test_replacement_clear_invalid_fields_and_stale_revision(self):
        values = self.values(); old = dict(values)
        values['bot_token'] = '987654321:' + 'b' * 35; self.command(values)
        self.assertNotIn(TOKEN, self.path.read_text())
        with self.assertRaisesRegex(ValueError, 'changed'): self.command(old)
        for changes in (dict(bot_token='invalid'), dict(chat_id='123\nBAD=1'), dict(enabled=False, listener_enabled=True), dict(clear_token=True)):
            values = self.values(); values.update(changes)
            with self.assertRaises(ValueError): self.command(values)
        values = self.values(); values.update(enabled=False, clear_token=True); self.command(values)
        self.assertFalse(self.repo.read(self.user)['token_configured'])

    def test_api_access_revocation_and_busy_is_unknown_not_rejected(self):
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo); client = LocalApiClient(app)
        payload = dict(request_id=str(uuid4()), operation='telegram.save', values=self.values())
        with file_lock(store.lock_path(self.path)):
            response = client.post('/api/native/telegram/commands', json=payload)
        self.assertEqual(response.status_code, 503); self.assertNotIn('rejected', response.json())
        with self.fixture.connect() as conn: conn.execute("UPDATE users SET role='Manager',permissions='settings,edit_settings' WHERE id=1")
        self.assertEqual(client.get('/api/native/telegram').status_code, 403)
        self.assertEqual(client.post('/api/native/telegram/commands', json=payload).status_code, 403)

    def test_legacy_function_uses_atomic_shared_store_without_bootstrap(self):
        source = ast.parse((phase7.ROOT / 'utils/telegram_service.py').read_text(encoding='utf-8-sig'))
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'save_telegram_config')
        scope = dict(TelegramConfig=types.SimpleNamespace, Path=Path, get_env_path=lambda: self.path, logger=Mock())
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'isolated_telegram_save.py', 'exec'), scope)
        config = types.SimpleNamespace(enabled=False, listener_enabled=False, bot_token=TOKEN, chat_id='54321')
        self.assertEqual(scope['save_telegram_config'](config), self.path)
        self.assertIn('TELEGRAM_CHAT_ID=54321', self.path.read_text()); self.assertIn('private-fixture', self.path.read_text())


class TelegramConfigUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_masked_replacement_form_and_encrypted_recovery(self):
        from PyQt6.QtWidgets import QLineEdit
        from native_pos.integrations import TelegramSettingsDialog
        from native_pos.protected_journal import ProtectedJournal
        dialog = TelegramSettingsDialog(dict(revision='revision-fixture', token_configured=True, message='Fixture only', environment_overrides=['TELEGRAM_ENABLED']))
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.fields['bot_token'].echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(dialog.fields['bot_token'].text(), '')
        dialog.fields['bot_token'].setText(TOKEN)
        with tempfile.TemporaryDirectory() as folder:
            journal = ProtectedJournal('https://fixture.invalid/native/telegram', 1, folder)
            pending = dict(payload=dict(request_id=str(uuid4()), operation='telegram.save', values=dialog.values()))
            journal.write(pending); self.assertNotIn(TOKEN, journal.path.read_text()); self.assertEqual(journal.read(), pending)
            journal.write(dict(pending, result={'message': 'Saved'})); self.assertNotIn('bot_token', journal.path.read_text())


if __name__ == '__main__': unittest.main()
