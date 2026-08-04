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
        is_dark = is_dark_theme()
        
        if is_dark:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4752c4, stop:1 #3c45a3);
                    border-radius: 8px;
                    padding: 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5865f2, stop:1 #4752c4);
                    border-radius: 8px;
                    padding: 5px;
                }
            """)