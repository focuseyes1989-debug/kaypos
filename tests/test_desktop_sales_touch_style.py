import os
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from PyQt6.QtCore import Qt, QObject, QEvent
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QWidget
from ui.sales_page.grid_view import GridViewWidget, ModernProductCard
from ui.sales_page.cart_widget import CartWidget
from ui.themes.theme_manager import get_current_theme, set_current_theme


class SalesTouchStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_product_image_stretches_to_fill_frame(self):
        with patch("ui.sales_page.grid_view.load_thumbnail", return_value=None):
            card = ModernProductCard(1, "Example", 1000, 10, 2, "Each", "")
        for width, height in ((40, 120), (160, 40)):
            source = QPixmap(width, height)
            source.fill(QColor("#358a75"))
            rendered = card._rounded_pixmap(source, 140, 88).toImage()
            for x, y in ((2, 44), (137, 44), (70, 2), (70, 85)):
                self.assertEqual(rendered.pixelColor(x, y), QColor("#358a75"))
            self.assertEqual(rendered.pixelColor(0, 0).alpha(), 0)
        card.deleteLater()

    def test_category_badges_match_touch_palette(self):
        from ui.sales_page.category_colors import category_badge_colors, LIGHT, DARK
        for index, name in enumerate(("f", "a", "b", "c", "d", "e")):
            self.assertEqual(category_badge_colors(name), LIGHT[index])
            self.assertEqual(category_badge_colors(name, True), DARK[index])
        self.assertEqual(category_badge_colors(" Services "), category_badge_colors("services"))
        for dark in (False, True):
            with patch("ui.sales_page.grid_view.load_thumbnail", return_value=None):
                card = ModernProductCard(1, "Example", 1000, 10, 2, "Each", "", category_name="Services", is_dark=dark)
            background, foreground = category_badge_colors("Services", dark)
            self.assertIn(background, card.category_label.styleSheet())
            self.assertIn(foreground, card.category_label.styleSheet())
            card.deleteLater()

    def test_grid_background_shows_parent_surface(self):
        parent = QWidget()
        parent.setStyleSheet("background-color: #d8eedb;")
        parent.resize(500, 350)
        grid = GridViewWidget(parent, card_style="modern")
        grid.setGeometry(10, 10, 480, 330)
        parent.show()
        self.app.processEvents()
        self.assertFalse(grid.viewport().autoFillBackground())
        self.assertFalse(grid._container.autoFillBackground())
        rendered = parent.grab().toImage()
        self.assertEqual(rendered.pixelColor(240, 250), QColor("#d8eedb"))
        grid._resize_timer.stop()
        parent.close()
        from PyQt6 import sip
        sip.delete(parent)

    def test_service_keypad_input_and_blur_cleanup(self):
        from ui.sales_page.service_price_dialog import ServicePriceDialog
        from PyQt6.QtWidgets import QGraphicsBlurEffect
        parent = QWidget()
        parent.resize(900, 650)
        parent.show()
        self.app.processEvents()
        dialog = ServicePriceDialog("Car Border Pass", parent)
        for accepted in (False, True):
            def inspect(widget):
                widget.show()
                self.app.processEvents()
                from PyQt6.QtWidgets import QLabel
                self.assertFalse(any(label.text() in ("Enter service price", "Price") for label in widget.findChildren(QLabel)))
                for key in widget.findChildren(QPushButton):
                    if key.text().isdigit():
                        self.assertEqual(key.height(), 52)
                effects = parent.findChildren(QGraphicsBlurEffect)
                self.assertTrue(any(effect.parent().isVisible() for effect in effects))
                widget._handle_key("C")
                for key in ("1", "2", ".", "5"):
                    widget._handle_key(key)
                self.assertEqual(widget.value(), 12.5)
                for button in widget.findChildren(QPushButton):
                    self.assertTrue(widget.rect().contains(button.geometry()))
                output = os.environ.get("DESKTOP_QA_OUTPUT")
                if output:
                    widget.grab().save(str(Path(output) / "service-keypad.png"))
                widget.accept() if accepted else widget.reject()
                return widget.result()
            with patch.object(QDialog, "exec", inspect):
                self.assertEqual(dialog.exec(), QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected)
            self.assertFalse(any(effect.parent().isVisible() for effect in parent.findChildren(QGraphicsBlurEffect)))
        dialog.deleteLater()
        parent.close()
        parent.deleteLater()

    def test_product_name_is_one_line_with_full_tooltip(self):
        for name in ("Tea", "A very long product name that cannot fit in a single card"):
            with patch("ui.sales_page.grid_view.load_thumbnail", return_value=None):
                card = ModernProductCard(1, name, 1000, 10, 2, "Each", "", card_width=156, card_height=212)
            card.show()
            self.app.processEvents()
            label = card.name_label
            self.assertFalse(label.wordWrap())
            self.assertEqual(label.toolTip(), name)
            self.assertLessEqual(label.fontMetrics().horizontalAdvance(label.text()), label.contentsRect().width())
            if name == "Tea":
                self.assertEqual(label.text(), name)
            else:
                self.assertTrue(label.text().endswith("..."))
            card.close()
            card.deleteLater()

    def test_grid_loading_never_shows_a_separate_window(self):
        shown_windows = []

        class ShowObserver(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
                    shown_windows.append(type(obj).__name__)
                return False

        grid = GridViewWidget(card_style="modern")
        grid.resize(520, 500)
        grid.show()
        self.app.processEvents()
        observer = ShowObserver()
        self.app.installEventFilter(observer)
        try:
            rows = [(1, "Example", 1000, 7, 2, "Each", "", False, "General")]
            with patch("ui.sales_page.grid_view.load_thumbnail", return_value=None):
                grid.populate(rows)
                grid.append_rows([(2, "Second", 2000, 2, 1, "Each", "", False, "General")])
                self.app.processEvents()
            self.assertEqual(shown_windows, [])
        finally:
            self.app.removeEventFilter(observer)
            grid._resize_timer.stop()
            grid.close()
            grid.deleteLater()

    def test_responsive_grid_fits_five_cards_and_uses_available_width(self):
        grid = GridViewWidget(card_style="modern")
        rows = [(i, "Example product", 32000, 7, 2, "Each", "", False, "General") for i in range(30)]
        try:
            with patch("ui.sales_page.grid_view.load_thumbnail", return_value=None):
                for width in (740, 1000, 520, 1600, 740):
                    grid.resize(width, 500)
                    grid.show()
                    self.app.processEvents()
                    grid.populate(rows)
                    self.app.processEvents()
                    QTest.qWait(200)
                    self.app.processEvents()
                    if width == 740:
                        self.assertEqual(grid._cols, 5)
                    right = grid._cards[grid._cols - 1].geometry().right() + 1
                    self.assertLessEqual(grid.viewport().width() - right, 4 + grid._cols)
                    self.assertGreaterEqual(grid.viewport().width() - right, 0)
                    self.assertEqual(grid.horizontalScrollBar().maximum(), 0)
        finally:
            grid._resize_timer.stop()
            grid.close()
            grid.deleteLater()

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
                self.assertEqual(grid._cards[0].height(), 184)
                first, second = grid._cards[:2]
                self.assertLessEqual(second.x() - first.geometry().right(), 10)
                for card in grid._cards:
                    card.ensurePolished()
                    card.layout().activate()
                    self.assertTrue(card.rect().contains(card.price_label.geometry()))
                    self.assertLessEqual(card.height() - card.price_label.geometry().bottom(), 12)
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
            self.assertGreater(page.product_grid.width(), page.right_container.width())
            self.assertLessEqual(page.right_container.width(), 440)
            self.assertTrue(page.rect().contains(page.right_container.geometry()))
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
                original_style = self.app.styleSheet()
                self.addCleanup(self.app.setStyleSheet, original_style)
                self.app.setStyleSheet(original_style + "\nQPushButton { min-height: 22px; padding: 6px; }")
                dialog.show()
                self.app.processEvents()
                from PyQt6.QtWidgets import QGraphicsBlurEffect
                from PyQt6.QtWidgets import QScrollArea
                self.assertFalse(dialog.findChildren(QScrollArea))
                self.assertLessEqual(dialog.height(), 600)
                self.assertTrue(any(effect.parent().isVisible() for effect in page.findChildren(QGraphicsBlurEffect)))
                for button in dialog.findChildren(QPushButton):
                    if button.text().isdigit():
                        self.assertEqual(button.height(), 72)
                self.assertTrue(page.payment_widget.payment_input.isVisible())
                dialog._key("clear")
                self.assertFalse(dialog.save.isEnabled())
                dialog.exact.click()
                self.assertTrue(dialog.save.isEnabled())
                page.payment_widget.payment_input.selectAll()
                dialog._key("3")
                dialog._key("00")
                dialog._key("0")
                self.assertEqual(page.payment_widget.get_payment_amount(), 3000)
                page.payment_widget.payment_input.setValue(3000)
                self.app.processEvents()
                self.assertIn("1,000", dialog.values["Change"].text())
                page.totals_widget.discount_checkbox.setChecked(True)
                page.totals_widget.discount_input.setValue(10)
                self.assertEqual(page.totals_widget.get_current_grand_total(), 1990)
                self.assertEqual(page.payment_widget.get_payment_amount(), 3000)
                page.totals_widget.discount_input.lineEdit().setFocus()
                self.app.processEvents()
                for key in ("1", "2", ".", "5"):
                    dialog._key(key)
                self.assertEqual(page.totals_widget.discount_input.value(), 12.5)
                self.assertEqual(page.totals_widget.get_current_grand_total(), 1987.5)
                dialog.exact.click()
                self.assertIs(dialog.target, page.payment_widget.payment_input)
                self.assertEqual(page.payment_widget.get_payment_amount(), 1987.5)
                page.payment_widget.payment_input.setValue(3000)
                page.totals_widget.discount_input.setValue(2001)
                self.assertFalse(dialog.save.isEnabled())
                page.totals_widget.discount_input.setValue(10)
                self.app.processEvents()
                field = page.payment_widget.payment_input
                self.assertGreaterEqual(dialog.status.y(), field.geometry().bottom())
                self.assertTrue(dialog.rect().contains(dialog.save.geometry()))
                output = os.environ.get("DESKTOP_QA_OUTPUT")
                if output:
                    dialog.resize(1040, 600)
                    self.app.processEvents()
                    dialog.grab().save(str(Path(output) / "sales-checkout.png"))
                dialog.reject()
                return QDialog.DialogCode.Rejected

            with patch.object(QDialog, "exec", cancel):
                page.request_checkout()
            core.assert_not_called()
            from PyQt6.QtWidgets import QGraphicsBlurEffect
            self.assertFalse(any(effect.parent().isVisible() for effect in page.findChildren(QGraphicsBlurEffect)))
            self.assertEqual(page.payment_widget.get_payment_amount(), 2000)
            self.assertFalse(page.totals_widget.discount_checkbox.isChecked())
            self.assertEqual(page.totals_widget.discount_input.value(), 0)
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
