"""Real desktop transaction methods with disposable storage and mocked dialogs."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget
from models.database import connect_db
from models import variant_batches
from services.credit_service import CreditService
from ui.sales_page.checkout_handler.checkout_handler import CheckoutHandler
from ui.sales_page.checkout_handler.checkout_helpers import CheckoutHelpers
from ui.sales_page.checkout_handler.checkout_processor import CheckoutProcessor
from ui.sales_page.product_grid import ProductGrid
from ui.receipts_page.receipts_tab import ReceiptsTab
from ui.sales_page.checkout_handler.checkout_utils import print_receipt


@unittest.skipUnless(os.environ.get("KAY_DESKTOP_QA_ISOLATED") == "1", "Use the isolated QA runner")
class DesktopWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.conn = connect_db()
        self.addCleanup(self.conn.close)
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO products (name, price, stock, sold_by) VALUES (?,100,17,'Each')", (f"QA-{uuid4()}",))
        self.product_id = cursor.lastrowid
        cursor.execute("INSERT INTO product_locations (product_id, location, batch_no, expire_date, quantity) VALUES (?,'Shop','QA','',17)", (self.product_id,))
        self.location_id = cursor.lastrowid
        self.conn.commit()
        self.cart = [dict(id=self.product_id, name="QA product", qty=2, price=100, location_id=self.location_id)]
        self.page = QWidget()
        self.addCleanup(self.page.close)
        self.page.current_user = {"username": "qa-admin"}
        self.page.cart_widget = Mock()
        self.page.cart_widget.get_cart.return_value = self.cart
        self.page.cart_widget.compute_subtotal.return_value = 200
        self.page.totals_widget = Mock()
        self.page.totals_widget.get_current_grand_total.return_value = 200
        self.page.totals_widget.compute_regular_discount.return_value = 0
        self.page.totals_widget.compute_points_discount.return_value = 0
        self.page.options_widget = Mock()
        self.page.options_widget.is_credit_sale.return_value = False
        self.page.payment_widget = Mock()
        self.page.payment_widget.get_payment_amount.return_value = 250
        self.page.payment_widget.get_selected_payment_type.return_value = "Cash"
        self.page.product_grid = Mock()
        self.handler = SimpleNamespace(
            parent_widget=self.page, selected_customer_id=None,
            helpers=CheckoutHelpers(self.page), _show_completion_dialog=Mock(),
            _reset_after_checkout=Mock(), update_credit_radio_state=Mock(),
        )
        self.handler.processor = CheckoutProcessor(self.page, self.handler)
        for method in ("warning", "critical", "information", "question"):
            mock = self.enterContext(patch.object(QMessageBox, method, return_value=QMessageBox.StandardButton.Yes))
            setattr(self, method, mock)
        self.delete_backup = self.enterContext(patch("ui.sales_page.checkout_handler.checkout_handler.delete_cart_backup"))

    def stock(self):
        return self.conn.execute("SELECT stock FROM products WHERE id=?", (self.product_id,)).fetchone()[0]

    def test_cash_checkout_and_refund_are_stock_balanced(self):
        result = CheckoutHandler.checkout(self.handler)
        self.assertIsNotNone(result)
        self.assertEqual(result["change"], 50)
        self.assertEqual(self.stock(), 15)
        item = self.conn.execute("SELECT product_id, qty, location, batch_no FROM sale_items WHERE sale_id=?", (result["sale_id"],)).fetchone()
        self.assertEqual(tuple(item), (self.product_id, 2, "Shop", "QA"))
        receipt = SimpleNamespace(user_id=None, get_lang=lambda: "en", window=lambda: None, parent=lambda: None, load_sales=Mock())
        ReceiptsTab.refund_sale(receipt, result["sale_id"])
        self.critical.assert_not_called()
        self.assertEqual(self.stock(), 17)
        self.assertEqual(self.conn.execute("SELECT status FROM sales WHERE id=?", (result["sale_id"],)).fetchone()[0], "refunded")
        ReceiptsTab.refund_sale(receipt, result["sale_id"])
        self.assertEqual(self.stock(), 17)
        self.assertIn("already", self.warning.call_args.args[2])

    def test_insufficient_payment_does_not_deduct_stock(self):
        self.page.payment_widget.get_payment_amount.return_value = 199
        self.assertIsNone(CheckoutHandler.checkout(self.handler))
        self.assertEqual(self.stock(), 17)
        self.handler._reset_after_checkout.assert_not_called()
        self.delete_backup.assert_not_called()
        self.warning.assert_called_once()

    def test_metadata_write_failure_cannot_fall_back_to_anonymous_item(self):
        before = self.conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        # A persistent trigger is visible to the checkout connection as well.
        self.conn.execute("""CREATE TRIGGER qa_reject_metadata BEFORE INSERT ON sale_items
            WHEN NEW.product_id IS NOT NULL BEGIN SELECT RAISE(ABORT, 'QA metadata rejected'); END""")
        self.conn.commit()
        try:
            self.assertIsNone(CheckoutHandler.checkout(self.handler))
            self.assertEqual(self.stock(), 17)
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0], before)
            self.delete_backup.assert_not_called()
            self.critical.assert_called_once()
        finally:
            self.conn.execute("DROP TRIGGER qa_reject_metadata")
            self.conn.commit()

    def test_variant_sale_refund_restores_both_original_batches(self):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO product_variants (product_id, size, stock) VALUES (?,'PVC',17)", (self.product_id,))
        variant_id = cursor.lastrowid
        variant_batches.receive(cursor, self.product_id, variant_id, 1, "Shop", "A", "2098-01-01")
        variant_batches.receive(cursor, self.product_id, variant_id, 16, "Warehouse", "B", "2099-01-01")
        original = variant_batches.list_batches(cursor, self.product_id)
        self.conn.commit()
        self.cart[0].pop("location_id")
        self.cart[0]["variant_id"] = variant_id
        result = CheckoutHandler.checkout(self.handler)
        self.assertIsNotNone(result)
        rows = self.conn.execute("SELECT variant_id, qty, location, batch_no FROM sale_items WHERE sale_id=? ORDER BY batch_no", (result["sale_id"],)).fetchall()
        self.assertEqual([tuple(row) for row in rows], [(variant_id, 1, "Shop", "A"), (variant_id, 1, "Warehouse", "B")])
        self.assertEqual(self.stock(), 15)
        receipt = SimpleNamespace(user_id=None, get_lang=lambda: "en", window=lambda: None, parent=lambda: None, load_sales=Mock())
        ReceiptsTab.refund_sale(receipt, result["sale_id"])
        self.critical.assert_not_called()
        self.assertEqual(self.stock(), 17)
        self.assertEqual(self.conn.execute("SELECT stock FROM product_variants WHERE id=?", (variant_id,)).fetchone()[0], 17)
        self.assertEqual(variant_batches.list_batches(cursor, self.product_id), original)
        self.conn.commit()

    def test_credit_checkout_partial_and_final_payment(self):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO customers (name, current_balance) VALUES (?,0)", (f"QA-credit-{uuid4()}",))
        customer_id = cursor.lastrowid
        self.conn.commit()
        self.handler.selected_customer_id = customer_id
        self.handler.check_credit_limit = Mock(return_value=True)
        self.page.options_widget.is_credit_sale.return_value = True
        result = CheckoutHandler.checkout(self.handler)
        self.assertIsNotNone(result)
        self.assertEqual(result["payment_type"], "Credit")
        self.assertEqual(result["payment"], 0)
        credit_id = self.conn.execute("SELECT id FROM credit_sales WHERE sale_id=?", (result["sale_id"],)).fetchone()[0]
        service = CreditService()
        partial = service.make_payment(credit_id, 75)
        self.assertTrue(partial["success"])
        self.assertEqual(partial["new_balance"], 125)
        self.assertEqual(partial["status"], "partial")
        self.assertFalse(service.make_payment(credit_id, 126)["success"])
        final = service.make_payment(credit_id, 125)
        self.assertTrue(final["success"])
        self.assertEqual(final["status"], "paid")
        self.assertEqual(self.conn.execute("SELECT current_balance FROM customers WHERE id=?", (customer_id,)).fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM credit_payments WHERE credit_sale_id=?", (credit_id,)).fetchone()[0], 2)
        self.assertEqual(self.stock(), 15)

    def test_touch_credit_accepts_deposit_and_records_only_remaining_balance(self):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO customers (name, current_balance) VALUES (?,0)", (f"QA-deposit-{uuid4()}",))
        customer_id = cursor.lastrowid
        self.conn.commit()
        self.handler.selected_customer_id = customer_id
        self.handler.check_credit_limit = Mock(return_value=True)
        self.page.options_widget.is_credit_sale.return_value = True
        self.page._touch_checkout_active = True
        self.page.payment_widget.get_payment_amount.return_value = 75.5
        result = CheckoutHandler.checkout(self.handler)
        self.assertEqual(result["payment"], 75.5)
        self.handler.check_credit_limit.assert_called_once_with(124.5)
        row = self.conn.execute("SELECT paid_amount, balance_amount, status FROM credit_sales WHERE sale_id=?", (result["sale_id"],)).fetchone()
        self.assertEqual(tuple(row), (75.5, 124.5, "partial"))
        self.assertEqual(self.conn.execute("SELECT current_balance FROM customers WHERE id=?", (customer_id,)).fetchone()[0], 124.5)
        self.assertEqual(self.stock(), 15)

    def test_touch_credit_overpayment_does_not_change_stock(self):
        self.page._touch_checkout_active = True
        self.page.options_widget.is_credit_sale.return_value = True
        self.handler.selected_customer_id = 1
        self.page.payment_widget.get_payment_amount.return_value = 201
        self.assertIsNone(CheckoutHandler.checkout(self.handler))
        self.assertEqual(self.stock(), 17)
        self.handler._show_completion_dialog.assert_not_called()

    def test_failed_sale_item_write_rolls_back_sale_and_stock(self):
        before = self.conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        with patch.object(self.handler.processor, "create_sale_items", side_effect=RuntimeError("QA write failure")):
            self.assertIsNone(CheckoutHandler.checkout(self.handler))
        self.assertEqual(self.stock(), 17)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0], before)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM stock_movements WHERE product_id=?", (self.product_id,)).fetchone()[0], 0)
        self.handler._reset_after_checkout.assert_not_called()
        self.delete_backup.assert_not_called()
        self.critical.assert_called_once()

    def test_empty_cart_never_opens_completion(self):
        self.page.cart_widget.get_cart.return_value = []
        self.assertIsNone(CheckoutHandler.checkout(self.handler))
        self.handler._show_completion_dialog.assert_not_called()
        self.assertEqual(self.stock(), 17)

    def test_network_print_failure_keeps_completed_sale(self):
        result = CheckoutHandler.checkout(self.handler)
        response = SimpleNamespace(handled=True, success=False, message="QA printer offline")
        with patch("services.network_printer_client.queue_receipt", return_value=response) as queue:
            with patch("ui.sales_page.checkout_handler.checkout_utils.QPrinter") as local:
                self.assertFalse(print_receipt(self.page, result["sale_id"]))
                local.assert_not_called()
        self.assertEqual(queue.call_args.kwargs["request_key"], f"pos-sale-{result['sale_id']}")
        self.assertEqual(self.stock(), 15)
        self.assertEqual(self.conn.execute("SELECT status FROM sales WHERE id=?", (result["sale_id"],)).fetchone()[0], "completed")
        self.warning.assert_called_once()

    def test_network_print_success_uses_sale_receipt(self):
        result = CheckoutHandler.checkout(self.handler)
        response = SimpleNamespace(handled=True, success=True, job_id="qa-job")
        with patch("services.network_printer_client.queue_receipt", return_value=response) as queue:
            self.assertTrue(print_receipt(self.page, result["sale_id"]))
        self.assertIn("QA product", "\n".join(queue.call_args.args[1]))
        self.warning.assert_not_called()

    def test_refund_permission_denial_keeps_stock(self):
        receipt = SimpleNamespace(user_id=99, get_lang=lambda: "en")
        with patch("ui.receipts_page.receipts_tab.PermissionManager.user_has_permission", return_value=False):
            ReceiptsTab.refund_sale(receipt, -1)
        self.warning.assert_called_once()
        self.question.assert_not_called()
        self.assertEqual(self.stock(), 17)

    def test_scanner_submission_clears_input_and_stops_search_timer(self):
        field = QLineEdit()
        timer = QTimer()
        timer.start(1000)
        signal = Mock()
        grid = SimpleNamespace(search_input=field, _search_filter_timer=timer, barcode_scanned=signal)
        field.setText("  000123456789  ")
        ProductGrid.scan_barcode(grid)
        signal.emit.assert_called_once_with("000123456789")
        self.assertEqual(field.text(), "")
        self.assertFalse(timer.isActive())
        ProductGrid.scan_barcode(grid)
        signal.emit.assert_called_once()
