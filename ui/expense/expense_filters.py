# ui/expense/expense_filters.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QDateEdit, QPushButton
from PyQt6.QtCore import QDate, pyqtSignal
from models.database import connect_db
from ui.widgets.combo_box_widget import ComboBoxWidget


class ExpenseFilters(QWidget):
    """Filter widgets for expense page"""
    
    filter_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by description or reference...")
        self.search_input.textChanged.connect(self.filter_changed.emit)
        layout.addWidget(self.search_input, 2)
        
        self.category_filter = ComboBoxWidget("All Categories")
        self.category_filter.addItem("All Categories")
        self.category_filter.currentTextChanged.connect(self.filter_changed.emit)
        layout.addWidget(QLabel("Category:"))
        layout.addWidget(self.category_filter, 1)
        
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-30))
        self.from_date.dateChanged.connect(self.filter_changed.emit)
        layout.addWidget(QLabel("From:"))
        layout.addWidget(self.from_date, 1)
        
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.dateChanged.connect(self.filter_changed.emit)
        layout.addWidget(QLabel("To:"))
        layout.addWidget(self.to_date, 1)
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.filter_changed.emit)
        layout.addWidget(self.btn_refresh)
        
        self.setLayout(layout)
    
    def load_categories(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM expense_categories ORDER BY name")
        rows = cursor.fetchall()
        self.category_filter.blockSignals(True)
        current = self.category_filter.currentText()
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        for (name,) in rows:
            self.category_filter.addItem(name)
        idx = self.category_filter.findText(current)
        if idx >= 0:
            self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)
        conn.close()
    
    def get_search_text(self):
        return self.search_input.text().strip().lower()
    
    def get_category(self):
        return self.category_filter.currentText()
    
    def get_date_range(self):
        return (
            self.from_date.date().toString("yyyy-MM-dd"),
            self.to_date.date().toString("yyyy-MM-dd")
        )
    
    def retranslateUi(self, lang_code):
        if lang_code == "my":
            self.search_input.setPlaceholderText("ဖော်ပြချက် သို့မဟုတ် ကိုးကားအမှတ်ဖြင့် ရှာရန်...")
            self.btn_refresh.setText("ပြန်လည်")
        else:
            self.search_input.setPlaceholderText("Search by description or reference...")
            self.btn_refresh.setText("Refresh")
