# ui/supplier_payment_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton,
    QMessageBox, QDialogButtonBox, QGroupBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QPixmap
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets.modern_button import ModernButton
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
import os


class SupplierPaymentDialog(QDialog):
    """Supplier Payment Dialog - Theme-aware with SVG Icons"""
    
    def __init__(self, supplier_id, supplier_name, current_balance=0, parent=None):
        super().__init__(parent)
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name
        self.current_balance = current_balance
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle(f"Record Payment - {supplier_name}")
        self.setMinimumWidth(550)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Summary Cards with SVG icons
        card_layout = QHBoxLayout()
        card_layout.setSpacing(15)
        
        # Determine color based on balance
        if current_balance > 0:
            balance_color = "#e74c3c"  # Red - owe money
        elif current_balance < 0:
            balance_color = "#2ecc71"  # Green - overpaid
        else:
            balance_color = "#3498db"  # Blue - zero balance
        
        # ✅ Balance Card with SVG icon
        self.balance_card = SummaryCardWidget(
            title="Current Balance",
            value=format_money(current_balance, get_currency_symbol()),
            icon="money_off",
            color=balance_color,
            icon_is_svg=True
        )
        self.balance_card.set_icon("money_off", is_svg=True, size=(24, 24))
        card_layout.addWidget(self.balance_card)
        
        # ✅ Supplier Card with SVG icon
        self.supplier_card = SummaryCardWidget(
            title="Supplier",
            value=supplier_name if len(supplier_name) <= 20 else supplier_name[:20] + "...",
            icon="local_shipping",
            color="#8e44ad",
            icon_is_svg=True
        )
        self.supplier_card.set_icon("local_shipping", is_svg=True, size=(24, 24))
        card_layout.addWidget(self.supplier_card)
        
        layout.addLayout(card_layout)

        # Payment form
        form_group = QGroupBox("Payment Details")
        colors = get_theme_colors()
        form_group.setStyleSheet(self._get_groupbox_style(colors))
        
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(15)

        # Payment amount
        symbol = get_currency_symbol()
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, current_balance if current_balance > 0 else 10000000)
        self.amount_spin.setDecimals(0)
        self.amount_spin.setSuffix(f" {symbol}")
        self.amount_spin.setMaximum(current_balance if current_balance > 0 else 10000000)
        self.amount_spin.setStyleSheet(self._get_spinbox_style(colors))
        form_layout.addRow(self._create_label("💵 Payment Amount:"), self.amount_spin)

        # Payment date
        self.payment_date = QDateEdit()
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setStyleSheet(self._get_date_style(colors))
        self.payment_date.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow(self._create_label("📅 Payment Date:"), self.payment_date)

        # Reference number
        self.reference_no = QLineEdit()
        self.reference_no.setPlaceholderText("Optional - e.g., Bank Ref, Cheque No")
        self.reference_no.setStyleSheet(self._get_line_edit_style(colors))
        form_layout.addRow(self._create_label("📄 Reference No:"), self.reference_no)

        # Payment type
        self.payment_type = QComboBox()
        self.payment_type.addItems(["Cash", "Bank Transfer", "Cheque", "Mobile Money"])
        self.payment_type.setStyleSheet(self._get_combo_style(colors))
        form_layout.addRow(self._create_label("💳 Payment Method:"), self.payment_type)

        # Purchase order selection (optional)
        self.po_combo = QComboBox()
        self.po_combo.addItem("-- General Payment (not linked to specific PO) --", None)
        self.load_unpaid_purchase_orders()
        self.po_combo.setStyleSheet(self._get_combo_style(colors))
        form_layout.addRow(self._create_label("📋 Apply to PO:"), self.po_combo)

        # Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Optional notes about this payment")
        self.notes.setStyleSheet(self._get_text_edit_style(colors))
        form_layout.addRow(self._create_label("📝 Notes:"), self.notes)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Buttons - Using ModernButton with SVG icons
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        btn_layout.addStretch()
        
        # ✅ Save button with SVG icon
        self.btn_save = ModernButton("", ModernButton.PRIMARY)
        self.btn_save.set_icon("save", size=(16, 16))
        self.btn_save.clicked.connect(self.save_payment)
        btn_layout.addWidget(self.btn_save)
        
        # ✅ Cancel button with SVG icon
        self.btn_cancel = ModernButton("", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addWidget(button_frame)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        self.retranslateUi()
    
    def _load_svg_icon(self, icon_name, size=(16, 16)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        # Try PNG fallback
        png_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(png_path):
            try:
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        return None
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        if hasattr(self, 'btn_save'):
            self.btn_save.set_icon("save", size=(16, 16))
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.set_icon("close", size=(16, 16))

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
    
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
        form_group = self.findChild(QGroupBox)
        if form_group:
            form_group.setStyleSheet(self._get_groupbox_style(colors))
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update all labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update input widgets
        self.amount_spin.setStyleSheet(self._get_spinbox_style(colors))
        self.payment_date.setStyleSheet(self._get_date_style(colors))
        self.reference_no.setStyleSheet(self._get_line_edit_style(colors))
        self.payment_type.setStyleSheet(self._get_combo_style(colors))
        self.po_combo.setStyleSheet(self._get_combo_style(colors))
        self.notes.setStyleSheet(self._get_text_edit_style(colors))
        
        # Update summary cards (they are theme-aware)
        if hasattr(self, 'balance_card'):
            self.balance_card.update_theme()
        if hasattr(self, 'supplier_card'):
            self.supplier_card.update_theme()
        
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
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder {{
                color: {colors['text_secondary']};
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
    
    def _get_combo_style(self, colors):
        return f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
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

    def load_unpaid_purchase_orders(self):
        """Load unpaid or partially paid purchase orders for this supplier"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, po_no, total_amount, payment_status
            FROM purchase_orders
            WHERE supplier_id = ? AND payment_status IN ('Unpaid', 'Partial')
            ORDER BY order_date DESC
        """, (self.supplier_id,))
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            po_id, po_no, amount, status = row
            self.po_combo.addItem(f"{po_no} - {format_money(amount)} ({status})", po_id)

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
        
        # Update button icons
        self._update_button_icons()
        
        if lang == "my":
            self.setWindowTitle(f"ငွေပေးချေမှု မှတ်တမ်းတင်ရန် - {self.supplier_name}")
            self.balance_card.set_title("လက်ကျန်ကြွေးငွေ")
            self.balance_card.set_value(format_money(self.current_balance, symbol))
            self.supplier_card.set_title("ပေးသွင်းသူ")
            self.supplier_card.set_value(self.supplier_name if len(self.supplier_name) <= 20 else self.supplier_name[:20] + "...")
            
            self.amount_spin.setSuffix(f" {symbol}")
            self.btn_save.setText(" သိမ်းဆည်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့")
            self.reference_no.setPlaceholderText("မလိုအပ်ပါ - ဘဏ်ကိုးကား၊ ချက်လက်မှတ်နံပါတ်")
            self.notes.setPlaceholderText("ငွေပေးချေမှုအကြောင်း မှတ်ချက်")
        else:
            self.setWindowTitle(f"Record Payment - {self.supplier_name}")
            self.balance_card.set_title("Current Balance")
            self.balance_card.set_value(format_money(self.current_balance, symbol))
            self.supplier_card.set_title("Supplier")
            self.supplier_card.set_value(self.supplier_name if len(self.supplier_name) <= 20 else self.supplier_name[:20] + "...")
            
            self.amount_spin.setSuffix(f" {symbol}")
            self.btn_save.setText(" Record Payment")
            self.btn_cancel.setText(" Cancel")
            self.reference_no.setPlaceholderText("Optional - e.g., Bank Ref, Cheque No")
            self.notes.setPlaceholderText("Optional notes about this payment")
        
        # Update card icons after language change
        self.balance_card.set_icon("money_off", is_svg=True, size=(24, 24))
        self.supplier_card.set_icon("local_shipping", is_svg=True, size=(24, 24))
        
        # Update label styles after language change
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update input styles
        self.amount_spin.setStyleSheet(self._get_spinbox_style(colors))
        self.payment_date.setStyleSheet(self._get_date_style(colors))
        self.reference_no.setStyleSheet(self._get_line_edit_style(colors))
        self.payment_type.setStyleSheet(self._get_combo_style(colors))
        self.po_combo.setStyleSheet(self._get_combo_style(colors))
        self.notes.setStyleSheet(self._get_text_edit_style(colors))
        
        # Update groupbox
        form_group = self.findChild(QGroupBox)
        if form_group:
            form_group.setStyleSheet(self._get_groupbox_style(colors))
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update summary cards
        if hasattr(self, 'balance_card'):
            self.balance_card.update_theme()
        if hasattr(self, 'supplier_card'):
            self.supplier_card.update_theme()
        
        # Apply theme after language change
        self._apply_theme()

    def save_payment(self):
        amount = self.amount_spin.value()
        if amount <= 0:
            lang = self.get_lang()
            msg = "Please enter a valid payment amount." if lang != "my" else "ငွေပေးချေမှုပမာဏ ထည့်ပါ။"
            QMessageBox.warning(self, "Error" if lang != "my" else "အမှား", msg)
            return

        payment_date = self.payment_date.date().toString("yyyy-MM-dd")
        ref_no = self.reference_no.text().strip() or f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        payment_type = self.payment_type.currentText()
        notes = self.notes.toPlainText()
        po_id = self.po_combo.currentData()

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")

            # Insert payment record
            cursor.execute("""
                INSERT INTO supplier_payments 
                (supplier_id, amount, payment_date, reference_no, payment_type, notes, purchase_order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.supplier_id, amount, payment_date, ref_no, payment_type, notes, po_id))

            # Update purchase order payment status if linked to a PO
            if po_id:
                cursor.execute("""
                    SELECT total_amount, payment_status, COALESCE((
                        SELECT SUM(amount) FROM supplier_payments 
                        WHERE purchase_order_id = ? AND payment_type != 'Purchase'
                    ), 0) as total_paid
                    FROM purchase_orders WHERE id = ?
                """, (po_id, po_id))
                po = cursor.fetchone()
                if po:
                    total_amount, current_status, total_paid = po
                    new_total_paid = total_paid + amount
                    
                    if new_total_paid >= total_amount:
                        new_status = "Paid"
                    elif new_total_paid > 0:
                        new_status = "Partial"
                    else:
                        new_status = current_status
                    
                    cursor.execute("""
                        UPDATE purchase_orders 
                        SET payment_status = ? 
                        WHERE id = ?
                    """, (new_status, po_id))

            conn.commit()
            
            lang = self.get_lang()
            msg = "Payment recorded successfully!" if lang != "my" else "ငွေပေးချေမှု အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ။"
            QMessageBox.information(self, "Success" if lang != "my" else "အောင်မြင်ပြီး", msg)
            
            # Recalculate current balance
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN payment_type = 'Purchase' THEN amount ELSE 0 END), 0) as total_purchases,
                    COALESCE(SUM(CASE WHEN payment_type != 'Purchase' THEN amount ELSE 0 END), 0) as total_payments
                FROM supplier_payments
                WHERE supplier_id = ?
            """, (self.supplier_id,))
            row = cursor.fetchone()
            if row:
                total_purchases = row[0] if row else 0
                total_payments = row[1] if row else 0
                new_balance = total_purchases - total_payments
                symbol = get_currency_symbol()
                self.balance_card.set_value(format_money(new_balance, symbol))
                if new_balance > 0:
                    self.balance_card.set_color("#e74c3c")
                elif new_balance < 0:
                    self.balance_card.set_color("#2ecc71")
                else:
                    self.balance_card.set_color("#3498db")
            
            self.accept()
            
        except Exception as e:
            conn.rollback()
            lang = self.get_lang()
            msg = f"Failed to record payment: {e}" if lang != "my" else f"ငွေပေးချေမှု မှတ်တမ်းတင်ရာတွင် အမှားရှိသည်: {e}"
            QMessageBox.critical(self, "Error" if lang != "my" else "အမှား", msg)
        finally:
            conn.close()
    
    def showEvent(self, event):
        """Update button icons when dialog becomes visible"""
        self._update_button_icons()
        super().showEvent(event)