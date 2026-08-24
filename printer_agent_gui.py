"""Setup dialog and system-tray runtime for the KAY Printer Agent."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
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


def _icon() -> QIcon:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for relative in ("assets/icons/app_icon.ico", "assets/kay/kay_multi.ico"):
        path = base / relative
        if path.is_file():
            return QIcon(str(path))
    return QIcon()


class AgentSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KAY Printer Agent Setup")
        self.setWindowIcon(_icon())
        self.setMinimumWidth(540)
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
        self.insecure = QCheckBox("Allow Server Manager self-signed HTTPS certificate")
        self.insecure.setChecked(bool(config.get("insecure", False)))
        self.startup = QCheckBox("Start Printer Agent after Windows login")
        self.startup.setChecked(startup_shortcut_path().is_file())
        form.addRow("Printer Server URL", self.server_url)
        form.addRow("Enrollment Key", self.enrollment_key)
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
            save_agent_config(server_url=server_url, insecure=self.insecure.isChecked())
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


class TrayAgent:
    def __init__(self, app: QApplication):
        self.app = app
        self.tray = QSystemTrayIcon(_icon(), app)
        self.tray.setToolTip("KAY Printer Agent · Starting")
        menu = QMenu()
        self.status_action = QAction("Starting…", menu)
        self.status_action.setEnabled(False)
        configure = QAction("Configure…", menu)
        configure.triggered.connect(self.configure)
        check_now = QAction("Check Queue Now", menu)
        check_now.triggered.connect(self.poll)
        quit_action = QAction("Exit", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(self.status_action)
        menu.addSeparator()
        menu.addAction(check_now)
        menu.addAction(configure)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.timer = QTimer(app)
        self.timer.timeout.connect(self.poll)
        self.timer.start(10_000)
        self.tray.show()
        QTimer.singleShot(0, self.poll)

    def configure(self):
        AgentSetupDialog().exec()
        QTimer.singleShot(0, self.poll)

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


def run_tray_agent() -> int:
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
    return app.exec()
