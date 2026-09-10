"""Desktop integrations must not restart from previously saved settings."""

from pathlib import Path
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication


class RemovedIntegrationsTests(unittest.TestCase):
    def test_desktop_entry_points_do_not_reference_removed_services(self):
        root = Path(__file__).resolve().parents[1]
        paths = list((root / "ui/main_window").glob("*.py")) + [
            root / "ui/settings/settings_center.py",
            root / "ui/settings/performance_setting.py",
            root / "ui/settings/__init__.py",
            root / "ui/customer_page/customer_display.py",
        ]
        for path in paths:
            source = path.read_text(encoding="utf-8-sig").lower()
            with self.subTest(path=path.name):
                self.assertNotIn("telegram", source)
                self.assertNotIn("youtube", source)
                if path.name == "customer_display.py":
                    self.assertNotIn("webengine", source)

    def test_customer_display_keeps_local_cart_without_video(self):
        from ui.customer_page.customer_display import CustomerDisplayWindow

        app = QApplication.instance() or QApplication([])
        with patch.object(CustomerDisplayWindow, "load_shop_info"), patch(
            "ui.customer_page.customer_display.set_default_geometry"
        ):
            display = CustomerDisplayWindow()
            try:
                self.assertIsNotNone(display.cart_display)
                self.assertTrue(display.refresh_timer.isActive())
                self.assertFalse(hasattr(display, "youtube_view"))
                display.cart_display.update_display([])
            finally:
                display.refresh_timer.stop()
                display.deleteLater()
                app.processEvents()
