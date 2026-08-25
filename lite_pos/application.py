"""Minimal application bootstrap for KAY POS Lite."""

from __future__ import annotations

import sys

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

from lite_pos.window import LiteWindow
from utils.branded_icons import pos_icon


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


def apply_classic_style(app: QApplication) -> str:
    """Apply a compact Qt Designer/Cleanlooks-like desktop appearance."""
    # Qt 6 no longer ships the old Cleanlooks/Plastique engines.  Fusion keeps
    # the same native Qt geometry and subtle borders without Windows Classic's
    # heavy black outlines.
    base_style = QStyleFactory.create("Fusion") or QStyleFactory.create("Windows")
    if base_style is not None:
        style = DesignerFusionStyle(base_style)
        style.setObjectName("fusion")
        app.setStyle(style)
        palette = base_style.standardPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#efefef"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f5f5"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#efefef"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#3399cc"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#fffde7"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#202020"))
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor("#999999"),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor("#999999"),
        )
        app.setPalette(palette)
    return app.style().objectName()


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("KAY POS Lite")
    app.setWindowIcon(pos_icon())
    apply_classic_style(app)
    families = set(QFontDatabase.families())
    font = QFont("Myanmar Text" if "Myanmar Text" in families else "Segoe UI", 9)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    app.setFont(font)
    window = LiteWindow()
    window.show()
    return app.exec()
