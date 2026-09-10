import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QComboBox, QPushButton
from ui.design_system.stylesheet import build_design_stylesheet


class DesktopControlGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_compact_controls_keep_geometry_on_focus(self):
        for theme in ("Light", "Dark"):
            with self.subTest(theme=theme):
                window = QWidget()
                window.setStyleSheet(build_design_stylesheet(theme))
                layout = QVBoxLayout(window)
                controls = [QLineEdit("Product search"), QComboBox(), QPushButton("Apply filters")]
                controls[1].addItem("All categories")
                for control in controls:
                    layout.addWidget(control)
                window.show()
                self.app.processEvents()
                before = [control.size() for control in controls]
                for control in controls:
                    control.setFocus()
                    self.app.processEvents()
                    self.assertEqual([item.size() for item in controls], before)
                    self.assertGreaterEqual(control.height(), 36)
                    self.assertLessEqual(control.height(), 42)
                window.close()


if __name__ == "__main__":
    unittest.main()
