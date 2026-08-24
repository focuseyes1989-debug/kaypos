# ui/inventory_page/product_location_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QInputDialog, QHeaderView, QLineEdit,
    QLabel, QSpinBox, QGroupBox, QComboBox, QDateEdit, QFormLayout,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.language import lang
from utils.currency import format_money

# ✅ ModernButton import
from ui.widgets.modern_button import ModernButton
# ✅ ModernSearchWidget import
from ui.widgets.search_widget import ModernSearchWidget
from ui.themes.theme_manager import get_theme_colors, theme_manager
from ui.design_system.dialog_styles import modern_table_stylesheet


class ProductLocationDialog(QDialog):
    """Manage multiple locations for a single product"""
    locations_changed = pyqtSignal()
    
    def __init__(self, product_id, product_name, parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.product_name = product_name
        self.setWindowTitle(f"Manage Locations - {product_name}")
        self.setMinimumSize(750, 500)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(15)
        
        # Info label
        self.title_label = QLabel("Product locations")
        self.title_label.setObjectName("dialogTitle")
        info_label = QLabel(f"Manage batches and stock locations for {product_name}.")
        info_label.setObjectName("dialogSubtitle")
        layout.addWidget(self.title_label)
        layout.addWidget(info_label)
        
        # Location table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Location", "Quantity", "Batch No", "Expiry Date"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setColumnHidden(0, True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        
        # Add location section
        add_group = QGroupBox("Add to Location")
        add_layout = QHBoxLayout()
        add_layout.setSpacing(10)
        
        self.location_combo = QComboBox()
        self.location_combo.setMinimumWidth(150)
        self.load_locations()
        add_layout.addWidget(QLabel("Location:"))
        add_layout.addWidget(self.location_combo)
        
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 999999)
        self.qty_spin.setValue(1)
        add_layout.addWidget(QLabel("Qty:"))
        add_layout.addWidget(self.qty_spin)
        
        # ✅ ModernButton for Add
        self.btn_add = ModernButton("Add to Location", ModernButton.PRIMARY)
        self.btn_add.set_compact(True)
        self.btn_add.clicked.connect(self.add_to_location)
        add_layout.addWidget(self.btn_add)
        
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        # ✅ Buttons - ModernButton အကုန်သုံးပါ
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        # Edit button - Secondary style
        self.btn_edit = ModernButton("Edit", ModernButton.SECONDARY)
        self.btn_edit.set_compact(True)
        self.btn_edit.clicked.connect(self.edit_location)
        
        # Delete button - Custom danger style (override with stylesheet)
        self.btn_delete = ModernButton("Delete", ModernButton.TERTIARY)
        self.btn_delete.setObjectName("dangerButton")
        self.btn_delete.set_compact(True)
        self.btn_delete.clicked.connect(self.delete_location)
        
        # Move button - Custom warning style
        self.btn_move = ModernButton("Move Stock", ModernButton.SECONDARY)
        self.btn_move.setObjectName("warningButton")
        self.btn_move.set_compact(True)
        self.btn_move.clicked.connect(self.move_stock)
        
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_move)
        btn_layout.addStretch()
        
        # Close button - Tertiary style
        self.btn_close = ModernButton("Close", ModernButton.SECONDARY)
        self.btn_close.set_icon("close", size=(15, 15))
        self.btn_close.set_compact(False)
        self.btn_close.setFixedSize(112, 38)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()
        self.load_product_locations()
        self.retranslateUi()
    
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

    def _apply_theme(self, _theme_name=None):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{ background-color: {colors['bg']}; color: {colors['text']}; }}
            QLabel {{ color: {colors['text']}; background: transparent; }}
            QLabel#dialogTitle {{ font-size: 21px; font-weight: 700; }}
            QLabel#dialogSubtitle {{ color: {colors['text_secondary']}; font-size: 11px; }}
            QGroupBox {{ background-color: {colors['card_bg']}; border: 1px solid {colors['border']}; border-radius: 11px; margin-top: 10px; padding: 14px 12px 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {colors['text_secondary']}; }}
            QComboBox, QSpinBox {{ min-height: 36px; padding: 0 10px; color: {colors['text']}; background-color: {colors['input_bg']}; border: 1px solid {colors['input_border']}; border-radius: 8px; }}
            QPushButton#dangerButton {{ color: {colors['danger']}; border-color: {colors['danger']}; }}
            QPushButton#dangerButton:hover {{ background-color: {colors['danger']}; color: white; }}
            QPushButton#warningButton {{ background-color: {colors['warning']}; color: white; border-color: {colors['warning']}; }}
        """ + modern_table_stylesheet(colors))
    
    def retranslateUi(self):
        lang_code = self.get_lang()
        if lang_code == "my":
            self.setWindowTitle(f"နေရာများ စီမံရန် - {self.product_name}")
            self.table.setHorizontalHeaderLabels(["ID", "နေရာ", "ပမာဏ", "အသုတ်အမှတ်", "သက်တမ်းကုန်ရက်"])
            self.btn_add.setText("➕ နေရာသို့ထည့်")
            self.btn_edit.setText("✏️ ပြင်ဆင်")
            self.btn_delete.setText("🗑️ ဖျက်")
            self.btn_move.setText("🔄 စတော့ရွှေ့ပြောင်း")
            self.btn_close.setText("✖️ ပိတ်မည်")
        else:
            self.setWindowTitle(f"Manage Locations - {self.product_name}")
            self.table.setHorizontalHeaderLabels(["ID", "Location", "Quantity", "Batch No", "Expiry Date"])
            self.btn_add.setText("➕ Add to Location")
            self.btn_edit.setText("✏️ Edit")
            self.btn_delete.setText("🗑️ Delete")
            self.btn_move.setText("🔄 Move Stock")
            self.btn_close.setText("✖️ Close")
    
    def load_locations(self):
        """Load locations from product_locations table"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT location FROM product_locations 
            WHERE location IS NOT NULL AND location != '' 
            ORDER BY location
        """)
        rows = cursor.fetchall()
        self.location_combo.clear()
        for (name,) in rows:
            self.location_combo.addItem(name, name)
        # Add option to create new location
        self.location_combo.addItem("+ New Location", None)
        conn.close()
    
    def load_product_locations(self):
        """Load product locations from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, location, quantity, batch_no, expire_date
            FROM product_locations
            WHERE product_id = ?
            ORDER BY location
        """, (self.product_id,))
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        total_qty = 0
        
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.table.setItem(r, 1, QTableWidgetItem(row[1]))
            self.table.setItem(r, 2, QTableWidgetItem(str(row[2])))
            self.table.setItem(r, 3, QTableWidgetItem(row[3] or ""))
            self.table.setItem(r, 4, QTableWidgetItem(row[4] or ""))
            total_qty += row[2]
        
        # Update total stock in products table
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (total_qty, self.product_id))
        conn.commit()
        conn.close()
        
        self.locations_changed.emit()
    
    def add_to_location(self):
        """Add stock to a location"""
        location = self.location_combo.currentData()
        qty = self.qty_spin.value()
        
        if qty <= 0:
            QMessageBox.warning(self, "Error", "Please enter a valid quantity.")
            return
        
        if location is None:
            # Create new location
            new_location, ok = QInputDialog.getText(
                self, 
                "New Location",
                "Enter location name:"
            )
            if ok and new_location.strip():
                location = new_location.strip()
            else:
                return
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # Check if location already exists for this product
        cursor.execute(
            "SELECT id, quantity FROM product_locations WHERE product_id = ? AND location = ?",
            (self.product_id, location)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing location
            new_qty = existing[1] + qty
            cursor.execute(
                "UPDATE product_locations SET quantity = ? WHERE id = ?",
                (new_qty, existing[0])
            )
            msg = f"Updated {location}: {new_qty} units"
        else:
            # Insert new location
            cursor.execute("""
                INSERT INTO product_locations (product_id, location, quantity)
                VALUES (?, ?, ?)
            """, (self.product_id, location, qty))
            msg = f"Added {qty} units to {location}"
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(self, "Success", msg)
        self.load_product_locations()
    
    def edit_location(self):
        """Edit location details"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a location to edit.")
            return
        
        loc_id = int(self.table.item(current_row, 0).text())
        current_location = self.table.item(current_row, 1).text()
        current_qty = int(self.table.item(current_row, 2).text())
        current_batch = self.table.item(current_row, 3).text()
        current_expiry = self.table.item(current_row, 4).text()
        
        # Edit dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Location")
        dialog.setMinimumWidth(400)
        
        form_layout = QFormLayout()
        
        location_edit = QLineEdit(current_location)
        qty_edit = QSpinBox()
        qty_edit.setRange(0, 999999)
        qty_edit.setValue(current_qty)
        batch_edit = QLineEdit(current_batch)
        expiry_edit = QDateEdit()
        expiry_edit.setCalendarPopup(True)
        if current_expiry:
            expiry_edit.setDate(QDate.fromString(current_expiry, "yyyy-MM-dd"))
        
        form_layout.addRow("Location:", location_edit)
        form_layout.addRow("Quantity:", qty_edit)
        form_layout.addRow("Batch No:", batch_edit)
        form_layout.addRow("Expiry Date:", expiry_edit)
        
        # Buttons - Using ModernButton
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addStretch()
        
        btn_cancel = ModernButton("Cancel", ModernButton.TERTIARY)
        btn_cancel.set_compact(True)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_ok = ModernButton("Save", ModernButton.PRIMARY)
        btn_ok.set_compact(True)
        btn_ok.clicked.connect(dialog.accept)
        
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_ok)
        form_layout.addRow(button_layout)
        
        dialog.setLayout(form_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_location = location_edit.text().strip()
            new_qty = qty_edit.value()
            new_batch = batch_edit.text().strip()
            new_expiry = expiry_edit.date().toString("yyyy-MM-dd") if expiry_edit.date() else ""
            
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE product_locations 
                SET location = ?, quantity = ?, batch_no = ?, expire_date = ?
                WHERE id = ?
            """, (new_location, new_qty, new_batch, new_expiry, loc_id))
            conn.commit()
            conn.close()
            
            self.load_product_locations()
    
    def delete_location(self):
        """Delete a location entry"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a location to delete.")
            return
        
        loc_id = int(self.table.item(current_row, 0).text())
        location = self.table.item(current_row, 1).text()
        qty = int(self.table.item(current_row, 2).text())
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {qty} units from '{location}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM product_locations WHERE id = ?", (loc_id,))
            conn.commit()
            conn.close()
            self.load_product_locations()
    
    def move_stock(self):
        """Move stock from one location to another"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a location to move from.")
            return
        
        from_location = self.table.item(current_row, 1).text()
        from_qty = int(self.table.item(current_row, 2).text())
        
        # Get target location
        locations = []
        for row in range(self.table.rowCount()):
            loc = self.table.item(row, 1).text()
            if loc != from_location:
                locations.append(loc)
        
        if not locations:
            QMessageBox.warning(self, "No Location", "No other locations available to move to.")
            return
        
        to_location, ok = QInputDialog.getItem(
            self,
            "Move Stock",
            f"Move from '{from_location}' to:",
            locations,
            0,
            False
        )
        
        if not ok:
            return
        
        qty_to_move, ok = QInputDialog.getInt(
            self,
            "Move Stock",
            f"How many units to move from '{from_location}' to '{to_location}'?",
            min=1, max=from_qty, value=1
        )
        
        if not ok or qty_to_move <= 0:
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # Update from location
        cursor.execute(
            "UPDATE product_locations SET quantity = quantity - ? WHERE product_id = ? AND location = ?",
            (qty_to_move, self.product_id, from_location)
        )
        
        # Update to location
        cursor.execute(
            "SELECT id FROM product_locations WHERE product_id = ? AND location = ?",
            (self.product_id, to_location)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                "UPDATE product_locations SET quantity = quantity + ? WHERE id = ?",
                (qty_to_move, existing[0])
            )
        else:
            cursor.execute("""
                INSERT INTO product_locations (product_id, location, quantity)
                VALUES (?, ?, ?)
            """, (self.product_id, to_location, qty_to_move))
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(self, "Success", f"Moved {qty_to_move} units from {from_location} to {to_location}")
        self.load_product_locations()
