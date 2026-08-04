# ui/ai_pages/ai_error_handler.py
"""
Smart error handling for AI queries
"""

import re
from typing import Dict, Optional


class AIErrorHandler:
    """Smart error handling for AI queries"""
    
    @staticmethod
    def handle_query_error(query: str, error: Exception) -> str:
        """Generate helpful error messages"""
        query_lower = query.lower()
        
        # Try to understand what user wanted
        if any(word in query_lower for word in ['sales', 'sale', 'ရောင်း', 'ရောင်းအား']):
            return AIErrorHandler._get_sales_help()
        
        elif any(word in query_lower for word in ['product', 'ပစ္စည်း', 'stock', 'စတော့']):
            return AIErrorHandler._get_product_help()
        
        elif any(word in query_lower for word in ['customer', 'ဖောက်သည်', 'ဝယ်သူ']):
            return AIErrorHandler._get_customer_help()
        
        elif any(word in query_lower for word in ['expense', 'ကုန်ကျ', 'အသုံး']):
            return AIErrorHandler._get_expense_help()
        
        else:
            return AIErrorHandler._get_general_help()
    
    @staticmethod
    def _get_sales_help() -> str:
        return """
❌ I couldn't find sales data for that query.

💡 **Try these sales queries:**
• "today sales" - Today's sales
• "yesterday sales" - Yesterday's sales  
• "weekly sales" - This week's sales
• "monthly sales" - This month's sales
• "total sales" - All time sales
• "top products" - Best selling products

📝 **မြန်မာလို:**
• "ယနေ့ရောင်းအား"
• "အပတ်စဉ်ရောင်းအား"
• "စုစုပေါင်းရောင်းအား"
"""
    
    @staticmethod
    def _get_product_help() -> str:
        return """
❌ I couldn't find product information.

💡 **Try these product queries:**
• "low stock" - Low stock products
• "stock summary" - Overall stock
• "search [product name]" - Search products
• "B0001" - Product by barcode/SKU

📝 **မြန်မာလို:**
• "စတော့နည်းသောပစ္စည်းများ"
• "စတော့အကျဉ်းချုပ်"
• "ပစ္စည်းရှာ နို့"
"""
    
    @staticmethod
    def _get_customer_help() -> str:
        return """
❌ I couldn't find customer information.

💡 **Try these customer queries:**
• "top customers" - Best customers
• "customer stats" - Customer statistics

📝 **မြန်မာလို:**
• "ထိပ်ဆုံးဖောက်သည်များ"
• "ဖောက်သည်စာရင်းအင်း"
"""
    
    @staticmethod
    def _get_expense_help() -> str:
        return """
❌ I couldn't find expense data.

💡 **Try these expense queries:**
• "today expenses" - Today's expenses
• "monthly expenses" - Monthly expenses
• "total expenses" - All time expenses

📝 **မြန်မာလို:**
• "ယနေ့အသုံးစရိတ်"
• "လစဉ်အသုံးစရိတ်"
• "စုစုပေါင်းအသုံးစရိတ်"
"""
    
    @staticmethod
    def _get_general_help() -> str:
        return """
❌ I didn't understand that query.

💡 **Here's what I can help with:**

📊 **Sales:**
• "today sales" | "ယနေ့ရောင်းအား"
• "weekly sales" | "အပတ်စဉ်ရောင်းအား"
• "top products" | "ထိပ်ဆုံးပစ္စည်းများ"

📦 **Products:**
• "low stock" | "စတော့နည်းသောပစ္စည်းများ"
• "search [name]" | "ပစ္စည်းရှာ [အမည်]"

💰 **Profit:**
• "profit" | "အမြတ်"

👥 **Customers:**
• "top customers" | "ထိပ်ဆုံးဖောက်သည်များ"

💸 **Expenses:**
• "today expenses" | "ယနေ့အသုံးစရိတ်"

❓ **Help:**
• "help" | "အကူအညီ"
"""