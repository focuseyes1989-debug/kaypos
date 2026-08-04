# ui/design_system/combobox.py
"""
Primary ComboBox component with consistent styling
"""

from PyQt6.QtWidgets import QComboBox, QSizePolicy
from PyQt6.QtCore import Qt
from ui.design_system.theme import get_theme, get_theme_colors, is_dark_theme

class PrimaryComboBox(QComboBox):
    """
    Styled combobox with consistent theme-aware styling
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(34)
    
    def _setup_style(self):
        """Apply theme-aware styling"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        theme = get_theme()
        
        bg = colors.input_bg
        border = colors.input_border
        text = colors.text
        hover = colors.bg_hover
        
        # Popup styling
        popup_bg = colors.card_bg
        popup_hover = colors.bg_hover
        popup_selected = colors.primary
        
        self.setStyleSheet(f"""
            QComboBox {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {theme.radius.input}px;
                padding: {theme.spacing.input_padding_y}px {theme.spacing.input_padding_x}px;
                color: {text};
                font-size: {theme.typography.size_medium}pt;
                font-family: {theme.typography.font_family};
                min-height: 30px;
            }}
            QComboBox:hover {{
                border-color: {colors.border_hover};
            }}
            QComboBox:focus {{
                border-color: {colors.input_focus};
                border-width: 2px;
            }}
            QComboBox:disabled {{
                color: {colors.text_muted};
                opacity: 0.6;
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
                width: 28px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
                margin-right: 4px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {colors.text_secondary};
                margin-right: 4px;
            }}
            QComboBox QAbstractItemView {{
                background: {popup_bg};
                border: 1px solid {border};
                border-radius: {theme.radius.md}px;
                color: {text};
                selection-background: {popup_selected};
                selection-color: {colors.text_light};
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px;
                border: none;
                border-radius: {theme.radius.sm}px;
                min-height: 28px;
                color: {text};
                background: transparent;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {popup_hover};
                color: {text};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {popup_selected};
                color: {colors.text_light};
            }}
            QComboBox QAbstractItemView::item:selected:hover {{
                background: {popup_selected};
                color: {colors.text_light};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border-radius: 3px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors.scrollbar_handle};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors.scrollbar_handle_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
        """)
    
    def add_items(self, items: list):
        """Add multiple items at once"""
        self.addItems(items)
    
    def set_items(self, items: list):
        """Clear and add items"""
        self.clear()
        self.addItems(items)
    
    def get_selected_value(self) -> str:
        """Get the text of the current selection"""
        return self.currentText()
    
    def get_selected_data(self, role=Qt.ItemDataRole.UserRole):
        """Get the user data of the current selection"""
        return self.currentData(role)
    
    def select_by_text(self, text: str):
        """Select item by text"""
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)
    
    def select_by_data(self, data, role=Qt.ItemDataRole.UserRole):
        """Select item by user data"""
        for i in range(self.count()):
            if self.itemData(i, role) == data:
                self.setCurrentIndex(i)
                return True
        return False
    
    def update_theme(self):
        """Update theme when theme changes"""
        self._setup_style()
