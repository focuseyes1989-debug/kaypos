import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import utils.performance as performance
from ui.sales_page import product_utils


class LowEndPerformanceSettingsTests(unittest.TestCase):
    def tearDown(self):
        performance._CACHE = None

    def test_low_end_mode_enforces_aggressive_runtime_limits(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ("performance_low_end_mode", "1"),
            ("performance_product_page_size", "100"),
            ("performance_search_debounce_ms", "150"),
            ("performance_thumbnail_quality", "normal"),
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        performance._CACHE = None
        with patch("utils.performance.connect_db", return_value=connection):
            settings = performance.get_performance_settings(refresh=True)

        self.assertTrue(settings.low_end_mode)
        self.assertEqual(settings.product_page_size, 12)
        self.assertEqual(settings.search_debounce_ms, 600)
        self.assertEqual(settings.thumbnail_quality, "off")

    def test_disabled_thumbnails_do_not_open_image_files(self):
        settings = SimpleNamespace(thumbnail_quality="off")
        with (
            patch("ui.sales_page.product_utils.get_performance_settings", return_value=settings),
            patch("ui.sales_page.product_utils.QImageReader") as image_reader,
        ):
            result = product_utils.load_thumbnail("large-product.jpg", 120, 1)

        self.assertIsNone(result)
        image_reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
