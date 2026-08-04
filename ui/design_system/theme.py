# ui/design_system/theme.py
"""
Centralized Theme System
Dark / Light theme support with consistent design tokens
"""

from dataclasses import dataclass
from typing import Dict, Optional
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

@dataclass
class ThemeColors:
    """Color palette for the design system"""
    # Primary colors
    primary: str = "#5865f2"
    primary_hover: str = "#4752c4"
    primary_active: str = "#3c45a3"
    primary_light: str = "#e8ebff"
    primary_dark: str = "#40444b"
    
    # Semantic colors
    success: str = "#2ecc71"
    success_hover: str = "#27ae60"
    danger: str = "#e74c3c"
    danger_hover: str = "#c0392b"
    warning: str = "#f39c12"
    warning_hover: str = "#e67e22"
    info: str = "#3498db"
    info_hover: str = "#2980b9"
    
    # Neutral colors
    text: str = "#2d3436"
    text_secondary: str = "#636e72"
    text_muted: str = "#b2bec3"
    text_light: str = "#ffffff"
    
    bg: str = "#f5f6fa"
    bg_hover: str = "#f0f1f4"
    bg_active: str = "#e8e9ed"
    card_bg: str = "#ffffff"
    
    border: str = "#dfe6e9"
    border_hover: str = "#b2bec3"
    border_focus: str = "#5865f2"
    
    input_bg: str = "#ffffff"
    input_border: str = "#ced4da"
    input_focus: str = "#5865f2"
    
    table_header: str = "#f8f9fa"
    table_alternate: str = "#f8f9fa"
    table_selection: str = "#e9ecef"
    
    progress_bg: str = "#5865f2"
    shadow: str = "rgba(0, 0, 0, 0.1)"
    
    # Scrollbar
    scrollbar_bg: str = "#f0f0f0"
    scrollbar_handle: str = "#c0c0c0"
    scrollbar_handle_hover: str = "#a0a0a0"

@dataclass
class DarkThemeColors:
    """Dark theme color palette"""
    primary: str = "#5865f2"
    primary_hover: str = "#4752c4"
    primary_active: str = "#3c45a3"
    primary_light: str = "#36393f"
    primary_dark: str = "#202225"
    
    success: str = "#3ba55d"
    success_hover: str = "#2d8c47"
    danger: str = "#ed4245"
    danger_hover: str = "#c0392b"
    warning: str = "#faa81a"
    warning_hover: str = "#e67e22"
    info: str = "#3498db"
    info_hover: str = "#2980b9"
    
    text: str = "#dcddde"
    text_secondary: str = "#b9bbbe"
    text_muted: str = "#72767d"
    text_light: str = "#ffffff"
    
    bg: str = "#2f3136"
    bg_hover: str = "#40444b"
    bg_active: str = "#36393f"
    card_bg: str = "#36393f"
    
    border: str = "#40444b"
    border_hover: str = "#5a5f6b"
    border_focus: str = "#5865f2"
    
    input_bg: str = "#40444b"
    input_border: str = "#40444b"
    input_focus: str = "#5865f2"
    
    table_header: str = "#202225"
    table_alternate: str = "#36393f"
    table_selection: str = "#40444b"
    
    progress_bg: str = "#5865f2"
    shadow: str = "rgba(0, 0, 0, 0.4)"
    
    scrollbar_bg: str = "#2f3136"
    scrollbar_handle: str = "#40444b"
    scrollbar_handle_hover: str = "#5a5f6b"

@dataclass
class ThemeTypography:
    """Typography settings"""
    font_family: str = "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif"
    font_family_mono: str = "'Consolas', 'Courier New', monospace"
    
    # Sizes (in points)
    size_small: int = 8
    size_body: int = 9
    size_medium: int = 10
    size_large: int = 11
    size_xlarge: int = 12
    size_title: int = 14
    size_heading: int = 16
    size_display: int = 20
    
    # Weights
    weight_light: int = 300
    weight_normal: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700

@dataclass
class ThemeSpacing:
    """Spacing system"""
    xxs: int = 2
    xs: int = 4
    sm: int = 6
    md: int = 8
    lg: int = 12
    xl: int = 16
    xxl: int = 20
    xxxl: int = 24
    
    # Component specific
    button_padding_x: int = 16
    button_padding_y: int = 8
    input_padding_x: int = 12
    input_padding_y: int = 8
    card_padding: int = 16
    dialog_padding: int = 20

@dataclass
class ThemeRadius:
    """Border radius system"""
    none: int = 0
    sm: int = 4
    md: int = 6
    lg: int = 8
    xl: int = 12
    xxl: int = 16
    circle: int = 9999
    
    # Component specific
    button: int = 6
    input: int = 6
    card: int = 10
    dialog: int = 12
    table: int = 6

@dataclass
class ThemeIcons:
    """Icon names for the design system"""
    # Navigation
    dashboard: str = "dashboard"
    sales: str = "point_of_sale"
    products: str = "package"
    inventory: str = "inventory"
    customers: str = "person"
    expense: str = "money_off"
    reports: str = "bar_chart"
    settings: str = "settings"
    
    # Actions
    add: str = "add"
    edit: str = "edit"
    delete: str = "delete"
    save: str = "save"
    cancel: str = "close"
    search: str = "search"
    refresh: str = "refresh"
    print: str = "print"
    export: str = "file_export"
    import_file: str = "upload_file"
    
    # Status
    success: str = "check_circle"
    error: str = "cancel"
    warning: str = "warning"
    info: str = "info"
    
    # Misc
    close: str = "close"
    menu: str = "menu"
    more: str = "more_horiz"
    calendar: str = "calendar"
    clock: str = "clock"
    user: str = "person"
    group: str = "groups"
    receipt: str = "receipt"
    credit_card: str = "credit_card"
    trending_up: str = "trending_up"
    trending_down: str = "trending_down"

@dataclass
class Theme:
    """Complete theme configuration"""
    colors: ThemeColors = None
    dark_colors: DarkThemeColors = None
    typography: ThemeTypography = None
    spacing: ThemeSpacing = None
    radius: ThemeRadius = None
    icons: ThemeIcons = None
    
    def __post_init__(self):
        if self.colors is None:
            self.colors = ThemeColors()
        if self.dark_colors is None:
            self.dark_colors = DarkThemeColors()
        if self.typography is None:
            self.typography = ThemeTypography()
        if self.spacing is None:
            self.spacing = ThemeSpacing()
        if self.radius is None:
            self.radius = ThemeRadius()
        if self.icons is None:
            self.icons = ThemeIcons()
    
    def get_colors(self, dark: bool = False) -> ThemeColors:
        """Get color palette based on theme mode"""
        return self.dark_colors if dark else self.colors

# Singleton theme instance
_theme: Optional[Theme] = None

def get_theme() -> Theme:
    """Get the global theme instance"""
    global _theme
    if _theme is None:
        _theme = Theme()
    return _theme

def get_theme_colors(dark: bool = None) -> ThemeColors:
    """Get current theme colors"""
    if dark is None:
        dark = is_dark_theme()
    return get_theme().get_colors(dark)

def is_dark_theme() -> bool:
    """Check if dark theme is currently active"""
    try:
        from ui.themes.theme_manager import is_dark_theme as _is_dark
        return _is_dark()
    except ImportError:
        # Fallback: check settings
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] == "Dark" if row else False
        except:
            return False

# Design tokens for easy access
TOKENS = {
    # Spacing
    "spacing": {
        "xxs": 2,
        "xs": 4,
        "sm": 6,
        "md": 8,
        "lg": 12,
        "xl": 16,
        "xxl": 20,
        "xxxl": 24,
    },
    # Radius
    "radius": {
        "none": 0,
        "sm": 4,
        "md": 6,
        "lg": 8,
        "xl": 12,
        "xxl": 16,
        "circle": 9999,
    },
    # Typography
    "typography": {
        "size": {
            "small": 8,
            "body": 9,
            "medium": 10,
            "large": 11,
            "xlarge": 12,
            "title": 14,
            "heading": 16,
            "display": 20,
        },
        "weight": {
            "light": 300,
            "normal": 400,
            "medium": 500,
            "semibold": 600,
            "bold": 700,
        }
    }
}
