# ui/widgets/summary_card_widget.py
"""
Summary Card Widget with Modern Design (Glassmorphism style)
Inspired by Panelix – Modern Analytics Dashboard UI Design
Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
WITH PROGRESS BAR
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QSize
from PyQt6.QtGui import QColor, QLinearGradient, QBrush, QPainter, QPen, QFont, QPixmap, QIcon
from loguru import logger
import os
from pathlib import Path


class SummaryCardWidget(QWidget):
    """Summary card with modern glassmorphism design, theme support, and SVG icon support"""
    
    clicked = pyqtSignal()
    
    def __init__(self, title="", value="0", icon="", color="#5865f2", 
                 gradient_colors=None, icon_is_svg=False, parent=None,
                 show_progress=False, progress_value=0, progress_max=100,
                 flat=False):
        super().__init__(parent)
        self._title = title
        self._raw_value = value
        self._display_value = value
        self._icon_name = icon
        self._color = color
        self._gradient_colors = gradient_colors or [color, self._darken_color(color, 15)]
        self._icon_is_svg = icon_is_svg
        self._icon_pixmap = None
        self._is_dark = self._check_theme()
        self._is_hovered = False
        self._icon_loaded = False
        self._icon_size = 22
        self._show_progress = show_progress
        self._progress_value = progress_value
        self._progress_max = progress_max
        self._comparison_text = ""
        self._comparison_direction = "neutral"
        self._flat = bool(flat)
        
        # ✅ Load SVG icon if needed
        if self._icon_is_svg:
            self._load_svg_icon()
        
        self.setup_ui()
        
        # ✅ Set initial value with formatting
        self.set_value(self._raw_value)
        
        # ✅ Connect to theme manager
        try:
            from ui.themes.theme_manager import theme_manager
            theme_manager.theme_changed.connect(self.on_theme_changed)
        except:
            pass
    
    # ============================================================
    # ✅ NUMBER FORMATTING METHODS
    # ============================================================
    
    def _format_number(self, value):
        """Format large numbers with K, M, B suffixes."""
        try:
            if isinstance(value, str):
                clean_value = value.replace(',', '').strip()
                try:
                    num = float(clean_value)
                except ValueError:
                    return value
            elif isinstance(value, (int, float)):
                num = float(value)
            else:
                return str(value)
            
            is_negative = num < 0
            num = abs(num)
            
            if num >= 1_000_000_000:
                formatted = f"{num / 1_000_000_000:.1f}B"
            elif num >= 1_000_000:
                formatted = f"{num / 1_000_000:.1f}M"
            elif num >= 1_000:
                formatted = f"{num / 1_000:.1f}K"
            else:
                formatted = f"{int(num):,}" if num == int(num) else f"{num:,.2f}"
            
            if is_negative:
                formatted = f"-{formatted}"
            
            return formatted
            
        except (ValueError, TypeError):
            return str(value)
    
    def _format_currency(self, value, symbol="Ks"):
        """Format currency values with appropriate suffixes."""
        try:
            formatted = self._format_number(value)
            
            if formatted in ["—", "N/A", "-"]:
                return formatted
            
            suffix = ""
            for s in ["K", "M", "B"]:
                if s in formatted:
                    suffix = s
                    formatted = formatted.replace(s, "")
                    break
            
            formatted = formatted.strip()
            
            if suffix:
                return f"{symbol} {formatted}{suffix}"
            else:
                return f"{symbol} {formatted}"
            
        except:
            return str(value)
    
    def _darken_color(self, color_hex, percent):
        """Darken a hex color by percent"""
        color = QColor(color_hex)
        h, s, v, a = color.getHsv()
        v = max(0, v - percent)
        color.setHsv(h, s, v, a)
        return color.name()
    
    def _lighten_color(self, color_hex, percent):
        """Lighten a hex color by percent"""
        color = QColor(color_hex)
        h, s, v, a = color.getHsv()
        v = min(255, v + percent)
        color.setHsv(h, s, v, a)
        return color.name()
    
    def _get_base_dir(self):
        """Get the base directory of the project"""
        current_dir = Path(__file__).resolve().parent
        
        for _ in range(5):
            if (current_dir / "assets").exists():
                return current_dir
            current_dir = current_dir.parent
        
        return Path(__file__).resolve().parent.parent.parent
    
    def _get_themed_icon(self, icon_name, size=(22, 22)):
        """Get themed SVG icon using theme_manager"""
        try:
            from ui.themes.theme_manager import get_themed_icon, get_icon_path
            
            icon = get_themed_icon(icon_name, size=size)
            if not icon.isNull():
                pixmap = icon.pixmap(QSize(size[0], size[1]))
                if not pixmap.isNull():
                    return pixmap
            
            icon_path = get_icon_path(icon_name)
            if icon_path and icon_path.exists():
                pixmap = QPixmap(str(icon_path))
                if not pixmap.isNull():
                    return pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
        except Exception as e:
            logger.debug(f"Could not load themed icon: {e}")
        
        return None
    
    def _load_svg_icon(self, size=None):
        """Load SVG icon using theme_manager"""
        if not self._icon_name:
            self._icon_loaded = False
            return
        
        icon_size = size if size else (self._icon_size, self._icon_size)
        
        clean_name = self._icon_name
        if clean_name.endswith('.svg') or clean_name.endswith('.png'):
            clean_name = os.path.splitext(clean_name)[0]
        
        pixmap = self._get_themed_icon(clean_name, size=icon_size)
        
        if pixmap and not pixmap.isNull():
            self._icon_pixmap = pixmap
            self._icon_loaded = True
            logger.debug(f"Loaded SVG icon: {clean_name}")
            return
        
        base_dir = self._get_base_dir()
        icon_paths = [
            base_dir / "assets" / "icons" / f"{clean_name}.svg",
            base_dir / "assets" / "icons" / f"{clean_name}.png",
            Path("assets/icons") / f"{clean_name}.svg",
            Path("assets/icons") / f"{clean_name}.png",
        ]
        
        for path in icon_paths:
            if path.exists():
                try:
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        self._icon_pixmap = pixmap.scaled(
                            icon_size[0], icon_size[1],
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self._icon_loaded = True
                        logger.debug(f"Loaded icon from: {path}")
                        return
                except Exception as e:
                    logger.debug(f"Could not load icon {path}: {e}")
        
        self._icon_pixmap = None
        self._icon_loaded = False
        logger.debug(f"Could not load icon: {clean_name}")
    
    def _get_emoji_fallback(self):
        """Get emoji fallback for icon name"""
        emoji_map = {
            "receipt_long": "💰",
            "money_off": "💸",
            "trending_up": "📈",
            "currency_exchange": "↩️",
            "percent_discount": "🏷️",
            "credit_card": "💳",
            "warning": "⚠️",
            "attach_money": "💰",
            "bar_chart": "📊",
            "savings": "📈",
            "backup": "💾",
            "cloud_upload": "☁️",
            "point_of_sale": "🛒",
            "dashboard": "📊",
            "analytics": "📈",
            "package": "📦",
            "inventory": "📋",
            "receipt": "🧾",
            "person": "👤",
            "money": "💰",
            "logout": "🚪",
            "settings": "⚙️",
            "search": "🔍",
            "print": "🖨️",
            "clock": "🕐",
            "date": "📅",
            "category": "📂",
            "sell": "💲",
            "shopping_cart": "🛒",
            "groups": "👥",
            "home": "🏠",
            "local_shipping": "🚚",
            "payments": "💳",
            "swap_horiz": "🔄",
            "inventory_2": "📦",
            "orders": "📋",
            "leaderboard": "📊",
            "list_alt": "📋",
            "grid_view": "📊",
            "folder_open": "📂",
            "group_work": "👥",
            "file_export": "📤",
            "upload_file": "📤",
            "download_done": "✅",
            "label": "🏷️",
            "folder": "📁",
            "check_circle": "✅",
            "cancel": "❌",
            "visibility_off": "👁️",
            "active": "✅",
            "add": "➕",
            "article": "📄",
            "barcode": "📱",
            "calendar_month": "📅",
            "close": "❌",
            "close_small": "✕",
            "delete": "🗑️",
            "description": "📄",
            "edit": "✏️",
            "favorite": "⭐",
            "favorite_border": "☆",
            "hidden": "👁️",
            "image": "🖼️",
            "image_inset": "🖼️",
            "inactive": "⏸️",
            "inactive_order": "⏸️",
            "notifications_active": "🔔",
            "products": "📦",
            "save": "💾",
            "speech_to_text": "🎤",
            "today": "📅",
            "total": "💰",
            "visibility": "👁️",
        }
        return emoji_map.get(self._icon_name, "📊")
    
    def _check_theme(self):
        """Check if dark theme is active"""
        try:
            from ui.themes.theme_manager import is_dark_theme
            return is_dark_theme()
        except:
            try:
                from models.database import connect_db
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key='theme'")
                row = cursor.fetchone()
                conn.close()
                theme = row[0] if row else "Light"
                return theme.lower() in ["dark", "ubuntu dark", "pyqt6 dark"]
            except:
                return False
    
    def _get_icon_color(self):
        """Get icon color based on current theme"""
        if self._flat:
            return self._color
        if self._is_dark:
            return "#ffffff"
        else:
            return "#ffffff"
    
    def _create_colored_pixmap(self, source_pixmap, color_hex):
        """Create a colored version of the pixmap"""
        try:
            if source_pixmap is None or source_pixmap.isNull():
                return None
            
            pixmap = source_pixmap.copy()
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor(color_hex))
            painter.end()
            return pixmap
        except Exception as e:
            logger.debug(f"Could not color icon: {e}")
            return source_pixmap
    
    def _update_icon_display(self):
        """Update icon display (SVG or emoji) - only one at a time"""
        if not hasattr(self, 'icon_label'):
            return
        
        if self._icon_is_svg and self._icon_loaded and self._icon_pixmap:
            color = self._get_icon_color()
            colored_pixmap = self._create_colored_pixmap(self._icon_pixmap, color)
            
            if colored_pixmap and not colored_pixmap.isNull():
                self.icon_label.setPixmap(colored_pixmap)
            else:
                self.icon_label.setPixmap(self._icon_pixmap)
            self.icon_label.setText("")
            self.icon_label.setStyleSheet("""
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            """)
        else:
            emoji = self._get_emoji_fallback()
            self.icon_label.setText(emoji)
            self.icon_label.setPixmap(QPixmap())
            self.icon_label.setStyleSheet("""
                font-size: 18px;
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                color: white;
            """)
    
    def on_theme_changed(self, theme_name):
        """Handle theme change from theme manager"""
        self._is_dark = self._check_theme()
        self._apply_theme()
        self._update_icon_display()
    
    def _apply_theme(self):
        """Apply theme-aware styles to card"""
        if self._flat:
            from ui.themes.theme_manager import get_theme_colors
            colors = get_theme_colors()
            self.card.set_flat_palette(colors['card_bg'], colors['border'], colors['card_hover'])
            if hasattr(self, 'title_label'):
                self.title_label.setStyleSheet(f"color:{colors['text_secondary']};font-size:8.5pt;font-weight:600;background:transparent;border:none;")
            if hasattr(self, 'value_label'):
                self.value_label.setStyleSheet(f"color:{colors['text']};font-size:15pt;font-weight:700;background:transparent;border:none;padding:3px 0 1px 0;")
            if hasattr(self, 'icon_container'):
                tint = QColor(self._color)
                tint.setAlpha(34)
                self.icon_container.setStyleSheet(
                    f"QFrame{{background-color:{tint.name(QColor.NameFormat.HexArgb)};border:1px solid {self._color};border-radius:8px;}}"
                )
            self._update_icon_display()
            return

        if hasattr(self.card, 'set_gradient_colors'):
            if self._is_dark:
                dark_gradient = [self._darken_color(c, 10) for c in self._gradient_colors]
                self.card.set_gradient_colors(dark_gradient)
            else:
                light_gradient = [self._lighten_color(c, 10) for c in self._gradient_colors]
                self.card.set_gradient_colors(light_gradient)
        
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.7);
                    font-size: 8.5pt;
                    font-weight: 600;
                    letter-spacing: 0.5px;
                    text-transform: uppercase;
                    background: transparent;
                    border: none;
                    padding: 0px;
                    margin: 0px;
                }
            """)
        
        if hasattr(self, 'value_label'):
            self.value_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 15pt;
                    font-weight: 700;
                    background: transparent;
                    border: none;
                    padding: 3px 0px 1px 0px;
                    margin: 0px;
                }
            """)

        if hasattr(self, 'comparison_label'):
            self._apply_comparison_style()
        
        if hasattr(self, 'icon_container'):
            self.icon_container.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.16);
                    border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.10);
                }
            """)
        
        # ✅ Progress bar styling
        if hasattr(self, 'progress_bar'):
            if self._is_dark:
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(255, 255, 255, 0.1);
                        border: none;
                        border-radius: 4px;
                        height: 6px;
                    }
                    QProgressBar::chunk {
                        background-color: rgba(255, 255, 255, 0.8);
                        border-radius: 4px;
                    }
                """)
            else:
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(0, 0, 0, 0.08);
                        border: none;
                        border-radius: 4px;
                        height: 6px;
                    }
                    QProgressBar::chunk {
                        background-color: rgba(0, 0, 0, 0.5);
                        border-radius: 4px;
                    }
                """)
        
        self.card.setStyleSheet("""
            QFrame {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background-color: transparent;
            }
            QFrame:hover {
                border: 1px solid rgba(255, 255, 255, 0.18);
            }
        """)
        
        self._update_icon_display()
    
    def setup_ui(self):
        # Card frame
        self.card = ModernGradientCard(self._gradient_colors, self._color, flat=self._flat)
        self.card.setFixedHeight(140 if self._show_progress else 120)
        self.card.setMinimumWidth(140)
        self.card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._apply_theme()
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(4)
        card_layout.setContentsMargins(14, 8, 14, 8)
        
        # Top section: Icon and Title (horizontal layout)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        
        # Icon container
        self.icon_container = QFrame()
        self.icon_container.setFixedSize(34, 34)
        self.icon_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }
        """)
        
        icon_layout = QVBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("""
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        """)
        
        self._update_icon_display()
        
        icon_layout.addWidget(self.icon_label)
        top_layout.addWidget(self.icon_container)
        
        # Title
        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 8.5pt;
                font-weight: 600;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()
        
        card_layout.addLayout(top_layout)
        
        # ✅ Value (bottom section)
        value_layout = QHBoxLayout()
        value_layout.setSpacing(0)
        
        self.value_label = QLabel(str(self._display_value))
        self.value_label.setObjectName("cardValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setWordWrap(True)
        self.value_label.setMinimumHeight(34)
        self.value_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 15pt;
                font-weight: 700;
                background: transparent;
                border: none;
                padding: 3px 0px 1px 0px;
                margin: 0px;
            }
        """)
        value_layout.addStretch()
        value_layout.addWidget(self.value_label)
        
        card_layout.addLayout(value_layout)

        comparison_layout = QHBoxLayout()
        comparison_layout.setSpacing(0)
        comparison_layout.addStretch()

        self.comparison_label = QLabel()
        self.comparison_label.setObjectName("cardComparison")
        self.comparison_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.comparison_label.setFixedHeight(19)
        self.comparison_label.setVisible(False)
        self._apply_comparison_style()

        comparison_layout.addWidget(self.comparison_label)
        card_layout.addLayout(comparison_layout)
        
        # ✅ Progress Bar (if enabled)
        if self._show_progress:
            progress_layout = QHBoxLayout()
            progress_layout.setSpacing(0)
            
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, self._progress_max)
            self.progress_bar.setValue(self._progress_value)
            self.progress_bar.setFormat("")
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setFixedHeight(6)
            
            if self._is_dark:
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(255, 255, 255, 0.1);
                        border: none;
                        border-radius: 4px;
                        height: 6px;
                    }
                    QProgressBar::chunk {
                        background-color: rgba(255, 255, 255, 0.8);
                        border-radius: 4px;
                    }
                """)
            else:
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(0, 0, 0, 0.08);
                        border: none;
                        border-radius: 4px;
                        height: 6px;
                    }
                    QProgressBar::chunk {
                        background-color: rgba(0, 0, 0, 0.5);
                        border-radius: 4px;
                    }
                """)
            
            progress_layout.addWidget(self.progress_bar)
            card_layout.addLayout(progress_layout)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.card)
        self.setLayout(main_layout)
    
    # Mouse events
    def _on_click(self, event):
        self.clicked.emit()
    
    def _on_enter(self, event):
        self._is_hovered = True
        self.card.update()
    
    def _on_leave(self, event):
        self._is_hovered = False
        self.card.update()
    
    # ========== Public Methods ==========
    
    def set_value(self, value, currency_symbol=None, is_currency=True):
        """Update the value displayed with automatic formatting."""
        self._raw_value = value
        
        if is_currency and currency_symbol:
            self._display_value = self._format_currency(value, currency_symbol)
        elif is_currency:
            self._display_value = self._format_number(value)
        else:
            self._display_value = self._format_number(value)
        
        if hasattr(self, 'value_label'):
            self.value_label.setText(str(self._display_value))
    
    def set_value_raw(self, value):
        """Set value without any formatting (display as is)."""
        self._raw_value = value
        self._display_value = str(value)
        if hasattr(self, 'value_label'):
            self.value_label.setText(str(value))
    
    def set_title(self, title):
        """Update the title"""
        self._title = title
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)
    
    def set_color(self, color):
        """Update the value color and gradient"""
        self._color = color
        self._gradient_colors = [color, self._darken_color(color, 15)]
        
        if hasattr(self, 'card'):
            self.card.set_gradient_colors(self._gradient_colors)
            self.card.update()
    
    def set_icon(self, icon_name, is_svg=True, size=None):
        """Set icon by name."""
        self._icon_name = icon_name
        self._icon_is_svg = is_svg
        self._icon_loaded = False
        
        if size is not None:
            if isinstance(size, (tuple, list)) and len(size) >= 2:
                self._icon_size = size[0] if size[0] >= size[1] else size[1]
            elif isinstance(size, int):
                self._icon_size = size
        
        if is_svg:
            self._load_svg_icon(size=(self._icon_size, self._icon_size))
        
        self._update_icon_display()
    
    def set_icon_emoji(self, emoji):
        """Set emoji icon (fallback)"""
        self._icon_name = emoji
        self._icon_is_svg = False
        self._icon_loaded = False
        self._icon_pixmap = None
        self._update_icon_display()
    
    def set_progress(self, value, max_value=100):
        """Set progress bar value"""
        self._show_progress = True
        self._progress_value = value
        self._progress_max = max_value
        
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(0, max_value)
            self.progress_bar.setValue(value)
    
    def set_progress_visible(self, visible):
        """Show or hide progress bar"""
        self._show_progress = visible
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(visible)

    def set_comparison(self, text="", direction="neutral"):
        """Set a compact comparison label under the card value."""
        self._comparison_text = str(text or "")
        self._comparison_direction = direction if direction in ("up", "down", "neutral") else "neutral"
        if hasattr(self, 'comparison_label'):
            self.comparison_label.setText(self._comparison_text)
            self.comparison_label.setVisible(bool(self._comparison_text))
            self._apply_comparison_style()

    def _apply_comparison_style(self):
        if not hasattr(self, 'comparison_label'):
            return
        if self._comparison_direction == "up":
            bg = "rgba(46, 204, 113, 0.22)"
            fg = "#d9ffe8"
        elif self._comparison_direction == "down":
            bg = "rgba(231, 76, 60, 0.24)"
            fg = "#ffe0dc"
        else:
            bg = "rgba(255, 255, 255, 0.16)"
            fg = "rgba(255, 255, 255, 0.82)"
        self.comparison_label.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 8pt;
                font-weight: 700;
            }}
        """)
    
    def update_theme(self):
        """Manually update theme"""
        self._is_dark = self._check_theme()
        self._apply_theme()
        self._update_icon_display()


class ModernGradientCard(QFrame):
    """Custom QFrame with modern gradient background and glassmorphism effect"""
    
    def __init__(self, gradient_colors, accent_color, parent=None, flat=False):
        super().__init__(parent)
        self._gradient_colors = gradient_colors
        self._accent_color = accent_color
        self._radius = 8
        self._flat = bool(flat)
        self._surface_color = "#151c2a"
        self._border_color = "#293348"
        self._hover_color = "#192232"
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMouseTracking(True)
        
    def set_gradient_colors(self, colors):
        self._gradient_colors = colors
        self.update()

    def set_flat_palette(self, surface, border, hover):
        self._surface_color = surface
        self._border_color = border
        self._hover_color = hover
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()

        if self._flat:
            hovered = bool(getattr(self.parent(), '_is_hovered', False))
            painter.setBrush(QBrush(QColor(self._hover_color if hovered else self._surface_color)))
            painter.setPen(QPen(QColor(self._border_color), 1))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 11, 11)
            painter.setBrush(QBrush(QColor(self._accent_color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(12, rect.height() - 4, -12, -1), 2, 2)
            painter.end()
            return
        
        # ========== Main gradient background ==========
        gradient = QLinearGradient(
            QPointF(rect.topLeft()),
            QPointF(rect.bottomRight())
        )
        
        if self._gradient_colors and len(self._gradient_colors) >= 2:
            for i, color in enumerate(self._gradient_colors):
                gradient.setColorAt(i / (len(self._gradient_colors) - 1), QColor(color))
        else:
            gradient.setColorAt(0, QColor("#5865f2"))
            gradient.setColorAt(1, QColor("#4752c4"))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._radius, self._radius)
        
        # ========== Glassmorphism overlay ==========
        shine_rect = rect.adjusted(0, 0, -int(rect.width() * 0.25), -int(rect.height() * 0.55))
        shine_gradient = QLinearGradient(
            QPointF(rect.topLeft()),
            QPointF(rect.bottomRight())
        )
        shine_gradient.setColorAt(0, QColor(255, 255, 255, 16))
        shine_gradient.setColorAt(0.5, QColor(255, 255, 255, 4))
        shine_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setBrush(QBrush(shine_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(shine_rect, self._radius, self._radius)
        
        # ========== Subtle border glow ==========
        border_rect = rect.adjusted(1, 1, -1, -1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.drawRoundedRect(border_rect, self._radius - 1, self._radius - 1)
        
        # ========== Accent line (bottom) ==========
        accent_rect = rect.adjusted(14, rect.height() - 3, -14, -1)
        painter.setBrush(QBrush(QColor(self._accent_color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(accent_rect, 2, 2)
        
        painter.end()
    
    def enterEvent(self, event):
        if self.parent():
            parent = self.parent()
            if hasattr(parent, '_on_enter'):
                parent._on_enter(event)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        if self.parent():
            parent = self.parent()
            if hasattr(parent, '_on_leave'):
                parent._on_leave(event)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if self.parent():
            parent = self.parent()
            if hasattr(parent, '_on_click'):
                parent._on_click(event)
        super().mousePressEvent(event)
