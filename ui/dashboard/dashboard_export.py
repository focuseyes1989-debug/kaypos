# ui/dashboard/dashboard_export.py
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from models.database import connect_db
from utils.currency import format_money
from utils.excel_exporter import ExcelExporter
from datetime import datetime
import csv


class DashboardExport:
    """Handle dashboard export functions"""
    
    @staticmethod
    def get_lang():
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    @staticmethod
    def get_currency_symbol():
        from utils.currency import get_currency_symbol
        return get_currency_symbol()
    
    @staticmethod
    def get_summary_data(from_date, to_date):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales WHERE date(created_at) BETWEEN ? AND ?", (from_date, to_date))
        gross_sales = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales WHERE status='refunded' AND date(created_at) BETWEEN ? AND ?", (from_date, to_date))
        refunds = cursor.fetchone()[0]
        net_sales = gross_sales - refunds
        cursor.execute("SELECT COALESCE(SUM(discount_amount), 0) FROM sales WHERE status='completed' AND date(created_at) BETWEEN ? AND ?", (from_date, to_date))
        discount_total = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
            FROM sale_items
            JOIN products ON sale_items.product_id = products.id OR (sale_items.product_id IS NULL AND sale_items.product_name = products.name)
            JOIN sales ON sale_items.sale_id = sales.id
            WHERE sales.status='completed' AND date(sales.created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        cogs = cursor.fetchone()[0]
        gross_profit = net_sales - cogs
        cursor.execute("SELECT COUNT(*) FROM products WHERE (sold_by IS NULL OR sold_by != 'Service') AND stock > 0 AND stock <= low_stock")
        low_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM products WHERE (sold_by IS NULL OR sold_by != 'Service') AND stock = 0")
        out_count = cursor.fetchone()[0]
        stock_alerts = low_count + out_count
        conn.close()
        return {
            'period': f"{from_date} to {to_date}",
            'gross_sales': gross_sales,
            'net_sales': net_sales,
            'gross_profit': gross_profit,
            'refunds': refunds,
            'discount': discount_total,
            'stock_alerts': stock_alerts
        }
    
    @staticmethod
    def get_table_data(from_date, to_date):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date(created_at) as sale_date,
                   COALESCE(SUM(total), 0) as daily_gross,
                   COALESCE(SUM(CASE WHEN status='refunded' THEN total ELSE 0 END), 0) as daily_refunds,
                   COALESCE(SUM(CASE WHEN status='completed' THEN discount_amount ELSE 0 END), 0) as daily_discount
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
            GROUP BY date(created_at)
            ORDER BY sale_date DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        table_data = []
        for row in rows:
            sale_date, daily_gross, daily_refunds, daily_discount = row
            daily_net = daily_gross - daily_refunds
            conn2 = connect_db()
            cursor2 = conn2.cursor()
            cursor2.execute("""
                SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
                FROM sale_items
                JOIN products ON sale_items.product_id = products.id OR (sale_items.product_id IS NULL AND sale_items.product_name = products.name)
                JOIN sales ON sale_items.sale_id = sales.id
                WHERE date(sales.created_at) = ? AND sales.status='completed'
            """, (sale_date,))
            daily_cogs = cursor2.fetchone()[0]
            conn2.close()
            daily_profit = daily_net - daily_cogs
            table_data.append({
                'date': sale_date,
                'gross_sales': daily_gross,
                'net_sales': daily_net,
                'gross_profit': daily_profit,
                'refunds': daily_refunds,
                'discount': daily_discount
            })
        conn.close()
        return table_data
    
    @staticmethod
    def export_summary(parent, from_date, to_date):
        file_path, _ = QFileDialog.getSaveFileName(
            parent, "Export Dashboard Summary", 
            f"dashboard_summary_{from_date}_to_{to_date}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        try:
            data = DashboardExport.get_summary_data(from_date, to_date)
            symbol = DashboardExport.get_currency_symbol()
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["=" * 50])
                writer.writerow(["DASHBOARD SUMMARY REPORT"])
                writer.writerow(["=" * 50])
                writer.writerow([])
                writer.writerow(["Report Period:", data['period']])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                writer.writerow(["METRIC", "AMOUNT"])
                writer.writerow(["-" * 50])
                writer.writerow(["Gross Sales", format_money(data['gross_sales'], symbol)])
                writer.writerow(["Net Sales", format_money(data['net_sales'], symbol)])
                writer.writerow(["Gross Profit", format_money(data['gross_profit'], symbol)])
                writer.writerow(["Refunds", format_money(data['refunds'], symbol)])
                writer.writerow(["Discount", format_money(data['discount'], symbol)])
                writer.writerow(["Stock Alerts", data['stock_alerts']])
                writer.writerow([])
                writer.writerow(["=" * 50])
                writer.writerow(["End of Report"])
            msg = f"Summary exported successfully to:\n{file_path}" if DashboardExport.get_lang() != "my" else f"အကျဉ်းချုပ် အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(parent, "Export Complete", msg)
        except Exception as e:
            QMessageBox.critical(parent, "Export Error", f"Failed to export summary: {e}")
    
    @staticmethod
    def export_table(parent, from_date, to_date):
        file_path, _ = QFileDialog.getSaveFileName(
            parent, "Export Dashboard Table", 
            f"dashboard_table_{from_date}_to_{to_date}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        try:
            table_data = DashboardExport.get_table_data(from_date, to_date)
            symbol = DashboardExport.get_currency_symbol()
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["=" * 80])
                writer.writerow(["DASHBOARD DETAIL REPORT"])
                writer.writerow(["=" * 80])
                writer.writerow([])
                writer.writerow(["Report Period:", f"{from_date} to {to_date}"])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                writer.writerow(["Date", "Gross Sales", "Net Sales", "Gross Profit", "Refunds", "Discount"])
                writer.writerow(["-" * 80])
                for row in table_data:
                    writer.writerow([
                        row['date'],
                        format_money(row['gross_sales'], symbol),
                        format_money(row['net_sales'], symbol),
                        format_money(row['gross_profit'], symbol),
                        format_money(row['refunds'], symbol),
                        format_money(row['discount'], symbol)
                    ])
                total_gross = sum(row['gross_sales'] for row in table_data)
                total_net = sum(row['net_sales'] for row in table_data)
                total_profit = sum(row['gross_profit'] for row in table_data)
                total_refunds = sum(row['refunds'] for row in table_data)
                total_discount = sum(row['discount'] for row in table_data)
                writer.writerow([])
                writer.writerow(["TOTAL", 
                               format_money(total_gross, symbol),
                               format_money(total_net, symbol),
                               format_money(total_profit, symbol),
                               format_money(total_refunds, symbol),
                               format_money(total_discount, symbol)])
                writer.writerow([])
                writer.writerow(["=" * 80])
                writer.writerow(["End of Report"])
            msg = f"Table exported successfully to:\n{file_path}" if DashboardExport.get_lang() != "my" else f"ဇယား အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(parent, "Export Complete", msg)
        except Exception as e:
            QMessageBox.critical(parent, "Export Error", f"Failed to export table: {e}")
