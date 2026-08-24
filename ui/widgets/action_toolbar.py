# ui/widgets/action_toolbar.py
from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QMenu, QToolButton, QWidget

from ui.themes.theme_manager import get_theme_colors, get_themed_icon
from ui.widgets.modern_button import ModernButton


class ActionToolbar(QWidget):
    """Compact page toolbar with visible primary actions and a More menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.more_button = QToolButton(self)
        self.more_button.setText("More")
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.more_menu = QMenu(self.more_button)
        self.more_button.setMenu(self.more_menu)
        self.more_button.setFixedHeight(38)
        self.more_button.setMinimumWidth(84)
        self._more_added = False
        self._action_icons: dict[QAction, str] = {}
        self._apply_style()

    def add_primary(
        self,
        text: str,
        callback: Callable,
        icon: Optional[str] = None,
        style: str = ModernButton.PRIMARY,
        width: Optional[int] = None,
        stretch: bool = True,  # ✅ Add stretch parameter
    ) -> ModernButton:
        button = ModernButton(text, style)
        if icon:
            button.set_icon(icon, size=(16, 16))
        button.set_dense(True)
        button.setFixedHeight(38)
        if width:
            button.setMinimumWidth(width)
            button.setMaximumWidth(width)  # ✅ Also set maximum width
        button.clicked.connect(callback)
        
        # ✅ Add to layout with stretch control
        if stretch:
            self.layout.addWidget(button)
        else:
            self.layout.addWidget(button, 0)  # 0 = no stretch
        
        return button

    def add_more_action(
        self,
        text: str,
        callback: Callable,
        icon: Optional[str] = None,
        enabled: bool = True,
        tooltip: Optional[str] = None,
    ) -> QAction:
        action = QAction(text, self)
        if icon:
            action.setIcon(get_themed_icon(icon, size=(16, 16)))
            self._action_icons[action] = icon
        action.setEnabled(enabled)
        if tooltip:
            action.setToolTip(tooltip)
        action.triggered.connect(callback)
        self.more_menu.addAction(action)
        self._more_added = True
        self._sync_more_button()
        return action

    def add_separator(self) -> None:
        self.more_menu.addSeparator()
        self._more_added = True
        self._sync_more_button()

    def add_stretch(self) -> None:
        self.layout.addStretch()

    def finalize(self) -> None:
        self._sync_more_button()
        self.layout.addWidget(self.more_button)

    def _sync_more_button(self) -> None:
        self.more_button.setVisible(self._more_added)

    def _apply_style(self) -> None:
        colors = get_theme_colors()
        text = colors.get("text", "#212529")
        bg = colors.get("card_bg", "#ffffff")
        hover = colors.get("bg_hover", "#f1f3f5")
        border = colors.get("border", "#dee2e6")
        self.more_button.setStyleSheet(f"""
            QToolButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 3px 12px 3px 14px;
                font-weight: 600;
                font-size: 9pt;
            }}
            QToolButton:hover {{
                background-color: {hover};
            }}
            QToolButton::menu-indicator {{
                width: 12px;
            }}
        """)
        self.more_button.setIconSize(QSize(16, 16))
        self.more_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 7px 18px 7px 28px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {hover};
            }}
            QMenu::icon {{
                padding-left: 8px;
                padding-right: 8px;
            }}
        """)

    def update_theme(self) -> None:
        self._apply_style()
        for action, icon_name in self._action_icons.items():
            action.setIcon(get_themed_icon(icon_name, size=(16, 16)))
