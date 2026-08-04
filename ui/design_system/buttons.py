# ui/design_system/buttons.py
"""
Design System Buttons
Primary, Secondary, Danger, Success, Warning variants
"""

from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont
from ui.design_system.theme import get_theme, get_theme_colors, is_dark_theme
from ui.design_system.icon import get_icon

class BaseButton(QPushButton):
    """Base button with hover animation and consistent styling"""
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._opacity = 1.0
        self._animating = False
        self._icon_name = None
        self._icon_size = 18
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        
        # Hover animation
        self._hover_anim = QPropertyAnimation(self, b"opacity")
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._setup_style()
    
    def _setup_style(self):
        """Setup base styles (overridden by subclasses)"""
        pass
    
    def set_icon(self, icon_name: str, size: int = 18):
        """Set icon for the button"""
        self._icon_name = icon_name
        self._icon_size = size
        self._update_icon()
    
    def _update_icon(self):
        """Update button icon"""
        if self._icon_name:
            color = self._get_icon_color()
            icon = get_icon(self._icon_name, self._icon_size, color)
            if icon:
                self.setIcon(icon)
                self.setIconSize(QSize(self._icon_size, self._icon_size))
    
    def _get_icon_color(self) -> str:
        """Get icon color based on button state"""
        colors = get_theme_colors()
        if self.isEnabled():
            return colors.text_light
        return colors.text_muted
    
    def set_opacity(self, value: float):
        self._opacity = value
        self.update()
    
    def get_opacity(self) -> float:
        return self._opacity
    
    opacity = pyqtProperty(float, get_opacity, set_opacity)
    
    def enterEvent(self, event):
        if self.isEnabled() and not self._animating:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(1.0)
            self._hover_anim.setEndValue(0.85)
            self._hover_anim.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        if self.isEnabled() and not self._animating:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(0.85)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Apply opacity
        painter.setOpacity(self._opacity)
        
        super().paintEvent(event)
        painter.end()

class PrimaryButton(BaseButton):
    """Primary action button - uses brand color"""
    
    def _setup_style(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.primary};
                color: {colors.text_light};
                border: none;
                border-radius: {get_theme().radius.button}px;
                padding: {get_theme().spacing.button_padding_y}px {get_theme().spacing.button_padding_x}px;
                font-size: {get_theme().typography.size_medium}pt;
                font-weight: {get_theme().typography.weight_semibold};
                min-height: 32px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.primary_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.primary_active};
            }}
            QPushButton:disabled {{
                background-color: {colors.text_muted};
                color: {colors.text_light};
                opacity: 0.6;
            }}
        """)

class SecondaryButton(BaseButton):
    """Secondary action button - outlined style"""
    
    def _setup_style(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        border_color = colors.border
        text_color = colors.text
        
        if is_dark:
            border_color = "#5a5f6b"
            text_color = "#dcddde"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: {get_theme().radius.button}px;
                padding: {get_theme().spacing.button_padding_y - 1}px {get_theme().spacing.button_padding_x - 1}px;
                font-size: {get_theme().typography.size_medium}pt;
                font-weight: {get_theme().typography.weight_medium};
                min-height: 32px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.bg_hover};
                border-color: {colors.border_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.bg_active};
            }}
            QPushButton:disabled {{
                color: {colors.text_muted};
                border-color: {colors.border};
                opacity: 0.6;
            }}
        """)
    
    def _get_icon_color(self) -> str:
        colors = get_theme_colors()
        if self.isEnabled():
            return colors.text if not is_dark_theme() else colors.text_light
        return colors.text_muted

class DangerButton(BaseButton):
    """Danger/Destructive action button"""
    
    def _setup_style(self):
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.danger};
                color: {colors.text_light};
                border: none;
                border-radius: {get_theme().radius.button}px;
                padding: {get_theme().spacing.button_padding_y}px {get_theme().spacing.button_padding_x}px;
                font-size: {get_theme().typography.size_medium}pt;
                font-weight: {get_theme().typography.weight_semibold};
                min-height: 32px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.danger_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.danger_hover};
                opacity: 0.85;
            }}
            QPushButton:disabled {{
                background-color: {colors.text_muted};
                color: {colors.text_light};
                opacity: 0.6;
            }}
        """)

class SuccessButton(BaseButton):
    """Success/Confirm action button"""
    
    def _setup_style(self):
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.success};
                color: {colors.text_light};
                border: none;
                border-radius: {get_theme().radius.button}px;
                padding: {get_theme().spacing.button_padding_y}px {get_theme().spacing.button_padding_x}px;
                font-size: {get_theme().typography.size_medium}pt;
                font-weight: {get_theme().typography.weight_semibold};
                min-height: 32px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.success_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.success_hover};
                opacity: 0.85;
            }}
            QPushButton:disabled {{
                background-color: {colors.text_muted};
                color: {colors.text_light};
                opacity: 0.6;
            }}
        """)

class WarningButton(BaseButton):
    """Warning/Caution action button"""
    
    def _setup_style(self):
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.warning};
                color: {colors.text_light};
                border: none;
                border-radius: {get_theme().radius.button}px;
                padding: {get_theme().spacing.button_padding_y}px {get_theme().spacing.button_padding_x}px;
                font-size: {get_theme().typography.size_medium}pt;
                font-weight: {get_theme().typography.weight_semibold};
                min-height: 32px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {colors.warning_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.warning_hover};
                opacity: 0.85;
            }}
            QPushButton:disabled {{
                background-color: {colors.text_muted};
                color: {colors.text_light};
                opacity: 0.6;
            }}
        """)
