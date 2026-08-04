# ui/inventory_page/stock_movement_dialog.py
from PyQt6.QtWidgets import QMessageBox, QLabel, QPushButton
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QIcon, QColor
from ui.base_form_dialog import BaseFormDialog
from models.database import connect_db
from utils.currency import format_money
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
import os


class BaseStockMovementDialog(BaseFormDialog):
    def __init__(self, title, fields, movement_type, parent=None):
        self.movement_type = movement_type  # 'in', 'out', 'adjust'
        self._is_dark = is_dark_theme()
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        super().__init__(title, fields, parent)
        self.all_products = []
        self.load_products()
        
        # Apply theme
        self._apply_theme()
        
        # Connect search
        if 'search' in self.inputs:
            self.inputs['search'].textChanged.connect(self.filter_products)
        
        self.inputs['product'].currentIndexChanged.connect(self.on_product_selected)
        self.setup_extra()
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update buttons
        for child in self.findChildren(ModernButton):
            child.update_theme()
            if "save" in child.objectName().lower() or "ok" in child.objectName().lower():
                child.set_icon("save", size=(16, 16))
            elif "cancel" in child.objectName().lower():
                child.set_icon("close", size=(16, 16))
    
    def _load_svg_icon(self, icon_name, size=(20, 20)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                from PyQt6.QtGui import QPixmap
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        # Try PNG fallback
        png_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(png_path):
            try:
                from PyQt6.QtGui import QPixmap
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        return None

    def load_products(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by FROM products ORDER BY name")
        self.all_products = cursor.fetchall()
        conn.close()
        self.filter_products()

    def filter_products(self):
        search_text = self.inputs.get('search', None)
        if search_text:
            text = search_text.text().strip().lower()
        else:
            text = ""
        self.inputs['product'].clear()
        for pid, name, barcode, sku, sold_by in self.all_products:
            if (text in name.lower() or (barcode and text in barcode.lower()) or (sku and text in sku.lower())):
                display = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                self.inputs['product'].addItem(display, pid)
        if self.inputs['product'].count() > 0:
            self.inputs['product'].setCurrentIndex(0)

    def on_product_selected(self):
        pass  # override

    def setup_extra(self):
        pass

    def get_product_id(self):
        return self.inputs['product'].currentData()

    def validate(self):
        product_id = self.get_product_id()
        if product_id is None:
            QMessageBox.warning(self, "Error", "Please select a valid product.")
            return False
        return True


class StockInDialog(BaseStockMovementDialog):
    def __init__(self, parent=None):
        fields = [
            {'name': 'stock_in_no', 'label': 'Stock In No', 'type': 'line', 'readonly': True},
            {'name': 'search', 'label': 'Search Product', 'type': 'line'},
            {'name': 'product', 'label': 'Product', 'type': 'combo'},
            {'name': 'supplier', 'label': 'Supplier', 'type': 'combo'},
            {'name': 'po_no', 'label': 'PO No', 'type': 'line'},
            {'name': 'qty', 'label': 'Quantity', 'type': 'spin', 'range': (1, 999999)},
            {'name': 'unit_cost', 'label': 'Unit Cost', 'type': 'double', 'range': (0, 1000000), 'decimals': 2},
            {'name': 'total_cost', 'label': 'Total Cost', 'type': 'line', 'readonly': True},
            {'name': 'batch_no', 'label': 'Batch No', 'type': 'line'},
            {'name': 'expiry', 'label': 'Expiry Date', 'type': 'date', 'default': QDate.currentDate().addDays(30)},
            {'name': 'received_by', 'label': 'Received By', 'type': 'line', 'required': True},
            {'name': 'date', 'label': 'Date', 'type': 'date', 'default': QDate.currentDate()},
            {'name': 'notes', 'label': 'Notes', 'type': 'text'},
        ]
        super().__init__("Stock In", fields, 'in', parent)
        self.stock_in_no.setText(f"SIN-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.load_suppliers()
        self.inputs['unit_cost'].valueChanged.connect(self.update_total)
        self.inputs['qty'].valueChanged.connect(self.update_total)
        self.update_total()
        
        # Update button icons
        self._update_button_icons()

    def _update_button_icons(self):
        """Update button icons"""
        for child in self.findChildren(ModernButton):
            if "save" in child.objectName().lower() or "ok" in child.objectName().lower():
                child.set_icon("save", size=(16, 16))
            elif "cancel" in child.objectName().lower():
                child.set_icon("close", size=(16, 16))

    def load_suppliers(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
        for sid, name in cursor.fetchall():
            self.inputs['supplier'].addItem(name, sid)
        conn.close()

    def filter_products(self):
        search_text = self.inputs['search'].text().strip().lower()
        self.inputs['product'].clear()
        for pid, name, barcode, sku, sold_by in self.all_products:
            if (search_text in name.lower() or (barcode and search_text in barcode.lower()) or (sku and search_text in sku.lower())):
                display = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                self.inputs['product'].addItem(display, pid)
        if self.inputs['product'].count() > 0:
            self.inputs['product'].setCurrentIndex(0)

    def update_total(self):
        qty = self.inputs['qty'].value()
        cost = self.inputs['unit_cost'].value()
        total = qty * cost
        self.inputs['total_cost'].setText(format_money(total))

    def accept(self):
        if not self.validate():
            return
        product_id = self.get_product_id()
        qty = self.inputs['qty'].value()
        unit_cost = self.inputs['unit_cost'].value()
        batch_no = self.inputs['batch_no'].text()
        expire = self.inputs['expiry'].date().toString("yyyy-MM-dd")
        received_by = self.inputs['received_by'].text()
        notes = self.inputs['notes'].toPlainText()
        if not received_by:
            QMessageBox.warning(self, "Error", "Received By is required")
            return
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT stock, cost FROM products WHERE id=?", (product_id,))
            old_stock, old_cost = cursor.fetchone()
            new_stock = old_stock + qty
            cursor.execute("UPDATE products SET stock = ?, cost = ?, expire_date = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                           (new_stock, unit_cost, expire, product_id))
            cursor.execute("INSERT INTO stock_movements (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes) VALUES (?, 'in', ?, ?, ?, ?, ?, ?, ?)",
                           (product_id, qty, old_stock, new_stock, f"Stock In via {self.inputs['stock_in_no'].text()}", self.inputs['po_no'].text(), received_by, notes))
            conn.commit()
            QMessageBox.information(self, "Success", f"Stock In recorded. New stock: {new_stock}")
            super().accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()


class StockOutDialog(BaseStockMovementDialog):
    def __init__(self, parent=None):
        fields = [
            {'name': 'stock_out_no', 'label': 'Stock Out No', 'type': 'line', 'readonly': True},
            {'name': 'search', 'label': 'Search Product', 'type': 'line'},
            {'name': 'product', 'label': 'Product', 'type': 'combo'},
            {'name': 'customer', 'label': 'Customer', 'type': 'combo'},
            {'name': 'qty', 'label': 'Quantity', 'type': 'spin', 'range': (1, 999999)},
            {'name': 'reason', 'label': 'Reason', 'type': 'combo', 'items': ['Sale', 'Damage', 'Transfer', 'Other']},
            {'name': 'reference', 'label': 'Reference No', 'type': 'line'},
            {'name': 'issued_by', 'label': 'Issued By', 'type': 'line', 'required': True},
            {'name': 'date', 'label': 'Date', 'type': 'date', 'default': QDate.currentDate()},
            {'name': 'notes', 'label': 'Notes', 'type': 'text'},
        ]
        super().__init__("Stock Out", fields, 'out', parent)
        self.stock_out_no.setText(f"SOUT-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.load_customers()
        self.inputs['qty'].valueChanged.connect(self.update_stock_display)
        self.update_stock_display()
        
        # Update button icons
        self._update_button_icons()

    def _update_button_icons(self):
        """Update button icons"""
        for child in self.findChildren(ModernButton):
            if "save" in child.objectName().lower() or "ok" in child.objectName().lower():
                child.set_icon("save", size=(16, 16))
            elif "cancel" in child.objectName().lower():
                child.set_icon("close", size=(16, 16))

    def load_customers(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM customers ORDER BY name")
        for cid, name in cursor.fetchall():
            self.inputs['customer'].addItem(name, cid)
        conn.close()

    def filter_products(self):
        search_text = self.inputs['search'].text().strip().lower()
        self.inputs['product'].clear()
        for pid, name, barcode, sku, sold_by in self.all_products:
            if (search_text in name.lower() or (barcode and search_text in barcode.lower()) or (sku and search_text in sku.lower())):
                display = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                self.inputs['product'].addItem(display, pid)
        if self.inputs['product'].count() > 0:
            self.inputs['product'].setCurrentIndex(0)

    def on_product_selected(self):
        self.update_stock_display()

    def update_stock_display(self):
        product_id = self.get_product_id()
        if product_id:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                stock = row[0] if row[0] else 0
                qty = self.inputs['qty'].value()
                self.inputs['qty'].setMaximum(stock)
                self.set_status_label(f"Available stock: {stock}")

    def accept(self):
        if not self.validate():
            return
        product_id = self.get_product_id()
        qty = self.inputs['qty'].value()
        reason = self.inputs['reason'].currentText()
        reference = self.inputs['reference'].text()
        issued_by = self.inputs['issued_by'].text()
        notes = self.inputs['notes'].toPlainText()
        if not issued_by:
            QMessageBox.warning(self, "Error", "Issued By is required")
            return
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
            old_stock = cursor.fetchone()[0]
            if old_stock < qty:
                QMessageBox.warning(self, "Error", f"Insufficient stock. Only {old_stock} available")
                return
            new_stock = old_stock - qty
            cursor.execute("UPDATE products SET stock = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                           (new_stock, product_id))
            cursor.execute("INSERT INTO stock_movements (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes) VALUES (?, 'out', ?, ?, ?, ?, ?, ?, ?)",
                           (product_id, qty, old_stock, new_stock, reason, reference, issued_by, notes))
            conn.commit()
            QMessageBox.information(self, "Success", f"Stock Out recorded. New stock: {new_stock}")
            super().accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()


class AdjustmentDialog(BaseStockMovementDialog):
    def __init__(self, parent=None):
        fields = [
            {'name': 'adjustment_no', 'label': 'Adjustment No', 'type': 'line', 'readonly': True},
            {'name': 'search', 'label': 'Search Product', 'type': 'line'},
            {'name': 'product', 'label': 'Product', 'type': 'combo'},
            {'name': 'location', 'label': 'Location', 'type': 'combo'},
            {'name': 'old_qty', 'label': 'Current Qty', 'type': 'line', 'readonly': True},
            {'name': 'new_qty', 'label': 'New Qty', 'type': 'spin', 'range': (0, 999999)},
            {'name': 'reason', 'label': 'Reason', 'type': 'line', 'required': True},
            {'name': 'staff', 'label': 'Adjusted By', 'type': 'line', 'required': True},
            {'name': 'date', 'label': 'Date', 'type': 'date', 'default': QDate.currentDate()},
            {'name': 'notes', 'label': 'Notes', 'type': 'text'},
        ]
        super().__init__("Stock Adjustment", fields, 'adjust', parent)
        self.adjustment_no.setText(f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.load_locations()
        self.inputs['new_qty'].valueChanged.connect(self.update_diff)
        self.update_diff()
        
        # Update button icons
        self._update_button_icons()

    def _update_button_icons(self):
        """Update button icons"""
        for child in self.findChildren(ModernButton):
            if "save" in child.objectName().lower() or "ok" in child.objectName().lower():
                child.set_icon("save", size=(16, 16))
            elif "cancel" in child.objectName().lower():
                child.set_icon("close", size=(16, 16))

    def load_locations(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT location FROM product_locations WHERE location IS NOT NULL AND location != '' ORDER BY location")
        for (name,) in cursor.fetchall():
            self.inputs['location'].addItem(name, name)
        self.inputs['location'].addItem("+ Add New Location", "__NEW__")
        conn.close()

    def filter_products(self):
        search_text = self.inputs['search'].text().strip().lower()
        self.inputs['product'].clear()
        for pid, name, barcode, sku, sold_by in self.all_products:
            if (search_text in name.lower() or (barcode and search_text in barcode.lower()) or (sku and search_text in sku.lower())):
                display = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                self.inputs['product'].addItem(display, pid)
        if self.inputs['product'].count() > 0:
            self.inputs['product'].setCurrentIndex(0)

    def on_product_selected(self):
        self.update_stock_display()

    def update_stock_display(self):
        product_id = self.get_product_id()
        if product_id:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                stock = row[0] if row[0] else 0
                self.inputs['old_qty'].setText(str(stock))
                self.inputs['new_qty'].setValue(stock)
                self.update_diff()

    def update_diff(self):
        try:
            old = int(self.inputs['old_qty'].text()) if self.inputs['old_qty'].text().isdigit() else 0
        except:
            old = 0
        new = self.inputs['new_qty'].value()
        diff = new - old
        self.set_status_label(f"Difference: {diff:+d}")

    def accept(self):
        if not self.validate():
            return
        product_id = self.get_product_id()
        new_qty = self.inputs['new_qty'].value()
        reason = self.inputs['reason'].text()
        staff = self.inputs['staff'].text()
        notes = self.inputs['notes'].toPlainText()
        if not reason:
            QMessageBox.warning(self, "Error", "Reason is required")
            return
        if not staff:
            QMessageBox.warning(self, "Error", "Adjusted By is required")
            return
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
            old_stock = cursor.fetchone()[0]
            cursor.execute("UPDATE products SET stock = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                           (new_qty, product_id))
            cursor.execute("INSERT INTO stock_movements (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes) VALUES (?, 'adjustment', ?, ?, ?, ?, ?, ?, ?)",
                           (product_id, abs(new_qty - old_stock), old_stock, new_qty, reason, f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}", staff, notes))
            conn.commit()
            QMessageBox.information(self, "Success", f"Stock adjusted from {old_stock} to {new_qty}")
            super().accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()