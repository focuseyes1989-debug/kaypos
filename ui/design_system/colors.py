"""
POS System Color Design System
Project-wide color constants for consistent UI theming
"""

from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass(frozen=True)
class ColorPalette:
    """Immutable color palette container with hex and RGB support"""
    
    # Brand Colors
    PRIMARY: str = "#4A6CF7"        # Main brand blue
    SECONDARY: str = "#6C757D"      # Secondary gray
    
    # Semantic Colors
    SUCCESS: str = "#28A745"        # Success green
    WARNING: str = "#FFC107"        # Warning yellow
    ERROR: str = "#DC3545"          # Error red
    
    # Neutral Colors
    BACKGROUND: str = "#F8F9FA"     # Main background
    SURFACE: str = "#FFFFFF"        # Card/surface background
    BORDER: str = "#DEE2E6"         # Border color
    
    # Text Colors
    TEXT_PRIMARY: str = "#212529"   # Main text
    TEXT_SECONDARY: str = "#6C757D" # Secondary text
    
    def rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgba(self, hex_color: str, alpha: float = 1.0) -> str:
        """Convert hex color to RGBA string for QSS"""
        r, g, b = self.rgb(hex_color)
        return f"rgba({r}, {g}, {b}, {alpha})"
    
    def get_all_colors(self) -> Dict[str, str]:
        """Return all colors as dictionary"""
        return {
            "primary": self.PRIMARY,
            "secondary": self.SECONDARY,
            "success": self.SUCCESS,
            "warning": self.WARNING,
            "error": self.ERROR,
            "background": self.BACKGROUND,
            "surface": self.SURFACE,
            "text_primary": self.TEXT_PRIMARY,
            "text_secondary": self.TEXT_SECONDARY,
            "border": self.BORDER,
        }

# Singleton instance
COLORS = ColorPalette()

# QSS Style Template (for PyQt6 stylesheets)
QSS_COLORS = {
    "primary": COLORS.PRIMARY,
    "primary_hover": "#3B5DE7",      # Darker primary
    "primary_pressed": "#2A4FD4",    # Even darker
    "secondary": COLORS.SECONDARY,
    "success": COLORS.SUCCESS,
    "warning": COLORS.WARNING,
    "error": COLORS.ERROR,
    "background": COLORS.BACKGROUND,
    "surface": COLORS.SURFACE,
    "text_primary": COLORS.TEXT_PRIMARY,
    "text_secondary": COLORS.TEXT_SECONDARY,
    "border": COLORS.BORDER,
}

def get_qss_variables() -> str:
    """Generate QSS variable declarations for stylesheets"""
    return "\n".join([f"${key}: {value};" for key, value in QSS_COLORS.items()])

# Light Theme QSS for PyQt6
LIGHT_THEME_QSS = """
/* Base Application */
QWidget {
    background-color: #F8F9FA;
    color: #212529;
    font-family: 'Segoe UI', Arial, sans-serif;
}

/* Main Window */
QMainWindow {
    background-color: #F8F9FA;
}

/* Push Buttons */
QPushButton {
    background-color: #4A6CF7;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #3B5DE7;
}

QPushButton:pressed {
    background-color: #2A4FD4;
}

QPushButton:disabled {
    background-color: #6C757D;
    color: #DEE2E6;
}

/* Secondary Button */
QPushButton[secondary="true"] {
    background-color: #6C757D;
}

QPushButton[secondary="true"]:hover {
    background-color: #5A6268;
}

/* Success Button */
QPushButton[success="true"] {
    background-color: #28A745;
}

QPushButton[success="true"]:hover {
    background-color: #218838;
}

/* Warning Button */
QPushButton[warning="true"] {
    background-color: #FFC107;
    color: #212529;
}

QPushButton[warning="true"]:hover {
    background-color: #E0A800;
}

/* Danger Button */
QPushButton[danger="true"] {
    background-color: #DC3545;
}

QPushButton[danger="true"]:hover {
    background-color: #C82333;
}

/* Line Edits */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: white;
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    padding: 6px 10px;
    color: #212529;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #4A6CF7;
    outline: none;
}

QLineEdit:disabled {
    background-color: #F8F9FA;
    color: #6C757D;
}

/* Labels */
QLabel {
    color: #212529;
}

QLabel[secondary="true"] {
    color: #6C757D;
}

QLabel[heading="true"] {
    font-size: 18px;
    font-weight: 600;
}

QLabel[subheading="true"] {
    font-size: 14px;
    font-weight: 500;
    color: #6C757D;
}

/* ComboBox Dropdown */
QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(:/icons/down_arrow.svg);
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    padding: 4px 8px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #4A6CF7;
    color: white;
}

/* Tables */
QTableWidget, QListWidget, QTreeWidget {
    background-color: white;
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    gridline-color: #F8F9FA;
    selection-background-color: #4A6CF7;
    selection-color: white;
}

QTableWidget::item, QListWidget::item, QTreeWidget::item {
    padding: 4px 8px;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #4A6CF7;
    color: white;
}

QHeaderView::section {
    background-color: #F8F9FA;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid #DEE2E6;
    border-bottom: 1px solid #DEE2E6;
    font-weight: 600;
    color: #212529;
}

/* Scroll Bars */
QScrollBar:vertical {
    background-color: #F8F9FA;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #DEE2E6;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6C757D;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #F8F9FA;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #DEE2E6;
    border-radius: 5px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #6C757D;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Group Boxes */
QGroupBox {
    border: 1px solid #DEE2E6;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: 500;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #212529;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #DEE2E6;
    border-radius: 6px;
    background-color: white;
}

QTabBar::tab {
    background-color: #F8F9FA;
    border: 1px solid #DEE2E6;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
    color: #6C757D;
}

QTabBar::tab:selected {
    background-color: white;
    color: #4A6CF7;
    border-bottom: 2px solid #4A6CF7;
}

QTabBar::tab:hover:!selected {
    background-color: #E9ECEF;
}

/* Progress Bars */
QProgressBar {
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    text-align: center;
    color: #212529;
    background-color: #F8F9FA;
}

QProgressBar::chunk {
    background-color: #4A6CF7;
    border-radius: 4px;
}

QProgressBar::chunk[success="true"] {
    background-color: #28A745;
}

QProgressBar::chunk[warning="true"] {
    background-color: #FFC107;
}

QProgressBar::chunk[danger="true"] {
    background-color: #DC3545;
}

/* Status Bar */
QStatusBar {
    background-color: #F8F9FA;
    color: #6C757D;
    border-top: 1px solid #DEE2E6;
}

QStatusBar::item {
    border: none;
}

/* Menu Bar */
QMenuBar {
    background-color: white;
    border-bottom: 1px solid #DEE2E6;
    color: #212529;
}

QMenuBar::item:selected {
    background-color: #4A6CF7;
    color: white;
}

QMenu {
    background-color: white;
    border: 1px solid #DEE2E6;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #4A6CF7;
    color: white;
}

/* Tool Tips */
QToolTip {
    background-color: #212529;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}

/* Dialog Buttons Box */
QDialogButtonBox QPushButton {
    min-width: 80px;
}

QDialogButtonBox QPushButton[role="accept"] {
    background-color: #4A6CF7;
}

QDialogButtonBox QPushButton[role="reject"] {
    background-color: #6C757D;
}
"""

def apply_theme_to_app(app, theme_qss: str = LIGHT_THEME_QSS):
    """Apply the color theme to a PyQt6 application"""
    app.setStyleSheet(theme_qss)

# Usage example:
if __name__ == "__main__":
    # Print all colors for verification
    print("=== POS Color System ===")
    for name, value in COLORS.get_all_colors().items():
        print(f"{name.upper():15} : {value}")
    
    print("\n=== QSS Variables ===")
    print(get_qss_variables())
