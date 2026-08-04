# ui/sales_summary/payment_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar, QFrame,
    QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from models.database import connect_db
from utils.currency import format_money, get_currency_symbol


class PaymentTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.full_data = []
        
        layout = QVBoxLayout()
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table)
        
        self.setLayout(layout)
    
    def _get_theme_colors(self):
        """Get theme-aware colors for text"""
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            theme = row[0] if row else "Light"
        except:
            theme = "Light"
        
        if theme.lower() in ["dark", "ubuntu dark", "pyqt6 dark"]:
            return {
                'text_color': '#ffffff',
                'total_color': '#ffffff',
                'progress_bar_color': '#3498db'
            }
        else:
            return {
                'text_color': '#212529',
                'total_color': '#212529',
                'progress_bar_color': '#3498db'
            }
    
    def _get_lang(self):
        """Get current language"""
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    # ============================================================
    # ✅ FIXED: load() - Using Net Sales (after discount)
    # ============================================================
    def load(self, from_date, to_date, lang_code):
        symbol = get_currency_symbol()
        conn = connect_db()
        cursor = conn.cursor()
        
        # ✅ FIXED: Get Net Sales = Gross Sales - Discount
        cursor.execute("""
            SELECT 
                COALESCE(s.payment_type, 'Other') as payment_type,
                COUNT(DISTINCT s.id) as transaction_count,
                COALESCE(SUM(si.qty * si.price) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'completed' 
              AND date(s.created_at) BETWEEN ? AND ?
            GROUP BY s.payment_type
            ORDER BY net_sales DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        
        self.full_data = [list(row) for row in rows]
        self._display_data(lang_code)
    
    def _display_data(self, lang_code):
        symbol = get_currency_symbol()
        theme_colors = self._get_theme_colors()
        
        # Calculate max amount for progress bar scaling
        max_amount = max([row[2] for row in self.full_data]) if self.full_data else 0
        
        self.table.setRowCount(0)
        total_count = 0
        total_amount = 0.0
        
        for row_data in self.full_data:
            ptype, count, amount = row_data
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # Calculate percentage for progress bar (relative to max)
            percentage = (amount / max_amount * 100) if max_amount > 0 else 0
            
            # Payment Type
            self.table.setItem(r, 0, QTableWidgetItem(ptype))
            
            # Transaction Count
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 1, count_item)
            
            # Amount - Net Sales
            amount_item = QTableWidgetItem(format_money(amount, symbol))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if amount > 0:
                amount_item.setForeground(QColor(46, 204, 113))
            self.table.setItem(r, 2, amount_item)
            
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
            self.table.setCellWidget(r, 3, progress_widget)
            
            # Set row height
            self.table.setRowHeight(r, 50)
            
            total_count += count
            total_amount += amount
        
        # Total row
        r = self.table.rowCount()
        self.table.insertRow(r)
        font = self.table.font()
        font.setBold(True)
        
        # Calculate total percentage for progress bar
        total_percentage = (total_amount / max_amount * 100) if max_amount > 0 else 0
        
        # Total label - theme aware
        total_label = "TOTAL" if lang_code != "my" else "စုစုပေါင်း"
        total_item = QTableWidgetItem(total_label)
        total_item.setFont(font)
        total_item.setForeground(QColor(theme_colors['total_color']))
        self.table.setItem(r, 0, total_item)
        
        # Total count - theme aware
        count_item = QTableWidgetItem(str(total_count))
        count_item.setFont(font)
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        count_item.setForeground(QColor(theme_colors['total_color']))
        self.table.setItem(r, 1, count_item)
        
        # Total amount - theme aware
        amount_item = QTableWidgetItem(format_money(total_amount, symbol))
        amount_item.setFont(font)
        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        amount_item.setForeground(QColor(theme_colors['total_color']))
        self.table.setItem(r, 2, amount_item)
        
        # Progress Bar for total (different color - blue)
        progress_widget = QWidget()
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(5, 2, 5, 2)
        progress_layout.setSpacing(0)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(total_percentage))
        progress_bar.setFormat("")
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        
        progress_layout.addWidget(progress_bar)
        self.table.setCellWidget(r, 3, progress_widget)
        self.table.setRowHeight(r, 50)
        
        # Set headers based on language
        if lang_code == "my":
            self.table.setHorizontalHeaderLabels([
                "ငွေပေးချေမှုအမျိုးအစား", "ငွေပေးချေမှုအရေအတွက်", 
                "ငွေပေးချေမှုပမာဏ (အသားတင်)", "တိုးတက်မှု"
            ])
        else:
            self.table.setHorizontalHeaderLabels([
                "Payment Type", "Transaction Count", "Net Amount", "Progress"
            ])
    
    def retranslateUi(self):
        """Retranslate UI"""
        lang_code = self._get_lang()
        self._display_data(lang_code)