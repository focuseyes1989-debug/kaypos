import os
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class ReceiptExportSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_receipt_export_queries_return_lists(self):
        from ui.receipts_page.credit_tab import CreditTab
        from ui.receipts_page.discount_tab import DiscountTab
        from ui.receipts_page.refund_tab import RefundTab

        for tab_class in (RefundTab, DiscountTab, CreditTab):
            tab = tab_class()
            self.assertIsInstance(tab._get_export_rows(), list)

    def test_credit_status_display_marks_overdue(self):
        from PyQt6.QtCore import QDate
        from ui.receipts_page.credit_tab import CreditTab

        tab = CreditTab()
        yesterday = QDate.currentDate().addDays(-1).toString("yyyy-MM-dd")
        self.assertEqual(tab._display_status("pending", 1, yesterday), "Overdue")
        self.assertEqual(tab._display_status("paid", 0, yesterday), "Paid")


if __name__ == "__main__":
    unittest.main()
