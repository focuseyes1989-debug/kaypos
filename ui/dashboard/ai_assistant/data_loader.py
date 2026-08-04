# ui/dashboard/ai_assistant/data_loader.py
"""Data fetching functions"""

from models.database import connect_db
from datetime import datetime, timedelta


def get_quick_stats():
    """Get quick stats for header"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as total_sales,
            COUNT(DISTINCT s.id) as total_orders,
            COALESCE(AVG(si.qty * si.price), 0) as avg_order
        FROM sales s
        JOIN sale_items si ON s.id = si.sale_id
        WHERE s.status = 'completed'
          AND date(s.created_at) = date('now')
    """)
    
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, 0, 0)


def get_today_yesterday_sales():
    """Get today and yesterday sales"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as today_sales,
            COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as today_discount
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) = date('now')
    """)
    row = cursor.fetchone()
    today_sales = row[0] if row else 0
    today_discount = row[1] if row else 0
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as yesterday_sales
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) = date('now', '-1 day')
    """)
    yesterday_row = cursor.fetchone()
    yesterday_sales = yesterday_row[0] if yesterday_row else 0
    
    conn.close()
    return today_sales, today_discount, yesterday_sales


def get_weekly_comparison():
    """Get weekly sales comparison"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as this_week
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) >= date('now', 'weekday 0', '-7 days')
          AND date(s.created_at) < date('now', 'weekday 0')
    """)
    this_week = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as last_week
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) >= date('now', 'weekday 0', '-14 days')
          AND date(s.created_at) < date('now', 'weekday 0', '-7 days')
    """)
    last_week = cursor.fetchone()[0]
    
    conn.close()
    return this_week, last_week


def get_monthly_comparison():
    """Get monthly sales comparison"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as this_month
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) >= date('now', 'start of month')
    """)
    this_month = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(si.qty * si.price), 0) as last_month
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) >= date('now', 'start of month', '-1 month')
          AND date(s.created_at) < date('now', 'start of month')
    """)
    last_month = cursor.fetchone()[0]
    
    conn.close()
    return this_month, last_month


def get_top_categories(from_date, to_date):
    """Get top selling categories"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(p.category, 'Uncategorized') as category,
            COALESCE(SUM(si.qty * si.price), 0) as total
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        LEFT JOIN products p ON si.product_name = p.name
        WHERE s.status = 'completed' 
          AND date(s.created_at) BETWEEN ? AND ?
        GROUP BY p.category
        ORDER BY total DESC
        LIMIT 3
    """, (from_date, to_date))
    
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_top_products(from_date, to_date):
    """Get top selling products"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            si.product_name,
            COALESCE(SUM(si.qty), 0) as qty,
            COALESCE(SUM(si.qty * si.price), 0) as total
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed' 
          AND date(s.created_at) BETWEEN ? AND ?
        GROUP BY si.product_name
        ORDER BY total DESC
        LIMIT 5
    """, (from_date, to_date))
    
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_payment_breakdown(from_date, to_date):
    """Get payment method breakdown"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COALESCE(payment_type, 'Other') as payment_type,
            COALESCE(SUM(total), 0) as total
        FROM sales
        WHERE status = 'completed' 
          AND date(created_at) BETWEEN ? AND ?
        GROUP BY payment_type
        ORDER BY total DESC
    """, (from_date, to_date))
    
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_stock_alert():
    """Get low stock and out of stock counts"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM products 
        WHERE (sold_by IS NULL OR sold_by != 'Service') 
          AND stock > 0 AND stock <= low_stock
    """)
    low_stock = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM products 
        WHERE (sold_by IS NULL OR sold_by != 'Service') 
          AND stock = 0
    """)
    out_of_stock = cursor.fetchone()[0]
    
    conn.close()
    return low_stock, out_of_stock


def get_peak_hour():
    """Get peak sales hour"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            strftime('%H', created_at) as hour,
            COALESCE(SUM(si.qty * si.price), 0) as total
        FROM sales s
        JOIN sale_items si ON s.id = si.sale_id
        WHERE s.status = 'completed'
          AND date(created_at) = date('now')
        GROUP BY hour
        ORDER BY total DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_repeat_customers():
    """Get repeat customer rate"""
    conn = connect_db()
    cursor = conn.cursor()
    
    # Check if customer_name column exists
    cursor.execute("PRAGMA table_info(sales)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'customer_name' not in columns:
        conn.close()
        return 0, 0
    
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT customer_name) as total_customers,
            COUNT(DISTINCT CASE WHEN customer_name IN (
                SELECT customer_name FROM sales 
                WHERE status = 'completed' 
                  AND customer_name IS NOT NULL 
                  AND customer_name != ''
                GROUP BY customer_name 
                HAVING COUNT(*) > 1
            ) THEN customer_name END) as repeat_customers
        FROM sales
        WHERE status = 'completed'
          AND customer_name IS NOT NULL 
          AND customer_name != ''
          AND date(created_at) >= date('now', '-30 days')
    """)
    
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else 0, row[1] if row and row[1] else 0


def get_forecast(days=7):
    """Simple moving average forecast"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            date(created_at) as sale_date,
            COALESCE(SUM(si.qty * si.price), 0) as daily_total
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.status = 'completed'
          AND date(created_at) >= date('now', ?)
        GROUP BY date(created_at)
        ORDER BY sale_date DESC
    """, (f'-{days} days',))
    
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 3:
        return 0
    
    totals = [row[1] for row in rows]
    return sum(totals) / len(totals)