"""Phase W5 cash checkout tests."""
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from server import api


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosPhaseW5Tests(unittest.TestCase):
    def test_touch_sale_endpoint_requires_sales_permission(self):
        payload = api.SaleRequest(items=[api.CartItem(product_id=1, qty=1)], payment=1000)
        with self.assertRaises(HTTPException) as caught:
            api.touch_pos_create_sale(payload, {"role": "Viewer", "permissions": []})
        self.assertEqual(caught.exception.status_code, 403)

    def test_touch_sale_endpoint_delegates_to_existing_sale_service(self):
        payload = api.SaleRequest(
            items=[api.CartItem(product_id=7, variant_id=3, qty=2, manual_price=None)],
            payment=5000,
            payment_type="Cash",
            sale_mode="Cash",
        )
        receipt = {"invoice_no": "WEB1", "total": 4000, "items": [{"qty": 2}]}
        with patch("server.api.cashier_service.create_sale", return_value=receipt) as create_sale:
            result = api.touch_pos_create_sale(payload, {"username": "cashier1", "role": "Cashier", "permissions": ["create_sale"]})
        create_sale.assert_called_once()
        kwargs = create_sale.call_args.kwargs
        self.assertEqual(kwargs["items"], [{"product_id": 7, "variant_id": 3, "qty": 2, "manual_price": None}])
        self.assertEqual(kwargs["payment"], 5000)
        self.assertEqual(kwargs["payment_type"], "Cash")
        self.assertEqual(kwargs["sale_mode"], "Cash")
        self.assertEqual(kwargs["created_by"], "cashier1")
        self.assertEqual(result, {"receipt": receipt})

    def test_touch_sale_endpoint_reports_business_errors(self):
        payload = api.SaleRequest(items=[api.CartItem(product_id=1, qty=1)], payment=100)
        with patch("server.api.cashier_service.create_sale", side_effect=ValueError("Insufficient payment")):
            with self.assertRaises(HTTPException) as caught:
                api.touch_pos_create_sale(payload, {"role": "Admin", "permissions": []})
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, "Insufficient payment")

    def test_shell_contains_cash_checkout_controls(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for marker in (
            'id="paymentAmount"',
            'data-cash="exact"',
            'id="changeDue"',
            'id="receiptModal"',
            'id="receiptInvoice"',
            'Complete Cash Sale',
            'Phase W7',
        ):
            self.assertIn(marker, html)

    def test_client_posts_touch_sale_and_keeps_later_features_as_placeholders(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("function checkoutCashSale", script)
        self.assertIn("api('/api/touch-pos/sales'", script)
        self.assertIn("payment_type: 'Cash'", script)
        self.assertIn("sale_mode: 'Cash'", script)
        self.assertIn("manual_price: item.is_service", script)
        self.assertIn("await loadProducts(); showReceipt", script)
        self.assertIn("Insufficient payment.", script)
        self.assertIn("addEventListener('click', holdCart)", script)
        self.assertNotIn("api('/api/sales'", script)


if __name__ == "__main__":
    unittest.main()
