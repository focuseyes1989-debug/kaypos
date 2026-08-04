# ui/widgets/loading_spinner_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer


class LoadingSpinnerWidget(QWidget):
    """ဒေတာဆွဲနေစဉ် ပြသမယ့် Spinner Widget"""
    
    def __init__(self, text="Loading...", parent=None):
        super().__init__(parent)
        self.text = text
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current_index = 0
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Spinner label
        self.spinner_label = QLabel(self.spinner_chars[0])
        self.spinner_label.setStyleSheet("""
            font-size: 32px;
            color: #5865f2;
        """)
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.spinner_label)
        
        # Text label
        self.text_label = QLabel(self.text)
        self.text_label.setStyleSheet("""
            font-size: 14px;
            color: #6c757d;
        """)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)
        
        self.setLayout(layout)
        
        # Timer for animation
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_spinner)
        self.timer.setInterval(100)
        
    def start(self):
        """Spinner ကို စတင်ရန်"""
        self.setVisible(True)
        self.timer.start()
        
    def stop(self):
        """Spinner ကို ရပ်ရန်"""
        self.timer.stop()
        self.setVisible(False)
        
    def _update_spinner(self):
        """Spinner animation ကို update လုပ်ရန်"""
        self.current_index = (self.current_index + 1) % len(self.spinner_chars)
        self.spinner_label.setText(self.spinner_chars[self.current_index])
        
    def set_text(self, text):
        """ပြသမယ့် စာသားကို ပြောင်းရန်"""
        self.text = text
        self.text_label.setText(text)
        
    def retranslateUi(self, lang_code):
        """ဘာသာပြန်ရန်"""
        if lang_code == "my":
            self.text_label.setText("ဒေတာဆွဲနေသည်...")
        else:
            self.text_label.setText("Loading...")