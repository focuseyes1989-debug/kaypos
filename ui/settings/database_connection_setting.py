"""Local PostgreSQL connection settings."""
import os
import subprocess
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from ui.themes.theme_manager import get_theme_colors
from utils.db_connection_config import (
    DEFAULT_DB_NAME, DEFAULT_DB_PORT, DEFAULT_DB_USER,
    load_database_config, save_database_config, test_database_connection,
)


class DatabaseConnectionSettingWidget(QWidget):
    """Manage the local POS server without cloud sync or failover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        colors = get_theme_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        heading = QLabel("PostgreSQL Server")
        heading.setStyleSheet("font-size: 18px; font-weight: 600; background: transparent;")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("192.168.110.112")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.database_edit = QLineEdit()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        for title, field in (
            ("Server / Host", self.host_edit), ("Port", self.port_spin),
            ("Database", self.database_edit), ("Username", self.username_edit),
            ("Password", self.password_edit),
        ):
            field.setMinimumWidth(0)
            form.addRow(title, field)
        layout.addLayout(form)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(36)
        layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.btn_test = QPushButton("Test Connection")
        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("saveDatabase")
        self.btn_test.clicked.connect(self.test_connection)
        self.btn_save.clicked.connect(self.save_settings)
        buttons.addWidget(self.btn_test, 1)
        buttons.addWidget(self.btn_save, 1)
        layout.addLayout(buttons)
        layout.addStretch()
        self.setStyleSheet(f"""
            QLineEdit, QSpinBox {{ background: {colors['card_bg']}; color: {colors['text']};
                border: 1px solid {colors['border']}; border-radius: 6px;
                min-height: 30px; padding: 2px 8px; }}
            QLabel {{ color: {colors['text']}; background: transparent; }}
            QPushButton {{ min-height: 38px; max-height: 38px; padding: 0 10px;
                border: 1px solid {colors['border']}; border-radius: 6px;
                background: {colors['card_bg']}; color: {colors['text']}; }}
            QPushButton#saveDatabase {{ background: #2563eb; color: white; }}
        """)

    def load_settings(self):
        config = load_database_config()
        self.host_edit.setText(config.get("host") or "")
        self.port_spin.setValue(int(config.get("port") or DEFAULT_DB_PORT))
        self.database_edit.setText(config.get("database") or DEFAULT_DB_NAME)
        self.username_edit.setText(config.get("username") or DEFAULT_DB_USER)
        self.password_edit.setText(config.get("password") or "")

    def _values(self):
        return (self.host_edit.text().strip(), self.port_spin.value(),
                self.database_edit.text().strip() or DEFAULT_DB_NAME,
                self.username_edit.text().strip() or DEFAULT_DB_USER,
                self.password_edit.text())

    def test_connection(self):
        values = self._values()
        if not values[0]:
            self.status_label.setText("Enter the server IP or host.")
            self.host_edit.setFocus()
            return
        self.btn_test.setEnabled(False)
        self.status_label.setText("Testing connection...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, message = test_database_connection(*values)
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #16805d;" if ok else "color: #c43d3d;")
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_test.setEnabled(True)

    def save_settings(self):
        values = self._values()
        if not values[0]:
            self.status_label.setText("Enter the server IP or host.")
            self.host_edit.setFocus()
            return
        try:
            save_database_config(*values)
        except Exception:
            self.status_label.setText("Could not save database settings.")
            return
        self._prompt_restart()

    def _restart_command(self):
        if getattr(sys, "frozen", False):
            return [sys.executable], os.path.dirname(sys.executable)

        script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
        if script and os.path.exists(script):
            return [sys.executable, script], os.getcwd()
        return [sys.executable, "main.py"], os.getcwd()

    def _prompt_restart(self):
        answer = QMessageBox.question(
            self,
            "Restart Required",
            "Database settings were saved successfully.\n\nRestart the app now to apply the new connection settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._restart_app()

    def _restart_app(self):
        try:
            command, cwd = self._restart_command()
            popen_kwargs = {"cwd": cwd, "close_fds": True}
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "DETACHED_PROCESS", 0)
                )
            subprocess.Popen(command, **popen_kwargs)
            app = QApplication.instance()
            if app:
                QTimer.singleShot(200, app.closeAllWindows)
                QTimer.singleShot(500, app.quit)
                QTimer.singleShot(1200, lambda: os._exit(0))
            else:
                QTimer.singleShot(1200, lambda: os._exit(0))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Restart Failed",
                f"Settings were saved, but the app could not restart automatically.\n\n{exc}",
            )

    def retranslateUi(self):
        pass
