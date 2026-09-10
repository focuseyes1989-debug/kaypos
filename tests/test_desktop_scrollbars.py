import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QScrollArea, QWidget, QScrollBar
from ui.design_system.scrollbars import install_scrollbar_style, scrollbar_stylesheet
from ui.themes.theme_manager import get_theme_colors


class ScrollbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shared_style_overrides_legacy_and_updates_existing_and_new_bars(self):
        area = QScrollArea()
        content = QWidget()
        content.setFixedSize(800, 800)
        area.setWidget(content)
        area.resize(300, 200)
        area.setStyleSheet("QScrollBar:vertical { width: 30px; background: red; }")
        area.show()
        try:
            for theme in ("Light", "Dark"):
                colors = get_theme_colors(theme)
                install_scrollbar_style(self.app, colors)
                self.app.processEvents()
                for bar in (area.verticalScrollBar(), area.horizontalScrollBar()):
                    self.assertEqual(bar.styleSheet(), scrollbar_stylesheet(colors))
                    bar.setValue(70)
                    self.assertEqual(bar.value(), 70)
                self.assertEqual(area.verticalScrollBar().width(), 10)
                self.assertEqual(area.horizontalScrollBar().height(), 10)
                bar = QScrollBar(Qt.Orientation.Vertical, area)
                bar.setStyleSheet("QScrollBar { background: red; }")
                bar.show()
                self.app.processEvents()
                self.assertEqual(bar.styleSheet(), scrollbar_stylesheet(colors))
                bar.deleteLater()
        finally:
            area.close()
            area.deleteLater()
            install_scrollbar_style(self.app, get_theme_colors())
