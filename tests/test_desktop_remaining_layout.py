import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QScrollArea
from ui.widgets.wrapping_toolbar import WrappingToolbar
from ui.employee_page import AttendanceTab
from ui.settings.settings_center import SettingsCenterWidget


class RemainingLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        font = Path(__file__).resolve().parents[1] / "assets/fonts/mmrtext.ttf"
        font_id = QFontDatabase.addApplicationFont(str(font))
        assert font_id >= 0, "Bundled Myanmar font did not load"
        cls.app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 10))

    def test_toolbar_wraps_and_unwraps_without_overlap(self):
        widget = QWidget()
        layout = WrappingToolbar(widget)
        buttons = [QPushButton(f"Action {i}") for i in range(6)]
        for button in buttons:
            button.setMinimumSize(150, 36)
            layout.addWidget(button)
        widget.resize(400, 200)
        widget.show()
        self.app.processEvents()
        small_height = layout.heightForWidth(400)
        self.assertGreater(small_height, layout.heightForWidth(1100))
        for width in (400, 1100, 400):
            widget.resize(width, 200)
            self.app.processEvents()
            for index, button in enumerate(buttons):
                self.assertTrue(widget.rect().contains(button.geometry()))
                for other in buttons[index + 1:]:
                    self.assertFalse(button.geometry().intersects(other.geometry()))
        widget.close()

    def test_attendance_toolbar_fits_short_workspace(self):
        with patch("ui.employee_page.service.list_employees", return_value=[]), patch.object(AttendanceTab, "refresh"):
            widget = AttendanceTab(1, True)
            for width in (900, 1100, 1600):
                widget.resize(width, 620)
                widget.show()
                self.app.processEvents()
                self.assertEqual(widget.width(), width)
                self.assertTrue(widget.rect().contains(widget.sync_button.geometry()))
                self.assertGreater(widget.table.height(), 200)
            output = os.environ.get("DESKTOP_QA_OUTPUT")
            if output:
                widget.resize(1100, 620)
                self.app.processEvents()
                widget.grab().save(str(Path(output) / "attendance.png"))
            widget.close()

    def test_settings_wrapped_page_keeps_navigation_and_scroll(self):
        with patch.object(SettingsCenterWidget, "build_pages"), patch.object(SettingsCenterWidget, "refresh_overview"):
            settings = SettingsCenterWidget()
            page = QWidget()
            layout = QVBoxLayout(page)
            for i in range(25):
                layout.addWidget(QPushButton(f"Setting {i}"))
            settings.add_page("test", "Test", "test", page)
            settings.resize(1000, 600)
            settings.show()
            self.app.processEvents()
            scroll = settings.stack.widget(0)
            self.assertIsInstance(scroll, QScrollArea)
            self.assertIs(settings.page_widgets["test"], page)
            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            settings.select_page("test")
            self.assertEqual(settings.stack.currentIndex(), 0)
            settings.close()

    def test_dashboard_cards_fit_without_overlap(self):
        from ui.dashboard.dashboard_page import DashboardPage
        with patch("ui.dashboard.dashboard_page.AIAssistantWidget", QWidget), patch.object(DashboardPage, "refresh_dashboard"), patch.object(DashboardPage, "retranslateUi"):
            widget = DashboardPage()
            for width in (1100, 1660):
                widget.resize(width, 620)
                widget.show()
                self.app.processEvents()
                self.assertEqual(widget.width(), width)
                cards = widget._get_all_cards()
                for index, card in enumerate(cards):
                    self.assertTrue(widget.left_widget.rect().contains(card.geometry()))
                    for other in cards[index + 1:]:
                        self.assertFalse(card.geometry().intersects(other.geometry()))
            output = os.environ.get("DESKTOP_QA_OUTPUT")
            if output:
                widget.resize(1100, 620)
                self.app.processEvents()
                widget.grab().save(str(Path(output) / "dashboard-qa.png"))
            widget.close()


if __name__ == "__main__":
    unittest.main()
