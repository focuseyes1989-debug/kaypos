# ui/customer_page/credit_sale_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton,
    QMessageBox, QComboBox, QGroupBox, QFrame, QWidget
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


class CreditSaleDialog(QDialog):
    """Credit Sale Dialog - Theme-aware with SVG Icons"""
    
    def __init__(self, customer_id=None, customer_name=None, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.credit_service = CreditService()
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle(f"Credit Sale - {customer_name}" if customer_name else "Credit Sale")
        self.setMinimumWidth(650)
        self.setMinimumHeight(600)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== Customer Information Cards (SummaryCardWidget) with SVG Icons ==========
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)
        
        # ✅ Customer Name Card with SVG icon
        self.customer_card = SummaryCardWidget(
            title="Customer",
            value=customer_name if customer_name else "Not Selected",
            icon="person",
            color="#3498db",
            icon_is_svg=True
        )
        self.customer_card.set_icon("person", is_svg=True, size=(24, 24))
        info_layout.addWidget(self.customer_card)
        
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

        # ========== Sale Details Group ==========
        sale_group = QGroupBox("Sale Details")
        colors = get_theme_colors()
        sale_group.setStyleSheet(self._get_groupbox_style(colors))
        
        sale_layout = QFormLayout()
        sale_layout.setVerticalSpacing(12)
        sale_layout.setHorizontalSpacing(15)

        # Invoice No (auto-generated)
        self.invoice_no = QLineEdit()
        self.invoice_no.setReadOnly(True)
        self.invoice_no.setText(f"CR-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.invoice_no.setStyleSheet(self._get_readonly_style(colors))
        sale_layout.addRow(self._create_label("Invoice No:"), self.invoice_no)

        # Total Amount
        self.total_amount = QDoubleSpinBox()
        self.total_amount.setRange(0, 99999999)
        self.total_amount.setDecimals(0)
        symbol = get_currency_symbol()
        self.total_amount.setPrefix(f"{symbol} ")
        self.total_amount.valueChanged.connect(self.update_balance)
        self.total_amount.setStyleSheet(self._get_spinbox_style(colors))
        sale_layout.addRow(self._create_label("Total Amount:"), self.total_amount)

        # Paid Amount (Partial payment)
        self.paid_amount = QDoubleSpinBox()
        self.paid_amount.setRange(0, 99999999)
        self.paid_amount.setDecimals(0)
        self.paid_amount.setPrefix(f"{symbol} ")
        self.paid_amount.valueChanged.connect(self.update_balance)
        self.paid_amount.setStyleSheet(self._get_spinbox_style(colors))
        sale_layout.addRow(self._create_label("Paid Today:"), self.paid_amount)

        # Balance Due
        balance_layout = QHBoxLayout()
        balance_label = self._create_label("Balance Due:")
        balance_label.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {colors['text']};")
        balance_layout.addWidget(balance_label)
        
        self.balance_amount = QLabel("0")
        self.balance_amount.setStyleSheet(self._get_balance_style(0, colors))
        balance_layout.addWidget(self.balance_amount)
        balance_layout.addStretch()
        sale_layout.addRow(balance_layout)

        # Sale Date
        self.sale_date = QDateEdit()
        self.sale_date.setCalendarPopup(True)
        self.sale_date.setDate(QDate.currentDate())
        self.sale_date.setStyleSheet(self._get_date_style(colors))
        self.sale_date.setDisplayFormat("yyyy-MM-dd")
        sale_layout.addRow(self._create_label("Sale Date:"), self.sale_date)

        # Due Date
        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        
        try:
            settings = self.credit_service.get_credit_settings()
            due_days = settings.get('credit_due_days', 15)
        except:
            due_days = 15
        
        self.due_date.setDate(QDate.currentDate().addDays(due_days))
        self.due_date.setStyleSheet(self._get_date_style(colors))
        self.due_date.setDisplayFormat("yyyy-MM-dd")
        sale_layout.addRow(self._create_label("Due Date:"), self.due_date)

        # Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setStyleSheet(self._get_text_edit_style(colors))
        sale_layout.addRow(self._create_label("Notes:"), self.notes)

        sale_group.setLayout(sale_layout)
        layout.addWidget(sale_group)

        # ========== Buttons ==========
        btn_frame = QFrame()
        btn_frame.setObjectName("button_frame")
        btn_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        # ✅ Save button with SVG icon
        self.btn_save = ModernButton("", ModernButton.PRIMARY)
        self.btn_save.set_icon("save", size=(16, 16))
        self.btn_save.set_compact(False)
        self.btn_save.clicked.connect(self.save_credit_sale)
        
        # ✅ Cancel button with SVG icon
        self.btn_cancel = ModernButton("", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_cancel.set_compact(False)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addWidget(btn_frame)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        self.load_customer_info()
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_customer_info()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_save.set_icon("save", size=(16, 16))
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
        
        # Update groupbox
        sale_group = self.findChild(QGroupBox)
        if sale_group:
            sale_group.setStyleSheet(self._get_groupbox_style(colors))
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update input widgets
        self.invoice_no.setStyleSheet(self._get_readonly_style(colors))
        self.total_amount.setStyleSheet(self._get_spinbox_style(colors))
        self.paid_amount.setStyleSheet(self._get_spinbox_style(colors))
        self.sale_date.setStyleSheet(self._get_date_style(colors))
        self.due_date.setStyleSheet(self._get_date_style(colors))
        self.notes.setStyleSheet(self._get_text_edit_style(colors))
        
        # Update balance label
        balance = self.total_amount.value() - self.paid_amount.value()
        self.balance_amount.setStyleSheet(self._get_balance_style(balance, colors))
        
        # Update summary cards
        if hasattr(self, 'customer_card'):
            self.customer_card.update_theme()
        if hasattr(self, 'credit_limit_card'):
            self.credit_limit_card.update_theme()
        if hasattr(self, 'current_balance_card'):
            self.current_balance_card.update_theme()
        if hasattr(self, 'available_credit_card'):
            self.available_credit_card.update_theme()
        
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
    
    def _get_readonly_style(self, colors):
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['bg_hover']};
                font-size: 10pt;
                color: {colors['text']};
            }}
        """
    
    def _get_spinbox_style(self, colors):
        return f"""
            QDoubleSpinBox {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
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
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QDateEdit:focus {{
                border-color: #5865f2;
            }}
        """
    
    def _get_text_edit_style(self, colors):
        return f"""
            QTextEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
            }}
        """
    
    def _get_balance_style(self, balance, colors):
        is_dark = is_dark_theme()
        if balance > 0:
            color = "#ed4245" if is_dark else "#e74c3c"
        else:
            color = "#3ba55d" if is_dark else "#27ae60"
        return f"font-weight: bold; color: {color}; font-size: 14pt; padding: 4px 8px; background: transparent;"

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
        
        if lang == "my":
            self.setWindowTitle(f"အကြွေးရောင်းချမှု - {self.customer_name}" if self.customer_name else "အကြွေးရောင်းချမှု")
            self.btn_save.setText(" သိမ်းဆည်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့")
            
            # Update card titles
            self.customer_card.set_title("ဝယ်ယူသူ")
            self.credit_limit_card.set_title("ခရက်ဒစ်ကန့်သတ်")
            self.current_balance_card.set_title("လက်ကျန်အကြွေး")
            self.available_credit_card.set_title("ကျန်ခရက်ဒစ်")
        else:
            self.setWindowTitle(f"Credit Sale - {self.customer_name}" if self.customer_name else "Credit Sale")
            self.btn_save.setText(" Save Credit Sale")
            self.btn_cancel.setText(" Cancel")
        
        # Update button icons
        self._update_button_icons()
        
        # Update label styles after language change
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Apply theme after language change
        self._apply_theme()

    def load_customer_info(self):
        if not self.customer_id:
            symbol = get_currency_symbol()
            self.credit_limit_card.set_value("—")
            self.current_balance_card.set_value("—")
            self.available_credit_card.set_value("—")
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT credit_limit, current_balance FROM customers WHERE id = ?
        """, (self.customer_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            symbol = get_currency_symbol()
            credit_limit = row[0] or 0
            current_balance = row[1] or 0
            available_credit = credit_limit - current_balance
            
            # Update cards
            self.credit_limit_card.set_value(format_money(credit_limit, symbol))
            self.current_balance_card.set_value(format_money(current_balance, symbol))
            self.available_credit_card.set_value(format_money(available_credit, symbol))
            
            # Color coding
            if current_balance >= credit_limit and credit_limit > 0:
                self.current_balance_card.set_color("#e74c3c")
            else:
                self.current_balance_card.set_color("#f39c12")
            
            if available_credit < 0:
                self.available_credit_card.set_color("#e74c3c")
            else:
                self.available_credit_card.set_color("#2ecc71")

    def update_balance(self):
        total = self.total_amount.value()
        paid = self.paid_amount.value()
        balance = max(total - paid, 0)
        symbol = get_currency_symbol()
        colors = get_theme_colors()
        self.balance_amount.setText(format_money(balance, symbol))
        self.balance_amount.setStyleSheet(self._get_balance_style(balance, colors))

    def check_credit_limit(self, amount):
        """Check if credit sale exceeds customer credit limit using CreditService"""
        if not self.customer_id:
            return True
        
        result = self.credit_service.check_credit_limit(self.customer_id, amount)
        
        if result.get('exceeded', False):
            symbol = get_currency_symbol()
            lang = self.get_lang()
            
            if lang == "my":
                msg = (f"ခရက်ဒစ်ကန့်သတ်ချက် ကျော်လွန်နေသည်!\n\n"
                       f"ကန့်သတ်ချက်: {format_money(result['credit_limit'], symbol)}\n"
                       f"လက်ရှိကျန်: {format_money(result['current_balance'], symbol)}\n"
                       f"ဤရောင်းချမှု: {format_money(amount, symbol)}\n"
                       f"အသစ်ကျန်: {format_money(result['new_balance'], symbol)}\n\n"
                       f"ဆက်လုပ်မည်လား?")
            else:
                msg = (f"Credit limit exceeded!\n\n"
                       f"Limit: {format_money(result['credit_limit'], symbol)}\n"
                       f"Current balance: {format_money(result['current_balance'], symbol)}\n"
                       f"This sale: {format_money(amount, symbol)}\n"
                       f"New balance: {format_money(result['new_balance'], symbol)}\n\n"
                       f"Proceed anyway?")
            
            reply = QMessageBox.warning(
                self, 
                "Credit Limit Warning" if lang != "my" else "ခရက်ဒစ်ကန့်သတ်ချက် သတိပေးချက်", 
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        
        return True

    def calculate_credit_status(self, total, paid, balance):
        """Calculate credit sale status using CreditService"""
        return self.credit_service.calculate_credit_status(total, paid, balance)

    def save_credit_sale(self):
        """Save credit sale using CreditService"""
        total = self.total_amount.value()
        paid = self.paid_amount.value()
        lang = self.get_lang()
        
        if paid > total:
            if lang == "my":
                msg = "သွင်းငွေသည် စုစုပေါင်းငွေထက် မပိုနိုင်ပါ။"
            else:
                msg = "Paid amount cannot exceed total amount."
            QMessageBox.warning(self, "Error", msg)
            return
        
        if total <= 0:
            if lang == "my":
                msg = "စုစုပေါင်းငွေ ထည့်သွင်းပေးပါ။"
            else:
                msg = "Please enter a valid total amount."
            QMessageBox.warning(self, "Error", msg)
            return
        
        balance = total - paid
        
        if not self.check_credit_limit(balance):
            return
        
        invoice_no = self.invoice_no.text()
        sale_date = self.sale_date.date().toString("yyyy-MM-dd")
        due_date = self.due_date.date().toString("yyyy-MM-dd")
        notes = self.notes.toPlainText()
        
        result = self.credit_service.create_credit_sale(
            customer_id=self.customer_id,
            invoice_no=invoice_no,
            total_amount=total,
            paid_amount=paid,
            sale_id=None,
            due_date=due_date,
            notes=notes,
            sale_date=sale_date
        )
        
        if result.get('success'):
            symbol = get_currency_symbol()
            balance_remaining = result.get('balance_amount', balance)
            
            if lang == "my":
                msg = (f"အကြွေးရောင်းချမှု အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ။\n"
                       f"ပြေစာအမှတ်: {invoice_no}\n"
                       f"ကျန်ရှိငွေ: {format_money(balance_remaining, symbol)}\n"
                       f"ပေးရမည့်ရက်: {due_date}")
            else:
                msg = (f"Credit sale recorded successfully!\n"
                       f"Invoice: {invoice_no}\n"
                       f"Balance due: {format_money(balance_remaining, symbol)}\n"
                       f"Due date: {due_date}")
            
            QMessageBox.information(self, "Success", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to save: {result.get('error', 'Unknown error')}")

    def showEvent(self, event):
        """Refresh customer info when dialog becomes visible"""
        self.load_customer_info()
        super().showEvent(event)