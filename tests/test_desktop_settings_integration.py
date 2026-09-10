import os
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.settings.settings_center import SettingsCenterWidget


@unittest.skipUnless(os.environ.get("KAY_DESKTOP_QA_ISOLATED") == "1", "Use tests/run_desktop_qa.py for disposable database storage")
class SettingsIntegrationTests(unittest.TestCase):
    def test_all_default_settings_pages_fit_workspace(self):
        app = QApplication.instance() or QApplication([])
        with patch.object(QMessageBox, "warning", side_effect=AssertionError("Settings emitted a warning")), patch.object(QMessageBox, "critical", side_effect=AssertionError("Settings emitted an error")):
            settings = SettingsCenterWidget()
            try:
                settings.resize(1100, 620)
                settings.show()
                app.processEvents()
                self.assertEqual(settings.width(), 1100)
                for page in settings.pages:
                    with self.subTest(page=page["key"]):
                        settings.select_page(page["key"])
                        app.processEvents()
                        self.assertEqual(settings.width(), 1100)
                        self.assertEqual(settings.height(), 620)
                        self.assertTrue(settings.rect().contains(settings.stack.geometry()))
            finally:
                settings.close()
