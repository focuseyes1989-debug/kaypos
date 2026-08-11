# ui/ai_pages/ai_dashboard/dashboard_data.py
"""
Data loading for AI Dashboard
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from loguru import logger
from models.database.connection import DBContext


class DashboardData:
    """Dashboard data loader"""
    
    @staticmethod
    def get_sales_data(start_date: str, end_date: str) -> Tuple[Optional[tuple], List[tuple], List[tuple], List[tuple], Optional[tuple]]:
        """
        Get all sales data for the given period
        
        Returns:
            Tuple of (sales_data, daily_data, category_data, recent_sales, expense_data)
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Total sales
                cursor.execute("""
                    SELECT 
                        COUNT(*) as transactions,
                        COALESCE(SUM(total), 0) as total_sales,
                        COALESCE(SUM(payment), 0) as total_payment,
                        COALESCE(AVG(total), 0) as avg_sale,
                        COALESCE(SUM(gross_profit), 0) as total_profit
                    FROM sales
                    WHERE date(created_at) BETWEEN ? AND ?
                    AND status = 'completed'
                """, (start_date, end_date))
                sales_data = cursor.fetchone()
                
                # Daily sales for chart
                cursor.execute("""
                    SELECT 
                        date(created_at) as date,
                        COUNT(*) as transactions,
                        COALESCE(SUM(total), 0) as total_sales
                    FROM sales
                    WHERE date(created_at) BETWEEN ? AND ?
                    AND status = 'completed'
                    GROUP BY date(created_at)
                    ORDER BY date(created_at)
                """, (start_date, end_date))
                daily_data = cursor.fetchall()
                
                # Sales by category
                cursor.execute("""
                    SELECT 
                        COALESCE(p.category, 'Uncategorized') as category,
                        COUNT(*) as count,
                        COALESCE(SUM(si.total), 0) as total
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    LEFT JOIN products p ON si.product_id = p.id OR (si.product_id IS NULL AND si.product_name = p.name)
                    WHERE s.status = 'completed'
                    AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY COALESCE(p.category, 'Uncategorized')
                    ORDER BY total DESC
                    LIMIT 8
                """, (start_date, end_date))
                category_data = cursor.fetchall()
                
                # Recent activities
                cursor.execute("""
                    SELECT 
                        'Sale' as type,
                        invoice_no as reference,
                        total as amount,
                        created_at
                    FROM sales
                    WHERE date(created_at) BETWEEN ? AND ?
                    AND status = 'completed'
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (start_date, end_date))
                recent_sales = cursor.fetchall()
                
                # Expenses summary
                cursor.execute("""
                    SELECT 
                        COUNT(*) as count,
                        COALESCE(SUM(amount), 0) as total
                    FROM expenses
                    WHERE date(expense_date) BETWEEN ? AND ?
                """, (start_date, end_date))
                expense_data = cursor.fetchone()
                
                return sales_data, daily_data, category_data, recent_sales, expense_data
                
        except Exception as e:
            logger.error(f"Failed to load dashboard data: {e}")
            return None, [], [], [], None


def get_dashboard_data_sync() -> Dict:
    """Get dashboard data as dict for external use"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        with DBContext() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(gross_profit), 0) as total_profit
                FROM sales
                WHERE date(created_at) = ?
                AND status = 'completed'
            """, (today,))
            today_data = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) FROM products
                WHERE stock <= low_stock AND stock > 0
            """)
            low_stock = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM customers")
            total_customers = cursor.fetchone()[0]
            
            return {
                'today_sales': float(today_data[1]) if today_data and today_data[1] else 0,
                'today_transactions': today_data[0] if today_data and today_data[0] else 0,
                'today_profit': float(today_data[2]) if today_data and today_data[2] else 0,
                'low_stock_count': low_stock or 0,
                'total_customers': total_customers or 0,
                'currency': 'Ks'
            }
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        return {}
