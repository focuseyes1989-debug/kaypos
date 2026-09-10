import os
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton
from ui.sales_page.grid_view import GridViewWidget
from ui.sales_page.cart_widget import CartWidget
from ui.themes.theme_manager import get_current_theme, set_current_theme


class SalesTouchStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_grid_keeps_price_and_category_visible_and_adds_columns(self):
        self.addCleanup(set_current_theme, get_current_theme())
        thumbnail = QPixmap(120, 80)
        thumbnail.fill(QColor("#358a75"))
        rows = [(i, "A long product name for testing", 9999999, 17, 2, "Each", "", False, "General") for i in range(12)]
        for theme in ("Light", "Dark"):
            set_current_theme(theme)
            grid = GridViewWidget(card_style="modern")
            with patch("ui.sales_page.grid_view.load_thumbnail", return_value=thumbnail):
                grid.resize(520, 500)
                grid.show()
                self.app.processEvents()
                grid.populate(rows)
                self.app.processEvents()
                small_columns = grid._cols
                for card in grid._cards:
                    card.ensurePolished()
                    card.layout().activate()
                    self.assertTrue(card.rect().contains(card.price_label.geometry()))
                    self.assertTrue(card.rect().contains(card.category_label.geometry()))
                    self.assertGreater(card.name_label.y(), card.image_frame.geometry().bottom())
                    self.assertGreaterEqual(card.price_label.width(), card.price_label.fontMetrics().horizontalAdvance(card.price_label.text()))
                card = grid._cards[0]
                selected = QSignalSpy(card.clicked)
                QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
                self.assertEqual(len(selected), 1)
                favourites = QSignalSpy(grid.favourite_toggled)
                QTest.mouseClick(card.fav_label, Qt.MouseButton.LeftButton)
                self.assertEqual(len(favourites), 1)
                grid.resize(1000, 500)
                grid.populate(rows)
                self.app.processEvents()
                self.assertGreater(grid._cols, small_columns)
                output = os.environ.get("DESKTOP_QA_OUTPUT")
                if output:
                    grid.grab().save(str(Path(output) / f"sales-grid-{theme}.png"))
            grid._resize_timer.stop()
            grid.close()

    def test_cart_populated_and_empty_keep_controls(self):
        with patch("ui.sales_page.cart_widget.save_cart_to_file"), patch.object(CartWidget, "_image_for_product", return_value=""):
            cart = CartWidget()
            cart.resize(440, 500)
            cart.show()
            cart.cart = [dict(id=1, name="Example product", price=1000, qty=2, stock=17)]
            cart.refresh_table()
            self.app.processEvents()
            self.assertEqual(cart.count_badge.text(), "2")
            self.assertEqual(len(cart._item_widgets), 1)
            self.assertTrue(cart.clear_btn.isVisible())
            self.assertFalse(cart.clear_btn.icon().isNull())
            cart.cart = []
            cart.refresh_table()
            self.app.processEvents()
            self.assertTrue(cart.empty_widget.isVisible())
            self.assertFalse(cart.empty_action_btn.isVisible())
            cart.close()

    @unittest.skipUnless(os.environ.get("KAY_DESKTOP_QA_ISOLATED") == "1", "Use isolated runner")
    def test_checkout_dialog_cancel_confirm_and_explicit_print(self):
        from ui.sales_page.sales_page import SalesPage
        with patch("ui.sales_page.sales_page.load_cart_from_file", return_value=[]), patch("ui.sales_page.cart_widget.save_cart_to_file"):
            page = SalesPage({"id": 1, "role": "admin"})
            page._initial_load_steps = []
            page.resize(1100, 580)
            page.show()
            self.app.processEvents()
            self.assertFalse(page.cart_checkout.isEnabled())
            self.assertFalse(page.payment_widget.isVisible())
            self.assertLessEqual(page.cart_actions_footer.height(), 128)
            page.cart_widget.cart = [dict(id=1, name="Test service", price=1000, qty=2, is_service=True)]
            page.cart_widget.refresh_table()
            self.assertTrue(page.cart_checkout.isEnabled())
            page.payment_widget.load_payment_types(["Cash", "Card"])
            page.payment_widget.set_payment_amount(2000)
            core = Mock(return_value={"sale_id": 123})
            page.checkout_handler.checkout = core

            def cancel(dialog):
                dialog.show()
                self.app.processEvents()
                self.assertTrue(page.payment_widget.isVisible())
                page.payment_widget.payment_input.setValue(3000)
                self.app.processEvents()
                self.assertGreaterEqual(page.payment_widget.change_label.width(), page.payment_widget.change_label.sizeHint().width())
                output = os.environ.get("DESKTOP_QA_OUTPUT")
                if output:
                    dialog.grab().save(str(Path(output) / "sales-checkout.png"))
                dialog.reject()
                return QDialog.DialogCode.Rejected

            with patch.object(QDialog, "exec", cancel):
                page.request_checkout()
            core.assert_not_called()
            self.assertEqual(page.payment_widget.get_payment_amount(), 2000)
            self.assertEqual(len(page.cart_widget.get_cart()), 1)
            self.assertFalse(page.checkout_controls.isVisible())

            def failed(dialog):
                core.return_value = None
                page.confirm_checkout()
                self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
                self.assertTrue(page.checkout_handler.btn_checkout.isEnabled())
                dialog.reject()
                return dialog.result()

            with patch.object(QDialog, "exec", failed):
                page.request_checkout()
            self.assertEqual(len(page.cart_widget.get_cart()), 1)
            core.reset_mock()
            core.return_value = {"sale_id": 123}

            def confirm(dialog):
                page.payment_widget.payment_input.setValue(3000)
                page.confirm_checkout()
                self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
                return dialog.result()

            with patch.object(QDialog, "exec", confirm):
                page.request_checkout()
            core.assert_called_once()
            self.assertEqual(page.payment_widget.get_payment_amount(), 3000)
            with patch("ui.sales_page.checkout_handler.checkout_utils.print_receipt", return_value=True) as printer:
                def complete(dialog):
                    dialog.show()
                    self.app.processEvents()
                    printer.assert_not_called()
                    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Receipt Print")
                    button.click()
                    printer.assert_called_once_with(page, 123)
                    self.assertFalse(button.isEnabled())
                    output = os.environ.get("DESKTOP_QA_OUTPUT")
                    if output:
                        dialog.grab().save(str(Path(output) / "sales-complete.png"))
                    dialog.accept()
                    return dialog.result()
                with patch.object(QDialog, "exec", complete):
                    page.show_sale_completion(123, "QA-123", 2000, 3000, 1000)
            with patch("ui.sales_page.checkout_handler.checkout_utils.print_receipt", side_effect=[False, True]) as printer:
                def retry(dialog):
                    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Receipt Print")
                    button.click()
                    self.assertTrue(button.isEnabled())
                    button.click()
                    self.assertFalse(button.isEnabled())
                    self.assertEqual(printer.call_count, 2)
                    dialog.accept()
                    return dialog.result()
                with patch.object(QDialog, "exec", retry):
                    page.show_sale_completion(123, "QA-123", 2000, 3000, 1000)
            page.hide()
            page.deleteLater()
