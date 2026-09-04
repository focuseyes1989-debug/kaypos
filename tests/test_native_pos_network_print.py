"""Network queue and drawer acceptance using mocked HTTP and Windows spooler."""
import base64
import ctypes
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QSignalSpy
from native_pos.config import load_config, save_config
from native_pos.data import Session
from native_pos.network_print import NetworkPrinterDialog, online_printers, server_url, request
from native_pos.cash_drawer import open_local_drawer


class NetworkPrintingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        path = Path(self.folder.name) / 'config.json'
        save_config(dict(print_server_url='https://print.invalid', print_agent='agent-fixture', print_remote_name='Receipt', receipt_paper='80mm'), path)
        self.host = types.SimpleNamespace(settings_path=path, config=load_config(path), session=Session(1, 'admin', 'Admin', 'Admin', frozenset()), store=types.SimpleNamespace(client=types.SimpleNamespace(server_url='https://pos.invalid', _request=Mock(return_value={'allowed': True}))))
        self.dialog = NetworkPrinterDialog(self.host, pdf=b'%PDF-1.4\nfixture\n%%EOF')
        self.dialog.key.setText('fixture-private-key')
        self.addCleanup(self.dialog.close)

    def wait(self, action):
        spy = QSignalSpy(self.dialog.runner.idle); action()
        if self.dialog.runner.busy: self.assertTrue(spy.wait(5000), 'Worker did not finish')
        self.app.processEvents()

    def test_lost_response_restart_recovers_same_pdf_and_id(self):
        jobs = {}; uploads = []
        def response(method, url, **kwargs):
            key = kwargs['data']['request_key']; uploads.append((key, kwargs['files']['file'][1]))
            jobs.setdefault(key, dict(job_id='job-fixture', request_key=key, status='pending'))
            if len(uploads) == 1: raise requests.Timeout('secret must not be displayed')
            return Mock(status_code=200, json=lambda: {'data': jobs[key]})
        with patch('native_pos.network_print.requests.request', side_effect=response), patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            self.wait(self.dialog.send)
            self.assertIsNotNone(self.dialog.pending)
            self.assertNotIn('fixture-private-key', self.dialog.journal.path.read_text())
            self.assertNotIn('secret must', self.dialog.message.text())
            self.dialog.close(); self.dialog = NetworkPrinterDialog(self.host)
            self.wait(self.dialog.recover)
        self.assertEqual(len(jobs), 1); self.assertEqual(uploads[0], uploads[1])
        self.assertIsNone(self.dialog.pending)
        self.assertNotIn('content', self.dialog.journal.path.read_text())
        self.assertNotIn('api_key', self.dialog.journal.path.read_text())
        self.assertIn('job-fixture', self.dialog.message.text())

    def test_rejected_recovery_preserves_original_unknown_request(self):
        with patch('native_pos.network_print.requests.request', side_effect=requests.Timeout()), patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            self.wait(self.dialog.send)
        key = self.dialog.pending['payload']['request_id']
        with patch('native_pos.network_print.requests.request', return_value=Mock(status_code=403)):
            self.wait(self.dialog.recover)
        self.assertEqual(self.dialog.pending['payload']['request_id'], key)
        self.assertIn('earlier request may still be queued', self.dialog.message.text())

    def test_first_rejection_allows_settings_correction(self):
        with patch('native_pos.network_print.requests.request', return_value=Mock(status_code=400)), patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            self.wait(self.dialog.send)
        self.assertIsNone(self.dialog.pending); self.assertFalse(self.dialog.journal.path.exists())
        self.assertTrue(self.dialog.agent.isEnabled())

    def test_pos_permission_denial_prevents_network_submission(self):
        self.host.store.client._request.side_effect = PermissionError('Printing permission revoked')
        with patch('native_pos.network_print.requests.request') as http, patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            self.wait(self.dialog.send); http.assert_not_called()
        self.assertIn('revoked', self.dialog.message.text())

    def test_server_authorization_uses_fresh_account_state(self):
        from tests import test_native_pos_phase7 as phase7
        from tests.test_native_pos_phase3 import LocalApiClient
        from server.native_catalog import CatalogRepository
        from server.native_printing import install_routes
        from fastapi import FastAPI
        fixture = phase7.AdminDatabaseTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        app = FastAPI(); install_routes(app, lambda: fixture.user, CatalogRepository(types.SimpleNamespace(**fixture.scope)))
        client = LocalApiClient(app)
        self.assertTrue(client.get('/api/native/printing/authorize').json()['allowed'])
        with fixture.connect() as c: c.execute('UPDATE users SET is_active=0 WHERE id=1')
        self.assertEqual(client.get('/api/native/printing/authorize').status_code, 403)

    def test_saved_key_encrypted_and_non_editor_cannot_change_target(self):
        with patch('native_pos.network_print.requests.request') as http:
            self.dialog.save(); http.assert_not_called()
        self.assertNotIn('fixture-private-key', self.host.settings_path.read_text())
        self.host.session = Session(1, 'cashier', 'Cashier', 'Cashier', frozenset({'print_receipt'}))
        self.dialog.close(); self.dialog = NetworkPrinterDialog(self.host, pdf=b'%PDF')
        self.assertEqual(self.dialog.key.text(), 'fixture-private-key')
        self.assertFalse(self.dialog.key.isEnabled()); self.assertFalse(self.dialog.save_button.isEnabled())
        self.assertTrue(self.dialog.send_button.isEnabled())

    def test_discovery_and_redirects_do_not_forward_credentials(self):
        values = self.dialog.values()
        data = {'data': [dict(agent_id='a', is_online=True, printers=[dict(printer_name='Online', status='online'), dict(printer_name='Old', status='offline')]), dict(agent_id='b', is_online=False, printers=[])]}
        with patch('native_pos.network_print.requests.request', return_value=Mock(status_code=200, json=lambda: data)) as http:
            self.assertEqual(online_printers(values), [('a', 'Online')])
            self.assertFalse(http.call_args.kwargs['allow_redirects'])
        with patch('native_pos.network_print.requests.request', return_value=Mock(status_code=302)):
            with self.assertRaisesRegex(ValueError, '302'): request(values, 'GET', '/api/printer/agents')
        for url in ('file:///tmp', 'https://name:secret@host', 'https://host/path', 'https://host?token=bad'):
            with self.assertRaises(ValueError): server_url(url)


class DrawerTests(unittest.TestCase):
    def test_fresh_permission_denial_never_sends_local_pulse(self):
        from native_pos.cash_drawer import authorized_local_drawer
        api = Mock(); api._request.side_effect = PermissionError('Revoked')
        with patch('native_pos.cash_drawer.open_local_drawer') as pulse:
            with self.assertRaises(PermissionError): authorized_local_drawer(api, 'Fixture')
            pulse.assert_not_called()
    def spool(self, written):
        spool = Mock()
        for name in ('OpenPrinterW', 'StartDocPrinterW', 'StartPagePrinter', 'EndPagePrinter', 'EndDocPrinter', 'ClosePrinter'):
            getattr(spool, name).return_value = 1
        def write(handle, buffer, length, count):
            self.assertEqual(ctypes.string_at(buffer, length), b'\x1b\x70\x00\x19\xfa')
            count._obj.value = written; return 1
        spool.WritePrinter.side_effect = write
        return spool

    def test_exact_pulse_and_cleanup_on_success(self):
        spool = self.spool(5)
        self.assertIn('Fixture printer', open_local_drawer('Fixture printer', spool)['message'])
        spool.EndPagePrinter.assert_called_once(); spool.EndDocPrinter.assert_called_once(); spool.ClosePrinter.assert_called_once()

    def test_partial_write_and_start_failure_close_handle(self):
        spool = self.spool(3)
        with self.assertRaises(OSError): open_local_drawer('Fixture', spool)
        spool.EndDocPrinter.assert_called_once(); spool.ClosePrinter.assert_called_once()
        spool = self.spool(5); spool.StartDocPrinterW.return_value = 0
        with self.assertRaises(OSError): open_local_drawer('Fixture', spool)
        spool.WritePrinter.assert_not_called(); spool.ClosePrinter.assert_called_once()
        spool = self.spool(5); spool.EndDocPrinter.return_value = 0
        with self.assertRaises(OSError): open_local_drawer('Fixture', spool)
        spool.ClosePrinter.assert_called_once()
        with self.assertRaises(ValueError): open_local_drawer('', spool)


if __name__ == '__main__': unittest.main()
