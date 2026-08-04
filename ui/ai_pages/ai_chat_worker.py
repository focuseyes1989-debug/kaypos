# ui/ai_pages/ai_chat_worker.py
"""
Query worker thread for AI Chat Room with caching
"""

import re
from PyQt6.QtCore import QThread, pyqtSignal
from ui.ai_pages.ai_query_handlers import QueryHandlers
from ui.ai_pages.ai_cache import _query_cache
from loguru import logger


class QueryWorker(QThread):
    """Background thread for database queries with caching"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, query, query_type="general"):
        super().__init__()
        self.query = query
        self.query_type = query_type
        self._is_running = True
        
        # Set cache for query handlers
        QueryHandlers.set_cache(_query_cache)
    
    def stop(self):
        self._is_running = False
    
    def run(self):
        try:
            self.progress.emit(10)
            result = self._process_query()
            self.progress.emit(100)
            self.finished.emit(result)
            
            # Log cache stats after query
            stats = _query_cache.get_stats()
            logger.debug(f"Cache stats: {stats}")
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _process_query(self):
        """Process the query and return results"""
        query_lower = self.query.lower().strip()
        result = {
            'type': 'response',
            'data': [],
            'message': '',
            'sql': ''
        }
        
        # ============================================================
        # ✅ DETECT LANGUAGE
        # ============================================================
        is_myanmar = self._is_myanmar_query(query_lower)
        
        # ============================================================
        # ✅ PRODUCT DETAIL QUERIES (Barcode, SKU, or Name)
        # ============================================================
        is_barcode = re.match(r'^[0-9]{8,13}$', query_lower)
        is_sku = re.match(r'^[A-Za-z0-9\-_]{3,20}$', query_lower) and not is_barcode
        is_single_word = len(query_lower.split()) <= 2 and not is_barcode and not is_sku
        
        if is_barcode or is_sku or (is_single_word and len(query_lower) >= 3):
            known_patterns = self._get_known_patterns(is_myanmar)
            is_known_pattern = any(p in query_lower for p in known_patterns)
            
            if not is_known_pattern:
                result = QueryHandlers.get_product_details(self.query)
                if result and result.get('data'):
                    return result
        
        # ============================================================
        # ✅ DEBT/CREDIT QUERIES - FIXED KEYWORDS
        # ============================================================
        
        # 🔥 FIX: Check for debt summary queries FIRST
        # English: debt summary, debt, credit summary
        # Myanmar: အကြွေးစာရင်း, အကြွေး, ချေးငွေ, အကြွေးအကျဉ်းချုပ်
        
        debt_summary_keywords = [
            'debt summary', 'debt overview', 'credit summary', 
            'အကြွေးစာရင်း', 'အကြွေး', 'ချေးငွေ', 
            'အကြွေးအကျဉ်းချုပ်', 'debt'
        ]
        
        # Check if it's a debt summary query (single keyword or contains summary)
        is_debt_summary = False
        for kw in debt_summary_keywords:
            if kw in query_lower:
                is_debt_summary = True
                break
        
        # Also check if query is exactly "အကြွေးစာရင်း" or similar
        if query_lower in ['အကြွေးစာရင်း', 'အကြွေး', 'ချေးငွေ', 'debt', 'debt summary']:
            is_debt_summary = True
        
        if is_debt_summary:
            result = QueryHandlers.get_debt_summary()
            return result
        
        # Customer Debt - with name extraction
        customer_debt_keywords = ['customer debt', 'debt customer', 'အကြွေး', 'debt']
        if any(kw in query_lower for kw in customer_debt_keywords) and not is_debt_summary:
            # Extract customer name
            customer_name = None
            
            # Try various patterns
            patterns = [
                r'(?:customer debt|debt customer|အကြွေး)\s+["\']?([^"\']+)["\']?',
                r'(["\']?[^"\']+["\']?)\s*(?:debt|အကြွေး)',
                r'(?:debt|အကြွေး)\s+(?:for|အတွက်)\s+["\']?([^"\']+)["\']?',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    potential_name = match.group(1).strip()
                    # Clean up
                    potential_name = potential_name.strip('"\'')
                    # Make sure it's not a keyword
                    if potential_name.lower() not in ['debt', 'အကြွေး', 'customer', 'ဖောက်သည်', 'summary', 'စာရင်း']:
                        customer_name = potential_name
                        break
            
            if customer_name:
                result = QueryHandlers.get_customer_debt(customer_name)
            else:
                # If no name found, show debt summary
                result = QueryHandlers.get_debt_summary()
            return result
        
        # Overdue Debts
        overdue_keywords = [
            'overdue', 'overdue debt', 'overdue debts', 
            'ကြာမြင့်', 'ကြာမြင့်အကြွေး', 'ကြာမြင့်အကြွေးများ',
            'late payment', 'နောက်ကျ', 'သတ်မှတ်ရက်ကျော်'
        ]
        if any(kw in query_lower for kw in overdue_keywords):
            result = QueryHandlers.get_overdue_debts()
            return result
        
        # Recent Debts
        recent_keywords = [
            'recent debt', 'recent debts', 
            'မကြာသေးမီအကြွေး', 'မကြာသေးမီအကြွေးများ',
            'နောက်ဆုံးအကြွေး', 'recent credit'
        ]
        if any(kw in query_lower for kw in recent_keywords):
            result = QueryHandlers.get_recent_debts()
            return result
        
        # ============================================================
        # ✅ LOW STOCK
        # ============================================================
        low_stock_keywords = ['low stock', 'low_stock', 'စတော့နည်း', 'စတော့ကျ', 'ပစ္စည်းနည်း']
        if any(kw in query_lower for kw in low_stock_keywords):
            result = QueryHandlers.get_low_stock_products()
        
        # ============================================================
        # ✅ SALES QUERIES
        # ============================================================
        elif self._is_sales_query(query_lower, is_myanmar):
            if self._contains_keywords(query_lower, ['today', 'ယနေ့', 'ဒီနေ့']):
                result = QueryHandlers.get_today_sales()
            elif self._contains_keywords(query_lower, ['yesterday', 'မနေ့က']):
                result = QueryHandlers.get_yesterday_sales()
            elif self._contains_keywords(query_lower, ['week', 'weekly', 'အပတ်', 'တစ်ပတ်']):
                result = QueryHandlers.get_weekly_sales()
            elif self._contains_keywords(query_lower, ['month', 'monthly', 'လ', 'တစ်လ']):
                result = QueryHandlers.get_monthly_sales()
            elif self._contains_keywords(query_lower, ['top', 'best', 'ထိပ်', 'အကောင်းဆုံး']):
                if self._contains_keywords(query_lower, ['product', 'ပစ္စည်း']):
                    result = QueryHandlers.get_top_products()
                else:
                    result = QueryHandlers.get_top_products()
            elif self._contains_keywords(query_lower, ['total', 'စုစုပေါင်း']):
                result = QueryHandlers.get_total_sales()
        
        # ============================================================
        # ✅ PRODUCTS QUERIES
        # ============================================================
        elif self._contains_keywords(query_lower, ['product', 'ပစ္စည်း']):
            if self._contains_keywords(query_lower, ['stock', 'စတော့']):
                result = QueryHandlers.get_stock_summary()
            elif self._contains_keywords(query_lower, ['search', 'find', 'ရှာ', 'ရှာဖွေ']):
                match = re.search(r'(?:search|find|ရှာ|ရှာဖွေ)\s+["\']?([^"\']+)["\']?', self.query, re.IGNORECASE)
                if match:
                    result = QueryHandlers.search_products(match.group(1).strip())
                else:
                    result = {
                        'type': 'response',
                        'data': [],
                        'message': 'Please specify what to search. Example: "search product Milk" / "ပစ္စည်းရှာ နို့"',
                        'sql': ''
                    }
            else:
                result = QueryHandlers.get_stock_summary()
        
        # ============================================================
        # ✅ CUSTOMERS QUERIES
        # ============================================================
        elif self._contains_keywords(query_lower, ['customer', 'ဖောက်သည်', 'ဝယ်သူ']):
            if self._contains_keywords(query_lower, ['top', 'ထိပ်']):
                result = QueryHandlers.get_top_customers()
            elif self._contains_keywords(query_lower, ['total', 'stat', 'စုစုပေါင်း', 'စာရင်းအင်း']):
                result = QueryHandlers.get_customer_stats()
        
        # ============================================================
        # ✅ EXPENSES QUERIES
        # ============================================================
        elif self._contains_keywords(query_lower, ['expense', 'ကုန်ကျ', 'အသုံး', 'သုံးစွဲ']):
            if self._contains_keywords(query_lower, ['today', 'ယနေ့', 'ဒီနေ့']):
                result = QueryHandlers.get_today_expenses()
            elif self._contains_keywords(query_lower, ['month', 'monthly', 'လ', 'တစ်လ']):
                result = QueryHandlers.get_monthly_expenses()
            elif self._contains_keywords(query_lower, ['total', 'စုစုပေါင်း']):
                result = QueryHandlers.get_total_expenses()
        
        # ============================================================
        # ✅ PROFIT QUERIES
        # ============================================================
        elif self._contains_keywords(query_lower, ['profit', 'အမြတ်']):
            result = QueryHandlers.get_profit_summary()
        
        # ============================================================
        # ✅ STOCK QUERIES
        # ============================================================
        elif self._contains_keywords(query_lower, ['stock', 'စတော့']):
            if self._contains_keywords(query_lower, ['low', 'နည်း', 'ကျ']):
                result = QueryHandlers.get_low_stock_products()
            else:
                result = QueryHandlers.get_stock_summary()
        
        # ============================================================
        # ✅ HELP / GENERAL
        # ============================================================
        elif self._contains_keywords(query_lower, ['help', '?', 'guide', 'အကူ', 'လမ်းညွှန်']):
            help_text = QueryHandlers.get_help_text_myanmar() if is_myanmar else QueryHandlers.get_help_text()
            result = {
                'type': 'response',
                'data': [],
                'message': help_text,
                'sql': ''
            }
        
        # ============================================================
        # ✅ DEFAULT / UNKNOWN
        # ============================================================
        else:
            # Try product detail one more time
            if len(query_lower) >= 2:
                result = QueryHandlers.get_product_details(self.query)
                if result and result.get('data'):
                    return result
            
            if is_myanmar:
                result['message'] = "❌ နားမလည်ပါ။ ကျေးဇူးပြု၍ အောက်ပါမေးခွန်းများကို မေးမြန်းပါ:\n\n" + QueryHandlers.get_help_text_myanmar()
            else:
                result['message'] = "❌ I don't understand. Please ask one of these questions:\n\n" + QueryHandlers.get_help_text()
        
        return result
    
    # ============================================================
    # ✅ HELPER METHODS
    # ============================================================
    
    def _is_myanmar_query(self, text):
        """Check if query contains Myanmar Unicode characters"""
        myanmar_pattern = re.compile(r'[\u1000-\u109F]')
        return bool(myanmar_pattern.search(text))
    
    def _get_known_patterns(self, is_myanmar):
        """Get known query patterns based on language"""
        if is_myanmar:
            return [
                'ယနေ့', 'ဒီနေ့', 'မနေ့က', 'အပတ်', 'တစ်ပတ်', 'လ', 'တစ်လ',
                'ထိပ်', 'အကောင်းဆုံး', 'စုစုပေါင်း', 'စတော့နည်း', 'စတော့ကျ',
                'ပစ္စည်းနည်း', 'ရှာ', 'ရှာဖွေ', 'ဖောက်သည်', 'ဝယ်သူ',
                'ကုန်ကျ', 'အသုံး', 'သုံးစွဲ', 'အမြတ်', 'စတော့',
                'အကူ', 'လမ်းညွှန်', 'အကြွေး', 'ချေးငွေ', 'ကြာမြင့်',
                'အကြွေးစာရင်း', 'ကြာမြင့်အကြွေး'
            ]
        else:
            return [
                'today', 'yesterday', 'weekly', 'monthly', 'total',
                'top', 'best', 'low stock', 'stock', 'search', 'find',
                'customer', 'expense', 'profit', 'help', 'debt', 'overdue',
                'debt summary', 'credit'
            ]
    
    def _contains_keywords(self, text, keywords):
        """Check if text contains any of the keywords"""
        return any(kw in text for kw in keywords)
    
    def _is_sales_query(self, text, is_myanmar):
        """Check if query is about sales"""
        sales_keywords = ['sale', 'sales', 'ရောင်း', 'ရောင်းအား']
        return any(kw in text for kw in sales_keywords)