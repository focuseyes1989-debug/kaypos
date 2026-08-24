# ui/customer_page/outstanding_report_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QFileDialog, QFrame, QWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.language import lang
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import csv
from datetime import datetime
from loguru import logger
import os


class OutstandingReportDialog(QDialog):
    """Outstanding Debts Report - Theme-aware with SVG Icons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        
        # Allow minimize and maximize
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        
        self.setWindowTitle("Outstanding Debts Report")
        self.setMinimumSize(960, 620)
        self.resize(1100, 720)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Enable resize grip
        self.setSizeGripEnabled(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(18)
        layout.setContentsMargins(28, 24, 28, 24)

        # Report heading
        self.header_frame = QFrame()
        self.header_frame.setObjectName("report_header")
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(5)
        self.title_label = QLabel("Outstanding Debts")
        self.title_label.setObjectName("report_title")
        self.subtitle_label = QLabel("Review customer balances and overdue invoices at a glance.")
        self.subtitle_label.setObjectName("report_subtitle")
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)
        layout.addWidget(self.header_frame)

        # Summary cards - Using SummaryCardWidget with SVG icons
        card_layout = QHBoxLayout()
        card_layout.setSpacing(14)

        # ✅ Total Outstanding Card with SVG icon
        self.total_card = SummaryCardWidget(
            title="Total Outstanding",
            value="0",
            icon="money_off",
            color="#3498db",
            icon_is_svg=True
        )
        self.total_card.set_icon("money_off", is_svg=True, size=(24, 24))
        self.total_card.setMinimumHeight(126)
        card_layout.addWidget(self.total_card)

        # ✅ Overdue Amount Card with SVG icon
        self.overdue_card = SummaryCardWidget(
            title="Overdue Amount",
            value="0",
            icon="warning",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.overdue_card.set_icon("warning", is_svg=True, size=(24, 24))
        self.overdue_card.setMinimumHeight(126)
        card_layout.addWidget(self.overdue_card)

        # ✅ Customers with Debt Card with SVG icon
        self.customer_count_card = SummaryCardWidget(
            title="Customers with Debt",
            value="0",
            icon="groups",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.customer_count_card.set_icon("groups", is_svg=True, size=(24, 24))
        self.customer_count_card.setMinimumHeight(126)
        card_layout.addWidget(self.customer_count_card)

        layout.addLayout(card_layout)

        # Data surface
        self.table_frame = QFrame()
        self.table_frame.setObjectName("report_table_frame")
        table_layout = QVBoxLayout(self.table_frame)
        table_layout.setContentsMargins(1, 1, 1, 1)
        table_layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setObjectName("outstanding_table")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Customer ID", "Customer Name", "Phone", "Current Balance", "Credit Limit", "Overdue Invoices", "Status"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setColumnHidden(0, True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        
        # Apply table style
        colors = get_theme_colors()
        self._update_table_style(colors)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table_layout.addWidget(self.table)
        layout.addWidget(self.table_frame, 1)

        # Buttons - Using ModernButton with SVG icons
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        # ✅ Export button with SVG icon
        self.btn_export = ModernButton("Export CSV", ModernButton.PRIMARY)
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_export.set_compact(False)
        self.btn_export.clicked.connect(self.export_report)
        btn_layout.addWidget(self.btn_export)
        
        # ✅ Refresh button with SVG icon
        self.btn_refresh = ModernButton("Refresh", ModernButton.SECONDARY)
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_refresh.set_compact(False)
        self.btn_refresh.clicked.connect(self.load_report)
        btn_layout.addWidget(self.btn_refresh)
        
        btn_layout.addStretch()
        
        # ✅ Close button with SVG icon
        self.btn_close = ModernButton("Close", ModernButton.SECONDARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.setFixedSize(112, 38)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addWidget(button_frame)

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
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_close.set_icon("close", size=(16, 16))
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
                font-family: "Segoe UI", "Myanmar Text", "Noto Sans Myanmar";
            }}
            QFrame#report_header {{
                background: transparent;
                border: none;
            }}
            QLabel#report_title {{
                color: {colors['text']};
                font-size: 20pt;
                font-weight: 700;
            }}
            QLabel#report_subtitle {{
                color: {colors['text_secondary']};
                font-size: 9.5pt;
            }}
            QFrame#report_table_frame {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
        """)
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update table
        self._update_table_style(colors)
        
        # Update summary cards
        if hasattr(self, 'total_card'):
            self.total_card.update_theme()
        if hasattr(self, 'overdue_card'):
            self.overdue_card.update_theme()
        if hasattr(self, 'customer_count_card'):
            self.customer_count_card.update_theme()
        
        # Update button icons
        self._update_button_icons()
    
    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: transparent;
                border: none;
            }}
        """
    
    def _update_table_style(self, colors):
        """Update table style based on theme"""
        table_style = f"""
            QTableWidget#outstanding_table {{
                background-color: {colors['card_bg']};
                alternate-background-color: {colors['table_alt']};
                color: {colors['text']};
                border: none;
                border-radius: 11px;
                gridline-color: transparent;
                selection-background-color: {colors['bg_hover']};
                selection-color: {colors['text']};
                font-size: 9.5pt;
            }}
            QTableWidget#outstanding_table::item {{
                padding: 7px 12px;
                border-bottom: 1px solid {colors['border']};
            }}
            QTableWidget#outstanding_table::item:hover,
            QTableWidget#outstanding_table::item:selected {{
                background-color: {colors['bg_hover']};
            }}
            QHeaderView::section {{
                background-color: {colors['card_bg']};
                color: {colors['text_secondary']};
                padding: 11px 12px;
                border: none;
                border-bottom: 1px solid {colors['border']};
                font-weight: 600;
                font-size: 9pt;
            }}
            QTableCornerButton::section {{
                background-color: {colors['card_bg']};
                border: none;
                border-bottom: 1px solid {colors['border']};
            }}
        """
        self.table.setStyleSheet(table_style)

    def get_lang(self):
        return lang.get_current()

    def retranslateUi(self):
        lang_code = self.get_lang()
        colors = get_theme_colors()
        
        if lang_code == "my":
            self.setWindowTitle("အကြွေးကျန်စာရင်း အစီရင်ခံစာ")
            self.title_label.setText("အကြွေးကျန်စာရင်း")
            self.subtitle_label.setText("ဝယ်ယူသူများ၏ လက်ကျန်ငွေနှင့် သက်တမ်းလွန်ပြေစာများကို တစ်နေရာတည်းတွင် စစ်ဆေးနိုင်သည်။")
            self.total_card.set_title("စုစုပေါင်းအကြွေးကျန်")
            self.overdue_card.set_title("သက်တမ်းလွန်အကြွေး")
            self.customer_count_card.set_title("အကြွေးရှိသောဝယ်ယူသူများ")
            self.btn_export.setText("CSV ထုတ်မည်")
            self.btn_refresh.setText("ပြန်လည်ဖတ်မည်")
            self.btn_close.setText("ပိတ်မည်")
            self.table.setHorizontalHeaderLabels([
                "ID", "အမည်", "ဖုန်း", "လက်ကျန်အကြွေး", 
                "ခရက်ဒစ်ကန့်သတ်ချက်", "သက်တမ်းလွန်ပြေစာ", "အခြေအနေ"
            ])
        else:
            self.setWindowTitle("Outstanding Debts Report")
            self.title_label.setText("Outstanding Debts")
            self.subtitle_label.setText("Review customer balances and overdue invoices at a glance.")
            self.total_card.set_title("Total Outstanding")
            self.overdue_card.set_title("Overdue Amount")
            self.customer_count_card.set_title("Customers with Debt")
            self.btn_export.setText("Export CSV")
            self.btn_refresh.setText("Refresh")
            self.btn_close.setText("Close")
            self.table.setHorizontalHeaderLabels([
                "ID", "Name", "Phone", "Current Balance", 
                "Credit Limit", "Overdue Invoices", "Status"
            ])
        
        # Update button icons
        self._update_button_icons()
        
        # Apply theme after language change
        self._apply_theme()

    def load_report(self):
        """Load outstanding report with optimized single query"""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            # Optimized: Single query with all aggregates
            query = """
                WITH customer_debt AS (
                    SELECT 
                        c.id,
                        c.name,
                        c.phone,
                        COALESCE(c.current_balance, 0) as current_balance,
                        COALESCE(c.credit_limit, 0) as credit_limit,
                        -- Calculate total balance from credit_sales (more accurate)
                        COALESCE((
                            SELECT SUM(balance_amount) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as credit_sales_balance,
                        -- Count overdue invoices
                        COALESCE((
                            SELECT COUNT(*) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND date(cs.due_date) < date('now') 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as overdue_count,
                        -- Total overdue amount
                        COALESCE((
                            SELECT SUM(balance_amount) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND date(cs.due_date) < date('now') 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as overdue_amount
                    FROM customers c
                    WHERE c.current_balance > 0 
                       OR EXISTS (
                           SELECT 1 FROM credit_sales cs 
                           WHERE cs.customer_id = c.id 
                             AND cs.balance_amount > 0
                             AND cs.status != 'refunded'
                       )
                )
                SELECT 
                    id,
                    name,
                    phone,
                    current_balance,
                    credit_limit,
                    credit_sales_balance,
                    overdue_count,
                    overdue_amount
                FROM customer_debt
                ORDER BY current_balance DESC, credit_sales_balance DESC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Get total summary in a single query
            summary_query = """
                SELECT 
                    COALESCE(SUM(current_balance), 0) as total_balance,
                    COUNT(*) as customer_count,
                    COALESCE(SUM(overdue_amount), 0) as total_overdue
                FROM (
                    SELECT 
                        c.current_balance,
                        COALESCE((
                            SELECT SUM(balance_amount) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND date(cs.due_date) < date('now') 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as overdue_amount
                    FROM customers c
                    WHERE c.current_balance > 0 
                       OR EXISTS (
                           SELECT 1 FROM credit_sales cs 
                           WHERE cs.customer_id = c.id 
                             AND cs.balance_amount > 0
                             AND cs.status != 'refunded'
                       )
                )
            """
            cursor.execute(summary_query)
            summary = cursor.fetchone()
            
            conn.close()
            
            symbol = get_currency_symbol()
            lang_code = self.get_lang()
            colors = get_theme_colors()
            is_dark = is_dark_theme()
            
            # Color definitions
            red_color = "#ed4245" if is_dark else "#dc3545"
            green_color = "#3ba55d" if is_dark else "#28a745"
            gray_color = "#72767d" if is_dark else "#6c757d"
            text_color = "#dcddde" if is_dark else "#212529"
            
            # Update summary cards
            total_outstanding = summary[0] if summary else 0
            customer_count = summary[1] if summary else 0
            total_overdue = summary[2] if summary else 0
            
            self.total_card.set_value(format_money(total_outstanding, symbol))
            self.customer_count_card.set_value(str(customer_count))
            self.overdue_card.set_value(format_money(total_overdue, symbol))
            
            # Set colors for amounts
            if total_outstanding > 0:
                self.total_card.set_color(red_color)
            else:
                self.total_card.set_color("#3498db")
            
            if total_overdue > 0:
                self.overdue_card.set_color(red_color)
            else:
                self.overdue_card.set_color(green_color)
            
            # Populate table
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                cust_id, name, phone, current_balance, credit_limit, credit_sales_balance, overdue_count, overdue_amount = row
                
                # Use max of current_balance and credit_sales_balance for accuracy
                display_balance = max(current_balance, credit_sales_balance)
                
                # ID (hidden)
                id_item = QTableWidgetItem(str(cust_id))
                id_item.setForeground(QColor(text_color))
                self.table.setItem(i, 0, id_item)
                
                # Name
                name_item = QTableWidgetItem(name)
                name_item.setForeground(QColor(text_color))
                self.table.setItem(i, 1, name_item)
                
                # Phone
                phone_item = QTableWidgetItem(phone or "-")
                phone_item.setForeground(QColor(text_color))
                self.table.setItem(i, 2, phone_item)
                
                # Balance
                balance_item = QTableWidgetItem(format_money(display_balance, symbol))
                if display_balance > 0:
                    balance_item.setForeground(QColor(red_color))
                else:
                    balance_item.setForeground(QColor(green_color))
                self.table.setItem(i, 3, balance_item)
                
                # Credit Limit
                credit_item = QTableWidgetItem(format_money(credit_limit or 0, symbol))
                credit_item.setForeground(QColor(text_color))
                self.table.setItem(i, 4, credit_item)
                
                # Overdue count
                overdue_item = QTableWidgetItem(str(overdue_count))
                if overdue_count > 0:
                    overdue_item.setForeground(QColor(red_color))
                    overdue_item.setBackground(QColor(red_color + "20" if is_dark else "#fff0f0"))
                else:
                    overdue_item.setForeground(QColor(text_color))
                self.table.setItem(i, 5, overdue_item)
                
                # Status
                if overdue_count > 0:
                    status = "⚠️ Overdue" if lang_code != "my" else "⚠️ သက်တမ်းလွန်"
                    status_color = QColor(red_color)
                elif display_balance > 0:
                    status = "✓ Current" if lang_code != "my" else "✓ လက်ရှိ"
                    status_color = QColor(green_color)
                else:
                    status = "-" if lang_code != "my" else "-"
                    status_color = QColor(gray_color)
                
                status_item = QTableWidgetItem(status)
                status_item.setForeground(status_color)
                self.table.setItem(i, 6, status_item)
            
        except Exception as e:
            conn.close()
            logger.error(f"Error loading outstanding report: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load report: {e}")

    def export_report(self):
        """Export outstanding report with all data"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Outstanding Report", 
            f"outstanding_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            
            # Use same optimized query for export
            query = """
                WITH customer_debt AS (
                    SELECT 
                        c.id,
                        c.name,
                        c.phone,
                        COALESCE(c.current_balance, 0) as current_balance,
                        COALESCE(c.credit_limit, 0) as credit_limit,
                        COALESCE((
                            SELECT SUM(balance_amount) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as credit_sales_balance,
                        COALESCE((
                            SELECT COUNT(*) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND date(cs.due_date) < date('now') 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as overdue_count,
                        COALESCE((
                            SELECT SUM(balance_amount) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND date(cs.due_date) < date('now') 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as overdue_amount
                    FROM customers c
                    WHERE c.current_balance > 0 
                       OR EXISTS (
                           SELECT 1 FROM credit_sales cs 
                           WHERE cs.customer_id = c.id 
                             AND cs.balance_amount > 0
                             AND cs.status != 'refunded'
                       )
                )
                SELECT 
                    name,
                    phone,
                    current_balance,
                    credit_limit,
                    credit_sales_balance,
                    overdue_count,
                    overdue_amount
                FROM customer_debt
                ORDER BY current_balance DESC, credit_sales_balance DESC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Get summary data
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(current_balance), 0) as total_balance,
                    COUNT(*) as customer_count,
                    COALESCE(SUM(overdue_amount), 0) as total_overdue
                FROM (
                    SELECT 
                        c.current_balance,
                        COALESCE((
                            SELECT SUM(balance_amount) 
                            FROM credit_sales cs 
                            WHERE cs.customer_id = c.id 
                              AND date(cs.due_date) < date('now') 
                              AND cs.balance_amount > 0
                              AND cs.status != 'refunded'
                        ), 0) as overdue_amount
                    FROM customers c
                    WHERE c.current_balance > 0 
                       OR EXISTS (
                           SELECT 1 FROM credit_sales cs 
                           WHERE cs.customer_id = c.id 
                             AND cs.balance_amount > 0
                             AND cs.status != 'refunded'
                       )
                )
            """)
            summary = cursor.fetchone()
            conn.close()
            
            symbol = get_currency_symbol()
            lang_code = self.get_lang()
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow(["=" * 80])
                writer.writerow(["OUTSTANDING DEBTS REPORT"])
                writer.writerow(["=" * 80])
                writer.writerow([])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                
                # Summary
                writer.writerow(["SUMMARY"])
                writer.writerow(["-" * 40])
                writer.writerow(["Total Outstanding:", format_money(summary[0] if summary else 0, symbol)])
                writer.writerow(["Customers with Debt:", summary[1] if summary else 0])
                writer.writerow(["Total Overdue:", format_money(summary[2] if summary else 0, symbol)])
                writer.writerow([])
                
                # Detail header
                writer.writerow(["Customer Name", "Phone", "Current Balance", "Credit Limit", 
                               "Credit Sales Balance", "Overdue Invoices", "Overdue Amount"])
                writer.writerow(["-" * 80])
                
                # Detail rows
                total_balance = 0
                total_credit_sales_balance = 0
                total_overdue_amount = 0
                
                for row in rows:
                    name, phone, current_balance, credit_limit, credit_sales_balance, overdue_count, overdue_amount = row
                    
                    writer.writerow([
                        name,
                        phone or "",
                        format_money(current_balance, symbol),
                        format_money(credit_limit or 0, symbol),
                        format_money(credit_sales_balance, symbol),
                        overdue_count,
                        format_money(overdue_amount, symbol)
                    ])
                    
                    total_balance += current_balance
                    total_credit_sales_balance += credit_sales_balance
                    total_overdue_amount += overdue_amount
                
                # Grand totals
                writer.writerow([])
                writer.writerow(["GRAND TOTALS", "", 
                               format_money(total_balance, symbol),
                               "", 
                               format_money(total_credit_sales_balance, symbol),
                               "", 
                               format_money(total_overdue_amount, symbol)])
                writer.writerow([])
                writer.writerow(["=" * 80])
                writer.writerow(["End of Report"])
            
            lang_code = self.get_lang()
            msg = f"Report exported successfully to:\n{file_path}" if lang_code != "my" else f"အစီရင်ခံစာ အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete" if lang_code != "my" else "ထုတ်ယူပြီးပါပြီ", msg)
            
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def showEvent(self, event):
        """Refresh data when dialog becomes visible"""
        self.load_report()
        super().showEvent(event)
