# ui/main_window/sidebar.py
"""
Main Window Sidebar - Menu Bar Style
Clean, minimal sidebar with menu bar-like button styling
Collapsed width increased for better icon visibility
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy,
    QPushButton, QWidget, QSpacerItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from ui.main_window.modern_button import ModernButton
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from utils.translations import tr
from utils.permissions import PermissionManager
from loguru import logger


class Sidebar(QFrame):
    """Main Window Sidebar - Menu Bar Style with Collapsible Support"""
    
    # Sidebar width constants - Collapsed width increased
    WIDTH_EXPANDED = 260
    WIDTH_COLLAPSED = 84
    NAV_HEIGHT_EXPANDED = 34
    NAV_HEIGHT_COLLAPSED = 40
    NAV_ICON_EXPANDED = 18
    NAV_ICON_COLLAPSED = 18
    
    collapse_state_changed = pyqtSignal(bool)  # True = Collapsed, False = Expanded
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self.sidebar_buttons = []
        self.version_label = None
        self.logout_btn = None
        self._is_collapsed = False
        self._is_dark = is_dark_theme()
        user = getattr(parent, "current_user", {}) or {}
        self._display_name = str(user.get("username") or user.get("name") or "Admin")
        self._display_subtitle = str(user.get("role") or user.get("email") or "ZAY POS")
        self.profile_text_container = None
        self.avatar_label = None
        self.profile_name_label = None
        self.profile_subtitle_label = None
        self.collapse_layout = None
        self.theme_toggle_container = None
        self.theme_light_btn = None
        self.theme_dark_btn = None
        
        # Set initial width to expanded.
        self.setMinimumWidth(self.WIDTH_EXPANDED)
        self.setMaximumWidth(self.WIDTH_EXPANDED)
        
        self._setup_ui()
        self._update_ui_elements()
        
        QTimer.singleShot(0, lambda: self.collapse_state_changed.emit(False))
    
    def _setup_ui(self) -> None:
        colors = get_theme_colors()
        is_dark = getattr(self, '_is_dark', True)
        
        # Menu bar style colors
        if is_dark:
            bg_color = "#2f3136"
            border_color = "#40444b"
            text_secondary = "#949ba4"
            header_color = "#72767d"
            hover_color = "#40444b"
            selected_color = "#40444b"
            text_color = "#dcddde"
            text_selected = "#ffffff"
        else:
            bg_color = "#f8f9fa"
            border_color = "#e9ecef"
            text_secondary = "#6c757d"
            header_color = "#6c757d"
            hover_color = "#e9ecef"
            selected_color = "#e9ecef"
            text_color = "#212529"
            text_selected = "#212529"
        
        self.setObjectName("sidebar")
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {bg_color};
                border-right: 1px solid {border_color};
            }}
            QFrame#sidebar QLabel {{
                background: transparent;
            }}
        """)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 18, 14, 18)
        self.main_layout.setSpacing(0)
        
        # ============ HEADER SECTION ============
        self.header_container = QWidget()
        self.header_container.setStyleSheet("background: transparent;")
        self.header_layout = QVBoxLayout(self.header_container)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(14)
        
        self.profile_row = QWidget()
        self.profile_row.setObjectName("sidebarProfile")
        profile_layout = QHBoxLayout(self.profile_row)
        profile_layout.setContentsMargins(2, 0, 2, 0)
        profile_layout.setSpacing(12)

        initial = (self._display_name[:1] or "U").upper()
        self.avatar_label = QLabel(initial)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setFixedSize(44, 44)
        profile_layout.addWidget(self.avatar_label)

        self.profile_text_container = QWidget()
        profile_text_layout = QVBoxLayout(self.profile_text_container)
        profile_text_layout.setContentsMargins(0, 0, 0, 0)
        profile_text_layout.setSpacing(1)
        self.profile_name_label = QLabel(self._display_name)
        self.profile_subtitle_label = QLabel(self._display_subtitle)
        self.profile_name_label.setObjectName("sidebarProfileName")
        self.profile_subtitle_label.setObjectName("sidebarProfileSubtitle")
        profile_text_layout.addWidget(self.profile_name_label)
        profile_text_layout.addWidget(self.profile_subtitle_label)
        profile_layout.addWidget(self.profile_text_container, 1)
        self.header_layout.addWidget(self.profile_row)
        
        # Divider line - Menu bar style
        self.header_divider = QFrame()
        self.header_divider.setFixedHeight(1)
        self.header_divider.setStyleSheet(f"background-color: {border_color}; margin: 4px 4px 8px 4px;")
        self.header_layout.addWidget(self.header_divider)
        
        self.header_container.setVisible(False)
        self.main_layout.addWidget(self.header_container)
        
        # ============ NAVIGATION SECTION ============
        self.nav_container = QWidget()
        self.nav_container.setStyleSheet("background: transparent;")
        self.nav_layout = QVBoxLayout(self.nav_container)
        self.nav_layout.setContentsMargins(0, 0, 0, 0)
        self.nav_layout.setSpacing(3)
        
        # Create navigation buttons (Menu bar style)
        self._create_sidebar_buttons()
        
        for btn in self.sidebar_buttons:
            self.nav_layout.addWidget(btn)
        
        # ============ COLLAPSE BUTTON (Below Page Buttons) ============
        self.nav_layout.addStretch()
        
        # Collapse button container
        self.collapse_container = QWidget()
        self.collapse_container.setStyleSheet("background: transparent;")
        self.collapse_layout = QVBoxLayout(self.collapse_container)
        self.collapse_layout.setContentsMargins(0, 8, 0, 8)
        self.collapse_layout.setSpacing(0)
        
        # Collapse divider
        self.collapse_divider = QFrame()
        self.collapse_divider.setFixedHeight(1)
        self.collapse_divider.setStyleSheet(f"background-color: {border_color}; margin: 4px 4px 4px 4px;")
        self.collapse_layout.addWidget(self.collapse_divider)
        
        # Collapse button - uses assets/icons and follows the same [icon] label pattern.
        self.collapse_btn = ModernButton("Collapse", style=ModernButton.SECONDARY)
        self.collapse_btn.set_icon("arrow_circle_left", size=(20, 20))
        self.collapse_btn.setCheckable(False)
        self.collapse_btn.setAutoExclusive(False)
        self.collapse_btn.setFixedHeight(42)
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {text_secondary};
                border: none;
                border-radius: 10px;
                font-size: 10.5pt;
                padding: 9px 12px;
                margin: 1px 0px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: {text_color};
            }}
        """)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        self.collapse_layout.addWidget(self.collapse_btn)
        
        self.nav_layout.addWidget(self.collapse_container)
        
        self.main_layout.addWidget(self.nav_container)
        
        # ============ BOTTOM SECTION ============
        self.bottom_container = QWidget()
        self.bottom_container.setStyleSheet("background: transparent;")
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(10)
        
        # Bottom divider
        self.bottom_divider = QFrame()
        self.bottom_divider.setFixedHeight(1)
        self.bottom_divider.setStyleSheet(f"background-color: {border_color}; margin: 4px 4px 4px 4px;")
        self.bottom_layout.addWidget(self.bottom_divider)

        self.theme_toggle_container = QWidget()
        self.theme_toggle_container.setObjectName("themeToggle")
        theme_toggle_layout = QHBoxLayout(self.theme_toggle_container)
        theme_toggle_layout.setContentsMargins(2, 2, 2, 2)
        theme_toggle_layout.setSpacing(1)
        self.theme_light_btn = QPushButton("Light")
        self.theme_dark_btn = QPushButton("Dark")
        self.theme_light_btn.setObjectName("themeLightButton")
        self.theme_dark_btn.setObjectName("themeDarkButton")
        self.theme_light_btn.setCheckable(True)
        self.theme_dark_btn.setCheckable(True)
        self.theme_light_btn.setToolTip("Light theme")
        self.theme_dark_btn.setToolTip("Dark theme")
        self.theme_light_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_dark_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_light_btn.clicked.connect(lambda: self._set_sidebar_theme("Light"))
        self.theme_dark_btn.clicked.connect(lambda: self._set_sidebar_theme("Dark"))
        theme_toggle_layout.addWidget(self.theme_light_btn)
        theme_toggle_layout.addWidget(self.theme_dark_btn)
        self.bottom_layout.addWidget(self.theme_toggle_container)
        
        # Logout button - Menu bar style
        self.logout_btn = ModernButton(tr("logout") or "Logout", style=ModernButton.SECONDARY)
        self.logout_btn.set_icon("logout", size=(20, 20))  # Slightly larger icon
        self.logout_btn.clicked.connect(self._on_logout_clicked)
        
        self.logout_btn.setStyleSheet(self.logout_btn.styleSheet() + f"""
            QPushButton {{
                text-align: left;
                padding: 6px 10px 6px 10px;
                margin: 2px 0px 2px 0px;
                border: none;
                border-radius: 4px;
                font-weight: 400;
                color: {text_color};
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """)
        self.bottom_layout.addWidget(self.logout_btn)
        
        # Version label
        self.version_label = QLabel()
        self.version_label.setObjectName("version_label")
        self.version_label.setStyleSheet(f"""
            color: {text_secondary};
            font-size: 8pt;
            padding: 4px 8px 2px 8px;
            background: transparent;
        """)
        self._update_version_label()
        self.bottom_layout.addWidget(self.version_label)
        
        self.main_layout.addWidget(self.bottom_container)
    
    def _apply_collapsed_state(self) -> None:
        """Apply collapsed state - Menu bar style with centered icons"""
        for btn in self.sidebar_buttons:
            btn.setText("")
        
        # Update collapse button
        if hasattr(self, 'collapse_btn') and self.collapse_btn:
            self.collapse_btn.setText("")
            self.collapse_btn.set_icon("arrow_circle_right", size=(20, 20))
        
        # Hide version label when collapsed
        if self.version_label:
            self.version_label.setVisible(False)
        
        # Update logout button - collapsed state with centered icon
        if self.logout_btn:
            self.logout_btn.setText("")
        self._apply_modern_styles()
        
        self.update()
    
    def _palette(self) -> dict:
        if self._is_dark:
            return {
                "bg": "#24272c", "border": "#3a3f46", "muted": "#8d949e",
                "text": "#e6e8eb", "hover": "#30343a", "selected": "#353a42",
                "selected_text": "#ffffff", "toggle": "#2e3238", "avatar": "#343941",
            }
        return {
            "bg": "#fbfbfc", "border": "#dfe3e8", "muted": "#6d747d",
            "text": "#30343a", "hover": "#eef1f4", "selected": "#e9edf2",
            "selected_text": "#1f242a", "toggle": "#edf0f4", "avatar": "#eef1f5",
        }

    def _nav_button_style(self, collapsed: bool = False) -> str:
        p = self._palette()
        pad = "0px" if collapsed else "0px 10px 0px 10px"
        align = "center" if collapsed else "left"
        margin = "0px" if collapsed else "0px"
        radius = "12px" if collapsed else "10px"
        min_height = f"{self.NAV_HEIGHT_COLLAPSED}px" if collapsed else f"{self.NAV_HEIGHT_EXPANDED}px"
        width_rules = f"min-width: {self.NAV_HEIGHT_COLLAPSED}px; max-width: {self.NAV_HEIGHT_COLLAPSED}px;" if collapsed else "min-width: 0px;"
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {p['muted']};
                border: none;
                border-radius: {radius};
                text-align: {align};
                padding: {pad};
                margin: {margin};
                font-size: {10.5 if collapsed else 9.5}pt;
                font-weight: 500;
                min-height: {min_height};
                max-height: {min_height};
                {width_rules}
            }}
            QPushButton::icon {{
                margin-left: 0px;
                margin-right: {0 if collapsed else 8}px;
            }}
            QPushButton:hover {{
                background-color: {p['hover']};
                color: {p['text']};
                border-radius: {radius};
            }}
            QPushButton:checked {{
                background-color: {p['selected']};
                color: {p['selected_text']};
                border-radius: {radius};
                font-weight: 600;
            }}
            QPushButton:checked:hover {{
                background-color: {p['selected']};
                color: {p['selected_text']};
                border-radius: {radius};
            }}
            QPushButton:pressed {{
                background-color: {p['selected']};
                border-radius: {radius};
            }}
        """

    def _apply_button_metrics(self, btn: QPushButton, collapsed: bool) -> None:
        icon_size = self.NAV_ICON_COLLAPSED if collapsed else self.NAV_ICON_EXPANDED
        btn.setIconSize(QSize(icon_size, icon_size))
        if collapsed:
            btn.setFixedSize(self.NAV_HEIGHT_COLLAPSED, self.NAV_HEIGHT_COLLAPSED)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return
        btn.setFixedHeight(self.NAV_HEIGHT_EXPANDED)
        btn.setMinimumHeight(self.NAV_HEIGHT_EXPANDED)
        btn.setMaximumHeight(self.NAV_HEIGHT_EXPANDED)
        btn.setMinimumWidth(0)
        btn.setMaximumWidth(16777215)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _apply_modern_styles(self) -> None:
        p = self._palette()
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {p['bg']};
                border-right: 1px solid {p['border']};
            }}
            QFrame#sidebar QLabel {{
                background: transparent;
            }}
        """)

        if self.avatar_label:
            size = 38 if self._is_collapsed else 44
            self.avatar_label.setFixedSize(size, size)
            self.avatar_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {p['avatar']};
                    color: {p['text']};
                    border: 1px solid {p['border']};
                    border-radius: {size // 2}px;
                    font-size: 13pt;
                    font-weight: 700;
                }}
            """)
        if self.profile_name_label:
            self.profile_name_label.setStyleSheet(f"color: {p['text']}; font-size: 10.5pt; font-weight: 700;")
        if self.profile_subtitle_label:
            self.profile_subtitle_label.setStyleSheet(f"color: {p['muted']}; font-size: 8.5pt;")
        if self.profile_text_container:
            self.profile_text_container.setVisible(not self._is_collapsed)

        for divider_name in ("header_divider", "collapse_divider", "bottom_divider"):
            divider = getattr(self, divider_name, None)
            if divider:
                divider.setStyleSheet(f"background-color: {p['border']}; margin: 6px 4px;")

        collapsed = self._is_collapsed
        if hasattr(self, "nav_layout") and self.nav_layout:
            self.nav_layout.setContentsMargins(0, 0, 0, 0)
            self.nav_layout.setSpacing(3)
        if hasattr(self, "bottom_layout") and self.bottom_layout:
            self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        for btn in self.sidebar_buttons:
            self._apply_button_metrics(btn, collapsed)
            btn.setStyleSheet(self._nav_button_style(collapsed))
            if hasattr(self, "nav_layout") and self.nav_layout:
                self.nav_layout.setAlignment(
                    btn,
                    Qt.AlignmentFlag.AlignHCenter if collapsed else Qt.AlignmentFlag(0),
                )
        if self.logout_btn:
            self._apply_button_metrics(self.logout_btn, collapsed)
            self.logout_btn.setStyleSheet(self._nav_button_style(collapsed))
            if hasattr(self, "bottom_layout") and self.bottom_layout:
                self.bottom_layout.setAlignment(
                    self.logout_btn,
                    Qt.AlignmentFlag.AlignHCenter if collapsed else Qt.AlignmentFlag(0),
                )

        if hasattr(self, "collapse_btn") and self.collapse_btn:
            self._apply_button_metrics(self.collapse_btn, collapsed)
            if self.collapse_layout:
                self.collapse_layout.setAlignment(
                    self.collapse_btn,
                    Qt.AlignmentFlag.AlignHCenter if collapsed else Qt.AlignmentFlag(0),
                )
            self.collapse_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {p['muted']};
                    border: none;
                    border-radius: {'12px' if collapsed else '10px'};
                    font-size: 10.5pt;
                    font-weight: 500;
                    text-align: {'center' if collapsed else 'left'};
                    padding: {'0px' if collapsed else '0px 10px'};
                    margin: {'0px' if collapsed else '0px'};
                    min-height: {self.NAV_HEIGHT_COLLAPSED if collapsed else self.NAV_HEIGHT_EXPANDED}px;
                    max-height: {self.NAV_HEIGHT_COLLAPSED if collapsed else self.NAV_HEIGHT_EXPANDED}px;
                    {f'min-width: {self.NAV_HEIGHT_COLLAPSED}px; max-width: {self.NAV_HEIGHT_COLLAPSED}px;' if collapsed else 'min-width: 0px;'}
                }}
                QPushButton:hover {{
                    background-color: {p['hover']};
                    color: {p['text']};
                    border-radius: {'12px' if collapsed else '10px'};
                }}
                QPushButton:pressed {{
                    background-color: {p['selected']};
                    border-radius: {'12px' if collapsed else '10px'};
                }}
            """)

        if self.version_label:
            self.version_label.setStyleSheet(f"color: {p['muted']}; font-size: 8pt; padding: 2px 8px;")

        self._apply_theme_toggle_style()

    def _apply_theme_toggle_style(self) -> None:
        if not self.theme_toggle_container:
            return
        p = self._palette()
        dark_active = self._is_dark
        collapsed = self._is_collapsed
        container_width = 56 if collapsed else 150
        button_width = 25 if collapsed else 72
        self.theme_toggle_container.setFixedSize(container_width, 30)
        if hasattr(self, "bottom_layout") and self.bottom_layout:
            self.bottom_layout.setAlignment(self.theme_toggle_container, Qt.AlignmentFlag.AlignHCenter)
        self.theme_toggle_container.setVisible(True)
        self.theme_toggle_container.setStyleSheet(f"""
            QWidget#themeToggle {{
                background-color: {p['toggle']};
                border: 1px solid {p['border']};
                border-radius: 7px;
            }}
        """)
        for btn, active in ((self.theme_light_btn, not dark_active), (self.theme_dark_btn, dark_active)):
            if not btn:
                continue
            btn.setChecked(active)
            btn.setFixedSize(button_width, 24)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#ffffff' if active and not self._is_dark else '#3a3f46' if active else 'transparent'};
                    color: {p['text'] if active else p['muted']};
                    border: none;
                    border-radius: 5px;
                    padding: 0px;
                    min-width: {button_width}px;
                    max-width: {button_width}px;
                    min-height: 24px;
                    max-height: 24px;
                    font-size: {'8.5pt' if collapsed else '9pt'};
                    font-weight: {600 if active else 500};
                }}
                QPushButton:hover {{
                    background-color: {'#ffffff' if active and not self._is_dark else '#3a3f46' if active else p['hover']};
                    color: {p['text']};
                }}
            """)

    def _set_sidebar_theme(self, theme_name: str) -> None:
        if self._parent and callable(getattr(self._parent, "apply_manual_theme", None)):
            self._parent.apply_manual_theme(theme_name)
            return
        app = QApplication.instance()
        if app:
            from ui.themes import apply_theme as apply_theme_style
            apply_theme_style(app, theme_name)

    def _on_logout_clicked(self) -> None:
        """Handle logout button click"""
        if self._parent and hasattr(self._parent, 'logout'):
            self._parent.logout()
    
    def _create_sidebar_buttons(self) -> None:
        """Create sidebar navigation buttons - Menu bar style"""
        self.sidebar_buttons = []
        
        pages = [
            (5, "point_of_sale", "Sales", "sales"),
            (10, "receipt_long", "Restaurant", "sales"),
            (0, "dashboard", "Dashboard", "dashboard"),
            (1, "analytics", "Sales Summary", "sales_summary"),
            (2, "package", "Products", "products"),
            (9, "percent_discount", "Discounts", "products"),
            (8, "smart_toy", "Ai", "ai_pages"),
            (3, "inventory", "Inventory", "inventory"),
            (4, "receipt", "Receipts", "receipts"),
            (6, "person", "Customers", "customers"),
            (7, "money", "Expense", "expense"),
            (11, "person", "Employees", "employees"),
        ]
        
        user_id = None
        if self._parent and hasattr(self._parent, 'current_user'):
            user_id = self._parent.current_user["id"]
        
        is_dark = getattr(self, '_is_dark', True)
        
        if is_dark:
            hover_color = "#40444b"
            selected_color = "#40444b"
            text_color = "#dcddde"
            text_selected = "#ffffff"
        else:
            hover_color = "#e9ecef"
            selected_color = "#e9ecef"
            text_color = "#212529"
            text_selected = "#212529"
        
        for index, icon_name, text, perm in pages:
            can_view = True
            if user_id is not None:
                can_view = PermissionManager.user_can_view_page(user_id, perm)
            
            if can_view:
                btn = ModernButton(text or "Button", style=ModernButton.SECONDARY)
                btn.set_icon(icon_name, size=(self.NAV_ICON_EXPANDED, self.NAV_ICON_EXPANDED))
                btn.setFixedHeight(self.NAV_HEIGHT_EXPANDED)
                btn.setIconSize(QSize(self.NAV_ICON_EXPANDED, self.NAV_ICON_EXPANDED))
                btn.setProperty("page_index", index)
                btn.setProperty("page_text", text)
                btn.setProperty("icon_name", icon_name)
                btn.clicked.connect(lambda checked, idx=index: self._on_button_clicked(idx))
                
                # Menu bar style button - left aligned for expanded
                btn.setStyleSheet(btn.styleSheet() + f"""
                    QPushButton {{
                        text-align: left;
                        padding: 0px 10px;
                        margin: 0px;
                        border: none;
                        border-radius: 10px;
                        font-weight: 400;
                        font-size: 9.5pt;
                        color: {text_color};
                    }}
                    QPushButton:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:checked {{
                        background-color: {selected_color};
                        color: {text_selected};
                    }}
                    QPushButton:checked:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:pressed {{
                        background-color: {hover_color};
                    }}
                """)
                
                self.sidebar_buttons.append(btn)
        
        logger.info(f"Sidebar buttons created: {len(self.sidebar_buttons)} buttons (Menu bar style)")
    
    def _on_button_clicked(self, index: int) -> None:
        if self._parent and hasattr(self._parent, 'switch_to_page'):
            self._parent.switch_to_page(index)
    
    def _update_version_label(self) -> None:
        if self.version_label:
            try:
                from updater.version_manager import VersionManager
                version = VersionManager().get_current_version()
                self.version_label.setText(f"v{version}")
            except Exception as e:
                logger.warning(f"Could not get version: {e}")
                self.version_label.setText("v1.0.0")
    
    def toggle_collapse(self) -> None:
        """Toggle sidebar collapse/expand - INSTANT"""
        self._is_collapsed = not self._is_collapsed
        
        target_width = self.WIDTH_COLLAPSED if self._is_collapsed else self.WIDTH_EXPANDED
        
        self.setMinimumWidth(target_width)
        self.setMaximumWidth(target_width)
        self.setFixedWidth(target_width)
        
        self._update_ui_elements()
        self.collapse_state_changed.emit(self._is_collapsed)
        logger.debug(f"Sidebar toggled: is_collapsed={self._is_collapsed}, width={target_width}")
    
    def _update_ui_elements(self) -> None:
        """Update UI elements - Menu bar style with centered icons when collapsed"""
        for btn in self.sidebar_buttons:
            original_text = btn.property("page_text")
            if self._is_collapsed:
                btn.setText("")
            else:
                if original_text:
                    btn.setText(original_text)
        
        # Update version label visibility
        if self.version_label:
            self.version_label.setVisible(not self._is_collapsed)
        
        # Update collapse button arrow direction
        if hasattr(self, 'collapse_btn') and self.collapse_btn:
            if self._is_collapsed:
                self.collapse_btn.setText("")
                self.collapse_btn.set_icon("arrow_circle_right", size=(20, 20))
            else:
                self.collapse_btn.setText("Collapse")
                self.collapse_btn.set_icon("arrow_circle_left", size=(20, 20))
        
        # Update logout button
        if self.logout_btn:
            if self._is_collapsed:
                self.logout_btn.setText("")
            else:
                self.logout_btn.setText(tr("logout") or "Logout")

        if self.theme_light_btn and self.theme_dark_btn:
            self.theme_light_btn.setText("L" if self._is_collapsed else "Light")
            self.theme_dark_btn.setText("D" if self._is_collapsed else "Dark")
        
        if self.profile_text_container:
            self.profile_text_container.setVisible(not self._is_collapsed)
        self._apply_modern_styles()
        self.update()
    
    def update_theme(self, theme_name: str) -> None:
        """Update sidebar theme - Menu bar style"""
        self._is_dark = theme_name == "Dark"
        self._update_ui_elements()
        self._apply_modern_styles()
        QTimer.singleShot(0, self._apply_modern_styles)
        return
        colors = get_theme_colors()
        is_dark = theme_name == "Dark"
        self._is_dark = is_dark
        
        if is_dark:
            bg_color = "#2f3136"
            border_color = "#40444b"
            text_secondary = "#949ba4"
            header_color = "#72767d"
            hover_color = "#40444b"
            selected_color = "#40444b"
            text_color = "#dcddde"
            text_selected = "#ffffff"
        else:
            bg_color = "#f8f9fa"
            border_color = "#e9ecef"
            text_secondary = "#6c757d"
            header_color = "#6c757d"
            hover_color = "#e9ecef"
            selected_color = "#e9ecef"
            text_color = "#212529"
            text_selected = "#212529"
        
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {bg_color};
                border-right: 1px solid {border_color};
            }}
            QFrame#sidebar QLabel {{
                background: transparent;
            }}
        """)
        
        # Update header
        if hasattr(self, 'logo_label') and self.logo_label:
            self.logo_label.setStyleSheet(f"""
                color: {text_secondary};
                font-size: 11pt;
                font-weight: 600;
                padding: 2px 8px 6px 8px;
                background: transparent;
            """)
        
        if hasattr(self, 'header_divider') and self.header_divider:
            self.header_divider.setStyleSheet(f"background-color: {border_color}; margin: 4px 4px 8px 4px;")
        
        if hasattr(self, 'collapse_divider') and self.collapse_divider:
            self.collapse_divider.setStyleSheet(f"background-color: {border_color}; margin: 4px 4px 4px 4px;")
        
        if hasattr(self, 'bottom_divider') and self.bottom_divider:
            self.bottom_divider.setStyleSheet(f"background-color: {border_color}; margin: 4px 4px 4px 4px;")
        
        if self.version_label:
            self.version_label.setStyleSheet(f"""
                color: {text_secondary};
                font-size: 8pt;
                padding: 4px 8px 2px 8px;
                background: transparent;
            """)
        
        # Update collapse button
        if hasattr(self, 'collapse_btn') and self.collapse_btn:
            self.collapse_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {text_secondary};
                    border: none;
                    border-radius: 4px;
                    font-size: 11pt;
                    padding: 0px;
                    margin: 0px 4px 0px 4px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                    color: {text_color};
                }}
            """)
        
        # Update navigation buttons
        for btn in self.sidebar_buttons:
            if self._is_collapsed:
                btn.setStyleSheet(btn.styleSheet() + f"""
                    QPushButton {{
                        padding: 0px;
                        text-align: center;
                        margin: 0px;
                        border-radius: 10px;
                    }}
                    QPushButton::icon {{
                        margin-right: 0px;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:checked {{
                        background-color: {selected_color};
                        color: {text_selected};
                    }}
                    QPushButton:checked:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:pressed {{
                        background-color: {hover_color};
                    }}
                """)
            else:
                btn.setStyleSheet(btn.styleSheet() + f"""
                    QPushButton {{
                        text-align: left;
                        padding: 0px 10px;
                        margin: 0px;
                        border-radius: 10px;
                        font-size: 9.5pt;
                        color: {text_color};
                    }}
                    QPushButton::icon {{
                        margin-right: 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:checked {{
                        background-color: {selected_color};
                        color: {text_selected};
                    }}
                    QPushButton:checked:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:pressed {{
                        background-color: {hover_color};
                    }}
                """)
            btn.update()
        
        # Update logout button
        if self.logout_btn:
            if self._is_collapsed:
                self.logout_btn.setStyleSheet(self.logout_btn.styleSheet() + f"""
                    QPushButton {{
                        padding: 0px;
                        text-align: center;
                        margin: 0px;
                        border-radius: 10px;
                    }}
                    QPushButton::icon {{
                        margin-right: 0px;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_color};
                    }}
                    QPushButton:pressed {{
                        background-color: {hover_color};
                    }}
                """)
            else:
                self.logout_btn.setStyleSheet(self.logout_btn.styleSheet() + f"""
                    QPushButton {{
                        text-align: left;
                        padding: 0px 10px;
                        margin: 0px;
                        border-radius: 10px;
                        font-size: 9.5pt;
                        color: {text_color};
                    }}
                    QPushButton::icon {{
                        margin-right: 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_color};
                        color: {text_selected};
                    }}
                    QPushButton:pressed {{
                        background-color: {hover_color};
                    }}
                """)
            self.logout_btn.update()
    
    def set_selected_page(self, index: int) -> None:
        for btn in self.sidebar_buttons:
            page_idx = btn.property("page_index")
            btn.setChecked(page_idx == index)

