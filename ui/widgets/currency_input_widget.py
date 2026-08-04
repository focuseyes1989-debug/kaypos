# ui/widgets/currency_input_widget.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from utils.currency import get_currency_symbol, format_money


class CurrencyInputWidget(QWidget):
    """ငွေကြေးထည့်သွင်းရန် Input Widget"""
    
    value_changed = pyqtSignal(float)
    
    def __init__(self, symbol=None, parent=None):
        super().__init__(parent)
        self.symbol = symbol or get_currency_symbol()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Currency symbol
        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #495057;
            background-color: #f1f3f5;
            padding: 6px 10px;
            border: 1px solid #ced4da;
            border-right: none;
            border-radius: 4px 0 0 4px;
        """)
        layout.addWidget(self.symbol_label)
        
        # Input
        self.input = QLineEdit()
        self.input.setPlaceholderText("0")
        self.input.textChanged.connect(self._on_text_changed)
        self.input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #ced4da;
                border-radius: 0 4px 4px 0;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #5865f2;
            }
        """)
        layout.addWidget(self.input, 1)
        
        self.setLayout(layout)
        
    def _on_text_changed(self, text):
        """စာသားပြောင်းတဲ့အခါ"""
        try:
            # Remove commas and currency symbol
            clean_text = text.replace(",", "").replace(self.symbol, "").strip()
            if clean_text:
                value = float(clean_text)
                self.value_changed.emit(value)
        except ValueError:
            pass
            
    def get_value(self):
        """တန်ဖိုးကို float အနေနဲ့ ပြန်ရယူရန်"""
        try:
            text = self.input.text().replace(",", "").replace(self.symbol, "").strip()
            return float(text) if text else 0.0
        except ValueError:
            return 0.0
            
    def set_value(self, value):
        """တန်ဖိုးကို သတ်မှတ်ရန်"""
        if isinstance(value, (int, float)):
            self.input.setText(format_money(value, self.symbol))
            
    def retranslateUi(self, lang_code):
        """ဘာသာပြန်ရန်"""
        pass