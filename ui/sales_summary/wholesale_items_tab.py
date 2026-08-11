# ui/sales_summary/wholesale_items_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from models.database import connect_db
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.search_widget import ModernSearchWidget
from utils.currency import format_money, get_currency_symbol
from utils.wholesale_pricing import ensure_wholesale_sale_item_columns


class WholesaleItemsTab(QWidget):
    """Wholesale sales summary tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.full_data = []
        self.filtered_data = []
        self.current_page = 1
        self.page_size = 25

        layout = QVBoxLayout()

        search_layout = QHBoxLayout()
        self.search_widget = ModernSearchWidget("Search wholesale item...")
        self.search_widget.search_changed.connect(self.on_search_changed)
        search_layout.addWidget(self.search_widget)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 8):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(42)
        layout.addWidget(self.table)

        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        self.setLayout(layout)

    def on_search_changed(self, _text):
        self.current_page = 1
        self.filter_data()

    def filter_data(self):
        search_text = self.search_widget.get_text().lower().strip()
        if not search_text:
            self.filtered_data = self.full_data.copy()
        else:
            self.filtered_data = [
                row for row in self.full_data
                if search_text in str(row[0]).lower()
                or search_text in str(row[1]).lower()
                or search_text in str(row[2]).lower()
            ]
        self.pagination.set_total_items(len(self.filtered_data))
        self.display_current_page()

    def display_current_page(self):
        symbol = get_currency_symbol()
        lang_code = self.parent_page.get_lang() if self.parent_page else "en"
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.filtered_data))
        page_data = self.filtered_data[start_idx:end_idx]

        self.table.setRowCount(0)
        for row_data in page_data:
            (
                product_name, category, tier, qty, regular_price,
                wholesale_price, savings, net_sales, transactions
            ) = row_data
            r = self.table.rowCount()
            self.table.insertRow(r)

            self.table.setItem(r, 0, QTableWidgetItem(str(product_name)))
            self.table.setItem(r, 1, QTableWidgetItem(str(category or "Uncategorized")))
            self.table.setItem(r, 2, QTableWidgetItem(str(tier or "-")))

            qty_item = QTableWidgetItem(f"{float(qty or 0):g}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 3, qty_item)

            regular_item = QTableWidgetItem(format_money(regular_price, symbol))
            regular_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r, 4, regular_item)

            wholesale_item = QTableWidgetItem(format_money(wholesale_price, symbol))
            wholesale_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            wholesale_item.setForeground(QColor(52, 152, 219))
            self.table.setItem(r, 5, wholesale_item)

            savings_item = QTableWidgetItem(format_money(savings, symbol))
            savings_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            savings_item.setForeground(QColor(46, 204, 113))
            self.table.setItem(r, 6, savings_item)

            net_item = QTableWidgetItem(format_money(net_sales, symbol))
            net_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r, 7, net_item)

            for col in range(8):
                item = self.table.item(r, col)
                if item:
                    item.setToolTip(f"Transactions: {transactions}")

        if lang_code == "my":
            self.table.setHorizontalHeaderLabels([
                "ပစ္စည်း", "အမျိုးအစား", "Wholesale Tier", "Qty",
                "ပုံမှန်ဈေး", "Wholesale ဈေး", "သက်သာငွေ", "Net Sales"
            ])
        else:
            self.table.setHorizontalHeaderLabels([
                "Item", "Category", "Tier", "Qty",
                "Regular Price", "Wholesale Price", "Saved", "Net Sales"
            ])

    def on_page_changed(self, page, page_size):
        self.current_page = page
        self.page_size = page_size
        self.display_current_page()

    def load(self, from_date, to_date):
        conn = connect_db()
        cursor = conn.cursor()
        ensure_wholesale_sale_item_columns(cursor)
        conn.commit()
        cursor.execute("""
            SELECT
                si.product_name,
                COALESCE(c.name, p.category, 'Uncategorized') as category,
                CASE
                    WHEN COALESCE(si.wholesale_tier_min_qty, 0) > 0
                    THEN CAST(si.wholesale_tier_min_qty AS TEXT) || '+ ' || COALESCE(si.wholesale_unit_label, '')
                    ELSE 'Wholesale'
                END as tier,
                COALESCE(SUM(si.qty), 0) as qty,
                COALESCE(MAX(si.wholesale_regular_price), 0) as regular_price,
                COALESCE(MIN(si.price), 0) as wholesale_price,
                COALESCE(SUM(si.wholesale_savings), 0) as savings,
                COALESCE(SUM(si.total), 0) as net_sales,
                COUNT(DISTINCT si.sale_id) as transactions
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_id = p.id OR (si.product_id IS NULL AND si.product_name = p.name)
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE s.status = 'completed'
              AND date(s.created_at) BETWEEN ? AND ?
              AND COALESCE(si.wholesale_savings, 0) > 0
            GROUP BY
                si.product_name,
                COALESCE(c.name, p.category, 'Uncategorized'),
                CASE
                    WHEN COALESCE(si.wholesale_tier_min_qty, 0) > 0
                    THEN CAST(si.wholesale_tier_min_qty AS TEXT) || '+ ' || COALESCE(si.wholesale_unit_label, '')
                    ELSE 'Wholesale'
                END
            ORDER BY savings DESC, net_sales DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()

        self.full_data = [list(row) for row in rows]
        self.current_page = 1
        self.filter_data()

    def retranslateUi(self):
        lang_code = self.parent_page.get_lang() if self.parent_page else "en"
        self.search_widget.retranslateUi("my" if lang_code == "my" else "en")
        self.display_current_page()
