# ui/ai_pages/ai_query_handlers.py
"""
Optimized database query handlers for AI Chat Room
"""

from datetime import datetime, timedelta
from models.database import connect_db
from loguru import logger
import re


class QueryHandlers:
    """Optimized database query handlers with caching support"""
    
    # Use class variable for cache
    _cache = None
    
    @classmethod
    def set_cache(cls, cache_instance):
        """Set cache instance"""
        cls._cache = cache_instance
    
    @staticmethod
    def _get_cached_or_query(cache_key, query_func, *args, **kwargs):
        """Get from cache or execute query"""
        if QueryHandlers._cache:
            cached = QueryHandlers._cache.get(cache_key)
            if cached is not None:
                return cached
        
        result = query_func(*args, **kwargs)
        
        if QueryHandlers._cache and result:
            QueryHandlers._cache.set(cache_key, result)
        
        return result

    @staticmethod
    def parse_date_expression(text):
        """Parse common English/Myanmar date expressions into YYYY-MM-DD."""
        query = (text or "").strip()
        query_lower = query.lower()

        relative_dates = [
            (['မနေ့တစ်နေ့က', 'တစ်နေ့က', 'day before yesterday'], 2, 'Day Before Yesterday'),
            (['မနေ့က', 'yesterday'], 1, 'Yesterday'),
            (['ယနေ့', 'ဒီနေ့', 'today'], 0, 'Today'),
        ]
        for words, days_ago, label in relative_dates:
            if any(word in query_lower or word in query for word in words):
                target = datetime.now() - timedelta(days=days_ago)
                return target.strftime("%Y-%m-%d"), label

        patterns = [
            r'(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)',
            r'(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)',
        ]

        match = re.search(patterns[0], query)
        if match:
            day, month, year = map(int, match.groups())
            try:
                target = datetime(year, month, day)
                return target.strftime("%Y-%m-%d"), target.strftime("%d.%m.%Y")
            except ValueError:
                return None, None

        match = re.search(patterns[1], query)
        if match:
            year, month, day = map(int, match.groups())
            try:
                target = datetime(year, month, day)
                return target.strftime("%Y-%m-%d"), target.strftime("%Y-%m-%d")
            except ValueError:
                return None, None

        return None, None
    
    # ============================================================
    # ✅ DEBT/CREDIT QUERIES - Using credit_sales table
    # ============================================================
    
    @staticmethod
    def get_debt_summary():
        """
        Get debt/credit summary from credit_sales table
        """
        cache_key = "debt_summary"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            # Total outstanding debt
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_debts,
                    COALESCE(SUM(total_amount), 0) as total_amount,
                    COALESCE(SUM(paid_amount), 0) as total_paid,
                    COALESCE(SUM(balance_amount), 0) as outstanding
                FROM credit_sales
                WHERE status = 'pending'
            """)
            row = cursor.fetchone()
            
            # Get debt by customer
            cursor.execute("""
                SELECT 
                    c.name as customer_name,
                    COUNT(cs.id) as debt_count,
                    COALESCE(SUM(cs.total_amount), 0) as total_amount,
                    COALESCE(SUM(cs.paid_amount), 0) as total_paid,
                    COALESCE(SUM(cs.balance_amount), 0) as outstanding
                FROM credit_sales cs
                JOIN customers c ON cs.customer_id = c.id
                WHERE cs.status = 'pending'
                GROUP BY cs.customer_id
                ORDER BY outstanding DESC
                LIMIT 10
            """)
            
            customer_rows = cursor.fetchall()
            conn.close()
            
            if row and row[0] > 0:
                total_debts = row[0]
                total_amount = row[1] or 0
                total_paid = row[2] or 0
                outstanding = row[3] or 0
                
                message = f"💰 **Debt Summary**\n\n"
                message += f"• Total Debts: {total_debts} transactions\n"
                message += f"• Total Amount: {total_amount:,.0f} Ks\n"
                message += f"• Total Paid: {total_paid:,.0f} Ks\n"
                message += f"• **Outstanding: {outstanding:,.0f} Ks**\n"
                
                if customer_rows:
                    message += "\n📋 **Top 10 Customers with Debt:**\n"
                    for i, row_data in enumerate(customer_rows, 1):
                        name, count, total, paid, outstanding = row_data
                        message += f"  {i}. {name}: {outstanding:,.0f} Ks ({count} debts)\n"
                
                return {
                    'type': 'debt_summary',
                    'data': [{
                        'Total Debts': total_debts,
                        'Total Amount': f"{total_amount:,.0f}",
                        'Total Paid': f"{total_paid:,.0f}",
                        'Outstanding': f"{outstanding:,.0f}"
                    }],
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': '✅ No outstanding debts found.\n\nAll debts have been cleared! 🎉',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_customer_debt(customer_name):
        """
        Get debt details for a specific customer from credit_sales
        """
        search_name = (customer_name or "").strip()
        cache_key = f"customer_debt_{search_name.lower()}"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            # Get customer info
            cursor.execute("""
                SELECT id, name, phone, total_spent, current_balance, credit_limit
                FROM customers
                WHERE name LIKE ?
                LIMIT 1
            """, (f'%{search_name}%',))
            
            customer = cursor.fetchone()
            
            if not customer:
                conn.close()
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"❌ Customer not found: '{customer_name}'",
                    'sql': ''
                }
            
            customer_id = customer[0]
            display_customer_name = customer[1]
            phone = customer[2] or 'N/A'
            total_spent = customer[3] or 0
            current_balance = customer[4] or 0
            credit_limit = customer[5] or 0
            
            # Get credit sale details
            cursor.execute("""
                SELECT 
                    cs.id,
                    cs.invoice_no,
                    cs.sale_date,
                    cs.total_amount,
                    cs.paid_amount,
                    cs.balance_amount,
                    cs.due_date,
                    cs.status,
                    cs.notes
                FROM credit_sales cs
                WHERE cs.customer_id = ?
                ORDER BY cs.sale_date DESC
                LIMIT 20
            """, (customer_id,))
            
            credit_rows = cursor.fetchall()
            
            # Get summary
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_debts,
                    COALESCE(SUM(total_amount), 0) as total_amount,
                    COALESCE(SUM(paid_amount), 0) as total_paid,
                    COALESCE(SUM(balance_amount), 0) as outstanding
                FROM credit_sales
                WHERE customer_id = ?
                AND status = 'pending'
            """, (customer_id,))
            
            summary = cursor.fetchone()
            conn.close()
            
            total_debts = summary[0] if summary else 0
            total_amount = summary[1] if summary else 0
            total_paid = summary[2] if summary else 0
            outstanding = summary[3] if summary else 0
            
            # Check if overdue
            overdue_count = 0
            for row in credit_rows:
                if row[6] and row[7] == 'pending':  # due_date and status pending
                    try:
                        due_date = datetime.strptime(row[6], "%Y-%m-%d")
                        if due_date < datetime.now():
                            overdue_count += 1
                    except:
                        pass
            
            message = f"👤 **Customer: {customer_name}**\n"
            message += f"📞 Phone: {phone}\n"
            message += f"💳 Credit Limit: {credit_limit:,.0f} Ks\n"
            message += f"💰 Current Balance: {current_balance:,.0f} Ks\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"💰 **Debt Summary:**\n"
            message += f"• Total Debts: {total_debts}\n"
            message += f"• Total Amount: {total_amount:,.0f} Ks\n"
            message += f"• Total Paid: {total_paid:,.0f} Ks\n"
            message += f"• **Outstanding: {outstanding:,.0f} Ks**\n"
            
            if overdue_count > 0:
                message += f"⚠️ **{overdue_count} overdue debts!**\n"
            
            if credit_rows:
                message += "\n📋 **Recent Credit Sales:**\n"
                for row in credit_rows[:5]:
                    debt_id, invoice_no, sale_date, amount, paid, balance, due_date, status, notes = row
                    status_emoji = "✅" if status == 'paid' else "⏳"
                    if status == 'pending' and due_date:
                        try:
                            due = datetime.strptime(due_date, "%Y-%m-%d")
                            if due < datetime.now():
                                status_emoji = "🔴"  # Overdue
                        except:
                            pass
                    message += f"  {status_emoji} #{invoice_no}: {amount:,.0f} Ks"
                    if paid > 0:
                        message += f" (Paid: {paid:,.0f} Ks)"
                    message += f" | Balance: {balance:,.0f} Ks"
                    if due_date:
                        message += f" | Due: {due_date}"
                    message += "\n"
            
            data = [{
                'Customer': customer_name,
                'Phone': phone,
                'Credit Limit': f"{credit_limit:,.0f}",
                'Current Balance': f"{current_balance:,.0f}",
                'Total Debts': total_debts,
                'Total Amount': f"{total_amount:,.0f}",
                'Total Paid': f"{total_paid:,.0f}",
                'Outstanding': f"{outstanding:,.0f}",
                'Overdue': overdue_count
            }]
            
            return {
                'type': 'customer_debt',
                'data': data,
                'message': message,
                'sql': ''
            }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_overdue_debts():
        """
        Get overdue debts (past due date)
        """
        cache_key = "overdue_debts"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT 
                    c.name as customer_name,
                    c.phone,
                    cs.invoice_no,
                    cs.sale_date,
                    cs.total_amount,
                    cs.paid_amount,
                    cs.balance_amount,
                    cs.due_date,
                    cs.notes
                FROM credit_sales cs
                JOIN customers c ON cs.customer_id = c.id
                WHERE cs.status = 'pending'
                AND cs.due_date IS NOT NULL
                AND cs.due_date != ''
                AND cs.due_date < ?
                ORDER BY cs.due_date ASC
                LIMIT 20
            """, (today,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                total_outstanding = sum(row[6] for row in rows)
                
                message = f"⚠️ **Overdue Debts**\n\n"
                message += f"• {len(rows)} debts overdue\n"
                message += f"• Total Outstanding: {total_outstanding:,.0f} Ks\n\n"
                message += "📋 **Details:**\n"
                
                for i, row in enumerate(rows, 1):
                    name, phone, invoice_no, sale_date, amount, paid, balance, due_date, notes = row
                    # Calculate days overdue
                    days_overdue = 0
                    if due_date:
                        try:
                            due = datetime.strptime(due_date, "%Y-%m-%d")
                            days_overdue = (datetime.now() - due).days
                        except:
                            pass
                    message += f"  {i}. {name} - {balance:,.0f} Ks"
                    message += f" ({days_overdue} days overdue)"
                    message += f" | Invoice: #{invoice_no}"
                    if notes:
                        message += f" - {notes}"
                    message += "\n"
                
                data = [{
                    'Customer': r[0],
                    'Phone': r[1],
                    'Invoice': r[2],
                    'Date': r[3],
                    'Total': f"{r[4]:,.0f}",
                    'Paid': f"{r[5]:,.0f}",
                    'Balance': f"{r[6]:,.0f}",
                    'Due Date': r[7],
                    'Days Overdue': (datetime.now() - datetime.strptime(r[7], "%Y-%m-%d")).days if r[7] else 0
                } for r in rows]
                
                return {
                    'type': 'overdue_debts',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': '✅ No overdue debts found. All debts are within the payment period! 🎉',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_recent_debts(limit=10):
        """
        Get recent credit sales
        """
        cache_key = f"recent_debts_{limit}"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    c.name as customer_name,
                    cs.invoice_no,
                    cs.sale_date,
                    cs.total_amount,
                    cs.paid_amount,
                    cs.balance_amount,
                    cs.status,
                    cs.due_date
                FROM credit_sales cs
                JOIN customers c ON cs.customer_id = c.id
                ORDER BY cs.sale_date DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                message = f"📋 **Recent Credit Sales** (Last {len(rows)})\n\n"
                
                for i, row in enumerate(rows, 1):
                    name, invoice_no, sale_date, amount, paid, balance, status, due_date = row
                    status_emoji = "✅" if status == 'paid' else "⏳"
                    if status == 'pending' and due_date:
                        try:
                            due = datetime.strptime(due_date, "%Y-%m-%d")
                            if due < datetime.now():
                                status_emoji = "🔴"  # Overdue
                        except:
                            pass
                    message += f"  {i}. {status_emoji} {name} - {amount:,.0f} Ks"
                    if paid > 0:
                        message += f" (Paid: {paid:,.0f} Ks)"
                    message += f" | Balance: {balance:,.0f} Ks"
                    message += f" | #{invoice_no}"
                    if due_date:
                        message += f" | Due: {due_date}"
                    message += "\n"
                
                data = [{
                    'Customer': r[0],
                    'Invoice': r[1],
                    'Date': r[2],
                    'Total': f"{r[3]:,.0f}",
                    'Paid': f"{r[4]:,.0f}",
                    'Balance': f"{r[5]:,.0f}",
                    'Status': r[6],
                    'Due Date': r[7] or '-'
                } for r in rows]
                
                return {
                    'type': 'recent_debts',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': 'No credit sales found.',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    # ============================================================
    # ✅ HELP TEXT - Updated with Credit/Debt queries
    # ============================================================
    
    @staticmethod
    def get_help_text():
        """Get help text in English"""
        return """
🤖 **ZAY POS AI Assistant - Help**

**Sales Queries:**
• "today sales" - Show today's sales
• "yesterday sales" - Show yesterday's sales  
• "weekly sales" - Show weekly sales
• "monthly sales" - Show monthly sales
• "total sales" - Show total sales
• "top products" - Show best selling products

**Product Queries:**
• "low stock" - Show low stock products
• "stock summary" - Show stock overview
• "search [product]" - Search for a product
• **Barcode/SKU/Name** - Show product details

**Customer Queries:**
• "top customers" - Show top customers
• "customer stats" - Show customer statistics

**💳 Credit/Debt Queries:**
• "debt summary" - Show overall debt summary
• "customer debt [name]" - Show debt for a customer
• "overdue debts" - Show overdue debts
• "recent debts" - Show recent credit sales

**Expense Queries:**
• "today expenses" - Show today's expenses
• "monthly expenses" - Show monthly expenses
• "total expenses" - Show total expenses
• "recent expenses" - Show latest expense entries
• "expense category [name]" - Show category expense summary

**Profit Queries:**
• "profit" - Show profit summary

**Examples:**
• "today sales"
• "search milk"
• "customer debt John"
• "overdue debts"
• "debt summary"
"""
    
    @staticmethod
    def get_help_text_myanmar():
        """Get help text in Myanmar"""
        return """
🤖 **ZAY POS AI Assistant - အကူအညီ**

**ရောင်းအားဆိုင်ရာ မေးခွန်းများ:**
• "ယနေ့ရောင်းအား" - ဒီနေ့ရဲ့ ရောင်းအားကိုပြမယ်
• "မနေ့ကရောင်းအား" - မနေ့ကရဲ့ ရောင်းအားကိုပြမယ်
• "အပတ်စဉ်ရောင်းအား" - တစ်ပတ်စာ ရောင်းအားကိုပြမယ်
• "လစဉ်ရောင်းအား" - တစ်လစာ ရောင်းအားကိုပြမယ်
• "စုစုပေါင်းရောင်းအား" - စုစုပေါင်းရောင်းအားကိုပြမယ်
• "ထိပ်ဆုံးပစ္စည်းများ" - ရောင်းအားအကောင်းဆုံး ပစ္စည်းများကိုပြမယ်

**ပစ္စည်းဆိုင်ရာ မေးခွန်းများ:**
• "စတော့နည်းသောပစ္စည်းများ" - စတော့နည်းနေတဲ့ ပစ္စည်းများကိုပြမယ်
• "စတော့အကျဉ်းချုပ်" - စတော့အကျဉ်းချုပ်ကိုပြမယ်
• "ပစ္စည်းရှာ [အမည်]" - ပစ္စည်းကိုရှာမယ်

**ဖောက်သည်ဆိုင်ရာ မေးခွန်းများ:**
• "ထိပ်ဆုံးဖောက်သည်များ" - ထိပ်ဆုံးဖောက်သည်များကိုပြမယ်
• "ဖောက်သည်စာရင်းအင်း" - ဖောက်သည်စာရင်းအင်းကိုပြမယ်

**💳 အကြွေးဆိုင်ရာ မေးခွန်းများ:**
• "အကြွေးစာရင်း" - စုစုပေါင်းအကြွေးစာရင်းကိုပြမယ်
• "[အမည်] အကြွေး" - ဖောက်သည်တစ်ဦးချင်းစီရဲ့ အကြွေးကိုပြမယ်
• "ကြာမြင့်အကြွေးများ" - သတ်မှတ်ရက်ကျော်လွန် အကြွေးများကိုပြမယ်
• "မကြာသေးမီအကြွေးများ" - မကြာသေးမီ အကြွေးများကိုပြမယ်

**အသုံးစရိတ်ဆိုင်ရာ မေးခွန်းများ:**
• "ယနေ့အသုံးစရိတ်" - ဒီနေ့ရဲ့ အသုံးစရိတ်ကိုပြမယ်
• "လစဉ်အသုံးစရိတ်" - တစ်လစာ အသုံးစရိတ်ကိုပြမယ်
• "စုစုပေါင်းအသုံးစရိတ်" - စုစုပေါင်းအသုံးစရိတ်ကိုပြမယ်

**အမြတ်ဆိုင်ရာ မေးခွန်းများ:**
• "အမြတ်" - အမြတ်အကျဉ်းချုပ်ကိုပြမယ်

**ဥပမာများ:**
• "ယနေ့ရောင်းအား"
• "ပစ္စည်းရှာ နို့"
• "ကျော်ဦး အကြွေး"
• "ကြာမြင့်အကြွေးများ"
• "အကြွေးစာရင်း"
"""
    
    # ============================================================
    # ✅ PRODUCT DETAILS
    # ============================================================
    
    @staticmethod
    def get_product_details(search_term):
        """
        Get product details by barcode, SKU, or name
        """
        cache_key = f"product_detail_{search_term.lower().strip()}"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            search = search_term.strip()
            
            cursor.execute("""
                SELECT 
                    id,
                    name,
                    category,
                    description,
                    price,
                    cost,
                    stock,
                    sku,
                    barcode,
                    low_stock,
                    sold_by,
                    unit,
                    warehouse,
                    expire_date,
                    supplier_id
                FROM products 
                WHERE barcode = ?
                OR sku = ?
                OR name LIKE ?
                LIMIT 1
            """, (search, search, f'%{search}%'))
            
            row = cursor.fetchone()
            
            if not row:
                cursor.execute("""
                    SELECT 
                        id,
                        name,
                        category,
                        description,
                        price,
                        cost,
                        stock,
                        sku,
                        barcode,
                        low_stock,
                        sold_by,
                        unit,
                        warehouse,
                        expire_date,
                        supplier_id
                    FROM products 
                    WHERE name LIKE ?
                    OR sku LIKE ?
                    LIMIT 1
                """, (f'%{search}%', f'%{search}%'))
                row = cursor.fetchone()
            
            conn.close()
            
            if row:
                supplier_name = ""
                if row[14]:
                    try:
                        conn2 = connect_db()
                        cursor2 = conn2.cursor()
                        cursor2.execute("SELECT name FROM suppliers WHERE id = ?", (row[14],))
                        supplier_row = cursor2.fetchone()
                        if supplier_row:
                            supplier_name = supplier_row[0]
                        conn2.close()
                    except:
                        pass
                
                expiry_status = "✅ သက်တမ်းမကုန်သေး"
                expiry_color = "🟢"
                if row[13]:
                    from datetime import date
                    try:
                        exp_date = date.fromisoformat(row[13])
                        today = date.today()
                        if exp_date < today:
                            expiry_status = "❌ သက်တမ်းကုန်ဆုံးပြီ"
                            expiry_color = "🔴"
                        elif (exp_date - today).days <= 7:
                            expiry_status = f"⚠️ { (exp_date - today).days } ရက်အတွင်း သက်တမ်းကုန်မည်"
                            expiry_color = "🟡"
                        else:
                            expiry_status = f"✅ { (exp_date - today).days } ရက်ကျန်သေး"
                            expiry_color = "🟢"
                    except:
                        pass
                
                stock_status = "✅ လုံလောက်သည်"
                stock_color = "🟢"
                if row[6] <= 0:
                    stock_status = "❌ ကုန်သွားပြီ"
                    stock_color = "🔴"
                elif row[6] <= row[9]:
                    stock_status = f"⚠️ စတော့နည်းနေသည် (Min: {row[9]})"
                    stock_color = "🟡"
                
                message = f"""
📦 **Product Details**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 **{row[1]}**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 **Basic Info**
• ID: `{row[0]}`
• SKU: `{row[7] or '-'}`
• Barcode: `{row[8] or '-'}`
• Category: `{row[2] or '-'}`
• Sold By: `{row[10] or 'Each'}`

💰 **Pricing**
• Price: `{row[4]:,.0f} Ks`
• Cost: `{row[5]:,.0f} Ks`
• Profit: `{(row[4] - row[5]):,.0f} Ks`

📦 **Stock**
• Stock: `{row[6]}` {stock_color} {stock_status}
• Low Stock Alert: `{row[9]}`

📝 **Description**
{row[3] or 'No description available'}

🏷️ **Additional Info**
• Unit: `{row[11] or '-'}`
• Warehouse: `{row[12] or '-'}`
• Expiry Date: `{row[13] or 'No expiry'}` {expiry_color} {expiry_status}
• Supplier: `{supplier_name or 'N/A'}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                
                return {
                    'type': 'product_detail',
                    'data': [{
                        'ID': row[0],
                        'Name': row[1],
                        'Category': row[2],
                        'Price': f"{row[4]:,.0f}",
                        'Cost': f"{row[5]:,.0f}",
                        'Stock': row[6],
                        'SKU': row[7],
                        'Barcode': row[8],
                        'Low Stock': row[9],
                        'Sold By': row[10] or 'Each',
                        'Unit': row[11] or '-',
                        'Warehouse': row[12] or '-',
                        'Expiry': row[13] or '-',
                        'Supplier': supplier_name or 'N/A'
                    }],
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"❌ Product not found for: '{search_term}'\n\n"
                              f"Please check:\n"
                              f"• Barcode\n"
                              f"• SKU\n"
                              f"• Product name",
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    # ============================================================
    # ✅ SALES QUERIES
    # ============================================================
    
    @staticmethod
    def get_sales_by_date(date_str, label=None):
        """Get sales for a specific date."""
        cache_key = f"sales_by_date_{date_str}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(payment), 0) as total_payment,
                    COALESCE(ROUND(AVG(total), 0), 0) as avg_sale,
                    COALESCE(SUM(cogs), 0) as total_cogs,
                    COALESCE(SUM(gross_profit), 0) as total_profit
                FROM sales
                WHERE date(created_at) = ?
                AND status = 'completed'
            """, (date_str,))

            row = cursor.fetchone()
            conn.close()

            title = label or date_str
            if row and row[1] > 0:
                return {
                    'type': 'sales',
                    'data': [{
                        'Date': date_str,
                        'Transactions': row[0],
                        'Total Sales': f"{row[1]:,.0f}",
                        'Payment': f"{row[2]:,.0f}",
                        'Average': f"{row[3]:,.0f}",
                        'Profit': f"{row[5]:,.0f}"
                    }],
                    'message': f"📊 Sales ({title} - {date_str})\n\n"
                              f"• Transactions: {row[0]}\n"
                              f"• Total Sales: {row[1]:,.0f} Ks\n"
                              f"• Total Payment: {row[2]:,.0f} Ks\n"
                              f"• Average Sale: {row[3]:,.0f} Ks\n"
                              f"• Profit: {row[5]:,.0f} Ks",
                    'sql': ''
                }

            return {
                'type': 'response',
                'data': [],
                'message': f"📊 Sales ({title} - {date_str})\n\nNo sales recorded.",
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_daily_summary(date_str, label=None):
        """Get sales and expenses summary for a specific date."""
        cache_key = f"daily_summary_{date_str}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(gross_profit), 0) as total_profit
                FROM sales
                WHERE date(created_at) = ?
                AND status = 'completed'
            """, (date_str,))
            sales_row = cursor.fetchone()

            cursor.execute("""
                SELECT
                    COUNT(*) as expense_count,
                    COALESCE(SUM(amount), 0) as total_expenses
                FROM expenses
                WHERE date(expense_date) = ?
            """, (date_str,))
            expense_row = cursor.fetchone()

            cursor.execute("""
                SELECT category, COALESCE(SUM(amount), 0) as total
                FROM expenses
                WHERE date(expense_date) = ?
                GROUP BY category
                ORDER BY total DESC
                LIMIT 5
            """, (date_str,))
            expense_categories = cursor.fetchall()
            conn.close()

            transactions = sales_row[0] if sales_row else 0
            total_sales = sales_row[1] if sales_row else 0
            gross_profit = sales_row[2] if sales_row else 0
            expense_count = expense_row[0] if expense_row else 0
            total_expenses = expense_row[1] if expense_row else 0
            net_after_expenses = gross_profit - total_expenses
            title = label or date_str

            message = f"📅 Daily Summary ({title} - {date_str})\n\n"
            message += f"• Sales Transactions: {transactions}\n"
            message += f"• Total Sales: {total_sales:,.0f} Ks\n"
            message += f"• Gross Profit: {gross_profit:,.0f} Ks\n"
            message += f"• Expense Entries: {expense_count}\n"
            message += f"• Total Expenses: {total_expenses:,.0f} Ks\n"
            message += f"• Net After Expenses: {net_after_expenses:,.0f} Ks\n"

            if expense_categories:
                message += "\n💰 Expense Categories:\n"
                for category, total in expense_categories:
                    message += f"• {category}: {total:,.0f} Ks\n"

            if not transactions and not expense_count:
                message += "\nNo sales or expenses recorded for this date."

            return {
                'type': 'daily_summary',
                'data': [{
                    'Date': date_str,
                    'Sales Transactions': transactions,
                    'Total Sales': f"{total_sales:,.0f}",
                    'Gross Profit': f"{gross_profit:,.0f}",
                    'Expense Entries': expense_count,
                    'Total Expenses': f"{total_expenses:,.0f}",
                    'Net After Expenses': f"{net_after_expenses:,.0f}",
                }],
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_sales_summary_report(from_date, to_date, label=None, view="overview", limit=10):
        """Get Sales Summary page style reports for AI Chat."""
        safe_view = (view or "overview").strip().lower()
        cache_key = f"sales_summary_report_{safe_view}_{from_date}_{to_date}_{limit}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            title = label or f"{from_date} to {to_date}"

            def _format_sales_rows(rows, name_label):
                total_items = sum(row[1] or 0 for row in rows)
                total_gross = sum(row[2] or 0 for row in rows)
                total_net = sum(row[3] or 0 for row in rows)
                total_discount = sum(row[4] or 0 for row in rows)
                total_cogs = sum(row[5] or 0 for row in rows)
                total_profit = total_net - total_cogs

                message = f"📊 Sales Summary - {name_label} ({title})\n\n"
                for index, row in enumerate(rows[:limit], 1):
                    name, items, gross, net, discount, cogs = row
                    profit = (net or 0) - (cogs or 0)
                    message += f"{index}. {name}: {net:,.0f} Ks ({items} items, profit {profit:,.0f} Ks)\n"
                message += "\nTotals:\n"
                message += f"• Items Sold: {total_items}\n"
                message += f"• Gross Sales: {total_gross:,.0f} Ks\n"
                message += f"• Discount: {total_discount:,.0f} Ks\n"
                message += f"• Net Sales: {total_net:,.0f} Ks\n"
                message += f"• COGS: {total_cogs:,.0f} Ks\n"
                message += f"• Gross Profit: {total_profit:,.0f} Ks"

                data = [{
                    name_label: r[0],
                    'Items Sold': r[1],
                    'Gross Sales': f"{(r[2] or 0):,.0f}",
                    'Net Sales': f"{(r[3] or 0):,.0f}",
                    'Discount': f"{(r[4] or 0):,.0f}",
                    'COGS': f"{(r[5] or 0):,.0f}",
                    'Gross Profit': f"{((r[3] or 0) - (r[5] or 0)):,.0f}",
                } for r in rows]
                return data, message

            if safe_view in ["top", "top_items", "items", "item"]:
                cursor.execute("""
                    SELECT
                        si.product_name,
                        COALESCE(SUM(si.qty), 0) as items_sold,
                        COALESCE(SUM(si.price * si.qty), 0) as gross_sales,
                        COALESCE(SUM(si.total) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales,
                        COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as total_discount,
                        COALESCE(SUM(COALESCE(si.cost, 0) * si.qty), 0) as cogs
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    WHERE s.status = 'completed'
                      AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY si.product_name
                    ORDER BY net_sales DESC
                    LIMIT ?
                """, (from_date, to_date, limit))
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No sales items found for {title}.", 'sql': ''}
                data, message = _format_sales_rows(rows, "Product")
                return {'type': 'sales_summary', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["category", "categories"]:
                cursor.execute("""
                    SELECT
                        COALESCE(p.category, 'Uncategorized') as category,
                        COALESCE(SUM(si.qty), 0) as items_sold,
                        COALESCE(SUM(si.price * si.qty), 0) as gross_sales,
                        COALESCE(SUM(si.total) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales,
                        COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as total_discount,
                        COALESCE(SUM(COALESCE(p.cost, 0) * si.qty), 0) as cogs
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    LEFT JOIN products p ON si.product_name = p.name
                    WHERE s.status = 'completed'
                      AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY p.category
                    ORDER BY net_sales DESC
                """, (from_date, to_date))
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No category sales found for {title}.", 'sql': ''}
                data, message = _format_sales_rows(rows, "Category")
                return {'type': 'sales_summary', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["parent", "parent_category"]:
                cursor.execute("""
                    SELECT
                        COALESCE(pc.name, 'No Parent') as parent_name,
                        COALESCE(SUM(si.qty), 0) as items_sold,
                        COALESCE(SUM(si.price * si.qty), 0) as gross_sales,
                        COALESCE(SUM(si.total) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales,
                        COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as total_discount,
                        COALESCE(SUM(COALESCE(p.cost, 0) * si.qty), 0) as cogs
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    LEFT JOIN products p ON si.product_name = p.name
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN categories pc ON c.parent_id = pc.id
                    WHERE s.status = 'completed'
                      AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY pc.id, pc.name
                    ORDER BY net_sales DESC
                """, (from_date, to_date))
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No parent category sales found for {title}.", 'sql': ''}
                data, message = _format_sales_rows(rows, "Parent Category")
                return {'type': 'sales_summary', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["group", "category_group"]:
                cursor.execute("""
                    SELECT
                        COALESCE(cg.name, 'Uncategorized') as group_name,
                        COALESCE(SUM(si.qty), 0) as items_sold,
                        COALESCE(SUM(si.price * si.qty), 0) as gross_sales,
                        COALESCE(SUM(si.total) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales,
                        COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as total_discount,
                        COALESCE(SUM(COALESCE(p.cost, 0) * si.qty), 0) as cogs
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    LEFT JOIN products p ON si.product_name = p.name
                    LEFT JOIN categories c ON p.category = c.name
                    LEFT JOIN category_groups cg ON c.group_id = cg.id
                    WHERE s.status = 'completed'
                      AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY cg.id, cg.name
                    ORDER BY net_sales DESC
                """, (from_date, to_date))
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No category group sales found for {title}.", 'sql': ''}
                data, message = _format_sales_rows(rows, "Category Group")
                return {'type': 'sales_summary', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["payment", "payments", "payment_type"]:
                cursor.execute("""
                    SELECT
                        COALESCE(s.payment_type, 'Other') as payment_type,
                        COUNT(DISTINCT s.id) as transaction_count,
                        COALESCE(SUM(si.qty * si.price) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales
                    FROM sales s
                    JOIN sale_items si ON s.id = si.sale_id
                    WHERE s.status = 'completed'
                      AND date(s.created_at) BETWEEN ? AND ?
                    GROUP BY s.payment_type
                    ORDER BY net_sales DESC
                """, (from_date, to_date))
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No payment sales found for {title}.", 'sql': ''}
                total_count = sum(row[1] or 0 for row in rows)
                total_amount = sum(row[2] or 0 for row in rows)
                message = f"💳 Sales Summary - Payment Type ({title})\n\n"
                for index, row in enumerate(rows, 1):
                    payment_type, count, amount = row
                    pct = (amount / total_amount * 100) if total_amount else 0
                    message += f"{index}. {payment_type}: {amount:,.0f} Ks ({count} orders, {pct:.1f}%)\n"
                message += f"\nTotal Orders: {total_count}\nTotal Net Sales: {total_amount:,.0f} Ks"
                data = [{
                    'Payment Type': r[0],
                    'Orders': r[1],
                    'Net Sales': f"{(r[2] or 0):,.0f}",
                } for r in rows]
                return {'type': 'sales_summary', 'data': data, 'message': message, 'sql': ''}

            cursor.execute("""
                SELECT
                    COALESCE(SUM(si.total), 0) as total_sales_before_discount,
                    COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as total_discount
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'completed'
                  AND date(s.created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            row = cursor.fetchone()
            total_before_discount = row[0] if row else 0
            total_discount = row[1] if row else 0
            total_sales = total_before_discount - total_discount

            cursor.execute("""
                SELECT COUNT(*)
                FROM sales
                WHERE status = 'completed'
                  AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_orders = cursor.fetchone()[0]

            cursor.execute("""
                SELECT
                    COALESCE(p.category, 'Uncategorized') as category,
                    COALESCE(SUM(si.total) - SUM(COALESCE(s.discount_amount, 0)), 0) as net_sales
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                LEFT JOIN products p ON si.product_name = p.name
                WHERE s.status = 'completed'
                  AND date(s.created_at) BETWEEN ? AND ?
                GROUP BY p.category
                ORDER BY net_sales DESC
                LIMIT 1
            """, (from_date, to_date))
            top_category_row = cursor.fetchone()
            conn.close()

            avg_order = total_sales / total_orders if total_orders else 0
            top_category = top_category_row[0] if top_category_row else "N/A"
            message = f"📊 Sales Summary ({title})\n\n"
            message += f"• Total Net Sales: {total_sales:,.0f} Ks\n"
            message += f"• Total Orders: {total_orders}\n"
            message += f"• Average Order: {avg_order:,.0f} Ks\n"
            message += f"• Top Category: {top_category}\n"
            message += f"• Total Discount: {total_discount:,.0f} Ks"

            return {
                'type': 'sales_summary',
                'data': [{
                    'Period': title,
                    'From': from_date,
                    'To': to_date,
                    'Total Net Sales': f"{total_sales:,.0f}",
                    'Total Orders': total_orders,
                    'Average Order': f"{avg_order:,.0f}",
                    'Top Category': top_category,
                    'Total Discount': f"{total_discount:,.0f}",
                }],
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_receipts_report(from_date, to_date, label=None, view="overview", search_term="", limit=10):
        """Get Receipts page style reports for AI Chat."""
        safe_view = (view or "overview").strip().lower()
        search_term = (search_term or "").strip()
        cache_key = f"receipts_report_{safe_view}_{from_date}_{to_date}_{search_term.lower()}_{limit}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            title = label or f"{from_date} to {to_date}"
            search_like = f"%{search_term}%"

            def _sales_search_clause(alias="s"):
                if not search_term:
                    return "", []
                return f"""AND (
                    {alias}.invoice_no LIKE ?
                    OR LOWER(COALESCE({alias}.payment_type, '')) LIKE LOWER(?)
                    OR LOWER(COALESCE(c.name, '')) LIKE LOWER(?)
                )""", [search_like, search_like, search_like]

            if safe_view in ["receipt", "receipts", "recent", "list"]:
                clause, params = _sales_search_clause("s")
                cursor.execute(f"""
                    SELECT
                        s.id,
                        s.invoice_no,
                        s.created_at,
                        COALESCE(SUM(si.qty * si.price), s.total, 0) as total,
                        COALESCE(s.payment, 0) as payment,
                        COALESCE(s.change_amount, 0) as change_amount,
                        COALESCE(c.name, 'Walk-in') as customer_name,
                        COALESCE(s.payment_type, '-') as payment_type,
                        COALESCE(s.discount_amount, 0) as discount_amount
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    LEFT JOIN sale_items si ON s.id = si.sale_id
                    WHERE s.status = 'completed'
                      AND date(s.created_at) BETWEEN ? AND ?
                      {clause}
                    GROUP BY s.id
                    ORDER BY s.created_at DESC
                    LIMIT ?
                """, [from_date, to_date] + params + [limit])
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    search_text = f" matching '{search_term}'" if search_term else ""
                    return {'type': 'response', 'data': [], 'message': f"No receipts found{search_text} for {title}.", 'sql': ''}

                total_amount = sum(row[3] or 0 for row in rows)
                total_payment = sum(row[4] or 0 for row in rows)
                message = f"🧾 Receipts ({title})\n\n"
                for index, row in enumerate(rows, 1):
                    _id, invoice_no, created_at, total, payment, change_amount, customer_name, payment_type, discount = row
                    message += f"{index}. {invoice_no} | {str(created_at)[:16]} | {customer_name} | {total:,.0f} Ks ({payment_type})\n"
                message += f"\nShown Receipts: {len(rows)}\nShown Total: {total_amount:,.0f} Ks\nShown Payment: {total_payment:,.0f} Ks"
                data = [{
                    'Invoice': r[1],
                    'Date': str(r[2])[:16],
                    'Total': f"{(r[3] or 0):,.0f}",
                    'Payment': f"{(r[4] or 0):,.0f}",
                    'Change': f"{(r[5] or 0):,.0f}",
                    'Customer': r[6],
                    'Payment Type': r[7],
                    'Discount': f"{(r[8] or 0):,.0f}",
                } for r in rows]
                return {'type': 'receipts', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["detail", "invoice"]:
                if not search_term:
                    conn.close()
                    return {'type': 'response', 'data': [], 'message': 'Please provide an invoice number. Example: receipt INV-0001', 'sql': ''}
                cursor.execute("""
                    SELECT
                        s.id,
                        s.invoice_no,
                        s.created_at,
                        COALESCE(s.total, 0),
                        COALESCE(s.payment, 0),
                        COALESCE(s.change_amount, 0),
                        COALESCE(s.payment_type, '-'),
                        COALESCE(s.discount_amount, 0),
                        COALESCE(c.name, 'Walk-in')
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    WHERE s.invoice_no LIKE ?
                    ORDER BY s.created_at DESC
                    LIMIT 1
                """, (search_like,))
                sale = cursor.fetchone()
                if not sale:
                    conn.close()
                    return {'type': 'response', 'data': [], 'message': f"No receipt found for '{search_term}'.", 'sql': ''}
                sale_id, invoice_no, created_at, total, payment, change_amount, payment_type, discount, customer_name = sale
                cursor.execute("""
                    SELECT product_name, qty, price, total
                    FROM sale_items
                    WHERE sale_id = ?
                    ORDER BY id ASC
                """, (sale_id,))
                items = cursor.fetchall()
                conn.close()
                message = f"🧾 Receipt Detail: {invoice_no}\n\n"
                message += f"• Date: {created_at}\n"
                message += f"• Customer: {customer_name}\n"
                message += f"• Payment Type: {payment_type}\n"
                message += f"• Total: {total:,.0f} Ks\n"
                message += f"• Payment: {payment:,.0f} Ks\n"
                message += f"• Change: {change_amount:,.0f} Ks\n"
                message += f"• Discount: {discount:,.0f} Ks\n"
                if items:
                    message += "\nItems:\n"
                    for index, item in enumerate(items, 1):
                        name, qty, price, item_total = item
                        message += f"{index}. {name} x {qty} @ {price:,.0f} = {item_total:,.0f} Ks\n"
                data = [{
                    'Invoice': invoice_no,
                    'Date': str(created_at),
                    'Customer': customer_name,
                    'Payment Type': payment_type,
                    'Total': f"{total:,.0f}",
                    'Payment': f"{payment:,.0f}",
                    'Change': f"{change_amount:,.0f}",
                    'Discount': f"{discount:,.0f}",
                }]
                return {'type': 'receipt_detail', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["refund", "refunded"]:
                clause, params = _sales_search_clause("s")
                cursor.execute(f"""
                    SELECT
                        s.invoice_no,
                        s.created_at,
                        COALESCE(SUM(si.qty * si.price), s.total, 0) as total,
                        COALESCE(c.name, 'Walk-in') as customer_name,
                        COALESCE(s.payment_type, '-') as payment_type
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    LEFT JOIN sale_items si ON s.id = si.sale_id
                    WHERE s.status = 'refunded'
                      AND date(s.created_at) BETWEEN ? AND ?
                      {clause}
                    GROUP BY s.id
                    ORDER BY s.created_at DESC
                    LIMIT ?
                """, [from_date, to_date] + params + [limit])
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No refunded receipts found for {title}.", 'sql': ''}
                total_refund = sum(row[2] or 0 for row in rows)
                message = f"↩️ Refunded Receipts ({title})\n\n"
                for index, row in enumerate(rows, 1):
                    invoice_no, created_at, total, customer_name, payment_type = row
                    message += f"{index}. {invoice_no} | {str(created_at)[:16]} | {customer_name}: {total:,.0f} Ks ({payment_type})\n"
                message += f"\nTotal Refunded: {total_refund:,.0f} Ks"
                data = [{'Invoice': r[0], 'Date': str(r[1])[:16], 'Total': f"{(r[2] or 0):,.0f}", 'Customer': r[3], 'Payment Type': r[4]} for r in rows]
                return {'type': 'receipts', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["discount", "discounted"]:
                clause, params = _sales_search_clause("s")
                cursor.execute(f"""
                    SELECT
                        s.invoice_no,
                        s.created_at,
                        COALESCE(s.total, 0) as total,
                        COALESCE(s.discount_amount, 0) as discount_amount,
                        COALESCE(c.name, 'Walk-in') as customer_name,
                        COALESCE(s.payment_type, '-') as payment_type
                    FROM sales s
                    LEFT JOIN customers c ON s.customer_id = c.id
                    WHERE COALESCE(s.discount_amount, 0) > 0
                      AND date(s.created_at) BETWEEN ? AND ?
                      {clause}
                    ORDER BY s.created_at DESC
                    LIMIT ?
                """, [from_date, to_date] + params + [limit])
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No discounted receipts found for {title}.", 'sql': ''}
                total_discount = sum(row[3] or 0 for row in rows)
                message = f"🏷️ Discounted Receipts ({title})\n\n"
                for index, row in enumerate(rows, 1):
                    invoice_no, created_at, total, discount, customer_name, payment_type = row
                    message += f"{index}. {invoice_no} | {str(created_at)[:16]} | Discount {discount:,.0f} Ks | Total {total:,.0f} Ks\n"
                message += f"\nTotal Discount: {total_discount:,.0f} Ks"
                data = [{'Invoice': r[0], 'Date': str(r[1])[:16], 'Total': f"{(r[2] or 0):,.0f}", 'Discount': f"{(r[3] or 0):,.0f}", 'Customer': r[4], 'Payment Type': r[5]} for r in rows]
                return {'type': 'receipts', 'data': data, 'message': message, 'sql': ''}

            if safe_view in ["credit", "credits"]:
                cursor.execute("""
                    SELECT
                        cs.invoice_no,
                        cs.sale_date,
                        COALESCE(c.name, 'Unknown') as customer_name,
                        COALESCE(cs.total_amount, 0),
                        COALESCE(cs.paid_amount, 0),
                        COALESCE(cs.balance_amount, 0),
                        COALESCE(cs.status, '-')
                    FROM credit_sales cs
                    LEFT JOIN customers c ON cs.customer_id = c.id
                    WHERE date(cs.sale_date) BETWEEN ? AND ?
                    ORDER BY cs.sale_date DESC, cs.id DESC
                    LIMIT ?
                """, (from_date, to_date, limit))
                rows = cursor.fetchall()
                conn.close()
                if not rows:
                    return {'type': 'response', 'data': [], 'message': f"No credit receipts found for {title}.", 'sql': ''}
                total_credit = sum(row[3] or 0 for row in rows)
                total_balance = sum(row[5] or 0 for row in rows)
                message = f"💳 Credit Receipts ({title})\n\n"
                for index, row in enumerate(rows, 1):
                    invoice_no, sale_date, customer_name, total, paid, balance, status = row
                    message += f"{index}. {invoice_no} | {sale_date} | {customer_name}: {total:,.0f} Ks (Balance {balance:,.0f}, {status})\n"
                message += f"\nTotal Credit: {total_credit:,.0f} Ks\nOutstanding: {total_balance:,.0f} Ks"
                data = [{'Invoice': r[0], 'Date': r[1], 'Customer': r[2], 'Total': f"{(r[3] or 0):,.0f}", 'Paid': f"{(r[4] or 0):,.0f}", 'Balance': f"{(r[5] or 0):,.0f}", 'Status': r[6]} for r in rows]
                return {'type': 'receipts', 'data': data, 'message': message, 'sql': ''}

            cursor.execute("""
                SELECT COUNT(*)
                FROM sales
                WHERE status = 'completed'
                  AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_receipts = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(si.qty * si.price), 0)
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'completed'
                  AND date(s.created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_sales = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(discount_amount), 0)
                FROM sales
                WHERE status = 'completed'
                  AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_discount = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(total), 0)
                FROM sales
                WHERE status = 'refunded'
                  AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_refund = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0)
                FROM credit_sales
                WHERE date(sale_date) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_credit = cursor.fetchone()[0]
            conn.close()

            message = f"🧾 Receipts Summary ({title})\n\n"
            message += f"• Total Receipts: {total_receipts}\n"
            message += f"• Total Sales: {total_sales:,.0f} Ks\n"
            message += f"• Total Discount: {total_discount:,.0f} Ks\n"
            message += f"• Total Refund: {total_refund:,.0f} Ks\n"
            message += f"• Total Credit: {total_credit:,.0f} Ks"
            data = [{
                'Period': title,
                'From': from_date,
                'To': to_date,
                'Total Receipts': total_receipts,
                'Total Sales': f"{total_sales:,.0f}",
                'Total Discount': f"{total_discount:,.0f}",
                'Total Refund': f"{total_refund:,.0f}",
                'Total Credit': f"{total_credit:,.0f}",
            }]
            return {'type': 'receipts', 'data': data, 'message': message, 'sql': ''}

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_today_sales():
        """Get today's sales"""
        cache_key = "today_sales"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(payment), 0) as total_payment,
                    COALESCE(ROUND(AVG(total), 0), 0) as avg_sale,
                    COALESCE(SUM(cogs), 0) as total_cogs,
                    COALESCE(SUM(gross_profit), 0) as total_profit
                FROM sales 
                WHERE date(created_at) = ? 
                AND status = 'completed'
            """, (today,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[1] > 0:
                return {
                    'type': 'sales',
                    'data': [{
                        'Date': today,
                        'Transactions': row[0],
                        'Total Sales': f"{row[1]:,.0f}",
                        'Payment': f"{row[2]:,.0f}",
                        'Average': f"{row[3]:,.0f}",
                        'Profit': f"{row[5]:,.0f}"
                    }],
                    'message': f"📊 Today's Sales ({today})\n\n"
                              f"• Transactions: {row[0]}\n"
                              f"• Total Sales: {row[1]:,.0f} Ks\n"
                              f"• Profit: {row[5]:,.0f} Ks",
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"📊 Today's Sales ({today})\n\nNo sales recorded today.",
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_yesterday_sales():
        """Get yesterday's sales"""
        cache_key = "yesterday_sales"
        
        def _query():
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_transactions,
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(payment), 0) as total_payment
                FROM sales 
                WHERE date(created_at) = ?
                AND status = 'completed'
            """, (yesterday,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[1] > 0:
                return {
                    'type': 'sales',
                    'data': [{
                        'Date': yesterday,
                        'Transactions': row[0],
                        'Total Sales': f"{row[1]:,.0f}",
                        'Total Payment': f"{row[2]:,.0f}"
                    }],
                    'message': f"📊 Yesterday's Sales ({yesterday})\n\n"
                              f"• Transactions: {row[0]}\n"
                              f"• Total Sales: {row[1]:,.0f} Ks\n"
                              f"• Total Payment: {row[2]:,.0f} Ks",
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"📊 Yesterday's Sales ({yesterday})\n\nNo sales recorded.",
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_weekly_sales():
        """Get weekly sales"""
        cache_key = "weekly_sales"
        
        def _query():
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    date(created_at) as date,
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales
                FROM sales 
                WHERE date(created_at) BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY date(created_at)
                ORDER BY date(created_at) DESC
            """, (week_ago, today))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                total_sales = sum(row[2] for row in rows)
                total_transactions = sum(row[1] for row in rows)
                
                data = [{'Date': r[0], 'Transactions': r[1], 'Total Sales': f"{r[2]:,.0f}"} for r in rows]
                
                return {
                    'type': 'weekly_sales',
                    'data': data,
                    'message': f"📈 Weekly Sales ({week_ago} to {today})\n\n"
                              f"• Total Transactions: {total_transactions}\n"
                              f"• Total Sales: {total_sales:,.0f} Ks\n"
                              f"• Average Daily: {total_sales/7:,.0f} Ks",
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"📈 Weekly Sales ({week_ago} to {today})\n\nNo sales recorded.",
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_monthly_sales():
        """Get monthly sales"""
        cache_key = "monthly_sales"
        
        def _query():
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(payment), 0) as total_payment,
                    COALESCE(ROUND(AVG(total), 0), 0) as avg_sale
                FROM sales 
                WHERE date(created_at) BETWEEN ? AND ?
                AND status = 'completed'
            """, (month_ago, today))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[1] > 0:
                return {
                    'type': 'sales',
                    'data': [{
                        'Period': f"{month_ago} to {today}",
                        'Transactions': row[0],
                        'Total Sales': f"{row[1]:,.0f}",
                        'Total Payment': f"{row[2]:,.0f}",
                        'Avg Sale': f"{row[3]:,.0f}"
                    }],
                    'message': f"📊 Monthly Sales ({month_ago} to {today})\n\n"
                              f"• Transactions: {row[0]}\n"
                              f"• Total Sales: {row[1]:,.0f} Ks\n"
                              f"• Total Payment: {row[2]:,.0f} Ks\n"
                              f"• Average Sale: {row[3]:,.0f} Ks",
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"📊 Monthly Sales ({month_ago} to {today})\n\nNo sales recorded.",
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_total_sales():
        """Get total sales"""
        cache_key = "total_sales"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as total_sales
                FROM sales 
                WHERE status = 'completed'
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            return {
                'type': 'sales',
                'data': [{
                    'Total Transactions': row[0],
                    'Total Sales': f"{row[1]:,.0f}"
                }],
                'message': f"💰 Total Sales Summary\n\n"
                          f"• Total Transactions: {row[0]}\n"
                          f"• Total Sales: {row[1]:,.0f} Ks",
                'sql': ''
            }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_top_products(limit=5):
        """Get top selling products"""
        cache_key = f"top_products_{limit}"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    product_name,
                    SUM(qty) as total_qty,
                    SUM(si.total) as total_revenue,
                    COUNT(*) as sale_count
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'completed'
                GROUP BY product_name
                ORDER BY total_revenue DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                data = [{
                    'Product': r[0],
                    'Total Quantity': r[1],
                    'Revenue': f"{r[2]:,.0f}",
                    'Sales Count': r[3]
                } for r in rows]
                
                message = f"🏆 Top {limit} Selling Products\n\n"
                for i, row in enumerate(rows, 1):
                    message += f"{i}. {row[0]}: {row[1]} units - {row[2]:,.0f} Ks\n"
                
                return {
                    'type': 'top_products',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': 'No products found.',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_low_stock_products():
        """Get low stock products"""
        cache_key = "low_stock_products"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    name,
                    stock,
                    low_stock,
                    sku,
                    category
                FROM products 
                WHERE stock <= low_stock
                AND stock > 0
                AND (sold_by IS NULL OR sold_by != 'Service')
                ORDER BY stock ASC
                LIMIT 20
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                data = [{
                    'Product': r[0],
                    'Stock': r[1],
                    'Low Stock': r[2],
                    'SKU': r[3],
                    'Category': r[4]
                } for r in rows]
                
                message = f"⚠️ Low Stock Products ({len(rows)} items)\n\n"
                for row in rows:
                    message += f"• {row[0]}: {row[1]} units (Min: {row[2]})\n"
                
                return {
                    'type': 'low_stock',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': '✅ No low stock products found.',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_stock_summary():
        """Get stock summary"""
        cache_key = "stock_summary"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_products,
                    COALESCE(SUM(stock), 0) as total_stock,
                    COUNT(CASE WHEN stock = 0 THEN 1 END) as out_of_stock,
                    COUNT(CASE WHEN stock <= low_stock AND stock > 0 THEN 1 END) as low_stock
                FROM products 
                WHERE sold_by IS NULL OR sold_by != 'Service'
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            return {
                'type': 'response',
                'data': [],
                'message': f"📦 Stock Summary\n\n"
                          f"• Total Products: {row[0]}\n"
                          f"• Total Stock: {row[1]} units\n"
                          f"• Out of Stock: {row[2]}\n"
                          f"• Low Stock: {row[3]}",
                'sql': ''
            }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def search_products(search_term):
        """Search products"""
        cache_key = f"search_{search_term.lower()}"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    name,
                    price,
                    stock,
                    sku,
                    category
                FROM products 
                WHERE name LIKE ?
                OR sku LIKE ?
                OR barcode LIKE ?
                LIMIT 10
            """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                data = [{
                    'Product': r[0],
                    'Price': f"{r[1]:,.0f}",
                    'Stock': r[2],
                    'SKU': r[3],
                    'Category': r[4]
                } for r in rows]
                
                message = f"🔍 Search Results for '{search_term}'\n\n"
                for row in rows:
                    message += f"• {row[0]}: {row[1]:,.0f} Ks (Stock: {row[2]})\n"
                
                return {
                    'type': 'search_results',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f'No products found for "{search_term}"',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_top_customers(limit=5):
        """Get top customers"""
        cache_key = f"top_customers_{limit}"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    name,
                    total_spent,
                    total_visit,
                    points,
                    phone
                FROM customers 
                WHERE total_spent > 0
                ORDER BY total_spent DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                data = [{
                    'Name': r[0],
                    'Total Spent': f"{r[1]:,.0f}",
                    'Visits': r[2],
                    'Points': r[3],
                    'Phone': r[4]
                } for r in rows]
                
                message = f"👑 Top {limit} Customers\n\n"
                for i, row in enumerate(rows, 1):
                    message += f"{i}. {row[0]}: {row[1]:,.0f} Ks ({row[2]} visits)\n"
                
                return {
                    'type': 'top_customers',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': 'No customers found.',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_customer_stats():
        """Get customer statistics"""
        cache_key = "customer_stats"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_customers,
                    COALESCE(SUM(total_spent), 0) as total_spent,
                    COALESCE(ROUND(AVG(total_spent), 0), 0) as avg_spent,
                    COUNT(CASE WHEN points > 0 THEN 1 END) as has_points
                FROM customers
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            return {
                'type': 'response',
                'data': [],
                'message': f"👥 Customer Statistics\n\n"
                          f"• Total Customers: {row[0]}\n"
                          f"• Total Spent: {row[1]:,.0f} Ks\n"
                          f"• Average Spent: {row[2]:,.0f} Ks\n"
                          f"• Customers with Points: {row[3]}",
                'sql': ''
            }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def search_customers(search_term, limit=10):
        """Search customers by name, phone, email, or address."""
        search_term = (search_term or "").strip()
        cache_key = f"customer_search_{search_term.lower()}_{limit}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()

            if search_term:
                like_term = f"%{search_term}%"
                cursor.execute("""
                    SELECT
                        id,
                        name,
                        phone,
                        email,
                        address,
                        COALESCE(total_visit, 0),
                        COALESCE(total_spent, 0),
                        COALESCE(points, 0),
                        COALESCE(current_balance, 0),
                        COALESCE(credit_limit, 0)
                    FROM customers
                    WHERE name LIKE ?
                       OR phone LIKE ?
                       OR email LIKE ?
                       OR address LIKE ?
                    ORDER BY total_spent DESC, name ASC
                    LIMIT ?
                """, (like_term, like_term, like_term, like_term, limit))
            else:
                cursor.execute("""
                    SELECT
                        id,
                        name,
                        phone,
                        email,
                        address,
                        COALESCE(total_visit, 0),
                        COALESCE(total_spent, 0),
                        COALESCE(points, 0),
                        COALESCE(current_balance, 0),
                        COALESCE(credit_limit, 0)
                    FROM customers
                    ORDER BY total_spent DESC, name ASC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                label = f" for '{search_term}'" if search_term else ""
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"No customers found{label}.",
                    'sql': ''
                }

            data = []
            title = f"👥 Found {len(rows)} customers"
            if search_term:
                title += f" for '{search_term}'"
            message = f"{title}:\n\n"

            for index, row in enumerate(rows, 1):
                customer_id, name, phone, email, address, visits, spent, points, balance, credit_limit = row
                phone_text = phone or "No phone"
                balance_text = f" | Balance: {balance:,.0f} Ks" if balance else ""
                message += f"{index}. {name} - {phone_text} | Spent: {spent:,.0f} Ks{balance_text}\n"
                data.append({
                    'ID': customer_id,
                    'Name': name,
                    'Phone': phone or '',
                    'Email': email or '',
                    'Address': address or '',
                    'Visits': visits,
                    'Total Spent': f"{spent:,.0f}",
                    'Points': points,
                    'Current Balance': f"{balance:,.0f}",
                    'Credit Limit': f"{credit_limit:,.0f}",
                })

            return {
                'type': 'customer_search',
                'data': data,
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_customer_profile(search_term):
        """Get one customer's profile, sales summary, and credit summary."""
        search_term = (search_term or "").strip()
        cache_key = f"customer_profile_{search_term.lower()}"

        def _query():
            if not search_term:
                return QueryHandlers.get_customer_stats()

            conn = connect_db()
            cursor = conn.cursor()

            like_term = f"%{search_term}%"
            cursor.execute("""
                SELECT
                    id,
                    name,
                    phone,
                    email,
                    address,
                    COALESCE(total_visit, 0),
                    COALESCE(total_spent, 0),
                    COALESCE(points, 0),
                    COALESCE(current_balance, 0),
                    COALESCE(credit_limit, 0),
                    remarks,
                    created_at
                FROM customers
                WHERE name LIKE ?
                   OR phone LIKE ?
                   OR email LIKE ?
                ORDER BY
                    CASE WHEN name = ? THEN 0 ELSE 1 END,
                    total_spent DESC,
                    name ASC
                LIMIT 1
            """, (like_term, like_term, like_term, search_term))

            customer = cursor.fetchone()
            if not customer:
                conn.close()
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"No customer found for '{search_term}'.\n\nTry: search customer {search_term}",
                    'sql': ''
                }

            customer_id = customer[0]

            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as sales_total,
                    MAX(created_at) as last_sale
                FROM sales
                WHERE customer_id = ?
                  AND status = 'completed'
            """, (customer_id,))
            sales_row = cursor.fetchone()

            cursor.execute("""
                SELECT
                    COUNT(*) as debt_count,
                    COALESCE(SUM(total_amount), 0) as credit_total,
                    COALESCE(SUM(paid_amount), 0) as paid_total,
                    COALESCE(SUM(balance_amount), 0) as outstanding
                FROM credit_sales
                WHERE customer_id = ?
                  AND status = 'pending'
            """, (customer_id,))
            debt_row = cursor.fetchone()
            conn.close()

            (
                _id, name, phone, email, address, visits, spent, points,
                current_balance, credit_limit, remarks, created_at
            ) = customer
            transactions = sales_row[0] if sales_row else 0
            sales_total = sales_row[1] if sales_row else 0
            last_sale = sales_row[2] if sales_row else None
            debt_count = debt_row[0] if debt_row else 0
            credit_total = debt_row[1] if debt_row else 0
            paid_total = debt_row[2] if debt_row else 0
            outstanding = debt_row[3] if debt_row else 0
            available_credit = credit_limit - current_balance

            message = f"👤 **Customer: {name}**\n\n"
            message += f"• Phone: {phone or 'N/A'}\n"
            message += f"• Email: {email or 'N/A'}\n"
            message += f"• Address: {address or 'N/A'}\n"
            message += f"• Visits: {visits}\n"
            message += f"• Points: {points}\n"
            message += f"• Total Spent: {spent:,.0f} Ks\n"
            message += f"• Sales Transactions: {transactions}\n"
            if last_sale:
                message += f"• Last Sale: {last_sale}\n"
            message += "\n💳 **Credit**\n"
            message += f"• Credit Limit: {credit_limit:,.0f} Ks\n"
            message += f"• Current Balance: {current_balance:,.0f} Ks\n"
            message += f"• Available Credit: {available_credit:,.0f} Ks\n"
            message += f"• Pending Debts: {debt_count}\n"
            message += f"• Outstanding: {outstanding:,.0f} Ks\n"
            if remarks:
                message += f"\n📝 Notes: {remarks}\n"

            return {
                'type': 'customer_profile',
                'data': [{
                    'ID': _id,
                    'Name': name,
                    'Phone': phone or '',
                    'Email': email or '',
                    'Address': address or '',
                    'Visits': visits,
                    'Points': points,
                    'Total Spent': f"{spent:,.0f}",
                    'Sales Total': f"{sales_total:,.0f}",
                    'Transactions': transactions,
                    'Last Sale': last_sale or '',
                    'Credit Limit': f"{credit_limit:,.0f}",
                    'Current Balance': f"{current_balance:,.0f}",
                    'Available Credit': f"{available_credit:,.0f}",
                    'Credit Total': f"{credit_total:,.0f}",
                    'Paid Total': f"{paid_total:,.0f}",
                    'Outstanding': f"{outstanding:,.0f}",
                    'Created At': created_at or '',
                }],
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_expenses_by_date(date_str, label=None):
        """Get expenses for a specific date."""
        cache_key = f"expenses_by_date_{date_str}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    category,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total
                FROM expenses
                WHERE date(expense_date) = ?
                GROUP BY category
                ORDER BY total DESC
            """, (date_str,))

            rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    expense_date,
                    category,
                    description,
                    amount,
                    payment_method,
                    reference_no
                FROM expenses
                WHERE date(expense_date) = ?
                ORDER BY id DESC
                LIMIT 10
            """, (date_str,))
            recent_rows = cursor.fetchall()
            conn.close()

            title = label or date_str
            if rows:
                total = sum(row[2] for row in rows)
                data = [{'Category': r[0], 'Amount': f"{r[2]:,.0f}", 'Count': r[1]} for r in rows]

                message = f"💰 Expenses ({title} - {date_str})\n\n"
                for row in rows:
                    message += f"• {row[0]}: {row[2]:,.0f} Ks ({row[1]} items)\n"
                message += f"\nTotal: {total:,.0f} Ks"

                if recent_rows:
                    message += "\n\n🧾 Entries:\n"
                    for index, row in enumerate(recent_rows, 1):
                        date, category, description, amount, payment_method, reference = row
                        detail = f" - {description}" if description else ""
                        payment = f" ({payment_method})" if payment_method else ""
                        message += f"{index}. {category}{detail}: {(amount or 0):,.0f} Ks{payment}\n"

                return {
                    'type': 'expenses',
                    'data': data,
                    'message': message,
                    'sql': ''
                }

            return {
                'type': 'response',
                'data': [],
                'message': f"💰 Expenses ({title} - {date_str})\n\nNo expenses recorded.",
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_expenses_by_category_and_date(category_name, date_str, label=None, limit=10):
        """Get expenses for a category on a specific date."""
        category_name = (category_name or "").strip()
        cache_key = f"expenses_category_date_{category_name.lower()}_{date_str}_{limit}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            like_term = f"%{category_name}%"

            cursor.execute("""
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as average_amount
                FROM expenses
                WHERE category LIKE ?
                  AND date(expense_date) = ?
            """, (like_term, date_str))
            summary = cursor.fetchone()

            cursor.execute("""
                SELECT
                    expense_date,
                    category,
                    description,
                    amount,
                    payment_method,
                    reference_no
                FROM expenses
                WHERE category LIKE ?
                  AND date(expense_date) = ?
                ORDER BY id DESC
                LIMIT ?
            """, (like_term, date_str, limit))
            rows = cursor.fetchall()
            conn.close()

            title = label or date_str
            count = summary[0] if summary else 0
            total = summary[1] if summary else 0
            average_amount = summary[2] if summary else 0

            if not count:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"💸 Expense Category: {category_name} ({title} - {date_str})\n\nNo expenses recorded.",
                    'sql': ''
                }

            message = f"💸 Expense Category: {category_name} ({title} - {date_str})\n\n"
            message += f"• Entries: {count}\n"
            message += f"• Total: {total:,.0f} Ks\n"
            message += f"• Average: {average_amount:,.0f} Ks\n"
            if rows:
                message += "\n🧾 Entries:\n"
                for index, row in enumerate(rows, 1):
                    _date, category, description, amount, payment_method, reference = row
                    detail = f" - {description}" if description else ""
                    payment = f" ({payment_method})" if payment_method else ""
                    message += f"{index}. {category}{detail}: {(amount or 0):,.0f} Ks{payment}\n"

            return {
                'type': 'expenses',
                'data': [{
                    'Category': category_name,
                    'Date': date_str,
                    'Entries': count,
                    'Total': f"{total:,.0f}",
                    'Average': f"{average_amount:,.0f}",
                }],
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_today_expenses():
        """Get today's expenses"""
        cache_key = "today_expenses"
        
        def _query():
            today = datetime.now().strftime("%Y-%m-%d")
            
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total
                FROM expenses 
                WHERE date(expense_date) = ?
                GROUP BY category
                ORDER BY total DESC
            """, (today,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                total = sum(row[2] for row in rows)
                data = [{'Category': r[0], 'Amount': f"{r[2]:,.0f}", 'Count': r[1]} for r in rows]
                
                message = f"💰 Today's Expenses ({today})\n\n"
                for row in rows:
                    message += f"• {row[0]}: {row[2]:,.0f} Ks ({row[1]} items)\n"
                message += f"\nTotal: {total:,.0f} Ks"
                
                return {
                    'type': 'expenses',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f'No expenses recorded today.',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_monthly_expenses():
        """Get monthly expenses"""
        cache_key = "monthly_expenses"
        
        def _query():
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total
                FROM expenses 
                WHERE date(expense_date) BETWEEN ? AND ?
                GROUP BY category
                ORDER BY total DESC
            """, (month_ago, today))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                total = sum(row[2] for row in rows)
                data = [{'Category': r[0], 'Amount': f"{r[2]:,.0f}", 'Count': r[1]} for r in rows]
                
                message = f"📊 Monthly Expenses ({month_ago} to {today})\n\n"
                for row in rows:
                    message += f"• {row[0]}: {row[2]:,.0f} Ks ({row[1]} items)\n"
                message += f"\nTotal: {total:,.0f} Ks"
                
                return {
                    'type': 'expenses',
                    'data': data,
                    'message': message,
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': 'No expenses recorded in the last 30 days.',
                    'sql': ''
                }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
    
    @staticmethod
    def get_total_expenses():
        """Get total expenses"""
        cache_key = "total_expenses"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_expenses,
                    COALESCE(SUM(amount), 0) as total_amount
                FROM expenses
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            return {
                'type': 'response',
                'data': [],
                'message': f"💰 Total Expenses Summary\n\n"
                          f"• Total Expenses: {row[0]}\n"
                          f"• Total Amount: {row[1]:,.0f} Ks",
                'sql': ''
            }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_recent_expenses(limit=10):
        """Get recent expense entries."""
        cache_key = f"recent_expenses_{limit}"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    expense_date,
                    category,
                    description,
                    amount,
                    payment_method,
                    reference_no
                FROM expenses
                ORDER BY date(expense_date) DESC, id DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {
                    'type': 'response',
                    'data': [],
                    'message': 'No recent expenses found.',
                    'sql': ''
                }

            total = sum(row[3] or 0 for row in rows)
            data = [{
                'Date': r[0],
                'Category': r[1],
                'Description': r[2] or '',
                'Amount': f"{(r[3] or 0):,.0f}",
                'Payment': r[4] or '',
                'Reference': r[5] or '',
            } for r in rows]

            message = f"🧾 Recent Expenses ({len(rows)} entries)\n\n"
            for index, row in enumerate(rows, 1):
                date, category, description, amount, payment_method, reference = row
                detail = f" - {description}" if description else ""
                payment = f" ({payment_method})" if payment_method else ""
                message += f"{index}. {date} | {category}{detail}: {(amount or 0):,.0f} Ks{payment}\n"
            message += f"\nTotal shown: {total:,.0f} Ks"

            return {
                'type': 'expenses',
                'data': data,
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_expense_categories():
        """List expense categories with usage totals."""
        cache_key = "expense_categories"

        def _query():
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    ec.name,
                    ec.description,
                    COALESCE(COUNT(e.id), 0) as entry_count,
                    COALESCE(SUM(e.amount), 0) as total_amount
                FROM expense_categories ec
                LEFT JOIN expenses e ON e.category = ec.name
                WHERE COALESCE(ec.is_active, 1) = 1
                GROUP BY ec.id, ec.name, ec.description
                ORDER BY total_amount DESC, ec.name ASC
            """)
            rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    e.category,
                    '' as description,
                    COUNT(e.id) as entry_count,
                    COALESCE(SUM(e.amount), 0) as total_amount
                FROM expenses e
                LEFT JOIN expense_categories ec ON ec.name = e.category
                WHERE ec.id IS NULL
                GROUP BY e.category
                ORDER BY total_amount DESC, e.category ASC
            """)
            uncategorized_rows = cursor.fetchall()
            conn.close()

            all_rows = list(rows) + list(uncategorized_rows)
            if not all_rows:
                return {
                    'type': 'response',
                    'data': [],
                    'message': 'No expense categories found.',
                    'sql': ''
                }

            total_amount = sum(row[3] or 0 for row in all_rows)
            message = f"💰 Expense Categories ({len(all_rows)})\n\n"
            for index, row in enumerate(all_rows, 1):
                name, description, count, total = row
                desc = f" - {description}" if description else ""
                message += f"{index}. {name}{desc}: {total:,.0f} Ks ({count} entries)\n"
            message += f"\nTotal Expenses: {total_amount:,.0f} Ks\n"
            message += "\nTip: Type a category name directly, e.g. ဈေးဖိုး"

            data = [{
                'Category': r[0],
                'Description': r[1] or '',
                'Entries': r[2],
                'Total': f"{(r[3] or 0):,.0f}",
            } for r in all_rows]

            return {
                'type': 'expense_categories',
                'data': data,
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def get_expenses_by_category(category_name, limit=10):
        """Get expense summary and recent entries for a category."""
        category_name = (category_name or "").strip()
        cache_key = f"expenses_category_{category_name.lower()}_{limit}"

        def _query():
            if not category_name:
                return QueryHandlers.get_total_expenses()

            conn = connect_db()
            cursor = conn.cursor()

            like_term = f"%{category_name}%"
            cursor.execute("""
                SELECT
                    category,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as average_amount,
                    MIN(expense_date) as first_date,
                    MAX(expense_date) as last_date
                FROM expenses
                WHERE category LIKE ?
                GROUP BY category
                ORDER BY total DESC
            """, (like_term,))
            summary_rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    expense_date,
                    category,
                    description,
                    amount,
                    payment_method,
                    reference_no
                FROM expenses
                WHERE category LIKE ?
                ORDER BY date(expense_date) DESC, id DESC
                LIMIT ?
            """, (like_term, limit))
            recent_rows = cursor.fetchall()
            conn.close()

            if not summary_rows:
                cursor = None
                conn = connect_db()
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT name, description
                        FROM expense_categories
                        WHERE name LIKE ?
                        ORDER BY LENGTH(name) ASC
                        LIMIT 1
                    """, (like_term,))
                    category_row = cursor.fetchone()
                finally:
                    conn.close()

                if category_row:
                    name, description = category_row
                    desc = f"\n• Description: {description}" if description else ""
                    return {
                        'type': 'expenses',
                        'data': [{
                            'Category': name,
                            'Description': description or '',
                            'Count': 0,
                            'Total': '0',
                            'Average': '0',
                            'First Date': '',
                            'Last Date': '',
                        }],
                        'message': f"💸 Expense Category: {name}\n\n• Entries: 0\n• Total: 0 Ks{desc}\n\nNo expenses recorded for this category yet.",
                        'sql': ''
                    }

                return {
                    'type': 'response',
                    'data': [],
                    'message': f"No expenses found for category '{category_name}'.",
                    'sql': ''
                }

            grand_total = sum(row[2] or 0 for row in summary_rows)
            message = f"💸 Expense Category: {category_name}\n\n"
            for row in summary_rows:
                category, count, total, average_amount, first_date, last_date = row
                message += f"• {category}: {total:,.0f} Ks ({count} entries, avg {average_amount:,.0f} Ks)\n"
                message += f"  Period: {first_date or 'N/A'} to {last_date or 'N/A'}\n"
            message += f"\nTotal: {grand_total:,.0f} Ks\n"

            if recent_rows:
                message += "\n🧾 Recent Entries:\n"
                for index, row in enumerate(recent_rows, 1):
                    date, category, description, amount, payment_method, reference = row
                    detail = f" - {description}" if description else ""
                    message += f"{index}. {date} | {category}{detail}: {(amount or 0):,.0f} Ks\n"

            data = [{
                'Category': r[0],
                'Count': r[1],
                'Total': f"{(r[2] or 0):,.0f}",
                'Average': f"{(r[3] or 0):,.0f}",
                'First Date': r[4] or '',
                'Last Date': r[5] or '',
            } for r in summary_rows]

            return {
                'type': 'expenses',
                'data': data,
                'message': message,
                'sql': ''
            }

        return QueryHandlers._get_cached_or_query(cache_key, _query)

    @staticmethod
    def find_expense_category(search_term):
        """Return the best matching expense category name, if one exists."""
        search_term = (search_term or "").strip()
        if not search_term:
            return None

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT name
                FROM expense_categories
                WHERE LOWER(name) = LOWER(?)
                LIMIT 1
            """, (search_term,))
            row = cursor.fetchone()
            if row:
                return row[0]

            cursor.execute("""
                SELECT category
                FROM expenses
                WHERE LOWER(category) = LOWER(?)
                GROUP BY category
                LIMIT 1
            """, (search_term,))
            row = cursor.fetchone()
            if row:
                return row[0]

            like_term = f"%{search_term}%"
            cursor.execute("""
                SELECT name
                FROM expense_categories
                WHERE name LIKE ?
                ORDER BY LENGTH(name) ASC
                LIMIT 1
            """, (like_term,))
            row = cursor.fetchone()
            if row:
                return row[0]

            cursor.execute("""
                SELECT category
                FROM expenses
                WHERE category LIKE ?
                GROUP BY category
                ORDER BY COUNT(*) DESC
                LIMIT 1
            """, (like_term,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    
    @staticmethod
    def get_profit_summary():
        """Get profit summary"""
        cache_key = "profit_summary"
        
        def _query():
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(cogs), 0) as total_cogs,
                    COALESCE(SUM(gross_profit), 0) as gross_profit
                FROM sales 
                WHERE status = 'completed'
            """)
            sales_row = cursor.fetchone()
            
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
            total_expenses = cursor.fetchone()[0]
            
            conn.close()
            
            total_sales = sales_row[0]
            total_cogs = sales_row[1]
            gross_profit = sales_row[2]
            net_profit = total_sales - total_expenses
            
            return {
                'type': 'response',
                'data': [],
                'message': f"📈 Profit Summary\n\n"
                          f"• Total Sales: {total_sales:,.0f} Ks\n"
                          f"• Total COGS: {total_cogs:,.0f} Ks\n"
                          f"• Gross Profit: {gross_profit:,.0f} Ks\n"
                          f"• Total Expenses: {total_expenses:,.0f} Ks\n"
                          f"• Net Profit: {net_profit:,.0f} Ks",
                'sql': ''
            }
        
        return QueryHandlers._get_cached_or_query(cache_key, _query)
