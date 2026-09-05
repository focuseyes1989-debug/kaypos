import types
import unittest
from datetime import date
from unittest.mock import patch
from tests import test_native_pos_phase7 as phase7
from server.native_assistant import AssistantRepository
from native_pos.sales_digest import digest_period


class SalesDigestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_relative_periods_and_invalid_commands(self):
        today = date(2026, 9, 4)
        self.assertEqual(digest_period('digest weekly', today), ('2026-08-31', '2026-09-04'))
        self.assertEqual(digest_period('digest monthly', today), ('2026-09-01', '2026-09-04'))
        self.assertEqual(digest_period('digest daily', today), ('2026-09-04', '2026-09-04'))
        self.assertIsNone(digest_period('today sales'))
        with self.assertRaises(ValueError): digest_period('digest arbitrary sql')

    def test_digest_uses_report_snapshot_and_fresh_permissions(self):
        fixture = phase7.AdminDatabaseTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        repo = AssistantRepository(types.SimpleNamespace(**fixture.scope), fixture.employee)
        with fixture.connect() as conn: before = list(conn.iterdump())
        result = repo.ask(fixture.user, 'digest 2026-09-01 2026-09-04')
        self.assertTrue(result['digest']); self.assertEqual(result['report']['view'], 'overview')
        self.assertIn('percentage unavailable', result['message'])
        self.assertIn('No completed invoices', result['message'])
        self.assertIn('2026-08-28 to 2026-08-31', result['message'])
        with fixture.connect() as conn:
            self.assertEqual(before, list(conn.iterdump()))
            conn.execute("UPDATE users SET role='Cashier',permissions='ai_pages' WHERE id=1")
            conn.execute("UPDATE user_roles SET permissions='' WHERE name='Cashier'")
        with self.assertRaises(PermissionError): repo.ask(fixture.user, 'digest daily')

    def test_button_uses_selected_dates_without_new_transport(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QDate
        from native_pos.assistant import AssistantPage
        from native_pos.tasks import TaskRunner
        app = QApplication.instance() or QApplication([])
        page = AssistantPage(types.SimpleNamespace(runner=TaskRunner(), closing=False, route_pages={}))
        self.addCleanup(page.close)
        page.start.setDate(QDate(2026, 9, 1)); page.end.setDate(QDate(2026, 9, 4))
        with patch.object(page, 'ask') as ask:
            page.ask_digest(); ask.assert_called_once()
        self.assertEqual(page.query.text(), 'digest 2026-09-01 2026-09-04')
