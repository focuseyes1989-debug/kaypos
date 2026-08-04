# ui/ai_pages/ai_customer_insights.py
"""
AI Customer Insights - Purchase patterns and analytics
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from models.database.connection import DBContext


class AICustomerInsights:
    """AI-powered customer insights and analytics"""
    
    @classmethod
    def get_customer_purchase_history(cls, customer_id: int, limit: int = 20) -> List[Dict]:
        """
        Get detailed purchase history for a customer
        
        Args:
            customer_id: Customer ID
            limit: Number of records to return
            
        Returns:
            List of purchase records with details
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        s.id,
                        s.invoice_no,
                        s.created_at,
                        s.total,
                        s.payment_type,
                        COUNT(si.id) as item_count,
                        SUM(si.qty) as total_items
                    FROM sales s
                    LEFT JOIN sale_items si ON s.id = si.sale_id
                    WHERE s.customer_id = ?
                    AND s.status = 'completed'
                    GROUP BY s.id
                    ORDER BY s.created_at DESC
                    LIMIT ?
                """, (customer_id, limit))
                
                sales = cursor.fetchall()
                
                results = []
                for s in sales:
                    # Get items for this sale
                    cursor.execute("""
                        SELECT product_name, qty, price, total
                        FROM sale_items
                        WHERE sale_id = ?
                    """, (s[0],))
                    items = cursor.fetchall()
                    
                    results.append({
                        'id': s[0],
                        'invoice_no': s[1],
                        'date': s[2],
                        'total': s[3],
                        'payment_type': s[4],
                        'item_count': s[5] or 0,
                        'total_items': s[6] or 0,
                        'items': [{
                            'name': i[0],
                            'qty': i[1],
                            'price': i[2],
                            'total': i[3]
                        } for i in items]
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get customer purchase history: {e}")
            return []
    
    @classmethod
    def get_frequent_items(cls, customer_id: int, limit: int = 10) -> List[Dict]:
        """
        Get most frequently purchased items by a customer
        
        Args:
            customer_id: Customer ID
            limit: Number of items to return
            
        Returns:
            List of items with frequency
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        si.product_name,
                        COUNT(*) as purchase_count,
                        SUM(si.qty) as total_qty,
                        SUM(si.total) as total_spent,
                        AVG(si.price) as avg_price
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    WHERE s.customer_id = ?
                    AND s.status = 'completed'
                    GROUP BY si.product_name
                    ORDER BY purchase_count DESC, total_spent DESC
                    LIMIT ?
                """, (customer_id, limit))
                
                results = cursor.fetchall()
                
                return [{
                    'name': r[0],
                    'purchase_count': r[1],
                    'total_qty': r[2],
                    'total_spent': r[3],
                    'avg_price': r[4]
                } for r in results]
                
        except Exception as e:
            logger.error(f"Failed to get frequent items: {e}")
            return []
    
    @classmethod
    def get_customer_segments(cls) -> List[Dict]:
        """
        Segment customers based on purchase behavior
        
        Returns:
            List of customer segments with counts
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Get customer metrics
                cursor.execute("""
                    SELECT 
                        id,
                        name,
                        total_spent,
                        total_visit,
                        points,
                        created_at
                    FROM customers
                    WHERE total_spent > 0
                """)
                customers = cursor.fetchall()
                
                segments = {
                    'VIP': {'min_spent': 1000000, 'min_visits': 20, 'label': '👑 VIP'},
                    'Regular': {'min_spent': 200000, 'min_visits': 5, 'label': '⭐ Regular'},
                    'Occasional': {'min_spent': 50000, 'min_visits': 1, 'label': '📋 Occasional'},
                    'New': {'min_spent': 0, 'min_visits': 0, 'label': '🆕 New'}
                }
                
                segment_counts = {k: 0 for k in segments.keys()}
                segment_customers = {k: [] for k in segments.keys()}
                
                for c in customers:
                    cid, name, spent, visits, points, created_at = c
                    
                    assigned = False
                    for seg, criteria in segments.items():
                        if spent >= criteria['min_spent'] and visits >= criteria['min_visits']:
                            if seg == 'VIP' or seg == 'Regular':
                                segment_counts[seg] += 1
                                segment_customers[seg].append({'id': cid, 'name': name, 'spent': spent, 'visits': visits})
                                assigned = True
                                break
                    
                    if not assigned:
                        if visits <= 3:
                            segment_counts['New'] += 1
                            segment_customers['New'].append({'id': cid, 'name': name, 'spent': spent, 'visits': visits})
                        else:
                            segment_counts['Occasional'] += 1
                            segment_customers['Occasional'].append({'id': cid, 'name': name, 'spent': spent, 'visits': visits})
                
                return [{
                    'name': seg,
                    'label': data['label'],
                    'count': segment_counts[seg],
                    'customers': segment_customers[seg][:5]  # Top 5
                } for seg, data in segments.items() if segment_counts[seg] > 0]
                
        except Exception as e:
            logger.error(f"Failed to get customer segments: {e}")
            return []
    
    @classmethod
    def get_customer_lifetime_value(cls, customer_id: int) -> Dict:
        """
        Calculate customer lifetime value metrics
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dict with CLV metrics
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Get customer info
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.name,
                        c.phone,
                        c.total_spent,
                        c.total_visit,
                        c.points,
                        c.created_at,
                        COUNT(s.id) as total_orders,
                        MAX(s.created_at) as last_order,
                        MIN(s.created_at) as first_order
                    FROM customers c
                    LEFT JOIN sales s ON c.id = s.customer_id AND s.status = 'completed'
                    WHERE c.id = ?
                    GROUP BY c.id
                """, (customer_id,))
                
                customer = cursor.fetchone()
                
                if not customer:
                    return {}
                
                cid, name, phone, total_spent, visits, points, created_at, orders, last_order, first_order = customer
                
                # Calculate metrics
                from datetime import datetime
                days_as_customer = (datetime.now() - datetime.fromisoformat(created_at[:10])).days if created_at else 0
                days_since_last = (datetime.now() - datetime.fromisoformat(last_order[:10])).days if last_order else None
                
                avg_order_value = total_spent / orders if orders > 0 else 0
                avg_orders_per_month = orders / (days_as_customer / 30) if days_as_customer > 0 else 0
                
                return {
                    'id': cid,
                    'name': name,
                    'phone': phone,
                    'total_spent': total_spent,
                    'total_visits': visits,
                    'points': points,
                    'total_orders': orders,
                    'avg_order_value': avg_order_value,
                    'orders_per_month': avg_orders_per_month,
                    'days_as_customer': days_as_customer,
                    'days_since_last': days_since_last,
                    'first_order': first_order,
                    'last_order': last_order,
                    'currency': 'Ks'
                }
                
        except Exception as e:
            logger.error(f"Failed to get customer lifetime value: {e}")
            return {}
    
    @classmethod
    def get_churn_risk_customers(cls, days_inactive: int = 90) -> List[Dict]:
        """
        Get customers at risk of churning
        
        Args:
            days_inactive: Days since last purchase to consider at risk
            
        Returns:
            List of customers at risk
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                cutoff = (datetime.now() - timedelta(days=days_inactive)).strftime("%Y-%m-%d")
                
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.name,
                        c.phone,
                        c.total_spent,
                        c.total_visit,
                        COALESCE(MAX(s.created_at), '') as last_order,
                        COUNT(s.id) as total_orders
                    FROM customers c
                    LEFT JOIN sales s ON c.id = s.customer_id AND s.status = 'completed'
                    GROUP BY c.id
                    HAVING MAX(s.created_at) < ? OR MAX(s.created_at) IS NULL
                    ORDER BY MAX(s.created_at) ASC
                    LIMIT 20
                """, (cutoff,))
                
                results = cursor.fetchall()
                
                return [{
                    'id': r[0],
                    'name': r[1],
                    'phone': r[2],
                    'total_spent': r[3],
                    'total_visits': r[4],
                    'last_order': r[5] or 'Never',
                    'total_orders': r[6] or 0,
                    'days_inactive': days_inactive
                } for r in results]
                
        except Exception as e:
            logger.error(f"Failed to get churn risk customers: {e}")
            return []