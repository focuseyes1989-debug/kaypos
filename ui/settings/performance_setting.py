from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from models.database import connect_db
from utils.performance import refresh_performance_settings


class PerformanceSettingWidget(QWidget):
    performance_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        group = QGroupBox("Performance")
        form = QFormLayout(group)
        form.setVerticalSpacing(12)

        self.low_end_check = QCheckBox("Low-end PC mode")
        self.low_end_check.toggled.connect(self._apply_low_end_defaults)
        form.addRow("", self.low_end_check)

        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(12, 100)
        self.page_size_spin.setSingleStep(6)
        form.addRow("Product grid page size:", self.page_size_spin)

        self.debounce_spin = QSpinBox()
        self.debounce_spin.setRange(150, 1200)
        self.debounce_spin.setSingleStep(50)
        self.debounce_spin.setSuffix(" ms")
        form.addRow("Search delay:", self.debounce_spin)

        self.thumbnail_quality_combo = QComboBox()
        self.thumbnail_quality_combo.addItem("Disabled (fastest)", "off")
        self.thumbnail_quality_combo.addItem("Low (fastest)", "low")
        self.thumbnail_quality_combo.addItem("Normal", "normal")
        form.addRow("Image quality:", self.thumbnail_quality_combo)

        self.youtube_enabled_check = QCheckBox("Enable YouTube in Customer Display")
        form.addRow("", self.youtube_enabled_check)

        note = QLabel(
            "Low-end mode reduces product cards per page, delays search while typing, "
            "uses smaller thumbnails, and lets you disable WebEngine-heavy YouTube playback."
        )
        note.setWordWrap(True)
        form.addRow("", note)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_settings)
        form.addRow("", self.btn_save)

        layout.addWidget(group)
        layout.addStretch()

    def _apply_low_end_defaults(self, checked):
        if checked:
            self.page_size_spin.setValue(25)
            self.debounce_spin.setValue(600)
            self.thumbnail_quality_combo.setCurrentIndex(self.thumbnail_quality_combo.findData("low"))
            self.youtube_enabled_check.setChecked(False)

    def load_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        keys = (
            "performance_low_end_mode",
            "performance_product_page_size",
            "performance_search_debounce_ms",
            "performance_thumbnail_quality",
            "performance_customer_display_youtube_enabled",
        )
        cursor.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join(['?'] * len(keys))})",
            keys,
        )
        values = dict(cursor.fetchall())
        conn.close()

        low_end = values.get("performance_low_end_mode", "1") == "1"
        self.low_end_check.blockSignals(True)
        self.low_end_check.setChecked(low_end)
        self.low_end_check.blockSignals(False)
        saved_page_size = int(values.get("performance_product_page_size") or 25)
        self.page_size_spin.setValue(25 if low_end else saved_page_size)
        self.debounce_spin.setValue(int(values.get("performance_search_debounce_ms") or (600 if low_end else 300)))
        quality = "low" if low_end else (values.get("performance_thumbnail_quality") or "normal")
        quality_index = self.thumbnail_quality_combo.findData(quality)
        self.thumbnail_quality_combo.setCurrentIndex(max(0, quality_index))
        self.youtube_enabled_check.setChecked(values.get("performance_customer_display_youtube_enabled", "0") == "1")

    def save_settings(self):
        values = {
            "performance_low_end_mode": "1" if self.low_end_check.isChecked() else "0",
            "performance_product_page_size": str(self.page_size_spin.value()),
            "performance_search_debounce_ms": str(self.debounce_spin.value()),
            "performance_thumbnail_quality": self.thumbnail_quality_combo.currentData() or "normal",
            "performance_customer_display_youtube_enabled": "1" if self.youtube_enabled_check.isChecked() else "0",
        }
        conn = connect_db()
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            values.items(),
        )
        conn.commit()
        conn.close()
        refresh_performance_settings()
        self.performance_settings_changed.emit()
        QMessageBox.information(self, "Saved", "Performance settings saved.")
