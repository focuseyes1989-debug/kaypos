import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from ui.sales_page.payment_widget import PaymentWidget


class PaymentLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_maximum_amount_has_room_for_keypad(self):
        widget = PaymentWidget()
        widget.payment_input.setValue(999999999)
        widget.resize(320, 150)
        widget.show()
        self.app.processEvents()
        field = widget.payment_input
        self.assertEqual(field.value(), 999999999)
        self.assertGreaterEqual(
            field.width(), field.fontMetrics().horizontalAdvance(field.text()) + 70
        )
        widget.close()


if __name__ == "__main__":
    unittest.main()
