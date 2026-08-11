# ui/sales_page/checkout_handler/checkout_handler.py
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QBrush, QPainter, QPen
from datetime import datetime
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.sales_page.cart_widget import delete_cart_backup
from services.credit_service import CreditService
from loguru import logger
from utils.language import lang
from utils.translations import tr
from utils.db_compat import begin_transaction_sql
from utils.held_sales import create_held_sale, delete_held_sale, get_held_sale, list_held_sales

from ui.sales_page.checkout_handler.checkout_dialogs import (
    CompletionDialog,
    ExpiredItemsDialog,
    ExpiryWarningDialog
)
from ui.sales_page.checkout_handler.checkout_helpers import CheckoutHelpers
from ui.sales_page.checkout_handler.checkout_processor import CheckoutProcessor
from ui.sales_page.checkout_handler.checkout_utils import (
    open_cash_drawer,
    print_receipt
)


class GradientButton(QPushButton):
    """Custom QPushButton with gradient background and hover animation"""
    
    def __init__(self, text, gradient_colors, hover_gradient_colors=None, parent=None):
        super().__init__(text, parent)
        self._gradient_colors = gradient_colors
        self._hover_gradient_colors = hover_gradient_colors or gradient_colors
        self._is_hovered = False
        
        # Animation for hover effect
        self._hover_animation = QPropertyAnimation(self, b"geometry")
        self._hover_animation.setDuration(150)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Remove default styling
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                color: white;
                font-weight: bold;
            }
        """)
        
        # Enable mouse tracking for hover
        self.setMouseTracking(True)
        
    def paintEvent(self, event):
        """Paint gradient background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create gradient - Use QPointF
        rect = self.rect()
        gradient = QLinearGradient(
            QPointF(rect.topLeft()),
            QPointF(rect.bottomRight())
        )
        
        # Choose colors based on hover state
        colors = self._hover_gradient_colors if self._is_hovered else self._gradient_colors
        
        if colors and len(colors) >= 2:
            for i, color in enumerate(colors):
                gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        else:
            gradient.setColorAt(0, QColor("#2ecc71"))
            gradient.setColorAt(1, QColor("#27ae60"))
        
        # Draw background
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 6, 6)
        
        # Draw text
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
        
        painter.end()
    
    def enterEvent(self, event):
        """Handle mouse enter - update gradient"""
        self._is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave - revert gradient"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)


class CheckoutHandler(QObject):
    checkout_completed = pyqtSignal()

    def __init__(self, parent: Any):
        super().__init__(parent)
        self.parent_widget: Any = parent
        self.selected_customer_id: Any = None
        self.points_available = 0
        self.credit_balance = 0
        self.credit_limit = 0
        self.tax_rate = 0.0
        self.tax_enabled = False
        self.points_per_dollar = 0.0
        self.points_expiry_months = 12
        self.credit_payment_type = "Credit"
        self.credit_due_days = 15
        self.credit_limit_enabled = True
        self.credit_service = CreditService()
        self.last_sale_result = None
        
        # Prevent duplicate credit info dialog
        self._credit_info_shown = False
        
        # Helpers and processors
        self.helpers = CheckoutHelpers(parent)
        self.processor = CheckoutProcessor(parent, self)

        # Load credit settings
        self.load_credit_settings()

        # Setup UI
        self._setup_ui()

    def _setup_ui(self):
        """Setup action group UI - No border, no background, no title"""
        self.action_group = QWidget()
        self.action_group.setStyleSheet("background: transparent;")
        
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)
        action_layout.setContentsMargins(0, 0, 0, 0)

        utility_layout = QHBoxLayout()
        utility_layout.setSpacing(8)

        self.btn_hold_sale = GradientButton(
            "Hold",
            gradient_colors=["#f39c12", "#d68910"],
            hover_gradient_colors=["#e67e22", "#b9770e"]
        )
        self.btn_hold_sale.setFixedHeight(40)
        self.btn_hold_sale.clicked.connect(self.hold_sale)

        self.btn_resume_sale = GradientButton(
            "Resume",
            gradient_colors=["#3498db", "#2471a3"],
            hover_gradient_colors=["#2e86c1", "#1f618d"]
        )
        self.btn_resume_sale.setFixedHeight(40)
        self.btn_resume_sale.clicked.connect(self.resume_sale)

        utility_layout.addWidget(self.btn_hold_sale, stretch=1)
        utility_layout.addWidget(self.btn_resume_sale, stretch=1)
        
        # Buttons Layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # Checkout Button (Green Gradient)
        self.btn_checkout = GradientButton(
            "Checkout",
            gradient_colors=["#2ecc71", "#1a9c54"],
            hover_gradient_colors=["#27ae60", "#1a7a42"]
        )
        self.btn_checkout.setFixedHeight(100)
        self.btn_checkout.clicked.connect(self.checkout)
        
        # Clear Cart Button (Red Gradient)
        self.btn_clear_cart = GradientButton(
            "Clear Cart",
            gradient_colors=["#e74c3c", "#c0392b"],
            hover_gradient_colors=["#c0392b", "#922b21"]
        )
        self.btn_clear_cart.setFixedHeight(100)
        self.btn_clear_cart.clicked.connect(self.clear_cart)
        
        # Clear Cart is available in the cart header, so keep this button for
        # compatibility but do not show it beside Checkout.
        self.btn_clear_cart.setVisible(False)
        button_layout.addWidget(self.btn_checkout, stretch=1)
        
        action_layout.addLayout(utility_layout)
        action_layout.addLayout(button_layout)
        self.action_group.setLayout(action_layout)

    def load_credit_settings(self):
        """Load credit settings from database"""
        try:
            settings = self.credit_service.get_credit_settings()
            self.credit_due_days = settings.get('credit_due_days', 15)
            self.credit_limit_enabled = settings.get('credit_limit_enabled', True)
        except Exception as e:
            logger.warning(f"Failed to load credit settings: {e}")
            self.credit_due_days = 15
            self.credit_limit_enabled = True

    def on_payment_type_changed(self, payment_type):
        """Handle payment type change from options widget"""
        if payment_type == "Credit":
            self._handle_credit_selected()
        else:
            self._handle_cash_selected()

    def _handle_cash_selected(self):
        """Handle Cash selection"""
        self._credit_info_shown = False
        self.parent_widget.payment_widget.setEnabled(True)
        grand_total = self.parent_widget.totals_widget.get_current_grand_total()
        self.parent_widget.payment_widget.auto_set_payment(grand_total)

    def _handle_credit_selected(self):
        """Handle Credit selection - only if customer selected"""
        self._credit_info_shown = False
        
        if not self.selected_customer_id:
            self.parent_widget.options_widget.set_payment_type("Cash")
            self.parent_widget.payment_widget.setEnabled(True)
            
            lang_code = lang.get_current()
            if lang_code == "my":
                msg = "ကျေးဇူးပြု၍ ဝယ်ယူသူတစ်ဦးကို ရွေးချယ်ပါ။ အကြွေးရောင်းချရန်အတွက် ဝယ်ယူသူ လိုအပ်ပါသည်။"
            else:
                msg = "Please select a customer. Credit sale requires a customer."
            QMessageBox.warning(self.parent_widget, "Customer Required", msg)
            self.parent_widget.customer_combo.setFocus()
            self.parent_widget.customer_combo.showPopup()
            return
        
        self.parent_widget.payment_widget.setEnabled(False)
        self.parent_widget.payment_widget.payment_input.setValue(0)
        self.show_credit_info()

    def show_credit_info(self):
        """Show credit balance information"""
        if self._credit_info_shown:
            return
        
        if self.selected_customer_id:
            self._credit_info_shown = True
            symbol = get_currency_symbol()
            lang_code = lang.get_current()
            
            if lang_code == "my":
                msg = f"🔄 အကြွေးရောင်းချမှု မုဒ်\n\n"
                msg += f"👤 ဝယ်ယူသူ: {self.parent_widget.customer_combo.currentText()}\n"
                msg += f"💰 လက်ကျန်အကြွေး: {format_money(self.credit_balance, symbol)}\n"
                if self.credit_limit > 0:
                    msg += f"📊 ခရက်ဒစ်ကန့်သတ်ချက်: {format_money(self.credit_limit, symbol)}\n"
                msg += f"\n✅ အကြွေးဖြင့် ရောင်းချမည်ဖြစ်သည်။"
            else:
                msg = f"🔄 Credit Sale Mode\n\n"
                msg += f"👤 Customer: {self.parent_widget.customer_combo.currentText()}\n"
                msg += f"💰 Current Balance: {format_money(self.credit_balance, symbol)}\n"
                if self.credit_limit > 0:
                    msg += f"📊 Credit Limit: {format_money(self.credit_limit, symbol)}\n"
                msg += f"\n✅ Proceeding with credit sale."
            
            QMessageBox.information(self.parent_widget, "Credit Info", msg)
            
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: setattr(self, '_credit_info_shown', False))

    def update_credit_radio_state(self):
        """Update credit radio state based on customer selection"""
        has_customer = self.selected_customer_id is not None
        self.parent_widget.options_widget.set_customer_selected(has_customer)
        
        if not has_customer and self.parent_widget.options_widget.is_credit_sale():
            self.parent_widget.options_widget.set_payment_type("Cash")
            self.parent_widget.payment_widget.setEnabled(True)
            self._credit_info_shown = False

    def load_customer_points(self):
        """Load customer points"""
        if self.selected_customer_id:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT points FROM customers WHERE id = ?", (self.selected_customer_id,))
            row = cursor.fetchone()
            self.points_available = row[0] if row else 0
            conn.close()
        else:
            self.points_available = 0
        self.parent_widget.totals_widget.set_customer_points(self.points_available)
        self.update_credit_radio_state()

    def load_customer_credit_balance(self):
        """Load customer credit balance"""
        if self.selected_customer_id:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT current_balance, credit_limit FROM customers WHERE id = ?", 
                          (self.selected_customer_id,))
            row = cursor.fetchone()
            if row:
                self.credit_balance = row[0] if row[0] else 0
                self.credit_limit = row[1] if row[1] else 0
            else:
                self.credit_balance = 0
                self.credit_limit = 0
            conn.close()
        else:
            self.credit_balance = 0
            self.credit_limit = 0
        
        self.update_credit_radio_state()
        self._credit_info_shown = False

    def _get_selected_customer_name(self):
        combo = getattr(self.parent_widget, "customer_combo", None)
        if not combo or combo.currentIndex() <= 0:
            return ""
        return combo.currentText()

    def _reset_sale_inputs(self, reset_customer=True):
        """Reset the active POS entry area without refreshing inventory pages."""
        self.parent_widget.cart_widget.clear()
        delete_cart_backup()
        self.parent_widget.totals_widget.discount_checkbox.setChecked(False)
        self.parent_widget.totals_widget.points_use_check.setChecked(False)
        self.parent_widget.payment_widget.payment_input.setValue(0.0)
        self.parent_widget.payment_widget.reset_manual_override()
        self.parent_widget.payment_widget.reset_to_default()
        self.parent_widget.options_widget.set_payment_type("Cash")
        self.parent_widget.payment_widget.setEnabled(True)
        if reset_customer and hasattr(self.parent_widget, "customer_combo"):
            self.parent_widget.customer_combo.setCurrentIndex(0)
            self.selected_customer_id = None
        self._credit_info_shown = False
        self.update_credit_radio_state()
        if hasattr(self.parent_widget, "product_grid"):
            self.parent_widget.product_grid.focus_search()

    def hold_sale(self):
        """Suspend the current cart so another sale can be served first."""
        cart = self.parent_widget.cart_widget.get_cart()
        if not cart:
            QMessageBox.information(self.parent_widget, "Hold Sale", "Cart is empty.")
            return

        note, ok = QInputDialog.getText(
            self.parent_widget,
            "Hold Sale",
            "Note / customer reference:",
        )
        if not ok:
            return

        try:
            customer_id = self.selected_customer_id
            customer_name = self._get_selected_customer_name()
            payment_type = "Credit" if self.parent_widget.options_widget.is_credit_sale() else "Cash"
            total_amount = self.parent_widget.totals_widget.get_current_grand_total()
            _, hold_no = create_held_sale(
                cart,
                customer_id=customer_id,
                customer_name=customer_name,
                payment_type=payment_type,
                note=note.strip(),
                total_amount=total_amount,
            )
            self._reset_sale_inputs(reset_customer=True)
            QMessageBox.information(self.parent_widget, "Hold Sale", f"Sale held: {hold_no}")
        except Exception as e:
            logger.error(f"Failed to hold sale: {e}", exc_info=True)
            QMessageBox.critical(self.parent_widget, "Hold Sale", f"Could not hold sale: {e}")

    def _select_held_sale_id(self):
        rows = list_held_sales()
        if not rows:
            QMessageBox.information(self.parent_widget, "Resume Sale", "No held sales found.")
            return None

        dialog = QDialog(self.parent_widget)
        dialog.setWindowTitle("Resume Held Sale")
        dialog.resize(760, 360)
        layout = QVBoxLayout(dialog)

        table = QTableWidget(len(rows), 7, dialog)
        table.setHorizontalHeaderLabels(["ID", "Hold No", "Customer", "Items", "Total", "Note", "Created"])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setColumnHidden(0, True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        symbol = get_currency_symbol()
        for row_idx, row in enumerate(rows):
            held_id, hold_no, customer_name, item_count, total_amount, note, created_at = row
            values = [
                str(held_id),
                hold_no or "",
                customer_name or "-",
                str(item_count or 0),
                format_money(float(total_amount or 0), symbol),
                note or "",
                str(created_at or ""),
            ]
            for col_idx, value in enumerate(values):
                table.setItem(row_idx, col_idx, QTableWidgetItem(value))

        table.selectRow(0)
        table.doubleClicked.connect(dialog.accept)
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        selected = table.currentRow()
        if selected < 0:
            return None
        item = table.item(selected, 0)
        return int(item.text()) if item else None

    def resume_sale(self):
        """Load a held cart back into the active checkout."""
        try:
            held_id = self._select_held_sale_id()
            if not held_id:
                return

            if self.parent_widget.cart_widget.cart:
                reply = QMessageBox.question(
                    self.parent_widget,
                    "Resume Sale",
                    "Replace the current cart with the held sale?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            held_sale = get_held_sale(held_id)
            if not held_sale:
                QMessageBox.warning(self.parent_widget, "Resume Sale", "Held sale was not found.")
                return

            self.parent_widget.cart_widget.cart = held_sale["cart"]
            self.parent_widget.cart_widget.refresh_table()
            delete_held_sale(held_id)

            combo = getattr(self.parent_widget, "customer_combo", None)
            self.selected_customer_id = held_sale.get("customer_id")
            if combo and self.selected_customer_id:
                index = combo.findData(self.selected_customer_id)
                if index >= 0:
                    combo.setCurrentIndex(index)
            elif combo:
                combo.setCurrentIndex(0)

            if held_sale.get("payment_type") == "Credit" and self.selected_customer_id:
                self.parent_widget.options_widget.set_payment_type("Credit")
            else:
                self.parent_widget.options_widget.set_payment_type("Cash")
                self.parent_widget.payment_widget.setEnabled(True)
            self.parent_widget.payment_widget.reset_manual_override()
            self.parent_widget.payment_widget.reset_to_default()
            self.update_credit_radio_state()
            if hasattr(self.parent_widget, "product_grid"):
                self.parent_widget.product_grid.focus_search()
            QMessageBox.information(self.parent_widget, "Resume Sale", f"Resumed {held_sale['hold_no']}.")
        except Exception as e:
            logger.error(f"Failed to resume sale: {e}", exc_info=True)
            QMessageBox.critical(self.parent_widget, "Resume Sale", f"Could not resume sale: {e}")

    def clear_cart(self):
        """Clear cart"""
        if self.parent_widget.cart_widget.cart:
            reply = QMessageBox.question(self.parent_widget, "Clear Cart", "Remove all items?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.parent_widget.cart_widget.clear()
                self.parent_widget.totals_widget.discount_checkbox.setChecked(False)
                self.parent_widget.totals_widget.points_use_check.setChecked(False)
                self.parent_widget.payment_widget.payment_input.setValue(0.0)
                self.parent_widget.payment_widget.reset_manual_override()
                self.parent_widget.options_widget.set_payment_type("Cash")
                self.parent_widget.payment_widget.setEnabled(True)
                self.parent_widget.product_grid.focus_search()
                self.parent_widget.customer_combo.setCurrentIndex(0)
                self.selected_customer_id = None
                self._credit_info_shown = False
                self.update_credit_radio_state()

    def check_credit_limit(self, amount):
        """Check if credit sale exceeds customer credit limit"""
        if not self.selected_customer_id:
            return True
        
        result = self.credit_service.check_credit_limit(self.selected_customer_id, amount)
        
        if result.get('exceeded', False):
            symbol = get_currency_symbol()
            lang_code = lang.get_current()
            
            if lang_code == "my":
                msg = (f"ခရက်ဒစ်ကန့်သတ်ချက် ကျော်လွန်နေသည်!\n\n"
                       f"ကန့်သတ်ချက်: {format_money(result['credit_limit'], symbol)}\n"
                       f"လက်ရှိကျန်: {format_money(result['current_balance'], symbol)}\n"
                       f"ဤရောင်းချမှု: {format_money(amount, symbol)}\n"
                       f"အသစ်ကျန်: {format_money(result['new_balance'], symbol)}\n\n"
                       f"ဆက်လုပ်မည်လား?")
            else:
                msg = (f"Credit limit exceeded!\n\n"
                       f"Limit: {format_money(result['credit_limit'], symbol)}\n"
                       f"Current balance: {format_money(result['current_balance'], symbol)}\n"
                       f"This sale: {format_money(amount, symbol)}\n"
                       f"New balance: {format_money(result['new_balance'], symbol)}\n\n"
                       f"Proceed anyway?")
            
            reply = QMessageBox.warning(
                self.parent_widget, 
                "Credit Limit Warning", 
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        
        return True

    # =========================================================================
    # MAIN CHECKOUT
    # =========================================================================
    def checkout(self):
        """Main checkout method"""
        self.last_sale_result = None
        cart = self.parent_widget.cart_widget.get_cart()
        if not cart:
            QMessageBox.warning(self.parent_widget, tr("empty_cart"), "Cart is empty")
            return None

        symbol = get_currency_symbol()
        grand_total = self.parent_widget.totals_widget.get_current_grand_total()
        
        # Check credit sale
        is_credit_sale = self.parent_widget.options_widget.is_credit_sale() and self.selected_customer_id
        
        # Handle credit selected without customer
        if self.parent_widget.options_widget.is_credit_sale() and not self.selected_customer_id:
            lang_code = lang.get_current()
            if lang_code == "my":
                msg = "အကြွေးရောင်းချရန်အတွက် ဝယ်ယူသူတစ်ဦးကို ရွေးချယ်ရန် လိုအပ်ပါသည်။ ငွေသားဖြင့် ဆက်လက်မည်။"
            else:
                msg = "Please select a customer for credit sale. Switching to Cash."
            QMessageBox.warning(self.parent_widget, "Customer Required", msg)
            self.parent_widget.options_widget.set_payment_type("Cash")
            self.parent_widget.payment_widget.setEnabled(True)
            grand_total = self.parent_widget.totals_widget.get_current_grand_total()
            self.parent_widget.payment_widget.auto_set_payment(grand_total)
            is_credit_sale = False
        
        # Handle credit sale
        if is_credit_sale:
            if not self.check_credit_limit(grand_total):
                return None
            payment = 0
            change = 0
            payment_type = "Credit"
        else:
            payment = self.parent_widget.payment_widget.get_payment_amount()
            if payment < grand_total:
                QMessageBox.warning(self.parent_widget, tr("insufficient_payment"),
                    f"Payment ({format_money(payment, symbol)}) < Total ({format_money(grand_total, symbol)})")
                return None
            change = payment - grand_total
            payment_type = self.parent_widget.payment_widget.get_selected_payment_type()

        # Generate invoice
        invoice_no = datetime.now().strftime("INV%Y%m%d%H%M%S")
        local_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Calculate totals
        subtotal = self.parent_widget.cart_widget.compute_subtotal()
        reg_discount = self.parent_widget.totals_widget.compute_regular_discount(subtotal)
        points_discount = self.parent_widget.totals_widget.compute_points_discount(subtotal)
        total_discount = reg_discount + points_discount

        conn = connect_db()
        cursor = conn.cursor()
        
        # Track sale success
        sale_successful = False
        sale_result = None
        
        try:
            cursor.execute(begin_transaction_sql(immediate=True))

            # Check expiry issues
            valid, expired_items, warning_items, all_expired_blocked = self.helpers.check_expiry_issues(cart)
            if not valid or all_expired_blocked:
                if expired_items:
                    dialog = ExpiredItemsDialog(self.parent_widget, expired_items, warning_items)
                    if dialog.exec() == ExpiredItemsDialog.DialogCode.Accepted:
                        expired_names = set(item['name'] for item in expired_items)
                        new_cart = [item for item in cart if item['name'] not in expired_names]
                        self.parent_widget.cart_widget.cart = new_cart
                        self.parent_widget.cart_widget.refresh_table()
                        self.parent_widget.totals_widget.update_totals()
                    conn.rollback()
                    return None
                else:
                    conn.rollback()
                    return None
            
            # Show expiry warning
            if warning_items:
                dialog = ExpiryWarningDialog(self.parent_widget, warning_items)
                if dialog.exec() == ExpiryWarningDialog.DialogCode.Rejected:
                    conn.rollback()
                    return None
            
            # Process stock deduction
            self.helpers.process_stock_deduction(cursor, cart, invoice_no)

            # Create sale record
            sale_id = self.processor.create_sale_record(
                cursor, invoice_no, grand_total, payment, change, 
                payment_type, local_now, total_discount
            )

            # Create sale items
            self.processor.create_sale_items(cursor, sale_id, cart)

            # Process credit or cash sale
            if is_credit_sale:
                self.processor.process_credit_sale(conn, cursor, invoice_no, grand_total, sale_id)
            else:
                self.processor.process_cash_sale(conn, cursor, grand_total, invoice_no)

            conn.commit()
            logger.info(f"Sale completed. Invoice: {invoice_no}")
            delete_cart_backup()
            
            sale_successful = True
            sale_result = {
                "sale_id": sale_id,
                "invoice_no": invoice_no,
                "grand_total": grand_total,
                "payment": payment,
                "change": change,
                "payment_type": payment_type,
                "is_credit_sale": is_credit_sale,
            }
            self.last_sale_result = sale_result

            # Show completion dialog
            self._show_completion_dialog(sale_id, invoice_no, grand_total, payment, change, total_discount, is_credit_sale)

        except Exception as e:
            conn.rollback()
            logger.error(f"Checkout failed: {e}", exc_info=True)
            QMessageBox.critical(self.parent_widget, "Error", f"Checkout failed: {e}")
        finally:
            conn.close()
            
            # Only reset if sale was successful
            if sale_successful:
                self._reset_after_checkout()
            else:
                # If failed, reset only payment but keep cart
                self.parent_widget.payment_widget.reset_manual_override()
                self.parent_widget.payment_widget.reset_to_default()
                self.parent_widget.options_widget.set_payment_type("Cash")
                self.parent_widget.payment_widget.setEnabled(True)
                self.parent_widget.product_grid.focus_search()
                self.update_credit_radio_state()
        return sale_result

    def _reset_after_checkout(self):
        """Reset after successful checkout"""
        self.parent_widget.cart_widget.clear()
        self.parent_widget.totals_widget.discount_checkbox.setChecked(False)
        self.parent_widget.totals_widget.points_use_check.setChecked(False)
        self.parent_widget.payment_widget.reset_manual_override()
        self.parent_widget.payment_widget.reset_to_default()
        self.parent_widget.options_widget.set_payment_type("Cash")
        self.parent_widget.payment_widget.setEnabled(True)
        self.parent_widget.product_grid.focus_search()
        
        # Reset customer
        self.parent_widget.customer_combo.setCurrentIndex(0)
        self.selected_customer_id = None
        self.points_available = 0
        self.credit_balance = 0
        self._credit_info_shown = False
        
        # Refresh data
        self.parent_widget.product_grid.load_products()
        if hasattr(self.parent, 'load_customers'):
            self.parent_widget.load_customers()
        
        # ✅ Fix: Check if main_window exists and has inventory_page before calling
        main_window = self.parent_widget.window()
        if main_window and hasattr(main_window, 'inventory_page') and main_window.inventory_page is not None:
            if hasattr(main_window.inventory_page, 'refresh_all'):
                main_window.inventory_page.refresh_all()
        if main_window and hasattr(main_window, 'check_stock_alerts'):
            main_window.check_stock_alerts()
        if main_window and hasattr(main_window, 'customers_page') and main_window.customers_page is not None:
            if hasattr(main_window.customers_page, 'load_customers'):
                main_window.customers_page.load_customers()
        
        self.update_credit_radio_state()
        logger.info("Cart cleared and reset after checkout")

    def _show_completion_dialog(self, sale_id, invoice_no, grand_total, payment, change, discount, is_credit_sale):
        """Show completion dialog"""
        dialog = CompletionDialog(
            self.parent_widget, sale_id, invoice_no, grand_total, payment, change, discount, is_credit_sale
        )
        
        if dialog.exec() == CompletionDialog.DialogCode.Accepted:
            # Print receipt if selected
            if dialog.is_print_receipt_enabled():
                print_receipt(self.parent_widget, sale_id)
            
            # Open cash drawer if selected
            if dialog.is_open_drawer_enabled():
                open_cash_drawer(self.parent_widget)

    def retranslateUi(self):
        """Update UI language"""
        from utils.language import lang
        if lang.get_current() == "my":
            self.btn_clear_cart.setText("ဈေးခြင်းရှင်း")
            self.btn_checkout.setText("ငွေရှင်းမည်")
        else:
            self.btn_clear_cart.setText("Clear Cart")
            self.btn_checkout.setText("Checkout")
        self.btn_hold_sale.setText("Hold")
        self.btn_resume_sale.setText("Resume")
        
        self.update_credit_radio_state()
