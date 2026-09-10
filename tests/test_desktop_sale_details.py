import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QWidget, QCheckBox, QDoubleSpinBox, QSpinBox, QLabel, QRadioButton, QDialog, QDialogButtonBox, QScrollArea
from ui.sales_page.sales_page import SalesPage
from ui.restaurant_page import RestaurantPage


class SaleDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_page(self):
        page = QWidget()
        page._details_dialog = None
        page._hide_original_details_widgets = Mock()
        page.update_theme = Mock()
        discount = QDoubleSpinBox()
        discount.setRange(0, 100)
        discount.setValue(5)
        page.totals_widget = SimpleNamespace(
            discount_checkbox=QCheckBox("Discount"), discount_input=discount,
            points_label=QLabel("Points: 10"), points_use_check=QCheckBox("Use points"),
            points_spin=QSpinBox(), subtotal_label=QLabel("Subtotal: 100"),
            tax_label=QLabel("Tax: 0"), total_label=QLabel("Total: 95"), update_totals=Mock(),
        )
        page.totals_widget.discount_checkbox.setChecked(True)
        cash = QRadioButton("Cash")
        cash.setChecked(True)
        page.options_widget = SimpleNamespace(
            cash_radio=cash, credit_radio=QRadioButton("Credit"),
            print_receipt_check=QCheckBox("Print receipt"), open_drawer_check=QCheckBox("Open drawer"),
            set_payment_type=Mock(), get_payment_type=Mock(return_value="Cash"), payment_type_changed=Mock(),
        )
        page.payment_widget = SimpleNamespace(update_change=Mock())
        return page

    def test_accept_and_cancel_on_both_pages(self):
        for page_type in (SalesPage, RestaurantPage):
            for accepted in (False, True):
                with self.subTest(page=page_type.__name__, accepted=accepted):
                    page = self.make_page()

                    def inspect_dialog(dialog):
                        dialog.resize(460, 360)
                        dialog.show()
                        self.app.processEvents()
                        footer = dialog.findChild(QDialogButtonBox)
                        scroll = dialog.findChild(QScrollArea)
                        self.assertTrue(dialog.rect().contains(footer.geometry()))
                        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
                        dialog.findChild(QDoubleSpinBox).setValue(12)
                        dialog.hide()
                        return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected

                    with patch.object(QDialog, "exec", inspect_dialog):
                        page_type.open_sale_details_dialog(page)
                    self.assertEqual(page.totals_widget.discount_input.value(), 12 if accepted else 5)
                    self.assertEqual(page.totals_widget.update_totals.call_count, int(accepted))
                    self.assertIsNone(page._details_dialog)
                    page.close()


if __name__ == "__main__":
    unittest.main()
