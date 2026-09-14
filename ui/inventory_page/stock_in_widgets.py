# ui/inventory_page/stock_in_widgets.py
from PyQt6.QtWidgets import QLabel, QFrame
from PyQt6.QtCore import Qt
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager


class StockInfoLabel(QLabel):
    """Custom label for displaying stock information with consistent styling - Theme-aware"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._is_dark = is_dark_theme()
        self.apply_style()
        self.setVisible(False)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self.apply_style()
    
    def apply_style(self):
        """Apply theme-aware style"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        bg = colors.get("bg_hover", "#eef0ff")
        border = colors.get("border", "#dbe1ee")
        text = colors.get("text", "#172033")
        self.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                color: {text};
                background: {bg};
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 9pt;
                border: 1px solid {border};
            }}
        """)


class HeaderFrame(QFrame):
    """Custom header frame with gradient styling - Theme-aware"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        self.apply_style()
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self.apply_style()
    
    def apply_style(self):
        """Apply theme-aware style"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QFrame {{
                background: {colors.get('progress_bg', '#6675f5')};
                border-radius: 6px;
                padding: 2px;
            }}
        """)
