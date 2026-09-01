import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

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
        self.assertEqual(window.job_table.columnCount(), 7)
        self.assertEqual(window.complete_button.text(), "Complete Job")
        self.assertFalse(hasattr(window, "checkout_button"))
        window.close()


if __name__ == "__main__":
    unittest.main()
