# ui/widgets/tag_input_widget.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton, QLabel, QFrame, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class TagInputWidget(QWidget):
    """Tag များကို ထည့်သွင်းရန်/ဖယ်ရှားရန် Widget"""
    
    tags_changed = pyqtSignal(list)  # Tag စာရင်း ပြောင်းတဲ့အခါ
    
    def __init__(self, placeholder="Enter tag...", parent=None):
        super().__init__(parent)
        self.tags = []
        self.placeholder = placeholder
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Input row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText(self.placeholder)
        self.input.returnPressed.connect(self.add_tag)
        self.input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #5865f2;
            }
        """)
        input_layout.addWidget(self.input, 1)
        
        self.add_btn = QPushButton("➕ Add")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
        """)
        self.add_btn.clicked.connect(self.add_tag)
        input_layout.addWidget(self.add_btn)
        
        main_layout.addLayout(input_layout)
        
        # Tag container (scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        
        self.tag_container = QWidget()
        self.tag_layout = QVBoxLayout(self.tag_container)
        self.tag_layout.setSpacing(6)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_layout.addStretch()
        
        self.scroll_area.setWidget(self.tag_container)
        main_layout.addWidget(self.scroll_area)
        
        self.setLayout(main_layout)
        
    def add_tag(self):
        """Tag အသစ်ထည့်ရန်"""
        text = self.input.text().strip()
        if text and text not in self.tags:
            self.tags.append(text)
            self._add_tag_widget(text)
            self.input.clear()
            self.tags_changed.emit(self.tags)
            
    def _add_tag_widget(self, text):
        """Tag widget ကို UI မှာ ထည့်ရန်"""
        tag_widget = QWidget()
        tag_widget.setObjectName(f"tag_{text}")
        
        tag_layout = QHBoxLayout(tag_widget)
        tag_layout.setContentsMargins(8, 4, 8, 4)
        tag_layout.setSpacing(8)
        
        # Tag label
        label = QLabel(text)
        label.setStyleSheet("""
            color: white;
            font-size: 12px;
            font-weight: 500;
        """)
        tag_layout.addWidget(label)
        
        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #b9bbbe;
                border: none;
                border-radius: 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
                color: white;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_tag(text))
        tag_layout.addWidget(remove_btn)
        
        # Tag styling
        tag_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #5865f2;
                border-radius: 6px;
            }}
            QWidget:hover {{
                background-color: #4752c4;
            }}
        """)
        
        # Add to layout (before stretch)
        self.tag_layout.insertWidget(self.tag_layout.count() - 1, tag_widget)
        
    def remove_tag(self, text):
        """Tag ကို ဖယ်ရှားရန်"""
        if text in self.tags:
            self.tags.remove(text)
            # Find and remove widget
            for i in range(self.tag_layout.count()):
                widget = self.tag_layout.itemAt(i).widget()
                if widget and widget.objectName() == f"tag_{text}":
                    widget.deleteLater()
                    break
            self.tags_changed.emit(self.tags)
            
    def get_tags(self):
        """Tag စာရင်းကို ပြန်ရယူရန်"""
        return self.tags.copy()
        
    def set_tags(self, tags):
        """Tag စာရင်းကို သတ်မှတ်ရန်"""
        self.clear_tags()
        for tag in tags:
            self.tags.append(tag)
            self._add_tag_widget(tag)
        self.tags_changed.emit(self.tags)
        
    def clear_tags(self):
        """Tag အားလုံးကို ရှင်းရန်"""
        self.tags.clear()
        # Clear all tag widgets
        for i in range(self.tag_layout.count() - 1, -1, -1):
            widget = self.tag_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
    def retranslateUi(self, lang_code):
        """ဘာသာပြန်ရန်"""
        if lang_code == "my":
            self.input.setPlaceholderText("Tag ထည့်ရန်...")
            self.add_btn.setText("➕ ထည့်")
        else:
            self.input.setPlaceholderText("Enter tag...")
            self.add_btn.setText("➕ Add")