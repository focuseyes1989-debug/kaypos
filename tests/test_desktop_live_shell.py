import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox
from models.database import connect_db
from ui.main_window.main_window import MainWindow


@unittest.skipUnless(os.environ.get("KAY_DESKTOP_QA_ISOLATED") == "1", "Use the isolated QA runner")
class LiveShellTests(unittest.TestCase):
    def test_main_window_management_pages(self):
        app = QApplication.instance() or QApplication([])
        conn = connect_db()
        conn.execute("INSERT OR IGNORE INTO users (id, username, password_hash, role) VALUES (1, 'qa-admin', 'not-a-login', 'admin')")
        conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('performance_low_end_mode','1')")
        conn.executemany("INSERT INTO products (name, price, cost, stock, sku) VALUES (?,?,?,?,?)", [
            ("QA product with a long display name", 12500, 8000, 17, "QA-001"),
            ("\u1019\u103c\u1014\u103a\u1019\u102c product", 9999999, 10, 2, "QA-002"),
        ])
        conn.execute("INSERT INTO customers (name, email, phone) VALUES (?,?,?)", ("QA Customer", "long-customer-address@example.test", "090000000"))
        conn.commit()
        conn.close()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok), patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok), patch.object(MainWindow, "_check_dashboard_digests"), patch("ui.sales_page.sales_page.load_cart_from_file", return_value=[]), patch("ui.sales_page.cart_widget.save_cart_to_file"):
            window = MainWindow({"id": 1, "username": "qa-admin", "role": "admin"})
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            try:
                for index in (5, 0, 1, 2, 6, 3, 4, 7, 8, 9, 11):
                    print(f"Rendering page {index}", flush=True)
                    with self.subTest(page=index):
                        window.switch_to_page(index)
                        for _ in range(40):
                            app.processEvents()
                            QTest.qWait(25)
                            if index in window._page_widgets:
                                break
                        self.assertIn(index, window._page_widgets)
                        for width, height in ((1350, 680), (1366, 700), (1920, 1000)):
                            window.resize(width, height)
                            window.show()
                            app.processEvents()
                            self.assertLessEqual(window.width(), width)
                            self.assertLessEqual(window.height(), height)
                            output = os.environ.get("DESKTOP_QA_OUTPUT")
                            if output:
                                window.grab().save(str(Path(output) / f"shell-{index}-{width}.png"))
                if app.platformName() == "windows":
                    window.showMaximized()
                    QTest.qWait(150)
                    available = window.screen().availableGeometry()
                    # Windows keeps invisible resize borders outside a maximized window.
                    self.assertLessEqual(window.geometry().height(), available.height())
                    window.showNormal()
                    QTest.qWait(100)
                    self.assertFalse(window.isMaximized())
            finally:
                for timer in window.findChildren(QTimer):
                    timer.stop()
                window.hide()
                window.deleteLater()
