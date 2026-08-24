import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.sales_page.product_grid import ProductGrid


class LowEndOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_product_grid_can_defer_initial_database_load(self):
        grid = ProductGrid(autoload=False)
        grid.load_categories = MagicMock()
        grid.load_products = MagicMock()

        grid.initialize_data()

        grid.load_categories.assert_called_once_with()
        grid.load_products.assert_called_once_with(page_size=grid.rows_per_page)
        grid.deleteLater()

    def test_secondary_product_views_are_created_on_demand(self):
        grid = ProductGrid(autoload=False)
        self.assertIsNone(grid.list_view)
        self.assertIsNone(grid.modern_grid_view)

        list_view = grid._ensure_view_widget(grid.VIEW_LIST)
        self.assertIs(list_view, grid.list_view)
        self.assertIsNone(grid.modern_grid_view)

        modern_view = grid._ensure_view_widget(grid.VIEW_MODERN_GRID)
        self.assertIs(modern_view, grid.modern_grid_view)
        grid.deleteLater()


if __name__ == "__main__":
    unittest.main()
