# ui/inventory_page/stock_transfer_handlers.py
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from models.database import connect_db
from utils.translations import tr
from datetime import datetime
from loguru import logger
import os


class StockTransferHandlers:
    """Event handlers for StockTransferDialog"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.all_products = []
        self.current_product_id = None
    
    def setup_signals(self):
        """Connect all signals"""
        d = self.dialog
        d.st_from_location.currentIndexChanged.connect(self.update_available_stock)
        d.st_product.currentIndexChanged.connect(self.on_product_changed)
        d.st_qty.valueChanged.connect(self.update_available_stock_display)
        d.product_search.textChanged.connect(self.filter_products)
        d.product_search.returnPressed.connect(self.on_search_entered)
        d.btn_transfer.clicked.connect(self.transfer_stock)
        d.btn_cancel.clicked.connect(d.reject)
    
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
        
        d = self.dialog
        d.st_from_location.blockSignals(True)
        d.st_to_location.blockSignals(True)
        
        d.st_from_location.clear()
        d.st_from_location.addItem("Select From Location...", None)
        
        d.st_to_location.clear()
        d.st_to_location.addItem("Select To Location...", None)
        
        for (name,) in rows:
            d.st_from_location.addItem(name, name)
            d.st_to_location.addItem(name, name)
        
        d.st_from_location.blockSignals(False)
        d.st_to_location.blockSignals(False)
        conn.close()
    
    def load_products(self):
        """Load products into combo box"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, barcode, sku, sold_by, stock
            FROM products 
            WHERE (sold_by IS NULL OR sold_by != 'Service')
            ORDER BY name
        """)
        self.all_products = cursor.fetchall()
        self.filter_products()
        conn.close()
    
    def filter_products(self):
        """Filter products based on search text"""
        search_text = self.dialog.product_search.text().strip().lower()
        d = self.dialog
        d.st_product.clear()
        d.st_product.blockSignals(True)
        
        for pid, name, barcode, sku, sold_by, stock in self.all_products:
            if (search_text in name.lower() or 
                (barcode and search_text in barcode.lower()) or 
                (sku and search_text in sku.lower())):
                display_text = f"{name}"
                d.st_product.addItem(display_text, pid)
        
        d.st_product.blockSignals(False)
        if d.st_product.count() > 0:
            d.st_product.setCurrentIndex(0)
            self.on_product_changed()
        
        self.update_available_stock()
        self.update_product_info()
    
    def set_product(self, product_id, product_name=None):
        """Set the product to be pre-selected"""
        if product_id is None:
            return
        
        if not self.all_products:
            self.load_products()
        
        d = self.dialog
        for i in range(d.st_product.count()):
            if d.st_product.itemData(i) == product_id:
                d.st_product.setCurrentIndex(i)
                if product_name:
                    d.product_search.setText(product_name)
                self.update_available_stock()
                self.update_product_info()
                QTimer.singleShot(200, lambda: d.st_qty.setFocus())
                return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, barcode, sku, sold_by, stock, image FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if product:
            pid, name, barcode, sku, sold_by, stock, image = product
            display_text = f"{name}"
            d.st_product.addItem(display_text, pid)
            d.st_product.setCurrentIndex(d.st_product.count() - 1)
            d.product_search.setText(name)
            self.update_available_stock()
            self.update_product_info()
            QTimer.singleShot(200, lambda: d.st_qty.setFocus())
    
    def on_product_changed(self):
        """Handle product selection change"""
        self.update_available_stock()
        self.update_product_info()
    
    def update_available_stock(self):
        """Update available stock label based on selected product and location"""
        d = self.dialog
        product_id = d.st_product.currentData()
        from_loc = d.st_from_location.currentData()
        
        if not product_id or not from_loc:
            d.st_available_stock.setText("0")
            d.st_qty.setMaximum(1)
            d.current_stock_label.setVisible(False)
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT quantity FROM product_locations 
            WHERE product_id = ? AND location = ?
        """, (product_id, from_loc))
        
        row = cursor.fetchone()
        conn.close()
        
        qty = row[0] if row else 0
        d.st_available_stock.setText(str(qty))
        
        # Update max quantity
        d.st_qty.setMaximum(qty if qty > 0 else 1)
        
        # Update stock label
        d.current_stock_label.setText(f"📊 Available: {qty}")
        d.current_stock_label.setVisible(True)
        self.current_product_id = product_id
    
    def update_available_stock_display(self):
        """Update available stock display when quantity changes"""
        d = self.dialog
        try:
            available = int(d.st_available_stock.text()) if d.st_available_stock.text().isdigit() else 0
        except:
            available = 0
        qty = d.st_qty.value()
        
        colors = get_theme_colors()
        
        if qty > available:
            d.st_qty.setStyleSheet(f"""
                QSpinBox {{
                    padding: 8px 12px;
                    border: 2px solid #e74c3c;
                    border-radius: 6px;
                    background: #fdedec;
                    color: {colors['text']};
                    font-size: 10pt;
                    min-width: 100px;
                }}
            """)
        else:
            d.st_qty.setStyleSheet(f"""
                QSpinBox {{
                    padding: 8px 12px;
                    border: 1px solid {colors['border']};
                    border-radius: 6px;
                    background: {colors['card_bg']};
                    color: {colors['text']};
                    font-size: 10pt;
                    min-width: 100px;
                }}
                QSpinBox:focus {{
                    border-color: #5865f2;
                }}
            """)
        
        remaining = available - qty
        d.current_stock_label.setText(f"📊 {available} → {remaining} (after transfer)")
    
    def update_product_info(self):
        """Update product information and image preview"""
        d = self.dialog
        product_id = d.st_product.currentData()
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
                for i in range(d.st_product.count()):
                    if d.st_product.itemData(i) == pid:
                        d.st_product.setCurrentIndex(i)
                        d.product_search.setStyleSheet("""
                            QLineEdit {
                                padding: 8px 12px;
                                border: 2px solid #27ae60;
                                border-radius: 6px;
                                background: white;
                                font-size: 10pt;
                            }
                        """)
                        self.update_available_stock()
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
    
    def transfer_stock(self):
        """Perform stock transfer"""
        d = self.dialog
        product_id = d.st_product.currentData()
        from_loc = d.st_from_location.currentData()
        to_loc = d.st_to_location.currentData()
        qty = d.st_qty.value()
        reason = d.st_reason.text().strip()
        notes = d.st_notes.toPlainText().strip()
        lang = self.get_lang()
        
        # Validations
        if not product_id:
            msg = "Please select a product." if lang != "my" else "ပစ္စည်းတစ်ခုရွေးပါ။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        if not from_loc:
            msg = "Please select 'From' location." if lang != "my" else "'မှ' နေရာကိုရွေးပါ။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        if not to_loc:
            msg = "Please select 'To' location." if lang != "my" else "'သို့' နေရာကိုရွေးပါ။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        if from_loc == to_loc:
            msg = "From and To locations cannot be the same!" if lang != "my" else "'မှ' နှင့် 'သို့' နေရာများ တူမနိုင်ပါ။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        if qty <= 0:
            msg = "Quantity must be greater than 0." if lang != "my" else "အရေအတွက်သည် ၀ ထက်ကြီးရပါမည်။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        if not reason:
            msg = "Please enter a reason for transfer." if lang != "my" else "လွှဲပြောင်းရသည့်အကြောင်းပြချက် ထည့်ပါ။"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            return
        
        # Check available stock
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT quantity FROM product_locations 
            WHERE product_id = ? AND location = ?
        """, (product_id, from_loc))
        row = cursor.fetchone()
        available = row[0] if row else 0
        
        if qty > available:
            msg = f"Insufficient stock. Available: {available}" if lang != "my" else f"စတော့မလုံလောက်ပါ။ ကျန်: {available}"
            QMessageBox.warning(self.dialog, tr("error"), msg)
            conn.close()
            return
        
        # Perform transfer
        try:
            cursor.execute("BEGIN IMMEDIATE")
            
            # Get current total stock for product
            cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
            total_stock = cursor.fetchone()[0]
            
            # 1. Remove from source location
            cursor.execute("""
                UPDATE product_locations 
                SET quantity = quantity - ?
                WHERE product_id = ? AND location = ?
            """, (qty, product_id, from_loc))
            
            # Check if source location becomes 0, delete it
            cursor.execute("""
                SELECT quantity FROM product_locations 
                WHERE product_id = ? AND location = ?
            """, (product_id, from_loc))
            remaining = cursor.fetchone()
            if remaining and remaining[0] <= 0:
                cursor.execute("""
                    DELETE FROM product_locations 
                    WHERE product_id = ? AND location = ?
                """, (product_id, from_loc))
            
            # 2. Add to destination location
            cursor.execute("""
                INSERT INTO product_locations (product_id, location, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, location) 
                DO UPDATE SET quantity = quantity + excluded.quantity
            """, (product_id, to_loc, qty))
            
            # 3. Update total stock in products table
            cursor.execute("""
                UPDATE products 
                SET stock = (
                    SELECT COALESCE(SUM(quantity), 0) 
                    FROM product_locations 
                    WHERE product_id = ?
                ), last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (product_id, product_id))
            
            # Get new total stock            cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
            new_total_stock = cursor.fetchone()[0]
            
            # 4. Record stock movement for FROM location (Stock Out)
            cursor.execute("""
                INSERT INTO stock_movements 
                (product_id, type, quantity, old_stock, new_stock, 
                 reason, reference, created_by, notes, location)
                VALUES (?, 'out', ?, ?, ?, 
                        ?, ?, ?, ?, ?)
            """, (
                product_id, 
                qty, 
                total_stock,
                new_total_stock,
                f"Transfer to {to_loc}: {reason}" if lang != "my" else f"{to_loc} သို့လွှဲ: {reason}",
                d.st_transfer_no.text(),
                "System",
                notes or reason,
                from_loc
            ))
            
            # 5. Record stock movement for TO location (Stock In)
            cursor.execute("""
                INSERT INTO stock_movements 
                (product_id, type, quantity, old_stock, new_stock, 
                 reason, reference, created_by, notes, location)
                VALUES (?, 'in', ?, ?, ?, 
                        ?, ?, ?, ?, ?)
            """, (
                product_id, 
                qty, 
                total_stock,
                new_total_stock,
                f"Transfer from {from_loc}: {reason}" if lang != "my" else f"{from_loc} မှလွှဲ: {reason}",
                d.st_transfer_no.text(),
                "System",
                notes or reason,
                to_loc
            ))
            
            conn.commit()
            
            # Get product name for success message
            cursor.execute("SELECT name FROM products WHERE id = ?", (product_id,))
            product_name = cursor.fetchone()[0]
            
            msg = f"Successfully transferred {qty} units of '{product_name}' from {from_loc} to {to_loc}!" if lang != "my" else f"'{product_name}' ပစ္စည်း {qty} ခုကို {from_loc} မှ {to_loc} သို့ အောင်မြင်စွာ လွှဲပြောင်းပြီးပါပြီ။"
            QMessageBox.information(self.dialog, tr("success"), msg)
            
            # Refresh stock alerts in main window
            main_window = self.dialog.window()
            if hasattr(main_window, 'check_stock_alerts'):
                main_window.check_stock_alerts()
            
            self.dialog.accept()
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Stock transfer failed: {e}")
            msg = f"Transfer failed: {e}" if lang != "my" else f"လွှဲပြောင်းမှု မအောင်မြင်ပါ: {e}"
            QMessageBox.critical(self.dialog, tr("error"), msg)
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