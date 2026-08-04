# ui/ai_pages/ai_nlp_processor.py
"""
Natural Language Processing for AI Chat
"""

import re
from typing import Dict, List, Tuple, Optional


class NLProcessor:
    """Natural Language Processing for queries"""
    
    # Intent patterns - English & Myanmar
    INTENT_PATTERNS = {
        # ============================================================
        # SALES INTENTS
        # ============================================================
        'sales_today': [
            r'(today|ယနေ့|ဒီနေ့).*(sales|ရောင်းအား)',
            r'(sales|ရောင်းအား).*(today|ယနေ့|ဒီနေ့)',
            r'^(today|ယနေ့|ဒီနေ့)\s*(sales|ရောင်းအား)?$',
            r'^(today\'s sales|ယနေ့ရောင်းအား)$',
        ],
        'sales_yesterday': [
            r'(yesterday|မနေ့က).*(sales|ရောင်းအား)',
            r'(sales|ရောင်းအား).*(yesterday|မနေ့က)',
            r'^(yesterday\'s sales|မနေ့ကရောင်းအား)$',
        ],
        'sales_weekly': [
            r'(this week|weekly|ဒီတစ်ပတ်|အပတ်စဉ်).*(sales|ရောင်းအား)',
            r'(sales|ရောင်းအား).*(this week|weekly|ဒီတစ်ပတ်|အပတ်စဉ်)',
            r'^(weekly sales|အပတ်စဉ်ရောင်းအား)$',
            r'^(this week\'s sales|ဒီတစ်ပတ်ရောင်းအား)$',
        ],
        'sales_monthly': [
            r'(this month|monthly|ဒီလ|လစဉ်).*(sales|ရောင်းအား)',
            r'(sales|ရောင်းအား).*(this month|monthly|ဒီလ|လစဉ်)',
            r'^(monthly sales|လစဉ်ရောင်းအား)$',
            r'^(this month\'s sales|ဒီလရောင်းအား)$',
        ],
        'sales_total': [
            r'(total|စုစုပေါင်း).*(sales|ရောင်းအား)',
            r'(sales|ရောင်းအား).*(total|စုစုပေါင်း)',
            r'^(total sales|စုစုပေါင်းရောင်းအား)$',
            r'^(all sales|all time sales|အားလုံးရောင်းအား)$',
        ],
        
        # ============================================================
        # PRODUCT INTENTS
        # ============================================================
        'top_products': [
            r'(top|best|ထိပ်|အကောင်းဆုံး).*(products|ပစ္စည်း|items)',
            r'(products|ပစ္စည်း|items).*(top|best|ထိပ်|အကောင်းဆုံး)',
            r'^(top products|ထိပ်ဆုံးပစ္စည်းများ)$',
            r'^(best selling|ရောင်းအားအကောင်းဆုံး)$',
        ],
        'low_stock': [
            r'(low stock|စတော့နည်း|ပစ္စည်းနည်း|stock alert|စတော့ကျ)',
            r'^(low stock|စတော့နည်းသောပစ္စည်းများ)$',
            r'(stock|စတော့).*(low|နည်း|ကျ)',
        ],
        'stock_summary': [
            r'(stock summary|စတော့အကျဉ်းချုပ်|stock overview)',
            r'^(stock|စတော့)\s*(summary|အကျဉ်းချုပ်)?$',
            r'(inventory|စာရင်း).*(summary|အကျဉ်းချုပ်)',
        ],
        'product_search': [
            r'(search|find|ရှာ|ရှာဖွေ).*(product|ပစ္စည်း)?\s*["\']?([^"\']+)["\']?',
            r'^(product|ပစ္စည်း)\s+(search|ရှာ)\s+["\']?([^"\']+)["\']?',
            r'^(find|ရှာ)\s+["\']?([^"\']+)["\']?',
        ],
        
        # ============================================================
        # CUSTOMER INTENTS
        # ============================================================
        'top_customers': [
            r'(top|best|ထိပ်|အကောင်းဆုံး).*(customers|ဖောက်သည်|ဝယ်သူ)',
            r'(customers|ဖောက်သည်|ဝယ်သူ).*(top|best|ထိပ်|အကောင်းဆုံး)',
            r'^(top customers|ထိပ်ဆုံးဖောက်သည်များ)$',
            r'^(best customers|အကောင်းဆုံးဖောက်သည်များ)$',
        ],
        'customer_stats': [
            r'(customer stats|ဖောက်သည်စာရင်းအင်း|customer statistics)',
            r'^(customer|ဖောက်သည်)\s*(stats|စာရင်းအင်း)?$',
            r'(customer|ဖောက်သည်).*(statistics|စာရင်းအင်း)',
        ],
        
        'customer_search': [
            r'(search|find|show)\s+(customer|customers)\s+["\']?([^"\']+)["\']?',
            r'(customer|customers)\s+(search|find)\s+["\']?([^"\']+)["\']?',
            r'(search|find|show).*(ဝယ်သူ|ဝယ်ယူသူ|ဖောက်သည်)\s*["\']?([^"\']+)["\']?',
            r'(ဝယ်သူ|ဝယ်ယူသူ|ဖောက်သည်).*(ရှာ|ရှာဖွေ)\s*["\']?([^"\']+)["\']?',
        ],
        'customer_detail': [
            r'(customer|customers)\s+(?:detail|details|profile|info|balance)\s+["\']?([^"\']+)["\']?',
            r'(?:detail|details|profile|info|balance)\s+(?:for\s+)?(?:customer|customers)\s+["\']?([^"\']+)["\']?',
            r'^(?:customer|customers)\s+["\']?([^"\']+)["\']?',
            r'(ဝယ်သူ|ဝယ်ယူသူ|ဖောက်သည်).*(အသေးစိတ်|အချက်အလက်|စာရင်း|လက်ကျန်)\s*["\']?([^"\']+)["\']?',
        ],

        # ============================================================
        # DEBT/CREDIT INTENTS
        # ============================================================
        'debt_summary': [
            r'(debt summary|debt overview|အကြွေးစာရင်း|အကြွေးအကျဉ်းချုပ်)',
            r'^(debt|အကြွေး)\s*(summary|စာရင်း)?$',
            r'(credit|ချေး).*(summary|စာရင်း)',
            r'^(credit summary|ချေးငွေစာရင်း)$',
        ],
        'customer_debt': [
            r'(customer debt|debt customer|အကြွေး).*["\']?([^"\']+)["\']?',
            r'(["\']?[^"\']+["\']?)\s*(debt|အကြွေး)',
            r'^(debt|အကြွေး)\s+(for|အတွက်)\s+["\']?([^"\']+)["\']?',
            r'^(customer|ဖောက်သည်)\s+(debt|အကြွေး)\s+["\']?([^"\']+)["\']?',
        ],
        'overdue_debts': [
            r'(overdue|overdue debt|overdue debts|ကြာမြင့်|ကြာမြင့်အကြွေး)',
            r'(debt|အကြွေး).*(overdue|ကြာမြင့်)',
            r'^(overdue debts|ကြာမြင့်အကြွေးများ)$',
            r'(late|နောက်ကျ).*(payment|ငွေချေ|အကြွေး)',
        ],
        'recent_debts': [
            r'(recent debt|recent debts|မကြာသေးမီအကြွေး|နောက်ဆုံးအကြွေး)',
            r'(debt|အကြွေး).*(recent|မကြာသေးမီ|နောက်ဆုံး)',
            r'^(recent credit sales|မကြာသေးမီအကြွေးများ)$',
        ],
        
        # ============================================================
        # EXPENSE INTENTS
        # ============================================================
        'expenses_today': [
            r'(today|ယနေ့|ဒီနေ့).*(expenses|ကုန်ကျ|အသုံး|သုံးစွဲ)',
            r'(expenses|ကုန်ကျ|အသုံး|သုံးစွဲ).*(today|ယနေ့|ဒီနေ့)',
            r'^(today\'s expenses|ယနေ့အသုံးစရိတ်)$',
        ],
        'expenses_monthly': [
            r'(this month|monthly|ဒီလ|လစဉ်).*(expenses|ကုန်ကျ|အသုံး|သုံးစွဲ)',
            r'(expenses|ကုန်ကျ|အသုံး|သုံးစွဲ).*(this month|monthly|ဒီလ|လစဉ်)',
            r'^(monthly expenses|လစဉ်အသုံးစရိတ်)$',
        ],
        'expenses_total': [
            r'(total|စုစုပေါင်း).*(expenses|ကုန်ကျ|အသုံး|သုံးစွဲ)',
            r'^(total expenses|စုစုပေါင်းအသုံးစရိတ်)$',
            r'(expenses|အသုံးစရိတ်).*(total|စုစုပေါင်း)',
        ],
        
        # ============================================================
        # PROFIT INTENT
        # ============================================================
        'profit': [
            r'(profit|အမြတ်|margin)',
            r'(profit|အမြတ်).*(summary|အကျဉ်းချုပ်)',
            r'^(profit|အမြတ်)$',
            r'(gross profit|အသားတင်အမြတ်)',
        ],
        
        # ============================================================
        # HELP INTENT
        # ============================================================
        'help': [
            r'(help|အကူ|guide|လမ်းညွှန်|\?)',
            r'^(help|အကူအညီ)$',
            r'(how to|ဘယ်လို|နည်းလမ်း)',
            r'(support|အကူအညီ).*',
        ],
        
        # ============================================================
        # 🆕 PRODUCT SEARCH & ADD TO CART
        # ============================================================
        'product_search': [
            r'(search|find|ရှာ|ရှာဖွေ|ပစ္စည်း).*[\'"]?([^\'"]+)[\'"]?',
            r'^[\'"]?([^\'"]+)[\'"]?\s*(product|ပစ္စည်း)?$',
            r'(show|ပြ).*(product|ပစ္စည်း).*[\'"]?([^\'"]+)[\'"]?',
        ],
        'add_to_cart': [
            r'(add|ထည့်|cart|ကတ်).*[\'"]?([^\'"]+)[\'"]?',
            r'^[\'"]?([^\'"]+)[\'"]?\s*(add|cart|ထည့်)',
            r'(put|ထား).*(cart|ကတ်|basket).*[\'"]?([^\'"]+)[\'"]?',
        ],
        'check_stock': [
            r'(stock|စတော့).*[\'"]?([^\'"]+)[\'"]?',
            r'(how many|ဘယ်လောက်).*(stock|စတော့).*[\'"]?([^\'"]+)[\'"]?',
            r'(available|ကျန်|ရှိ).*(stock|စတော့).*[\'"]?([^\'"]+)[\'"]?',
        ],
        
        # ============================================================
        # 🆕 TROUBLESHOOTING
        # ============================================================
        'troubleshoot': [
            r'(error|issue|problem|not working|အမှား|ပြဿနာ).*',
            r'(fix|solve|help|ဖြေရှင်း|အကူ).*(error|issue|problem|အမှား)',
            r'(printer|database|network|bluetooth|scan|barcode).*(error|issue|problem|not working|အမှား)',
        ],
        
        # ============================================================
        # 🆕 SETTINGS
        # ============================================================
        'settings': [
            r'(dark mode|ညမုဒ်|theme|ပုံစံ).*(on|off|ဖွင့်|ပိတ်)',
            r'(turn|switch|change|ဖွင့်|ပိတ်).*(dark mode|ညမုဒ်|theme|ပုံစံ)',
            r'(open|show|ဖွင့်|ပြ).*(settings|receipt|language|user|database|ဆက်တင်)',
            r'(what|ဘယ်လို).*(version|language|ဗားရှင်း|ဘာသာ)',
        ],
    }
    
    # Myanmar character detection
    MYANMAR_PATTERN = re.compile(r'[\u1000-\u109F]')
    
    @classmethod
    def detect_intent(cls, query: str) -> Dict:
        """
        Detect intent from query
        
        Returns:
            {
                'intent': 'sales_today',
                'confidence': 0.95,
                'entities': {'date': 'today', 'limit': 5},
                'language': 'en' or 'my',
                'raw_query': query
            }
        """
        query_lower = query.lower().strip()
        is_myanmar = bool(cls.MYANMAR_PATTERN.search(query))
        
        # Try exact intent patterns
        for intent, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    entities = cls._extract_entities(intent, match, query)
                    return {
                        'intent': intent,
                        'confidence': 0.9,
                        'entities': entities,
                        'language': 'my' if is_myanmar else 'en',
                        'raw_query': query
                    }
        
        # Try product detail detection (barcode, SKU, short name)
        product_match = cls._detect_product_identifier(query_lower)
        if product_match:
            return {
                'intent': 'product_detail',
                'confidence': 0.85,
                'entities': {'identifier': product_match},
                'language': 'my' if is_myanmar else 'en',
                'raw_query': query
            }
        
        # Unknown intent
        return {
            'intent': 'unknown',
            'confidence': 0.0,
            'entities': {},
            'language': 'my' if is_myanmar else 'en',
            'raw_query': query
        }
    
    @classmethod
    def _extract_entities(cls, intent: str, match, query: str) -> Dict:
        """Extract entities from matched query"""
        entities = {}
        query_lower = query.lower()
        
        # Extract search term for product_search
        if intent == 'product_search':
            groups = match.groups()
            if groups:
                # Get the last non-empty group (search term)
                for group in reversed(groups):
                    if group and group.strip():
                        entities['search_term'] = group.strip()
                        break
        
        # Extract customer name for customer_debt
        if intent in ['customer_debt', 'customer_search', 'customer_detail']:
            groups = match.groups()
            if groups:
                for group in reversed(groups):
                    if group and group.strip():
                        # Clean up the name
                        name = group.strip().strip('"\'')
                        if name and name not in ['debt', 'အကြွေး', 'customer', 'ဖောက်သည်']:
                            entities['customer_name'] = name
                            entities['search_term'] = name
                            break
        
        # Extract product for add_to_cart and check_stock
        if intent in ['add_to_cart', 'check_stock']:
            groups = match.groups()
            if groups:
                for group in reversed(groups):
                    if group and group.strip():
                        entity_key = 'product_name' if intent == 'add_to_cart' else 'product_name'
                        entities[entity_key] = group.strip().strip('"\'')
                        break
        
        # Extract number (like top 10)
        number_match = re.search(r'(\d+)', query)
        if number_match:
            entities['limit'] = int(number_match.group(1))
        else:
            # Default limits
            if intent in ['top_products', 'top_customers']:
                entities['limit'] = 5
            elif intent in ['recent_debts']:
                entities['limit'] = 10
        
        # Extract date/period references
        if 'yesterday' in query_lower or 'မနေ့က' in query_lower:
            entities['date'] = 'yesterday'
        elif 'today' in query_lower or 'ယနေ့' in query_lower or 'ဒီနေ့' in query_lower:
            entities['date'] = 'today'
        elif 'week' in query_lower or 'အပတ်' in query_lower:
            entities['period'] = 'week'
        elif 'month' in query_lower or 'လ' in query_lower:
            entities['period'] = 'month'
        
        # Extract due date for debt queries
        if 'overdue' in query_lower or 'ကြာမြင့်' in query_lower:
            entities['status'] = 'overdue'
        
        return entities
    
    @classmethod
    def _detect_product_identifier(cls, query: str) -> Optional[str]:
        """Detect if query is a barcode, SKU, or product name"""
        query_stripped = query.strip()
        
        # Barcode (8-13 digits)
        barcode_match = re.match(r'^[0-9]{8,13}$', query_stripped)
        if barcode_match:
            return barcode_match.group(0)
        
        # SKU (alphanumeric with hyphens/underscores, 3-20 chars)
        sku_match = re.match(r'^[A-Za-z0-9\-_]{3,20}$', query_stripped)
        if sku_match:
            return sku_match.group(0)
        
        # Short product name (2-20 chars, letters only, no special chars)
        if 2 <= len(query_stripped) <= 20:
            # Check if it's a valid product name (letters, spaces, Myanmar)
            if re.match(r'^[A-Za-z\s\u1000-\u109F]{2,20}$', query_stripped):
                # But not a common query word
                common_words = ['sales', 'stock', 'profit', 'debt', 'help', 'today', 'weekly', 
                               'monthly', 'total', 'top', 'best', 'customer', 'expense',
                               'ရောင်းအား', 'စတော့', 'အမြတ်', 'အကြွေး', 'အကူ']
                if query_stripped.lower() not in common_words:
                    return query_stripped
        
        return None
    
    @classmethod
    def is_myanmar_query(cls, text: str) -> bool:
        """Check if query contains Myanmar characters"""
        return bool(cls.MYANMAR_PATTERN.search(text))
    
    @classmethod
    def get_intent_description(cls, intent: str) -> str:
        """Get a human-readable description of an intent"""
        descriptions = {
            'sales_today': "Today's sales",
            'sales_yesterday': "Yesterday's sales",
            'sales_weekly': "Weekly sales",
            'sales_monthly': "Monthly sales",
            'sales_total': "Total sales",
            'top_products': "Top selling products",
            'low_stock': "Low stock products",
            'stock_summary': "Stock summary",
            'product_search': "Product search",
            'product_detail': "Product details",
            'add_to_cart': "Add to cart",
            'check_stock': "Check stock",
            'top_customers': "Top customers",
            'customer_stats': "Customer statistics",
            'debt_summary': "Debt summary",
            'customer_debt': "Customer debt",
            'overdue_debts': "Overdue debts",
            'recent_debts': "Recent debts",
            'expenses_today': "Today's expenses",
            'expenses_monthly': "Monthly expenses",
            'expenses_total': "Total expenses",
            'profit': "Profit summary",
            'troubleshoot': "Troubleshooting",
            'settings': "Settings",
            'help': "Help",
            'unknown': "Unknown query"
        }
        return descriptions.get(intent, "Unknown")
    
    @classmethod
    def get_intent_examples(cls, intent: str) -> List[str]:
        """Get example queries for an intent"""
        examples = {
            'sales_today': ['today sales', 'ဒီနေ့ရောင်းအား', "what's today's sales"],
            'sales_yesterday': ['yesterday sales', 'မနေ့ကရောင်းအား'],
            'sales_weekly': ['weekly sales', 'ဒီတစ်ပတ်ရောင်းအား', 'this week sales'],
            'sales_monthly': ['monthly sales', 'ဒီလရောင်းအား'],
            'sales_total': ['total sales', 'စုစုပေါင်းရောင်းအား'],
            'top_products': ['top products', 'ထိပ်ဆုံးပစ္စည်းများ', 'best selling items'],
            'low_stock': ['low stock', 'စတော့နည်းသောပစ္စည်းများ'],
            'stock_summary': ['stock summary', 'စတော့အကျဉ်းချုပ်'],
            'product_search': ['search milk', 'ပစ္စည်းရှာ နို့', 'find product Coke'],
            'product_detail': ['B0001', 'SKU123', 'Coca Cola'],
            'add_to_cart': ['add Coke to cart', 'Coke ထည့်', 'cart Blue Pen'],
            'check_stock': ['stock A4 paper', 'A4 စာရွက်စတော့', 'how many pens left'],
            'top_customers': ['top customers', 'ထိပ်ဆုံးဖောက်သည်များ'],
            'customer_stats': ['customer stats', 'ဖောက်သည်စာရင်းအင်း'],
            'debt_summary': ['debt summary', 'အကြွေးစာရင်း'],
            'customer_debt': ['customer debt John', 'ကျော်ဦး အကြွေး'],
            'overdue_debts': ['overdue debts', 'ကြာမြင့်အကြွေးများ'],
            'recent_debts': ['recent debts', 'မကြာသေးမီအကြွေးများ'],
            'expenses_today': ['today expenses', 'ယနေ့အသုံးစရိတ်'],
            'expenses_monthly': ['monthly expenses', 'လစဉ်အသုံးစရိတ်'],
            'expenses_total': ['total expenses', 'စုစုပေါင်းအသုံးစရိတ်'],
            'profit': ['profit', 'အမြတ်'],
            'troubleshoot': ['printer not working', 'database error', 'ပရင်တာအဆင်မပြေ'],
            'settings': ['dark mode on', 'ညမုဒ်ဖွင့်', 'open receipt settings'],
            'help': ['help', 'အကူအညီ', 'what can you do'],
        }
        return examples.get(intent, [])
