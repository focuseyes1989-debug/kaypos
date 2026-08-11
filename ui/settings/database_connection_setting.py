from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt

from utils.db_connection_config import (
    DEFAULT_DB_NAME,
    DEFAULT_DB_PORT,
    DEFAULT_DB_USER,
    load_database_config,
    save_database_config,
    test_database_connection,
)


class DatabaseConnectionSettingWidget(QWidget):
    """Local client database connection settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        self.connection_group = QGroupBox("PostgreSQL Server")
        form = QFormLayout()
        form.setSpacing(10)

        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("192.168.100.130")
        form.addRow("Server IP / Host:", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(DEFAULT_DB_PORT)
        form.addRow("Port:", self.port_spin)

        self.database_edit = QLineEdit(DEFAULT_DB_NAME)
        form.addRow("Database:", self.database_edit)

        self.username_edit = QLineEdit(DEFAULT_DB_USER)
        form.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self.password_edit)

        self.connection_group.setLayout(form)
        layout.addWidget(self.connection_group)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        self.btn_test = QPushButton("Test Connection")
        self.btn_save = QPushButton("Save")
        self.btn_test.clicked.connect(self.test_connection)
        self.btn_save.clicked.connect(self.save_settings)
        button_row.addStretch()
        button_row.addWidget(self.btn_test)
        button_row.addWidget(self.btn_save)
        layout.addLayout(button_row)

        note = QLabel(
            "These settings are saved on this client PC only. Restart the app after saving "
            "so every module reconnects with the new database settings."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(note)
        layout.addStretch()

    def load_settings(self):
        config = load_database_config()
        self.host_edit.setText(config.get("host") or "")
        self.port_spin.setValue(int(config.get("port") or DEFAULT_DB_PORT))
        self.database_edit.setText(config.get("database") or DEFAULT_DB_NAME)
        self.username_edit.setText(config.get("username") or DEFAULT_DB_USER)
        self.password_edit.setText(config.get("password") or "")

    def _values(self):
        return (
            self.host_edit.text().strip(),
            self.port_spin.value(),
            self.database_edit.text().strip() or DEFAULT_DB_NAME,
            self.username_edit.text().strip() or DEFAULT_DB_USER,
            self.password_edit.text(),
        )

    def test_connection(self):
        host, port, database, username, password = self._values()
        if not host:
            QMessageBox.warning(self, "Database Connection", "Please enter the server IP or host.")
            return
        self.status_label.setText("Testing connection...")
        ok, message = test_database_connection(host, port, database, username, password)
        self.status_label.setText(message)
        if ok:
            QMessageBox.information(self, "Database Connection", message)
        else:
            QMessageBox.critical(self, "Database Connection Failed", message)

    def save_settings(self):
        host, port, database, username, password = self._values()
        if not host:
            QMessageBox.warning(self, "Database Connection", "Please enter the server IP or host.")
            return
        env_path = save_database_config(host, port, database, username, password)
        QMessageBox.information(
            self,
            "Database Connection",
            f"Saved to {env_path}\n\nPlease restart the app.",
        )

    def retranslateUi(self):
        pass
