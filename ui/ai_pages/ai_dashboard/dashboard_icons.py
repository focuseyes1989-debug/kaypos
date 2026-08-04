# ui/ai_pages/ai_dashboard/dashboard_icons.py

import os
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QRectF, QSizeF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QGuiApplication
from PyQt6.QtSvg import QSvgRenderer
from loguru import logger


class DashboardIcons:
    """
    Production-ready SVG Icon Helper for Dashboard
    """
    
    EMOJI_MAP = {
        'dashboard': '📊',
        'trending_up': '📈',
        'bar_chart': '📊',
        'history': '📋',
        'lightbulb': '💡',
        'receipt': '🧾',
        'receipt_long': '🧾',
        'check_circle': '✅',
        'refresh': '🔄',
        'savings': '💰',
        'money_off': '💸',
        'currency_exchange': '💱',
        'settings': '⚙️',
        'search': '🔍',
        'delete': '🗑️',
        'edit': '✏️',
        'add': '➕',
        'close': '❌',
        'check': '✔️',
        'warning': '⚠️',
        'info': 'ℹ️',
        'home': '🏠',
        'analytics': '📈',
        'chat': '💬',
        'smart_toy': '🤖',
        'point_of_sale': '🛒',
        'category': '📂',
        'inventory': '📦',
        'orders': '📋',
        'print': '🖨️',
        'save': '💾',
        'undo': '↩️',
        'upload_file': '📤',
        'download_done': '✅',
        'visibility': '👁️',
        'favorite': '⭐',
        'groups': '👥',
        'leaderboard': '🏆',
        'folder_open': '📂',
        'folder': '📁',
        'description': '📄',
        'article': '📄',
        'date': '📅',
        'calendar': '📅',
        'clock': '🕐',
        'today': '📅',
        'total': '💰',
        'attach_money': '💰',
        'credit_card': '💳',
        'payments': '💳',
        'percent_discount': '🏷️',
        'sell': '💲',
        'shopping_cart': '🛒',
        'local_shipping': '🚚',
        'swap_horiz': '🔄',
        'backup': '💾',
        'cloud_upload': '☁️',
        'mobile': '📱',
        'barcode': '📱',
        'speech_to_text': '🎤',
        'notifications_active': '🔔',
        'image': '🖼️',
        'logout': '🚪',
        'login': '🚪',
        'location_on': '📍',
        'hourglass': '⏳',
        'maximize': '⤢',
        'minimize': '⤣',
        'close_small': '✕',
        'remove': '➖',
        'inactive': '⏸️',
        'active': '✅',
        'purchase': '🛍️',
        'package': '📦',
        'products': '📦',
        'supplier': '🏭',
        'person': '👤',
        'label': '🏷️',
        'trophy': '🏆',
        'trending_down': '📉',
        'inventory_2': '📦',
    }
    
    _icon_cache = {}
    
    @classmethod
    def create_svg_icon(cls, icon_name: str, size: tuple = (24, 24), color: str = None) -> QLabel:
        """
        Create a QLabel holding a crystal-clear, properly scaled and colorized SVG icon.
        """
        label = QLabel()
        
        # Determine theme color
        if color is None:
            from ui.themes.theme_manager import is_dark_theme
            is_dark = is_dark_theme()
            color = "#ffffff" if is_dark else "#495057"
        
        cache_key = f"{icon_name}_{size[0]}_{size[1]}_{color}"
        
        # Check Cache
        if cache_key in cls._icon_cache:
            pixmap = cls._icon_cache[cache_key]
            if pixmap and not pixmap.isNull():
                label.setPixmap(pixmap)
                label.setFixedSize(size[0], size[1])
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("background: transparent;")
                return label

        # Load & Render Icon
        pixmap = cls._load_colored_icon(icon_name, size, color)
        
        if pixmap and not pixmap.isNull():
            cls._icon_cache[cache_key] = pixmap
            label.setPixmap(pixmap)
            label.setFixedSize(size[0], size[1])
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background: transparent;")
            return label
        
        # Fallback to Emoji if icon file is missing
        emoji = cls.EMOJI_MAP.get(icon_name, '📊')
        label.setText(emoji)
        label.setFixedSize(size[0], size[1])
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"""
            font-size: {int(max(size[0], size[1]) * 0.65)}px;
            background: transparent;
            color: {color};
        """)
        
        # Ensure emoji is visible
        label.setMinimumSize(size[0], size[1])
        
        return label
    
    @classmethod
    def _load_colored_icon(cls, icon_name: str, size: tuple, color: str) -> QPixmap:
        """
        Loads SVG, calculates proper bounding box with padding/aspect ratio,
        and paints color safely using SourceIn composition.
        """
        possible_paths = cls._get_icon_paths(icon_name)
        
        for icon_path in possible_paths:
            if not os.path.exists(icon_path):
                continue
            
            try:
                # --- 1. SVG RENDERER PATH ---
                if icon_path.endswith('.svg'):
                    renderer = QSvgRenderer(icon_path)
                    if not renderer.isValid():
                        continue
                    
                    svg_size = renderer.defaultSize()
                    
                    # Detect device pixel ratio for High-DPI screens
                    dpr = 1.0
                    app = QGuiApplication.instance()
                    if app:
                        primary_screen = app.primaryScreen()
                        if primary_screen:
                            dpr = primary_screen.devicePixelRatio()

                    target_w, target_h = size[0], size[1]
                    pixel_w = int(target_w * dpr)
                    pixel_h = int(target_h * dpr)

                    pixmap = QPixmap(pixel_w, pixel_h)
                    pixmap.setDevicePixelRatio(dpr)
                    pixmap.fill(Qt.GlobalColor.transparent)

                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

                    # Calculate Safe Drawing Target Rect
                    if not svg_size.isValid() or svg_size.isEmpty():
                        svg_size = QSizeF(24.0, 24.0)

                    margin = 1.5
                    avail_w = max(1.0, float(target_w) - (margin * 2))
                    avail_h = max(1.0, float(target_h) - (margin * 2))

                    scale = min(avail_w / svg_size.width(), avail_h / svg_size.height())
                    
                    draw_w = svg_size.width() * scale
                    draw_h = svg_size.height() * scale

                    offset_x = (float(target_w) - draw_w) / 2.0
                    offset_y = (float(target_h) - draw_h) / 2.0

                    render_rect = QRectF(offset_x, offset_y, draw_w, draw_h)

                    # Render SVG onto Canvas
                    renderer.render(painter, render_rect)

                    # Apply Theme Tinting via SourceIn
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(QRectF(0, 0, float(target_w), float(target_h)), QColor(color))
                    painter.end()

                    return pixmap

                # --- 2. PNG FALLBACK PATH ---
                else:
                    pixmap = QPixmap(icon_path)
                    if pixmap.isNull():
                        continue
                    
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    result = QPixmap(scaled.size())
                    result.fill(Qt.GlobalColor.transparent)
                    
                    painter = QPainter(result)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.drawPixmap(0, 0, scaled)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
                    painter.fillRect(result.rect(), QColor(color))
                    painter.end()
                    
                    return result

            except Exception as e:
                logger.warning(f"Error rendering icon '{icon_path}': {e}")
                continue

        return None
    
    @classmethod
    def _get_icon_paths(cls, icon_name: str) -> list:
        """
        Dynamically resolve icon paths in project asset directories
        """
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try to find project root (where 'assets' folder is located)
        project_root = script_dir
        max_depth = 5
        for _ in range(max_depth):
            if os.path.exists(os.path.join(project_root, "assets")):
                break
            project_root = os.path.dirname(project_root)
        
        # Also try from current working directory
        cwd = os.getcwd()
        
        # Build possible paths
        paths = []
        
        # 1. From project root
        if os.path.exists(os.path.join(project_root, "assets")):
            paths.append(os.path.join(project_root, "assets", "icons", f"{icon_name}.svg"))
            paths.append(os.path.join(project_root, "assets", "icons", f"{icon_name}.png"))
        
        # 2. From current working directory
        if os.path.exists(os.path.join(cwd, "assets")):
            paths.append(os.path.join(cwd, "assets", "icons", f"{icon_name}.svg"))
            paths.append(os.path.join(cwd, "assets", "icons", f"{icon_name}.png"))
        
        # 3. From script directory going up
        parent_dir = script_dir
        for _ in range(3):
            parent_dir = os.path.dirname(parent_dir)
            if os.path.exists(os.path.join(parent_dir, "assets")):
                paths.append(os.path.join(parent_dir, "assets", "icons", f"{icon_name}.svg"))
                paths.append(os.path.join(parent_dir, "assets", "icons", f"{icon_name}.png"))
                break
        
        # 4. Direct relative path
        paths.append(os.path.join("assets", "icons", f"{icon_name}.svg"))
        paths.append(os.path.join("assets", "icons", f"{icon_name}.png"))
        
        # 5. From ui folder going up
        ui_dir = os.path.dirname(script_dir)
        if os.path.exists(os.path.join(ui_dir, "..", "assets")):
            paths.append(os.path.join(ui_dir, "..", "assets", "icons", f"{icon_name}.svg"))
            paths.append(os.path.join(ui_dir, "..", "assets", "icons", f"{icon_name}.png"))
        
        # 6. From project root directly (without checking)
        paths.append(os.path.join(project_root, "assets", "icons", f"{icon_name}.svg"))
        paths.append(os.path.join(project_root, "assets", "icons", f"{icon_name}.png"))
        
        # 7. Try with relative path from current file location
        paths.append(os.path.join(os.path.dirname(script_dir), "..", "assets", "icons", f"{icon_name}.svg"))
        paths.append(os.path.join(os.path.dirname(script_dir), "..", "assets", "icons", f"{icon_name}.png"))
        
        # Remove duplicates while preserving order
        unique_paths = []
        for path in paths:
            if path not in unique_paths:
                unique_paths.append(path)
        
        return unique_paths
    
    @classmethod
    def clear_cache(cls):
        """Clear cached icon pixmaps"""
        cls._icon_cache.clear()
    
    @classmethod
    def get_icon_path(cls, icon_name: str) -> str:
        """Get the actual path of an icon file if it exists"""
        possible_paths = cls._get_icon_paths(icon_name)
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    @classmethod
    def icon_exists(cls, icon_name: str) -> bool:
        """Check if an icon file exists"""
        return cls.get_icon_path(icon_name) is not None