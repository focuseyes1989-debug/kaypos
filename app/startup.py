# app/startup.py
"""
Application startup sequence.
"""

import os
import sys
from loguru import logger
from PyQt6.QtWidgets import QApplication, QMessageBox

from utils.paths import (
    app_path,
    get_app_root,
    get_db_path,
    get_log_dir,
    get_backup_dir,
    get_temp_dir,
    ensure_directories
)
from app.config import config  # ✅ Import config instance
from app.launcher import should_run_launcher, run_launcher_and_exit
from core.environment import setup_environment
from core.exception_handler import setup_exception_handlers


def bootstrap_runtime_paths():
    """Prepare writable folders and bundled data."""
    import shutil
    
    # Ensure all directories exist
    ensure_directories()
    
    if getattr(sys, "frozen", False):
        app_dir = get_app_root()
        bundle_dir = getattr(sys, "_MEIPASS", app_dir)
        os.chdir(app_dir)
        
        for folder in ("assets", "resources"):
            source = os.path.join(bundle_dir, folder)
            target = os.path.join(app_dir, folder)
            if os.path.isdir(source) and not os.path.exists(target):
                shutil.copytree(source, target)
                print(f"✅ Copied {folder} to {target}")

        version_source = os.path.join(bundle_dir, "version.txt")
        version_target = os.path.join(app_dir, "version.txt")
        if os.path.isfile(version_source) and not os.path.exists(version_target):
            shutil.copy2(version_source, version_target)
    
    # Test write permissions
    for folder in [get_db_path(), get_log_dir(), get_temp_dir()]:
        try:
            os.makedirs(os.path.dirname(folder) if os.path.splitext(folder)[1] else folder, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Could not create folder: {e}")


def setup_logging(log_dir: str = None):
    """
    Setup logging.
    
    Args:
        log_dir: Optional log directory (uses config if not provided)
    """
    if log_dir is None:
        log_dir = config.LOG_DIR  # ✅ Use property, not method
    
    os.makedirs(log_dir, exist_ok=True)
    
    logger.remove()
    if sys.stdout is not None:
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO"
        )
    logger.add(
        os.path.join(log_dir, "zaypos_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )


def show_database_error(error_msg: str):
    """Show database error dialog."""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Database Error")
    msg.setText("Database initialization failed!")
    msg.setInformativeText(
        "The application cannot start because the database could not be initialized.\n\n"
        f"Error: {error_msg}\n\n"
        "Please check the logs for more details.\n"
        "For client PCs, check the local .env database connection settings."
    )
    msg.setDetailedText(
        "Possible causes:\n"
        "1. Server IP, port, username, password, or database name is wrong\n"
        "2. PostgreSQL pg_hba.conf does not allow this client IP\n"
        "3. Windows Firewall is blocking port 5432\n"
        "4. The PostgreSQL service is not running\n"
        "5. SQLite database file is corrupted when using local SQLite mode\n\n"
        "Solution:\n"
        "1. Update .env beside the app or use Settings > Database after login\n"
        "2. Test from the client with scripts/postgres_app_smoke.py\n"
        "3. Ask the server admin to allow this client IP in pg_hba.conf"
    )
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg.exec()


def start_application():
    """Start the application."""
    # Bootstrap
    bootstrap_runtime_paths()
    setup_environment()
    setup_exception_handlers()
    
    # Setup logging
    setup_logging()  # ✅ No argument needed, uses config
    
    logger.info("🚀 Starting ZAY POS...")
    
    # Check launcher
    if should_run_launcher():
        logger.info("🔄 Starting launcher for update check...")
        run_launcher_and_exit()
        logger.warning("Launcher failed to start or was cancelled, continuing with normal startup")
    
    # Get version
    version = config.get_app_version()
    logger.info(f"📌 ZAY POS Version: {version}")
    
    return version
