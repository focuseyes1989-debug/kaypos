# ui/main_window/main_window.py
"""
KAY Point of Sales - Main Window with Lazy Loading
Sajiwa POS Style Layout with Modern Sidebar Navigation
(Standard Window - Frameless မဟုတ်သော Version)
"""

from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QMainWindow, QMessageBox, QWidget, QHBoxLayout, QLabel, QApplication
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.language import lang
from utils.system_theme import system_theme
from ui.main_window.main_window_ui import MainWindowUI
from ui.main_window.main_window_menus import MainWindowMenus
from ui.main_window.main_window_actions import MainWindowActions
from ui.main_window.main_window_handlers import MainWindowHandlers
from ui.themes.theme_manager import get_theme_colors, theme_manager, apply_theme
from loguru import logger
from datetime import datetime
from utils.performance import get_performance_settings


class MainWindow(MainWindowUI):
    """
    KAY Point of Sales ၏ အဓိက Window ဖြစ်ပါသည်။
    Lazy Loading ကို အသုံးပြုထားပြီး Page များကို လိုအပ်မှသာ Load လုပ်ပါသည်။
    
    Sajiwa POS စတိုင်လ်အတိုင်း ပြင်ဆင်ထားပြီး -
    - ဘယ်ဘက်တွင် Sidebar Navigation
    - အပေါ်တွင် Gradient Header
    - အောက်တွင် ခေတ်မီ Status Bar
    တို့ပါဝင်ပါသည်။
    
    ⚠️ ဤ Version သည် Frameless မဟုတ်သော ပုံမှန် Window ဖြစ်သည်။
    """
    
    logout_signal = pyqtSignal()

    # Declare attributes to fix Pylance errors
    current_user: Dict[str, Any]
    user_id: int
    logout_triggered: bool
    follow_system_theme: bool
    auto_backup_manager: Optional[Any] = None
    cloud_sync_manager: Optional[Any] = None
    telegram_command_listener: Optional[Any] = None
    customer_display_server: Optional[Any] = None
    expense_notification_checker: Optional[Any] = None
    clock_timer: Optional[QTimer] = None
    menu_clock_timer: Optional[QTimer] = None

    def __init__(self, current_user: Dict[str, Any]):
        """
        MainWindow ကို စတင်သတ်မှတ်ခြင်း
        
        Args:
            current_user (dict): လက်ရှိ login ဝင်ထားသော သုံးစွဲသူ၏ အချက်အလက်
                {'id': 1, 'username': 'admin', 'role': 'admin'}
        """
        QMainWindow.__init__(self)
        
        # ------------------------------------------------------------
        # ၁. အခြေခံ အချက်အလက်များ သတ်မှတ်ခြင်း
        # ------------------------------------------------------------
        self.current_user = current_user
        self.user_id = current_user["id"]
        self.logout_triggered = False
        self._startup_close_guard = True
        self._ignore_next_startup_close = False
        
        # Window Icon ကို သတ်မှတ်ခြင်း
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        
        # Scaling အတွက် Constants များ
        self._keep_aspect_ratio = Qt.AspectRatioMode.KeepAspectRatio
        self._smooth_transform = Qt.TransformationMode.SmoothTransformation
        
        # System Theme ကို လိုက်နာမည်လား သတ်မှတ်ခြင်း
        self.follow_system_theme = True
        
        # Page names for title
        self._page_names = {}

        # Cashier window reference
        self._cashier_window = None
        
        # ------------------------------------------------------------
        # ၂. UI ကို စတင်တည်ဆောက်ခြင်း (Sajiwa POS Style)
        # ------------------------------------------------------------
        self.setup_ui()
        
        # Menu Bar ကို ဖန်တီးခြင်း (Standard Window အတွက်)
        self.follow_system_theme = self.load_follow_system_theme()
        self.create_menu_bar()
        
        # ------------------------------------------------------------
        # ၃. ဘာသာပြန်ချက်များ အသုံးပြုခြင်း
        # ------------------------------------------------------------
        self.apply_language()
        
        # Shop Logo နှင့် Title ကို ပြင်ဆင်ခြင်း
        self.update_shop_logo()
        self.update_shop_title()
        
        # Window Title ကို Version နဲ့တွဲသတ်မှတ်ခြင်း
        self.set_fixed_window_title()
        
        # ------------------------------------------------------------
        # ၄. Shortcut Keys များ သတ်မှတ်ခြင်း (F5, Ctrl+R)
        # ------------------------------------------------------------
        self.setup_refresh_shortcut()

        # ------------------------------------------------------------
        # ၅. Auto Backup Manager ကို စတင်ခြင်း
        # ------------------------------------------------------------
        self.auto_backup_manager = None
        self.cloud_sync_manager = None
        
        # ------------------------------------------------------------
        # ၆. Telegram Service ကို စတင်ခြင်း
        # ------------------------------------------------------------
        self.telegram_command_listener = None
        
        # ------------------------------------------------------------
        # ၇. Customer Display Server ကို စတင်ခြင်း
        # ------------------------------------------------------------
        self.customer_display_server = None
        
        # Sales Page ရှိ Customer Display State ကို ထုတ်ပြန်ခြင်း
        if hasattr(self, "sales_page") and self.sales_page and hasattr(self.sales_page, 'publish_customer_display_state'):
            getattr(self.sales_page, 'publish_customer_display_state')()
        
        # ------------------------------------------------------------
        # ၈. Telegram Listener Watchdog (၁ မိနစ်တိုင်း စစ်ဆေးခြင်း)
        # ------------------------------------------------------------
        self.telegram_listener_watchdog = QTimer(self)
        self.telegram_listener_watchdog.timeout.connect(self.ensure_telegram_listener)
        
        # ------------------------------------------------------------
        # ၉. Background Activity Timer (၇၅၀ မီလီစက္ကန့်တိုင်း)
        # ------------------------------------------------------------
        self.background_activity_timer = QTimer(self)
        self.background_activity_timer.timeout.connect(self.update_background_activity_status)

        # Local executive digests are generated for completed periods only.
        self.dashboard_digest_timer = QTimer(self)
        self.dashboard_digest_timer.setInterval(15 * 60 * 1000)
        self.dashboard_digest_timer.timeout.connect(self._check_dashboard_digests)
        if not get_performance_settings().low_end_mode:
            self.dashboard_digest_timer.start()
            QTimer.singleShot(5000, self._check_dashboard_digests)

        # ------------------------------------------------------------
        # ၁၀. Language ပြောင်းလဲမှုကို နားဆင်ခြင်း
        # ------------------------------------------------------------
        lang.language_changed.connect(self.on_language_changed)

        # ------------------------------------------------------------
        # ၁၁. System Theme ကို လိုက်နာခြင်း
        # ------------------------------------------------------------
        system_theme.theme_changed.connect(self.on_system_theme_changed)

        # ------------------------------------------------------------
        # ၁၂. Stock Alert Notification
        # ------------------------------------------------------------
        self._init_notification_icon()
        
        # ------------------------------------------------------------
        # ၁၃. Expense Notification Checker
        # ------------------------------------------------------------
        self.expense_notification_checker = None
        
        # ------------------------------------------------------------
        # ၁၄. Theme ကို Settings မှ အသုံးပြုခြင်း
        # ------------------------------------------------------------
        self.apply_theme_from_settings(refresh_widgets=False)
        
        # ------------------------------------------------------------
        # ၁၅. Theme Manager နှင့် ချိတ်ဆက်ခြင်း
        # ------------------------------------------------------------
        theme_manager.theme_changed.connect(self.on_theme_manager_changed)
        
        # ------------------------------------------------------------
        # ၁၆. PRELOAD INITIAL PAGES
        # ------------------------------------------------------------
        # Preload Sales page and adjacent pages
        # Optional integrations and page preloading are disabled by default for
        # low-end client PCs. Start them only from explicit user actions.
        
        # ------------------------------------------------------------
        # ၁၇. Sidebar Collapse Signal ချိတ်ဆက်ခြင်း
        # ------------------------------------------------------------
        
        # ------------------------------------------------------------
        # ၁၈. Log ရေးသားခြင်း
        # ------------------------------------------------------------
        logger.info(f"✅ MainWindow initialised for user: {self.current_user['username']} (role: {self.current_user['role']})")
        logger.info(f"✅ Layout: Sajiwa POS Style with Lazy Loading and QSplitter")

    def _check_dashboard_digests(self) -> None:
        try:
            from ui.ai_pages.ai_dashboard_digest import DashboardDigestScheduler
            DashboardDigestScheduler.run_due(self.user_id,self.current_user.get("role"))
            from ui.ai_pages.ai_sales_summary_governance import SalesSummaryDigestScheduler
            SalesSummaryDigestScheduler.run_due(self.user_id,self.current_user.get("role"))
        except Exception as exc:
            logger.warning(f"Dashboard digest scheduler skipped: {exc}")

    def _start_background_services(self) -> None:
        """Start non-critical services after the main window has appeared."""
        if getattr(self, "_background_services_started", False):
            return

        self._background_services_started = True
        try:
            from utils.auto_backup import AutoBackupManager

            self.auto_backup_manager = AutoBackupManager(self)
            self.auto_backup_manager.backup_started.connect(self.on_background_activity_started)
            self.auto_backup_manager.backup_created.connect(self.on_background_activity_finished)
            self.auto_backup_manager.backup_failed.connect(self.on_background_activity_finished)
            self.auto_backup_manager.start()

            if get_performance_settings().low_end_mode:
                logger.info("Low-end mode: optional background integrations are disabled")
                return

            from utils.customer_display_server import start_customer_display_server
            from utils.expense_notification_checker import ExpenseNotificationChecker
            from utils.telegram_service import start_telegram_command_listener
            from services.cloud_sync_service import start_cloud_sync_manager

            self.telegram_command_listener = start_telegram_command_listener()
            self.customer_display_server = start_customer_display_server()
            self.cloud_sync_manager = start_cloud_sync_manager()
            self._show_customer_display_server_status()

            if hasattr(self, "sales_page") and self.sales_page and hasattr(self.sales_page, 'publish_customer_display_state'):
                getattr(self.sales_page, 'publish_customer_display_state')()

            self.telegram_listener_watchdog.start(60000)

            self.expense_notification_checker = ExpenseNotificationChecker(self)
            self.expense_notification_checker.alert_triggered.connect(self.show_expense_alert)

            logger.info("Background services started")
        except Exception as e:
            self._background_services_started = False
            logger.warning(f"Background services startup failed: {e}")

    def _preload_initial_pages(self) -> None:
        """Preload initial pages for better UX"""
        # Preload Sales page (index 5)
        self.preload_page(5)
        # Preload Dashboard (index 0)
        self.preload_page(0)
        # Preload adjacent pages
        self.preload_adjacent_pages(5)
        logger.info("✅ Initial pages preloaded")

    # ================================================================
    # WINDOW TITLE
    # ================================================================

    def set_fixed_window_title(self) -> None:
        """
        Window Title ကို Version Number နှင့်တွဲသတ်မှတ်ခြင်း
        """
        from updater.version_manager import VersionManager
        
        try:
            version_manager = VersionManager()
            version = version_manager.get_current_version()
            self.setWindowTitle(f"KAY Point of Sales v{version}")
            logger.info(f"Window title set: KAY Point of Sales v{version}")
        except Exception as e:
            logger.warning(f"Could not get version for window title: {e}")
            self.setWindowTitle("KAY Point of Sales")
            logger.info("Window title set: KAY Point of Sales (no version)")

    def setFixedWindowTitle(self) -> None:
        """
        Legacy method for compatibility - calls set_fixed_window_title
        """
        self.set_fixed_window_title()

    # ================================================================
    # CUSTOMER DISPLAY SERVER
    # ================================================================

    def _show_customer_display_server_status(self) -> None:
        """
        Customer Display Server ၏ အခြေအနေကို Status Bar တွင် ပြသခြင်း
        """
        try:
            customer_display_server = self.customer_display_server
            if not customer_display_server:
                return
            status = customer_display_server.status()
            if status and status.get("running"):
                urls = status.get("urls") or []
                first_url = urls[0] if urls else f"http://127.0.0.1:{status.get('port')}"
                if self.status_bar:
                    self.status_bar.showMessage(f"Customer display server: {first_url}", 8000)
                logger.info(f"Customer display server URLs: {', '.join(urls)}")
            else:
                error_msg = status.get('last_error') if status else 'Unknown error'
                logger.warning(f"Customer display server not running: {error_msg}")
        except Exception as exc:
            logger.debug(f"Could not show customer display server status: {exc}")

    # ================================================================
    # TELEGRAM LISTENER
    # ================================================================

    def ensure_telegram_listener(self) -> None:
        """
        Telegram Listener ကို လည်ပတ်နေစေရန် စစ်ဆေးခြင်း (Watchdog)
        """
        try:
            from utils.telegram_service import ensure_telegram_command_listener_running

            self.telegram_command_listener = ensure_telegram_command_listener_running()
        except Exception as exc:
            logger.warning(f"Telegram listener watchdog failed: {exc}")

    def update_background_activity_status(self) -> None:
        """
        Background Activity ၏ အခြေအနေကို ပြန်လည်ဆန်းသစ်ခြင်း
        """
        try:
            message = ""
            if hasattr(self, "telegram_command_listener") and self.telegram_command_listener:
                status = self.telegram_command_listener.status()
                message = status.get("active_task", "")
            self.set_background_activity("telegram", message)
        except Exception as exc:
            logger.debug(f"Could not update background activity status: {exc}")

    # ================================================================
    # BACKGROUND ACTIVITY - Delegated to StatusBar
    # ================================================================

    def begin_background_activity(self, key: str, message: str = "Background working...") -> None:
        """
        Background Activity စတင်သောအခါ ခေါ်ဆိုခြင်း
        Delegated to status_bar
        """
        if hasattr(self, 'status_bar') and self.status_bar and hasattr(self.status_bar, 'begin_background_activity'):
            self.status_bar.begin_background_activity(key, message)

    def end_background_activity(self, key: str) -> None:
        """
        Background Activity ပြီးဆုံးသောအခါ ခေါ်ဆိုခြင်း
        Delegated to status_bar
        """
        if hasattr(self, 'status_bar') and self.status_bar and hasattr(self.status_bar, 'end_background_activity'):
            self.status_bar.end_background_activity(key)

    def set_background_activity(self, key: str, message: str = "") -> None:
        """
        Background Activity အခြေအနေသတ်မှတ်ခြင်း
        Delegated to status_bar
        """
        if hasattr(self, 'status_bar') and self.status_bar and hasattr(self.status_bar, 'set_background_activity'):
            self.status_bar.set_background_activity(key, message)

    def on_background_activity_started(self, message: str) -> None:
        """
        Background Activity စတင်သောအခါ ခေါ်ဆိုခြင်း
        
        Args:
            message (str): ပြသရမည့် စာသား
        """
        self.begin_background_activity("auto_backup", message or "Auto backup running...")

    def on_background_activity_finished(self, _message: str) -> None:
        """
        Background Activity ပြီးဆုံးသောအခါ ခေါ်ဆိုခြင်း
        """
        self.end_background_activity("auto_backup")

    def finish_logout(self) -> None:
        """Finish logout without routing through the application-exit close dialog."""
        self.logout_triggered = True
        logger.info("Finishing logout and returning to login screen...")

        try:
            if hasattr(self, "update_loading"):
                self.update_loading("Stopping background timers...", 70)

            if hasattr(self, "telegram_listener_watchdog"):
                self.telegram_listener_watchdog.stop()
            if hasattr(self, "background_activity_timer"):
                self.background_activity_timer.stop()
            if hasattr(self, "blink_timer") and self.blink_timer:
                self.blink_timer.stop()

            clock_timer = self.clock_timer
            if isinstance(clock_timer, QTimer):
                clock_timer.stop()
            menu_clock_timer = self.menu_clock_timer
            if isinstance(menu_clock_timer, QTimer):
                menu_clock_timer.stop()

            if hasattr(self, "update_loading"):
                self.update_loading("Stopping backup services...", 82)
            if hasattr(self, "auto_backup_manager") and self.auto_backup_manager:
                self.auto_backup_manager.stop()
                self.auto_backup_manager = None
            if hasattr(self, "cloud_sync_manager") and self.cloud_sync_manager:
                self.cloud_sync_manager.stop()
                self.cloud_sync_manager = None

            if hasattr(self, "update_loading"):
                self.update_loading("Closing session...", 94)
            if hasattr(self, "update_loading"):
                self.update_loading("Logged out.", 100)
            # LoadingOverlay owns an application-wide WaitCursor. Release it
            # before this window is hidden and the login loop starts again.
            if hasattr(self, "hide_loading"):
                self.hide_loading()
            self.hide()

            app = QApplication.instance()
            if app:
                app.processEvents()
                app.quit()
                QTimer.singleShot(0, app.quit)
        except Exception as exc:
            logger.warning(f"Logout cleanup failed: {exc}")
            app = QApplication.instance()
            if app:
                while app.overrideCursor() is not None:
                    app.restoreOverrideCursor()
                app.quit()
                QTimer.singleShot(0, app.quit)

    # ================================================================
    # NOTIFICATION ICON
    # ================================================================

    def _init_notification_icon(self) -> None:
        """
        Stock Alert Notification Icon ကို စတင်သတ်မှတ်ခြင်း
        """
        from PyQt6.QtWidgets import QLabel
        
        self.notification_icon = QLabel()
        self.notification_icon.setFixedSize(16, 16)
        self.notification_icon.setStyleSheet("background-color: #ed4245; border-radius: 8px;")
        self.notification_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notification_icon.mousePressEvent = self.show_notification_dialog
        if self.status_bar:
            self.status_bar.addPermanentWidget(self.notification_icon)
        self.notification_icon.hide()
        
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_notification_icon)
        self.blink_state = False
        self.has_alerts = False

    # ================================================================
    # CLOSE EVENT - FIXED
    # ================================================================

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._startup_close_guard = False

    def closeEvent(self, event) -> None:
        """
        Window ကိုပိတ်သောအခါ ခေါ်ဆိုခြင်း
        - Background Services များကို ရပ်တန့်ခြင်း
        - User ကို အတည်ပြုမေးမြန်းခြင်း
        - Force process termination
        """
        if getattr(self, "_startup_close_guard", False) and not self.isVisible():
            logger.debug("Ignoring startup close event before MainWindow is visible")
            event.ignore()
            return

        if getattr(self, "_ignore_next_startup_close", False):
            logger.debug("Ignoring startup close event triggered while closing loading dialog")
            self._ignore_next_startup_close = False
            event.ignore()
            return

        if not self.logout_triggered and not self._confirm_application_close():
            event.ignore()
            return

        logger.info("Closing MainWindow and cleaning up background services...")

        try:
            if self.logout_triggered and hasattr(self, "update_loading"):
                self.update_loading("Stopping background timers...", 70)
            # 1. Stop all timers
            if hasattr(self, "telegram_listener_watchdog"):
                self.telegram_listener_watchdog.stop()
            if hasattr(self, "background_activity_timer"):
                self.background_activity_timer.stop()
            if hasattr(self, "blink_timer") and self.blink_timer:
                self.blink_timer.stop()
            clock_timer = self.clock_timer
            if isinstance(clock_timer, QTimer):
                clock_timer.stop()
            menu_clock_timer = self.menu_clock_timer
            if isinstance(menu_clock_timer, QTimer):
                menu_clock_timer.stop()
            
            # 2. Stop auto backup manager
            if self.logout_triggered and hasattr(self, "update_loading"):
                self.update_loading("Stopping backup services...", 78)
            if hasattr(self, "auto_backup_manager") and self.auto_backup_manager:
                self.auto_backup_manager.stop()
                self.auto_backup_manager = None
            if hasattr(self, "cloud_sync_manager") and self.cloud_sync_manager:
                self.cloud_sync_manager.stop()
                self.cloud_sync_manager = None
            
            if not self.logout_triggered:
                # 3. Stop Telegram listener on real application exit only. This can
                # wait up to a few seconds, so keep logout fast and let the login
                # loop reuse/restart integrations as needed.
                try:
                    from utils.telegram_service import stop_telegram_command_listener

                    stop_telegram_command_listener()
                except Exception as exc:
                    logger.warning(f"Error stopping telegram listener: {exc}")

                # 4. Stop customer display server on real application exit only.
                try:
                    from utils.customer_display_server import stop_customer_display_server

                    stop_customer_display_server()
                except Exception as exc:
                    logger.warning(f"Error stopping customer display server: {exc}")
            elif hasattr(self, "update_loading"):
                self.update_loading("Closing session...", 94)

            if self.logout_triggered and hasattr(self, "update_loading"):
                self.update_loading("Logged out.", 100)
            
            from PyQt6.QtCore import QCoreApplication
            QCoreApplication.quit()
            
        except Exception as exc:
            logger.warning(f"Error while stopping background services: {exc}")
        
        # Accept the event
        event.accept()
        
        # 6. Force exit for frozen executable
        import sys
        if getattr(sys, 'frozen', False) and not self.logout_triggered:
            logger.info("Frozen executable - forcing process exit...")
            import os
            os._exit(0)

    def _confirm_application_close(self) -> bool:
        """
        Application ကိုပိတ်ရန် သေချာစေရန် Dialog ပြသခြင်း
        
        Returns:
            bool: True ဆိုလျှင် ပိတ်မည်
        """
        if lang.get_current() == "my":
            title = "ZAY POS Desktop ပိတ်ရန်"
            message = "ZAY POS Desktop ကို ပိတ်မည်လား?"
            yes_text = "ပိတ်မည်"
            no_text = "မပိတ်ပါ"
        else:
            title = "Exit ZAY POS Desktop"
            message = "Do you want to close ZAY POS Desktop?"
            yes_text = "Exit"
            no_text = "Cancel"

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        yes_button = dialog.addButton(yes_text, QMessageBox.ButtonRole.AcceptRole)
        no_button = dialog.addButton(no_text, QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(no_button)
        dialog.setEscapeButton(no_button)
        dialog.exec()
        return dialog.clickedButton() == yes_button


def _install_main_window_mixins() -> None:
    """Attach pure-Python mixin methods without adding PyQt multiple inheritance."""
    for mixin in (MainWindowMenus, MainWindowActions, MainWindowHandlers):
        for name, value in mixin.__dict__.items():
            if name.startswith("__") or hasattr(MainWindow, name):
                continue
            setattr(MainWindow, name, value)


_install_main_window_mixins()
