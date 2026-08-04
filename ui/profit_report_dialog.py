# ui/profit_report_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QComboBox, QTabWidget, QFrame,
    QFileDialog, QWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets import DateRangeWidget, ToastNotificationWidget, SummaryCardWidget
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
import csv
import os


class ProfitReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profit & Loss Report")
        self.setMinimumSize(1100, 750)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setModal(True)
        self._is_dark = is_dark_theme()

        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # ========== FILTER SECTION ==========
        filter_group = QGroupBox("Report Filters")
        colors = get_theme_colors()
        filter_group.setStyleSheet(self._get_groupbox_style(colors))
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(15)

        # DateRangeWidget
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.on_date_range_changed)
        filter_layout.addWidget(self.date_range)

        # Report type
        filter_layout.addWidget(QLabel("Report Type:"))
        self.report_type = QComboBox()
        self.report_type.addItems(["Monthly", "Quarterly", "Yearly", "Custom Period"])
        self.report_type.currentTextChanged.connect(self.on_report_type_changed)
        self.report_type.setStyleSheet(self._get_combobox_style(colors))
        filter_layout.addWidget(self.report_type)

        # ✅ Export button with SVG icon
        self.btn_export = ModernButton(" Export CSV", ModernButton.PRIMARY)
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_export.set_compact(False)
        self.btn_export.clicked.connect(self.export_report)
        filter_layout.addWidget(self.btn_export)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # ========== SUMMARY CARDS (2 rows: 3 cards each) with SVG icons ==========
        # Row 1: Sales, COGS, Gross Profit
        card_layout1 = QHBoxLayout()
        card_layout1.setSpacing(10)

        # ✅ Sales Card
        self.sales_card = SummaryCardWidget(
            title="Total Sales",
            value="0",
            icon="attach_money",
            color="#3498db",
            icon_is_svg=True
        )
        self.sales_card.set_icon("attach_money", is_svg=True, size=(24, 24))
        self.sales_card.card.setFixedHeight(85)
        self.sales_card.card.setMinimumWidth(130)
        card_layout1.addWidget(self.sales_card, 1)

        # ✅ COGS Card
        self.cogs_card = SummaryCardWidget(
            title="Cost of Goods Sold",
            value="0",
            icon="package",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.cogs_card.set_icon("package", is_svg=True, size=(24, 24))
        self.cogs_card.card.setFixedHeight(85)
        self.cogs_card.card.setMinimumWidth(130)
        card_layout1.addWidget(self.cogs_card, 1)

        # ✅ Gross Profit Card
        self.gross_card = SummaryCardWidget(
            title="Gross Profit",
            value="0",
            icon="trending_up",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.gross_card.set_icon("trending_up", is_svg=True, size=(24, 24))
        self.gross_card.card.setFixedHeight(85)
        self.gross_card.card.setMinimumWidth(130)
        card_layout1.addWidget(self.gross_card, 1)

        layout.addLayout(card_layout1)

        # Row 2: Expenses, Net Profit, Margin
        card_layout2 = QHBoxLayout()
        card_layout2.setSpacing(10)

        # ✅ Expenses Card
        self.expenses_card = SummaryCardWidget(
            title="Operating Expenses",
            value="0",
            icon="money_off",
            color="#e67e22",
            icon_is_svg=True
        )
        self.expenses_card.set_icon("money_off", is_svg=True, size=(24, 24))
        self.expenses_card.card.setFixedHeight(85)
        self.expenses_card.card.setMinimumWidth(130)
        card_layout2.addWidget(self.expenses_card, 1)

        # ✅ Net Profit Card
        self.net_card = SummaryCardWidget(
            title="Net Profit",
            value="0",
            icon="bar_chart",
            color="#9b59b6",
            icon_is_svg=True
        )
        self.net_card.set_icon("bar_chart", is_svg=True, size=(24, 24))
        self.net_card.card.setFixedHeight(85)
        self.net_card.card.setMinimumWidth(130)
        card_layout2.addWidget(self.net_card, 1)

        # ✅ Margin Card
        self.margin_card = SummaryCardWidget(
            title="Net Profit Margin",
            value="0%",
            icon="analytics",
            color="#1abc9c",
            icon_is_svg=True
        )
        self.margin_card.set_icon("analytics", is_svg=True, size=(24, 24))
        self.margin_card.card.setFixedHeight(85)
        self.margin_card.card.setMinimumWidth(130)
        card_layout2.addWidget(self.margin_card, 1)

        layout.addLayout(card_layout2)

        # ========== TABS ==========
        self.tabs = QTabWidget()
        self._apply_tab_style()

        # Summary Tab
        self.summary_tab = self.create_summary_tab()
        self.tabs.addTab(self.summary_tab, "Summary")

        # Monthly Breakdown Tab
        self.monthly_tab = self.create_monthly_tab()
        self.tabs.addTab(self.monthly_tab, "Monthly Breakdown")

        # Category Analysis Tab
        self.category_tab = self.create_category_tab()
        self.tabs.addTab(self.category_tab, "Category Analysis")

        # Top Products Tab
        self.products_tab = self.create_products_tab()
        self.tabs.addTab(self.products_tab, "Top Products")

        layout.addWidget(self.tabs)

        # ========== Toast Notification ==========
        self.toast = ToastNotificationWidget(self)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        self.load_report()
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_report()

    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_export.set_icon("file_export", size=(16, 16))

    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update groupbox
        for child in self.findChildren(QGroupBox):
            child.setStyleSheet(self._get_groupbox_style(colors))
        
        # Update combobox
        if hasattr(self, 'report_type'):
            self.report_type.setStyleSheet(self._get_combobox_style(colors))
        
        # Update tab style
        self._apply_tab_style()
        
        # Update summary cards
        self.sales_card.update_theme()
        self.cogs_card.update_theme()
        self.gross_card.update_theme()
        self.expenses_card.update_theme()
        self.net_card.update_theme()
        self.margin_card.update_theme()
        
        # Update button icons
        self._update_button_icons()

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

    def _apply_tab_style(self):
        """Apply tab style based on theme"""
        is_dark = is_dark_theme()
        
        if is_dark:
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    background-color: #2f3136;
                }
                QTabBar::tab {
                    background-color: #2f3136;
                    color: #b9bbbe;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border: none;
                }
                QTabBar::tab:selected {
                    background-color: #40444b;
                    color: #ffffff;
                }
                QTabBar::tab:hover {
                    background-color: #36393f;
                    color: #ffffff;
                }
                QTabBar::tab:!selected {
                    background-color: #202225;
                    color: #72767d;
                }
            """)
        else:
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background-color: #f8f9fa;
                    color: #495057;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border: 1px solid #dee2e6;
                    border-bottom: none;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: #212529;
                    border-bottom: 2px solid #5865f2;
                }
                QTabBar::tab:hover {
                    background-color: #e9ecef;
                    color: #212529;
                }
            """)

    def on_theme_changed(self, theme_name):
        """Handle theme change"""
        pass

    def on_date_range_changed(self, from_date, to_date):
        """Handle date range change"""
        self.load_report()

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

    def get_date_range(self):
        return self.date_range.get_from_date(), self.date_range.get_to_date()

    def on_report_type_changed(self):
        today = QDate.currentDate()
        report_type = self.report_type.currentText()
        
        if report_type == "Monthly":
            self.date_range.from_date.setDate(QDate(today.year(), today.month(), 1))
            self.date_range.to_date.setDate(today)
        elif report_type == "Quarterly":
            quarter = (today.month() - 1) // 3
            quarter_start = quarter * 3 + 1
            self.date_range.from_date.setDate(QDate(today.year(), quarter_start, 1))
            self.date_range.to_date.setDate(today)
        elif report_type == "Yearly":
            self.date_range.from_date.setDate(QDate(today.year(), 1, 1))
            self.date_range.to_date.setDate(today)
        self.load_report()

    def load_report(self):
        from_date, to_date = self.get_date_range()
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()

        conn = connect_db()
        cursor = conn.cursor()

        # Total Sales
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) FROM sales
            WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        total_sales = cursor.fetchone()[0]

        # COGS
        cursor.execute("""
            SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
            FROM sale_items
            JOIN sales ON sale_items.sale_id = sales.id
            JOIN products ON sale_items.product_name = products.name
            WHERE sales.status = 'completed' 
              AND date(sales.created_at) BETWEEN ? AND ?
              AND (products.sold_by IS NULL OR products.sold_by != 'Service')
        """, (from_date, to_date))
        total_cogs = cursor.fetchone()[0]

        # Expenses
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE expense_date BETWEEN ? AND ?
        """, (from_date, to_date))
        total_expenses = cursor.fetchone()[0]

        # Calculate profits
        gross_profit = total_sales - total_cogs
        net_profit = gross_profit - total_expenses
        net_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0

        # Color definitions
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"

        # Update cards using SummaryCardWidget methods
        self.sales_card.set_value(format_money(total_sales, symbol))
        self.cogs_card.set_value(format_money(total_cogs, symbol))
        self.gross_card.set_value(format_money(gross_profit, symbol))
        self.expenses_card.set_value(format_money(total_expenses, symbol))
        self.net_card.set_value(format_money(net_profit, symbol))
        self.margin_card.set_value(f"{net_margin:.1f}%")

        # Color coding for net profit
        net_color = green_color if net_profit >= 0 else red_color
        self.net_card.set_color(net_color)
        
        margin_color = green_color if net_margin >= 0 else red_color
        self.margin_card.set_color(margin_color)

        # Load tabs
        self.load_summary_tab(from_date, to_date)
        self.load_monthly_tab(from_date, to_date)
        self.load_category_tab(from_date, to_date)
        self.load_products_tab(from_date, to_date)

        conn.close()

    def create_summary_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(["Metric", "Amount", "Percentage of Sales", "Trend"])
        self.summary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.summary_table.setAlternatingRowColors(True)
        
        # Apply table style
        self._apply_table_style(self.summary_table)
        
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.summary_table)
        
        widget.setLayout(layout)
        return widget

    def create_monthly_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.monthly_table = QTableWidget()
        self.monthly_table.setColumnCount(7)
        self.monthly_table.setHorizontalHeaderLabels(["Month", "Sales", "COGS", "Gross Profit", "Expenses", "Net Profit", "Margin %"])
        self.monthly_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.monthly_table.setAlternatingRowColors(True)
        
        # Apply table style
        self._apply_table_style(self.monthly_table)
        
        header = self.monthly_table.horizontalHeader()
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.monthly_table)
        
        widget.setLayout(layout)
        return widget

    def create_category_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.category_table = QTableWidget()
        self.category_table.setColumnCount(5)
        self.category_table.setHorizontalHeaderLabels(["Category", "Sales", "COGS", "Gross Profit", "Margin %"])
        self.category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.category_table.setAlternatingRowColors(True)
        
        # Apply table style
        self._apply_table_style(self.category_table)
        
        header = self.category_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.category_table)
        
        widget.setLayout(layout)
        return widget

    def create_products_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(6)
        self.products_table.setHorizontalHeaderLabels(["Product", "Quantity Sold", "Sales", "COGS", "Gross Profit", "Margin %"])
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        
        # Apply table style
        self._apply_table_style(self.products_table)
        
        header = self.products_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.products_table)
        
        widget.setLayout(layout)
        return widget

    def _apply_table_style(self, table):
        """Apply theme-aware table styling"""
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

    def load_summary_tab(self, from_date, to_date):
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"
        
        conn = connect_db()
        cursor = conn.cursor()
        
        from_qdate = QDate.fromString(from_date, "yyyy-MM-dd")
        to_qdate = QDate.fromString(to_date, "yyyy-MM-dd")
        date_range = from_qdate.daysTo(to_qdate)
        
        prev_from = from_qdate.addDays(-date_range - 1).toString("yyyy-MM-dd")
        prev_to = from_qdate.addDays(-1).toString("yyyy-MM-dd")
        
        # Current period data
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) FROM sales
            WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        current_sales = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
            FROM sale_items
            JOIN sales ON sale_items.sale_id = sales.id
            JOIN products ON sale_items.product_name = products.name
            WHERE sales.status = 'completed' AND date(sales.created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        current_cogs = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE expense_date BETWEEN ? AND ?
        """, (from_date, to_date))
        current_expenses = cursor.fetchone()[0]
        
        # Previous period data
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) FROM sales
            WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
        """, (prev_from, prev_to))
        prev_sales = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
            FROM sale_items
            JOIN sales ON sale_items.sale_id = sales.id
            JOIN products ON sale_items.product_name = products.name
            WHERE sales.status = 'completed' AND date(sales.created_at) BETWEEN ? AND ?
        """, (prev_from, prev_to))
        prev_cogs = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE expense_date BETWEEN ? AND ?
        """, (prev_from, prev_to))
        prev_expenses = cursor.fetchone()[0]
        
        conn.close()
        
        current_gross = current_sales - current_cogs
        current_net = current_gross - current_expenses
        
        prev_gross = prev_sales - prev_cogs
        prev_net = prev_gross - prev_expenses
        
        metrics = [
            ("Total Sales", current_sales, prev_sales, 100),
            ("Cost of Goods Sold", current_cogs, prev_cogs, (current_cogs/current_sales*100) if current_sales > 0 else 0),
            ("Gross Profit", current_gross, prev_gross, (current_gross/current_sales*100) if current_sales > 0 else 0),
            ("Operating Expenses", current_expenses, prev_expenses, (current_expenses/current_sales*100) if current_sales > 0 else 0),
            ("Net Profit", current_net, prev_net, (current_net/current_sales*100) if current_sales > 0 else 0),
        ]
        
        self.summary_table.setRowCount(len(metrics))
        for i, (name, current, prev, percent) in enumerate(metrics):
            # Name
            name_item = QTableWidgetItem(name)
            name_item.setForeground(QColor(text_color))
            self.summary_table.setItem(i, 0, name_item)
            
            # Amount
            amount_item = QTableWidgetItem(format_money(current, symbol))
            if "Profit" in name and current >= 0:
                amount_item.setForeground(QColor(green_color))
            elif "Profit" in name and current < 0:
                amount_item.setForeground(QColor(red_color))
            else:
                amount_item.setForeground(QColor(text_color))
            self.summary_table.setItem(i, 1, amount_item)
            
            # Percentage
            percent_item = QTableWidgetItem(f"{percent:.1f}%")
            percent_item.setForeground(QColor(text_color))
            self.summary_table.setItem(i, 2, percent_item)
            
            # Trend
            if prev > 0:
                change = ((current - prev) / prev) * 100
                if change > 0:
                    trend = f"↑ +{change:.1f}%"
                    trend_color = QColor(green_color)
                elif change < 0:
                    trend = f"↓ {change:.1f}%"
                    trend_color = QColor(red_color)
                else:
                    trend = "→ 0%"
                    trend_color = QColor(128, 128, 128)
            else:
                trend = "N/A"
                trend_color = QColor(128, 128, 128)
            
            trend_item = QTableWidgetItem(trend)
            trend_item.setForeground(trend_color)
            self.summary_table.setItem(i, 3, trend_item)

    def load_monthly_tab(self, from_date, to_date):
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            WITH months AS (
                SELECT strftime('%Y-%m', created_at) AS month
                FROM sales
                WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
                UNION
                SELECT strftime('%Y-%m', expense_date) AS month
                FROM expenses
                WHERE expense_date BETWEEN ? AND ?
            ),
            sales_by_month AS (
                SELECT strftime('%Y-%m', created_at) AS month,
                       COALESCE(SUM(total), 0) AS sales
                FROM sales
                WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', created_at)
            ),
            cogs_by_month AS (
                SELECT strftime('%Y-%m', s.created_at) AS month,
                       COALESCE(SUM(
                           COALESCE(
                               NULLIF(si.cost, 0),
                               (SELECT p.cost FROM products p WHERE p.name = si.product_name ORDER BY p.id DESC LIMIT 1),
                               0
                           ) * si.qty
                       ), 0) AS cogs
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'completed'
                  AND date(s.created_at) BETWEEN ? AND ?
                  AND COALESCE(
                        (SELECT p.sold_by FROM products p WHERE p.name = si.product_name ORDER BY p.id DESC LIMIT 1),
                        ''
                      ) != 'Service'
                GROUP BY strftime('%Y-%m', s.created_at)
            ),
            expense_by_month AS (
                SELECT strftime('%Y-%m', expense_date) AS month,
                       COALESCE(SUM(amount), 0) AS expenses
                FROM expenses
                WHERE expense_date BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', expense_date)
            )
            SELECT m.month,
                   COALESCE(s.sales, 0) AS sales,
                   COALESCE(c.cogs, 0) AS cogs,
                   COALESCE(e.expenses, 0) AS expenses
            FROM months m
            LEFT JOIN sales_by_month s ON s.month = m.month
            LEFT JOIN cogs_by_month c ON c.month = m.month
            LEFT JOIN expense_by_month e ON e.month = m.month
            ORDER BY m.month
        """, (
            from_date, to_date,
            from_date, to_date,
            from_date, to_date,
            from_date, to_date,
            from_date, to_date,
        ))
        rows = cursor.fetchall()
        conn.close()
        
        self.monthly_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            month, sales, cogs, expenses = row
            gross = sales - cogs
            net = gross - expenses
            margin = (net / sales * 100) if sales > 0 else 0
            
            # Month
            month_item = QTableWidgetItem(month)
            month_item.setForeground(QColor(text_color))
            self.monthly_table.setItem(i, 0, month_item)
            
            # Sales
            sales_item = QTableWidgetItem(format_money(sales, symbol))
            sales_item.setForeground(QColor(green_color))
            self.monthly_table.setItem(i, 1, sales_item)
            
            # COGS
            cogs_item = QTableWidgetItem(format_money(cogs, symbol))
            cogs_item.setForeground(QColor(red_color))
            self.monthly_table.setItem(i, 2, cogs_item)
            
            # Gross Profit
            gross_item = QTableWidgetItem(format_money(gross, symbol))
            gross_item.setForeground(QColor(green_color) if gross >= 0 else QColor(red_color))
            self.monthly_table.setItem(i, 3, gross_item)
            
            # Expenses
            expenses_item = QTableWidgetItem(format_money(expenses, symbol))
            expenses_item.setForeground(QColor(red_color))
            self.monthly_table.setItem(i, 4, expenses_item)
            
            # Net Profit
            net_item = QTableWidgetItem(format_money(net, symbol))
            net_item.setForeground(QColor(green_color) if net >= 0 else QColor(red_color))
            self.monthly_table.setItem(i, 5, net_item)
            
            # Margin %
            margin_item = QTableWidgetItem(f"{margin:.1f}%")
            if margin >= 20:
                margin_item.setForeground(QColor(green_color))
            elif margin >= 10:
                margin_item.setForeground(QColor(orange_color))
            elif margin >= 0:
                margin_item.setForeground(QColor(orange_color))
            else:
                margin_item.setForeground(QColor(red_color))
            self.monthly_table.setItem(i, 6, margin_item)

    def load_category_tab(self, from_date, to_date):
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        green_color = "#3ba55d" if is_dark else "#28a745"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(p.category, 'Uncategorized') as category,
                COALESCE(SUM(si.total), 0) as sales,
                COALESCE(SUM(p.cost * si.qty), 0) as cogs
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_name = p.name
            WHERE s.status = 'completed' AND date(s.created_at) BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY sales DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        
        self.category_table.setRowCount(len(rows))
        
        for i, row in enumerate(rows):
            category, sales, cogs = row
            gross = sales - cogs
            margin = (gross / sales * 100) if sales > 0 else 0
            
            # Category
            cat_item = QTableWidgetItem(category or "Uncategorized")
            cat_item.setForeground(QColor(text_color))
            self.category_table.setItem(i, 0, cat_item)
            
            # Sales
            sales_item = QTableWidgetItem(format_money(sales, symbol))
            sales_item.setForeground(QColor(green_color))
            self.category_table.setItem(i, 1, sales_item)
            
            # COGS
            cogs_item = QTableWidgetItem(format_money(cogs, symbol))
            cogs_item.setForeground(QColor(text_color))
            self.category_table.setItem(i, 2, cogs_item)
            
            # Gross Profit
            gross_item = QTableWidgetItem(format_money(gross, symbol))
            gross_item.setForeground(QColor(green_color) if gross >= 0 else QColor(text_color))
            self.category_table.setItem(i, 3, gross_item)
            
            # Margin %
            margin_item = QTableWidgetItem(f"{margin:.1f}%")
            if margin > 30:
                margin_item.setForeground(QColor(green_color))
            elif margin > 15:
                margin_item.setForeground(QColor(orange_color))
            else:
                margin_item.setForeground(QColor(orange_color))
            self.category_table.setItem(i, 4, margin_item)

    def load_products_tab(self, from_date, to_date):
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        green_color = "#3ba55d" if is_dark else "#28a745"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                si.product_name,
                COALESCE(SUM(si.qty), 0) as qty,
                COALESCE(SUM(si.total), 0) as sales,
                COALESCE(SUM(p.cost * si.qty), 0) as cogs
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_name = p.name
            WHERE s.status = 'completed' AND date(s.created_at) BETWEEN ? AND ?
            GROUP BY si.product_name
            ORDER BY sales DESC
            LIMIT 20
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        
        self.products_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            product, qty, sales, cogs = row
            gross = sales - cogs
            margin = (gross / sales * 100) if sales > 0 else 0
            
            # Product
            product_item = QTableWidgetItem(product)
            product_item.setForeground(QColor(text_color))
            self.products_table.setItem(i, 0, product_item)
            
            # Quantity Sold
            qty_item = QTableWidgetItem(str(int(qty)))
            qty_item.setForeground(QColor(text_color))
            self.products_table.setItem(i, 1, qty_item)
            
            # Sales
            sales_item = QTableWidgetItem(format_money(sales, symbol))
            sales_item.setForeground(QColor(green_color))
            self.products_table.setItem(i, 2, sales_item)
            
            # COGS
            cogs_item = QTableWidgetItem(format_money(cogs, symbol))
            cogs_item.setForeground(QColor(text_color))
            self.products_table.setItem(i, 3, cogs_item)
            
            # Gross Profit
            gross_item = QTableWidgetItem(format_money(gross, symbol))
            gross_item.setForeground(QColor(green_color) if gross >= 0 else QColor(red_color))
            self.products_table.setItem(i, 4, gross_item)
            
            # Margin %
            margin_item = QTableWidgetItem(f"{margin:.1f}%")
            if margin > 30:
                margin_item.setForeground(QColor(green_color))
            elif margin > 15:
                margin_item.setForeground(QColor(orange_color))
            else:
                margin_item.setForeground(QColor(orange_color))
            self.products_table.setItem(i, 5, margin_item)

    def export_report(self):
        from_date, to_date = self.get_date_range()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Profit Report", f"profit_report_{from_date}_to_{to_date}.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        symbol = get_currency_symbol()
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            WITH months AS (
                SELECT strftime('%Y-%m', created_at) AS month
                FROM sales
                WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
                UNION
                SELECT strftime('%Y-%m', expense_date) AS month
                FROM expenses
                WHERE expense_date BETWEEN ? AND ?
            ),
            sales_by_month AS (
                SELECT strftime('%Y-%m', created_at) AS month,
                       COALESCE(SUM(total), 0) AS sales
                FROM sales
                WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', created_at)
            ),
            cogs_by_month AS (
                SELECT strftime('%Y-%m', s.created_at) AS month,
                       COALESCE(SUM(
                           COALESCE(
                               NULLIF(si.cost, 0),
                               (SELECT p.cost FROM products p WHERE p.name = si.product_name ORDER BY p.id DESC LIMIT 1),
                               0
                           ) * si.qty
                       ), 0) AS cogs
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'completed'
                  AND date(s.created_at) BETWEEN ? AND ?
                  AND COALESCE(
                        (SELECT p.sold_by FROM products p WHERE p.name = si.product_name ORDER BY p.id DESC LIMIT 1),
                        ''
                      ) != 'Service'
                GROUP BY strftime('%Y-%m', s.created_at)
            ),
            expense_by_month AS (
                SELECT strftime('%Y-%m', expense_date) AS month,
                       COALESCE(SUM(amount), 0) AS expenses
                FROM expenses
                WHERE expense_date BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', expense_date)
            )
            SELECT m.month,
                   COALESCE(s.sales, 0) AS sales,
                   COALESCE(c.cogs, 0) AS cogs,
                   COALESCE(e.expenses, 0) AS expenses
            FROM months m
            LEFT JOIN sales_by_month s ON s.month = m.month
            LEFT JOIN cogs_by_month c ON c.month = m.month
            LEFT JOIN expense_by_month e ON e.month = m.month
            ORDER BY m.month
        """, (
            from_date, to_date,
            from_date, to_date,
            from_date, to_date,
            from_date, to_date,
            from_date, to_date,
        ))
        rows = cursor.fetchall()
        conn.close()
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["Month", "Sales", "COGS", "Gross Profit", "Expenses", "Net Profit", "Margin %"])
                for row in rows:
                    month, sales, cogs, expenses = row
                    gross = sales - cogs
                    net = gross - expenses
                    margin = (net / sales * 100) if sales > 0 else 0
                    writer.writerow([month, sales, cogs, gross, expenses, net, f"{margin:.1f}%"])
            QMessageBox.information(self, "Success", f"Report exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def retranslateUi(self):
        lang = self.get_lang()
        self.date_range.retranslateUi(lang)
        
        # Update button icons
        self._update_button_icons()
        
        # Update card icons after language change
        self.sales_card.set_icon("attach_money", is_svg=True, size=(24, 24))
        self.cogs_card.set_icon("package", is_svg=True, size=(24, 24))
        self.gross_card.set_icon("trending_up", is_svg=True, size=(24, 24))
        self.expenses_card.set_icon("money_off", is_svg=True, size=(24, 24))
        self.net_card.set_icon("bar_chart", is_svg=True, size=(24, 24))
        self.margin_card.set_icon("analytics", is_svg=True, size=(24, 24))
        
        if lang == "my":
            self.setWindowTitle("အမြတ်အစွန်း အစီရင်ခံစာ")
            self.btn_export.setText(" CSV ထုတ်မည်")
            self.tabs.setTabText(0, "အကျဉ်းချုပ်")
            self.tabs.setTabText(1, "လစဉ် ခွဲခြမ်းစိတ်ဖြာ")
            self.tabs.setTabText(2, "အမျိုးအစား အလိုက်")
            self.tabs.setTabText(3, "ထိပ်ဆုံးပစ္စည်းများ")
            
            # Update card titles
            self.sales_card.set_title("စုစုပေါင်းရောင်းအား")
            self.cogs_card.set_title("ကုန်ပစ္စည်းကုန်ကျစရိတ်")
            self.gross_card.set_title("အကြမ်းအမြတ်")
            self.expenses_card.set_title("လုပ်ငန်းသုံးစရိတ်")
            self.net_card.set_title("အသားတင်အမြတ်")
            self.margin_card.set_title("အသားတင်အမြတ်နှုန်း")
        else:
            self.setWindowTitle("Profit & Loss Report")
            self.btn_export.setText(" Export CSV")
            self.tabs.setTabText(0, "Summary")
            self.tabs.setTabText(1, "Monthly Breakdown")
            self.tabs.setTabText(2, "Category Analysis")
            self.tabs.setTabText(3, "Top Products")
            
            # Update card titles
            self.sales_card.set_title("Total Sales")
            self.cogs_card.set_title("Cost of Goods Sold")
            self.gross_card.set_title("Gross Profit")
            self.expenses_card.set_title("Operating Expenses")
            self.net_card.set_title("Net Profit")
            self.margin_card.set_title("Net Profit Margin")
        
        # Apply theme after language change
        self._apply_theme()
        self.load_report()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme()