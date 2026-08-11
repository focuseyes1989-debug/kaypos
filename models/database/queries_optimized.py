# models/database/queries_optimized.py
"""
Optimized database queries with caching and pagination.
"""

import sqlite3
from loguru import logger
from models.database.connection import DBContext
from models.database.cache import cached_query, _query_cache


# ========== OPTIMIZED PRODUCT QUERIES ==========

@cached_query(ttl_seconds=60)  # 1 minute cache
def get_products_optimized(category=None, search=None, 
                           limit=25, offset=0, sort_by="name"):
    """
    Get products with optimized query and pagination.
    """
    query = """
        SELECT id, name, category, price, stock, sku, barcode,
               expire_date, low_stock, image
        FROM products
        WHERE 1=1
    """
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if search:
        query += " AND (name LIKE ? OR sku LIKE ? OR barcode LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    # Use indexed columns for sorting
    if sort_by == "name":
        query += " ORDER BY name COLLATE NOCASE"
    elif sort_by == "price":
        query += " ORDER BY price"
    elif sort_by == "stock":
        query += " ORDER BY stock"
    elif sort_by == "category":
        query += " ORDER BY category"
    else:
        query += " ORDER BY name COLLATE NOCASE"
    
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def get_product_count_optimized(category=None, search=None):
    """
    Get total product count for pagination.
    """
    query = "SELECT COUNT(*) FROM products WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if search:
        query += " AND (name LIKE ? OR sku LIKE ? OR barcode LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()[0]


def bulk_update_products(updates):
    """
    Bulk update products in a single transaction.
    """
    if not updates:
        return 0
    
    with DBContext() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN TRANSACTION")
            
            updated = 0
            for product_id, data in updates.items():
                set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
                query = f"UPDATE products SET {set_clause}, last_updated = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, list(data.values()) + [product_id])
                updated += cursor.rowcount
            
            conn.commit()
            
            # Clear cache
            _query_cache.clear()
            
            return updated
        except Exception as e:
            conn.rollback()
            logger.error(f"Bulk update failed: {e}")
            raise


# ========== OPTIMIZED SALES QUERIES ==========

@cached_query(ttl_seconds=30)  # 30 seconds cache
def get_daily_sales_summary(date=None):
    """
    Get daily sales summary with optimized aggregation.
    """
    if date is None:
        from datetime import date
        date = date.today().strftime("%Y-%m-%d")
    
    query = """
        SELECT 
            COUNT(*) as total_transactions,
            COALESCE(SUM(total), 0) as total_sales,
            COALESCE(SUM(payment), 0) as total_payment,
            COALESCE(AVG(total), 0) as avg_transaction,
            COALESCE(MAX(total), 0) as max_transaction,
            COALESCE(MIN(total), 0) as min_transaction,
            COALESCE(SUM(cogs), 0) as total_cogs,
            COALESCE(SUM(gross_profit), 0) as total_profit
        FROM sales
        WHERE date(created_at) = ?
        AND status = 'completed'
    """
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (date,))
        return cursor.fetchone()


@cached_query(ttl_seconds=60)
def get_top_products(start_date, end_date, limit=10):
    """
    Get top selling products with aggregated sales.
    """
    query = """
        SELECT 
            si.product_name,
            COUNT(*) as total_transactions,
            SUM(si.qty) as total_quantity,
            SUM(si.total) as total_revenue,
            AVG(si.price) as avg_price
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed'
        AND date(s.created_at) >= ?
        AND date(s.created_at) <= ?
        GROUP BY si.product_name
        ORDER BY total_revenue DESC
        LIMIT ?
    """
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date, limit))
        return cursor.fetchall()


# ========== OPTIMIZED CUSTOMER QUERIES ==========

@cached_query(ttl_seconds=60)
def get_customer_with_stats(customer_id):
    """
    Get customer with calculated stats in one query.
    """
    query = """
        SELECT 
            c.*,
            COUNT(DISTINCT s.id) as total_orders,
            COALESCE(SUM(s.total), 0) as total_spent,
            COALESCE(AVG(s.total), 0) as avg_order_value,
            MAX(s.created_at) as last_order_date,
            COUNT(DISTINCT DATE(s.created_at)) as active_days
        FROM customers c
        LEFT JOIN sales s ON c.id = s.customer_id AND s.status = 'completed'
        WHERE c.id = ?
        GROUP BY c.id
    """
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (customer_id,))
        return cursor.fetchone()


def search_customers_optimized(search_term, limit=20):
    """
    Optimized customer search with ranking.
    """
    query = """
        SELECT 
            id, name, phone, email, address,
            total_spent, points,
            CASE 
                WHEN name LIKE ? THEN 100
                WHEN phone LIKE ? THEN 80
                WHEN email LIKE ? THEN 60
                ELSE 0
            END as relevance
        FROM customers
        WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
        ORDER BY relevance DESC, name
        LIMIT ?
    """
    search_pattern = f"%{search_term}%"
    
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (
            search_pattern, search_pattern, search_pattern,
            search_pattern, search_pattern, search_pattern,
            limit
        ))
        return cursor.fetchall()