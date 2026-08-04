# ui/expense_comparison_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QFrame, QComboBox, QDateEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from datetime import datetime

# Import widgets
from ui.widgets import (
    DateRangeWidget,
    ToastNotificationWidget,
    LoadingSpinnerWidget,
    SummaryCardWidget
)
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors
import os


class ExpenseComparisonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Expense Comparison")
        self.setWindowFlags(
            self.windowFlags() | 
            Qt.WindowType.WindowMinimizeButtonHint | 
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setMinimumSize(1000, 700)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        self._is_dark = is_dark_theme()

        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== COMPARISON TYPE SELECTION ==========
        type_group = QGroupBox("Comparison Type")
        colors = get_theme_colors()
        type_group.setStyleSheet(self._get_groupbox_style(colors))
        
        type_layout = QHBoxLayout()
        type_layout.setSpacing(10)

        self.comparison_type = QComboBox()
        self.comparison_type.addItems([
            "Current Month vs Last Month",
            "Current Month vs Same Month Last Year",
            "Custom Period Comparison"
        ])
        self.comparison_type.currentTextChanged.connect(self.on_comparison_type_changed)
        self.comparison_type.setStyleSheet(self._get_combobox_style(colors))
        type_layout.addWidget(QLabel("Compare:"))
        type_layout.addWidget(self.comparison_type)
        type_layout.addStretch()

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # ========== CUSTOM PERIOD (Vertical Layout with aligned widgets) ==========
        self.custom_group = QGroupBox("Custom Period")
        self.custom_group.setStyleSheet(self._get_groupbox_style(colors))
        custom_layout = QVBoxLayout()
        custom_layout.setSpacing(12)
        custom_layout.setContentsMargins(15, 15, 15, 15)

        # ===== Period 1 (Current) =====
        period1_layout = QHBoxLayout()
        period1_layout.setSpacing(10)
        
        label1 = QLabel("Period 1 (Current):")
        label1.setFixedWidth(150)
        label1.setStyleSheet(self._get_label_style(colors))
        period1_layout.addWidget(label1)
        
        self.period1_range = DateRangeWidget()
        # Set to current month
        today = QDate.currentDate()
        self.period1_range.set_range(
            QDate(today.year(), today.month(), 1).toString("yyyy-MM-dd"),
            QDate(today.year(), today.month(), today.daysInMonth()).toString("yyyy-MM-dd")
        )
        self.period1_range.date_range_changed.connect(self.on_custom_date_changed)
        period1_layout.addWidget(self.period1_range)
        period1_layout.addStretch()
        
        custom_layout.addLayout(period1_layout)

        # ===== Period 2 (Previous) =====
        period2_layout = QHBoxLayout()
        period2_layout.setSpacing(10)
        
        label2 = QLabel("Period 2 (Previous):")
        label2.setFixedWidth(150)
        label2.setStyleSheet(self._get_label_style(colors))
        period2_layout.addWidget(label2)
        
        self.period2_range = DateRangeWidget()
        # Set to previous month
        today = QDate.currentDate()
        prev_month = today.addMonths(-1)
        self.period2_range.set_range(
            QDate(prev_month.year(), prev_month.month(), 1).toString("yyyy-MM-dd"),
            QDate(prev_month.year(), prev_month.month(), prev_month.daysInMonth()).toString("yyyy-MM-dd")
        )
        self.period2_range.date_range_changed.connect(self.on_custom_date_changed)
        period2_layout.addWidget(self.period2_range)
        period2_layout.addStretch()
        
        custom_layout.addLayout(period2_layout)

        self.custom_group.setLayout(custom_layout)
        self.custom_group.setVisible(False)
        layout.addWidget(self.custom_group)

        # ========== SUMMARY CARDS (Using SummaryCardWidget with SVG icons) ==========
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(15)

        # ✅ Current Period Card
        self.current_card = SummaryCardWidget(
            title="Current Period",
            value="0",
            icon="attach_money",
            color="#3498db",
            icon_is_svg=True
        )
        self.current_card.set_icon("attach_money", is_svg=True, size=(28, 28))
        summary_layout.addWidget(self.current_card, 1)

        # ✅ Previous Period Card
        self.previous_card = SummaryCardWidget(
            title="Previous Period",
            value="0",
            icon="money_off",
            color="#95a5a6",
            icon_is_svg=True
        )
        self.previous_card.set_icon("money_off", is_svg=True, size=(28, 28))
        summary_layout.addWidget(self.previous_card, 1)

        # ✅ Difference Card
        self.diff_card = SummaryCardWidget(
            title="Difference",
            value="0",
            icon="trending_up",
            color="#f39c12",
            icon_is_svg=True
        )
        self.diff_card.set_icon("trending_up", is_svg=True, size=(28, 28))
        summary_layout.addWidget(self.diff_card, 1)

        layout.addLayout(summary_layout)

        # ========== BEST/WORST CATEGORIES ==========
        best_worst_layout = QHBoxLayout()
        best_worst_layout.setSpacing(15)

        # Best Categories (Most decreased)
        best_group = QGroupBox("Biggest Decreases (Savings)")
        best_group.setStyleSheet(self._get_groupbox_style(colors))
        best_layout = QVBoxLayout()
        self.best_table = QTableWidget()
        self.best_table.setColumnCount(3)
        self.best_table.setHorizontalHeaderLabels(["Category", "Change", "Percentage"])
        self.best_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.best_table.setAlternatingRowColors(True)
        best_layout.addWidget(self.best_table)
        best_group.setLayout(best_layout)
        best_worst_layout.addWidget(best_group, 1)

        # Worst Categories (Most increased)
        worst_group = QGroupBox("Biggest Increases (Spending)")
        worst_group.setStyleSheet(self._get_groupbox_style(colors))
        worst_layout = QVBoxLayout()
        self.worst_table = QTableWidget()
        self.worst_table.setColumnCount(3)
        self.worst_table.setHorizontalHeaderLabels(["Category", "Change", "Percentage"])
        self.worst_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.worst_table.setAlternatingRowColors(True)
        worst_layout.addWidget(self.worst_table)
        worst_group.setLayout(worst_layout)
        best_worst_layout.addWidget(worst_group, 1)

        layout.addLayout(best_worst_layout)

        # ========== MAIN COMPARISON TABLE ==========
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Category", "Current Period", "Previous Period", 
            "Difference", "Change %", "Trend"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # ========== BUTTONS ==========
        btn_layout = QHBoxLayout()
        
        # ✅ Close button with SVG icon
        self.btn_close = ModernButton(" Close", ModernButton.TERTIARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        # ========== Toast Notification ==========
        self.toast = ToastNotificationWidget(self)

        # ========== Loading Spinner ==========
        self.spinner = LoadingSpinnerWidget("Loading comparison data...")
        self.spinner.hide()
        layout.addWidget(self.spinner)

        self.setLayout(layout)
        
        # Apply table theme after all tables are created
        self._apply_table_theme()
        
        # Apply initial theme
        self._apply_theme()
        
        self.load_month_vs_last_month()
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self._update_card_icons()
        self.load_month_vs_last_month()

    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_close.set_icon("close", size=(16, 16))

    def _update_card_icons(self):
        """Update card icons when theme changes"""
        self.current_card.set_icon("attach_money", is_svg=True, size=(28, 28))
        self.previous_card.set_icon("money_off", is_svg=True, size=(28, 28))
        self.diff_card.set_icon("trending_up", is_svg=True, size=(28, 28))
        
        self.current_card.update_theme()
        self.previous_card.update_theme()
        self.diff_card.update_theme()

    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update groupboxes
        for child in self.findChildren(QGroupBox):
            child.setStyleSheet(self._get_groupbox_style(colors))
        
        # Update combobox
        if hasattr(self, 'comparison_type'):
            self.comparison_type.setStyleSheet(self._get_combobox_style(colors))
        
        # Update tables
        self._apply_table_theme()
        
        # Update summary cards
        self.current_card.update_theme()
        self.previous_card.update_theme()
        self.diff_card.update_theme()
        
        # Update button icons
        self._update_button_icons()
        
        # Update labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style(colors))

    def _get_groupbox_style(self, colors):
        return f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 10pt;
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding-top: 10px;
                margin-top: 5px;
                color: {colors['text']};
                background-color: {colors['card_bg']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {colors['text']};
            }}
        """

    def _get_combobox_style(self, colors):
        return f"""
            QComboBox {{
                padding: 6px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-width: 120px;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 8px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """

    def _get_label_style(self, colors):
        return f"color: {colors['text']}; font-size: 10pt; font-weight: 500;"

    def _apply_table_theme(self):
        """Apply theme-aware table styling to all tables"""
        self._apply_table_theme_to_table(self.table)
        self._apply_table_theme_to_table(self.best_table)
        self._apply_table_theme_to_table(self.worst_table)

    def _apply_table_theme_to_table(self, table):
        """Apply theme-aware table styling to a specific table"""
        is_dark = is_dark_theme()
        
        if is_dark:
            table_style = """
                QTableWidget {
                    background-color: #2f3136;
                    alternate-background-color: #36393f;
                    selection-background-color: #40444b;
                    selection-color: #dcddde;
                    gridline-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    color: #dcddde;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #dcddde;
                }
                QTableWidget::item:selected {
                    background-color: #40444b;
                    color: #dcddde;
                }
                QHeaderView::section {
                    background-color: #202225;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #40444b;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #b9bbbe;
                }
                QTableWidget::item:hover {
                    background-color: #40444b;
                }
            """
        else:
            table_style = """
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    selection-background-color: #e9ecef;
                    selection-color: #212529;
                    gridline-color: #dee2e6;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    color: #212529;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #212529;
                }
                QTableWidget::item:selected {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #2c3e50;
                }
                QTableWidget::item:hover {
                    background-color: #f1f3f5;
                }
            """
        
        table.setStyleSheet(table_style)

    def get_theme(self):
        """Get current theme from settings"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except:
            return "Light"

    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"

    def retranslateUi(self):
        lang = self.get_lang()
        symbol = get_currency_symbol()
        colors = get_theme_colors()
        
        # Retranslate DateRangeWidgets
        self.period1_range.retranslateUi(lang)
        self.period2_range.retranslateUi(lang)
        
        if lang == "my":
            self.setWindowTitle("အသုံးစရိတ် နှိုင်းယှဉ်ချက်")
            self.current_card.set_title("လက်ရှိရကား")
            self.previous_card.set_title("ယခင်ရကား")
            self.diff_card.set_title("ကွာခြားချက်")
            self.btn_close.setText(" ပိတ်မည်")
            self.table.setHorizontalHeaderLabels([
                "အမျိုးအစား", "လက်ရှိရကား", "ယခင်ရကား",
                "ကွာခြားချက်", "ရာခိုင်နှုန်း", "လမ်းကြောင်း"
            ])
            self.best_table.setHorizontalHeaderLabels(["အမျိုးအစား", "ပြောင်းလဲမှု", "ရာခိုင်နှုန်း"])
            self.worst_table.setHorizontalHeaderLabels(["အမျိုးအစား", "ပြောင်းလဲမှု", "ရာခိုင်နှုန်း"])
        else:
            self.setWindowTitle("Expense Comparison")
            self.current_card.set_title("Current Period")
            self.previous_card.set_title("Previous Period")
            self.diff_card.set_title("Difference")
            self.btn_close.setText(" Close")
            self.table.setHorizontalHeaderLabels([
                "Category", "Current Period", "Previous Period",
                "Difference", "Change %", "Trend"
            ])
            self.best_table.setHorizontalHeaderLabels(["Category", "Change", "Percentage"])
            self.worst_table.setHorizontalHeaderLabels(["Category", "Change", "Percentage"])
        
        # Update button icons
        self._update_button_icons()
        
        # Update card icons after language change
        self._update_card_icons()
        
        # Apply theme after language change
        self._apply_theme()

    def on_comparison_type_changed(self, text):
        if text == "Custom Period Comparison":
            self.custom_group.setVisible(True)
            self.load_custom_comparison()
        else:
            self.custom_group.setVisible(False)
            if text == "Current Month vs Last Month":
                self.load_month_vs_last_month()
            else:
                self.load_month_vs_last_year()

    def on_custom_date_changed(self, from_date, to_date):
        """Handle custom date range changes"""
        if self.comparison_type.currentText() == "Custom Period Comparison":
            self.load_custom_comparison()

    def load_month_vs_last_month(self):
        """Load comparison between current month and last month"""
        today = QDate.currentDate()
        
        # Current month (this month)
        current_start = QDate(today.year(), today.month(), 1)
        current_end = QDate(today.year(), today.month(), today.daysInMonth())
        
        # Last month
        last_month_date = today.addMonths(-1)
        last_start = QDate(last_month_date.year(), last_month_date.month(), 1)
        last_end = QDate(last_month_date.year(), last_month_date.month(), last_month_date.daysInMonth())
        
        self.current_card.set_title(f"{current_start.toString('MMM yyyy')}")
        self.previous_card.set_title(f"{last_start.toString('MMM yyyy')}")
        
        self.load_comparison_data(
            current_start.toString("yyyy-MM-dd"),
            current_end.toString("yyyy-MM-dd"),
            last_start.toString("yyyy-MM-dd"),
            last_end.toString("yyyy-MM-dd")
        )

    def load_month_vs_last_year(self):
        """Load comparison between current month and same month last year"""
        today = QDate.currentDate()
        
        # Current month (this month this year)
        current_start = QDate(today.year(), today.month(), 1)
        current_end = QDate(today.year(), today.month(), today.daysInMonth())
        
        # Same month last year
        last_year_start = QDate(today.year() - 1, today.month(), 1)
        last_year_end = QDate(today.year() - 1, today.month(), last_year_start.daysInMonth())
        
        self.current_card.set_title(f"{current_start.toString('MMM yyyy')}")
        self.previous_card.set_title(f"{last_year_start.toString('MMM yyyy')}")
        
        self.load_comparison_data(
            current_start.toString("yyyy-MM-dd"),
            current_end.toString("yyyy-MM-dd"),
            last_year_start.toString("yyyy-MM-dd"),
            last_year_end.toString("yyyy-MM-dd")
        )

    def load_custom_comparison(self):
        """Load comparison with custom date ranges"""
        period1_from = self.period1_range.get_from_date()
        period1_to = self.period1_range.get_to_date()
        period2_from = self.period2_range.get_from_date()
        period2_to = self.period2_range.get_to_date()
        
        self.current_card.set_title(f"{period1_from} to {period1_to}")
        self.previous_card.set_title(f"{period2_from} to {period2_to}")
        
        self.load_comparison_data(period1_from, period1_to, period2_from, period2_to)

    def load_comparison_data(self, current_from, current_to, previous_from, previous_to):
        self.spinner.start()
        
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()
        
        # Color definitions
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"
        gray_color = "#72767d" if is_dark else "#6c757d"
        text_color = "#dcddde" if is_dark else "#212529"

        conn = connect_db()
        cursor = conn.cursor()

        # Get current period expenses by category
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category
        """, (current_from, current_to))
        current_data = {row[0]: row[1] for row in cursor.fetchall()}

        # Get previous period expenses by category
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category
        """, (previous_from, previous_to))
        previous_data = {row[0]: row[1] for row in cursor.fetchall()}

        # Get all categories
        cursor.execute("SELECT name FROM expense_categories ORDER BY name")
        categories = cursor.fetchall()
        conn.close()

        # Calculate totals
        total_current = sum(current_data.values())
        total_previous = sum(previous_data.values())
        total_diff = total_current - total_previous
        total_percent = (total_diff / total_previous * 100) if total_previous > 0 else 0

        # Update summary cards
        self.current_card.set_value(format_money(total_current, symbol))
        self.previous_card.set_value(format_money(total_previous, symbol))
        
        diff_text = format_money(total_diff, symbol)
        
        # Set color for diff card
        if total_diff > 0:
            self.diff_card.set_color(red_color)
            self.diff_card.set_value(f"{diff_text} (+{total_percent:.1f}%)")
        elif total_diff < 0:
            self.diff_card.set_color(green_color)
            self.diff_card.set_value(f"{diff_text} ({total_percent:+.1f}%)")
        else:
            self.diff_card.set_color(gray_color)
            self.diff_card.set_value(f"{diff_text} (0%)")

        # Populate main table
        self.table.setRowCount(0)
        comparisons = []

        for (cat_name,) in categories:
            current = current_data.get(cat_name, 0)
            previous = previous_data.get(cat_name, 0)
            diff = current - previous
            percent = (diff / previous * 100) if previous > 0 else (100 if current > 0 else 0)
            
            comparisons.append({
                'category': cat_name,
                'current': current,
                'previous': previous,
                'diff': diff,
                'percent': percent
            })
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Category
            cat_item = QTableWidgetItem(cat_name)
            cat_item.setForeground(QColor(text_color))
            self.table.setItem(row, 0, cat_item)
            
            # Current Period
            current_item = QTableWidgetItem(format_money(current, symbol))
            current_item.setForeground(QColor(text_color))
            self.table.setItem(row, 1, current_item)
            
            # Previous Period
            previous_item = QTableWidgetItem(format_money(previous, symbol))
            previous_item.setForeground(QColor(text_color))
            self.table.setItem(row, 2, previous_item)
            
            # Difference
            diff_item = QTableWidgetItem(format_money(diff, symbol))
            if diff > 0:
                diff_item.setForeground(QColor(red_color))
            elif diff < 0:
                diff_item.setForeground(QColor(green_color))
            else:
                diff_item.setForeground(QColor(text_color))
            self.table.setItem(row, 3, diff_item)
            
            # Change %
            percent_item = QTableWidgetItem(f"{percent:+.1f}%")
            if percent > 0:
                percent_item.setForeground(QColor(red_color))
            elif percent < 0:
                percent_item.setForeground(QColor(green_color))
            else:
                percent_item.setForeground(QColor(text_color))
            self.table.setItem(row, 4, percent_item)
            
            # Trend indicator
            if diff > 0:
                trend = "↑ Increased"
                trend_color = QColor(red_color)
            elif diff < 0:
                trend = "↓ Decreased"
                trend_color = QColor(green_color)
            else:
                trend = "→ No change"
                trend_color = QColor(gray_color)
            
            trend_item = QTableWidgetItem(trend)
            trend_item.setForeground(trend_color)
            self.table.setItem(row, 5, trend_item)

        # Load best and worst categories
        self.load_best_worst_categories(comparisons)
        
        self.spinner.stop()

    def load_best_worst_categories(self, comparisons):
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()
        
        # Color definitions
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"
        text_color = "#dcddde" if is_dark else "#212529"
        
        # Best = most decreased (negative diff)
        best_categories = sorted(comparisons, key=lambda x: x['diff'])[:5]
        
        # Worst = most increased (positive diff)
        worst_categories = sorted(comparisons, key=lambda x: x['diff'], reverse=True)[:5]
        
        # Best table (Savings)
        self.best_table.setRowCount(0)
        has_best = False
        for cat in best_categories:
            if cat['diff'] >= 0:
                continue
            has_best = True
            row = self.best_table.rowCount()
            self.best_table.insertRow(row)
            
            cat_item = QTableWidgetItem(cat['category'])
            cat_item.setForeground(QColor(text_color))
            self.best_table.setItem(row, 0, cat_item)
            
            change_text = format_money(cat['diff'], symbol)
            change_item = QTableWidgetItem(change_text)
            change_item.setForeground(QColor(green_color))
            self.best_table.setItem(row, 1, change_item)
            
            percent_text = f"{cat['percent']:+.1f}%"
            percent_item = QTableWidgetItem(percent_text)
            percent_item.setForeground(QColor(green_color))
            self.best_table.setItem(row, 2, percent_item)
        
        if not has_best:
            row = self.best_table.rowCount()
            self.best_table.insertRow(row)
            no_item = QTableWidgetItem("No savings")
            no_item.setForeground(QColor(text_color))
            self.best_table.setItem(row, 0, no_item)
            self.best_table.setItem(row, 1, QTableWidgetItem("0"))
            self.best_table.setItem(row, 2, QTableWidgetItem("0%"))
        
        # Worst table (Increased spending)
        self.worst_table.setRowCount(0)
        has_worst = False
        for cat in worst_categories:
            if cat['diff'] <= 0:
                continue
            has_worst = True
            row = self.worst_table.rowCount()
            self.worst_table.insertRow(row)
            
            cat_item = QTableWidgetItem(cat['category'])
            cat_item.setForeground(QColor(text_color))
            self.worst_table.setItem(row, 0, cat_item)
            
            change_text = format_money(cat['diff'], symbol)
            change_item = QTableWidgetItem(change_text)
            change_item.setForeground(QColor(red_color))
            self.worst_table.setItem(row, 1, change_item)
            
            percent_text = f"{cat['percent']:+.1f}%"
            percent_item = QTableWidgetItem(percent_text)
            percent_item.setForeground(QColor(red_color))
            self.worst_table.setItem(row, 2, percent_item)
        
        if not has_worst:
            row = self.worst_table.rowCount()
            self.worst_table.insertRow(row)
            no_item = QTableWidgetItem("No increases")
            no_item.setForeground(QColor(text_color))
            self.worst_table.setItem(row, 0, no_item)
            self.worst_table.setItem(row, 1, QTableWidgetItem("0"))
            self.worst_table.setItem(row, 2, QTableWidgetItem("0%"))

    def showEvent(self, event):
        """Apply theme when dialog becomes visible"""
        self._apply_theme()
        self._update_card_icons()
        super().showEvent(event)