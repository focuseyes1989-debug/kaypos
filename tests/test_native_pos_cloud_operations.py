import hashlib
import tempfile
import types
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch
from tests import test_native_pos_phase7 as phase7
from server.native_cloud_operations import CloudOperationsRepository, install_routes


CLOUD = 'postgresql://cloud-user:secret@cloud.invalid/pos'
PRIMARY = 'postgresql://local-user:secret@local.invalid/pos'


class Adapter:
    def __init__(self, result=None, cloud=CLOUD, primary=PRIMARY):
        self.result = result or types.SimpleNamespace(ok=True, synced_tables=3, synced_rows=12, backup_path='')
        self.cloud, self.primary, self.calls = cloud, primary, []
    def effective(self): return self.cloud, False, self.primary, 'SQLite'
    def run(self, operation): self.calls.append(operation); return self.result


class CloudOperationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.adapter = Adapter(); self.backup = Mock(); self.backup.create.return_value = {'name': 'safety.db'}
        self.repo = CloudOperationsRepository(types.SimpleNamespace(**self.fixture.scope), self.adapter, Path(self.folder.name) / 'cloud.lock', self.backup)

    def test_preflight_masks_credentials_and_success_replays_once(self):
        state = self.repo.preflight(self.fixture.user)
        self.assertEqual(state['destination'], 'cloud.invalid:5432 / pos')
        self.assertNotIn('secret', str(state)); self.assertTrue(state['ready'])
        request = str(uuid4()); result = self.repo.execute(self.fixture.user, request, 'cloud.sync')
        self.assertEqual(result['status'], 'completed'); self.assertEqual(result['synced_rows'], 12)
        self.assertFalse(result['backup_created']); self.assertNotIn('secret', str(result))
        self.backup.create.assert_not_called()
        self.assertEqual(self.repo.execute(self.fixture.user, request, 'cloud.sync'), result)
        self.assertEqual(self.adapter.calls, ['cloud.sync'])
        with self.fixture.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM user_activity_log WHERE action='cloud.sync'").fetchone()[0], 1)

    def test_failure_is_confirmed_without_sensitive_exception_or_auto_retry(self):
        self.adapter.result = types.SimpleNamespace(ok=False, synced_tables=1, synced_rows=5, backup_path='C:/secret/backup.db', message='password=private')
        request = str(uuid4()); result = self.repo.execute(self.fixture.user, request, 'cloud.pull')
        self.assertEqual(result['status'], 'failed'); self.assertTrue(result['backup_created'])
        self.backup.create.assert_called_once_with(self.fixture.user, request)
        self.assertNotIn('private', str(result)); self.assertNotIn('C:', str(result))
        self.repo.execute(self.fixture.user, request, 'cloud.pull')
        self.assertEqual(self.adapter.calls, ['cloud.pull'])

    def test_interrupted_unknown_result_requires_review_without_rerun(self):
        self.adapter.run = Mock(side_effect=SystemExit('server stopped'))
        request = str(uuid4())
        with self.assertRaises(SystemExit): self.repo.execute(self.fixture.user, request, 'cloud.sync')
        result = self.repo.execute(self.fixture.user, request, 'cloud.sync')
        self.assertEqual(result['status'], 'needs_review'); self.adapter.run.assert_called_once()

    def test_same_target_and_fresh_permissions_block_before_adapter(self):
        self.adapter.primary = 'postgres://different:credentials@CLOUD.invalid:5432/pos'
        self.assertFalse(self.repo.preflight(self.fixture.user)['ready'])
        with self.assertRaises(ValueError): self.repo.execute(self.fixture.user, str(uuid4()), 'cloud.sync')
        self.adapter.primary = PRIMARY
        with self.fixture.connect() as conn:
            conn.execute("UPDATE users SET role='Cashier',permissions='' WHERE id=1")
            conn.execute("UPDATE user_roles SET permissions='' WHERE name='Cashier'")
        with self.assertRaises(PermissionError): self.repo.execute(self.fixture.user, str(uuid4()), 'cloud.sync')
        self.assertEqual(self.adapter.calls, [])

    def test_routes_and_client_typed_confirmation_shape(self):
        from fastapi import FastAPI
        from tests.test_native_pos_phase3 import LocalApiClient
        app = FastAPI(); install_routes(app, lambda: self.fixture.user, self.repo); client = LocalApiClient(app)
        self.assertEqual(client.get('/api/native/cloud_operations').status_code, 200)
        request = str(uuid4())
        denied = client.post('/api/native/cloud_operations/commands', json={'request_id': str(uuid4()), 'operation': 'cloud.sync', 'values': {}})
        self.assertEqual(denied.status_code, 400); self.assertEqual(self.adapter.calls, [])
        response = client.post('/api/native/cloud_operations/commands', json={'request_id': request, 'operation': 'cloud.sync', 'values': {'confirmation': 'SYNC TO CLOUD'}})
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json()['result']['request_id'], request)
        self.assertIn('/api/native/cloud_operations/commands', app.openapi()['paths'])

    def test_ui_requires_exact_typed_phrase_before_submit(self):
        from native_pos.integrations import IntegrationsPage
        channel = types.SimpleNamespace(pending=None, error='', submit=Mock())
        channel.run = lambda operation, received, message: received(dict(ready=True, destination='cloud.invalid:5432 / pos', backend='SQLite', enabled=False, message='ready'))
        page = types.SimpleNamespace(host=types.SimpleNamespace(runner=types.SimpleNamespace(busy=False), store=types.SimpleNamespace(client=Mock())), cloud_operations=channel, update_enabled=Mock())
        with patch('native_pos.integrations.QInputDialog.getText', return_value=('wrong', True)):
            IntegrationsPage.run_cloud(page, 'cloud.pull')
        channel.submit.assert_not_called()
        with patch('native_pos.integrations.QInputDialog.getText', return_value=('PULL FROM CLOUD', True)):
            IntegrationsPage.run_cloud(page, 'cloud.pull')
        channel.submit.assert_called_once_with('cloud.pull', {'confirmation': 'PULL FROM CLOUD'})
