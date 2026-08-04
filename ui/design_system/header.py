# ui/design_system/header.py
"""
Page Header component with title, subtitle, and actions
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from ui.design_system.theme import get_theme, get_theme_colors
from ui.design_system.icon import get_icon

class PageHeader(QWidget):
    """
    Page header with title, subtitle, and action buttons area
    """
    
    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        """Setup the header UI"""
        theme = get_theme()
        
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, theme.spacing.md)
        self._main_layout.setSpacing(theme.spacing.xs)
        
        # Top row: Title + Actions
        self._top_layout = QHBoxLayout()
        self._top_layout.setSpacing(theme.spacing.md)
        
        # Title container
        self._title_container = QWidget()
        title_layout = QVBoxLayout(self._title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        
        # Title with optional icon
        self._title_icon = QLabel()
        self._title_icon.setFixedSize(20, 20)
        self._title_icon.setVisible(False)
        
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)
        
        title_row.addWidget(self._title_icon)
        
        self._title_label = QLabel(self._title)
        font = QFont()
        font.setPointSize(get_theme().typography.size_heading)
        font.setWeight(get_theme().typography.weight_semibold)
        self._title_label.setFont(font)
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        
        title_layout.addLayout(title_row)
        
        # Subtitle
        self._subtitle_label = QLabel(self._subtitle)
        self._subtitle_label.setWordWrap(True)
        title_layout.addWidget(self._subtitle_label)
        
        self._top_layout.addWidget(self._title_container, 1)
        
        # Actions area
        self._actions_container = QWidget()
        self._actions_layout = QHBoxLayout(self._actions_container)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(get_theme().spacing.sm)
        self._actions_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self._top_layout.addWidget(self._actions_container)
        
        self._main_layout.addLayout(self._top_layout)
        
        # Separator
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setObjectName("header_separator")
        self._main_layout.addWidget(self._separator)
    
    def _apply_style(self):
        """Apply theme-aware styling"""
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QLabel#header_title {{
                color: {colors.text};
            }}
            QLabel#header_subtitle {{
                color: {colors.text_secondary};
                font-size: {get_theme().typography.size_medium}pt;
            }}
            QFrame#header_separator {{
                background-color: {colors.border};
                max-height: 1px;
                min-height: 1px;
                border: none;
            }}
        """)
        
        self._title_label.setObjectName("header_title")
        self._subtitle_label.setObjectName("header_subtitle")
    
    def set_title(self, title: str, icon_name: str = None):
        """Set the page title and optional icon"""
        self._title = title
        self._title_label.setText(title)
        
        if icon_name:
            colors = get_theme_colors()
            icon = get_icon(icon_name, 18, colors.primary)
            if icon:
                self._title_icon.setPixmap(icon.pixmap(18, 18))
                self._title_icon.setVisible(True)
        else:
            self._title_icon.setVisible(False)
    
    def set_subtitle(self, subtitle: str):
        """Set the page subtitle"""
        self._subtitle = subtitle
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))
    
    def add_action(self, widget: QWidget):
        """Add an action widget to the header"""
        self._actions_layout.addWidget(widget)
    
    def add_action_button(self, button):
        """Add an action button to the header"""
        self._actions_layout.addWidget(button)
    
    def clear_actions(self):
        """Clear all action widgets"""
        for i in reversed(range(self._actions_layout.count())):
            item = self._actions_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
            self._actions_layout.removeItem(item)
    
    def update_theme(self):
        """Update theme when theme changes"""
        self._apply_style()
