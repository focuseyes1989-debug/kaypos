from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from loguru import logger

from models.database import connect_db
from ui.sales_page.cart_widget import CartWidget
from ui.sales_page.checkout_handler import CheckoutHandler
from ui.sales_page.options_widget import OptionsWidget
from ui.sales_page.payment_widget import PaymentWidget
from ui.sales_page.product_grid import ProductGrid
from ui.sales_page.totals_widget import TotalsWidget
from ui.themes import get_theme_colors, is_dark_theme, theme_manager
from ui.widgets.modern_button import ModernButton
from utils.currency import format_money, get_currency_symbol
from utils.customer_utils import load_customers
from utils.restaurant_service import (
    cancel_kitchen_ticket_item,
    close_order,
    ensure_default_tables,
    build_kitchen_ticket_lines,
    get_kitchen_ticket,
    get_open_order_for_table,
    get_order,
    get_restaurant_setting,
    list_kitchen_tickets,
    list_open_takeaway_orders,
    list_tables_with_status,
    mark_kitchen_ticket_printed,
    send_to_kitchen,
    update_kitchen_ticket_item_status,
    update_kitchen_ticket_status,
    upsert_order,
)
from utils.restaurant_modifiers import get_product_restaurant_modifiers
from utils.translations import tr


class RestaurantPage(QWidget):
    """Restaurant table/order workflow built on the existing POS checkout engine."""

    def __init__(self):
        super().__init__()
        self.setObjectName("restaurantPage")

        self.current_table_id = None
        self.current_table_name = ""
        self.current_order_id = None
        self.order_type = "Dine-in"
        self._loading_order = False
        self._loading_tables = False
        self._table_buttons = {}
        self._details_dialog = None
        self._kitchen_dialog = None
        self.kitchen_list = None
        self.btn_refresh_kitchen = None

        self.shop_name = "ZAY POS"
        self.receipt_header_text = ""
        self.receipt_footer_text = ""
        self.show_customer_name = True

        ensure_default_tables()

        self.product_grid = ProductGrid(self)
        self.cart_widget = CartWidget(self)
        self.totals_widget = TotalsWidget(self)
        self.payment_widget = PaymentWidget(self)
        self.options_widget = OptionsWidget(self)
        self.options_widget.hide()
        self.options_widget.setFixedSize(0, 0)
        self.options_widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.checkout_handler = CheckoutHandler(self)
        self._prepare_product_grid_for_restaurant()

        self.product_grid.product_selected.connect(self.add_menu_product)
        self.product_grid.service_selected.connect(self.cart_widget.add_service)
        self.product_grid.barcode_scanned.connect(self.cart_widget.add_product_by_barcode)
        self.cart_widget.cart_changed.connect(self._on_cart_changed)
        self.cart_widget.cart_changed.connect(self.payment_widget.update_change)
        self.totals_widget.grand_total_changed.connect(self.payment_widget.auto_set_payment)
        self.totals_widget.grand_total_changed.connect(self.cart_widget.update_grand_total)
        self.payment_widget.payment_amount_changed.connect(self.totals_widget.update_change_display)
        self.payment_widget.checkout_requested.connect(self.settle_bill)
        self.options_widget.payment_type_changed.connect(self.checkout_handler.on_payment_type_changed)

        self._build_ui()
        self.load_customers()
        self.load_payment_types()
        self.load_loyalty_settings()
        self.product_grid.load_products()
        self.refresh_tables()
        self.refresh_takeaway_orders()
        self.update_theme()
        theme_manager.theme_changed.connect(lambda _theme: self.update_theme())

    def should_auto_open_kitchen_preview(self):
        return str(get_restaurant_setting("restaurant_auto_kitchen_preview", "1")) == "1"

    def _prepare_product_grid_for_restaurant(self):
        """Keep menu picking compact inside Restaurant Mode."""
        grid_layout = self.product_grid.layout()
        if grid_layout:
            grid_layout.setSpacing(5)
        category_combo = getattr(self.product_grid, "category_combo", None)
        if category_combo:
            category_combo.show()
            category_combo.setFixedWidth(180)
            category_combo.setMinimumHeight(32)

        for widget_name in ("discount_filter_combo", "view_label", "view_combo"):
            widget = getattr(self.product_grid, widget_name, None)
            if widget:
                widget.hide()
                widget.setFixedSize(0, 0)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 4)
        root.setSpacing(6)

        root.addWidget(self.product_grid, 3)
        root.addWidget(self._build_order_panel(), 2)

    def _build_order_panel(self):
        panel = QFrame()
        panel.setObjectName("restaurantOrderPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        self.order_title = QLabel("Select a table")
        self.order_title.setObjectName("restaurantOrderTitle")
        title_row.addWidget(self.order_title, 1)

        self.table_count_label = QLabel("Table 0")
        self.table_count_label.setObjectName("restaurantCountBadge")
        self.table_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(self.table_count_label)

        self.takeaway_count_label = QLabel("Takeaway 0")
        self.takeaway_count_label.setObjectName("restaurantCountBadge")
        self.takeaway_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(self.takeaway_count_label)

        layout.addLayout(title_row)

        selector_row = QHBoxLayout()
        selector_row.setContentsMargins(0, 0, 0, 0)
        selector_row.setSpacing(8)

        self.customer_combo = QComboBox()
        self.customer_combo.currentIndexChanged.connect(self.on_customer_changed)
        self.customer_combo.setMinimumHeight(34)
        selector_row.addWidget(self.customer_combo, 1)

        self.order_type_combo = QComboBox()
        self.order_type_combo.addItem("Dine-in", "Dine-in")
        self.order_type_combo.addItem("Takeaway", "Takeaway")
        self.order_type_combo.setMinimumHeight(34)
        self.order_type_combo.currentIndexChanged.connect(self._on_order_type_changed)
        selector_row.addWidget(self.order_type_combo)

        self.table_combo = QComboBox()
        self.table_combo.setMinimumHeight(34)
        self.table_combo.currentIndexChanged.connect(self._on_table_combo_changed)
        selector_row.addWidget(self.table_combo, 1)

        self.btn_new_takeaway = ModernButton("New", ModernButton.SECONDARY)
        self.btn_new_takeaway.set_text_only(True)
        self.btn_new_takeaway.setFixedWidth(70)
        self.btn_new_takeaway.clicked.connect(self.new_takeaway_order)
        self.btn_new_takeaway.hide()
        selector_row.addWidget(self.btn_new_takeaway)
        self._sync_selector_control_heights()
        layout.addLayout(selector_row)

        self.btn_dine_in = QPushButton("Dine-in")
        self.btn_dine_in.setCheckable(True)
        self.btn_dine_in.setChecked(True)
        self.btn_dine_in.hide()
        self.btn_takeaway = QPushButton("Takeaway")
        self.btn_takeaway.hide()
        self.takeaway_combo = QComboBox()
        self.takeaway_combo.hide()
        self.takeaway_combo.currentIndexChanged.connect(self._on_takeaway_selected)

        layout.addWidget(self.cart_widget, 1)

        self._make_group_compact(self.totals_widget.discount_group)
        self._make_group_compact(self.totals_widget.loyalty_group)
        self._make_group_compact(self.totals_widget.totals_group)
        self._make_group_compact(self.options_widget)
        self._make_group_compact(self.payment_widget)
        self._make_group_compact(self.checkout_handler.action_group)
        self._make_payment_compact()
        self.checkout_handler.action_group.hide()
        self.totals_widget.totals_group.hide()

        utility_row = QHBoxLayout()
        utility_row.setContentsMargins(0, 0, 0, 0)
        utility_row.setSpacing(8)
        self.btn_sale_details = ModernButton(" Sale Details", ModernButton.SECONDARY)
        self.btn_sale_details.set_icon("receipt_long", size=(16, 16))
        self.btn_sale_details.setFixedHeight(34)
        self.btn_sale_details.clicked.connect(self.open_sale_details_dialog)
        utility_row.addWidget(self.btn_sale_details, 1)

        self.btn_add_expense = ModernButton(" Expense", ModernButton.SECONDARY)
        self.btn_add_expense.set_icon("money", size=(16, 16))
        self.btn_add_expense.setFixedHeight(34)
        self.btn_add_expense.clicked.connect(self.open_expense_dialog)
        utility_row.addWidget(self.btn_add_expense, 1)

        self.btn_open_kitchen = ModernButton(" Kitchen View", ModernButton.SECONDARY)
        self.btn_open_kitchen.set_text_only(True)
        self.btn_open_kitchen.setFixedHeight(34)
        self.btn_open_kitchen.clicked.connect(self.open_kitchen_view)
        utility_row.addWidget(self.btn_open_kitchen, 1)
        layout.addLayout(utility_row)

        payment_action_row = QHBoxLayout()
        payment_action_row.setContentsMargins(0, 0, 0, 0)
        payment_action_row.setSpacing(8)
        payment_action_row.addWidget(self.payment_widget, 1)

        action_col = QVBoxLayout()
        action_col.setContentsMargins(0, 0, 0, 0)
        action_col.setSpacing(6)
        self.btn_send_kitchen = ModernButton(" Send Kitchen", ModernButton.SECONDARY)
        self.btn_send_kitchen.set_text_only(True)
        self.btn_send_kitchen.setFixedHeight(59)
        self.btn_send_kitchen.clicked.connect(self.send_current_order_to_kitchen)
        action_col.addWidget(self.btn_send_kitchen)

        self.btn_settle = ModernButton(" Settle Bill", ModernButton.PRIMARY)
        self.btn_settle.set_icon("payments", size=(20, 20))
        self.btn_settle.setFixedHeight(59)
        self.btn_settle.clicked.connect(self.settle_bill)
        action_col.addWidget(self.btn_settle)

        self.btn_clear_order = ModernButton(" Clear Order", ModernButton.SECONDARY)
        self.btn_clear_order.set_text_only(True)
        self.btn_clear_order.setFixedHeight(59)
        self.btn_clear_order.clicked.connect(self.clear_current_order)
        self.btn_clear_order.hide()
        payment_action_row.addLayout(action_col, 1)
        layout.addLayout(payment_action_row)

        return panel

    def _make_group_compact(self, widget):
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if hasattr(widget, "setTitle"):
            widget.setTitle("")

    def _make_payment_compact(self):
        payment_layout = self.payment_widget.layout()
        if payment_layout:
            payment_layout.setContentsMargins(12, 10, 12, 10)
            payment_layout.setSpacing(6)
        self.payment_widget.setMaximumHeight(124)
        self.payment_widget.payment_combo.setFixedHeight(32)
        self.payment_widget.payment_input.setFixedHeight(44)

    def _sync_selector_control_heights(self):
        selector_height = 34
        for widget in (self.customer_combo, self.order_type_combo, self.table_combo):
            widget.setMinimumHeight(selector_height)
            widget.setMaximumHeight(selector_height)
        self.btn_new_takeaway.setMinimumHeight(selector_height)
        self.btn_new_takeaway.setMaximumHeight(selector_height)
        self.btn_new_takeaway.setFixedHeight(selector_height)

    def _sync_compact_button_heights(self):
        for button in (self.btn_sale_details, self.btn_add_expense, self.btn_open_kitchen):
            button.setFixedHeight(34)
        for button in (self.btn_send_kitchen, self.btn_settle, self.btn_clear_order):
            button.setFixedHeight(59)
        self._make_payment_compact()

    def open_sale_details_dialog(self):
        """Open hidden sale controls in a compact dialog."""
        if self._details_dialog:
            self._details_dialog.raise_()
            self._details_dialog.activateWindow()
            return

        colors = get_theme_colors()
        dialog = QDialog(self)
        dialog.setWindowTitle("Sale Details")
        dialog.setModal(True)
        dialog.resize(420, 500)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.get('bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
            }}
            QGroupBox {{
                color: {colors.get('text', '#212529')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 6px;
                margin-top: 8px;
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }}
            QLabel, QCheckBox, QRadioButton {{
                color: {colors.get('text', '#212529')};
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        discount_group = QGroupBox("Discount")
        discount_layout = QVBoxLayout(discount_group)
        discount_check = QCheckBox(self.totals_widget.discount_checkbox.text())
        discount_check.setChecked(self.totals_widget.discount_checkbox.isChecked())
        discount_check.setEnabled(self.totals_widget.discount_checkbox.isEnabled())
        discount_input = QDoubleSpinBox()
        discount_input.setRange(self.totals_widget.discount_input.minimum(), self.totals_widget.discount_input.maximum())
        discount_input.setDecimals(self.totals_widget.discount_input.decimals())
        discount_input.setSuffix(self.totals_widget.discount_input.suffix())
        discount_input.setValue(self.totals_widget.discount_input.value())
        discount_input.setEnabled(discount_check.isChecked())
        discount_check.toggled.connect(discount_input.setEnabled)
        discount_layout.addWidget(discount_check)
        discount_layout.addWidget(discount_input)
        layout.addWidget(discount_group)

        loyalty_group = QGroupBox("Loyalty")
        loyalty_layout = QVBoxLayout(loyalty_group)
        points_label = QLabel(self.totals_widget.points_label.text())
        points_check = QCheckBox(self.totals_widget.points_use_check.text())
        points_check.setChecked(self.totals_widget.points_use_check.isChecked())
        points_spin = QSpinBox()
        points_spin.setRange(self.totals_widget.points_spin.minimum(), self.totals_widget.points_spin.maximum())
        points_spin.setSuffix(self.totals_widget.points_spin.suffix())
        points_spin.setValue(self.totals_widget.points_spin.value())
        points_spin.setEnabled(points_check.isChecked())
        points_check.toggled.connect(points_spin.setEnabled)
        loyalty_layout.addWidget(points_label)
        loyalty_layout.addWidget(points_check)
        loyalty_layout.addWidget(points_spin)
        layout.addWidget(loyalty_group)

        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        cash_radio = QRadioButton(self.options_widget.cash_radio.text())
        credit_radio = QRadioButton(self.options_widget.credit_radio.text())
        credit_radio.setEnabled(self.options_widget.credit_radio.isEnabled())
        payment_group = QButtonGroup(dialog)
        payment_group.addButton(cash_radio)
        payment_group.addButton(credit_radio)
        cash_radio.setChecked(self.options_widget.cash_radio.isChecked())
        credit_radio.setChecked(self.options_widget.credit_radio.isChecked())
        print_check = QCheckBox(self.options_widget.print_receipt_check.text())
        print_check.setChecked(self.options_widget.print_receipt_check.isChecked())
        open_drawer_check = QCheckBox(self.options_widget.open_drawer_check.text())
        open_drawer_check.setChecked(self.options_widget.open_drawer_check.isChecked())
        options_layout.addWidget(cash_radio)
        options_layout.addWidget(credit_radio)
        options_layout.addWidget(print_check)
        options_layout.addWidget(open_drawer_check)
        layout.addWidget(options_group)

        totals_group = QGroupBox("Totals")
        totals_layout = QVBoxLayout(totals_group)
        totals_layout.addWidget(QLabel(self.totals_widget.subtotal_label.text()))
        totals_layout.addWidget(QLabel(self.totals_widget.tax_label.text()))
        totals_layout.addWidget(QLabel(self.totals_widget.total_label.text()))
        layout.addWidget(totals_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        self._details_dialog = dialog
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.totals_widget.discount_checkbox.setChecked(discount_check.isChecked())
                self.totals_widget.discount_input.setValue(discount_input.value())
                self.totals_widget.points_use_check.setChecked(points_check.isChecked())
                self.totals_widget.points_spin.setValue(points_spin.value())
                self.options_widget.set_payment_type("Credit" if credit_radio.isChecked() else "Cash")
                self.options_widget.payment_type_changed.emit(self.options_widget.get_payment_type())
                self.options_widget.print_receipt_check.setChecked(print_check.isChecked())
                self.options_widget.open_drawer_check.setChecked(open_drawer_check.isChecked())
                self.totals_widget.update_totals()
                self.payment_widget.update_change()
        finally:
            self._details_dialog = None

    def open_expense_dialog(self):
        """Open expense entry dialog from Restaurant Mode."""
        from ui.expense_dialog import ExpenseDialog

        dialog = ExpenseDialog(parent=self)
        if dialog.exec():
            main_window = self.window()
            expense_page = getattr(main_window, "expense_page", None)
            if expense_page:
                for method_name in ("load_expenses", "load_categories", "update_cards"):
                    method = getattr(expense_page, method_name, None)
                    if callable(method):
                        method()

    def open_kitchen_view(self):
        if self._kitchen_dialog:
            self._kitchen_dialog.raise_()
            self._kitchen_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setObjectName("kitchenQueueDialog")
        dialog.setWindowTitle("Kitchen Queue")
        dialog.resize(980, 760)
        dialog.setMinimumSize(860, 620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Kitchen Queue")
        title.setObjectName("restaurantPanelTitle")
        header.addWidget(title)
        header.addStretch()
        self.btn_refresh_kitchen = ModernButton(" Refresh", ModernButton.SECONDARY)
        self.btn_refresh_kitchen.set_text_only(True)
        self.btn_refresh_kitchen.setFixedHeight(34)
        self.btn_refresh_kitchen.clicked.connect(self.refresh_kitchen_tickets)
        header.addWidget(self.btn_refresh_kitchen)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        holder = QWidget()
        self.kitchen_list = QVBoxLayout(holder)
        self.kitchen_list.setContentsMargins(4, 4, 4, 4)
        self.kitchen_list.setSpacing(14)
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)

        self._kitchen_dialog = dialog
        self.update_theme()
        self.refresh_kitchen_tickets()
        try:
            dialog.exec()
        finally:
            self._kitchen_dialog = None
            self.kitchen_list = None
            self.btn_refresh_kitchen = None

    def set_order_type(self, order_type):
        self._save_current_order()
        self.order_type = order_type
        self._sync_order_type_combo()
        if order_type == "Takeaway":
            self.current_table_id = None
            self.current_table_name = "Takeaway"
            self.btn_takeaway.setChecked(True)
            open_orders = self.refresh_takeaway_orders()
            if open_orders:
                self._load_takeaway_order(open_orders[0])
            else:
                self.current_order_id = None
                self._set_takeaway_combo_current(None)
                self._load_cart([])
                self._restore_customer(None)
                self._update_order_title()
        else:
            self.btn_dine_in.setChecked(True)
            self.btn_new_takeaway.hide()
            self.current_order_id = None
            self.current_table_name = ""
            self._load_cart([])
            self.refresh_tables()
            self._update_order_title()

    def _sync_order_type_combo(self):
        combo = getattr(self, "order_type_combo", None)
        if not combo:
            return
        combo.blockSignals(True)
        try:
            index = combo.findData(self.order_type)
            combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            combo.blockSignals(False)

    def _on_order_type_changed(self, index):
        if index < 0:
            return
        order_type = self.order_type_combo.itemData(index) or "Dine-in"
        if order_type == self.order_type:
            return
        self.set_order_type(order_type)

    def _set_takeaway_combo_current(self, order_id):
        self._loading_tables = True
        try:
            index = self.table_combo.findData(order_id)
            self.table_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._loading_tables = False

    def _set_takeaway_table_placeholder(self):
        self._loading_tables = True
        try:
            self.table_combo.clear()
            self.table_combo.addItem("New Takeaway Order", None)
            self.table_combo.setEnabled(True)
            self.btn_new_takeaway.show()
        finally:
            self._loading_tables = False

    def refresh_tables(self):
        self._table_rows = list_tables_with_status()
        self._update_order_counts()
        if self.order_type == "Takeaway":
            self._set_takeaway_table_placeholder()
            return
        self._loading_tables = True
        self._table_buttons.clear()
        current_id = self.current_table_id
        self.table_combo.clear()
        self.table_combo.addItem("Select table...", None)
        self.table_combo.setEnabled(True)
        for row in self._table_rows:
            table_id, table_no, display_name, seats, status, order_id, order_no, total, item_count, kitchen = row
            kitchen_text = self._kitchen_status_label(kitchen) if order_id else ""
            label = f"{display_name} - {status.title()} | {item_count or 0} items"
            if kitchen_text:
                label += f" | {kitchen_text}"
            self.table_combo.addItem(label, table_id)
        self._loading_tables = False
        self._set_table_combo_current(current_id)
        self._style_table_buttons()

    def _set_table_combo_current(self, table_id):
        self._loading_tables = True
        try:
            index = self.table_combo.findData(table_id)
            self.table_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._loading_tables = False

    def _on_table_combo_changed(self, index):
        if self._loading_tables or index < 0:
            return
        if self.order_type == "Takeaway":
            order_id = self.table_combo.itemData(index)
            if not order_id:
                self.new_takeaway_order()
                return
            self._save_current_order()
            order = get_order(order_id)
            if order:
                self._load_takeaway_order(order)
            return
        table_id = self.table_combo.itemData(index)
        if not table_id:
            return
        table_name = self.table_combo.itemText(index).split(" - ", 1)[0]
        self.select_table(table_id, table_name)

    def refresh_kitchen_tickets(self):
        if self.kitchen_list is None:
            return
        while self.kitchen_list.count():
            item = self.kitchen_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        tickets = list_kitchen_tickets()
        if not tickets:
            empty_card = QFrame()
            empty_card.setObjectName("kitchenEmptyState")
            empty_card.setMinimumHeight(180)
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(16, 16, 16, 16)
            empty_layout.addStretch()
            empty_title = QLabel("No active kitchen tickets")
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_title.setObjectName("kitchenEmptyTitle")
            empty_hint = QLabel("Sent kitchen orders will appear here.")
            empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_hint.setObjectName("kitchenEmptyLabel")
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_hint)
            empty_layout.addStretch()
            self.kitchen_list.addWidget(empty_card)
            self.kitchen_list.addStretch()
            return

        for ticket in tickets:
            self.kitchen_list.addWidget(self._build_kitchen_ticket_card(ticket))
        self.kitchen_list.addStretch()

    def _make_kitchen_button(self, text, style=ModernButton.SECONDARY, width=None):
        button = ModernButton(text, style)
        button.set_text_only(True)
        button.set_compact(True)
        button.setCheckable(False)
        button.setAutoExclusive(False)
        if width:
            button.setFixedWidth(width)
        button.setFixedHeight(28)
        return button

    def _build_kitchen_ticket_card(self, ticket):
        card = QFrame()
        card.setObjectName("kitchenTicketCard")
        card.setProperty("ticket_status", ticket["status"])
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setLineWidth(1)
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        colors = get_theme_colors()
        card.setStyleSheet(f"""
            QFrame#kitchenTicketCard {{
                background-color: transparent;
                border: 1px solid {colors['text_secondary']};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(5)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel(ticket["source_name"])
        title.setObjectName("kitchenTicketTitle")
        title.setMinimumWidth(150)
        header.addWidget(title)

        meta = QLabel(f"{ticket['ticket_no']}  |  {ticket['status'].title()}  |  {ticket['item_lines']} lines  |  {ticket['created_at']}")
        meta.setObjectName("kitchenTicketMeta")
        header.addWidget(meta, 1)

        preview_btn = self._make_kitchen_button("Preview", ModernButton.SECONDARY, 76)
        preview_btn.clicked.connect(lambda checked=False, tid=ticket["id"]: self.open_kitchen_ticket_preview(tid))
        header.addWidget(preview_btn)
        layout.addLayout(header)

        for item in ticket["items"]:
            quantity = item["quantity"]
            qty = int(quantity) if float(quantity).is_integer() else quantity
            item_status = str(item.get("status") or "sent").lower()
            status_text = self._kitchen_status_label(item_status)
            row = QFrame()
            row.setObjectName("kitchenItemRow")
            row.setProperty("item_status", item_status)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)

            qty_label = QLabel(f"{qty}x")
            qty_label.setObjectName("kitchenQtyLabel")
            qty_label.setFixedWidth(42)
            row_layout.addWidget(qty_label)

            text = item["display_name"] or item["product_name"]
            if item["modifier_summary"]:
                text += f"\n{item['modifier_summary']}"
            if item["note"]:
                text += f"\nNote: {item['note']}"
            item_label = QLabel(text)
            item_label.setObjectName("kitchenTicketItem")
            item_label.setWordWrap(True)
            row_layout.addWidget(item_label, 1)

            status_label = QLabel(status_text)
            status_label.setObjectName("kitchenStatusBadge")
            status_label.setProperty("item_status", item_status)
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setFixedWidth(96)
            row_layout.addWidget(status_label)

            item_actions = QHBoxLayout()
            item_actions.setSpacing(4)
            if item_status not in {"cancelled", "served"}:
                for label, status in (("Prep", "preparing"), ("Ready", "ready"), ("Served", "served")):
                    button_style = ModernButton.PRIMARY if status == "ready" else ModernButton.SECONDARY
                    btn = self._make_kitchen_button(label, button_style, 62)
                    btn.setEnabled(item_status != status)
                    btn.clicked.connect(
                        lambda checked=False, iid=item["id"], s=status: self.set_kitchen_item_status(iid, s)
                    )
                    item_actions.addWidget(btn)
                cancel_btn = self._make_kitchen_button("Cancel", ModernButton.DANGER, 64)
                cancel_btn.clicked.connect(lambda checked=False, iid=item["id"]: self.cancel_kitchen_item(iid))
                item_actions.addWidget(cancel_btn)
            item_actions.addStretch()
            row_layout.addLayout(item_actions)
            layout.addWidget(row)
        return card

    def set_kitchen_item_status(self, ticket_item_id, status):
        try:
            order_id = update_kitchen_ticket_item_status(ticket_item_id, status)
            self.refresh_kitchen_tickets()
            self.refresh_tables()
            self.refresh_takeaway_orders()
            if order_id == self.current_order_id:
                self._update_order_title()
        except Exception as exc:
            logger.error(f"Failed to update kitchen item {ticket_item_id}: {exc}", exc_info=True)
            QMessageBox.critical(self, "Kitchen", f"Could not update item: {exc}")

    def set_kitchen_ticket_status(self, ticket_id, status):
        try:
            update_kitchen_ticket_status(ticket_id, status)
            self.refresh_kitchen_tickets()
            self.refresh_tables()
        except Exception as exc:
            logger.error(f"Failed to update kitchen ticket {ticket_id}: {exc}", exc_info=True)
            QMessageBox.critical(self, "Kitchen", f"Could not update ticket: {exc}")

    def cancel_kitchen_item(self, ticket_item_id):
        reply = QMessageBox.question(
            self,
            "Kitchen",
            "Cancel this item from the order?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            order_id = cancel_kitchen_ticket_item(ticket_item_id)
            self.refresh_kitchen_tickets()
            self.refresh_tables()
            self.refresh_takeaway_orders()
            if order_id == self.current_order_id:
                order = get_order(order_id)
                self._load_cart(order["cart"] if order else [])
                self._update_order_title()
        except Exception as exc:
            logger.error(f"Failed to cancel kitchen item {ticket_item_id}: {exc}", exc_info=True)
            QMessageBox.critical(self, "Kitchen", f"Could not cancel item: {exc}")

    def open_kitchen_ticket_preview(self, ticket_id):
        ticket = get_kitchen_ticket(ticket_id)
        if not ticket:
            QMessageBox.warning(self, "Kitchen", "Kitchen ticket not found.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Kitchen Ticket - {ticket['ticket_no']}")
        dialog.resize(420, 520)
        colors = get_theme_colors()
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QTextEdit {{
                background-color: #ffffff;
                color: #000000;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 8px;
                font-family: 'Courier New';
                font-size: 10pt;
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText("\n".join(build_kitchen_ticket_lines(ticket)))
        layout.addWidget(preview, 1)

        button_row = QHBoxLayout()
        btn_print = self._make_kitchen_button("Print", ModernButton.SECONDARY, 90)
        btn_print.clicked.connect(lambda: self.print_kitchen_ticket(ticket_id, preview, dialog))
        button_row.addWidget(btn_print)
        button_row.addStretch()
        btn_close = self._make_kitchen_button("Close", ModernButton.TERTIARY, 90)
        btn_close.clicked.connect(dialog.accept)
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)
        dialog.exec()

    def print_kitchen_ticket(self, ticket_id, preview, dialog):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_dialog = QPrintDialog(printer, dialog)
        if print_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        preview.document().print(printer)
        mark_kitchen_ticket_printed(ticket_id)
        self.refresh_kitchen_tickets()

    def _kitchen_status_label(self, status):
        labels = {
            "sent": "Kitchen Sent",
            "preparing": "Preparing",
            "ready": "Ready",
            "served": "Served",
            "cancelled": "Cancelled",
        }
        return labels.get(str(status or "").lower(), "")

    def refresh_takeaway_orders(self):
        orders = list_open_takeaway_orders()
        self._takeaway_order_count = len(orders)
        self._update_order_counts()
        self.takeaway_combo.blockSignals(True)
        self.takeaway_combo.clear()
        for order in orders:
            label = f"{order['order_no']} | {order['item_count']} items | {format_money(order['total_amount'], get_currency_symbol())}"
            self.takeaway_combo.addItem(label, order["id"])
        self.takeaway_combo.blockSignals(False)
        if self.order_type == "Takeaway":
            self._loading_tables = True
            try:
                self.table_combo.clear()
                self.table_combo.addItem("New Takeaway Order", None)
                for order in orders:
                    label = f"{order['order_no']} | {order['item_count']} items | {format_money(order['total_amount'], get_currency_symbol())}"
                    self.table_combo.addItem(label, order["id"])
                self.table_combo.setEnabled(True)
                self.btn_new_takeaway.show()
            finally:
                self._loading_tables = False
            self._set_takeaway_combo_current(self.current_order_id)
        return orders

    def _update_order_counts(self):
        table_rows = getattr(self, "_table_rows", []) or []
        occupied_tables = sum(1 for row in table_rows if str(row[4] or "").lower() == "occupied")
        takeaway_count = int(getattr(self, "_takeaway_order_count", 0) or 0)
        if hasattr(self, "table_count_label"):
            self.table_count_label.setText(f"Table {occupied_tables}")
        if hasattr(self, "takeaway_count_label"):
            self.takeaway_count_label.setText(f"Takeaway {takeaway_count}")

    def select_table(self, table_id, table_name):
        self._save_current_order()
        self.order_type = "Dine-in"
        self._sync_order_type_combo()
        self.current_table_id = table_id
        self.current_table_name = table_name
        self.btn_dine_in.setChecked(True)
        order = get_open_order_for_table(table_id)
        self.current_order_id = order["id"] if order else None
        self._load_cart(order["cart"] if order else [])
        self._restore_customer(order)
        self._update_order_title()
        self._set_table_combo_current(table_id)
        self._style_table_buttons()

    def new_takeaway_order(self):
        self._save_current_order()
        self.order_type = "Takeaway"
        self._sync_order_type_combo()
        self.current_table_id = None
        self.current_table_name = "Takeaway"
        self.current_order_id = None
        self.btn_takeaway.setChecked(True)
        self.refresh_takeaway_orders()
        self._set_takeaway_combo_current(None)
        self._load_cart([])
        self._restore_customer(None)
        self._update_order_title()

    def _on_takeaway_selected(self, index):
        if self._loading_order or index < 0:
            return
        order_id = self.takeaway_combo.itemData(index)
        if not order_id:
            self.new_takeaway_order()
            return
        self._save_current_order()
        order = get_order(order_id)
        if not order:
            return
        self._load_takeaway_order(order)

    def _load_takeaway_order(self, order):
        self.order_type = "Takeaway"
        self._sync_order_type_combo()
        self.current_table_id = None
        self.current_table_name = "Takeaway"
        self.current_order_id = order["id"]
        self.btn_takeaway.setChecked(True)
        self.refresh_takeaway_orders()
        self._set_takeaway_combo_current(order["id"])
        self._load_cart(order["cart"])
        self._restore_customer(order)
        self._update_order_title()

    def add_menu_product(self, product_id, name, price, stock_available):
        if self.order_type == "Dine-in" and not self.current_table_id:
            QMessageBox.information(self, "Restaurant Order", "Select a table before adding items.")
            return

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(sold_by, 'Each') FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        sold_by = row[0] if row else "Each"
        modifiers = get_product_restaurant_modifiers(cursor, product_id)
        conn.close()

        if str(sold_by).lower() == "restaurant":
            option_payload = self._select_restaurant_modifiers(name, modifiers)
            if option_payload is None:
                return
            self.cart_widget.add_restaurant_product(
                product_id,
                name,
                price,
                option_payload.get("modifiers", []),
                option_payload.get("note", ""),
            )
        else:
            self.cart_widget.add_product(product_id, name, price, stock_available)

    def _select_restaurant_modifiers(self, product_name, modifiers):
        modifiers = modifiers or []
        if not modifiers:
            return []

        colors = get_theme_colors()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Options - {product_name}")
        dialog.setModal(True)
        dialog.resize(540, 420)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {colors['bg']};
                color: {colors['text']};
            }}
            QLabel {{
                color: {colors['text']};
                background: transparent;
                font-weight: 600;
            }}
            QRadioButton, QCheckBox {{
                color: {colors['text']};
                background: transparent;
                padding: 4px;
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        by_group = {}
        for modifier in modifiers:
            by_group.setdefault(modifier["group"], []).append(modifier)

        controls = []
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        for column, (group, group_modifiers) in enumerate(by_group.items()):
            group_widget = QWidget()
            group_layout = QVBoxLayout(group_widget)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(6)
            group_layout.addWidget(QLabel(group))
            has_choice = any(mod["type"] == "choice" for mod in group_modifiers)
            choice_group = QButtonGroup(dialog) if has_choice else None
            if choice_group:
                choice_group.setExclusive(True)
            for modifier in group_modifiers:
                suffix = f" (+{format_money(modifier['price_delta'], get_currency_symbol())})" if modifier.get("price_delta") else ""
                text = f"{modifier['name']}{suffix}"
                if modifier["type"] == "choice":
                    control = QRadioButton(text)
                    choice_group.addButton(control)
                else:
                    control = QCheckBox(text)
                control.setProperty("modifier", modifier)
                controls.append(control)
                group_layout.addWidget(control)
            group_layout.addStretch()
            grid.addWidget(group_widget, 0, column % 2)
        layout.addLayout(grid)

        layout.addWidget(QLabel("Note:"))
        note_input = QTextEdit()
        note_input.setPlaceholderText("Kitchen note: no onion, extra spicy, no sugar...")
        note_input.setFixedHeight(62)
        layout.addWidget(note_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return {
            "modifiers": [control.property("modifier") for control in controls if control.isChecked()],
            "note": note_input.toPlainText().strip(),
        }

    def _load_cart(self, cart):
        self._loading_order = True
        try:
            self.cart_widget.cart = list(cart or [])
            self.cart_widget.refresh_table()
            self.totals_widget.update_totals()
            self.payment_widget.reset_manual_override()
            self.payment_widget.reset_to_default()
        finally:
            self._loading_order = False

    def _restore_customer(self, order):
        customer_id = order.get("customer_id") if order else None
        self.checkout_handler.selected_customer_id = customer_id
        if customer_id:
            idx = self.customer_combo.findData(customer_id)
            if idx >= 0:
                self.customer_combo.setCurrentIndex(idx)
        else:
            self.customer_combo.setCurrentIndex(0)

    def _on_cart_changed(self):
        self.totals_widget.update_totals()
        if not self._loading_order:
            if self.order_type == "Dine-in" and not self.current_table_id and self.cart_widget.get_cart():
                QMessageBox.information(self, "Restaurant Order", "Select a table before adding dine-in items.")
                self._load_cart([])
                return
            self._save_current_order(silent=True)

    def _save_current_order(self, silent=False):
        if self._loading_order:
            return
        cart = self.cart_widget.get_cart()
        if not cart and self.current_order_id:
            close_order(self.current_order_id, "cancelled")
            self.current_order_id = None
            self.refresh_tables()
            self.refresh_takeaway_orders()
            self.refresh_kitchen_tickets()
            self._update_order_title()
            return
        if not cart and not self.current_order_id:
            return
        if self.order_type == "Dine-in" and not self.current_table_id:
            if not silent:
                QMessageBox.information(self, "Restaurant Order", "Select a table first.")
            return
        try:
            self.current_order_id = upsert_order(
                self.current_order_id,
                self.current_table_id,
                self.order_type,
                cart,
                customer_id=self.checkout_handler.selected_customer_id,
                customer_name=self.customer_combo.currentText() if self.customer_combo.currentIndex() > 0 else "",
                total_amount=self.totals_widget.get_current_grand_total(),
            )
            self.refresh_tables()
            self.refresh_takeaway_orders()
            self._update_order_title()
        except Exception as exc:
            logger.error(f"Failed to save restaurant order: {exc}", exc_info=True)
            if not silent:
                QMessageBox.critical(self, "Restaurant Order", f"Could not save order: {exc}")

    def send_current_order_to_kitchen(self):
        if not self.cart_widget.get_cart():
            QMessageBox.information(self, "Kitchen", "Cart is empty.")
            return
        self._save_current_order()
        if not self.current_order_id:
            return
        ticket_id = send_to_kitchen(self.current_order_id)
        self.refresh_tables()
        self.refresh_kitchen_tickets()
        if not ticket_id:
            QMessageBox.information(self, "Kitchen", "No new kitchen items to send.")
        elif self.should_auto_open_kitchen_preview():
            self.open_kitchen_ticket_preview(ticket_id)
        else:
            QMessageBox.information(self, "Kitchen", "Order sent to kitchen.")

    def settle_bill(self):
        if not self.cart_widget.get_cart():
            QMessageBox.information(self, "Settle Bill", "Cart is empty.")
            return
        self._save_current_order()
        order_id = self.current_order_id
        sale_result = self.checkout_handler.checkout()
        if order_id and sale_result and not self.cart_widget.get_cart():
            close_order(order_id, "settled", sale_result)
            self.current_order_id = None
            self.refresh_tables()
            self.refresh_takeaway_orders()
            self.refresh_kitchen_tickets()
            self._update_order_title()

    def clear_current_order(self):
        if not self.cart_widget.get_cart():
            return
        reply = QMessageBox.question(
            self,
            "Clear Order",
            "Clear the current order cart?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._load_cart([])
            if self.current_order_id:
                close_order(self.current_order_id, "cancelled")
                self.current_order_id = None
                self.refresh_tables()
                self.refresh_takeaway_orders()
                self.refresh_kitchen_tickets()
                self._update_order_title()

    def _update_order_title(self):
        if self.order_type == "Dine-in":
            target = self.current_table_name or "Select a table"
        else:
            target = "Takeaway"
        suffix = f" | Order #{self.current_order_id}" if self.current_order_id else ""
        self.order_title.setText(f"{target}{suffix}")

    def load_customers(self):
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem(tr("walk_in_customer"), None)
        for cust_id, name, points in load_customers():
            self.customer_combo.addItem(f"{name} (Points: {points})", cust_id)
        self.customer_combo.blockSignals(False)

    def load_payment_types(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM payment_types ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
            self.payment_widget.load_payment_types([row[0] for row in rows] if rows else ["Cash", "Card", "Mobile Money"])
        except Exception as exc:
            logger.error(f"Failed to load payment types: {exc}")
            self.payment_widget.load_payment_types(["Cash", "Card", "Mobile Money"])

    def load_loyalty_settings(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='loyalty_points_per_dollar'")
            row = cursor.fetchone()
            points_per_dollar = float(row[0] or 0) if row else 0.0
            cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
            row = cursor.fetchone()
            expiry_months = int(row[0] or 12) if row else 12
            cursor.execute("SELECT value FROM settings WHERE key='points_dollar_value'")
            row = cursor.fetchone()
            point_value = float(row[0] or 0.01) if row else 0.01
            conn.close()
            self.totals_widget.set_loyalty_params(points_per_dollar, expiry_months, point_value)
        except Exception as exc:
            logger.error(f"Failed to load loyalty settings: {exc}")

    def on_customer_changed(self):
        self.checkout_handler.selected_customer_id = self.customer_combo.currentData()
        self.checkout_handler.load_customer_points()
        self.checkout_handler.load_customer_credit_balance()
        self.totals_widget.update_totals()
        self._save_current_order(silent=True)

    def refresh_customer_display(self):
        return

    def publish_customer_display_state(self):
        return

    def showEvent(self, event):
        self.refresh_tables()
        self.refresh_takeaway_orders()
        super().showEvent(event)

    def update_theme(self):
        colors = get_theme_colors()
        restaurant_style = f"""
            QDialog#kitchenQueueDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QWidget#restaurantPage {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QFrame#restaurantSidePanel,
            QFrame#restaurantOrderPanel,
            QFrame#openTakeawayPanel {{
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }}
            QLabel#restaurantPanelTitle,
            QLabel#restaurantOrderTitle {{
                font-size: 13pt;
                font-weight: 700;
                color: {colors['text']};
                background: transparent;
            }}
            QLabel#restaurantCountBadge {{
                color: {colors['text']};
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 9pt;
                font-weight: 700;
                min-height: 20px;
            }}
            QComboBox {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px;
            }}
            QPushButton:not(#restaurantTableButton) {{
                border-radius: 6px;
                padding: 6px;
                font-weight: 600;
            }}
            QPushButton:not(#restaurantTableButton):checked {{
                background-color: {colors['progress_bg']};
                color: white;
            }}
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background-color: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                padding: 7px 10px;
                min-width: 70px;
            }}
            QTabBar::tab:selected {{
                background-color: {colors['progress_bg']};
                color: white;
            }}
            QFrame#kitchenTicketCard {{
                background-color: transparent;
                border: 1px solid {colors['text_secondary']};
                border-radius: 6px;
            }}
            QLabel#kitchenTicketTitle {{
                color: {colors['text']};
                background: transparent;
                padding: 0px;
                font-size: 10.5pt;
                font-weight: 700;
            }}
            QLabel#kitchenTicketMeta,
            QLabel#kitchenTicketItem,
            QLabel#kitchenEmptyLabel,
            QLabel#kitchenCancelledLabel {{
                color: {colors['text']};
                background: transparent;
            }}
            QFrame#kitchenItemRow {{
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }}
            QFrame#kitchenItemRow[item_status="ready"] {{
                border-left: 4px solid #27ae60;
            }}
            QFrame#kitchenItemRow[item_status="preparing"] {{
                border-left: 4px solid #f39c12;
            }}
            QFrame#kitchenItemRow[item_status="served"] {{
                border-left: 4px solid #3498db;
            }}
            QFrame#kitchenItemRow[item_status="cancelled"] {{
                border-left: 4px solid #e74c3c;
                opacity: 0.75;
            }}
            QLabel#kitchenQtyLabel {{
                color: {colors['text_secondary']};
                font-weight: 700;
                background: transparent;
            }}
            QLabel#kitchenStatusBadge {{
                color: {colors['text']};
                background-color: {colors['input_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 4px 6px;
                font-weight: 700;
            }}
            QLabel#kitchenStatusBadge[item_status="ready"] {{
                color: #27ae60;
            }}
            QLabel#kitchenStatusBadge[item_status="preparing"] {{
                color: #f39c12;
            }}
            QLabel#kitchenStatusBadge[item_status="served"] {{
                color: #3498db;
            }}
            QLabel#kitchenStatusBadge[item_status="cancelled"] {{
                color: #e74c3c;
            }}
            QLabel#kitchenCancelledLabel {{
                color: #e74c3c;
                font-weight: 700;
            }}
            QFrame#kitchenEmptyState {{
                background-color: {colors['input_bg']};
                border: 1px dashed {colors['border']};
                border-radius: 8px;
            }}
            QLabel#kitchenEmptyTitle {{
                color: {colors['text']};
                font-size: 12pt;
                font-weight: 700;
                background: transparent;
            }}
        """
        self.setStyleSheet(restaurant_style)
        if self._kitchen_dialog:
            self._kitchen_dialog.setStyleSheet(restaurant_style)
        for widget in (self.product_grid, self.cart_widget, self.totals_widget, self.payment_widget, self.options_widget):
            if hasattr(widget, "update_theme"):
                widget.update_theme()
        for button in (
            self.btn_sale_details,
            self.btn_add_expense,
            self.btn_send_kitchen,
            self.btn_settle,
            self.btn_clear_order,
            self.btn_new_takeaway,
            self.btn_open_kitchen,
            self.btn_refresh_kitchen,
        ):
            if button:
                button.update_theme()
        self._sync_selector_control_heights()
        self._sync_compact_button_heights()
        self._style_table_buttons()

    def _style_table_buttons(self):
        for table_id, btn in self._table_buttons.items():
            self._apply_table_button_style(btn, table_id)

    def _apply_table_button_style(self, btn, table_id):
        colors = get_theme_colors()
        dark = is_dark_theme()
        selected = table_id == self.current_table_id
        status = btn.property("live_status")
        kitchen = btn.property("kitchen_status")
        if selected:
            if status == "occupied":
                bg = "#3d3424" if dark else "#fff4d6"
                fg = "#ffffff" if dark else "#1f2933"
                border = colors["progress_bg"]
            else:
                bg = colors["progress_bg"]
                fg = "#ffffff"
                border = colors["progress_bg"]
        elif status == "occupied":
            bg = "#3d3424" if dark else "#fff4d6"
            fg = "#ffffff" if dark else "#1f2933"
            border_map = {
                "sent": "#f0b429",
                "preparing": "#3498db",
                "ready": "#2ecc71",
                "served": colors["border"],
            }
            border = border_map.get(str(kitchen or "").lower(), colors["border"])
        else:
            bg = colors["input_bg"]
            fg = colors["text"]
            border = colors["border"]
        btn.setStyleSheet(f"""
            QPushButton#restaurantTableButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
                text-align: left;
                padding: 6px 8px;
                font-weight: 600;
            }}
            QPushButton#restaurantTableButton:hover {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {colors['progress_bg']};
            }}
            QPushButton#restaurantTableButton:pressed,
            QPushButton#restaurantTableButton:checked {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
            }}
        """)

    def retranslateUi(self):
        self.checkout_handler.retranslateUi()
