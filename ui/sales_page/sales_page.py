# ui/sales_page/sales_page.py
import ctypes
import json
from PyQt6 import sip
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QMessageBox, QApplication, QComboBox, QLabel, QDialog, QCheckBox, QDoubleSpinBox, QSpinBox, QRadioButton, QButtonGroup, QDialogButtonBox
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtPrintSupport import QPrinterInfo
from loguru import logger

from ui.sales_page.product_grid import ProductGrid
from ui.sales_page.cart_widget import CartWidget, load_cart_from_file, delete_cart_backup
from ui.sales_page.totals_widget import TotalsWidget
from ui.sales_page.payment_widget import PaymentWidget
from ui.sales_page.options_widget import OptionsWidget
from ui.sales_page.checkout_handler import CheckoutHandler

# âœ… Import ModernButton
from ui.widgets.modern_button import ModernButton
from ui.design_system.icon import get_icon

from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.language import lang
from utils.translations import tr
from utils.customer_utils import load_customers
from ui.themes import theme_manager, get_current_theme, is_dark_theme, get_theme_colors


class SalesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("salesPage")
        self.shop_name = "ZAY POS"
        self.receipt_header_text = ""
        self.receipt_footer_text = ""
        self.show_customer_name = True
        self.customer_display = None
        self.details_panel = None
        self.details_layout = None
        self._details_dialog = None
        self.btn_toggle_details = None
        self.right_container = None
        self.btn_customer_display = None
        self.btn_cash_drawer = None
        self.btn_add_expense = None

        # Create subâ€‘widgets
        self.product_grid = ProductGrid(self)
        self.cart_widget = CartWidget(self)
        self.totals_widget = TotalsWidget(self)
        self.payment_widget = PaymentWidget(self)
        self.options_widget = OptionsWidget(self)
        self.checkout_handler = CheckoutHandler(self)

        # Connect signals
        self.product_grid.product_selected.connect(self.cart_widget.add_product)
        self.product_grid.service_selected.connect(self.cart_widget.add_service)
        self.product_grid.barcode_scanned.connect(self.cart_widget.add_product_by_barcode)
        self.cart_widget.cart_changed.connect(self.totals_widget.update_totals)
        self.cart_widget.cart_changed.connect(self.payment_widget.update_change)
        self.cart_widget.cart_changed.connect(self.refresh_customer_display)
        self.totals_widget.grand_total_changed.connect(self.payment_widget.auto_set_payment)
        self.totals_widget.grand_total_changed.connect(self.cart_widget.update_grand_total)
        self.totals_widget.grand_total_changed.connect(lambda _total: self.cart_widget.update_change())
        self.payment_widget.payment_amount_changed.connect(self.totals_widget.update_change_display)
        self.payment_widget.payment_amount_changed.connect(lambda _amount: self.cart_widget.update_change())
        self.payment_widget.checkout_requested.connect(self.checkout_handler.checkout)
        
        self.options_widget.payment_type_changed.connect(self.checkout_handler.on_payment_type_changed)
        
        self.cart_widget.cart_changed.connect(self.publish_customer_display_state)
        self.totals_widget.grand_total_changed.connect(lambda _total: self.publish_customer_display_state())
        self.payment_widget.payment_amount_changed.connect(lambda _amount: self.publish_customer_display_state())
        self.payment_widget.payment_combo.currentIndexChanged.connect(lambda *_: self.publish_customer_display_state())

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        content_layout.addWidget(self.product_grid, stretch=3)

        self.right_container = QWidget()
        self.right_container.setObjectName("salesRightContainer")
        self.right_container.setStyleSheet("QWidget#salesRightContainer { background-color: transparent; }")
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setSpacing(6)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.setup_customer_section()
        right_layout.addLayout(self.customer_layout)

        right_layout.addWidget(self.cart_widget, stretch=1)
        
        self._make_group_compact(self.totals_widget.discount_group, hide_title=True)
        self._make_group_compact(self.totals_widget.loyalty_group, hide_title=True)
        self._make_group_compact(self.totals_widget.totals_group, hide_title=True)
        self.options_widget.hide_title = True
        self._make_group_compact(self.options_widget, hide_title=True)
        self._make_group_compact(self.payment_widget, hide_title=True)
        self._make_group_compact(self.checkout_handler.action_group, hide_title=False)

        self.btn_toggle_details = QPushButton("Sale Details")
        self.btn_toggle_details.setFixedHeight(30)
        self.btn_toggle_details.setIconSize(QSize(16, 16))
        self.btn_toggle_details.clicked.connect(self.open_sale_details_dialog)

        self.btn_add_expense = QPushButton("Add Expense")
        self.btn_add_expense.setFixedHeight(30)
        self.btn_add_expense.setIconSize(QSize(16, 16))
        self.btn_add_expense.setToolTip("Add Expense (Ctrl+E)")
        self.btn_add_expense.clicked.connect(self.open_expense_dialog)

        self._apply_details_toggle_style()
        detail_buttons_layout = QHBoxLayout()
        detail_buttons_layout.setContentsMargins(0, 0, 0, 0)
        detail_buttons_layout.setSpacing(6)
        detail_buttons_layout.addWidget(self.btn_toggle_details, 1)
        detail_buttons_layout.addWidget(self.btn_add_expense, 1)
        right_layout.addLayout(detail_buttons_layout)

        self.details_panel = QWidget(self)
        self.details_panel.setObjectName("saleDetailsHiddenHolder")
        self.details_panel.setWindowFlag(Qt.WindowType.Widget, True)
        self.details_panel.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.details_layout = QVBoxLayout(self.details_panel)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(5)
        self._restore_details_widgets()
        self._hide_original_details_widgets()
        self.details_panel.setFixedSize(0, 0)
        self.details_panel.setVisible(False)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addWidget(self.payment_widget, 1)
        action_layout.addWidget(self.checkout_handler.action_group, 2)
        right_layout.addLayout(action_layout)

        content_layout.addWidget(self.right_container, stretch=2)
        main_layout.addLayout(content_layout, stretch=1)

        self.setLayout(main_layout)
        self._apply_root_theme_style()

        # Restore cart from backup
        restored_cart = load_cart_from_file()
        if restored_cart:
            conn = connect_db()
            cursor = conn.cursor()
            valid_items = []
            for item in restored_cart:
                if item.get("variant_id"):
                    cursor.execute("""
                        SELECT p.name, p.price, p.sold_by,
                               v.size, v.color, v.sku, v.barcode, v.price, v.stock, v.image
                        FROM product_variants v
                        JOIN products p ON p.id = v.product_id
                        WHERE v.id = ? AND v.product_id = ? AND COALESCE(v.active, 1) = 1
                    """, (item.get("variant_id"), item["id"]))
                    row = cursor.fetchone()
                    if row:
                        db_name, db_price, sold_by, size, color, sku, barcode, variant_price, variant_stock, variant_image = row
                        variant_label = " / ".join([part for part in (color or "", size or "") if part])
                        item["base_name"] = db_name
                        item["name"] = f"{db_name} - {variant_label}" if variant_label else db_name
                        item["variant_size"] = size or ""
                        item["variant_color"] = color or ""
                        item["variant_sku"] = sku or ""
                        item["variant_barcode"] = barcode or ""
                        item["original_price"] = float(variant_price or db_price or 0)
                        item["price"] = float(item.get("price") or item["original_price"])
                        item["stock"] = int(variant_stock or 0)
                        item["location"] = variant_label or "Variant"
                        item["image"] = variant_image or item.get("image", "")
                        if not item.get("is_service", False) and int(variant_stock or 0) < item["qty"]:
                            item["qty"] = int(variant_stock or 0)
                        if item["qty"] > 0:
                            valid_items.append(item)
                    continue
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

        # Load data
        self.load_settings()
        self.load_customers()
        self.load_receipt_settings()
        self.load_payment_types()
        self.product_grid.load_products()

        self.setup_shortcuts()

        # Connect theme manager signal
        theme_manager.theme_changed.connect(self.on_theme_changed)

        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
        self.publish_customer_display_state()

    def _make_group_compact(self, group, hide_title=False):
        """Make a group box compact with reduced padding and spacing"""
        if isinstance(group, QGroupBox):
            colors = get_theme_colors()
            border = colors.get('border', '#dee2e6')
            text = colors.get('text', '#212529')
            bg = colors.get('card_bg', '#ffffff')
            input_bg = colors.get('input_bg', '#ffffff')
            input_border = colors.get('input_border', border)
            focus = colors.get('border_hover', '#5865f2')
            if hide_title:
                group.setStyleSheet(f"""
                    QGroupBox {{
                        font-weight: bold;
                        padding-top: 0px;
                        margin-top: 0px;
                        border: 1px solid {border};
                        border-radius: 3px;
                        background-color: {bg};
                        color: {text};
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin;
                        left: -9999px;
                        padding: 0px;
                    }}
                    QGroupBox QLabel, QGroupBox QCheckBox, QGroupBox QRadioButton {{
                        color: {text};
                        background-color: transparent;
                    }}
                    QGroupBox QSpinBox, QGroupBox QDoubleSpinBox, QGroupBox QComboBox {{
                        background-color: {input_bg};
                        color: {text};
                        border: 1px solid {input_border};
                        border-radius: 4px;
                        padding: 4px 6px;
                    }}
                    QGroupBox QSpinBox:focus, QGroupBox QDoubleSpinBox:focus, QGroupBox QComboBox:focus {{
                        border: 1px solid {focus};
                    }}
                """)
            else:
                group.setStyleSheet(f"""
                    QGroupBox {{
                        font-weight: bold;
                        padding-top: 3px;
                        margin-top: 2px;
                        background-color: {bg};
                        color: {text};
                        border: 1px solid {border};
                        border-radius: 3px;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin;
                        left: 5px;
                        padding: 0 3px 0 3px;
                        color: {text};
                        background-color: {bg};
                    }}
                """)
            if group.layout():
                group.layout().setSpacing(2)
                group.layout().setContentsMargins(5, 3, 5, 3)

    def _details_widgets(self):
        return [
            self.totals_widget.discount_group,
            self.totals_widget.loyalty_group,
            self.options_widget,
            self.totals_widget.totals_group,
        ]

    def _valid_details_widgets(self):
        widgets = []
        for widget in self._details_widgets():
            if widget is not None and not sip.isdeleted(widget):
                widgets.append(widget)
        return widgets

    def _detach_details_from_layout(self, layout):
        if not layout:
            return
        for widget in self._valid_details_widgets():
            layout.removeWidget(widget)
            widget.setParent(self.details_panel)
            widget.hide()
        if self.details_panel:
            self.details_panel.setFixedSize(0, 0)
            self.details_panel.hide()

    def _hide_original_details_widgets(self):
        """Keep the original detail widgets off-screen so they never leak into the page."""
        if self.details_panel:
            self.details_panel.setParent(self)
            self.details_panel.setFixedSize(0, 0)
            self.details_panel.move(-10000, -10000)
            self.details_panel.hide()
        for widget in self._valid_details_widgets():
            widget.setParent(self.details_panel)
            widget.hide()

    def _restore_details_widgets(self):
        if not self.details_layout:
            return
        if self.details_panel:
            self.details_panel.setFixedSize(0, 0)
            self.details_panel.move(-10000, -10000)
            self.details_panel.hide()
        for widget in self._valid_details_widgets():
            widget.setParent(self.details_panel)
            self.details_layout.addWidget(widget)
            widget.hide()

    def open_sale_details_dialog(self):
        """Open optional sale controls in a dialog instead of expanding inline."""
        self._hide_original_details_widgets()
        if self._details_dialog:
            self._details_dialog.raise_()
            self._details_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Sale Details")
        dialog.setModal(True)
        dialog.resize(420, 520)
        colors = get_theme_colors()
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.get('bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
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
            self._hide_original_details_widgets()
            self.update_theme()

    def _apply_details_toggle_style(self):
        buttons = [button for button in (self.btn_toggle_details, self.btn_add_expense) if button]
        if not buttons:
            return

        colors = get_theme_colors()
        bg = colors.get('card_bg', '#ffffff')
        hover = colors.get('bg_hover', '#f1f3f5')
        text = colors.get('text', '#212529')
        border = colors.get('border', '#dee2e6')
        active = colors.get('border_hover', '#5865f2')
        style = f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover};
                border-color: {active};
            }}
        """
        for button in buttons:
            button.setStyleSheet(style)
        self._update_details_button_icons()

    def _update_details_button_icons(self):
        colors = get_theme_colors()
        icon_color = colors.get("icon_color", colors.get("text", "#495057"))
        if self.btn_toggle_details:
            icon = get_icon("receipt_long", 16, icon_color)
            if icon:
                self.btn_toggle_details.setIcon(icon)
        if self.btn_add_expense:
            icon = get_icon("money_off", 16, icon_color)
            if icon:
                self.btn_add_expense.setIcon(icon)

    def open_expense_dialog(self):
        """Open the add expense dialog from the Sales page."""
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

    def setup_shortcuts(self):
        """Keyboard shortcuts for fast POS operation on the Sale page."""
        self.sale_shortcuts = []

        self._add_shortcut("F2", self.product_grid.focus_search)
        self._add_shortcut("Ctrl+F", self.product_grid.focus_search)
        self._add_shortcut("F3", self.focus_customer)
        self._add_shortcut("F4", self.focus_payment_amount)
        self._add_shortcut("F6", self.focus_payment_type)
        self._add_shortcut("F7", self.toggle_discount)
        self._add_shortcut("F8", self.focus_discount)
        self._add_shortcut("F9", self.set_cash_sale)
        self._add_shortcut("F10", self.set_credit_sale)
        self._add_shortcut("Ctrl+E", self.open_expense_dialog)
        self._add_shortcut("F12", self.checkout_handler.checkout)
        self._add_shortcut("Ctrl+Backspace", self.checkout_handler.clear_cart)
        self._add_shortcut("Ctrl+Delete", self.remove_selected_cart_item)
        self.update_shortcut_tooltips()

    def _add_shortcut(self, sequence, handler):
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(handler)
        self.sale_shortcuts.append(shortcut)
        return shortcut

    def _customer_display_tooltip(self):
        if self.customer_display:
            return tr("hide_customer_display")
        return tr("show_hide_customer_display")

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

    def remove_selected_cart_item(self):
        table_proxy = getattr(self.cart_widget, "table", None)
        row = table_proxy.currentRow() if table_proxy and hasattr(table_proxy, "currentRow") else -1
        if row < 0 and len(self.cart_widget.cart) == 1:
            row = 0
        if row < 0 or row >= len(self.cart_widget.cart):
            QApplication.beep()
            return
        self.cart_widget.remove_item(row)
        self.product_grid.focus_search()

    def update_shortcut_tooltips(self):
        self.customer_combo.setToolTip(tr("select_customer_shortcut"))
        self.payment_widget.payment_input.setToolTip(tr("enter_received_shortcut"))
        self.payment_widget.payment_combo.setToolTip(tr("select_payment_type_shortcut"))
        self.totals_widget.discount_checkbox.setToolTip(tr("toggle_discount_shortcut"))
        self.totals_widget.discount_input.setToolTip(tr("edit_discount_shortcut"))
        self.options_widget.cash_radio.setToolTip(tr("cash_sale_shortcut"))
        self.options_widget.credit_radio.setToolTip(tr("credit_sale_shortcut"))
        self.checkout_handler.btn_checkout.setToolTip(tr("checkout_shortcut"))
        self.checkout_handler.btn_clear_cart.setToolTip(tr("clear_cart_shortcut"))
        if self.btn_add_expense:
            self.btn_add_expense.setToolTip("Add Expense (Ctrl+E)")
        table_proxy = getattr(self.cart_widget, "table", None)
        if table_proxy and hasattr(table_proxy, "setToolTip"):
            table_proxy.setToolTip(tr("remove_selected_cart_item_shortcut"))
        else:
            self.cart_widget.setToolTip(tr("remove_selected_cart_item_shortcut"))

    def refresh_categories(self):
        """Refresh categories in product grid"""
        if hasattr(self, 'product_grid'):
            self.product_grid.load_categories()
            logger.info("Sales page product grid categories refreshed")

    def update_theme(self):
        """Refresh sales page widgets that keep their own stylesheet."""
        self._apply_root_theme_style()
        if hasattr(self, 'product_grid'):
            self.product_grid.update_theme()
        self._make_group_compact(self.totals_widget.discount_group, hide_title=True)
        self._make_group_compact(self.totals_widget.loyalty_group, hide_title=True)
        self._make_group_compact(self.totals_widget.totals_group, hide_title=True)
        self.options_widget.hide_title = True
        self._make_group_compact(self.options_widget, hide_title=True)
        self._make_group_compact(self.payment_widget, hide_title=True)
        if hasattr(self.totals_widget, 'update_theme'):
            self.totals_widget.update_theme()
        if hasattr(self.payment_widget, 'update_theme'):
            self.payment_widget.update_theme()
        if hasattr(self.options_widget, 'update_theme'):
            self.options_widget.update_theme()
        self._apply_details_toggle_style()
        if self.btn_customer_display and hasattr(self.btn_customer_display, 'update_theme'):
            self.btn_customer_display.update_theme()
        if self.btn_cash_drawer and hasattr(self.btn_cash_drawer, 'update_theme'):
            self.btn_cash_drawer.update_theme()
        if self.customer_display and hasattr(self.customer_display, 'apply_theme_style'):
            self.customer_display.apply_theme_style()
            self.customer_display.refresh_display()
        # Update customer combo theme
        self.update_customer_combo_style()
        self._hide_original_details_widgets()

    def _apply_root_theme_style(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QWidget#salesPage {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
        """)
        if self.right_container:
            self.right_container.setStyleSheet("""
                QWidget#salesRightContainer {
                    background-color: transparent;
                }
            """)
        if self.details_panel:
            self.details_panel.setStyleSheet("background-color: transparent;")

    def on_theme_changed(self, theme_name):
        """Handle theme change from theme manager"""
        self.update_theme()

    def update_customer_combo_style(self):
        """Update customer combo box style based on current theme"""
        if is_dark_theme():
            self.customer_combo.setStyleSheet("""
                QComboBox {
                    background-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 4px;
                    padding: 5px 8px;
                    color: #dcddde;
                    min-height: 20px;
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
                    background-color: #2f3136 !important;
                    border: 1px solid #40444b !important;
                    border-radius: 4px !important;
                    color: #dcddde !important;
                    selection-background-color: #5865f2 !important;
                    selection-color: white !important;
                    outline: none !important;
                    padding: 4px !important;
                }
                QComboBox QAbstractItemView::item {
                    background-color: transparent !important;
                    color: #dcddde !important;
                    padding: 6px 10px !important;
                    border: none !important;
                    border-radius: 2px !important;
                    min-height: 24px !important;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #40444b !important;
                    color: #dcddde !important;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #5865f2 !important;
                    color: white !important;
                }
            """)
        else:
            self.customer_combo.setStyleSheet("""
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 5px 8px;
                    color: #212529;
                    min-height: 20px;
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
                    border-top: 4px solid #495057;
                    margin-right: 4px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff !important;
                    border: 1px solid #ced4da !important;
                    border-radius: 4px !important;
                    color: #212529 !important;
                    selection-background-color: #5865f2 !important;
                    selection-color: white !important;
                    outline: none !important;
                    padding: 4px !important;
                }
                QComboBox QAbstractItemView::item {
                    background-color: transparent !important;
                    color: #212529 !important;
                    padding: 6px 10px !important;
                    border: none !important;
                    border-radius: 2px !important;
                    min-height: 24px !important;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #e9ecef !important;
                    color: #212529 !important;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #5865f2 !important;
                    color: white !important;
                }
            """)

    def setup_customer_section(self):
        """Setup customer section with combo box and display button - aligned to right"""
        self.customer_layout = QHBoxLayout()
        self.customer_layout.setSpacing(5)
        self.customer_layout.setContentsMargins(0, 2, 0, 2)
        
        self.customer_layout.addStretch()
        
        self.customer_label = QLabel("Customer:")
        self.customer_layout.addWidget(self.customer_label)
        
        self.customer_combo = QComboBox()
        self.customer_combo.addItem("Walk-in Customer (no loyalty)", None)
        self.customer_combo.currentIndexChanged.connect(self.on_customer_changed)
        self.customer_combo.setMinimumWidth(180)
        
        # Apply initial style
        self.update_customer_combo_style()
        
        self.customer_layout.addWidget(self.customer_combo)
        
        self.btn_customer_display = None
        self.btn_cash_drawer = None

    def load_settings(self):
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
        self.totals_widget.load_discount_settings(self.discount_enabled, self.discount_type, self.discount_default_value)
        self.publish_customer_display_state()

    def load_loyalty_settings(self):
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
            self.totals_widget.set_loyalty_params(points_per_dollar, expiry_months, point_value)
        except Exception as e:
            logger.error(f"Failed to load loyalty settings: {e}")

    def load_customers(self):
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem(tr("walk_in_customer"), None)
        customers = load_customers()
        for cust_id, name, points in customers:
            self.customer_combo.addItem(f"{name} (Points: {points})", cust_id)
        self.customer_combo.blockSignals(False)

    def load_payment_types(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM payment_types ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
            types = [row[0] for row in rows] if rows else ["Cash", "Card", "Mobile Money"]
            self.payment_widget.load_payment_types(types)
        except Exception as e:
            logger.error(f"Failed to load payment types: {e}")
            self.payment_widget.load_payment_types(["Cash", "Card", "Mobile Money"])

    def on_customer_changed(self):
        data = self.customer_combo.currentData()
        self.checkout_handler.selected_customer_id = data if data is not None else None
        self.checkout_handler.load_customer_points()
        self.checkout_handler.load_customer_credit_balance()
        self.totals_widget.update_totals()
        self.publish_customer_display_state()

    def load_receipt_settings(self):
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
        self.publish_customer_display_state()

    def load_cart(self):
        if hasattr(self, 'cart_widget'):
            self.cart_widget.refresh_table()

    def update_totals(self):
        if hasattr(self, 'totals_widget'):
            self.totals_widget.update_totals()

    def show_customer_display(self):
        """Show the customer display window"""
        if self.customer_display is None:
            from ui import CustomerDisplayWindow

            self.customer_display = CustomerDisplayWindow(self)
            self.customer_display.show()
            if self.btn_customer_display:
                self.btn_customer_display.setChecked(True)
                self.btn_customer_display.setToolTip(tr("hide_customer_display"))
            logger.info("Customer display opened")
            self._show_customer_display_message(True)
        else:
            self.close_customer_display()

    def close_customer_display(self):
        """Close the customer display window"""
        if self.customer_display:
            self.customer_display.close()
            self.customer_display = None
            if self.btn_customer_display:
                self.btn_customer_display.setChecked(False)
                self.btn_customer_display.setToolTip(tr("show_customer_display"))
            logger.info("Customer display closed")
            self._show_customer_display_message(False)

    def _show_customer_display_message(self, enabled):
        """Show user feedback after customer display is toggled."""
        if lang.get_current() == "my":
            message = "Customer Display ဖွင့်ပြီးပါပြီ။" if enabled else "Customer Display ပိတ်ပြီးပါပြီ။"
        else:
            message = "Customer Display is on." if enabled else "Customer Display is off."
        QMessageBox.information(self, "Customer Display", message)

    def toggle_customer_display(self):
        """Toggle customer display on/off"""
        if self.customer_display:
            self.close_customer_display()
        else:
            self.show_customer_display()

    def open_cash_drawer(self):
        """Open the cash drawer through the default receipt printer."""
        default_printer = QPrinterInfo.defaultPrinter()
        if default_printer.isNull():
            QMessageBox.warning(self, tr("cash_drawer"), tr("no_default_printer_found"))
            logger.warning("Cash drawer open failed: no default printer found")
            return

        printer_name = default_printer.printerName()
        try:
            self._send_cash_drawer_pulse(printer_name)
            logger.info(f"Cash drawer open command sent to printer: {printer_name}")
        except Exception as e:
            logger.error(f"Cash drawer open failed: {e}")
            QMessageBox.warning(
                self,
                tr("cash_drawer"),
                tr("cash_drawer_open_failed"),
            )

    def _send_cash_drawer_pulse(self, printer_name):
        """Send ESC/POS drawer kick command to a Windows printer queue."""
        drawer_kick_command = b"\x1b\x70\x00\x19\xfa"
        winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)

        class DOC_INFO_1(ctypes.Structure):
            _fields_ = [
                ("pDocName", ctypes.c_wchar_p),
                ("pOutputFile", ctypes.c_wchar_p),
                ("pDatatype", ctypes.c_wchar_p),
            ]

        h_printer = ctypes.c_void_p()
        if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(h_printer), None):
            raise ctypes.WinError(ctypes.get_last_error())

        try:
            doc_info = DOC_INFO_1("Open Cash Drawer", None, "RAW")
            if not winspool.StartDocPrinterW(h_printer, 1, ctypes.byref(doc_info)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not winspool.StartPagePrinter(h_printer):
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    written = ctypes.c_ulong(0)
                    buffer = ctypes.create_string_buffer(drawer_kick_command)
                    if not winspool.WritePrinter(
                        h_printer,
                        buffer,
                        len(drawer_kick_command),
                        ctypes.byref(written),
                    ):
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    winspool.EndPagePrinter(h_printer)
            finally:
                winspool.EndDocPrinter(h_printer)
        finally:
            winspool.ClosePrinter(h_printer)

    def refresh_customer_display(self):
        """Refresh customer display when cart changes"""
        if self.customer_display:
            self.customer_display.refresh_display()
        self.publish_customer_display_state()

    def get_customer_display_state(self):
        """Build the LAN customer display JSON payload from the current sale."""
        symbol = get_currency_symbol()
        cart_items = []
        subtotal = 0.0

        for item in self.cart_widget.get_cart():
            qty = int(item.get("qty") or 0)
            price = float(item.get("price") or 0)
            line_total = price * qty
            subtotal += line_total
            cart_items.append({
                "id": item.get("id"),
                "name": str(item.get("name") or ""),
                "qty": qty,
                "price": price,
                "total": line_total,
                "is_service": bool(item.get("is_service", False)),
            })

        reg_discount = self.totals_widget.compute_regular_discount(subtotal)
        points_discount = self.totals_widget.compute_points_discount(subtotal)
        discount = reg_discount + points_discount
        after_discount = max(subtotal - discount, 0.0)

        tax = 0.0
        if getattr(self, "tax_enabled", False):
            tax = after_discount * (float(getattr(self, "tax_rate", 0.0)) / 100.0)

        grand_total = after_discount + tax
        payment = self.payment_widget.get_payment_amount()
        change = payment - grand_total
        customer_id = getattr(self.checkout_handler, "selected_customer_id", None)

        shop_info = {
            "name": getattr(self, "shop_name", "") or "ZAY POS",
            "phone": "",
            "address": "",
            "footer": getattr(self, "receipt_footer_text", "") or "",
        }
        customer_name = ""

        conn = None
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM settings WHERE key IN ('shop_name', 'shop_phone', 'shop_address', 'shop_footer_message')"
            )
            settings = dict(cursor.fetchall())
            shop_info["name"] = settings.get("shop_name") or shop_info["name"]
            shop_info["phone"] = settings.get("shop_phone") or ""
            shop_info["address"] = settings.get("shop_address") or ""
            shop_info["footer"] = settings.get("shop_footer_message") or shop_info["footer"]
            if customer_id:
                cursor.execute("SELECT name FROM customers WHERE id = ?", (customer_id,))
                row = cursor.fetchone()
                customer_name = row[0] if row else ""
        except Exception as exc:
            logger.debug(f"Could not load customer display metadata: {exc}")
        finally:
            if conn:
                conn.close()

        return {
            "status": "active" if cart_items else "idle",
            "shop": shop_info,
            "customer": {
                "id": customer_id,
                "name": customer_name,
            },
            "currency_symbol": symbol,
            "items": cart_items,
            "item_count": sum(item["qty"] for item in cart_items),
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax,
            "grand_total": grand_total,
            "payment": payment,
            "change": change,
            "payment_type": self.payment_widget.get_selected_payment_type(),
        }

    def publish_customer_display_state(self):
        return

    def customer_display_closed(self):
        """Called when customer display is closed"""
        self.customer_display = None
        if self.btn_customer_display:
            self.btn_customer_display.setChecked(False)
            self.btn_customer_display.setToolTip(tr("show_customer_display"))
        logger.info("Customer display closed by user")

    def retranslateUi(self):
        self.customer_label.setText(tr("customer"))
        if self.btn_customer_display:
            self.btn_customer_display.setToolTip(self._customer_display_tooltip())
        if self.btn_cash_drawer:
            self.btn_cash_drawer.setToolTip(tr("open_cash_drawer"))
        self.product_grid.retranslateUi()
        self.cart_widget.retranslateUi()
        self.totals_widget.retranslateUi()
        self.payment_widget.retranslateUi()
        self.options_widget.retranslateUi()
        self.checkout_handler.retranslateUi()
        if self.btn_toggle_details:
            self.btn_toggle_details.setText("Sale Details")
        if self.btn_add_expense:
            self.btn_add_expense.setText("Add Expense")
        self.update_shortcut_tooltips()

    def showEvent(self, event):
        self._hide_original_details_widgets()
        main_window = self.window()
        if hasattr(main_window, "page_title") and main_window.page_title:
            main_window.page_title.setText("Sales")
        self.product_grid.load_products()
        self.load_customers()
        self.load_payment_types()
        self.product_grid.focus_search()
        # Update combo style on show
        self.update_customer_combo_style()
        super().showEvent(event)

    def clear_cart(self):
        if self.cart_widget.cart:
            reply = QMessageBox.question(self, "Clear Cart", "Remove all items?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.cart_widget.clear()
                self.totals_widget.discount_checkbox.setChecked(False)
                self.totals_widget.points_use_check.setChecked(False)
                self.payment_widget.payment_input.setValue(0.0)
                self.payment_widget.reset_manual_override()
                self.payment_widget.reset_to_default()
                self.options_widget.set_payment_type("Cash")
                self.payment_widget.setEnabled(True)
                self.product_grid.focus_search()
                self.customer_combo.setCurrentIndex(0)
                self.checkout_handler.selected_customer_id = None
