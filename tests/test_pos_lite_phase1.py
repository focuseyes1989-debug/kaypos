import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QDate, QEventLoop, QSize, QTimer
from PyQt6.QtGui import QPalette, QPixmap
from PyQt6.QtWidgets import QApplication, QPushButton as QtPushButton, QTableWidgetItem

from lite_pos.api import LiteApiClient, LiteApiError
from lite_pos.application import apply_classic_style
from lite_pos.cart import CartError, LiteCart, sold_by_mode
from lite_pos.config import DEFAULT_SERVER_URL, load_config, save_config
from lite_pos.window import CheckoutDialog, ExpenseDialog, LiteWindow, ProductEditorDialog, ReceiptDialog


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
                "receipt_printer_name": "GA-E200I",
                "print_receipt_after_sale": True,
                "open_cash_drawer_after_sale": True,
            }, path)
            self.assertEqual(load_config(path), saved)
            self.assertEqual(saved["receipt_printer_name"], "GA-E200I")
            self.assertTrue(saved["print_receipt_after_sale"])
            self.assertTrue(saved["open_cash_drawer_after_sale"])

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
        self.assertFalse(dialog.print_after_sale.isChecked())
        self.assertFalse(dialog.open_drawer_after_sale.isChecked())
        self.assertTrue(hasattr(ReceiptDialog, "print_receipt_automatic"))
        dialog.close()

    def test_checkout_dialog_selects_customer_for_credit_sale(self):
        dialog = CheckoutDialog(15000, customers=[{
            "id": 4, "name": "Ko Kyaw Moe", "phone": "09664362121",
            "points": 12, "current_balance": 79000,
        }], payment_types=["Cash", "KBZPay", "Credit"])
        self.assertEqual(
            [dialog.payment_type.itemText(index) for index in range(dialog.payment_type.count())],
            ["Cash", "KBZPay", "Credit"],
        )
        dialog.customer.setCurrentIndex(1)
        dialog.open_drawer_after_sale.setChecked(True)
        dialog.payment_type.setCurrentText("Credit")
        self.assertEqual(dialog.selected_customer_id(), 4)
        self.assertEqual(dialog.payment.value(), 0)
        self.assertFalse(dialog.payment.isEnabled())
        self.assertFalse(dialog.open_drawer_after_sale.isEnabled())
        self.assertFalse(dialog.open_drawer_after_sale.isChecked())
        dialog.payment_type.setCurrentText("Cash")
        self.assertTrue(dialog.open_drawer_after_sale.isEnabled())
        self.assertTrue(dialog.open_drawer_after_sale.isChecked())
        self.assertIn("79,000", dialog.customer_info.text())
        dialog.close()

    @patch("lite_pos.api.requests.Session.request")
    def test_checkout_sends_customer_and_credit_sale_mode(self, request):
        response = unittest.mock.Mock(ok=True)
        response.json.return_value = {"receipt": {"id": 10, "invoice_no": "LITE-10", "total": 15000}}
        request.return_value = response
        client = LiteApiClient("https://server:8000")
        client.checkout([{"product_id": 7, "qty": 1}], 0, "Credit", 4)
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["customer_id"], 4)
        self.assertEqual(payload["sale_mode"], "Credit")
        self.assertEqual(payload["payment"], 0)

    def test_expense_dialog_returns_server_payload(self):
        dialog = ExpenseDialog(["Transport", "Utilities"])
        dialog.category.setCurrentText("Transport")
        dialog.description.setText("Delivery")
        dialog.amount.setValue(3500)
        dialog.date.setDate(QDate(2026, 8, 25))
        values = dialog.values()
        self.assertEqual(values["category"], "Transport")
        self.assertEqual(values["amount"], 3500)
        self.assertEqual(values["expense_date"], "2026-08-25")
        dialog.close()

    @patch("lite_pos.api.requests.Session.request")
    def test_expense_api_lists_and_adds_expenses(self, request):
        list_response = unittest.mock.Mock(ok=True)
        list_response.json.return_value = {"expenses": [{"id": 1}], "total": 3500}
        add_response = unittest.mock.Mock(ok=True)
        add_response.json.return_value = {"expense": {"id": 2, "expense_no": "EXP-2"}}
        request.side_effect = [list_response, add_response]
        client = LiteApiClient("https://server:8000")
        client.token = "token"
        self.assertEqual(client.expenses(from_date="2026-08-01", to_date="2026-08-31")["total"], 3500)
        saved = client.add_expense({"category": "Transport", "amount": 1000})
        self.assertEqual(saved["expense_no"], "EXP-2")

    @patch("lite_pos.api.requests.Session.request")
    def test_stock_in_sends_complete_audit_details(self, request):
        response = unittest.mock.Mock(ok=True)
        response.json.return_value = {"product": {"id": 7, "stock": 14}}
        request.return_value = response
        client = LiteApiClient("https://server:8000")
        client.adjust_stock(
            7, 3, variant_id=12, supplier_id=2, unit_cost=1250, batch_no="BATCH-20260825",
            received_by="Admin", location="Shop", notes="Delivery received",
            customer_id=4, reference="SOUT-1", issued_by="Manager",
            transaction_date="2026-08-25",
        )
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["variant_id"], 12)
        self.assertEqual(payload["supplier_id"], 2)
        self.assertEqual(payload["unit_cost"], 1250)
        self.assertEqual(payload["batch_no"], "BATCH-20260825")
        self.assertEqual(payload["received_by"], "Admin")
        self.assertEqual(payload["notes"], "Delivery received")
        self.assertEqual(payload["customer_id"], 4)
        self.assertEqual(payload["reference"], "SOUT-1")
        self.assertEqual(payload["issued_by"], "Manager")
        self.assertEqual(payload["transaction_date"], "2026-08-25")

    @patch("lite_pos.api.requests.Session.request")
    def test_adjustment_transfer_and_movements_api(self, request):
        adjustment_response = unittest.mock.Mock(ok=True)
        adjustment_response.json.return_value = {"product": {"id": 7, "stock": 8}}
        transfer_response = unittest.mock.Mock(ok=True)
        transfer_response.json.return_value = {"product": {"id": 7, "stock": 8}}
        movements_response = unittest.mock.Mock(ok=True)
        movements_response.json.return_value = {"movements": [{"id": 1, "type": "adjustment"}]}
        reverse_response = unittest.mock.Mock(ok=True)
        reverse_response.json.return_value = {"success": True, "message": "Movement reversed"}
        request.side_effect = [adjustment_response, transfer_response, movements_response, reverse_response]
        client = LiteApiClient("https://server:8000")
        client.set_stock_quantity({
            "product_id": 7, "new_quantity": 8, "reason": "Counted",
            "adjusted_by": "Admin", "location": "Shop",
        })
        client.transfer_stock({
            "product_id": 7, "from_location": "Shop", "to_location": "Store",
            "quantity": 2, "reason": "Replenishment",
        })
        movements = client.stock_movements(7)
        self.assertEqual(movements[0]["type"], "adjustment")
        reversed_result = client.reverse_stock_movement(1, "Counting correction")
        self.assertTrue(reversed_result["success"])
        self.assertEqual(request.call_args.kwargs["json"]["reason"], "Counting correction")

    def test_stock_management_action_buttons_are_available(self):
        window = LiteWindow()
        labels = {button.text() for button in window.findChildren(QtPushButton)}
        self.assertTrue({"Adjustment", "Transfer", "View Movements"}.issubset(labels))
        window.close()

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

    def test_sidebar_tracks_the_active_workspace_page(self):
        window = LiteWindow()
        self.assertTrue(window.nav_buttons["Dashboard"].isChecked())
        window._activate_workspace("Expenses")
        self.assertIs(window.workspace_stack.currentWidget(), window.expense_page)
        self.assertTrue(window.nav_buttons["Expenses"].isChecked())
        self.assertFalse(window.nav_buttons["Dashboard"].isChecked())
        window.workspace_stack.setCurrentWidget(window.pos_page)
        self.assertTrue(window.nav_buttons["Point of Sale"].isChecked())
        self.assertIn("Inventory", window.workspace_pages)
        self.assertIn("Customers", window.workspace_pages)
        self.assertNotIn("Stock & Customers", window.workspace_pages)
        self.assertIsNot(window.workspace_pages["Inventory"], window.workspace_pages["Customers"])
        window.close()

    def test_product_table_has_lazy_thumbnail_column(self):
        window = LiteWindow()
        self.assertEqual(window.product_table.columnCount(), 6)
        self.assertEqual(window.product_table.horizontalHeaderItem(0).text(), "Image")
        self.assertEqual(window.product_page_size, 50)
        self.assertEqual(window.product_table.iconSize(), QSize(44, 40))
        window.close()

    def test_product_stock_status_distinguishes_low_out_and_service(self):
        self.assertEqual(
            LiteWindow._product_stock_status({"sold_by": "Each", "low_stock": 3}, 0),
            "out",
        )
        self.assertEqual(
            LiteWindow._product_stock_status({"sold_by": "Each", "low_stock": 3}, 2),
            "low",
        )
        self.assertEqual(
            LiteWindow._product_stock_status({
                "sold_by": "Variants", "variants": [
                    {"stock": 8, "low_stock": 2}, {"stock": 1, "low_stock": 2},
                ],
            }, 9),
            "low",
        )
        self.assertEqual(
            LiteWindow._product_stock_status({"sold_by": "Service"}, 0),
            "normal",
        )

    def test_product_management_page_and_variant_editor(self):
        window = LiteWindow()
        self.assertIn("Products", window.workspace_pages)
        self.assertEqual(window.manage_product_table.columnCount(), 9)
        dialog = ProductEditorDialog(categories=["Frames"])
        dialog.name.setText("Frame 5x7")
        dialog.sold_by.setCurrentText("Variants")
        dialog.add_variant({"color": "White", "sku": "FR-W", "stock": 3, "price": 5000})
        values = dialog.values()
        self.assertEqual(values["sold_by"], "Variants")
        self.assertEqual(values["variants"][0]["sku"], "FR-W")
        self.assertEqual(values["variants"][0]["stock"], 3)
        dialog.close(); window.close()

    def test_product_editor_matches_each_service_and_variant_forms(self):
        dialog = ProductEditorDialog(categories=["CCTV"])
        self.assertTrue(dialog.barcode.isVisibleTo(dialog))
        self.assertTrue(dialog.price.isVisibleTo(dialog))
        self.assertFalse(dialog.variants.isVisibleTo(dialog))
        self.assertEqual((dialog.width(), dialog.height()), (750, 570))
        dialog.sold_by.setCurrentText("Service")
        self.assertTrue(dialog.barcode.isVisibleTo(dialog))
        self.assertFalse(dialog.price.isVisibleTo(dialog))
        self.assertIn("no stock tracking", dialog.mode_note.text())
        self.assertEqual((dialog.width(), dialog.height()), (750, 400))
        dialog.sold_by.setCurrentText("Variants")
        self.assertFalse(dialog.barcode.isVisibleTo(dialog))
        self.assertTrue(dialog.variants.isVisibleTo(dialog))
        self.assertIn("barcode, price and stock", dialog.mode_note.text())
        self.assertEqual((dialog.width(), dialog.height()), (750, 605))
        dialog.close()

    @patch("lite_pos.api.requests.Session.request")
    def test_product_management_api_sends_variants(self, request):
        response = unittest.mock.Mock(ok=True)
        response.json.return_value = {"product": {"id": 19, "name": "Frame"}}
        request.return_value = response
        client = LiteApiClient("https://server:8000")
        product = client.save_product({"name": "Frame", "sold_by": "Variants", "variants": [{"color": "White", "stock": 2}]})
        self.assertEqual(product["id"], 19)
        self.assertEqual(request.call_args.args[0], "POST")
        self.assertEqual(request.call_args.kwargs["json"]["variants"][0]["color"], "White")

    def test_management_stock_table_has_lazy_thumbnail_column(self):
        window = LiteWindow()
        self.assertEqual(window.stock_table.columnCount(), 5)
        self.assertEqual(window.stock_table.horizontalHeaderItem(0).text(), "Image")
        self.assertEqual(window.stock_table.iconSize(), QSize(44, 40))
        window.management_products = [{"id": 8}]
        window.stock_table.setRowCount(1)
        item = QTableWidgetItem()
        window.stock_table.setItem(0, 0, item)
        window._apply_product_thumbnail(8, QPixmap(4, 4))
        self.assertIs(window.stock_table.item(0, 0), item)
        window.close()

    def test_thumbnail_updates_reuse_the_owned_table_item(self):
        window = LiteWindow()
        window.products = [{"id": 7}]
        window.product_table.setRowCount(1)
        item = QTableWidgetItem()
        window.product_table.setItem(0, 0, item)
        pixmap = QPixmap(4, 4)
        window._apply_product_thumbnail(7, pixmap)
        window._apply_product_thumbnail(7, pixmap)
        self.assertIs(window.product_table.item(0, 0), item)
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
