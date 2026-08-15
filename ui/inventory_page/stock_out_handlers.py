# ui/inventory_page/stock_out_handlers.py
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from models.database import connect_db
from utils.currency import format_money
from utils.translations import tr
from datetime import datetime


class StockOutHandlers:
    """Event handlers for StockOutDialog"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.all_products = []
        self.current_product_id = None
    
    def setup_signals(self):
        """Connect all signals"""
        d = self.dialog
        d.btn_save.clicked.connect(self.save)
        d.btn_cancel.clicked.connect(d.reject)
        d.so_location.currentIndexChanged.connect(self.on_location_changed)
        d.product_search.textChanged.connect(self.filter_products)
        d.product_search.returnPressed.connect(self.on_search_entered)
        d.so_product.currentIndexChanged.connect(self.on_product_changed)
        d.so_qty.valueChanged.connect(self.update_current_stock_after_qty)
    
    def on_product_changed(self, index):
        """Handle product selection change"""
        self.update_current_stock()
        self.update_product_info()
    
    def load_dropdowns(self):
        """Load products and customers"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by, stock FROM products ORDER BY name")
        self.all_products = cursor.fetchall()
        self.filter_products()
        
        cursor.execute("SELECT id, name FROM customers ORDER BY name")
        custs = cursor.fetchall()
        d = self.dialog
        d.so_customer.clear()
        d.so_customer.addItem("None", None)
        for cid, name in custs:
            d.so_customer.addItem(name, cid)
        conn.close()
    
    # ✅ Updated: Removed "None" option
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
        d.so_location.blockSignals(True)
        d.so_location.clear()
        
        locations_set = set()
        for (name,) in rows:
            locations_set.add(name)
        
        for location in sorted(locations_set):
            d.so_location.addItem(location, location)
        
        d.so_location.addItem("+ Add New Location", "__NEW__")
        d.so_location.blockSignals(False)
        conn.close()
    
    def filter_products(self):
        """Filter products based on search text"""
        search_text = self.dialog.product_search.text().strip().lower()
        d = self.dialog
        
        # Block signals to prevent triggering on_product_changed during update
        d.so_product.blockSignals(True)
        d.so_product.clear()
        
        for pid, name, barcode, sku, sold_by, stock in self.all_products:
            if (search_text in name.lower() or 
                (barcode and search_text in barcode.lower()) or 
                (sku and search_text in sku.lower())):
                display_text = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                d.so_product.addItem(display_text, pid)
        
        d.so_product.blockSignals(False)
        
        if d.so_product.count() > 0:
            d.so_product.setCurrentIndex(0)
            # Manually update after setting current index
            self.update_current_stock()
            self.update_product_info()
        else:
            # Clear product info if no products found
            d.current_stock_label.setVisible(False)
            d.image_preview.setPixmap(QPixmap())
            d.image_preview.setText("📷 No Image\n\nNo products found")
            d.product_details_label.setText("No products match your search")
            self.current_product_id = None
    
    def set_product(self, product_id, product_name=None):
        """Set the product to be pre-selected"""
        if product_id is None:
            return
            
        if not self.all_products:
            self.load_dropdowns()
        
        d = self.dialog
        d.so_product.blockSignals(True)
        
        # Try to find product in combo box
        found = False
        for i in range(d.so_product.count()):
            if d.so_product.itemData(i) == product_id:
                d.so_product.setCurrentIndex(i)
                found = True
                if product_name:
                    d.product_search.setText(product_name)
                break
        
        # If product not found, add it
        if not found:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, barcode, sku, sold_by, stock, image FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()
            conn.close()
            
            if product:
                pid, name, barcode, sku, sold_by, stock, image = product
                display_text = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                d.so_product.addItem(display_text, pid)
                d.so_product.setCurrentIndex(d.so_product.count() - 1)
                d.product_search.setText(name)
        
        d.so_product.blockSignals(False)
        
        # Update product info
        self.update_current_stock()
        self.update_product_info()
        
        # Focus on quantity
        QTimer.singleShot(200, lambda: d.so_qty.setFocus())
    
    def update_product_info(self):
        """Update product information and image preview"""
        d = self.dialog
        product_id = d.so_product.currentData()
        
        if product_id is None:
            d.image_preview.setPixmap(QPixmap())
            d.image_preview.setText("📷 No Image\n\nSelect a product to preview")
            d.product_details_label.setText("Select a product to view details")
            return
        
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
            
            try:
                # Resolve relative/moved image files and fall back to the image
                # bytes stored in the database for synced client installations.
                from ui.products_page.product_table import load_thumbnail

                available_width = max(50, d.image_preview.width() - 30)
                available_height = max(50, d.image_preview.height() - 30)
                pixmap = load_thumbnail(
                    image or "",
                    max(available_width, available_height),
                    product_id,
                )
                if pixmap and not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        available_width,
                        available_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    d.image_preview.setPixmap(scaled_pixmap)
                    d.image_preview.setText("")
                else:
                    d.image_preview.setPixmap(QPixmap())
                    d.image_preview.setText("📷 No Image Available")
            except Exception:
                d.image_preview.setPixmap(QPixmap())
                d.image_preview.setText("🖼️ Image Not Available")
        else:
            d.image_preview.setPixmap(QPixmap())
            d.image_preview.setText("📷 No Image\n\nProduct not found")
            d.product_details_label.setText("Product not found")
    
    def update_current_stock(self):
        """Update the current stock label based on selected product"""
        d = self.dialog
        product_id = d.so_product.currentData()
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
            d.current_stock_label.setStyleSheet("""
                QLabel {
                    font-weight: 600;
                    color: #2c3e50;
                    background: #ecf0f1;
                    padding: 6px 16px;
                    border-radius: 6px;
                    font-size: 10pt;
                    border: 1px solid #dfe6e9;
                }
            """)
            self.current_product_id = product_id
        else:
            d.current_stock_label.setVisible(False)
            self.current_product_id = None
    
    def update_current_stock_after_qty(self):
        """Update current stock display to show after stock-out"""
        d = self.dialog
        product_id = d.so_product.currentData()
        if product_id is None:
            return
        
        qty = d.so_qty.value()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            current_stock = row[0] if row[0] is not None else 0
            after_stock = current_stock - qty
            
            d.current_stock_label.setVisible(True)
            
            if after_stock < 0:
                d.current_stock_label.setText(f"⚠️ {current_stock} → {after_stock} (Insufficient!)")
                d.current_stock_label.setStyleSheet("""
                    QLabel {
                        font-weight: 600;
                        color: #e74c3c;
                        background: #fde8e8;
                        padding: 6px 16px;
                        border-radius: 6px;
                        font-size: 10pt;
                        border: 1px solid #f5c6cb;
                    }
                """)
            else:
                d.current_stock_label.setText(f"📊 {current_stock} → {after_stock}")
                d.current_stock_label.setStyleSheet("""
                    QLabel {
                        font-weight: 600;
                        color: #2c3e50;
                        background: #ecf0f1;
                        padding: 6px 16px;
                        border-radius: 6px;
                        font-size: 10pt;
                        border: 1px solid #dfe6e9;
                    }
                """)
    
    def on_search_entered(self):
        """Handle search entry"""
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
                for i in range(d.so_product.count()):
                    if d.so_product.itemData(i) == pid:
                        d.so_product.setCurrentIndex(i)
                        d.product_search.setStyleSheet("""
                            QLineEdit {
                                padding: 8px 12px;
                                border: 2px solid #27ae60;
                                border-radius: 6px;
                                background: white;
                                font-size: 10pt;
                            }
                        """)
                        # Update will be triggered by on_product_changed
                        QTimer.singleShot(300, lambda: d.product_search.setStyleSheet("""
                            QLineEdit {
                                padding: 8px 12px;
                                border: 1px solid #dfe6e9;
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
        
        current_data = d.so_location.currentData()
        current_text = d.so_location.currentText()
        
        if current_data == "__NEW__" or current_text == "+ Add New Location":
            self.add_new_location()
    
    # ✅ Updated: Handle default location after adding
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
                index = d.so_location.findText(new_location)
                if index >= 0:
                    d.so_location.setCurrentIndex(index)
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
                index = d.so_location.findText(new_location)
                if index >= 0:
                    d.so_location.setCurrentIndex(index)
                QMessageBox.information(self.dialog, tr("success"), msg)
            else:
                QMessageBox.warning(self.dialog, tr("warning"), msg)
                if d.so_location.count() > 0:
                    d.so_location.setCurrentIndex(0)
        else:
            if d.so_location.count() > 0:
                d.so_location.setCurrentIndex(0)
    
    # ✅ Updated: Added location = "Default" fallback
    def save(self):
        """Save stock out transaction"""
        d = self.dialog
        product_id = d.so_product.currentData()
        if product_id is None:
            QMessageBox.warning(self.dialog, tr("error"), tr("valid_product_required"))
            return
        
        qty = d.so_qty.value()
        reason = d.so_reason.currentText()
        ref_no = d.so_reference.text().strip()
        issued_by = d.so_issued_by.text().strip()
        notes = d.so_notes.toPlainText()
        location = d.so_location.currentData()
        customer_id = d.so_customer.currentData()
        lang = self.get_lang()
        
        if not issued_by:
            msg = "ထုတ်ပေးသူအမည် ထည့်ရန်လိုအပ်ပါသည်။" if lang == "my" else "Issued By is required"
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
            
            cursor.execute("SELECT stock, sold_by FROM products WHERE id=?", (product_id,))
            row = cursor.fetchone()
            if not row:
                QMessageBox.warning(self.dialog, tr("error"), "Product not found")
                conn.rollback()
                conn.close()
                return
                
            old_stock, sold_by = row
            old_stock = old_stock if old_stock is not None else 0
            
            if sold_by == "Service":
                QMessageBox.warning(self.dialog, tr("error"), tr("service_stock_not_allowed"))
                conn.rollback()
                conn.close()
                return
            
            if old_stock < qty:
                msg = f"စတော့မလုံလောက်ပါ။ ကျန် {old_stock} သာရှိသည်။" if lang == "my" else f"Insufficient stock. Only {old_stock} available"
                QMessageBox.warning(self.dialog, tr("error"), msg)
                conn.rollback()
                conn.close()
                return
            
            new_stock = old_stock - qty
            cursor.execute("""
                UPDATE products 
                SET stock = ?, last_updated = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (new_stock, product_id))
            
            # Update product_locations table
            if location:
                cursor.execute("""
                    SELECT id, quantity
                    FROM product_locations
                    WHERE product_id = ? AND location = ?
                      AND quantity > 0
                    ORDER BY
                      CASE WHEN expire_date IS NULL OR expire_date = '' THEN 1 ELSE 0 END,
                      expire_date ASC,
                      last_updated ASC,
                      id ASC
                """, (product_id, location))
                location_rows = cursor.fetchall()
                location_available = sum(int(row[1] or 0) for row in location_rows)
                if location_available < qty:
                    msg = f"Insufficient stock in {location}. Only {location_available} available"
                    QMessageBox.warning(self.dialog, tr("error"), msg)
                    conn.rollback()
                    conn.close()
                    return

                remaining_qty = qty
                for loc_id, loc_qty in location_rows:
                    if remaining_qty <= 0:
                        break
                    take = min(int(loc_qty or 0), remaining_qty)
                    cursor.execute("""
                        UPDATE product_locations
                        SET quantity = quantity - ?, last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (take, loc_id))
                    cursor.execute("DELETE FROM product_locations WHERE id = ? AND quantity <= 0", (loc_id,))
                    remaining_qty -= take
            
            # Record stock movement
            cursor.execute("""
                INSERT INTO stock_movements 
                (product_id, type, quantity, old_stock, new_stock, reason, 
                 reference, created_by, notes, location, customer_id)
                VALUES (?, 'out', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, qty, old_stock, new_stock, reason, 
                  ref_no, issued_by, notes, location, customer_id))
            
            conn.commit()
            
            msg = f"စတော့ထွက်ပြီးပါပြီ။ လက်ကျန်: {new_stock}" if lang == "my" else f"Stock Out recorded. New stock: {new_stock}"
            if location:
                msg += f" (Location: {location})"
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
