"""Expanded assistant report navigation/export on disposable fixtures."""
import csv
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from tests import test_native_pos_phase7 as phase7
from server.native_assistant import AssistantRepository
from native_pos.assistant_queries import REPORT_CHOICES


class AssistantReportServerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = phase7.AdminDatabaseTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.repo = AssistantRepository(types.SimpleNamespace(**self.fixture.scope), self.fixture.employee)

    def test_all_shortcuts_use_requested_view_period_and_shared_report(self):
        for label, section, view in REPORT_CHOICES:
            with self.subTest(label=label):
                result = self.repo.ask(self.fixture.user, f'report {section}/{view} 2026-09-01 2026-09-04')
                self.assertEqual(result['report_section'], section)
                self.assertEqual(result['report']['view'], view)
                self.assertEqual(result['report']['start'], '2026-09-01')
                self.assertEqual(result['report']['end'], '2026-09-04')
        result = self.repo.ask(self.fixture.user, 'hourly sales today')
        self.assertEqual(result['report']['view'], 'hourly')

    def test_invalid_commands_and_revoked_report_permission(self):
        for query in ('report summary/unknown', 'report summary/hourly 2026-09-04 2026-09-01', 'report summary/hourly 2026-02-31 2026-03-01', 'report reports/inventory; DROP TABLE products'):
            with self.subTest(query=query), self.assertRaises(ValueError): self.repo.ask(self.fixture.user, query)
        with self.fixture.connect() as c:
            c.execute("UPDATE users SET role='Cashier',permissions='ai_pages' WHERE id=1")
            c.execute("UPDATE user_roles SET permissions='' WHERE name='Cashier'")
        with self.assertRaises(PermissionError): self.repo.ask(self.fixture.user, 'report reports/invoices')


class AssistantReportUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from native_pos.assistant import AssistantPage
        from native_pos.tasks import TaskRunner
        self.host = types.SimpleNamespace(runner=TaskRunner(), closing=False, route_pages={})
        self.page = AssistantPage(self.host); self.addCleanup(self.page.close)
        self.report = dict(start='2026-09-01', end='2026-09-04', as_of='fixture', view='credit', tables=[
            dict(title='Credit accounts', columns=[dict(key='name', label='Name', kind='text')], rows=[{'name': 'A'}]),
            dict(title='Collections', columns=[dict(key='name', label='Name', kind='text'), dict(key='amount', label='Amount', kind='money')], rows=[dict(name='=formula', amount=i) for i in range(205)])])
        self.page.received(dict(message='Fixture report', report=self.report, report_section='reports', route_id=12))

    def test_all_tables_preview_cap_and_full_snapshot_export(self):
        self.assertEqual(self.page.table_choice.count(), 2)
        self.page.table_choice.setCurrentIndex(1)
        self.assertEqual(self.page.table.rowCount(), 200)
        self.assertIn('205', self.page.row_count.text())
        self.assertEqual(self.page.table.item(2, 1).text(), '2.00')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'result.csv'
            with patch('native_pos.assistant.QFileDialog.getSaveFileName', return_value=(str(path), 'CSV')): self.page.export()
            with path.open(encoding='utf-8-sig', newline='') as stream: rows = list(csv.reader(stream))
            self.assertEqual(len(rows), 206)
            self.assertEqual(rows[-1][-1], '204')
            self.assertEqual(rows[1][-2], "'=formula")

    def test_previous_period_keeps_view_and_selected_dates_generate_command(self):
        with patch.object(self.page, 'ask') as ask:
            self.page.previous_period(); ask.assert_called_once()
            self.assertEqual(self.page.query.text(), 'report reports/credit 2026-08-28 2026-08-31')
        with patch.object(self.page, 'ask'):
            self.page.report_choice.setCurrentIndex(self.page.report_choice.findData('summary/hourly'))
            self.page.ask_report()
            self.assertEqual(self.page.query.text(), 'report summary/hourly 2026-09-01 2026-09-04')
