# app/application.py
"""
Main application class with lazy loading support.
"""

import sys
import os
from loguru import logger
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject

from app.config import config
from app.startup import start_application, show_database_error


def fix_audio_libraries():
    """Fix audio library errors."""
    return
    try:
        sd = None
        sd.default.callback = lambda *args: None
        
        try:
            devices = sd.query_devices()
            logger.info(f"✅ Audio devices found: {len(devices)}")
            has_input = False
            for i, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    has_input = True
                    logger.info(f"✅ Input device: {dev.get('name')}")
                    break
            if not has_input:
                logger.warning("⚠️ No input device found for speech recognition")
        except Exception as e:
            logger.warning(f"⚠️ Audio device detection warning: {e}")
    except ImportError:
        logger.warning("Speech recognition disabled")
    except Exception as e:
        logger.warning(f"⚠️ Audio library initialization warning: {e}")


# ============================================================
# SIGNALS FOR LOADING PROGRESS
# ============================================================
class LoadingSignals(QObject):
    """Signals for updating loading dialog from any thread"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    message = pyqtSignal(str)
    log = pyqtSignal(str)
    finished = pyqtSignal()


class Application:
    """Main application class."""
    
    def __init__(self):
        self.version = None
        self.app = None
        self.main_window = None
        self.db_status = None
        self.logout_triggered = False
        self._loading = None
        self._load_timer = None
        self._signals = LoadingSignals()
        
        # Loading state
        self._load_step = 0
        self._load_user_info = None
        
        # Connect signals
        self._signals.progress.connect(self._on_progress)
        self._signals.status.connect(self._on_status)
        self._signals.message.connect(self._on_message)
        self._signals.log.connect(self._on_log)
        self._signals.finished.connect(self._on_loading_finished)
    
    def run(self):
        """Run the application."""
        # Start application
        self.version = start_application()
        
        # Qt WebEngine requires this before QApplication is created.
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

        # Create QApplication
        self.app = QApplication(sys.argv)
        
        # Initialize database
        try:
            from core.database import initialize_database

            self.db_status = initialize_database(config.DB_PATH)
        except Exception as e:
            error_msg = str(e)
            logger.critical(f"Database initialization failed: {error_msg}")
            
            # Try auto recovery
            try:
                from models.database.recovery import DatabaseRecovery
                from models.database.auto_fix import run_auto_fix
                
                logger.info("Attempting auto-recovery...")
                if run_auto_fix():
                    logger.info("Auto-fix completed. Retrying database initialization...")
                    self.db_status = initialize_database(config.DB_PATH)
                    logger.info("✅ Database initialized after auto-fix")
                else:
                    recovery = DatabaseRecovery()
                    success, message = recovery.auto_recover()
                    if success:
                        logger.info(f"✅ {message}")
                        self.db_status = initialize_database(config.DB_PATH)
                        logger.info("✅ Database initialized after recovery")
                    else:
                        raise
            except:
                show_database_error(error_msg)
                sys.exit(1)
        
        # Load fonts
        self.load_fonts()
        
        # Load theme
        saved_theme = self.load_theme()
        
        # Apply theme
        from ui.themes import apply_theme
        apply_theme(self.app, saved_theme)
        logger.info(f"Theme loaded: {saved_theme}")
        
        # Set font
        self.set_application_font()
        
        # Show login and run
        login_loop = self.create_login_loop()
        login_loop()
        
        # ✅ Use exec() instead of exec_()
        return_code = self.app.exec()
        
        # ✅ Force clean exit after app.exec() returns
        logger.info("Application exec completed, cleaning up...")
        
        # ✅ Force terminate any remaining child processes
        try:
            import psutil
            current_process = psutil.Process()
            for child in current_process.children(recursive=True):
                try:
                    child.terminate()
                    child.wait(timeout=2)
                except:
                    try:
                        child.kill()
                    except:
                        pass
        except ImportError:
            # If psutil not available, use os._exit as last resort
            logger.warning("psutil not available, using os._exit...")
            os._exit(0)
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
            os._exit(0)
        
        # If we get here, use os._exit to ensure process terminates
        os._exit(return_code)
    
    def load_fonts(self):
        """Load custom fonts."""
        fonts_dir = config.ASSETS_DIR
        fonts_path = os.path.join(fonts_dir, "fonts")
        
        if os.path.exists(fonts_path):
            for filename in os.listdir(fonts_path):
                if filename.lower().endswith(('.ttf', '.otf')):
                    font_path = os.path.join(fonts_path, filename)
                    QFontDatabase.addApplicationFont(font_path)
                    logger.debug(f"Loaded font: {filename}")
    
    def load_theme(self) -> str:
        """Load saved theme from database."""
        try:
            from models.database import connect_db

            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except Exception as e:
            logger.error(f"Failed to load theme: {e}")
            return "Light"
    
    def set_application_font(self):
        """Set application font."""
        if "Noto Sans Myanmar" in QFontDatabase.families():
            self.app.setFont(QFont("Noto Sans Myanmar", 10))
        else:
            self.app.setFont(QFont("Segoe UI", 10))
    
    def create_login_loop(self):
        """Create login loop function."""
        from ui.login_dialog import LoginDialog
        from ui.loading_dialog import LoadingDialog
        from ui.main_window import MainWindow
        
        def run():
            while True:
                login = LoginDialog()
                if login.exec() != LoginDialog.DialogCode.Accepted:
                    logger.info("User cancelled login, exiting application.")
                    sys.exit(0)
                
                logger.info(f"User logged in: {login.user_info['username']} (role: {login.user_info['role']})")
                
                # ✅ Show loading dialog
                self._loading = LoadingDialog("Please wait...", show_log=True)
                self._loading.show()
                self.app.processEvents()
                
                # ✅ Load MainWindow asynchronously with lazy loading support
                self._load_main_window_async(login.user_info)
                
                self.app.exec()
                
                if self.main_window and self.main_window.logout_triggered:
                    logger.info("User logged out, showing login screen again.")
                    continue
                else:
                    logger.info("Application closed normally.")
                    break
        
        return run
    
    def _load_main_window_async(self, user_info):
        """
        Load MainWindow asynchronously using QTimer.
        All GUI operations happen on Main Thread.
        Supports lazy loading for faster startup.
        """
        from ui.main_window import MainWindow
        
        # Step tracking
        self._load_step = 0
        self._load_user_info = user_info
        self._load_error = None
        
        # Define steps with progress, status, message
        steps = [
            (0, "Starting...", "Initializing application..."),
            (10, "Loading database...", "Connecting to database..."),
            (30, "Loading main window...", "Creating main window..."),
            (50, "Loading dashboard...", "Building dashboard..."),
            (70, "Loading services...", "Starting background services..."),
            (85, "Preloading pages...", "Preloading frequently used pages..."),
            (100, "Ready", "Application is ready!"),
        ]
        
        # Send initial progress
        self._signals.progress.emit(0)
        self._signals.status.emit("Starting...")
        self._signals.message.emit("Initializing application...")
        self._signals.log.emit("🚀 Starting ZAY POS...")
        self.app.processEvents()
        
        # Start async loading with QTimer
        self._load_timer = QTimer()
        self._load_timer.timeout.connect(self._load_main_window_step)
        self._load_timer.start(150)  # 150ms interval for smoother loading
    
    def _load_main_window_step(self):
        """
        Load MainWindow step by step using QTimer.
        With lazy loading support - only creates MainWindow shell,
        pages are loaded on demand.
        """
        from ui.main_window import MainWindow
        
        # Define steps with progress, status, message
        steps = [
            (0, "Starting...", "Initializing application..."),
            (10, "Loading database...", "Connecting to database..."),
            (30, "Loading main window...", "Creating main window..."),
            (50, "Loading dashboard...", "Building dashboard..."),
            (70, "Loading services...", "Starting background services..."),
            (85, "Preloading pages...", "Preloading frequently used pages..."),
            (100, "Ready", "Application is ready!"),
        ]
        
        try:
            # Update progress based on step
            if self._load_step < len(steps):
                progress, status, message = steps[self._load_step]
                self._signals.progress.emit(progress)
                self._signals.status.emit(status)
                self._signals.message.emit(message)
                self._signals.log.emit(f"⏳ {status}")
                self.app.processEvents()
                
                # Step 2 (index 2): Create MainWindow
                if self._load_step == 2:
                    logger.info("Creating MainWindow with lazy loading support...")
                    self.main_window = MainWindow(self._load_user_info)
                    self._signals.log.emit("✅ MainWindow created with lazy loading")
                    self.app.processEvents()
                
                # Step 5 (index 5): Preload pages
                if False and self._load_step == 5:
                    logger.info("Preloading frequently used pages...")
                    if self.main_window:
                        # Preload Sales page and Dashboard
                        try:
                            self.main_window.preload_page(5)  # Sales page
                            self.main_window.preload_page(0)  # Dashboard
                            self._signals.log.emit("✅ Pages preloaded: Sales, Dashboard")
                        except Exception as e:
                            logger.warning(f"Preload failed: {e}")
                    self.app.processEvents()
                
                # Step 6 (index 6): Finish loading
                if self._load_step == len(steps) - 1:
                    self._load_timer.stop()
                    self._load_timer = None
                    self._signals.finished.emit()
                    return
                
                self._load_step += 1
            else:
                # Should not happen, but just in case
                self._load_timer.stop()
                self._load_timer = None
                self._signals.finished.emit()
                
        except Exception as e:
            self._load_timer.stop()
            self._load_timer = None
            logger.error(f"Failed to load main window: {e}")
            logger.exception(e)
            self._signals.log.emit(f"❌ Error: {str(e)}")
            self._on_loading_error(str(e))
    
    def _on_progress(self, value):
        """Update progress in loading dialog"""
        if self._loading and not self._loading._is_closing:
            self._loading.set_progress_direct(value)
    
    def _on_status(self, text):
        """Update status in loading dialog"""
        if self._loading and not self._loading._is_closing:
            self._loading.set_status(text)
    
    def _on_message(self, text):
        """Update message in loading dialog"""
        if self._loading and not self._loading._is_closing:
            self._loading.set_message(text)
    
    def _on_log(self, text):
        """Add log to loading dialog"""
        if self._loading and not self._loading._is_closing:
            self._loading.add_log(text)
    
    def _on_loading_finished(self):
        """Loading finished - show main window"""
        if self.main_window:
            self.main_window.showMaximized()
            logger.info("MainWindow displayed with lazy loading support")
            self.app.processEvents()

        # Close loading dialog
        if self._loading:
            if self.main_window:
                self.main_window._ignore_next_startup_close = True
            self._loading.accept()
            self._loading = None
        
        # Show main window
        if self.main_window:
            self.main_window.showMaximized()
            logger.info("✅ MainWindow displayed with lazy loading support")
        
        self.app.processEvents()
    
    def _on_loading_error(self, error_msg):
        """Handle loading error"""
        # Close loading dialog
        if self._loading:
            self._loading.accept()
            self._loading = None
        
        # Show error
        QMessageBox.critical(
            None, 
            "Error", 
            f"Failed to initialize application:\n{error_msg}\n\n"
            "Please check the logs for more details."
        )
        self.app.processEvents()
