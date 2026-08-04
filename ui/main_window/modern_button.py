# ui/main_window/modern_button.py
"""
Modern Button with Multiple Styles (Primary, Secondary, Tertiary)
Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
Support SVG icons with theme colors
No icon animations - Clean and minimal
"""

import os
from typing import Optional

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt6.QtCore import Qt, QSize

from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme


class ModernButton(QPushButton):
    """Modern button with Primary, Secondary, and Tertiary styles - Theme-aware (No animations)"""
    
    # Button style constants
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    
    # Complete Fallback emojis for all icons (when SVG not found)
    FALLBACK_ICONS = {
        # Action icons
        'add': '➕',
        'edit': '✏️',
        'delete': '🗑️',
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
        'point_of_sale': '💳',
        'barcode': '📱',
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
        'remove': '➖',
    }
    
    def __init__(self, text: str = "", style: str = PRIMARY, parent=None):
        super().__init__(text, parent)
        
        # Remove default icon
        self.setIcon(QIcon())
        
        # Set style
        self._style = style
        self._compact = False
        self._is_dark = is_dark_theme()
        self._text_only = False
        self._updating_text = False
        
        # Icon data
        self._icon_name: Optional[str] = None
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
        
        # Default size - normal
        self.setMinimumHeight(32)
        self.setMaximumHeight(40)
        
        # Connect theme change signal
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme change - update button style and icon"""
        self._is_dark = is_dark_theme()
        self._apply_style()
        
        # Update icon if we have an icon name
        if self._icon_name and not self._custom_icon and not self._text_only:
            self._update_icon()
        
        self.update()
    
    def _apply_style(self) -> None:
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
            
            secondary_color = "#dcddde"
            secondary_hover = "#ffffff"
            secondary_border = "transparent"  # ✅ Transparent border
            secondary_border_hover = "transparent"
            
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
            
            secondary_color = "#495057"
            secondary_hover = "#212529"
            secondary_border = "transparent"  # ✅ Transparent border
            secondary_border_hover = "transparent"
            
            tertiary_color = "#6c757d"
            tertiary_hover = "#495057"
            
            bg_hover = "#f8f9fa"
            bg_checked = "#f1f3f5"
            
            disabled_text = "#adb5bd"
        
        # Base styles common to all buttons - No border for secondary
        style_sheet = f"""
            QPushButton {{
                border: none;
                border-radius: 0px;
                font-weight: 500;
                text-align: left;
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
                margin-right: 12px;
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
            
        elif self._style == self.SECONDARY:
            style_sheet += f"""
                QPushButton {{
                    background-color: transparent;
                    color: {secondary_color};
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                    color: {secondary_hover};
                }}
                QPushButton:checked {{
                    background-color: {bg_checked};
                    color: {secondary_hover};
                }}
                QPushButton:checked:hover {{
                    background-color: {bg_hover};
                }}
                QPushButton:disabled {{
                    color: {disabled_text};
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
            style_sheet += """
                QPushButton {
                    padding: 3px 12px;
                    font-size: 8pt;
                }
            """
        else:
            style_sheet += """
                QPushButton {
                    padding: 6px 20px;
                    font-size: 9.5pt;
                }
            """
        
        self.setStyleSheet(style_sheet)
        
        # Update icon if we have one and not text-only
        if not self._updating_text:
            if self._icon_name and not self._custom_icon and not self._text_only:
                self._update_icon()
    
    def _get_fallback_icon(self, icon_name: str) -> Optional[str]:
        """Get fallback emoji for icon name, return None if not found"""
        return self.FALLBACK_ICONS.get(icon_name)
    
    def _strip_emoji(self, text: str) -> str:
        """Strip any emoji prefix from text"""
        if not text:
            return ""
        for emoji in self.FALLBACK_ICONS.values():
            if text.startswith(emoji):
                return text[len(emoji):].strip()
        return text.strip()
    
    def _update_icon(self) -> None:
        """Update icon with current theme colors"""
        if not self._icon_name or self._text_only:
            return
        
        # Prevent recursion
        if self._updating_text:
            return
        
        self._updating_text = True
        
        try:
            # Get icon color based on button style and theme
            if self._style == self.PRIMARY:
                color = "#ffffff"
            elif self._style == self.SECONDARY:
                color = "#dcddde" if self._is_dark else "#495057"
            else:  # TERTIARY
                color = "#dcddde" if self._is_dark else "#6c757d"
            
            # Try to load icon from SVG or PNG
            icon = self._load_icon(self._icon_name, color)
            
            # Get clean text (without emoji)
            clean_text = self._strip_emoji(self._original_text or self.text())
            
            # If icon loaded successfully, set it
            if not icon.isNull():
                self.setIcon(icon)
                self.setIconSize(self._icon_size)
                self._has_icon = True
                # Update text without emoji
                if self.text() != clean_text:
                    super().setText(clean_text)
                return
            
            # If icon not found, use fallback emoji (if available)
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
    
    def _load_icon(self, icon_name: str, color: Optional[str] = None) -> QIcon:
        """
        Load icon from assets/icons/
        
        Args:
            icon_name: Name of the icon (without extension)
            color: Hex color code for the icon
            
        Returns:
            QIcon or QIcon() if not found
        """
        icon_paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        # Scale to desired size
                        scaled = pixmap.scaled(
                            self._icon_size.width(), self._icon_size.height(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # If color is provided, colorize the icon
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
                    # Silent fail - we'll use fallback
                    pass
        
        return QIcon()
    
    def set_button_style(self, style: str) -> None:
        """Change button style dynamically"""
        self._style = style
        self._apply_style()
    
    def set_compact(self, compact: bool = True) -> None:
        """Toggle between compact and normal size"""
        self._compact = compact
        if compact:
            self.setMinimumHeight(28)
            self.setMaximumHeight(36)
            if not self.text().strip():
                self.setMinimumWidth(28)
        else:
            self.setMinimumHeight(32)
            self.setMaximumHeight(40)
            self.setMinimumWidth(0)
        self._apply_style()
    
    def set_icon(self, icon_name: str, size: tuple = (16, 16)) -> None:
        """
        Set icon from SVG file with theme color support.
        
        Args:
            icon_name: Name of the SVG file (without extension)
            size: Tuple of (width, height)
        """
        self._icon_name = icon_name
        self._icon_size = QSize(size[0], size[1])
        self._custom_icon = None
        self._text_only = False
        self._update_icon()
    
    def set_icon_name(self, icon_name: str, size: tuple = (16, 16)) -> None:
        """
        Set icon from SVG file with theme color support.
        This is an alias for set_icon for compatibility.
        
        Args:
            icon_name: Name of the SVG file (without extension)
            size: Tuple of (width, height)
        """
        self.set_icon(icon_name, size)
    
    def set_custom_icon(self, icon: QIcon, size: tuple = (16, 16)) -> None:
        """Set a custom icon manually (not theme-aware)"""
        self._custom_icon = icon
        self._icon_name = None
        self._text_only = False
        self._has_icon = True
        
        self._updating_text = True
        try:
            self.setIcon(icon)
            self.setIconSize(QSize(size[0], size[1]))
            # Remove any emoji from text
            clean_text = self._strip_emoji(self._original_text or self.text())
            if self.text() != clean_text:
                super().setText(clean_text)
        finally:
            self._updating_text = False
    
    def set_text_only(self, text_only: bool = True) -> None:
        """Set button to text-only mode (no icon)"""
        self._text_only = text_only
        if text_only:
            self._updating_text = True
            try:
                self.setIcon(QIcon())
                self._has_icon = False
                clean_text = self._strip_emoji(self._original_text or self.text())
                if self.text() != clean_text:
                    super().setText(clean_text)
            finally:
                self._updating_text = False
        elif self._icon_name:
            self._update_icon()
    
    def get_icon_name(self) -> Optional[str]:
        """Get the current icon name"""
        return self._icon_name
    
    def has_icon(self) -> bool:
        """Check if button has an icon loaded"""
        return self._has_icon
    
    def update_theme(self) -> None:
        """Public method to manually update theme"""
        self._on_theme_changed(theme_manager.get_current_theme())
    
    # ❌ REMOVED: enterEvent and leaveEvent (icon animation)
    # No hover animations anymore
    
    def setText(self, text: str) -> None:
        """Override setText to ensure proper styling"""
        # Store original text without emoji
        self._original_text = self._strip_emoji(text)
        
        # Update the actual text
        if not self._updating_text:
            self._updating_text = True
            try:
                super().setText(text)
            finally:
                self._updating_text = False
        else:
            super().setText(text)
        
        # Re-apply style to ensure text color is correct
        self._apply_style()