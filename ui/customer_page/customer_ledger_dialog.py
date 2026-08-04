# ui/customer_page/customer_ledger_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QFrame, QComboBox, QWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets.date_range_widget import DateRangeWidget
from ui.widgets.modern_button import ModernButton
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
from loguru import logger
import os


class CustomerLedgerDialog(QDialog):
    """Customer Ledger Dialog - Theme-aware with SVG Icons"""
    
    def __init__(self, customer_id, customer_name, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = customer_name
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle(f"Ledger - {customer_name}")
        self.setMinimumSize(1100, 800)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== TOP ROW: Customer Information Cards (SummaryCardWidget) ==========
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)
        
        # ✅ Customer Name Card with SVG icon
        self.customer_card = SummaryCardWidget(
            title="Customer",
            value=customer_name,
            icon="person",
            color="#3498db",
            icon_is_svg=True
        )
        self.customer_card.set_icon("person", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.customer_card)
        
        # ✅ Current Balance Card with SVG icon
        self.balance_card = SummaryCardWidget(
            title="Current Balance",
            value="Loading...",
            icon="money_off",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.balance_card.set_icon("money_off", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.balance_card)
        
        # ✅ Credit Limit Card with SVG icon
        self.credit_limit_card = SummaryCardWidget(
            title="Credit Limit",
            value="Loading...",
            icon="credit_card",
            color="#9b59b6",
            icon_is_svg=True
        )
        self.credit_limit_card.set_icon("credit_card", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.credit_limit_card)
        
        # ✅ Available Credit Card with SVG icon
        self.available_credit_card = SummaryCardWidget(
            title="Available Credit",
            value="Loading...",
            icon="check_circle",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.available_credit_card.set_icon("check_circle", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.available_credit_card)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # ========== SECOND ROW: Summary Cards (for totals) ==========
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)
        
        # ✅ Total Debit Card with SVG icon
        self.total_debit_card = SummaryCardWidget(
            title="Total Debit",
            value="0",
            icon="trending_up",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.total_debit_card.set_icon("trending_up", is_svg=True, size=(24, 24))
        summary_layout.addWidget(self.total_debit_card)
        
        # ✅ Total Credit Card with SVG icon
        self.total_credit_card = SummaryCardWidget(
            title="Total Credit",
            value="0",
            icon="trending_down",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.total_credit_card.set_icon("trending_down", is_svg=True, size=(24, 24))
        summary_layout.addWidget(self.total_credit_card)
        
        # ✅ Net Balance Card with SVG icon
        self.net_balance_card = SummaryCardWidget(
            title="Net Balance",
            value="0",
            icon="analytics",
            color="#3498db",
            icon_is_svg=True
        )
        self.net_balance_card.set_icon("analytics", is_svg=True, size=(24, 24))
        summary_layout.addWidget(self.net_balance_card)
        
        # ✅ Transaction Count Card with SVG icon
        self.transaction_count_card = SummaryCardWidget(
            title="Transactions",
            value="0",
            icon="receipt_long",
            color="#f39c12",
            icon_is_svg=True
        )
        self.transaction_count_card.set_icon("receipt_long", is_svg=True, size=(24, 24))
        summary_layout.addWidget(self.transaction_count_card)
        
        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # ========== Filter controls ==========
        filter_frame = QFrame()
        filter_frame.setObjectName("filter_frame")
        colors = get_theme_colors()
        filter_frame.setStyleSheet(self._get_filter_frame_style(colors))
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(12)
        filter_layout.setContentsMargins(15, 8, 15, 8)
        
        # Date Range Widget
        date_label = QLabel("📅 Date Range:")
        date_label.setStyleSheet(self._get_label_style())
        filter_layout.addWidget(date_label)
        
        self.date_range_widget = DateRangeWidget(self)
        self.date_range_widget.date_range_changed.connect(self.on_date_range_changed)
        filter_layout.addWidget(self.date_range_widget)
        
        # Type Filter
        type_label = QLabel("📌 Type:")
        type_label.setStyleSheet(self._get_label_style())
        filter_layout.addWidget(type_label)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Credit Sale", "Payment", "Refund", "Adjustment", "Write-off"])
        self.type_filter.currentTextChanged.connect(self.load_ledger)
        self.type_filter.setStyleSheet(self._get_combobox_style(colors))
        filter_layout.addWidget(self.type_filter)
        
        # ✅ Refresh Button with SVG icon
        self.btn_refresh = ModernButton(" Refresh", ModernButton.SECONDARY)
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_refresh.set_compact(True)
        self.btn_refresh.clicked.connect(self.load_ledger)
        filter_layout.addWidget(self.btn_refresh)
        
        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        # ========== Main table ==========
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Reference", "Type", "Description", "Debit", "Credit", "Balance"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # Apply table style
        self._update_table_style(colors)
        
        # Row height
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.verticalHeader().setVisible(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # ========== Buttons ==========
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        # ✅ Print button with SVG icon
        self.btn_print = ModernButton(" Print Report", ModernButton.SECONDARY)
        self.btn_print.set_icon("print", size=(16, 16))
        self.btn_print.set_compact(False)
        self.btn_print.clicked.connect(self.print_report)
        btn_layout.addWidget(self.btn_print)
        
        # ✅ Export button with SVG icon
        self.btn_export = ModernButton(" Export CSV", ModernButton.SECONDARY)
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_export.set_compact(False)
        self.btn_export.clicked.connect(self.export_csv)
        btn_layout.addWidget(self.btn_export)
        
        btn_layout.addStretch()
        
        # ✅ Close button with SVG icon
        self.btn_close = ModernButton(" Close", ModernButton.TERTIARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addWidget(button_frame)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        # Load initial data
        self.load_ledger()
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_ledger()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_print.set_icon("print", size=(16, 16))
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_close.set_icon("close", size=(16, 16))
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update filter frame
        filter_frame = self.findChild(QFrame, "filter_frame")
        if filter_frame:
            filter_frame.setStyleSheet(self._get_filter_frame_style(colors))
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update combobox
        if hasattr(self, 'type_filter'):
            self.type_filter.setStyleSheet(self._get_combobox_style(colors))
        
        # Update table
        self._update_table_style(colors)
        
        # Update summary cards
        for card in [self.customer_card, self.balance_card, self.credit_limit_card, 
                     self.available_credit_card, self.total_debit_card, self.total_credit_card,
                     self.net_balance_card, self.transaction_count_card]:
            if hasattr(card, 'update_theme'):
                card.update_theme()
        
        # Update button icons
        self._update_button_icons()
    
    def _get_label_style(self):
        colors = get_theme_colors()
        return f"color: {colors['text']}; font-size: 10pt; font-weight: 500;"
    
    def _get_filter_frame_style(self, colors):
        return f"""
            QFrame#filter_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
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
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors['text_secondary']};
                margin-right: 8px;
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
                padding: 6px 10px;
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
    
    def _update_table_style(self, colors):
        """Update table style based on theme"""
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
                    padding: 10px 14px;
                    color: #dcddde;
                }
                QTableWidget::item:selected {
                    background-color: #40444b;
                    color: #dcddde;
                }
                QHeaderView::section {
                    background-color: #202225;
                    padding: 10px 14px;
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
                    padding: 10px 14px;
                    color: #212529;
                }
                QTableWidget::item:selected {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 10px 14px;
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
        
        if lang == "my":
            self.setWindowTitle(f"စာရင်း - {self.customer_name}")
            self.btn_refresh.setText(" ပြန်လည်")
            self.btn_print.setText(" ပရင့်ထုတ်မည်")
            self.btn_export.setText(" CSV ထုတ်မည်")
            self.btn_close.setText(" ပိတ်မည်")
            
            # Update summary cards (Top row)
            self.customer_card.set_title("ဝယ်ယူသူ")
            self.balance_card.set_title("လက်ကျန်အကြွေး")
            self.credit_limit_card.set_title("ခရက်ဒစ်ကန့်သတ်")
            self.available_credit_card.set_title("ကျန်ခရက်ဒစ်")
            
            # Update summary cards (Second row)
            self.total_debit_card.set_title("စုစုပေါင်းအကြွေး")
            self.total_credit_card.set_title("စုစုပေါင်းအသွေး")
            self.net_balance_card.set_title("အသားတင်လက်ကျန်")
            self.transaction_count_card.set_title("ငွေပေးချေမှုအရေအတွက်")
            
            self.table.setHorizontalHeaderLabels([
                "ရက်စွဲ", "ကိုးကားအမှတ်", "အမျိုးအစား", 
                "အကြောင်းအရာ", "အကြွေး", "အသွေး", "ကျန်ငွေ"
            ])
            
            # Update filter items
            self.type_filter.setItemText(0, "အားလုံး")
            self.type_filter.setItemText(1, "အကြွေးရောင်း")
            self.type_filter.setItemText(2, "ငွေပေးချေမှု")
            self.type_filter.setItemText(3, "ပြန်အမ်းမှု")
            self.type_filter.setItemText(4, "ချိန်ညှိမှု")
            self.type_filter.setItemText(5, "ရှင်းထုတ်မှု")
            
            # Update date range widget
            self.date_range_widget.retranslateUi("my")
        else:
            self.date_range_widget.retranslateUi("en")
        
        # Update button icons
        self._update_button_icons()
        
        # Apply theme after language change
        self._apply_theme()

    def on_date_range_changed(self, from_date, to_date):
        """Handle date range change from DateRangeWidget"""
        self.load_ledger()

    def load_ledger(self):
        """Load complete ledger with all transaction types"""
        from_date = self.date_range_widget.get_from_date()
        to_date = self.date_range_widget.get_to_date()
        
        symbol = get_currency_symbol()
        type_filter = self.type_filter.currentText()
        lang = self.get_lang()
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Color definitions
        red_color = "#ed4245" if is_dark else "#dc3545"
        green_color = "#3ba55d" if is_dark else "#28a745"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        blue_color = "#5865f2" if is_dark else "#3498db"
        purple_color = "#9b59b6" if is_dark else "#9b59b6"
        text_color = "#dcddde" if is_dark else "#212529"
        
        conn = connect_db()
        cursor = conn.cursor()

        try:
            # Get customer info
            cursor.execute("""
                SELECT current_balance, credit_limit 
                FROM customers WHERE id = ?
            """, (self.customer_id,))
            customer_row = cursor.fetchone()
            current_balance = customer_row[0] if customer_row else 0
            credit_limit = customer_row[1] if customer_row else 0

            # Update Top Row Summary Cards
            self.balance_card.set_value(format_money(current_balance, symbol))
            if current_balance > 0:
                self.balance_card.set_color(red_color)
            else:
                self.balance_card.set_color(green_color)
            
            self.credit_limit_card.set_value(format_money(credit_limit or 0, symbol))
            
            available_credit = (credit_limit or 0) - current_balance
            self.available_credit_card.set_value(format_money(available_credit, symbol))
            if available_credit < 0:
                self.available_credit_card.set_color(red_color)
            else:
                self.available_credit_card.set_color(green_color)

            # Query: Credit Sales
            sales_query = """
                SELECT 
                    cs.sale_date as trans_date,
                    cs.invoice_no as reference,
                    'Credit Sale' as type,
                    cs.total_amount as debit,
                    0 as credit,
                    '' as description,
                    cs.id as transaction_id,
                    'sale' as category
                FROM credit_sales cs
                WHERE cs.customer_id = ?
                  AND cs.sale_date BETWEEN ? AND ?
                  AND COALESCE(cs.status, '') != 'refunded'
            """
            
            # Query: Payments
            payments_query = """
                SELECT 
                    cp.payment_date as trans_date,
                    COALESCE(cp.reference_no, '') as reference,
                    'Payment' as type,
                    0 as debit,
                    cp.amount as credit,
                    COALESCE(cp.note, '') as description,
                    cp.id as transaction_id,
                    'payment' as category
                FROM credit_payments cp
                WHERE cp.customer_id = ?
                  AND cp.payment_date BETWEEN ? AND ?
            """
            
            # Query: Refunds
            refunds_query = """
                SELECT 
                    cs.sale_date as trans_date,
                    cs.invoice_no as reference,
                    'Refund' as type,
                    0 as debit,
                    cs.total_amount as credit,
                    'Refunded sale' as description,
                    cs.id as transaction_id,
                    'refund' as category
                FROM credit_sales cs
                WHERE cs.customer_id = ?
                  AND cs.sale_date BETWEEN ? AND ?
                  AND cs.status = 'refunded'
            """
            
            # Check if adjustments table exists
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='credit_adjustments'")
                has_adjustments = cursor.fetchone() is not None
                
                if has_adjustments:
                    cursor.execute("PRAGMA table_info(credit_adjustments)")
                    adjustment_columns = [col[1] for col in cursor.fetchall()]
                    
                    date_col = 'adjustment_date' if 'adjustment_date' in adjustment_columns else 'created_at' if 'created_at' in adjustment_columns else 'date'
                    ref_col = 'reference_no' if 'reference_no' in adjustment_columns else 'reference' if 'reference' in adjustment_columns else 'id'
                    type_col = 'adjustment_type' if 'adjustment_type' in adjustment_columns else 'type'
                    amount_col = 'amount' if 'amount' in adjustment_columns else 0
                    reason_col = 'reason' if 'reason' in adjustment_columns else 'note' if 'note' in adjustment_columns else 'description'
                    
                    if amount_col != 0 and date_col != 'date':
                        adjustments_query = f"""
                            SELECT 
                                {date_col} as trans_date,
                                {ref_col} as reference,
                                'Adjustment' as type,
                                CASE WHEN {type_col} = 'increase' THEN {amount_col} ELSE 0 END as debit,
                                CASE WHEN {type_col} = 'decrease' THEN {amount_col} ELSE 0 END as credit,
                                {reason_col} as description,
                                id as transaction_id,
                                'adjustment' as category
                            FROM credit_adjustments
                            WHERE customer_id = ?
                              AND {date_col} BETWEEN ? AND ?
                        """
                        has_adjustments = True
                    else:
                        has_adjustments = False
            except:
                has_adjustments = False

            # Check if writeoffs table exists
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='credit_writeoffs'")
                has_writeoffs = cursor.fetchone() is not None
                
                if has_writeoffs:
                    cursor.execute("PRAGMA table_info(credit_writeoffs)")
                    writeoff_columns = [col[1] for col in cursor.fetchall()]
                    
                    date_col = 'writeoff_date' if 'writeoff_date' in writeoff_columns else 'created_at' if 'created_at' in writeoff_columns else 'date'
                    ref_col = 'reference_no' if 'reference_no' in writeoff_columns else 'reference' if 'reference' in writeoff_columns else 'id'
                    amount_col = 'amount' if 'amount' in writeoff_columns else 0
                    reason_col = 'reason' if 'reason' in writeoff_columns else 'note' if 'note' in writeoff_columns else 'description'
                    
                    if amount_col != 0:
                        writeoffs_query = f"""
                            SELECT 
                                {date_col} as trans_date,
                                {ref_col} as reference,
                                'Write-off' as type,
                                0 as debit,
                                {amount_col} as credit,
                                {reason_col} as description,
                                id as transaction_id,
                                'writeoff' as category
                            FROM credit_writeoffs
                            WHERE customer_id = ?
                              AND {date_col} BETWEEN ? AND ?
                        """
                        has_writeoffs = True
                    else:
                        has_writeoffs = False
            except:
                has_writeoffs = False

            # Collect all entries
            entries = []

            # Get sales
            cursor.execute(sales_query, (self.customer_id, from_date, to_date))
            for row in cursor.fetchall():
                entries.append({
                    'date': row[0],
                    'reference': row[1],
                    'type': row[2],
                    'debit': row[3],
                    'credit': row[4],
                    'description': row[5],
                    'transaction_id': row[6],
                    'category': row[7]
                })

            # Get payments
            cursor.execute(payments_query, (self.customer_id, from_date, to_date))
            for row in cursor.fetchall():
                entries.append({
                    'date': row[0],
                    'reference': row[1],
                    'type': row[2],
                    'debit': row[3],
                    'credit': row[4],
                    'description': row[5],
                    'transaction_id': row[6],
                    'category': row[7]
                })

            # Get refunds
            cursor.execute(refunds_query, (self.customer_id, from_date, to_date))
            for row in cursor.fetchall():
                entries.append({
                    'date': row[0],
                    'reference': row[1],
                    'type': row[2],
                    'debit': row[3],
                    'credit': row[4],
                    'description': row[5],
                    'transaction_id': row[6],
                    'category': row[7]
                })

            # Get adjustments
            if has_adjustments:
                cursor.execute(adjustments_query, (self.customer_id, from_date, to_date))
                for row in cursor.fetchall():
                    entries.append({
                        'date': row[0],
                        'reference': row[1],
                        'type': row[2],
                        'debit': row[3],
                        'credit': row[4],
                        'description': row[5] or '',
                        'transaction_id': row[6],
                        'category': row[7]
                    })

            # Get write-offs
            if has_writeoffs:
                cursor.execute(writeoffs_query, (self.customer_id, from_date, to_date))
                for row in cursor.fetchall():
                    entries.append({
                        'date': row[0],
                        'reference': row[1],
                        'type': row[2],
                        'debit': row[3],
                        'credit': row[4],
                        'description': row[5] or '',
                        'transaction_id': row[6],
                        'category': row[7]
                    })

            conn.close()

            # Apply type filter
            if type_filter and type_filter != "All" and type_filter != "အားလုံး":
                entries = [e for e in entries if e['type'] == type_filter]

            # Sort by date
            entries.sort(key=lambda x: (x['date'], x['transaction_id']))

            # Calculate running balance
            starting_balance = self.get_balance_before_date(from_date)
            running_balance = starting_balance

            total_debit = 0
            total_credit = 0

            self.table.setRowCount(0)

            # Add opening balance row
            if starting_balance != 0:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setRowHeight(row, 50)
                
                opening_text = "Opening Balance" if lang != "my" else "အစကျန်ငွေ"
                
                # Date
                date_item = QTableWidgetItem(from_date)
                date_item.setForeground(QColor(text_color))
                self.table.setItem(row, 0, date_item)
                
                # Reference
                ref_item = QTableWidgetItem("-")
                ref_item.setForeground(QColor(text_color))
                self.table.setItem(row, 1, ref_item)
                
                # Type
                type_item = QTableWidgetItem("Opening")
                type_item.setForeground(QColor(text_color))
                self.table.setItem(row, 2, type_item)
                
                # Description
                desc_item = QTableWidgetItem(opening_text)
                desc_item.setForeground(QColor(text_color))
                self.table.setItem(row, 3, desc_item)
                
                if starting_balance > 0:
                    debit_item = QTableWidgetItem(format_money(starting_balance, symbol))
                    debit_item.setForeground(QColor(red_color))
                    self.table.setItem(row, 4, debit_item)
                    
                    credit_item = QTableWidgetItem("0")
                    credit_item.setForeground(QColor(text_color))
                    self.table.setItem(row, 5, credit_item)
                else:
                    debit_item = QTableWidgetItem("0")
                    debit_item.setForeground(QColor(text_color))
                    self.table.setItem(row, 4, debit_item)
                    
                    credit_item = QTableWidgetItem(format_money(abs(starting_balance), symbol))
                    credit_item.setForeground(QColor(green_color))
                    self.table.setItem(row, 5, credit_item)
                
                balance_item = QTableWidgetItem(format_money(starting_balance, symbol))
                if starting_balance > 0:
                    balance_item.setForeground(QColor(red_color))
                elif starting_balance < 0:
                    balance_item.setForeground(QColor(green_color))
                else:
                    balance_item.setForeground(QColor(text_color))
                self.table.setItem(row, 6, balance_item)

            # Populate transactions
            for entry in entries:
                running_balance += entry['debit'] - entry['credit']
                total_debit += entry['debit']
                total_credit += entry['credit']

                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setRowHeight(row, 50)

                # Date
                date_item = QTableWidgetItem(entry['date'])
                date_item.setForeground(QColor(text_color))
                self.table.setItem(row, 0, date_item)
                
                # Reference
                ref_item = QTableWidgetItem(entry['reference'])
                ref_item.setForeground(QColor(text_color))
                if entry['reference']:
                    ref_item.setToolTip(f"ID: {entry['transaction_id']}")
                self.table.setItem(row, 1, ref_item)
                
                # Type with color coding
                type_item = QTableWidgetItem(entry['type'])
                if entry['type'] in ['Credit Sale', 'အကြွေးရောင်း']:
                    type_item.setForeground(QColor(red_color))
                elif entry['type'] in ['Payment', 'ငွေပေးချေမှု']:
                    type_item.setForeground(QColor(green_color))
                elif entry['type'] in ['Refund', 'ပြန်အမ်းမှု']:
                    type_item.setForeground(QColor(orange_color))
                elif entry['type'] in ['Adjustment', 'ချိန်ညှိမှု']:
                    type_item.setForeground(QColor(blue_color))
                elif entry['type'] in ['Write-off', 'ရှင်းထုတ်မှု']:
                    type_item.setForeground(QColor(purple_color))
                self.table.setItem(row, 2, type_item)
                
                # Description
                desc_item = QTableWidgetItem(entry.get('description', ''))
                desc_item.setForeground(QColor(text_color))
                self.table.setItem(row, 3, desc_item)
                
                # Debit
                debit_item = QTableWidgetItem(format_money(entry['debit'], symbol))
                if entry['debit'] > 0:
                    debit_item.setForeground(QColor(red_color))
                else:
                    debit_item.setForeground(QColor(text_color))
                self.table.setItem(row, 4, debit_item)
                
                # Credit
                credit_item = QTableWidgetItem(format_money(entry['credit'], symbol))
                if entry['credit'] > 0:
                    credit_item.setForeground(QColor(green_color))
                else:
                    credit_item.setForeground(QColor(text_color))
                self.table.setItem(row, 5, credit_item)
                
                # Balance
                balance_item = QTableWidgetItem(format_money(running_balance, symbol))
                if running_balance > 0:
                    balance_item.setForeground(QColor(red_color))
                elif running_balance < 0:
                    balance_item.setForeground(QColor(green_color))
                else:
                    balance_item.setForeground(QColor(text_color))
                self.table.setItem(row, 6, balance_item)

            # Update Second Row Summary Cards with totals
            self.total_debit_card.set_value(format_money(total_debit, symbol))
            self.total_credit_card.set_value(format_money(total_credit, symbol))
            
            net_balance = total_debit - total_credit
            self.net_balance_card.set_value(format_money(net_balance, symbol))
            if net_balance > 0:
                self.net_balance_card.set_color(red_color)
            elif net_balance < 0:
                self.net_balance_card.set_color(green_color)
            else:
                self.net_balance_card.set_color(blue_color)
            
            self.transaction_count_card.set_value(str(len(entries)))

            self.table.resizeColumnsToContents()

        except Exception as e:
            conn.close()
            logger.error(f"Error loading ledger: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load ledger: {e}")

    def get_balance_before_date(self, date):
        """Get customer balance before a specific date"""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COALESCE(SUM(balance_amount), 0)
                FROM credit_sales
                WHERE customer_id = ?
                  AND sale_date < ?
                  AND COALESCE(status, '') != 'refunded'
            """, (self.customer_id, date))
            balance = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM credit_payments cp
                JOIN credit_sales cs ON cp.credit_sale_id = cs.id
                WHERE cp.customer_id = ?
                  AND cp.payment_date < ?
                  AND COALESCE(cs.status, '') != 'refunded'
            """, (self.customer_id, date))
            payments = cursor.fetchone()[0]
            
            conn.close()
            return balance - payments
            
        except Exception as e:
            conn.close()
            logger.error(f"Error getting balance before date: {e}")
            return 0

    def export_csv(self):
        """Export ledger to CSV"""
        from PyQt6.QtWidgets import QFileDialog
        import csv
        
        if self.table.rowCount() == 0:
            lang = self.get_lang()
            msg = "No ledger entries to export." if lang != "my" else "ထုတ်ယူရန် စာရင်းမရှိပါ။"
            QMessageBox.warning(self, "No Data" if lang != "my" else "ဒေတာမရှိ", msg)
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", 
            f"ledger_{self.customer_name}_{datetime.now().strftime('%Y%m%d')}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            symbol = get_currency_symbol()
            lang = self.get_lang()
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                writer.writerow(["=" * 80])
                writer.writerow([f"CUSTOMER LEDGER - {self.customer_name}"])
                writer.writerow(["=" * 80])
                writer.writerow([])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Period:", f"{self.date_range_widget.get_from_date()} to {self.date_range_widget.get_to_date()}"])
                writer.writerow([])
                
                # Summary from top row cards
                writer.writerow(["CUSTOMER SUMMARY"])
                writer.writerow(["-" * 40])
                writer.writerow([f"Current Balance: {self.balance_card._value}"])
                writer.writerow([f"Credit Limit: {self.credit_limit_card._value}"])
                writer.writerow([f"Available Credit: {self.available_credit_card._value}"])
                writer.writerow([])
                
                # Summary from second row cards
                writer.writerow(["TRANSACTION SUMMARY"])
                writer.writerow(["-" * 40])
                writer.writerow([f"Total Debit: {self.total_debit_card._value}"])
                writer.writerow([f"Total Credit: {self.total_credit_card._value}"])
                writer.writerow([f"Net Balance: {self.net_balance_card._value}"])
                writer.writerow([f"Transactions: {self.transaction_count_card._value}"])
                writer.writerow([])
                
                # Column headers
                headers = ["Date", "Reference", "Type", "Description", "Debit", "Credit", "Balance"]
                writer.writerow(headers)
                writer.writerow(["-" * 80])
                
                # Data
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
                
                writer.writerow([])
                writer.writerow(["=" * 80])
                writer.writerow(["End of Report"])
            
            lang = self.get_lang()
            msg = f"CSV exported to:\n{file_path}" if lang != "my" else f"CSV ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete" if lang != "my" else "ထုတ်ယူပြီးပါပြီ", msg)
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def print_report(self):
        """Print ledger as PDF"""
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QPageLayout, QPageSize
        from PyQt6.QtWidgets import QFileDialog

        if self.table.rowCount() == 0:
            lang = self.get_lang()
            msg = "No ledger entries to print." if lang != "my" else "ပရင့်ထုတ်ရန် စာရင်းမရှိပါ။"
            QMessageBox.warning(self, "No Data" if lang != "my" else "ဒေတာမရှိ", msg)
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", 
            f"ledger_{self.customer_name}_{datetime.now().strftime('%Y%m%d')}.pdf", 
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Error", "Could not start PDF generation.")
            return

        try:
            font = QFont("Arial", 8)
            painter.setFont(font)
            fm = QFontMetrics(font)
            
            headers = ["Date", "Reference", "Type", "Description", "Debit", "Credit", "Balance"]
            col_widths = [90, 110, 90, 150, 100, 100, 100]
            
            y = 30
            x = 20
            row_height = fm.height() + 4

            # Title
            title_font = QFont("Arial", 14, QFont.Weight.Bold)
            painter.setFont(title_font)
            painter.drawText(20, y, f"Customer Ledger - {self.customer_name}")
            y += 30
            
            # Summary - Top row
            summary_font = QFont("Arial", 10)
            painter.setFont(summary_font)
            from_date = self.date_range_widget.get_from_date()
            to_date = self.date_range_widget.get_to_date()
            painter.drawText(20, y, f"Period: {from_date} to {to_date}")
            y += 20
            painter.drawText(20, y, f"Current Balance: {self.balance_card._value}")
            y += 20
            painter.drawText(20, y, f"Credit Limit: {self.credit_limit_card._value}")
            y += 20
            painter.drawText(20, y, f"Available Credit: {self.available_credit_card._value}")
            y += 25
            
            # Summary - Second row
            painter.drawText(20, y, f"Total Debit: {self.total_debit_card._value}")
            y += 20
            painter.drawText(20, y, f"Total Credit: {self.total_credit_card._value}")
            y += 20
            painter.drawText(20, y, f"Net Balance: {self.net_balance_card._value}")
            y += 20
            painter.drawText(20, y, f"Transactions: {self.transaction_count_card._value}")
            y += 25

            # Column headers
            painter.setFont(font)
            for i, header in enumerate(headers):
                painter.drawText(x, y, col_widths[i], row_height, 
                                Qt.AlignmentFlag.AlignLeft, header)
                x += col_widths[i]
            
            y += row_height
            x = 20

            # Data rows
            for row in range(self.table.rowCount()):
                if y + row_height > printer.height() - 50:
                    printer.newPage()
                    y = 30
                    for i, header in enumerate(headers):
                        painter.drawText(x, y, col_widths[i], row_height, 
                                        Qt.AlignmentFlag.AlignLeft, header)
                        x += col_widths[i]
                    y += row_height
                    x = 20

                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    text = item.text() if item else ""
                    painter.drawText(x, y, col_widths[col], row_height, 
                                    Qt.AlignmentFlag.AlignLeft, text)
                    x += col_widths[col]
                y += row_height
                x = 20

            painter.end()
            lang = self.get_lang()
            msg = f"PDF saved to:\n{file_path}" if lang != "my" else f"PDF သိမ်းဆည်းပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete" if lang != "my" else "သိမ်းဆည်းပြီးပါပြီ", msg)
            
        except Exception as e:
            painter.end()
            logger.error(f"PDF export failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"Failed to generate PDF: {e}")

    def showEvent(self, event):
        """Refresh data when dialog becomes visible"""
        self.load_ledger()
        super().showEvent(event)