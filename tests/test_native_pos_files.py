"""Portable attachments: disposable database, guarded legacy helpers and Qt."""
import ast
import base64
import hashlib
import io
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from server.native_files import FilesRepository, install_routes, image_png, MAX_BYTES
from tests import test_native_pos_phase7 as phase7
from tests.test_native_pos_phase3 import LocalApiClient


def png():
    from PIL import Image
    stream = io.BytesIO(); Image.new('RGB', (40, 20), 'blue').save(stream, 'JPEG')
    return stream.getvalue()


class FileDatabaseTests(unittest.TestCase):
    connect = phase7.AdminDatabaseTests.connect
    count = phase7.AdminDatabaseTests.count
    command = phase7.AdminDatabaseTests.command

    def setUp(self):
        phase7.AdminDatabaseTests.setUp(self)
        self.admin = self.repo
        self.repo = FilesRepository(types.SimpleNamespace(**self.scope), self.employee)

    def upload(self, kind, identifier, data, name='picture.jpg', revision=None, request_id=None):
        prior = self.repo.read(self.user, kind, identifier)
        values = dict(kind=kind, id=identifier, revision=revision or prior['revision'],
                      content=base64.b64encode(data).decode(), filename=name)
        operation = 'receipt_image.save' if kind in ('logo', 'qr') else kind + '.save'
        return self.repo.command(self.user, request_id or str(uuid4()), operation, values), values

    def test_photo_normalization_stale_revision_and_recovery(self):
        prior = self.repo.read(self.user, 'photo', 1)
        request = str(uuid4()); result, values = self.upload('photo', 1, png(), request_id=request)
        asset = self.repo.read(self.user, 'photo', 1)
        self.assertTrue(base64.b64decode(asset['content']).startswith(b'\x89PNG'))
        self.assertEqual(asset['size'], result['size'])
        self.assertEqual(self.repo.command(self.user, request, 'photo.save', values), result)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.upload('photo', 1, png(), revision=prior['revision'])
        self.command('photo.save', dict(kind='photo', id=1, revision=asset['revision'], remove=True))
        self.assertEqual(self.repo.read(self.user, 'photo', 1)['size'], 0)
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT full_name FROM employees WHERE id=1').fetchone()[0], 'Test Employee')

    def test_document_round_trip_audit_rollback_and_backup(self):
        self.admin.command(self.user, str(uuid4()), 'employee.documents.save', dict(employee_id=1, document_type='ID', document_no='ABC', file_path='C:/old/reference.pdf'))
        identifier = self.admin.read(self.user, 'documents')['records'][0]['id']
        pdf = b'%PDF-1.4\nfixture only\n%%EOF\n'
        result, values = self.upload('document', identifier, pdf, '../../employee.pdf')
        asset = self.repo.read(self.user, 'document', identifier)
        self.assertEqual(asset['name'], 'employee.pdf')
        self.assertEqual(base64.b64decode(asset['content']), pdf)
        insert = self.repo.insert
        def fail(c, table, values):
            if table == 'user_activity_log': raise RuntimeError('Audit unavailable')
            return insert(c, table, values)
        with patch.object(self.repo, 'insert', fail):
            with self.assertRaisesRegex(RuntimeError, 'Audit'):
                self.command('document.save', dict(kind='document', id=identifier, revision=asset['revision'], remove=True))
        self.assertEqual(self.repo.read(self.user, 'document', identifier)['content'], asset['content'])
        from server.native_backup import BackupRepository
        with tempfile.TemporaryDirectory() as folder:
            backup_repo = BackupRepository(types.SimpleNamespace(**self.scope), folder)
            backup = backup_repo.create(self.user, str(uuid4()))
            restored = backup_repo.rehearse(self.user, backup['name'], backup['sha256'])
            copied = sqlite3.connect(Path(folder) / restored['copy_name'])
            try: self.assertEqual(copied.execute('SELECT content FROM native_employee_documents').fetchone()[0], pdf)
            finally: copied.close()
        self.command('document.save', dict(kind='document', id=identifier, revision=asset['revision'], remove=True))
        self.assertEqual(self.count('employee_documents'), 1)
        self.assertEqual(self.count('native_employee_documents'), 0)

    def test_invalid_content_and_permission_revocation(self):
        with self.assertRaises(ValueError): self.upload('photo', 1, b'not an image')
        self.admin.command(self.user, str(uuid4()), 'employee.documents.save', dict(employee_id=1, document_type='ID'))
        identifier = self.admin.read(self.user, 'documents')['records'][0]['id']
        with self.assertRaisesRegex(ValueError, 'PDF'): self.upload('document', identifier, b'not PDF', 'test.pdf')
        with self.assertRaisesRegex(ValueError, 'Documents'): self.upload('document', identifier, b'command', 'test.exe')
        from server.native_files import decode
        with self.assertRaisesRegex(ValueError, '8 MB'): decode('A' * (((MAX_BYTES + 2) // 3 * 4) + 1))
        with self.connect() as c:
            c.execute("UPDATE users SET role='Viewer',permissions='' WHERE id=1")
            c.execute("UPDATE user_roles SET permissions='' WHERE name='Viewer'")
        with self.assertRaises(PermissionError): self.repo.read(self.user, 'photo', 1)
        with self.assertRaises(PermissionError): self.command('photo.save', dict(kind='photo', id=1, revision='', remove=True))

    def test_receipt_images_are_shared_and_api_rejections_confirmed(self):
        self.upload('logo', 0, png()); self.upload('qr', 0, png())
        sale = self.sale(items=[dict(product_id=1, qty=1)], payment=105, request_id=str(uuid4()))
        from native_pos.receipt import receipt_html
        self.assertIn('native-receipt:logo', receipt_html(sale))
        self.assertIn('native-receipt:qr', receipt_html(sale))
        self.assertTrue(sale['receipt_settings']['shop_logo_image'].startswith('data:image/png;base64,'))
        from fastapi import FastAPI
        app = FastAPI(); install_routes(app, lambda: self.user, self.repo); client = LocalApiClient(app)
        response = client.get('/api/native/files?kind=logo')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()['size'], 0)
        response = client.post('/api/native/files/commands', json=dict(request_id=str(uuid4()), operation='receipt_image.save', values=dict(kind='photo')))
        self.assertIn('rejected', response.json())

    def test_legacy_receipt_cache_refreshes_from_shared_blob(self):
        # Execute only the existing helper's functions, never its DB bootstrap import.
        import os
        import mimetypes
        import shutil
        module = ast.parse((phase7.ROOT / 'utils/receipt_images.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in module.body if isinstance(n, ast.FunctionDef) or isinstance(n, ast.Assign)]
        with tempfile.TemporaryDirectory() as folder:
            scope = dict(base64=base64, os=os, mimetypes=mimetypes, shutil=shutil, logger=Mock(), connect_db=self.connect, get_db_dir=lambda: folder)
            exec(compile(ast.Module(body=nodes, type_ignores=[]), 'isolated_receipt_images.py', 'exec'), scope)
            old = Path(folder) / 'old.png'; old.write_bytes(b'old-client-cache')
            self.upload('logo', 0, png())
            with self.connect() as c: c.execute("UPDATE settings SET value=? WHERE key='shop_logo'", (str(old),))
            actual = Path(scope['resolve_receipt_image_path']('logo'))
            self.assertEqual(actual.read_bytes(), image_png(png()))


class FileUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_image_resource_print_document_and_journal_privacy(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QTextDocument
        from native_pos.receipt import ReceiptDialog, receipt_html
        from native_pos.protected_journal import ProtectedJournal
        content = base64.b64encode(image_png(png())).decode()
        receipt = dict(receipt_settings=dict(shop_logo_image='data:image/png;base64,' + content, shop_qr_code_image='https://untrusted.invalid/image'))
        dialog = ReceiptDialog(receipt)
        resource = dialog.document.document().resource(QTextDocument.ResourceType.ImageResource, QUrl('native-receipt:logo'))
        self.assertFalse(resource.isNull()); self.assertNotIn('native-receipt:qr', receipt_html(receipt)); dialog.close()
        with tempfile.TemporaryDirectory() as folder:
            journal = ProtectedJournal('https://fixture.invalid/files', 1, folder)
            pending = dict(payload=dict(request_id=str(uuid4()), operation='photo.save', values=dict(content=content)))
            journal.write(pending); self.assertNotIn(content, journal.path.read_text()); self.assertEqual(journal.read(), pending)
            journal.write(dict(pending, result={'message': 'Saved'})); self.assertNotIn('content', journal.path.read_text())


if __name__ == '__main__': unittest.main()
