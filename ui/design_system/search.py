# ui/design_system/search.py
"""
Search Line Edit component with clear button and search icon
"""

from PyQt6.QtWidgets import QLineEdit, QHBoxLayout, QWidget, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from ui.design_system.theme import get_theme, get_theme_colors, is_dark_theme
from ui.design_system.icon import get_icon

class SearchLineEdit(QWidget):
    """
    Search input with icon and clear button
    """
    
    search_changed = pyqtSignal(str)
    search_cleared = pyqtSignal()
    return_pressed = pyqtSignal()
    
    def __init__(self, placeholder: str = "Search...", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_search)
        self._debounce_delay = 300  # ms
        
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        """Setup the search widget layout"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Input field
        self._input = QLineEdit()
        self._input.setPlaceholderText(self._placeholder)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self.return_pressed.emit)
        layout.addWidget(self._input, 1)
        
        # Clear button
        self._clear_btn = QPushButton()
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear)
        self._clear_btn.setFixedSize(24, 24)
        self._clear_btn.setVisible(False)
        layout.addWidget(self._clear_btn)
        
        self.setFocusProxy(self._input)
    
    def _apply_style(self):
        """Apply theme-aware styling"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        theme = get_theme()
        
        # Input style
        input_style = f"""
            QLineEdit {{
                padding: {theme.spacing.input_padding_y}px {theme.spacing.input_padding_x + 28}px {theme.spacing.input_padding_y}px {theme.spacing.input_padding_x}px;
                border: 1px solid {colors.input_border};
                border-radius: {theme.radius.input}px;
                background: {colors.input_bg};
                color: {colors.text};
                font-size: {theme.typography.size_medium}pt;
                font-family: {theme.typography.font_family};
                selection-background-color: {colors.primary};
                selection-color: {colors.text_light};
            }}
            QLineEdit:focus {{
                border-color: {colors.input_focus};
                border-width: 2px;
            }}
            QLineEdit:hover {{
                border-color: {colors.border_hover};
            }}
            QLineEdit::placeholder {{
                color: {colors.text_muted};
            }}
        """
        self._input.setStyleSheet(input_style)
        
        # Clear button style
        clear_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {theme.radius.circle}px;
                color: {colors.text_muted};
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {colors.bg_hover};
                color: {colors.text};
            }}
        """
        self._clear_btn.setStyleSheet(clear_style)
        
        # Set search icon
        icon_color = colors.text_muted
        icon = get_icon("search", 18, icon_color)
        if icon:
            self._input.addAction(icon, QLineEdit.ActionPosition.LeadingPosition)
        
        # Set clear icon
        clear_icon = get_icon("close", 14, colors.text_muted)
        if clear_icon:
            self._clear_btn.setIcon(clear_icon)
            self._clear_btn.setIconSize(QSize(14, 14))
    
    def _on_text_changed(self, text: str):
        """Handle text change with debounce"""
        self._clear_btn.setVisible(bool(text))
        self._debounce_timer.start(self._debounce_delay)
    
    def _emit_search(self):
        """Emit search signal after debounce"""
        self.search_changed.emit(self._input.text())
    
    def clear(self):
        """Clear the search input"""
        self._input.clear()
        self.search_cleared.emit()
        self._input.setFocus()
    
    def get_text(self) -> str:
        """Get current search text"""
        return self._input.text()
    
    def set_text(self, text: str):
        """Set search text programmatically"""
        self._input.setText(text)
    
    def set_placeholder(self, text: str):
        """Set placeholder text"""
        self._placeholder = text
        self._input.setPlaceholderText(text)
    
    def set_focus(self):
        """Set focus to input"""
        self._input.setFocus()
    
    def select_all(self):
        """Select all text"""
        self._input.selectAll()
    
    def set_debounce_delay(self, ms: int):
        """Set debounce delay in milliseconds"""
        self._debounce_delay = max(50, ms)
    
    def update_theme(self):
        """Update theme when theme changes"""
        self._apply_style()
