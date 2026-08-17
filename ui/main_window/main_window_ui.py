# ui/main_window/main_window_ui.py
"""
Main Window UI - Sajiwa POS Style with Lazy Loading
With SVG Icons from assets/icons
Collapsible Sidebar Support with QSplitter
Default state: Sidebar Expanded
"""

from typing import Optional, Dict, Any, Callable, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QStackedWidget, QStatusBar, QFrame, QSizePolicy, QApplication,
    QProgressBar, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont
from utils.translations import tr
from utils.permissions import PermissionManager
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager
from ui.lazy_loading_widget import LazyLoadingWidget
from ui.main_window.sidebar import Sidebar
from ui.main_window.header import Header
from ui.main_window.status_bar import StatusBar
from ui.widgets.loading_overlay import LoadingOverlay
from ui.responsive_utils import parse_resolution
from models.database import connect_db
from utils.sale_mode import get_sale_mode, is_sale_page_enabled
from utils.db_compat import is_postgres_backend
from loguru import logger


class MainWindowUI(QMainWindow):
    """Handle UI setup for MainWindow - Sajiwa POS Style with Lazy Loading"""
    
    # Declare attributes to fix Pylance errors
    current_user: Dict[str, Any]
    header: Optional[Header] = None
    sidebar: Optional[Sidebar] = None
    splitter: Optional[QSplitter] = None
    status_bar: Optional[StatusBar] = None
    pages: Optional[QStackedWidget] = None
    content_area: Optional[QWidget] = None
    page_header: Optional[QFrame] = None
    page_title: Optional[QLabel] = None
    loading_overlay: Optional[LoadingOverlay] = None
    _page_builders: Dict[int, Callable]
    _page_widgets: Dict[int, QWidget]
    _lazy_widgets: Dict[int, LazyLoadingWidget]
    _page_names: Dict[int, str]
    
    # Page references
    dashboard_page: Optional[Any] = None
    sales_summary_page: Optional[Any] = None
    products_page: Optional[Any] = None
    ai_pages_page: Optional[Any] = None
    inventory_page: Optional[Any] = None
    receipts_page: Optional[Any] = None
    sales_page: Optional[Any] = None
    restaurant_page: Optional[Any] = None
    customers_page: Optional[Any] = None
    expense_page: Optional[Any] = None
    discount_page: Optional[Any] = None
    employee_page: Optional[Any] = None
    
    def setup_ui(self) -> None:
        # Employee schema/role additions are idempotent and must exist before
        # permission-filtered sidebar/page construction.
        try:
            from services.employee_service import ensure_employee_schema
            ensure_employee_schema()
        except Exception as exc:
            logger.error(f"Employee module initialization failed: {exc}")
        # Get screen geometry for dynamic sizing
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
        else:
            screen_width = 1920
            screen_height = 1080
        
        preferred_width, preferred_height = self._load_saved_window_resolution()
        window_width = min(preferred_width, screen_width)
        window_height = min(preferred_height, screen_height)
        self.resize(window_width, window_height)
        if screen:
            x = screen_geometry.x() + max(0, (screen_width - window_width) // 2)
            y = screen_geometry.y() + max(0, (screen_height - window_height) // 2)
            self.move(x, y)
        self.setMinimumSize(min(1366, window_width), min(768, window_height))
        
        # Theme colors
        colors = get_theme_colors()
        
        # Main container
        central_widget = QWidget()
        central_widget.setObjectName("mainContainer")
        central_widget.setStyleSheet(f"""
            QWidget#mainContainer {{
                background-color: {colors['bg']};
            }}
        """)
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ============================================================
        # HEADER
        # ============================================================
        self.header = Header(self)
        main_layout.addWidget(self.header)
        
        # ============================================================
        # BODY - SPLITTER (Sidebar + Content)
        # ============================================================
        # Use QSplitter for dynamic sidebar resize
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(0)
        
        # --- Sidebar (default expanded) ---
        self.sidebar = Sidebar(self)
        self.splitter.addWidget(self.sidebar)
        
        # --- Content Area ---
        self.content_area = QWidget()
        self.content_area.setObjectName("mainContent")
        self.content_area.setStyleSheet(f"""
            QWidget#mainContent {{
                background-color: {colors['bg']};
            }}
        """)
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(24, 10, 24, 18)
        content_layout.setSpacing(8)
        
        # Page header is kept as a hidden compatibility object; page titles are
        # not shown so content gets more vertical room.
        self.page_header = QFrame()
        self.page_header.setObjectName("pageHeader")
        self.page_header.setFixedHeight(0)
        self.page_header.setStyleSheet("QFrame#pageHeader { background-color: transparent; }")
        page_header_layout = QHBoxLayout(self.page_header)
        page_header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.page_title = QLabel("Sales")
        self.page_title.setStyleSheet(f"""
            font-size: 15pt;
            font-weight: bold;
            color: {colors['text']};
            background: transparent;
        """)
        page_header_layout.addWidget(self.page_title)
        page_header_layout.addStretch()
        self.page_header.hide()
        content_layout.addWidget(self.page_header)
        
        # ============================================================
        # PAGES STACKED WIDGET
        # ============================================================
        self.pages = QStackedWidget()
        self.pages.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {colors['bg']};
                border-radius: 10px;
            }}
        """)
        
        # Page builders
        self._page_builders = {}
        self._page_widgets = {}
        self._lazy_widgets = {}
        self._page_names = {}
        
        # Define pages
        page_definitions = [
            (0, "Dashboard", self._build_dashboard_page, "dashboard"),
            (1, "Sales Summary", self._build_sales_summary_page, "sales_summary"),
            (2, "Products", self._build_products_page, "products"),
            (9, "Discounts", self._build_discount_page, "products"),
            (8, "AI Pages", self._build_ai_pages_page, "ai_pages"),
            (3, "Inventory", self._build_inventory_page, "inventory"),
            (4, "Receipts", self._build_receipts_page, "receipts"),
            (5, "Sales", self._build_sales_page, "sales"),
            (10, "Restaurant", self._build_restaurant_page, "sales"),
            (6, "Customers", self._build_customers_page, "customers"),
            (7, "Expense", self._build_expense_page, "expense"),
            (11, "Employees", self._build_employee_page, "employees"),
        ]
        
        for index, name, builder, perm in page_definitions:
            if PermissionManager.user_can_view_page(self.current_user["id"], perm):
                lazy_widget = LazyLoadingWidget(self.pages, load_delay=50)
                self.pages.addWidget(lazy_widget)
                self._lazy_widgets[index] = lazy_widget
                self._page_builders[index] = builder
                self._page_names[index] = name
        
        content_layout.addWidget(self.pages)
        
        self.splitter.addWidget(self.content_area)
        
        # ============================================================
        # 🔥 SET INITIAL SPLITTER SIZES - EXPANDED
        # ============================================================
        self.splitter.setSizes([Sidebar.WIDTH_EXPANDED, 99999])
        
        main_layout.addWidget(self.splitter)
        
        # ============================================================
        # STATUS BAR
        # ============================================================
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        self.loading_overlay = LoadingOverlay(central_widget)
        
        # ============================================================
        # Apply role permissions
        # ============================================================
        self.apply_role_permissions()
        
        # ============================================================
        # DEFAULT PAGE - Sales (index 5)
        # ============================================================
        self._initial_page_index = self._get_initial_page_index()
        if self._initial_page_index is not None:
            initial_widget = self._lazy_widgets.get(self._initial_page_index)
            if initial_widget and self.pages:
                self.pages.setCurrentWidget(initial_widget)
                self._update_sidebar_buttons(self._initial_page_index)
                self._update_page_title(self._initial_page_index)
        
        # Theme manager connection
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # ============================================================
        # 🔥 SIDEBAR COLLAPSE SIGNAL CONNECTION (ONLY ONCE)
        # ============================================================
        if self.sidebar:
            self.sidebar.collapse_state_changed.connect(self._on_sidebar_collapse_changed)
        
        logger.info("MainWindow UI setup complete - with Lazy Loading, SVG Icons, and QSplitter")
        logger.info("Sidebar default state: EXPANDED")

    def _get_initial_page_index(self) -> Optional[int]:
        """Choose the first page to show without forcing it to load during startup."""
        preferred = 10 if get_sale_mode() == "restaurant" else 5
        if preferred in self._lazy_widgets and is_sale_page_enabled(preferred):
            return preferred
        if 5 in self._lazy_widgets and is_sale_page_enabled(5):
            return 5
        if 10 in self._lazy_widgets and is_sale_page_enabled(10):
            return 10
        return next(iter(self._lazy_widgets), None)

    def load_initial_page(self) -> None:
        """Load the initial page after the main window is visible."""
        index = getattr(self, "_initial_page_index", None)
        if index is not None:
            self.switch_to_page(index)

    def show_loading(self, message: str = "Loading...", progress: Optional[int] = None) -> None:
        if self.status_bar:
            self.status_bar.begin_background_activity("main_loading", message)
        if self.loading_overlay:
            self.loading_overlay.show_loading(message, progress)

    def update_loading(self, message: Optional[str] = None, progress: Optional[int] = None) -> None:
        if message and self.status_bar:
            self.status_bar.begin_background_activity("main_loading", message)
        if self.loading_overlay:
            self.loading_overlay.update_loading(message, progress)

    def hide_loading(self) -> None:
        if self.loading_overlay:
            self.loading_overlay.hide_loading()
        if self.status_bar:
            self.status_bar.end_background_activity("main_loading")

    def _load_saved_window_resolution(self) -> tuple[int, int]:
        try:
            conn = connect_db()
            cursor = conn.cursor()
            if is_postgres_backend():
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES ('window_resolution', '1366x768')
                    ON CONFLICT (key) DO NOTHING
                """)
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES ('window_resolution', '1366x768')"
                )
            cursor.execute("SELECT value FROM settings WHERE key='window_resolution'")
            row = cursor.fetchone()
            conn.commit()
            conn.close()
            return parse_resolution(row[0] if row else "1366x768")
        except Exception as e:
            logger.warning(f"Could not load window resolution setting: {e}")
            return 1366, 768

    # ============================================================
    # 🔥 SIDEBAR COLLAPSE EVENT HANDLER
    # ============================================================
    def _on_sidebar_collapse_changed(self, is_collapsed: bool) -> None:
        """
        Handle sidebar collapse/expand - update splitter sizes
        Uses constants directly for reliable sizing
        """
        if self.splitter and self.sidebar:
            # Use constant values directly
            width = Sidebar.WIDTH_COLLAPSED if is_collapsed else Sidebar.WIDTH_EXPANDED
            self.splitter.setSizes([width, 99999])
            self.update()
            logger.debug(f"Splitter updated: sidebar_width={width}, is_collapsed={is_collapsed}")

    def _get_app_version(self) -> str:
        """Get application version"""
        try:
            from updater.version_manager import VersionManager
            version_manager = VersionManager()
            return version_manager.get_current_version()
        except Exception as e:
            logger.warning(f"Could not get app version: {e}")
            return "1.0.0"

    # ============================================================
    # PAGE BUILDERS
    # ============================================================
    
    def _build_dashboard_page(self) -> QWidget:
        from ui.dashboard.dashboard_page import DashboardPage
        return DashboardPage()
    
    def _build_sales_summary_page(self) -> QWidget:
        from ui.sales_summary import SalesSummaryPage
        return SalesSummaryPage()
    
    def _build_products_page(self) -> QWidget:
        from ui.products_page import ProductsPage
        page = ProductsPage(
            user_role=self.current_user["role"],
            user_id=self.current_user["id"]
        )
        page.categories_changed.connect(self.refresh_sales_categories)
        page.categories_changed.connect(self.refresh_current_stock_categories)
        return page

    def _build_discount_page(self) -> QWidget:
        from ui.discount_page import DiscountPage
        return DiscountPage()
    
    def _build_ai_pages_page(self) -> QWidget:
        """Build AI Pages page"""
        from ui.ai_pages import AIPagesPage
        return AIPagesPage(current_user=self.current_user)
    
    def _build_inventory_page(self) -> QWidget:
        from ui.inventory_page import InventoryPage
        return InventoryPage(self.current_user["role"])
    
    def _build_receipts_page(self) -> QWidget:
        from ui.receipts_page import ReceiptsPage
        return ReceiptsPage(
            user_id=self.current_user["id"],
            user_role=self.current_user["role"]
        )
    
    def _build_sales_page(self) -> QWidget:
        from ui.sales_page import SalesPage
        page = SalesPage(self.current_user)
        self.sales_page = page
        return page

    def _build_restaurant_page(self) -> QWidget:
        from ui.restaurant_page import RestaurantPage
        page = RestaurantPage()
        self.restaurant_page = page
        return page
    
    def _build_customers_page(self) -> QWidget:
        from ui.customer_page import CustomersPage
        return CustomersPage(self.current_user["role"])
    
    def _build_expense_page(self) -> QWidget:
        from ui.expense import ExpensePage
        return ExpensePage(user_role=self.current_user["role"])

    def _build_employee_page(self) -> QWidget:
        from ui.employee_page import EmployeeManagementPage
        return EmployeeManagementPage(self.current_user)

    # ============================================================
    # PAGE SWITCHING
    # ============================================================
    
    def switch_to_page(self, index: int) -> None:
        from PyQt6.QtWidgets import QMessageBox
        from utils.translations import tr
        
        allowed = self._get_allowed_pages_for_role(self.current_user["id"])
        if index not in allowed:
            QMessageBox.warning(self, tr("access_denied"), tr("permission_denied"))
            return
        
        lazy_widget = self._lazy_widgets.get(index)
        if not lazy_widget:
            logger.warning(f"Page {index} not found")
            return
        
        if lazy_widget.is_loaded():
            if self.pages:
                self.pages.setCurrentWidget(lazy_widget)
            self._update_sidebar_buttons(index)
            self._update_page_title(index)
            return
        
        if lazy_widget.is_loading():
            return
        
        builder = self._page_builders.get(index)
        if builder:
            if self.pages:
                self.pages.setCurrentWidget(lazy_widget)
            self._update_sidebar_buttons(index)
            self._update_page_title(index)
            
            lazy_widget.load_page(builder)
            
            def on_page_loaded(widget):
                self._page_widgets[index] = widget
                self._update_page_references(index, widget)
            
            lazy_widget.page_loaded.connect(on_page_loaded)
            logger.info(f"Started lazy loading page: {index} - {self._page_names.get(index, 'Unknown')}")
    
    def _update_sidebar_buttons(self, index: int) -> None:
        """Update sidebar button selection state"""
        if self.sidebar:
            for btn in self.sidebar.sidebar_buttons:
                page_idx = btn.property("page_index")
                btn.setChecked(page_idx == index)
    
    def _update_page_title(self, index: int) -> None:
        page_names = {
            0: "Dashboard",
            1: "Sales Summary",
            2: "Products",
            9: "Discounts",
            8: "AI Pages",
            3: "Inventory",
            4: "Receipts",
            5: "Sales",
            10: "Restaurant",
            6: "Customers",
            7: "Expense",
            11: "Employees",
        }
        if self.page_title:
            self.page_title.setText(page_names.get(index, ""))
    
    def _update_page_references(self, index: int, widget: QWidget) -> None:
        page_names = {
            0: "dashboard_page",
            1: "sales_summary_page",
            2: "products_page",
            9: "discount_page",
            8: "ai_pages_page",
            3: "inventory_page",
            4: "receipts_page",
            5: "sales_page",
            10: "restaurant_page",
            6: "customers_page",
            7: "expense_page",
            11: "employee_page",
        }
        attr_name = page_names.get(index)
        if attr_name:
            setattr(self, attr_name, widget)
            logger.info(f"Updated reference: {attr_name}")
    
    def _get_allowed_pages_for_role(self, user_id: int) -> List[int]:
        allowed = []
        sale_mode = get_sale_mode()
        page_permissions = {
            5: "sales",
            0: "dashboard",
            1: "sales_summary",
            2: "products",
            9: "products",
            8: "ai_pages",
            3: "inventory",
            4: "receipts",
            10: "sales",
            6: "customers",
            7: "expense",
            11: "employees",
        }
        for index, perm in page_permissions.items():
            if PermissionManager.user_can_view_page(user_id, perm) and is_sale_page_enabled(index, sale_mode):
                allowed.append(index)
        return allowed

    def switch_to_inventory_tab(self, tab_index: int) -> None:
        logger.info(f"Switching to inventory tab: {tab_index}")
        self.switch_to_page(3)
        
        def check_and_switch() -> None:
            if hasattr(self, 'inventory_page') and self.inventory_page:
                # Use getattr for safety
                if hasattr(self.inventory_page, 'tabs'):
                    tabs = getattr(self.inventory_page, 'tabs')
                    if 0 <= tab_index < tabs.count():
                        tabs.setCurrentIndex(tab_index)
                        tab_text = tabs.tabText(tab_index)
                        logger.info(f"Switched to inventory tab: {tab_index} - {tab_text}")
                        if self.status_bar:
                            self.status_bar.showMessage(f"Switched to: {tab_text}", 3000)
            else:
                QTimer.singleShot(100, check_and_switch)
        
        QTimer.singleShot(200, check_and_switch)

    def preload_page(self, index: int) -> None:
        if index not in self._lazy_widgets:
            return
        
        lazy_widget = self._lazy_widgets[index]
        if lazy_widget.is_loaded() or lazy_widget.is_loading():
            return
        
        builder = self._page_builders.get(index)
        if builder:
            logger.info(f"Preloading page: {index}")
            lazy_widget.load_page(builder)
            
            def on_preload_done(widget):
                self._page_widgets[index] = widget
                self._update_page_references(index, widget)
            
            lazy_widget.page_loaded.connect(on_preload_done)
    
    def preload_adjacent_pages(self, current_index: int) -> None:
        next_index = current_index + 1
        if next_index in self._lazy_widgets:
            self.preload_page(next_index)
        
        prev_index = current_index - 1
        if prev_index in self._lazy_widgets:
            self.preload_page(prev_index)

    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def refresh_sales_categories(self) -> None:
        if hasattr(self, 'sales_page') and self.sales_page:
            if hasattr(self.sales_page, 'refresh_categories'):
                getattr(self.sales_page, 'refresh_categories')()

    def refresh_current_stock_categories(self) -> None:
        if hasattr(self, 'inventory_page') and self.inventory_page:
            inventory = self.inventory_page
            if hasattr(inventory, 'current_stock_tab'):
                current_stock_tab = getattr(inventory, 'current_stock_tab')
                if hasattr(current_stock_tab, 'load_categories'):
                    current_stock_tab.load_categories()
                if hasattr(current_stock_tab, 'refresh'):
                    current_stock_tab.refresh()

    def apply_role_permissions(self) -> None:
        user_id = self.current_user["id"]
        allowed_pages = self._get_allowed_pages_for_role(user_id)
        
        if self.sidebar:
            for btn in self.sidebar.sidebar_buttons:
                page_idx = btn.property("page_index")
                btn.setVisible(page_idx in allowed_pages)

        current_index = None
        if self.pages:
            current_widget = self.pages.currentWidget()
            for page_index, lazy_widget in self._lazy_widgets.items():
                if lazy_widget is current_widget:
                    current_index = page_index
                    break
        if current_index is not None and current_index not in allowed_pages and allowed_pages:
            target_index = self._get_initial_page_index()
            if target_index in allowed_pages:
                self.switch_to_page(target_index)

    # ============================================================
    # THEME UPDATE
    # ============================================================
    
    def _on_theme_changed(self, theme_name: str) -> None:
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Update main container
        central_widget = self.centralWidget()
        if central_widget:
            central_widget.setStyleSheet(f"""
                QWidget#mainContainer {{
                    background-color: {colors['bg']};
                }}
            """)

        if self.content_area:
            self.content_area.setStyleSheet(f"""
                QWidget#mainContent {{
                    background-color: {colors['bg']};
                }}
            """)

        if self.page_header:
            self.page_header.setStyleSheet("""
                QFrame#pageHeader {
                    background-color: transparent;
                    border: none;
                }
            """)
        
        # Update header
        if self.header:
            self.header.update_theme(theme_name)
        
        # Update sidebar
        if self.sidebar:
            self.sidebar.update_theme(theme_name)
        
        # Update page title
        if self.page_title:
            self.page_title.setStyleSheet(f"""
                font-size: 15pt;
                font-weight: bold;
                color: {colors['text']};
                background: transparent;
            """)
        
        # Update pages stacked widget
        if self.pages:
            self.pages.setStyleSheet(f"""
                QStackedWidget {{
                    background-color: {colors['bg']};
                    border-radius: 10px;
                }}
            """)
        
        # Update status bar
        if self.status_bar:
            self.status_bar.update_theme(theme_name)
        
        # Update loaded pages only
        page_attrs = ['dashboard_page', 'sales_summary_page', 'products_page',
                  'ai_pages_page', 'inventory_page', 'receipts_page', 'sales_page',
                      'customers_page', 'expense_page', 'discount_page']
        
        for attr_name in page_attrs:
            page = getattr(self, attr_name, None)
            notify = getattr(self, '_notify_widget_theme_changed', None)
            if callable(notify):
                notify(page, theme_name, attr_name)
            elif page and hasattr(page, 'update_theme'):
                try:
                    page.update_theme()
                except Exception as e:
                    logger.error(f"Error updating theme for {attr_name}: {e}")
        
        self.update()
        logger.info(f"Theme updated in MainWindow UI: {theme_name}")

    def _update_menu_bar_clock_color(self, theme_name: Optional[str] = None) -> None:
        if not self.header or not hasattr(self.header, 'menu_bar_clock'):
            return

        colors = get_theme_colors(theme_name)
        self.header.menu_bar_clock.setStyleSheet(f"""
            QLabel {{
                color: {colors.get('text', '#212529')};
                font-size: 9pt;
                font-weight: 500;
                padding: 2px 0px;
                background-color: transparent;
                border: none;
            }}
        """)

    def on_theme_manager_changed(self, theme_name: str) -> None:
        self._on_theme_changed(theme_name)
