# ui/inventory_page/stock_out_widgets.py
from PyQt6.QtWidgets import QLabel, QFrame
from PyQt6.QtCore import Qt
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme


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
