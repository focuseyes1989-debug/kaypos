"""Small code-native icons shared by KAY desktop applications."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


def branded_tile_icon(glyph: str, color: str) -> QIcon:
    """Create a crisp multi-resolution rounded tile matching Launcher cards."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        inset = max(1.0, size * 0.035)
        radius = size * 0.29
        painter.drawRoundedRect(QRectF(inset, inset, size - inset * 2, size - inset * 2), radius, radius)

        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPixelSize(max(9, round(size * 0.52)))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph[:1].upper())
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def pos_icon() -> QIcon:
    return branded_tile_icon("P", "#6675f5")


def car_management_icon() -> QIcon:
    return branded_tile_icon("C", "#27c992")


def service_job_icon() -> QIcon:
    # Draw the S directly so the icon does not depend on installed fonts.
    tile = branded_tile_icon("", "#d97706")
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128):
        pixmap = tile.pixmap(size, size)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.scale(size / 100, size / 100)
        painter.setPen(QPen(QColor("#ffffff"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path = QPainterPath()
        path.moveTo(70, 31)
        path.cubicTo(60, 20, 30, 21, 30, 38)
        path.cubicTo(30, 54, 70, 46, 70, 63)
        path.cubicTo(70, 82, 39, 82, 29, 70)
        painter.drawPath(path)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def launcher_app_icon() -> QIcon:
    return branded_tile_icon("K", "#6675f5")
