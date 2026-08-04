# ui/themes/__init__.py
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase
from ui.themes.dark_theme import DARK_THEME
from ui.themes.light_theme import LIGHT_THEME
from ui.themes.theme_manager import (
    theme_manager,
    THEMES,
    THEME_COLORS,
    set_current_theme,
    get_current_theme,
    get_theme_colors,
    is_dark_theme,
    get_scaled_font_size,
    get_preferred_font_family,
    apply_font,
    apply_theme,
    apply_discord_theme,
    apply_dark_gray_touch_theme,
    # ✅ SVG helper functions
    get_icon_color,
    get_active_icon_color,
    get_hover_icon_color,
    get_icon_with_color,
    get_themed_icon,
    get_active_themed_icon,
    get_base_dir,
    get_icon_path,
)

__all__ = [
    'DARK_THEME',
    'LIGHT_THEME',
    'THEMES',
    'THEME_COLORS',
    'set_current_theme',
    'get_current_theme',
    'get_theme_colors',
    'is_dark_theme',
    'get_scaled_font_size',
    'get_preferred_font_family',
    'apply_font',
    'apply_theme',
    'apply_discord_theme',
    'apply_dark_gray_touch_theme',
    # ✅ SVG helper functions
    'get_icon_color',
    'get_active_icon_color',
    'get_hover_icon_color',
    'get_icon_with_color',
    'get_themed_icon',
    'get_active_themed_icon',
    'get_base_dir',
    'get_icon_path',
]