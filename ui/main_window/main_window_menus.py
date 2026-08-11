# ui/main_window/main_window_menus.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, cast

from PyQt6.QtWidgets import QMainWindow, QMenu
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QKeySequence
from utils.translations import tr
from utils.permissions import PermissionManager, Permission
from loguru import logger

if TYPE_CHECKING:
    from ui.main_window.main_window import MainWindow


class MainWindowMenus:
    """Handle menu bar creation for MainWindow"""

    # Expected MainWindow mixin attributes and methods
    current_user: Dict[str, Any]
    follow_system_theme: bool
    switch_to_page: Any
    switch_to_inventory_tab: Any
    open_outstanding_report: Any
    open_role_management: Any
    open_auto_backup: Any
    open_telegram_settings_dialog: Any
    open_youtube_settings_dialog: Any
    open_performance_settings_dialog: Any
    open_update_settings_dialog: Any
    open_budget_settings: Any
    open_expense_comparison: Any
    logout: Any
    exit_app: Any
    refresh_all_pages: Any
    open_general_settings_dialog: Any
    open_receipt_settings_dialog: Any
    open_regional_settings_dialog: Any
    open_backup_reset_settings_dialog: Any
    open_users_settings_dialog: Any
    open_profit_report: Any
    open_financial_summary: Any
    open_cashier_mode: Any
    apply_theme: Any
    apply_manual_theme: Any
    on_follow_system_theme_changed: Any
    show_activity_log: Any
    sales_page: Any

    file_menu: QMenu
    view_menu: QMenu
    products_menu: QMenu
    ai_pages_menu: QMenu
    inventory_menu: QMenu
    receipts_menu: QMenu
    customers_menu: QMenu
    credit_menu: QMenu
    expense_menu: QMenu
    settings_menu: QMenu
    reports_menu: QMenu
    tools_menu: QMenu
    themes_menu: QMenu
    admin_menu: QMenu

    def _qmainwindow(self) -> QMainWindow:
        return cast(QMainWindow, self)

    def create_menu_bar(self) -> None:
        main_window = self._qmainwindow()
        menubar = main_window.menuBar()
        assert menubar is not None
        user_id = self.current_user["id"]
        
        # ========== FILE MENU ==========
        self.file_menu = cast(QMenu, menubar.addMenu("File"))
        self._create_file_menu()
        
        # ========== VIEW MENU ==========
        self.view_menu = cast(QMenu, menubar.addMenu("View"))
        self._create_view_menu()
        
        # ========== PRODUCTS MENU ==========
        if PermissionManager.user_can_view_page(user_id, "products"):
            self.products_menu = cast(QMenu, menubar.addMenu("Products"))  # ✅ tr("products") ကို "Products" လို့ တိုက်ရိုက်ပြောင်း
            self.products_action = QAction("Products", main_window)  # ✅ tr("products") ကို "Products" လို့ တိုက်ရိုက်ပြောင်း
            self.products_action.triggered.connect(lambda: self.switch_to_page(2))
            self.products_menu.addAction(self.products_action)
        
        # ========== AI PAGES MENU ==========
        if PermissionManager.user_can_view_page(user_id, "ai_pages"):
            self.ai_pages_menu = cast(QMenu, menubar.addMenu("Ai"))  # ✅ "Ai" လို့ တိုက်ရိုက်သတ်မှတ်
            self.ai_pages_action = QAction("Ai", main_window)  # ✅ "Ai" လို့ တိုက်ရိုက်သတ်မှတ်
            self.ai_pages_action.triggered.connect(lambda: self.switch_to_page(8))
            self.ai_pages_menu.addAction(self.ai_pages_action)

        # ========== INVENTORY MENU ==========
        if PermissionManager.user_can_view_page(user_id, "inventory"):
            self.inventory_menu = cast(QMenu, menubar.addMenu("Inventory"))
            self._create_inventory_submenu()

        # ========== RECEIPTS MENU ==========
        if PermissionManager.user_can_view_page(user_id, "receipts"):
            self.receipts_menu = cast(QMenu, menubar.addMenu("Receipts"))  # ✅ tr("receipts") ကို "Receipts" လို့ တိုက်ရိုက်ပြောင်း
            self.receipts_action = QAction("Receipts", main_window)  # ✅ tr("receipts") ကို "Receipts" လို့ တိုက်ရိုက်ပြောင်း
            self.receipts_action.triggered.connect(lambda: self.switch_to_page(4))
            self.receipts_menu.addAction(self.receipts_action)

        # ========== CUSTOMERS MENU ==========
        if PermissionManager.user_can_view_page(user_id, "customers"):
            self.customers_menu = cast(QMenu, menubar.addMenu("Customers"))  # ✅ tr("customers") ကို "Customers" လို့ တိုက်ရိုက်ပြောင်း
            self.customers_action = QAction("Customers", main_window)  # ✅ tr("customers") ကို "Customers" လို့ တိုက်ရိုက်ပြောင်း
            self.customers_action.triggered.connect(lambda: self.switch_to_page(6))
            self.customers_menu.addAction(self.customers_action)

        # ========== CREDIT MENU ==========
        if PermissionManager.user_has_permission(user_id, Permission.VIEW_CREDIT):
            self.credit_menu = cast(QMenu, menubar.addMenu("Credit"))  # ✅ tr("credit") ကို "Credit" လို့ တိုက်ရိုက်ပြောင်း
            self.outstanding_report_action = QAction("Outstanding Report", main_window)  # ✅ tr("outstanding_report") ကို တိုက်ရိုက်ပြောင်း
            self.outstanding_report_action.triggered.connect(self.open_outstanding_report)
            self.credit_menu.addAction(self.outstanding_report_action)
            
            if self.current_user["role"] == "admin":
                self.role_management_action = QAction("Role Management", main_window)  # ✅ tr("role_management") ကို တိုက်ရိုက်ပြောင်း
                self.role_management_action.triggered.connect(self.open_role_management)
                self.credit_menu.addAction(self.role_management_action)

        # ========== EXPENSE MENU ==========
        if PermissionManager.user_can_view_page(user_id, "expense"):
            self.expense_menu = cast(QMenu, menubar.addMenu("Expense"))
            self._create_expense_menu()

        # ========== SETTINGS MENU ==========
        if PermissionManager.user_can_view_page(user_id, "settings"):
            self.settings_menu = cast(QMenu, menubar.addMenu("Settings"))
            self._create_settings_menu()

        # ========== REPORTS MENU ==========
        if PermissionManager.user_has_permission(user_id, Permission.VIEW_REPORTS):
            self.reports_menu = cast(QMenu, menubar.addMenu("Reports"))
            self._create_reports_menu()

        # ========== TOOLS MENU ==========
        if PermissionManager.user_has_permission(user_id, Permission.BACKUP) or \
           PermissionManager.user_has_permission(user_id, Permission.EDIT_SETTINGS):
            self.tools_menu = cast(QMenu, menubar.addMenu("Tools"))
            self._create_tools_menu()

        # ========== THEMES MENU ==========
        self.themes_menu = cast(QMenu, menubar.addMenu("Themes"))
        self._create_themes_menu()

        # ========== ADMIN MENU ==========
        if self.current_user["role"] == "admin":
            self.admin_menu = cast(QMenu, menubar.addMenu("Admin"))  # ✅ tr("admin") ကို "Admin" လို့ တိုက်ရိုက်ပြောင်း
            self.activity_log_action = QAction("Activity Log", main_window)  # ✅ tr("activity_log") ကို တိုက်ရိုက်ပြောင်း
            self.activity_log_action.triggered.connect(self.show_activity_log)
            self.admin_menu.addAction(self.activity_log_action)

    def _create_tools_menu(self) -> None:
        """Create Tools menu items - Auto Backup, Telegram, YouTube, Update"""
        main_window = self._qmainwindow()
        user_id = self.current_user["id"]
        can_edit_settings = PermissionManager.user_has_permission(user_id, Permission.EDIT_SETTINGS)
        edit_tooltip = "You don't have permission to edit settings"
        
        # Auto Backup (requires BACKUP permission)
        if PermissionManager.user_has_permission(user_id, Permission.BACKUP):
            self.auto_backup_action = QAction("Auto Backup", main_window)  # ✅ tr("auto_backup") ကို တိုက်ရိုက်ပြောင်း
            self.auto_backup_action.triggered.connect(self.open_auto_backup)
            self.tools_menu.addAction(self.auto_backup_action)
            self.tools_menu.addSeparator()
        
        # Telegram Settings (requires EDIT_SETTINGS permission)
        self.telegram_settings_action = QAction("Telegram", main_window)  # ✅ တိုက်ရိုက်ပြောင်း
        self.telegram_settings_action.triggered.connect(self.open_telegram_settings_dialog)
        self.telegram_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.telegram_settings_action.setToolTip(edit_tooltip)
        self.tools_menu.addAction(self.telegram_settings_action)

        self.youtube_settings_action = QAction("YouTube", main_window)
        self.youtube_settings_action.triggered.connect(self.open_youtube_settings_dialog)
        self.youtube_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.youtube_settings_action.setToolTip(edit_tooltip)
        self.tools_menu.addAction(self.youtube_settings_action)

        self.performance_settings_action = QAction("Performance", main_window)
        self.performance_settings_action.triggered.connect(self.open_performance_settings_dialog)
        self.performance_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.performance_settings_action.setToolTip(edit_tooltip)
        self.tools_menu.addAction(self.performance_settings_action)
        
        # Update Settings (no special permission required - user can check updates)
        self.update_settings_action = QAction("Update", main_window)  # ✅ တိုက်ရိုက်ပြောင်း
        self.update_settings_action.triggered.connect(self.open_update_settings_dialog)
        self.tools_menu.addAction(self.update_settings_action)

    def _create_inventory_submenu(self) -> None:
        """Create Inventory submenu items"""
        main_window = self._qmainwindow()
        logger.info("Creating inventory submenu...")
        
        # Tab indices mapping for InventoryPage
        # 0: Current Stock, 1: Low Stock Alert, 2: Supplier, 
        # 3: Purchase History, 4: Expiry Date, 5: Inventory Logs, 6: Stock by Location
        
        # Current Stock - tab index 0
        self.current_stock_action = QAction("Current Stock", main_window)  # ✅ tr("current_stock") ကို တိုက်ရိုက်ပြောင်း
        self.current_stock_action.triggered.connect(lambda: self.switch_to_inventory_tab(0))
        self.inventory_menu.addAction(self.current_stock_action)
        
        # Low Stock Alert - tab index 1
        self.low_stock_alert_action = QAction("Low Stock Alert", main_window)  # ✅ tr("low_stock_alert_tab") ကို တိုက်ရိုက်ပြောင်း
        self.low_stock_alert_action.triggered.connect(lambda: self.switch_to_inventory_tab(1))
        self.inventory_menu.addAction(self.low_stock_alert_action)
        
        # Supplier - tab index 2
        self.supplier_menu_action = QAction("Supplier", main_window)  # ✅ tr("supplier") ကို တိုက်ရိုက်ပြောင်း
        self.supplier_menu_action.triggered.connect(lambda: self.switch_to_inventory_tab(2))
        self.inventory_menu.addAction(self.supplier_menu_action)
        
        # Purchase History - tab index 3
        self.purchase_history_menu_action = QAction("Purchase History", main_window)  # ✅ tr("purchase_history") ကို တိုက်ရိုက်ပြောင်း
        self.purchase_history_menu_action.triggered.connect(lambda: self.switch_to_inventory_tab(3))
        self.inventory_menu.addAction(self.purchase_history_menu_action)
        
        # Expiry Date - tab index 4
        self.expiry_date_action = QAction("Expiry Date", main_window)  # ✅ tr("expiry_date") ကို တိုက်ရိုက်ပြောင်း
        self.expiry_date_action.triggered.connect(lambda: self.switch_to_inventory_tab(4))
        self.inventory_menu.addAction(self.expiry_date_action)
        
        # Inventory Logs - tab index 5
        self.inventory_logs_action = QAction("Inventory Logs", main_window)  # ✅ tr("inventory_logs") ကို တိုက်ရိုက်ပြောင်း
        self.inventory_logs_action.triggered.connect(lambda: self.switch_to_inventory_tab(5))
        self.inventory_menu.addAction(self.inventory_logs_action)
        
        # Stock by Location - tab index 6
        self.stock_by_location_action = QAction("Stock by Location", main_window)  # ✅ tr("stock_by_location") ကို တိုက်ရိုက်ပြောင်း
        self.stock_by_location_action.triggered.connect(lambda: self.switch_to_inventory_tab(6))
        self.inventory_menu.addAction(self.stock_by_location_action)
        
        logger.info("Inventory submenu created with 7 items")

    def _create_expense_menu(self) -> None:
        """Create Expense menu items"""
        main_window = self._qmainwindow()

        # Expense page (existing)
        self.expense_action = QAction("Expense", main_window)  # ✅ tr("expense") ကို တိုက်ရိုက်ပြောင်း
        self.expense_action.triggered.connect(lambda: self.switch_to_page(7))
        self.expense_menu.addAction(self.expense_action)
        
        self.expense_menu.addSeparator()
        
        # Budget Settings
        self.budget_settings_action = QAction("Budget Settings", main_window)  # ✅ tr("budget_settings") ကို တိုက်ရိုက်ပြောင်း
        self.budget_settings_action.triggered.connect(self.open_budget_settings)
        self.expense_menu.addAction(self.budget_settings_action)
        
        # Expense Comparison
        self.expense_comparison_action = QAction("Expense Comparison", main_window)  # ✅ tr("expense_comparison") ကို တိုက်ရိုက်ပြောင်း
        self.expense_comparison_action.triggered.connect(self.open_expense_comparison)
        self.expense_menu.addAction(self.expense_comparison_action)

    def _create_file_menu(self) -> None:
        """Create File menu items"""
        main_window = self._qmainwindow()
        
        # Refresh
        self.refresh_action = QAction("Refresh", main_window)
        self.refresh_action.setShortcut(QKeySequence("F5"))
        self.refresh_action.setStatusTip("Refresh all pages")
        self.refresh_action.triggered.connect(self.refresh_all_pages)
        self.file_menu.addAction(self.refresh_action)
        
        self.file_menu.addSeparator()
        
        # ─── CASHIER MODE (NEW) ─────────────────────────────────────────
        self.cashier_mode_action = QAction("Cashier Mode", main_window)
        self.cashier_mode_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.cashier_mode_action.setStatusTip("Switch to Cashier Mode (Full Screen)")
        self.cashier_mode_action.triggered.connect(self.open_cashier_mode)
        self.file_menu.addAction(self.cashier_mode_action)
        
        self.file_menu.addSeparator()

        self.customer_display_action = QAction("Customer Display", main_window)
        self.customer_display_action.setShortcut(QKeySequence("Ctrl+D"))
        self.customer_display_action.setStatusTip("Show or hide the customer display")
        self.customer_display_action.triggered.connect(
            lambda: self._invoke_sales_page_action("toggle_customer_display")
        )
        self.file_menu.addAction(self.customer_display_action)

        self.open_cash_drawer_action = QAction("Open Cash Drawer", main_window)
        self.open_cash_drawer_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.open_cash_drawer_action.setStatusTip("Open the cash drawer")
        self.open_cash_drawer_action.triggered.connect(
            lambda: self._invoke_sales_page_action("open_cash_drawer")
        )
        self.file_menu.addAction(self.open_cash_drawer_action)

        self.file_menu.addSeparator()
        
        # Logout
        self.logout_action = QAction("Logout", main_window)
        self.logout_action.triggered.connect(self.logout)
        self.file_menu.addAction(self.logout_action)

        self.file_menu.addSeparator()
        
        # Exit
        self.exit_action = QAction("Exit", main_window)
        self.exit_action.triggered.connect(self.exit_app)
        self.file_menu.addAction(self.exit_action)

    def _invoke_sales_page_action(self, method_name: str) -> None:
        sales_page = getattr(self, "sales_page", None)
        method = getattr(sales_page, method_name, None)
        if callable(method):
            method()
            return

        self.switch_to_page(5)
        QTimer.singleShot(200, lambda: self._invoke_sales_page_action(method_name))

    def _create_view_menu(self) -> None:
        """Create View menu items for Dashboard and Sales Summary"""
        main_window = self._qmainwindow()
        user_id = self.current_user["id"]
        
        # Dashboard - Use translation
        if PermissionManager.user_can_view_page(user_id, "dashboard"):
            self.dashboard_menu_action = QAction("Dashboard", main_window)  # ✅ tr("dashboard") ကို တိုက်ရိုက်ပြောင်း
            self.dashboard_menu_action.triggered.connect(lambda: self.switch_to_page(0))
            self.view_menu.addAction(self.dashboard_menu_action)
        
        # Sales Summary - Use translation
        if PermissionManager.user_can_view_page(user_id, "sales_summary"):
            self.sales_summary_menu_action = QAction("Sales Summary", main_window)  # ✅ tr("sales_summary") ကို တိုက်ရိုက်ပြောင်း
            self.sales_summary_menu_action.triggered.connect(lambda: self.switch_to_page(1))
            self.view_menu.addAction(self.sales_summary_menu_action)

    def _create_settings_menu(self) -> None:
        """Create Settings menu items as standalone dialogs."""
        main_window = self._qmainwindow()
        user_id = self.current_user["id"]
        can_edit_settings = PermissionManager.user_has_permission(user_id, Permission.EDIT_SETTINGS)
        edit_tooltip = "You don't have permission to edit settings"

        self.general_settings_action = QAction("General Settings", main_window)  # ✅ tr("general_settings") ကို တိုက်ရရိပ်ပြောင်း
        self.general_settings_action.triggered.connect(self.open_general_settings_dialog)
        self.general_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.general_settings_action.setToolTip(edit_tooltip)
        self.settings_menu.addAction(self.general_settings_action)

        self.receipt_settings_action = QAction("Receipt Settings", main_window)  # ✅ tr("receipt_setting") ကို တိုက်ရိုက်ပြောင်း
        self.receipt_settings_action.triggered.connect(self.open_receipt_settings_dialog)
        self.receipt_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.receipt_settings_action.setToolTip(edit_tooltip)
        self.settings_menu.addAction(self.receipt_settings_action)

        self.restaurant_settings_action = QAction("Restaurant Setting", main_window)
        self.restaurant_settings_action.triggered.connect(self.open_restaurant_settings_dialog)
        self.restaurant_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.restaurant_settings_action.setToolTip(edit_tooltip)
        self.settings_menu.addAction(self.restaurant_settings_action)

        self.regional_settings_action = QAction("Regional Settings", main_window)
        self.regional_settings_action.triggered.connect(self.open_regional_settings_dialog)
        self.regional_settings_action.setEnabled(can_edit_settings)
        if not can_edit_settings:
            self.regional_settings_action.setToolTip(edit_tooltip)
        self.settings_menu.addAction(self.regional_settings_action)

        self.settings_menu.addSeparator()

        # Backup & Reset (requires BACKUP permission)
        if PermissionManager.user_has_permission(user_id, Permission.BACKUP):
            self.backup_reset_settings_action = QAction("Backup & Reset", main_window)
            self.backup_reset_settings_action.triggered.connect(self.open_backup_reset_settings_dialog)
            self.settings_menu.addAction(self.backup_reset_settings_action)

        # Users (requires VIEW_USERS permission)
        if PermissionManager.user_has_permission(user_id, Permission.VIEW_USERS):
            self.users_settings_action = QAction("Users", main_window)
            self.users_settings_action.triggered.connect(self.open_users_settings_dialog)
            self.settings_menu.addAction(self.users_settings_action)

    def _create_reports_menu(self) -> None:
        """Create Reports menu items"""
        main_window = self._qmainwindow()
        
        # Profit Report (Detailed)
        self.profit_report_action = QAction("Profit Report", main_window)  # ✅ tr("profit_report") ကို တိုက်ရိုက်ပြောင်း
        self.profit_report_action.triggered.connect(self.open_profit_report)
        self.reports_menu.addAction(self.profit_report_action)
        
        # Financial Summary
        self.financial_summary_action = QAction("Financial Summary", main_window)
        self.financial_summary_action.triggered.connect(self.open_financial_summary)
        self.reports_menu.addAction(self.financial_summary_action)

    def _create_themes_menu(self) -> None:
        """Create Themes menu items - Only Dark and Light."""
        main_window = self._qmainwindow()

        # Dark Theme
        self.dark_theme_action = QAction("Dark", main_window)  # ✅ tr("dark") ကို တိုက်ရိုက်ပြောင်း
        self.dark_theme_action.triggered.connect(lambda: self.apply_manual_theme("Dark"))
        self.themes_menu.addAction(self.dark_theme_action)
        
        # Light Theme
        self.light_theme_action = QAction("Light", main_window)  # ✅ tr("light") ကို တိုက်ရိုက်ပြောင်း
        self.light_theme_action.triggered.connect(lambda: self.apply_manual_theme("Light"))
        self.themes_menu.addAction(self.light_theme_action)
        
        self.themes_menu.addSeparator()
        
        # Follow System Theme
        self.follow_system_theme_action = QAction("Follow System Theme", main_window)  # ✅ tr("follow_system_theme") ကို တိုက်ရိုက်ပြောင်း
        self.follow_system_theme_action.setCheckable(True)
        self.follow_system_theme_action.setChecked(self.follow_system_theme)
        self.follow_system_theme_action.triggered.connect(self.on_follow_system_theme_changed)
        self.themes_menu.addAction(self.follow_system_theme_action)
