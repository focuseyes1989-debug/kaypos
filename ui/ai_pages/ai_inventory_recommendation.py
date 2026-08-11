# ui/ai_pages/ai_inventory_recommendation.py
"""
AI Inventory Recommendation - Smart restocking suggestions
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from models.database.connection import DBContext


class AIInventoryRecommendation:
    """AI-powered inventory recommendations"""
    
    @classmethod
    def get_reorder_recommendations(cls, threshold_days: int = 30) -> List[Dict]:
        """
        Get products that need reordering based on sales velocity
        
        Args:
            threshold_days: Days to consider for sales velocity
            
        Returns:
            List of recommendations with priority
        """
        recommendations = []
        
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Get products with sales velocity
                cursor.execute("""
                    SELECT 
                        p.id,
                        p.name,
                        p.sku,
                        p.stock,
                        p.low_stock,
                        p.price,
                        p.supplier_id,
                        s.name as supplier_name,
                        COALESCE(SUM(si.qty), 0) as total_sold,
                        COUNT(DISTINCT si.sale_id) as sale_count,
                        AVG(si.qty) as avg_qty_per_sale
                    FROM products p
                    LEFT JOIN sale_items si ON p.name = si.product_name
                    LEFT JOIN sales sl ON si.sale_id = sl.id 
                        AND sl.status = 'completed'
                        AND date(sl.created_at) >= date('now', ?)
                    LEFT JOIN suppliers s ON p.supplier_id = s.id
                    WHERE p.sold_by IS NULL OR p.sold_by != 'Service'
                    GROUP BY p.id, p.name, p.sku, p.stock, p.low_stock, p.price, p.supplier_id, s.name
                    ORDER BY (p.stock / (COALESCE(SUM(si.qty), 1) + 1)) ASC
                    LIMIT 50
                """, (f'-{threshold_days} days',))
                
                products = cursor.fetchall()
                
                for p in products:
                    pid, name, sku, stock, low_stock, price, supplier_id, supplier_name, total_sold, sale_count, avg_qty = p
                    
                    # Calculate days of stock remaining
                    daily_avg = total_sold / threshold_days if total_sold > 0 else 0
                    days_remaining = stock / daily_avg if daily_avg > 0 else 999
                    
                    # Determine priority
                    if stock <= low_stock:
                        priority = "critical"
                        priority_label = "🚨 CRITICAL"
                    elif days_remaining < 7:
                        priority = "high"
                        priority_label = "🔴 HIGH"
                    elif days_remaining < 14:
                        priority = "medium"
                        priority_label = "🟡 MEDIUM"
                    elif days_remaining < 30:
                        priority = "low"
                        priority_label = "🟢 LOW"
                    else:
                        priority = "none"
                        continue
                    
                    # Calculate recommended order quantity
                    recommended_qty = max(low_stock * 2, int(daily_avg * 14)) if daily_avg > 0 else low_stock * 2
                    if recommended_qty < 1:
                        recommended_qty = 10
                    
                    recommendations.append({
                        'id': pid,
                        'name': name,
                        'sku': sku,
                        'stock': stock,
                        'low_stock': low_stock,
                        'price': price,
                        'supplier_id': supplier_id,
                        'supplier_name': supplier_name or 'Unknown',
                        'total_sold': total_sold,
                        'daily_avg': daily_avg,
                        'days_remaining': days_remaining,
                        'recommended_qty': int(recommended_qty),
                        'priority': priority,
                        'priority_label': priority_label
                    })
                
                # Sort by priority
                priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
                recommendations.sort(key=lambda x: priority_order.get(x['priority'], 4))
                
                logger.info(f"Generated {len(recommendations)} reorder recommendations")
                return recommendations
                
        except Exception as e:
            logger.error(f"Failed to get reorder recommendations: {e}")
            return []
    
    @classmethod
    def get_supplier_recommendations(cls, product_id: int) -> List[Dict]:
        """
        Get supplier recommendations for a product
        
        Args:
            product_id: Product ID
            
        Returns:
            List of suppliers with their performance
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        s.id,
                        s.name,
                        s.phone,
                        s.email,
                        s.address,
                        COUNT(DISTINCT po.id) as po_count,
                        COALESCE(SUM(po.total_amount), 0) as total_spent,
                        AVG(po.total_amount) as avg_order_value
                    FROM suppliers s
                    LEFT JOIN purchase_orders po ON s.id = po.supplier_id
                    WHERE po.status != 'cancelled' OR po.status IS NULL
                    GROUP BY s.id
                    ORDER BY po_count DESC, total_spent DESC
                    LIMIT 5
                """)
                
                suppliers = cursor.fetchall()
                
                return [{
                    'id': s[0],
                    'name': s[1],
                    'phone': s[2],
                    'email': s[3],
                    'address': s[4],
                    'po_count': s[5],
                    'total_spent': s[6],
                    'avg_order_value': s[7]
                } for s in suppliers]
                
        except Exception as e:
            logger.error(f"Failed to get supplier recommendations: {e}")
            return []
    
    @classmethod
    def get_seasonal_recommendations(cls) -> List[Dict]:
        """
        Get seasonal product recommendations based on historical patterns
        
        Returns:
            List of seasonal insights
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Get month-over-month growth
                cursor.execute("""
                    WITH monthly_sales AS (
                        SELECT 
                            strftime('%Y-%m', created_at) as month,
                            product_name,
                            SUM(qty) as total_qty
                        FROM sale_items si
                        JOIN sales s ON si.sale_id = s.id
                        WHERE s.status = 'completed'
                        GROUP BY strftime('%Y-%m', created_at), product_name
                    ),
                    growth AS (
                        SELECT 
                            product_name,
                            total_qty,
                            LAG(total_qty, 1) OVER (PARTITION BY product_name ORDER BY month) as prev_qty,
                            ROUND((total_qty - LAG(total_qty, 1) OVER (PARTITION BY product_name ORDER BY month)) 
                                  / LAG(total_qty, 1) OVER (PARTITION BY product_name ORDER BY month) * 100, 1) as growth_pct
                        FROM monthly_sales
                    )
                    SELECT 
                        p.name,
                        p.sku,
                        g.total_qty,
                        g.growth_pct,
                        p.stock,
                        p.low_stock
                    FROM growth g
                    JOIN products p ON g.product_name = p.name
                    WHERE g.growth_pct > 20
                    AND g.prev_qty IS NOT NULL
                    ORDER BY g.growth_pct DESC
                    LIMIT 20
                """)
                
                results = cursor.fetchall()
                
                return [{
                    'name': r[0],
                    'sku': r[1],
                    'total_qty': r[2],
                    'growth_pct': r[3],
                    'stock': r[4],
                    'low_stock': r[5],
                    'trend': '📈 Up' if r[3] > 0 else '📉 Down'
                } for r in results]
                
        except Exception as e:
            logger.error(f"Failed to get seasonal recommendations: {e}")
            return []
    
    @classmethod
    def get_inventory_summary(cls) -> Dict:
        """
        Get inventory summary statistics
        
        Returns:
            Dict with summary metrics
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Total products
                cursor.execute("""
                    SELECT COUNT(*) FROM products
                    WHERE sold_by IS NULL OR sold_by != 'Service'
                """)
                total_products = cursor.fetchone()[0]
                
                # Out of stock
                cursor.execute("""
                    SELECT COUNT(*) FROM products
                    WHERE stock <= 0 AND (sold_by IS NULL OR sold_by != 'Service')
                """)
                out_of_stock = cursor.fetchone()[0]
                
                # Low stock
                cursor.execute("""
                    SELECT COUNT(*) FROM products
                    WHERE stock <= low_stock AND stock > 0 
                    AND (sold_by IS NULL OR sold_by != 'Service')
                """)
                low_stock = cursor.fetchone()[0]
                
                # Total stock value
                cursor.execute("""
                    SELECT COALESCE(SUM(stock * cost), 0) FROM products
                    WHERE (sold_by IS NULL OR sold_by != 'Service')
                """)
                total_value = cursor.fetchone()[0]
                
                return {
                    'total_products': total_products,
                    'out_of_stock': out_of_stock,
                    'low_stock': low_stock,
                    'healthy_stock': total_products - out_of_stock - low_stock,
                    'total_value': total_value,
                    'currency': 'Ks'
                }
                
        except Exception as e:
            logger.error(f"Failed to get inventory summary: {e}")
            return {}
