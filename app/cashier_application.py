"""Optimized lightweight bootstrap used by Cashier Mode.exe only."""

import os
import sys
from loguru import logger
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.config import config
from core.exception_handler import setup_exception_handlers
from utils.paths import ensure_directories, get_app_root
from utils.branded_icons import pos_icon


class CashierApplication:
    """Start LoginDialog and CashierUI without the full ZAY POS bootstrap."""

    ALLOWED_ROLES = {"cashier", "admin", "manager"}

    def __init__(self):
        self.app = None
        self.cashier_window = None

    def run(self) -> int:
        self._bootstrap()

        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("ZAY POS Cashier Mode")
        self.app.setWindowIcon(pos_icon())
        self.app.setQuitOnLastWindowClosed(True)
        from utils.touch_scroll import install_global_touch_scrolling
        install_global_touch_scrolling(self.app)

        if not self._check_database():
            return 1

        self._load_fonts()
        self._apply_saved_theme()
        self._set_application_font()

        if not self._login_and_open_cashier():
            return 0

        return self.app.exec()

    def _bootstrap(self):
        """Prepare only paths, logging and exception handling needed by Cashier Mode."""
        self._setup_runtime_environment()
        ensure_directories()
        self._setup_logging()
        setup_exception_handlers()
        logger.info("Starting optimized Cashier Mode...")

    def _setup_runtime_environment(self):
        """Configure frozen paths and Qt variables without importing Matplotlib."""
        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
            if app_dir not in sys.path:
                sys.path.insert(0, app_dir)
            bundle_dir = getattr(sys, "_MEIPASS", None)
            if bundle_dir and bundle_dir not in sys.path:
                sys.path.insert(0, bundle_dir)
            os.chdir(get_app_root())

        # Must be configured before QApplication is created.
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "Round")

    def _setup_logging(self):
        log_dir = config.LOG_DIR
        os.makedirs(log_dir, exist_ok=True)
        logger.remove()
        if sys.stdout is not None:
            logger.add(
                sys.stdout,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                    "<level>{message}</level>"
                ),
                level="INFO",
            )
        logger.add(
            os.path.join(log_dir, "cashier_{time:YYYY-MM-DD}.log"),
            rotation="1 day",
            retention="14 days",
            compression="zip",
            level="DEBUG",
        )

    def _check_database(self) -> bool:
        """Only verify the existing database; do not run migrations or auto-fix."""
        try:
            from models.database import connect_db

            conn = connect_db()
            try:
                conn.execute("SELECT 1")
                # Verify the minimum tables required to show Cashier Mode.
                required = {"users", "products", "settings"}
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                existing = {str(row[0]) for row in rows}
                missing = required - existing
                if missing:
                    raise RuntimeError(
                        "Database is not initialized. Missing tables: "
                        + ", ".join(sorted(missing))
                    )
            finally:
                conn.close()
            logger.info("Cashier database connection verified")
            return True
        except Exception as exc:
            logger.critical(f"Cashier database check failed: {exc}")
            QMessageBox.critical(
                None,
                "Database Error",
                "Cashier Mode could not open the existing ZAY POS database.\n\n"
                f"{exc}\n\nPlease run ZAY_POS.exe as administrator/manager first.",
            )
            return False

    def _load_fonts(self):
        fonts_path = os.path.join(config.ASSETS_DIR, "fonts")
        if not os.path.isdir(fonts_path):
            return
        for filename in os.listdir(fonts_path):
            if filename.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(fonts_path, filename))

    def _load_saved_theme(self) -> str:
        try:
            from models.database import connect_db

            conn = connect_db()
            try:
                row = conn.execute(
                    "SELECT value FROM settings WHERE key='theme'"
                ).fetchone()
            finally:
                conn.close()
            return row[0] if row else "Light"
        except Exception as exc:
            logger.warning(f"Could not load theme: {exc}")
            return "Light"

    def _apply_saved_theme(self):
        from ui.themes import apply_theme

        apply_theme(self.app, self._load_saved_theme())

    def _set_application_font(self):
        if "Myanmar Text" in QFontDatabase.families():
            self.app.setFont(QFont("Myanmar Text", 10))
        elif "Noto Sans Myanmar" in QFontDatabase.families():
            self.app.setFont(QFont("Noto Sans Myanmar", 10))
        else:
            self.app.setFont(QFont("Segoe UI", 10))

    def _login_and_open_cashier(self) -> bool:
        from ui.login_dialog import LoginDialog

        login = LoginDialog()
        login.setWindowTitle("ZAY POS - Cashier Login")
        if login.exec() != LoginDialog.DialogCode.Accepted:
            return False

        user_info = login.user_info
        role = str(user_info.get("role", "")).strip().lower()
        if role not in self.ALLOWED_ROLES:
            QMessageBox.warning(
                None,
                "Access Denied",
                "This account does not have permission to use Cashier Mode.",
            )
            return False

        from ui.cashier_window.cashier_ui import CashierUI

        self.cashier_window = CashierUI(user_info)
        self.cashier_window.setWindowTitle("ZAY POS - Cashier Mode")
        self.cashier_window.set_on_closed_callback(self.app.quit)
        self.cashier_window.show()
        return True
