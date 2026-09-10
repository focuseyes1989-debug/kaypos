# ui/dashboard/modern_card.py
from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QPainter
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors
from loguru import logger
from ui.design_system.metrics import CARD_HEIGHT, CARD_MIN_WIDTH, CARD_RADIUS, CARD_PADDING


class ModernSummaryCard(QFrame):
    """Shopeers စတိုင်လ် ခေတ်မီကဒ်"""
    
    clicked = pyqtSignal()
    
    def __init__(self, title, value, icon, color, trend=None, trend_value=None, subtitle=None, parent=None):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._icon_name = icon
        self._color = color
        self._trend = trend  # 'up' or 'down'
        self._trend_value = trend_value
        self._subtitle = subtitle
        self._is_dark = is_dark_theme()
        
        self.setMinimumHeight(CARD_HEIGHT)
        self.setMinimumWidth(CARD_MIN_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        self._setup_ui()
        self._apply_style()
        
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(*([CARD_PADDING] * 4))
        layout.setSpacing(4)
        
        # Top row: Icon and Trend
        top_layout = QHBoxLayout()
        top_layout.setSpacing(6)
        
        # Icon container
        self.icon_container = QFrame()
        self.icon_container.setFixedSize(36, 36)
        self.icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {self._color}20;
                border-radius: 8px;
                border: none;
            }}
        """)
        
        icon_layout = QVBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_icon()
        icon_layout.addWidget(self.icon_label)
        
        top_layout.addWidget(self.icon_container)
        top_layout.addStretch()
        
        # Trend indicator
        if self._trend and self._trend_value:
            self.trend_label = QLabel()
            self.trend_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            trend_color = "#2ecc71" if self._trend == "up" else "#e74c3c"
            arrow = "↑" if self._trend == "up" else "↓"
            self.trend_label.setText(f"{arrow} {self._trend_value}")
            self.trend_label.setStyleSheet(f"""
                color: {trend_color};
                font-size: 9pt;
                font-weight: 600;
                background: transparent;
                border: none;
                padding: 2px 6px;
                border-radius: 4px;
                background-color: {trend_color}20;
            """)
            top_layout.addWidget(self.trend_label)
        
        layout.addLayout(top_layout)
        
        # Value
        self.value_label = QLabel(str(self._value))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.value_label.setStyleSheet(f"""
            font-size: 18pt;
            font-weight: 700;
            color: {self._color};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.value_label)
        
        # Title and Subtitle
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(6)
        
        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet("""
            font-size: 8pt;
            font-weight: 500;
            color: #7f8c8d;
            background: transparent;
            border: none;
        """)
        bottom_layout.addWidget(self.title_label)
        
        if self._subtitle:
            self.subtitle_label = QLabel(self._subtitle)
            self.subtitle_label.setStyleSheet("""
                font-size: 7pt;
                color: #95a5a6;
                background: transparent;
                border: none;
            """)
            bottom_layout.addWidget(self.subtitle_label)
        
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
    
    def _load_icon(self):
        """Load SVG icon"""
        try:
            from ui.themes.theme_manager import get_icon_path
            
            icon_path = get_icon_path(self._icon_name)
            if icon_path and icon_path.exists():
                pixmap = QPixmap(str(icon_path))
                if not pixmap.isNull():
                    colored = pixmap.scaled(
                        18, 18,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    painter = QPainter(colored)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(colored.rect(), QColor(self._color))
                    painter.end()
                    
                    self.icon_label.setPixmap(colored)
                    self.icon_label.setText("")
                    return
        except Exception as e:
            logger.debug(f"Could not load icon: {e}")
        
        emoji_map = {
            "receipt_long": "💰",
            "money_off": "💸",
            "trending_up": "📈",
            "currency_exchange": "↩️",
            "percent_discount": "🏷️",
            "credit_card": "💳",
            "warning": "⚠️",
            "attach_money": "💰",
            "bar_chart": "📊",
            "savings": "📈",
        }
        self.icon_label.setText(emoji_map.get(self._icon_name, "📊"))
        self.icon_label.setStyleSheet(f"font-size: 16px; color: {self._color};")
    
    def _apply_style(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            ModernSummaryCard {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: {CARD_RADIUS}px;
            }}
            ModernSummaryCard:hover {{
                border-color: {colors['border_hover']};
                background-color: {colors['bg_hover']};
            }}
        """)
        self.value_label.setStyleSheet(f"color: {colors['text']}; font-size: 18pt; font-weight: 600;")
    
    def _on_theme_changed(self, theme_name):
        self._is_dark = is_dark_theme()
        self._apply_style()
    
    def set_value(self, value):
        self._value = value
        self.value_label.setText(str(value))
    
    def set_title(self, title):
        self._title = title
        self.title_label.setText(title)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
