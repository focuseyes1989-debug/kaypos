"""English-only, server-backed settings center for KAY POS Lite."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QFileDialog, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)


class UserDialog(QDialog):
    def __init__(self, roles, user=None, parent=None):
        super().__init__(parent); self.setWindowTitle("Edit User" if user else "Add User"); self.setMinimumWidth(420)
        user = dict(user or {}); form = QFormLayout(self)
        self.username = QLineEdit(str(user.get("username") or "")); self.full_name = QLineEdit(str(user.get("full_name") or ""))
        self.role = QComboBox(); self.role.addItems(list(roles or ["Cashier"])); self.role.setCurrentText(str(user.get("role") or "Cashier"))
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit(); self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.active = QCheckBox("Active account"); self.active.setChecked(bool(user.get("active", True)))
        form.addRow("Username", self.username); form.addRow("Full Name", self.full_name); form.addRow("Role", self.role)
        form.addRow("Password" + (" (leave blank to keep)" if user else ""), self.password); form.addRow("Confirm Password", self.confirm); form.addRow("", self.active)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def values(self):
        return {"username": self.username.text().strip(), "full_name": self.full_name.text().strip(), "role": self.role.currentText(), "password": self.password.text(), "active": self.active.isChecked()}


class LiteSettingsCenter(QWidget):
    def __init__(self, host):
        super().__init__(); self.host = host; self.api = lambda: host.api; self.settings = {}; self.payment_rows = []; self.users = []; self.roles = []
        root = QHBoxLayout(self); root.setContentsMargins(18, 18, 18, 18)
        left = QVBoxLayout(); title = QLabel("Setting Center"); title.setObjectName("title"); left.addWidget(title)
        note = QLabel("KAY POS server settings · English interface"); note.setObjectName("muted"); left.addWidget(note)
        self.nav = QListWidget(); self.nav.setFixedWidth(210)
        for text in ("Appearance", "Payment Types", "Tax and Discount", "Business and Branding", "Receipt Text", "Regional", "Users"): self.nav.addItem(text)
        left.addWidget(self.nav, 1); root.addLayout(left)
        self.stack = QStackedWidget(); root.addWidget(self.stack, 1)
        self.stack.addWidget(self._appearance_page()); self.stack.addWidget(self._payment_page()); self.stack.addWidget(self._tax_page()); self.stack.addWidget(self._branding_page())
        self.stack.addWidget(self._receipt_page()); self.stack.addWidget(self._regional_page()); self.stack.addWidget(self._users_page())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex); self.nav.setCurrentRow(0)

    def _page(self, title, description):
        page = QWidget(); layout = QVBoxLayout(page); heading = QLabel(title); heading.setObjectName("title"); layout.addWidget(heading)
        sub = QLabel(description); sub.setObjectName("muted"); sub.setWordWrap(True); layout.addWidget(sub); return page, layout

    def _appearance_page(self):
        page, layout = self._page("Appearance", "Choose the display theme for this POS Lite device.")
        group = QGroupBox("Theme")
        form = QFormLayout(group)
        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark"])
        form.addRow("Color Theme", self.theme)
        layout.addWidget(group)
        layout.addStretch()
        apply_button = QPushButton("Apply Theme")
        apply_button.clicked.connect(self.save_appearance)
        layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _payment_page(self):
        page, layout = self._page("Payment Types", "Payment methods shared by KAY POS and every POS Lite client.")
        self.payment_table = QTableWidget(0, 2); self.payment_table.setHorizontalHeaderLabels(["ID", "Name"]); self.payment_table.setColumnHidden(0, True); self.payment_table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.payment_table)
        row = QHBoxLayout(); add = QPushButton("Add"); edit = QPushButton("Edit"); delete = QPushButton("Delete"); refresh = QPushButton("Refresh")
        add.clicked.connect(self.add_payment); edit.clicked.connect(self.edit_payment); delete.clicked.connect(self.delete_payment); refresh.clicked.connect(self.load_payment_types)
        for button in (add, edit, delete, refresh): row.addWidget(button)
        row.addStretch(); layout.addLayout(row); return page

    def _tax_page(self):
        page, layout = self._page("Tax and Discount", "Configure the default tax and sale discount policy.")
        group = QGroupBox("Tax"); form = QFormLayout(group); self.tax_enabled = QCheckBox("Enable tax"); self.tax_rate = QDoubleSpinBox(); self.tax_rate.setRange(0,100); self.tax_rate.setSuffix(" %"); form.addRow(self.tax_enabled); form.addRow("Tax Rate", self.tax_rate); layout.addWidget(group)
        group = QGroupBox("Discount"); form = QFormLayout(group); self.discount_enabled = QCheckBox("Enable discount"); self.discount_type = QComboBox(); self.discount_type.addItems(["percentage", "fixed", "manual"]); self.discount_value = QDoubleSpinBox(); self.discount_value.setRange(0,999999999); form.addRow(self.discount_enabled); form.addRow("Discount Type", self.discount_type); form.addRow("Default Value", self.discount_value); layout.addWidget(group); layout.addStretch(); save=QPushButton("Save Tax and Discount"); save.clicked.connect(self.save_tax); layout.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight); return page

    def _branding_page(self):
        page, layout = self._page("Business and Branding", "Business identity used on receipts and customer-facing output.")
        form = QFormLayout(); self.shop_name=QLineEdit(); self.shop_phone=QLineEdit(); self.shop_address=QTextEdit(); self.shop_address.setMaximumHeight(90); self.logo_path=QLineEdit(); self.logo_path.setReadOnly(True); self.qr_path=QLineEdit(); self.qr_path.setReadOnly(True); self.qr_name=QLineEdit()
        logo_row=QHBoxLayout(); logo_row.addWidget(self.logo_path,1); logo_button=QPushButton("Choose Logo"); logo_button.clicked.connect(lambda:self._choose_image("logo")); logo_row.addWidget(logo_button)
        qr_row=QHBoxLayout(); qr_row.addWidget(self.qr_path,1); qr_button=QPushButton("Choose QR"); qr_button.clicked.connect(lambda:self._choose_image("qr")); qr_row.addWidget(qr_button)
        form.addRow("Shop Name",self.shop_name); form.addRow("Phone",self.shop_phone); form.addRow("Address",self.shop_address); form.addRow("Logo",logo_row); form.addRow("QR Image",qr_row); form.addRow("QR Name",self.qr_name); layout.addLayout(form); layout.addStretch(); save=QPushButton("Save Business and Branding"); save.clicked.connect(self.save_branding); layout.addWidget(save,alignment=Qt.AlignmentFlag.AlignRight); return page

    def _receipt_page(self):
        page, layout = self._page("Receipt Text", "Text printed at the top and bottom of receipts.")
        form=QFormLayout(); self.receipt_header=QTextEdit(); self.receipt_header.setMaximumHeight(120); self.receipt_footer=QTextEdit(); self.receipt_footer.setMaximumHeight(120); self.footer_message=QLineEdit(); form.addRow("Header",self.receipt_header); form.addRow("Footer",self.receipt_footer); form.addRow("Footer Message",self.footer_message); layout.addLayout(form); layout.addStretch(); save=QPushButton("Save Receipt Text"); save.clicked.connect(self.save_receipt); layout.addWidget(save,alignment=Qt.AlignmentFlag.AlignRight); return page

    def _regional_page(self):
        page, layout=self._page("Regional", "POS Lite settings are currently available in English only.")
        form=QFormLayout(); self.language=QComboBox(); self.language.addItem("English","en"); self.language.setEnabled(False); self.currency=QComboBox(); self.currency.addItems(["Kyats (Ks)","Dollar ($)","Baht (B)"]); self.currency_symbol=QLineEdit(); form.addRow("Language",self.language); form.addRow("Currency",self.currency); form.addRow("Currency Symbol",self.currency_symbol); layout.addLayout(form); layout.addStretch(); save=QPushButton("Save Regional Settings"); save.clicked.connect(self.save_regional); layout.addWidget(save,alignment=Qt.AlignmentFlag.AlignRight); return page

    def _users_page(self):
        page, layout=self._page("Users", "Admin-only account management. Passwords are hashed by the server.")
        self.user_table=QTableWidget(0,5); self.user_table.setHorizontalHeaderLabels(["ID","Username","Full Name","Role","Active"]); self.user_table.setColumnHidden(0,True); self.user_table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.user_table)
        row=QHBoxLayout(); add=QPushButton("Add User"); edit=QPushButton("Edit User"); delete=QPushButton("Delete User"); refresh=QPushButton("Refresh"); add.clicked.connect(self.add_user); edit.clicked.connect(self.edit_user); delete.clicked.connect(self.delete_user); refresh.clicked.connect(self.load_users)
        for b in (add,edit,delete,refresh): row.addWidget(b)
        row.addStretch(); layout.addLayout(row); self.user_actions=(add,edit,delete); return page

    def refresh(self):
        self.theme.setCurrentText(getattr(self.host, "theme_name", "Light"))
        if not self.api(): return
        is_admin=str(self.host.user.get("role") or "").casefold()=="admin"
        self.nav.item(6).setHidden(not is_admin)
        self.host._run_task(self.api().lite_settings, self._settings_loaded, self._error)
        self.load_payment_types()
        if is_admin: self.load_users()

    def _settings_loaded(self, s):
        self.settings=dict(s); self.host.receipt_settings=dict(s); self.tax_enabled.setChecked(s.get("tax_enabled")=="1"); self.tax_rate.setValue(float(s.get("tax_rate") or 0)); self.discount_enabled.setChecked(s.get("discount_enabled")=="1"); self.discount_type.setCurrentText(s.get("discount_type") or "percentage"); self.discount_value.setValue(float(s.get("discount_value") or 0)); self.shop_name.setText(s.get("shop_name", "")); self.shop_phone.setText(s.get("shop_phone", "")); self.shop_address.setPlainText(s.get("shop_address", "")); self.logo_path.setText(s.get("shop_logo", "")); self.qr_path.setText(s.get("shop_qr_code", "")); self.qr_name.setText(s.get("shop_qr_name", "")); self.receipt_header.setPlainText(s.get("receipt_header", "")); self.receipt_footer.setPlainText(s.get("receipt_footer", "")); self.footer_message.setText(s.get("shop_footer_message", "")); self.currency.setCurrentText(s.get("currency") or "Kyats (Ks)"); self.currency_symbol.setText(s.get("currency_symbol") or "Ks")

    def _save(self, values, message): self.host._run_task(lambda:self.api().save_lite_settings(values), lambda s:(self._settings_loaded(s), QMessageBox.information(self,"Setting Center",message)), self._error)
    def save_tax(self): self._save({"tax_enabled":"1" if self.tax_enabled.isChecked() else "0","tax_rate":self.tax_rate.value(),"discount_enabled":"1" if self.discount_enabled.isChecked() else "0","discount_type":self.discount_type.currentText(),"discount_value":self.discount_value.value()},"Tax and discount settings saved.")
    def _choose_image(self, kind):
        filename,_=QFileDialog.getOpenFileName(self,"Choose Image","","Images (*.png *.jpg *.jpeg *.webp)")
        if not filename: return
        path=Path(filename); mime=mimetypes.guess_type(path.name)[0] or "image/png"; data=f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
        if kind=="logo": self.logo_path.setText(path.name); self.settings["shop_logo_image"]=data
        else: self.qr_path.setText(path.name); self.settings["shop_qr_code_image"]=data
    def save_branding(self): self._save({"shop_name":self.shop_name.text().strip(),"shop_phone":self.shop_phone.text().strip(),"shop_address":self.shop_address.toPlainText().strip(),"shop_logo":self.logo_path.text().strip(),"shop_logo_image":self.settings.get("shop_logo_image",""),"shop_qr_code":self.qr_path.text().strip(),"shop_qr_code_image":self.settings.get("shop_qr_code_image",""),"shop_qr_name":self.qr_name.text().strip()},"Business and branding settings saved.")
    def save_receipt(self): self._save({"receipt_header":self.receipt_header.toPlainText(),"receipt_footer":self.receipt_footer.toPlainText(),"shop_footer_message":self.footer_message.text()},"Receipt text saved.")
    def save_regional(self): self._save({"language":"en","currency":self.currency.currentText(),"currency_symbol":self.currency_symbol.text().strip()},"Regional settings saved.")
    def save_appearance(self):
        self.host.apply_theme(self.theme.currentText())
        self.theme.setCurrentText(self.host.theme_name)
        self.host.statusBar().showMessage(f"{self.host.theme_name} theme applied")

    def load_payment_types(self):
        if self.api(): self.host._run_task(self.api().payment_type_records,self._payments_loaded,self._error)
    def _payments_loaded(self, rows):
        self.payment_rows=list(rows); self.payment_table.setRowCount(len(rows))
        for r,data in enumerate(rows): self.payment_table.setItem(r,0,QTableWidgetItem(str(data.get("id")))); self.payment_table.setItem(r,1,QTableWidgetItem(str(data.get("name") or "")))
    def _selected(self, table, rows):
        r=table.currentRow(); return rows[r] if 0<=r<len(rows) else None
    def add_payment(self):
        name,ok=QInputDialog.getText(self,"Add Payment Type","Name");
        if ok and name.strip(): self.host._run_task(lambda:self.api().save_payment_type(name),lambda _x:self.load_payment_types(),self._error)
    def edit_payment(self):
        item=self._selected(self.payment_table,self.payment_rows)
        if not item: return self._warn("Select a payment type first.")
        name,ok=QInputDialog.getText(self,"Edit Payment Type","Name",text=item["name"])
        if ok and name.strip(): self.host._run_task(lambda:self.api().save_payment_type(name,item["id"]),lambda _x:self.load_payment_types(),self._error)
    def delete_payment(self):
        item=self._selected(self.payment_table,self.payment_rows)
        if not item: return self._warn("Select a payment type first.")
        if QMessageBox.question(self,"Delete Payment Type",f"Delete {item['name']}?")==QMessageBox.StandardButton.Yes: self.host._run_task(lambda:self.api().delete_payment_type(item["id"]),lambda _x:self.load_payment_types(),self._error)

    def load_users(self):
        if self.api(): self.host._run_task(self.api().users_settings,self._users_loaded,self._error)
    def _users_loaded(self, payload):
        self.users=list(payload.get("users") or []); self.roles=list(payload.get("roles") or []); self.user_table.setRowCount(len(self.users))
        for r,u in enumerate(self.users):
            for c,v in enumerate((u.get("id"),u.get("username"),u.get("full_name"),u.get("role"),"Yes" if u.get("active") else "No")): self.user_table.setItem(r,c,QTableWidgetItem(str(v or "")))
    def _user_dialog(self,user=None):
        dialog=UserDialog(self.roles,user,self)
        if not dialog.exec(): return
        values=dialog.values()
        if not values["username"]: return self._warn("Username is required.")
        if values["password"] != dialog.confirm.text(): return self._warn("Passwords do not match.")
        self.host._run_task(lambda:self.api().save_user(values,user.get("id") if user else None),lambda _x:self.load_users(),self._error)
    def add_user(self): self._user_dialog()
    def edit_user(self):
        user=self._selected(self.user_table,self.users)
        if user: self._user_dialog(user)
        else: self._warn("Select a user first.")
    def delete_user(self):
        user=self._selected(self.user_table,self.users)
        if not user: return self._warn("Select a user first.")
        if QMessageBox.question(self,"Delete User",f"Delete {user['username']}?")==QMessageBox.StandardButton.Yes: self.host._run_task(lambda:self.api().delete_user(user["id"]),lambda _x:self.load_users(),self._error)
    def _warn(self,text): QMessageBox.warning(self,"Setting Center",text)
    def _error(self,text): QMessageBox.critical(self,"Setting Center",text)
