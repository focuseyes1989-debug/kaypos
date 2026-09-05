import tempfile
import types
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from tests import test_native_pos_phase7 as phase7
from server.native_backup import BackupRepository


class BackupVerifyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.repo = BackupRepository(types.SimpleNamespace(**self.fixture.scope), self.folder.name)

    def test_sqlite_verification_preserves_snapshot_and_database(self):
        backup = self.repo.create(self.fixture.user, str(uuid4()))
        path = self.repo.path(backup['name']); original = path.read_bytes()
        with self.fixture.connect() as conn: before = list(conn.iterdump())
        result = self.repo.verify(self.fixture.user, backup['name'], backup['sha256'])
        self.assertIn('quick check passed', result['message'])
        self.assertEqual(path.read_bytes(), original)
        with self.fixture.connect() as conn: self.assertEqual(before, list(conn.iterdump()))
        with self.assertRaisesRegex(ValueError, 'changed'): self.repo.verify(self.fixture.user, backup['name'], 'wrong')

    def test_corruption_and_permission_rejection(self):
        name = f'native-{uuid4()}.db'; path = Path(self.folder.name) / name; path.write_bytes(b'not a database')
        with self.assertRaisesRegex(ValueError, 'verification failed'):
            self.repo.verify(self.fixture.user, name, self.repo.metadata(path)['sha256'])
        with self.fixture.connect() as conn:
            conn.execute("UPDATE users SET role='Cashier',permissions='' WHERE id=1")
            conn.execute("UPDATE user_roles SET permissions='' WHERE name='Cashier'")
        with self.assertRaises(PermissionError): self.repo.verify(self.fixture.user, name, self.repo.metadata(path)['sha256'])

    def test_postgres_inspects_only_index_and_reports_limitations(self):
        name = f'native-{uuid4()}.dump'; path = Path(self.folder.name) / name; path.write_bytes(b'fixture archive')
        checksum = self.repo.metadata(path)['sha256']
        with patch('server.native_backup.shutil.which', return_value='pg_restore'), patch('server.native_backup.subprocess.run', return_value=types.SimpleNamespace(returncode=0)) as run:
            result = self.repo.verify(self.fixture.user, name, checksum)
            self.assertEqual(run.call_args.args[0], ['pg_restore', '--list', str(path)])
            self.assertIn('not verified', result['message'])
            run.return_value.returncode = 1
            with self.assertRaises(ValueError): self.repo.verify(self.fixture.user, name, checksum)
        with patch('server.native_backup.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Install matching'): self.repo.verify(self.fixture.user, name, checksum)
