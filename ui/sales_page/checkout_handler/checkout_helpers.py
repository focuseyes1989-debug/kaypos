# ui/sales_page/checkout_handler/checkout_helpers.py
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QMessageBox
from models.database import connect_db
from models.database.queries import check_expiry_status, get_fifo_locations_with_expiry_check
from utils.currency import get_currency_symbol, format_money
from utils.language import lang
from utils.translations import tr
from loguru import logger


class CheckoutHelpers:
    """Helper methods for checkout operations"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def validate_cart(self, cart):
        """Validate cart is not empty"""
        if not cart:
            QMessageBox.warning(self.parent, tr("empty_cart"), "Cart is empty")
            return False
        return True
    
    def validate_payment(self, payment, grand_total):
        """Validate payment amount"""
        if payment < grand_total:
            symbol = get_currency_symbol()
            QMessageBox.warning(
                self.parent, 
                tr("insufficient_payment"), 
                f"Payment ({format_money(payment, symbol)}) < Total ({format_money(grand_total, symbol)})"
            )
            return False
        return True
    
    def check_expiry_issues(self, cart):
        """Check for expired items and warnings"""
        expired_items = []
        warning_items = []
        all_expired_blocked = False
        
        for item in cart:
            if item.get("is_service", False):
                continue
                
            product_id = item["id"]
            qty_needed = item["qty"]
            if item.get("variant_id"):
                conn = connect_db()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT stock FROM product_variants
                        WHERE id = ? AND product_id = ? AND COALESCE(active, 1) = 1
                    """, (item["variant_id"], product_id))
                    row = cursor.fetchone()
                finally:
                    conn.close()
                if not row or int(row[0] or 0) < qty_needed:
                    return False, expired_items, warning_items, all_expired_blocked
                continue
            if item.get("location_id"):
                conn = connect_db()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT id, location, batch_no, expire_date, quantity
                        FROM product_locations
                        WHERE id = ? AND product_id = ? AND quantity > 0
                    """, (item["location_id"], product_id))
                    row = cursor.fetchone()
                finally:
                    conn.close()
                if not row:
                    return False, expired_items, warning_items, True
                loc_id, location, batch_no, expire_date, available = row
                expired = []
                warnings = []
                locations = []
                status = check_expiry_status(expire_date)
                batch_info = {
                    'id': loc_id,
                    'location': location,
                    'batch_no': batch_no or '',
                    'expire_date': expire_date,
                    'quantity': available,
                }
                if status == 'expired':
                    expired = [batch_info]
                else:
                    if status == 'warning':
                        warnings = [batch_info]
                    locations = [{
                        "id": loc_id,
                        "location": location,
                        "batch_no": batch_no or "",
                        "expire_date": expire_date,
                        "available": available,
                        "take": min(available, qty_needed),
                        "expiry_status": status,
                    }]
            else:
                locations, remaining, expired, warnings = get_fifo_locations_with_expiry_check(
                    product_id, qty_needed
                )
            
            if expired:
                for exp in expired:
                    expired_items.append({
                        'name': item['name'],
                        'location': exp['location'],
                        'batch': exp['batch_no'],
                        'expiry': exp['expire_date'],
                        'qty': exp['quantity']
                    })
                all_expired_blocked = True
            
            if warnings:
                for warn in warnings:
                    warning_items.append({
                        'name': item['name'],
                        'location': warn['location'],
                        'expiry': warn['expire_date'],
                        'qty': warn['quantity']
                    })
            
            total_available = sum(loc['available'] for loc in locations)
            if total_available < qty_needed:
                if expired:
                    expired_qty = sum(exp['quantity'] for exp in expired)
                    if total_available + expired_qty >= qty_needed:
                        all_expired_blocked = True
                    else:
                        return False, expired_items, warning_items, all_expired_blocked
                else:
                    return False, expired_items, warning_items, all_expired_blocked
        
        return True, expired_items, warning_items, all_expired_blocked
    
    def process_stock_deduction(self, cursor, cart, invoice_no):
        """Process stock deduction for all items"""
        for item in cart:
            if item.get("is_service", False):
                continue
                
            product_id = item["id"]
            qty_needed = item["qty"]
            item["stock_allocations"] = []
            if item.get("variant_id"):
                cursor.execute("""
                    SELECT stock FROM product_variants
                    WHERE id = ? AND product_id = ? AND COALESCE(active, 1) = 1
                """, (item["variant_id"], product_id))
                row = cursor.fetchone()
                if not row:
                    raise Exception(f"Selected variant is no longer available: {item.get('name')}")
                available = int(row[0] or 0)
                if available < qty_needed:
                    raise Exception(f"Only {available} left for selected variant: {item.get('name')}")
                cursor.execute("""
                    UPDATE product_variants
                    SET stock = stock - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND product_id = ?
                """, (qty_needed, item["variant_id"], product_id))
                cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty_needed, product_id))
                item["stock_allocations"].append({
                    "product_id": product_id,
                    "variant_id": item.get("variant_id"),
                    "qty": qty_needed,
                    "location_id": None,
                    "location": item.get("location") or "Variant",
                    "batch_no": "",
                    "expire_date": "",
                })
                cursor.execute("""
                    INSERT INTO stock_movements
                    (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, location, notes)
                    VALUES (?, 'sale', ?, ?, ?, 'Sale', ?, ?, ?, ?)
                """, (
                    product_id,
                    qty_needed,
                    available,
                    available - qty_needed,
                    invoice_no,
                    "",
                    item.get("location") or "Variant",
                    f"Variant ID: {item.get('variant_id')}"
                ))
                continue
            if item.get("location_id"):
                cursor.execute("""
                    SELECT id, location, batch_no, expire_date, quantity
                    FROM product_locations
                    WHERE id = ? AND product_id = ? AND quantity > 0
                """, (item["location_id"], product_id))
                row = cursor.fetchone()
                if not row:
                    raise Exception(f"Selected batch is no longer available: {item.get('name')}")
                loc_id, location, batch_no, expire_date, available = row
                if available < qty_needed:
                    raise Exception(f"Only {available} left in selected batch: {item.get('name')}")
                locations = [{
                    "id": loc_id,
                    "location": location,
                    "batch_no": batch_no or "",
                    "expire_date": expire_date,
                    "available": available,
                    "take": qty_needed,
                    "expiry_status": "batch",
                }]
            else:
                locations, remaining, expired, warnings = get_fifo_locations_with_expiry_check(
                    product_id, qty_needed
                )
            
            for loc in locations:
                if loc['take'] > 0:
                    item["stock_allocations"].append({
                        "product_id": product_id,
                        "variant_id": None,
                        "qty": loc["take"],
                        "location_id": loc.get("id"),
                        "location": loc.get("location") or "",
                        "batch_no": loc.get("batch_no") or "",
                        "expire_date": loc.get("expire_date") or "",
                    })
                    cursor.execute("""
                        UPDATE product_locations 
                        SET quantity = quantity - ?, last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (loc['take'], loc['id']))
                    
                    cursor.execute("""
                        INSERT INTO stock_movements 
                        (product_id, type, quantity, old_stock, new_stock, 
                         reason, reference, created_by, location, notes)
                        VALUES (?, 'sale', ?, ?, ?, 'Sale', ?, ?, ?, ?)
                    """, (product_id, loc['take'], 0, 0, invoice_no, "", loc['location'], 
                          f"Expiry: {loc['expire_date'] or 'N/A'}"))
                    
                    cursor.execute("SELECT quantity FROM product_locations WHERE id = ?", (loc['id'],))
                    if cursor.fetchone()[0] <= 0:
                        cursor.execute("DELETE FROM product_locations WHERE id = ?", (loc['id'],))
                    
                    cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (loc['take'], product_id))
    
    def reset_for_new_sale(self):
        """Reset all widgets for new sale"""
        self.parent.cart_widget.clear()
        self.parent.totals_widget.discount_checkbox.setChecked(False)
        self.parent.totals_widget.points_use_check.setChecked(False)
        self.parent.payment_widget.reset_manual_override()
        self.parent.payment_widget.reset_to_default()
        self.parent.options_widget.set_payment_type("Cash")
        self.parent.payment_widget.setEnabled(True)
        self.parent.product_grid.focus_search()
        
        # Reset customer
        self.parent.customer_combo.setCurrentIndex(0)
        self.parent.checkout_handler.selected_customer_id = None
        self.parent.checkout_handler.points_available = 0
        self.parent.checkout_handler.credit_balance = 0
        self.parent.checkout_handler._credit_info_shown = False
        
        # Refresh data
        self.parent.product_grid.load_products()
        self.parent.load_customers()
        
        main_window = self.parent.window()
        if hasattr(main_window, 'inventory_page'):
            main_window.inventory_page.refresh_all()
        if hasattr(main_window, 'check_stock_alerts'):
            main_window.check_stock_alerts()
        customers_page = getattr(main_window, "customers_page", None)
        if customers_page is not None and hasattr(customers_page, "load_customers"):
            customers_page.load_customers()
