# ui/widgets/ai_assistant_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea

class AIAssistantWidget(QWidget):
    """AI အကြံပြုချက်များ ပြသရန် ဝစ်ဂျက်"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # ခေါင်းစဉ်
        title = QLabel("🤖 AI Insights")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)
        
        # အကြံပြုချက်များ စာရင်း
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        
        # နမူနာ အကြံပြုချက်များ
        insights = [
            ("📈", "Today's sales are 15% higher than yesterday", "#2ecc71"),
            ("📊", "Best selling category: Coffee (35% of sales)", "#3498db"),
            ("💡", "Consider running promotion on slow-moving items", "#f39c12"),
        ]
        
        for icon, text, color in insights:
            item = QLabel(f"{icon} {text}")
            item.setWordWrap(True)
            item.setStyleSheet(f"""
                background-color: {color}20;
                border-radius: 8px;
                padding: 8px 12px;
                color: {color};
            """)
            self.content_layout.addWidget(item)
        
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)
        self.setLayout(layout)