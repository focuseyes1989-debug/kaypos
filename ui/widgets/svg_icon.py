# ui/widgets/svg_icon.py
"""
SVG Icon Helper - Load and render SVG icons
Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer
from loguru import logger
import os
import base64
import re


def get_svg_icon(icon_name: str, size: int = 24, color: str = None, fallback_text: str = "📁") -> QPixmap:
    """
    Load and render an SVG icon as QPixmap
    
    Args:
        icon_name: Name of SVG file (with or without .svg extension)
        size: Size of the icon in pixels
        color: Color to use for the icon (hex or name)
        fallback_text: Text to show if icon not found
    
    Returns:
        QPixmap of the icon
    """
    # Ensure .svg extension
    if not icon_name.endswith('.svg'):
        icon_name = f"{icon_name}.svg"
    
    # Try multiple paths
    possible_paths = [
        os.path.join('assets', 'icons', icon_name),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'icons', icon_name),
        os.path.join(os.getcwd(), 'assets', 'icons', icon_name),
    ]
    
    icon_path = None
    for path in possible_paths:
        if os.path.exists(path):
            icon_path = path
            break
    
    if not icon_path:
        logger.debug(f"SVG icon not found: {icon_name}")
        return None
    
    try:
        # Read SVG file
        with open(icon_path, 'r', encoding='utf-8') as f:
            svg_data = f.read()
        
        # If color is provided, replace fill colors
        if color:
            svg_data = _recolor_svg(svg_data, color)
        
        # Create QPixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Render SVG to pixmap
        renderer = QSvgRenderer(svg_data.encode('utf-8'))
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(painter)
            painter.end()
            return pixmap
        else:
            logger.warning(f"Invalid SVG: {icon_path}")
            return None
            
    except Exception as e:
        logger.warning(f"Failed to load SVG {icon_path}: {e}")
        return None


def _recolor_svg(svg_data: str, color: str) -> str:
    """
    Replace fill colors in SVG with the specified color
    """
    # Handle color formats
    if color.startswith('#'):
        hex_color = color
    else:
        # Convert color name to hex
        color_map = {
            'white': '#ffffff',
            'black': '#000000',
            'red': '#ff0000',
            'green': '#00ff00',
            'blue': '#0000ff',
            'yellow': '#ffff00',
        }
        hex_color = color_map.get(color.lower(), color)
    
    # Replace fill attributes
    # Pattern: fill="..." or fill='...' or fill: ...
    
    # Replace fill="..." 
    svg_data = re.sub(r'fill="[^"]*"', f'fill="{hex_color}"', svg_data)
    svg_data = re.sub(r"fill='[^']*'", f"fill='{hex_color}'", svg_data)
    
    # Replace style="fill: ..."
    svg_data = re.sub(r'style="[^"]*fill:[^;"]*[;"]', f'style="fill:{hex_color};', svg_data)
    
    # If no fill attribute found, add it to the first element
    if 'fill="' not in svg_data and "fill='" not in svg_data:
        svg_data = svg_data.replace('<svg', f'<svg fill="{hex_color}"', 1)
    
    return svg_data


def get_svg_icon_data_uri(icon_name: str, color: str = None) -> str:
    """
    Get SVG icon as data URI (for use in HTML/CSS)
    
    Args:
        icon_name: Name of SVG file (with or without .svg extension)
        color: Color to use for the icon
    
    Returns:
        Data URI string
    """
    if not icon_name.endswith('.svg'):
        icon_name = f"{icon_name}.svg"
    
    icon_path = os.path.join('assets', 'icons', icon_name)
    
    if not os.path.exists(icon_path):
        return None
    
    try:
        with open(icon_path, 'r', encoding='utf-8') as f:
            svg_data = f.read()
        
        if color:
            svg_data = _recolor_svg(svg_data, color)
        
        # Convert to base64
        encoded = base64.b64encode(svg_data.encode('utf-8')).decode('utf-8')
        return f"data:image/svg+xml;base64,{encoded}"
        
    except Exception as e:
        logger.warning(f"Failed to create data URI: {e}")
        return None


def get_icon_for_category(category: dict, size: int = 24) -> QPixmap:
    """
    Get icon for a category (uses SVG if available, fallback to emoji)
    
    Args:
        category: Category dictionary with 'icon' and 'color' fields
        size: Size of the icon
    
    Returns:
        QPixmap of the icon
    """
    icon_name = category.get('icon', 'category')
    color = category.get('color', '#6c5ce7')
    
    # Try SVG first
    pixmap = get_svg_icon(icon_name, size, color)
    if pixmap and not pixmap.isNull():
        return pixmap
    
    # Fallback: Use emoji
    emoji_map = {
        'category': '📁',
        'folder': '📂',
        'folder_open': '📂',
        'label': '🏷️',
        'sell': '💲',
        'shopping_cart': '🛒',
        'package': '📦',
        'inventory': '📋',
        'inventory_2': '📦',
        'orders': '📋',
        'receipt': '🧾',
        'receipt_long': '🧾',
        'local_shipping': '🚚',
        'payments': '💳',
        'credit_card': '💳',
        'money': '💰',
        'attach_money': '💰',
        'money_off': '💸',
        'savings': '📈',
        'trending_up': '📈',
        'bar_chart': '📊',
        'analytics': '📊',
        'dashboard': '📊',
        'leaderboard': '📊',
        'list_alt': '📋',
        'grid_view': '📊',
        'groups': '👥',
        'group_work': '👥',
        'home': '🏠',
        'person': '👤',
        'search': '🔍',
        'print': '🖨️',
        'clock': '🕐',
        'date': '📅',
        'settings': '⚙️',
        'logout': '🚪',
        'backup': '💾',
        'cloud_upload': '☁️',
        'file_export': '📤',
        'upload_file': '📤',
        'download_done': '✅',
        'warning': '⚠️',
        'description': '📝',
        'image': '🖼️',
        'edit': '✏️',
        'delete': '🗑️',
        'save': '💾',
        'add': '➕',
        'cancel': '✖',
        'close': '✖',
        'visibility': '👁️',
        'visibility_off': '🚫',
        'notifications_active': '🔔',
        'barcode': '📱',
        'speech_to_text': '🎤',
    }
    
    fallback = emoji_map.get(icon_name, '📁')
    
    # Create pixmap with emoji
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(QFont("Segoe UI Emoji", size - 4))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, fallback)
    painter.end()
    
    return pixmap


def get_icon_pixmap(icon_name: str, size: int = 24, color: str = None) -> QPixmap:
    """
    Simple wrapper to get icon pixmap
    
    Args:
        icon_name: Name of icon (with or without .svg)
        size: Size in pixels
        color: Color for the icon
    
    Returns:
        QPixmap or None
    """
    return get_svg_icon(icon_name, size, color)