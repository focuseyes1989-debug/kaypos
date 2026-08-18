# ui/ai_pages/ai_chat_widgets.py
"""
Custom widgets for AI Chat Room
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from ui.widgets.modern_button import ModernButton
from ui.ai_pages.ai_chat_visuals import AIResultVisual
import os


class CopyableMessageFrame(QFrame):
    """Frame with copy functionality for messages"""
    
    def __init__(self, text, is_user=False, parent=None, timestamp=None, action_text=None, action_callback=None, actions=None, visual_spec=None, utility_actions=None):
        super().__init__(parent)
        self._text = text
        self.is_user = is_user
        self.timestamp = timestamp
        self.action_text = action_text
        self.action_callback = action_callback
        self.actions = list(actions or [])[:4]
        self.visual_spec = visual_spec
        self.utility_actions = list(utility_actions or [])[:4]
        self._setup_ui()
    
    def _setup_ui(self):
        colors = get_theme_colors()
        
        if self.is_user:
            bg_color = "#5865f2"
            text_color = "white"
            # User message - ကျစ်ကျစ်လစ်လစ်ဖြစ်အောင်
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 16px;
                    padding: 8px 14px;
                    max-width: 500px;
                }}
            """)
        else:
            bg_color = colors.get('card_bg', '#f0f0f0')
            text_color = colors.get('text', '#2d3436')
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 12px;
                    padding: 12px 16px;
                }}
            """)
        
        layout = QVBoxLayout(self)
        if self.is_user:
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(0)
        else:
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)
        
        # Message text
        self.text_label = QLabel(self._text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        if self.is_user:
            self.text_label.setStyleSheet(f"""
                color: {text_color};
                font-size: 10.5pt;
                background: transparent;
                padding: 0px;
                line-height: 1.3;
            """)
        else:
            self.text_label.setStyleSheet(f"""
                color: {text_color};
                font-size: 11pt;
                background: transparent;
            """)
        layout.addWidget(self.text_label)

        if not self.is_user and self.visual_spec:
            self.result_visual=AIResultVisual(self.visual_spec,self)
            layout.addWidget(self.result_visual)

        if not self.is_user and self.utility_actions:
            utility_row=QHBoxLayout();utility_row.setContentsMargins(0,2,0,0);utility_row.setSpacing(6)
            utility_row.addWidget(QLabel("Result:"))
            for label,callback in self.utility_actions:
                button=ModernButton(str(label),ModernButton.TERTIARY);button.set_compact(True);button.setFixedHeight(28)
                button.setCursor(Qt.CursorShape.PointingHandCursor);button.clicked.connect(callback);utility_row.addWidget(button)
            utility_row.addStretch();layout.addLayout(utility_row)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        has_footer = False

        available_actions=list(self.actions)
        if self.action_text and self.action_callback:
            available_actions.insert(0,(self.action_text,self.action_callback))
        if not self.is_user:
            for action in available_actions[:4]:
                if isinstance(action,dict):
                    label,callback=action.get("label"),action.get("callback")
                else:
                    label,callback=action
                if not label or not callback:
                    continue
                action_btn=ModernButton(str(label),ModernButton.SECONDARY)
                action_btn.setCheckable(False);action_btn.setAutoExclusive(False);action_btn.setFixedHeight(30)
                action_btn.setCursor(Qt.CursorShape.PointingHandCursor);action_btn.clicked.connect(callback)
                footer_layout.addWidget(action_btn,alignment=Qt.AlignmentFlag.AlignVCenter)
                has_footer=True

        footer_layout.addStretch()

        if self.timestamp:
            time_label = QLabel(self.timestamp)
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            time_label.setStyleSheet(f"""
                color: {'rgba(255, 255, 255, 0.78)' if self.is_user else colors.get('text_secondary', '#636e72')};
                font-size: 8pt;
                background: transparent;
            """)
            footer_layout.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignVCenter)
            has_footer = True

        if not self.is_user:
            copy_btn = ModernButton("Copy", ModernButton.TERTIARY)
            copy_btn.set_compact(True)
            copy_btn.setFixedHeight(30)

            copy_icon = self._load_copy_icon()
            if not copy_icon.isNull():
                copy_btn.set_custom_icon(copy_icon, size=(14, 14))
                copy_btn.setText("")
            else:
                copy_btn.setText("Copy")

            copy_btn.setToolTip("Copy response")
            copy_btn.set_chatgpt_style(True)
            copy_btn.setFixedSize(30, 28)
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.clicked.connect(self._copy_text)
            footer_layout.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            has_footer = True

        if has_footer:
            layout.addLayout(footer_layout)
        return

        if self.timestamp:
            time_label = QLabel(self.timestamp)
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            time_label.setStyleSheet(f"""
                color: {'rgba(255, 255, 255, 0.78)' if self.is_user else colors.get('text_secondary', '#636e72')};
                font-size: 8pt;
                background: transparent;
            """)
            layout.addWidget(time_label)

        if not self.is_user and self.action_text and self.action_callback:
            action_btn = ModernButton(self.action_text, ModernButton.SECONDARY)
            action_btn.setCheckable(False)
            action_btn.setAutoExclusive(False)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.clicked.connect(self.action_callback)
            layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Copy button - only for bot messages
        if not self.is_user:
            copy_btn = ModernButton("Copy", ModernButton.TERTIARY)
            copy_btn.set_compact(True)
            
            # ✅ Set SVG icon from assets/icons/file_copy.svg
            copy_icon = self._load_copy_icon()
            if not copy_icon.isNull():
                copy_btn.set_custom_icon(copy_icon, size=(14, 14))
            else:
                # Fallback to emoji if SVG not found
                copy_btn.setText("📋 Copy")
            
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.clicked.connect(self._copy_text)
            layout.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignRight)
    
    def _load_copy_icon(self, size=14):
        """
        Load file_copy.svg icon with theme color
        
        Args:
            size: Icon size in pixels
        
        Returns:
            QIcon: Colored icon
        """
        # Try SVG first
        svg_path = "assets/icons/file_copy.svg"
        png_path = "assets/icons/file_copy.png"
        
        icon_path = None
        if os.path.exists(svg_path):
            icon_path = svg_path
        elif os.path.exists(png_path):
            icon_path = png_path
        else:
            return QIcon()
        
        try:
            pixmap = QPixmap(icon_path)
            if pixmap.isNull():
                return QIcon()
            
            # Scale to desired size
            scaled = pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Get theme color for icon
            is_dark = is_dark_theme()
            color_hex = "#b9bbbe" if is_dark else "#6c757d"
            
            # Colorize the icon
            colored = scaled.copy()
            painter = QPainter(colored)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(colored.rect(), QColor(color_hex))
            painter.end()
            
            return QIcon(colored)
            
        except Exception as e:
            print(f"Could not load copy icon: {e}")
            return QIcon()
    
    def _copy_text(self):
        """Copy message text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._text)

    def update_theme(self):
        colors = get_theme_colors()

        if self.is_user:
            self.setStyleSheet("""
                QFrame {
                    background-color: #5865f2;
                    border-radius: 16px;
                    padding: 8px 14px;
                    max-width: 500px;
                }
            """)
            self.text_label.setStyleSheet("""
                color: white;
                font-size: 10.5pt;
                background: transparent;
                padding: 0px;
                line-height: 1.3;
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.get('card_bg', '#f0f0f0')};
                    border-radius: 12px;
                    padding: 12px 16px;
                }}
            """)
            self.text_label.setStyleSheet(f"""
                color: {colors.get('text', '#2d3436')};
                font-size: 11pt;
                background: transparent;
            """)

        for label in self.findChildren(QLabel):
            if label is self.text_label:
                continue
            label.setStyleSheet(f"""
                color: {'rgba(255, 255, 255, 0.78)' if self.is_user else colors.get('text_secondary', '#636e72')};
                font-size: 8pt;
                background: transparent;
            """)

        for button in self.findChildren(ModernButton):
            button.update_theme()
        if hasattr(self,"result_visual"):
            self.result_visual.update_theme()
    
    def get_text(self):
        return self._text
