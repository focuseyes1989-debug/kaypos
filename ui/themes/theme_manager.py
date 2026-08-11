# ui/themes/theme_manager.py
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QFont, QFontDatabase, QColor
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QByteArray
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QPixmap, QPainter, QIcon
from io import BytesIO
import re
import os
from pathlib import Path

from ui.themes.dark_theme import DARK_THEME
from ui.themes.light_theme import LIGHT_THEME
from ui.design_system.stylesheet import compose_app_stylesheet

THEMES = {
    "Dark": DARK_THEME,
    "Light": LIGHT_THEME,
}

# Theme color definitions for programmatic access
THEME_COLORS = {
    "Dark": {
        'bg': '#36393f',
        'bg_hover': '#40444b',
        'text': '#dcddde',
        'text_secondary': '#b9bbbe',
        'border': '#202225',
        'border_hover': '#5865f2',
        'card_bg': '#2f3136',
        'card_hover': '#383a40',
        'table_alt': '#36393f',
        'progress_bg': '#5865f2',
        'danger': '#ed4245',
        'success': '#3ba55d',
        'warning': '#faa81a',
        'input_bg': 'transparent',
        'input_border': '#40444b',
        'icon_color': '#dcddde',
        'icon_active': '#5865f2',
        'icon_hover': '#ffffff',
    },
    "Light": {
        'bg': '#f8f9fa',
        'bg_hover': '#e9ecef',
        'text': '#212529',
        'text_secondary': '#6c757d',
        'border': '#dee2e6',
        'border_hover': '#5865f2',
        'card_bg': '#ffffff',
        'card_hover': '#f8f9fa',
        'table_alt': '#f8f9fa',
        'progress_bg': '#5865f2',
        'danger': '#dc3545',
        'success': '#28a745',
        'warning': '#ffc107',
        'input_bg': 'transparent',
        'input_border': '#ced4da',
        'icon_color': '#495057',
        'icon_active': '#5865f2',
        'icon_hover': '#212529',
    }
}

# Global variables
_current_theme = "Light"
_theme_change_callbacks = []


class ThemeManager(QObject):
    """Theme manager with signal support"""
    theme_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._current_theme = "Light"
        self._updating = False
    
    def set_theme(self, theme_name, app=None):
        """Set theme and emit signal"""
        global _current_theme
        if theme_name in THEMES:
            _current_theme = theme_name
            self._current_theme = theme_name
            
            if app:
                apply_font()
                app.setStyleSheet(compose_app_stylesheet(THEMES.get(theme_name, THEMES["Light"]), theme_name))
                
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self._finish_theme_update(app, theme_name))
            
            self.theme_changed.emit(theme_name)
            
            stale_callbacks = []
            for callback in list(_theme_change_callbacks):
                try:
                    callback(theme_name)
                except RuntimeError as e:
                    if "has been deleted" in str(e):
                        stale_callbacks.append(callback)
                    else:
                        print(f"Error in theme callback: {e}")
                except Exception as e:
                    print(f"Error in theme callback: {e}")
            for callback in stale_callbacks:
                self.unregister_callback(callback)
    
    def _finish_theme_update(self, app, theme_name):
        if self._updating:
            return
        self._updating = True
        
        try:
            for widget in app.topLevelWidgets():
                try:
                    widget.update()
                except:
                    pass
        finally:
            self._updating = False
    
    def get_current_theme(self):
        return self._current_theme
    
    def register_callback(self, callback):
        if callback not in _theme_change_callbacks:
            _theme_change_callbacks.append(callback)

    def unregister_callback(self, callback):
        try:
            _theme_change_callbacks.remove(callback)
        except ValueError:
            pass


# ✅ Get the base directory (project root)
def get_base_dir():
    """Get the base directory of the project"""
    current_dir = Path(__file__).resolve().parent
    
    for _ in range(5):
        if (current_dir / "assets").exists():
            return current_dir
        current_dir = current_dir.parent
    
    return Path(__file__).resolve().parent.parent.parent


# ✅ Get icon path
def get_icon_path(icon_name):
    """Get the full path to an SVG icon"""
    base_dir = get_base_dir()
    
    possible_paths = [
        base_dir / "assets" / "icons" / f"{icon_name}.svg",
        Path("assets/icons") / f"{icon_name}.svg",
        Path(__file__).parent.parent.parent / "assets" / "icons" / f"{icon_name}.svg",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


# ✅ SVG Icon Helper Functions
def get_icon_color(theme_name=None):
    """Get the current icon color based on theme"""
    if theme_name is None:
        theme_name = _current_theme
    colors = THEME_COLORS.get(theme_name, THEME_COLORS["Light"])
    return colors.get('icon_color', '#495057')


def get_active_icon_color(theme_name=None):
    """Get the active icon color based on theme"""
    if theme_name is None:
        theme_name = _current_theme
    colors = THEME_COLORS.get(theme_name, THEME_COLORS["Light"])
    return colors.get('icon_active', '#5865f2')


def get_hover_icon_color(theme_name=None):
    """Get the hover icon color based on theme"""
    if theme_name is None:
        theme_name = _current_theme
    colors = THEME_COLORS.get(theme_name, THEME_COLORS["Light"])
    return colors.get('icon_hover', '#212529')


def get_icon_with_color(icon_name, color_hex, size=(24, 24)):
    """
    Load SVG icon and apply color.
    
    Args:
        icon_name: Name of the SVG file (without extension)
        color_hex: Hex color code (e.g., '#5865f2')
        size: Tuple of (width, height)
    
    Returns:
        QIcon with colored SVG
    """
    try:
        # Get icon path
        icon_path = get_icon_path(icon_name)
        
        if icon_path is None or not icon_path.exists():
            print(f"Icon not found: {icon_name}")
            return QIcon()
        
        # Read SVG content
        with open(icon_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        # Replace fill colors in SVG
        svg_content = re.sub(r'fill="[^"]*"', '', svg_content)
        svg_content = re.sub(r'fill:\s*[^;"]+', '', svg_content)
        
        # Add fill color to SVG
        svg_content = svg_content.replace('<svg', f'<svg fill="{color_hex}"', 1)
        
        if 'fill="' not in svg_content[:200]:
            svg_content = svg_content.replace('<svg', f'<svg fill="{color_hex}"', 1)
        
        # ✅ Fix: Convert to QByteArray
        byte_array = QByteArray(svg_content.encode('utf-8'))
        
        # ✅ Fix: Create QSvgRenderer with QByteArray
        renderer = QSvgRenderer(byte_array)
        
        if not renderer.isValid():
            print(f"Invalid SVG renderer for: {icon_name}")
            # Try loading original SVG without color modification
            return QIcon(str(icon_path))
        
        pixmap = QPixmap(size[0], size[1])
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        return QIcon(pixmap)
        
    except Exception as e:
        print(f"Error loading icon {icon_name}: {e}")
        # Try loading original SVG
        try:
            icon_path = get_icon_path(icon_name)
            if icon_path and icon_path.exists():
                return QIcon(str(icon_path))
        except:
            pass
        return QIcon()


def get_themed_icon(icon_name, theme_name=None, size=(24, 24)):
    """
    Get an SVG icon with the current theme's color.
    
    Args:
        icon_name: Name of the SVG file (without extension)
        theme_name: Optional theme name, uses current if None
        size: Tuple of (width, height)
    
    Returns:
        QIcon with themed color
    """
    color = get_icon_color(theme_name)
    icon = get_icon_with_color(icon_name, color, size)
    
    if icon.isNull():
        try:
            icon_path = get_icon_path(icon_name)
            if icon_path and icon_path.exists():
                return QIcon(str(icon_path))
        except:
            pass
    
    return icon


def get_active_themed_icon(icon_name, theme_name=None, size=(24, 24)):
    """
    Get an SVG icon with the current theme's active color.
    
    Args:
        icon_name: Name of the SVG file (without extension)
        theme_name: Optional theme name, uses current if None
        size: Tuple of (width, height)
    
    Returns:
        QIcon with active themed color
    """
    color = get_active_icon_color(theme_name)
    icon = get_icon_with_color(icon_name, color, size)
    
    if icon.isNull():
        try:
            icon_path = get_icon_path(icon_name)
            if icon_path and icon_path.exists():
                return QIcon(str(icon_path))
        except:
            pass
    
    return icon


# Singleton instance
theme_manager = ThemeManager()


def set_current_theme(theme_name):
    """Set the active theme used by programmatic theme colors."""
    global _current_theme
    _current_theme = theme_name if theme_name in THEME_COLORS else "Light"
    theme_manager._current_theme = _current_theme


def get_scaled_font_size(base_size=9):
    """Get font size scaled based on screen DPI"""
    try:
        screen = QApplication.primaryScreen()
        if screen:
            dpi = screen.logicalDotsPerInch()
            scale = dpi / 96.0
            return int(base_size * scale)
    except:
        pass
    return base_size


def get_preferred_font_family():
    """Prefer Windows' built-in Myanmar font for clearer Burmese rendering."""
    preferred_fonts = [
        "Myanmar Text",
        "Noto Sans Myanmar",
        "Pyidaungsu",
        "Myanmar3",
        "Segoe UI",
    ]
    try:
        installed_fonts = set(QFontDatabase.families())
        for font_name in preferred_fonts:
            if font_name in installed_fonts:
                return font_name
    except Exception:
        pass
    return "Segoe UI"


def apply_font():
    """Apply scaled font to the application"""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        font_size = get_scaled_font_size(10)
        font = QFont(get_preferred_font_family(), font_size)
        app.setFont(font)
        return font
    return None


def apply_theme(app, theme_name):
    """Apply the selected theme to the QApplication."""
    set_current_theme(theme_name)
    theme_manager.set_theme(theme_name, app)


def get_current_theme():
    """Get the current theme name."""
    return _current_theme


def get_theme_colors(theme_name=None):
    """Get theme colors for the specified theme or current theme."""
    if theme_name is None:
        theme_name = _current_theme
    return THEME_COLORS.get(theme_name, THEME_COLORS["Light"])


def is_dark_theme(theme_name=None):
    """Check if the current theme is dark."""
    if theme_name is None:
        theme_name = _current_theme
    return theme_name == "Dark"


def register_theme_callback(callback):
    """Register a callback to be called when theme changes"""
    theme_manager.register_callback(callback)


def unregister_theme_callback(callback):
    """Unregister a callback when the owning widget is destroyed."""
    theme_manager.unregister_callback(callback)


def apply_discord_theme(app):
    apply_theme(app, "Dark")


def apply_dark_gray_touch_theme(app):
    apply_theme(app, "Dark")
