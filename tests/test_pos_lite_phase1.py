import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QDate, QEventLoop, QSize, QTimer
from PyQt6.QtGui import QPalette, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QHeaderView, QMessageBox, QPushButton as QtPushButton, QTableWidgetItem

from lite_pos.api import LiteApiClient, LiteApiError
from lite_pos.application import apply_classic_style
from lite_pos.cart import CartError, LiteCart, sold_by_mode
from lite_pos.config import DEFAULT_SERVER_URL, load_config, save_config
from lite_pos.window import CategoryManagerDialog, CheckoutDialog, ExpenseDialog, LiteSaleDisplay, LiteWindow, ProductEditorDialog, ReceiptDialog
from server.cashier_service import expand_category_scope, order_categories_by_usage


class PosLitePhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_config_round_trip_uses_separate_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            self.assertEqual(load_config(path)["server_url"], DEFAULT_SERVER_URL)
            self.assertTrue(load_config(path)["insecure_tls"])
            self.assertEqual(load_config(path)["theme"], "Light")
            saved = save_config({
                "server_url": "https://192.168.1.10:8000",
                "insecure_tls": True,
                "remember_username": "cashier",
                "receipt_printer_name": "GA-E200I",
                "print_receipt_after_sale": True,
                "open_cash_drawer_after_sale": True,
                "theme": "Dark",
            }, path)
            self.assertEqual(load_config(path), saved)
            self.assertEqual(saved["receipt_printer_name"], "GA-E200I")
            self.assertTrue(saved["print_receipt_after_sale"])
            self.assertTrue(saved["open_cash_drawer_after_sale"])
            self.assertEqual(saved["theme"], "Dark")

    def test_parent_category_scope_includes_children_and_subchildren(self):
        names, category_ids = expand_category_scope("Drinks", [
            (1, "Drinks", None),
            (2, "Juice", 1),
            (3, "Orange Juice", 2),
            (4, "Snacks", None),
        ])
        self.assertEqual(names, ["Drinks", "Juice", "Orange Juice"])
        self.assertEqual(category_ids, [1, 2, 3])

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
        self.assertEqual(payload["discount_amount"], 0)

    def test_checkout_dialog_calculates_change(self):
        dialog = CheckoutDialog(7500)
        dialog.payment.setValue(10000)
        self.assertEqual(dialog.change_label.text(), "2,500 Ks")
        self.assertFalse(dialog.print_after_sale.isChecked())
        self.assertFalse(dialog.open_drawer_after_sale.isChecked())
        self.assertTrue(hasattr(ReceiptDialog, "print_receipt_automatic"))
        dialog.close()

    def test_checkout_dialog_supports_amount_and_percent_discounts(self):
        dialog = CheckoutDialog(10000)
        dialog.discount_type.setCurrentIndex(dialog.discount_type.findData("amount"))
        dialog.discount_value.setValue(1500)
        self.assertEqual(dialog.discount_amount(), 1500)
        self.assertEqual(dialog.payable_total(), 8500)
        self.assertEqual(dialog.payment.value(), 8500)
        self.assertEqual(dialog.total_due_label.text(), "8,500 Ks")
        dialog.discount_type.setCurrentIndex(dialog.discount_type.findData("percent"))
        dialog.discount_value.setValue(10)
        self.assertEqual(dialog.discount_amount(), 1000)
        self.assertEqual(dialog.payable_total(), 9000)
        dialog.payment.setValue(10000)
        self.assertEqual(dialog.change_label.text(), "1,000 Ks")
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
        self.assertTrue(dialog.payment.isEnabled())
        self.assertTrue(dialog.credit_due_date.isVisibleTo(dialog))
        dialog.payment.setValue(5000)
        self.assertEqual(dialog.credit_balance_label.text(), "10,000 Ks")
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
        self.assertIn("due_date", payload)
        self.assertIn("credit_notes", payload)
        self.assertFalse(payload["allow_credit_over_limit"])

    @patch("lite_pos.api.requests.Session.request")
    def test_checkout_sends_discount_amount(self, request):
        response = unittest.mock.Mock(ok=True)
        response.json.return_value = {"receipt": {"id": 11, "invoice_no": "LITE-11", "total": 9000}}
        request.return_value = response
        client = LiteApiClient("https://server:8000")
        client.checkout([{"product_id": 7, "qty": 1}], 9000, "Cash", discount_amount=1000)
        self.assertEqual(request.call_args.kwargs["json"]["discount_amount"], 1000)

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

    def test_receipt_uses_setting_center_text_logo_and_shop_name(self):
        dialog = ReceiptDialog(
            {
                "invoice_no": "INV-10", "status": "completed", "created_at": "2026-08-26",
                "total": 1200, "payment": 1500, "change_amount": 300, "items": [],
            },
            settings={
                "shop_name": "KAY Mini Mart",
                "shop_logo_image": "data:image/png;base64,QUJD",
                "receipt_header": "Welcome\nDaily Fresh",
                "receipt_footer": "No refund after 7 days",
                "shop_footer_message": "Thank you!",
                "currency_symbol": "Ks",
            },
        )
        html = dialog._html()
        self.assertIn("KAY Mini Mart", html)
        self.assertIn("kaypos://receipt/logo", html)
        self.assertIn("Welcome<br>Daily Fresh", html)
        self.assertIn("No refund after 7 days", html)
        self.assertIn("Thank you!", html)
        dialog.close()

    def test_credit_receipt_shows_paid_balance_and_due_date(self):
        dialog = ReceiptDialog({
            "invoice_no": "CR-1", "payment_type": "Credit", "total": 15000,
            "payment": 5000, "paid_amount": 5000, "balance_amount": 10000,
            "due_date": "2026-09-10", "items": [],
        })
        html = dialog._html()
        self.assertIn("Credit Paid:</b> 5,000", html)
        self.assertIn("Balance Due:</b> 10,000", html)
        self.assertIn("2026-09-10", html)
        dialog.close()

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

    def test_lite_window_keeps_native_content_with_launcher_branded_sidebar(self):
        window = LiteWindow()
        window.apply_theme("Light", persist=False)
        self.assertEqual(window.styleSheet(), "")
        nav = window.workspace_page.findChild(
            __import__("PyQt6.QtWidgets", fromlist=["QFrame"]).QFrame, "nav"
        )
        self.assertIsNotNone(nav)
        self.assertIn("#5365df", nav.styleSheet().lower())
        self.assertIn("#eef1ff", window.statusBar().styleSheet().lower())
        self.assertTrue(all(
            frame.frameShape() == frame.Shape.StyledPanel
            for frame in window.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QFrame"]).QFrame)
            if frame.objectName() in {"card", "nav"}
        ))
        from lite_pos.window import QPushButton as CenteredButton
        self.assertGreater(len(window.findChildren(CenteredButton)), 10)
        self.assertTrue(all(button.styleSheet() == "" for button in window.findChildren(CenteredButton)))
        self.assertIn("F11", [shortcut.key().toString() for shortcut in window._shortcuts])
        self.assertIn("Esc", [shortcut.key().toString() for shortcut in window._shortcuts])
        self.assertIn("F2", [shortcut.key().toString() for shortcut in window._shortcuts])
        self.assertIn("F4", [shortcut.key().toString() for shortcut in window._shortcuts])
        window.close()

    def test_login_uses_compact_modal_dialog(self):
        window = LiteWindow()
        self.assertIsInstance(window.login_dialog, QDialog)
        self.assertTrue(window.login_dialog.isModal())
        self.assertLessEqual(window.login_dialog.width(), 500)
        self.assertLessEqual(window.login_dialog.height(), 400)
        self.assertEqual(window.login_dialog.windowTitle(), "Sign in · KAY POS Lite")
        window.show_login_dialog()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        self.assertTrue(window.login_dialog.isVisible())
        window.login_dialog.hide()
        window.close()

    def test_sidebar_tracks_the_active_workspace_page(self):
        window = LiteWindow()
        self.assertEqual(next(iter(window.nav_buttons)), "Point of Sale")
        self.assertTrue(all(button.property("leftAligned") for button in window.nav_buttons.values()))
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

    def test_pos_catalog_can_switch_between_list_and_grid_views(self):
        window = LiteWindow()
        window.set_product_view("list")
        self.assertIs(window.product_view_stack.currentWidget(), window.product_table)
        window.set_product_view("grid")
        self.assertIs(window.product_view_stack.currentWidget(), window.product_grid)
        self.assertTrue(window.grid_view_button.isChecked())
        window.set_product_view("list")
        self.assertIs(window.product_view_stack.currentWidget(), window.product_table)
        self.assertTrue(window.list_view_button.isChecked())
        window.close()

    def test_barcode_scan_is_not_blocked_by_catalog_task_and_keeps_checkout_enabled(self):
        window = LiteWindow()
        window.workspace_stack.setCurrentWidget(window.pos_page)
        window.show()
        self.app.processEvents()

        class Api:
            @staticmethod
            def scan_product(code):
                self.assertEqual(code, "123456")
                return {
                    "id": 7, "name": "Scanned item", "barcode": code,
                    "price": 1500, "stock": 5, "sold_by": "Each", "variants": [],
                }

        window.api = Api()
        window._threads.add(object())  # Simulate an in-flight debounced catalogue load.
        window._run_task = lambda operation, success, _failure: success(operation())
        window.product_search.setText("123456")
        window.scan_or_search()
        self.app.processEvents()

        self.assertEqual(window.cart.count(), 1)
        self.assertTrue(window.checkout_button.isEnabled())
        self.assertEqual(window.product_search.text(), "")
        self.assertTrue(window.product_search.hasFocus())
        window._threads.clear()
        window.close()

    def test_category_slider_preserves_server_popularity_order(self):
        window = LiteWindow()
        window._render_categories(["Drinks", "Snacks", "Household"])
        labels = [button.text() for button in window.category_group.buttons()]
        self.assertEqual(labels, ["All", "Drinks", "Snacks", "Household"])
        window.close()

    def test_popular_categories_are_ordered_before_alphabetical_categories(self):
        categories = ["CCTV", "Services", "ရေခဲမှုန့်", "General"]
        ordered = order_categories_by_usage(categories, {"services": 3791, "ရေခဲမှုန့်": 1696, "cctv": 3})
        self.assertEqual(ordered, ["Services", "ရေခဲမှုန့်", "CCTV", "General"])

    def test_lite_dashboard_matches_ai_dashboard_core_cards(self):
        window = LiteWindow()
        labels = {label.text().splitlines()[0] for label in window.dashboard_metrics}
        self.assertEqual(labels, {
            "Net Sales", "Transactions", "Gross Profit", "Expenses",
            "Net Profit", "Refunds", "Low / Out of Stock", "Outstanding Credit",
        })
        self.assertEqual(
            [window.dashboard_analytics.tabText(index) for index in range(window.dashboard_analytics.count())],
            ["Sale Categories", "Expense Categories", "Sales by Payment Type", "Daily Sales Trend"],
        )
        today = QDate.currentDate()
        self.assertEqual(window.dashboard_from.date(), QDate(today.year(), today.month(), 1))
        self.assertEqual(window.dashboard_to.date(), today)
        self.assertEqual(window.dashboard_sale_categories_status.text(), "0 item(s) loaded")
        self.assertEqual(window.dashboard_sale_categories_total.text(), "Total · 0 Ks")
        window.close()

    def test_product_table_has_lazy_thumbnail_column(self):
        window = LiteWindow()
        self.assertEqual(window.product_table.columnCount(), 6)
        self.assertEqual(window.product_table.horizontalHeaderItem(0).text(), "Image")
        self.assertEqual(window.product_page_size, 50)
        self.assertEqual(window.product_table.iconSize(), QSize(44, 40))
        window.close()

    def test_single_product_click_adds_item_to_cart(self):
        window = LiteWindow()
        window.products = [{
            "id": 501, "name": "Single Click Product", "price": 2500,
            "stock": 3, "sold_by": "each", "variants": [],
        }]
        window.product_table.setRowCount(1)
        window.product_table.setItem(0, 1, QTableWidgetItem("Single Click Product"))
        window.product_table.setCurrentCell(0, 1)
        window.product_table.clicked.emit(window.product_table.model().index(0, 1))
        self.assertEqual(window.cart.count(), 1)
        self.assertEqual(window.cart.total(), 2500)
        window.close()

    def test_sale_display_renders_live_cart_and_total(self):
        display = LiteSaleDisplay("Demo Shop")
        display.set_cart([
            {"name": "Coffee", "qty": 2, "price": 1500},
            {"name": "Shirt", "variant_label": "Blue / M", "qty": 1, "price": 5000},
        ])
        self.assertEqual(display.shop_label.text(), "Demo Shop")
        self.assertEqual(display.items_table.rowCount(), 2)
        self.assertEqual(display.items_table.item(1, 0).text(), "Shirt · Blue / M")
        self.assertEqual(display.total_label.text(), "8,000 Ks")
        display.close()

    def test_sale_display_target_is_different_from_pos_window_screen(self):
        first, second = object(), object()
        self.assertEqual(LiteWindow._sale_display_targets([first, second], first), [second])
        self.assertEqual(LiteWindow._sale_display_targets([first, second], second), [first])

    def test_pos_action_row_uses_sale_display_instead_of_printer_button(self):
        window = LiteWindow()
        button_texts = [button.text() for button in window.pos_page.findChildren(QtPushButton)]
        self.assertIn("Sale Display", button_texts)
        self.assertNotIn("Printer…", button_texts)
        self.assertEqual(window.checkout_button.minimumHeight(), 46)
        self.assertEqual(window.settings_page.nav.item(1).text(), "Local Printer")
        window.close()

    @patch("lite_pos.settings_center.save_config")
    def test_local_printer_settings_save_device_preferences(self, save):
        window = LiteWindow()
        page = window.settings_page
        page.receipt_printer.addItem("Test Receipt Printer", "Test Receipt Printer")
        page.receipt_printer.setCurrentIndex(page.receipt_printer.count() - 1)
        page.print_after_sale.setChecked(True)
        page.open_drawer_after_sale.setChecked(True)
        page.save_local_printer()
        save.assert_called_once_with({
            "receipt_printer_name": "Test Receipt Printer",
            "print_receipt_after_sale": True,
            "open_cash_drawer_after_sale": True,
        })
        window.close()

    @patch.object(QApplication, "screens", return_value=[])
    def test_automatic_sale_display_is_silent_without_extended_screen(self, _screens):
        window = LiteWindow()
        with patch.object(QMessageBox, "information") as information:
            self.assertFalse(window.open_sale_display_if_available())
            information.assert_not_called()
        window.close()

    def test_products_page_thumbnail_does_not_depend_on_pos_page_cache_render(self):
        window = LiteWindow()
        window.managed_products = [{"id": 77, "thumbnail_url": "/api/products/77/thumbnail"}]
        window.managed_product_rows = {77: 0}
        window.manage_product_table.setRowCount(1)
        window.manage_product_table.setItem(0, 0, QTableWidgetItem())
        pixmap = QPixmap(44, 40)
        pixmap.fill()
        window._apply_product_thumbnail(77, pixmap)
        self.assertFalse(window.manage_product_table.item(0, 0).icon().isNull())
        self.assertTrue(hasattr(window, "product_management_thumbnail_timer"))
        window.close()

    def test_product_page_exposes_parent_child_category_manager(self):
        window = LiteWindow()
        self.assertTrue(any(
            button.text() == "Manage Categories"
            for button in window.product_management_page.findChildren(QtPushButton)
        ))

        class FakeApi:
            @staticmethod
            def managed_categories():
                return [
                    {"id": 1, "name": "Drinks", "parent_id": None, "parent_name": "", "status": "active"},
                    {"id": 2, "name": "Juice", "parent_id": 1, "parent_name": "Drinks", "status": "active"},
                    {"id": 3, "name": "Orange Juice", "parent_id": 2, "parent_name": "Juice", "status": "active"},
                ]

        dialog = CategoryManagerDialog(FakeApi(), window)
        self.assertEqual(dialog.table.rowCount(), 3)
        self.assertEqual(dialog.table.item(0, 0).text(), "Drinks")
        self.assertIn("Juice", dialog.table.item(1, 0).text())
        self.assertNotEqual(dialog.table.item(0, 0).foreground().color(), dialog.table.item(1, 0).foreground().color())
        self.assertNotEqual(dialog.table.item(1, 0).foreground().color(), dialog.table.item(2, 0).foreground().color())
        self.assertEqual(dialog.table.item(0, 0).toolTip(), "Parent category")
        self.assertEqual(dialog.table.item(1, 0).toolTip(), "Child category")
        self.assertEqual(dialog.table.item(2, 0).toolTip(), "Sub-child category")
        self.assertEqual(dialog.table.item(2, 1).foreground().color(), dialog.table.item(1, 0).foreground().color())
        dialog.close(); window.close()

    def test_pos_receipt_action_is_replaced_by_add_expense(self):
        window = LiteWindow()
        self.assertEqual(window.add_expense_button.text(), "Add Expense")
        self.assertTrue(window.add_expense_button.isEnabled())
        self.assertFalse(any(
            button.text() == "Print Receipt"
            for button in window.pos_page.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QPushButton"]).QPushButton)
        ))
        window.close()

    def test_pos_add_expense_loads_categories_before_opening_dialog(self):
        window = LiteWindow()

        class FakeApi:
            @staticmethod
            def expense_categories():
                return ["Fuel", "Utilities"]

        window.api = FakeApi()
        window._run_task = lambda operation, success, _failure: success(operation())
        with patch("lite_pos.window.ExpenseDialog") as dialog_class:
            dialog_class.return_value.exec.return_value = QDialog.DialogCode.Rejected
            window.add_expense()
            dialog_class.assert_called_once_with(["Fuel", "Utilities"], window)
        self.assertTrue(window.expense_categories_loaded)
        self.assertEqual(window.add_expense_button.text(), "Add Expense")
        self.assertTrue(window.add_expense_button.isEnabled())
        window.api = None
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

    def test_product_editor_shows_existing_product_image(self):
        pixmap = QPixmap(120, 90)
        pixmap.fill()
        dialog = ProductEditorDialog(
            {"id": 77, "name": "Camera", "sold_by": "Each"},
            categories=["CCTV"], existing_pixmap=pixmap,
        )
        self.assertFalse(dialog.image_preview.pixmap().isNull())
        self.assertEqual(dialog.image_label.text(), "Current product image")
        self.assertEqual(dialog.image_path, "")
        dialog.close()

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

    def test_large_tables_avoid_resize_to_contents_and_page_loads_are_independent(self):
        window = LiteWindow()
        for table in (
            window.manage_product_table, window.stock_table, window.customer_table,
            window.product_table, window.expense_table, window.history_table,
        ):
            header = table.horizontalHeader()
            for column in range(table.columnCount()):
                self.assertNotEqual(header.sectionResizeMode(column), QHeaderView.ResizeMode.ResizeToContents)
        product_token = window._new_page_load("products")
        customer_token = window._new_page_load("customers")
        self.assertTrue(window._page_load_is_current("products", product_token))
        self.assertTrue(window._page_load_is_current("customers", customer_token))
        self.assertNotEqual(window._new_page_load("products"), product_token)
        self.assertTrue(window._page_load_is_current("customers", customer_token))
        window.close()

    def test_lite_uses_classic_windows_qt_style(self):
        style_name = apply_classic_style(self.app)
        self.assertEqual(style_name.lower(), "fusion")
        self.assertEqual(
            self.app.palette().color(QPalette.ColorRole.Window).name(),
            "#efefef",
        )

    @patch("lite_pos.window.save_config")
    def test_lite_theme_can_switch_and_settings_exposes_appearance(self, save):
        window = LiteWindow()
        self.assertNotIn(
            "KAY POS server settings · English interface",
            [label.text() for label in window.settings_page.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)],
        )
        self.assertEqual(window.settings_page.nav.item(0).text(), "Appearance")
        self.assertEqual(
            [window.settings_page.theme.itemText(index) for index in range(window.settings_page.theme.count())],
            ["Light", "Dark"],
        )
        self.assertEqual(window.apply_theme("Dark"), "Dark")
        self.assertEqual(
            self.app.palette().color(QPalette.ColorRole.Window).name(),
            "#171b26",
        )
        self.assertIn("#20283a", window.statusBar().styleSheet())
        save.assert_called_once_with({"theme": "Dark"})
        window.apply_theme("Light", persist=False)
        window.close()


if __name__ == "__main__":
    unittest.main()
