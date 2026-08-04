# ui/products_page/product_form_widgets.py
from PyQt6.QtWidgets import QLabel, QFrame
from PyQt6.QtCore import Qt


class FormHeaderFrame(QFrame):
    """Custom header frame with gradient styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5865f2, stop:1 #8e44ad);
                border-radius: 8px;
                padding: 5px;
            }
        """)


class InfoLabel(QLabel):
    """Custom label for displaying information with consistent styling"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QLabel {
                color: #5865f2;
                font-size: 9pt;
                padding: 6px 12px;
                background: #ebf5fb;
                border-radius: 4px;
                font-weight: 500;
            }
        """)
        self.setWordWrap(True)


class StatusBadge(QLabel):
    """Custom status badge"""
    
    def __init__(self, text="", status_type="info", parent=None):
        super().__init__(text, parent)
        
        colors = {
            "info": ("#3498db", "#d6eaf8"),
            "success": ("#27ae60", "#d5f5e3"),
            "warning": ("#f39c12", "#fdebd0"),
            "danger": ("#e74c3c", "#fadbd8")
        }
        
        color, bg = colors.get(status_type, colors["info"])
        
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: {bg};
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: 600;
            }}
        """)