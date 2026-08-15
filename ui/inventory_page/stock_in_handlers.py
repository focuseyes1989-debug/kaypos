# ui/inventory_page/stock_in_handlers.py
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from models.database import connect_db
from utils.currency import format_money
from utils.translations import tr
from utils.unit_conversion import (
    get_product_unit_settings,
    normalize_unit_settings,
    to_base_quantity,
    to_base_unit_cost,
    unit_combo_items,
)
from datetime import datetime
import os


class StockInHandlers:
    """Event handlers for StockInDialog"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.all_products = []
        self.current_product_id = None
        self.current_variant_id = None
        self.current_unit_settings = normalize_unit_settings()
    
    def setup_signals(self):
        """Connect all signals"""
        d = self.dialog
        d.si_unit_cost.valueChanged.connect(self.update_total)
        d.si_qty.valueChanged.connect(self.update_total)
        d.si_qty.valueChanged.connect(self.update_current_stock_after_qty)
        if hasattr(d, "si_unit"):
            d.si_unit.currentIndexChanged.connect(self.update_total)
            d.si_unit.currentIndexChanged.connect(self.update_current_stock_after_qty)
        d.btn_save.clicked.connect(self.save)
        d.si_location.currentIndexChanged.connect(self.on_location_changed)
        d.si_product.currentIndexChanged.connect(self.update_product_info)
        if hasattr(d, "si_variant"):
            d.si_variant.currentIndexChanged.connect(self.on_variant_changed)
        d.product_search.textChanged.connect(self.filter_products)
        d.product_search.returnPressed.connect(self.on_search_entered)
        d.btn_cancel.clicked.connect(d.reject)
    
    def load_dropdowns(self):
        """Load products and suppliers"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by, stock FROM products ORDER BY name")
        self.all_products = cursor.fetchall()
        self.filter_products()
        
        cursor.execute("SELECT id, name FROM suppliers WHERE status = 'Active' ORDER BY name")
        sups = cursor.fetchall()
        d = self.dialog
        d.si_supplier.clear()
        d.si_supplier.addItem("None", None)
        for sid, name in sups:
            d.si_supplier.addItem(name, sid)
        conn.close()
    
    def load_locations(self):
        """Load locations from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT location FROM product_locations 
            WHERE location IS NOT NULL AND location != '' ORDER BY location
        """)
        rows = cursor.fetchall()
        
        d = self.dialog
        d.si_location.blockSignals(True)
        d.si_location.clear()
        # ✅ REMOVED: "None" option
        
        locations_set = set()
        for (name,) in rows:
            locations_set.add(name)
        
        for location in sorted(locations_set):
            d.si_location.addItem(location, location)
        
        d.si_location.addItem("+ Add New Location", "__NEW__")
        d.si_location.blockSignals(False)
        conn.close()
    
    def filter_products(self):
        """Filter products based on search text"""
        search_text = self.dialog.product_search.text().strip().lower()
        d = self.dialog
        d.si_product.clear()
        d.si_product.blockSignals(True)
        for pid, name, barcode, sku, sold_by, stock in self.all_products:
            if (search_text in name.lower() or 
                (barcode and search_text in barcode.lower()) or 
                (sku and search_text in sku.lower())):
                display_text = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                d.si_product.addItem(display_text, pid)
        d.si_product.blockSignals(False)
        if d.si_product.count() > 0:
            d.si_product.setCurrentIndex(0)
            self.update_current_stock()
            self.update_product_info()
    
    def set_product(self, product_id, product_name=None):
        """Set the product to be pre-selected"""
        if product_id is None:
            return
            
        if not self.all_products:
            self.load_dropdowns()
        
        d = self.dialog
        for i in range(d.si_product.count()):
            if d.si_product.itemData(i) == product_id:
                d.si_product.setCurrentIndex(i)
                if product_name:
                    d.product_search.setText(product_name)
                self.update_total()
                self.update_current_stock()
                self.update_product_info()
                QTimer.singleShot(200, lambda: d.si_qty.setFocus())
                return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by, stock, image FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if product:
            pid, name, barcode, sku, sold_by, stock, image = product
            display_text = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
            d.si_product.addItem(display_text, pid)
            d.si_product.setCurrentIndex(d.si_product.count() - 1)
            d.product_search.setText(name)
            self.update_total()
            self.update_current_stock()
            self.update_product_info()
            QTimer.singleShot(200, lambda: d.si_qty.setFocus())
    
    def update_product_info(self):
        """Update product information and image preview"""
        d = self.dialog
        product_id = d.si_product.currentData()
        if product_id is None:
            d.image_preview.setText("📷 No Image\n\nSelect a product to preview")
            d.product_details_label.setText("Select a product to view details")
            self.update_unit_selector(None)
            return
        self.load_product_variants(product_id)
        self.update_unit_selector(product_id)
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, barcode, sku, sold_by, stock, cost, image
            FROM products WHERE id = ?
        """, (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            name, barcode, sku, sold_by, stock, cost, image = row
            
            details = f"""
<b style='font-size:11pt;'>{name}</b><br>
<span style='color:#5d6d7e;'>📌 SKU:</span> <b>{sku or 'N/A'}</b> &nbsp;|&nbsp; 
<span style='color:#5d6d7e;'>🔢 Barcode:</span> <b>{barcode or 'N/A'}</b><br>
<span style='color:#5d6d7e;'>📦 Stock:</span> <b style='color:#2c3e50;'>{stock or 0}</b> &nbsp;|&nbsp; 
<span style='color:#5d6d7e;'>💰 Cost:</span> <b style='color:#27ae60;'>{format_money(cost or 0)}</b><br>
<span style='color:#5d6d7e;'>🔄 Type:</span> <b>{sold_by or 'Each'}</b>
            """
            d.product_details_label.setText(details)
            
            if image and os.path.exists(image):
                try:
                    pixmap = QPixmap(image)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            d.image_preview.width() - 30,
                            d.image_preview.height() - 30,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        d.image_preview.setPixmap(scaled_pixmap)
                        d.image_preview.setText("")
                    else:
                        d.image_preview.setText("🖼️ Invalid Image")
                except Exception:
                    d.image_preview.setText("🖼️ Image Not Available")
            else:
                d.image_preview.setText("📷 No Image Available")
        else:
            d.image_preview.setText("📷 No Image\n\nSelect a product to preview")
            d.product_details_label.setText("Select a product to view details")
    
    def update_unit_selector(self, product_id):
        """Refresh stock-in unit choices for the selected product."""
        d = self.dialog
        if not hasattr(d, "si_unit"):
            return
        settings = normalize_unit_settings()
        if product_id is not None:
            conn = connect_db()
            cursor = conn.cursor()
            settings = get_product_unit_settings(cursor, product_id)
            conn.close()
        self.current_unit_settings = settings
        previous = d.si_unit.currentData()
        d.si_unit.blockSignals(True)
        d.si_unit.clear()
        for label, value in unit_combo_items(settings):
            d.si_unit.addItem(label, value)
        idx = d.si_unit.findData(previous)
        d.si_unit.setCurrentIndex(idx if idx >= 0 else 0)
        d.si_unit.blockSignals(False)
        self.update_total()

    def _selected_stock_in_unit(self):
        if hasattr(self.dialog, "si_unit"):
            return self.dialog.si_unit.currentData() or "base"
        return "base"

    def _stock_in_base_qty(self):
        return to_base_quantity(
            self.dialog.si_qty.value(),
            self._selected_stock_in_unit(),
            self.current_unit_settings,
        )

    def _stock_in_base_cost(self):
        return to_base_unit_cost(
            self.dialog.si_unit_cost.value(),
            self._selected_stock_in_unit(),
            self.current_unit_settings,
        )

    def update_current_stock(self):
        """Update the current stock label based on selected product"""
        d = self.dialog
        product_id = d.si_product.currentData()
        if product_id is None:
            d.current_stock_label.setVisible(False)
            self.current_product_id = None
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            stock = row[0] if row[0] is not None else 0
            d.current_stock_label.setText(f"📊 Stock: {stock}")
            d.current_stock_label.setVisible(True)
            self.current_product_id = product_id
        else:
            d.current_stock_label.setVisible(False)
            self.current_product_id = None
    
    def update_current_stock_after_qty(self):
        """Update current stock display to show after stock-in"""
        d = self.dialog
        product_id = d.si_product.currentData()
        if product_id is None:
            return
        
        qty = self._stock_in_base_qty()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            current_stock = row[0] if row[0] is not None else 0
            after_stock = current_stock + qty
            d.current_stock_label.setText(f"📊 {current_stock} → {after_stock}")
            d.current_stock_label.setVisible(True)
    
    def update_total(self):
        """Update total cost display using format_money"""
        d = self.dialog
        qty = d.si_qty.value()
        cost = d.si_unit_cost.value()
        total = qty * cost
        d.si_total_cost.setText(format_money(total))

    def load_product_variants(self, product_id):
        """Load active variants for selected product."""
        d = self.dialog
        if not hasattr(d, "si_variant"):
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, size, color, sku, barcode, stock
            FROM product_variants
            WHERE product_id = ? AND COALESCE(active, 1) = 1
            ORDER BY size, color, id
        """, (product_id,))
        rows = cursor.fetchall()
        conn.close()

        d.si_variant.blockSignals(True)
        d.si_variant.clear()
        for variant_id, size, color, sku, barcode, stock in rows:
            label_parts = [part for part in (color or "", size or "") if part]
            label = " / ".join(label_parts) or sku or barcode or f"Variant #{variant_id}"
            d.si_variant.addItem(f"{label} - Stock: {stock or 0}", variant_id)
        has_variants = bool(rows)
        d.variant_label.setVisible(has_variants)
        d.si_variant.setVisible(has_variants)
        d.si_variant.blockSignals(False)
        if has_variants:
            d.si_variant.setCurrentIndex(0)

    def on_variant_changed(self, *_):
        self.update_current_stock()
        self.update_current_stock_after_qty()

    def _selected_variant_id(self):
        d = self.dialog
        if hasattr(d, "si_variant") and d.si_variant.isVisible():
            return d.si_variant.currentData()
        return None

    def update_current_stock(self):
        """Update current stock for selected product or variant."""
        d = self.dialog
        product_id = d.si_product.currentData()
        if product_id is None:
            d.current_stock_label.setVisible(False)
            self.current_product_id = None
            self.current_variant_id = None
            return

        variant_id = self._selected_variant_id()
        conn = connect_db()
        cursor = conn.cursor()
        if variant_id:
            cursor.execute("SELECT stock FROM product_variants WHERE id = ? AND product_id = ?", (variant_id, product_id))
        else:
            cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            d.current_stock_label.setVisible(False)
            self.current_product_id = None
            self.current_variant_id = None
            return
        stock = row[0] if row[0] is not None else 0
        d.current_stock_label.setText(f"Stock: {stock}")
        d.current_stock_label.setVisible(True)
        self.current_product_id = product_id
        self.current_variant_id = variant_id

    def update_current_stock_after_qty(self):
        """Update current stock display to show after stock-in."""
        d = self.dialog
        product_id = d.si_product.currentData()
        if product_id is None:
            return
        qty = self._stock_in_base_qty()
        variant_id = self._selected_variant_id()
        conn = connect_db()
        cursor = conn.cursor()
        if variant_id:
            cursor.execute("SELECT stock FROM product_variants WHERE id = ? AND product_id = ?", (variant_id, product_id))
        else:
            cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            current_stock = row[0] if row[0] is not None else 0
            d.current_stock_label.setText(f"{current_stock} -> {current_stock + qty}")
            d.current_stock_label.setVisible(True)
    
    def on_search_entered(self):
        """Handle search entry - stay in field after scanning/searching"""
        d = self.dialog
        search_text = d.product_search.text().strip()
        
        if search_text:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name FROM products 
                WHERE barcode = ? OR sku = ? 
                LIMIT 1
            """, (search_text, search_text))
            product = cursor.fetchone()
            conn.close()
            
            if product:
                pid, name = product
                for i in range(d.si_product.count()):
                    if d.si_product.itemData(i) == pid:
                        d.si_product.setCurrentIndex(i)
                        d.product_search.setStyleSheet("""
                            QLineEdit {
                                padding: 10px 14px;
                                border: 2px solid #27ae60;
                                border-radius: 6px;
                                background: white;
                                font-size: 10pt;
                            }
                        """)
                        self.update_current_stock()
                        self.update_product_info()
                        QTimer.singleShot(300, lambda: d.product_search.setStyleSheet("""
                            QLineEdit {
                                padding: 10px 14px;
                                border: 2px solid #dfe6e9;
                                border-radius: 6px;
                                background: white;
                                font-size: 10pt;
                            }
                            QLineEdit:focus {
                                border-color: #5865f2;
                            }
                        """))
                        return
            
            d.product_search.setFocus()
            d.product_search.selectAll()
    
    def on_location_changed(self, index):
        """Handle location selection change"""
        d = self.dialog
        if index < 0:
            return
        
        current_data = d.si_location.currentData()
        current_text = d.si_location.currentText()
        
        if current_data == "__NEW__" or current_text == "+ Add New Location":
            self.add_new_location()
    
    def add_new_location(self):
        """Add a new location"""
        d = self.dialog
        lang = self.get_lang()
        
        new_location, ok = QInputDialog.getText(
            self.dialog,
            "New Location" if lang != "my" else "နေရာအသစ်ထည့်ရန်",
            "Enter location name:" if lang != "my" else "နေရာအမည်ထည့်ပါ:"
        )
        
        if ok and new_location.strip():
            new_location = new_location.strip()
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM product_locations WHERE location = ?", (new_location,))
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                conn.close()
                msg = f"Location '{new_location}' already exists!" if lang != "my" else f"နေရာ '{new_location}' ရှိပြီးသားပါ။"
                QMessageBox.warning(self.dialog, tr("error"), msg)
                self.load_locations()
                index = d.si_location.findText(new_location)
                if index >= 0:
                    d.si_location.setCurrentIndex(index)
                return
            
            cursor.execute("SELECT id FROM products LIMIT 1")
            product = cursor.fetchone()
            
            if product:
                cursor.execute("""
                    INSERT INTO product_locations (product_id, location, quantity)
                    VALUES (?, ?, 0)
                """, (product[0], new_location))
                conn.commit()
                msg = f"Location '{new_location}' added successfully!" if lang != "my" else f"နေရာ '{new_location}' ထည့်သွင်းပြီးပါပြီ။"
                success = True
            else:
                msg = "No products found. Please add a product first, then add locations." if lang != "my" else "ပစ္စည်းမရှိပါ။ ပစ္စည်းအရင်ထည့်ပြီးမှ နေရာအသစ်ထည့်ပါ။"
                success = False
            
            conn.close()
            
            if success:
                self.load_locations()
                index = d.si_location.findText(new_location)
                if index >= 0:
                    d.si_location.setCurrentIndex(index)
                QMessageBox.information(self.dialog, tr("success"), msg)
            else:
                QMessageBox.warning(self.dialog, tr("warning"), msg)
                if d.si_location.count() > 0:
                    d.si_location.setCurrentIndex(0)
        else:
            if d.si_location.count() > 0:
                d.si_location.setCurrentIndex(0)
    
    def save(self):
        """Save stock in transaction"""
        d = self.dialog
        product_id = d.si_product.currentData()
        if product_id is None:
            QMessageBox.warning(self.dialog, tr("error"), tr("valid_product_required"))
            return
        
        entered_qty = d.si_qty.value()
        entered_unit_cost = d.si_unit_cost.value()
        qty = self._stock_in_base_qty()
        unit_cost = self._stock_in_base_cost()
        batch_no = d.si_batch_no.text().strip()
        expire = d.si_expiry.date().toString("yyyy-MM-dd")
        received_by = d.si_received_by.text().strip()
        notes = d.si_notes.toPlainText()
        supplier_id = d.si_supplier.currentData()
        po_no_input = d.si_po_no.text().strip()
        payment_status = d.si_payment_status.currentText()
        location = d.si_location.currentData()
        lang = self.get_lang()
        variant_id = self._selected_variant_id()
        
        if not received_by:
            msg = "လက်ခံသူအမည် ထည့်ရန်လိုအပ်ပါသည်။" if lang == "my" else "Received By is required"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        # ✅ Updated validation
        if location == "__NEW__":
            msg = "Please select a valid location or add a new one first." if lang != "my" else "ကျေးဇူးပြု၍ နေရာတစ်ခုရွေးပါ သို့မဟုတ် အသစ်ထည့်ပါ။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        # ✅ If no location selected, use "Default"
        if location is None:
            location = "Default"

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            
            cursor.execute("SELECT stock, cost, supplier_id FROM products WHERE id=?", (product_id,))
            old_stock, old_cost, old_supplier = cursor.fetchone()
            old_stock = old_stock if old_stock is not None else 0
            old_cost = old_cost if old_cost is not None else 0
            new_stock = old_stock + qty
            
            if new_stock > 0:
                new_average_cost = ((old_stock * old_cost) + (qty * unit_cost)) / new_stock
            else:
                new_average_cost = unit_cost
            
            if old_supplier is None and supplier_id:
                cursor.execute("""
                    UPDATE products 
                    SET stock = ?, cost = ?, expire_date = ?, supplier_id = ?, 
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_stock, new_average_cost, expire, supplier_id, product_id))
            else:
                cursor.execute("""
                    UPDATE products 
                    SET stock = ?, cost = ?, expire_date = ?, 
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_stock, new_average_cost, expire, product_id))

            if variant_id:
                cursor.execute("""
                    UPDATE product_variants
                    SET stock = stock + ?, cost = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND product_id = ?
                """, (qty, unit_cost, variant_id, product_id))
            
            if location:
                if not batch_no:
                    batch_no = f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                expire_value = expire if expire else ""
                cursor.execute("""
                    INSERT INTO product_locations (product_id, location, batch_no, expire_date, quantity)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(product_id, location, batch_no, expire_date) 
                    DO UPDATE SET quantity = product_locations.quantity + excluded.quantity,
                                  last_updated = CURRENT_TIMESTAMP
                """, (product_id, location, batch_no, expire_value, qty))
            
            cursor.execute("""
                INSERT INTO stock_movements 
                (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes, supplier_id, location)
                VALUES (?, 'in', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, qty, old_stock, new_stock, f"Stock In via {d.stock_in_no.text()}", 
                  po_no_input, received_by, notes, supplier_id, location))
            
            if supplier_id and supplier_id != "None":
                if not po_no_input:
                    po_no_input = f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                order_date = d.si_date.date().toString("yyyy-MM-dd")
                total_amount = entered_qty * entered_unit_cost
                cursor.execute("""
                    INSERT INTO purchase_orders 
                    (po_no, supplier_id, order_date, total_amount, status, payment_status, received_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (po_no_input, supplier_id, order_date, total_amount, 'completed', payment_status, received_by, notes))
                po_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO purchase_order_items 
                    (po_id, product_id, quantity, unit_price, total)
                    VALUES (?, ?, ?, ?, ?)
                """, (po_id, product_id, qty, unit_cost, total_amount))
                
                cursor.execute("""
                    INSERT INTO supplier_payments 
                    (supplier_id, amount, payment_date, reference_no, payment_type, notes, purchase_order_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (supplier_id, total_amount, order_date, po_no_input, 'Purchase', notes, po_id))
                
                if payment_status == "Paid":
                    cursor.execute("""
                        INSERT INTO supplier_payments 
                        (supplier_id, amount, payment_date, reference_no, payment_type, notes, purchase_order_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (supplier_id, total_amount, order_date, po_no_input, 'Paid', f"Full payment for {po_no_input}", po_id))

            conn.commit()
            
            if location:
                expire_value = expire if expire else ""
                cursor.execute("SELECT quantity FROM product_locations WHERE product_id=? AND location=? AND batch_no=? AND expire_date=?", 
                             (product_id, location, batch_no, expire_value))
                location_qty = cursor.fetchone()
                loc_qty = location_qty[0] if location_qty else 0
                expiry_display = expire if expire else "No Expiry"
                msg = f"စတော့ဝင်ပြီးပါပြီ။ နေရာ {location} တွင် လက်ကျန်: {loc_qty} (Batch: {batch_no}, Expiry: {expiry_display})" if lang == "my" else f"Stock In recorded. Location {location} now has: {loc_qty} (Batch: {batch_no}, Expiry: {expiry_display})"
            else:
                msg = f"စတော့ဝင်ပြီးပါပြီ။ စုစုပေါင်းလက်ကျန်: {new_stock}" if lang == "my" else f"Stock In recorded. Total stock: {new_stock}"
            
            QMessageBox.information(self.dialog, tr("success"), msg)
            
            main_window = self.dialog.window()
            if hasattr(main_window, 'check_stock_alerts'):
                main_window.check_stock_alerts()
            
            self.dialog.accept()
            
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self.dialog, tr("error"), str(e))
        finally:
            conn.close()
    
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
