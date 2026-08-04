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
        
        if is_dark:
            self.setStyleSheet(f"""
                QLabel {{
                    font-weight: 600;
                    color: #dcddde;
                    background: #40444b;
                    padding: 6px 16px;
                    border-radius: 6px;
                    font-size: 10pt;
                    border: 1px solid #40444b;
                }}
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    font-weight: 600;
                    color: #2c3e50;
                    background: #ecf0f1;
                    padding: 6px 16px;
                    border-radius: 6px;
                    font-size: 10pt;
                    border: 1px solid #dfe6e9;
                }
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