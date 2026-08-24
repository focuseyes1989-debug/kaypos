# ui/sales_page/payment_widget.py
from PyQt6.QtWidgets import QDialog, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QDoubleValidator
from utils.currency import get_currency_symbol, format_money
from ui.themes import get_theme_colors, is_dark_theme
from ui.themes.theme_manager import get_icon_with_color
from ui.widgets.numeric_keypad_dialog import NumericKeypadDialog


class MoneyInput(QLineEdit):
    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        validator = QDoubleValidator(0.0, 999999999.0, 0, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(validator)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setText("0")
        self.textChanged.connect(self._emit_value_changed)

    def value(self) -> float:
        text = self.text().replace(",", "").strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def setValue(self, value: float) -> None:
        clean_value = max(0.0, min(999999999.0, float(value or 0)))
        self.setText(str(int(round(clean_value))))

    def _emit_value_changed(self) -> None:
        self.valueChanged.emit(self.value())


class PaymentWidget(QGroupBox):
    payment_amount_changed = pyqtSignal(float)
    checkout_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Payment")
        self.payment_manual_override = False
        self._programmatic_update = False
        self._grand_total = 0.0
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Payment Type
        pt_layout = QHBoxLayout()
        self.payment_type_label = QLabel("Type:")
        pt_layout.addWidget(self.payment_type_label)
        self.payment_combo = QComboBox()
        self.payment_combo.setFixedWidth(180)
        pt_layout.addWidget(self.payment_combo)
        layout.addLayout(pt_layout)

        # Received Amount
        amt_layout = QHBoxLayout()
        self.amt_label = QLabel("Received:")
        amt_layout.addWidget(self.amt_label)
        self.payment_input = MoneyInput()
        # ✅ FIXED: max value increased from 1,000,000 to 999,999,999
        self.payment_input.setFixedHeight(44)
        self.payment_input.setFixedWidth(180)
        self.payment_input.valueChanged.connect(self.on_payment_changed)
        self.payment_input.returnPressed.connect(self.apply_received_amount)
        self._setup_received_keypad_action()
        self._apply_received_input_style()
        amt_layout.addWidget(self.payment_input)
        layout.addLayout(amt_layout)

        # Change Display
        chg_layout = QHBoxLayout()
        self.change_label_title = QLabel("Change:")
        chg_layout.addWidget(self.change_label_title)
        self.change_label = QLabel("0")
        chg_layout.addWidget(self.change_label)
        chg_layout.addStretch()
        layout.addLayout(chg_layout)
        self.change_label_title.setVisible(False)
        self.change_label.setVisible(False)
        self.update_theme()

    def _sales_page(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "totals_widget") and hasattr(parent, "cart_widget"):
                return parent
            parent = parent.parent()
        return None

    def _setup_received_keypad_action(self):
        colors = get_theme_colors()
        icon = get_icon_with_color("keyboard", colors.get("text_secondary", "#6c757d"), (18, 18))
        self.received_keypad_action = self.payment_input.addAction(
            icon,
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self.received_keypad_action.triggered.connect(self.open_received_keypad)

    def _apply_received_input_style(self):
        dark = is_dark_theme()
        if dark:
            bg = "#3a3320"
            border = "#f59f00"
            focus = "#ffd43b"
            text = "#fff3bf"
            selection = "#f59f00"
        else:
            bg = "#fff7d6"
            border = "#f08c00"
            focus = "#e67700"
            text = "#2e2a1f"
            selection = "#f08c00"

        self.payment_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg};
                color: {text};
                border: 2px solid {border};
                border-radius: 6px;
                padding: 6px 30px 6px 10px;
                font-size: 17pt;
                font-weight: 700;
                selection-background-color: {selection};
                selection-color: white;
            }}
            QLineEdit:focus {{
                border: 2px solid {focus};
            }}
            QLineEdit:disabled {{
                color: #8a8f98;
                background-color: rgba(128, 128, 128, 0.16);
                border: 1px solid rgba(128, 128, 128, 0.36);
            }}
        """)

    def open_received_keypad(self):
        dialog = NumericKeypadDialog(
            "Received Amount",
            self.payment_input.value(),
            self,
            decimals=0,
            minimum=0,
            maximum=999999999,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.payment_input.setValue(dialog.value())
            self.apply_received_amount()

    def on_payment_changed(self, value):
        """Called when payment value changes (user or programmatic)"""
        if self._programmatic_update:
            return
        
        # User is manually changing the value
        self.payment_manual_override = True
        self.payment_amount_changed.emit(value)
        self.update_change()
        QTimer.singleShot(0, self.update_change)

    def apply_received_amount(self):
        """Apply the typed received amount and refresh the cart change display."""
        self.payment_manual_override = True
        self.payment_amount_changed.emit(self.payment_input.value())
        self.update_change()
        parent = self._sales_page()
        if parent and hasattr(parent, "cart_widget"):
            parent.cart_widget.update_change()

    def auto_set_payment(self, grand_total):
        """Auto-set payment to grand total (only if not manually overridden)"""
        self._grand_total = grand_total
        
        if not self.payment_manual_override:
            self._programmatic_update = True
            self.payment_input.blockSignals(True)
            try:
                self.payment_input.setValue(grand_total)
            finally:
                self.payment_input.blockSignals(False)
            self._programmatic_update = False
            self.update_change()

    def update_change(self):
        """Update change display based on current payment and grand total"""
        # Get current grand total from totals widget
        parent = self._sales_page()
        if parent and hasattr(parent, 'totals_widget'):
            grand_total = parent.totals_widget.get_current_grand_total()
        else:
            grand_total = self._grand_total
            
        payment = self.payment_input.value()
        change = payment - grand_total
        symbol = get_currency_symbol()
        colors = get_theme_colors()
        
        if change >= 0:
            self.change_label.setText(format_money(change, symbol))
            self.change_label.setStyleSheet(f"color: {colors.get('success', '#27c992')}; font-weight: bold; background: transparent;")
        else:
            self.change_label.setText(f"-{format_money(abs(change), symbol)}")
            self.change_label.setStyleSheet(f"color: {colors.get('danger', '#ff6b7a')}; font-weight: bold; background: transparent;")
        if parent and hasattr(parent, "cart_widget") and hasattr(parent.cart_widget, "update_change"):
            parent.cart_widget.update_change()

    def load_payment_types(self, types):
        self.payment_combo.blockSignals(True)
        self.payment_combo.clear()
        for name in types:
            self.payment_combo.addItem(name)
        # Always set "Cash" as default
        cash_idx = self.payment_combo.findText("Cash")
        if cash_idx >= 0:
            self.payment_combo.setCurrentIndex(cash_idx)
        else:
            self.payment_combo.setCurrentIndex(0)
        self.payment_combo.blockSignals(False)

    def get_selected_payment_type(self):
        return self.payment_combo.currentText()

    def get_payment_amount(self):
        return self.payment_input.value()

    def reset_manual_override(self):
        """Reset manual override flag after checkout"""
        self.payment_manual_override = False

    def set_payment_amount(self, amount):
        """Force set payment amount (used after manual override reset)"""
        self._programmatic_update = True
        self.payment_input.blockSignals(True)
        try:
            self.payment_input.setValue(amount)
        finally:
            self.payment_input.blockSignals(False)
        self._programmatic_update = False
        self.update_change()
    
    def reset_to_default(self):
        """Reset payment widget to default state"""
        # Reset payment type to Cash
        cash_idx = self.payment_combo.findText("Cash")
        if cash_idx >= 0:
            self.payment_combo.setCurrentIndex(cash_idx)
        
        # Reset payment amount to 0
        self._programmatic_update = True
        self.payment_input.blockSignals(True)
        try:
            self.payment_input.setValue(0)
        finally:
            self.payment_input.blockSignals(False)
        self._programmatic_update = False
        
        # Reset manual override
        self.payment_manual_override = False
        self._grand_total = 0.0
        
        # Update change display
        self.update_change()

    def retranslateUi(self):
        from utils.language import lang
        if lang.get_current() == "my":
            self.setTitle("ငွေပေးချေမှု")
            self.payment_type_label.setText("အမျိုးအစား:")
            self.amt_label.setText("လက်ခံငွေ:")
            self.change_label_title.setText("ပြန်အမ်းငွေ:")
        else:
            self.setTitle("Payment")
            self.payment_type_label.setText("Type:")
            self.amt_label.setText("Received:")
            self.change_label_title.setText("Change:")

    def update_theme(self, theme_name=None):
        """Apply current theme colors to payment controls."""
        colors = get_theme_colors(theme_name)
        text = colors.get('text', '#212529')
        secondary = colors.get('text_secondary', '#6c757d')
        input_bg = colors.get('input_bg', '#ffffff')
        input_border = colors.get('input_border', colors.get('border', '#dee2e6'))
        focus = colors.get('border_hover', '#5865f2')
        card_bg = colors.get('card_bg', '#ffffff')

        for label in (self.payment_type_label, self.amt_label, self.change_label_title):
            label.setStyleSheet(f"color: {text}; background: transparent;")

        if hasattr(self, "received_keypad_action"):
            self.received_keypad_action.setIcon(get_icon_with_color("keyboard", secondary, (18, 18)))

        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {card_bg};
                color: {text};
            }}
            QComboBox, QLineEdit {{
                background-color: {input_bg};
                color: {text};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 4px 6px;
            }}
            QLineEdit {{
                font-size: 17pt;
                font-weight: 700;
                padding: 6px 10px;
            }}
            QComboBox:disabled, QLineEdit:disabled {{
                color: {secondary};
                background-color: {colors.get('bg_hover', input_bg)};
            }}
            QComboBox:focus, QLineEdit:focus {{
                border: 1px solid {focus};
            }}
            QComboBox QAbstractItemView {{
                background-color: {card_bg};
                color: {text};
                border: 1px solid {input_border};
                selection-background-color: {focus};
                selection-color: white;
            }}
        """)
        self._apply_received_input_style()
        self.update_change()
