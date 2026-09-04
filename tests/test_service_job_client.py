import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QMessageBox

from service_job_client.config import load_config, save_config
from service_job_client.window import ServiceJobClientWindow


class ServiceJobClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_separate_config_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            save_config({"server_url": "https://server:8000", "insecure_tls": False, "remember_username": "client-2"}, path)
            config = load_config(path)
            self.assertEqual(config["server_url"], "https://server:8000")
            self.assertEqual(config["remember_username"], "client-2")
            self.assertFalse(config["insecure_tls"])

    def test_window_contains_only_job_workflow(self):
        window = ServiceJobClientWindow()
        self.assertEqual(window.windowTitle(), "KAY Service Job Client")
        self.assertEqual(window.job_table.columnCount(), 12)
        self.assertEqual(window.complete_button.text(), "Complete Job")
        self.assertFalse(hasattr(window, "checkout_button"))
        window.close()

    def test_start_job_shows_authenticated_worker_and_keeps_selection(self):
        window = ServiceJobClientWindow()
        self.addCleanup(window.close)
        window.user = {"username": "tech1"}
        window.api = Mock()
        rows = [{"id": 1, "job_title": "First", "status": "received"},
                {"id": 2, "job_title": "Second", "status": "received"}]
        window.api.service_orders.side_effect = lambda **kwargs: list(rows)
        def run(operation, success, failure):
            try:
                result = operation()
            except Exception as exc:
                failure(str(exc))
            else:
                success(result)
        window._run_task = run
        window.refresh_jobs()
        window.job_table.selectRow(1)
        self.assertTrue(window.start_button.isEnabled())
        def start(order_id, status, note):
            rows[1] = dict(rows[1], status=status, started_by="tech1", started_at="2026-09-04 10:00:00")
            return rows[1]
        window.api.change_service_order_status.side_effect = start
        window.start_job()
        self.assertEqual(window.selected_job["id"], 2)
        self.assertEqual(window.job_table.item(1, 7).text(), "tech1")
        self.assertEqual(window.detail_status.text(), "In Progress")
        self.assertIn("2026-09-04 10:00:00", window.detail_text.toPlainText())
        self.assertFalse(window.start_button.isEnabled())
        self.assertTrue(window.complete_button.isEnabled())
        window.status_filter.setCurrentIndex(window.status_filter.findData("in_progress"))
        self.assertEqual(window.job_table.rowCount(), 1)

    def test_no_console_windows_launcher_exists(self):
        launcher = Path(__file__).resolve().parents[1] / "service_job_client_main.pyw"
        self.assertTrue(launcher.is_file())
        self.assertIn("from service_job_client_main import main", launcher.read_text(encoding="utf-8"))

    def test_finish_then_collect_are_separate_actions_and_show_notes(self):
        window = ServiceJobClientWindow()
        self.addCleanup(window.close)
        window.user = {"username": "tech1"}
        window.api = Mock()
        rows = [{"id": 1, "job_title": "Print", "status": "in_progress", "internal_notes": "Deposit 5000"}]
        window.api.service_orders.side_effect = lambda **kwargs: list(rows)
        window._run_task = lambda operation, success, failure: success(operation())
        def change(order_id, status, note):
            fields = ({"completed_by": "tech1", "completed_at": "2026-09-04 10:00:00"}
                      if status == "ready_for_pickup" else {"delivered_by": "cashier1", "delivered_at": "2026-09-04 12:00:00"})
            rows[0] = dict(rows[0], status=status, **fields)
            return rows[0]
        window.api.change_service_order_status.side_effect = change
        window.refresh_jobs()
        self.assertFalse(window.collect_button.isEnabled())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.complete_job()
        self.assertEqual(rows[0]["status"], "ready_for_pickup")
        self.assertEqual(window.job_table.rowCount(), 0)
        window.status_filter.setCurrentIndex(window.status_filter.findData("ready_for_pickup"))
        self.assertEqual(window.detail_status.text(), "Ready for Pickup")
        self.assertFalse(window.complete_button.isEnabled())
        self.assertTrue(window.collect_button.isEnabled())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as confirm:
            window.collect_job()
            self.assertIn("Deposit 5000", confirm.call_args.args[2])
        self.assertEqual(rows[0]["status"], "ready_for_pickup")
        window.user = {"username": "cashier1"}
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.collect_job()
        window.status_filter.setCurrentIndex(window.status_filter.findData("delivered"))
        self.assertEqual(window.detail_status.text(), "Delivered")
        self.assertIn("Work Completed By: tech1", window.detail_text.toPlainText())
        self.assertIn("Delivered By: cashier1", window.detail_text.toPlainText())
        self.assertFalse(window.collect_button.isEnabled())
        self.assertFalse(window.complete_button.isEnabled())

    def test_legacy_completed_jobs_can_be_collected(self):
        window = ServiceJobClientWindow()
        self.addCleanup(window.close)
        window.api = Mock()
        window.api.service_orders.return_value = [{"id": 1, "status": "completed"}]
        window._run_task = lambda operation, success, failure: success(operation())
        window.status_filter.setCurrentIndex(window.status_filter.findData("ready_for_pickup"))
        self.assertEqual(window.job_table.rowCount(), 1)
        self.assertEqual(window.detail_status.text(), "Ready for Pickup")
        self.assertTrue(window.collect_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
