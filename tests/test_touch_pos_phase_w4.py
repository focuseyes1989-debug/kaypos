"""Phase W4 browser cart builder tests."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosPhaseW4Tests(unittest.TestCase):
    def test_shell_contains_touch_cart_targets(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for marker in (
            'id="cartItems"',
            'id="cartCount"',
            'id="cartSubtotal"',
            'id="cartTotal"',
            'id="clearCart"',
            'id="holdCart"',
            'id="paymentButton"',
        ):
            self.assertIn(marker, html)
        self.assertIn("Phase W7", html)

    def test_client_cart_is_session_only_and_stock_safe(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("CART_KEY = 'kay_touch_pos_cart'", script)
        self.assertIn("sessionStorage.setItem(CART_KEY", script)
        self.assertIn("sessionStorage.removeItem(CART_KEY)", script)
        self.assertIn("function addToCart", script)
        self.assertIn("Only ${stock} left", script)
        self.assertIn("Only ${item.stock || 0} left", script)
        self.assertIn("is out of stock", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("/api/sales", script)

    def test_cart_controls_render_quantities_and_totals(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        for marker in (
            "function renderCart",
            "data-cart-action=\"minus\"",
            "data-cart-action=\"plus\"",
            "data-cart-action=\"remove\"",
            "cartSubtotal",
            "cartTotal",
            "paymentButton",
        ):
            self.assertIn(marker, script)

    def test_variants_are_not_dropped_when_adding_to_cart(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("soldByMode(product.sold_by) !== 'variants'", script)
        self.assertIn("variant_id", script)
        self.assertIn("variantLabel(variant)", script)
        self.assertIn("variant?.sku || product.sku", script)

    def test_hold_control_is_available_from_w6(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("function holdCart", script)
        self.assertIn("addEventListener('click', holdCart)", script)


if __name__ == "__main__":
    unittest.main()
