"""QR-code generation and preview for Car Management records."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)


def qr_access_url(token: str, host: str, owner_web_url: str = "", web_port: int = 8000) -> str:
    """Build the owner URL, defaulting to LAN independently of Cloud API settings."""
    base = str(owner_web_url or "").strip().rstrip("/")
    if not base:
        base = f"https://{str(host or '').strip()}:{int(web_port)}"
    return f"{base}/car/print?t={str(token or '').strip()}"


def record_qr_png(payload: str, box_size: int = 10, border: int = 4) -> bytes:
    """Render an opaque owner access URL as PNG bytes."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(str(payload))
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def suggested_qr_filename(record: dict) -> str:
    car_number = str(record.get("car_number") or "car").strip()
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in car_number)
    return f"{safe or 'car'}_qr.png"


class CarQrDialog(QDialog):
    def __init__(self, record: dict, access_url: str, parent=None):
        super().__init__(parent)
        self.record = dict(record)
        self.access_url = str(access_url)
        self.png_data = record_qr_png(self.access_url)
        self.setWindowTitle("Car QR Code")
        self.setMinimumWidth(410)

        layout = QVBoxLayout(self)
        title = QLabel(str(record.get("car_number") or "Car Record"))
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        detail = QLabel("Owner QR · Scan to open this car's secure print-service page.")
        detail.setObjectName("muted")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        layout.addWidget(detail)

        pixmap = QPixmap()
        if not pixmap.loadFromData(self.png_data, "PNG"):
            raise ValueError("Unable to render the QR code image.")
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setPixmap(pixmap.scaled(320, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.qr_label)

        caption = QLabel(f"Driver: {record.get('driver_name') or '—'}")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)

        actions = QHBoxLayout()
        copy_button = QPushButton("Copy Image")
        save_button = QPushButton("Save PNG")
        close_button = QPushButton("Close")
        save_button.setObjectName("primary")
        copy_button.clicked.connect(self.copy_image)
        save_button.clicked.connect(self.save_image)
        close_button.clicked.connect(self.accept)
        actions.addWidget(copy_button)
        actions.addWidget(save_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def copy_image(self):
        pixmap = QPixmap()
        pixmap.loadFromData(self.png_data, "PNG")
        QApplication.clipboard().setPixmap(pixmap)
        QMessageBox.information(self, "Car QR Code", "QR code image copied to the clipboard.")

    def save_image(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Car QR Code", suggested_qr_filename(self.record), "PNG Image (*.png)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        try:
            path.write_bytes(self.png_data)
        except OSError as exc:
            QMessageBox.critical(self, "Car QR Code", f"Could not save the QR code:\n{exc}")
            return
        QMessageBox.information(self, "Car QR Code", f"QR code saved to:\n{path}")
