# ui/sales_summary/category_groups_tab.py
"""
Sales Summary by Category Group
Shows sales grouped by category groups (from category_groups table)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from models.database import connect_db
from utils.currency import format_money, get_currency_symbol
from ui.widgets.search_widget import ModernSearchWidget


class CategoryGroupsTab(QWidget):
    """Sales summary by category group (from category_groups table)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.full_data = []
        
        layout = QVBoxLayout()
        
        # ✅ Search bar - ModernSearchWidget
        search_layout = QHBoxLayout()
        self.search_widget = ModernSearchWidget("Search category group name...")
        self.search_widget.search_changed.connect(self.filter_table)
        search_layout.addWidget(self.search_widget)
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)  # 8 columns
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table)
        
        self.setLayout(layout)
    
    def filter_table(self, text=None):
        """Filter table based on search text"""
        if text is None:
            text = self.search_widget.get_text()
        
        search_text = text.lower().strip()
        
        if not search_text:
            self._display_data(self.full_data)
            return
        
        filtered = [row for row in self.full_data if search_text in row[0].lower()]
        self._display_data(filtered)
    
    def _display_data(self, rows):
        symbol = get_currency_symbol()
        lang_code = self.parent_page.get_lang() if self.parent_page else "en"
        
        # Calculate max net sales for progress bar scaling
        max_sales = max([row[3] for row in rows]) if rows else 0
        
        self.table.setRowCount(0)
        for row_data in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            group_name = row_data[0] if row_data[0] else "Uncategorized"
            items_sold = row_data[1]
            gross_sales = row_data[2]
            net_sales = row_data[3]
            discount = row_data[4]
            cogs = row_data[5]
            profit = net_sales - cogs
            
            # Calculate percentage for progress bar (relative to max)
            percentage = (net_sales / max_sales * 100) if max_sales > 0 else 0
            
            # Category Group Name
            self.table.setItem(r, 0, QTableWidgetItem(group_name))
            
            # Items Sold
            items_item = QTableWidgetItem(str(items_sold))
            items_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 1, items_item)
            
            # Gross Sales
            gross_item = QTableWidgetItem(format_money(gross_sales, symbol))
            gross_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if gross_sales > 0:
                gross_item.setForeground(QColor(52, 152, 219))
            self.table.setItem(r, 2, gross_item)
            
            # Net Sales
            sales_item = QTableWidgetItem(format_money(net_sales, symbol))
            sales_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if net_sales > 0:
                sales_item.setForeground(QColor(46, 204, 113))
            self.table.setItem(r, 3, sales_item)
            
            # Discount
            discount_item = QTableWidgetItem(format_money(discount, symbol))
            discount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if discount > 0:
                discount_item.setForeground(QColor(231, 76, 60))
            else:
                discount_item.setForeground(QColor(149, 165, 166))
            self.table.setItem(r, 4, discount_item)
            
            # Cost of Goods
            cogs_item = QTableWidgetItem(format_money(cogs, symbol))
            cogs_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if cogs > 0:
                cogs_item.setForeground(QColor(231, 76, 60))
            self.table.setItem(r, 5, cogs_item)
            
            # Gross Profit
            profit_item = QTableWidgetItem(format_money(profit, symbol))
            profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if profit > 0:
                profit_item.setForeground(QColor(46, 204, 113))
            elif profit < 0:
                profit_item.setForeground(QColor(231, 76, 60))
            self.table.setItem(r, 6, profit_item)
            
            # Progress Bar
            progress_widget = QWidget()
            progress_layout = QHBoxLayout(progress_widget)
            progress_layout.setContentsMargins(5, 2, 5, 2)
            progress_layout.setSpacing(0)
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(int(percentage))
            progress_bar.setFormat("")
            progress_bar.setTextVisible(False)
            
            # Color based on percentage
            if percentage >= 80:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #e74c3c;
                        border-radius: 3px;
                    }
                """)
            elif percentage >= 50:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #f39c12;
                        border-radius: 3px;
                    }
                """)
            else:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #2ecc71;
                        border-radius: 3px;
                    }
                """)
            
            progress_layout.addWidget(progress_bar)
            self.table.setCellWidget(r, 7, progress_widget)
            
            # Set row height
            self.table.setRowHeight(r, 50)
        
        # Set headers based on language
        if lang_code == "my":
            self.table.setHorizontalHeaderLabels([
                "အုပ်စု", "ရောင်းရသည့်အရေအတွက်",
                "စုစုပေါင်းရောင်းအား (အကြမ်း)", "အသားတင်ရောင်းအား",
                "လျှော့စျေး", "ကုန်ကျစရိတ်",
                "အသားတင်အမြတ်", "တိုးတက်မှု"
            ])
        else:
            self.table.setHorizontalHeaderLabels([
                "Category Group", "Items Sold", "Gross Sales", "Net Sales",
                "Discount", "Cost of Goods", "Gross Profit", "Progress"
            ])
    
    def load(self, from_date, to_date):
        """
        Load sales data grouped by category group.
        Shows data from category_groups table.
        """
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(cg.name, 'Uncategorized') as group_name,
                COALESCE(SUM(si.qty), 0) as items_sold,
                COALESCE(SUM(si.price * si.qty), 0) as gross_sales,
                COALESCE(SUM(si.total) - SUM(s.discount_amount), 0) as net_sales,
                COALESCE(SUM(s.discount_amount), 0) as total_discount,
                COALESCE(SUM(p.cost * si.qty), 0) as cogs
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_name = p.name
            LEFT JOIN categories c ON p.category = c.name
            LEFT JOIN category_groups cg ON c.group_id = cg.id
            WHERE s.status = 'completed' 
              AND date(s.created_at) BETWEEN ? AND ?
            GROUP BY cg.id, cg.name
            ORDER BY net_sales DESC
        """, (from_date, to_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        self.full_data = [list(row) for row in rows]
        
        if self.search_widget.get_text().strip():
            self.filter_table()
        else:
            self._display_data(self.full_data)
    
    def retranslateUi(self):
        """Retranslate UI"""
        lang_code = self.parent_page.get_lang() if self.parent_page else "en"
        
        if hasattr(self.search_widget, 'retranslateUi'):
            self.search_widget.retranslateUi(lang_code)
        
        if hasattr(self.search_widget, 'set_placeholder_text'):
            if lang_code == "my":
                self.search_widget.set_placeholder_text("အုပ်စုအမည် ရှာရန်...")
            else:
                self.search_widget.set_placeholder_text("Search category group name...")
        
        # Refresh display with new headers
        if self.search_widget.get_text().strip():
            self.filter_table()
        else:
            self._display_data(self.full_data)


# ✅ EXPORT
__all__ = ['CategoryGroupsTab']