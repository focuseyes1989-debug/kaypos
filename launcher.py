"""KAY application hub for POS, Car Management, and Server Manager."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)
from utils.branded_icons import launcher_app_icon

APP_NAME = "KAY POS"
GITHUB_REPO = "focuseyes1989-debug/kaypos"
UPDATE_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.json"

INSTANCE_MUTEXES = {
    "pos": r"Global\KAY_POS_Main_SingleInstance_v1",
    "car": r"Global\KAY_Car_Management_SingleInstance_v1",
    "server": r"Global\KAY_POS_Server_Manager_SingleInstance_v1",
    "printer": r"Global\KAY_Printer_Agent_SingleInstance_v1",
    "lite": r"Global\KAY_POS_Lite_SingleInstance_v1",
}


class LauncherMode:
    MAIN = "main"
    CASHIER = "cashier"
    CAR = "car"
    SERVER = "server"
    LITE = "lite"


@dataclass(frozen=True)
class AppDefinition:
    key: str
    title: str
    subtitle: str
    description: str
    script_names: tuple[str, ...]
    exe_names: tuple[str, ...]
    accent: str
    glyph: str
    artwork: str
    launch_args: tuple[str, ...] = ()


APPLICATIONS = (
    AppDefinition("pos", "KAY POS", "Point of Sale", "ကုန်ပစ္စည်းစာရင်းများ၊ အရောင်း၊ အဝယ်၊ ကုန်ကျစရိတ်များနှင့် နေ့စဉ်လုပ်ငန်းများကို လွယ်ကူစွာ စီမံပါ။", ("main.py",), ("ZAY_POS.exe", "KAY_POS.exe"), "#6675f5", "P", "pos-system.png"),
    AppDefinition("car", "Car Management", "Vehicle Service", "ယာဉ်နှင့် ယာဉ်မောင်းများ မှတ်ပုံတင်ခြင်း၊ ဖောင်များပြင်ဆင်ခြင်းနှင့် QR ပရင့်တောင်းဆိုမှုများကို စီမံပါ။", ("car_client_main.py",), ("KAY_Car_Management.exe", "Car_Management.exe"), "#27c992", "C", "car-management.png"),
    AppDefinition("server", "Server Manager", "Services & Database", "ဘရောက်ဇာဝန်ဆောင်မှုများ စတင်ခြင်း၊ PostgreSQL စောင့်ကြည့်ခြင်းနှင့် ဆာဗာချိတ်ဆက်မှုကို စီမံပါ။", ("server_manager.py",), ("KAY_POS_Server_Manager.exe",), "#f3a64a", "S", "server-manager.png"),
    AppDefinition("printer", "Printer Agent", "LAN/Wi-Fi Printing", "ကွန်ရက်ပရင်တာများ၊ စာရွက်စာတမ်းပရင့်ထုတ်ခြင်းနှင့် လုံခြုံသောပရင့်အလုပ်များကို စီမံပါ။", ("printer_agent.py",), ("KAY_Printer_Agent.exe",), "#35a7ff", "P", "printer-server.png", ("--tray", "--open-manager")),
    AppDefinition("lite", "KAY POS Lite", "Low-End Point of Sale", "စက်အင်အားနည်းသော PC များအတွက် မြန်ဆန်ပေါ့ပါးသည့် အရောင်းနှင့် စတော့စီမံခန့်ခွဲမှု။", ("kay_pos_lite.py",), ("KAY_POS_Lite.exe",), "#5365df", "L", "pos-system.png"),
)

STYLE = """
QWidget { color:#edf2ff; font-family:"Segoe UI","Myanmar Text"; font-size:10pt; }
QMainWindow, QWidget#root { background:#0d111b; }
QFrame#sidebar { background:#111724; border-right:1px solid #252d3d; }
QLabel#brand { font-size:19pt; font-weight:800; color:white; }
QLabel#eyebrow { color:#8995ad; font-size:9pt; font-weight:700; letter-spacing:1px; }
QLabel#pageTitle { font-size:25pt; font-weight:800; color:white; }
QLabel#muted { color:#99a4ba; }
QLabel#clock { font-size:17pt; font-weight:700; color:white; }
QFrame#appCard { background:#151c2a; border:1px solid #293348; border-radius:18px; }
QFrame#appCard:hover { border-color:#465573; background:#192232; }
QLabel#cardTitle { font-size:13pt; font-weight:750; color:white; }
QLabel#cardSubtitle { color:#8f9bb3; font-weight:650; }
QLabel#description { color:#aab4c8; }
QLabel#badgeReady { color:#79e2bb; background:#17382f; border:1px solid #245744; border-radius:9px; padding:5px 9px; font-weight:700; }
QLabel#badgeRunning { color:#aeb7ff; background:#252d55; border:1px solid #46529a; border-radius:9px; padding:5px 9px; font-weight:700; }
QLabel#badgeMissing { color:#ff9ca7; background:#42242d; border:1px solid #713542; border-radius:9px; padding:5px 9px; font-weight:700; }
QPushButton#launchButton { min-height:42px; border:0; border-radius:11px; color:white; font-weight:750; padding:0 18px; }
QPushButton#launchButton:disabled { background:#313847; color:#707b91; }
QPushButton#sideButton { text-align:left; min-height:42px; border:0; border-radius:10px; background:transparent; color:#aeb8ca; padding:0 13px; font-weight:650; }
QPushButton#sideButton:hover { background:#1c2535; color:white; }
QFrame#statusBar { background:#121925; border:1px solid #253044; border-radius:12px; }
QLabel#statusText { color:#aeb9cd; }
"""


def get_app_dir() -> str:
    return str(Path(sys.executable).resolve().parent) if getattr(sys, "frozen", False) else str(Path(__file__).resolve().parent)


def get_python_executable(app_dir: Optional[str] = None, *, windowed: bool = False) -> str:
    candidates = []
    if app_dir:
        if windowed and os.name == "nt":
            candidates.append(Path(app_dir) / "pythonw.exe")
        candidates.extend((Path(app_dir) / "python.exe", Path(app_dir) / "python"))
    if windowed and os.name == "nt":
        current = Path(sys.executable)
        candidates.extend((current.with_name("pythonw.exe"), Path(shutil.which("pythonw") or "")))
    candidates.extend(Path(value) for value in (sys.executable, shutil.which("python") or "") if value)
    return next((str(path) for path in candidates if path.is_file()), sys.executable)


def _search_roots(app_dir: Optional[str]) -> list[Path]:
    root = Path(app_dir or get_app_dir()).resolve()
    return [root, root.parent] if root.parent != root else [root]


def _definition_for_mode(mode: str) -> AppDefinition:
    if mode == LauncherMode.CASHIER:
        return AppDefinition("cashier", "Cashier", "Cashier Mode", "Cashier mode", ("cashier_main.py",), ("ZAY_POS_Cashier.exe", "cashier_main.exe"), "#6675f5", "C", "pos-system.png")
    if mode == LauncherMode.CAR:
        return APPLICATIONS[1]
    if mode == LauncherMode.SERVER:
        return APPLICATIONS[2]
    if mode == LauncherMode.LITE:
        return next(item for item in APPLICATIONS if item.key == "lite")
    return APPLICATIONS[0]


def resolve_application_target(definition: AppDefinition, app_dir: Optional[str] = None) -> tuple[list[str], str]:
    roots = _search_roots(app_dir)
    groups = ((definition.exe_names, "exe"), (definition.script_names, "script")) if getattr(sys, "frozen", False) else ((definition.script_names, "script"), (definition.exe_names, "exe"))
    for names, source in groups:
        for root in roots:
            for name in names:
                candidate = root / name
                if candidate.is_file():
                    command = ([get_python_executable(str(root), windowed=True), str(candidate)] if source == "script" else [str(candidate)])
                    return command + list(definition.launch_args), source
    return [], "missing"


def resolve_launch_target(app_dir: Optional[str] = None, mode: str = LauncherMode.MAIN) -> tuple[list[str], str]:
    return resolve_application_target(_definition_for_mode(mode), app_dir)


def should_auto_download_update(available: bool, auto_update_enabled: bool) -> bool:
    return bool(available and auto_update_enabled)


def is_application_running(key: str) -> bool:
    """Detect apps launched by this or an earlier Launcher process."""
    mutex_name = INSTANCE_MUTEXES.get(key)
    if not mutex_name:
        return False
    from utils.single_instance import is_single_instance_running

    return is_single_instance_running(mutex_name)


def current_version() -> str:
    path = Path(get_app_dir()) / "version.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("version") or "—") if path.is_file() else "—"
    except (OSError, ValueError, json.JSONDecodeError):
        return "—"


def fetch_latest_update() -> dict:
    try:
        with urlopen(Request(UPDATE_URL, headers={"User-Agent": "KAY-POS-Launcher"}), timeout=12) as response:
            data = json.loads(response.read(1024 * 1024).decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Update check failed: {exc}") from exc
    latest = str(data.get("version") or "")
    return {"version": latest, "release_notes": data.get("release_notes") or data.get("notes") or "", "download_url": data.get("download_url") or "", "file_size": data.get("file_size") or 0, "available": bool(latest and latest != current_version())}


def check_only() -> int:
    try:
        result = fetch_latest_update()
        notes = str(result.get("release_notes") or "").splitlines()
        print(f"version: {result.get('version', '')}")
        print(f"notes: {notes[0] if notes else ''}")
        print(f"url: {result.get('download_url') or ''}")
        print(f"size: {result.get('file_size') or 0}")
        print(f"available: {1 if result.get('available') else 0}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def apply_launcher_font(app: QApplication) -> None:
    fonts_dir = Path(get_app_dir()) / "assets" / "fonts"
    for filename in ("mmrtext.ttf", "NotoSansMyanmar-Regular.ttf"):
        path = fonts_dir / filename
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Myanmar Text" if "Myanmar Text" in set(QFontDatabase.families()) else "Segoe UI", 10))


def launcher_icon() -> QIcon:
    return launcher_app_icon()


class AppCard(QFrame):
    launch_requested = pyqtSignal(str)

    def __init__(self, definition: AppDefinition, parent=None):
        super().__init__(parent)
        self.definition = definition
        self.setObjectName("appCard")
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body = QVBoxLayout(self)
        body.setContentsMargins(14, 14, 14, 13)
        body.setSpacing(7)
        top = QHBoxLayout()
        glyph = QLabel(definition.glyph)
        glyph.setFixedSize(44, 44)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setStyleSheet(f"background:{definition.accent};color:white;border-radius:15px;font-size:20pt;font-weight:900;")
        top.addWidget(glyph)
        top.addStretch()
        self.badge = QLabel("READY")
        self.badge.setObjectName("badgeReady")
        top.addWidget(self.badge)
        body.addLayout(top)
        title = QLabel(definition.title)
        title.setObjectName("cardTitle")
        subtitle = QLabel(definition.subtitle.upper())
        subtitle.setObjectName("cardSubtitle")
        description = QLabel(definition.description)
        description.setObjectName("description")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        description.setMinimumHeight(72)
        body.addWidget(title)
        body.addWidget(subtitle)
        body.addSpacing(3)
        body.addWidget(description)
        artwork = ArtworkLabel(Path(get_app_dir()) / "assets" / "launcher" / definition.artwork)
        body.addWidget(artwork, 1)
        self.launch_button = QPushButton("Open Application")
        self.launch_button.setObjectName("launchButton")
        self._apply_launch_button_style("ready")
        self.launch_button.clicked.connect(lambda: self.launch_requested.emit(definition.key))
        body.addWidget(self.launch_button)

    def _apply_launch_button_style(self, state: str) -> None:
        if state == "missing":
            background, foreground, border = "#313847", "#aab4c8", "#3d475a"
        else:
            background, foreground, border = self.definition.accent, "#ffffff", self.definition.accent
        self.launch_button.setStyleSheet(f"""
            QPushButton#launchButton,
            QPushButton#launchButton:disabled {{
                background: {background};
                color: {foreground};
                border: 1px solid {border};
            }}
        """)

    def set_state(self, state: str, detail="") -> None:
        states = {"running": ("RUNNING", "badgeRunning", "Already Running", False), "missing": ("NOT FOUND", "badgeMissing", "Application Missing", False), "ready": ("READY", "badgeReady", "Open Application", True)}
        label, object_name, button_text, enabled = states.get(state, states["ready"])
        self.badge.setText(label)
        self.badge.setObjectName(object_name)
        self.launch_button.setText(button_text)
        self.launch_button.setEnabled(enabled)
        self._apply_launch_button_style(state)
        self.setToolTip(detail)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)


class ArtworkLabel(QLabel):
    """Keep launcher artwork sharp and proportional as a card resizes."""

    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.source = QPixmap(str(image_path))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(55)
        self.setMaximumHeight(105)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.source.isNull():
            target = self.contentsRect().size()
            self.setPixmap(self.source.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KAY Application Launcher")
        self.setWindowIcon(launcher_icon())
        self.setMinimumSize(1050, 620)
        self.resize(1320, 700)
        self.setStyleSheet(STYLE)
        self.processes: dict[str, subprocess.Popen] = {}
        self.cards: dict[str, AppCard] = {}
        self._build_ui()
        self.refresh_targets()
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self.refresh_processes)
        self.process_timer.start(1500)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        mark = QLabel("K")
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet("background:#6675f5;color:white;border-radius:12px;font-size:17pt;font-weight:900;")
        header.addWidget(mark)
        heading = QVBoxLayout()
        eyebrow = QLabel(f"KAY APPLICATION SUITE  ·  VERSION {current_version()}")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Choose an application")
        title.setObjectName("pageTitle")
        hint = QLabel("KAY Application Suite က သင့်လုပ်ငန်းကို ပိုမိုမြန်ဆန်စေမှာပါ")
        hint.setObjectName("muted")
        heading.addWidget(eyebrow)
        heading.addWidget(title)
        heading.addWidget(hint)
        header.addLayout(heading)
        header.addStretch()
        refresh = QPushButton("↻  Refresh")
        refresh.setObjectName("sideButton")
        refresh.clicked.connect(self.refresh_targets)
        logs = QPushButton("▣  Logs")
        logs.setObjectName("sideButton")
        logs.clicked.connect(lambda: self.open_folder("logs"))
        data = QPushButton("▤  Data")
        data.setObjectName("sideButton")
        data.clicked.connect(lambda: self.open_folder("database"))
        header.addWidget(refresh)
        header.addWidget(logs)
        header.addWidget(data)
        clock_box = QVBoxLayout()
        self.clock_label = QLabel()
        self.clock_label.setObjectName("clock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_label = QLabel()
        self.date_label.setObjectName("muted")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.date_label)
        header.addLayout(clock_box)
        layout.addLayout(header)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        column_count = 5
        for index, definition in enumerate(APPLICATIONS):
            card = AppCard(definition)
            card.launch_requested.connect(self.launch_application)
            self.cards[definition.key] = card
            row, column = divmod(index, column_count)
            grid.addWidget(card, row, column)
            grid.setColumnStretch(column, 1)
            grid.setRowStretch(row, 1)
        layout.addLayout(grid, 1)
        status = QFrame()
        status.setObjectName("statusBar")
        status_row = QHBoxLayout(status)
        status_row.setContentsMargins(15, 10, 15, 10)
        dot = QLabel("●")
        dot.setStyleSheet("color:#55d9a5;")
        self.status_label = QLabel("Launcher ready")
        self.status_label.setObjectName("statusText")
        status_row.addWidget(dot)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(QLabel("Applications continue running when this launcher closes."))
        layout.addWidget(status)
        shell.addWidget(content, 1)

    def _update_clock(self) -> None:
        now = datetime.now()
        self.clock_label.setText(now.strftime("%I:%M:%S %p"))
        self.date_label.setText(now.strftime("%A, %d %B %Y"))

    def refresh_targets(self) -> None:
        ready = 0
        for definition in APPLICATIONS:
            command, source = resolve_application_target(definition)
            if is_application_running(definition.key):
                self.cards[definition.key].set_state("running")
            elif command:
                ready += 1
                self.cards[definition.key].set_state("ready", source)
            else:
                self.cards[definition.key].set_state("missing", ", ".join(definition.script_names + definition.exe_names))
        self.status_label.setText(f"{ready} application(s) ready · workspace {Path(get_app_dir()).name}")

    def refresh_processes(self) -> None:
        finished = [(key, process.poll()) for key, process in self.processes.items() if process.poll() is not None]
        for key, code in finished:
            self.processes.pop(key, None)
            title = next(item.title for item in APPLICATIONS if item.key == key)
            self.status_label.setText(f"{title} closed" if code == 0 else f"{title} exited with code {code}")
        # Also discovers apps that survived a previous Launcher process or were
        # opened directly from their executable.
        self.refresh_targets()

    def launch_application(self, key: str) -> None:
        definition = next((item for item in APPLICATIONS if item.key == key), None)
        if not definition:
            return
        if is_application_running(key):
            self.status_label.setText(f"{definition.title} is already running")
            self.cards[key].set_state("running")
            return
        command, source = resolve_application_target(definition)
        if not command:
            QMessageBox.warning(self, "Application Not Found", f"Could not find {definition.title}.\n\nExpected: {', '.join(definition.script_names + definition.exe_names)}")
            self.refresh_targets()
            return
        try:
            flags = 0
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(command, cwd=get_app_dir(), close_fds=True, creationflags=flags)
        except OSError as exc:
            QMessageBox.critical(self, "Could Not Launch", f"{definition.title} could not start.\n\n{exc}")
            return
        self.processes[key] = process
        self.cards[key].set_state("running")
        self.status_label.setText(f"Opened {definition.title} from {source}")

    def open_folder(self, name: str) -> None:
        target = Path(get_app_dir()) / name
        target.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except OSError as exc:
            QMessageBox.warning(self, "Could Not Open Folder", str(exc))


def main() -> int:
    if "--check-only" in sys.argv:
        return check_only()
    app = QApplication(sys.argv)
    app.setApplicationName("KAY Application Launcher")
    app.setOrganizationName("KAY POS")
    app.setStyle("Fusion")
    apply_launcher_font(app)
    app.setWindowIcon(launcher_icon())
    window = LauncherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
