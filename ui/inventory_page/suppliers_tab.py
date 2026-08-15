# ui/inventory_page/suppliers_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QComboBox, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter
from models.database import connect_db
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.modern_button import ModernButton
from ui.widgets.search_widget import SearchWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from utils.translations import tr
import os


class SuppliersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.selected_supplier_id = None
        self.current_page = 1
        self.page_size = 25
        self._is_dark = is_dark_theme()
        
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Search and Filter row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(0, 8, 0, 8)
        
        # ✅ SearchWidget with SVG icon
        self.search_widget = SearchWidget(
            placeholder=tr("search_supplier"),
            show_label=False
        )
        self.search_widget.search_changed.connect(self.reset_pagination)
        self.search_widget.search_cleared.connect(self.reset_pagination)
        filter_layout.addWidget(self.search_widget, 2)
        
        # Status filter combo box
        filter_layout.addWidget(QLabel(tr("show_status")))
        self.status_filter = QComboBox()
        self.status_filter.addItem(tr("all"), None)
        self.status_filter.addItem(tr("active"), "Active")
        self.status_filter.addItem(tr("inactive"), "Inactive")
        self.status_filter.setCurrentIndex(self.status_filter.findData("Active"))
        self.status_filter.currentTextChanged.connect(self.reset_pagination)
        filter_layout.addWidget(self.status_filter, 1)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Button layout with SVG icons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # ✅ Add Supplier button
        self.btn_add = ModernButton(" " + tr("add_supplier"), ModernButton.PRIMARY)
        self.btn_add.set_icon("add", size=(16, 16))
        self.btn_add.set_compact(False)
        self.btn_add.clicked.connect(self.add_supplier)
        btn_layout.addWidget(self.btn_add)
        
        # ✅ Edit button
        self.btn_edit = ModernButton(" " + tr("edit"), ModernButton.SECONDARY)
        self.btn_edit.set_icon("edit", size=(16, 16))
        self.btn_edit.set_compact(False)
        self.btn_edit.clicked.connect(self.edit_supplier)
        btn_layout.addWidget(self.btn_edit)
        
        # ✅ Delete button (Red)
        self.btn_delete = ModernButton(" " + tr("delete"), ModernButton.PRIMARY)
        self.btn_delete.set_icon("delete", size=(16, 16))
        self.btn_delete.set_compact(False)
        self.btn_delete.clicked.connect(self.delete_supplier)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                padding: 5px 16px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        btn_layout.addWidget(self.btn_delete)
        
        # ✅ Ledger button
        self.btn_ledger = ModernButton(" " + tr("ledger"), ModernButton.SECONDARY)
        self.btn_ledger.set_icon("receipt_long", size=(16, 16))
        self.btn_ledger.set_compact(False)
        self.btn_ledger.clicked.connect(self.show_ledger)
        btn_layout.addWidget(self.btn_ledger)
        
        # ✅ Payment button
        self.btn_payment = ModernButton(" " + tr("make_payment"), ModernButton.SECONDARY)
        self.btn_payment.set_icon("payments", size=(16, 16))
        self.btn_payment.set_compact(False)
        self.btn_payment.clicked.connect(self.make_payment)
        btn_layout.addWidget(self.btn_payment)
        
        # ✅ Toggle Status button
        self.btn_toggle_status = ModernButton(" " + tr("toggle_status"), ModernButton.SECONDARY)
        self.btn_toggle_status.set_icon("swap_horiz", size=(16, 16))
        self.btn_toggle_status.set_compact(False)
        self.btn_toggle_status.clicked.connect(self.toggle_supplier_status)
        btn_layout.addWidget(self.btn_toggle_status)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Table - NO custom style, use PyQt6 default
        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.select_supplier)
        self.table.setColumnHidden(0, True)
        
        # ✅ NO custom table style
        # self._apply_table_theme()  <-- ဒီ line ကို ဖယ်ရှားပါ
        
        header = self.table.horizontalHeader()
        for col in range(1, 12):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        self.setLayout(layout)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        # ✅ Only update button icons and reload data - no table style update
        self._update_button_icons()
        self.load_data()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_add.set_icon("add", size=(16, 16))
        self.btn_edit.set_icon("edit", size=(16, 16))
        self.btn_delete.set_icon("delete", size=(16, 16))
        self.btn_ledger.set_icon("receipt_long", size=(16, 16))
        self.btn_payment.set_icon("payments", size=(16, 16))
        self.btn_toggle_status.set_icon("swap_horiz", size=(16, 16))

    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"

    def retranslateUi(self):
        # Update search placeholder
        self.search_widget.set_placeholder_text(tr("search_supplier"))
        
        # Update status filter items
        selected_status = self.status_filter.currentData()
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItem(tr("all"), None)
        self.status_filter.addItem(tr("active"), "Active")
        self.status_filter.addItem(tr("inactive"), "Inactive")
        selected_index = self.status_filter.findData(selected_status)
        self.status_filter.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.status_filter.blockSignals(False)
        
        # Update buttons with text only (icons are SVG)
        lang = self.get_lang()
        if lang == "my":
            self.btn_add.setText(" " + tr("add_supplier"))
            self.btn_edit.setText(" " + tr("edit"))
            self.btn_delete.setText(" " + tr("delete"))
            self.btn_ledger.setText(" " + tr("ledger"))
            self.btn_payment.setText(" " + tr("make_payment"))
            self.btn_toggle_status.setText(" " + tr("toggle_status"))
        else:
            self.btn_add.setText(" " + tr("add_supplier"))
            self.btn_edit.setText(" " + tr("edit"))
            self.btn_delete.setText(" " + tr("delete"))
            self.btn_ledger.setText(" " + tr("ledger"))
            self.btn_payment.setText(" " + tr("make_payment"))
            self.btn_toggle_status.setText(" " + tr("toggle_status"))
        
        # Update button icons
        self._update_button_icons()
        
        # Update table headers
        if lang == "my":
            headers = [
                "ID", "ပေးသွင်းသူအမည်", "ဆက်သွယ်ရမည့်သူ", "ဖုန်း", "အီးမေး", "လိပ်စာ",
                "ကုမ္ပဏီအမည်", "အခွန်အမှတ်", "ဝက်ဘ်ဆိုက်", "ငွေပေးချေမှုအခြေအနေ", "ဘဏ်အကောင့်", "အခြေအနေ"
            ]
        else:
            headers = [
                "ID", "Supplier Name", "Contact Person", "Phone", "Email", "Address",
                "Company Name", "Tax ID", "Website", "Payment Terms", "Bank Account", "Status"
            ]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setColumnHidden(0, True)
        
        # Refresh data to update status texts
        self.load_data()

    def reset_pagination(self):
        self.pagination.set_current_page(1)
        self.load_data()

    def on_page_changed(self, page: int, page_size: int):
        self.current_page = page
        self.page_size = page_size
        self.load_data(page, page_size)

    def refresh(self):
        self.load_data()
        self.retranslateUi()

    def load_data(self, page=None, page_size=None):
        if page is None:
            page = self.current_page
        if page_size is None:
            page_size = self.page_size
            
        search_text = self.search_widget.get_text().lower()
        db_status = self.status_filter.currentData()
        lang = self.get_lang()
        
        # Set headers based on language
        if lang == "my":
            headers = [
                "ID", "ပေးသွင်းသူအမည်", "ဆက်သွယ်ရမည့်သူ", "ဖုန်း", "အီးမေး", "လိပ်စာ",
                "ကုမ္ပဏီအမည်", "အခွန်အမှတ်", "ဝက်ဘ်ဆိုက်", "ငွေပေးချေမှုအခြေအနေ", "ဘဏ်အကောင့်", "အခြေအနေ"
            ]
        else:
            headers = [
                "ID", "Supplier Name", "Contact Person", "Phone", "Email", "Address",
                "Company Name", "Tax ID", "Website", "Payment Terms", "Bank Account", "Status"
            ]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setColumnHidden(0, True)

        conn = connect_db()
        cursor = conn.cursor()
        like = f'%{search_text}%'

        search_clause = """(
            LOWER(COALESCE(name, '')) LIKE ?
            OR LOWER(COALESCE(contact_person, '')) LIKE ?
            OR LOWER(COALESCE(phone, '')) LIKE ?
            OR LOWER(COALESCE(email, '')) LIKE ?
        )"""
        params = [like, like, like, like]
        if db_status == "Active":
            # Blank status is the legacy equivalent of Active.
            where_clause = (
                "(COALESCE(TRIM(status), '') = '' "
                "OR LOWER(TRIM(status)) = 'active') AND " + search_clause
            )
        elif db_status == "Inactive":
            where_clause = "LOWER(TRIM(COALESCE(status, ''))) = 'inactive' AND " + search_clause
        else:
            where_clause = search_clause

        cursor.execute(f"SELECT COUNT(*) FROM suppliers WHERE {where_clause}", params)
        total_items = cursor.fetchone()[0]
        self.pagination.set_total_items(total_items, emit_signal=False)

        # Keep this tab's page state in sync with PaginationWidget. Previously
        # the widget clamped itself while this stale value still produced an
        # out-of-range OFFSET and an empty table.
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        page = min(max(1, page), total_pages)
        self.current_page = page
        self.page_size = page_size
        self.pagination.set_current_page(page, emit_signal=False)
        offset = (page - 1) * page_size

        cursor.execute(f"""
            SELECT id, name, contact_person, phone, email, address,
                   company_name, tax_number, website, payment_terms, bank_account, status
            FROM suppliers
            WHERE {where_clause}
            ORDER BY
                CASE WHEN LOWER(TRIM(COALESCE(status, ''))) = 'active' THEN 0 ELSE 1 END,
                name
            LIMIT ? OFFSET ?
        """, params + [page_size, offset])
        
        rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                # Translate status for display
                if col_idx == 11:  # Status column
                    if value == "Active":
                        display_value = tr("active")
                    elif value == "Inactive":
                        display_value = tr("inactive")
                    else:
                        display_value = str(value) if value else ""
                    item = QTableWidgetItem(display_value)
                    # ✅ Use hardcoded colors
                    if value == "Active":
                        item.setForeground(QColor("#28a745"))  # Green
                    else:
                        item.setForeground(QColor("#dc3545"))  # Red
                else:
                    item = QTableWidgetItem(str(value) if value is not None else "")
                self.table.setItem(row_idx, col_idx, item)

    def select_supplier(self, row, col):
        id_item = self.table.item(row, 0)
        if id_item:
            self.selected_supplier_id = int(id_item.text())

    def toggle_supplier_status(self):
        """Toggle supplier status between Active and Inactive"""
        if not self.selected_supplier_id:
            QMessageBox.warning(self, tr("no_selection"), tr("select_supplier_first"))
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, status FROM suppliers WHERE id = ?", (self.selected_supplier_id,))
        row = cursor.fetchone()
        
        if not row:
            QMessageBox.warning(self, tr("error"), tr("supplier_not_found"))
            conn.close()
            return
        
        supplier_name, current_status = row
        new_status = "Inactive" if current_status == "Active" else "Active"
        new_status_display = tr("inactive") if new_status == "Inactive" else tr("active")
        
        confirm_msg = tr("confirm_status_change").format(supplier_name, current_status, new_status_display)
        
        reply = QMessageBox.question(self, tr("confirm"), confirm_msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            conn.close()
            return
        
        try:
            cursor.execute("UPDATE suppliers SET status = ? WHERE id = ?", (new_status, self.selected_supplier_id))
            conn.commit()
            
            success_msg = tr("status_updated").format(supplier_name, new_status_display)
            QMessageBox.information(self, tr("success"), success_msg)
            self.load_data()
            
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, tr("error"), f"{tr('update_failed')}: {e}")
        finally:
            conn.close()

    def show_ledger(self):
        if not self.selected_supplier_id:
            QMessageBox.warning(self, tr("no_selection"), tr("select_supplier_first"))
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM suppliers WHERE id = ?", (self.selected_supplier_id,))
        row = cursor.fetchone()
        conn.close()
        supplier_name = row[0] if row else "Unknown"
        
        from ui.supplier_ledger_dialog import SupplierLedgerDialog
        dialog = SupplierLedgerDialog(self.selected_supplier_id, supplier_name, self)
        dialog.exec()

    def make_payment(self):
        """Open payment dialog for selected supplier"""
        if not self.selected_supplier_id:
            QMessageBox.warning(self, tr("no_selection"), tr("select_supplier_first"))
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM suppliers WHERE id = ?", (self.selected_supplier_id,))
        row = cursor.fetchone()
        supplier_name = row[0] if row else "Unknown"
        
        # Calculate current balance
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN payment_type = 'Purchase' THEN amount ELSE 0 END), 0) as total_purchases,
                COALESCE(SUM(CASE WHEN payment_type != 'Purchase' THEN amount ELSE 0 END), 0) as total_payments
            FROM supplier_payments
            WHERE supplier_id = ?
        """, (self.selected_supplier_id,))
        row = cursor.fetchone()
        
        if not row or (row[0] == 0 and row[1] == 0):
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as total_purchases
                FROM purchase_orders
                WHERE supplier_id = ?
            """, (self.selected_supplier_id,))
            po_row = cursor.fetchone()
            total_purchases = po_row[0] if po_row else 0
            total_payments = 0
        else:
            total_purchases = row[0] if row else 0
            total_payments = row[1] if row else 0
        
        conn.close()
        current_balance = total_purchases - total_payments
        
        from ui.supplier_payment_dialog import SupplierPaymentDialog
        dialog = SupplierPaymentDialog(self.selected_supplier_id, supplier_name, current_balance, self)
        if dialog.exec():
            self.refresh()

    def add_supplier(self):
        from ui.inventory_page.supplier_dialog import SupplierDialog
        dialog = SupplierDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if not data["name"]:
                QMessageBox.warning(self, tr("error"), tr("supplier_name_required"))
                return
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO suppliers 
                    (name, contact_person, phone, email, address, company_name, tax_number, website, payment_terms, bank_account, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data['name'], data['contact_person'], data['phone'], data['email'], data['address'],
                      data['company_name'], data['tax_number'], data['website'], data['payment_terms'], data['bank_account'], 'Active'))
                conn.commit()
                QMessageBox.information(self, tr("success"), tr("supplier_added"))
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(self, tr("error"), f"{tr('add_failed')}: {e}")
            finally:
                conn.close()
            self.load_data()

    def edit_supplier(self):
        if not self.selected_supplier_id:
            QMessageBox.warning(self, tr("no_selection"), tr("select_supplier_first"))
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, contact_person, phone, email, address,
                   company_name, tax_number, website, payment_terms, bank_account, status
            FROM suppliers WHERE id = ?
        """, (self.selected_supplier_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            QMessageBox.warning(self, tr("error"), tr("supplier_not_found"))
            return
        supplier_data = {
            "name": row[0],
            "contact_person": row[1] or "",
            "phone": row[2] or "",
            "email": row[3] or "",
            "address": row[4] or "",
            "company_name": row[5] or "",
            "tax_number": row[6] or "",
            "website": row[7] or "",
            "payment_terms": row[8] or "Cash",
            "bank_account": row[9] or "",
            "status": row[10] or "Active"
        }
        from ui.inventory_page.supplier_dialog import SupplierDialog
        dialog = SupplierDialog(supplier_id=self.selected_supplier_id, supplier_data=supplier_data, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if not data["name"]:
                QMessageBox.warning(self, tr("error"), tr("supplier_name_required"))
                return
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE suppliers SET
                        name = ?, contact_person = ?, phone = ?, email = ?, address = ?,
                        company_name = ?, tax_number = ?, website = ?, payment_terms = ?, bank_account = ?, status = ?
                    WHERE id = ?
                """, (data['name'], data['contact_person'], data['phone'], data['email'], data['address'],
                      data['company_name'], data['tax_number'], data['website'], data['payment_terms'], data['bank_account'], data['status'],
                      self.selected_supplier_id))
                conn.commit()
                QMessageBox.information(self, tr("success"), tr("supplier_updated"))
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(self, tr("error"), f"{tr('update_failed')}: {e}")
            finally:
                conn.close()
            self.load_data()

    def delete_supplier(self):
        if not self.selected_supplier_id:
            QMessageBox.warning(self, tr("no_selection"), tr("select_supplier_first"))
            return
        
        # Check if supplier has any purchase orders
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE supplier_id = ?", (self.selected_supplier_id,))
        po_count = cursor.fetchone()[0]
        conn.close()
        
        if po_count > 0:
            QMessageBox.warning(self, tr("cannot_delete"), tr("supplier_has_orders"))
            return
        
        reply = QMessageBox.question(self, tr("confirm_delete"), tr("confirm_delete_supplier"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM suppliers WHERE id = ?", (self.selected_supplier_id,))
                conn.commit()
                self.selected_supplier_id = None
                self.load_data()
                QMessageBox.information(self, tr("deleted"), tr("supplier_deleted"))
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(self, tr("error"), f"{tr('delete_failed')}: {e}")
            finally:
                conn.close()
    
    def showEvent(self, event):
        """Handle show event - refresh data"""
        self.load_data()
        super().showEvent(event)
