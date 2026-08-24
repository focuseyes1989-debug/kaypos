# models/database/queries.py
"""
Database query functions for CRUD operations.
"""

import sqlite3
from loguru import logger
from datetime import datetime, timedelta, date
from models.database.connection import DBContext


def _ensure_expiry_discount_columns(cursor):
    """Ensure optional batch clearance discount columns exist."""
    cursor.execute("PRAGMA table_info(product_locations)")
    columns = {row[1] for row in cursor.fetchall()}
    for column, definition in {
        "expiry_discount_enabled": "INTEGER DEFAULT 0",
        "expiry_discount_percent": "REAL DEFAULT 0",
        "clearance_note": "TEXT",
    }.items():
        if column not in columns:
            cursor.execute(f"ALTER TABLE product_locations ADD COLUMN {column} {definition}")


# ========== PRODUCTS ==========

def get_products(category=None, search=None, limit=None, offset=None):
    """Get products with optional filters."""
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if search:
        query += " AND (name LIKE ? OR sku LIKE ? OR barcode LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    query += " ORDER BY name"
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def get_product(product_id):
    """Get a single product by ID."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return cursor.fetchone()


def add_product(name, category=None, price=0, cost=0, stock=0, sku=None, barcode=None, 
                low_stock=0, description=None, sold_by="Each", image=None, supplier_id=None,
                unit=None, warehouse=None, batch_no=None, manufacture_date=None, expire_date=None):
    """Add a new product."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, category, description, sold_by, price, cost, sku, barcode,
                                 stock, expire_date, low_stock, image, supplier_id, unit, warehouse,
                                 batch_no, manufacture_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, category, description, sold_by, price, cost, sku, barcode,
              stock, expire_date, low_stock, image, supplier_id, unit, warehouse,
              batch_no, manufacture_date))
        conn.commit()
        return cursor.lastrowid


def update_product(product_id, **kwargs):
    """Update a product."""
    if not kwargs:
        return False
    
    set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    query = f"UPDATE products SET {set_clause}, last_updated = CURRENT_TIMESTAMP WHERE id = ?"
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, list(kwargs.values()) + [product_id])
        conn.commit()
        return cursor.rowcount > 0


def delete_product(product_id):
    """Delete a product."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== SALES ==========

def get_sales(from_date=None, to_date=None, status='completed', limit=None, offset=None):
    """Get sales with optional filters."""
    query = """
        SELECT s.*, c.name as customer_name 
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE 1=1
    """
    params = []
    
    if status:
        query += " AND s.status = ?"
        params.append(status)
    
    if from_date:
        query += " AND date(s.created_at) >= ?"
        params.append(from_date)
    
    if to_date:
        query += " AND date(s.created_at) <= ?"
        params.append(to_date)
    
    query += " ORDER BY s.created_at DESC"
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def get_sale(sale_id):
    """Get a single sale by ID."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.name as customer_name 
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = ?
        """, (sale_id,))
        return cursor.fetchone()


def get_sale_items(sale_id):
    """Get items for a sale."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
        return cursor.fetchall()


def add_sale(invoice_no, total, payment, change_amount, customer_id=None, 
             payment_type='Cash', discount_amount=0, status='completed', items=None):
    """Add a new sale with items."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sales (invoice_no, total, payment, change_amount, customer_id,
                              payment_type, discount_amount, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (invoice_no, total, payment, change_amount, customer_id,
              payment_type, discount_amount, status))
        sale_id = cursor.lastrowid
        
        # Add sale items
        if items:
            for item in items:
                try:
                    cursor.execute("""
                        INSERT INTO sale_items (
                            sale_id, product_id, product_name, qty, price, total, cost,
                            variant_id, location_id, location, batch_no, expire_date
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sale_id,
                        item.get('product_id'),
                        item['product_name'],
                        item['qty'],
                        item['price'],
                        item['total'],
                        item.get('cost', 0),
                        item.get('variant_id'),
                        item.get('location_id'),
                        item.get('location', ''),
                        item.get('batch_no', ''),
                        item.get('expire_date', ''),
                    ))
                except Exception:
                    cursor.execute("""
                        INSERT INTO sale_items (sale_id, product_name, qty, price, total, cost)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (sale_id, item['product_name'], item['qty'], item['price'],
                          item['total'], item.get('cost', 0)))
        
        conn.commit()
        return sale_id


def update_sale(sale_id, **kwargs):
    """Update a sale."""
    if not kwargs:
        return False
    
    set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    query = f"UPDATE sales SET {set_clause} WHERE id = ?"
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, list(kwargs.values()) + [sale_id])
        conn.commit()
        return cursor.rowcount > 0


def delete_sale(sale_id):
    """Delete a sale (cascade will delete items)."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== CUSTOMERS ==========

def get_customers(search=None, limit=None, offset=None):
    """Get customers with optional filters."""
    query = "SELECT * FROM customers WHERE 1=1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    query += " ORDER BY name"
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def get_customer(customer_id):
    """Get a single customer by ID."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        return cursor.fetchone()


def add_customer(name, phone=None, email=None, address=None, credit_limit=0, remarks=None):
    """Add a new customer."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers (name, phone, email, address, credit_limit, remarks)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, phone, email, address, credit_limit, remarks))
        conn.commit()
        return cursor.lastrowid


def update_customer(customer_id, **kwargs):
    """Update a customer."""
    if not kwargs:
        return False
    
    set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    query = f"UPDATE customers SET {set_clause} WHERE id = ?"
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, list(kwargs.values()) + [customer_id])
        conn.commit()
        return cursor.rowcount > 0


def delete_customer(customer_id):
    """Delete a customer."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== EXPENSES ==========

def get_expenses(from_date=None, to_date=None, category=None, limit=None, offset=None):
    """Get expenses with optional filters."""
    query = "SELECT * FROM expenses WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if from_date:
        query += " AND expense_date >= ?"
        params.append(from_date)
    
    if to_date:
        query += " AND expense_date <= ?"
        params.append(to_date)
    
    query += " ORDER BY expense_date DESC"
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def get_expense(expense_id):
    """Get a single expense by ID."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        return cursor.fetchone()


def add_expense(expense_no, category, description, amount, expense_date, 
                payment_method='Cash', reference_no=None, notes=None, image=None, created_by=None):
    """Add a new expense."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (expense_no, category, description, amount, expense_date,
                                 payment_method, reference_no, notes, image, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (expense_no, category, description, amount, expense_date,
              payment_method, reference_no, notes, image, created_by))
        conn.commit()
        return cursor.lastrowid


def update_expense(expense_id, **kwargs):
    """Update an expense."""
    if not kwargs:
        return False
    
    set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    query = f"UPDATE expenses SET {set_clause} WHERE id = ?"
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, list(kwargs.values()) + [expense_id])
        conn.commit()
        return cursor.rowcount > 0


def delete_expense(expense_id):
    """Delete an expense."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== SETTINGS ==========

def get_settings():
    """Get all settings."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return dict(cursor.fetchall())


def get_setting(key, default=None):
    """Get a single setting."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default


def update_setting(key, value):
    """Update a setting."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        return True


# =============================================================================
# ✅ FIFO Stock Retrieval - NULL expiry handled correctly
# =============================================================================

def get_fifo_locations(product_id: int, quantity_needed: int):
    """
    Get locations with FIFO order for a product.
    
    ✅ FIX: NULL expiry dates are pushed to the end (after non-NULL dates).
    Expiry dates are sorted chronologically, and NULL/empty values come last.
    
    Returns:
        tuple: (locations_list, remaining_quantity)
        locations_list: List of dict with location, batch_no, expire_date, available, take
        remaining_quantity: Quantity still needed after FIFO allocation
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        _ensure_expiry_discount_columns(cursor)
        
        cursor.execute("""
            SELECT id, location, batch_no, expire_date, quantity,
                   COALESCE(expiry_discount_enabled, 0),
                   COALESCE(expiry_discount_percent, 0),
                   COALESCE(clearance_note, '')
            FROM product_locations
            WHERE product_id = ? AND quantity > 0
            ORDER BY 
                CASE 
                    WHEN expire_date IS NULL OR expire_date = '' THEN 1 
                    ELSE 0 
                END,
                expire_date ASC,
                last_updated ASC
        """, (product_id,))
        
        locations = []
        remaining = quantity_needed
        
        for loc_id, loc, batch, expiry, qty, discount_enabled, discount_percent, clearance_note in cursor.fetchall():
            if remaining <= 0:
                break
            take = min(qty, remaining)
            locations.append({
                'id': loc_id,
                'location': loc,
                'batch_no': batch or '',
                'expire_date': expiry,
                'available': qty,
                'take': take,
                'expiry_discount_enabled': bool(discount_enabled),
                'expiry_discount_percent': float(discount_percent or 0),
                'clearance_note': clearance_note or ''
            })
            remaining -= take
        
        return locations, remaining


# =============================================================================
# ✅ FIFO with Expiry Check - Blocks Expired Items
# =============================================================================

def check_expiry_status(expire_date_str):
    """
    Check expiry status of a product.
    
    Returns:
        'expired' - Expired, block sale
        'warning' - Expiring within 7 days, allow with warning
        'report' - Expiring within 30 days, allow with note
        'ok' - Safe to sell
        'no_expiry' - No expiry date set
    """
    if not expire_date_str or expire_date_str == '':
        return 'no_expiry'
    
    try:
        today = date.today()
        exp_date = date.fromisoformat(expire_date_str)
        
        if exp_date < today:
            return 'expired'
        elif exp_date <= today + timedelta(days=7):
            return 'warning'
        elif exp_date <= today + timedelta(days=30):
            return 'report'
        else:
            return 'ok'
    except:
        return 'no_expiry'


def get_fifo_locations_with_expiry_check(product_id: int, quantity_needed: int):
    """
    Get locations with FIFO order - EXCLUDING expired items.
    
    Returns:
        tuple: (locations_list, remaining_quantity, expired_items, warning_items)
        locations_list: List of dict with location, batch_no, expire_date, available, take, expiry_status
        remaining_quantity: Quantity still needed after allocation
        expired_items: List of expired items (blocked)
        warning_items: List of items expiring within 7 days (warning)
    """
    today = date.today()
    warning_threshold = today + timedelta(days=7)
    
    with DBContext() as conn:
        cursor = conn.cursor()
        _ensure_expiry_discount_columns(cursor)
        
        cursor.execute("""
            SELECT id, location, batch_no, expire_date, quantity,
                   COALESCE(expiry_discount_enabled, 0),
                   COALESCE(expiry_discount_percent, 0),
                   COALESCE(clearance_note, '')
            FROM product_locations
            WHERE product_id = ? AND quantity > 0
            ORDER BY 
                CASE 
                    WHEN expire_date IS NULL OR expire_date = '' THEN 1 
                    ELSE 0 
                END,
                expire_date ASC,
                last_updated ASC
        """, (product_id,))
        
        all_locations = cursor.fetchall()
        
        locations = []
        expired_items = []
        warning_items = []
        remaining = quantity_needed
        
        for loc_id, loc, batch, expiry, qty, discount_enabled, discount_percent, clearance_note in all_locations:
            if remaining <= 0:
                break
                
            # Check expiry status
            expiry_status = check_expiry_status(expiry)
            
            if expiry_status == 'expired':
                # ❌ Expired - block completely
                expired_items.append({
                    'id': loc_id,
                    'location': loc,
                    'batch_no': batch,
                    'expire_date': expiry,
                    'quantity': qty,
                    'expiry_discount_enabled': bool(discount_enabled),
                    'expiry_discount_percent': float(discount_percent or 0),
                    'clearance_note': clearance_note or ''
                })
                continue  # Skip expired items
                
            elif expiry_status == 'warning':
                # ⚠️ Warning - allow but track
                warning_items.append({
                    'id': loc_id,
                    'location': loc,
                    'batch_no': batch,
                    'expire_date': expiry,
                    'quantity': qty,
                    'expiry_discount_enabled': bool(discount_enabled),
                    'expiry_discount_percent': float(discount_percent or 0),
                    'clearance_note': clearance_note or ''
                })
                # Still allow sale with warning
                take = min(qty, remaining)
                locations.append({
                    'id': loc_id,
                    'location': loc,
                    'batch_no': batch or '',
                    'expire_date': expiry,
                    'available': qty,
                    'take': take,
                    'expiry_status': 'warning',
                    'expiry_discount_enabled': bool(discount_enabled),
                    'expiry_discount_percent': float(discount_percent or 0),
                    'clearance_note': clearance_note or ''
                })
                remaining -= take
                
            else:
                # ✅ OK or no expiry - normal sale
                take = min(qty, remaining)
                locations.append({
                    'id': loc_id,
                    'location': loc,
                    'batch_no': batch or '',
                    'expire_date': expiry,
                    'available': qty,
                    'take': take,
                    'expiry_status': 'ok',
                    'expiry_discount_enabled': bool(discount_enabled),
                    'expiry_discount_percent': float(discount_percent or 0),
                    'clearance_note': clearance_note or ''
                })
                remaining -= take
        
        return locations, remaining, expired_items, warning_items


def get_expired_stock_for_product(product_id: int):
    """Get all expired stock for a specific product."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, location, batch_no, expire_date, quantity
            FROM product_locations
            WHERE product_id = ? 
              AND quantity > 0
              AND expire_date IS NOT NULL 
              AND expire_date != ''
              AND date(expire_date) < date('now')
            ORDER BY expire_date ASC
        """, (product_id,))
        return cursor.fetchall()


def get_all_expired_stock():
    """Get all expired stock across all products."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.id as product_id,
                p.name as product_name,
                p.sku,
                pl.location,
                pl.batch_no,
                pl.expire_date,
                pl.quantity,
                p.category
            FROM product_locations pl
            JOIN products p ON pl.product_id = p.id
            WHERE pl.quantity > 0
              AND pl.expire_date IS NOT NULL 
              AND pl.expire_date != ''
              AND date(pl.expire_date) < date('now')
            ORDER BY pl.expire_date ASC, p.name ASC
        """)
        return cursor.fetchall()


def get_expiring_soon_stock(days: int = 7):
    """Get stock expiring within specified days (excluding expired)."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.id as product_id,
                p.name as product_name,
                p.sku,
                pl.location,
                pl.batch_no,
                pl.expire_date,
                pl.quantity,
                p.category,
                julianday(pl.expire_date) - julianday('now') as days_left
            FROM product_locations pl
            JOIN products p ON pl.product_id = p.id
            WHERE pl.quantity > 0
              AND pl.expire_date IS NOT NULL 
              AND pl.expire_date != ''
              AND date(pl.expire_date) >= date('now')
              AND date(pl.expire_date) <= date('now', ?)
            ORDER BY pl.expire_date ASC
        """, (f'+{days} days',))
        return cursor.fetchall()


def get_product_locations(product_id: int):
    """
    Get all locations for a product with batch and expiry info.
    
    ✅ FIX: NULL expiry dates come last in ordering
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, location, batch_no, expire_date, quantity, last_updated
            FROM product_locations
            WHERE product_id = ?
            ORDER BY 
                CASE 
                    WHEN expire_date IS NULL OR expire_date = '' THEN 1 
                    ELSE 0 
                END,
                expire_date ASC,
                last_updated ASC
        """, (product_id,))
        return cursor.fetchall()


def update_location_stock(location_id: int, new_quantity: int):
    """
    Update stock quantity for a specific location.
    If quantity becomes 0, delete the location entry.
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        
        if new_quantity <= 0:
            cursor.execute("DELETE FROM product_locations WHERE id = ?", (location_id,))
        else:
            cursor.execute("""
                UPDATE product_locations 
                SET quantity = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_quantity, location_id))
        
        conn.commit()
        return True


def get_total_stock_by_location(product_id: int, location: str = None):
    """
    Get total stock for a product, optionally filtered by location.
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        
        if location:
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM product_locations
                WHERE product_id = ? AND location = ?
            """, (product_id, location))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM product_locations
                WHERE product_id = ?
            """, (product_id,))
        
        return cursor.fetchone()[0]


# =============================================================================
# ✅ NEW: Stock Movement Reversal Functions
# =============================================================================

def reverse_stock_movement(movement_id: int, reason: str = "Correction", created_by: str = "System"):
    """
    Reverse a stock movement by creating an opposite movement.
    
    Args:
        movement_id: ID of the stock movement to reverse
        reason: Reason for reversal
        created_by: User who performed the reversal
    
    Returns:
        dict: Result with success status and message
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            
            # Get the original movement
            cursor.execute("""
                SELECT product_id, type, quantity, old_stock, new_stock, 
                       reason, reference, created_by, notes, location, supplier_id, variant_id
                FROM stock_movements
                WHERE id = ?
            """, (movement_id,))
            movement = cursor.fetchone()
            
            if not movement:
                conn.rollback()
                return {'success': False, 'message': 'Movement not found'}
            
            product_id, mov_type, quantity, old_stock, new_stock, ref_reason, reference, created_by_orig, notes, location, supplier_id, variant_id = movement
            
            # Determine reversal type
            if mov_type == 'in':
                reversal_type = 'out'
                reversal_reason = f"Reversal of Stock In: {ref_reason}"
            elif mov_type == 'out':
                reversal_type = 'in'
                reversal_reason = f"Reversal of Stock Out: {ref_reason}"
            elif mov_type == 'adjustment':
                reversal_type = 'adjustment'
                # Get adjustment details
                cursor.execute("""
                    SELECT type, quantity, old_stock, new_stock
                    FROM stock_movements
                    WHERE id = ?
                """, (movement_id,))
                adj_data = cursor.fetchone()
                if adj_data:
                    adj_type, adj_qty, adj_old, adj_new = adj_data
                    reversal_reason = f"Reversal of Adjustment: {ref_reason}"
                else:
                    conn.rollback()
                    return {'success': False, 'message': 'Could not determine adjustment details'}
            else:
                conn.rollback()
                return {'success': False, 'message': f'Unknown movement type: {mov_type}'}
            
            # Get current stock
            cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
            current_stock_row = cursor.fetchone()
            current_stock = current_stock_row[0] if current_stock_row else 0
            
            # Calculate new stock after reversal
            if mov_type == 'in':
                # Reverse stock in: remove the stock
                new_stock_after = current_stock - quantity
                if new_stock_after < 0:
                    conn.rollback()
                    return {'success': False, 'message': f'Insufficient stock to reverse. Current: {current_stock}, Reversal: {quantity}'}
            elif mov_type == 'out':
                # Reverse stock out: add the stock back
                new_stock_after = current_stock + quantity
            elif mov_type == 'adjustment':
                # Reverse the adjustment
                if new_stock > old_stock:
                    # Was an increase, reverse by decreasing
                    new_stock_after = current_stock - (new_stock - old_stock)
                else:
                    # Was a decrease, reverse by increasing
                    new_stock_after = current_stock + (old_stock - new_stock)
            else:
                conn.rollback()
                return {'success': False, 'message': f'Unsupported movement type: {mov_type}'}
            
            # Update product stock
            cursor.execute("""
                UPDATE products 
                SET stock = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_stock_after, product_id))

            # Variant movements must be reversed at the same inventory level.
            if variant_id:
                cursor.execute(
                    "SELECT stock FROM product_variants WHERE id = ? AND product_id = ?",
                    (variant_id, product_id),
                )
                variant_row = cursor.fetchone()
                if not variant_row:
                    conn.rollback()
                    return {'success': False, 'message': 'The movement variant no longer exists'}
                variant_stock = variant_row[0] or 0
                if mov_type == 'in':
                    variant_stock_after = variant_stock - quantity
                    if variant_stock_after < 0:
                        conn.rollback()
                        return {
                            'success': False,
                            'message': f'Insufficient variant stock to reverse. Current: {variant_stock}, Reversal: {quantity}',
                        }
                elif mov_type == 'out':
                    variant_stock_after = variant_stock + quantity
                else:
                    change = (new_stock or 0) - (old_stock or 0)
                    variant_stock_after = variant_stock - change
                cursor.execute(
                    "UPDATE product_variants SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND product_id = ?",
                    (variant_stock_after, variant_id, product_id),
                )
            
            # Update product locations if location was specified
            if location and mov_type == 'in':
                # Remove stock from location
                cursor.execute("""
                    UPDATE product_locations 
                    SET quantity = quantity - ?
                    WHERE product_id = ? AND location = ?
                """, (quantity, product_id, location))
                # Delete if zero
                cursor.execute("SELECT quantity FROM product_locations WHERE product_id = ? AND location = ?", (product_id, location))
                remaining = cursor.fetchone()
                if remaining and remaining[0] <= 0:
                    cursor.execute("DELETE FROM product_locations WHERE product_id = ? AND location = ?", (product_id, location))
            
            elif location and mov_type == 'out':
                # Add stock back to location
                cursor.execute("""
                    INSERT INTO product_locations (product_id, location, quantity)
                    VALUES (?, ?, ?)
                    ON CONFLICT(product_id, location) 
                    DO UPDATE SET quantity = product_locations.quantity + excluded.quantity,
                                  last_updated = CURRENT_TIMESTAMP
                """, (product_id, location, quantity))
            
            elif location and mov_type == 'adjustment':
                # Adjust location stock
                diff = new_stock - old_stock
                cursor.execute("""
                    UPDATE product_locations 
                    SET quantity = quantity - ?
                    WHERE product_id = ? AND location = ?
                """, (diff, product_id, location))
                # Delete if zero
                cursor.execute("SELECT quantity FROM product_locations WHERE product_id = ? AND location = ?", (product_id, location))
                remaining = cursor.fetchone()
                if remaining and remaining[0] <= 0:
                    cursor.execute("DELETE FROM product_locations WHERE product_id = ? AND location = ?", (product_id, location))
            
            # Create reversal movement record
            reversal_notes = f"REVERSAL: {notes}" if notes else "REVERSAL"
            reversal_ref = f"REV-{reference}" if reference else f"REV-{movement_id}"
            
            cursor.execute("""
                INSERT INTO stock_movements 
                (product_id, type, quantity, old_stock, new_stock, reason, reference, created_by, notes, location, supplier_id, variant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_id, 
                reversal_type, 
                quantity,
                current_stock,
                new_stock_after,
                reversal_reason,
                reversal_ref,
                created_by,
                reversal_notes,
                location,
                supplier_id,
                variant_id
            ))
            
            # Mark original movement as reversed
            cursor.execute("""
                UPDATE stock_movements 
                SET notes = COALESCE(notes, '') || ' [REVERSED]',
                    reference = COALESCE(reference, '') || '-REV'
                WHERE id = ?
            """, (movement_id,))
            
            conn.commit()
            
            return {
                'success': True, 
                'message': f'Stock movement reversed successfully. New stock: {new_stock_after}',
                'new_stock': new_stock_after,
                'reversal_id': cursor.lastrowid
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to reverse stock movement: {e}")
            return {'success': False, 'message': str(e)}


def get_stock_movement(movement_id: int):
    """Get a single stock movement by ID with product details."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                sm.id,
                sm.product_id,
                p.name as product_name,
                p.sku,
                sm.type,
                sm.quantity,
                sm.old_stock,
                sm.new_stock,
                sm.reason,
                sm.reference,
                sm.created_by,
                sm.notes,
                sm.location,
                sm.supplier_id,
                s.name as supplier_name,
                sm.created_at
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            LEFT JOIN suppliers s ON sm.supplier_id = s.id
            WHERE sm.id = ?
        """, (movement_id,))
        return cursor.fetchone()


def get_stock_movement_items(product_id: int = None, type_filter: str = None, 
                            from_date: str = None, to_date: str = None,
                            limit: int = 50, offset: int = 0):
    """Get stock movements with filters."""
    with DBContext() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                sm.id,
                p.name as product_name,
                p.sku,
                sm.type,
                sm.quantity,
                sm.old_stock,
                sm.new_stock,
                sm.reason,
                sm.reference,
                sm.created_by,
                sm.location,
                sm.created_at
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        if product_id:
            query += " AND sm.product_id = ?"
            params.append(product_id)
        
        if type_filter:
            query += " AND sm.type = ?"
            params.append(type_filter)
        
        if from_date:
            query += " AND date(sm.created_at) >= ?"
            params.append(from_date)
        
        if to_date:
            query += " AND date(sm.created_at) <= ?"
            params.append(to_date)
        
        query += " ORDER BY sm.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        return cursor.fetchall()
