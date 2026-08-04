# ui/main_window/header.py
"""
Main Window Header Component with SVG Icons
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from loguru import logger
import os
from datetime import datetime


class Header(QFrame):
    """Main Window Header with SVG icons for clock and user"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self._setup_ui()
        
        # Start clock timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
        # Update clock immediately
        self.update_clock()
    
    def _setup_ui(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        self.setObjectName("header")
        self.setFixedHeight(56)
        
        if is_dark:
            self.setStyleSheet("""
                QFrame#header {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4752c4, stop:1 #3c45a3);
                    border-bottom: none;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#header {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5865f2, stop:1 #4752c4);
                    border-bottom: none;
                }
            """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 6, 20, 6)
        
        # Left: Logo and Title
        logo_container = QWidget()
        logo_container.setStyleSheet("background: transparent;")
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(10)
        
        # Logo Label
        self.logo_label = QLabel()
        self.logo_label.setObjectName("logo_label")
        self.logo_label.setFixedSize(48, 48)
        self.logo_label.setScaledContents(True)
        self.logo_label.setStyleSheet("""
            background: transparent;
            border-radius: 10px;
            padding: 4px;
        """)
        logo_layout.addWidget(self.logo_label)
        
        # Title Label
        self.title_label = QLabel("ZAY POS")
        self.title_label.setObjectName("title_label")
        self.title_label.setStyleSheet("""
            color: white;
            font-size: 13pt;
            font-weight: bold;
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        """)
        logo_layout.addWidget(self.title_label)
        logo_layout.addStretch()
        
        layout.addWidget(logo_container)
        layout.addStretch()
        
        # Right: Date, Clock, User with SVG icons
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # ============================================================
        # DATE ICON + TEXT (using date.svg)
        # ============================================================
        date_container = QWidget()
        date_container.setStyleSheet("background: transparent;")
        date_layout = QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(6)
        
        # Date icon (SVG)
        self.date_icon = QLabel()
        self.date_icon.setFixedSize(20, 20)
        self.date_icon.setScaledContents(True)
        self._load_svg_icon(self.date_icon, "date", "#ffffff")
        date_layout.addWidget(self.date_icon)
        
        # Date text
        self.date_label = QLabel()
        self.date_label.setObjectName("date_label")
        self.date_label.setStyleSheet("""
            color: white;
            font-size: 9.5pt;
            font-weight: 500;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        date_layout.addWidget(self.date_label)
        
        right_layout.addWidget(date_container)
        
        # ============================================================
        # CLOCK ICON + TEXT (using clock.svg)
        # ============================================================
        clock_container = QWidget()
        clock_container.setStyleSheet("background: transparent;")
        clock_layout = QHBoxLayout(clock_container)
        clock_layout.setContentsMargins(0, 0, 0, 0)
        clock_layout.setSpacing(6)
        
        # Clock icon (SVG)
        self.clock_icon = QLabel()
        self.clock_icon.setFixedSize(20, 20)
        self.clock_icon.setScaledContents(True)
        self._load_svg_icon(self.clock_icon, "clock", "#ffffff")
        clock_layout.addWidget(self.clock_icon)
        
        # Clock text
        self.menu_bar_clock = QLabel()
        self.menu_bar_clock.setObjectName("menu_bar_clock")
        self.menu_bar_clock.setStyleSheet("""
            color: white;
            font-size: 9.5pt;
            font-weight: 500;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        clock_layout.addWidget(self.menu_bar_clock)
        
        right_layout.addWidget(clock_container)
        
        # Separator
        separator = QLabel("|")
        separator.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 14pt; background: transparent;")
        right_layout.addWidget(separator)
        
        # ============================================================
        # USER ICON + NAME (using person.svg)
        # ============================================================
        user_container = QWidget()
        user_container.setStyleSheet("background: transparent;")
        user_layout = QHBoxLayout(user_container)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(6)
        
        # User icon (SVG)
        self.user_icon = QLabel()
        self.user_icon.setFixedSize(20, 20)
        self.user_icon.setScaledContents(True)
        self._load_svg_icon(self.user_icon, "person", "#ffffff")
        user_layout.addWidget(self.user_icon)
        
        # User name
        self.user_label = QLabel()
        self.user_label.setObjectName("user_label")
        if hasattr(self._parent, 'current_user'):
            self.user_label.setText(f"{self._parent.current_user['username']}")
        self.user_label.setStyleSheet("""
            color: white;
            font-size: 9.5pt;
            font-weight: 500;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        user_layout.addWidget(self.user_label)
        
        right_layout.addWidget(user_container)
        
        layout.addWidget(right_widget)
    
    def _load_svg_icon(self, label, icon_name, color_hex="#ffffff"):
        """Load SVG icon and color it"""
        icon_paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        # Scale to 20x20
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        # Color the icon
                        from PyQt6.QtGui import QPainter, QColor
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        label.setPixmap(colored)
                        return
                except Exception as e:
                    logger.debug(f"Could not load icon {path}: {e}")
        
        # Fallback: use text emoji
        emoji_map = {
            "date": "📅",
            "clock": "🕐",
            "person": "👤",
        }
        label.setText(emoji_map.get(icon_name, ""))
        label.setStyleSheet(f"color: {color_hex}; font-size: 14pt; background: transparent;")
    
    def update_clock(self):
        """Update the clock display with current date and time"""
        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y")
        time_str = now.strftime("%I:%M %p")
        
        # Update date label (without emoji)
        self.date_label.setText(date_str)
        
        # Update clock label (without emoji)
        self.menu_bar_clock.setText(time_str)
    
    def update_theme(self, theme_name):
        """Update header theme"""
        is_dark = is_dark_theme()
        
        if is_dark:
            self.setStyleSheet("""
                QFrame#header {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4752c4, stop:1 #3c45a3);
                    border-bottom: none;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#header {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5865f2, stop:1 #4752c4);
                    border-bottom: none;
                }
            """)
        
        # Update icon colors
        self._load_svg_icon(self.date_icon, "date", "#ffffff")
        self._load_svg_icon(self.clock_icon, "clock", "#ffffff")
        self._load_svg_icon(self.user_icon, "person", "#ffffff")
        self._apply_text_styles()

    def _apply_text_styles(self):
        label_style = """
            color: #ffffff;
            font-size: 9.5pt;
            font-weight: 500;
            background: transparent;
            border: none;
            padding: 0px;
        """
        self.date_label.setStyleSheet(label_style)
        self.menu_bar_clock.setStyleSheet(label_style)
        self.user_label.setStyleSheet(label_style)
    
    def set_shop_logo(self, pixmap):
        """Set shop logo"""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(scaled)
            self.logo_label.setVisible(True)
        else:
            self.logo_label.setVisible(False)
    
    def set_shop_title(self, title):
        """Set shop title"""
        self.title_label.setText(title)
    
    def set_user_name(self, name):
        """Set user name"""
        self.user_label.setText(name)
