# ui/widgets/modern_button.py
"""
Modern Button with Multiple Styles (Primary, Secondary, Tertiary, Danger)
Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
Support SVG icons with theme colors
"""

import os
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt6.QtCore import Qt, QSize

from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme


class ModernButton(QPushButton):
    """Modern button with Primary, Secondary, Tertiary, and Danger styles - Theme-aware"""
    
    # Button style constants
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    DANGER = "danger"
    
    # Complete Fallback emojis for all icons
    FALLBACK_ICONS = {
        # Action icons
        'add': '➕',
        'edit': '✏️',
        'delete': '🗑️',
        'delete_all': '🗑️',
        'save': '💾',
        'cancel': '✖',
        'close': '✖',
        'check': '✔',
        'refresh': '🔄',
        'search': '🔍',
        'settings': '⚙️',
        'export': '📤',
        'import': '📥',
        'upload_file': '📤',
        'file_export': '📤',
        'print': '🖨️',
        'send': '📤',
        'undo': '↩️',
        'redo': '↪️',
        'remove': '➖',
        
        # Navigation
        'home': '🏠',
        'dashboard': '📊',
        'analytics': '📈',
        
        # Status
        'warning': '⚠️',
        'info': 'ℹ️',
        'check_circle': '✅',
        'visibility': '👁️',
        'visibility_off': '🚫',
        
        # Categories
        'category': '📂',
        'folder': '📁',
        'folder_open': '📂',
        
        # Products
        'products': '📦',
        'inventory': '📦',
        'inventory_2': '📦',
        'shopping_cart': '🛒',
        'package': '📦',
        
        # Sales
        'payments': '💳',
        'credit_card': '💳',
        'money': '💰',
        'savings': '🏦',
        'attach_money': '💰',
        'currency_exchange': '💱',
        'point_of_sale': '💳',
        'barcode': '📱',
        
        # People
        'person': '👤',
        'groups': '👥',
        'group_work': '👥',
        'supplier': '🏭',
        
        # Time
        'calendar': '📅',
        'calendar_month': '📅',
        'clock': '🕐',
        'today': '📅',
        'history': '📜',
        
        # Actions
        'backup': '💾',
        'cloud_upload': '☁️',
        'download_done': '⬇️',
        'swap_horiz': '🔄',
        
        # UI
        'grid_view': '📊',
        'list_alt': '📋',
        'label': '🏷️',
        'description': '📝',
        'article': '📄',
        'receipt': '🧾',
        'receipt_long': '🧾',
        
        # Colors
        'color_lens': '🎨',
        'emoji_objects': '😊',
        
        # Selection
        'select_all': '✅',
        'deselect': '❌',
        'merge': '🔀',
        
        # Misc
        'smart_toy': '🤖',
        'chat': '💬',
        'logout': '🚪',
        'login': '🚪',
        'trending_up': '📈',
        'trending_down': '📉',
        'leaderboard': '🏆',
        'trophy': '🏆',
        'local_fire_department': '🔥',
        'local_shipping': '🚚',
        'location_on': '📍',
        'mobile': '📱',
        'bar_chart': '📊',
        'percent_discount': '💯',
        'purchase': '🛍️',
        'sell': '💰',
        'image': '🖼️',
        'image_inset': '🖼️',
        'maximize': '⬆️',
        'minimize': '⬇️',
        'hourglass': '⌛',
        'active': '✅',
        'inactive': '❌',
        'hidden': '🙈',
        'inactive_order': '❌',
        'notifications_active': '🔔',
        'orders': '📋',
        'speech_to_text': '🎤',
    }
    
    def __init__(self, text="", style=PRIMARY, parent=None):
        super().__init__(text, parent)
        
        # Remove default icon
        self.setIcon(QIcon())
        
        # Set style
        self._style = style
        self._compact = False
        self._dense = False
        self._is_dark = is_dark_theme()
        self._text_only = False
        self._chatgpt_style = False
        self._updating_text = False
        
        # Icon data
        self._icon_name = None
        self._icon_size = QSize(16, 16)
        self._custom_icon = None
        self._has_icon = False
        self._original_text = text
        
        # Apply style
        self._apply_style()
        
        # Common properties
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        
        # Default size - normal (slightly reduced)
        self.setMinimumHeight(30)
        self.setMaximumHeight(38)
        
        # Connect theme change signal
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change - update button style and icon"""
        self._is_dark = is_dark_theme()
        self._apply_style()
        
        if self._icon_name and not self._custom_icon and not self._text_only:
            self._update_icon()
        
        self.update()
    
    def _apply_style(self):
        """Apply different styles based on button type and current theme"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Theme-aware color definitions
        if is_dark:
            # Dark theme colors
            primary_color = "#5865f2"
            primary_hover = "#4752c4"
            primary_checked = "#4752c4"
            primary_disabled = "#40444b"
            
            # Danger colors (dark theme)
            danger_color = "#e74c3c"
            danger_hover = "#c0392b"
            danger_checked = "#c0392b"
            danger_disabled = "#40444b"
            
            secondary_color = "#dcddde"
            secondary_hover = "#ffffff"
            secondary_border = "#40444b"
            secondary_border_hover = "#5865f2"
            
            tertiary_color = "#b9bbbe"
            tertiary_hover = "#dcddde"
            
            bg_hover = "#40444b"
            bg_checked = "#40444b"
            
            disabled_text = "#72767d"
            
        else:
            # Light theme colors
            primary_color = "#5865f2"
            primary_hover = "#4752c4"
            primary_checked = "#4752c4"
            primary_disabled = "#e9ecef"
            
            # Danger colors (light theme)
            danger_color = "#dc3545"
            danger_hover = "#b02a37"
            danger_checked = "#b02a37"
            danger_disabled = "#e9ecef"
            
            secondary_color = "#495057"
            secondary_hover = "#212529"
            secondary_border = "#ced4da"
            secondary_border_hover = "#5865f2"
            
            tertiary_color = "#6c757d"
            tertiary_hover = "#495057"
            
            bg_hover = "#f8f9fa"
            bg_checked = "#f1f3f5"
            
            disabled_text = "#adb5bd"
        
        # Base styles common to all buttons
        style_sheet = f"""
            QPushButton {{
                border: none;
                border-radius: 5px;
                font-weight: 500;
                text-align: center;
                outline: none;
            }}
            QPushButton:focus {{
                outline: none;
            }}
            QPushButton:focus:checked {{
                outline: none;
            }}
            QPushButton:disabled {{
                opacity: 0.5;
                cursor: default;
            }}
            QPushButton::icon {{
                margin-right: 3px;
            }}
        """
        
        if self._style == self.PRIMARY:
            style_sheet += f"""
                QPushButton {{
                    background-color: {primary_color};
                    color: white;
                }}
                QPushButton:hover {{
                    background-color: {primary_hover};
                }}
                QPushButton:checked {{
                    background-color: {primary_checked};
                    color: white;
                }}
                QPushButton:checked:hover {{
                    background-color: {primary_hover};
                }}
                QPushButton:disabled {{
                    background-color: {primary_disabled};
                    color: {disabled_text};
                }}
            """
        
        elif self._style == self.DANGER:
            style_sheet += f"""
                QPushButton {{
                    background-color: {danger_color};
                    color: white;
                }}
                QPushButton:hover {{
                    background-color: {danger_hover};
                }}
                QPushButton:checked {{
                    background-color: {danger_checked};
                    color: white;
                }}
                QPushButton:checked:hover {{
                    background-color: {danger_hover};
                }}
                QPushButton:disabled {{
                    background-color: {danger_disabled};
                    color: {disabled_text};
                }}
            """
        
        elif self._style == self.SECONDARY:
            style_sheet += f"""
                QPushButton {{
                    background-color: transparent;
                    color: {secondary_color};
                    border: 1px solid {secondary_border};
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                    color: {secondary_hover};
                    border-color: {secondary_border_hover};
                }}
                QPushButton:checked {{
                    background-color: {bg_checked};
                    color: {secondary_hover};
                    border-color: {secondary_border_hover};
                }}
                QPushButton:checked:hover {{
                    background-color: {bg_hover};
                    border-color: {secondary_border_hover};
                }}
                QPushButton:disabled {{
                    color: {disabled_text};
                    border-color: {disabled_text};
                }}
            """
            
        else:  # TERTIARY
            style_sheet += f"""
                QPushButton {{
                    background-color: transparent;
                    color: {tertiary_color};
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                    color: {tertiary_hover};
                }}
                QPushButton:checked {{
                    background-color: {bg_checked};
                    color: {tertiary_hover};
                }}
                QPushButton:checked:hover {{
                    background-color: {bg_hover};
                }}
                QPushButton:disabled {{
                    color: {disabled_text};
                }}
            """
        
        # Add padding and font size based on compact mode
        if self._compact:
            # Super compact - for toolbars and tight spaces
            style_sheet += """
                QPushButton {
                    padding: 2px 6px;
                    font-size: 8pt;
                }
            """
        elif self._dense:
            # Dense - compact but readable
            style_sheet += """
                QPushButton {
                    padding: 3px 10px;
                    font-size: 8.5pt;
                }
            """
        else:
            # Normal
            style_sheet += """
                QPushButton {
                    padding: 5px 16px;
                    font-size: 9pt;
                }
            """

        if self._chatgpt_style:
            style_sheet += f"""
                QPushButton {{
                    background-color: transparent;
                    color: {tertiary_color};
                    border: none;
                    border-radius: 6px;
                    padding: 4px;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                    color: {tertiary_hover};
                    border: none;
                }}
                QPushButton:pressed, QPushButton:checked {{
                    background-color: {bg_checked};
                    color: {tertiary_hover};
                    border: none;
                }}
                QPushButton:disabled {{
                    background-color: transparent;
                    color: {disabled_text};
                    border: none;
                }}
            """
        
        self.setStyleSheet(style_sheet)
        
        if not self._updating_text:
            if self._icon_name and not self._custom_icon and not self._text_only:
                self._update_icon()
    
    def _get_fallback_icon(self, icon_name: str) -> str | None:
        """Get fallback emoji for icon name"""
        return self.FALLBACK_ICONS.get(icon_name)
    
    def _strip_emoji(self, text: str | None) -> str:
        """Strip any emoji prefix from text"""
        if not text:
            return ""
        for emoji in self.FALLBACK_ICONS.values():
            if text.startswith(emoji):
                return text[len(emoji):].strip()
        return text.strip()
    
    def _update_icon(self):
        """Update icon with current theme colors"""
        if not self._icon_name or self._text_only:
            return
        
        if self._updating_text:
            return
        
        self._updating_text = True
        
        try:
            # Get icon color based on button style and theme
            if self._style == self.PRIMARY:
                color = "#ffffff"
            elif self._style == self.DANGER:
                color = "#ffffff"
            elif self._style == self.SECONDARY:
                color = "#dcddde" if self._is_dark else "#495057"
            else:  # TERTIARY
                color = "#dcddde" if self._is_dark else "#6c757d"
            
            # Try to load icon from SVG or PNG
            icon = self._load_icon(self._icon_name, color)
            
            current_text = self.text() or ""
            clean_text = self._strip_emoji(self._original_text or current_text)
            
            if not icon.isNull():
                self.setIcon(icon)
                self.setIconSize(self._icon_size)
                self._has_icon = True
                if self.text() != clean_text:
                    super().setText(clean_text)
                return
            
            # Use fallback emoji
            self._has_icon = False
            fallback_emoji = self._get_fallback_icon(self._icon_name)
            
            if fallback_emoji and clean_text:
                new_text = f"{fallback_emoji} {clean_text}"
                if self.text() != new_text:
                    super().setText(new_text)
            elif clean_text:
                if self.text() != clean_text:
                    super().setText(clean_text)
            self.setIcon(QIcon())
            
        finally:
            self._updating_text = False
    
    def _load_icon(self, icon_name: str, color: str | None = None):
        """Load icon from assets/icons/"""
        icon_paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            self._icon_size.width(), self._icon_size.height(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        if color:
                            colored = scaled.copy()
                            painter = QPainter(colored)
                            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                            painter.fillRect(colored.rect(), QColor(color))
                            painter.end()
                            return QIcon(colored)
                        else:
                            return QIcon(scaled)
                except Exception:
                    pass
        
        return QIcon()
    
    def set_button_style(self, style):
        """Change button style dynamically"""
        self._style = style
        self._apply_style()
    
    def set_compact(self, compact=True):
        """Toggle between compact and normal size - for tight spaces like toolbars"""
        self._compact = compact
        if compact:
            self._dense = False
            self.setMinimumHeight(24)
            self.setMaximumHeight(28)
            self.setIconSize(QSize(14, 14))
            if not self.text().strip():
                self.setMinimumWidth(28)
        else:
            self.setMinimumHeight(30)
            self.setMaximumHeight(38)
            self.setIconSize(QSize(16, 16))
            self.setMinimumWidth(0)
        self._apply_style()

    def set_dense(self, dense=True):
        """Use a compact-but-readable preset - for sidebars and dense layouts"""
        self._dense = dense
        if dense:
            self._compact = False
            self.setMinimumHeight(28)
            self.setMaximumHeight(32)
            self.setIconSize(QSize(15, 15))
            if not self.text().strip():
                self.setMinimumWidth(32)
        else:
            self.setMinimumHeight(30)
            self.setMaximumHeight(38)
            self.setIconSize(QSize(16, 16))
            self.setMinimumWidth(0)
        self._apply_style()

    def set_chatgpt_style(self, enabled=True):
        """Use a quiet, borderless icon-button style with a subtle hover state."""
        self._chatgpt_style = bool(enabled)
        if enabled:
            self._style = self.TERTIARY
            self.setCheckable(False)
            self.setAutoExclusive(False)
        self._apply_style()
    
    def set_icon(self, icon_name, size=(16, 16)):
        """Set icon from SVG file with theme color support"""
        self._icon_name = icon_name
        self._icon_size = QSize(size[0], size[1])
        self._custom_icon = None
        self._text_only = False
        self._update_icon()
    
    def set_custom_icon(self, icon, size=(16, 16)):
        """Set a custom icon manually"""
        self._custom_icon = icon
        self._icon_name = None
        self._text_only = False
        self._has_icon = True
        
        self._updating_text = True
        try:
            self.setIcon(icon)
            self.setIconSize(QSize(size[0], size[1]))
            current_text = self.text() or ""
            clean_text = self._strip_emoji(self._original_text or current_text)
            if self.text() != clean_text:
                super().setText(clean_text)
        finally:
            self._updating_text = False
    
    def set_text_only(self, text_only=True):
        """Set button to text-only mode"""
        self._text_only = text_only
        if text_only:
            self._updating_text = True
            try:
                self.setIcon(QIcon())
                self._has_icon = False
                current_text = self.text() or ""
                clean_text = self._strip_emoji(self._original_text or current_text)
                if self.text() != clean_text:
                    super().setText(clean_text)
            finally:
                self._updating_text = False
        elif self._icon_name:
            self._update_icon()
    
    def get_icon_name(self):
        return self._icon_name
    
    def has_icon(self):
        return self._has_icon
    
    def setText(self, text: str | None):
        safe_text = text if text is not None else ""
        self._original_text = self._strip_emoji(safe_text)
        
        if not self._updating_text:
            self._updating_text = True
            try:
                super().setText(safe_text)
            finally:
                self._updating_text = False
        else:
            super().setText(safe_text)
        
        self._apply_style()
    
    def update_theme(self):
        self._on_theme_changed(theme_manager.get_current_theme())
