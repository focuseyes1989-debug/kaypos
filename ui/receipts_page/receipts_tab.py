# ui/receipts_page/receipts_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView,
    QComboBox, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.permissions import PermissionManager, Permission
from ui.receipt_detail_dialog import ReceiptDetailDialog
from ui.receipt_dialog import ReceiptDialog
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.search_widget import SearchWidget
from ui.widgets.toast_notification_widget import ToastNotificationWidget
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from services.credit_service import CreditService
import csv
from datetime import datetime
from loguru import logger


class ReceiptsTab(QWidget):
    """Receipts Tab - Theme-aware (uses parent's date range)"""
    
    def __init__(self, user_id=None, user_role=None, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_role = user_role
        self.credit_service = CreditService()
        self._is_dark = is_dark_theme()
        self.parent_page = parent
        
        # Store current date range
        self._current_from_date = None
        self._current_to_date = None
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # ====== Top bar: Search and Filters ======
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(0, 8, 0, 8)
        
        # SearchWidget - ရှာဖွေမှုကို invoice_no, customer_name, payment_type အားလုံးနဲ့ ရှာနိုင်အောင်
        self.search_widget = SearchWidget(
            placeholder="Search by invoice no, customer, or payment type...",
            show_label=True
        )
        self.search_widget.search_changed.connect(self.reset_and_load)
        top_layout.addWidget(self.search_widget, 2)
        
        # Payment type filter
        payment_label = QLabel("Payment:")
        payment_label.setStyleSheet(self._get_label_style())
        top_layout.addWidget(payment_label)
        
        self.payment_filter = QComboBox()
        self.payment_filter.currentTextChanged.connect(self.reset_and_load)
        self.payment_filter.setStyleSheet(self._get_combobox_style())
        top_layout.addWidget(self.payment_filter)
        
        # Customer filter
        customer_label = QLabel("Customer:")
        customer_label.setStyleSheet(self._get_label_style())
        top_layout.addWidget(customer_label)
        
        self.customer_filter = QComboBox()
        self.customer_filter.addItems(["All", "Walk-in", "Registered", "Credit"])
        self.customer_filter.currentTextChanged.connect(self.reset_and_load)
        self.customer_filter.setStyleSheet(self._get_combobox_style())
        top_layout.addWidget(self.customer_filter)
        
        # Export buttons with SVG icons
        self.btn_export_list = ModernButton(" Export List", ModernButton.SECONDARY)
        self.btn_export_list.set_icon("file_export", size=(16, 16))
        self.btn_export_list.set_compact(True)
        self.btn_export_list.clicked.connect(self.export_receipt_list)
        top_layout.addWidget(self.btn_export_list)
        
        self.btn_export_range = ModernButton(" Export Range", ModernButton.SECONDARY)
        self.btn_export_range.set_icon("file_export", size=(16, 16))
        self.btn_export_range.set_compact(True)
        self.btn_export_range.clicked.connect(self.export_receipt_range)
        top_layout.addWidget(self.btn_export_range)
        
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # ====== Table - NO custom style, use PyQt6 default ======
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setColumnHidden(0, True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self.show_receipt_detail)
        self.table.setAlternatingRowColors(True)
        
        # Set row height to accommodate buttons
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.verticalHeader().setMinimumSectionSize(48)

        # ✅ NO custom table style
        # self._update_table_style(colors)  <-- ဒီ line ကို ဖယ်ရှားပါ

        header = self.table.horizontalHeader()
        for col in range(1, 8):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(8, 128)
        self.table.setColumnWidth(9, 120)
        
        layout.addWidget(self.table)

        # ====== Pagination ======
        self.pagination = PaginationWidget()
        self.pagination.set_page_size(100, emit_signal=False)
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        # ====== Toast Notification ======
        self.toast = ToastNotificationWidget(self)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        self.retranslateUi()
        
        # Load payment types from database
        self.load_payment_types()

    def _centered_cell_widget(self, widget):
        container = QWidget()
        container.setObjectName("tableActionCell")
        container.setStyleSheet("background: transparent; border: none;")
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignCenter)
        return container

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_sales()

    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_export_list.set_icon("file_export", size=(16, 16))
        self.btn_export_range.set_icon("file_export", size=(16, 16))

    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # ✅ NO table style update
        # self._update_table_style(colors)  <-- ဒီ line ကို ဖယ်ရှားပါ
        
        # Update comboboxes
        if hasattr(self, 'payment_filter'):
            self.payment_filter.setStyleSheet(self._get_combobox_style())
        if hasattr(self, 'customer_filter'):
            self.customer_filter.setStyleSheet(self._get_combobox_style())
        
        # Update labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update button icons
        self._update_button_icons()
    
    def _get_label_style(self):
        colors = get_theme_colors()
        return f"color: {colors['text']}; font-size: 10pt;"
    
    def _get_combobox_style(self):
        colors = get_theme_colors()
        return f"""
            QComboBox {{
                padding: 5px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 9pt;
                min-width: 90px;
                max-height: 32px;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 8px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """

    # ---------- Load Payment Types ----------
    def load_payment_types(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM payment_types ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        
        self.payment_filter.blockSignals(True)
        lang = self.get_lang()
        self.payment_filter.clear()
        self.payment_filter.addItem("All" if lang != "my" else "အားလုံး")
        
        for row in rows:
            self.payment_filter.addItem(row[0])
        self.payment_filter.blockSignals(False)

    # ---------- Language ----------
    def get_lang(self):
        from utils.language import lang
        return lang.get_current()

    def retranslateUi(self):
        lang = self.get_lang()
        colors = get_theme_colors()
        
        self.search_widget.retranslateUi(lang)
        
        if lang == "my":
            self.search_widget.search_input.setPlaceholderText("ပြေစာအမှတ်၊ ဝယ်ယူသူ သို့မဟုတ် ငွေပေးချေမှုအမျိုးအစားဖြင့် ရှာရန်...")
            self.btn_export_list.setText(" စာရင်းထုတ်မည်")
            self.btn_export_range.setText(" ရက်ကား အလိုက် ထုတ်မည်")
            
            self.customer_filter.setItemText(0, "အားလုံး")
            self.customer_filter.setItemText(1, "လမ်းဘေးဝယ်")
            self.customer_filter.setItemText(2, "မှတ်ပုံတင်ထားသူ")
            self.customer_filter.setItemText(3, "အကြွေး")
            
            headers = [
                "ID", "ပြေစာအမှတ်", "ရက်စွဲ", "စုစုပေါင်း", "ငွေပေးချေမှု", 
                "ပြန်အမ်းငွေ", "ဝယ်ယူသူ", "ငွေပေးချေမှုအမျိုးအစား", "ပြန်အမ်းမည်", "ပြေစာထုတ်မည်"
            ]
        else:
            self.search_widget.search_input.setPlaceholderText("Search by invoice no, customer, or payment type...")
            self.btn_export_list.setText(" Export List")
            self.btn_export_range.setText(" Export Range")
            
            self.customer_filter.setItemText(0, "All")
            self.customer_filter.setItemText(1, "Walk-in")
            self.customer_filter.setItemText(2, "Registered")
            self.customer_filter.setItemText(3, "Credit")
            
            headers = [
                "ID", "Invoice No", "Date", "Total", "Payment", "Change", 
                "Customer", "Payment Type", "Refund", "Print"
            ]
        
        self.table.setHorizontalHeaderLabels(headers)
        
        self.table.setColumnWidth(8, 128)
        self.table.setColumnWidth(9, 120)
        
        # Update button icons
        self._update_button_icons()
        
        # Apply theme after language change
        self._apply_theme()

    def on_page_changed(self, page: int, page_size: int):
        self.load_sales(page=page, page_size=page_size)

    def reset_and_load(self):
        self.pagination.set_current_page(1)
        self.load_sales()

    # ============================================================
    # ✅ FIXED: load_sales() - Search by payment type too
    # ============================================================
    def load_sales(self, from_date=None, to_date=None, page=1, page_size=None):
        """Load sales with pagination - search by invoice_no, customer_name, and payment_type"""
        try:
            symbol = get_currency_symbol()
            search_text = self.search_widget.get_text().strip()
            lang = self.get_lang()
            if page_size is None:
                page_size = getattr(self.pagination, "_page_size", 100)
            try:
                page_size = int(page_size)
            except (TypeError, ValueError):
                page_size = 100
            
            # Get date range from parent
            if from_date is not None and to_date is not None:
                self._current_from_date = from_date
                self._current_to_date = to_date
            elif hasattr(self.parent_page, 'get_current_date_range'):
                from_date, to_date = self.parent_page.get_current_date_range()
                self._current_from_date = from_date
                self._current_to_date = to_date
            else:
                today = QDate.currentDate().toString("yyyy-MM-dd")
                from_date, to_date = today, today
                self._current_from_date = from_date
                self._current_to_date = to_date
            
            payment_type = self.payment_filter.currentText()
            customer_filter = self.customer_filter.currentText()
            
            conn = connect_db()
            cursor = conn.cursor()
            
            # ✅ Search condition - include payment_type in search
            search_condition = ""
            search_params = []
            
            if search_text:
                # Search by invoice_no, customer name, or payment_type
                search_condition = """AND (
                    s.invoice_no LIKE ? 
                    OR COALESCE(c.name, '') LIKE ? 
                    OR LOWER(s.payment_type) LIKE LOWER(?)
                )"""
                like = f'%{search_text}%'
                search_params = [like, like, like]
            
            payment_condition = ""
            filter_params = []
            if payment_type and payment_type not in ["All", "အားလုံး"]:
                cursor.execute("SELECT name FROM payment_types WHERE LOWER(name) = LOWER(?)", (payment_type,))
                result = cursor.fetchone()
                if result:
                    actual_name = result[0]
                else:
                    actual_name = payment_type
                payment_condition = "AND LOWER(COALESCE(s.payment_type, '')) = LOWER(?)"
                filter_params.append(actual_name)
            
            customer_condition = ""
            if customer_filter == "Walk-in" or customer_filter == "လမ်းဘေးဝယ်":
                customer_condition = "AND s.customer_id IS NULL"
            elif customer_filter == "Registered" or customer_filter == "မှတ်ပုံတင်ထားသူ":
                customer_condition = "AND s.customer_id IS NOT NULL"
            elif customer_filter == "Credit" or customer_filter == "အကြွေး":
                customer_condition = "AND LOWER(s.payment_type) = 'credit'"
            
            # Build WHERE clause
            where_clause = f"""
                WHERE s.status='completed' 
                  AND date(s.created_at) BETWEEN ? AND ?
                  {search_condition}
                  {payment_condition}
                  {customer_condition}
            """
            
            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                {where_clause}
            """
            
            # Count params
            count_params = [from_date, to_date] + search_params + filter_params
            
            cursor.execute(count_query, count_params)
            total_items = cursor.fetchone()[0]
            
            # Convert to int
            try:
                total_items = int(total_items) if total_items is not None else 0
            except (ValueError, TypeError):
                total_items = 0
            
            # Ensure page and page_size are int
            try:
                page = int(page) if page is not None else 1
            except (ValueError, TypeError):
                page = 1
            
            try:
                page_size = int(page_size) if page_size is not None else 25
            except (ValueError, TypeError):
                page_size = 25
            
            # Set pagination
            try:
                self.pagination.set_total_items(total_items, emit_signal=False)
            except Exception as e:
                logger.error(f"Error setting pagination total items: {e}")
                self.pagination.set_total_items(0, emit_signal=False)
            
            offset = (page - 1) * page_size
            
            # Select query
            select_query = f"""
                SELECT 
                    s.id, 
                    s.invoice_no, 
                    s.created_at, 
                    COALESCE(SUM(si.qty * si.price), 0) as total,
                    s.payment, 
                    s.change_amount, 
                    c.name, 
                    s.payment_type
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                LEFT JOIN sale_items si ON s.id = si.sale_id
                {where_clause}
                GROUP BY s.id, s.invoice_no, s.created_at, s.payment, s.change_amount, c.name, s.payment_type
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
            """
            
            select_params = [from_date, to_date] + search_params + filter_params + [page_size, offset]
            
            cursor.execute(select_query, select_params)
            rows = cursor.fetchall()
            conn.close()
            
            self.table.setRowCount(0)
            for row_data in rows:
                sale_id, invoice_no, created_at, total, payment, change_amount, customer_name, payment_type_db = row_data
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setRowHeight(row, 58)
                
                # ✅ Use PyQt6 default colors - no custom text color
                # ID (hidden)
                id_item = QTableWidgetItem(str(sale_id))
                self.table.setItem(row, 0, id_item)
                
                # Invoice No
                inv_item = QTableWidgetItem(invoice_no)
                self.table.setItem(row, 1, inv_item)
                
                # Date
                date_item = QTableWidgetItem(str(created_at))
                self.table.setItem(row, 2, date_item)
                
                # Total
                total_item = QTableWidgetItem(format_money(total, symbol))
                self.table.setItem(row, 3, total_item)
                
                # Payment
                payment_item = QTableWidgetItem(format_money(payment, symbol))
                self.table.setItem(row, 4, payment_item)
                
                # Change
                change_item = QTableWidgetItem(format_money(change_amount, symbol))
                self.table.setItem(row, 5, change_item)
                
                # Customer
                cust_name = customer_name if customer_name else "-"
                cust_item = QTableWidgetItem(cust_name)
                self.table.setItem(row, 6, cust_item)
                
                # Payment Type
                ptype_item = QTableWidgetItem(payment_type_db if payment_type_db else "-")
                self.table.setItem(row, 7, ptype_item)

                # Refund button
                btn_refund = ModernButton("Refund" if lang != "my" else "ပြန်အမ်းမည်", ModernButton.PRIMARY)
                btn_refund.set_icon("currency_exchange", size=(14, 14))
                btn_refund.set_compact(True)
                btn_refund.setFixedSize(104, 36)
                btn_refund.clicked.connect(lambda _, sid=sale_id: self.refund_sale(sid))
                self.table.setCellWidget(row, 8, self._centered_cell_widget(btn_refund))

                # Print button
                btn_print = ModernButton("Print" if lang != "my" else "ထုတ်မည်", ModernButton.SECONDARY)
                btn_print.set_icon("print", size=(14, 14))
                btn_print.set_compact(True)
                btn_print.setFixedSize(96, 36)
                btn_print.clicked.connect(lambda _, sid=sale_id: self.print_receipt(sid))
                self.table.setCellWidget(row, 9, self._centered_cell_widget(btn_print))
                
        except Exception as e:
            logger.error(f"Error loading sales: {e}")
            self.table.setRowCount(1)
            error_item = QTableWidgetItem(f"Error loading data: {str(e)}")
            error_item.setForeground(QColor("#dc3545"))
            self.table.setItem(0, 1, error_item)

    def show_receipt_detail(self, row, column):
        sale_id_item = self.table.item(row, 0)
        if sale_id_item:
            sale_id = int(sale_id_item.text())
            dialog = ReceiptDetailDialog(sale_id)
            dialog.exec()

    def print_receipt(self, sale_id):
        try:
            dialog = ReceiptDialog(sale_id, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Print Error", f"Could not print receipt: {e}")

    def refund_sale(self, sale_id):
        lang = self.get_lang()
        
        if self.user_id:
            has_permission = PermissionManager.user_has_permission(self.user_id, Permission.REFUND_RECEIPT)
            if not has_permission:
                QMessageBox.warning(self, "Access Denied", "You don't have permission to refund sales.")
                return
        
        if lang == "my":
            confirm_title = "အတည်ပြုရန်"
            confirm_text = "ဤရောင်းချမှုကို ပြန်အမ်းမည်လား?\nစတော့ပြန်လည်သိုလှောင်ပေးမည်ဖြစ်ပြီး အမှတ်များကို ပြန်လည်ချိန်ညှိပေးမည်။"
            success_msg = "အောင်မြင်စွာ ပြန်အမ်းပြီးပါပြီ။"
            error_msg = "ပြန်အမ်းခြင်း မအောင်မြင်ပါ: {e}"
            partial_refund_msg = "ဤအကြွေးစာရင်းတွင် ကျန်ငွေရှိသေးသောကြောင့် အပြည့်အဝ ပြန်အမ်းနိုင်မည်မဟုတ်ပါ။ ဦးစွာ ကျန်ငွေကို ကောက်ခံပါ။"
        else:
            confirm_title = "Confirm Refund"
            confirm_text = "Refund this sale? Stock will be restored and customer points adjusted."
            success_msg = "Sale refunded successfully."
            error_msg = "Refund failed: {e}"
            partial_refund_msg = "This credit sale still has remaining balance. Please collect the outstanding amount first."

        confirm = QMessageBox.question(
            self, confirm_title, confirm_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT status FROM sales WHERE id=?", (sale_id,))
            result = cursor.fetchone()
            if not result:
                QMessageBox.warning(self, "Error", "Sale not found.")
                return
                
            if result[0] != 'completed':
                QMessageBox.warning(self, "Error", "This sale has already been refunded.")
                return

            cursor.execute("SELECT customer_id, total, invoice_no, payment_type FROM sales WHERE id=?", (sale_id,))
            sale_data = cursor.fetchone()
            if not sale_data:
                QMessageBox.warning(self, "Error", "Sale data not found.")
                return
                
            customer_id, total, invoice_no, payment_type = sale_data

            # Check credit sale
            credit_sale = None
            if customer_id and (payment_type or "").lower() == "credit":
                cursor.execute("""
                    SELECT id, balance_amount, paid_amount, status
                    FROM credit_sales
                    WHERE sale_id = ?
                    LIMIT 1
                """, (sale_id,))
                credit_sale = cursor.fetchone()

                if not credit_sale and invoice_no:
                    cursor.execute("""
                        SELECT id, balance_amount, paid_amount, status
                        FROM credit_sales
                        WHERE invoice_no = ? AND customer_id = ?
                        LIMIT 1
                    """, (invoice_no, customer_id))
                    credit_sale = cursor.fetchone()

            # Handle credit refund - FIXED
            if credit_sale:
                credit_sale_id, balance_amount, paid_amount, credit_status = credit_sale
                balance_amount = float(balance_amount or 0)
                paid_amount = float(paid_amount or 0)
                
                if credit_status != "refunded":
                    # Check if this is a credit sale with no payment yet
                    if balance_amount > 0 and paid_amount == 0:
                        # Unpaid credit sale - can refund directly
                        result = self.credit_service.refund_credit_sale(
                            credit_sale_id=credit_sale_id,
                            reason="Unpaid credit refund",
                            refund_type='full'
                        )
                        if not result.get('success'):
                            QMessageBox.critical(self, "Error", f"Refund failed: {result.get('error')}")
                            return
                    elif balance_amount == 0 and paid_amount > 0:
                        # Fully paid credit sale - needs payment refund
                        result = self.credit_service.refund_credit_sale(
                            credit_sale_id=credit_sale_id,
                            reason="Fully paid credit refund",
                            refund_type='full'
                        )
                        if not result.get('success'):
                            QMessageBox.critical(self, "Error", f"Refund failed: {result.get('error')}")
                            return
                    elif balance_amount > 0 and paid_amount > 0:
                        # Partially paid - cannot refund full, must collect remaining first
                        QMessageBox.warning(self, "Cannot Refund", partial_refund_msg)
                        return
                    elif balance_amount == 0 and paid_amount == 0:
                        # Zero balance, zero paid - can refund
                        result = self.credit_service.refund_credit_sale(
                            credit_sale_id=credit_sale_id,
                            reason="Zero balance refund",
                            refund_type='full'
                        )
                        if not result.get('success'):
                            QMessageBox.critical(self, "Error", f"Refund failed: {result.get('error')}")
                            return

            # Restore stock to the original product/location/batch when available.
            cursor.execute("PRAGMA table_info(sale_items)")
            sale_item_cols = {row[1] for row in cursor.fetchall()}
            wanted_cols = [
                "product_name", "qty",
                "product_id" if "product_id" in sale_item_cols else "NULL AS product_id",
                "variant_id" if "variant_id" in sale_item_cols else "NULL AS variant_id",
                "location_id" if "location_id" in sale_item_cols else "NULL AS location_id",
                "location" if "location" in sale_item_cols else "'' AS location",
                "batch_no" if "batch_no" in sale_item_cols else "'' AS batch_no",
                "expire_date" if "expire_date" in sale_item_cols else "'' AS expire_date",
            ]
            cursor.execute(f"SELECT {', '.join(wanted_cols)} FROM sale_items WHERE sale_id=?", (sale_id,))
            items = cursor.fetchall()
            
            for product_name, qty, product_id, variant_id, location_id, location, batch_no, expire_date in items:
                qty = int(qty or 0)
                if qty <= 0:
                    continue

                if not product_id:
                    clean_name = str(product_name or "").split(" (", 1)[0]
                    cursor.execute("SELECT id, sold_by FROM products WHERE name=?", (clean_name,))
                else:
                    cursor.execute("SELECT id, sold_by FROM products WHERE id=?", (product_id,))
                prod = cursor.fetchone()
                if not prod or prod[1] == 'Service':
                    continue

                product_id = prod[0]
                cursor.execute("UPDATE products SET stock = stock + ?, last_updated = CURRENT_TIMESTAMP WHERE id=?", (qty, product_id))

                if variant_id:
                    cursor.execute("""
                        UPDATE product_variants
                        SET stock = stock + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND product_id = ?
                    """, (qty, variant_id, product_id))
                    restore_location = location or "Variant"
                else:
                    restore_location = location or "Default"
                    restore_batch = batch_no or ""
                    restore_expire = expire_date or ""
                    cursor.execute("""
                        INSERT INTO product_locations
                            (product_id, location, batch_no, expire_date, quantity, last_updated)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(product_id, location, batch_no, expire_date)
                        DO UPDATE SET quantity = product_locations.quantity + excluded.quantity,
                                      last_updated = CURRENT_TIMESTAMP
                    """, (product_id, restore_location, restore_batch, restore_expire, qty))

                cursor.execute("""
                    INSERT INTO stock_movements
                        (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes, location)
                    VALUES (
                        ?, 'refund', ?, 
                        (SELECT COALESCE(stock, 0) - ? FROM products WHERE id = ?),
                        (SELECT COALESCE(stock, 0) FROM products WHERE id = ?),
                        'Refund', ?, 'System', ?, ?
                    )
                """, (
                    product_id, qty, qty, product_id, product_id, invoice_no,
                    f"Refund sale item: {product_name}; batch: {batch_no or 'N/A'}; expiry: {expire_date or 'N/A'}",
                    restore_location,
                ))

            # Adjust customer points
            if customer_id:
                cursor.execute("SELECT value FROM settings WHERE key='loyalty_points_per_dollar'")
                res = cursor.fetchone()
                points_per_dollar = float(res[0]) if res else 0.0
                points_earned = int(total * points_per_dollar)
                
                cursor.execute("""
                    UPDATE customers 
                    SET total_visit = CASE WHEN total_visit > 0 THEN total_visit - 1 ELSE 0 END,
                        total_spent = CASE WHEN total_spent >= ? THEN total_spent - ? ELSE 0 END,
                        points = CASE WHEN points >= ? THEN points - ? ELSE 0 END
                    WHERE id = ?
                """, (total, total, points_earned, points_earned, customer_id))

            cursor.execute("UPDATE sales SET status='refunded' WHERE id=?", (sale_id,))
            conn.commit()
            
            QMessageBox.information(self, "Success", success_msg)

            # Refresh UI
            main_window = self.window()
            if hasattr(main_window, 'check_stock_alerts'):
                main_window.check_stock_alerts()
            customers_page = getattr(main_window, "customers_page", None)
            if customers_page is not None and hasattr(customers_page, "load_customers"):
                customers_page.load_customers()

            self.load_sales()

            parent_page = self.parent()
            if hasattr(parent_page, 'refund_tab'):
                parent_page.refund_tab.load_refunded_sales()

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", error_msg.format(e=str(e)))
        finally:
            conn.close()

    # ============================================================
    # Export functions (updated with search support)
    # ============================================================
    def export_receipt_list(self):
        """Export receipt list using stored date range"""
        if self._current_from_date and self._current_to_date:
            from_date, to_date = self._current_from_date, self._current_to_date
        elif hasattr(self.parent_page, 'get_current_date_range'):
            from_date, to_date = self.parent_page.get_current_date_range()
            self._current_from_date = from_date
            self._current_to_date = to_date
        else:
            today = QDate.currentDate().toString("yyyy-MM-dd")
            from_date, to_date = today, today
            
        payment_type = self.payment_filter.currentText()
        customer_filter = self.customer_filter.currentText()
        search_text = self.search_widget.get_text().strip()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Receipt List", 
            f"receipt_list_{from_date}_to_{to_date}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            symbol = get_currency_symbol()
            
            conn = connect_db()
            cursor = conn.cursor()
            
            # Search condition
            search_condition = ""
            search_params = []
            
            if search_text:
                search_condition = """AND (
                    s.invoice_no LIKE ? 
                    OR COALESCE(c.name, '') LIKE ? 
                    OR LOWER(s.payment_type) LIKE LOWER(?)
                )"""
                like = f'%{search_text}%'
                search_params = [like, like, like]
            
            payment_condition = ""
            if payment_type and payment_type not in ["All", "အားလုံး"]:
                payment_condition = f"AND LOWER(s.payment_type) = LOWER('{payment_type}')"
            
            customer_condition = ""
            if customer_filter == "Walk-in" or customer_filter == "လမ်းဘေးဝယ်":
                customer_condition = "AND s.customer_id IS NULL"
            elif customer_filter == "Registered" or customer_filter == "မှတ်ပုံတင်ထားသူ":
                customer_condition = "AND s.customer_id IS NOT NULL"
            elif customer_filter == "Credit" or customer_filter == "အကြွေး":
                customer_condition = "AND LOWER(s.payment_type) = 'credit'"
            
            select_query = f"""
                SELECT 
                    s.invoice_no, 
                    s.created_at, 
                    COALESCE(SUM(si.qty * si.price), 0) as total,
                    s.payment, 
                    s.change_amount, 
                    c.name, 
                    s.payment_type
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                LEFT JOIN sale_items si ON s.id = si.sale_id
                WHERE s.status='completed' 
                  AND date(s.created_at) BETWEEN ? AND ?
                  {search_condition}
                  {payment_condition}
                  {customer_condition}
                GROUP BY s.id, s.invoice_no, s.created_at, s.payment, s.change_amount, c.name, s.payment_type
                ORDER BY s.created_at DESC
            """
            
            select_params = [from_date, to_date] + search_params
            
            cursor.execute(select_query, select_params)
            rows = cursor.fetchall()
            conn.close()
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["=" * 80])
                writer.writerow(["RECEIPT LIST REPORT"])
                writer.writerow(["=" * 80])
                writer.writerow([])
                writer.writerow(["Report Period:", f"{from_date} to {to_date}"])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                if search_text:
                    writer.writerow(["Search Filter:", search_text])
                if payment_type and payment_type not in ["All", "အားလုံး"]:
                    writer.writerow(["Payment Type:", payment_type])
                if customer_filter and customer_filter not in ["All", "အားလုံး"]:
                    writer.writerow(["Customer Type:", customer_filter])
                writer.writerow([])
                writer.writerow(["Invoice No", "Date", "Total", "Payment", "Change", "Customer", "Payment Type"])
                writer.writerow(["-" * 80])
                
                total_amount = 0
                total_payment = 0
                total_change = 0
                
                for row in rows:
                    invoice_no, created_at, total, payment, change_amount, customer_name, payment_type_db = row
                    writer.writerow([
                        invoice_no,
                        created_at[:16] if created_at else "",
                        format_money(total, symbol),
                        format_money(payment, symbol),
                        format_money(change_amount, symbol),
                        customer_name if customer_name else "Walk-in",
                        payment_type_db or ""
                    ])
                    total_amount += total
                    total_payment += payment
                    total_change += change_amount
                
                writer.writerow([])
                writer.writerow(["TOTAL", "", 
                               format_money(total_amount, symbol),
                               format_money(total_payment, symbol),
                               format_money(total_change, symbol), "", ""])
                writer.writerow([])
                writer.writerow(["=" * 80])
                writer.writerow(["End of Report"])
            
            lang = self.get_lang()
            msg = f"Receipt list exported successfully to:\n{file_path}" if lang != "my" else f"ပြေစာစာရင်း အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete", msg)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export receipt list: {e}")

    def export_receipt_range(self):
        """Export receipt range using stored date range"""
        if self._current_from_date and self._current_to_date:
            from_date, to_date = self._current_from_date, self._current_to_date
        elif hasattr(self.parent_page, 'get_current_date_range'):
            from_date, to_date = self.parent_page.get_current_date_range()
            self._current_from_date = from_date
            self._current_to_date = to_date
        else:
            today = QDate.currentDate().toString("yyyy-MM-dd")
            from_date, to_date = today, today
            
        payment_type = self.payment_filter.currentText()
        customer_filter = self.customer_filter.currentText()
        search_text = self.search_widget.get_text().strip()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Receipt Range", 
            f"receipt_range_{from_date}_to_{to_date}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            symbol = get_currency_symbol()
            
            conn = connect_db()
            cursor = conn.cursor()
            
            # Search condition
            search_condition = ""
            search_params = []
            
            if search_text:
                search_condition = """AND (
                    s.invoice_no LIKE ? 
                    OR COALESCE(c.name, '') LIKE ? 
                    OR LOWER(s.payment_type) LIKE LOWER(?)
                )"""
                like = f'%{search_text}%'
                search_params = [like, like, like]
            
            payment_condition = ""
            if payment_type and payment_type not in ["All", "အားလုံး"]:
                payment_condition = f"AND LOWER(s.payment_type) = LOWER('{payment_type}')"
            
            customer_condition = ""
            if customer_filter == "Walk-in" or customer_filter == "လမ်းဘေးဝယ်":
                customer_condition = "AND s.customer_id IS NULL"
            elif customer_filter == "Registered" or customer_filter == "မှတ်ပုံတင်ထားသူ":
                customer_condition = "AND s.customer_id IS NOT NULL"
            elif customer_filter == "Credit" or customer_filter == "အကြွေး":
                customer_condition = "AND LOWER(s.payment_type) = 'credit'"
            
            select_query = f"""
                SELECT 
                    s.invoice_no, 
                    s.created_at, 
                    COALESCE(SUM(si.qty * si.price), 0) as total,
                    s.payment, 
                    s.change_amount, 
                    c.name, 
                    s.payment_type, 
                    s.discount_amount
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                LEFT JOIN sale_items si ON s.id = si.sale_id
                WHERE s.status='completed' 
                  AND date(s.created_at) BETWEEN ? AND ?
                  {search_condition}
                  {payment_condition}
                  {customer_condition}
                GROUP BY s.id, s.invoice_no, s.created_at, s.payment, s.change_amount, c.name, s.payment_type, s.discount_amount
                ORDER BY s.created_at DESC
            """
            
            select_params = [from_date, to_date] + search_params
            
            cursor.execute(select_query, select_params)
            rows = cursor.fetchall()
            
            # Stats query
            stats_query = f"""
                SELECT 
                    COUNT(DISTINCT s.id) as total_count,
                    COALESCE(SUM(si.qty * si.price), 0) as total_sales,
                    COALESCE(SUM(s.payment), 0) as total_payments,
                    COALESCE(SUM(s.change_amount), 0) as total_change,
                    COALESCE(AVG(si.qty * si.price), 0) as avg_sale
                FROM sales s
                LEFT JOIN sale_items si ON s.id = si.sale_id
                WHERE s.status='completed' 
                  AND date(s.created_at) BETWEEN ? AND ?
                  {search_condition}
                  {payment_condition}
                  {customer_condition}
            """
            
            stats_params = [from_date, to_date] + search_params
            
            cursor.execute(stats_query, stats_params)
            stats = cursor.fetchone()
            conn.close()
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["=" * 90])
                writer.writerow(["RECEIPT DETAIL REPORT"])
                writer.writerow(["=" * 90])
                writer.writerow([])
                writer.writerow(["Report Period:", f"{from_date} to {to_date}"])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                if search_text:
                    writer.writerow(["Search Filter:", search_text])
                if payment_type and payment_type not in ["All", "အားလုံး"]:
                    writer.writerow(["Payment Type Filter:", payment_type])
                if customer_filter and customer_filter not in ["All", "အားလုံး"]:
                    writer.writerow(["Customer Type:", customer_filter])
                writer.writerow([])
                
                writer.writerow(["SUMMARY STATISTICS"])
                writer.writerow(["-" * 50])
                writer.writerow(["Total Receipts:", stats[0] if stats else 0])
                writer.writerow(["Total Sales:", format_money(stats[1] if stats else 0, symbol)])
                writer.writerow(["Total Payments:", format_money(stats[2] if stats else 0, symbol)])
                writer.writerow(["Total Change:", format_money(stats[3] if stats else 0, symbol)])
                writer.writerow(["Average Sale:", format_money(stats[4] if stats else 0, symbol)])
                writer.writerow([])
                
                writer.writerow(["DETAILED RECEIPTS"])
                writer.writerow(["Invoice No", "Date", "Total", "Payment", "Change", "Customer", "Payment Type", "Discount"])
                writer.writerow(["-" * 90])
                
                total_sales = 0
                total_payments = 0
                total_change = 0
                total_discount = 0
                
                for row in rows:
                    invoice_no, created_at, total, payment, change_amount, customer_name, payment_type_db, discount = row
                    writer.writerow([
                        invoice_no,
                        created_at[:16] if created_at else "",
                        format_money(total, symbol),
                        format_money(payment, symbol),
                        format_money(change_amount, symbol),
                        customer_name if customer_name else "Walk-in",
                        payment_type_db or "",
                        format_money(discount or 0, symbol)
                    ])
                    total_sales += total
                    total_payments += payment
                    total_change += change_amount
                    total_discount += discount or 0
                
                writer.writerow([])
                writer.writerow(["GRAND TOTALS", "", 
                               format_money(total_sales, symbol),
                               format_money(total_payments, symbol),
                               format_money(total_change, symbol), "", "",
                               format_money(total_discount, symbol)])
                writer.writerow([])
                writer.writerow(["=" * 90])
                writer.writerow(["End of Report"])
            
            lang = self.get_lang()
            msg = f"Receipt range exported successfully to:\n{file_path}" if lang != "my" else f"ပြေစာရက်ကား အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete", msg)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export receipt range: {e}")

    def showEvent(self, event):
        self.load_payment_types()
        self.load_sales()
        super().showEvent(event)
