# ui/main_window/main_window_handlers.py
"""
Main Window Handlers - Event handlers and signal connections
"""

from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox, QWidget
from utils.translations import tr
from utils.language import lang
from loguru import logger


class MainWindowHandlers(QWidget):
    """Handle event handlers for MainWindow"""
    
    # Declare attributes to fix Pylance errors
    current_user: Dict[str, Any]
    status_bar: Optional[Any] = None
    sidebar: Optional[Any] = None
    pages: Optional[Any] = None
    page_title: Optional[Any] = None
    
    # Page references
    dashboard_page: Optional[Any] = None
    sales_summary_page: Optional[Any] = None
    products_page: Optional[Any] = None
    ai_pages_page: Optional[Any] = None
    inventory_page: Optional[Any] = None
    receipts_page: Optional[Any] = None
    sales_page: Optional[Any] = None
    customers_page: Optional[Any] = None
    expense_page: Optional[Any] = None
    
    # Notification
    notification_icon: Optional[Any] = None
    blink_timer: Optional[Any] = None
    has_alerts: bool = False
    _alert_shown: bool = False
    
    # Menu actions
    file_menu: Optional[Any] = None
    view_menu: Optional[Any] = None
    products_menu: Optional[Any] = None
    ai_pages_menu: Optional[Any] = None
    inventory_menu: Optional[Any] = None
    receipts_menu: Optional[Any] = None
    customers_menu: Optional[Any] = None
    credit_menu: Optional[Any] = None
    expense_menu: Optional[Any] = None
    settings_menu: Optional[Any] = None
    reports_menu: Optional[Any] = None
    tools_menu: Optional[Any] = None
    themes_menu: Optional[Any] = None
    admin_menu: Optional[Any] = None
    
    # Action references
    refresh_action: Optional[Any] = None
    logout_action: Optional[Any] = None
    exit_action: Optional[Any] = None
    dashboard_menu_action: Optional[Any] = None
    sales_summary_menu_action: Optional[Any] = None
    products_action: Optional[Any] = None
    ai_pages_action: Optional[Any] = None
    current_stock_action: Optional[Any] = None
    low_stock_alert_action: Optional[Any] = None
    supplier_menu_action: Optional[Any] = None
    purchase_history_menu_action: Optional[Any] = None
    expiry_date_action: Optional[Any] = None
    inventory_logs_action: Optional[Any] = None
    stock_by_location_action: Optional[Any] = None
    receipts_action: Optional[Any] = None
    customers_action: Optional[Any] = None
    outstanding_report_action: Optional[Any] = None
    role_management_action: Optional[Any] = None
    expense_action: Optional[Any] = None
    budget_settings_action: Optional[Any] = None
    expense_comparison_action: Optional[Any] = None
    general_settings_action: Optional[Any] = None
    receipt_settings_action: Optional[Any] = None
    regional_settings_action: Optional[Any] = None
    update_settings_action: Optional[Any] = None
    telegram_settings_action: Optional[Any] = None
    youtube_settings_action: Optional[Any] = None
    performance_settings_action: Optional[Any] = None
    backup_reset_settings_action: Optional[Any] = None
    users_settings_action: Optional[Any] = None
    sales_report_action: Optional[Any] = None
    expense_report_action: Optional[Any] = None
    profit_loss_report_action: Optional[Any] = None
    profit_report_action: Optional[Any] = None
    financial_summary_action: Optional[Any] = None
    auto_backup_action: Optional[Any] = None
    dark_theme_action: Optional[Any] = None
    light_theme_action: Optional[Any] = None
    follow_system_theme_action: Optional[Any] = None
    activity_log_action: Optional[Any] = None
    
    def setup_refresh_shortcut(self) -> None:
        from PyQt6.QtGui import QShortcut, QKeySequence
        # Use self as parent - MainWindow inherits QMainWindow which inherits QWidget
        parent_widget = self if isinstance(self, QWidget) else None
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), parent_widget)
        self.refresh_shortcut.activated.connect(self.refresh_all_pages)
        self.refresh_shortcut2 = QShortcut(QKeySequence("Ctrl+R"), parent_widget)
        self.refresh_shortcut2.activated.connect(self.refresh_all_pages)

    def refresh_all_pages(self) -> None:
        """Refresh all loaded pages"""
        logger.info("Manual refresh triggered")
        
        # Dashboard
        if hasattr(self, 'dashboard_page') and self.dashboard_page:
            if hasattr(self.dashboard_page, 'refresh_dashboard'):
                self.dashboard_page.refresh_dashboard()
        
        # Sales Summary
        if hasattr(self, 'sales_summary_page') and self.sales_summary_page:
            if hasattr(self.sales_summary_page, 'load_all_tabs'):
                self.sales_summary_page.load_all_tabs()
        
        # Products
        if hasattr(self, 'products_page') and self.products_page:
            if hasattr(self.products_page, 'load_products'):
                self.products_page.load_products()
            if hasattr(self.products_page, 'update_cards'):
                self.products_page.update_cards()
        
        # AI Pages
        if hasattr(self, 'ai_pages_page') and self.ai_pages_page:
            if hasattr(self.ai_pages_page, 'refresh'):
                self.ai_pages_page.refresh()
        
        # Inventory
        if hasattr(self, 'inventory_page') and self.inventory_page:
            if hasattr(self.inventory_page, 'refresh_all'):
                self.inventory_page.refresh_all()
        
        # Receipts
        if hasattr(self, 'receipts_page') and self.receipts_page:
            if hasattr(self.receipts_page, 'load_sales'):
                self.receipts_page.load_sales()
        
        # Sales
        if hasattr(self, 'sales_page') and self.sales_page:
            if hasattr(self.sales_page, 'product_grid') and hasattr(self.sales_page.product_grid, 'load_products'):
                self.sales_page.product_grid.load_products()
            if hasattr(self.sales_page, 'load_customers'):
                self.sales_page.load_customers()
            if hasattr(self.sales_page, 'load_payment_types'):
                self.sales_page.load_payment_types()
        
        # Customers
        if hasattr(self, 'customers_page') and self.customers_page:
            if hasattr(self.customers_page, 'load_customers'):
                self.customers_page.load_customers()
        
        # Expense
        if hasattr(self, 'expense_page') and self.expense_page:
            if hasattr(self.expense_page, 'load_expenses'):
                self.expense_page.load_expenses()
            if hasattr(self.expense_page, 'update_card_totals'):
                self.expense_page.update_card_totals()
        
        lang_code = lang.get_current()
        msg = "စာမျက်နှာအားလုံး ပြန်လည်စတင်ပြီးပါပြီ" if lang_code == "my" else "All pages refreshed"
        if self.status_bar:
            self.status_bar.showMessage(msg, 3000)
        
        # Check stock alerts after refresh
        self.check_stock_alerts()

    def check_stock_alerts(self) -> None:
        from models.database import connect_db
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM products 
            WHERE (sold_by IS NULL OR sold_by != 'Service') 
              AND stock > 0 AND stock <= low_stock
        """)
        low_count = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM products 
            WHERE (sold_by IS NULL OR sold_by != 'Service') 
              AND stock = 0
        """)
        out_count = cursor.fetchone()[0]
        conn.close()

        self.has_alerts = (low_count + out_count) > 0

        if self.has_alerts and self.notification_icon:
            self.notification_icon.show()
            if self.blink_timer and not self.blink_timer.isActive():
                self.blink_timer.start(500)
            
            lang_code = lang.get_current()
            if lang_code == "my":
                parts = []
                if low_count > 0:
                    parts.append(f"စတော့နည်းနေသောပစ္စည်း {low_count} မျိုး")
                if out_count > 0:
                    parts.append(f"ကုန်သွားသောပစ္စည်း {out_count} မျိုး")
                msg = "⚠️ " + "၊ ".join(parts) + " ရှိပါသည်။"
                popup_title = "စတော့သတိပေးချက်"
            else:
                parts = []
                if low_count > 0:
                    parts.append(f"{low_count} low stock product(s)")
                if out_count > 0:
                    parts.append(f"{out_count} out of stock product(s)")
                msg = "⚠️ " + ", ".join(parts) + "."
                popup_title = "Stock Alert"

            if self.status_bar:
                self.status_bar.showMessage(msg, 10000)

            if not hasattr(self, '_alert_shown') or not self._alert_shown:
                self._alert_shown = True
                QMessageBox.warning(self, popup_title, msg)
        else:
            if self.blink_timer:
                self.blink_timer.stop()
            if self.notification_icon:
                self.notification_icon.hide()
            if self.status_bar:
                self.status_bar.showMessage(tr("ok_stock"), 5000)
            self._alert_shown = False

    def toggle_notification_icon(self) -> None:
        if not self.has_alerts or not self.notification_icon:
            return
        if self.notification_icon.isVisible():
            self.notification_icon.hide()
        else:
            self.notification_icon.show()

    def show_notification_dialog(self, event) -> None:
        if self.has_alerts:
            from ui.stock_notification_dialog import StockNotificationDialog

            dialog = StockNotificationDialog(self)
            dialog.exec()
        else:
            QMessageBox.information(self, tr("info"), tr("ok_stock"))

    def show_expense_alert(self, alert_data: Dict[str, Any]) -> None:
        lang_code = lang.get_current()
        title = "ဘတ်ဂျက်သတိပေးချက်" if lang_code == "my" else "Budget Alert"
        QMessageBox.warning(self, title, alert_data['message'])

    def on_language_changed(self, lang_code: str) -> None:
        """Handle language change event"""
        logger.info(f"Language changed to: {lang_code}")
        if hasattr(self, 'current_language'):
            self.current_language = lang_code
        self.apply_language()
        
        # Update all loaded pages
        pages = [
            self.dashboard_page,
            self.sales_summary_page,
            self.products_page,
            self.ai_pages_page,
            self.inventory_page,
            self.receipts_page,
            self.sales_page,
            self.customers_page,
            self.expense_page
        ]
        
        for page in pages:
            if page and hasattr(page, 'retranslateUi'):
                try:
                    page.retranslateUi()
                except Exception as e:
                    logger.error(f"Error in retranslateUi for {page.__class__.__name__}: {e}")
        
        self.check_stock_alerts()

    def apply_language(self) -> None:
        """
        Apply language translations to all UI elements
        """
        from utils.translations import tr
        
        # Update menu texts
        self._update_menu_texts()
        
        # Update status bar
        if self.status_bar:
            lang_code = lang.get_current()
            msg = "ဘာသာပြန်ချက် အသစ်ပြန်လည်သတ်မှတ်ပြီးပါပြီ" if lang_code == "my" else "Language applied"
            self.status_bar.showMessage(msg, 3000)
        
        logger.info(f"Language applied: {lang.get_current()}")

    def _update_menu_texts(self) -> None:
        """
        Update all menu texts with translations
        """
        from utils.translations import tr
        
        # File Menu
        if hasattr(self, 'file_menu') and self.file_menu:
            self.file_menu.setTitle("File")
            if hasattr(self, 'refresh_action') and self.refresh_action:
                self.refresh_action.setText("Refresh")
            if hasattr(self, 'logout_action') and self.logout_action:
                self.logout_action.setText("Logout")
            if hasattr(self, 'exit_action') and self.exit_action:
                self.exit_action.setText("Exit")
        
        # View Menu
        if hasattr(self, 'view_menu') and self.view_menu:
            self.view_menu.setTitle("View")
            if hasattr(self, 'dashboard_menu_action') and self.dashboard_menu_action:
                self.dashboard_menu_action.setText("Dashboard")
            if hasattr(self, 'sales_summary_menu_action') and self.sales_summary_menu_action:
                self.sales_summary_menu_action.setText("Sales Summary")
        
        # Products Menu
        if hasattr(self, 'products_menu') and self.products_menu:
            self.products_menu.setTitle("Products")
            if hasattr(self, 'products_action') and self.products_action:
                self.products_action.setText("Products")
        
        # AI Pages Menu
        if hasattr(self, 'ai_pages_menu') and self.ai_pages_menu:
            self.ai_pages_menu.setTitle("Ai")
            if hasattr(self, 'ai_pages_action') and self.ai_pages_action:
                self.ai_pages_action.setText("Ai")
        
        # Inventory Menu
        if hasattr(self, 'inventory_menu') and self.inventory_menu:
            self.inventory_menu.setTitle("Inventory")
            if hasattr(self, 'current_stock_action') and self.current_stock_action:
                self.current_stock_action.setText("Current Stock")
            if hasattr(self, 'low_stock_alert_action') and self.low_stock_alert_action:
                self.low_stock_alert_action.setText("Low Stock Alert")
            if hasattr(self, 'supplier_menu_action') and self.supplier_menu_action:
                self.supplier_menu_action.setText("Supplier")
            if hasattr(self, 'purchase_history_menu_action') and self.purchase_history_menu_action:
                self.purchase_history_menu_action.setText("Purchase History")
            if hasattr(self, 'expiry_date_action') and self.expiry_date_action:
                self.expiry_date_action.setText("Expiry Date")
            if hasattr(self, 'inventory_logs_action') and self.inventory_logs_action:
                self.inventory_logs_action.setText("Inventory Logs")
            if hasattr(self, 'stock_by_location_action') and self.stock_by_location_action:
                self.stock_by_location_action.setText("Stock by Location")
        
        # Receipts Menu
        if hasattr(self, 'receipts_menu') and self.receipts_menu:
            self.receipts_menu.setTitle("Receipts")
            if hasattr(self, 'receipts_action') and self.receipts_action:
                self.receipts_action.setText("Receipts")
        
        # Customers Menu
        if hasattr(self, 'customers_menu') and self.customers_menu:
            self.customers_menu.setTitle("Customers")
            if hasattr(self, 'customers_action') and self.customers_action:
                self.customers_action.setText("Customers")
        
        # Credit Menu
        if hasattr(self, 'credit_menu') and self.credit_menu:
            self.credit_menu.setTitle("Credit")
            if hasattr(self, 'outstanding_report_action') and self.outstanding_report_action:
                self.outstanding_report_action.setText("Outstanding Report")
            if hasattr(self, 'role_management_action') and self.role_management_action:
                self.role_management_action.setText("Role Management")
        
        # Expense Menu
        if hasattr(self, 'expense_menu') and self.expense_menu:
            self.expense_menu.setTitle("Expense")
            if hasattr(self, 'expense_action') and self.expense_action:
                self.expense_action.setText("Expense")
            if hasattr(self, 'budget_settings_action') and self.budget_settings_action:
                self.budget_settings_action.setText("Budget Settings")
            if hasattr(self, 'expense_comparison_action') and self.expense_comparison_action:
                self.expense_comparison_action.setText("Expense Comparison")

        # Settings Menu
        if hasattr(self, 'settings_menu') and self.settings_menu:
            self.settings_menu.setTitle("Settings")
            if hasattr(self, 'general_settings_action') and self.general_settings_action:
                self.general_settings_action.setText("General Settings")
            if hasattr(self, 'receipt_settings_action') and self.receipt_settings_action:
                self.receipt_settings_action.setText("Receipt Settings")
            if hasattr(self, 'regional_settings_action') and self.regional_settings_action:
                self.regional_settings_action.setText("Regional Settings")
            if hasattr(self, 'update_settings_action') and self.update_settings_action:
                self.update_settings_action.setText("Update")
            if hasattr(self, 'telegram_settings_action') and self.telegram_settings_action:
                self.telegram_settings_action.setText("Telegram")
            if hasattr(self, 'youtube_settings_action') and self.youtube_settings_action:
                self.youtube_settings_action.setText("YouTube")
            if hasattr(self, 'performance_settings_action') and self.performance_settings_action:
                self.performance_settings_action.setText("Performance")
            if hasattr(self, 'backup_reset_settings_action') and self.backup_reset_settings_action:
                self.backup_reset_settings_action.setText("Backup & Reset")
            if hasattr(self, 'users_settings_action') and self.users_settings_action:
                self.users_settings_action.setText("Users")
        
        # Reports Menu
        if hasattr(self, 'reports_menu') and self.reports_menu:
            self.reports_menu.setTitle("Reports")
            if hasattr(self, 'sales_report_action') and self.sales_report_action:
                self.sales_report_action.setText("Sales Report")
            if hasattr(self, 'expense_report_action') and self.expense_report_action:
                self.expense_report_action.setText("Expense Report")
            if hasattr(self, 'profit_loss_report_action') and self.profit_loss_report_action:
                self.profit_loss_report_action.setText("Profit & Loss Report")
            if hasattr(self, 'profit_report_action') and self.profit_report_action:
                self.profit_report_action.setText("Profit Report")
            if hasattr(self, 'financial_summary_action') and self.financial_summary_action:
                self.financial_summary_action.setText("Financial Summary")
        
        # Tools Menu
        if hasattr(self, 'tools_menu') and self.tools_menu:
            self.tools_menu.setTitle("Tools")
            if hasattr(self, 'auto_backup_action') and self.auto_backup_action:
                self.auto_backup_action.setText("Auto Backup")
        
        # Themes Menu
        if hasattr(self, 'themes_menu') and self.themes_menu:
            self.themes_menu.setTitle("Themes")
            if hasattr(self, 'dark_theme_action') and self.dark_theme_action:
                self.dark_theme_action.setText("Dark")
            if hasattr(self, 'light_theme_action') and self.light_theme_action:
                self.light_theme_action.setText("Light")
            if hasattr(self, 'follow_system_theme_action') and self.follow_system_theme_action:
                self.follow_system_theme_action.setText("Follow System Theme")
        
        # Admin Menu
        if hasattr(self, 'admin_menu') and self.admin_menu:
            self.admin_menu.setTitle("Admin")
            if hasattr(self, 'activity_log_action') and self.activity_log_action:
                self.activity_log_action.setText("Activity Log")
        
        # Sidebar Buttons - Update with translations
        if hasattr(self, 'sidebar') and self.sidebar:
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
                    # Store text for when expanded
                    btn.setProperty("page_text", page_names[idx])
                    # Only update visible text if not collapsed
                    if not is_collapsed:
                        btn.setText(page_names[idx])
        
        # Page title
        if hasattr(self, 'page_title') and self.page_title:
            current_index = self.pages.currentIndex() if hasattr(self, 'pages') and self.pages else 5
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
            if current_index in page_names:
                self.page_title.setText(page_names[current_index])
