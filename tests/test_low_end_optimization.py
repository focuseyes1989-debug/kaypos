import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.sales_page.product_grid import ProductGrid
from ui.lazy_loading_widget import HamsterProgressWidget


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

    def test_low_end_mode_does_not_decode_or_animate_hamster(self):
        with (
            patch(
                "ui.lazy_loading_widget.get_performance_settings",
                return_value=SimpleNamespace(low_end_mode=True),
            ),
            patch.object(HamsterProgressWidget, "_load_frames") as load_frames,
        ):
            progress = HamsterProgressWidget()

        load_frames.assert_not_called()
        self.assertEqual(progress._frames, [])
        self.assertIsNone(progress.animation_timer)
        self.assertTrue(progress.hamster.isHidden())
        self.assertEqual(progress.height(), 36)
        progress.deleteLater()

    def test_cached_category_tree_avoids_database_round_trip(self):
        grid = ProductGrid(autoload=False)
        grid._category_tree_cache = {10: [10, 11, 12]}
        with patch("ui.sales_page.product_grid.connect_db") as connect:
            result = grid._get_category_tree_ids(10)
        self.assertEqual(result, [10, 11, 12])
        connect.assert_not_called()
        grid.deleteLater()

    def test_low_end_category_slider_skips_sales_ranking_query(self):
        grid = ProductGrid(autoload=False)
        grid._performance_settings = SimpleNamespace(low_end_mode=True)
        cursor = MagicMock()
        cursor.fetchall.return_value = [("Food", None, None, 1)]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        grid.category_slider.load_categories = MagicMock()

        with patch("ui.sales_page.product_grid.connect_db", return_value=connection):
            grid._load_category_slider_data()

        self.assertEqual(cursor.execute.call_count, 1)
        grid.category_slider.load_categories.assert_called_once_with(
            [("Food", None, None, 1)], groups=None, top_categories=[]
        )
        grid.deleteLater()


if __name__ == "__main__":
    unittest.main()
