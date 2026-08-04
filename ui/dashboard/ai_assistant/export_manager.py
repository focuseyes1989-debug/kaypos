# ui/dashboard/ai_assistant/export_manager.py
"""Export manager for AI reports"""

from datetime import datetime
import csv

from models.database import connect_db
from utils.currency import get_currency_symbol, format_money


def export_report(from_date, to_date, file_path):
    """Export detailed report to CSV"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            date(s.created_at) as date,
            COUNT(DISTINCT s.id) as orders,
            COALESCE(SUM(si.qty), 0) as items_sold,
            COALESCE(SUM(si.qty * si.price), 0) as gross_sales,
            COALESCE(SUM(s.discount_amount), 0) as total_discount,
            COALESCE(SUM(si.qty * si.price) - SUM(s.discount_amount), 0) as net_sales,
            COALESCE(s.payment_type, 'Other') as payment_type
        FROM sales s
        LEFT JOIN sale_items si ON s.id = si.sale_id
        WHERE s.status = 'completed' 
          AND date(s.created_at) BETWEEN ? AND ?
        GROUP BY date(s.created_at), s.payment_type
        ORDER BY date(s.created_at) DESC, s.payment_type
    """, (from_date, to_date))
    
    rows = cursor.fetchall()
    conn.close()
    
    symbol = get_currency_symbol()
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["AI ASSISTANT REPORT - UPGRADED"])
        writer.writerow([f"Period: {from_date} to {to_date}"])
        writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])
        writer.writerow(["Date", "Orders", "Items Sold", "Gross Sales", "Discount", "Net Sales", "Payment Type"])
        
        total_orders = 0
        total_items = 0
        total_gross = 0
        total_discount = 0
        total_net = 0
        
        for row in rows:
            date, orders, items, gross, discount, net, payment = row
            writer.writerow([date, orders, items, gross, discount, net, payment])
            total_orders += orders
            total_items += items
            total_gross += gross
            total_discount += discount
            total_net += net
        
        writer.writerow([])
        writer.writerow(["TOTAL", total_orders, total_items, total_gross, total_discount, total_net, ""])
        
        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow([f"Total Orders: {total_orders}"])
        writer.writerow([f"Total Items Sold: {total_items}"])
        writer.writerow([f"Total Gross Sales: {format_money(total_gross, symbol)}"])
        writer.writerow([f"Total Discount: {format_money(total_discount, symbol)}"])
        writer.writerow([f"Total Net Sales: {format_money(total_net, symbol)}"])
        
        if total_orders > 0:
            writer.writerow([f"Average Order Value: {format_money(total_net / total_orders, symbol)}"])
    
    return True