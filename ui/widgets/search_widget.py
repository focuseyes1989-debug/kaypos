# ui/widgets/search_widget.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import QEvent

from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme, get_icon_path
import os


class ModernSearchWidget(QWidget):
    """Modern search widget - Static size (no animation) - Theme-aware"""
    
    search_changed = pyqtSignal(str)
    search_cleared = pyqtSignal()
    search_focused = pyqtSignal()
    search_unfocused = pyqtSignal()
    
    def __init__(self, placeholder="Search...", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self._is_dark = is_dark_theme()
        self._icon_pixmap = None
        self._clear_icon_pixmap = None
        self._is_clear_hovered = False
        
        self.setup_ui()
        self.apply_modern_style()
        
        self.setFixedHeight(38)
        
        # ✅ Connect theme change signal
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change - update styles and icon"""
        self._is_dark = is_dark_theme()
        self.apply_modern_style()
        self._update_icon_color()
        self._update_clear_icon_color()
    
    def _load_svg_icon(self):
        """Load SVG icon from assets/icons folder using theme_manager"""
        try:
            from ui.themes.theme_manager import get_icon_path, get_icon_with_color
            
            # ✅ Use theme_manager to get icon path
            icon_path = get_icon_path("search")
            
            if icon_path and os.path.exists(icon_path):
                try:
                    from PyQt6.QtSvg import QSvgRenderer
                    from PyQt6.QtGui import QPixmap, QPainter
                    from PyQt6.QtCore import QByteArray
                    
                    with open(icon_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    
                    # Create pixmap from SVG
                    renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
                    if renderer.isValid():
                        pixmap = QPixmap(16, 16)
                        pixmap.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(pixmap)
                        renderer.render(painter)
                        painter.end()
                        self._icon_pixmap = pixmap
                        return
                except Exception as e:
                    print(f"Could not load SVG search icon: {e}")
            
            # Fallback: Try PNG
            icon_paths = [
                "assets/icons/search.png",
            ]
            for path in icon_paths:
                if os.path.exists(path):
                    try:
                        pixmap = QPixmap(path)
                        if not pixmap.isNull():
                            self._icon_pixmap = pixmap.scaled(
                                16, 16,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            )
                            return
                    except Exception as e:
                        print(f"Could not load icon {path}: {e}")
            
            self._icon_pixmap = None
            
        except Exception as e:
            print(f"Error loading search icon: {e}")
            self._icon_pixmap = None
    
    def _load_clear_icon(self):
        """Load clear icon from assets/icons folder using theme_manager"""
        try:
            from ui.themes.theme_manager import get_icon_path
            
            # ✅ Use theme_manager to get icon path
            icon_path = get_icon_path("close")
            
            if icon_path and os.path.exists(icon_path):
                try:
                    from PyQt6.QtSvg import QSvgRenderer
                    from PyQt6.QtCore import QByteArray
                    
                    with open(icon_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    
                    renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
                    if renderer.isValid():
                        pixmap = QPixmap(14, 14)
                        pixmap.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(pixmap)
                        renderer.render(painter)
                        painter.end()
                        self._clear_icon_pixmap = pixmap
                        return
                except Exception as e:
                    print(f"Could not load SVG clear icon: {e}")
            
            # Fallback: Try PNG
            icon_paths = [
                "assets/icons/close.png",
            ]
            for path in icon_paths:
                if os.path.exists(path):
                    try:
                        pixmap = QPixmap(path)
                        if not pixmap.isNull():
                            self._clear_icon_pixmap = pixmap.scaled(
                                14, 14,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            )
                            return
                    except Exception as e:
                        print(f"Could not load icon {path}: {e}")
            
            self._clear_icon_pixmap = None
            
        except Exception as e:
            print(f"Error loading clear icon: {e}")
            self._clear_icon_pixmap = None
    
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
            print(f"Could not color icon: {e}")
            return source_pixmap
    
    def _update_icon_color(self):
        """Update search icon color based on theme"""
        if not self._icon_pixmap:
            return
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if self.search_input.hasFocus():
            icon_color = colors['icon_active']
        else:
            icon_color = colors['text_secondary']
        
        colored_pixmap = self._create_colored_pixmap(self._icon_pixmap, icon_color)
        if colored_pixmap:
            self.icon_label.setPixmap(colored_pixmap)
            self.icon_label.setStyleSheet("""
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            """)
    
    def _update_clear_icon_color(self):
        """Update clear icon color based on theme and hover state"""
        if not self._clear_icon_pixmap:
            return
        
        is_dark = is_dark_theme()
        
        if self._is_clear_hovered:
            icon_color = "#ed4245" if is_dark else "#dc3545"
        else:
            icon_color = "#72767d" if is_dark else "#6c757d"
        
        colored_pixmap = self._create_colored_pixmap(self._clear_icon_pixmap, icon_color)
        if colored_pixmap:
            self.clear_btn.setPixmap(colored_pixmap)
            self.clear_btn.setStyleSheet("""
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            """)
    
    def setup_ui(self):
        """Setup the UI components"""
        # Load SVG icons
        self._load_svg_icon()
        self._load_clear_icon()
        
        # Main layout
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Container widget for the search bar
        self.container = QWidget()
        self.container.setObjectName("searchContainer")
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(8, 2, 8, 2)
        container_layout.setSpacing(4)
        
        # Search icon
        self.icon_label = QLabel()
        self.icon_label.setObjectName("searchIcon")
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("""
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        """)
        
        # Set initial search icon
        if self._icon_pixmap:
            colors = get_theme_colors()
            is_dark = is_dark_theme()
            icon_color = "#72767d" if is_dark else "#6c757d"
            colored_pixmap = self._create_colored_pixmap(self._icon_pixmap, icon_color)
            if colored_pixmap:
                self.icon_label.setPixmap(colored_pixmap)
        else:
            self.icon_label.setText("🔍")
            self.icon_label.setStyleSheet("""
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                color: #6c757d;
            """)
        
        container_layout.addWidget(self.icon_label)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText(self.placeholder)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        self.search_input.installEventFilter(self)
        container_layout.addWidget(self.search_input, 1)
        
        # Clear button
        self.clear_btn = QLabel()
        self.clear_btn.setObjectName("clearButton")
        self.clear_btn.setFixedSize(18, 18)
        self.clear_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.mousePressEvent = self._on_clear_clicked
        self.clear_btn.enterEvent = self._on_clear_enter
        self.clear_btn.leaveEvent = self._on_clear_leave
        self.clear_btn.hide()
        
        # Set initial clear icon
        if self._clear_icon_pixmap:
            is_dark = is_dark_theme()
            icon_color = "#72767d" if is_dark else "#6c757d"
            colored_pixmap = self._create_colored_pixmap(self._clear_icon_pixmap, icon_color)
            if colored_pixmap:
                self.clear_btn.setPixmap(colored_pixmap)
                self.clear_btn.setStyleSheet("""
                    background: transparent;
                    border: none;
                    padding: 0px;
                    margin: 0px;
                """)
        else:
            self.clear_btn.setText("✕")
            self.clear_btn.setStyleSheet("""
                font-size: 12px;
                font-weight: 300;
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                color: #6c757d;
            """)
        
        container_layout.addWidget(self.clear_btn)
        
        self.container.setLayout(container_layout)
        layout.addWidget(self.container)
        
        self.setLayout(layout)
        
        # ✅ Fixed width - no animation
        self.setFixedWidth(250)
    
    def _on_clear_enter(self, event):
        """Handle mouse enter on clear button"""
        self._is_clear_hovered = True
        self._update_clear_icon_color()
    
    def _on_clear_leave(self, event):
        """Handle mouse leave on clear button"""
        self._is_clear_hovered = False
        self._update_clear_icon_color()
    
    def _on_clear_clicked(self, event):
        """Handle clear button click"""
        self.clear_search()
    
    def apply_modern_style(self):
        """Apply modern style with theme awareness"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            bg_color = colors['input_bg']
            bg_hover = colors['card_hover']
            bg_focus = colors['input_bg']
            border_color = colors['input_border']
            border_hover = colors['border_hover']
            border_focus = colors['border_hover']
            text_color = colors['text']
            placeholder_color = colors['text_secondary']
            shadow_color = "rgba(88, 101, 242, 0.25)"
        else:
            bg_color = "#f8f9fa"
            bg_hover = "#ffffff"
            bg_focus = "#ffffff"
            border_color = "#ced4da"
            border_hover = "#adb5bd"
            border_focus = colors['border_hover']
            text_color = "#212529"
            placeholder_color = "#6c757d"
            shadow_color = "rgba(88, 101, 242, 0.15)"
        
        self.setStyleSheet(f"""
            /* Container styling */
            #searchContainer {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 0px;
                height: 36px;
            }}
            
            #searchContainer:hover {{
                border-color: {border_hover};
            }}
            
            #searchContainer:focus-within {{
                background-color: {bg_focus};
                border-color: {border_focus};
            }}
            
            /* Search input */
            #searchInput {{
                background: transparent;
                border: none;
                padding: 2px 4px;
                font-size: 12px;
                color: {text_color};
                font-weight: 400;
                outline: none;
                height: 28px;
            }}
            
            #searchInput::placeholder {{
                color: {placeholder_color};
                font-weight: 300;
            }}
            
            /* Search icon */
            #searchIcon {{
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }}
            
            /* Clear button */
            #clearButton {{
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }}
        """)
        
        # Update icons after style change
        self._update_icon_color()
        self._update_clear_icon_color()
    
    def _on_text_changed(self, text):
        """Handle text changes"""
        self.search_changed.emit(text)
        
        if text:
            self.clear_btn.show()
            self._update_clear_icon_color()
        else:
            self.clear_btn.hide()
    
    def _on_return_pressed(self):
        """Handle Enter key press"""
        text = self.search_input.text().strip()
        if text:
            self.search_changed.emit(text)
    
    def clear_search(self):
        """Clear search"""
        self.search_input.clear()
        self.search_cleared.emit()
    
    def get_text(self):
        """Get current search text"""
        return self.search_input.text().strip()
    
    def set_text(self, text):
        """Set search text programmatically"""
        self.search_input.setText(text)
        if text:
            self.clear_btn.show()
            self._update_clear_icon_color()
    
    def focus_search(self):
        """Programmatically focus the search bar"""
        self.search_input.setFocus()
    
    def retranslateUi(self, lang_code):
        """Update language"""
        if lang_code == "my":
            self.search_input.setPlaceholderText("ရှာရန်...")
        else:
            self.search_input.setPlaceholderText(self.placeholder)
    
    def set_placeholder_text(self, text):
        """Set placeholder text"""
        self.placeholder = text
        self.search_input.setPlaceholderText(text)
    
    def eventFilter(self, obj, event):
        """Handle focus events for icon color"""
        if obj == self.search_input:
            if event.type() == QEvent.Type.FocusIn:
                self.search_focused.emit()
                self._update_icon_color()
            elif event.type() == QEvent.Type.FocusOut:
                self.search_unfocused.emit()
                self._update_icon_color()
        return super().eventFilter(obj, event)


# Keep backward compatibility with original SearchWidget name
class SearchWidget(ModernSearchWidget):
    """Backward compatible search widget"""
    
    def __init__(self, placeholder="Search...", show_label=False, parent=None):
        super().__init__(placeholder, parent)
