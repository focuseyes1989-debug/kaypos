"""Minimal application bootstrap for KAY POS Lite."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from lite_pos.config import load_config
from lite_pos.theme import apply_lite_theme
from lite_pos.window import LiteWindow
from utils.branded_icons import pos_icon


def apply_classic_style(app: QApplication) -> str:
    """Apply a compact Qt Designer/Cleanlooks-like desktop appearance."""
    apply_lite_theme(app, "Light")
    return app.style().objectName()


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("KAY POS Lite")
    app.setWindowIcon(pos_icon())
    apply_lite_theme(app, load_config().get("theme"))
    families = set(QFontDatabase.families())
    font = QFont("Myanmar Text" if "Myanmar Text" in families else "Segoe UI", 9)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    app.setFont(font)
    window = LiteWindow()
    QTimer.singleShot(0, window.show_login_dialog)
    return app.exec()
