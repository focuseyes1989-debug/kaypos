# ui/design_system/dialog.py
"""
Primary Dialog component with consistent styling
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from ui.design_system.theme import get_theme, get_theme_colors, is_dark_theme
from ui.design_system.buttons import PrimaryButton, SecondaryButton, DangerButton
from ui.design_system.icon import get_icon

class PrimaryDialog(QDialog):
    """
    Modern dialog with consistent styling, header, and action buttons
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        self._setup_ui()
        self._apply_style()
        
        # Remove ? button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
    
    def _setup_ui(self):
        """Setup the dialog UI"""
        theme = get_theme()
        
        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        # Header
        self._header = QFrame()
        self._header.setObjectName("dialog_header")
        self._header_layout = QHBoxLayout(self._header)
        self._header_layout.setContentsMargins(theme.spacing.xl, theme.spacing.lg, theme.spacing.xl, theme.spacing.lg)
        
        self._title_icon = QLabel()
        self._title_icon.setFixedSize(24, 24)
        self._header_layout.addWidget(self._title_icon)
        
        self._title_label = QLabel()
        self._title_label.setObjectName("dialog_title")
        font = QFont()
        font.setPointSize(theme.typography.size_title)
        font.setWeight(theme.typography.weight_semibold)
        self._title_label.setFont(font)
        self._header_layout.addWidget(self._title_label)
        
        self._header_layout.addStretch()
        
        # Close button
        self._close_btn = QPushButton()
        self._close_btn.setObjectName("dialog_close")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.reject)
        self._header_layout.addWidget(self._close_btn)
        
        self._main_layout.addWidget(self._header)
        
        # Separator
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setObjectName("dialog_separator")
        self._main_layout.addWidget(self._separator)
        
        # Content area
        self._content_area = QFrame()
        self._content_area.setObjectName("dialog_content")
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(
            theme.spacing.xl, theme.spacing.lg,
            theme.spacing.xl, theme.spacing.lg
        )
        self._content_layout.setSpacing(theme.spacing.md)
        self._main_layout.addWidget(self._content_area, 1)
        
        # Buttons
        self._button_area = QFrame()
        self._button_area.setObjectName("dialog_buttons")
        self._button_layout = QHBoxLayout(self._button_area)
        self._button_layout.setContentsMargins(
            theme.spacing.xl, theme.spacing.md,
            theme.spacing.xl, theme.spacing.md
        )
        self._button_layout.setSpacing(theme.spacing.sm)
        self._button_layout.addStretch()
        self._main_layout.addWidget(self._button_area)
    
    def _apply_style(self):
        """Apply theme-aware styling"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        theme = get_theme()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.bg};
            }}
            QFrame#dialog_header {{
                background-color: {colors.card_bg};
                border-top-left-radius: {theme.radius.dialog}px;
                border-top-right-radius: {theme.radius.dialog}px;
            }}
            QLabel#dialog_title {{
                color: {colors.text};
                font-size: {theme.typography.size_title}pt;
                font-weight: {theme.typography.weight_semibold};
            }}
            QFrame#dialog_separator {{
                background-color: {colors.border};
                max-height: 1px;
                min-height: 1px;
                border: none;
            }}
            QFrame#dialog_content {{
                background-color: {colors.bg};
            }}
            QFrame#dialog_buttons {{
                background-color: {colors.bg_hover};
                border-bottom-left-radius: {theme.radius.dialog}px;
                border-bottom-right-radius: {theme.radius.dialog}px;
                border-top: 1px solid {colors.border};
            }}
            QPushButton#dialog_close {{
                background: transparent;
                border: none;
                border-radius: {theme.radius.sm}px;
                color: {colors.text_secondary};
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton#dialog_close:hover {{
                background: {colors.bg_hover};
                color: {colors.text};
            }}
            QPushButton#dialog_close:pressed {{
                background: {colors.bg_active};
            }}
        """)
        
        # Set close icon
        icon_color = colors.text_secondary
        icon = get_icon("close", 16, icon_color)
        if icon:
            self._close_btn.setIcon(icon)
            self._close_btn.setIconSize(Qt.QSize(16, 16))
    
    def set_title(self, title: str, icon_name: str = None):
        """Set dialog title and optional icon"""
        self._title_label.setText(title)
        if icon_name:
            colors = get_theme_colors()
            icon = get_icon(icon_name, 22, colors.primary)
            if icon:
                self._title_icon.setPixmap(icon.pixmap(22, 22))
    
    def set_content(self, widget: QWidget):
        """Set the content widget"""
        # Clear existing content
        for i in reversed(range(self._content_layout.count())):
            item = self._content_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
            self._content_layout.removeItem(item)
        
        self._content_layout.addWidget(widget)
    
    def add_button(self, button: QPushButton):
        """Add a button to the button area"""
        self._button_layout.insertWidget(self._button_layout.count() - 1, button)
    
    def add_primary_button(self, text: str, callback=None) -> PrimaryButton:
        """Add a primary action button"""
        btn = PrimaryButton(text)
        if callback:
            btn.clicked.connect(callback)
        self.add_button(btn)
        return btn
    
    def add_secondary_button(self, text: str, callback=None) -> SecondaryButton:
        """Add a secondary action button"""
        btn = SecondaryButton(text)
        if callback:
            btn.clicked.connect(callback)
        self.add_button(btn)
        return btn
    
    def add_danger_button(self, text: str, callback=None) -> DangerButton:
        """Add a danger/destructive action button"""
        btn = DangerButton(text)
        if callback:
            btn.clicked.connect(callback)
        self.add_button(btn)
        return btn
    
    def add_cancel_button(self, text: str = "Cancel", callback=None) -> SecondaryButton:
        """Add a cancel button"""
        btn = SecondaryButton(text)
        btn.clicked.connect(self.reject)
        if callback:
            btn.clicked.connect(callback)
        self.add_button(btn)
        return btn
    
    def sizeHint(self):
        """Return a reasonable size hint"""
        return Qt.QSize(500, 350)
    
    def update_theme(self):
        """Update theme when theme changes"""
        self._is_dark = is_dark_theme()
        self._apply_style()
