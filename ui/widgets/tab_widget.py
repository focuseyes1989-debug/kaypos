# tab_widget.py (standalone demo)
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QStackedWidget, QLabel,
                             QFrame, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QColor

class AnimatedTabButton(QPushButton):
    """Animated tab button with hover and active states"""
    def __init__(self, text, icon_text="", index=0):
        super().__init__(text)
        self.icon_text = icon_text
        self.index = index
        self.is_active = False
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        font = self.font()
        font.setPointSize(10)
        font.setWeight(600 if index == 0 else 500)
        self.setFont(font)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_anim.setDuration(200)
        
        self.update_style(False)
        
    def update_style(self, active):
        self.is_active = active
        if active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #1a2a44;
                    border: none;
                    border-radius: 20px;
                    padding: 8px 18px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #f8f9fc;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #8896ab;
                    border: none;
                    border-radius: 20px;
                    padding: 8px 18px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.3);
                    color: #2a3b5c;
                }
            """)
    
    def enterEvent(self, event):
        self.opacity_anim.setStartValue(0.8)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.opacity_anim.setStartValue(1.0)
        self.opacity_anim.setEndValue(0.8)
        self.opacity_anim.start()
        super().leaveEvent(event)


class TabWidget(QWidget):
    """Custom Tab Widget with No.4 Design"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)
        
        # Container
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 30px;
                border: none;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Tab navigation bar - No.4 Design
        nav_bar = QFrame()
        nav_bar.setFixedHeight(58)
        nav_bar.setStyleSheet("""
            QFrame {
                background-color: #f8f9fc;
                border-radius: 30px;
                margin: 8px;
            }
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(5)
        
        self.tab_buttons = []
        tab_data = [
            ("🏠 Home", "home", 0),
            ("❤️ Likes", "likes", 1),
            ("👤 Profile", "profile", 2)
        ]
        
        for text, icon, idx in tab_data:
            btn = AnimatedTabButton(text, icon, idx)
            btn.clicked.connect(lambda checked, b=btn: self.switch_tab(b))
            nav_layout.addWidget(btn)
            self.tab_buttons.append(btn)
        
        if self.tab_buttons:
            self.tab_buttons[0].update_style(True)
        
        self.stacked_widget = QStackedWidget()
        self.create_content_panels()
        
        container_layout.addWidget(nav_bar)
        container_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(container)
        
        self.setMinimumWidth(500)
        self.setStyleSheet("QWidget { background-color: #f0f2f5; }")
    
    def create_content_panels(self):
        contents = [
            {"title": "🏠 Home", "text": "Welcome back! Here's your personalized feed...", "badge": "✨ 12 new updates"},
            {"title": "❤️ Likes", "text": "All the things you've loved so far...", "badge": "⭐ 48 saved items"},
            {"title": "👤 Profile", "text": "Manage your account, view your activity...", "badge": "🔒 Privacy settings"}
        ]
        
        for content in contents:
            panel = QWidget()
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(30, 20, 30, 30)
            panel_layout.setSpacing(15)
            
            title = QLabel(content["title"])
            title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
            title.setFont(title_font)
            title.setStyleSheet("color: #1a2a44;")
            
            text_label = QLabel(content["text"])
            text_label.setWordWrap(True)
            text_font = QFont("Segoe UI", 10)
            text_label.setFont(text_font)
            text_label.setStyleSheet("color: #5a6e8a; line-height: 1.7;")
            
            badge = QLabel(content["badge"])
            badge.setFixedHeight(30)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet("""
                QLabel {
                    background-color: #eef3ff;
                    color: #4a6cf7;
                    border-radius: 15px;
                    padding: 5px 18px;
                    font-weight: 600;
                    font-size: 11px;
                }
            """)
            
            panel_layout.addWidget(title)
            panel_layout.addWidget(text_label)
            panel_layout.addStretch()
            panel_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)
            self.stacked_widget.addWidget(panel)
    
    def switch_tab(self, clicked_button):
        for i, btn in enumerate(self.tab_buttons):
            if btn == clicked_button:
                for b in self.tab_buttons:
                    b.update_style(False)
                clicked_button.update_style(True)
                self.stacked_widget.setCurrentIndex(i)
                
                current_widget = self.stacked_widget.currentWidget()
                opacity_effect = QGraphicsOpacityEffect(current_widget)
                current_widget.setGraphicsEffect(opacity_effect)
                
                anim = QPropertyAnimation(opacity_effect, b"opacity")
                anim.setDuration(300)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()
                break


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tab Design No.4 - PyQt6")
        self.setGeometry(100, 100, 600, 450)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TabWidget())


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 242, 245))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()