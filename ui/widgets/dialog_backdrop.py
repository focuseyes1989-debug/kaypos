"""Blur a snapshot without modifying the live window's graphics effects."""

from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QDialog, QGraphicsBlurEffect, QLabel


def exec_with_blurred_backdrop(dialog):
    window = dialog.parentWidget().window() if dialog.parentWidget() else None
    overlay = None
    try:
        if window and window.isVisible():
            snapshot = window.grab()
            painter = QPainter(snapshot)
            painter.fillRect(snapshot.rect(), QColor(0, 0, 0, 85))
            painter.end()
            overlay = QLabel(window)
            overlay.setPixmap(snapshot)
            overlay.setScaledContents(True)
            overlay.setGeometry(window.rect())
            blur = QGraphicsBlurEffect(overlay)
            blur.setBlurRadius(10)
            overlay.setGraphicsEffect(blur)
            overlay.show()
            overlay.raise_()
            dialog.move(window.mapToGlobal(window.rect().center()) - dialog.rect().center())
        return QDialog.exec(dialog)
    finally:
        if overlay:
            overlay.hide()
            overlay.deleteLater()
