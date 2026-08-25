"""Setup dialog and system-tray runtime for the KAY Printer Agent."""

from __future__ import annotations

import sys
import secrets
import uuid
from pathlib import Path

import requests
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from printer_agent import (
    agent_config_path,
    enroll_agent,
    load_agent_config,
    load_agent_key,
    run_agent_cycle,
    save_agent_config,
    set_windows_startup,
    startup_shortcut_path,
)
from utils.single_instance import SingleInstanceGuard, show_already_running_message
from utils.branded_icons import branded_tile_icon
from printer_picture_page import PrintPicturesPage
from virtual_printer import (
    DEFAULT_DRIVER, VIRTUAL_PRINTER_NAME, install_virtual_printer,
    installed_printer_drivers, remove_virtual_printer, VirtualPrinterBridge,
)


def _icon() -> QIcon:
    return branded_tile_icon("P", "#35a7ff")


def printer_visibility_key(agent_id: str, printer_name: str) -> str:
    return f"{str(agent_id or '').strip()}\x1f{str(printer_name or '').strip()}"


def generate_security_key() -> str:
    """Return a copy/paste-friendly 256-bit key for Printer Server security."""
    return secrets.token_urlsafe(32)


def _api_headers(config: dict, *, admin: bool = False) -> dict[str, str]:
    key_name = "admin_api_key" if admin else "client_api_key"
    key = str(config.get(key_name) or "").strip()
    if not key and admin:
        key = str(config.get("client_api_key") or "").strip()
    return {"X-Printer-Api-Key": key} if key else {}


AGENT_STYLESHEET = """
    QDialog { background: #0d111b; color: #edf2ff; font-family: "Segoe UI", "Myanmar Text"; }
    QWidget { color: #edf2ff; font-family: "Segoe UI", "Myanmar Text"; font-size: 10pt; }
    QLabel { color: #c7d2e5; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background: #0f1520; color: #edf2ff; border: 1px solid #303b50;
        border-radius: 7px; padding: 6px 8px; min-height: 24px;
    }
    QDoubleSpinBox:disabled {
        background: #1a2230; color: #aebbd0; border-color: #354158;
    }
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        background: #263247; border: 0; width: 18px;
    }
    QComboBox QAbstractItemView {
        background: #151c2a; color: #edf2ff; border: 1px solid #3a465a;
        selection-background-color: #238bd1; selection-color: white; outline: 0;
    }
    QPushButton {
        background: #35a7ff; color: white; border: 0; border-radius: 7px;
        padding: 8px 12px; font-weight: 600;
    }
    QPushButton:hover { background: #58b7ff; }
    QPushButton:disabled { background: #303847; color: #707b91; }
    QFrame#AgentSidebar { background: #111724; border-right: 1px solid #252d3d; }
    QLabel#AgentBrandMark {
        background: #35a7ff; color: white; border-radius: 13px;
        font-size: 18pt; font-weight: 800;
    }
    QLabel#AgentBrand { color: white; font-size: 19pt; font-weight: 800; }
    QLabel#AgentEyebrow { color: #78c7ff; font-size: 9pt; font-weight: 700; }
    QLabel#AgentTitle { color: white; font-size: 24pt; font-weight: 800; }
    QLabel#AgentSubtitle { color: #99a4ba; }
    QLabel#AgentStatus {
        background: #182231; color: #b9c5d9; border: 1px solid #2b3a50;
        border-radius: 9px; padding: 7px 11px;
    }
    QPushButton#AgentNavButton {
        text-align: left; min-height: 44px; border: 0; border-radius: 10px;
        background: transparent; color: #aeb8ca; padding: 0 13px; font-weight: 650;
    }
    QPushButton#AgentNavButton:hover { background: #1c2535; color: white; }
    QPushButton#AgentNavButton:checked {
        background: #172b3d; color: #78c7ff; border-left: 3px solid #35a7ff;
    }
    QTableWidget {
        background: #090e17; alternate-background-color: #0f1622; color: #dbeafe;
        border: 1px solid #283448; gridline-color: #202b3d; selection-background-color: #245f87;
    }
    QHeaderView::section {
        background: #182231; color: #c7d2e5; border: 0;
        border-bottom: 1px solid #303b50; padding: 8px; font-weight: 700;
    }
    QTabWidget::pane { border: 0; background: transparent; }
    QFrame#PicturePreviewCard, QFrame#PictureOptionsCard {
        background: #111925; border: 1px solid #29384a; border-radius: 12px;
    }
    QLabel#PicturePreview { background: #080d15; color: #8f9db2; border-radius: 8px; padding: 10px; }
    QListWidget#PictureThumbnails {
        background: #0b111b; alternate-background-color: #101824; color: #dbeafe;
        border: 1px solid #29384a; border-radius: 10px; outline: 0;
    }
    QListWidget#PictureThumbnails::item { min-height: 66px; padding: 6px; border-radius: 7px; }
    QListWidget#PictureThumbnails::item:selected { background: #245f87; color: white; }
    QProgressBar {
        min-width: 110px; max-height: 8px; background: #253243;
        border: 0; border-radius: 4px;
    }
    QProgressBar::chunk { background: #35a7ff; border-radius: 4px; }
    QCheckBox { color: #c7d2e5; spacing: 8px; }
    QCheckBox::indicator {
        width: 17px; height: 17px; border: 1px solid #52647c;
        border-radius: 4px; background: #0b111b;
    }
    QCheckBox::indicator:hover { border-color: #78c7ff; }
    QCheckBox::indicator:checked {
        background: #35a7ff; border: 2px solid #8dd2ff;
    }
"""


class AgentSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KAY Printer Agent Setup")
        self.setWindowIcon(_icon())
        self.setMinimumWidth(540)
        self.setStyleSheet(AGENT_STYLESHEET)
        config = load_agent_config()
        layout = QVBoxLayout(self)
        note = QLabel(
            "Connect this PC to the KAY Printer Server. The enrollment key is used once and is never saved."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.server_url = QLineEdit(str(config.get("server_url") or "http://127.0.0.1:8000"))
        self.enrollment_key = QLineEdit()
        self.enrollment_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_api_key = QLineEdit(str(config.get("client_api_key") or ""))
        self.client_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_api_key.setPlaceholderText("Required when Printer Server security is enabled")
        self.admin_api_key = QLineEdit(str(config.get("admin_api_key") or ""))
        self.admin_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_api_key.setPlaceholderText("Optional · required for retry and PC enable/disable")
        self.insecure = QCheckBox("Allow Server Manager self-signed HTTPS certificate")
        self.insecure.setChecked(bool(config.get("insecure", False)))
        self.startup = QCheckBox("Start Printer Agent after Windows login")
        self.startup.setChecked(startup_shortcut_path().is_file())
        form.addRow("Printer Server URL", self.server_url)
        form.addRow("Enrollment Key", self.enrollment_key)
        form.addRow("Client API Key", self.client_api_key)
        form.addRow("Admin API Key", self.admin_api_key)
        form.addRow("", self.insecure)
        form.addRow("", self.startup)
        layout.addLayout(form)
        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        test_button = QPushButton("Test, Enroll and Save")
        test_button.clicked.connect(self.test_and_save)
        layout.addWidget(test_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def test_and_save(self):
        server_url = self.server_url.text().strip()
        if not server_url:
            QMessageBox.warning(self, "Printer Agent", "Printer Server URL is required.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            agent_key = load_agent_key()
            enrollment_key = self.enrollment_key.text()
            if enrollment_key:
                agent_key = enroll_agent(server_url, enrollment_key, not self.insecure.isChecked())
            agent, _ = run_agent_cycle(server_url, self.insecure.isChecked(), agent_key)
            save_agent_config(
                server_url=server_url,
                insecure=self.insecure.isChecked(),
                client_api_key=self.client_api_key.text().strip(),
                admin_api_key=self.admin_api_key.text().strip(),
            )
            set_windows_startup(self.startup.isChecked())
            self.status.setText(
                f"Connected as {agent.get('computer_name', 'this PC')} · "
                f"{len(agent.get('printers') or [])} printer(s) detected."
            )
            QMessageBox.information(self, "Printer Agent", "Configuration saved successfully.")
        except Exception as exc:
            self.status.setText(f"Connection failed: {exc}")
            QMessageBox.warning(self, "Printer Agent Setup", str(exc))
        finally:
            QApplication.restoreOverrideCursor()


class PrinterAgentDashboard(QDialog):
    """Printer operations UI; the Server Manager remains focused on server services."""

    def __init__(self, parent=None, tray_icon: QSystemTrayIcon | None = None, virtual_bridge=None):
        super().__init__(parent)
        self.tray_icon = tray_icon
        self.virtual_bridge = virtual_bridge
        self._allow_close = False
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("KAY Printer Agent")
        self.setWindowIcon(_icon())
        self.setMinimumSize(1050, 680)
        self.setStyleSheet(AGENT_STYLESHEET)

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("AgentSidebar")
        sidebar.setFixedWidth(238)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(24, 30, 24, 24)
        side.setSpacing(8)
        brand_row = QHBoxLayout()
        mark = QLabel("P")
        mark.setObjectName("AgentBrandMark")
        mark.setFixedSize(44, 44)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand = QLabel("KAY")
        brand.setObjectName("AgentBrand")
        brand_row.addWidget(mark)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        side.addLayout(brand_row)
        eyebrow = QLabel("PRINTER AGENT")
        eyebrow.setObjectName("AgentEyebrow")
        side.addWidget(eyebrow)
        side.addSpacing(28)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.picture_page = PrintPicturesPage(request=self._request)
        self.picture_page.job_queued.connect(self._picture_job_queued)
        pages = (
            ("Printer List", "Network printers and print controls", self._printers_page()),
            ("Print Pictures", "Photo selection, layouts and network print queue", self.picture_page),
            ("Recent Print Jobs", "Print queue history and retry", self._jobs_page()),
            ("Connection Setup", "Server connection, security and startup", self._connection_page()),
            ("Security Keys", "Generate enrollment, client and admin keys", self._security_keys_page()),
        )
        self.nav_buttons = []
        for index, (name, description, page) in enumerate(pages):
            self.tabs.addTab(page, name)
            button = QPushButton(f"{index + 1:02d}   {name}")
            button.setObjectName("AgentNavButton")
            button.setCheckable(True)
            button.setToolTip(description)
            button.clicked.connect(lambda _checked=False, page_index=index: self._select_page(page_index))
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch()
        side.addWidget(QLabel("Runs securely in the Windows system tray"))
        shell.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 28, 34, 28)
        content_layout.setSpacing(18)
        header = QFrame()
        header_layout = QGridLayout(header)
        self.page_title = QLabel()
        self.page_title.setObjectName("AgentTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("AgentSubtitle")
        self.connection_status = QLabel("Printer Server: not checked")
        self.connection_status.setObjectName("AgentStatus")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_all)
        header_layout.addWidget(self.page_title, 0, 0)
        header_layout.addWidget(self.connection_status, 0, 1, Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.page_subtitle, 1, 0)
        header_layout.addWidget(refresh, 1, 1, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(header)
        content_layout.addWidget(self.tabs, 1)
        shell.addWidget(content, 1)
        self._select_page(0)

    def _select_page(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)
        titles = (
            ("Printer List", "Choose any online PC printer and send a test page, photo or document."),
            ("Print Pictures", "Select photos, choose a page layout, preview, and create a print-ready PDF."),
            ("Recent Print Jobs", "Monitor queued, completed and failed network print jobs."),
            ("Connection Setup", "Connect this PC securely to the KAY Printer Server."),
            ("Security Keys", "Generate strong keys, copy them to the Server, then use them in Connection Setup."),
        )
        title, subtitle = titles[index]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def closeEvent(self, event) -> None:
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "KAY Printer Agent",
                "Printer Agent is still running. Double-click the tray icon to open it again.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def reject(self) -> None:
        # Escape and dialog-style Close actions follow the same tray behavior
        # as the window's X button.
        self.close()

    def _printers_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.show_hidden = QCheckBox("Show Hidden / Offline Printers")
        self.show_hidden.toggled.connect(lambda _checked: self.refresh_printers())
        hide_show = QPushButton("Hide / Show Printer")
        hide_show.clicked.connect(self.toggle_visibility)
        enable_disable_printer = QPushButton("Enable / Disable Printer")
        enable_disable_printer.clicked.connect(self.toggle_printer)
        enable_disable = QPushButton("Enable / Disable PC")
        enable_disable.clicked.connect(self.toggle_agent)
        test = QPushButton("Print Test Page")
        test.clicked.connect(self.send_test_page)
        controls.addWidget(self.show_hidden)
        controls.addStretch()
        controls.addWidget(hide_show)
        controls.addWidget(enable_disable_printer)
        controls.addWidget(enable_disable)
        controls.addWidget(test)
        layout.addLayout(controls)

        virtual = QFrame()
        virtual.setObjectName("AgentStatus")
        virtual_row = QGridLayout(virtual)
        self.virtual_target_label = QLabel("Virtual target: not selected")
        self.virtual_driver = QComboBox()
        drivers = installed_printer_drivers()
        xerox_drivers = [name for name in drivers if "xerox" in name.lower() and "pcl" in name.lower()]
        self.virtual_driver.addItems(xerox_drivers or drivers)
        if self.virtual_driver.findText(DEFAULT_DRIVER) >= 0:
            self.virtual_driver.setCurrentText(DEFAULT_DRIVER)
        set_target = QPushButton("Use Selected as Virtual Target")
        set_target.clicked.connect(self.set_virtual_target)
        install_virtual = QPushButton(f"Install {VIRTUAL_PRINTER_NAME}")
        install_virtual.clicked.connect(self.install_virtual_queue)
        remove_virtual = QPushButton("Remove Virtual Printer")
        remove_virtual.clicked.connect(self.remove_virtual_queue)
        virtual_row.addWidget(self.virtual_target_label, 0, 0, 1, 2)
        virtual_row.addWidget(set_target, 0, 2)
        virtual_row.addWidget(QLabel("Windows Driver"), 1, 0)
        virtual_row.addWidget(self.virtual_driver, 1, 1)
        virtual_row.addWidget(install_virtual, 1, 2)
        virtual_row.addWidget(remove_virtual, 1, 3)
        virtual_row.setColumnStretch(1, 1)
        layout.addWidget(virtual)

        self.printers_table = QTableWidget(0, 8)
        self.printers_table.setHorizontalHeaderLabels(
            ["PC", "IP Address", "Agent", "Printer", "Default", "Status", "Visibility", "Last Seen"]
        )
        self._prepare_table(self.printers_table)
        layout.addWidget(self.printers_table, 1)

        print_row = QHBoxLayout()
        self.paper_size = QComboBox()
        self.paper_size.addItems(["A4", "A5", "80mm", "58mm"])
        self.orientation = QComboBox()
        self.orientation.addItems(["Portrait", "Landscape"])
        self.copies = QSpinBox()
        self.copies.setRange(1, 99)
        print_document = QPushButton("Print Photo / Document…")
        print_document.clicked.connect(self.send_document)
        print_row.addWidget(QLabel("Paper"))
        print_row.addWidget(self.paper_size)
        print_row.addWidget(QLabel("Orientation"))
        print_row.addWidget(self.orientation)
        print_row.addWidget(QLabel("Copies"))
        print_row.addWidget(self.copies)
        print_row.addStretch()
        print_row.addWidget(print_document)
        layout.addLayout(print_row)
        return page

    def _jobs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        note = QLabel("Failed jobs can be selected and queued again.")
        retry = QPushButton("Retry Selected Job")
        retry.clicked.connect(self.retry_job)
        row.addWidget(note)
        row.addStretch()
        row.addWidget(retry)
        layout.addLayout(row)
        self.jobs_table = QTableWidget(0, 8)
        self.jobs_table.setHorizontalHeaderLabels(
            ["Created", "PC", "Printer", "Type", "Status", "Attempts", "Error", "Job ID"]
        )
        self._prepare_table(self.jobs_table)
        layout.addWidget(self.jobs_table, 1)
        return page

    def _connection_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        note = QLabel(
            "Enter the Printer Server address and security keys for this PC. "
            "The Enrollment Key is used only when enrolling and is not saved."
        )
        note.setWordWrap(True)
        note.setObjectName("AgentStatus")
        layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(12)
        self.connection_server_url = QLineEdit()
        self.connection_server_url.setPlaceholderText("http://192.168.1.10:8000")
        self.connection_enrollment_key = QLineEdit()
        self.connection_enrollment_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.connection_enrollment_key.setPlaceholderText("Required only for first enrollment or reset")
        self.connection_client_key = QLineEdit()
        self.connection_client_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.connection_client_key.setPlaceholderText("Required when Printer Server security is enabled")
        self.connection_admin_key = QLineEdit()
        self.connection_admin_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.connection_admin_key.setPlaceholderText("Optional · enables job retry and PC enable/disable")
        self.connection_insecure = QCheckBox("Allow Server Manager self-signed HTTPS certificate")
        self.connection_startup = QCheckBox("Start Printer Agent after Windows login")
        self.connection_show_keys = QCheckBox("Show security keys")
        self.connection_show_keys.toggled.connect(self._toggle_connection_key_visibility)
        form.addRow("Printer Server URL", self.connection_server_url)
        form.addRow("Enrollment Key", self.connection_enrollment_key)
        form.addRow("Client API Key", self.connection_client_key)
        form.addRow("Admin API Key", self.connection_admin_key)
        form.addRow("", self.connection_show_keys)
        form.addRow("", self.connection_insecure)
        form.addRow("", self.connection_startup)
        layout.addLayout(form)

        self.connection_page_status = QLabel("Ready")
        self.connection_page_status.setObjectName("AgentStatus")
        self.connection_page_status.setWordWrap(True)
        layout.addWidget(self.connection_page_status)
        action_row = QHBoxLayout()
        action_row.addStretch()
        save_button = QPushButton("Test, Enroll and Save")
        save_button.clicked.connect(self.save_connection_page)
        action_row.addWidget(save_button)
        layout.addLayout(action_row)
        layout.addStretch()
        self._load_connection_page()
        return page

    def _security_keys_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        note = QLabel(
            "Generate the three Printer Server security keys here. Copy the generated values to the "
            "Server PC's .env file using the variable names shown below, then restart the POS Server. "
            "Generating keys here does not change the Server automatically."
        )
        note.setWordWrap(True)
        note.setObjectName("AgentStatus")
        layout.addWidget(note)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        self.security_key_fields = {}
        key_rows = (
            ("Enrollment Key", "KAY_PRINTER_ENROLLMENT_KEY", "enrollment"),
            ("Client API Key", "KAY_PRINTER_CLIENT_KEY", "client"),
            ("Admin API Key", "KAY_PRINTER_ADMIN_KEY", "admin"),
        )
        for row, (label, variable_name, key_name) in enumerate(key_rows):
            field = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText("Click Generate")
            field.setToolTip(variable_name)
            self.security_key_fields[key_name] = field
            generate = QPushButton("Generate")
            generate.clicked.connect(lambda _checked=False, name=key_name: self._generate_key(name))
            copy = QPushButton("Copy")
            copy.clicked.connect(lambda _checked=False, name=key_name: self._copy_key(name))
            form.addWidget(QLabel(label), row, 0)
            form.addWidget(QLabel(variable_name), row, 1)
            form.addWidget(field, row, 2)
            form.addWidget(generate, row, 3)
            form.addWidget(copy, row, 4)
        form.setColumnStretch(2, 1)
        layout.addLayout(form)

        self.security_show_keys = QCheckBox("Show generated keys")
        self.security_show_keys.toggled.connect(self._toggle_security_key_visibility)
        layout.addWidget(self.security_show_keys)

        self.security_keys_status = QLabel("Keys are generated locally and are not saved by this page.")
        self.security_keys_status.setObjectName("AgentStatus")
        self.security_keys_status.setWordWrap(True)
        layout.addWidget(self.security_keys_status)

        actions = QHBoxLayout()
        generate_all = QPushButton("Generate All")
        generate_all.clicked.connect(self._generate_all_keys)
        copy_env = QPushButton("Copy .env Block")
        copy_env.clicked.connect(self._copy_env_block)
        use_keys = QPushButton("Use in Connection Setup")
        use_keys.clicked.connect(self._use_generated_keys)
        actions.addStretch()
        actions.addWidget(generate_all)
        actions.addWidget(copy_env)
        actions.addWidget(use_keys)
        layout.addLayout(actions)
        layout.addStretch()
        return page

    def _generate_key(self, key_name: str) -> None:
        self.security_key_fields[key_name].setText(generate_security_key())
        self.security_keys_status.setText(f"{key_name.title()} key generated locally. Copy it to the Server PC.")

    def _generate_all_keys(self) -> None:
        for key_name in self.security_key_fields:
            self.security_key_fields[key_name].setText(generate_security_key())
        self.security_keys_status.setText(
            "Three new keys generated. Copy the .env block to the Server PC and restart the POS Server."
        )

    def _copy_key(self, key_name: str) -> None:
        value = self.security_key_fields[key_name].text().strip()
        if not value:
            QMessageBox.warning(self, "Security Key", "Generate this key first.")
            return
        QApplication.clipboard().setText(value)
        self.security_keys_status.setText(f"{key_name.title()} key copied to the clipboard.")

    def _copy_env_block(self) -> None:
        values = {name: field.text().strip() for name, field in self.security_key_fields.items()}
        if not all(values.values()):
            QMessageBox.warning(self, "Security Keys", "Generate all three keys first.")
            return
        block = (
            f"KAY_PRINTER_ENROLLMENT_KEY={values['enrollment']}\n"
            f"KAY_PRINTER_CLIENT_KEY={values['client']}\n"
            f"KAY_PRINTER_ADMIN_KEY={values['admin']}"
        )
        QApplication.clipboard().setText(block)
        self.security_keys_status.setText(".env block copied. Paste it into the Server PC's .env file.")

    def _use_generated_keys(self) -> None:
        values = {name: field.text().strip() for name, field in self.security_key_fields.items()}
        if not all(values.values()):
            QMessageBox.warning(self, "Security Keys", "Generate all three keys first.")
            return
        self.connection_enrollment_key.setText(values["enrollment"])
        self.connection_client_key.setText(values["client"])
        self.connection_admin_key.setText(values["admin"])
        self._select_page(3)
        self.connection_page_status.setText(
            "Generated keys loaded. Apply the same keys on the Server PC and restart its POS Server before connecting."
        )

    def _toggle_security_key_visibility(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        for field in self.security_key_fields.values():
            field.setEchoMode(mode)

    def _load_connection_page(self) -> None:
        config = load_agent_config()
        self.connection_server_url.setText(str(config.get("server_url") or "http://127.0.0.1:8000"))
        self.connection_enrollment_key.clear()
        self.connection_client_key.setText(str(config.get("client_api_key") or ""))
        self.connection_admin_key.setText(str(config.get("admin_api_key") or ""))
        self.connection_insecure.setChecked(bool(config.get("insecure", False)))
        self.connection_startup.setChecked(startup_shortcut_path().is_file())

    def _toggle_connection_key_visibility(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.connection_enrollment_key.setEchoMode(mode)
        self.connection_client_key.setEchoMode(mode)
        self.connection_admin_key.setEchoMode(mode)

    def save_connection_page(self) -> None:
        server_url = self.connection_server_url.text().strip()
        if not server_url:
            QMessageBox.warning(self, "Printer Agent", "Printer Server URL is required.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            agent_key = load_agent_key()
            enrollment_key = self.connection_enrollment_key.text()
            if enrollment_key:
                agent_key = enroll_agent(server_url, enrollment_key, not self.connection_insecure.isChecked())
            agent, _ = run_agent_cycle(server_url, self.connection_insecure.isChecked(), agent_key)
            save_agent_config(
                server_url=server_url,
                insecure=self.connection_insecure.isChecked(),
                client_api_key=self.connection_client_key.text().strip(),
                admin_api_key=self.connection_admin_key.text().strip(),
            )
            set_windows_startup(self.connection_startup.isChecked())
            self.connection_enrollment_key.clear()
            message = (
                f"Connected as {agent.get('computer_name', 'this PC')} · "
                f"{len(agent.get('printers') or [])} printer(s) detected."
            )
            self.connection_page_status.setText(message)
            self.connection_status.setText("Printer Server: connected")
            QMessageBox.information(self, "Printer Agent", "Configuration saved successfully.")
            QTimer.singleShot(0, self.refresh_all)
        except Exception as exc:
            self.connection_page_status.setText(f"Connection failed: {exc}")
            QMessageBox.warning(self, "Printer Agent Setup", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    @staticmethod
    def _prepare_table(table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)

    def _request(self, method: str, path: str, *, admin: bool = False, **kwargs):
        config = load_agent_config()
        server_url = str(config.get("server_url") or "").strip()
        if not server_url:
            raise RuntimeError("Printer Server URL is not configured")
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(_api_headers(config, admin=admin))
        response = requests.request(
            method,
            f"{server_url.rstrip('/')}{path}",
            headers=headers,
            timeout=30,
            verify=not bool(config.get("insecure", False)),
            **kwargs,
        )
        response.raise_for_status()
        return response.json().get("data")

    def configure(self) -> None:
        self._load_connection_page()
        self._select_page(3)

    def refresh_all(self) -> None:
        self.refresh_printers()
        self.refresh_jobs()

    def _hidden_keys(self) -> set[str]:
        values = load_agent_config().get("hidden_printers") or []
        return {str(value) for value in values} if isinstance(values, list) else set()

    def _selected_printer(self) -> dict | None:
        row = self.printers_table.currentRow()
        if row < 0 and self.printers_table.rowCount() == 1:
            row = 0
            self.printers_table.selectRow(row)
        item = self.printers_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value if isinstance(value, dict) else None

    def refresh_printers(self) -> None:
        try:
            selected = self._selected_printer()
            selected_key = printer_visibility_key(
                selected.get("agent_id"), selected.get("printer_name")
            ) if selected else ""
            agents = self._request("GET", "/api/printer/agents") or []
            self.picture_page.set_printer_agents(agents)
            hidden = self._hidden_keys()
            self.printers_table.setRowCount(0)
            online = 0
            selected_row = -1
            for agent in agents:
                for printer in agent.get("printers") or [None]:
                    printer = printer or {}
                    name = str(printer.get("printer_name") or "")
                    key = printer_visibility_key(agent.get("agent_id"), name)
                    is_hidden = bool(name and key in hidden)
                    printer_enabled = bool(printer.get("is_enabled", True))
                    physical_online = (
                        bool(agent.get("is_online"))
                        and bool(agent.get("is_enabled", True))
                        and printer.get("status") == "online"
                    )
                    is_online = physical_online and printer_enabled
                    online += int(is_online)
                    if not self.show_hidden.isChecked() and (not is_online or is_hidden):
                        continue
                    target = {
                        "agent_id": agent.get("agent_id"),
                        "printer_name": name,
                        "is_online": is_online,
                        "is_enabled": bool(agent.get("is_enabled", True)),
                        "printer_enabled": printer_enabled,
                        "is_hidden": is_hidden,
                    }
                    status = (
                        "Disabled" if not bool(agent.get("is_enabled", True))
                        else "Disabled" if not printer_enabled
                        else "Online" if is_online else "Offline"
                    )
                    values = (
                        agent.get("computer_name"), agent.get("ip_address"), agent.get("agent_version"),
                        name or "No printer detected", "Yes" if printer.get("is_default") else "",
                        status, "Hidden" if is_hidden else "Shown",
                        printer.get("last_seen") or agent.get("last_seen"),
                    )
                    row = self.printers_table.rowCount()
                    self.printers_table.insertRow(row)
                    if key == selected_key:
                        selected_row = row
                    for column, value in enumerate(values):
                        item = QTableWidgetItem(str(value or ""))
                        item.setData(Qt.ItemDataRole.UserRole, target)
                        self.printers_table.setItem(row, column, item)
            if self.printers_table.rowCount():
                self.printers_table.selectRow(selected_row if selected_row >= 0 else 0)
            self.connection_status.setText(f"Printer Server: online · {online} printer(s) available")
            target = load_agent_config().get("virtual_printer_target") or {}
            self.virtual_target_label.setText(
                f"Virtual target: {target.get('computer_name')} · {target.get('printer_name')}"
                if target.get("printer_name") else "Virtual target: not selected"
            )
        except Exception as exc:
            self.printers_table.setRowCount(0)
            self.connection_status.setText(f"Printer Server: unavailable ({exc})")

    def set_virtual_target(self) -> None:
        target = self._online_target()
        if not target:
            return
        row = self.printers_table.currentRow()
        computer = self.printers_table.item(row, 0).text() if row >= 0 else "Remote PC"
        saved = {
            "agent_id": target["agent_id"], "printer_name": target["printer_name"],
            "computer_name": computer,
        }
        save_agent_config(virtual_printer_target=saved)
        self.virtual_target_label.setText(f"Virtual target: {computer} · {target['printer_name']}")
        if self.virtual_bridge:
            self.virtual_bridge.start()
        QMessageBox.information(self, "Virtual Printer", "Selected remote printer is now the KAY virtual target.")

    def install_virtual_queue(self) -> None:
        driver = self.virtual_driver.currentText().strip()
        if not driver:
            QMessageBox.warning(self, "Virtual Printer", "Install a PCL6 printer driver first.")
            return
        try:
            install_virtual_printer(driver)
            save_agent_config(virtual_printer_driver=driver)
            if self.virtual_bridge:
                self.virtual_bridge.start()
            QMessageBox.information(
                self, "Virtual Printer",
                f"{VIRTUAL_PRINTER_NAME} installed. It is now available in Photoshop, Office and Windows apps.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Virtual Printer Setup", str(exc))

    def remove_virtual_queue(self) -> None:
        try:
            remove_virtual_printer()
            QMessageBox.information(self, "Virtual Printer", f"{VIRTUAL_PRINTER_NAME} was removed.")
        except Exception as exc:
            QMessageBox.critical(self, "Virtual Printer Setup", str(exc))

    def _picture_job_queued(self, _job: dict) -> None:
        self.refresh_jobs()

    def refresh_jobs(self) -> None:
        try:
            jobs = self._request("GET", "/api/printer/jobs?limit=100", admin=True) or []
            self.jobs_table.setRowCount(0)
            for job in jobs:
                values = (
                    job.get("created_at"), job.get("computer_name") or job.get("target_agent_id"),
                    job.get("printer_name"), job.get("job_type"), job.get("status"),
                    f"{job.get('attempts', 0)}/{job.get('max_attempts', 0)}",
                    job.get("error_message"), job.get("job_id"),
                )
                row = self.jobs_table.rowCount()
                self.jobs_table.insertRow(row)
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value or ""))
                    item.setData(Qt.ItemDataRole.UserRole, job.get("job_id"))
                    self.jobs_table.setItem(row, column, item)
        except Exception as exc:
            self.jobs_table.setRowCount(0)
            self.jobs_table.setToolTip(f"Recent jobs unavailable: {exc}")

    def toggle_visibility(self) -> None:
        target = self._selected_printer()
        if not target and not self.printers_table.rowCount() and not self.show_hidden.isChecked():
            # A fully hidden printer list has no row the user can select. Reveal
            # hidden/offline rows and select the first one before continuing.
            self.show_hidden.setChecked(True)
            target = self._selected_printer()
        if not target or not target.get("printer_name"):
            QMessageBox.warning(
                self, "Select Printer",
                "No printer row is available. Turn on Show Hidden / Offline Printers, refresh, then select a row.",
            )
            return
        hidden = self._hidden_keys()
        key = printer_visibility_key(target.get("agent_id"), target.get("printer_name"))
        hidden.remove(key) if key in hidden else hidden.add(key)
        save_agent_config(hidden_printers=sorted(hidden))
        self.refresh_printers()

    def toggle_agent(self) -> None:
        target = self._selected_printer()
        if not target or not target.get("agent_id"):
            QMessageBox.warning(self, "Select PC", "Select a printer PC row first.")
            return
        try:
            self._request(
                "PUT", f"/api/printer/agents/{target['agent_id']}/permissions", admin=True,
                json={"enabled": not target.get("is_enabled", True), "allowed_job_types": []},
            )
            self.refresh_printers()
        except Exception as exc:
            QMessageBox.warning(self, "Agent Permission", str(exc))

    def toggle_printer(self) -> None:
        target = self._selected_printer()
        if not target or not target.get("agent_id") or not target.get("printer_name"):
            QMessageBox.warning(self, "Select Printer", "Select a printer row first.")
            return
        enabled = not bool(target.get("printer_enabled", True))
        try:
            self._request(
                "PUT", f"/api/printer/agents/{target['agent_id']}/printers/permissions",
                admin=True,
                json={"printer_name": target["printer_name"], "enabled": enabled},
            )
            hidden = self._hidden_keys()
            key = printer_visibility_key(target["agent_id"], target["printer_name"])
            if enabled:
                hidden.discard(key)
            else:
                hidden.add(key)
            save_agent_config(hidden_printers=sorted(hidden))
            self.refresh_printers()
        except Exception as exc:
            QMessageBox.warning(self, "Printer Permission", str(exc))

    def send_test_page(self) -> None:
        target = self._online_target()
        if not target:
            return
        try:
            job = self._request("POST", "/api/printer/jobs", json={
                "request_key": f"agent-test-{uuid.uuid4()}",
                "target_agent_id": target["agent_id"], "printer_name": target["printer_name"],
                "job_type": "test_page", "payload": {"requested_by": "KAY Printer Agent"},
                "copies": 1, "source_agent_id": "printer-agent-ui",
            })
            QMessageBox.information(self, "Print Test Page", f"Print job queued.\n{job.get('job_id', '')}")
            self.refresh_jobs()
        except Exception as exc:
            QMessageBox.critical(self, "Print Job Failed", str(exc))

    def _online_target(self) -> dict | None:
        target = self._selected_printer()
        if not target or not target.get("printer_name"):
            QMessageBox.warning(self, "Select Printer", "Select an available printer row first.")
            return None
        if not target.get("is_online"):
            QMessageBox.warning(self, "Printer Offline", "The selected PC or printer is currently offline.")
            return None
        return target

    def send_document(self) -> None:
        target = self._online_target()
        if not target:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Photo or Document", "",
            "Supported Documents (*.pdf *.png *.jpg *.jpeg *.bmp *.txt *.escpos *.bin)",
        )
        if not filename:
            return
        try:
            with Path(filename).open("rb") as stream:
                job = self._request(
                    "POST", "/api/printer/jobs/upload",
                    files={"file": (Path(filename).name, stream)},
                    data={
                        "target_agent_id": target["agent_id"], "printer_name": target["printer_name"],
                        "request_key": f"agent-document-{uuid.uuid4()}", "copies": self.copies.value(),
                        "paper_size": self.paper_size.currentText().upper(),
                        "orientation": self.orientation.currentText().lower(),
                        "source_agent_id": "printer-agent-ui",
                    },
                )
            QMessageBox.information(self, "Print Document", f"Document queued.\n{job.get('job_id', '')}")
            self.refresh_jobs()
        except Exception as exc:
            QMessageBox.critical(self, "Document Print Failed", str(exc))

    def retry_job(self) -> None:
        row = self.jobs_table.currentRow()
        item = self.jobs_table.item(row, 0) if row >= 0 else None
        job_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not job_id:
            QMessageBox.warning(self, "Select Print Job", "Select a failed print job first.")
            return
        try:
            self._request("POST", f"/api/printer/jobs/{job_id}/retry", admin=True)
            self.refresh_jobs()
        except Exception as exc:
            QMessageBox.warning(self, "Retry Print Job", str(exc))


class TrayAgent:
    def __init__(self, app: QApplication):
        self.app = app
        self.virtual_bridge = VirtualPrinterBridge(load_agent_config)
        self.virtual_bridge.start()
        app.aboutToQuit.connect(self.virtual_bridge.stop)
        self.tray = QSystemTrayIcon(_icon(), app)
        self.tray.setToolTip("KAY Printer Agent · Starting")
        menu = QMenu()
        self.status_action = QAction("Starting…", menu)
        self.status_action.setEnabled(False)
        open_manager = QAction("Open Printer Manager…", menu)
        open_manager.triggered.connect(self.open_manager)
        configure = QAction("Connection Setup…", menu)
        configure.triggered.connect(self.configure)
        check_now = QAction("Check Queue Now", menu)
        check_now.triggered.connect(self.poll)
        quit_action = QAction("Exit", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(self.status_action)
        menu.addSeparator()
        menu.addAction(open_manager)
        menu.addAction(check_now)
        menu.addAction(configure)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.dashboard = None
        self.timer = QTimer(app)
        self.timer.timeout.connect(self.poll)
        self.timer.start(10_000)
        self.tray.show()
        QTimer.singleShot(500, self.poll)

    def configure(self):
        self.open_manager(refresh=False)
        self.dashboard.configure()

    def open_manager(self, refresh: bool = True):
        if self.dashboard is None:
            self.dashboard = PrinterAgentDashboard(
                tray_icon=self.tray, virtual_bridge=self.virtual_bridge
            )
        if self.dashboard.isMinimized():
            self.dashboard.showNormal()
        else:
            self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()
        if refresh:
            # Let Qt paint and activate the window before any network request
            # can block on an offline Printer Server.
            QTimer.singleShot(150, self.dashboard.refresh_all)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_manager()

    def poll(self):
        config = load_agent_config()
        server_url = str(config.get("server_url") or "").strip()
        if not server_url:
            self._set_status("Not configured", error=True)
            return
        try:
            agent, completed = run_agent_cycle(
                server_url,
                bool(config.get("insecure", False)),
                load_agent_key(),
            )
            printers = len(agent.get("printers") or [])
            suffix = f" · printed {completed}" if completed else ""
            self._set_status(f"Online · {printers} printer(s){suffix}")
        except Exception as exc:
            self._set_status(f"Offline · reconnecting ({exc})", error=True)

    def _set_status(self, text: str, error: bool = False):
        self.status_action.setText(text)
        self.tray.setToolTip(f"KAY Printer Agent · {text}")
        if error:
            # The timer remains active, providing automatic reconnect without
            # interrupting the user with a popup every ten seconds.
            return


def run_setup_dialog() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setWindowIcon(_icon())
    return AgentSetupDialog().exec()


def run_tray_agent(open_manager: bool = False) -> int:
    guard = SingleInstanceGuard(r"Global\KAY_Printer_Agent_SingleInstance_v1")
    if not guard.acquire():
        show_already_running_message(
            title="KAY Printer Agent",
            message="KAY Printer Agent is already running on this computer.",
        )
        return 0
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("KAY Printer Agent")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_icon())
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "KAY Printer Agent", "Windows system tray is not available.")
        return 1
    runtime = TrayAgent(app)
    if open_manager:
        runtime.open_manager(refresh=False)
        QTimer.singleShot(150, runtime.dashboard.refresh_all)
    return app.exec()
