from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.telegram_service import (
    TelegramConfig,
    TelegramError,
    load_telegram_config,
    save_telegram_config,
    send_test_message,
    send_today_sales_summary,
    start_telegram_command_listener,
    stop_telegram_command_listener,
    upload_database_backup,
)


class TelegramTaskThread(QThread):
    success = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            if self.action == "test":
                message = send_test_message()
            elif self.action == "summary":
                message = send_today_sales_summary()
            elif self.action == "backup":
                message = upload_database_backup()
            else:
                raise TelegramError(f"Unknown Telegram action: {self.action}")
            self.success.emit(message)
        except Exception as exc:
            self.failed.emit(str(exc))


class TelegramSettingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_thread = None
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(18)

        self.config_group = QGroupBox()
        config_layout = QFormLayout()
        config_layout.setSpacing(8)

        self.enabled_check = QCheckBox()
        self.listener_check = QCheckBox()
        self.enabled_check.toggled.connect(self._on_enabled_toggled)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("1234567890:ABC...")

        self.chat_id_edit = QLineEdit()
        self.chat_id_edit.setPlaceholderText("2043234455 or -100...")

        config_layout.addRow("Enable Telegram:", self.enabled_check)
        config_layout.addRow("Enable command listener:", self.listener_check)
        config_layout.addRow("Bot token:", self.token_edit)
        config_layout.addRow("Chat ID:", self.chat_id_edit)

        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self.save_settings)
        config_layout.addRow("", self.btn_save)

        self.config_group.setLayout(config_layout)
        content_layout.addWidget(self.config_group)

        self.actions_group = QGroupBox()
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(10)

        button_layout = QHBoxLayout()
        self.btn_test = QPushButton()
        self.btn_summary = QPushButton()
        self.btn_backup = QPushButton()
        self.btn_test.clicked.connect(lambda: self.run_task("test"))
        self.btn_summary.clicked.connect(lambda: self.run_task("summary"))
        self.btn_backup.clicked.connect(lambda: self.run_task("backup"))

        button_layout.addWidget(self.btn_test)
        button_layout.addWidget(self.btn_summary)
        button_layout.addWidget(self.btn_backup)
        button_layout.addStretch()
        actions_layout.addLayout(button_layout)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        actions_layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(140)
        actions_layout.addWidget(self.log_text)

        self.actions_group.setLayout(actions_layout)
        content_layout.addWidget(self.actions_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.setLayout(layout)
        self.retranslateUi()

    def retranslateUi(self):
        self.config_group.setTitle("Telegram Bot Configuration")
        self.actions_group.setTitle("Telegram Actions")
        self.enabled_check.setText("Enabled")
        self.listener_check.setText("Listen for /backup, /db, /additem commands")
        self.btn_save.setText("Save Telegram Settings")
        self.btn_test.setText("Send Test Message")
        self.btn_summary.setText("Send Today's Summary")
        self.btn_backup.setText("Upload SQLite Backup")
        self.status_label.setText(
            "Settings are stored in the local .env file and are not included in database backups.\n"
            "Turn on the command listener only when you want ZAY POS to respond to /backup, /db, or /additem.\n"
            'To add a product, send text or a photo with caption: /additem name="Coffee" category=Drinks price=2500 barcode=123456 low_stock=5'
        )

    def load_settings(self):
        config = load_telegram_config()
        self.enabled_check.setChecked(config.enabled)
        self.listener_check.setChecked(config.listener_enabled)
        self.token_edit.setText(config.bot_token)
        self.chat_id_edit.setText(config.chat_id)
        self._on_enabled_toggled(config.enabled)

    def _on_enabled_toggled(self, checked):
        self.listener_check.setEnabled(checked)
        if not checked:
            self.listener_check.setChecked(False)

    def save_settings(self, show_message=True):
        config = TelegramConfig(
            enabled=self.enabled_check.isChecked(),
            listener_enabled=self.listener_check.isChecked(),
            bot_token=self.token_edit.text().strip(),
            chat_id=self.chat_id_edit.text().strip(),
        )

        if config.listener_enabled and not config.enabled:
            QMessageBox.warning(
                self,
                "Telegram Settings",
                "Enable Telegram before turning on the command listener.",
            )
            return False

        if config.enabled and (not config.bot_token or not config.chat_id):
            QMessageBox.warning(
                self,
                "Telegram Settings",
                "Bot token and chat ID are required when Telegram is enabled.",
            )
            return False

        try:
            save_telegram_config(config)
            if config.enabled and config.listener_enabled:
                start_telegram_command_listener()
            else:
                stop_telegram_command_listener()
        except Exception as exc:
            QMessageBox.critical(self, "Telegram Settings", f"Could not save settings: {exc}")
            return False

        self.append_log("Telegram settings saved.")
        if show_message:
            QMessageBox.information(self, "Saved", "Telegram settings saved.")
        return True

    def run_task(self, action):
        if not self.save_settings(show_message=False):
            return

        if not self.enabled_check.isChecked():
            QMessageBox.warning(self, "Telegram", "Enable Telegram before running this action.")
            return

        self.set_actions_enabled(False)
        self.append_log(f"Starting action: {action}")

        thread = TelegramTaskThread(action, self)
        thread.success.connect(self.on_task_success)
        thread.failed.connect(self.on_task_failed)
        thread.finished.connect(lambda: self.set_actions_enabled(True))
        thread.finished.connect(lambda: self.clear_thread(thread))
        self.current_thread = thread
        thread.start()

    def on_task_success(self, message):
        self.append_log(message)
        QMessageBox.information(self, "Telegram", message)

    def on_task_failed(self, message):
        self.append_log(f"Failed: {message}")
        QMessageBox.warning(self, "Telegram", message)

    def set_actions_enabled(self, enabled):
        self.btn_test.setEnabled(enabled)
        self.btn_summary.setEnabled(enabled)
        self.btn_backup.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.enabled_check.setEnabled(enabled)
        self.listener_check.setEnabled(enabled and self.enabled_check.isChecked())
        self.token_edit.setEnabled(enabled)
        self.chat_id_edit.setEnabled(enabled)

    def clear_thread(self, thread):
        if self.current_thread is thread:
            self.current_thread = None
        thread.deleteLater()

    def append_log(self, message):
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
