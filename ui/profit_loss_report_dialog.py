# ui/profit_loss_report_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QFrame, QFileDialog, QWidget
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


class ProfitLossReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profit & Loss Report")
        self.setMinimumSize(900, 600)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        self._is_dark = is_dark_theme()

        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # ========== Date Range and Export ==========
        filter_group = QGroupBox("Date Range")
        colors = get_theme_colors()
        filter_group.setStyleSheet(self._get_groupbox_style(colors))
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        # DateRangeWidget
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.load_report)
        filter_layout.addWidget(self.date_range)

        # ✅ Export button with SVG icon
        self.btn_export = ModernButton(" Export CSV", ModernButton.PRIMARY)
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_export.set_compact(False)
        self.btn_export.clicked.connect(self.export_report)
        filter_layout.addWidget(self.btn_export)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # ========== Summary Cards using SummaryCardWidget with SVG icons ==========
        card_layout = QHBoxLayout()
        card_layout.setSpacing(10)

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
        card_layout.addWidget(self.sales_card, 1)

        # ✅ Expenses Card
        self.expenses_card = SummaryCardWidget(
            title="Total Expenses",
            value="0",
            icon="money_off",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.expenses_card.set_icon("money_off", is_svg=True, size=(24, 24))
        self.expenses_card.card.setFixedHeight(85)
        self.expenses_card.card.setMinimumWidth(130)
        card_layout.addWidget(self.expenses_card, 1)

        # ✅ Profit Card
        self.profit_card = SummaryCardWidget(
            title="Net Profit",
            value="0",
            icon="bar_chart",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.profit_card.set_icon("bar_chart", is_svg=True, size=(24, 24))
        self.profit_card.card.setFixedHeight(85)
        self.profit_card.card.setMinimumWidth(130)
        card_layout.addWidget(self.profit_card, 1)

        # ✅ Margin Card
        self.margin_card = SummaryCardWidget(
            title="Profit Margin",
            value="0%",
            icon="analytics",
            color="#9b59b6",
            icon_is_svg=True
        )
        self.margin_card.set_icon("analytics", is_svg=True, size=(24, 24))
        self.margin_card.card.setFixedHeight(85)
        self.margin_card.card.setMinimumWidth(130)
        card_layout.addWidget(self.margin_card, 1)

        layout.addLayout(card_layout)

        # ========== Main Table ==========
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Category", "Amount", "Percentage of Sales", "Status", "Trend"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # Apply table style
        self._apply_table_theme()
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

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
        
        # Update table
        self._apply_table_theme()
        
        # Update summary cards
        self.sales_card.update_theme()
        self.expenses_card.update_theme()
        self.profit_card.update_theme()
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
    
    def _apply_table_theme(self):
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
        
        self.table.setStyleSheet(table_style)

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
        colors = get_theme_colors()
        
        self.date_range.retranslateUi(lang)
        
        if lang == "my":
            self.setWindowTitle("အမြတ်အစွန်း အစီရင်ခံစာ")
            self.btn_export.setText(" CSV ထုတ်မည်")
            self.table.setHorizontalHeaderLabels([
                "အမျိုးအစား", "ပမာဏ", "ရောင်းအား၏ ရာခိုင်နှုန်း", 
                "အခြေအနေ", "လမ်းကြောင်း"
            ])
            self.sales_card.set_title("စုစုပေါင်းရောင်းအား")
            self.expenses_card.set_title("စုစုပေါင်းအသုံးစရိတ်")
            self.profit_card.set_title("အသားတင်အမြတ်")
            self.margin_card.set_title("အမြတ်နှုန်း")
        else:
            self.setWindowTitle("Profit & Loss Report")
            self.btn_export.setText(" Export CSV")
            self.table.setHorizontalHeaderLabels([
                "Category", "Amount", "Percentage of Sales", 
                "Status", "Trend"
            ])
            self.sales_card.set_title("Total Sales")
            self.expenses_card.set_title("Total Expenses")
            self.profit_card.set_title("Net Profit")
            self.margin_card.set_title("Profit Margin")
        
        # Update button icons
        self._update_button_icons()
        
        # Update card icons after language change
        self.sales_card.set_icon("attach_money", is_svg=True, size=(24, 24))
        self.expenses_card.set_icon("money_off", is_svg=True, size=(24, 24))
        self.profit_card.set_icon("bar_chart", is_svg=True, size=(24, 24))
        self.margin_card.set_icon("analytics", is_svg=True, size=(24, 24))
        
        # Apply theme after language change
        self._apply_theme()

    def get_date_range(self):
        return self.date_range.get_from_date(), self.date_range.get_to_date()

    def load_report(self):
        from_date, to_date = self.get_date_range()
        symbol = get_currency_symbol()
        is_dark = is_dark_theme()

        conn = connect_db()
        cursor = conn.cursor()

        # Calculate Total Sales
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) FROM sales
            WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        total_sales = cursor.fetchone()[0]

        # Calculate COGS
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

        # Calculate Gross Profit
        gross_profit = total_sales - total_cogs

        # Calculate Total Expenses
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE expense_date BETWEEN ? AND ?
        """, (from_date, to_date))
        total_expenses = cursor.fetchone()[0]

        # Calculate Net Profit
        net_profit = gross_profit - total_expenses

        # Calculate Profit Margin
        profit_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0

        conn.close()

        # Color definitions
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"
        blue_color = "#5865f2" if is_dark else "#3498db"
        text_color = "#dcddde" if is_dark else "#212529"

        # Update Cards
        self.sales_card.set_value(format_money(total_sales, symbol))
        self.expenses_card.set_value(format_money(total_expenses, symbol))
        
        # Color coding for profit
        if net_profit >= 0:
            self.profit_card.set_value(format_money(net_profit, symbol))
            profit_color = green_color
        else:
            self.profit_card.set_value(f"-{format_money(abs(net_profit), symbol)}")
            profit_color = red_color
        
        self.profit_card.set_color(profit_color)
        self.margin_card.set_value(f"{profit_margin:.1f}%")
        
        if profit_margin >= 0:
            self.margin_card.set_color(green_color)
        else:
            self.margin_card.set_color(red_color)

        # Populate Table with color coding
        data = [
            ("Total Sales", total_sales, 100, "Income", "↑"),
            ("Cost of Goods Sold (COGS)", total_cogs, 
             (total_cogs / total_sales * 100) if total_sales > 0 else 0, "Expense", "↓"),
            ("Gross Profit", gross_profit, 
             (gross_profit / total_sales * 100) if total_sales > 0 else 0, 
             "Profit" if gross_profit >= 0 else "Loss",
             "↑" if gross_profit >= 0 else "↓"),
            ("Operating Expenses", total_expenses, 
             (total_expenses / total_sales * 100) if total_sales > 0 else 0, "Expense", "↓"),
            ("Net Profit", net_profit, 
             (net_profit / total_sales * 100) if total_sales > 0 else 0,
             "Profit" if net_profit >= 0 else "Loss",
             "↑" if net_profit >= 0 else "↓"),
        ]

        self.table.setRowCount(len(data))
        for i, (category, amount, percentage, status, trend) in enumerate(data):
            # Category
            cat_item = QTableWidgetItem(category)
            cat_item.setForeground(QColor(text_color))
            self.table.setItem(i, 0, cat_item)
            
            # Amount
            amount_item = QTableWidgetItem(format_money(amount, symbol))
            amount_item.setForeground(QColor(text_color))
            self.table.setItem(i, 1, amount_item)
            
            # Percentage
            percent_item = QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setForeground(QColor(text_color))
            self.table.setItem(i, 2, percent_item)
            
            # Status
            status_item = QTableWidgetItem(status)
            if status == "Profit":
                status_item.setForeground(QColor(green_color))
            elif status == "Loss":
                status_item.setForeground(QColor(red_color))
            else:
                status_item.setForeground(QColor(blue_color))
            self.table.setItem(i, 3, status_item)
            
            # Trend
            trend_item = QTableWidgetItem(trend)
            if trend == "↑":
                trend_item.setForeground(QColor(green_color))
            elif trend == "↓":
                trend_item.setForeground(QColor(red_color))
            self.table.setItem(i, 4, trend_item)

    def export_report(self):
        from_date, to_date = self.get_date_range()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Profit & Loss Report", 
            f"profit_loss_{from_date}_to_{to_date}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            symbol = get_currency_symbol()
            lang = self.get_lang()
            
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COALESCE(SUM(total), 0) FROM sales
                WHERE status = 'completed' AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_sales = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
                FROM sale_items
                JOIN sales ON sale_items.sale_id = sales.id
                JOIN products ON sale_items.product_name = products.name
                WHERE sales.status = 'completed' AND date(sales.created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_cogs = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM expenses
                WHERE expense_date BETWEEN ? AND ?
            """, (from_date, to_date))
            total_expenses = cursor.fetchone()[0]
            
            conn.close()

            gross_profit = total_sales - total_cogs
            net_profit = gross_profit - total_expenses
            profit_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0

            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["=" * 60])
                writer.writerow(["PROFIT & LOSS REPORT"])
                writer.writerow(["=" * 60])
                writer.writerow([])
                writer.writerow(["Period:", f"{from_date} to {to_date}"])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                writer.writerow(["METRIC", "AMOUNT", "% OF SALES"])
                writer.writerow(["-" * 60])
                writer.writerow(["Total Sales", format_money(total_sales, symbol), "100%"])
                writer.writerow(["COGS", format_money(total_cogs, symbol), 
                               f"{(total_cogs/total_sales*100):.1f}%" if total_sales > 0 else "0%"])
                writer.writerow(["Gross Profit", format_money(gross_profit, symbol),
                               f"{(gross_profit/total_sales*100):.1f}%" if total_sales > 0 else "0%"])
                writer.writerow(["Operating Expenses", format_money(total_expenses, symbol),
                               f"{(total_expenses/total_sales*100):.1f}%" if total_sales > 0 else "0%"])
                writer.writerow(["Net Profit", format_money(net_profit, symbol),
                               f"{profit_margin:.1f}%"])
                writer.writerow([])
                writer.writerow(["=" * 60])
                writer.writerow(["End of Report"])
            
            msg = f"Report exported successfully to:\n{file_path}" if lang != "my" else f"အစီရင်ခံစာ အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete", msg)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")
    
    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme()