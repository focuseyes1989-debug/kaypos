# ui/cashier_window/cashier_ui.py
"""
Cashier Mode UI - 3 Column Layout
1. Product Grid | 2. Mobile Shopping Cart | 3. Widgets & Checkout
"""

from typing import Optional, Dict, Any, Callable

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QApplication, QSplitter, QComboBox, QSizePolicy,
    QPushButton, QMessageBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QShortcut, QKeySequence
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QSize

from ui.themes.theme_manager import get_theme_colors, theme_manager, is_dark_theme
from ui.sales_page.product_grid import ProductGrid
from ui.sales_page.cart_widget import CartWidget, load_cart_from_file, delete_cart_backup
from ui.sales_page.totals_widget import TotalsWidget
from ui.sales_page.payment_widget import PaymentWidget
from ui.sales_page.options_widget import OptionsWidget
from ui.sales_page.checkout_handler import CheckoutHandler
from ui.sales_page.checkout_handler.checkout_utils import open_cash_drawer
from ui import CustomerDisplayWindow
from ui.widgets.combo_box_widget import ComboBoxWidget
from ui.responsive_utils import (
    get_responsive_window_size,
    get_responsive_font_size,
    get_responsive_spacing,
    get_responsive_padding
)
from models.database import connect_db
from utils.language import lang
from utils.translations import tr
from loguru import logger

from ui.widgets.modern_button import ModernButton


class CashierUI(QMainWindow):
    """
    Cashier Mode Window - 3 Column Layout
    1. Product Grid | 2. Mobile Shopping Cart | 3. Widgets & Checkout
    """
    
    def __init__(self, current_user: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.current_user = current_user
        self.user_id = current_user["id"]
        self._on_closed_callback: Optional[Callable[[], None]] = None
        self._customer_display = None
        
        # Initialize attributes before UI setup
        self.product_grid: Any = None
        self.cart_widget: Any = None
        self.totals_widget: Any = None
        self.payment_widget: Any = None
        self.options_widget: Any = None
        self.checkout_handler: Any = None
        self.customer_combo: Any = None
        self.customer_label: Any = None
        self.btn_customer_display: Any = None
        self.btn_open_cashdrawer: Any = None
        self.btn_checkout: Any = None
        self.btn_expense: Any = None
        self.btn_clear_cart: Any = None
        self.btn_toggle_details: Any = None
        self.btn_add_expense: Any = None
        self.btn_receipts: Any = None
        self.btn_backup: Any = None
        self._receipts_dialog: Optional[QDialog] = None
        self._backup_worker: Any = None
        self._backup_progress_dialog: Any = None
        self.details_panel: Any = None
        self.details_layout: Any = None
        self._details_dialog: Any = None
        self._main_splitter: Any = None
        self._splitter_initialized = False
        self.cashier_shortcuts = []
        self._font_size = 10
        self._spacing = 8
        self._padding = 16
        
        # Tax and settings
        self.tax_enabled = False
        self.tax_rate = 0.0
        self.discount_enabled = False
        self.discount_type = "percentage"
        self.discount_default_value = 0.0
        self.shop_name = "ZAY POS"
        self.receipt_header_text = ""
        self.receipt_footer_text = ""
        self.show_customer_name = True
        
        # Window setup
        self.setWindowTitle("💰 Cashier Mode - ZAY POS")
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        
        # Screen size အလိုက် Window Size ချိန်ညှိခြင်း
        self._setup_responsive_window()
        
        # UI ကို စတင်တည်ဆောက်ခြင်း
        self._setup_ui()
        self.setup_shortcuts()
        
        # Load data (after UI is fully created)
        self._load_initial_data()
        
        # Restore cart from backup
        self._restore_cart()
        
        # Connect theme
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Connect language
        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
        
        logger.info(f"✅ Cashier Mode initialized for user: {current_user['username']}")
        logger.info(f"📐 Window size: {self.width()}x{self.height()}")
    
    def _setup_responsive_window(self) -> None:
        """Screen size အလိုက် Window size ကို အလိုအလျောက် သတ်မှတ်ခြင်း"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
        else:
            screen_width = 1920
            screen_height = 1080
        
        window_width, window_height = get_responsive_window_size(
            screen_width,
            screen_height,
            preferred_width=1366,
            preferred_height=768,
            min_width=1024,
            min_height=600,
        )
        
        self.resize(window_width, window_height)
        self.setMinimumSize(1024, 600)
    
    def set_on_closed_callback(self, callback: Callable[[], None]) -> None:
        """Window ပိတ်တဲ့အခါ ခေါ်ဆိုရန် callback သတ်မှတ်ခြင်း"""
        self._on_closed_callback = callback
    
    def _setup_ui(self):
        """Cashier UI ကို စတင်တည်ဆောက်ခြင်း - 3 Column Layout"""
        colors = get_theme_colors()
        window_width = self.width()
        
        # Responsive values
        self._font_size = get_responsive_font_size(window_width)
        self._spacing = get_responsive_spacing(window_width)
        self._padding = get_responsive_padding(window_width)
        
        # အဓိက container
        central_widget = QWidget()
        central_widget.setObjectName("cashierContainer")
        central_widget.setStyleSheet(f"""
            QWidget#cashierContainer {{
                background-color: {colors['bg']};
            }}
        """)
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ─── Main Content (3 Column Splitter) ──────────────────────────
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setHandleWidth(6)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setStyleSheet(f"""
            QSplitter {{
                background-color: {colors['bg']};
            }}
            QSplitter::handle {{
                background-color: {colors['border']};
                margin: {self._padding // 2}px 0px;
                border-radius: 3px;
            }}
            QSplitter::handle:hover {{
                background-color: {colors['border_hover']};
            }}
        """)
        
        # ─── Column 1: Product Grid ────────────────────────────────────
        product_grid_container = self._create_product_grid_column()
        self._main_splitter.addWidget(product_grid_container)
        
        # ─── Column 2: Mobile Shopping Cart ────────────────────────────
        sale_panel = self._create_sales_style_panel()
        self._main_splitter.addWidget(sale_panel)
        
        # ─── Column 3: Widgets & Checkout ─────────────────────────────
        product_grid_container.setMinimumWidth(520)
        sale_panel.setMinimumWidth(420)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 2)
        self._set_default_splitter_sizes()
        
        main_layout.addWidget(self._main_splitter, stretch=1)
        
        # ─── Status Bar ─────────────────────────────────────────────────
        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)
        
        # Connect signals
        self._connect_signals()

    def _set_default_splitter_sizes(self):
        """Set balanced initial column widths without fighting user resizing."""
        if self._splitter_initialized or not self._main_splitter:
            return

        total_width = max(self.width(), 1024)
        self._main_splitter.setSizes([
            int(total_width * 0.60),
            int(total_width * 0.40),
        ])
        self._splitter_initialized = True
    
    def _create_product_grid_column(self) -> QWidget:
        """Column 1: Product Grid with margin"""
        colors = get_theme_colors()
        
        container = QWidget()
        container.setObjectName("cashierProductColumn")
        container.setStyleSheet(f"""
            QWidget#cashierProductColumn {{
                background-color: {colors.get('bg', '#f8f9fa')};
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            6,
            6,
            self._padding // 2,
            self._padding // 2,
        )
        layout.setSpacing(self._spacing)
        
        self.product_grid = ProductGrid(self, use_modern_combos=True)

        # ProductGrid ရဲ့ default top padding ကြောင့် window title bar အောက်မှာ
        # အလွတ် background strip တစ်ခု ပေါ်နေတာကို ဖယ်ရှားပါ။ ဘေးနဲ့အောက်
        # margins တွေကို မပြောင်းဘဲ top margin ကိုပဲ 0 သတ်မှတ်ထားပါတယ်။
        product_grid_layout = self.product_grid.layout()
        if product_grid_layout is not None:
            margins = product_grid_layout.contentsMargins()
            product_grid_layout.setContentsMargins(
                margins.left(),
                0,
                margins.right(),
                margins.bottom(),
            )
        self._apply_cashier_product_grid_style()

        layout.addWidget(self.product_grid, stretch=1)
        
        return container

    def _apply_cashier_product_grid_style(self):
        """Keep the cashier product search row flush and compact."""
        if not self.product_grid:
            return
        colors = get_theme_colors()
        input_bg = colors.get('card_bg', '#ffffff')
        input_border = colors.get('input_border', colors.get('border', '#dee2e6'))
        focus = colors.get('input_focus', colors.get('border_hover', '#5865f2'))
        text = colors.get('text', '#212529')
        muted = colors.get('text_secondary', '#6c757d')
        control_style = f"""
            QLineEdit, QComboBox {{
                background-color: {input_bg};
                color: {text};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 24px;
                max-height: 24px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {focus};
            }}
            QLineEdit::placeholder {{
                color: {muted};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
                background: transparent;
            }}
        """
        for control in (
            self.product_grid.category_combo,
            self.product_grid.discount_filter_combo,
            self.product_grid.view_combo,
        ):
            control.setFixedHeight(36)
            if hasattr(control, "apply_theme"):
                control.apply_theme()
            else:
                control.setStyleSheet(control_style)
        if hasattr(self.product_grid, "search_widget"):
            self.product_grid.search_widget.setFixedHeight(36)
            self.product_grid.search_widget.setMinimumWidth(220)
            self.product_grid.search_widget.setMaximumWidth(16777215)
            self.product_grid.search_widget.apply_modern_style()
        self.product_grid.search_input.setFixedHeight(24)
    
    def _create_cart_column(self) -> QWidget:
        """Column 2: Mobile Shopping Cart"""
        colors = get_theme_colors()
        
        container = QWidget()
        container.setObjectName("cashierCartColumn")
        container.setStyleSheet(f"""
            QWidget#cashierCartColumn {{
                background-color: {colors['card_bg']};
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            self._padding // 2,
            self._padding,
            self._padding // 2,
            self._padding // 2,
        )
        layout.setSpacing(self._spacing)
        
        self.cart_widget = CartWidget(self)
        layout.addWidget(self.cart_widget, stretch=1)
        
        return container

    def _create_sales_style_panel(self) -> QWidget:
        """Right panel arranged like Sale Page: customer, cart, details, payment, checkout."""
        colors = get_theme_colors()

        container = QWidget()
        container.setObjectName("cashierSalePanel")
        container.setStyleSheet(f"""
            QWidget#cashierSalePanel {{
                background-color: {colors['card_bg']};
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        self._setup_customer_section()
        layout.addLayout(self.customer_layout)

        self.cart_widget = CartWidget(self)
        layout.addWidget(self.cart_widget, stretch=1)

        self.totals_widget = TotalsWidget(self)
        self._make_group_compact(self.totals_widget.discount_group, hide_title=True)
        self._make_group_compact(self.totals_widget.loyalty_group, hide_title=True)
        self._make_group_compact(self.totals_widget.totals_group, hide_title=True)
        self.options_widget = OptionsWidget(self)
        self.options_widget.hide_title = True
        self._make_group_compact(self.options_widget, hide_title=True)

        self.payment_widget = PaymentWidget(self)
        self._make_group_compact(self.payment_widget, hide_title=True)
        self.payment_widget._apply_received_input_style()

        self.checkout_handler = CheckoutHandler(self)

        # Four matching ModernButton controls.
        self.btn_toggle_details = ModernButton("Sale Details", ModernButton.SECONDARY)
        self.btn_toggle_details.set_icon("receipt_long", size=(15, 15))
        self.btn_toggle_details.setCheckable(False)
        self.btn_toggle_details.setAutoExclusive(False)
        self.btn_toggle_details.clicked.connect(self.open_sale_details_dialog)

        self.btn_add_expense = ModernButton("Add Expense", ModernButton.SECONDARY)
        self.btn_add_expense.set_icon("money", size=(15, 15))
        self.btn_add_expense.setCheckable(False)
        self.btn_add_expense.setAutoExclusive(False)
        self.btn_add_expense.setToolTip("Add Expense (Ctrl+E)")
        self.btn_add_expense.clicked.connect(self._open_expense_dialog)

        self.btn_customer_display = ModernButton("Customer Display", ModernButton.SECONDARY)
        self.btn_customer_display.set_icon("visibility", size=(15, 15))
        self.btn_customer_display.setCheckable(True)
        self.btn_customer_display.setAutoExclusive(False)
        self.btn_customer_display.setToolTip(tr("show_hide_customer_display"))
        self.btn_customer_display.clicked.connect(self._toggle_customer_display)

        self.btn_open_cashdrawer = ModernButton("Open CashDrawer", ModernButton.SECONDARY)
        self.btn_open_cashdrawer.set_icon("point_of_sale", size=(15, 15))
        self.btn_open_cashdrawer.setCheckable(False)
        self.btn_open_cashdrawer.setAutoExclusive(False)
        self.btn_open_cashdrawer.setToolTip("Open Cash Drawer / ငွေထုတ်စက်ဖွင့်ရန်")
        self.btn_open_cashdrawer.clicked.connect(self._open_cashdrawer)

        for button in (
            self.btn_toggle_details,
            self.btn_add_expense,
            self.btn_customer_display,
            self.btn_open_cashdrawer,
        ):
            button.set_dense(True)
            button.setFixedHeight(32)
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        detail_buttons_layout = QHBoxLayout()
        detail_buttons_layout.setContentsMargins(0, 0, 0, 0)
        detail_buttons_layout.setSpacing(6)
        detail_buttons_layout.addWidget(self.btn_toggle_details, 1)
        detail_buttons_layout.addWidget(self.btn_add_expense, 1)
        detail_buttons_layout.addWidget(self.btn_customer_display, 1)
        detail_buttons_layout.addWidget(self.btn_open_cashdrawer, 1)
        layout.addLayout(detail_buttons_layout)

        self.details_panel = QWidget()
        self.details_panel.setObjectName("cashierDetailsHiddenHolder")
        self.details_panel.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.details_panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.details_layout = QVBoxLayout(self.details_panel)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(5)
        self._hide_detail_widgets()

        self.btn_checkout = ModernButton(" Checkout", ModernButton.PRIMARY)
        self.btn_checkout.set_icon("payment", size=(24, 24))
        self.btn_checkout.setFixedHeight(100)
        self.btn_checkout.clicked.connect(self._checkout)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        action_layout.addWidget(self.payment_widget, 1)
        action_layout.addWidget(self.btn_checkout, 2)
        layout.addLayout(action_layout)

        return container

    def _detail_widgets(self):
        return [
            self.options_widget,
            self.totals_widget.discount_group,
            self.totals_widget.loyalty_group,
            self.totals_widget.totals_group,
        ]

    def _hide_detail_widgets(self):
        if self.details_layout is None:
            return
        self.details_panel.setFixedSize(0, 0)
        self.details_panel.move(-10000, -10000)
        self.details_panel.hide()
        for widget in self._detail_widgets():
            widget.setParent(self.details_panel)
            self.details_layout.addWidget(widget)
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            widget.setFixedSize(0, 0)
            widget.move(-10000, -10000)
            widget.hide()

    def open_sale_details_dialog(self):
        if self._details_dialog:
            self._details_dialog.raise_()
            self._details_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Sale Details")
        dialog.setModal(True)
        dialog.resize(420, 430)
        colors = get_theme_colors()
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
        """)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(12, 12, 12, 12)
        dialog_layout.setSpacing(8)
        for widget in self._detail_widgets():
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(16777215, 16777215)
            widget.setParent(dialog)
            widget.show()
            dialog_layout.addWidget(widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        dialog_layout.addWidget(buttons)

        def restore_details():
            self._details_dialog = None
            self._hide_detail_widgets()

        dialog.finished.connect(lambda _result: restore_details())
        self._details_dialog = dialog
        dialog.show()

    def _apply_details_button_style(self):
        """Refresh the four utility ModernButtons for the active theme."""
        for button in (
            self.btn_toggle_details,
            self.btn_add_expense,
            self.btn_customer_display,
            self.btn_open_cashdrawer,
        ):
            if button:
                button.update_theme()

    def _create_widgets_column(self) -> QWidget:
        """Column 3: Widgets & Checkout"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        container = QWidget()
        container.setObjectName("cashierCheckoutColumn")
        container.setStyleSheet(f"""
            QWidget#cashierCheckoutColumn {{
                background-color: {colors['card_bg']};
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            self._padding // 2,
            self._padding,
            self._padding,
            self._padding // 2,
        )
        layout.setSpacing(self._spacing)
        
        # ─── Customer Section ──────────────────────────────────────────
        self._setup_customer_section()
        layout.addLayout(self.customer_layout)
        layout.addSpacing(8)
        
        # ─── Options Widget ────────────────────────────────────────────
        self.options_widget = OptionsWidget(self)
        self._make_group_compact(self.options_widget, hide_title=True)
        layout.addWidget(self.options_widget)
        layout.addSpacing(6)
        
        # ─── Control Buttons: Customer Display & Cashdrawer ────────────
        control_container = self._create_control_buttons()
        layout.addWidget(control_container)
        layout.addSpacing(6)
        
        # ─── Totals Widget ─────────────────────────────────────────────
        self.totals_widget = TotalsWidget(self)
        self._make_group_compact(self.totals_widget.discount_group, hide_title=True)
        self._make_group_compact(self.totals_widget.loyalty_group, hide_title=True)
        self._make_group_compact(self.totals_widget.totals_group, hide_title=True)
        
        layout.addWidget(self.totals_widget.discount_group)
        layout.addSpacing(4)
        layout.addWidget(self.totals_widget.loyalty_group)
        layout.addSpacing(4)
        layout.addWidget(self.totals_widget.totals_group)
        layout.addSpacing(6)
        
        # ─── Payment Widget ────────────────────────────────────────────
        self.payment_widget = PaymentWidget(self)
        self._make_group_compact(self.payment_widget, hide_title=True)
        self.payment_widget._apply_received_input_style()
        layout.addWidget(self.payment_widget)
        layout.addSpacing(6)
        
        # ─── Checkout Handler ──────────────────────────────────────────
        self.checkout_handler = CheckoutHandler(self)
        
        # ─── Buttons: Checkout & Expense (4:1 ratio) ──────────────────
        from ui.widgets.modern_button import ModernButton
        
        # Button container (horizontal layout)
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        
        # ✅ Checkout Button (4 parts) - Theme-aware
        self.btn_checkout = ModernButton(" Checkout", ModernButton.PRIMARY)
        self.btn_checkout.set_icon("payment", size=(24, 24))
        self.btn_checkout.setFixedHeight(60)
        self.btn_checkout.clicked.connect(self._checkout)
        button_layout.addWidget(self.btn_checkout, 4)
        
        # ✅ Expense Button (1 part) - Theme-aware
        self.btn_expense = ModernButton("", ModernButton.SECONDARY)
        self.btn_expense.set_icon("money_off", size=(24, 24))
        self.btn_expense.setFixedHeight(60)
        self.btn_expense.clicked.connect(self._open_expense_dialog)
        button_layout.addWidget(self.btn_expense, 1)
        
        layout.addWidget(button_container)
        layout.addSpacing(0)
        
        return container
    
    def _create_control_buttons(self) -> QWidget:
        """Create control buttons container (Customer Display & Cashdrawer) - Theme-aware"""
        from ui.widgets.modern_button import ModernButton
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # ─── Show/Hide Customer Display Button ────────────────────────
        self.btn_customer_display = ModernButton("", ModernButton.PRIMARY)
        self.btn_customer_display.set_icon("visibility", size=(18, 18))
        self.btn_customer_display.setToolTip(tr("show_hide_customer_display"))
        self.btn_customer_display.setCheckable(True)
        self.btn_customer_display.setAutoExclusive(True)
        self.btn_customer_display.setFixedHeight(38)
        self.btn_customer_display.clicked.connect(self._toggle_customer_display)
        layout.addWidget(self.btn_customer_display, 1)
        
        # ─── Open Cashdrawer Button ────────────────────────────────────
        self.btn_open_cashdrawer = ModernButton("", ModernButton.SECONDARY)
        self.btn_open_cashdrawer.set_icon("point_of_sale", size=(20, 20))
        self.btn_open_cashdrawer.setToolTip("Open Cash Drawer / ငွေထုတ်စက်ဖွင့်ရန်")
        self.btn_open_cashdrawer.setFixedHeight(38)
        self.btn_open_cashdrawer.clicked.connect(self._open_cashdrawer)
        layout.addWidget(self.btn_open_cashdrawer, 1)
        
        return container
    
    def _setup_customer_section(self):
        """Setup customer section - Theme-aware SVG Icon"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        self.customer_layout = QHBoxLayout()
        self.customer_layout.setSpacing(4)
        self.customer_layout.setContentsMargins(0, 0, 0, 0)
        
        # 👤 SVG Icon - Theme-aware
        self.customer_icon = QLabel()
        icon_color = "#dcddde" if is_dark else "#495057"
        self._set_colored_svg_icon(self.customer_icon, "person", icon_color, 20, 20)
        self.customer_layout.addWidget(self.customer_icon)
        
        self.customer_combo = ComboBoxWidget("Customer")
        self.customer_combo.addItem("Walk-in", None)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_changed)
        self.customer_combo.setMinimumWidth(120)
        self.customer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_customer_combo_style()
        self.customer_layout.addWidget(self.customer_combo, 1)

        self.btn_receipts = ModernButton("Receipts", ModernButton.SECONDARY)
        self.btn_receipts.set_icon("receipt_long", size=(15, 15))
        self.btn_receipts.set_dense(True)
        self.btn_receipts.setCheckable(False)
        self.btn_receipts.setAutoExclusive(False)
        self.btn_receipts.setFixedHeight(32)
        self.btn_receipts.setMinimumWidth(92)
        self.btn_receipts.setToolTip("Open receipts and refunds")
        self.btn_receipts.clicked.connect(self._open_receipts_dialog)
        self.customer_layout.addWidget(self.btn_receipts)

        # Backup-only control for Cashier Mode. Restore and Factory Reset are
        # intentionally not exposed here. The heavy backup module is imported
        # only after the user clicks this button.
        self.btn_backup = ModernButton("Backup", ModernButton.SECONDARY)
        self.btn_backup.set_icon("backup", size=(15, 15))
        self.btn_backup.set_dense(True)
        self.btn_backup.setCheckable(False)
        self.btn_backup.setAutoExclusive(False)
        self.btn_backup.setFixedHeight(32)
        self.btn_backup.setToolTip("Backup database")
        self.btn_backup.clicked.connect(self._backup_database)
        self.customer_layout.addWidget(self.btn_backup)
    
    def _set_colored_svg_icon(self, label: QLabel, icon_name: str, color: str, width: int, height: int):
        """Set colored SVG icon to QLabel"""
        try:
            from ui.themes.theme_manager import get_icon_with_color
            icon = get_icon_with_color(icon_name, color, (width, height))
            if not icon.isNull():
                pixmap = icon.pixmap(width, height)
                label.setPixmap(pixmap)
                return
        except Exception as e:
            logger.debug(f"Could not load SVG icon {icon_name}: {e}")
        
        # Fallback: use emoji
        emoji_map = {
            "person": "👤",
            "visibility": "👁️",
            "visibility_off": "🚫",
            "payment": "💳",
            "money_off": "💰",
            "point_of_sale": "💳",
        }
        label.setText(emoji_map.get(icon_name, ""))
        label.setStyleSheet(f"font-size: {height}px; background: transparent; color: {color};")
    
    def _apply_customer_combo_style(self):
        """Apply theme-aware style to customer combo"""
        if hasattr(self.customer_combo, "apply_theme"):
            self.customer_combo.apply_theme()
            return

        is_dark = is_dark_theme()
        
        if is_dark:
            self.customer_combo.setStyleSheet("""
                QComboBox {
                    background-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 4px;
                    padding: 3px 6px;
                    color: #dcddde;
                    min-height: 22px;
                }
                QComboBox:focus {
                    border: 1px solid #5865f2;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                    background: transparent;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 4px solid #b9bbbe;
                    margin-right: 4px;
                }
                QComboBox QAbstractItemView {
                    background-color: #2f3136;
                    border: 1px solid #40444b;
                    border-radius: 4px;
                    color: #dcddde;
                    selection-background-color: #5865f2;
                    selection-color: white;
                    outline: none;
                    padding: 4px;
                }
                QComboBox QAbstractItemView::item {
                    background-color: transparent;
                    color: #dcddde;
                    padding: 6px 10px;
                    border: none;
                    border-radius: 2px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #40444b;
                    color: #dcddde;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #5865f2;
                    color: white;
                }
            """)
        else:
            self.customer_combo.setStyleSheet("""
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 3px 6px;
                    color: #212529;
                    min-height: 22px;
                }
                QComboBox:focus {
                    border: 1px solid #5865f2;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                    background: transparent;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 4px solid #4a4f55;
                    margin-right: 4px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    color: #212529;
                    selection-background-color: #5865f2;
                    selection-color: white;
                    outline: none;
                    padding: 4px;
                }
                QComboBox QAbstractItemView::item {
                    background-color: transparent;
                    color: #212529;
                    padding: 6px 10px;
                    border: none;
                    border-radius: 2px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #ebedef;
                    color: #212529;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #5865f2;
                    color: white;
                }
            """)
    
    def _make_group_compact(self, group, hide_title=False):
        """Make a group box compact and optionally hide title"""
        is_dark = is_dark_theme()
        
        if hasattr(group, 'setStyleSheet'):
            if hide_title:
                group.setStyleSheet("""
                    QGroupBox {
                        padding-top: 0px;
                        margin-top: 0px;
                        border: none;
                        background-color: transparent;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: -9999px;
                    }
                """)
            else:
                border_color = "#40444b" if is_dark else "#ced4da"
                text_color = "#b9bbbe" if is_dark else "#495057"
                bg_color = "#2f3136" if is_dark else "#ffffff"
                
                group.setStyleSheet(f"""
                    QGroupBox {{
                        font-weight: bold;
                        padding-top: 4px;
                        margin-top: 2px;
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        border-radius: 8px;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin;
                        left: 4px;
                        padding: 0 3px 0 3px;
                        background-color: {bg_color};
                        color: {text_color};
                    }}
                """)
            if hasattr(group, 'layout') and group.layout():
                group.layout().setSpacing(2)
                group.layout().setContentsMargins(4, 3, 4, 3)
    
    def _connect_signals(self):
        """Connect all signals"""
        self.product_grid.product_selected.connect(self.cart_widget.add_product)
        self.product_grid.service_selected.connect(self.cart_widget.add_service)
        self.product_grid.barcode_scanned.connect(self.cart_widget.add_product_by_barcode)
        
        self.cart_widget.cart_changed.connect(self._on_cart_changed)
        self.cart_widget.cart_changed.connect(self.payment_widget.update_change)
        
        self.totals_widget.grand_total_changed.connect(self.payment_widget.auto_set_payment)
        self.totals_widget.grand_total_changed.connect(self.cart_widget.update_grand_total)
        self.payment_widget.payment_amount_changed.connect(self.totals_widget.update_change_display)
        self.payment_widget.checkout_requested.connect(self._checkout)
        
        self.options_widget.payment_type_changed.connect(self.checkout_handler.on_payment_type_changed)
        
        self.cart_widget.cart_changed.connect(self._refresh_customer_display)
        self.totals_widget.grand_total_changed.connect(lambda _: self._refresh_customer_display())
        self.payment_widget.payment_amount_changed.connect(lambda _: self._refresh_customer_display())
        self.payment_widget.payment_combo.currentIndexChanged.connect(lambda _: self._refresh_customer_display())

    def setup_shortcuts(self):
        """Keyboard shortcuts for fast cashier-mode operation."""
        self.cashier_shortcuts = []

        self._add_shortcut("F2", self.product_grid.focus_search)
        self._add_shortcut("Ctrl+F", self.product_grid.focus_search)
        self._add_shortcut("F3", self.focus_customer)
        self._add_shortcut("F4", self.focus_payment_amount)
        self._add_shortcut("F6", self.focus_payment_type)
        self._add_shortcut("F7", self.toggle_discount)
        self._add_shortcut("F8", self.focus_discount)
        self._add_shortcut("F9", self.set_cash_sale)
        self._add_shortcut("F10", self.set_credit_sale)
        self._add_shortcut("F12", self._checkout)
        self._add_shortcut("Ctrl+Backspace", self._clear_cart)
        self._add_shortcut("Ctrl+Delete", self.remove_last_cart_item)
        self._add_shortcut("Ctrl+D", self._toggle_customer_display)
        self._add_shortcut("Ctrl+Shift+D", self._open_cashdrawer)
        self._add_shortcut("Ctrl+E", self._open_expense_dialog)
        self.update_shortcut_tooltips()

    def _add_shortcut(self, sequence, handler):
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(handler)
        self.cashier_shortcuts.append(shortcut)
        return shortcut

    def focus_customer(self):
        self.customer_combo.setFocus()
        self.customer_combo.showPopup()

    def focus_payment_amount(self):
        if not self.payment_widget.isEnabled():
            QApplication.beep()
            return
        self.payment_widget.payment_input.setFocus()
        self.payment_widget.payment_input.selectAll()

    def focus_payment_type(self):
        if not self.payment_widget.isEnabled():
            QApplication.beep()
            return
        self.payment_widget.payment_combo.setFocus()
        self.payment_widget.payment_combo.showPopup()

    def toggle_discount(self):
        checkbox = self.totals_widget.discount_checkbox
        if not checkbox.isEnabled():
            QApplication.beep()
            return
        checkbox.setChecked(not checkbox.isChecked())
        if checkbox.isChecked():
            self.focus_discount()
        else:
            self.product_grid.focus_search()

    def focus_discount(self):
        if not self.totals_widget.discount_checkbox.isEnabled():
            QApplication.beep()
            return
        self.totals_widget.discount_checkbox.setChecked(True)
        self.totals_widget.discount_input.setFocus()
        self.totals_widget.discount_input.selectAll()

    def set_cash_sale(self):
        self.options_widget.set_payment_type("Cash")
        self.payment_widget.setEnabled(True)
        self.focus_payment_amount()

    def set_credit_sale(self):
        if self.customer_combo.currentData() is None:
            QMessageBox.warning(self, tr("credit_sale"), tr("select_customer_for_credit"))
            self.focus_customer()
            return
        self.options_widget.set_payment_type("Credit")

    def remove_last_cart_item(self):
        if not self.cart_widget.cart:
            QApplication.beep()
            return
        self.cart_widget.remove_item(len(self.cart_widget.cart) - 1)
        self.product_grid.focus_search()

    def update_shortcut_tooltips(self):
        self.customer_combo.setToolTip(tr("select_customer_shortcut"))
        self.payment_widget.payment_input.setToolTip(tr("enter_received_shortcut"))
        self.payment_widget.payment_combo.setToolTip(tr("select_payment_type_shortcut"))
        self.totals_widget.discount_checkbox.setToolTip(tr("toggle_discount_shortcut"))
        self.totals_widget.discount_input.setToolTip(tr("edit_discount_shortcut"))
        self.options_widget.cash_radio.setToolTip(tr("cash_sale_shortcut"))
        self.options_widget.credit_radio.setToolTip(tr("credit_sale_shortcut"))
        self.btn_checkout.setToolTip(f"{tr('checkout_shortcut')} | Ctrl+E: Expense")
        self.cart_widget.clear_btn.setToolTip(tr("clear_cart_shortcut"))
        self.cart_widget.setToolTip(tr("remove_selected_cart_item_shortcut"))
        if self.btn_customer_display:
            display_tip = "Hide Customer Display" if self._customer_display else tr("show_hide_customer_display")
            self.btn_customer_display.setToolTip(f"{display_tip} (Ctrl+D)")
        if self.btn_open_cashdrawer:
            self.btn_open_cashdrawer.setToolTip("Open Cash Drawer (Ctrl+Shift+D)")
        if self.btn_add_expense:
            self.btn_add_expense.setToolTip("Add Expense (Ctrl+E)")
        if self.btn_receipts:
            self.btn_receipts.setToolTip("Open receipts and refunds")
    
    def _on_cart_changed(self):
        """Handle cart changes"""
        self.totals_widget.update_totals()
    
    def _clear_cart(self):
        """Clear cart"""
        if self.checkout_handler:
            self.checkout_handler.clear_cart()
    
    def _checkout(self):
        """Checkout"""
        if self.checkout_handler:
            self.checkout_handler.checkout()

    def _open_receipts_dialog(self):
        """Open the receipts page in a cashier-sized dialog."""
        if self._receipts_dialog is not None:
            self._receipts_dialog.show()
            self._receipts_dialog.raise_()
            self._receipts_dialog.activateWindow()
            return

        try:
            from ui.receipts_page.receipts_page import ReceiptsPage

            dialog = QDialog(self)
            dialog.setWindowTitle("Receipts")
            dialog.setModal(False)

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

            receipts_page = ReceiptsPage(
                user_id=self.user_id,
                user_role=self.current_user.get("role"),
                parent=dialog,
            )
            layout.addWidget(receipts_page, 1)

            close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close_buttons.rejected.connect(dialog.reject)
            layout.addWidget(close_buttons)

            screen = QApplication.primaryScreen()
            if screen:
                available = screen.availableGeometry()
                width = min(1180, max(900, available.width() - 48))
                height = min(680, max(580, available.height() - 48))
            else:
                width, height = 1180, 680

            dialog.resize(width, height)
            dialog.setMinimumSize(min(900, width), min(560, height))
            dialog.finished.connect(self._on_receipts_dialog_closed)

            self._receipts_dialog = dialog
            dialog.show()
        except Exception as exc:
            logger.error(f"Failed to open receipts dialog: {exc}")
            QMessageBox.critical(self, "Receipts Error", f"Could not open receipts page: {exc}")

    def _on_receipts_dialog_closed(self):
        self._receipts_dialog = None
        try:
            if self.product_grid:
                self.product_grid.load_products()
            self.load_customers()
        except Exception as exc:
            logger.debug(f"Could not refresh cashier data after receipts dialog closed: {exc}")
    
    def _backup_database(self):
        """Create a database-and-product-images backup without exposing restore/reset."""
        from datetime import datetime
        from PyQt6.QtWidgets import QFileDialog

        try:
            from ui.backup_reset_setting import BackupWorker, ProgressDialog

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"pos_backup_{timestamp}.zaybackup"
            title = "Database Backup သိမ်းရန်" if lang.get_current() == "my" else "Backup Database"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                title,
                default_name,
                "ZAY POS Backup (*.zaybackup);;Database Files (*.db)",
            )
            if not file_path:
                return

            self.btn_backup.setEnabled(False)
            progress_title = "Database Backup ပြုလုပ်နေသည်..." if lang.get_current() == "my" else "Backing up database..."
            self._backup_progress_dialog = ProgressDialog(progress_title, self)
            self._backup_progress_dialog.show()
            QApplication.processEvents()

            self._backup_worker = BackupWorker(file_path)
            self._backup_worker.progress.connect(self._on_backup_progress)
            self._backup_worker.finished.connect(self._on_backup_finished)
            self._backup_worker.start()
        except Exception as exc:
            if self.btn_backup:
                self.btn_backup.setEnabled(True)
            logger.error(f"Failed to start cashier backup: {exc}")
            QMessageBox.critical(self, "Backup Error", f"Could not start backup: {exc}")

    def _on_backup_progress(self, value: int, status: str):
        if self._backup_progress_dialog:
            self._backup_progress_dialog.update_progress(value, status)

    def _on_backup_finished(self, success: bool, result: str):
        if self._backup_progress_dialog:
            self._backup_progress_dialog.accept()
            self._backup_progress_dialog = None
        if self.btn_backup:
            self.btn_backup.setEnabled(True)

        if success:
            message = (
                f"Backup ဖိုင်ကို ဤနေရာတွင် သိမ်းဆည်းပြီးပါပြီ:\n{result}"
                if lang.get_current() == "my"
                else f"Backup saved to:\n{result}"
            )
            QMessageBox.information(self, "Backup Complete", message)
        else:
            QMessageBox.critical(self, "Backup Error", f"Backup failed: {result}")

        # Release the QThread after its finished signal has been handled.
        worker = self._backup_worker
        self._backup_worker = None
        if worker:
            worker.deleteLater()

    def _open_expense_dialog(self):
        """Open expense dialog"""
        try:
            from ui.expense_dialog import ExpenseDialog
            dialog = ExpenseDialog(parent=self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Failed to open expense dialog: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Could not open expense dialog: {e}")
    
    def _open_cashdrawer(self):
        """Open cash drawer and show a localized result message."""
        try:
            success = open_cash_drawer(self)
            if not success:
                return

            logger.info("Cash drawer opened from cashier button")
            message = (
                "ငွေထုတ်စက် ဖွင့်လိုက်ပါပြီ။"
                if self.get_lang() == "my"
                else "Cash drawer opened successfully."
            )
            QMessageBox.information(self, "Cash Drawer", message)
        except Exception as e:
            logger.error(f"Failed to open cash drawer: {e}")
            QMessageBox.warning(self, "Error", f"Could not open cash drawer: {e}")
    
    def get_lang(self):
        """Get current language"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    def _load_initial_data(self):
        """Load initial data"""
        self._load_settings()
        self._load_customers()
        self._load_receipt_settings()
        self._load_payment_types()
        self._load_loyalty_settings()
        # ProductGrid loads its first page during construction. Calling
        # load_products() again here duplicated the most expensive startup query.
    
    def _load_settings(self):
        """Load settings"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='tax_enabled'")
            res = cursor.fetchone()
            self.tax_enabled = res[0] == '1' if res else False
            cursor.execute("SELECT value FROM settings WHERE key='tax_rate'")
            res = cursor.fetchone()
            self.tax_rate = float(res[0]) if res else 0.0
            cursor.execute("SELECT value FROM settings WHERE key='discount_enabled'")
            res = cursor.fetchone()
            self.discount_enabled = res[0] == '1' if res else False
            cursor.execute("SELECT value FROM settings WHERE key='discount_type'")
            res = cursor.fetchone()
            self.discount_type = res[0] if res else "percentage"
            cursor.execute("SELECT value FROM settings WHERE key='discount_value'")
            res = cursor.fetchone()
            self.discount_default_value = float(res[0]) if res else 0.0
            conn.close()
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
        if self.totals_widget:
            self.totals_widget.load_discount_settings(
                self.discount_enabled, self.discount_type, self.discount_default_value
            )
    
    def _load_loyalty_settings(self):
        """Load loyalty settings"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='loyalty_points_per_dollar'")
            row = cursor.fetchone()
            points_per_dollar = float(row[0]) if row else 0.0
            cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
            row = cursor.fetchone()
            expiry_months = int(row[0]) if row else 12
            cursor.execute("SELECT value FROM settings WHERE key='points_dollar_value'")
            row = cursor.fetchone()
            point_value = float(row[0]) if row else 0.01
            conn.close()
            if self.totals_widget:
                self.totals_widget.set_loyalty_params(points_per_dollar, expiry_months, point_value)
        except Exception as e:
            logger.error(f"Failed to load loyalty settings: {e}")
    
    def _load_customers(self):
        """Load customers"""
        from utils.customer_utils import load_customers
        
        if self.customer_combo:
            self.customer_combo.blockSignals(True)
            self.customer_combo.clear()
            self.customer_combo.addItem(tr("walk_in_customer"), None)
            customers = load_customers()
            for cust_id, name, points in customers:
                self.customer_combo.addItem(f"{name} (Points: {points})", cust_id)
            self.customer_combo.blockSignals(False)
    
    def load_customers(self):
        """Load customers - Called by CheckoutHandler"""
        from utils.customer_utils import load_customers
        
        if self.customer_combo:
            self.customer_combo.blockSignals(True)
            self.customer_combo.clear()
            self.customer_combo.addItem(tr("walk_in_customer"), None)
            customers = load_customers()
            for cust_id, name, points in customers:
                self.customer_combo.addItem(f"{name} (Points: {points})", cust_id)
            self.customer_combo.blockSignals(False)
    
    def _load_receipt_settings(self):
        """Load receipt settings"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='shop_name'")
            row = cursor.fetchone()
            self.shop_name = row[0] if row else "ZAY POS"
            cursor.execute("SELECT value FROM settings WHERE key='receipt_header'")
            row = cursor.fetchone()
            self.receipt_header_text = row[0] if row else ""
            cursor.execute("SELECT value FROM settings WHERE key='receipt_footer'")
            row = cursor.fetchone()
            self.receipt_footer_text = row[0] if row else ""
            cursor.execute("SELECT value FROM settings WHERE key='show_customer_name'")
            row = cursor.fetchone()
            self.show_customer_name = (row[0] == '1') if row else True
            conn.close()
        except Exception as e:
            logger.error(f"Failed to load receipt settings: {e}")
    
    def _load_payment_types(self):
        """Load payment types"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM payment_types ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
            types = [row[0] for row in rows] if rows else ["Cash", "Card", "Mobile Money"]
            if self.payment_widget:
                self.payment_widget.load_payment_types(types)
        except Exception as e:
            logger.error(f"Failed to load payment types: {e}")
            if self.payment_widget:
                self.payment_widget.load_payment_types(["Cash", "Card", "Mobile Money"])
    
    def _restore_cart(self):
        """Restore cart from backup"""
        restored_cart = load_cart_from_file()
        if restored_cart and self.cart_widget:
            conn = connect_db()
            cursor = conn.cursor()
            valid_items = []
            for item in restored_cart:
                cursor.execute("SELECT name, price, stock, sold_by FROM products WHERE id=?", (item['id'],))
                row = cursor.fetchone()
                if row:
                    db_name, db_price, db_stock, sold_by = row
                    item['name'] = db_name
                    item['original_price'] = float(db_price or 0)
                    discount_percent = float(item.get('expiry_discount_percent') or item.get('promo_discount_percent') or 0)
                    if discount_percent > 0:
                        item['price'] = max(0.0, item['original_price'] * (1 - min(discount_percent, 100) / 100.0))
                    else:
                        item['price'] = db_price
                    if not item.get('is_service', False) and db_stock < item['qty']:
                        item['qty'] = db_stock
                    valid_items.append(item)
            conn.close()
            if valid_items:
                self.cart_widget.cart = valid_items
                self.cart_widget.refresh_table()
                logger.info(f"Restored cart with {len(valid_items)} items from backup")
            else:
                delete_cart_backup()
    
    def _on_customer_changed(self):
        """Handle customer change"""
        if self.customer_combo and self.checkout_handler:
            data = self.customer_combo.currentData()
            self.checkout_handler.selected_customer_id = data if data is not None else None
            self.checkout_handler.load_customer_points()
            self.checkout_handler.load_customer_credit_balance()
            if self.totals_widget:
                self.totals_widget.update_totals()
            self._refresh_customer_display()
    
    def _toggle_customer_display(self):
        """Toggle customer display"""
        if self._customer_display is None:
            self._customer_display = CustomerDisplayWindow(self)
            self._customer_display.show()
            if self.btn_customer_display:
                self.btn_customer_display.setChecked(True)
                self.btn_customer_display.setToolTip("Hide Customer Display")
                self.btn_customer_display.set_icon("visibility_off", size=(18, 18))
            self._customer_display.destroyed.connect(self._on_customer_display_closed)
            self._show_customer_display_message(True)
        else:
            self._customer_display.close()
            self._customer_display = None
            if self.btn_customer_display:
                self.btn_customer_display.setChecked(False)
                self.btn_customer_display.setToolTip("Show Customer Display")
                self.btn_customer_display.set_icon("visibility", size=(18, 18))
            self._show_customer_display_message(False)

    def _show_customer_display_message(self, enabled):
        """Show user feedback after customer display is toggled."""
        if lang.get_current() == "my":
            message = "Customer Display ဖွင့်ပြီးပါပြီ။" if enabled else "Customer Display ပိတ်ပြီးပါပြီ။"
        else:
            message = "Customer Display is on." if enabled else "Customer Display is off."
        QMessageBox.information(self, "Customer Display", message)
    
    def _on_customer_display_closed(self):
        """Handle customer display closed"""
        self._customer_display = None
        if self.btn_customer_display:
            self.btn_customer_display.setChecked(False)
            self.btn_customer_display.setToolTip("Show Customer Display")
            self.btn_customer_display.set_icon("visibility", size=(18, 18))
    
    def _refresh_customer_display(self):
        """Refresh customer display"""
        if self._customer_display:
            self._customer_display.refresh_display()
    
    def _create_status_bar(self):
        """အောက်ခြေ Status Bar ကို ဖန်တီးခြင်း - Theme-aware"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        status_bar = QFrame()
        status_bar.setFixedHeight(32)
        status_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {colors['card_bg']};
                border: none;  /* ← border အားလုံးကို ဖယ်ရှားခြင်း */
            }}
        """)
        
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(16, 2, 16, 2)
        
        # 👤 SVG Icon - Theme-aware
        user_icon = QLabel()
        icon_color = "#dcddde" if is_dark else "#495057"
        self._set_colored_svg_icon(user_icon, "person", icon_color, 16, 16)
        layout.addWidget(user_icon)
        
        user_label = QLabel(f" {self.current_user.get('username', 'User')}")
        user_label.setStyleSheet(f"""
            font-size: {self._font_size - 1}pt;
            color: {colors['text_secondary']};
            background: transparent;
            border: none;  /* ← label အတွက် border ဖယ်ရှားခြင်း */
        """)
        layout.addWidget(user_label)
        layout.addStretch()

        shortcut_hint = QLabel("F2 Search | F3 Customer | F4 Received | F12 Checkout")
        shortcut_hint.setStyleSheet(f"""
            font-size: {self._font_size - 2}pt;
            color: {colors['text_secondary']};
            background: transparent;
            border: none;  /* ← label အတွက် border ဖယ်ရှားခြင်း */
        """)
        layout.addWidget(shortcut_hint)
        
        status_label = QLabel("✅ Ready")
        status_label.setStyleSheet(f"""
            font-size: {self._font_size - 1}pt;
            color: {colors['text_secondary']};
            background: transparent;
            border: none;  /* ← label အတွက် border ဖယ်ရှားခြင်း */
        """)
        layout.addWidget(status_label)
        
        return status_bar
    
    def _update_icon_colors(self):
        """Update all icon colors based on current theme"""
        is_dark = is_dark_theme()
        icon_color = "#dcddde" if is_dark else "#495057"
        
        # Update customer icon
        if hasattr(self, 'customer_icon') and self.customer_icon:
            self._set_colored_svg_icon(self.customer_icon, "person", icon_color, 20, 20)
        
        # Update status bar user icon
        status_bar = self.findChild(QFrame, "status_bar")
        if status_bar:
            for child in status_bar.findChildren(QLabel):
                if child.text() == "" and child.pixmap() is not None:
                    # This is the user icon
                    self._set_colored_svg_icon(child, "person", icon_color, 16, 16)
                    break
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme change"""
        colors = get_theme_colors()
        
        central = self.centralWidget()
        if central:
            central.setStyleSheet(f"""
                QWidget#cashierContainer {{
                    background-color: {colors['bg']};
                }}
            """)
        
        self._apply_customer_combo_style()
        self._update_icon_colors()
        
        if hasattr(self, 'product_grid') and self.product_grid:
            self.product_grid.update_theme()
            self._apply_cashier_product_grid_style()
        
        if hasattr(self, 'cart_widget') and self.cart_widget:
            self.cart_widget.update_theme()
        
        if self._customer_display and hasattr(self._customer_display, 'apply_theme_style'):
            self._customer_display.apply_theme_style()
        
        # ✅ Update buttons theme
        if hasattr(self, 'btn_toggle_details') and self.btn_toggle_details:
            self.btn_toggle_details.update_theme()
        if hasattr(self, 'btn_add_expense') and self.btn_add_expense:
            self.btn_add_expense.update_theme()
        if hasattr(self, 'btn_expense') and self.btn_expense:
            self.btn_expense.update_theme()
        if hasattr(self, 'btn_customer_display') and self.btn_customer_display:
            self.btn_customer_display.update_theme()
        if hasattr(self, 'btn_open_cashdrawer') and self.btn_open_cashdrawer:
            self.btn_open_cashdrawer.update_theme()
        if hasattr(self, 'btn_checkout') and self.btn_checkout:
            self.btn_checkout.update_theme()
        if hasattr(self, 'btn_receipts') and self.btn_receipts:
            self.btn_receipts.update_theme()
        if hasattr(self, 'btn_backup') and self.btn_backup:
            self.btn_backup.update_theme()
        self._apply_details_button_style()
        
        logger.info(f"Cashier mode theme updated: {theme_name}")
    
    def resizeEvent(self, event):
        """Handle resize event"""
        super().resizeEvent(event)

    def showEvent(self, event):
        """Ensure dialog-only detail widgets never paint over the cashier surface."""
        super().showEvent(event)
        if self.details_panel and not self._details_dialog:
            QTimer.singleShot(0, self._hide_detail_widgets)
    
    def retranslateUi(self):
        """Update UI language"""
        if lang.get_current() == "my":
            self.setWindowTitle("💰 ငွေကိုင်မုဒ် - ZAY POS")
            if hasattr(self, 'cart_widget') and self.cart_widget:
                self.cart_widget.retranslateUi()
            if hasattr(self, 'btn_checkout'):
                self.btn_checkout.setText(" ငွေရှင်းမည်")
            if self.btn_toggle_details:
                self.btn_toggle_details.setText("Sale Details")
            if self.btn_add_expense:
                self.btn_add_expense.setText("Add Expense")
                self.btn_add_expense.setToolTip("အသုံးစရိတ်ထည့်ရန် (Ctrl+E)")
            if self.btn_customer_display:
                self.btn_customer_display.setText("Customer Display")
                if self._customer_display is not None:
                    self.btn_customer_display.setToolTip("Customer Display ပိတ်ရန်")
                else:
                    self.btn_customer_display.setToolTip("Customer Display ဖွင့်ရန်")
            if self.btn_open_cashdrawer:
                self.btn_open_cashdrawer.setText("Open CashDrawer")
                self.btn_open_cashdrawer.setToolTip("ငွေထုတ်စက်ဖွင့်ရန် (Ctrl+Shift+D)")
            if self.btn_receipts:
                self.btn_receipts.setText("Receipts")
                self.btn_receipts.setToolTip("Receipts and refunds")
            if self.btn_backup:
                self.btn_backup.setText("Backup")
                self.btn_backup.setToolTip("Database Backup ပြုလုပ်ရန်")
        else:
            self.setWindowTitle("💰 Cashier Mode - ZAY POS")
            if hasattr(self, 'cart_widget') and self.cart_widget:
                self.cart_widget.retranslateUi()
            if hasattr(self, 'btn_checkout'):
                self.btn_checkout.setText(" Checkout")
            if self.btn_toggle_details:
                self.btn_toggle_details.setText("Sale Details")
            if self.btn_add_expense:
                self.btn_add_expense.setText("Add Expense")
                self.btn_add_expense.setToolTip("Add Expense (Ctrl+E)")
            if self.btn_customer_display:
                self.btn_customer_display.setText("Customer Display")
                if self._customer_display is not None:
                    self.btn_customer_display.setToolTip("Hide Customer Display (Ctrl+D)")
                else:
                    self.btn_customer_display.setToolTip("Show Customer Display (Ctrl+D)")
            if self.btn_open_cashdrawer:
                self.btn_open_cashdrawer.setText("Open CashDrawer")
                self.btn_open_cashdrawer.setToolTip("Open Cash Drawer (Ctrl+Shift+D)")
            if self.btn_receipts:
                self.btn_receipts.setText("Receipts")
                self.btn_receipts.setToolTip("Receipts and refunds")
            if self.btn_backup:
                self.btn_backup.setText("Backup")
                self.btn_backup.setToolTip("Backup database")
        
        if hasattr(self, 'product_grid') and self.product_grid:
            self.product_grid.retranslateUi()
        if hasattr(self, 'totals_widget') and self.totals_widget:
            self.totals_widget.retranslateUi()
        if hasattr(self, 'payment_widget') and self.payment_widget:
            self.payment_widget.retranslateUi()
        if hasattr(self, 'options_widget') and self.options_widget:
            self.options_widget.retranslateUi()
        if hasattr(self, 'cashier_shortcuts') and self.cashier_shortcuts:
            self.update_shortcut_tooltips()
    
    def closeEvent(self, event):
        """Handle close event - Call callback before closing"""
        if self._backup_worker and self._backup_worker.isRunning():
            QMessageBox.warning(self, "Backup in progress", "Please wait until the backup is complete.")
            event.ignore()
            return
        if self._customer_display:
            self._customer_display.close()
            self._customer_display = None
        if self._receipts_dialog:
            self._receipts_dialog.close()
            self._receipts_dialog = None
        
        logger.info("Cashier Mode closing...")
        
        if self._on_closed_callback is not None:
            try:
                self._on_closed_callback()
            except Exception as e:
                logger.error(f"Error calling closed callback: {e}")
        
        event.accept()
