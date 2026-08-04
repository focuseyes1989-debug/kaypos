# ui/design_system/icon.py
"""
Icon utilities for the design system
Loads SVG icons from assets/icons with theme-aware coloring
"""

import os
from typing import Optional
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from ui.design_system.theme import get_theme_colors, is_dark_theme
from loguru import logger

# Icon cache for performance
_icon_cache = {}

def get_icon_path(icon_name: str) -> Optional[str]:
    """
    Get the full path to an icon file
    
    Args:
        icon_name: Name of the icon (without extension)
    
    Returns:
        Full path to the icon file, or None if not found
    """
    # Try SVG first
    svg_path = f"assets/icons/{icon_name}.svg"
    if os.path.exists(svg_path):
        return svg_path
    
    # Try PNG
    png_path = f"assets/icons/{icon_name}.png"
    if os.path.exists(png_path):
        return png_path
    
    return None

def load_svg_icon(icon_name: str, size: int = 20, color_hex: Optional[str] = None) -> Optional[QPixmap]:
    """
    Load an SVG icon with optional color
    
    Args:
        icon_name: Name of the SVG file (without extension)
        size: Icon size in pixels
        color_hex: Hex color code (optional)
    
    Returns:
        QPixmap with the colored icon, or None if failed
    """
    # Check cache
    cache_key = f"{icon_name}_{size}_{color_hex}"
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]
    
    icon_path = get_icon_path(icon_name)
    if not icon_path:
        return None
    
    try:
        # For SVG
        if icon_path.endswith('.svg'):
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # If color is provided, replace fill colors
            if color_hex:
                import re
                # Remove existing fills
                svg_content = re.sub(r'fill="[^"]*"', '', svg_content)
                svg_content = re.sub(r'fill:\s*[^;"]+', '', svg_content)
                # Add new fill
                svg_content = svg_content.replace('<svg', f'<svg fill="{color_hex}"', 1)
            
            byte_array = QByteArray(svg_content.encode('utf-8'))
            renderer = QSvgRenderer(byte_array)
            
            if renderer.isValid():
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                
                _icon_cache[cache_key] = pixmap
                return pixmap
        
        # For PNG
        else:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Colorize if color provided
                if color_hex:
                    colored = scaled.copy()
                    painter = QPainter(colored)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(colored.rect(), QColor(color_hex))
                    painter.end()
                    _icon_cache[cache_key] = colored
                    return colored
                
                _icon_cache[cache_key] = scaled
                return scaled
    
    except Exception as e:
        logger.debug(f"Could not load icon {icon_name}: {e}")
    
    return None

def get_icon(icon_name: str, size: int = 20, color_hex: Optional[str] = None) -> Optional[QIcon]:
    """
    Get a QIcon for an icon
    
    Args:
        icon_name: Name of the icon (without extension)
        size: Icon size
        color_hex: Hex color code (optional)
    
    Returns:
        QIcon instance, or None if failed
    """
    pixmap = load_svg_icon(icon_name, size, color_hex)
    if pixmap:
        return QIcon(pixmap)
    return None

def get_themed_icon(icon_name: str, size: int = 20) -> Optional[QIcon]:
    """
    Get an icon with the current theme color
    
    Args:
        icon_name: Name of the icon
        size: Icon size
    
    Returns:
        QIcon with theme color
    """
    colors = get_theme_colors()
    color = colors.text_secondary
    return get_icon(icon_name, size, color)

def get_primary_icon(icon_name: str, size: int = 20) -> Optional[QIcon]:
    """
    Get an icon with the primary theme color
    
    Args:
        icon_name: Name of the icon
        size: Icon size
    
    Returns:
        QIcon with primary color
    """
    colors = get_theme_colors()
    return get_icon(icon_name, size, colors.primary)

def clear_icon_cache():
    """Clear the icon cache"""
    _icon_cache.clear()

# Common icon names for easy reference
ICONS = {
    # Navigation
    "dashboard": "dashboard",
    "sales": "point_of_sale",
    "products": "package",
    "inventory": "inventory",
    "customers": "person",
    "expense": "money_off",
    "reports": "bar_chart",
    "settings": "settings",
    
    # Actions
    "add": "add",
    "edit": "edit",
    "delete": "delete",
    "save": "save",
    "cancel": "close",
    "search": "search",
    "refresh": "refresh",
    "print": "print",
    "export": "file_export",
    "import_file": "upload_file",
    
    # Status
    "success": "check_circle",
    "error": "cancel",
    "warning": "warning",
    "info": "info",
    
    # Misc
    "close": "close",
    "menu": "menu",
    "more": "more_horiz",
    "calendar": "calendar",
    "clock": "clock",
    "user": "person",
    "group": "groups",
    "receipt": "receipt",
    "credit_card": "credit_card",
    "trending_up": "trending_up",
    "trending_down": "trending_down",
}
