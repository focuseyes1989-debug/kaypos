import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication
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
