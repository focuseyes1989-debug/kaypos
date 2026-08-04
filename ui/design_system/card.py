# ui/design_system/card.py
"""
Stat Card component for displaying metrics and KPIs
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush
from ui.design_system.theme import get_theme, get_theme_colors, is_dark_theme
from ui.design_system.icon import get_icon

class StatCard(QFrame):
    """
    Statistics card for displaying metrics with icon and optional trend
    """
    
    clicked = pyqtSignal()
    
    def __init__(self, title: str = "", value: str = "0", icon_name: str = "",
                 color: str = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._icon_name = icon_name
        self._color = color or "#5865f2"
        self._trend = None
        self._trend_value = None
        
        self._setup_ui()
        self._apply_style()
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _setup_ui(self):
        """Setup the card UI"""
        theme = get_theme()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.spacing.lg, theme.spacing.lg, theme.spacing.lg, theme.spacing.lg)
        layout.setSpacing(theme.spacing.xs)
        
        # Top row: Icon and Trend
        self._top_layout = QHBoxLayout()
        self._top_layout.setSpacing(theme.spacing.sm)
        
        # Icon container
        self._icon_container = QFrame()
        self._icon_container.setFixedSize(36, 36)
        self._icon_layout = QVBoxLayout(self._icon_container)
        self._icon_layout.setContentsMargins(0, 0, 0, 0)
        self._icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_layout.addWidget(self._icon_label)
        
        self._top_layout.addWidget(self._icon_container)
        self._top_layout.addStretch()
        
        # Trend indicator
        self._trend_container = QFrame()
        self._trend_container.setVisible(False)
        trend_layout = QHBoxLayout(self._trend_container)
        trend_layout.setContentsMargins(0, 0, 0, 0)
        trend_layout.setSpacing(4)
        
        self._trend_label = QLabel()
        self._trend_label.setStyleSheet("font-size: 9pt; font-weight: 600;")
        
        self._trend_arrow = QLabel()
        self._trend_arrow.setStyleSheet("font-size: 10pt;")
        
        trend_layout.addWidget(self._trend_arrow)
        trend_layout.addWidget(self._trend_label)
        
        self._top_layout.addWidget(self._trend_container)
        
        layout.addLayout(self._top_layout)
        
        # Value
        self._value_label = QLabel(self._value)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font = self._value_label.font()
        font.setPointSize(18)
        font.setWeight(700)
        self._value_label.setFont(font)
        layout.addWidget(self._value_label)
        
        # Title
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("stat_title")
        font = self._title_label.font()
        font.setPointSize(9)
        font.setWeight(500)
        self._title_label.setFont(font)
        layout.addWidget(self._title_label)
    
    def _apply_style(self):
        """Apply theme-aware styling"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        theme = get_theme()
        
        # Card style
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.card_bg};
                border: 1px solid {colors.border};
                border-radius: {theme.radius.card}px;
                padding: 0px;
            }}
            QFrame:hover {{
                border-color: {colors.border_hover};
                background-color: {colors.bg_hover if not is_dark else colors.card_bg};
            }}
            QLabel#stat_title {{
                color: {colors.text_secondary};
                font-size: {theme.typography.size_medium}pt;
                font-weight: {theme.typography.weight_medium};
            }}
        """)
        
        # Icon container style
        self._icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {self._color}20;
                border-radius: 8px;
                border: none;
            }}
        """)
        
        # Value color
        self._value_label.setStyleSheet(f"color: {self._color};")
        
        # Set icon
        self._update_icon()
    
    def _update_icon(self):
        """Update the icon"""
        if self._icon_name:
            icon = get_icon(self._icon_name, 20, self._color)
            if icon:
                self._icon_label.setPixmap(icon.pixmap(20, 20))
            else:
                # Fallback to text
                self._icon_label.setText("📊")
                self._icon_label.setStyleSheet(f"font-size: 16px; color: {self._color};")
    
    def set_value(self, value: str):
        """Set the value display"""
        self._value = value
        self._value_label.setText(value)
    
    def set_title(self, title: str):
        """Set the title"""
        self._title = title
        self._title_label.setText(title)
    
    def set_icon(self, icon_name: str):
        """Set the icon"""
        self._icon_name = icon_name
        self._update_icon()
    
    def set_color(self, color: str):
        """Set the accent color"""
        self._color = color
        self._value_label.setStyleSheet(f"color: {color};")
        self._icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {color}20;
                border-radius: 8px;
                border: none;
            }}
        """)
        self._update_icon()
    
    def set_trend(self, value: float, direction: str = "up"):
        """Set trend indicator"""
        self._trend = value
        self._trend_value = value
        self._trend_container.setVisible(True)
        
        if direction == "up":
            self._trend_arrow.setText("↑")
            self._trend_arrow.setStyleSheet("color: #2ecc71; font-size: 10pt;")
            self._trend_label.setStyleSheet("color: #2ecc71; font-size: 9pt; font-weight: 600;")
        else:
            self._trend_arrow.setText("↓")
            self._trend_arrow.setStyleSheet("color: #e74c3c; font-size: 10pt;")
            self._trend_label.setStyleSheet("color: #e74c3c; font-size: 9pt; font-weight: 600;")
        
        self._trend_label.setText(f"{abs(value):.1f}%")
    
    def hide_trend(self):
        """Hide trend indicator"""
        self._trend_container.setVisible(False)
    
    def mousePressEvent(self, event):
        """Handle mouse click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def update_theme(self):
        """Update theme when theme changes"""
        self._apply_style()
