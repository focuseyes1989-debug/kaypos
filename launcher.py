# launcher.py
"""
ZAY POS Launcher - Modern Design with Logo
"""

import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import hashlib
import zipfile
import re
import importlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple, List


class LauncherMode:
    MAIN = "main"
    CASHIER = "cashier"

# ============================================================
# ✅ FIX: Set console encoding to UTF-8 for Windows (safe version)
# ============================================================
if sys.platform == 'win32':
    try:
        import io
        # Only wrap if stdout exists and has buffer
        if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # Fallback to default encoding

# Try importing requests with fallback
try:
    import requests
except ImportError:
    print("WARNING: requests not found, installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTextEdit, QMessageBox,
    QFrame, QGroupBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, qInstallMessageHandler
pyqtProperty = None
try:
    pyqt_property_module = importlib.import_module('PyQt6.QtCore')
    pyqtProperty = getattr(pyqt_property_module, 'pyqtProperty', None)
except Exception:  # pragma: no cover - compatibility fallback
    pyqtProperty = None
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QLinearGradient, QBrush, QPalette, QFontDatabase

# Configuration
GITHUB_REPO = "focuseyes1989-debug/ZAY_POS"
APP_NAME = "ZAY_POS"


def qt_message_handler(_msg_type, _context, message):
    """Hide harmless Qt warnings that confuse users during startup."""
    if "SetProcessDpiAwarenessContext() failed" in message:
        return
    if "DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2" in message:
        return
    print(f"Qt: {message}")


qInstallMessageHandler(qt_message_handler)


def apply_launcher_font(app):
    """Use bundled Myanmar Text as the launcher UI font when available."""
    fonts_dir = Path(get_app_dir()) / "assets" / "fonts"
    font_path = fonts_dir / "mmrtext.ttf"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))

    families = set(QFontDatabase.families())
    if "Myanmar Text" in families:
        app.setFont(QFont("Myanmar Text", 10))
    elif "Noto Sans Myanmar" in families:
        app.setFont(QFont("Noto Sans Myanmar", 10))
    else:
        app.setFont(QFont("Segoe UI", 10))


def get_app_dir():
    """Return the folder where the launcher should read/write app files."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def get_python_executable(app_dir: Optional[str] = None) -> str:
    """Resolve a usable Python interpreter for launching scripts."""
    candidates: List[str] = []
    if app_dir:
        candidates.extend([
            os.path.join(app_dir, 'python.exe'),
            os.path.join(app_dir, 'python'),
            os.path.join(app_dir, 'Python.exe'),
        ])

    candidates.extend([
        sys.executable,
        shutil.which('python') or '',
        shutil.which('python3') or '',
        shutil.which('py') or '',
    ])

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return sys.executable


def resolve_launch_target(app_dir: Optional[str] = None, mode: str = LauncherMode.MAIN) -> Tuple[List[str], str]:
    """Resolve the best app entry point for the selected launcher mode.

    The launcher now prefers Python entry points so main.py and cashier_main.py can
    be run directly without requiring separate .exe builds.
    """
    base_dir = Path(app_dir or get_app_dir()).resolve()
    search_roots = [base_dir]
    parent_dir = base_dir.parent
    if parent_dir != base_dir:
        search_roots.append(parent_dir)

    script_names = [
        'main.py',
        'cashier_main.py',
        'launcher.py',
    ]
    if mode == LauncherMode.CASHIER:
        script_names = ['cashier_main.py', 'main.py', 'launcher.py']

    exe_names = [
        'ZAY_POS.exe',
        'main.exe',
        'cashier_main.exe',
        'ZAY_POS_main.exe',
    ]

    for root in search_roots:
        for name in script_names:
            candidate = root / name
            if candidate.exists() and candidate.is_file():
                python_executable = get_python_executable(str(root))
                return [python_executable, str(candidate)], 'script'

        for name in exe_names:
            candidate = root / name
            if candidate.exists() and candidate.is_file():
                return [str(candidate)], 'exe'

    for root in search_roots:
        for pattern in ('**/main.py', '**/cashier_main.py', '**/ZAY_POS.exe'):
            for candidate in root.glob(pattern):
                if candidate.is_file():
                    if candidate.suffix.lower() == '.py':
                        python_executable = get_python_executable(str(root))
                        return [python_executable, str(candidate)], 'script'
                    return [str(candidate)], 'exe'

    return [], 'missing'


def should_auto_download_update(available: bool, auto_update_enabled: bool) -> bool:
    """Return True when the launcher should auto-download an available update."""
    return bool(available and auto_update_enabled)


def normalize_version(value: str) -> str:
    """Extract a dotted numeric version from values like v1.0.3."""
    match = re.search(r'\d+(?:\.\d+)+', str(value or ''))
    return match.group(0) if match else ""


def extract_version_from_text(content: str) -> Optional[str]:
    """Read version text from PyInstaller version files or simple metadata files."""
    patterns = [
        r'ProductVersion\s*=\s*["\']([\d.]+)["\']',
        r'FileVersion\s*=\s*["\']([\d.]+)["\']',
        r'StringStruct\(\s*u?["\']ProductVersion["\']\s*,\s*u?["\']([\d.]+)["\']\s*\)',
        r'StringStruct\(\s*u?["\']FileVersion["\']\s*,\s*u?["\']([\d.]+)["\']\s*\)',
        r'"version"\s*:\s*"([\d.]+)"',
        r'version\s*=\s*["\']([\d.]+)["\']',
        r'Version\s*[:=]\s*([\d.]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            version = normalize_version(match.group(1))
            if version:
                return version
    return None


def get_update_download_info(data: Dict) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Return the best update zip URL from GitHub release data or version.json data."""
    assets = data.get('assets') or []
    zip_assets = [
        asset for asset in assets
        if str(asset.get('name', '')).lower().endswith('.zip') and asset.get('browser_download_url')
    ]
    preferred_assets = [
        asset for asset in zip_assets
        if 'update' in str(asset.get('name', '')).lower()
    ]
    candidates = preferred_assets or zip_assets
    if candidates:
        asset = candidates[0]
        return asset.get('browser_download_url'), asset.get('name'), asset.get('size')

    download_url = data.get('download_url')
    if download_url:
        return download_url, os.path.basename(download_url), data.get('file_size')

    return None, None, None


def fetch_latest_update(log_callback=None) -> Dict:
    """Fetch latest update metadata from GitHub release API or version.json."""
    def log(message: str):
        if log_callback:
            log_callback(message)

    urls = [
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/update_build/version.json",
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.json"
    ]

    errors = []
    for url in urls:
        try:
            log(f"Fetching: {url}")
            response = requests.get(
                url,
                timeout=10,
                headers={'User-Agent': 'ZAY-POS-Launcher/1.0'}
            )
            if response.status_code != 200:
                errors.append(f"{url} returned HTTP {response.status_code}")
                continue

            data = response.json()
            latest_version = normalize_version(data.get('tag_name') or data.get('version'))
            if not latest_version:
                errors.append(f"{url} did not include a valid version")
                continue

            download_url, asset_name, file_size = get_update_download_info(data)
            return {
                'version': latest_version,
                'data': data,
                'available': compare_versions(latest_version, CURRENT_VERSION) > 0,
                'download_url': download_url,
                'asset_name': asset_name,
                'file_size': file_size,
                'release_notes': data.get('body') or data.get('release_notes') or '',
            }
        except Exception as e:
            errors.append(f"{url}: {e}")
            log(f"Failed: {e}")

    raise RuntimeError("; ".join(errors) if errors else "All update sources failed")


def compare_versions(v1: str, v2: str) -> int:
    def parse(v):
        version = normalize_version(v)
        try:
            return [int(x) for x in version.split('.')]
        except Exception:
            return [0, 0, 0]

    a = parse(v1)
    b = parse(v2)
    for i in range(max(len(a), len(b))):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        if av < bv:
            return -1
        if av > bv:
            return 1
    return 0

# Try to get current version from version.txt
def get_current_version():
    """Get current version from version.txt file."""
    try:
        app_dir = get_app_dir()
        version_file = os.path.join(app_dir, 'version.txt')
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                version = extract_version_from_text(f.read())
                if version:
                    return version
    except:
        pass
    return "1.0.0"

CURRENT_VERSION = get_current_version()


# ============================================================================
# MODERN STYLESHEET
# ============================================================================
STYLESHEET = """
/* Main Window */
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0f172a, stop:0.45 #111827, stop:1 #0b1220);
    border: none;
}

/* Central Widget */
QWidget#centralWidget {
    background: transparent;
}

/* Title Label */
QLabel#titleLabel {
    color: #ffffff;
    font-size: 22pt;
    font-weight: bold;
    font-family: 'Segoe UI', 'Arial';
    letter-spacing: 1px;
}

QLabel#subTitleLabel {
    color: #a8b2d1;
    font-size: 10pt;
    font-family: 'Segoe UI', 'Arial';
}

/* Version Group */
QGroupBox {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 12px;
    padding-bottom: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 10px;
    color: #64ffda;
    font-size: 10pt;
    font-weight: bold;
}

/* Version Labels */
QLabel#versionCurrent {
    color: #ffffff;
    font-size: 16pt;
    font-weight: bold;
}

QLabel#versionLatest {
    color: #64ffda;
    font-size: 16pt;
    font-weight: bold;
}

QLabel#versionLabel {
    color: #8892b0;
    font-size: 9pt;
}

/* Status Group */
QGroupBox#statusGroup {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    margin-top: 10px;
    padding-top: 12px;
    padding-bottom: 8px;
}

QGroupBox#statusGroup::title {
    color: #64ffda;
}

QLabel#statusLabel {
    color: #64ffda;
    font-size: 11pt;
    padding: 5px;
}

/* Progress Bar */
QProgressBar {
    background: rgba(255, 255, 255, 0.1);
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #64ffda, stop:1 #00b4d8);
    border-radius: 6px;
}

/* Log Group */
QGroupBox#logGroup {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    margin-top: 10px;
    padding-top: 12px;
    padding-bottom: 8px;
}

QGroupBox#logGroup::title {
    color: #8892b0;
}

QTextEdit {
    background: rgba(0, 0, 0, 0.3);
    border: none;
    border-radius: 8px;
    color: #ccd6f6;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    padding: 8px;
}

QTextEdit:focus {
    border: none;
}

/* Buttons */
QPushButton {
    border: none;
    border-radius: 8px;
    padding: 12px 25px;
    font-size: 11pt;
    font-weight: bold;
    font-family: 'Segoe UI', 'Arial';
    color: white;
}

QPushButton#startBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #10b981, stop:1 #14b8a6);
}

QPushButton#startBtn:hover:!disabled {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00d2d3, stop:1 #55efc4);
}

QPushButton#startBtn:disabled {
    background: #2d3436;
    color: #636e72;
}

QPushButton#updateBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:1 #6366f1);
}

QPushButton#updateBtn:hover:!disabled {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #74b9ff, stop:1 #a29bfe);
}

QPushButton#updateBtn:disabled {
    background: #2d3436;
    color: #636e72;
}

QPushButton#skipBtn {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

QPushButton#skipBtn:hover:!disabled {
    background: rgba(255, 255, 255, 0.2);
}

QPushButton#skipBtn:disabled {
    background: rgba(255, 255, 255, 0.03);
    color: #636e72;
}

QPushButton#modeBtnActive {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:1 #6366f1);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: white;
}

QPushButton#modeBtnInactive {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(148, 163, 184, 0.18);
    color: #cbd5e1;
}

/* Note Label */
QLabel#noteLabel {
    color: #495670;
    font-size: 9pt;
    font-style: italic;
}

/* Scrollbar */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.3);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* Logo label */
QLabel#logoLabel {
    background: transparent;
}
"""

# ============================================================================
# CUSTOM MESSAGE BOX STYLESHEET
# ============================================================================
MESSAGE_BOX_STYLESHEET = """
QDialog {
    background-color: #1a1a2e;
    border: 1px solid #2d3436;
    border-radius: 12px;
}

QLabel {
    color: #ffffff;
    font-size: 11pt;
    font-family: 'Segoe UI', 'Arial';
}

QPushButton {
    border: none;
    border-radius: 8px;
    padding: 10px 30px;
    font-size: 11pt;
    font-weight: bold;
    font-family: 'Segoe UI', 'Arial';
    color: white;
    min-width: 80px;
}

QPushButton[text="Yes"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00b894, stop:1 #00cec9);
}

QPushButton[text="Yes"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00d2d3, stop:1 #55efc4);
}

QPushButton[text="No"] {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

QPushButton[text="No"]:hover {
    background: rgba(255, 255, 255, 0.2);
}

QPushButton[text="OK"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0984e3, stop:1 #6c5ce7);
}

QPushButton[text="OK"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #74b9ff, stop:1 #a29bfe);
}

QPushButton[text="Cancel"] {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

QPushButton[text="Cancel"]:hover {
    background: rgba(255, 255, 255, 0.2);
}

QDialogButtonBox {
    background: transparent;
    border: none;
}
"""


def load_logo():
    """Load logo from assets/icons/zaypos.png."""
    logo_paths = [
        "assets/icons/zaypos.png",
        "assets/icons/zaypos.ico",
        "assets/icons/app_icon.png",
        "../assets/icons/zaypos.png",
    ]
    
    # If running as frozen exe
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        logo_paths = [
            os.path.join(app_dir, "assets/icons/zaypos.png"),
            os.path.join(app_dir, "assets/icons/zaypos.ico"),
            os.path.join(app_dir, "assets/icons/app_icon.png"),
        ]
    
    for path in logo_paths:
        if os.path.exists(path):
            try:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    # Scale logo to fit
                    return pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            except:
                pass
    return None


def load_window_icon():
    """Load window icon from assets/icons/app_icon.ico."""
    icon_paths = [
        "assets/icons/app_icon.ico",
        "assets/icons/zaypos.ico",
        "assets/icons/app_icon.png",
        "../assets/icons/app_icon.ico",
    ]
    
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        icon_paths = [
            os.path.join(app_dir, "assets/icons/app_icon.ico"),
            os.path.join(app_dir, "assets/icons/zaypos.ico"),
            os.path.join(app_dir, "assets/icons/app_icon.png"),
        ]
    
    for path in icon_paths:
        if os.path.exists(path):
            try:
                icon = QIcon(path)
                if not icon.isNull():
                    return icon
            except:
                pass
    return None


def custom_message_box(parent, title, message, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, default_button=QMessageBox.StandardButton.Yes):
    """
    Custom message box with proper styling for dark theme.
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(buttons)
    msg_box.setDefaultButton(default_button)

    # Apply custom stylesheet
    msg_box.setStyleSheet(MESSAGE_BOX_STYLESHEET)

    # Set text color for buttons using QDialogButtonBox
    for button in msg_box.buttons():
        if button.text() == "Yes":
            button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #00b894, stop:1 #00cec9);
                    border: none;
                    border-radius: 8px;
                    padding: 10px 30px;
                    font-size: 11pt;
                    font-weight: bold;
                    color: white;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #00d2d3, stop:1 #55efc4);
                }
            """)
        elif button.text() == "No":
            button.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    padding: 10px 30px;
                    font-size: 11pt;
                    font-weight: bold;
                    color: white;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.2);
                }
            """)
        elif button.text() == "OK":
            button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #0984e3, stop:1 #6c5ce7);
                    border: none;
                    border-radius: 8px;
                    padding: 10px 30px;
                    font-size: 11pt;
                    font-weight: bold;
                    color: white;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #74b9ff, stop:1 #a29bfe);
                }
            """)
        elif button.text() == "Cancel":
            button.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    padding: 10px 30px;
                    font-size: 11pt;
                    font-weight: bold;
                    color: white;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.2);
                }
            """)

    return msg_box.exec()


class UpdateCheckerThread(QThread):
    """Background thread for checking updates."""
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._is_cancelled = False
        
    def run(self):
        try:
            self.log.emit("Checking for updates...")
            self.finished.emit(fetch_latest_update(self.log.emit))
                
        except Exception as e:
            self.error.emit(str(e))
    
    def compare_versions(self, v1: str, v2: str) -> int:
        return compare_versions(v1, v2)


class DownloadThread(QThread):
    """Thread for downloading updates."""
    
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    
    def __init__(self, download_url: str, version: str):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self._is_cancelled = False
        self.download_path = None
        
    def run(self):
        try:
            self.log.emit(f"Downloading update v{self.version}...")
            
            temp_dir = tempfile.mkdtemp(prefix='zay_update_')
            self.download_path = os.path.join(temp_dir, 'update.zip')
            
            response = requests.get(
                self.download_url,
                stream=True,
                timeout=30,
                headers={'User-Agent': 'ZAY-POS-Launcher/1.0'}
            )
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(self.download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self._is_cancelled:
                        self.finished.emit(False, "Download cancelled")
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress.emit(progress, f"Downloading... {progress}%")

            if downloaded == 0:
                raise ValueError("Downloaded file is empty")
            if not zipfile.is_zipfile(self.download_path):
                raise ValueError("Downloaded file is not a valid zip update package")
            
            self.log.emit(f"Download complete: {downloaded // 1024} KB")
            self.finished.emit(True, self.download_path)
            
        except Exception as e:
            self.log.emit(f"Download failed: {e}")
            self.finished.emit(False, str(e))
    
    def cancel(self):
        self._is_cancelled = True


class InstallThread(QThread):
    """Thread for installing updates - skips launcher files."""
    
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    
    def __init__(self, zip_path: str, expected_version: str = ""):
        super().__init__()
        self.zip_path = zip_path
        self.expected_version = expected_version
        self._is_cancelled = False

    def _get_install_source_dir(self, extract_dir: str) -> str:
        """Support both flat update zips and full release zips with one root folder."""
        if os.path.exists(os.path.join(extract_dir, 'ZAY_POS.exe')):
            return extract_dir

        entries = [
            os.path.join(extract_dir, entry)
            for entry in os.listdir(extract_dir)
            if not entry.startswith('__MACOSX')
        ]
        dirs = [entry for entry in entries if os.path.isdir(entry)]
        if len(dirs) == 1 and os.path.exists(os.path.join(dirs[0], 'ZAY_POS.exe')):
            return dirs[0]

        return extract_dir

    def _should_skip_file(self, rel_path: str) -> bool:
        parts = Path(rel_path).parts
        if not parts:
            return True

        runtime_dirs = {'database', 'logs', 'temp', 'attachments'}
        if parts[0].lower() in runtime_dirs:
            return True

        lowered = rel_path.lower()
        if '__pycache__' in parts or lowered.endswith('.pyc'):
            return True

        skip_files = {
            'zay_pos_launcher.exe',
            'zay_pos_launcher',
        }
        return os.path.basename(lowered) in skip_files

    def _copy_update_file(self, src: str, dest: str):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            shutil.copy2(src, dest)
            return
        except PermissionError:
            if not os.path.exists(dest):
                raise
            old_path = dest + '.old'
            if os.path.exists(old_path):
                os.remove(old_path)
            os.replace(dest, old_path)
            shutil.copy2(src, dest)
        
    def run(self):
        try:
            self.log.emit("Installing update...")
            
            extract_dir = os.path.join(os.path.dirname(self.zip_path), 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                total = len(zip_ref.namelist())
                for i, file_info in enumerate(zip_ref.infolist()):
                    if self._is_cancelled:
                        self.finished.emit(False, "Installation cancelled")
                        return
                    zip_ref.extract(file_info, extract_dir)
                    progress = int((i + 1) / total * 100)
                    self.progress.emit(progress, f"Extracting... {progress}%")
            
            self.log.emit("Extraction complete")
            
            app_dir = get_app_dir()
            source_dir = self._get_install_source_dir(extract_dir)
            
            self.log.emit(f"Copying to: {app_dir}")
            if source_dir != extract_dir:
                self.log.emit(f"Detected release root: {os.path.basename(source_dir)}")

            files_to_copy = []
            skipped = 0
            has_main_exe = False
            has_version_file = False
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [
                    d for d in dirs
                    if d != '__pycache__' and d.lower() not in {'database', 'logs', 'temp', 'attachments'}
                ]
                for file in files:
                    src = os.path.join(root, file)
                    rel_path = os.path.relpath(src, source_dir)
                    if self._should_skip_file(rel_path):
                        skipped += 1
                        continue
                    if rel_path == 'ZAY_POS.exe':
                        has_main_exe = True
                    if rel_path == 'version.txt':
                        has_version_file = True
                    files_to_copy.append((src, rel_path))

            if not has_main_exe:
                raise FileNotFoundError("Update package does not contain ZAY_POS.exe")
            if not has_version_file:
                self.log.emit("Warning: update package does not contain version.txt")

            copied = 0
            failures = []
            total_files = len(files_to_copy)
            for src, rel_path in files_to_copy:
                if self._is_cancelled:
                    self.finished.emit(False, "Installation cancelled")
                    return

                dest = os.path.join(app_dir, rel_path)
                try:
                    self._copy_update_file(src, dest)
                    copied += 1
                except Exception as e:
                    failures.append(f"{rel_path}: {e}")
                    self.log.emit(f"Copy failed: {rel_path} - {e}")

                if total_files > 0:
                    progress = 90 + int((copied / total_files) * 10)
                    self.progress.emit(progress, f"Copying files... {copied}/{total_files}")

            if copied == 0:
                raise RuntimeError("No update files were copied")

            critical_failures = [
                failure for failure in failures
                if failure.startswith('ZAY_POS.exe') or failure.startswith('version.txt')
            ]
            if critical_failures:
                raise RuntimeError("; ".join(critical_failures))
            
            self.log.emit(f"Copied {copied} files ({skipped} skipped)")
            if failures:
                self.log.emit(f"Warning: {len(failures)} non-critical file(s) were not copied")
            
            try:
                shutil.rmtree(os.path.dirname(self.zip_path))
            except:
                pass
            
            global CURRENT_VERSION
            version_file = os.path.join(app_dir, 'version.txt')
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    found_version = extract_version_from_text(f.read())
                    if found_version:
                        CURRENT_VERSION = found_version
            elif self.expected_version:
                CURRENT_VERSION = self.expected_version
            
            self.finished.emit(True, f"Installed version {CURRENT_VERSION}")
            
        except Exception as e:
            self.log.emit(f"Installation failed: {e}")
            self.finished.emit(False, str(e))
    
    def cancel(self):
        self._is_cancelled = True


class ModernButton(QPushButton):
    """Modern animated button."""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._opacity = 1.0
        self.animation = QPropertyAnimation(self, b"opacity")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def enterEvent(self, event):
        self.animation.stop()
        self.animation.setEndValue(0.8)
        self.animation.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.animation.stop()
        self.animation.setEndValue(1.0)
        self.animation.start()
        super().leaveEvent(event)
    
    def get_opacity(self):
        return self._opacity
    
    def set_opacity(self, value):
        self._opacity = value
        self.setStyleSheet(f"QPushButton {{ opacity: {value}; }}")
    
    if pyqtProperty is not None:
        opacity = pyqtProperty(float, get_opacity, set_opacity)
    else:
        opacity = property(get_opacity, set_opacity)


class LauncherWindow(QMainWindow):
    """Main launcher window with modern design and logo."""
    
    def __init__(self):
        super().__init__()
        self.checker_thread = None
        self.download_thread = None
        self.install_thread = None
        self.update_info = None
        self.pending_update_version = ""
        self.selected_mode = LauncherMode.MAIN
        self.auto_update_enabled = True
        self.auto_update_countdown = 5
        self.auto_update_timer = None
        self.setup_ui()
        QTimer.singleShot(500, self.check_for_updates)
    
    def setup_ui(self):
        """Setup the modern user interface."""
        self.setWindowTitle("ZAY POS Launcher")
        self.setFixedSize(720, 620)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Set window icon from app_icon.ico
        window_icon = load_window_icon()
        if window_icon:
            self.setWindowIcon(window_icon)
            print("[OK] Window icon loaded")
        else:
            print("[WARN] Window icon not found")
        
        # Set stylesheet
        self.setStyleSheet(STYLESHEET)
        
        # Center window
        primary_screen = QApplication.primaryScreen()
        if primary_screen is not None:
            screen_geometry = primary_screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
        
        # Main widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(30, 25, 30, 25)
        
        # ============================================================
        # HEADER WITH LOGO
        # ============================================================
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Logo from zaypos.png
        logo_pixmap = load_logo()
        if logo_pixmap:
            logo_label = QLabel()
            logo_label.setObjectName("logoLabel")
            logo_label.setPixmap(logo_pixmap)
            header_layout.addWidget(logo_label)
        else:
            # Fallback to emoji if logo not found
            icon_label = QLabel("⚡")
            icon_label.setStyleSheet("font-size: 36pt;")
            header_layout.addWidget(icon_label)
            print("[WARN] Logo not found, using fallback")
        
        # Title
        title_layout = QVBoxLayout()
        title_label = QLabel("ZAY POS")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label)
        
        sub_title = QLabel("Smart Point of Sale System")
        sub_title.setObjectName("subTitleLabel")
        title_layout.addWidget(sub_title)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Version label
        version_label = QLabel(f"v{CURRENT_VERSION}")
        version_label.setStyleSheet("""
            QLabel {
                color: #cbd5e1;
                font-size: 10pt;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(version_label)
        
        layout.addLayout(header_layout)

        mode_group = QGroupBox("Launch Mode")
        mode_group.setObjectName("modeGroup")
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(10)
        self.main_mode_btn = ModernButton("Main")
        self.main_mode_btn.setObjectName("modeBtnActive")
        self.main_mode_btn.clicked.connect(lambda: self.set_mode(LauncherMode.MAIN))
        self.cashier_mode_btn = ModernButton("Cashier")
        self.cashier_mode_btn.setObjectName("modeBtnInactive")
        self.cashier_mode_btn.clicked.connect(lambda: self.set_mode(LauncherMode.CASHIER))
        mode_layout.addWidget(self.main_mode_btn)
        mode_layout.addWidget(self.cashier_mode_btn)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # ============================================================
        # MAIN CONTENT AREA (LEFT + DEDICATED RIGHT LOG COLUMN)
        # ============================================================
        content_row = QHBoxLayout()
        content_row.setSpacing(12)

        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        version_group = QGroupBox("Version Information")
        version_layout = QHBoxLayout()
        version_layout.setSpacing(30)
        
        # Current version
        current_widget = QWidget()
        current_layout = QVBoxLayout(current_widget)
        current_layout.setSpacing(2)
        current_label = QLabel("Current Version")
        current_label.setObjectName("versionLabel")
        current_layout.addWidget(current_label)
        self.current_version_label = QLabel(f"v{CURRENT_VERSION}")
        self.current_version_label.setObjectName("versionCurrent")
        current_layout.addWidget(self.current_version_label)
        version_layout.addWidget(current_widget)
        
        # Arrow
        arrow_label = QLabel("➜")
        arrow_label.setStyleSheet("color: #495670; font-size: 18pt;")
        version_layout.addWidget(arrow_label)
        
        # Latest version
        latest_widget = QWidget()
        latest_layout = QVBoxLayout(latest_widget)
        latest_layout.setSpacing(2)
        latest_label = QLabel("Latest Version")
        latest_label.setObjectName("versionLabel")
        latest_layout.addWidget(latest_label)
        self.latest_version_label = QLabel("Checking...")
        self.latest_version_label.setObjectName("versionLatest")
        latest_layout.addWidget(self.latest_version_label)
        version_layout.addWidget(latest_widget)
        
        version_layout.addStretch()
        version_group.setLayout(version_layout)
        left_column.addWidget(version_group)
        
        status_group = QGroupBox("Update Status")
        status_group.setObjectName("statusGroup")
        self.status_group = status_group
        status_layout = QVBoxLayout()
        status_layout.setSpacing(8)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        status_layout.addWidget(self.progress_bar)

        self.mode_status_label = QLabel("Ready to launch Main mode")
        self.mode_status_label.setStyleSheet("color: #cbd5e1; font-size: 10pt;")
        status_layout.addWidget(self.mode_status_label)

        self.update_badge_label = QLabel("Auto-update: checking")
        self.update_badge_label.setStyleSheet("""
            QLabel {
                color: #fbbf24;
                background: rgba(251, 191, 36, 0.14);
                border: 1px solid rgba(251, 191, 36, 0.25);
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        status_layout.addWidget(self.update_badge_label)
        
        status_group.setLayout(status_layout)
        left_column.addWidget(status_group)

        right_column = QVBoxLayout()
        right_column.setSpacing(10)

        activity_container = QWidget()
        activity_layout = QVBoxLayout(activity_container)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.setSpacing(8)

        log_group = QGroupBox("Activity Log")
        log_group.setObjectName("logGroup")
        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(220)
        self.log_text.setMaximumHeight(320)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        activity_layout.addWidget(log_group)

        right_column.addWidget(activity_container)

        content_row.addLayout(left_column, 1)
        content_row.addLayout(right_column, 2)
        layout.addLayout(content_row)
        
        # ============================================================
        # BUTTONS
        # ============================================================
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        self.start_btn = ModernButton("Launch")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setMinimumHeight(45)
        self.start_btn.clicked.connect(self.start_app)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        
        self.update_btn = ModernButton("Download Update")
        self.update_btn.setObjectName("updateBtn")
        self.update_btn.setMinimumHeight(45)
        self.update_btn.clicked.connect(self.download_update)
        self.update_btn.setEnabled(False)
        button_layout.addWidget(self.update_btn)
        
        self.skip_btn = ModernButton("Skip")
        self.skip_btn.setObjectName("skipBtn")
        self.skip_btn.setMinimumHeight(45)
        self.skip_btn.clicked.connect(self.skip_update)
        self.skip_btn.setEnabled(False)
        button_layout.addWidget(self.skip_btn)

        self.auto_update_btn = ModernButton("Auto-Install")
        self.auto_update_btn.setObjectName("updateBtn")
        self.auto_update_btn.setMinimumHeight(45)
        self.auto_update_btn.clicked.connect(self.start_auto_update)
        self.auto_update_btn.setEnabled(False)
        button_layout.addWidget(self.auto_update_btn)
        
        layout.addLayout(button_layout)
        
        # ============================================================
        # FOOTER
        # ============================================================
        note_label = QLabel("Launcher can check for updates, switch between Main and Cashier modes, and launch the selected app.")
        note_label.setObjectName("noteLabel")
        note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note_label)

        self.set_mode(LauncherMode.MAIN)
    
    def set_mode(self, mode: str):
        """Switch the selected launch mode and update the UI hints."""
        if mode not in {LauncherMode.MAIN, LauncherMode.CASHIER}:
            return
        self.selected_mode = mode
        if mode == LauncherMode.MAIN:
            self.main_mode_btn.setEnabled(False)
            self.cashier_mode_btn.setEnabled(True)
            self.mode_status_label.setText("Selected mode: Main")
            self.start_btn.setText("Launch Main")
            self.main_mode_btn.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1); border: 1px solid rgba(255,255,255,0.25); color: white;")
            self.cashier_mode_btn.setStyleSheet("background: rgba(255,255,255,0.06); border: 1px solid rgba(148,163,184,0.18); color: #cbd5e1;")
            self.log("Selected launch mode: Main")
        else:
            self.main_mode_btn.setEnabled(True)
            self.cashier_mode_btn.setEnabled(False)
            self.mode_status_label.setText("Selected mode: Cashier")
            self.start_btn.setText("Launch Cashier")
            self.main_mode_btn.setStyleSheet("background: rgba(255,255,255,0.06); border: 1px solid rgba(148,163,184,0.18); color: #cbd5e1;")
            self.cashier_mode_btn.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1); border: 1px solid rgba(255,255,255,0.25); color: white;")
            self.log("Selected launch mode: Cashier")

    def log(self, message: str):
        """Add log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scroll_bar = self.log_text.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.setValue(scroll_bar.maximum())
        QApplication.processEvents()
    
    def check_for_updates(self):
        """Start update check."""
        self.log("Checking for updates...")
        self.status_label.setText("Checking for updates...")
        self.update_badge_label.setText("Auto-update: checking")
        self.update_badge_label.setStyleSheet("""
            QLabel {
                color: #fbbf24;
                background: rgba(251, 191, 36, 0.14);
                border: 1px solid rgba(251, 191, 36, 0.25);
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        self.status_group.setStyleSheet("QGroupBox { border: 1px solid rgba(148, 163, 184, 0.25); }")
        self.start_btn.setEnabled(True)
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        
        self.checker_thread = UpdateCheckerThread()
        self.checker_thread.finished.connect(self.on_check_finished)
        self.checker_thread.error.connect(self.on_check_error)
        self.checker_thread.log.connect(self.log)
        self.checker_thread.start()
    
    def on_check_finished(self, result: dict):
        """Handle check completion."""
        latest_version = result.get('version', '')
        available = result.get('available', False)
        
        self.latest_version_label.setText(f"v{latest_version or 'Unknown'}")
        
        if available:
            self.update_info = result
            self.pending_update_version = latest_version
            self.status_label.setText("New update ready. Download to install it.")
            self.mode_status_label.setText(f"Selected mode: {self.selected_mode.title()}")
            self.status_label.setStyleSheet("color: #64ffda; font-size: 11pt;")
            self.update_badge_label.setText("Auto-update: available")
            self.update_badge_label.setStyleSheet("""
                QLabel {
                    color: #5eead4;
                    background: rgba(45, 212, 191, 0.16);
                    border: 1px solid rgba(45, 212, 191, 0.3);
                    border-radius: 10px;
                    padding: 6px 10px;
                    font-size: 9pt;
                    font-weight: bold;
                }
            """)
            self.status_group.setStyleSheet("QGroupBox { border: 1px solid rgba(45, 212, 191, 0.35); }")
            self.update_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            self.log(f"Update available: v{CURRENT_VERSION} -> v{latest_version}")
        else:
            self.update_info = None
            self.pending_update_version = ""
            self.status_label.setText("You already have the latest version.")
            self.mode_status_label.setText(f"Selected mode: {self.selected_mode.title()}")
            self.status_label.setStyleSheet("color: #64ffda; font-size: 11pt;")
            self.update_badge_label.setText("Auto-update: up to date")
            self.update_badge_label.setStyleSheet("""
                QLabel {
                    color: #93c5fd;
                    background: rgba(59, 130, 246, 0.16);
                    border: 1px solid rgba(59, 130, 246, 0.25);
                    border-radius: 10px;
                    padding: 6px 10px;
                    font-size: 9pt;
                    font-weight: bold;
                }
            """)
            self.status_group.setStyleSheet("QGroupBox { border: 1px solid rgba(59, 130, 246, 0.3); }")
            self.update_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            self.auto_update_btn.setEnabled(False)
            self.log("Application is up to date")
    
    def on_check_error(self, error: str):
        """Handle check error."""
        self.status_label.setText("Update check failed")
        self.status_label.setStyleSheet("color: #fdcb6e; font-size: 11pt;")
        self.start_btn.setEnabled(True)
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.update_info = None
        self.pending_update_version = ""
        self.latest_version_label.setText("Unknown")
        self.update_badge_label.setText("Auto-update: failed")
        self.update_badge_label.setStyleSheet("""
            QLabel {
                color: #fda4af;
                background: rgba(244, 63, 94, 0.16);
                border: 1px solid rgba(244, 63, 94, 0.26);
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        self.status_group.setStyleSheet("QGroupBox { border: 1px solid rgba(244, 63, 94, 0.3); }")
        self.log(f"Update check failed: {error}")
        self.log("Starting application without update...")
    
    def start_auto_update_countdown(self):
        """Start a short countdown and auto-download when the user does not cancel it."""
        if self.auto_update_timer is not None:
            self.auto_update_timer.stop()
        self.auto_update_countdown = 5
        self.auto_update_btn.setText("Auto-Installing in 5s")
        self.auto_update_btn.setEnabled(False)
        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.setInterval(1000)
        self.auto_update_timer.timeout.connect(self._tick_auto_update_countdown)
        self.auto_update_timer.start()

    def _tick_auto_update_countdown(self):
        self.auto_update_countdown -= 1
        if self.auto_update_countdown <= 0:
            if self.auto_update_timer is not None:
                self.auto_update_timer.stop()
                self.auto_update_timer = None
            self.start_auto_update()
            return
        self.auto_update_btn.setText(f"Auto-Installing in {self.auto_update_countdown}s")

    def start_auto_update(self):
        """Start downloading the update automatically."""
        if self.auto_update_timer is not None:
            self.auto_update_timer.stop()
            self.auto_update_timer = None
        if not self.update_info:
            return
        self.auto_update_btn.setText("Auto-Installing")
        self.auto_update_btn.setEnabled(False)
        self.log("Auto-update started")
        self.download_update()

    def download_update(self):
        """Start download process."""
        if not self.update_info:
            return
        
        download_url = self.update_info.get('download_url')
        asset_name = self.update_info.get('asset_name')
        if not download_url:
            download_url, asset_name, _ = get_update_download_info(self.update_info.get('data', {}))
        
        if not download_url:
            custom_message_box(self, "Error", "No download URL found!", QMessageBox.StandardButton.Ok)
            return
        
        version = self.update_info.get('version') or '1.0.0'
        self.pending_update_version = version
        if asset_name:
            self.log(f"Selected update package: {asset_name}")
        
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.auto_update_btn.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.download_thread = DownloadThread(download_url, version)
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.log.connect(self.log)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()
    
    def on_download_progress(self, value: int, status: str):
        """Update download progress."""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
    
    def on_download_finished(self, success: bool, result: str):
        """Handle download completion."""
        if success:
            self.log("Download complete")
            self.status_label.setText("Installing update...")
            
            self.install_thread = InstallThread(result, self.pending_update_version)
            self.install_thread.progress.connect(self.on_install_progress)
            self.install_thread.log.connect(self.log)
            self.install_thread.finished.connect(self.on_install_finished)
            self.install_thread.start()
        else:
            self.status_label.setText("Download failed")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11pt;")
            self.update_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            self.auto_update_btn.setEnabled(bool(self.update_info))
            self.progress_bar.setVisible(False)
    
    def on_install_progress(self, value: int, status: str):
        """Update install progress."""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
    
    def on_install_finished(self, success: bool, message: str):
        """Handle install completion."""
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText("Update installed successfully!")
            self.status_label.setStyleSheet("color: #64ffda; font-size: 11pt;")
            self.current_version_label.setText(f"v{CURRENT_VERSION}")
            self.log(message)
            
            reply = custom_message_box(
                self,
                "Update Complete",
                f"ZAY POS has been updated to version {CURRENT_VERSION}!\n\n"
                "The launcher can restart the app now.\n\n"
                "Would you like to restart now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.restart_launcher()
            else:
                self.start_app()
        else:
            self.status_label.setText("Installation failed")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11pt;")
            self.update_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            self.auto_update_btn.setEnabled(bool(self.update_info))
            self.log(f"Installation failed: {message}")
    
    def restart_launcher(self):
        """Restart the launcher or launch the application directly if needed."""
        self.log("Restarting launcher...")
        try:
            command = []
            if getattr(sys, 'frozen', False):
                command = [sys.executable]
            else:
                command = [sys.executable, 'launcher.py']

            subprocess.Popen(command, cwd=get_app_dir(), close_fds=True, creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            ) if sys.platform == "win32" else 0)
            self.log("Launcher restarted successfully")
            QTimer.singleShot(500, self.close)
        except Exception as e:
            self.log(f"Failed to restart: {e}")
            self.start_app()
    
    def start_app(self):
        """Start the main application using the best available entry point."""
        self.log(f"Starting ZAY POS in {self.selected_mode.title()} mode...")

        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.getcwd()

        command, source = resolve_launch_target(app_dir, mode=self.selected_mode)
        if not command:
            self.log(f"Application entry point not found in: {app_dir}")
            custom_message_box(
                self,
                "Error",
                f"Application entry point not found in: {app_dir}\n\nPlease check your installation.",
                QMessageBox.StandardButton.Ok
            )
            return

        self.log(f"Resolved launch target via {source}: {command[0]}")
        try:
            popen_kwargs = {
                "cwd": app_dir,
                "close_fds": True,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "DETACHED_PROCESS", 0)
                )

            subprocess.Popen(command, **popen_kwargs)
            self.log("Application started!")
            QTimer.singleShot(300, self.exit_launcher_after_start)
        except Exception as e:
            self.log(f"Failed to start: {e}")
            custom_message_box(self, "Error", f"Failed to start application: {e}", QMessageBox.StandardButton.Ok)
    
    def skip_update(self):
        """Skip update and start app."""
        self.log("Skipping update...")
        self.start_app()

    def exit_launcher_after_start(self):
        """Exit the launcher after ZAY POS has been started."""
        self.log("Closing launcher...")
        self.close()
        app = QApplication.instance()
        if app:
            app.quit()
        QTimer.singleShot(1000, lambda: os._exit(0))


def check_only() -> int:
    """CLI mode used by the Settings > Update tab."""
    try:
        result = fetch_latest_update()
        print(f"version: {result.get('version', '')}")
        print(f"notes: {str(result.get('release_notes', '')).splitlines()[0] if result.get('release_notes') else ''}")
        print(f"url: {result.get('download_url') or ''}")
        print(f"size: {result.get('file_size') or 0}")
        print(f"available: {1 if result.get('available') else 0}")
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def main():
    """Main entry point."""
    if '--check-only' in sys.argv:
        sys.exit(check_only())

    # Qt WebEngine requires this before QApplication is created.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    apply_launcher_font(app)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = LauncherWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
