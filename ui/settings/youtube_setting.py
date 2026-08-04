from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.database import connect_db


class YouTubeSettingWidget(QWidget):
    youtube_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        group = QGroupBox("Customer Display YouTube")
        form = QFormLayout(group)
        form.setVerticalSpacing(12)

        self.youtube_url_edit = QLineEdit()
        self.youtube_url_edit.setPlaceholderText(
            "https://www.youtube.com/watch?v=VIDEO_ID or playlist URL"
        )
        form.addRow("YouTube link:", self.youtube_url_edit)

        help_label = QLabel(
            "Use a YouTube video, Shorts, playlist, or embed link. "
            "A plain YouTube homepage link will not play."
        )
        help_label.setWordWrap(True)
        form.addRow("", help_label)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_settings)
        form.addRow("", self.btn_save)

        layout.addWidget(group)
        layout.addStretch()

    def load_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='customer_display_youtube_url'")
        row = cursor.fetchone()
        conn.close()
        self.youtube_url_edit.setText(row[0] if row else "")

    def save_settings(self):
        url = self.youtube_url_edit.text().strip()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("customer_display_youtube_url", url),
        )
        conn.commit()
        conn.close()
        self.youtube_settings_changed.emit()
        QMessageBox.information(self, "Saved", "YouTube setting saved.")
