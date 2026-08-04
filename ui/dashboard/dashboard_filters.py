# ui/dashboard/dashboard_filters.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QDateEdit
from PyQt6.QtCore import QDate, pyqtSignal
from models.database import connect_db
from utils.currency import get_currency_symbol


class DashboardFilters(QWidget):
    filter_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Quick date buttons
        self.btn_today = QPushButton("Today")
        self.btn_this_week = QPushButton("This Week")
        self.btn_this_month = QPushButton("This Month")
        self.btn_last_month = QPushButton("Last Month")
        self.btn_this_year = QPushButton("This Year")
        
        self.btn_today.clicked.connect(lambda: self.set_date_range("today"))
        self.btn_this_week.clicked.connect(lambda: self.set_date_range("week"))
        self.btn_this_month.clicked.connect(lambda: self.set_date_range("month"))
        self.btn_last_month.clicked.connect(lambda: self.set_date_range("last_month"))
        self.btn_this_year.clicked.connect(lambda: self.set_date_range("year"))
        
        layout.addWidget(self.btn_today)
        layout.addWidget(self.btn_this_week)
        layout.addWidget(self.btn_this_month)
        layout.addWidget(self.btn_last_month)
        layout.addWidget(self.btn_this_year)
        layout.addStretch()
        
        # Date pickers
        self.from_label = QLabel("From:")
        self.from_label.setVisible(False)
        layout.addWidget(self.from_label)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-30))
        self.from_date.dateChanged.connect(self.filter_changed.emit)
        layout.addWidget(self.from_date)
        
        self.to_label = QLabel("To:")
        self.to_label.setVisible(False)
        layout.addWidget(self.to_label)
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.dateChanged.connect(self.filter_changed.emit)
        layout.addWidget(self.to_date)
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.filter_changed.emit)
        layout.addWidget(self.btn_refresh)
        
        # Export buttons
        self.btn_export_summary = QPushButton("📊 Export Summary")
        self.btn_export_table = QPushButton("📋 Export Table")
        layout.addWidget(self.btn_export_summary)
        layout.addWidget(self.btn_export_table)
        
        self.setLayout(layout)
    
    def get_currency_symbol(self):
        """Get current currency symbol"""
        return get_currency_symbol()
    
    def get_lang(self):
        """Get current language from database"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    def set_date_range(self, range_type):
        today = QDate.currentDate()
        
        if range_type == "today":
            self.from_date.setDate(today)
            self.to_date.setDate(today)
        elif range_type == "week":
            start = today.addDays(-(today.dayOfWeek() - 1))
            end = start.addDays(6)
            self.from_date.setDate(start)
            self.to_date.setDate(end)
        elif range_type == "month":
            start = QDate(today.year(), today.month(), 1)
            self.from_date.setDate(start)
            self.to_date.setDate(today)
        elif range_type == "last_month":
            first_day_this = QDate(today.year(), today.month(), 1)
            last_day_last = first_day_this.addDays(-1)
            first_day_last = QDate(last_day_last.year(), last_day_last.month(), 1)
            self.from_date.setDate(first_day_last)
            self.to_date.setDate(last_day_last)
        elif range_type == "year":
            start = QDate(today.year(), 1, 1)
            self.from_date.setDate(start)
            self.to_date.setDate(today)
        
        self.filter_changed.emit()
    
    def get_date_range(self):
        return (
            self.from_date.date().toString("yyyy-MM-dd"),
            self.to_date.date().toString("yyyy-MM-dd")
        )
    
    def retranslateUi(self, lang_code):
        if lang_code == "my":
            self.btn_today.setText("ယနေ့")
            self.btn_this_week.setText("ဤတစ်ပတ်")
            self.btn_this_month.setText("ဤလ")
            self.btn_last_month.setText("ပြီးခဲ့သည့်လ")
            self.btn_this_year.setText("ဤနှစ်")
            self.from_label.setText("မှ:")
            self.to_label.setText("အထိ:")
            self.btn_refresh.setText("ပြန်လည်")
            self.btn_export_summary.setText("📊 အကျဉ်းချုပ်ထုတ်မည်")
            self.btn_export_table.setText("📋 ဇယားထုတ်မည်")
        else:
            self.btn_today.setText("Today")
            self.btn_this_week.setText("This Week")
            self.btn_this_month.setText("This Month")
            self.btn_last_month.setText("Last Month")
            self.btn_this_year.setText("This Year")
            self.from_label.setText("From:")
            self.to_label.setText("To:")
            self.btn_refresh.setText("Refresh")
            self.btn_export_summary.setText("📊 Export Summary")
            self.btn_export_table.setText("📋 Export Table")
