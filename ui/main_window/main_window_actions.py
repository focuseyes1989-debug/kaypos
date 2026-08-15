# ui/main_window/main_window_actions.py
"""
Main Window Actions - Theme, Reports, Settings, and other actions
With sidebar text update support
"""

from typing import Optional, Dict, Any, Union, cast

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QApplication, QWidget, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from models.database import connect_db
from ui.themes import apply_theme as apply_theme_style
from ui.themes.theme_manager import get_current_theme, get_theme_colors, theme_manager
from ui.responsive_utils import parse_resolution
from utils.translations import tr
from utils.activity_logger import log_activity
from utils.receipt_images import resolve_receipt_image_path
from utils.system_theme import system_theme
from loguru import logger
import os


class MainWindowActions:
    """Handle action methods for MainWindow"""
    
    # Declare attributes to fix Pylance errors
    current_user: Dict[str, Any]
    user_id: int
    follow_system_theme: bool
    logout_triggered: bool
    logout_signal: Any
    auto_backup_manager: Optional[Any] = None
    _cashier_window: Optional[Any] = None  # Cashier window reference
    
    # UI references
    header: Optional[Any] = None
    sidebar: Optional[Any] = None
    status_bar: Optional[Any] = None
    sales_page: Optional[Any] = None
    dashboard_page: Optional[Any] = None
    expense_page: Optional[Any] = None
    customers_page: Optional[Any] = None
    receipts_page: Optional[Any] = None
    products_page: Optional[Any] = None
    inventory_page: Optional[Any] = None
    sales_summary_page: Optional[Any] = None
    product_grid: Optional[Any] = None
    
    # Menu actions
    dark_theme_action: Optional[Any] = None
    light_theme_action: Optional[Any] = None
    follow_system_theme_action: Optional[Any] = None

    # ========== THEME ACTIONS ==========
    def save_theme_to_db(self, theme_name: str) -> None:
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'theme'", (theme_name,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save theme: {e}")

    def apply_theme(self, theme_name: str) -> None:
        """Apply theme to entire application and refresh all widgets"""
        logger.info(f"Switching theme to: {theme_name}")
        app = QApplication.instance()
        if app:
            try:
                if hasattr(self, "show_loading"):
                    self.show_loading(f"Switching theme to {theme_name}...", 5)
                apply_theme_style(app, theme_name)

                if not self.follow_system_theme:
                    self.save_theme_to_db(theme_name)

                if hasattr(self, "update_loading"):
                    self.update_loading("Refreshing visible pages...", 20)
                self._update_menu_bar_clock_color(theme_name)
                QTimer.singleShot(0, lambda: self._start_chunked_theme_refresh(theme_name))
            except Exception:
                if hasattr(self, "hide_loading"):
                    self.hide_loading()
                raise

    def _finish_theme_refresh(self, theme_name: str) -> None:
        """Refresh visible theme-aware widgets after the app stylesheet changes."""
        self._update_all_pages_theme(theme_name)

        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                widget.update()
        if hasattr(self, "hide_loading"):
            self.hide_loading()

    def _start_chunked_theme_refresh(self, theme_name: str) -> None:
        """Refresh loaded widgets in batches so local styles match immediately."""
        app = QApplication.instance()
        if not app:
            return

        self._theme_refresh_name = theme_name
        self._theme_refresh_widgets = [
            widget for widget in app.allWidgets()
            if widget is not None and self._has_theme_refresh_method(widget)
        ]
        self._theme_refresh_index = 0
        if hasattr(self, "update_loading"):
            self.update_loading("Preparing theme refresh...", 30)
        self._update_all_pages_theme(theme_name)
        self._refresh_theme_batch()

    def _has_theme_refresh_method(self, widget: Any) -> bool:
        try:
            for method_name in ('update_theme', 'on_theme_changed', '_on_theme_changed', 'apply_theme_style', '_apply_theme'):
                if callable(getattr(widget, method_name, None)):
                    return True
            return False
        except RuntimeError:
            return False

    def _refresh_theme_batch(self) -> None:
        app = QApplication.instance()
        widgets = getattr(self, '_theme_refresh_widgets', [])
        theme_name = getattr(self, '_theme_refresh_name', get_current_theme())
        index = getattr(self, '_theme_refresh_index', 0)
        batch_size = 35

        for widget in widgets[index:index + batch_size]:
            self._notify_widget_theme_changed(widget, theme_name, self._safe_widget_name(widget))
            try:
                widget.update()
            except RuntimeError:
                pass

        index += batch_size
        self._theme_refresh_index = index
        total = max(1, len(widgets))
        progress = min(95, 30 + int((index / total) * 60))
        if hasattr(self, "update_loading"):
            self.update_loading("Applying theme to loaded widgets...", progress)

        if index < len(widgets):
            QTimer.singleShot(0, self._refresh_theme_batch)
            return

        if app:
            for widget in app.topLevelWidgets():
                try:
                    widget.update()
                except RuntimeError:
                    pass
        if hasattr(self, "sidebar") and self.sidebar and hasattr(self.sidebar, "_apply_modern_styles"):
            self.sidebar._apply_modern_styles()
        if hasattr(self, "update_loading"):
            self.update_loading("Theme updated.", 100)
        if hasattr(self, "hide_loading"):
            QTimer.singleShot(150, self.hide_loading)
        logger.info(f"Theme refresh completed for {len(widgets)} loaded widgets")

    def _safe_widget_name(self, widget: Any) -> str:
        try:
            return widget.__class__.__name__
        except RuntimeError:
            return "deleted_widget"

    def apply_manual_theme(self, theme_name: str) -> None:
        """Apply a user-selected menu theme and stop following the OS theme."""
        if self.follow_system_theme:
            self.follow_system_theme = False
            try:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE settings SET value = ? WHERE key = 'follow_system_theme'",
                    ('0',)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to save follow_system_theme: {e}")

        if hasattr(self, 'follow_system_theme_action') and self.follow_system_theme_action:
            self.follow_system_theme_action.setChecked(False)

        self.set_theme_menu_enabled(True)
        self.apply_theme(theme_name)

    def _update_all_pages_theme(self, theme_name: str) -> None:
        """Update all pages when theme changes"""
        widgets = [
            ('product_grid', getattr(self, 'product_grid', None)),
            ('sales_page', getattr(self, 'sales_page', None)),
            ('dashboard_page', getattr(self, 'dashboard_page', None)),
            ('expense_page', getattr(self, 'expense_page', None)),
            ('customers_page', getattr(self, 'customers_page', None)),
            ('receipts_page', getattr(self, 'receipts_page', None)),
            ('products_page', getattr(self, 'products_page', None)),
            ('inventory_page', getattr(self, 'inventory_page', None)),
            ('sales_summary_page', getattr(self, 'sales_summary_page', None)),
        ]

        for name, widget in widgets:
            self._notify_widget_theme_changed(widget, theme_name, name)

    def _notify_widget_theme_changed(self, widget: Optional[Any], theme_name: str, name: str = "widget") -> None:
        """Call the theme refresh method a widget actually implements."""
        try:
            if not widget:
                return
        except RuntimeError:
            return

        for method_name in ('update_theme', 'on_theme_changed', '_on_theme_changed', 'apply_theme_style', '_apply_theme'):
            try:
                method = getattr(widget, method_name, None)
            except RuntimeError:
                return
            if not callable(method):
                continue

            try:
                method(theme_name)
            except TypeError:
                try:
                    method()
                except RuntimeError as e:
                    if "has been deleted" not in str(e):
                        logger.error(f"Error updating theme for {name}.{method_name}: {e}")
                except Exception as e:
                    logger.error(f"Error updating theme for {name}.{method_name}: {e}")
            except RuntimeError as e:
                if "has been deleted" not in str(e):
                    logger.error(f"Error updating theme for {name}.{method_name}: {e}")
            except Exception as e:
                logger.error(f"Error updating theme for {name}.{method_name}: {e}")
            return

    def _update_menu_bar_clock_color(self, theme_name: Optional[str] = None) -> None:
        """Update clock text color based on current theme"""
        if hasattr(self, 'header') and self.header and hasattr(self.header, 'menu_bar_clock'):
            self.header.menu_bar_clock.setStyleSheet(f"""
                QLabel#menu_bar_clock {{
                    color: #ffffff;
                    font-size: 9pt;
                    font-weight: 500;
                    padding: 2px 0px;
                    background-color: transparent;
                    border: none;
                }}
            """)

    def set_theme_menu_enabled(self, enabled: bool) -> None:
        if hasattr(self, 'dark_theme_action') and self.dark_theme_action:
            self.dark_theme_action.setEnabled(enabled)
        if hasattr(self, 'light_theme_action') and self.light_theme_action:
            self.light_theme_action.setEnabled(enabled)

    def load_follow_system_theme(self) -> bool:
        """
        System Theme ကို လိုက်နာမည်လား ဆိုသည်ကို Database မှ ဖတ်ယူခြင်း
        
        Returns:
            bool: True ဆိုလျှင် System Theme ကို လိုက်နာမည်
        """
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='follow_system_theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] == '1' if row else True
        except Exception as e:
            logger.error(f"Failed to load follow_system_theme: {e}")
            return True

    def on_follow_system_theme_changed(self, checked: bool) -> None:
        """
        Follow System Theme Checkbox ပြောင်းလဲသောအခါ ခေါ်ဆိုခြင်း
        
        Args:
            checked (bool): Checkbox ၏ အခြေအနေ
        """
        self.follow_system_theme = checked
        # Save to database
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE settings SET value = ? WHERE key = 'follow_system_theme'",
                ('1' if checked else '0',)
            )
            conn.commit()
            conn.close()
            logger.info(f"Follow system theme set to: {checked}")
        except Exception as e:
            logger.error(f"Failed to save follow_system_theme: {e}")
        
        # Apply theme
        self.apply_theme_from_settings()
        
        # Update menu
        if hasattr(self, 'follow_system_theme_action') and self.follow_system_theme_action:
            self.follow_system_theme_action.setChecked(checked)

    def apply_theme_from_settings(self, refresh_widgets: bool = True) -> None:
        """
        Settings ထဲမှ Theme ကို အသုံးပြုခြင်း
        """
        if self.follow_system_theme:
            theme = system_theme.get_system_theme()
            self.set_theme_menu_enabled(True)
        else:
            try:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key='theme'")
                row = cursor.fetchone()
                saved_theme = row[0] if row else "Light"
                conn.close()
            except Exception as e:
                logger.error(f"Failed to load theme from settings: {e}")
                saved_theme = "Light"
            theme = saved_theme
            self.set_theme_menu_enabled(True)

        if refresh_widgets:
            self.apply_theme(theme)
        else:
            app = QApplication.instance()
            if app:
                apply_theme_style(app, theme)
            self._update_menu_bar_clock_color(theme)

        if hasattr(self, 'follow_system_theme_action') and self.follow_system_theme_action:
            self.follow_system_theme_action.setChecked(self.follow_system_theme)

    def on_system_theme_changed(self, theme_name: str) -> None:
        """
        System Theme ပြောင်းလဲသောအခါ ခေါ်ဆိုခြင်း
        
        Args:
            theme_name (str): Theme အမည်
        """
        if self.follow_system_theme:
            self.apply_theme(theme_name)

    def on_theme_manager_changed(self, theme_name: str) -> None:
        """
        Theme Manager မှ Theme ပြောင်းလဲသောအခါ ခေါ်ဆိုခြင်း
        
        Args:
            theme_name (str): Theme အမည် ("Dark" သို့မဟုတ် "Light")
        """
        self._update_menu_bar_clock_color(theme_name)
    
    # ========== REPORT ACTIONS ==========
    def open_sales_report(self) -> None:
        from ui.reports.reports_dialog import ReportsDialog

        dialog = ReportsDialog(self)
        dialog.set_default_tab(0)
        dialog.exec()

    def open_expense_report(self) -> None:
        from ui.reports.reports_dialog import ReportsDialog

        dialog = ReportsDialog(self)
        dialog.set_default_tab(1)
        dialog.exec()

    def open_profit_loss_report(self) -> None:
        from ui.profit_loss_report_dialog import ProfitLossReportDialog
        dialog = ProfitLossReportDialog(self)
        dialog.exec()

    def open_profit_report(self) -> None:
        from ui.profit_report_dialog import ProfitReportDialog

        dialog = ProfitReportDialog(self)
        dialog.exec()

    def open_financial_summary(self) -> None:
        from ui.reports.reports_dialog import ReportsDialog

        dialog = ReportsDialog(self)
        dialog.set_default_tab(3)
        if hasattr(dialog, 'btn_close'):
            dialog.btn_close.hide()
        dialog.exec()

    # ========== EXPENSE BUDGET & COMPARISON ACTIONS ==========
    def open_budget_settings(self) -> None:
        from ui.expense_budget_dialog import ExpenseBudgetDialog
        dialog = ExpenseBudgetDialog(self)
        dialog.exec()

    def open_expense_comparison(self) -> None:
        from ui.expense_comparison_dialog import ExpenseComparisonDialog
        dialog = ExpenseComparisonDialog(self)
        dialog.exec()

    # ========== CREDIT ACTIONS ==========
    def open_outstanding_report(self) -> None:
        from ui.customer_page.outstanding_report_dialog import OutstandingReportDialog

        dialog = OutstandingReportDialog(self)
        dialog.exec()

    # ========== BACKUP ACTIONS ==========
    def open_auto_backup(self) -> None:
        if hasattr(self, 'auto_backup_manager') and self.auto_backup_manager:
            from ui.auto_backup_dialog import AutoBackupDialog

            dialog = AutoBackupDialog(self.auto_backup_manager, self)
            dialog.exec()

    # ========== ROLE MANAGEMENT ==========
    def open_role_management(self) -> None:
        from ui.role_management_dialog import RoleManagementDialog

        dialog = RoleManagementDialog(self)
        dialog.exec()

    # ========== USER ACTIONS ==========
    def logout(self) -> None:
        logger.info(f"User {self.current_user['username']} logging out")
        if hasattr(self, "show_loading"):
            self.show_loading("Logging out...", 10)
        app = QApplication.instance()
        if app:
            app.processEvents()
        log_activity(self.current_user["id"], self.current_user["username"], "Logout", "User logged out")
        if hasattr(self, "update_loading"):
            self.update_loading("Saving logout activity...", 35)
        self.logout_triggered = True
        self.logout_signal.emit()
        if hasattr(self, "update_loading"):
            self.update_loading("Closing session...", 60)
        if hasattr(self, "finish_logout"):
            self.finish_logout()
            return
        # Use the parent window's close method via try/except
        try:
            cast(QWidget, self).close()
        except Exception:
            # Fallback: if close is not available, use the parent
            if hasattr(self, 'parent'):
                parent = cast(QWidget, self).parent()
                if isinstance(parent, QWidget) and hasattr(parent, 'close'):
                    parent.close()

    def exit_app(self) -> None:
        logger.info("Application exit requested")
        self.logout_triggered = False
        try:
            cast(QWidget, self).close()
        except Exception:
            if hasattr(self, 'parent'):
                parent = cast(QWidget, self).parent()
                if isinstance(parent, QWidget) and hasattr(parent, 'close'):
                    parent.close()

    def show_activity_log(self) -> None:
        from ui.activity_log_page import ActivityLogPage

        dialog = QDialog(cast(QWidget, self))
        dialog.setWindowTitle(tr("activity_log"))
        dialog.resize(1000, 600)
        layout = QVBoxLayout()
        layout.addWidget(ActivityLogPage())
        dialog.setLayout(layout)
        dialog.exec()

    # ========== SETTINGS ACTIONS ==========
    def _settings_dialog_title(self, key: str, fallback: str) -> str:
        title = tr(key)
        return fallback if title == key else (title if title else fallback)

    def _open_setting_dialog(self, title: str, widget: Any, width: int = 800, height: int = 600) -> None:
        if hasattr(widget, 'retranslateUi') and callable(getattr(widget, 'retranslateUi')):
            try:
                widget.retranslateUi()
            except Exception:
                pass

        dialog = QDialog(cast(QWidget, self))
        dialog.setWindowTitle(title)
        dialog.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        dialog.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        dialog.setSizeGripEnabled(True)
        dialog.setMinimumSize(min(width, 960), min(height, 640))
        dialog.resize(width, height)

        layout = QVBoxLayout(dialog)
        layout.addWidget(widget)

        dialog.exec()

    def open_settings_center_dialog(self) -> None:
        from ui.settings import SettingsCenterWidget

        widget = SettingsCenterWidget(
            current_user_role=self.current_user.get("role", "admin"),
            user_id=self.user_id,
        )
        widget.general_settings_changed.connect(self.refresh_general_settings)
        widget.general_settings_changed.connect(self.apply_theme_from_settings)
        widget.receipt_settings_changed.connect(self.refresh_receipt_settings)
        widget.print_settings_changed.connect(self.refresh_receipt_settings)
        widget.currency_changed.connect(self.refresh_currency)
        self._open_setting_dialog(
            self._settings_dialog_title("settings", "Settings Center"),
            widget,
            1240,
            780
        )

    def open_general_settings_dialog(self) -> None:
        from ui.settings import GeneralSettingWidget

        widget = GeneralSettingWidget()
        widget.settings_saved.connect(self.refresh_general_settings)
        widget.settings_saved.connect(self.apply_theme_from_settings)
        widget.follow_system_theme_changed.connect(self.on_follow_system_theme_changed)
        self._open_setting_dialog(
            self._settings_dialog_title("general_settings", "General Settings"),
            widget,
            980,
            700
        )

    def open_receipt_settings_dialog(self) -> None:
        from ui.settings import ReceiptSettingWidget

        widget = ReceiptSettingWidget()
        widget.receipt_settings_changed.connect(self.refresh_receipt_settings)
        self._open_setting_dialog(
            self._settings_dialog_title("receipt_setting", "Receipt Setting"),
            widget,
            1180,
            760
        )

    def open_print_settings_dialog(self) -> None:
        from ui.settings import PrintSettingWidget

        widget = PrintSettingWidget()
        widget.print_settings_changed.connect(self.refresh_receipt_settings)
        self._open_setting_dialog(
            self._settings_dialog_title("print_setting", "Print Setting"),
            widget,
            620,
            320
        )

    def open_database_connection_settings_dialog(self) -> None:
        from ui.settings import DatabaseConnectionSettingWidget

        widget = DatabaseConnectionSettingWidget()
        self._open_setting_dialog(
            "Database",
            widget,
            760,
            520
        )

    def open_restaurant_settings_dialog(self) -> None:
        from ui.settings import RestaurantSettingWidget

        widget = RestaurantSettingWidget()
        self._open_setting_dialog(
            self._settings_dialog_title("restaurant_setting", "Restaurant Setting"),
            widget,
            980,
            680
        )
        restaurant_page = getattr(self, "restaurant_page", None)
        if restaurant_page:
            try:
                restaurant_page.refresh_tables()
                restaurant_page.refresh_takeaway_orders()
            except Exception as exc:
                logger.error(f"Failed to refresh Restaurant page after settings: {exc}")

    def open_regional_settings_dialog(self) -> None:
        from ui.settings import RegionalSettingWidget

        widget = RegionalSettingWidget()
        widget.currency_changed.connect(self.refresh_currency)
        self._open_setting_dialog(
            self._settings_dialog_title("regional_settings", "Regional Settings"),
            widget,
            600,
            360
        )

    def open_update_settings_dialog(self) -> None:
        from ui.settings import UpdateSettingWidget

        widget = UpdateSettingWidget(user_id=self.user_id)
        self._open_setting_dialog(
            self._settings_dialog_title("update", "Update"),
            widget,
            720,
            540
        )

    def open_telegram_settings_dialog(self) -> None:
        from ui.settings import TelegramSettingWidget

        widget = TelegramSettingWidget()
        self._open_setting_dialog(
            self._settings_dialog_title("telegram", "Telegram"),
            widget,
            760,
            560
        )

    def open_youtube_settings_dialog(self) -> None:
        from ui.settings import YouTubeSettingWidget

        widget = YouTubeSettingWidget()
        widget.youtube_settings_changed.connect(self.refresh_customer_display_youtube)
        self._open_setting_dialog(
            "YouTube",
            widget,
            640,
            220
        )

    def open_performance_settings_dialog(self) -> None:
        from ui.settings import PerformanceSettingWidget

        widget = PerformanceSettingWidget()
        widget.performance_settings_changed.connect(self.refresh_performance_settings)
        self._open_setting_dialog(
            "Performance",
            widget,
            680,
            360
        )

    def refresh_performance_settings(self) -> None:
        from utils.performance import refresh_performance_settings
        from ui.sales_page.product_utils import load_thumbnail

        settings = refresh_performance_settings()
        try:
            load_thumbnail.cache_clear()
        except Exception:
            pass
        sales_page = getattr(self, "sales_page", None)
        product_grid = getattr(sales_page, "product_grid", None) if sales_page else None
        if product_grid and hasattr(product_grid, "apply_performance_settings"):
            product_grid.apply_performance_settings(settings)
        self.refresh_customer_display_youtube()
        if getattr(self, "status_bar", None):
            mode = "Low-end PC mode" if settings.low_end_mode else "Performance settings"
            self.status_bar.showMessage(f"{mode} applied", 3000)

    def refresh_customer_display_youtube(self) -> None:
        displays = []
        sales_page = getattr(self, "sales_page", None)
        if sales_page and getattr(sales_page, "customer_display", None):
            displays.append(sales_page.customer_display)

        cashier_window = getattr(self, "_cashier_window", None)
        cashier_display = getattr(cashier_window, "_customer_display", None) if cashier_window else None
        if cashier_display:
            displays.append(cashier_display)

        for display in displays:
            try:
                if hasattr(display, "load_youtube_player"):
                    display.load_youtube_player()
            except RuntimeError:
                continue

    def open_backup_reset_settings_dialog(self) -> None:
        from ui.settings import BackupResetSettingWidget

        widget = BackupResetSettingWidget(user_id=self.user_id)
        self._open_setting_dialog(
            self._settings_dialog_title("backup_reset", "Backup & Reset"),
            widget,
            820,
            420
        )

    def open_users_settings_dialog(self) -> None:
        from ui.settings import UsersSettingWidget

        widget = UsersSettingWidget(user_id=self.user_id)
        self._open_setting_dialog(
            self._settings_dialog_title("users", "Users"),
            widget,
            820,
            560
        )

    def refresh_receipt_settings(self) -> None:
        self.refresh_shop_info()
        if hasattr(self, 'sales_page') and self.sales_page:
            if hasattr(self.sales_page, 'load_receipt_settings'):
                self.sales_page.load_receipt_settings()
            if hasattr(self.sales_page, 'customer_display') and hasattr(self.sales_page.customer_display, 'load_shop_info'):
                self.sales_page.customer_display.load_shop_info()
        logger.info("Receipt settings refreshed")

    def refresh_general_settings(self) -> None:
        self.apply_window_resolution_from_settings()
        if hasattr(self, "apply_role_permissions"):
            self.apply_role_permissions()
        if hasattr(self, 'sales_page') and self.sales_page:
            if hasattr(self.sales_page, 'load_settings'):
                self.sales_page.load_settings()
            if hasattr(self.sales_page, 'load_loyalty_settings'):
                self.sales_page.load_loyalty_settings()
            if hasattr(self.sales_page, 'load_payment_types'):
                self.sales_page.load_payment_types()
            if hasattr(self.sales_page, 'update_totals'):
                self.sales_page.update_totals()
            logger.info("General settings refreshed in SalesPage")

    def apply_window_resolution_from_settings(self) -> None:
        """Resize the main window to the saved app resolution."""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='window_resolution'")
            row = cursor.fetchone()
            conn.close()
            saved_resolution = row[0] if row else "1366x768"
            width, height = parse_resolution(saved_resolution)

            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.availableGeometry()
                width = min(width, geometry.width())
                height = min(height, geometry.height())
                x = geometry.x() + max(0, (geometry.width() - width) // 2)
                y = geometry.y() + max(0, (geometry.height() - height) // 2)
                self.setGeometry(x, y, width, height)
            else:
                self.resize(width, height)

            self.setMinimumSize(min(1366, width), min(768, height))
            logger.info(f"Applied window resolution: {width}x{height}")
        except Exception as e:
            logger.error(f"Failed to apply window resolution: {e}")

    def refresh_currency(self) -> None:
        if hasattr(self, 'sales_page') and self.sales_page:
            if hasattr(self.sales_page, 'cart_widget') and hasattr(self.sales_page.cart_widget, 'refresh_table'):
                self.sales_page.cart_widget.refresh_table()
            elif hasattr(self.sales_page, 'load_cart'):
                self.sales_page.load_cart()
            if hasattr(self.sales_page, 'totals_widget') and hasattr(self.sales_page.totals_widget, 'update_totals'):
                self.sales_page.totals_widget.update_totals()
            elif hasattr(self.sales_page, 'update_totals'):
                self.sales_page.update_totals()
            logger.info("Currency refreshed in SalesPage")

    def refresh_shop_info(self) -> None:
        """Refresh shop logo and title"""
        self.update_shop_logo()
        self.update_shop_title()
        logger.info("Shop info refreshed")

    def update_shop_logo(self) -> None:
        """Update shop logo from database"""
        try:
            logo_path = resolve_receipt_image_path("logo")
            
            # Use header's logo_label
            if hasattr(self, 'header') and self.header and hasattr(self.header, 'logo_label'):
                if logo_path and os.path.exists(logo_path):
                    pixmap = QPixmap(logo_path)
                    if not pixmap.isNull():
                        self.header.set_shop_logo(pixmap)
                        return
                self.header.logo_label.setVisible(False)
        except Exception as e:
            logger.error(f"Failed to load shop logo: {e}")
            if hasattr(self, 'header') and self.header and hasattr(self.header, 'logo_label'):
                self.header.logo_label.setVisible(False)

    def update_shop_title(self) -> None:
        """Update shop title from database"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='shop_name'")
            row = cursor.fetchone()
            conn.close()
            shop_name = row[0] if row and row[0] else "ZAY POS"
        except Exception as e:
            logger.error(f"Failed to load shop name: {e}")
            shop_name = "ZAY POS"
        
        # Use header's title_label
        if hasattr(self, 'header') and self.header and hasattr(self.header, 'title_label'):
            self.header.set_shop_title(shop_name)
    
    # ========== SIDEBAR ACTIONS ==========
    def update_sidebar_texts(self) -> None:
        """
        Update sidebar button texts based on current language
        Called when language changes
        """
        if not hasattr(self, 'sidebar') or not self.sidebar:
            return
        
        page_names = {
            0: "Dashboard",
            1: "Sales Summary",
            2: "Products",
            9: "Discounts",
            8: "Ai",
            3: "Inventory",
            4: "Receipts",
            5: "Sales",
            6: "Customers",
            7: "Expense",
        }
        
        # Check if sidebar is collapsed
        is_collapsed = getattr(self.sidebar, '_is_collapsed', False)
        
        for btn in self.sidebar.sidebar_buttons:
            idx = btn.property("page_index")
            if idx in page_names:
                # Store the text for when expanded
                btn.setProperty("page_text", page_names[idx])
                # Only update visible text if not collapsed
                if not is_collapsed:
                    btn.setText(page_names[idx])

    # ========== CASHIER MODE ACTIONS ==========
    def open_cashier_mode(self) -> None:
        """Open Cashier Mode - Hide Main Window and Show Cashier Window"""
        from ui.cashier_window import MainCashierWindow
        
        # Cashier window ရှိမရှိ စစ်ဆေးခြင်း
        if hasattr(self, '_cashier_window') and self._cashier_window is not None:
            try:
                # Already open - just bring to front
                self._cashier_window.raise_()
                self._cashier_window.activateWindow()
                return
            except Exception:
                self._cashier_window = None
        
        # Cashier window အသစ်ဖွင့်ခြင်း
        try:
            # Main window ကို Hide လုပ်မယ်
            main_widget = cast(QWidget, self)
            main_widget.hide()
            
            # Cashier window ကို ဖန်တီးမယ်
            self._cashier_window = MainCashierWindow(self.current_user)
            
            # Cashier window ပိတ်တဲ့အခါ Main window ပြန်ပြဖို့ callback သတ်မှတ်
            self._cashier_window.set_on_closed_callback(self._on_cashier_window_closed)
            
            # Cashier window ကို Full Screen နီးပါးဖွင့်မယ်
            self._cashier_window.showMaximized()
            self._cashier_window.raise_()
            self._cashier_window.activateWindow()
            
            logger.info(f"Cashier Mode opened by: {self.current_user['username']}")
            
        except Exception as e:
            logger.error(f"Failed to open Cashier Mode: {e}")
            # Error ဖြစ်ရင် Main window ကို ပြန်ပြမယ်
            main_widget = cast(QWidget, self)
            main_widget.show()
            
            parent_widget = QApplication.activeWindow()
            if parent_widget is None:
                parent_widget = cast(QWidget, self)
            
            QMessageBox.critical(
                parent_widget,
                "Error",
                f"Cashier Mode ဖွင့်မရပါ:\n{str(e)}"
            )
    
    def _on_cashier_window_closed(self) -> None:
        """Cashier window ပိတ်သွားတဲ့အခါ Main window ကို ပြန်ပြခြင်း"""
        self._cashier_window = None
        
        # Main window ကို ပြန်ပြမယ်
        main_widget = cast(QWidget, self)
        main_widget.show()
        main_widget.raise_()
        main_widget.activateWindow()
        
        logger.info("Cashier Mode closed - Main window restored")
