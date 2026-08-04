# ui/widgets/toast_notification_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QRectF  # ✅ Added QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPen


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
        self.frame.setStyleSheet("""
            QFrame#toastFrame {
                background-color: #2f3136;
                border-radius: 8px;
                padding: 12px 16px;
            }
        """)
        
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
        self.frame.setStyleSheet(f"""
            QFrame#toastFrame {{
                background-color: #2f3136;
                border-radius: 8px;
                padding: 12px 16px;
                border-left: 4px solid {color};
            }}
        """)
        
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