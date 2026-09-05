"""Phase W7 receipt print tests."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosPhaseW7Tests(unittest.TestCase):
    def test_shell_contains_print_receipt_controls(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="printReceipt"', html)
        self.assertIn('id="printReceiptButton"', html)
        self.assertIn("Print Receipt", html)
        self.assertIn("Phase W7", html)

    def test_client_builds_printable_receipt_text(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("function receiptLines", script)
        self.assertIn("receipt.invoice_no", script)
        self.assertIn("item.product_name || item.name", script)
        self.assertIn("Thank you.", script)
        self.assertIn("document.querySelector('#printReceipt').textContent = receiptLines(receipt, paid)", script)

    def test_print_button_uses_browser_print_only(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("addEventListener('click', () => window.print())", script)
        self.assertNotIn("printer", script.lower())
        self.assertNotIn("cash drawer", script.lower())

    def test_print_css_outputs_receipt_without_app_shell(self):
        css = (STATIC / "touch-pos.css").read_text(encoding="utf-8")
        self.assertIn("@media print", css)
        self.assertIn("body>*:not(#receiptModal)", css)
        self.assertIn(".print-receipt{display:block", css)
        self.assertIn("width:72mm", css)


if __name__ == "__main__":
    unittest.main()
