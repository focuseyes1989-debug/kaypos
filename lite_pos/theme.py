"""Light and dark application palettes for KAY POS Lite."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory


class DesignerFusionStyle(QProxyStyle):
    """Fusion style with optically centred native dialog-button labels."""

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_PushButtonLabel:
            painter.save()
            painter.translate(0, 1)
            try:
                return super().drawControl(element, option, painter, widget)
            finally:
                painter.restore()
        return super().drawControl(element, option, painter, widget)


def normalize_theme(theme_name: str | None) -> str:
    return "Dark" if str(theme_name or "").strip().casefold() == "dark" else "Light"


def apply_lite_theme(app: QApplication, theme_name: str | None) -> str:
    """Apply the requested POS Lite palette and return its normalized name."""
    theme = normalize_theme(theme_name)
    base_style = QStyleFactory.create("Fusion") or QStyleFactory.create("Windows")
    if base_style is None:
        return theme

    style = DesignerFusionStyle(base_style)
    style.setObjectName("fusion")
    app.setStyle(style)
    palette = base_style.standardPalette()

    colors = ({
        "window": "#171b26", "window_text": "#edf2ff", "base": "#111724",
        "alternate": "#1f2635", "text": "#edf2ff", "button": "#252d3d",
        "button_text": "#edf2ff", "highlight": "#5365df", "highlighted": "#ffffff",
        "tooltip_base": "#252d3d", "tooltip_text": "#edf2ff", "disabled": "#7d8799",
        "link": "#8ea0ff", "placeholder": "#98a2b5",
    } if theme == "Dark" else {
        "window": "#efefef", "window_text": "#202020", "base": "#ffffff",
        "alternate": "#f5f5f5", "text": "#202020", "button": "#efefef",
        "button_text": "#202020", "highlight": "#3399cc", "highlighted": "#ffffff",
        "tooltip_base": "#fffde7", "tooltip_text": "#202020", "disabled": "#999999",
        "link": "#2457c5", "placeholder": "#707070",
    })
    role_colors = {
        QPalette.ColorRole.Window: colors["window"],
        QPalette.ColorRole.WindowText: colors["window_text"],
        QPalette.ColorRole.Base: colors["base"],
        QPalette.ColorRole.AlternateBase: colors["alternate"],
        QPalette.ColorRole.Text: colors["text"],
        QPalette.ColorRole.Button: colors["button"],
        QPalette.ColorRole.ButtonText: colors["button_text"],
        QPalette.ColorRole.Highlight: colors["highlight"],
        QPalette.ColorRole.HighlightedText: colors["highlighted"],
        QPalette.ColorRole.ToolTipBase: colors["tooltip_base"],
        QPalette.ColorRole.ToolTipText: colors["tooltip_text"],
        QPalette.ColorRole.Link: colors["link"],
        QPalette.ColorRole.PlaceholderText: colors["placeholder"],
    }
    for role, color in role_colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled"]))
    app.setPalette(palette)
    return theme
