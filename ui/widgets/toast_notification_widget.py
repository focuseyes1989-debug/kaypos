# ui/widgets/toast_notification_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QRectF  # ✅ Added QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPen
from ui.themes.theme_manager import get_theme_colors, theme_manager


class ToastNotificationWidget(QWidget):
    """အကြောင်းကြားချက် Popup Widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
        theme_manager.theme_changed.connect(self._apply_theme)
        
        # Auto-hide timer
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_animation)
        
        # Animation
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Main frame
        self.frame = QFrame()
        self.frame.setObjectName("toastFrame")
        self._accent_color = get_theme_colors()['progress_bg']
        
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setSpacing(12)
        
        # Icon
        self.icon_label = QLabel("✅")
        self.icon_label.setStyleSheet("font-size: 20px;")
        frame_layout.addWidget(self.icon_label)
        
        # Message
        self.message_label = QLabel()
        self.message_label.setStyleSheet("""
            color: white;
            font-size: 13px;
            font-weight: 500;
        """)
        self.message_label.setWordWrap(True)
        frame_layout.addWidget(self.message_label, 1)
        
        # Close button
        self.close_btn = QPushButton("✕")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #b9bbbe;
                border: none;
                font-size: 14px;
                padding: 4px;
            }
            QPushButton:hover {
                color: white;
                background-color: #40444b;
                border-radius: 4px;
            }
        """)
        self.close_btn.clicked.connect(self.hide_animation)
        frame_layout.addWidget(self.close_btn)
        
        layout.addWidget(self.frame)
        self.setLayout(layout)
        self._apply_theme()

    def _apply_theme(self, *_):
        colors = get_theme_colors()
        self.frame.setStyleSheet(f"""
            QFrame#toastFrame {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-left: 4px solid {self._accent_color};
                border-radius: 10px;
                padding: 12px 16px;
            }}
        """)
        self.message_label.setStyleSheet(f"color: {colors['text']}; font-size: 13px; font-weight: 600;")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {colors['text_secondary']}; border: none; border-radius: 6px; padding: 4px; }}
            QPushButton:hover {{ color: {colors['text']}; background-color: {colors['bg_hover']}; }}
        """)
        
    def show_toast(self, message, type="success", duration=3000):
        """Toast ကို ပြသရန်"""
        # Set icon based on type
        icons = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        colors = {
            "success": "#2ecc71",
            "error": "#e74c3c",
            "warning": "#f39c12",
            "info": "#3498db"
        }
        
        self.icon_label.setText(icons.get(type, "ℹ️"))
        self.message_label.setText(message)
        
        # Update frame border color
        color = colors.get(type, "#3498db")
        self._accent_color = color
        self._apply_theme()
        
        # Position at bottom-right
        parent = self.parent()
        if parent:
            parent_rect = parent.rect()
            self.setGeometry(
                parent_rect.width() - 400,
                parent_rect.height() - 100,
                380,
                60
            )
        
        self.show()
        self.timer.start(duration)
        
    def hide_animation(self):
        """ပိတ်သွားတဲ့ animation"""
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(QRect(
            self.x(),
            self.y() + 100,
            self.width(),
            self.height()
        ))
        self.animation.finished.connect(self.hide)
        self.animation.start()
        
    def paintEvent(self, event):
        """Background shadow ဆွဲရန်"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect().adjusted(2, 2, -2, -2)
        # ✅ FIX: Convert QRect to QRectF
        path.addRoundedRect(QRectF(rect), 8, 8)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
        painter.drawPath(path)
        
        super().paintEvent(event)
