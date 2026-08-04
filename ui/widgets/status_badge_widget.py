# ui/widgets/status_badge_widget.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt


class StatusBadgeWidget(QWidget):
    """Status badge with color indicators"""
    
    STATUS_COLORS = {
        'completed': '#2ecc71',    # Green
        'pending': '#f39c12',      # Orange
        'cancelled': '#e74c3c',    # Red
        'draft': '#95a5a6',        # Gray
        'paid': '#2ecc71',         # Green
        'unpaid': '#e74c3c',       # Red
        'partial': '#f39c12',      # Orange
        'overdue': '#e74c3c',      # Red
        'active': '#2ecc71',       # Green
        'inactive': '#95a5a6',     # Gray
        'warning': '#f39c12',      # Orange
        'info': '#3498db',         # Blue
    }
    
    STATUS_LABELS = {
        'en': {
            'completed': 'Completed',
            'pending': 'Pending',
            'cancelled': 'Cancelled',
            'draft': 'Draft',
            'paid': 'Paid',
            'unpaid': 'Unpaid',
            'partial': 'Partial',
            'overdue': 'Overdue',
            'active': 'Active',
            'inactive': 'Inactive',
            'warning': 'Warning',
            'info': 'Info',
        },
        'my': {
            'completed': 'ပြီးစီး',
            'pending': 'ဆိုင်းငံ့',
            'cancelled': 'ဖျက်သိမ်း',
            'draft': 'မူကြမ်း',
            'paid': 'ပေးချေပြီး',
            'unpaid': 'ပေးချေရန်',
            'partial': 'တစ်စိတ်တစ်ပိုင်း',
            'overdue': 'ကျော်လွန်',
            'active': 'အသက်ဝင်',
            'inactive': 'မလှုပ်ရှား',
            'warning': 'သတိပေး',
            'info': 'အချက်အလက်',
        }
    }
    
    def __init__(self, status="active", show_text=True, parent=None):
        super().__init__(parent)
        self.status = status
        self.show_text = show_text
        self.lang = "en"
        self.setup_ui()
        self.set_status(status)
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        
        # Color indicator dot
        self.dot = QLabel()
        self.dot.setFixedSize(12, 12)
        self.dot.setStyleSheet(f"""
            QLabel {{
                background-color: {self.STATUS_COLORS.get('active', '#95a5a6')};
                border-radius: 6px;
            }}
        """)
        layout.addWidget(self.dot)
        
        # Text label
        self.text_label = QLabel()
        self.text_label.setStyleSheet("font-weight: 500;")
        layout.addWidget(self.text_label)
        
        self.setLayout(layout)
        
        # Make widget transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
    
    def set_status(self, status):
        """Set the status and update appearance"""
        self.status = status
        color = self.STATUS_COLORS.get(status, '#95a5a6')
        
        self.dot.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
        
        if self.show_text:
            label = self.STATUS_LABELS.get(self.lang, {}).get(status, status.capitalize())
            self.text_label.setText(label)
            self.text_label.setVisible(True)
        else:
            self.text_label.setVisible(False)
    
    def set_language(self, lang_code):
        """Update language"""
        self.lang = lang_code
        if self.show_text:
            label = self.STATUS_LABELS.get(lang_code, {}).get(self.status, self.status.capitalize())
            self.text_label.setText(label)
    
    def set_show_text(self, show):
        self.show_text = show
        self.text_label.setVisible(show)