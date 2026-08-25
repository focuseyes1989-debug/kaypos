import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QPushButton as QtPushButton

from lite_pos.api import LiteApiClient, LiteApiError
from lite_pos.application import apply_classic_style
from lite_pos.cart import CartError, LiteCart, sold_by_mode
from lite_pos.config import DEFAULT_SERVER_URL, load_config, save_config
from lite_pos.window import CheckoutDialog, LiteWindow, ReceiptDialog


class PosLitePhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_config_round_trip_uses_separate_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            self.assertEqual(load_config(path)["server_url"], DEFAULT_SERVER_URL)
            self.assertTrue(load_config(path)["insecure_tls"])
            saved = save_config({
                "server_url": "https://192.168.1.10:8000",
                "insecure_tls": True,
                "remember_username": "cashier",
            }, path)
            self.assertEqual(load_config(path), saved)

    @patch("lite_pos.api.requests.Session.request")
    def test_login_stores_token_and_me_uses_bearer_auth(self, request):
        login_response = unittest.mock.Mock(ok=True)
        login_response.json.return_value = {
            "token": "token-1", "user": {"username": "cashier", "role": "Cashier"},
        }
        me_response = unittest.mock.Mock(ok=True)
        me_response.json.return_value = {"user": {"username": "cashier", "role": "Cashier"}}
        request.side_effect = [login_response, me_response]
        client = LiteApiClient("https://server:8000", insecure_tls=True)
        self.assertEqual(client.login("cashier", "secret")["role"], "Cashier")
        self.assertEqual(client.current_user()["username"], "cashier")
        self.assertFalse(request.call_args.kwargs["verify"])
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer token-1")

    @patch("lite_pos.api.requests.Session.request")
    def test_server_error_is_presented_as_lite_api_error(self, request):
        response = unittest.mock.Mock(ok=False, status_code=401)
        response.json.return_value = {"detail": "Invalid username/password or inactive user"}
        request.return_value = response
        with self.assertRaisesRegex(LiteApiError, "Invalid username"):
            LiteApiClient("https://server:8000").login("bad", "bad")

    def test_server_url_without_scheme_defaults_to_https(self):
        client = LiteApiClient("192.168.110.196:8000", insecure_tls=True)
        self.assertEqual(client.server_url, "https://192.168.110.196:8000")

    def test_background_task_finishes_and_releases_worker(self):
        window = LiteWindow()
        loop = QEventLoop()
        result = []

        def succeeded(value):
            result.append(value)

        window._run_task(lambda: "finished", succeeded, self.fail)
        QTimer.singleShot(2000, loop.quit)
        while window._threads and not result:
            QTimer.singleShot(20, loop.quit)
            loop.exec()
        self.assertEqual(result, ["finished"])
        QTimer.singleShot(50, loop.quit)
        loop.exec()
        self.assertFalse(window._workers)
        window.close()

    def test_cart_separates_variants_and_enforces_stock(self):
        cart = LiteCart()
        product = {"id": 7, "name": "Frame", "price": 5000, "stock": 3}
        white = {"variant_id": 11, "color": "White", "price": 5500, "stock": 1}
        black = {"variant_id": 12, "color": "Black", "price": 6000, "stock": 2}
        cart.add(product, white)
        cart.add(product, black)
        cart.add(product, black)
        self.assertEqual(cart.count(), 3)
        self.assertEqual(cart.total(), 17500)
        with self.assertRaises(CartError):
            cart.add(product, white)

    def test_cart_sells_display_form_services_without_stock(self):
        cart = LiteCart()
        service = {
            "id": 8, "name": "Photo Service", "price": 2500,
            "stock": 0, "sold_by": "Sold by Service",
        }
        cart.add(service)
        cart.add({**service, "price": 3000})
        self.assertEqual(cart.count(), 2)
        self.assertEqual(cart.total(), 5500)
        self.assertEqual(sold_by_mode("Sold by Variants"), "variants")

    @patch("lite_pos.api.requests.Session.request")
    def test_checkout_sends_variant_and_receives_receipt(self, request):
        response = unittest.mock.Mock(ok=True)
        response.json.return_value = {"receipt": {"id": 9, "invoice_no": "LITE-9", "total": 6000}}
        request.return_value = response
        client = LiteApiClient("https://server:8000")
        client.token = "token"
        receipt = client.checkout(
            [{"product_id": 7, "variant_id": 12, "qty": 1, "manual_price": None}],
            10000,
            "Cash",
        )
        self.assertEqual(receipt["invoice_no"], "LITE-9")
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["items"][0]["variant_id"], 12)
        self.assertEqual(payload["payment"], 10000)

    def test_checkout_dialog_calculates_change(self):
        dialog = CheckoutDialog(7500)
        dialog.payment.setValue(10000)
        self.assertEqual(dialog.change_label.text(), "2,500 Ks")
        dialog.close()

    def test_completed_receipt_detail_has_refund_button(self):
        callback = unittest.mock.Mock()
        dialog = ReceiptDialog(
            {"id": 3, "invoice_no": "INV-3", "status": "completed", "payment_type": "Cash"},
            refund_callback=callback,
        )
        labels = {button.text() for button in dialog.findChildren(QtPushButton)}
        self.assertIn("Refund Receipt", labels)
        dialog.close()

        refunded = ReceiptDialog(
            {"id": 3, "invoice_no": "INV-3", "status": "refunded", "payment_type": "Cash"},
            refund_callback=callback,
        )
        labels = {button.text() for button in refunded.findChildren(QtPushButton)}
        self.assertNotIn("Refund Receipt", labels)
        refunded.close()

    def test_cart_handles_repeated_low_end_workload_without_duplicate_rows(self):
        cart = LiteCart()
        for product_id in range(1, 101):
            product = {"id": product_id, "name": f"Item {product_id}", "price": 100, "stock": 20}
            for _ in range(10):
                cart.add(product)
        self.assertEqual(len(cart.items), 100)
        self.assertEqual(cart.count(), 1000)
        self.assertEqual(cart.total(), 100000)

    def test_api_client_reuses_one_http_session(self):
        client = LiteApiClient("https://server:8000")
        session = client.session
        self.assertIs(client.session, session)
        client.close()

    def test_lite_window_uses_native_qt_style_without_custom_stylesheet(self):
        window = LiteWindow()
        self.assertEqual(window.styleSheet(), "")
        self.assertTrue(all(
            frame.frameShape() == frame.Shape.StyledPanel
            for frame in window.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QFrame"]).QFrame)
            if frame.objectName() in {"card", "nav"}
        ))
        from lite_pos.window import QPushButton as CenteredButton
        self.assertGreater(len(window.findChildren(CenteredButton)), 10)
        self.assertTrue(all(button.styleSheet() == "" for button in window.findChildren(CenteredButton)))
        window.close()

    def test_lite_uses_classic_windows_qt_style(self):
        style_name = apply_classic_style(self.app)
        self.assertEqual(style_name.lower(), "fusion")
        self.assertEqual(
            self.app.palette().color(QPalette.ColorRole.Window).name(),
            "#efefef",
        )


if __name__ == "__main__":
    unittest.main()
