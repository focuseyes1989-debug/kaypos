"""Phase W6 hold sale tests."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosPhaseW6Tests(unittest.TestCase):
    def test_shell_contains_restore_held_sale_control(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="restoreHeldCart"', html)
        self.assertIn("Restore Held Sale", html)
        self.assertIn("Phase W7", html)

    def test_client_stores_held_sale_in_session_storage(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("HELD_CART_KEY = 'kay_touch_pos_held_cart'", script)
        self.assertIn("function holdCart", script)
        self.assertIn("sessionStorage.setItem(HELD_CART_KEY", script)
        self.assertIn("held_at: new Date().toISOString()", script)
        self.assertIn("Sale held on this tablet.", script)
        self.assertNotIn("localStorage", script)

    def test_client_restores_held_sale_without_merging_carts(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("function restoreHeldCart", script)
        self.assertIn("Clear the current cart before restoring.", script)
        self.assertIn("sessionStorage.removeItem(HELD_CART_KEY); saveCart(); renderCart();", script)
        self.assertIn("Held sale restored.", script)

    def test_sign_out_and_session_expiry_clear_held_sale(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("function clearHeldCart", script)
        self.assertIn("clearHeldCart();", script)

    def test_w6_does_not_add_new_sale_mutation_paths(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("api('/api/touch-pos/sales'", script)
        self.assertNotIn("api('/api/sales'", script)


if __name__ == "__main__":
    unittest.main()
