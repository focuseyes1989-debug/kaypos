"""Phase W9 responsive density and cache refresh tests."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosPhaseW9Tests(unittest.TestCase):
    def test_service_worker_caches_current_touch_css(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        worker = (STATIC / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("touch-pos.css?v=20260910-phase10-price-fit", html)
        self.assertIn("touch-pos.css?v=20260910-phase10-price-fit", worker)
        self.assertIn("kay-pos-touch-w10", worker)

    def test_touch_catalog_has_dense_breakpoints(self):
        css = (STATIC / "touch-pos.css").read_text(encoding="utf-8")
        self.assertIn("Phase 8: denser touch catalog", css)
        self.assertIn("(min-width:761px) and (max-width:1099px) and (orientation:portrait)", css)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", css)
        self.assertIn("grid-template-columns:repeat(auto-fill,minmax(112px,1fr))", css)
        self.assertIn("grid-template-columns:repeat(auto-fill,minmax(132px,1fr))", css)

    def test_touch_product_labels_and_fullscreen_icon_are_guarded(self):
        css = (STATIC / "touch-pos.css").read_text(encoding="utf-8")
        self.assertIn(".catalog .product-category", css)
        self.assertIn("min-height:17px", css)
        self.assertIn(".topbar #fullscreen[data-icon]::before", css)
        self.assertIn("transform:translate(-50%,-50%)!important", css)
        self.assertIn(".cart.open .totals", css)

    def test_maximized_desktop_product_prices_have_room(self):
        css = (STATIC / "touch-pos.css").read_text(encoding="utf-8")
        self.assertIn("Phase 10: keep product prices fully visible", css)
        self.assertIn("grid-template-rows:88px minmax(102px,auto)", css)
        self.assertIn("padding:8px 8px 12px", css)
        self.assertIn("white-space:nowrap", css)


if __name__ == "__main__":
    unittest.main()
