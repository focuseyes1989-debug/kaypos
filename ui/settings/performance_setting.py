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
from utils.db_compat import is_postgres_backend
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

        self.lite_mode_check = QCheckBox("Lite Mode")
        self.lite_mode_check.setToolTip("Use fewer product cards, slower search triggering, and no product thumbnails.")
        self.lite_mode_check.toggled.connect(self._on_lite_mode_toggled)
        form.addRow("", self.lite_mode_check)

        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(12, 72)
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


        note = QLabel(
            "Lite Mode is best for slower PCs and busy counters. Custom values are still available when Lite Mode is off."
        )
        note.setWordWrap(True)
        form.addRow("", note)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_settings)
        form.addRow("", self.btn_save)

        layout.addWidget(group)
        layout.addStretch()

    def load_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        keys = (
            "performance_product_page_size",
            "performance_search_debounce_ms",
            "performance_thumbnail_quality",
            "performance_lite_mode_enabled",
        )
        cursor.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join(['?'] * len(keys))})",
            keys,
        )
        values = dict(cursor.fetchall())
        conn.close()

        lite_mode = str(values.get("performance_lite_mode_enabled") or "0").lower() in ("1", "true", "yes", "on")
        self.lite_mode_check.setChecked(lite_mode)
        saved_page_size = int(values.get("performance_product_page_size") or 36)
        self.page_size_spin.setValue(saved_page_size)
        self.debounce_spin.setValue(int(values.get("performance_search_debounce_ms") or 350))
        quality = values.get("performance_thumbnail_quality") or "low"
        quality_index = self.thumbnail_quality_combo.findData(quality)
        self.thumbnail_quality_combo.setCurrentIndex(max(0, quality_index))
        self._on_lite_mode_toggled(lite_mode)

    def save_settings(self):
        lite_mode = self.lite_mode_check.isChecked()
        values = {
            "performance_lite_mode_enabled": "1" if lite_mode else "0",
            "performance_product_page_size": "24" if lite_mode else str(self.page_size_spin.value()),
            "performance_search_debounce_ms": "450" if lite_mode else str(self.debounce_spin.value()),
            "performance_thumbnail_quality": "off" if lite_mode else (self.thumbnail_quality_combo.currentData() or "low"),
        }
        conn = connect_db()
        cursor = conn.cursor()
        if is_postgres_backend():
            cursor.executemany(
                """
                INSERT INTO settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                values.items(),
            )
        else:
            cursor.executemany(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                values.items(),
            )
        conn.commit()
        conn.close()
        refresh_performance_settings()
        self.performance_settings_changed.emit()
        QMessageBox.information(self, "Saved", "Performance settings saved.")

    def _on_lite_mode_toggled(self, checked: bool):
        self.page_size_spin.setEnabled(not checked)
        self.debounce_spin.setEnabled(not checked)
        self.thumbnail_quality_combo.setEnabled(not checked)
        if checked:
            self.page_size_spin.setValue(24)
            self.debounce_spin.setValue(450)
            index = self.thumbnail_quality_combo.findData("off")
            self.thumbnail_quality_combo.setCurrentIndex(max(0, index))
