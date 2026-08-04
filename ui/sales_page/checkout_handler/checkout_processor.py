# ui/sales_page/checkout_handler/checkout_processor.py
from datetime import datetime, timedelta
from models.database import connect_db
from services.credit_service import CreditService
from loguru import logger


class CheckoutProcessor:
    """Process checkout operations"""
    
    def __init__(self, parent, handler):
        self.parent = parent
        self.handler = handler
    
    def create_sale_record(self, cursor, invoice_no, grand_total, payment, change, 
                           payment_type, local_now, total_discount):
        """Create sale record in database"""
        cursor.execute("""
            INSERT INTO sales (invoice_no, total, payment, change_amount, customer_id, 
                              status, payment_type, created_at, discount_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (invoice_no, grand_total, payment, change, 
              self.handler.selected_customer_id, 'completed', 
              payment_type, local_now, total_discount))
        return cursor.lastrowid
    
    def create_sale_items(self, cursor, sale_id, cart):
        """Create sale items in database"""
        for item in cart:
            product_name = item["name"]
            discount_percent = float(item.get("expiry_discount_percent") or item.get("promo_discount_percent") or 0)
            if discount_percent > 0:
                source = "Expiry" if item.get("expiry_discount_enabled") else "Promo"
                product_name = f"{product_name} ({source} -{discount_percent:g}%)"
            allocations = item.get("stock_allocations") or [{
                "product_id": item.get("id"),
                "variant_id": item.get("variant_id"),
                "qty": item.get("qty", 0),
                "location_id": item.get("location_id"),
                "location": item.get("location") or "",
                "batch_no": item.get("batch_no") or "",
                "expire_date": item.get("expire_date") or "",
            }]
            for allocation in allocations:
                qty = int(allocation.get("qty") or 0)
                if qty <= 0:
                    continue
                total = item["price"] * qty
                try:
                    cursor.execute("""
                        INSERT INTO sale_items (
                            sale_id, product_id, product_name, qty, price, total,
                            variant_id, location_id, location, batch_no, expire_date
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sale_id,
                        allocation.get("product_id") or item.get("id"),
                        product_name,
                        qty,
                        item["price"],
                        total,
                        allocation.get("variant_id") or item.get("variant_id"),
                        allocation.get("location_id"),
                        allocation.get("location") or "",
                        allocation.get("batch_no") or "",
                        allocation.get("expire_date") or "",
                    ))
                except Exception:
                    cursor.execute("""
                        INSERT INTO sale_items (sale_id, product_name, qty, price, total)
                        VALUES (?, ?, ?, ?, ?)
                    """, (sale_id, product_name, qty, item["price"], total))
    
    def process_credit_sale(self, conn, cursor, invoice_no, grand_total, sale_id):
        """Process credit sale"""
        credit_service = CreditService()
        result = credit_service.create_credit_sale(
            customer_id=self.handler.selected_customer_id,
            invoice_no=invoice_no,
            total_amount=grand_total,
            paid_amount=0,
            sale_id=sale_id,
            notes="POS credit sale",
            cursor=cursor,
            conn=conn
        )
        
        if not result.get('success'):
            raise Exception(f"Failed to create credit sale: {result.get('error')}")
        
        due_date = result.get('due_date', '')
        balance_amount = result.get('balance_amount', grand_total)
        logger.info(f"Credit sale created: {invoice_no}, due: {due_date}, balance: {balance_amount}")
    
    def process_cash_sale(self, conn, cursor, grand_total, invoice_no):
        """Process cash sale with customer points"""
        if not self.handler.selected_customer_id:
            return
        
        # Earn points
        earned = int(grand_total * self.parent.totals_widget.points_per_dollar)
        if earned > 0:
            expiry_date = (datetime.now() + timedelta(
                days=self.parent.totals_widget.points_expiry_months * 30
            )).strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO customer_points_log (customer_id, points, type, reference, expiry_date)
                VALUES (?, ?, 'earn', ?, ?)
            """, (self.handler.selected_customer_id, earned, invoice_no, expiry_date))
            cursor.execute("UPDATE customers SET points = points + ? WHERE id = ?", 
                          (earned, self.handler.selected_customer_id))
        
        # Redeem points
        if self.parent.totals_widget.points_use_check.isChecked():
            points_used = self.parent.totals_widget.points_spin.value()
            if points_used > 0:
                cursor.execute("UPDATE customers SET points = points - ? WHERE id = ?", 
                              (points_used, self.handler.selected_customer_id))
                cursor.execute("""
                    INSERT INTO customer_points_log (customer_id, points, type, reference)
                    VALUES (?, ?, 'redeem', ?)
                """, (self.handler.selected_customer_id, points_used, invoice_no))
        
        # Update customer stats
        cursor.execute("""
            UPDATE customers
            SET total_visit = total_visit + 1,
                total_spent = total_spent + ?
            WHERE id = ?
        """, (grand_total, self.handler.selected_customer_id))
