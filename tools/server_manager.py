"""Kay POS Server Manager GUI.

This tool is intended to run on the Server PC. It keeps server-side setup and
operations separate from the cashier/client app.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import uuid
import webbrowser
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Server Manager is a Windows utility.
    winreg = None

from PyQt6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
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


POSTGRES_INSTALLER_URL = "https://www.enterprisedb.com/downloads/postgres-postgresql-downloads"
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AUTO_START_FILE_NAME = "KayPOSServerManager.cmd"
AUTO_START_REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTO_START_APPROVED_PATH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
AUTO_START_REGISTRY_NAME = "Kay POS Server Manager"
DEFAULT_BROWSER_SERVER_PORT = 8000


def auto_start_file_path() -> Path:
    appdata = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / AUTO_START_FILE_NAME


def auto_start_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --auto-start --minimized'
    launcher_path = PROJECT_ROOT / "server_manager.py"
    return f'"{sys.executable}" "{launcher_path}" --auto-start --minimized'


def auto_start_registry_state() -> str:
    """Return missing, enabled, or disabled for the current user's startup entry."""
    if winreg is None:
        return "missing"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_START_REGISTRY_PATH) as key:
            winreg.QueryValueEx(key, AUTO_START_REGISTRY_NAME)
    except FileNotFoundError:
        return "missing"

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_START_APPROVED_PATH) as key:
            approval, _ = winreg.QueryValueEx(key, AUTO_START_REGISTRY_NAME)
        if isinstance(approval, bytes) and approval and approval[0] == 3:
            return "disabled"
    except FileNotFoundError:
        pass
    return "enabled"


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def local_subnet() -> str:
    ip = local_ip()
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["0"]) + "/24"
    return "192.168.0.0/16"


def can_bind_port(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


class ServerManagerWindow(QMainWindow):
    def __init__(self, auto_start=None) -> None:
        super().__init__()
        self.setWindowTitle("Kay POS Server Manager")
        self.setMinimumSize(1000, 680)
        self.resize(1280, 820)

        self.server_process: QProcess | None = None
        self.postgres_process: QProcess | None = None
        self.log_file: Path | None = None
        self.log_position = 0
        self.settings = QSettings("KAY POS", "Server Manager")
        self._allow_close = False

        load_project_env()
        self._build_ui()
        self._setup_system_tray()
        self._load_config()
        self._refresh_all()

        should_auto_start = (
            bool(auto_start)
            if auto_start is not None
            else self.settings.value("start_services_on_open", True, type=bool)
        )
        if should_auto_start:
            QTimer.singleShot(1800, self._auto_start_services)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all)
        self.refresh_timer.start(5000)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(238)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(24, 30, 24, 24)
        side.setSpacing(8)

        brand_row = QHBoxLayout()
        mark = QLabel("S")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(44, 44)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand = QLabel("KAY")
        brand.setObjectName("Brand")
        brand_row.addWidget(mark)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        side.addLayout(brand_row)
        suite = QLabel("SERVER CONTROL")
        suite.setObjectName("Eyebrow")
        side.addWidget(suite)
        side.addSpacing(28)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        pages = (
            ("Setup", "Initial configuration", self._wizard_tab()),
            ("Database", "Connection and schema", self._database_tab()),
            ("Services", "POS, car and PostgreSQL", self._server_tab()),
            ("Printers", "LAN/Wi-Fi printer agents", self._printers_tab()),
            ("Activity", "Client request history", self._activity_tab()),
            ("Logs", "Runtime diagnostics", self._logs_tab()),
        )
        self.nav_buttons = []
        for index, (name, description, page) in enumerate(pages):
            self.tabs.addTab(page, name)
            button = QPushButton(f"{index + 1:02d}   {name}")
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setToolTip(description)
            button.clicked.connect(lambda checked=False, page_index=index: self._select_page(page_index))
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch()
        machine = QLabel(f"SERVER PC\n{local_ip()}")
        machine.setObjectName("SidebarInfo")
        side.addWidget(machine)
        shell.addWidget(sidebar)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(18)

        header = QFrame()
        header.setObjectName("Header")
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setHorizontalSpacing(18)

        eyebrow = QLabel("SERVER WORKSPACE")
        eyebrow.setObjectName("Eyebrow")
        self.page_title = QLabel("Setup")
        self.page_title.setObjectName("HeaderTitle")
        title = QLabel("Kay POS Server Manager")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Setup PostgreSQL, manage services, and monitor client activity from the Server PC.")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setWordWrap(True)
        self.header_ip_label = QLabel(f"Server IP: {local_ip()}")
        self.header_ip_label.setObjectName("InfoChip")
        self.header_db_label = QLabel("Database: not checked")
        self.header_db_label.setObjectName("InfoChip")

        header_layout.addWidget(eyebrow, 0, 0)
        header_layout.addWidget(title, 1, 0)
        header_layout.addWidget(subtitle, 2, 0)
        header_layout.addWidget(self.header_ip_label, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.header_db_label, 1, 1, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        header_layout.setColumnStretch(0, 1)

        layout.addWidget(header)
        layout.addWidget(self.tabs, 1)
        shell.addWidget(content, 1)
        self.setCentralWidget(root)
        self._apply_stylesheet()
        self._select_page(2)

    def _select_page(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget#Root {
                background: #0d111b;
                color: #edf2ff;
                font-family: "Segoe UI", "Myanmar Text";
                font-size: 10pt;
            }
            QWidget {
                color: #edf2ff;
                font-family: "Segoe UI", "Myanmar Text";
                font-size: 10pt;
            }
            QFrame#Sidebar {
                background: #111724;
                border-right: 1px solid #252d3d;
            }
            QLabel#BrandMark {
                background: #f3a64a;
                color: white;
                border-radius: 13px;
                font-size: 18pt;
                font-weight: 800;
            }
            QLabel#Brand {
                color: white;
                font-size: 19pt;
                font-weight: 800;
            }
            QLabel#Eyebrow {
                color: #8995ad;
                font-size: 9pt;
                font-weight: 700;
            }
            QLabel#SidebarInfo {
                color: #8995ad;
                line-height: 1.4;
            }
            QPushButton#NavButton {
                text-align: left;
                min-height: 44px;
                border: 0;
                border-radius: 10px;
                background: transparent;
                color: #aeb8ca;
                padding: 0 13px;
                font-weight: 650;
            }
            QPushButton#NavButton:hover {
                background: #1c2535;
                color: white;
            }
            QPushButton#NavButton:checked {
                background: #2a2430;
                color: #ffc46d;
                border-left: 3px solid #f3a64a;
            }
            QFrame#Header {
                background: transparent;
                border: 0;
            }
            QGroupBox {
                background: #151c2a;
                border: 1px solid #293348;
                border-radius: 14px;
            }
            QLabel#HeaderTitle {
                font-size: 24pt;
                font-weight: 800;
                color: white;
            }
            QLabel#HeaderSubtitle {
                color: #99a4ba;
            }
            QLabel#InfoChip, QLabel#StatusChip {
                background: #182231;
                border: 1px solid #2b3a50;
                border-radius: 9px;
                padding: 6px 10px;
                color: #b9c5d9;
            }
            QLabel#Note {
                color: #aeb9cd;
                background: #121925;
                border: 1px solid #253044;
                border-radius: 9px;
                padding: 8px 10px;
            }
            QGroupBox {
                margin-top: 12px;
                padding: 16px 14px 14px 14px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 7px;
                color: #f3b45f;
                background: #151c2a;
            }
            QLineEdit, QSpinBox {
                background: #0f1520;
                color: #edf2ff;
                border: 1px solid #303b50;
                border-radius: 8px;
                padding: 6px 8px;
                min-height: 24px;
                selection-background-color: #d8892f;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #f3a64a;
            }
            QCheckBox {
                color: #c1cada;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
            }
            QPushButton {
                background: #e89a3b;
                color: #ffffff;
                border: 0;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f3ad55;
            }
            QPushButton:disabled {
                background: #303847;
                color: #707b91;
            }
            QMessageBox {
                background: #151c2a;
                color: #edf2ff;
            }
            QMessageBox QLabel {
                background: transparent;
                color: #edf2ff;
            }
            QMessageBox QLabel#qt_msgbox_label,
            QMessageBox QLabel#qt_msgbox_informativelabel {
                min-width: 320px;
                padding: 8px 10px;
            }
            QMessageBox QPushButton {
                min-width: 84px;
                min-height: 36px;
                padding: 4px 14px;
                background: #e89a3b;
                color: #ffffff;
                border: 1px solid #e89a3b;
                border-radius: 8px;
                font-weight: 650;
            }
            QMessageBox QPushButton:hover {
                background: #f3ad55;
                border-color: #f3ad55;
            }
            QMessageBox QPushButton:pressed {
                background: #cf8128;
                border-color: #cf8128;
            }
            QPlainTextEdit, QTableWidget {
                background: #090e17;
                color: #dbeafe;
                border: 1px solid #283448;
                border-radius: 10px;
                padding: 8px;
                font-family: Consolas, "Courier New", monospace;
                selection-background-color: #774d25;
            }
            QTabWidget::pane {
                border: 0;
                background: transparent;
            }
            QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {
                background: transparent;
                border: 0;
            }
            QWidget#ScrollContent {
                background: #0d111b;
            }
            QHeaderView::section {
                background: #182231;
                color: #aeb9cd;
                border: 0;
                border-bottom: 1px solid #303b50;
                padding: 8px;
                font-weight: 700;
            }
            QScrollBar:vertical {
                background: #101722;
                width: 11px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3a465a;
                border-radius: 5px;
                min-height: 28px;
            }
        """)

    def _note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Note")
        label.setWordWrap(True)
        return label

    def _status_chip(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("StatusChip")
        label.setWordWrap(True)
        return label

    def _set_chip(self, label: QLabel, text: str, tone: str = "neutral") -> None:
        colors = {
            "neutral": ("#182231", "#b9c5d9", "#2b3a50"),
            "ok": ("#14392f", "#79e2bb", "#245744"),
            "warn": ("#402f1d", "#ffc46d", "#6b4a25"),
            "bad": ("#42242d", "#ff9ca7", "#713542"),
        }
        bg, fg, border = colors.get(tone, colors["neutral"])
        label.setText(text)
        label.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; "
            "border-radius: 6px; padding: 6px 10px;"
        )

    def _update_server_buttons(self) -> None:
        running = bool(self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning)
        self.start_server_button.setEnabled(not running)
        self.stop_server_button.setEnabled(running)
        self.restart_server_button.setEnabled(running)

    def _wizard_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        page = QWidget()
        page.setObjectName("ScrollContent")
        page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        page.setMinimumWidth(0)
        page.setMinimumHeight(920)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._note(
            "Run this setup on the Server PC. Use Administrator mode for network config and firewall steps."
        ))

        install_box = QGroupBox("1. PostgreSQL Install / Detect")
        install_box.setMinimumHeight(150)
        install_layout = QVBoxLayout(install_box)
        install_buttons = QHBoxLayout()
        detect_button = QPushButton("Detect PostgreSQL")
        installer_button = QPushButton("Open PostgreSQL Download")
        detect_button.clicked.connect(self.detect_postgresql)
        installer_button.clicked.connect(lambda: webbrowser.open(POSTGRES_INSTALLER_URL))
        install_buttons.addWidget(detect_button)
        install_buttons.addWidget(installer_button)
        install_buttons.addStretch()
        self.detect_status = QLabel("PostgreSQL status: not checked")
        self.detect_status.setWordWrap(True)
        install_layout.addLayout(install_buttons)
        install_layout.addWidget(self.detect_status)
        install_layout.addStretch()

        setup_box = QGroupBox("2. Create Kay POS Database")
        setup_box.setMinimumHeight(430)
        setup_layout = QVBoxLayout(setup_box)
        setup_form = QFormLayout()
        setup_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        setup_form.setVerticalSpacing(8)
        self.superuser_input = QLineEdit("postgres")
        self.super_password_input = QLineEdit()
        self.super_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.wizard_host_input = QLineEdit("127.0.0.1")
        self.wizard_port_input = QSpinBox()
        self.wizard_port_input.setRange(1, 65535)
        self.wizard_port_input.setValue(DEFAULT_DB_PORT)
        self.wizard_database_input = QLineEdit(DEFAULT_DB_NAME)
        self.wizard_username_input = QLineEdit(DEFAULT_DB_USER)
        self.wizard_password_input = QLineEdit("lonepair")
        self.wizard_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.super_password_input.setPlaceholderText("PostgreSQL installer password")
        setup_form.addRow("Postgres Admin User", self.superuser_input)
        setup_form.addRow("Postgres Admin Password", self.super_password_input)
        setup_form.addRow("Admin Setup Host", self.wizard_host_input)
        setup_form.addRow("Port", self.wizard_port_input)
        setup_form.addRow("Kay POS Database", self.wizard_database_input)
        setup_form.addRow("Kay POS Username", self.wizard_username_input)
        setup_form.addRow("Kay POS Password", self.wizard_password_input)
        create_db_button = QPushButton("Create / Update Database and User")
        create_db_button.clicked.connect(self.create_wizard_database)
        setup_layout.addLayout(setup_form)
        setup_layout.addWidget(create_db_button)
        setup_layout.addStretch()

        network_box = QGroupBox("3. Network Access")
        network_box.setMinimumHeight(260)
        network_layout = QVBoxLayout(network_box)
        network_form = QFormLayout()
        network_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        network_form.setVerticalSpacing(8)
        default_pg_dir = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "PostgreSQL" / "18" / "data"
        self.pg_data_dir_input = QLineEdit(str(default_pg_dir))
        self.pg_data_dir_input.setPlaceholderText("Example: C:\\Program Files\\PostgreSQL\\18\\data")
        self.allowed_subnet_input = QLineEdit(local_subnet())
        self.listen_addresses_input = QLineEdit("*")
        network_form.addRow("PostgreSQL Data Folder", self.pg_data_dir_input)
        network_form.addRow("Allowed Client Subnet", self.allowed_subnet_input)
        network_form.addRow("Listen Addresses", self.listen_addresses_input)
        network_buttons = QHBoxLayout()
        config_network_button = QPushButton("Configure pg_hba/postgresql.conf")
        firewall_button = QPushButton("Open Firewall Port 5432")
        config_network_button.clicked.connect(self.configure_network_files)
        firewall_button.clicked.connect(self.open_postgres_firewall_port)
        network_buttons.addWidget(config_network_button)
        network_buttons.addWidget(firewall_button)
        network_buttons.addStretch()
        network_layout.addLayout(network_form)
        network_layout.addLayout(network_buttons)
        network_layout.addStretch()

        finish_box = QGroupBox("4. Initialize Kay POS")
        finish_box.setMinimumHeight(120)
        finish_layout = QHBoxLayout(finish_box)
        save_test_button = QPushButton("Save App Config and Test")
        init_schema_button = QPushButton("Initialize Schema")
        finish_button = QPushButton("Show Client Settings")
        save_test_button.clicked.connect(self.save_wizard_to_app_config)
        init_schema_button.clicked.connect(self.initialize_database)
        finish_button.clicked.connect(self.show_client_settings)
        finish_layout.addWidget(save_test_button)
        finish_layout.addWidget(init_schema_button)
        finish_layout.addWidget(finish_button)
        finish_layout.addStretch()

        self.wizard_output = QPlainTextEdit()
        self.wizard_output.setReadOnly(True)
        self.wizard_output.setPlaceholderText("Setup progress and command output will appear here.")
        self.wizard_output.setMinimumHeight(150)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        left_column.addWidget(install_box)
        left_column.addWidget(setup_box)
        left_column.addStretch(1)

        right_column.addWidget(network_box)
        right_column.addWidget(finish_box)
        right_column.addStretch(1)

        columns.addLayout(left_column, 1)
        columns.addLayout(right_column, 1)

        layout.addLayout(columns)
        layout.addWidget(self.wizard_output, 1)
        scroll.setWidget(page)
        return scroll

    def _database_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._note(
            "Server PC should normally use 127.0.0.1 here. Client PCs should use the Server IP shown in Setup > Show Client Settings."
        ))

        form_box = QGroupBox("PostgreSQL Connection")
        form = QFormLayout(form_box)
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.database_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.host_input.setPlaceholderText("127.0.0.1 on Server PC")
        self.database_input.setPlaceholderText(DEFAULT_DB_NAME)
        self.username_input.setPlaceholderText(DEFAULT_DB_USER)
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

        self.db_status = self._status_chip("Database status: not checked")
        self.db_output = QPlainTextEdit()
        self.db_output.setReadOnly(True)
        self.db_output.setPlaceholderText("Database test, schema initialization, and image sync results will appear here.")

        layout.addWidget(form_box)
        layout.addLayout(buttons)
        layout.addWidget(self.db_status)
        layout.addWidget(self.db_output, 1)
        return page

    def _server_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        page = QWidget()
        page.setObjectName("ScrollContent")
        page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        page.setMinimumWidth(0)
        page.setMinimumHeight(760)
        layout = QGridLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        layout.addWidget(self._note(
            f"Mobile barcode scanning needs HTTPS. Use https://{local_ip()}:{DEFAULT_BROWSER_SERVER_PORT}/mobile/products after starting with HTTPS enabled."
        ), 0, 0, 1, 2)

        pos_box = QGroupBox("Kay POS Browser/Cashier Server")
        pos_box.setMinimumHeight(230)
        pos_layout = QVBoxLayout(pos_box)
        form = QFormLayout()
        self.bind_host_input = QLineEdit("0.0.0.0")
        self.server_port_input = QSpinBox()
        self.server_port_input.setRange(1, 65535)
        self.server_port_input.setValue(DEFAULT_BROWSER_SERVER_PORT)
        self.https_server_checkbox = QCheckBox("Enable HTTPS for mobile camera/barcode scanning")
        self.https_server_checkbox.setChecked(True)
        form.addRow("Bind Host", self.bind_host_input)
        form.addRow("Port", self.server_port_input)
        form.addRow("HTTPS", self.https_server_checkbox)
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
        self.server_status = self._status_chip("Server status: stopped")
        pos_layout.addWidget(self.server_status)

        car_box = QGroupBox("Car Management LAN Service")
        car_box.setMinimumHeight(270)
        car_layout = QVBoxLayout(car_box)
        car_form = QFormLayout()
        self.car_server_enabled_checkbox = QCheckBox("Start with the POS server")
        self.car_server_enabled_checkbox.setChecked(True)
        self.car_server_port_input = QSpinBox()
        self.car_server_port_input.setRange(1, 65535)
        self.car_server_port_input.setValue(12345)
        car_form.addRow("Enabled", self.car_server_enabled_checkbox)
        car_form.addRow("TCP Port", self.car_server_port_input)
        car_layout.addLayout(car_form)
        car_layout.addWidget(self._note(
            f"Car clients on this LAN/Wi-Fi should connect to {local_ip()}:12345. "
            "The service uses the same local PostgreSQL database as KAY POS."
        ))
        self.car_server_status = self._status_chip("Car server status: stopped")
        car_layout.addWidget(self.car_server_status)
        car_actions = QHBoxLayout()
        self.import_car_database_button = QPushButton("Import Legacy Database")
        self.import_car_database_button.clicked.connect(self.import_car_database)
        car_actions.addWidget(self.import_car_database_button)
        car_actions.addStretch()
        car_layout.addLayout(car_actions)
        self.car_import_status = self._status_chip("Car database import: not started")
        car_layout.addWidget(self.car_import_status)

        startup_box = QGroupBox("Windows Auto Start")
        startup_box.setMinimumHeight(230)
        startup_layout = QVBoxLayout(startup_box)
        self.start_services_on_open_checkbox = QCheckBox(
            "Start services when Server Manager opens"
        )
        self.start_services_on_open_checkbox.setChecked(
            self.settings.value("start_services_on_open", True, type=bool)
        )
        self.start_services_on_open_checkbox.toggled.connect(self._save_service_auto_start_setting)
        startup_layout.addWidget(self.start_services_on_open_checkbox)
        startup_layout.addWidget(self._note(
            "After Windows login, open Server Manager minimized and automatically start the POS and Car services. "
            "The PostgreSQL Windows service should be configured as Automatic."
        ))
        startup_actions = QHBoxLayout()
        self.enable_auto_start_button = QPushButton("Enable Auto Start")
        self.disable_auto_start_button = QPushButton("Disable Auto Start")
        self.enable_auto_start_button.clicked.connect(self.enable_windows_auto_start)
        self.disable_auto_start_button.clicked.connect(self.disable_windows_auto_start)
        startup_actions.addWidget(self.enable_auto_start_button)
        startup_actions.addWidget(self.disable_auto_start_button)
        startup_actions.addStretch()
        startup_layout.addLayout(startup_actions)
        self.auto_start_status = self._status_chip("Windows auto start: not checked")
        startup_layout.addWidget(self.auto_start_status)

        pg_box = QGroupBox("PostgreSQL Windows Service")
        pg_box.setMinimumHeight(230)
        pg_layout = QVBoxLayout(pg_box)
        pg_form = QFormLayout()
        self.pg_service_input = QLineEdit("postgresql-x64-18")
        pg_form.addRow("Service Name", self.pg_service_input)
        pg_layout.addLayout(pg_form)
        pg_buttons = QHBoxLayout()
        self.pg_start_button = QPushButton("Start DB")
        self.pg_stop_button = QPushButton("Stop DB")
        self.pg_restart_button = QPushButton("Restart DB")
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
        self.server_output.setMinimumHeight(160)
        self.server_output.setPlaceholderText("Service output and PostgreSQL service command results will appear here.")

        layout.addWidget(pos_box, 1, 0)
        layout.addWidget(car_box, 1, 1)
        layout.addWidget(startup_box, 2, 0)
        layout.addWidget(pg_box, 2, 1)
        layout.addWidget(self.server_output, 3, 0, 1, 2)
        layout.setRowStretch(3, 1)
        scroll.setWidget(page)
        return scroll

    def _activity_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.stats_label = self._status_chip("Stats: not loaded")
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_activity)
        top.addWidget(self.stats_label)
        top.addStretch()
        top.addWidget(refresh_button)
        layout.addLayout(top)

        format_row = QHBoxLayout()
        self.print_paper_size = QComboBox()
        self.print_paper_size.addItems(["A4", "A5", "80mm", "58mm"])
        self.print_orientation = QComboBox()
        self.print_orientation.addItems(["Portrait", "Landscape"])
        self.print_copies = QSpinBox()
        self.print_copies.setRange(1, 99)
        self.print_copies.setValue(1)
        self.send_document_button = QPushButton("Print Document…")
        self.send_document_button.clicked.connect(self.send_printer_document)
        format_row.addWidget(QLabel("Paper"))
        format_row.addWidget(self.print_paper_size)
        format_row.addWidget(QLabel("Orientation"))
        format_row.addWidget(self.print_orientation)
        format_row.addWidget(QLabel("Copies"))
        format_row.addWidget(self.print_copies)
        format_row.addStretch()
        format_row.addWidget(self.send_document_button)
        layout.addLayout(format_row)

        self.activity_table = QTableWidget(0, 5)
        self.activity_table.setHorizontalHeaderLabels(["Time", "User", "Action", "Details", "IP"])
        self.activity_table.horizontalHeader().setStretchLastSection(True)
        self.activity_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.activity_table, 1)
        return page

    def _printers_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._note(
            f"Run printer_agent.py on every PC and point it to "
            f"https://{local_ip()}:{DEFAULT_BROWSER_SERVER_PORT} (use --insecure for the local certificate), "
            f"or http://{local_ip()}:{DEFAULT_BROWSER_SERVER_PORT} when HTTPS is disabled. "
            "Agents report installed Windows printers every 10 seconds."
        ))
        top = QHBoxLayout()
        self.printer_server_status = self._status_chip("Printer Server: registry not checked")
        self.send_test_print_button = QPushButton("Print Test Page")
        self.send_test_print_button.clicked.connect(self.send_printer_test_page)
        self.toggle_printer_agent_button = QPushButton("Enable / Disable PC")
        self.toggle_printer_agent_button.clicked.connect(self.toggle_selected_printer_agent)
        refresh_button = QPushButton("Refresh Printers")
        refresh_button.clicked.connect(self.refresh_printer_agents)
        top.addWidget(self.printer_server_status)
        top.addStretch()
        top.addWidget(self.toggle_printer_agent_button)
        top.addWidget(self.send_test_print_button)
        top.addWidget(refresh_button)
        layout.addLayout(top)

        self.printer_agents_table = QTableWidget(0, 7)
        self.printer_agents_table.setHorizontalHeaderLabels(
            ["PC", "IP Address", "Agent", "Printer", "Default", "Status", "Last Seen"]
        )
        self.printer_agents_table.horizontalHeader().setStretchLastSection(True)
        self.printer_agents_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.printer_agents_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.printer_agents_table, 1)

        jobs_top = QHBoxLayout()
        jobs_label = QLabel("Recent Print Jobs")
        jobs_label.setObjectName("HeaderSubtitle")
        self.retry_print_job_button = QPushButton("Retry Failed Job")
        self.retry_print_job_button.clicked.connect(self.retry_selected_print_job)
        jobs_top.addWidget(jobs_label)
        jobs_top.addStretch()
        jobs_top.addWidget(self.retry_print_job_button)
        layout.addLayout(jobs_top)
        self.printer_jobs_table = QTableWidget(0, 8)
        self.printer_jobs_table.setHorizontalHeaderLabels(
            ["Created", "PC", "Printer", "Type", "Status", "Attempts", "Error", "Job ID"]
        )
        self.printer_jobs_table.horizontalHeader().setStretchLastSection(True)
        self.printer_jobs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.printer_jobs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.printer_jobs_table, 1)
        return page

    def _logs_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.log_path_label = self._status_chip("Log file: not selected")
        refresh_button = QPushButton("Refresh Logs")
        refresh_button.clicked.connect(self.refresh_logs)
        top.addWidget(self.log_path_label)
        top.addStretch()
        top.addWidget(refresh_button)
        layout.addLayout(top)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Application logs will appear here after a log file is detected.")
        layout.addWidget(self.log_output, 1)
        return page

    def _load_config(self) -> None:
        cfg = load_database_config()
        self.host_input.setText(cfg.get("host") or local_ip())
        self.port_input.setValue(int(cfg.get("port") or DEFAULT_DB_PORT))
        self.database_input.setText(cfg.get("database") or DEFAULT_DB_NAME)
        self.username_input.setText(cfg.get("username") or DEFAULT_DB_USER)
        self.password_input.setText(cfg.get("password") or "")
        self.wizard_port_input.setValue(int(cfg.get("port") or DEFAULT_DB_PORT))
        self.wizard_database_input.setText(cfg.get("database") or DEFAULT_DB_NAME)
        self.wizard_username_input.setText(cfg.get("username") or DEFAULT_DB_USER)
        self.wizard_password_input.setText(cfg.get("password") or "lonepair")
        self.allowed_subnet_input.setText(local_subnet())
        self._set_chip(
            self.header_db_label,
            f"Database: {self.database_input.text()} @ {self.host_input.text()}:{self.port_input.value()}",
        )
        self._update_server_buttons()

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

    def append_wizard_output(self, text: str) -> None:
        self.wizard_output.appendPlainText(text.rstrip())

    def wizard_database_values(self):
        return (
            "127.0.0.1",
            self.wizard_port_input.value(),
            self.wizard_database_input.text().strip() or DEFAULT_DB_NAME,
            self.wizard_username_input.text().strip() or DEFAULT_DB_USER,
            self.wizard_password_input.text(),
        )

    def detect_postgresql(self) -> None:
        service_process = QProcess(self)
        service_process.setProgram("powershell")
        service_process.setArguments([
            "-NoProfile",
            "-Command",
            "Get-Service 'postgresql*' -ErrorAction SilentlyContinue | "
            "Select-Object Name,Status,DisplayName | Format-Table -AutoSize | Out-String",
        ])
        service_process.readyReadStandardOutput.connect(
            lambda: self._append_detect_output(service_process, False)
        )
        service_process.readyReadStandardError.connect(
            lambda: self._append_detect_output(service_process, True)
        )
        service_process.finished.connect(lambda: self.detect_status.setText("PostgreSQL status: detect completed"))
        self.detect_process = service_process
        service_process.start()

    def _append_detect_output(self, process: QProcess, is_error: bool) -> None:
        data = process.readAllStandardError() if is_error else process.readAllStandardOutput()
        text = bytes(data).decode(errors="ignore").strip()
        if text:
            self.append_wizard_output(text)
            if "postgresql" in text.lower():
                first_service = self._first_postgres_service_name(text)
                if first_service:
                    self.pg_service_input.setText(first_service)

    def _first_postgres_service_name(self, text: str) -> str:
        for line in text.splitlines():
            value = line.strip().split()
            if value and value[0].lower().startswith("postgresql"):
                return value[0]
        return ""

    def create_wizard_database(self) -> None:
        admin_user = self.superuser_input.text().strip() or "postgres"
        admin_password = self.super_password_input.text()
        requested_host = self.wizard_host_input.text().strip() or "127.0.0.1"
        port = self.wizard_port_input.value()
        db_name = self.wizard_database_input.text().strip() or DEFAULT_DB_NAME
        app_user = self.wizard_username_input.text().strip() or DEFAULT_DB_USER
        app_password = self.wizard_password_input.text()

        if not IDENTIFIER_RE.match(db_name) or not IDENTIFIER_RE.match(app_user):
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Database and username must use letters, numbers, and underscores only.",
            )
            return

        try:
            from models.database.postgres_adapter import import_postgres_driver

            driver_name, driver = import_postgres_driver()
            conn = self._connect_admin_postgres(driver, admin_user, admin_password, requested_host, port)
            if hasattr(conn, "autocommit"):
                conn.autocommit = True
            cursor = conn.cursor()
            password_sql = app_password.replace("'", "''")
            cursor.execute(f"SELECT 1 FROM pg_roles WHERE rolname = '{app_user}'")
            if cursor.fetchone():
                cursor.execute(f"ALTER ROLE {app_user} WITH LOGIN PASSWORD '{password_sql}'")
                self.append_wizard_output(f"Updated role: {app_user}")
            else:
                cursor.execute(f"CREATE ROLE {app_user} WITH LOGIN PASSWORD '{password_sql}'")
                self.append_wizard_output(f"Created role: {app_user}")

            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
            if not cursor.fetchone():
                cursor.execute(f"CREATE DATABASE {db_name} OWNER {app_user}")
                self.append_wizard_output(f"Created database: {db_name}")
            else:
                self.append_wizard_output(f"Database already exists: {db_name}")

            cursor.close()
            conn.close()

            app_conn = self._connect_admin_postgres(driver, admin_user, admin_password, requested_host, port, db_name)
            if hasattr(app_conn, "autocommit"):
                app_conn.autocommit = True
            app_cursor = app_conn.cursor()
            app_cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {app_user}")
            app_cursor.execute(f"GRANT ALL ON SCHEMA public TO {app_user}")
            app_cursor.execute(f"ALTER SCHEMA public OWNER TO {app_user}")
            app_cursor.close()
            app_conn.close()

            self.save_wizard_to_app_config()
            self.append_wizard_output("Database/user setup completed.")
        except Exception as exc:
            QMessageBox.warning(self, "Database Setup Failed", str(exc))
            self.append_wizard_output(f"Database setup failed: {exc}")

    def _connect_admin_postgres(
        self,
        driver,
        admin_user: str,
        admin_password: str,
        requested_host: str,
        port: int,
        database: str = "postgres",
    ):
        hosts = []
        for candidate in (requested_host, "127.0.0.1", "localhost"):
            if candidate and candidate not in hosts:
                hosts.append(candidate)
        last_error = None
        for host in hosts:
            try:
                conn = driver.connect(
                    dbname=database,
                    user=admin_user,
                    password=admin_password,
                    host=host,
                    port=port,
                )
                self.append_wizard_output(f"Connected to PostgreSQL database '{database}' via {host}.")
                return conn
            except Exception as exc:
                last_error = exc
                self.append_wizard_output(f"Admin connection to '{database}' via {host} failed: {exc}")
        raise last_error

    def save_wizard_to_app_config(self) -> None:
        host, port, database, username, password = self.wizard_database_values()
        self.host_input.setText(host)
        self.port_input.setValue(port)
        self.database_input.setText(database)
        self.username_input.setText(username)
        self.password_input.setText(password)
        env_path = save_database_config(host, port, database, username, password)
        self.append_wizard_output(f"Saved server-local Kay POS database config to {env_path}")
        self.test_database()

    def configure_network_files(self) -> None:
        data_dir = Path(self.pg_data_dir_input.text().strip())
        pg_hba = data_dir / "pg_hba.conf"
        postgresql_conf = data_dir / "postgresql.conf"
        subnet = self.allowed_subnet_input.text().strip()
        listen_addresses = self.listen_addresses_input.text().strip() or "*"
        db_name = self.wizard_database_input.text().strip() or DEFAULT_DB_NAME
        app_user = self.wizard_username_input.text().strip() or DEFAULT_DB_USER

        if not pg_hba.exists() or not postgresql_conf.exists():
            QMessageBox.warning(
                self,
                "Config Files Not Found",
                f"Could not find pg_hba.conf and postgresql.conf in:\n{data_dir}",
            )
            return

        try:
            self._backup_once(pg_hba)
            self._backup_once(postgresql_conf)
            hba_text = pg_hba.read_text(encoding="utf-8", errors="ignore")
            hba_line = f"host    {db_name}    {app_user}    {subnet}    scram-sha-256"
            if hba_line not in hba_text:
                pg_hba.write_text(hba_text.rstrip() + "\n" + hba_line + "\n", encoding="utf-8")
                self.append_wizard_output(f"Added pg_hba rule: {hba_line}")
            else:
                self.append_wizard_output("pg_hba rule already exists.")

            conf_lines = postgresql_conf.read_text(encoding="utf-8", errors="ignore").splitlines()
            new_lines = []
            replaced = False
            for line in conf_lines:
                if line.strip().startswith("listen_addresses") or line.strip().startswith("#listen_addresses"):
                    new_lines.append(f"listen_addresses = '{listen_addresses}'")
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.append(f"listen_addresses = '{listen_addresses}'")
            postgresql_conf.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
            self.append_wizard_output("Updated postgresql.conf listen_addresses.")
            self.append_wizard_output("Restart PostgreSQL service after this step.")
        except PermissionError:
            QMessageBox.warning(
                self,
                "Administrator Required",
                "Run Server Manager as Administrator to edit PostgreSQL config files.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Network Config Failed", str(exc))
            self.append_wizard_output(f"Network config failed: {exc}")

    def _backup_once(self, path: Path) -> None:
        backup = path.with_suffix(path.suffix + ".kaypos.bak")
        if not backup.exists():
            backup.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")

    def open_postgres_firewall_port(self) -> None:
        port = self.wizard_port_input.value()
        process = QProcess(self)
        process.setProgram("powershell")
        process.setArguments([
            "-NoProfile",
            "-Command",
            (
                "New-NetFirewallRule "
                "-DisplayName 'Kay POS PostgreSQL 5432' "
                "-Direction Inbound "
                "-Protocol TCP "
                f"-LocalPort {port} "
                "-Action Allow "
                "-ErrorAction SilentlyContinue"
            ),
        ])
        process.readyReadStandardOutput.connect(
            lambda: self.append_wizard_output(bytes(process.readAllStandardOutput()).decode(errors="ignore"))
        )
        process.readyReadStandardError.connect(
            lambda: self.append_wizard_output(bytes(process.readAllStandardError()).decode(errors="ignore"))
        )
        process.finished.connect(lambda: self.append_wizard_output(f"Firewall rule checked/opened for TCP {port}."))
        self.firewall_process = process
        process.start()

    def show_client_settings(self) -> None:
        host = local_ip()
        port = self.wizard_port_input.value()
        database = self.wizard_database_input.text().strip() or DEFAULT_DB_NAME
        username = self.wizard_username_input.text().strip() or DEFAULT_DB_USER
        password = self.wizard_password_input.text()
        text = (
            "Use these settings on each Client PC:\n\n"
            f"Server IP: {host}\n"
            f"Port: {port}\n"
            f"Database: {database}\n"
            f"Username: {username}\n"
            f"Password: {password}\n\n"
            "Client app path: Settings > Database"
        )
        self.append_wizard_output(text)
        QMessageBox.information(self, "Client Settings", text)

    def test_database(self) -> None:
        ok, message = test_database_connection(*self._database_values())
        status_text = f"Database status: {'connected' if ok else 'failed'}"
        self._set_chip(self.db_status, status_text, "ok" if ok else "bad")
        self._set_chip(
            self.header_db_label,
            f"Database: {self.database_input.text()} @ {self.host_input.text()}:{self.port_input.value()}",
            "ok" if ok else "bad",
        )
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

    def start_pos_server(self, _checked=False, silent=False) -> None:
        if self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning:
            self.append_server_output("POS server is already running.")
            return

        bind_host = self.bind_host_input.text().strip() or "0.0.0.0"
        port = self.server_port_input.value()
        car_enabled = self.car_server_enabled_checkbox.isChecked()
        car_port = self.car_server_port_input.value()
        scheme = self._server_scheme()
        if not can_bind_port(bind_host, port):
            url = f"{scheme}://{local_ip()}:{port}"
            message = f"Port {port} is already in use. Cashier Server may already be running at {url}"
            self.append_server_output(message)
            self._set_chip(self.server_status, message, "warn")
            if not silent:
                QMessageBox.information(self, "Cashier Server Already Running", message)
            return
        if car_enabled and car_port == port:
            message = "POS Server and Car Management service must use different ports."
            self._set_chip(self.car_server_status, message, "bad")
            if not silent:
                QMessageBox.warning(self, "Duplicate Server Port", message)
            return
        if car_enabled and not can_bind_port(bind_host, car_port):
            message = (
                f"Car Management port {car_port} is already in use. Stop the old Car Server/Server.exe "
                "or choose another port before starting KAY POS Server."
            )
            self.append_server_output(message)
            self._set_chip(self.car_server_status, message, "bad")
            if not silent:
                QMessageBox.warning(self, "Car Server Port In Use", message)
            return

        self.server_process = QProcess(self)
        self.server_process.setWorkingDirectory(str(PROJECT_ROOT))
        self.server_process.setProgram(sys.executable)
        process_environment = QProcessEnvironment.systemEnvironment()
        process_environment.insert("ZAY_CAR_SERVER_ENABLED", "1" if car_enabled else "0")
        process_environment.insert("ZAY_CAR_SERVER_HOST", bind_host)
        process_environment.insert("ZAY_CAR_SERVER_PORT", str(car_port))
        self.server_process.setProcessEnvironment(process_environment)
        args = [
            "--run-pos-server" if getattr(sys, "frozen", False) else "run_pos_server.py",
            "--host",
            bind_host,
            "--port",
            str(port),
        ]
        if self.https_server_checkbox.isChecked():
            args.append("--https")
        self.server_process.setArguments(args)
        self.server_process.readyReadStandardOutput.connect(self._read_server_stdout)
        self.server_process.readyReadStandardError.connect(self._read_server_stderr)
        self.server_process.finished.connect(self._server_finished)
        self.server_process.start()
        self._set_chip(
            self.server_status,
            f"Server status: starting. Network URL: {scheme}://{local_ip()}:{port}",
            "warn",
        )
        self._set_chip(
            self.car_server_status,
            f"Car server status: starting on {local_ip()}:{car_port}" if car_enabled else "Car server status: disabled",
            "warn" if car_enabled else "neutral",
        )
        self._update_server_buttons()

    def _server_scheme(self) -> str:
        return "https" if self.https_server_checkbox.isChecked() else "http"

    def stop_pos_server(self) -> None:
        if not self.server_process or self.server_process.state() == QProcess.ProcessState.NotRunning:
            self._set_chip(self.server_status, "Server status: stopped")
            self._set_chip(self.car_server_status, "Car server status: stopped")
            self._update_server_buttons()
            return
        self.server_process.terminate()
        if not self.server_process.waitForFinished(3000):
            self.server_process.kill()
        self._set_chip(self.server_status, "Server status: stopped")
        self._set_chip(self.car_server_status, "Car server status: stopped")
        self._update_server_buttons()

    def restart_pos_server(self) -> None:
        self.stop_pos_server()
        self.start_pos_server()

    def _auto_start_services(self) -> None:
        """Start the integrated services after a Windows-login launch."""
        if not self.start_services_on_open_checkbox.isChecked():
            return
        if self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning:
            return
        self.append_server_output("Windows auto start requested POS and Car services.")
        self.start_pos_server(silent=True)

    def _save_service_auto_start_setting(self, enabled: bool) -> None:
        self.settings.setValue("start_services_on_open", bool(enabled))
        self.settings.sync()

    def _setup_system_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("KAY POS Server Manager")
        tray_menu = QMenu(self)
        tray_menu.setObjectName("TrayMenu")
        tray_menu.setStyleSheet("""
            QMenu#TrayMenu {
                background: #151c2a;
                color: #edf2ff;
                border: 1px solid #354158;
                border-radius: 8px;
                padding: 6px;
                font-family: "Segoe UI", "Myanmar Text";
                font-size: 10pt;
            }
            QMenu#TrayMenu::item {
                background: transparent;
                color: #edf2ff;
                border-radius: 6px;
                padding: 8px 28px 8px 12px;
                margin: 1px 0;
            }
            QMenu#TrayMenu::item:selected {
                background: #2a2430;
                color: #ffc46d;
            }
            QMenu#TrayMenu::item:disabled {
                color: #667085;
            }
            QMenu#TrayMenu::separator {
                height: 1px;
                background: #303b50;
                margin: 5px 8px;
            }
        """)
        show_action = QAction("Show Server Manager", self)
        show_action.triggered.connect(self._show_from_tray)
        stop_action = QAction("Stop POS and Car Services", self)
        stop_action.triggered.connect(self.stop_pos_server)
        exit_action = QAction("Exit Server Manager", self)
        exit_action.triggered.connect(self._exit_manager)
        tray_menu.addAction(show_action)
        tray_menu.addAction(stop_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        self.tray_menu = tray_menu
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self._show_from_tray()

    def _exit_manager(self) -> None:
        running = bool(self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning)
        if running:
            answer = QMessageBox.question(
                self,
                "Exit Server Manager",
                "Exiting Server Manager will stop POS and Car services. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.stop_pos_server()
        self._allow_close = True
        self.tray_icon.hide()
        self.close()
        QApplication.quit()

    def enable_windows_auto_start(self) -> None:
        """Register Server Manager in the current user's Windows Startup Apps."""
        try:
            if winreg is None:
                raise OSError("Windows Registry is unavailable on this system.")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, AUTO_START_REGISTRY_PATH) as key:
                winreg.SetValueEx(key, AUTO_START_REGISTRY_NAME, 0, winreg.REG_SZ, auto_start_command())
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    AUTO_START_APPROVED_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.DeleteValue(key, AUTO_START_REGISTRY_NAME)
            except FileNotFoundError:
                pass
            legacy_path = auto_start_file_path()
            if legacy_path.exists():
                legacy_path.unlink()
            self._update_auto_start_status()
            QMessageBox.information(
                self,
                "Windows Auto Start",
                "Auto start enabled. Kay POS Server Manager is now listed in Task Manager > Startup Apps.",
            )
        except OSError as exc:
            self._set_chip(self.auto_start_status, f"Windows auto start: failed ({exc})", "bad")
            QMessageBox.critical(self, "Windows Auto Start", f"Could not enable auto start:\n{exc}")

    def disable_windows_auto_start(self) -> None:
        try:
            if winreg is None:
                raise OSError("Windows Registry is unavailable on this system.")
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    AUTO_START_REGISTRY_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.DeleteValue(key, AUTO_START_REGISTRY_NAME)
            except FileNotFoundError:
                pass
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    AUTO_START_APPROVED_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.DeleteValue(key, AUTO_START_REGISTRY_NAME)
            except FileNotFoundError:
                pass
            legacy_path = auto_start_file_path()
            if legacy_path.exists():
                legacy_path.unlink()
            self._update_auto_start_status()
            QMessageBox.information(self, "Windows Auto Start", "Auto start entry removed from Windows Startup Apps.")
        except OSError as exc:
            self._set_chip(self.auto_start_status, f"Windows auto start: failed ({exc})", "bad")
            QMessageBox.critical(self, "Windows Auto Start", f"Could not disable auto start:\n{exc}")

    def _update_auto_start_status(self) -> None:
        state = auto_start_registry_state()
        legacy_enabled = auto_start_file_path().is_file()
        if state == "enabled":
            text, tone = "Windows auto start: enabled (Task Manager > Startup Apps)", "ok"
        elif state == "disabled":
            text, tone = "Windows auto start: disabled in Task Manager", "warn"
        elif legacy_enabled:
            text, tone = "Windows auto start: legacy entry detected; click Enable to migrate", "warn"
        else:
            text, tone = "Windows auto start: not registered", "neutral"
        self._set_chip(
            self.auto_start_status,
            text,
            tone,
        )
        self.enable_auto_start_button.setEnabled(state != "enabled" or legacy_enabled)
        self.disable_auto_start_button.setEnabled(state != "missing" or legacy_enabled)

    def import_car_database(self) -> None:
        """Run the safe legacy SQLite-to-PostgreSQL car migration tool."""
        process = getattr(self, "car_import_process", None)
        if process and process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Car Database Import", "A car database import is already running.")
            return

        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Legacy Car Management Database",
            "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*.*)",
        )
        if not source_path:
            return

        answer = QMessageBox.question(
            self,
            "Import Car Management Database",
            (
                f"Import records from:\n{source_path}\n\n"
                "Records keep their original IDs. IDs already present in PostgreSQL are skipped, "
                "and existing records are not overwritten. Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.car_import_process = QProcess(self)
        self.car_import_process.setWorkingDirectory(str(PROJECT_ROOT))
        self.car_import_process.setProgram(sys.executable)
        self.car_import_process.setArguments([
            "--migrate-car-sqlite" if getattr(sys, "frozen", False) else "tools/migrate_car_sqlite.py",
            source_path,
        ])
        self.car_import_process.readyReadStandardOutput.connect(self._read_car_import_stdout)
        self.car_import_process.readyReadStandardError.connect(self._read_car_import_stderr)
        self.car_import_process.finished.connect(self._car_import_finished)
        self.import_car_database_button.setEnabled(False)
        self._set_chip(self.car_import_status, "Car database import: running...", "warn")
        self.append_server_output(f"Importing legacy Car Management database: {source_path}")
        self.car_import_process.start()

    def _read_car_import_stdout(self) -> None:
        if not getattr(self, "car_import_process", None):
            return
        data = bytes(self.car_import_process.readAllStandardOutput()).decode(errors="ignore")
        if data:
            self.append_server_output(data)

    def _read_car_import_stderr(self) -> None:
        if not getattr(self, "car_import_process", None):
            return
        data = bytes(self.car_import_process.readAllStandardError()).decode(errors="ignore")
        if data:
            self.append_server_output(data)

    def _car_import_finished(self, exit_code: int, _status) -> None:
        self.import_car_database_button.setEnabled(True)
        if exit_code == 0:
            self._set_chip(self.car_import_status, "Car database import: completed", "ok")
            QMessageBox.information(
                self,
                "Car Database Import",
                "Import completed. Restart the POS Server, then refresh the Car Management client.",
            )
        else:
            self._set_chip(self.car_import_status, "Car database import: failed", "bad")
            QMessageBox.critical(
                self,
                "Car Database Import",
                "Import failed. Check the Server Output panel for details.",
            )

    def _read_server_stdout(self) -> None:
        if not self.server_process:
            return
        data = bytes(self.server_process.readAllStandardOutput()).decode(errors="ignore")
        if data:
            self.append_server_output(data)
            if "Car Management service listening" in data:
                self._set_chip(
                    self.car_server_status,
                    f"Car server status: running. LAN: {local_ip()}:{self.car_server_port_input.value()}",
                    "ok",
                )

    def _read_server_stderr(self) -> None:
        if not self.server_process:
            return
        data = bytes(self.server_process.readAllStandardError()).decode(errors="ignore")
        if data:
            self.append_server_output(data)
            if "Car Management service listening" in data:
                self._set_chip(
                    self.car_server_status,
                    f"Car server status: running. LAN: {local_ip()}:{self.car_server_port_input.value()}",
                    "ok",
                )
            elif "Could not start Car Management service" in data:
                self._set_chip(self.car_server_status, "Car server status: failed to start", "bad")

    def _server_finished(self) -> None:
        self._set_chip(self.server_status, "Server status: stopped")
        self._set_chip(self.car_server_status, "Car server status: stopped")
        self._update_server_buttons()
        self.append_server_output("POS server stopped.")

    def run_postgres_service_command(self, command: str) -> None:
        service = self.pg_service_input.text().strip()
        if not service:
            QMessageBox.warning(self, "Missing Service Name", "Enter the PostgreSQL service name.")
            return
        process = QProcess(self)
        process.setProgram("powershell")
        process.setArguments(["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"{command} -Name '{service}' -ErrorAction Stop"])
        process.readyReadStandardOutput.connect(
            lambda: self.append_server_output(bytes(process.readAllStandardOutput()).decode(errors="ignore"))
        )
        process.readyReadStandardError.connect(
            lambda: self.append_server_output(bytes(process.readAllStandardError()).decode(errors="ignore"))
        )
        process.finished.connect(
            lambda exit_code, _status, cmd=command, svc=service: self._postgres_service_finished(cmd, svc, exit_code)
        )
        self.postgres_process = process
        process.start()

    def restart_postgres_service(self) -> None:
        self.run_postgres_service_command("Restart-Service")

    def _postgres_service_finished(self, command: str, service: str, exit_code: int) -> None:
        if exit_code == 0:
            self.append_server_output(f"{command} completed for {service}.")
            return

        self.append_server_output(
            f"{command} failed for {service} (exit code {exit_code}). "
            "Run Server Manager as Administrator, then try again."
        )

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
            self._set_chip(
                self.stats_label,
                "Stats: "
                f"Products {counts['products']} | Users {counts['users']} | "
                f"Sales {counts['sales']} | Customers {counts['customers']}",
                "ok",
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
            self._set_chip(self.stats_label, f"Stats: unavailable ({exc})", "warn")

    def refresh_logs(self) -> None:
        log_dir = Path(config.LOG_DIR)
        candidates = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            self._set_chip(self.log_path_label, f"Log file: no .log files in {log_dir}", "warn")
            return
        if self.log_file != candidates[0]:
            self.log_file = candidates[0]
            self.log_position = 0
            self.log_output.clear()
            self._set_chip(self.log_path_label, f"Log file: {self.log_file}", "ok")

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

    def refresh_printer_agents(self) -> None:
        try:
            from server.printer_service import PrinterRegistry

            agents = PrinterRegistry().list_agents()
            self.printer_agents_table.setRowCount(0)
            online_agents = sum(1 for agent in agents if agent.get("is_online"))
            online_printers = 0
            for agent in agents:
                printers = agent.get("printers") or [None]
                for printer in printers:
                    printer = printer or {}
                    agent_online = bool(agent.get("is_online"))
                    printer_online = agent_online and bool(agent.get("is_enabled", True)) and printer.get("status") == "online"
                    online_printers += int(printer_online)
                    values = (
                        agent.get("computer_name"),
                        agent.get("ip_address"),
                        agent.get("agent_version"),
                        printer.get("printer_name") or "No printer detected",
                        "Yes" if printer.get("is_default") else "",
                        "Online" if printer_online else "Offline",
                        printer.get("last_seen") or agent.get("last_seen"),
                    )
                    row_index = self.printer_agents_table.rowCount()
                    self.printer_agents_table.insertRow(row_index)
                    for column, value in enumerate(values):
                        item = QTableWidgetItem(str(value or ""))
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        item.setData(Qt.ItemDataRole.UserRole, {
                            "agent_id": agent.get("agent_id"),
                            "printer_name": printer.get("printer_name"),
                            "is_online": printer_online,
                            "is_enabled": bool(agent.get("is_enabled", True)),
                        })
                        self.printer_agents_table.setItem(row_index, column, item)
            tone = "ok" if online_agents else "warn"
            self._set_chip(
                self.printer_server_status,
                f"Printer Server: {online_agents}/{len(agents)} PC(s) online · "
                f"{online_printers} printer(s) available",
                tone,
            )
            self._refresh_printer_jobs()
        except Exception as exc:
            self._set_chip(self.printer_server_status, f"Printer Server: unavailable ({exc})", "warn")

    def _refresh_printer_jobs(self) -> None:
        from server.printer_service import PrinterRegistry

        jobs = PrinterRegistry().list_jobs(100)
        agents = {item["agent_id"]: item.get("computer_name") for item in PrinterRegistry().list_agents()}
        self.printer_jobs_table.setRowCount(0)
        for job in jobs:
            values = (
                job.get("created_at"),
                agents.get(job.get("target_agent_id"), job.get("target_agent_id")),
                job.get("printer_name"),
                job.get("job_type"),
                job.get("status"),
                f"{job.get('attempts', 0)}/{job.get('max_attempts', 0)}",
                job.get("error_message"),
                job.get("job_id"),
            )
            row_index = self.printer_jobs_table.rowCount()
            self.printer_jobs_table.insertRow(row_index)
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setData(Qt.ItemDataRole.UserRole, job.get("job_id"))
                self.printer_jobs_table.setItem(row_index, column, item)

    def send_printer_test_page(self) -> None:
        row = self.printer_agents_table.currentRow()
        item = self.printer_agents_table.item(row, 0) if row >= 0 else None
        target = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not target or not target.get("printer_name"):
            QMessageBox.warning(self, "Select Printer", "Select an available printer row first.")
            return
        if not target.get("is_online"):
            QMessageBox.warning(self, "Printer Offline", "The selected PC or printer is currently offline.")
            return
        try:
            from server.printer_service import PrinterRegistry

            job = PrinterRegistry().create_job(
                request_key=f"server-test-{uuid.uuid4()}",
                target_agent_id=target["agent_id"],
                printer_name=target["printer_name"],
                job_type="test_page",
                payload={"requested_by": "KAY Server Manager"},
                source_agent_id="server-manager",
            )
            self._set_chip(self.printer_server_status, f"Test page queued: {job['job_id']}", "ok")
            self._refresh_printer_jobs()
        except Exception as exc:
            QMessageBox.critical(self, "Print Job Failed", str(exc))

    def toggle_selected_printer_agent(self) -> None:
        target = self._selected_network_printer()
        if not target or not target.get("agent_id"):
            QMessageBox.warning(self, "Select PC", "Select a printer PC row first.")
            return
        enabled = not bool(target.get("is_enabled", True))
        try:
            from server.printer_service import PrinterRegistry

            PrinterRegistry().set_agent_permissions(target["agent_id"], enabled, [])
            self.refresh_printer_agents()
            state = "enabled" if enabled else "disabled"
            self._set_chip(self.printer_server_status, f"Printer Agent {state}.", "ok" if enabled else "warn")
        except Exception as exc:
            QMessageBox.warning(self, "Agent Permission", str(exc))

    def _selected_network_printer(self) -> dict | None:
        row = self.printer_agents_table.currentRow()
        item = self.printer_agents_table.item(row, 0) if row >= 0 else None
        target = item.data(Qt.ItemDataRole.UserRole) if item else None
        return target if isinstance(target, dict) else None

    def send_printer_document(self) -> None:
        target = self._selected_network_printer()
        if not target or not target.get("printer_name"):
            QMessageBox.warning(self, "Select Printer", "Select an available printer row first.")
            return
        if not target.get("is_online"):
            QMessageBox.warning(self, "Printer Offline", "The selected PC or printer is currently offline.")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document to Print",
            "",
            "Supported Documents (*.pdf *.png *.jpg *.jpeg *.bmp *.txt *.escpos *.bin)",
        )
        if not filename:
            return
        try:
            from server.printer_assets import store_asset
            from server.printer_service import PrinterRegistry

            path = Path(filename)
            asset_id, asset_path, job_type = store_asset(path.name, path.read_bytes())
            try:
                job = PrinterRegistry().create_job(
                    request_key=f"server-document-{uuid.uuid4()}",
                    target_agent_id=target["agent_id"],
                    printer_name=target["printer_name"],
                    job_type=job_type,
                    payload={
                        "asset_id": asset_id,
                        "asset_path": asset_path,
                        "filename": path.name,
                        "paper_size": self.print_paper_size.currentText().upper(),
                        "orientation": self.print_orientation.currentText().lower(),
                    },
                    copies=self.print_copies.value(),
                    source_agent_id="server-manager",
                )
            except Exception:
                Path(asset_path).unlink(missing_ok=True)
                raise
            self._set_chip(self.printer_server_status, f"Document queued: {path.name} · {job['job_id']}", "ok")
            self._refresh_printer_jobs()
        except Exception as exc:
            QMessageBox.critical(self, "Document Print Failed", str(exc))

    def retry_selected_print_job(self) -> None:
        row = self.printer_jobs_table.currentRow()
        item = self.printer_jobs_table.item(row, 0) if row >= 0 else None
        job_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not job_id:
            QMessageBox.warning(self, "Select Print Job", "Select a failed print job first.")
            return
        try:
            from server.printer_service import PrinterRegistry

            PrinterRegistry().retry_job(job_id)
            self._set_chip(self.printer_server_status, f"Print job queued for retry: {job_id}", "ok")
            self._refresh_printer_jobs()
        except Exception as exc:
            QMessageBox.warning(self, "Retry Unavailable", str(exc))

    def _refresh_all(self) -> None:
        self.refresh_activity()
        self.refresh_logs()
        self.refresh_printer_agents()
        if self.server_process and self.server_process.state() != QProcess.ProcessState.NotRunning:
            self._set_chip(
                self.server_status,
                f"Server status: running. Network URL: {self._server_scheme()}://{local_ip()}:{self.server_port_input.value()}",
                "ok",
            )
        self._update_server_buttons()
        self._update_auto_start_status()

    def closeEvent(self, event) -> None:
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray_icon.showMessage(
                "KAY POS Server Manager",
                "Server Manager is still running. POS and Car services were not stopped.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            self.showMinimized()


def main() -> int:
    if "--run-pos-server" in sys.argv:
        sys.argv.remove("--run-pos-server")
        from run_pos_server import main as run_pos_server

        run_pos_server()
        return 0
    if "--migrate-car-sqlite" in sys.argv:
        sys.argv.remove("--migrate-car-sqlite")
        from tools.migrate_car_sqlite import main as migrate_car_sqlite

        migrate_car_sqlite()
        return 0

    from utils.single_instance import SingleInstanceGuard, show_already_running_message

    # Apply the lock only to the manager GUI. Internal helper modes above may
    # legitimately run as child processes of the already-open Server Manager.
    instance_guard = SingleInstanceGuard(r"Global\KAY_POS_Server_Manager_SingleInstance_v1")
    if not instance_guard.acquire():
        show_already_running_message(
            title="KAY POS Server Manager",
            message="KAY POS Server Manager is already running on this computer.",
        )
        return 0

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--no-auto-start", action="store_true")
    parser.add_argument("--minimized", action="store_true")
    args, qt_args = parser.parse_known_args(sys.argv[1:])
    app = QApplication([sys.argv[0], *qt_args])
    app.setQuitOnLastWindowClosed(False)
    auto_start = False if args.no_auto_start else (True if args.auto_start else None)
    window = ServerManagerWindow(auto_start=auto_start)
    if args.minimized:
        window.showMinimized()
    else:
        window.show()
    return app.exec()
