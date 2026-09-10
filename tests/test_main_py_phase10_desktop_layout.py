"""Phase 10 desktop layout contract tests for the main KAY POS app."""
import unittest

from ui import responsive_utils
from ui.main_window.sidebar import Sidebar


class MainPyPhase10DesktopLayoutTests(unittest.TestCase):
    def test_shared_compact_metrics_target_1366_by_768(self):
        metrics = responsive_utils.get_desktop_compact_metrics()
        self.assertEqual(metrics["min_width"], 1366)
        self.assertEqual(metrics["min_height"], 768)
        self.assertEqual(metrics["header_height"], 56)
        self.assertEqual(metrics["content_margins"], (12, 10, 12, 10))
        self.assertLessEqual(metrics["sidebar_expanded"], 232)
        self.assertLessEqual(metrics["sidebar_collapsed"], 72)
        self.assertLessEqual(metrics["statusbar_max_height"], 30)

    def test_main_shell_uses_shared_compact_sidebar_metrics(self):
        metrics = responsive_utils.get_desktop_compact_metrics()
        self.assertEqual(Sidebar.WIDTH_EXPANDED, metrics["sidebar_expanded"])
        self.assertEqual(Sidebar.WIDTH_COLLAPSED, metrics["sidebar_collapsed"])
        self.assertLessEqual(Sidebar.NAV_HEIGHT_EXPANDED, 32)
        self.assertLessEqual(Sidebar.NAV_HEIGHT_COLLAPSED, 38)

    def test_resolution_helpers_keep_1366_baseline(self):
        self.assertEqual(responsive_utils.parse_resolution("bad-value"), (1366, 768))
        self.assertIn(("1366x768", 1366, 768), responsive_utils.get_supported_resolution_options(1920, 1080))
        width, height = responsive_utils.get_responsive_window_size(1366, 768)
        self.assertLessEqual(width, 1366)
        self.assertLessEqual(height, 768)
        self.assertGreaterEqual(width, 1024)
        self.assertGreaterEqual(height, 600)


if __name__ == "__main__":
    unittest.main()
