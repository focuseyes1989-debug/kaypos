from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QComboBox,
    QPushButton, QMessageBox, QScrollArea, QFrame, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from models.database import connect_db
from utils.language import lang


class RegionalSettingWidget(QWidget):
    currency_changed = pyqtSignal()   # <-- signal added
    language_changed = pyqtSignal(str)  # optional, but kept for compatibility

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_currency_setting()
        self.load_language_setting()

    def setup_ui(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)

        # Currency group
        self.currency_group = QGroupBox()
        currency_layout = QFormLayout()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["Kyats (Ks)", "Dollar ($)", "Baht (B)"])
        currency_layout.addRow(QLabel("Select Currency:"), self.currency_combo)
        self.currency_group.setLayout(currency_layout)
        content_layout.addWidget(self.currency_group)

        # Language group
        self.language_group = QGroupBox()
        language_layout = QFormLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Myanmar"])
        language_layout.addRow(QLabel("Select Language:"), self.language_combo)
        self.language_group.setLayout(language_layout)
        content_layout.addWidget(self.language_group)

        # Save button
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self.save_settings)
        content_layout.addWidget(self.btn_save, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.currency_group.setTitle("ငွေကြေးသတ်မှတ်ချက်")
            self.language_group.setTitle("ဘာသာစကား")
            self.btn_save.setText("သိမ်းဆည်းမည်")
        else:
            self.currency_group.setTitle("Currency Configuration")
            self.language_group.setTitle("Language / ဘာသာစကား")
            self.btn_save.setText("Save Regional Settings")

    def load_currency_setting(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='currency'")
        row = cursor.fetchone()
        conn.close()
        currency = row[0] if row else "Kyats (Ks)"
        index = self.currency_combo.findText(currency)
        if index >= 0:
            self.currency_combo.setCurrentIndex(index)

    def load_language_setting(self):
        current_lang = lang.get_current()
        self.language_combo.setCurrentText("English" if current_lang == "en" else "Myanmar")

    def save_settings(self):
        main_window = self.window()
        if hasattr(main_window, "show_loading"):
            main_window.show_loading("Saving regional settings...", 20)
        selected_currency = self.currency_combo.currentText()
        selected_lang = self.language_combo.currentText()
        lang_code = "en" if selected_lang == "English" else "my"
        
        # Save currency
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("currency", selected_currency))
        conn.commit()
        conn.close()
        if hasattr(main_window, "update_loading"):
            main_window.update_loading("Refreshing regional settings...", 70)
        
        # Emit currency changed signal
        self.currency_changed.emit()
        
        # Change language using centralized manager (delay to avoid crash)
        if lang_code != lang.get_current():
            QTimer.singleShot(100, lambda: lang.set_language(lang_code))
        
        # Show message in current language
        if lang.get_current() == "my":
            msg = "ငွေကြေးနှင့် ဘာသာစကား သိမ်းဆည်းပြီးပါပြီ။"
        else:
            msg = "Currency and language settings saved."
        if hasattr(main_window, "update_loading"):
            main_window.update_loading("Regional settings saved.", 100)
        if hasattr(main_window, "hide_loading"):
            main_window.hide_loading()
        QMessageBox.information(self, "Saved", msg)
