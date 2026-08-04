# ui/expense/expense_category_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QProgressBar, QComboBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money

# ✅ Import widgets
from ui.widgets import (
    SearchWidget,
    ToastNotificationWidget,
    LoadingSpinnerWidget,
    SummaryCardWidget
)
from ui.themes.theme_manager import theme_manager, is_dark_theme
import os


class ExpenseCategoryTab(QWidget):
    """Expense by Categories tab showing category-wise breakdown"""
    
    category_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self._from_date = None
        self._to_date = None
        self.setup_ui()
        
        # Connect theme change
        theme_manager.theme_changed.connect(self.on_theme_changed)
        
    def on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._apply_card_style()
        # ✅ Update tab icon
        self._update_tab_icon()
    
    def _update_tab_icon(self):
        """✅ Update tab icon color based on theme"""
        if self.parent_page and hasattr(self.parent_page, 'tab_widget'):
            # Find this tab index
            for idx in range(self.parent_page.tab_widget.count()):
                if self.parent_page.tab_widget.widget(idx) == self:
                    # Load colored icon
                    icon = self._load_colored_tab_icon()
                    self.parent_page.tab_widget.setTabIcon(idx, icon)
                    break
    
    def _load_colored_tab_icon(self):
        """✅ Load SVG icon with color based on theme"""
        is_dark = is_dark_theme()
        color_hex = "#ffffff" if is_dark else "#495057"
        
        # Try SVG first
        paths = [
            "assets/icons/category.svg",
            "assets/icons/category.png",
        ]
        
        for path in paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Color the icon
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        
                        return QIcon(colored)
                except Exception as e:
                    print(f"Could not load icon {path}: {e}")
        
        return QIcon()
    
    def set_date_range(self, from_date, to_date):
        """Set date range from parent page"""
        self._from_date = from_date
        self._to_date = to_date
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # ========== FILTERS ==========
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(0, 8, 0, 8)
        
        # ✅ Use SearchWidget only
        self.search_widget = SearchWidget(
            placeholder="Search category...",
            show_label=True
        )
        self.search_widget.search_changed.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_widget)
        
        filter_layout.addStretch()
        
        # ✅ Show date range info
        self.date_info_label = QLabel("Date: Loading...")
        self.date_info_label.setStyleSheet("color: #6c757d; font-size: 10pt;")
        filter_layout.addWidget(self.date_info_label)
        
        layout.addLayout(filter_layout)
        
        # ========== SUMMARY CARDS (Using SummaryCardWidget with SVG Icons) ==========
        card_layout = QHBoxLayout()
        card_layout.setSpacing(15)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        # Total Expenses Card - Using SVG icon
        self.total_card = SummaryCardWidget(
            title="Total Expenses",
            value="0",
            icon="money",           # SVG file: money.svg
            color="#e74c3c",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.total_card, 1)
        
        # Categories Count Card - Using SVG icon
        self.count_card = SummaryCardWidget(
            title="Categories",
            value="0",
            icon="category",        # SVG file: category.svg
            color="#3498db",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.count_card, 1)
        
        # Top Category Card - Using SVG icon
        self.top_card = SummaryCardWidget(
            title="Top Category",
            value="—",
            icon="trending_up",     # SVG file: trending_up.svg
            color="#f39c12",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.top_card, 1)
        
        # Average Per Category Card - Using SVG icon
        self.avg_card = SummaryCardWidget(
            title="Average",
            value="0",
            icon="bar_chart",       # SVG file: bar_chart.svg
            color="#9b59b6",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.avg_card, 1)
        
        layout.addLayout(card_layout)
        
        # ========== CATEGORY TABLE ==========
        self.setup_table(layout)
        
        # ========== Toast Notification ==========
        self.toast = ToastNotificationWidget(self)
        
        # ========== Loading Spinner ==========
        self.spinner = LoadingSpinnerWidget("Loading categories...")
        self.spinner.hide()
        layout.addWidget(self.spinner)
        
        self.setLayout(layout)
        self.retranslateUi()
        
        # ✅ Apply tab icon
        self._update_tab_icon()
    
    def setup_table(self, layout):
        """Setup the category breakdown table"""
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Category", "Count", "Total Amount", "Average", "Percentage", "Progress"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.on_category_clicked)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table)
    
    def get_date_range(self):
        """Get date range from parent page or default"""
        if self._from_date and self._to_date:
            return self._from_date, self._to_date
        
        # Fallback to last 30 days
        today = QDate.currentDate()
        return today.addDays(-30).toString("yyyy-MM-dd"), today.toString("yyyy-MM-dd")
    
    def on_search_changed(self, text):
        """Handle search text changes"""
        self.load_data()
    
    def load_data(self):
        """Load category data from database"""
        self.spinner.start()
        
        from_date, to_date = self.get_date_range()
        symbol = get_currency_symbol()
        search_text = self.search_widget.get_text().lower().strip()
        
        # Update date info
        lang = self._get_lang()
        if lang == "my":
            self.date_info_label.setText(f"ရက်စွဲ: {from_date} မှ {to_date} ထိ")
        else:
            self.date_info_label.setText(f"Date: {from_date} to {to_date}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # Get category breakdown
        cursor.execute("""
            SELECT 
                category,
                COUNT(*) as count,
                COALESCE(SUM(amount), 0) as total,
                COALESCE(AVG(amount), 0) as average,
                COALESCE(MIN(amount), 0) as min_amount,
                COALESCE(MAX(amount), 0) as max_amount
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        
        # Get grand total
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM expenses 
            WHERE expense_date BETWEEN ? AND ?
        """, (from_date, to_date))
        grand_total = cursor.fetchone()[0]
        conn.close()
        
        # Filter by search text
        if search_text:
            rows = [row for row in rows if search_text in (row[0] or "").lower()]
        
        # Update summary cards
        total_categories = len(rows)
        self.count_card.set_value(str(total_categories))
        self.total_card.set_value(format_money(grand_total, symbol))
        
        if total_categories > 0:
            top_category = rows[0][0] if rows[0][0] else "Uncategorized"
            self.top_card.set_value(top_category)
            avg_per_category = grand_total / total_categories
            self.avg_card.set_value(format_money(avg_per_category, symbol))
        else:
            self.top_card.set_value("—")
            self.avg_card.set_value("0")
        
        # Populate table
        self.table.setRowCount(0)
        
        for row_idx, row_data in enumerate(rows):
            category, count, total, avg, min_amt, max_amt = row_data
            percentage = (total / grand_total * 100) if grand_total > 0 else 0
            
            self.table.insertRow(row_idx)
            
            # Category
            self.table.setItem(row_idx, 0, QTableWidgetItem(category if category else "Uncategorized"))
            
            # Count
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 1, count_item)
            
            # Total Amount
            total_item = QTableWidgetItem(format_money(total, symbol))
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if total > 0:
                total_item.setForeground(QColor(46, 204, 113))
            self.table.setItem(row_idx, 2, total_item)
            
            # Average
            avg_item = QTableWidgetItem(format_money(avg, symbol))
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 3, avg_item)
            
            # Percentage
            percent_item = QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if percentage >= 50:
                percent_item.setForeground(QColor(231, 76, 60))
            elif percentage >= 20:
                percent_item.setForeground(QColor(241, 196, 15))
            else:
                percent_item.setForeground(QColor(46, 204, 113))
            self.table.setItem(row_idx, 4, percent_item)
            
            # Progress Bar (as a QWidget)
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
            if percentage >= 50:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #e74c3c;
                        border-radius: 3px;
                    }
                """)
            elif percentage >= 20:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #f1c40f;
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
            self.table.setCellWidget(row_idx, 5, progress_widget)
            
            # Set row height
            self.table.setRowHeight(row_idx, 50)
        
        self.spinner.stop()
    
    def on_category_clicked(self, row, col):
        """Handle category selection - emit signal to filter main table"""
        category_item = self.table.item(row, 0)
        if category_item:
            category = category_item.text()
            if category == "Uncategorized":
                category = ""
            self.category_selected.emit(category)
            
            if hasattr(self.parent_page, 'category_filter'):
                try:
                    idx = self.parent_page.category_filter.findText(category)
                    if idx >= 0:
                        self.parent_page.category_filter.setCurrentIndex(idx)
                    else:
                        idx = self.parent_page.category_filter.findText("All Categories")
                        if idx >= 0:
                            self.parent_page.category_filter.setCurrentIndex(idx)
                except Exception as e:
                    pass
    
    def refresh(self):
        """Refresh the data"""
        self.load_data()
    
    def retranslateUi(self):
        """Retranslate UI elements"""
        lang = self._get_lang()
        
        # Retranslate search widget
        self.search_widget.retranslateUi(lang)
        
        if lang == "my":
            self.total_card.set_title("စုစုပေါင်းအသုံးစရိတ်")
            self.count_card.set_title("အမျိုးအစားအရေအတွက်")
            self.top_card.set_title("ထိပ်ဆုံးအမျိုးအစား")
            self.avg_card.set_title("ပျမ်းမျှ")
            
            self.table.setHorizontalHeaderLabels([
                "အမျိုးအစား", "အရေအတွက်", "စုစုပေါင်း", "ပျမ်းမျှ", "ရာခိုင်နှုန်း", "တိုးတက်မှု"
            ])
            
            self.search_widget.search_input.setPlaceholderText("အမျိုးအစားရှာရန်...")
            
        else:
            self.total_card.set_title("Total Expenses")
            self.count_card.set_title("Categories")
            self.top_card.set_title("Top Category")
            self.avg_card.set_title("Average")
            
            self.table.setHorizontalHeaderLabels([
                "Category", "Count", "Total Amount", "Average", "Percentage", "Progress"
            ])
            
            self.search_widget.search_input.setPlaceholderText("Search category...")
        
        self._apply_card_style()
        self.load_data()
        
        # ✅ Update tab icon on language change
        self._update_tab_icon()
    
    def _get_lang(self):
        """Get current language"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    def _apply_card_style(self):
        """Apply card styles"""
        self.total_card.update_theme()
        self.count_card.update_theme()
        self.top_card.update_theme()
        self.avg_card.update_theme()
    
    def showEvent(self, event):
        """Refresh data when tab becomes visible"""
        if self._from_date and self._to_date:
            self.load_data()
        # ✅ Update tab icon when shown
        self._update_tab_icon()
        super().showEvent(event)