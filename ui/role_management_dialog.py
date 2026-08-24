from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QCheckBox, QScrollArea,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.language import lang
from ui.themes.theme_manager import get_theme_colors, theme_manager
from ui.design_system.dialog_styles import add_standard_close_footer, modern_table_stylesheet


class RoleManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Role Management")
        self.setMinimumSize(900, 700)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        self.selected_role_id = None

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        title = QLabel("Role management")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Create roles and control access to each part of the workspace.")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # ========== MAIN LAYOUT (Left + Right) ==========
        main_layout = QHBoxLayout()
        
        # ========== LEFT PANEL: Role List ==========
        left_panel = QWidget()
        left_panel.setObjectName("roleCard")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        
        left_layout.addWidget(QLabel("Roles"))
        
        self.role_table = QTableWidget()
        self.role_table.setColumnCount(3)
        self.role_table.setHorizontalHeaderLabels(["ID", "Role Name", "Description"])
        self.role_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.role_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.role_table.cellClicked.connect(self.select_role)
        self.role_table.setColumnHidden(0, True)
        header = self.role_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.role_table)
        
        btn_layout = QHBoxLayout()
        self.btn_add_role = QPushButton("Add Role")
        self.btn_add_role.clicked.connect(self.add_role)
        self.btn_delete_role = QPushButton("Delete Role")
        self.btn_delete_role.clicked.connect(self.delete_role)
        btn_layout.addWidget(self.btn_add_role)
        btn_layout.addWidget(self.btn_delete_role)
        left_layout.addLayout(btn_layout)
        
        # ========== RIGHT PANEL: Permission Settings ==========
        right_panel = QWidget()
        right_panel.setObjectName("permissionCard")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)
        
        self.role_name_edit = QLineEdit()
        self.role_name_edit.setPlaceholderText("Role Name")
        right_layout.addWidget(self.role_name_edit)
        
        self.role_desc_edit = QTextEdit()
        self.role_desc_edit.setMaximumHeight(60)
        self.role_desc_edit.setPlaceholderText("Description")
        right_layout.addWidget(self.role_desc_edit)
        
        # Permissions group
        perm_group = QGroupBox("Permissions")
        perm_layout = QVBoxLayout()
        
        # Scroll area for permissions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Permission categories
        self.permission_checkboxes = {}
        
        categories = [
            ("Dashboard", ["dashboard"]),
            ("Sales", ["sales", "create_sale", "edit_sale", "delete_sale", "refund_sale"]),
            ("Sales Summary", ["sales_summary"]),
            ("Products", ["products", "add_product", "edit_product", "delete_product"]),
            ("Ai", ["ai_pages"]),
            ("Inventory", ["inventory", "stock_in", "stock_out", "adjustment"]),
            ("Receipts", ["receipts", "print_receipt", "refund_receipt"]),
            ("Customers", ["customers", "add_customer", "edit_customer", "delete_customer"]),
            ("Expense", ["expense", "add_expense", "edit_expense", "delete_expense", "manage_expense_categories"]),
            ("Credit", ["credit", "credit_sale", "payment_collection"]),
            ("Reports", ["reports"]),
            ("Employees", ["employees", "manage_employees"]),
            ("Attendance", ["attendance", "manage_attendance"]),
            ("Shifts", ["shifts", "manage_shifts"]),
            ("Payroll", ["payroll", "manage_payroll"]),
            ("Leave", ["leave", "manage_leave"]),
            ("Employee Documents", ["employee_documents"]),
            ("Employee Finance", ["employee_finance", "manage_employee_finance"]),
            ("Employee Performance", ["employee_performance"]),
            ("Cash Sessions", ["cash_sessions", "manage_cash_sessions"]),
            ("Users & Settings", ["users", "add_user", "edit_user", "delete_user", "settings", "edit_settings"]),
            ("Backup", ["backup", "restore", "factory_reset"]),
        ]
        
        for category, perms in categories:
            cat_label = QLabel(category)
            cat_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            scroll_layout.addWidget(cat_label)
            
            for perm in perms:
                display_name = perm.replace('_', ' ').title()
                cb = QCheckBox(display_name)
                cb.setObjectName(perm)
                scroll_layout.addWidget(cb)
                self.permission_checkboxes[perm] = cb
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        perm_layout.addWidget(scroll)
        perm_group.setLayout(perm_layout)
        right_layout.addWidget(perm_group)
        
        # Buttons
        self.btn_save = QPushButton("Save Role")
        self.btn_save.clicked.connect(self.save_role)
        right_layout.addWidget(self.btn_save)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)
        
        layout.addLayout(main_layout)
        
        # Close button
        self.btn_close = add_standard_close_footer(layout, self)
        
        self.setLayout(layout)
        theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()
        self.load_roles()
        self.retranslateUi()

    def get_lang(self):
        return lang.get_current()

    def retranslateUi(self):
        lang_code = self.get_lang()
        if lang_code == "my":
            self.setWindowTitle("အခန်းကဏ္ဍ စီမံခန့်ခွဲမှု")
            self.role_name_edit.setPlaceholderText("အခန်းကဏ္ဍအမည်")
            self.role_desc_edit.setPlaceholderText("ဖော်ပြချက်")
            self.btn_add_role.setText("အခန်းကဏ္ဍအသစ်")
            self.btn_delete_role.setText("ဖျက်မည်")
            self.btn_save.setText("သိမ်းဆည်းမည်")
            self.btn_close.setText("ပိတ်မည်")
        else:
            self.setWindowTitle("Role Management")
            self.role_name_edit.setPlaceholderText("Role Name")
            self.role_desc_edit.setPlaceholderText("Description")
            self.btn_add_role.setText("Add Role")
            self.btn_delete_role.setText("Delete Role")
            self.btn_save.setText("Save Role")
            self.btn_close.setText("Close")

    def _apply_theme(self, _theme_name=None):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{ background-color: {colors['bg']}; color: {colors['text']}; }}
            QLabel {{ color: {colors['text']}; background: transparent; }}
            QLabel#dialogTitle {{ font-size: 22px; font-weight: 700; }}
            QLabel#dialogSubtitle {{ color: {colors['text_secondary']}; font-size: 11px; }}
            QWidget#roleCard, QWidget#permissionCard, QGroupBox {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QGroupBox {{ margin-top: 10px; padding-top: 12px; font-weight: 600; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {colors['text_secondary']}; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
            QLineEdit, QTextEdit {{
                color: {colors['text']}; background-color: {colors['input_bg']};
                border: 1px solid {colors['input_border']}; border-radius: 8px; padding: 8px 10px;
            }}
            QLineEdit:focus, QTextEdit:focus {{ border-color: {colors['border_hover']}; }}
            QCheckBox {{ color: {colors['text']}; spacing: 8px; padding: 3px; }}
            QPushButton {{ min-height: 36px; padding: 0 16px; border-radius: 8px; }}
        """ + modern_table_stylesheet(colors))

    def load_roles(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description FROM user_roles ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        
        self.role_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.role_table.setItem(i, 0, QTableWidgetItem(str(row[0])))
            self.role_table.setItem(i, 1, QTableWidgetItem(row[1]))
            self.role_table.setItem(i, 2, QTableWidgetItem(row[2] or ""))

    def select_role(self, row, col):
        id_item = self.role_table.item(row, 0)
        if id_item:
            self.selected_role_id = int(id_item.text())
            name_item = self.role_table.item(row, 1)
            desc_item = self.role_table.item(row, 2)
            
            self.role_name_edit.setText(name_item.text() if name_item else "")
            self.role_desc_edit.setPlainText(desc_item.text() if desc_item else "")
            
            # Load permissions for this role
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT permissions FROM user_roles WHERE id = ?", (self.selected_role_id,))
            row = cursor.fetchone()
            conn.close()
            
            # Reset checkboxes
            for cb in self.permission_checkboxes.values():
                cb.setChecked(False)
            
            if row and row[0]:
                perms = row[0].split(',')
                for perm in perms:
                    if perm in self.permission_checkboxes:
                        self.permission_checkboxes[perm].setChecked(True)

    def add_role(self):
        self.selected_role_id = None
        self.role_name_edit.clear()
        self.role_desc_edit.clear()
        for cb in self.permission_checkboxes.values():
            cb.setChecked(False)

    def delete_role(self):
        if not self.selected_role_id:
            QMessageBox.warning(self, "No Selection", "Please select a role to delete.")
            return
        
        # Check if role is in use
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE role = (SELECT name FROM user_roles WHERE id = ?)
        """, (self.selected_role_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            QMessageBox.warning(self, "Cannot Delete", f"This role is assigned to {count} user(s).")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", "Delete this role permanently?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_roles WHERE id = ?", (self.selected_role_id,))
            conn.commit()
            conn.close()
            self.load_roles()
            self.add_role()

    def save_role(self):
        role_name = self.role_name_edit.text().strip()
        role_desc = self.role_desc_edit.toPlainText().strip()
        
        if not role_name:
            QMessageBox.warning(self, "Error", "Role name is required.")
            return
        
        # Collect selected permissions
        selected_perms = []
        for perm, cb in self.permission_checkboxes.items():
            if cb.isChecked():
                selected_perms.append(perm)
        
        permissions_str = ','.join(selected_perms)
        
        conn = connect_db()
        cursor = conn.cursor()
        try:
            if self.selected_role_id:
                cursor.execute("""
                    UPDATE user_roles 
                    SET name = ?, description = ?, permissions = ?
                    WHERE id = ?
                """, (role_name, role_desc, permissions_str, self.selected_role_id))
            else:
                cursor.execute("""
                    INSERT INTO user_roles (name, description, permissions, is_system)
                    VALUES (?, ?, ?, 0)
                """, (role_name, role_desc, permissions_str))
            conn.commit()
            QMessageBox.information(self, "Success", "Role saved successfully.")
            self.load_roles()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save role: {e}")
        finally:
            conn.close()
