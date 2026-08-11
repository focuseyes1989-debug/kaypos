# ui/customer_page/customers_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.modern_button import ModernButton
from ui.widgets.action_toolbar import ActionToolbar
from ui.widgets.search_widget import SearchWidget
from utils.language import lang
from utils.activity_logger import log_activity
from ui.customer_page.credit_sale_dialog import CreditSaleDialog
from ui.customer_page.credit_payment_dialog import CreditPaymentDialog
from ui.customer_page.customer_ledger_dialog import CustomerLedgerDialog
from ui.customer_page.outstanding_report_dialog import OutstandingReportDialog
from ui.customer_page.add_edit_customer_dialog import AddEditCustomerDialog
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from utils.excel_exporter import ExcelExporter
from datetime import datetime
import csv


class CustomersPage(QWidget):
    """Customers Page - Theme-aware with SVG Icons"""
    
    def __init__(self, user_role=None, parent=None):
        super().__init__(parent)
        self.user_role = user_role
        self.selected_customer_id = None
        self.current_language = lang.get_current()
        self._is_dark = is_dark_theme()
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # ====== Top Row: Search, Add Button, Action Toolbar (All on left) ======
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        top_layout.setContentsMargins(0, 8, 0, 8)
        
        # ====== Search Widget (Leftmost) ======
        self.search_widget = SearchWidget(
            placeholder="Search by name, phone, email...",
            show_label=False
        )
        self.search_widget.search_changed.connect(self.reset_and_search)
        self.search_widget.search_cleared.connect(self.reset_and_search)
        top_layout.addWidget(self.search_widget, 0)  # No stretch, fixed size
        
        # ====== Add Customer Button ======
        self.btn_add = ModernButton("", ModernButton.PRIMARY)
        self.btn_add.set_icon("add", size=(16, 16))
        self.btn_add.setFixedWidth(130)
        self.btn_add.setFixedHeight(36)
        self.btn_add.clicked.connect(self.add_customer)
        top_layout.addWidget(self.btn_add)
        
        # ====== Action Toolbar (More menu) ======
        self.action_toolbar = ActionToolbar(self)
        
        # More actions
        self.action_edit = self.action_toolbar.add_more_action("Edit", self.edit_customer, "edit")
        self.action_credit_sale = self.action_toolbar.add_more_action("Credit Sale", self.credit_sale, "credit_card")
        self.action_payment = self.action_toolbar.add_more_action("Payment Collection", self.payment_collection, "payments")
        self.action_ledger = self.action_toolbar.add_more_action("Ledger", self.show_ledger, "receipt_long")
        self.action_outstanding_report = self.action_toolbar.add_more_action("Outstanding Report", self.show_outstanding_report, "analytics")
        self.action_toolbar.add_separator()
        self.action_export_excel = self.action_toolbar.add_more_action("Export Excel", self.export_to_excel, "file_export")
        self.action_delete = self.action_toolbar.add_more_action("Delete", self.delete_customer, "delete")
        self.action_toolbar.finalize()
        
        # Add action toolbar
        top_layout.addWidget(self.action_toolbar)
        
        # Add stretch to push everything to the left (optional, but keeps things left-aligned)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # ====== Table - NO custom style, use PyQt6 default ======
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self.select_customer)
        self.table.setAlternatingRowColors(True)
        
        # Row height
        self.table.verticalHeader().setDefaultSectionSize(55)
        self.table.verticalHeader().setVisible(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Phone
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Email
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Address
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Total Visit
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Total Spent
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Points
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Credit Limit
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)  # Current Balance
        
        layout.addWidget(self.table)

        # ====== Pagination ======
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        self.setLayout(layout)

        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
        self.load_customers()

    def _get_delete_button_style(self):
        """Get delete button style with red color"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            return """
                QPushButton {
                    background-color: #ed4245;
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
            """
        else:
            return """
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
            """

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_customers()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        if hasattr(self, 'btn_add'):
            self.btn_add.set_icon("add", size=(16, 16))
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        if hasattr(self, 'action_edit'):
            self.action_edit.setText("Edit")
        if hasattr(self, 'action_delete'):
            self.action_delete.setText("Delete")
        if hasattr(self, 'action_credit_sale'):
            self.action_credit_sale.setText("Credit Sale")
        if hasattr(self, 'action_payment'):
            self.action_payment.setText("Payment Collection")
        if hasattr(self, 'action_ledger'):
            self.action_ledger.setText("Ledger")
        if hasattr(self, 'action_outstanding_report'):
            self.action_outstanding_report.setText("Outstanding Report")
        if hasattr(self, 'action_export_excel'):
            self.action_export_excel.setText("Export Excel")
        
        # Update button icons
        self._update_button_icons()
        if hasattr(self, "action_toolbar"):
            self.action_toolbar.update_theme()

    def reset_and_search(self):
        self.pagination.set_current_page(1)
        self.load_customers()

    def on_page_changed(self, page: int, page_size: int):
        self.load_customers(page, page_size)

    def get_currency_symbol(self):
        return get_currency_symbol()

    def get_lang(self):
        return lang.get_current()

    # ---------- EXPORT TO EXCEL ----------
    def export_to_excel(self):
        """Export customer list to Excel (.xlsx)"""
        file_path = ExcelExporter.save_file_dialog(
            self, 
            f"customer_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Export Customer List" if self.current_language != "my" else "ဖောက်သည်စာရင်း ထုတ်ရန်"
        )
        if not file_path:
            return
        
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            
            symbol = get_currency_symbol()
            search_text = self.search_widget.get_text().lower()
            lang_code = self.current_language
            
            conn = connect_db()
            cursor = conn.cursor()
            
            if search_text:
                like = f'%{search_text}%'
                cursor.execute("""
                    SELECT name, phone, email, address, total_visit, total_spent, points,
                           COALESCE(credit_limit, 0), COALESCE(current_balance, 0)
                    FROM customers
                    WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                    ORDER BY name
                """, (like, like, like))
            else:
                cursor.execute("""
                    SELECT name, phone, email, address, total_visit, total_spent, points,
                           COALESCE(credit_limit, 0), COALESCE(current_balance, 0)
                    FROM customers
                    ORDER BY name
                """)
            rows = cursor.fetchall()
            
            # Get summary statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_customers,
                    COALESCE(SUM(current_balance), 0) as total_balance,
                    COALESCE(SUM(credit_limit), 0) as total_credit_limit,
                    COALESCE(SUM(total_spent), 0) as total_spent
                FROM customers
            """)
            stats = cursor.fetchone()
            conn.close()
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Customers"
            
            # Title
            ws.merge_cells('A1:J1')
            ws['A1'] = "CUSTOMER LIST REPORT"
            ws['A1'].font = Font(bold=True, size=14)
            ws['A1'].alignment = Alignment(horizontal="center")
            
            ws['A2'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ws['A2'].font = Font(size=10, color="7f8c8d")
            
            if search_text:
                ws['A3'] = f"Search Filter: {search_text}"
                ws['A3'].font = Font(size=10, color="7f8c8d")
            
            # Summary row
            ws['A4'] = f"Total Customers: {stats[0] if stats else 0}"
            ws['A4'].font = Font(bold=True, size=11)
            ws['A5'] = f"Total Outstanding Balance: {format_money(stats[1] if stats else 0, symbol)}"
            ws['A5'].font = Font(bold=True, size=11)
            ws['A6'] = f"Total Credit Limit: {format_money(stats[2] if stats else 0, symbol)}"
            ws['A6'].font = Font(bold=True, size=11)
            ws['A7'] = f"Total Spent All Time: {format_money(stats[3] if stats else 0, symbol)}"
            ws['A7'].font = Font(bold=True, size=11)
            
            # Headers
            if lang_code == "my":
                headers = ["အမည်", "ဖုန်း", "အီးမေး", "လိပ်စာ", "အလည်လာခဲ့မှု", 
                          "စုစုပေါင်းသုံးစွဲမှု", "အမှတ်", "ခရက်ဒစ်ကန့်သတ်ချက်", "လက်ကျန်ငွေ"]
            else:
                headers = ["Name", "Phone", "Email", "Address", "Total Visit", 
                          "Total Spent", "Points", "Credit Limit", "Current Balance"]
            
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=9, column=col, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="2c3e50", end_color="2c3e50", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")
            
            # Data
            total_visit = 0
            total_spent = 0
            total_points = 0
            total_credit = 0
            total_balance = 0
            
            for row_idx, row_data in enumerate(rows, start=10):
                name, phone, email, address, visit, spent, points, credit, balance = row_data
                
                ws.cell(row=row_idx, column=1, value=name)
                ws.cell(row=row_idx, column=2, value=phone or "")
                ws.cell(row=row_idx, column=3, value=email or "")
                ws.cell(row=row_idx, column=4, value=address or "")
                ws.cell(row=row_idx, column=5, value=visit)
                ws.cell(row=row_idx, column=6, value=format_money(spent, symbol))
                ws.cell(row=row_idx, column=7, value=points)
                ws.cell(row=row_idx, column=8, value=format_money(credit, symbol))
                ws.cell(row=row_idx, column=9, value=format_money(balance, symbol))
                
                total_visit += visit
                total_spent += spent
                total_points += points
                total_credit += credit
                total_balance += balance
            
            # Summary row
            summary_row = len(rows) + 11
            ws.cell(row=summary_row, column=4, value="TOTAL").font = Font(bold=True)
            ws.cell(row=summary_row, column=5, value=total_visit)
            ws.cell(row=summary_row, column=6, value=format_money(total_spent, symbol))
            ws.cell(row=summary_row, column=7, value=total_points)
            ws.cell(row=summary_row, column=8, value=format_money(total_credit, symbol))
            ws.cell(row=summary_row, column=9, value=format_money(total_balance, symbol))
            
            # Auto adjust columns
            for col in range(1, 10):
                max_length = 0
                for row in range(9, summary_row + 1):
                    cell_value = ws.cell(row=row, column=col).value
                    if cell_value:
                        max_length = max(max_length, len(str(cell_value)))
                ws.column_dimensions[chr(64 + col)].width = min(max_length + 2, 40)
            
            wb.save(file_path)
            ExcelExporter.show_success_message(self, file_path)
            
        except Exception as e:
            ExcelExporter.show_error_message(self, e)

    def load_customers(self, page=1, page_size=25):
        try:
            symbol = get_currency_symbol()
            search_text = self.search_widget.get_text().lower()
            
            conn = connect_db()
            cursor = conn.cursor()
            
            if search_text:
                like = f'%{search_text}%'
                cursor.execute("""
                    SELECT COUNT(*) FROM customers 
                    WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                """, (like, like, like))
            else:
                cursor.execute("SELECT COUNT(*) FROM customers")
            total_items = cursor.fetchone()[0]
            self.pagination.set_total_items(total_items, emit_signal=False)

            offset = (page - 1) * page_size
            if search_text:
                cursor.execute("""
                    SELECT id, name, phone, email, address, total_visit, total_spent, points, 
                           COALESCE(credit_limit, 0), COALESCE(current_balance, 0)
                    FROM customers
                    WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                    ORDER BY name
                    LIMIT ? OFFSET ?
                """, (like, like, like, page_size, offset))
            else:
                cursor.execute("""
                    SELECT id, name, phone, email, address, total_visit, total_spent, points,
                           COALESCE(credit_limit, 0), COALESCE(current_balance, 0)
                    FROM customers
                    ORDER BY name
                    LIMIT ? OFFSET ?
                """, (page_size, offset))
            rows = cursor.fetchall()
            conn.close()
            
            self.table.setRowCount(len(rows))
            
            # Use hardcoded colors
            red_color = "#dc3545"
            green_color = "#28a745"
            
            for row_idx, row_data in enumerate(rows):
                self.table.setRowHeight(row_idx, 55)
                
                for col_idx, val in enumerate(row_data):
                    # Use PyQt6 default colors - no custom text color
                    if col_idx == 9:  # current_balance
                        item = QTableWidgetItem(format_money(val, symbol))
                        if val > 0:
                            item.setForeground(QColor(red_color))
                        else:
                            item.setForeground(QColor(green_color))
                    elif col_idx == 6:  # total_spent
                        item = QTableWidgetItem(format_money(val, symbol))
                    elif col_idx == 8:  # credit_limit
                        item = QTableWidgetItem(format_money(val, symbol))
                    else:
                        item = QTableWidgetItem(str(val) if val else "")
                    self.table.setItem(row_idx, col_idx, item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load customers: {e}")

    def select_customer(self, row, col):
        id_item = self.table.item(row, 0)
        if id_item:
            self.selected_customer_id = int(id_item.text())

    def get_customer_name(self):
        if not self.selected_customer_id:
            return "Unknown"
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM customers WHERE id = ?", (self.selected_customer_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "Unknown"

    def credit_sale(self):
        if not self.selected_customer_id:
            lang_code = lang.get_current()
            msg = "Please select a customer first." if lang_code != "my" else "ကျေးဇူးပြု၍ ဖောက်သည်တစ်ဦးကို ရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        customer_name = self.get_customer_name()
        dialog = CreditSaleDialog(self.selected_customer_id, customer_name, self)
        if dialog.exec():
            self.load_customers()

    def payment_collection(self):
        if not self.selected_customer_id:
            lang_code = lang.get_current()
            msg = "Please select a customer first." if lang_code != "my" else "ကျေးဇူးပြု၍ ဖောက်သည်တစ်ဦးကို ရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        customer_name = self.get_customer_name()
        dialog = CreditPaymentDialog(self.selected_customer_id, customer_name, self)
        if dialog.exec():
            self.load_customers()

    def show_ledger(self):
        if not self.selected_customer_id:
            lang_code = lang.get_current()
            msg = "Please select a customer first." if lang_code != "my" else "ကျေးဇူးပြု၍ ဖောက်သည်တစ်ဦးကို ရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        customer_name = self.get_customer_name()
        dialog = CustomerLedgerDialog(self.selected_customer_id, customer_name, self)
        dialog.exec()

    def show_outstanding_report(self):
        dialog = OutstandingReportDialog(self)
        dialog.exec()

    def add_customer(self):
        try:
            dialog = AddEditCustomerDialog(language=self.current_language)
            if dialog.exec():
                data = dialog.get_data()
                if not data["name"]:
                    msg = "အမည်ထည့်ရန်လိုအပ်ပါသည်။" if self.current_language == "my" else "Name is required"
                    QMessageBox.warning(self, "Error", msg)
                    return
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO customers (name, phone, email, address, credit_limit, remarks, total_visit, total_spent, points, current_balance)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0)
                """, (data["name"], data["phone"], data["email"], data["address"], data["credit_limit"], data["remarks"]))
                conn.commit()
                conn.close()
                self.load_customers()
                main_window = self.window()
                if hasattr(main_window, 'current_user'):
                    log_activity(main_window.current_user["id"], main_window.current_user["username"],
                               "Add Customer", f"Customer: {data['name']}")
                msg = "ဖောက်သည်ထည့်သွင်းပြီးပါပြီ။" if self.current_language == "my" else "Customer added"
                QMessageBox.information(self, "Success", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add customer: {e}")

    def edit_customer(self):
        if not self.selected_customer_id:
            msg = "ကျေးဇူးပြု၍ ဖောက်သည်တစ်ဦးကို ရွေးပါ။" if self.current_language == "my" else "Please select a customer first."
            QMessageBox.warning(self, "No Selection", msg)
            return
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, phone, email, address, credit_limit, remarks 
                FROM customers WHERE id = ?
            """, (self.selected_customer_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                QMessageBox.warning(self, "Error", "Customer not found")
                return
            old_name = row[0]
            customer_data = {
                "name": old_name,
                "phone": row[1] or "",
                "email": row[2] or "",
                "address": row[3] or "",
                "credit_limit": row[4] or 0,
                "remarks": row[5] or ""
            }
            dialog = AddEditCustomerDialog(customer_data=customer_data, language=self.current_language)
            if dialog.exec():
                data = dialog.get_data()
                if not data["name"]:
                    msg = "အမည်ထည့်ရန်လိုအပ်ပါသည်။" if self.current_language == "my" else "Name is required"
                    QMessageBox.warning(self, "Error", msg)
                    return
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE customers SET name=?, phone=?, email=?, address=?, credit_limit=?, remarks=?
                    WHERE id=?
                """, (data["name"], data["phone"], data["email"], data["address"], data["credit_limit"], data["remarks"], self.selected_customer_id))
                conn.commit()
                conn.close()
                self.load_customers()
                main_window = self.window()
                if hasattr(main_window, 'current_user'):
                    log_activity(main_window.current_user["id"], main_window.current_user["username"],
                               "Edit Customer", f"Customer: {old_name} → {data['name']}")
                msg = "ဖောက်သည်ပြင်ဆင်ပြီးပါပြီ။" if self.current_language == "my" else "Customer updated"
                QMessageBox.information(self, "Success", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not edit customer: {e}")

    def delete_customer(self):
        if self.user_role not in ['admin']:
            QMessageBox.warning(self, "Access Denied", "You don't have permission to delete customers.")
            return
        if not self.selected_customer_id:
            msg = "ကျေးဇူးပြု၍ ဖောက်သည်တစ်ဦးကို ရွေးပါ။" if self.current_language == "my" else "Please select a customer first."
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        # Check if customer has credit sales
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM credit_sales WHERE customer_id = ? AND balance_amount > 0", (self.selected_customer_id,))
        credit_count = cursor.fetchone()[0]
        conn.close()
        
        if credit_count > 0:
            msg = "This customer has outstanding credit sales. Please settle all debts before deleting." if self.current_language != "my" else "ဤဖောက်သည်တွင် အကွှေးနေသေးပါသည်။ ဖျက်မည်ဆိုပါက အကြွေးအားလုံးကို ရှင်းပါ။"
            QMessageBox.warning(self, "Cannot Delete", msg)
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM customers WHERE id=?", (self.selected_customer_id,))
        cust_name = cursor.fetchone()[0]
        conn.close()
        
        confirm_text = "ဤဖောက်သည်ကို ဖျက်မည်လား?" if self.current_language == "my" else "Delete this customer?"
        reply = QMessageBox.question(self, "Confirm Delete", confirm_text,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM customers WHERE id=?", (self.selected_customer_id,))
                conn.commit()
                conn.close()
                self.selected_customer_id = None
                self.load_customers()
                main_window = self.window()
                if hasattr(main_window, 'current_user'):
                    log_activity(main_window.current_user["id"], main_window.current_user["username"],
                               "Delete Customer", f"Customer: {cust_name}")
                msg = "ဖောက်သည်ဖျက်ပြီးပါပြီ။" if self.current_language == "my" else "Customer deleted"
                QMessageBox.information(self, "Deleted", msg)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete customer: {e}")

    def retranslateUi(self):
        lang_code = lang.get_current()
        self.current_language = lang_code
        colors = get_theme_colors()
        
        # Update SearchWidget placeholder
        if lang_code == "my":
            self.search_widget.set_placeholder_text("အမည်၊ ဖုန်း၊ အီးမေးဖွင့် ရှာရန်...")
            self.btn_add.setText(" ဖောက်သည်အသစ်")
            headers = [
                "ID", "အမည်", "ဖုန်း", "အီးမေး", "လိပ်စာ",
                "အလည်လာခဲ့မှု", "စုစုပေါင်းသုံးစွဲမှု", 
                "အမှတ်", "ခရက်ဒစ်ကန့်သတ်ချက်", "လက်ကျန်ငွေ"
            ]
        else:
            self.search_widget.set_placeholder_text("Search by name, phone, email...")
            self.btn_add.setText(" Add Customer")
            headers = [
                "ID", "Name", "Phone", "Email", "Address",
                "Total Visit", "Total Spent", "Points", "Credit Limit", "Current Balance"
            ]
        
        if hasattr(self, 'action_edit'):
            self.action_edit.setText("Edit")
        if hasattr(self, 'action_delete'):
            self.action_delete.setText("Delete")
        if hasattr(self, 'action_credit_sale'):
            self.action_credit_sale.setText("Credit Sale")
        if hasattr(self, 'action_payment'):
            self.action_payment.setText("Payment Collection")
        if hasattr(self, 'action_ledger'):
            self.action_ledger.setText("Ledger")
        if hasattr(self, 'action_outstanding_report'):
            self.action_outstanding_report.setText("Outstanding Report")
        if hasattr(self, 'action_export_excel'):
            self.action_export_excel.setText("Export Excel")
        
        # Update button icons
        self._update_button_icons()
        
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Apply theme after language change
        self._apply_theme()
        self.load_customers()

    def showEvent(self, event):
        self.load_customers()
        super().showEvent(event)