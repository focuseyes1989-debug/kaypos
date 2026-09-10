import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from ui.products_page.product_filters import ProductFilters
from ui.widgets.action_toolbar import ActionToolbar


class ManagementLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_product_search_grows_with_workspace(self):
        widget = ProductFilters()
        widget.resize(900, 50)
        widget.show()
        self.app.processEvents()
        small_width = widget.search_widget.width()
        widget.resize(1300, 50)
        self.app.processEvents()
        self.assertGreater(widget.search_widget.width(), small_width)
        combo_corner = widget.category_combo.mapTo(widget, widget.category_combo.rect().bottomRight())
        self.assertTrue(widget.rect().contains(combo_corner))
        widget.close()

    def test_long_action_label_and_callback(self):
        calls = []
        toolbar = ActionToolbar()
        button = toolbar.add_primary("Manage category groups", lambda: calls.append("primary"), width=78)
        action = toolbar.add_more_action("Export", lambda: calls.append("export"))
        toolbar.finalize()
        toolbar.show()
        self.app.processEvents()
        self.assertGreater(button.width(), 78)
        button.click()
        action.trigger()
        self.assertEqual(calls, ["primary", "export"])
        action.setEnabled(False)
        self.assertFalse(action.isEnabled())
        toolbar.close()


if __name__ == "__main__":
    unittest.main()
