from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QCheckBox, QLineEdit, QPushButton, QSpinBox, QMessageBox, QProgressDialog
)
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal

from utils.db_connection_config import (
    DEFAULT_DB_NAME,
    DEFAULT_DB_PORT,
    DEFAULT_DB_USER,
    load_database_config,
    load_cloud_sync_config,
    save_database_config,
    save_database_failover_config,
    save_cloud_sync_config,
    test_database_connection,
    test_cloud_sync_connection,
)


class CloudSyncWorker(QObject):
    finished = pyqtSignal(bool, str)

    def __init__(self, database_url, action="sync"):
        super().__init__()
        self.database_url = database_url
        self.action = action

    def run(self):
        try:
            from services.cloud_sync_service import CloudSyncService

            service = CloudSyncService(database_url=self.database_url)
            result = service.pull_once() if self.action == "pull" else service.sync_once()
            self.finished.emit(result.ok, result.message)
        except Exception as exc:
            self.finished.emit(False, str(exc))


class DatabaseConnectionSettingWidget(QWidget):
    """Local client database connection settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sync_thread = None
        self._sync_worker = None
        self._sync_progress = None
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(14)

        self.connection_group = QGroupBox("PostgreSQL Server")
        self.connection_group.setMinimumWidth(320)
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

        self.cloud_group = QGroupBox("Cloud Sync (Aiven PostgreSQL)")
        self.cloud_group.setMinimumWidth(360)
        cloud_form = QFormLayout()
        cloud_form.setSpacing(10)

        self.cloud_enabled_check = QCheckBox("Enable cloud sync on this PC")
        cloud_form.addRow("", self.cloud_enabled_check)

        self.failover_enabled_check = QCheckBox("Use this cloud database if the local PostgreSQL server is offline")
        cloud_form.addRow("", self.failover_enabled_check)

        self.cloud_host_edit = QLineEdit()
        self.cloud_host_edit.setPlaceholderText("pg-xxxx.aivencloud.com")
        cloud_form.addRow("Aiven Host:", self.cloud_host_edit)

        self.cloud_port_spin = QSpinBox()
        self.cloud_port_spin.setRange(1, 65535)
        self.cloud_port_spin.setValue(16365)
        cloud_form.addRow("Port:", self.cloud_port_spin)

        self.cloud_database_edit = QLineEdit("defaultdb")
        cloud_form.addRow("Database:", self.cloud_database_edit)

        self.cloud_username_edit = QLineEdit("avnadmin")
        cloud_form.addRow("Username:", self.cloud_username_edit)

        self.cloud_password_edit = QLineEdit()
        self.cloud_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        cloud_form.addRow("Password:", self.cloud_password_edit)

        self.cloud_ssl_edit = QLineEdit("require")
        cloud_form.addRow("SSL mode:", self.cloud_ssl_edit)

        self.cloud_interval_spin = QSpinBox()
        self.cloud_interval_spin.setRange(60, 86400)
        self.cloud_interval_spin.setSingleStep(60)
        self.cloud_interval_spin.setValue(300)
        cloud_form.addRow("Sync interval (sec):", self.cloud_interval_spin)

        self.branch_id_edit = QLineEdit("shop_001")
        cloud_form.addRow("Branch ID:", self.branch_id_edit)

        self.device_id_edit = QLineEdit("server_pc")
        cloud_form.addRow("Device ID:", self.device_id_edit)

        self.cloud_group.setLayout(cloud_form)

        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        left_column.addWidget(self.connection_group)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        left_column.addWidget(self.status_label)
        left_column.addStretch()

        right_column = QVBoxLayout()
        right_column.setSpacing(10)
        right_column.addWidget(self.cloud_group)

        self.cloud_status_label = QLabel("")
        self.cloud_status_label.setWordWrap(True)
        right_column.addWidget(self.cloud_status_label)
        right_column.addStretch()

        columns_layout.addLayout(left_column, 1)
        columns_layout.addLayout(right_column, 1)
        layout.addLayout(columns_layout, stretch=1)

        button_row = QHBoxLayout()
        self.btn_test = QPushButton("Test Connection")
        self.btn_test_cloud = QPushButton("Test Cloud")
        self.btn_sync_now = QPushButton("Sync Now")
        self.btn_pull_cloud = QPushButton("Pull from Cloud")
        self.btn_save = QPushButton("Save")
        self.btn_test.clicked.connect(self.test_connection)
        self.btn_test_cloud.clicked.connect(self.test_cloud_connection)
        self.btn_sync_now.clicked.connect(self.sync_cloud_now)
        self.btn_pull_cloud.clicked.connect(self.pull_cloud_now)
        self.btn_save.clicked.connect(self.save_settings)
        button_row.addStretch()
        button_row.addWidget(self.btn_test)
        button_row.addWidget(self.btn_test_cloud)
        button_row.addWidget(self.btn_sync_now)
        button_row.addWidget(self.btn_pull_cloud)
        button_row.addWidget(self.btn_save)
        layout.addLayout(button_row)

        note = QLabel(
            "Local PostgreSQL settings control the primary POS database connection. Cloud Sync "
            "pushes local data to Aiven from server PCs. Client failover lets this app use the "
            "cloud database when the local PostgreSQL server is offline. "
            "Restart the app after saving so background services reload the new settings."
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

        cloud = load_cloud_sync_config()
        self.cloud_enabled_check.setChecked(bool(cloud.get("enabled")))
        self.failover_enabled_check.setChecked(bool(cloud.get("failover_enabled")))
        self.cloud_host_edit.setText(cloud.get("host") or "")
        self.cloud_port_spin.setValue(int(cloud.get("port") or 16365))
        self.cloud_database_edit.setText(cloud.get("database") or "defaultdb")
        self.cloud_username_edit.setText(cloud.get("username") or "avnadmin")
        self.cloud_password_edit.setText(cloud.get("password") or "")
        self.cloud_ssl_edit.setText(cloud.get("sslmode") or "require")
        self.cloud_interval_spin.setValue(int(cloud.get("interval_seconds") or 300))
        self.branch_id_edit.setText(cloud.get("branch_id") or "shop_001")
        self.device_id_edit.setText(cloud.get("device_id") or "server_pc")

    def _values(self):
        return (
            self.host_edit.text().strip(),
            self.port_spin.value(),
            self.database_edit.text().strip() or DEFAULT_DB_NAME,
            self.username_edit.text().strip() or DEFAULT_DB_USER,
            self.password_edit.text(),
        )

    def _cloud_values(self):
        return (
            self.cloud_enabled_check.isChecked(),
            self.failover_enabled_check.isChecked(),
            self.cloud_host_edit.text().strip(),
            self.cloud_port_spin.value(),
            self.cloud_database_edit.text().strip() or "defaultdb",
            self.cloud_username_edit.text().strip() or "avnadmin",
            self.cloud_password_edit.text(),
            self.cloud_ssl_edit.text().strip() or "require",
            self.cloud_interval_spin.value(),
            self.branch_id_edit.text().strip() or "shop_001",
            self.device_id_edit.text().strip() or "server_pc",
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

    def test_cloud_connection(self):
        enabled, failover_enabled, host, port, database, username, password, sslmode, *_ = self._cloud_values()
        if not host:
            QMessageBox.warning(self, "Cloud Sync", "Please enter the Aiven host.")
            return
        self.cloud_status_label.setText("Testing cloud connection...")
        ok, message = test_cloud_sync_connection(host, port, database, username, password, sslmode)
        self.cloud_status_label.setText(message)
        if ok:
            QMessageBox.information(self, "Cloud Sync", message)
        else:
            QMessageBox.critical(self, "Cloud Sync Failed", message)

    def sync_cloud_now(self):
        enabled, failover_enabled, host, port, database, username, password, sslmode, *_ = self._cloud_values()
        if not host:
            QMessageBox.warning(self, "Cloud Sync", "Please enter the Aiven host.")
            return
        if self._sync_thread and self._sync_thread.isRunning():
            QMessageBox.information(self, "Cloud Sync", "Cloud sync is already running.")
            return

        from utils.db_connection_config import build_cloud_database_url

        url = build_cloud_database_url(host, port, database, username, password, sslmode)
        self.cloud_status_label.setText("Running cloud sync...")
        self._set_cloud_action_buttons_enabled(False)

        self._sync_progress = QProgressDialog(
            "Preparing cloud sync...",
            None,
            0,
            0,
            self,
        )
        self._sync_progress.setWindowTitle("Cloud Sync")
        self._sync_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._sync_progress.setMinimumDuration(0)
        self._sync_progress.setAutoClose(False)
        self._sync_progress.setAutoReset(False)
        self._sync_progress.setLabelText("Uploading local POS data to Aiven PostgreSQL...")
        self._sync_progress.show()

        self._sync_thread = QThread(self)
        self._sync_worker = CloudSyncWorker(url, action="sync")
        self._sync_worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._sync_worker.run)
        self._sync_worker.finished.connect(self._on_cloud_sync_finished)
        self._sync_worker.finished.connect(self._sync_thread.quit)
        self._sync_worker.finished.connect(self._sync_worker.deleteLater)
        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.finished.connect(self._clear_cloud_sync_thread)
        self._sync_thread.start()

    def pull_cloud_now(self):
        enabled, failover_enabled, host, port, database, username, password, sslmode, *_ = self._cloud_values()
        if not host:
            QMessageBox.warning(self, "Cloud Pull", "Please enter the Aiven host.")
            return
        if self._sync_thread and self._sync_thread.isRunning():
            QMessageBox.information(self, "Cloud Pull", "A cloud operation is already running.")
            return
        answer = QMessageBox.warning(
            self,
            "Pull from Cloud",
            "This will copy Aiven cloud data into this local POS database. "
            "Cloud rows will overwrite matching local rows by ID. "
            "Use this after the server PC was offline and clients used cloud mode.\n\n"
            "A local SQLite backup will be created first when possible. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        from utils.db_connection_config import build_cloud_database_url

        url = build_cloud_database_url(host, port, database, username, password, sslmode)
        self.cloud_status_label.setText("Pulling cloud data into local POS...")
        self._set_cloud_action_buttons_enabled(False)

        self._sync_progress = QProgressDialog(
            "Preparing cloud pull...",
            None,
            0,
            0,
            self,
        )
        self._sync_progress.setWindowTitle("Cloud Pull")
        self._sync_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._sync_progress.setMinimumDuration(0)
        self._sync_progress.setAutoClose(False)
        self._sync_progress.setAutoReset(False)
        self._sync_progress.setLabelText("Downloading Aiven PostgreSQL data into the local POS database...")
        self._sync_progress.show()

        self._sync_thread = QThread(self)
        self._sync_worker = CloudSyncWorker(url, action="pull")
        self._sync_worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._sync_worker.run)
        self._sync_worker.finished.connect(self._on_cloud_sync_finished)
        self._sync_worker.finished.connect(self._sync_thread.quit)
        self._sync_worker.finished.connect(self._sync_worker.deleteLater)
        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.finished.connect(self._clear_cloud_sync_thread)
        self._sync_thread.start()

    def _set_cloud_action_buttons_enabled(self, enabled):
        self.btn_sync_now.setEnabled(enabled)
        self.btn_pull_cloud.setEnabled(enabled)
        self.btn_test_cloud.setEnabled(enabled)

    def _on_cloud_sync_finished(self, ok, message):
        if self._sync_progress:
            self._sync_progress.close()
            self._sync_progress = None
        self._set_cloud_action_buttons_enabled(True)
        self.cloud_status_label.setText(message)
        if ok:
            QMessageBox.information(self, "Cloud Sync", message)
        else:
            QMessageBox.critical(self, "Cloud Sync Failed", message)

    def _clear_cloud_sync_thread(self):
        self._sync_thread = None
        self._sync_worker = None

    def save_settings(self):
        host, port, database, username, password = self._values()
        if not host:
            QMessageBox.warning(self, "Database Connection", "Please enter the server IP or host.")
            return
        (
            cloud_enabled,
            failover_enabled,
            cloud_host,
            cloud_port,
            cloud_database,
            cloud_username,
            cloud_password,
            cloud_sslmode,
            cloud_interval,
            branch_id,
            device_id,
        ) = self._cloud_values()
        if cloud_enabled and not cloud_host:
            QMessageBox.warning(self, "Cloud Sync", "Please enter the Aiven host or disable cloud sync.")
            return
        if failover_enabled and not cloud_host:
            QMessageBox.warning(self, "Client Failover", "Please enter the Aiven host or disable cloud failover.")
            return
        env_path = save_database_config(host, port, database, username, password)
        save_cloud_sync_config(
            cloud_enabled,
            cloud_host,
            cloud_port,
            cloud_database,
            cloud_username,
            cloud_password,
            cloud_sslmode,
            cloud_interval,
            branch_id,
            device_id,
        )
        save_database_failover_config(
            failover_enabled,
            cloud_host,
            cloud_port,
            cloud_database,
            cloud_username,
            cloud_password,
            cloud_sslmode,
        )
        QMessageBox.information(
            self,
            "Database Connection",
            f"Saved to {env_path}\n\nPlease restart the app.",
        )

    def retranslateUi(self):
        pass
