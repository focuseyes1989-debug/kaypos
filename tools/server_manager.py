"""Kay POS Server Manager GUI.

This tool is intended to run on the Server PC. It keeps server-side setup and
operations separate from the cashier/client app.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import config
from models.database import connect_db, safe_initialize_database
from utils.db_connection_config import (
    DEFAULT_DB_NAME,
    DEFAULT_DB_PORT,
    DEFAULT_DB_USER,
    load_database_config,
    save_database_config,
    test_database_connection,
)
from utils.env_loader import load_project_env
from utils.product_image_store import save_product_image_blob


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class ServerManagerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kay POS Server Manager")
        self.resize(1080, 720)

        self.server_process: QProcess | None = None
        self.postgres_process: QProcess | None = None
        self.log_file: Path | None = None
        self.log_position = 0

        load_project_env()
        self._build_ui()
        self._load_config()
        self._refresh_all()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all)
        self.refresh_timer.start(5000)

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._database_tab(), "Database")
        tabs.addTab(self._server_tab(), "Server")
        tabs.addTab(self._activity_tab(), "Clients & Activity")
        tabs.addTab(self._logs_tab(), "Logs")
        self.setCentralWidget(tabs)

    def _database_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_box = QGroupBox("PostgreSQL Connection")
        form = QFormLayout(form_box)
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.database_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Server IP / Host", self.host_input)
        form.addRow("Port", self.port_input)
        form.addRow("Database", self.database_input)
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)

        buttons = QHBoxLayout()
        self.test_db_button = QPushButton("Test")
        self.save_db_button = QPushButton("Save")
        self.init_db_button = QPushButton("Initialize Schema")
        self.sync_images_button = QPushButton("Sync Product Images")
        self.test_db_button.clicked.connect(self.test_database)
        self.save_db_button.clicked.connect(self.save_database)
        self.init_db_button.clicked.connect(self.initialize_database)
        self.sync_images_button.clicked.connect(self.sync_product_images)
        for button in (
            self.test_db_button,
            self.save_db_button,
            self.init_db_button,
            self.sync_images_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch()

        self.db_status = QLabel("Database status: not checked")
        self.db_status.setWordWrap(True)
        self.db_output = QPlainTextEdit()
        self.db_output.setReadOnly(True)

        layout.addWidget(form_box)
        layout.addLayout(buttons)
        layout.addWidget(self.db_status)
        layout.addWidget(self.db_output, 1)
        return page

    def _server_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        pos_box = QGroupBox("Kay POS Browser/Cashier Server")
        pos_layout = QVBoxLayout(pos_box)
        form = QFormLayout()
        self.bind_host_input = QLineEdit("0.0.0.0")
        self.server_port_input = QSpinBox()
        self.server_port_input.setRange(1, 65535)
        self.server_port_input.setValue(8000)
        form.addRow("Bind Host", self.bind_host_input)
        form.addRow("Port", self.server_port_input)
        pos_layout.addLayout(form)

        pos_buttons = QHBoxLayout()
        self.start_server_button = QPushButton("Start")
        self.stop_server_button = QPushButton("Stop")
        self.restart_server_button = QPushButton("Restart")
        self.start_server_button.clicked.connect(self.start_pos_server)
        self.stop_server_button.clicked.connect(self.stop_pos_server)
        self.restart_server_button.clicked.connect(self.restart_pos_server)
        pos_buttons.addWidget(self.start_server_button)
        pos_buttons.addWidget(self.stop_server_button)
        pos_buttons.addWidget(self.restart_server_button)
        pos_buttons.addStretch()
        pos_layout.addLayout(pos_buttons)
        self.server_status = QLabel("Server status: stopped")
        pos_layout.addWidget(self.server_status)

        pg_box = QGroupBox("PostgreSQL Windows Service")
        pg_layout = QVBoxLayout(pg_box)
        pg_form = QFormLayout()
        self.pg_service_input = QLineEdit("postgresql-x64-18")
        pg_form.addRow("Service Name", self.pg_service_input)
        pg_layout.addLayout(pg_form)
        pg_buttons = QHBoxLayout()
        self.pg_start_button = QPushButton("Start DB Service")
        self.pg_stop_button = QPushButton("Stop DB Service")
        self.pg_restart_button = QPushButton("Restart DB Service")
        self.pg_start_button.clicked.connect(lambda: self.run_postgres_service_command("Start-Service"))
        self.pg_stop_button.clicked.connect(lambda: self.run_postgres_service_command("Stop-Service"))
        self.pg_restart_button.clicked.connect(self.restart_postgres_service)
        pg_buttons.addWidget(self.pg_start_button)
        pg_buttons.addWidget(self.pg_stop_button)
        pg_buttons.addWidget(self.pg_restart_button)
        pg_buttons.addStretch()
        pg_layout.addLayout(pg_buttons)

        self.server_output = QPlainTextEdit()
        self.server_output.setReadOnly(True)

        layout.addWidget(pos_box)
        layout.addWidget(pg_box)
        layout.addWidget(self.server_output, 1)
        return page

    def _activity_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.stats_label = QLabel("Stats: not loaded")
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_activity)
        top.addWidget(self.stats_label)
        top.addStretch()
        top.addWidget(refresh_button)
        layout.addLayout(top)

        self.activity_table = QTableWidget(0, 5)
        self.activity_table.setHorizontalHeaderLabels(["Time", "User", "Action", "Details", "IP"])
        self.activity_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.activity_table, 1)
        return page

    def _logs_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.log_path_label = QLabel("Log file: not selected")
        refresh_button = QPushButton("Refresh Logs")
        refresh_button.clicked.connect(self.refresh_logs)
        top.addWidget(self.log_path_label)
        top.addStretch()
        top.addWidget(refresh_button)
        layout.addLayout(top)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output, 1)
        return page

    def _load_config(self) -> None:
        cfg = load_database_config()
        self.host_input.setText(cfg.get("host") or local_ip())
        self.port_input.setValue(int(cfg.get("port") or DEFAULT_DB_PORT))
        self.database_input.setText(cfg.get("database") or DEFAULT_DB_NAME)
        self.username_input.setText(cfg.get("username") or DEFAULT_DB_USER)
        self.password_input.setText(cfg.get("password") or "")

    def _database_values(self):
        return (
            self.host_input.text().strip(),
            self.port_input.value(),
            self.database_input.text().strip() or DEFAULT_DB_NAME,
            self.username_input.text().strip() or DEFAULT_DB_USER,
            self.password_input.text(),
        )

    def append_db_output(self, text: str) -> None:
        self.db_output.appendPlainText(text)

    def append_server_output(self, text: str) -> None:
        self.server_output.appendPlainText(text.rstrip())

    def test_database(self) -> None:
        ok, message = test_database_connection(*self._database_values())
        self.db_status.setText(f"Database status: {'connected' if ok else 'failed'}")
        self.append_db_output(message)
        if not ok:
            QMessageBox.warning(self, "Database Test Failed", message)

    def save_database(self) -> None:
        env_path = save_database_config(*self._database_values())
        self.append_db_output(f"Saved PostgreSQL config to {env_path}")
        self.test_database()

    def initialize_database(self) -> None:
        save_database_config(*self._database_values())
        os.environ["ZAY_POS_DB_BACKEND"] = "postgres"
        ok = safe_initialize_database()
        self.append_db_output("Schema initialized successfully." if ok else "Schema initialization failed.")
        self.refresh_activity()

    def sync_product_images(self) -> None:
        save_database_config(*self._database_values())
        os.environ["ZAY_POS_DB_BACKEND"] = "postgres"
        if not safe_initialize_database():
            self.append_db_output("Cannot sync images because schema initialization failed.")
            return

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, image
            FROM products
            WHERE image IS NOT NULL
              AND image != ''
              AND image_data IS NULL
            ORDER BY id
        """)
        rows = cursor.fetchall()
        synced = 0
        for product_id, image_path in rows:
            cursor.execute("SELECT image_data FROM products WHERE id = ?", (product_id,))
            before = cursor.fetchone()
            save_product_image_blob(cursor, product_id, image_path)
            cursor.execute("SELECT image_data FROM products WHERE id = ?", (product_id,))
            after = cursor.fetchone()
            if (not before or before[0] is None) and after and after[0] is not None:
                synced += 1
        conn.commit()
        conn.close()
        self.append_db_output(f"Product image sync complete. synced={synced}, checked={len(rows)}")

    def start_pos_server(self) -> None:
        if self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning:
            self.append_server_output("POS server is already running.")
            return

        self.server_process = QProcess(self)
        self.server_process.setWorkingDirectory(str(PROJECT_ROOT))
        self.server_process.setProgram(sys.executable)
        self.server_process.setArguments([
            "run_pos_server.py",
            "--host",
            self.bind_host_input.text().strip() or "0.0.0.0",
            "--port",
            str(self.server_port_input.value()),
        ])
        self.server_process.readyReadStandardOutput.connect(self._read_server_stdout)
        self.server_process.readyReadStandardError.connect(self._read_server_stderr)
        self.server_process.finished.connect(self._server_finished)
        self.server_process.start()
        self.server_status.setText(
            f"Server status: starting. Network URL: http://{local_ip()}:{self.server_port_input.value()}"
        )

    def stop_pos_server(self) -> None:
        if not self.server_process or self.server_process.state() == QProcess.ProcessState.NotRunning:
            self.server_status.setText("Server status: stopped")
            return
        self.server_process.terminate()
        if not self.server_process.waitForFinished(3000):
            self.server_process.kill()
        self.server_status.setText("Server status: stopped")

    def restart_pos_server(self) -> None:
        self.stop_pos_server()
        self.start_pos_server()

    def _read_server_stdout(self) -> None:
        if not self.server_process:
            return
        data = bytes(self.server_process.readAllStandardOutput()).decode(errors="ignore")
        if data:
            self.append_server_output(data)

    def _read_server_stderr(self) -> None:
        if not self.server_process:
            return
        data = bytes(self.server_process.readAllStandardError()).decode(errors="ignore")
        if data:
            self.append_server_output(data)

    def _server_finished(self) -> None:
        self.server_status.setText("Server status: stopped")
        self.append_server_output("POS server stopped.")

    def run_postgres_service_command(self, command: str) -> None:
        service = self.pg_service_input.text().strip()
        if not service:
            QMessageBox.warning(self, "Missing Service Name", "Enter the PostgreSQL service name.")
            return
        process = QProcess(self)
        process.setProgram("powershell")
        process.setArguments(["-NoProfile", "-Command", f"{command} -Name '{service}'"])
        process.readyReadStandardOutput.connect(
            lambda: self.append_server_output(bytes(process.readAllStandardOutput()).decode(errors="ignore"))
        )
        process.readyReadStandardError.connect(
            lambda: self.append_server_output(bytes(process.readAllStandardError()).decode(errors="ignore"))
        )
        process.finished.connect(lambda: self.append_server_output(f"{command} completed for {service}."))
        self.postgres_process = process
        process.start()

    def restart_postgres_service(self) -> None:
        service = self.pg_service_input.text().strip()
        if not service:
            QMessageBox.warning(self, "Missing Service Name", "Enter the PostgreSQL service name.")
            return
        process = QProcess(self)
        process.setProgram("powershell")
        process.setArguments(["-NoProfile", "-Command", f"Restart-Service -Name '{service}'"])
        process.readyReadStandardOutput.connect(
            lambda: self.append_server_output(bytes(process.readAllStandardOutput()).decode(errors="ignore"))
        )
        process.readyReadStandardError.connect(
            lambda: self.append_server_output(bytes(process.readAllStandardError()).decode(errors="ignore"))
        )
        process.finished.connect(lambda: self.append_server_output(f"Restart-Service completed for {service}."))
        self.postgres_process = process
        process.start()

    def refresh_activity(self) -> None:
        try:
            conn = connect_db()
            cursor = conn.cursor()
            counts = {}
            for table in ("products", "users", "sales", "customers"):
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            self.stats_label.setText(
                "Stats: "
                f"Products {counts['products']} | Users {counts['users']} | "
                f"Sales {counts['sales']} | Customers {counts['customers']}"
            )

            cursor.execute("""
                SELECT created_at, username, action, details, ip_address
                FROM user_activity_log
                ORDER BY created_at DESC
                LIMIT 100
            """)
            rows = cursor.fetchall()
            conn.close()
            self.activity_table.setRowCount(0)
            for row_values in rows:
                row_index = self.activity_table.rowCount()
                self.activity_table.insertRow(row_index)
                for col, value in enumerate(row_values):
                    item = QTableWidgetItem(str(value or ""))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.activity_table.setItem(row_index, col, item)
        except Exception as exc:
            self.stats_label.setText(f"Stats: unavailable ({exc})")

    def refresh_logs(self) -> None:
        log_dir = Path(config.LOG_DIR)
        candidates = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            self.log_path_label.setText(f"Log file: no .log files in {log_dir}")
            return
        if self.log_file != candidates[0]:
            self.log_file = candidates[0]
            self.log_position = 0
            self.log_output.clear()
            self.log_path_label.setText(f"Log file: {self.log_file}")

        try:
            text = self.log_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            self.log_output.appendPlainText(f"Could not read log: {exc}")
            return

        if self.log_position == 0:
            lines = text.splitlines()[-500:]
            self.log_output.setPlainText("\n".join(lines))
        elif len(text) > self.log_position:
            self.log_output.appendPlainText(text[self.log_position :])
        self.log_position = len(text)

    def _refresh_all(self) -> None:
        self.refresh_activity()
        self.refresh_logs()
        if self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning:
            self.server_status.setText(
                f"Server status: running. Network URL: http://{local_ip()}:{self.server_port_input.value()}"
            )

    def closeEvent(self, event) -> None:
        if self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.question(
                self,
                "Stop POS Server?",
                "POS server is still running. Stop it before closing Server Manager?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.stop_pos_server()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = ServerManagerWindow()
    window.show()
    return app.exec()
