import json
import sqlite3
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from tests import test_native_pos_phase7 as phase7
from server.native_backup import BackupRepository
from server.native_backup_package import build_package, verify_package, rehearse_package


class BackupPackageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name); self.assets = self.root / 'assets'; self.assets.mkdir()
        (self.assets / 'images').mkdir(); (self.assets / 'images' / 'logo.png').write_bytes(b'fixture-logo')
        (self.assets / '.env').write_text('secret=excluded')
        self.repo = BackupRepository(types.SimpleNamespace(**self.fixture.scope), self.root / 'backups', self.assets)

    def test_package_replay_manifest_download_listing_and_snapshot(self):
        request = str(uuid4()); result = self.repo.package(self.fixture.user, request)
        path = self.repo.path(result['name']); original = path.read_bytes()
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.read('database/images/logo.png'), b'fixture-logo')
            self.assertNotIn('database/.env', archive.namelist())
            manifest = json.loads(archive.read('manifest.json')); self.assertEqual(len(manifest['files']), 2)
            snapshot = self.root / 'restored.db'; snapshot.write_bytes(archive.read('snapshot.db'))
        conn = sqlite3.connect(snapshot)
        try: self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        finally: conn.close()
        (self.assets / 'images' / 'logo.png').write_bytes(b'new-logo')
        self.repo.package(self.fixture.user, request); self.assertEqual(path.read_bytes(), original)
        self.assertIn('checksums verified', self.repo.verify(self.fixture.user, result['name'], result['sha256'])['message'])
        self.assertIn(result['name'], [r['name'] for r in self.repo.read(self.fixture.user)['records']])

    def test_failure_leaves_no_final_package_and_permissions_are_fresh(self):
        request = str(uuid4())
        with patch('server.native_backup_package.MAX_BYTES', 1):
            with self.assertRaises(ValueError): self.repo.package(self.fixture.user, request)
        self.assertFalse((self.repo.directory / f'native-{request}.zip').exists())
        self.assertFalse(list(self.repo.directory.glob('*.partial')))
        with self.fixture.connect() as conn:
            conn.execute("UPDATE users SET role='Cashier',permissions='' WHERE id=1")
            conn.execute("UPDATE user_roles SET permissions='' WHERE name='Cashier'")
        with self.assertRaises(PermissionError): self.repo.package(self.fixture.user, request)

    def test_bad_manifest_and_tampering_rejected_without_extraction(self):
        result = self.repo.package(self.fixture.user, str(uuid4()))
        source = self.repo.path(result['name']); target = self.root / 'bad.zip'
        with zipfile.ZipFile(source) as archive, zipfile.ZipFile(target, 'w') as output:
            for name in archive.namelist(): output.writestr(name, b'tampered' if name.endswith('logo.png') else archive.read(name))
        with self.assertRaisesRegex(ValueError, 'checksum'): verify_package(target)
        with zipfile.ZipFile(target, 'w') as output:
            output.writestr('manifest.json', json.dumps({'version': 1, 'files': [{'path': '../escape', 'size': 0, 'sha256': '0' * 64}]}))
            output.writestr('../escape', b'')
        with self.assertRaisesRegex(ValueError, 'Unsafe'): verify_package(target)
        self.assertFalse((self.root.parent / 'escape').exists())

    def test_asset_changes_abort_package(self):
        snapshot = self.root / 'snapshot.db'; snapshot.write_bytes(b'fixture')
        from server.native_backup_package import inventory
        records = inventory(self.assets)
        with patch('server.native_backup_package.inventory', side_effect=[records, []]):
            with self.assertRaisesRegex(ValueError, 'assets changed'):
                build_package(snapshot, self.assets, self.root / 'changed.zip')

    def test_package_restore_rehearsal_isolated_replay_and_file_bytes(self):
        result = self.repo.package(self.fixture.user, str(uuid4()))
        source = self.repo.path(result['name'])
        with self.fixture.connect() as conn:
            live_before = conn.execute('SELECT COUNT(*),COALESCE(SUM(total),0) FROM sales').fetchone()
            audit_before = conn.execute("SELECT COUNT(*) FROM user_activity_log WHERE action='backup.package_rehearse'").fetchone()[0]
        restored = self.repo.rehearse(self.fixture.user, result['name'], result['sha256'])
        folder = self.repo.directory / restored['copy_name']
        self.assertEqual((folder / 'database/images/logo.png').read_bytes(), b'fixture-logo')
        self.assertEqual((folder / 'rehearsal.json').is_file(), True)
        restored_again = self.repo.rehearse(self.fixture.user, result['name'], result['sha256'])
        self.assertEqual(restored_again['tables'], restored['tables'])
        (folder / 'database/images/logo.png').write_bytes(b'changed rehearsal')
        with self.assertRaisesRegex(ValueError, 'files changed'):
            self.repo.rehearse(self.fixture.user, result['name'], result['sha256'])
        with self.fixture.connect() as conn:
            self.assertEqual(live_before, conn.execute('SELECT COUNT(*),COALESCE(SUM(total),0) FROM sales').fetchone())
            self.assertEqual(audit_before + 1, conn.execute("SELECT COUNT(*) FROM user_activity_log WHERE action='backup.package_rehearse'").fetchone()[0])
        self.assertEqual(source.read_bytes(), self.repo.path(result['name']).read_bytes())

    def test_failed_rehearsal_cleans_partial_and_preserves_existing_copy(self):
        result = self.repo.package(self.fixture.user, str(uuid4()))
        target = self.repo.directory / 'manual-rehearsal'
        with patch('server.native_backup_package.os.fsync', side_effect=OSError('disk failed')):
            with self.assertRaises(OSError): rehearse_package(self.repo.path(result['name']), target, result['sha256'])
        self.assertFalse(target.exists()); self.assertFalse(target.with_name(target.name + '.partial').exists())
        valid = rehearse_package(self.repo.path(result['name']), target, result['sha256'])
        marker = (target / 'rehearsal.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'different package'):
            rehearse_package(self.repo.path(result['name']), target, '0' * 64)
        self.assertEqual((target / 'rehearsal.json').read_bytes(), marker)
        self.assertIn('Production files were not changed', valid['message'])

    def test_postgres_package_rehearsal_rejected_without_extraction(self):
        package = self.root / 'postgres.zip'
        dump = self.root / 'snapshot.dump'; dump.write_bytes(b'pg fixture')
        build_package(dump, self.assets, package)
        destination = self.root / 'pg-rehearsal'
        with self.assertRaisesRegex(ValueError, 'PostgreSQL package rehearsal'):
            rehearse_package(package, destination, self.repo.metadata(package)['sha256'])
        self.assertFalse(destination.exists()); self.assertFalse(destination.with_name(destination.name + '.partial').exists())
