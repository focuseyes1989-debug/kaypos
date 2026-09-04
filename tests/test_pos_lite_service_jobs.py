import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox
from lite_pos.window import LiteWindow
from server.service_order_service import ServiceOrderRepository


class PosLiteServiceJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "jobs.db"
        self.repo = ServiceOrderRepository(lambda: sqlite3.connect(path))
        self.window = LiteWindow()
        self.addCleanup(self.window.close)
        self.window.user = {"username": "tech"}
        self.window.api = Mock()
        self.window.api.service_orders.side_effect = lambda query="", status="", limit=200: self.repo.list(search=query, status=status, limit=limit)
        self.window.api.service_order.side_effect = self.repo.get
        self.window.api.change_service_order_status.side_effect = lambda order_id, status, note: self.repo.change_status(order_id, status, changed_by=self.window.user["username"], note=note)
        def run(operation, success, failure):
            try:
                result = operation()
            except Exception as exc:
                failure(str(exc))
            else:
                success(result)
        self.window._run_task = run

    def filter(self, status):
        combo = self.window.service_order_status_filter
        combo.setCurrentIndex(combo.findData(status))

    def test_full_work_and_collection_flow_with_separate_staff(self):
        job = self.repo.create({"job_title": "Print", "internal_notes": "Deposit 5000"}, created_by="server")
        window = self.window
        window.load_service_orders()
        self.assertTrue(window.service_order_start_button.isEnabled())
        self.assertFalse(window.service_order_collect_button.isEnabled())
        window.start_selected_service_order()
        self.assertEqual(window.service_order_table.item(0, 7).text(), "tech")
        self.assertFalse(window.service_order_start_button.isEnabled())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.complete_selected_service_order()
        self.filter("ready_for_pickup")
        self.assertEqual(window.service_order_table.rowCount(), 1)
        self.assertEqual(window.service_order_table.item(0, 5).text(), "Ready for Pickup")
        self.assertFalse(window.service_order_change_button.isEnabled())
        self.assertTrue(window.service_order_collect_button.isEnabled())
        self.assertTrue(window.service_order_edit_button.isEnabled())
        window.user = {"username": "cashier"}
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as question:
            window.collect_selected_service_order()
            self.assertIn("Deposit 5000", question.call_args.args[2])
        self.assertEqual(self.repo.get(job["id"])["status"], "ready_for_pickup")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.collect_selected_service_order()
        self.assertEqual(window.service_order_table.rowCount(), 0)
        self.filter("delivered")
        self.assertEqual(window.service_order_table.item(0, 10).text(), "cashier")
        self.assertIn("Work Completed By: tech", window.service_order_detail_summary.text())
        self.assertIn("Delivered By: cashier", window.service_order_detail_summary.text())
        self.assertFalse(window.service_order_collect_button.isEnabled())
        self.assertFalse(window.service_order_change_button.isEnabled())
        self.assertEqual(self.repo.get(job["id"])["internal_notes"], "Deposit 5000")

    def test_external_status_change_refreshes_without_new_job_and_keeps_selection(self):
        job = self.repo.create({"job_title": "Selected"}, created_by="server")
        self.repo.create({"job_title": "Other"}, created_by="server")
        window = self.window
        window.workspace_stack.setCurrentWidget(window.service_orders_page)
        window._poll_service_jobs()
        row = next(i for i, order in enumerate(window.service_orders_data) if order["id"] == job["id"])
        window.service_order_table.selectRow(row)
        self.repo.change_status(job["id"], "in_progress", changed_by="other-tech")
        window._poll_service_jobs()
        self.assertEqual(window.selected_service_order["id"], job["id"])
        self.assertIn("Working By: other-tech", window.service_order_detail_summary.text())
        self.assertFalse(window.service_order_start_button.isEnabled())

    def test_filters_include_legacy_ready_jobs_and_exclude_them_from_pending(self):
        for status in ["completed", "ready_for_pickup", "in_progress"]:
            job = self.repo.create({"job_title": status}, created_by="server")
            self.repo.change_status(job["id"], status, changed_by="tech")
        self.filter("ready_for_pickup")
        self.assertEqual(self.window.service_order_table.rowCount(), 2)
        self.assertTrue(self.window.service_order_collect_button.isEnabled())
        self.filter("pending")
        self.assertEqual(self.window.service_order_table.rowCount(), 1)
        self.filter("in_progress")
        self.assertEqual(self.window.service_order_table.rowCount(), 1)

    def test_failed_claim_refreshes_actual_owner(self):
        job = self.repo.create({"job_title": "Shared"}, created_by="server")
        self.window.load_service_orders()
        self.repo.change_status(job["id"], "in_progress", changed_by="other-tech")
        with patch.object(QMessageBox, "warning") as warning:
            self.window.start_selected_service_order()
        warning.assert_called_once()
        self.assertFalse(self.window._service_job_updating)
        self.assertIn("other-tech", self.window.service_order_detail_summary.text())
        self.assertFalse(self.window.service_order_start_button.isEnabled())
