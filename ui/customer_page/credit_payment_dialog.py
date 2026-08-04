# ui/customer_page/credit_payment_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton,
    QMessageBox, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QFrame, QGridLayout, QWidget
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from services.credit_service import CreditService
from ui.widgets.modern_button import ModernButton
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
from loguru import logger
import os


class CreditPaymentDialog(QDialog):
    """Credit Payment Dialog - Theme-aware with SVG Icons"""
    
    def __init__(self, customer_id, customer_name, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.selected_credit_sale_id = None
        self.credit_service = CreditService()
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle(f"Payment Collection - {customer_name}")
        self.setMinimumSize(950, 700)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== Customer Information Cards (SummaryCardWidget) - 4 Cards in a Row ==========
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
        self.current_balance_card = SummaryCardWidget(
            title="Current Balance",
            value="Loading...",
            icon="money_off",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.current_balance_card.set_icon("money_off", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.current_balance_card)
        
        # ✅ Total Outstanding Card with SVG icon
        self.total_outstanding_card = SummaryCardWidget(
            title="Total Outstanding",
            value="Loading...",
            icon="receipt_long",
            color="#f39c12",
            icon_is_svg=True
        )
        self.total_outstanding_card.set_icon("receipt_long", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.total_outstanding_card)
        
        # ✅ Payment Amount Card with SVG icon
        self.payment_amount_card = SummaryCardWidget(
            title="Payment Amount",
            value="0",
            icon="payments",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.payment_amount_card.set_icon("payments", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.payment_amount_card)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # ========== 2-Column Layout: LEFT = Payment Form, RIGHT = Invoice Table ==========
        two_col_layout = QHBoxLayout()
        two_col_layout.setSpacing(15)
        
        # ========== LEFT COLUMN: Payment Details (Form) ==========
        left_column = QVBoxLayout()
        left_column.setSpacing(0)
        
        payment_group = QGroupBox("💳 Payment Details")
        colors = get_theme_colors()
        payment_group.setStyleSheet(self._get_groupbox_style(colors))
        
        payment_layout = QFormLayout()
        payment_layout.setVerticalSpacing(14)
        payment_layout.setHorizontalSpacing(15)
        payment_layout.setContentsMargins(15, 15, 15, 15)

        # Amount
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 99999999)
        self.amount_input.setDecimals(0)
        symbol = get_currency_symbol()
        self.amount_input.setPrefix(f"{symbol} ")
        self.amount_input.valueChanged.connect(self.update_payment_amount_card)
        self.amount_input.setStyleSheet(self._get_spinbox_style(colors))
        payment_layout.addRow(self._create_label("💰 Payment Amount:"), self.amount_input)

        # Payment Date
        self.payment_date = QDateEdit()
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setStyleSheet(self._get_date_style(colors))
        self.payment_date.setDisplayFormat("yyyy-MM-dd")
        payment_layout.addRow(self._create_label("📅 Payment Date:"), self.payment_date)

        # Payment Method
        self.payment_method = QComboBox()
        self.payment_method.addItems(["Cash", "KBZPay", "WavePay", "Bank Transfer"])
        self.payment_method.setStyleSheet(self._get_combobox_style(colors))
        payment_layout.addRow(self._create_label("🏦 Payment Method:"), self.payment_method)

        # Reference No
        self.reference_no = QLineEdit()
        self.reference_no.setPlaceholderText("Transaction reference (optional)")
        self.reference_no.setStyleSheet(self._get_line_edit_style(colors))
        payment_layout.addRow(self._create_label("🔖 Reference No:"), self.reference_no)

        # Note
        self.note = QTextEdit()
        self.note.setMaximumHeight(80)
        self.note.setPlaceholderText("Payment note (optional)")
        self.note.setStyleSheet(self._get_text_edit_style(colors))
        payment_layout.addRow(self._create_label("📝 Note:"), self.note)
        
        # Selected Invoice Info
        self.selected_invoice_label = QLabel("No invoice selected")
        self.selected_invoice_label.setStyleSheet(self._get_selected_invoice_style(colors))
        payment_layout.addRow(self._create_label("📌 Selected Invoice:"), self.selected_invoice_label)

        payment_group.setLayout(payment_layout)
        left_column.addWidget(payment_group)
        
        # ========== RIGHT COLUMN: Outstanding Invoices (Table) ==========
        right_column = QVBoxLayout()
        right_column.setSpacing(0)
        
        invoice_group = QGroupBox("📋 Outstanding Invoices")
        invoice_group.setStyleSheet(self._get_groupbox_style(colors))
        
        invoice_layout = QVBoxLayout()
        
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(5)
        self.invoice_table.setHorizontalHeaderLabels(["ID", "Invoice No", "Date", "Due Date", "Balance"])
        self.invoice_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.invoice_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.invoice_table.cellClicked.connect(self.select_invoice)
        self.invoice_table.setColumnHidden(0, True)
        self.invoice_table.setAlternatingRowColors(True)
        
        # Apply table style
        self._update_table_style(colors)
        
        # Row height
        self.invoice_table.verticalHeader().setDefaultSectionSize(45)
        self.invoice_table.verticalHeader().setVisible(False)
        
        header = self.invoice_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        invoice_layout.addWidget(self.invoice_table)
        invoice_group.setLayout(invoice_layout)
        right_column.addWidget(invoice_group)
        
        # Add left and right columns to the 2-column layout
        two_col_layout.addLayout(left_column, 1)
        two_col_layout.addLayout(right_column, 2)
        
        layout.addLayout(two_col_layout)

        # ========== Buttons ==========
        btn_frame = QFrame()
        btn_frame.setObjectName("button_frame")
        btn_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        # Total outstanding summary
        self.total_summary_label = QLabel("Total Outstanding: 0")
        self.total_summary_label.setStyleSheet(self._get_summary_label_style(colors))
        btn_layout.addWidget(self.total_summary_label)
        
        btn_layout.addStretch()
        
        # ✅ Record Payment button with SVG icon
        self.btn_pay = ModernButton("", ModernButton.PRIMARY)
        self.btn_pay.set_icon("payments", size=(16, 16))
        self.btn_pay.set_compact(False)
        self.btn_pay.clicked.connect(self.record_payment)
        
        # ✅ Cancel button with SVG icon
        self.btn_cancel = ModernButton("", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_cancel.set_compact(False)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_pay)
        layout.addWidget(btn_frame)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        self.load_customer_info()
        self.load_outstanding_invoices()
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_outstanding_invoices()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_pay.set_icon("payments", size=(16, 16))
        self.btn_cancel.set_icon("close", size=(16, 16))
    
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
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update input widgets
        self.amount_input.setStyleSheet(self._get_spinbox_style(colors))
        self.payment_date.setStyleSheet(self._get_date_style(colors))
        self.payment_method.setStyleSheet(self._get_combobox_style(colors))
        self.reference_no.setStyleSheet(self._get_line_edit_style(colors))
        self.note.setStyleSheet(self._get_text_edit_style(colors))
        self.selected_invoice_label.setStyleSheet(self._get_selected_invoice_style(colors))
        
        # Update table
        self._update_table_style(colors)
        
        # Update summary label
        self.total_summary_label.setStyleSheet(self._get_summary_label_style(colors))
        
        # Update summary cards (they are theme-aware)
        if hasattr(self, 'customer_card'):
            self.customer_card.update_theme()
        if hasattr(self, 'current_balance_card'):
            self.current_balance_card.update_theme()
        if hasattr(self, 'total_outstanding_card'):
            self.total_outstanding_card.update_theme()
        if hasattr(self, 'payment_amount_card'):
            self.payment_amount_card.update_theme()
        
        # Update button icons
        self._update_button_icons()
    
    def _get_label_style(self):
        colors = get_theme_colors()
        return f"font-weight: 600; color: {colors['text']}; font-size: 10pt;"
    
    def _create_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(self._get_label_style())
        return label
    
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
    
    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _get_line_edit_style(self, colors):
        return f"""
            QLineEdit {{
                padding: 10px 14px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 11pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """
    
    def _get_spinbox_style(self, colors):
        return f"""
            QDoubleSpinBox {{
                padding: 10px 14px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 11pt;
            }}
            QDoubleSpinBox:focus {{
                border-color: #5865f2;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 16px;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 2px;
            }}
        """
    
    def _get_date_style(self, colors):
        return f"""
            QDateEdit {{
                padding: 10px 14px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 11pt;
            }}
            QDateEdit:focus {{
                border-color: #5865f2;
            }}
        """
    
    def _get_combobox_style(self, colors):
        return f"""
            QComboBox {{
                padding: 10px 14px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 11pt;
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
    
    def _get_text_edit_style(self, colors):
        return f"""
            QTextEdit {{
                padding: 10px 14px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 11pt;
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
            }}
        """
    
    def _get_selected_invoice_style(self, colors):
        return f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 10pt;
                padding: 6px 10px;
                background: {colors['bg_hover']};
                border-radius: 4px;
                border: 1px dashed {colors['border']};
            }}
        """
    
    def _get_summary_label_style(self, colors):
        is_dark = is_dark_theme()
        if is_dark:
            return f"""
                QLabel {{
                    font-weight: 600;
                    font-size: 11pt;
                    color: #ed4245;
                    padding: 4px 8px;
                    background: transparent;
                }}
            """
        else:
            return f"""
                QLabel {{
                    font-weight: 600;
                    font-size: 11pt;
                    color: #e74c3c;
                    padding: 4px 8px;
                    background: transparent;
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
                    padding: 8px 14px;
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
                    padding: 8px 14px;
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
        
        self.invoice_table.setStyleSheet(table_style)

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
            self.setWindowTitle(f"ငွေပေးချေမှု ကောက်ခံခြင်း - {self.customer_name}")
            self.btn_pay.setText(" ငွေပေးချေမှု မှတ်တမ်းတင်ရန်")
            self.btn_cancel.setText(" ပိတ်မည်")
            
            # Update card titles
            self.customer_card.set_title("ဝယ်ယူသူ")
            self.current_balance_card.set_title("လက်ကျန်အကြွေး")
            self.total_outstanding_card.set_title("စုစုပေါင်းကျန်ငွေ")
            self.payment_amount_card.set_title("ပေးချေမည့်ငွေ")
            
            self.total_summary_label.setText("စုစုပေါင်းကျန်ငွေ: 0")
        else:
            self.setWindowTitle(f"Payment Collection - {self.customer_name}")
            self.btn_pay.setText(" Record Payment")
            self.btn_cancel.setText(" Close")
            
            self.total_summary_label.setText("Total Outstanding: 0")
        
        # Update button icons
        self._update_button_icons()
        
        # Update label styles after language change
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Apply theme after language change
        self._apply_theme()

    def update_payment_amount_card(self, value):
        """Update payment amount card when amount changes"""
        symbol = get_currency_symbol()
        self.payment_amount_card.set_value(format_money(value, symbol))
        if value > 0:
            self.payment_amount_card.set_color("#2ecc71")
        else:
            self.payment_amount_card.set_color("#95a5a6")

    def load_customer_info(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT current_balance FROM customers WHERE id = ?", (self.customer_id,))
        row = cursor.fetchone()
        conn.close()
        
        symbol = get_currency_symbol()
        balance = row[0] if row else 0
        
        # Update cards
        self.current_balance_card.set_value(format_money(balance, symbol))
        if balance > 0:
            self.current_balance_card.set_color("#e74c3c")
        else:
            self.current_balance_card.set_color("#2ecc71")
        
        # Set max amount
        self.amount_input.setMaximum(balance)
        
        # Set payment amount card initial value
        self.payment_amount_card.set_value("0")
        self.payment_amount_card.set_color("#95a5a6")

    def load_outstanding_invoices(self):
        """Load outstanding invoices ordered by due date (oldest first)"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, invoice_no, sale_date, due_date, balance_amount
            FROM credit_sales
            WHERE customer_id = ? AND balance_amount > 0
            ORDER BY due_date ASC, sale_date ASC
        """, (self.customer_id,))
        rows = cursor.fetchall()
        conn.close()
        
        symbol = get_currency_symbol()
        total_outstanding = 0
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        red_color = "#ed4245" if is_dark else "#dc3545"
        green_color = "#3ba55d" if is_dark else "#28a745"
        
        self.invoice_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.invoice_table.setRowHeight(i, 45)
            
            # ID (hidden)
            id_item = QTableWidgetItem(str(row[0]))
            id_item.setForeground(QColor(text_color))
            self.invoice_table.setItem(i, 0, id_item)
            
            # Invoice No
            inv_item = QTableWidgetItem(row[1])
            inv_item.setForeground(QColor(text_color))
            self.invoice_table.setItem(i, 1, inv_item)
            
            # Date
            date_item = QTableWidgetItem(row[2])
            date_item.setForeground(QColor(text_color))
            self.invoice_table.setItem(i, 2, date_item)
            
            # Due Date
            due_date_item = QTableWidgetItem(row[3] or "")
            due_date_item.setForeground(QColor(text_color))
            if row[3]:
                due_date = QDate.fromString(row[3], "yyyy-MM-dd")
                today = QDate.currentDate()
                if due_date < today:
                    due_date_item.setForeground(QColor(red_color))
            self.invoice_table.setItem(i, 3, due_date_item)
            
            # Balance
            balance_item = QTableWidgetItem(format_money(row[4], symbol))
            if row[4] > 0:
                balance_item.setForeground(QColor(red_color))
            else:
                balance_item.setForeground(QColor(green_color))
            self.invoice_table.setItem(i, 4, balance_item)
            
            total_outstanding += row[4]
        
        # Update total outstanding cards
        self.total_outstanding_card.set_value(format_money(total_outstanding, symbol))
        self.total_summary_label.setText(f"Total Outstanding: {format_money(total_outstanding, symbol)}")
        
        if total_outstanding > 0:
            self.total_outstanding_card.set_color("#f39c12")
            self.total_summary_label.setStyleSheet(self._get_summary_label_style(colors))
        else:
            self.total_outstanding_card.set_color("#2ecc71")
            self.total_summary_label.setStyleSheet(f"""
                QLabel {{
                    font-weight: 600;
                    font-size: 11pt;
                    color: {green_color};
                    padding: 4px 8px;
                    background: transparent;
                }}
            """)

    def select_invoice(self, row, col):
        id_item = self.invoice_table.item(row, 0)
        if id_item:
            self.selected_credit_sale_id = int(id_item.text())
            balance_item = self.invoice_table.item(row, 4)
            invoice_no_item = self.invoice_table.item(row, 1)
            
            if balance_item and invoice_no_item:
                symbol = get_currency_symbol()
                balance_text = balance_item.text().replace(symbol, "").replace(",", "").strip()
                try:
                    balance = float(balance_text)
                    self.amount_input.setMaximum(balance)
                    self.amount_input.setValue(balance)
                    self.invoice_table.selectRow(row)
                    colors = get_theme_colors()
                    self.selected_invoice_label.setText(f"{invoice_no_item.text()} - {format_money(balance, symbol)}")
                    self.selected_invoice_label.setStyleSheet(f"""
                        QLabel {{
                            color: {colors['text']};
                            font-weight: 600;
                            font-size: 10pt;
                            padding: 6px 10px;
                            background: {colors['bg_hover']};
                            border-radius: 4px;
                            border: 1px solid #5865f2;
                        }}
                    """)
                except:
                    pass

    def record_payment(self):
        amount = self.amount_input.value()
        lang = self.get_lang()
        
        if amount <= 0:
            if lang == "my":
                msg = "ငွေပေးချေမှုပမာဏ ထည့်သွင်းပေးပါ။"
            else:
                msg = "Please enter a valid payment amount."
            QMessageBox.warning(self, "Error", msg)
            return
        
        if self.selected_credit_sale_id:
            self.record_payment_to_invoice()
        else:
            if lang == "my":
                msg = "ပြေစာမရွေးချယ်ထားပါ။ ငွေပေးချေမှုကို စုစုပေါင်းကျန်ငွေမှ လျှော့ချမည်လား?"
            else:
                msg = "No invoice selected. The payment will be applied to the total outstanding balance. Continue?"
            
            reply = QMessageBox.question(
                self, 
                "Confirm" if lang != "my" else "အတည်ပြုပါ", 
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.record_general_payment()

    def record_payment_to_invoice(self):
        """Record payment to a specific invoice using CreditService"""
        payment_amount = self.amount_input.value()
        payment_date = self.payment_date.date().toString("yyyy-MM-dd")
        payment_method = self.payment_method.currentText()
        reference_no = self.reference_no.text()
        note = self.note.toPlainText()
        
        result = self.credit_service.record_credit_payment(
            customer_id=self.customer_id,
            amount=payment_amount,
            credit_sale_id=self.selected_credit_sale_id,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_no=reference_no,
            note=note,
            auto_allocate=False
        )
        
        if result.get('success'):
            lang = self.get_lang()
            msg = "Payment recorded successfully!" if lang != "my" else "ငွေပေးချေမှု အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ။"
            QMessageBox.information(self, "Success", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to record payment: {result.get('error', 'Unknown error')}")

    def record_general_payment(self):
        """Record general payment (auto-allocate to oldest invoices) using CreditService"""
        payment_amount = self.amount_input.value()
        payment_date = self.payment_date.date().toString("yyyy-MM-dd")
        payment_method = self.payment_method.currentText()
        reference_no = self.reference_no.text()
        note = self.note.toPlainText()
        
        result = self.credit_service.record_credit_payment(
            customer_id=self.customer_id,
            amount=payment_amount,
            credit_sale_id=None,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_no=reference_no,
            note=note,
            auto_allocate=True
        )
        
        if result.get('success'):
            total_applied = result.get('total_allocated', 0)
            unallocated = result.get('unallocated', 0)
            
            lang = self.get_lang()
            symbol = get_currency_symbol()
            
            if lang == "my":
                msg = (f"ငွေပေးချေမှု အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ။\n"
                       f"လျှော့ချငွေ: {format_money(total_applied, symbol)}\n"
                       f"ကျန်ငွေ: {format_money(unallocated, symbol)}")
            else:
                msg = (f"Payment recorded successfully!\n"
                       f"Applied: {format_money(total_applied, symbol)}\n"
                       f"Unallocated: {format_money(unallocated, symbol)}")
            
            QMessageBox.information(self, "Success", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to record payment: {result.get('error', 'Unknown error')}")

    def showEvent(self, event):
        """Refresh data when dialog becomes visible"""
        self.load_customer_info()
        self.load_outstanding_invoices()
        super().showEvent(event)