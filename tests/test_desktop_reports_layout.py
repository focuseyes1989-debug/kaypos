import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QScrollArea
from ui.sales_summary.top_items_tab import _TopItemsBarChart
from ui.settings.settings_center import SettingsOverviewCard


class ReportLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_twenty_chart_rows_remain_scrollable(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        chart = _TopItemsBarChart()
        scroll.setWidget(chart)
        chart.set_data([(f"Product {i}", i + 1) for i in range(20)])
        scroll.resize(700, 300)
        scroll.show()
        self.app.processEvents()
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        self.assertGreaterEqual(chart.height(), 76 + 20 * 32)
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        chart.set_data([])
        self.app.processEvents()
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
        scroll.close()

    def test_settings_card_preserves_full_value_and_action(self):
        value = "Network printer in the main shop reception area"
        card = SettingsOverviewCard("Print", value, "Open Print")
        card.resize(240, 150)
        calls = []
        card.clicked.connect(lambda: calls.append(True))
        card.show()
        self.app.processEvents()
        self.assertTrue(card.content_label.wordWrap())
        self.assertIn(value, card.accessibleName())
        self.assertTrue(card.rect().contains(card.content_label.geometry()))
        card.click()
        self.assertEqual(calls, [True])
        card.set_value("Windows default")
        self.assertIn("Windows default", card.content_label.text())
        card.close()


if __name__ == "__main__":
    unittest.main()
