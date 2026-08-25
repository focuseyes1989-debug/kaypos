import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

import ui.inventory_page.inventory_tabs as inventory_tabs


class _FakeTab(QWidget):
    created = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        type(self).created += 1
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1

    def export_to_excel(self):
        pass


class InventoryLazyTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_only_current_stock_is_built_until_another_tab_is_selected(self):
        _FakeTab.created = 0
        replacements = {
            "CurrentStockTab": _FakeTab, "LowStockTab": _FakeTab,
            "SuppliersTab": _FakeTab, "PurchaseHistoryTab": _FakeTab,
            "ExpiryTab": _FakeTab, "LogsTab": _FakeTab,
            "StockByLocationTab": _FakeTab,
        }
        with patch.multiple(inventory_tabs, **replacements), \
             patch.object(inventory_tabs.InventoryPage, "get_lang", return_value="en"):
            page = inventory_tabs.InventoryPage("admin")
            self.assertEqual(_FakeTab.created, 1)
            self.assertIsNone(page.low_stock_tab)
            page.tabs.setCurrentIndex(1)
            self.assertEqual(_FakeTab.created, 2)
            self.assertIsNotNone(page.low_stock_tab)
            self.assertIsNone(page.suppliers_tab)
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
