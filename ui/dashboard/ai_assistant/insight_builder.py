# ui/dashboard/ai_assistant/insight_builder.py
"""Insight card builder - with SVG icons support"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap

from ui.themes.theme_manager import get_theme_colors
from .utils import get_themed_icon_helper, get_emoji_fallback, get_insight_icon_name
from .styles import get_insight_card_style, get_error_card_style, get_section_header_style


class InsightBuilder:
    """Builds insight cards with theme awareness and SVG icons"""
    
    def __init__(self, is_dark):
        self._is_dark = is_dark
    
    def create_insight_card(self, icon_name, text, color, details=None, 
                           category=None, trend=None, content_layout=None):
        """Create and add an insight card with SVG icon"""
        colors = get_insight_card_style(self._is_dark, color)
        
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border_color']};
                border-radius: 8px;
                padding: 0px;
            }}
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(2)
        
        # Main row
        main_row = QHBoxLayout()
        main_row.setSpacing(10)
        
        # ✅ Icon - Use SVG with fallback to emoji
        icon_label = QLabel()
        icon_label.setFixedSize(22, 22)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Get actual SVG icon name
        svg_icon_name = get_insight_icon_name(icon_name)
        
        # Try to load SVG icon
        icon_pixmap = get_themed_icon_helper(svg_icon_name, 20, self._is_dark)
        
        if icon_pixmap:
            icon_label.setPixmap(icon_pixmap)
            icon_label.setStyleSheet("background: transparent; border: none;")
        else:
            # Fallback to emoji
            icon_label.setText(get_emoji_fallback(icon_name))
            icon_label.setStyleSheet(f"""
                font-size: 16px;
                color: {color};
                background: transparent;
                border: none;
            """)
        main_row.addWidget(icon_label)
        
        # Text
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"""
            color: {colors['text_color']};
            font-size: 10pt;
            font-weight: 500;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        main_row.addWidget(text_label)
        
        # Trend indicator
        if trend:
            trend_label = QLabel(trend)
            trend_label.setStyleSheet(f"""
                font-size: 8pt;
                font-weight: 600;
                color: {color};
                background: transparent;
                border: none;
            """)
            main_row.addWidget(trend_label)
        
        # Category tag
        if category:
            tag_label = QLabel(category)
            tag_label.setStyleSheet(f"""
                background-color: {colors['tag_bg']};
                color: {colors['tag_color']};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 7pt;
                font-weight: 600;
            """)
            main_row.addWidget(tag_label)
        
        main_row.addStretch()
        container_layout.addLayout(main_row)
        
        # Details
        if details:
            detail_label = QLabel(details)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet(f"""
                color: {colors['detail_color']};
                font-size: 8.5pt;
                font-weight: 400;
                background: transparent;
                border: none;
                padding-left: 32px;
            """)
            container_layout.addWidget(detail_label)
        
        if content_layout:
            content_layout.insertWidget(content_layout.count() - 1, container)
        
        return container

    def create_section_header(self, title, icon="📌", content_layout=None):
        """Create a section header with optional icon"""
        from .styles import get_section_header_style
        
        # Try to use SVG icon for section header
        icon_label = ""
        if icon and icon != "📌":
            svg_icon_name = get_insight_icon_name(icon)
            icon_pixmap = get_themed_icon_helper(svg_icon_name, 16, self._is_dark)
            if icon_pixmap:
                # Use QLabel with pixmap for icon
                header_widget = QWidget()
                header_layout = QHBoxLayout(header_widget)
                header_layout.setContentsMargins(0, 0, 0, 0)
                header_layout.setSpacing(6)
                
                icon_label_widget = QLabel()
                icon_label_widget.setPixmap(icon_pixmap)
                icon_label_widget.setFixedSize(18, 18)
                header_layout.addWidget(icon_label_widget)
                
                text_label = QLabel(title)
                text_label.setStyleSheet(get_section_header_style(self._is_dark))
                header_layout.addWidget(text_label)
                
                header_layout.addStretch()
                
                if content_layout:
                    content_layout.insertWidget(content_layout.count() - 1, header_widget)
                return header_widget
        
        # Fallback to emoji
        header = QLabel(f"{icon} {title}")
        header.setStyleSheet(get_section_header_style(self._is_dark))
        
        if content_layout:
            content_layout.insertWidget(content_layout.count() - 1, header)
        
        return header

    def create_error_card(self, message, content_layout=None):
        """Create an error card"""
        colors = get_error_card_style(self._is_dark)
        
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {colors['bg']};
                border-radius: 8px;
                border: 1px solid {colors['border']};
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        
        # Try to use warning icon
        icon_pixmap = get_themed_icon_helper("warning", 20, self._is_dark)
        
        error_layout = QHBoxLayout()
        error_layout.setSpacing(10)
        
        if icon_pixmap:
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap)
            icon_label.setFixedSize(22, 22)
            error_layout.addWidget(icon_label)
        else:
            error_label_icon = QLabel("⚠️")
            error_label_icon.setStyleSheet("font-size: 16px;")
            error_layout.addWidget(error_label_icon)
        
        error_label = QLabel(message)
        error_label.setWordWrap(True)
        error_label.setStyleSheet(f"""
            color: {colors['text']};
            font-size: 10pt;
            background: transparent;
            border: none;
        """)
        error_layout.addWidget(error_label)
        error_layout.addStretch()
        
        container_layout.addLayout(error_layout)
        
        if content_layout:
            content_layout.insertWidget(content_layout.count() - 1, container)
        
        return container