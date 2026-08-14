# ui/inventory_page/adjustment_handlers.py
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from models.database import connect_db
from utils.translations import tr
from datetime import datetime
import os

# ✅ Import theme manager
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme


def _quantity_value(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _format_quantity(value):
    return f"{_quantity_value(value):g}"


class AdjustmentHandlers:
    """Event handlers for AdjustmentDialog"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.all_products = []
        self.current_product_id = None
    
    def setup_signals(self):
        """Connect all signals"""
        d = self.dialog
        d.adj_new_qty.valueChanged.connect(self.update_diff)
        d.adj_product.currentIndexChanged.connect(self.load_old_stock)
        d.adj_location.currentIndexChanged.connect(self.on_location_changed)
        d.product_search.textChanged.connect(self.filter_products)
        d.product_search.returnPressed.connect(self.on_search_entered)
        d.btn_save.clicked.connect(self.save)
        d.btn_cancel.clicked.connect(d.reject)
        d.adj_type.currentIndexChanged.connect(self.on_type_changed)
        
        # ✅ Connect location only toggle
        if hasattr(d, 'adj_location_only'):
            d.adj_location_only.toggled.connect(self.on_location_only_toggled)
    
    def load_products(self):
        """Load products from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by, stock FROM products ORDER BY name")
        self.all_products = cursor.fetchall()
        self.filter_products()
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
        d.adj_location.blockSignals(True)
        d.adj_location.clear()
        
        locations_set = set()
        for (name,) in rows:
            locations_set.add(name)
        
        for location in sorted(locations_set):
            d.adj_location.addItem(location, location)
        
        d.adj_location.addItem("+ Add New Location", "__NEW__")
        d.adj_location.blockSignals(False)
        conn.close()
    
    def filter_products(self):
        """Filter products based on search text"""
        search_text = self.dialog.product_search.text().strip().lower()
        d = self.dialog
        d.adj_product.clear()
        d.adj_product.blockSignals(True)
        for pid, name, barcode, sku, sold_by, stock in self.all_products:
            if (search_text in name.lower() or 
                (barcode and search_text in barcode.lower()) or 
                (sku and search_text in sku.lower())):
                display_text = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
                d.adj_product.addItem(display_text, pid)
        d.adj_product.blockSignals(False)
        if d.adj_product.count() > 0:
            d.adj_product.setCurrentIndex(0)
            self.load_old_stock()
            self.update_product_info()
    
    def set_product(self, product_id, product_name=None):
        """Set the product to be pre-selected"""
        if product_id is None:
            return
        
        if not self.all_products:
            self.load_products()
        
        d = self.dialog
        for i in range(d.adj_product.count()):
            if d.adj_product.itemData(i) == product_id:
                d.adj_product.setCurrentIndex(i)
                if product_name:
                    d.product_search.setText(product_name)
                self.load_old_stock()
                self.update_product_info()
                QTimer.singleShot(200, lambda: d.adj_new_qty.setFocus())
                return
        
        # If product not found in combo, load it directly
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by, stock, image FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if product:
            pid, name, barcode, sku, sold_by, stock, image = product
            display_text = f"{name} {'(Service)' if sold_by == 'Service' else ''}"
            d.adj_product.addItem(display_text, pid)
            d.adj_product.setCurrentIndex(d.adj_product.count() - 1)
            d.product_search.setText(name)
            self.load_old_stock()
            self.update_product_info()
            QTimer.singleShot(200, lambda: d.adj_new_qty.setFocus())
    
    def load_old_stock(self):
        """Load old stock for selected product"""
        d = self.dialog
        pid = d.adj_product.currentData()
        if pid:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT stock, sold_by FROM products WHERE id=?", (pid,))
            row = cursor.fetchone()
            conn.close()
            if row:
                stock, sold_by = row
                stock = _quantity_value(stock)
                if sold_by == "Service":
                    QMessageBox.warning(d, tr("warning"), tr("service_adjustment_not_allowed"))
                    d.adj_new_qty.setEnabled(False)
                    d.adj_old_qty.setText("N/A")
                    d.current_stock_label.setVisible(False)
                    return
                else:
                    d.adj_new_qty.setEnabled(True)
                    d.adj_old_qty.setText(_format_quantity(stock))
                    
                    # ✅ Check if location only mode is active
                    if hasattr(d, 'adj_location_only') and d.adj_location_only.isChecked():
                        d.adj_new_qty.setValue(stock)
                        d.current_stock_label.setText("📍 Location Only Mode - Stock will not change")
                    else:
                        d.adj_new_qty.setValue(stock)
                        d.current_stock_label.setText(f"📊 Stock: {_format_quantity(stock)}")
                    
                    d.current_stock_label.setVisible(True)
                    self.current_product_id = pid
                    self.update_diff()
        else:
            d.adj_old_qty.setText("0")
            d.adj_new_qty.setValue(0)
            d.current_stock_label.setVisible(False)
            self.current_product_id = None
    
    def update_diff(self):
        """Update difference between old and new quantity"""
        d = self.dialog
        try:
            old = _quantity_value(d.adj_old_qty.text())
        except:
            old = 0.0
        new = _quantity_value(d.adj_new_qty.value())
        diff = new - old
        
        # Format diff with sign and color
        if diff > 0:
            d.adj_diff.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #27ae60;
                    background: #e8f8f5;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 14pt;
                    border: 1px solid #a3e4d7;
                    min-width: 80px;
                }
            """)
            d.adj_diff.setText(f"+{_format_quantity(diff)}")
        elif diff < 0:
            d.adj_diff.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #e74c3c;
                    background: #fdedec;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 14pt;
                    border: 1px solid #f5b7b1;
                    min-width: 80px;
                }
            """)
            d.adj_diff.setText(_format_quantity(diff))
        else:
            # ✅ Check if location only mode is active
            if hasattr(d, 'adj_location_only') and d.adj_location_only.isChecked():
                d.adj_diff.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        color: #3498db;
                        background: #ebf5fb;
                        padding: 8px 16px;
                        border-radius: 6px;
                        font-size: 12pt;
                        border: 1px solid #85c1e9;
                        min-width: 80px;
                    }
                """)
                d.adj_diff.setText("📍")
            else:
                d.adj_diff.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        color: #7f8c8d;
                        background: #f4f6f7;
                        padding: 8px 16px;
                        border-radius: 6px;
                        font-size: 14pt;
                        border: 1px solid #d5dbdb;
                        min-width: 80px;
                    }
                """)
                d.adj_diff.setText("0")
    
    def on_type_changed(self):
        """Handle adjustment type change"""
        d = self.dialog
        current_type = d.adj_type.currentText()
        self.update_diff()
    
    def update_product_info(self):
        """Update product information and image preview"""
        d = self.dialog
        product_id = d.adj_product.currentData()
        if product_id is None:
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
<span style='color:#5d6d7e;'>💰 Cost:</span> <b style='color:#27ae60;'>{cost or 0}</b><br>
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
                for i in range(d.adj_product.count()):
                    if d.adj_product.itemData(i) == pid:
                        d.adj_product.setCurrentIndex(i)
                        d.product_search.setStyleSheet("""
                            QLineEdit {
                                padding: 8px 12px;
                                border: 2px solid #27ae60;
                                border-radius: 6px;
                                background: white;
                                font-size: 10pt;
                            }
                        """)
                        self.load_old_stock()
                        self.update_product_info()
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
        
        current_data = d.adj_location.currentData()
        current_text = d.adj_location.currentText()
        
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
                index = d.adj_location.findText(new_location)
                if index >= 0:
                    d.adj_location.setCurrentIndex(index)
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
                index = d.adj_location.findText(new_location)
                if index >= 0:
                    d.adj_location.setCurrentIndex(index)
                QMessageBox.information(self.dialog, tr("success"), msg)
            else:
                QMessageBox.warning(self.dialog, tr("warning"), msg)
                if d.adj_location.count() > 0:
                    d.adj_location.setCurrentIndex(0)
        else:
            if d.adj_location.count() > 0:
                d.adj_location.setCurrentIndex(0)
    
    # =========================================================================
    # ✅ Location Only Mode
    # =========================================================================
    
    def on_location_only_toggled(self, checked):
        """Handle location only mode toggle"""
        d = self.dialog
        if checked:
            # Disable new_qty and set it to current stock
            d.adj_new_qty.setEnabled(False)
            d.adj_type.setEnabled(False)
            d.adj_location.setEnabled(True)
            
            # Set new_qty to current stock
            product_id = d.adj_product.currentData()
            if product_id:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    stock = _quantity_value(row[0])
                    d.adj_new_qty.setValue(stock)
                    
                    # Update label
                    d.current_stock_label.setText("📍 Location Only Mode - Stock will not change")
                    d.adj_diff.setStyleSheet("""
                        QLabel {
                            font-weight: bold;
                            color: #3498db;
                            background: #ebf5fb;
                            padding: 8px 16px;
                            border-radius: 6px;
                            font-size: 12pt;
                            border: 1px solid #85c1e9;
                            min-width: 80px;
                        }
                    """)
                    d.adj_diff.setText("📍")
            
            # Update UI hint
            d.adj_diff.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #3498db;
                    background: #ebf5fb;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 12pt;
                    border: 1px solid #85c1e9;
                    min-width: 80px;
                }
            """)
            d.adj_diff.setText("📍")
            
            # Change new_qty background to indicate it's locked
            d.adj_new_qty.setStyleSheet("""
                QDoubleSpinBox {
                    padding: 8px 12px;
                    border: 2px solid #3498db;
                    border-radius: 6px;
                    background: #ebf5fb;
                    color: #2c3e50;
                    font-size: 10pt;
                    min-width: 100px;
                }
            """)
            
        else:
            # Enable new_qty
            d.adj_new_qty.setEnabled(True)
            d.adj_type.setEnabled(True)
            d.adj_location.setEnabled(True)
            
            # Reset styles
            colors = get_theme_colors()
            d.adj_new_qty.setStyleSheet(self._get_spinbox_style(colors))
            
            # Reload old stock
            self.load_old_stock()
            self.update_diff()
    
    def _get_spinbox_style(self, colors):
        """Get spinbox style for resetting"""
        return f"""
            QDoubleSpinBox {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-width: 100px;
            }}
            QDoubleSpinBox:focus {{
                border-color: #5865f2;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 16px;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 2px;
            }}
        """
    
    # =========================================================================
    # ✅ Save Method with Location Only Support
    # =========================================================================
    
    # ✅ Updated: Added location = "Default" fallback
    def save(self):
        """Save adjustment"""
        d = self.dialog
        product_id = d.adj_product.currentData()
        if product_id is None:
            QMessageBox.warning(self.dialog, tr("error"), tr("valid_product_required"))
            return
        
        new_qty = _quantity_value(d.adj_new_qty.value())
        reason = d.adj_reason.text().strip()
        staff = d.adj_staff.text().strip()
        notes = d.adj_notes.toPlainText().strip()
        location = d.adj_location.currentData()
        lang = self.get_lang()
        
        # ✅ Check if Location Only mode is active
        is_location_only = hasattr(d, 'adj_location_only') and d.adj_location_only.isChecked()
        
        if not reason:
            msg = "အကြောင်းပြချက်ထည့်ရန်လိုအပ်ပါသည်။" if lang == "my" else "Reason is required"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        if not staff:
            msg = "ပြင်ဆင်သူအမည်ထည့်ရန်လိုအပ်ပါသည်။" if lang == "my" else "Adjusted By is required"
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
            cursor.execute("SELECT stock, sold_by FROM products WHERE id=?", (product_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                QMessageBox.warning(self.dialog, tr("error"), "Product not found")
                return
            
            old_stock, sold_by = row
            old_stock = _quantity_value(old_stock)
            
            if sold_by == "Service":
                QMessageBox.warning(self.dialog, tr("error"), tr("service_stock_not_allowed"))
                conn.close()
                return
            
            # ✅ Check if Location Only mode
            if is_location_only:
                # Location Only Mode - Update location without changing stock
                if location and location != "None":
                    # Check if product already has this location
                    cursor.execute("""
                        SELECT id, quantity FROM product_locations 
                        WHERE product_id = ? AND location = ?
                    """, (product_id, location))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Location exists, update quantity to current stock
                        cursor.execute("""
                            UPDATE product_locations 
                            SET quantity = ?,
                                last_updated = CURRENT_TIMESTAMP
                            WHERE product_id = ? AND location = ?
                        """, (old_stock, product_id, location))
                        msg = f"Location '{location}' updated with {_format_quantity(old_stock)} units!" if lang != "my" else f"နေရာ '{location}' ကို {_format_quantity(old_stock)} ခုဖြင့် ပြင်ဆင်ပြီးပါပြီ။"
                    else:
                        # Location doesn't exist, add it
                        cursor.execute("""
                            INSERT INTO product_locations (product_id, location, quantity, last_updated)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (product_id, location, old_stock))
                        msg = f"Location '{location}' added with {_format_quantity(old_stock)} units!" if lang != "my" else f"နေရာ '{location}' ကို {_format_quantity(old_stock)} ခုဖြင့် ထည့်သွင်းပြီးပါပြီ။"
                    
                    # Record stock movement for location update
                    cursor.execute("""
                        INSERT INTO stock_movements 
                        (product_id, type, quantity, old_stock, new_stock, reason, created_by, notes, location)
                        VALUES (?, 'adjustment', ?, ?, ?, ?, ?, ?, ?)
                    """, (product_id, 0, old_stock, old_stock, f"Location set to {location}: {reason}", staff, notes, location))
                    
                    conn.commit()
                    QMessageBox.information(self.dialog, tr("success"), msg)
                    
                    main_window = self.dialog.window()
                    if hasattr(main_window, 'check_stock_alerts'):
                        main_window.check_stock_alerts()
                    
                    self.dialog.accept()
                    return
                else:
                    QMessageBox.warning(self.dialog, tr("error"), "Please select a location to set.")
                    conn.close()
                    return
            
            # ✅ Normal Adjustment Mode
            if old_stock == new_qty:
                QMessageBox.information(self.dialog, tr("info"), tr("no_change"))
                conn.close()
                return
            
            diff = new_qty - old_stock
            
            # Update product stock
            cursor.execute("""
                UPDATE products 
                SET stock = ?, last_updated = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (new_qty, product_id))
            
            # Update product_locations table
            if location:
                if diff > 0:
                    cursor.execute("""
                        SELECT quantity FROM product_locations 
                        WHERE product_id = ? AND location = ?
                    """, (product_id, location))
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute("""
                            UPDATE product_locations 
                            SET quantity = quantity + ?
                            WHERE product_id = ? AND location = ?
                        """, (diff, product_id, location))
                    else:
                        cursor.execute("""
                            INSERT INTO product_locations (product_id, location, quantity)
                            VALUES (?, ?, ?)
                        """, (product_id, location, diff))
                        
                elif diff < 0:
                    cursor.execute("""
                        UPDATE product_locations 
                        SET quantity = quantity + ?
                        WHERE product_id = ? AND location = ?
                    """, (diff, product_id, location))
                    
                    cursor.execute("""
                        SELECT quantity FROM product_locations 
                        WHERE product_id = ? AND location = ?
                    """, (product_id, location))
                    remaining = cursor.fetchone()
                    if remaining and remaining[0] <= 0:
                        cursor.execute("""
                            DELETE FROM product_locations 
                            WHERE product_id = ? AND location = ?
                        """, (product_id, location))
            
            # Record stock movement
            cursor.execute("""
                INSERT INTO stock_movements 
                (product_id, type, quantity, old_stock, new_stock, reason, created_by, notes, location)
                VALUES (?, 'adjustment', ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, abs(diff), old_stock, new_qty, reason, staff, notes, location))
            
            conn.commit()
            
            msg = f"စတော့ကို {_format_quantity(old_stock)} မှ {_format_quantity(new_qty)} သို့ ပြင်ဆင်ပြီးပါပြီ။" if lang == "my" else f"Stock adjusted from {_format_quantity(old_stock)} to {_format_quantity(new_qty)}"
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
