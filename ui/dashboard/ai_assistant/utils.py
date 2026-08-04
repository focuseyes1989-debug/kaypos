# ui/dashboard/ai_assistant/utils.py
"""Helper utilities with SVG icon support"""

from datetime import datetime, timedelta
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
import os

from ui.themes.theme_manager import get_themed_icon, get_theme_colors, get_icon_path
from .constants import EMOJI_ICONS


def get_themed_icon_helper(icon_name, size=18, is_dark=False):
    """Get themed SVG icon with fallback to emoji"""
    colors = get_theme_colors()
    icon_color = colors.get('icon_color', '#dcddde' if is_dark else '#495057')
    
    # ✅ Try to get themed icon first
    icon = get_themed_icon(icon_name, size=(size, size))
    if not icon.isNull():
        return icon.pixmap(QSize(size, size))
    
    # ✅ Try to load SVG directly with custom color
    try:
        icon_path = get_icon_path(icon_name)
        if icon_path and os.path.exists(icon_path):
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Replace fill colors
            import re
            svg_content = re.sub(r'fill="[^"]*"', '', svg_content)
            svg_content = re.sub(r'fill:\s*[^;"]+', '', svg_content)
            svg_content = svg_content.replace('<svg', f'<svg fill="{icon_color}"', 1)
            
            byte_array = QByteArray(svg_content.encode('utf-8'))
            renderer = QSvgRenderer(byte_array)
            
            if renderer.isValid():
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap
    except Exception as e:
        pass
    
    # ✅ Try SVG/PNG from assets without color modification
    icon_paths = [
        f"assets/icons/{icon_name}.svg",
        f"assets/icons/{icon_name}.png",
    ]
    
    for path in icon_paths:
        if os.path.exists(path):
            try:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Color the icon
                    colored = scaled.copy()
                    painter = QPainter(colored)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(colored.rect(), QColor(icon_color))
                    painter.end()
                    return colored
            except Exception:
                pass
    
    # ✅ Fallback to emoji
    return None


def get_icon_pixmap(icon_name, size=18, color=None, is_dark=False):
    """
    Get SVG icon as QPixmap with optional color
    
    Args:
        icon_name: Name of the SVG file (without extension)
        size: Size in pixels
        color: Hex color code (optional)
        is_dark: Whether dark theme is active
    
    Returns:
        QPixmap or None
    """
    if color is None:
        colors = get_theme_colors()
        color = colors.get('icon_color', '#dcddde' if is_dark else '#495057')
    
    try:
        icon_path = get_icon_path(icon_name)
        if icon_path and os.path.exists(icon_path):
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            import re
            svg_content = re.sub(r'fill="[^"]*"', '', svg_content)
            svg_content = re.sub(r'fill:\s*[^;"]+', '', svg_content)
            svg_content = svg_content.replace('<svg', f'<svg fill="{color}"', 1)
            
            byte_array = QByteArray(svg_content.encode('utf-8'))
            renderer = QSvgRenderer(byte_array)
            
            if renderer.isValid():
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap
    except Exception:
        pass
    
    return None


def get_emoji_fallback(icon_name):
    """Get emoji fallback for icon name"""
    return EMOJI_ICONS.get(icon_name, "📊")


def get_date_range(range_type):
    """Get date range based on selection"""
    today = datetime.now().date()
    
    if range_type == "Today":
        return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif range_type == "Yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")
    elif range_type == "This Week":
        start = today - timedelta(days=today.weekday())
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif range_type == "This Month":
        start = today.replace(day=1)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif range_type == "Last 7 Days":
        start = today - timedelta(days=7)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    elif range_type == "Last 30 Days":
        start = today - timedelta(days=30)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def get_date_range_days(range_type):
    """Get number of days for current date range"""
    if range_type in ("Today", "Yesterday"):
        return 1
    elif range_type in ("This Week", "Last 7 Days"):
        return 7
    elif range_type in ("This Month", "Last 30 Days"):
        return 30
    return 1


def format_trend(change):
    """Format trend indicator"""
    if change > 15:
        return "↑"
    elif change < -15:
        return "↓"
    return "→"


def get_myanmar_text(texts, key, **kwargs):
    """Get Myanmar text for insights"""
    return texts.get(key, key).format(**kwargs)


# ✅ Icon mapping for AI Assistant insights
INSIGHT_ICON_MAP = {
    # Sales & Trends
    "trending_up": "trending_up",
    "trending_down": "trending_down",
    "bar_chart": "bar_chart",
    "analytics": "analytics",
    
    # Categories & Products
    "trophy": "trophy",
    "local_fire_department": "local_fire_department",
    "package": "package",
    
    # Inventory
    "warning": "warning",
    "check_circle": "check_circle",
    
    # Time
    "clock": "clock",
    "calendar": "calendar",
    "calendar_month": "calendar_month",
    
    # Customers
    "groups": "groups",
    
    # Payments
    "credit_card": "credit_card",
    
    # Others
    "star": "star",
    "bolt": "bolt",
    "chart": "bar_chart",
}


def get_insight_icon_name(icon_key):
    """Get the actual SVG icon name for an insight"""
    return INSIGHT_ICON_MAP.get(icon_key, icon_key)