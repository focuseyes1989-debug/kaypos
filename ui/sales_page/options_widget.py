# ui/sales_page/options_widget.py
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QRadioButton, QCheckBox, QWidget, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from utils.translations import tr
from ui.themes import get_theme_colors


class OptionsWidget(QGroupBox):
    """Options widget with Payment Type, Print Receipt, and Open Cash Drawer options"""
    
    payment_type_changed = pyqtSignal(str)  # "Cash" or "Credit"
    print_receipt_toggled = pyqtSignal(bool)
    open_drawer_toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Options")
        self.hide_title = False
        
        # ✅ Set transparent background for the group box
        self.setStyleSheet("""
            QGroupBox {
                background-color: transparent;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding-top: 8px;
                margin-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                background-color: transparent;
            }
            QGroupBox QWidget {
                background-color: transparent;
            }
            QGroupBox QLabel {
                background-color: transparent;
            }
            QGroupBox QRadioButton {
                background-color: transparent;
            }
            QGroupBox QCheckBox {
                background-color: transparent;
            }
        """)
        
        # Main layout - no extra spacing at bottom
        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(6, 4, 6, 4)
        self.setLayout(layout)
        
        # === Payment Type - Simple horizontal row ===
        payment_widget = QWidget()
        payment_widget.setStyleSheet("background-color: transparent;")
        payment_layout = QHBoxLayout(payment_widget)
        payment_layout.setContentsMargins(0, 0, 0, 0)
        payment_layout.setSpacing(10)
        
        # Label
        self.type_label = QLabel("Payment:")
        self.type_label.setStyleSheet("font-weight: bold; font-size: 9pt; background-color: transparent;")
        payment_layout.addWidget(self.type_label)
        
        # Cash Radio
        self.cash_radio = QRadioButton("Cash")
        self.cash_radio.setChecked(True)
        self.cash_radio.clicked.connect(lambda: self.payment_type_changed.emit("Cash"))
        payment_layout.addWidget(self.cash_radio)
        
        # Credit Radio
        self.credit_radio = QRadioButton("Credit")
        self.credit_radio.clicked.connect(lambda: self.payment_type_changed.emit("Credit"))
        payment_layout.addWidget(self.credit_radio)
        
        payment_layout.addStretch()
        layout.addWidget(payment_widget)
        
        # === Simple separator line ===
        self.separator_line = QWidget()
        self.separator_line.setFixedHeight(1)
        layout.addWidget(self.separator_line)
        
        # === Options - Simple horizontal row ===
        options_widget = QWidget()
        options_widget.setStyleSheet("background-color: transparent;")
        options_layout = QHBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(12)
        
        # Print Receipt
        self.print_receipt_check = QCheckBox("Print Receipt")
        self.print_receipt_check.setChecked(True)
        self.print_receipt_check.toggled.connect(self.print_receipt_toggled.emit)
        options_layout.addWidget(self.print_receipt_check)
        
        # Open Cash Drawer
        self.open_drawer_check = QCheckBox("Open Cash Drawer")
        self.open_drawer_check.setChecked(True)
        self.open_drawer_check.toggled.connect(self.open_drawer_toggled.emit)
        options_layout.addWidget(self.open_drawer_check)
        
        options_layout.addStretch()
        layout.addWidget(options_widget)
        
        # Set initial credit radio state
        self.set_customer_selected(False)
        self.update_theme()
    
    def is_print_receipt_enabled(self):
        """Return whether print receipt is enabled"""
        return self.print_receipt_check.isChecked()
    
    def is_open_drawer_enabled(self):
        """Return whether open cash drawer is enabled"""
        return self.open_drawer_check.isChecked()
    
    def get_payment_type(self):
        """Return selected payment type: 'Cash' or 'Credit'"""
        if self.credit_radio.isChecked():
            return "Credit"
        return "Cash"
    
    def set_payment_type(self, payment_type):
        """Set payment type programmatically"""
        if payment_type == "Credit":
            self.credit_radio.setChecked(True)
        else:
            self.cash_radio.setChecked(True)
    
    def is_credit_sale(self):
        """Return True if credit sale is selected"""
        return self.credit_radio.isChecked()
    
    def is_cash_sale(self):
        """Return True if cash sale is selected"""
        return self.cash_radio.isChecked()
    
    def set_customer_selected(self, has_customer):
        """Update credit radio state based on customer selection"""
        if not has_customer and self.credit_radio.isChecked():
            self.cash_radio.setChecked(True)
        
        # Update credit radio tooltip and enable/disable
        self.credit_radio.setEnabled(has_customer)
        
        if has_customer:
            self.credit_radio.setToolTip("Select customer for credit sale")
        else:
            self.credit_radio.setToolTip("Please select a customer first")
    
    def retranslateUi(self):
        from utils.language import lang
        if lang.get_current() == "my":
            self.setTitle("ရွေးချယ်စရာများ")
            # Find and update the payment label
            for child in self.children():
                if isinstance(child, QLabel) and child.text() == "Payment:":
                    child.setText("ငွေပေးချေမှု:")
                    break
            self.cash_radio.setText("ငွေသား")
            self.credit_radio.setText("အကြွေး")
            self.print_receipt_check.setText("ပြေစာထုတ်ရန်")
            self.open_drawer_check.setText("ငွေသေတ္တာဖွင့်ရန်")
        else:
            self.setTitle("Options")
            # Find and update the payment label
            for child in self.children():
                if isinstance(child, QLabel) and child.text() == "ငွေပေးချေမှု:":
                    child.setText("Payment:")
                    break
            self.cash_radio.setText("Cash")
            self.credit_radio.setText("Credit")
            self.print_receipt_check.setText("Print Receipt")
            self.open_drawer_check.setText("Open Cash Drawer")

    def update_theme(self, theme_name=None):
        """Apply current theme colors to option controls."""
        colors = get_theme_colors(theme_name)
        text = colors.get('text', '#212529')
        border = colors.get('border', '#dee2e6')
        card_bg = colors.get('card_bg', '#ffffff')
        title_style = """
                subcontrol-origin: margin;
                left: -9999px;
                padding: 0px;
        """ if self.hide_title else f"""
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                background-color: {card_bg};
                color: {text};
        """
        top_padding = "0px" if self.hide_title else "8px"
        top_margin = "0px" if self.hide_title else "4px"

        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 4px;
                padding-top: {top_padding};
                margin-top: {top_margin};
                color: {text};
            }}
            QGroupBox::title {{
                {title_style}
            }}
            QGroupBox QWidget, QGroupBox QLabel, QGroupBox QRadioButton, QGroupBox QCheckBox {{
                background-color: transparent;
                color: {text};
            }}
        """)
        self.type_label.setStyleSheet(f"font-weight: bold; font-size: 9pt; color: {text}; background: transparent;")
        self.separator_line.setStyleSheet(f"background-color: {border}; border: none; margin: 2px 0px;")
