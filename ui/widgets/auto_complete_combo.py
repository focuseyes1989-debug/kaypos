# ui/widgets/auto_complete_combo.py
from PyQt6.QtWidgets import QComboBox, QLineEdit, QCompleter, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel


class AutoCompleteComboBox(QWidget):
    """Auto-complete ပါတဲ့ ComboBox"""
    
    current_text_changed = pyqtSignal(str)
    
    def __init__(self, items=None, placeholder="Select or type...", parent=None):
        super().__init__(parent)
        self.items = items or []
        self.setup_ui(placeholder)
        
    def setup_ui(self, placeholder):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # ComboBox
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setPlaceholderText(placeholder)
        self.combo.currentTextChanged.connect(self.current_text_changed.emit)
        self.combo.setStyleSheet("""
            QComboBox {
                padding: 6px 10px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                min-height: 30px;
            }
            QComboBox:focus {
                border-color: #5865f2;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                selection-background-color: #5865f2;
                selection-color: white;
            }
        """)
        
        # Add items
        if self.items:
            self.combo.addItems(self.items)
        
        # Setup completer
        self.completer = QCompleter(self.items)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo.setCompleter(self.completer)
        
        layout.addWidget(self.combo)
        self.setLayout(layout)
        
    def add_items(self, items):
        """Items များကို ထည့်ရန်"""
        self.items = items
        self.combo.clear()
        self.combo.addItems(items)
        self.completer.setModel(QStringListModel(items))
        
    def get_current_text(self):
        return self.combo.currentText()
        
    def set_current_text(self, text):
        self.combo.setCurrentText(text)
        
    def clear(self):
        self.combo.clear()
        self.combo.setCurrentText("")
        
    def retranslateUi(self, lang_code):
        """ဘာသာပြန်ရန်"""
        if lang_code == "my":
            self.combo.setPlaceholderText("ရွေးရန် သို့မဟုတ် ရိုက်ထည့်ရန်...")
        else:
            self.combo.setPlaceholderText("Select or type...")