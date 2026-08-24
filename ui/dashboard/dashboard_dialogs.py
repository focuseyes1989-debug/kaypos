# ui/dashboard/dashboard_dialogs.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.currency import format_money
from ui.receipt_detail_dialog import ReceiptDetailDialog
from ui.themes.theme_manager import get_theme_colors, theme_manager
from ui.design_system.dialog_styles import add_standard_close_footer, modern_table_stylesheet


def _apply_sales_dialog_theme(dialog):
    colors = get_theme_colors()
    dialog.setStyleSheet(f"""
        QDialog {{ background-color: {colors['bg']}; color: {colors['text']}; }}
        QLabel {{ color: {colors['text_secondary']}; background: transparent; font-size: 11px; }}
        QPushButton {{ min-width: 100px; min-height: 36px; padding: 0 18px; border-radius: 8px; }}
    """ + modern_table_stylesheet(colors))


class DiscountedSalesDialog(QDialog):
    def __init__(self, from_date: str, to_date: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Discounted Sales")
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setMinimumSize(700, 500)
        self.setModal(True)
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        info = QLabel(f"Sales with discount from {from_date} to {to_date}")
        layout.addWidget(info)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Invoice No", "Date", "Total", "Discount", "Net Total", "Customer"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self.view_receipt)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.btn_close = add_standard_close_footer(layout, self)
        self.setLayout(layout)
        theme_manager.theme_changed.connect(lambda _name: _apply_sales_dialog_theme(self))
        _apply_sales_dialog_theme(self)
        self.symbol = self.get_currency_symbol()
        self.load_data(from_date, to_date)

    def get_currency_symbol(self):
        from utils.currency import get_currency_symbol
        return get_currency_symbol()

    def load_data(self, from_date, to_date):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.invoice_no, s.created_at, s.total, s.discount_amount,
                   (s.total + s.discount_amount) as subtotal, c.name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.status = 'completed' AND s.discount_amount > 0
              AND date(s.created_at) BETWEEN ? AND ?
            ORDER BY s.created_at DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        self.table.setRowCount(0)
        for row in rows:
            invoice, date, total, discount, subtotal, customer = row
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(invoice))
            self.table.setItem(r, 1, QTableWidgetItem(str(date)))
            self.table.setItem(r, 2, QTableWidgetItem(format_money(total, self.symbol)))
            self.table.setItem(r, 3, QTableWidgetItem(format_money(discount, self.symbol)))
            self.table.setItem(r, 4, QTableWidgetItem(format_money(subtotal, self.symbol)))
            self.table.setItem(r, 5, QTableWidgetItem(customer if customer else "Walk-in"))

    def view_receipt(self, row, column):
        invoice_no = self.table.item(row, 0).text()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sales WHERE invoice_no = ?", (invoice_no,))
        sale_id = cursor.fetchone()
        conn.close()
        if sale_id:
            dialog = ReceiptDetailDialog(sale_id[0], self)
            dialog.exec()


class RefundedSalesDialog(QDialog):
    def __init__(self, from_date: str, to_date: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Refunded Sales")
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setMinimumSize(700, 500)
        self.setModal(True)
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        info = QLabel(f"Refunded sales from {from_date} to {to_date}")
        layout.addWidget(info)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Invoice No", "Date", "Total Refunded", "Customer", "Original Status"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self.view_receipt)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.btn_close = add_standard_close_footer(layout, self)
        self.setLayout(layout)
        theme_manager.theme_changed.connect(lambda _name: _apply_sales_dialog_theme(self))
        _apply_sales_dialog_theme(self)
        self.symbol = self.get_currency_symbol()
        self.load_data(from_date, to_date)

    def get_currency_symbol(self):
        from utils.currency import get_currency_symbol
        return get_currency_symbol()

    def load_data(self, from_date, to_date):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.invoice_no, s.created_at, s.total, c.name, s.status
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.status = 'refunded' AND date(s.created_at) BETWEEN ? AND ?
            ORDER BY s.created_at DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        self.table.setRowCount(0)
        for row in rows:
            invoice, date, total, customer, status = row
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(invoice))
            self.table.setItem(r, 1, QTableWidgetItem(str(date)))
            self.table.setItem(r, 2, QTableWidgetItem(format_money(total, self.symbol)))
            self.table.setItem(r, 3, QTableWidgetItem(customer if customer else "Walk-in"))
            self.table.setItem(r, 4, QTableWidgetItem(status))

    def view_receipt(self, row, column):
        invoice_no = self.table.item(row, 0).text()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sales WHERE invoice_no = ?", (invoice_no,))
        sale_id = cursor.fetchone()
        conn.close()
        if sale_id:
            dialog = ReceiptDetailDialog(sale_id[0], self)
            dialog.exec()
