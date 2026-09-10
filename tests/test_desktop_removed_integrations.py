"""Desktop integrations must not restart from previously saved settings."""

from pathlib import Path
import unittest
import os
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication


class RemovedIntegrationsTests(unittest.TestCase):
    def test_combo_popup_expands_without_resizing_control(self):
        from ui.widgets.combo_box_widget import ComboBoxWidget
        app = QApplication.instance() or QApplication([])
        combo = ComboBoxWidget()
        combo.addItems(["All Categories", "CCTV Accessories and Replacement Components"])
        combo.setFixedWidth(160)
        combo.show()
        combo.showPopup()
        app.processEvents()
        self.assertEqual(combo.width(), 160)
        self.assertGreater(combo.view().window().width(), 250)
        self.assertLessEqual(combo.view().window().width(), combo.screen().availableGeometry().width())
        output = os.environ.get("DESKTOP_QA_OUTPUT")
        if output:
            combo.view().window().grab().save(str(Path(output) / "combo-popup.png"))
        combo.hidePopup()
        combo.close()
        combo.deleteLater()

    def test_sales_default_category_popup_expands(self):
        from ui.sales_page.product_grid import ProductGrid
        app = QApplication.instance() or QApplication([])
        grid = ProductGrid(autoload=False)
        combo = grid.category_combo
        combo.addItem("CCTV Accessories and Replacement Components")
        grid.resize(800, 500)
        grid.show()
        combo.showPopup()
        app.processEvents()
        self.assertEqual(combo.width(), 160)
        self.assertGreater(combo.view().window().width(), 250)
        combo.hidePopup()
        grid.close()
        grid.deleteLater()

    def test_category_navigation_and_selection(self):
        from ui.sales_page.category_slider import CategorySlider
        app = QApplication.instance() or QApplication([])
        slider = CategorySlider()
        slider.resize(740, 44)
        slider.load_categories([(f"Category {i}", None, "", 1) for i in range(15)])
        slider.show()
        slider._update_scroll_area()
        app.processEvents()
        self.assertFalse(slider._previous.isEnabled())
        slider._next.click()
        self.assertGreater(slider.horizontalScrollBar().value(), 0)
        slider.set_selected_category("Category 9")
        app.processEvents()
        self.assertEqual(sum(button.isChecked() for button in slider._buttons), 1)
        self.assertEqual(slider._selected_category, "Category 9")
        output = os.environ.get("DESKTOP_QA_OUTPUT")
        if output:
            slider.grab().save(str(Path(output) / "category-slider.png"))
        slider.close()
        slider.deleteLater()

    def test_cloud_fallback_is_ignored(self):
        from utils.db_compat import database_urls
        with patch.dict(os.environ, {
            "ZAY_POS_DATABASE_URL": "postgresql://local/pos",
            "ZAY_POS_DATABASE_FAILOVER_ENABLED": "1",
            "ZAY_POS_DATABASE_FALLBACK_URL": "postgresql://retired/cloud",
        }):
            self.assertEqual(database_urls(), ["postgresql://local/pos"])

    def test_local_database_dialog_is_compact(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
        from ui.settings.database_connection_setting import DatabaseConnectionSettingWidget
        module = "ui.settings.database_connection_setting"
        app = QApplication.instance() or QApplication([])
        with patch(module + ".load_database_config", return_value={"host": "192.168.110.112"}), patch(
            module + ".save_database_config"
        ) as save, patch(module + ".test_database_connection", return_value=(True, "Connected.")) as test:
            dialog = QDialog()
            layout = QVBoxLayout(dialog)
            widget = DatabaseConnectionSettingWidget()
            layout.addWidget(widget)
            dialog.resize(480, 420)
            dialog.show()
            app.processEvents()
            self.assertLessEqual(dialog.height(), 460)
            self.assertEqual({b.text() for b in widget.findChildren(QPushButton)}, {"Test Connection", "Save"})
            widget.btn_test.click()
            test.assert_called_once()
            self.assertEqual(widget.status_label.text(), "Connected.")
            with patch.object(widget, "_prompt_restart"):
                widget.btn_save.click()
            save.assert_called_once()
            self.assertTrue(widget.rect().contains(widget.btn_save.mapTo(widget, widget.btn_save.rect().bottomRight())))
            output = os.environ.get("DESKTOP_QA_OUTPUT")
            if output:
                dialog.grab().save(str(Path(output) / "database-local.png"))
            dialog.close()
            dialog.deleteLater()

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
