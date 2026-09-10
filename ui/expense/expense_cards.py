# ui/expense/expense_cards.py
from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from utils.currency import format_money
from models.database import connect_db
from PyQt6.QtCore import QDate
from ui.design_system.metrics import CARD_HEIGHT, CARD_PADDING, GAP


class ExpenseCards(QWidget):
    """Card widgets for expense totals"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        card_layout = QHBoxLayout()
        card_layout.setSpacing(GAP)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        self.total_card, self.total_title_label, self.total_amount_label = self._create_card("Total Expenses")
        self.month_card, self.month_title_label, self.month_amount_label = self._create_card("This Month")
        self.today_card, self.today_title_label, self.today_amount_label = self._create_card("Today")
        
        card_layout.addWidget(self.total_card, 1)
        card_layout.addWidget(self.month_card, 1)
        card_layout.addWidget(self.today_card, 1)
        
        self.setLayout(card_layout)
    
    def _create_card(self, title):
        card = QFrame()
        card.setObjectName("dashboardCard")
        card.setMinimumHeight(CARD_HEIGHT)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*([CARD_PADDING] * 4))
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label = QLabel("0")
        value_label.setObjectName("cardValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, title_label, value_label
    
    def update_totals(self):
        conn = connect_db()
        cursor = conn.cursor()
        symbol = self._get_currency_symbol()
        
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
        total_all = cursor.fetchone()[0]
        self.total_amount_label.setText(format_money(total_all, symbol))
        
        today = QDate.currentDate()
        month_start = QDate(today.year(), today.month(), 1)
        month_start_str = month_start.toString("yyyy-MM-dd")
        month_end_str = today.toString("yyyy-MM-dd")
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date BETWEEN ? AND ?", 
                      (month_start_str, month_end_str))
        total_month = cursor.fetchone()[0]
        self.month_amount_label.setText(format_money(total_month, symbol))
        
        today_str = today.toString("yyyy-MM-dd")
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date = ?", (today_str,))
        total_today = cursor.fetchone()[0]
        self.today_amount_label.setText(format_money(total_today, symbol))
        
        conn.close()
    
    def _get_currency_symbol(self):
        from utils.currency import get_currency_symbol
        return get_currency_symbol()
    
    def retranslateUi(self, lang_code):
        if lang_code == "my":
            self.total_title_label.setText("စုစုပေါင်းအသုံးစရိတ်")
            self.month_title_label.setText("ယခုလအတွင်း")
            self.today_title_label.setText("ယနေ့")
        else:
            self.total_title_label.setText("Total Expenses")
            self.month_title_label.setText("This Month")
            self.today_title_label.setText("Today")
    
    def apply_style(self, theme):
        for widget in [
            self.total_card, self.month_card, self.today_card,
            self.total_title_label, self.month_title_label, self.today_title_label,
            self.total_amount_label, self.month_amount_label, self.today_amount_label,
        ]:
            widget.setStyleSheet("")
