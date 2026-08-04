# ui/ai_pages/ai_report_generator.py
"""
AI Report Generator - Generate comprehensive reports
FIXED: ambiguous column name error
"""

import csv
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger
from models.database.connection import DBContext


class AIReportGenerator:
    """AI-powered report generation"""
    
    @classmethod
    def generate_sales_report(cls, start_date: str, end_date: str) -> Dict:
        """
        Generate comprehensive sales report
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dict with sales report data
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # ✅ FIX: Use table alias to avoid ambiguous column name
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_transactions,
                        COALESCE(SUM(s.total), 0) as total_sales,
                        COALESCE(SUM(s.payment), 0) as total_payment,
                        COALESCE(SUM(s.gross_profit), 0) as total_profit,
                        COALESCE(AVG(s.total), 0) as avg_transaction
                    FROM sales s
                    WHERE date(s.created_at) BETWEEN ? AND ?
                    AND s.status = 'completed'
                """, (start_date, end_date))
                summary = cursor.fetchone()
                
                # ✅ FIX: Use table alias for all queries
                cursor.execute("""
                    SELECT 
                        date(s.created_at) as date,
                        COUNT(*) as transactions,
                        COALESCE(SUM(s.total), 0) as total_sales
                    FROM sales s
                    WHERE date(s.created_at) BETWEEN ? AND ?
                    AND s.status = 'completed'
                    GROUP BY date(s.created_at)
                    ORDER BY date(s.created_at)
                """, (start_date, end_date))
                daily = cursor.fetchall()
                
                # ✅ FIX: Payment types query
                cursor.execute("""
                    SELECT 
                        s.payment_type,
                        COUNT(*) as count,
                        COALESCE(SUM(s.total), 0) as total
                    FROM sales s
                    WHERE date(s.created_at) BETWEEN ? AND ?
                    AND s.status = 'completed'
                    AND s.payment_type IS NOT NULL
                    GROUP BY s.payment_type
                """, (start_date, end_date))
                payment_types = cursor.fetchall()
                
                # ✅ FIX: Top products query
                cursor.execute("""
                    SELECT 
                        si.product_name,
                        SUM(si.qty) as qty,
                        SUM(si.total) as revenue,
                        COUNT(DISTINCT si.sale_id) as transactions
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    WHERE s.status = 'completed'
                    AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY si.product_name
                    ORDER BY revenue DESC
                    LIMIT 10
                """, (start_date, end_date))
                top_products = cursor.fetchall()
                
                return {
                    'summary': {
                        'total_transactions': summary[0] if summary else 0,
                        'total_sales': float(summary[1]) if summary else 0,
                        'total_payment': float(summary[2]) if summary else 0,
                        'total_profit': float(summary[3]) if summary else 0,
                        'avg_transaction': float(summary[4]) if summary else 0,
                        'currency': 'Ks'
                    },
                    'daily': [{
                        'date': d[0],
                        'transactions': d[1],
                        'total_sales': float(d[2])
                    } for d in daily],
                    'payment_types': [{
                        'type': p[0] or 'Unknown',
                        'count': p[1],
                        'total': float(p[2])
                    } for p in payment_types],
                    'top_products': [{
                        'name': p[0],
                        'qty': p[1],
                        'revenue': float(p[2]),
                        'transactions': p[3]
                    } for p in top_products],
                    'period': {
                        'start_date': start_date,
                        'end_date': end_date
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to generate sales report: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    @classmethod
    def generate_inventory_report(cls) -> Dict:
        """Generate inventory report"""
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Summary
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_products,
                        COALESCE(SUM(stock), 0) as total_stock,
                        COALESCE(SUM(stock * cost), 0) as total_value,
                        COUNT(CASE WHEN stock = 0 THEN 1 END) as out_of_stock,
                        COUNT(CASE WHEN stock <= low_stock AND stock > 0 THEN 1 END) as low_stock
                    FROM products
                    WHERE sold_by IS NULL OR sold_by != 'Service'
                """)
                summary = cursor.fetchone()
                
                # Products by category
                cursor.execute("""
                    SELECT 
                        category,
                        COUNT(*) as product_count,
                        COALESCE(SUM(stock), 0) as total_stock,
                        COALESCE(SUM(stock * cost), 0) as total_value
                    FROM products
                    WHERE sold_by IS NULL OR sold_by != 'Service'
                    AND category IS NOT NULL
                    GROUP BY category
                    ORDER BY total_value DESC
                """)
                by_category = cursor.fetchall()
                
                # Low stock products
                cursor.execute("""
                    SELECT 
                        name,
                        sku,
                        stock,
                        low_stock,
                        price,
                        cost
                    FROM products
                    WHERE stock <= low_stock AND stock > 0
                    AND (sold_by IS NULL OR sold_by != 'Service')
                    ORDER BY stock ASC
                    LIMIT 20
                """)
                low_stock = cursor.fetchall()
                
                return {
                    'summary': {
                        'total_products': summary[0] if summary else 0,
                        'total_stock': summary[1] if summary else 0,
                        'total_value': float(summary[2]) if summary else 0,
                        'out_of_stock': summary[3] if summary else 0,
                        'low_stock': summary[4] if summary else 0,
                        'currency': 'Ks'
                    },
                    'by_category': [{
                        'category': c[0] or 'Uncategorized',
                        'product_count': c[1],
                        'total_stock': c[2],
                        'total_value': float(c[3])
                    } for c in by_category],
                    'low_stock': [{
                        'name': l[0],
                        'sku': l[1] or '-',
                        'stock': l[2],
                        'low_stock': l[3],
                        'price': float(l[4]) if l[4] else 0,
                        'cost': float(l[5]) if l[5] else 0
                    } for l in low_stock]
                }
                
        except Exception as e:
            logger.error(f"Failed to generate inventory report: {e}")
            return {}
    
    @classmethod
    def export_to_csv(cls, data: List[Dict], filename: str, headers: List[str] = None) -> bool:
        """Export data to CSV"""
        try:
            if not data:
                logger.warning("No data to export")
                return False
            
            if not headers:
                headers = list(data[0].keys())
            
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Exported {len(data)} records to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return False
    
    @classmethod
    def export_to_json(cls, data: Dict, filename: str) -> bool:
        """Export data to JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Exported data to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            return False