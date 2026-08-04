# ui/ai_pages/ai_response_templates.py
"""
Enhanced response templates with context
"""

from datetime import datetime
from typing import Dict, List, Any


class ResponseTemplates:
    """Enhanced response templates with context"""
    
    @staticmethod
    def get_sales_response(data: Dict, period: str, currency_symbol: str = "Ks") -> str:
        """Generate contextual sales response"""
        if not data or not data.get('data'):
            return f"📊 No sales recorded for {period}."
        
        row = data['data'][0]
        total = float(row.get('Total Sales', 0).replace(',', '')) if isinstance(row.get('Total Sales'), str) else row.get('Total Sales', 0)
        transactions = row.get('Transactions', 0)
        avg = total / transactions if transactions > 0 else 0
        
        messages = []
        
        # Performance emoji
        if total > 1000000:
            messages.append("🎉 Excellent performance!")
        elif total > 500000:
            messages.append("📈 Good performance!")
        elif total > 100000:
            messages.append("📊 Solid performance!")
        else:
            messages.append("💪 Keep going!")
        
        # Transaction insights
        if transactions > 50:
            messages.append(f"🔥 {transactions} transactions is impressive!")
        elif transactions > 20:
            messages.append(f"📝 {transactions} transactions today")
        else:
            messages.append(f"📋 {transactions} transactions")
        
        # Main numbers
        messages.append("")
        messages.append(f"💰 **Total Sales:** {currency_symbol} {total:,.0f}")
        messages.append(f"📊 **Average Sale:** {currency_symbol} {avg:,.0f}")
        
        # Additional info if available
        if 'Profit' in row:
            profit = float(row['Profit'].replace(',', '')) if isinstance(row['Profit'], str) else row.get('Profit', 0)
            profit_margin = (profit / total * 100) if total > 0 else 0
            messages.append(f"📈 **Profit:** {currency_symbol} {profit:,.0f} ({profit_margin:.1f}% margin)")
        
        return "\n".join(messages)
    
    @staticmethod
    def get_trend_response(current: float, previous: float, period: str) -> str:
        """Generate trend analysis response"""
        if previous == 0:
            return "📊 No previous data to compare."
        
        change = ((current - previous) / previous) * 100
        abs_change = abs(change)
        
        emoji = "🚀" if change > 20 else "📈" if change > 5 else "➡️" if abs_change <= 5 else "📉"
        direction = "increased" if change > 0 else "decreased"
        
        return f"{emoji} {direction} by {abs_change:.1f}% compared to previous {period}"
    
    @staticmethod
    def get_stock_response(products: List[Dict]) -> str:
        """Generate stock response with urgency levels"""
        if not products:
            return "✅ All products have sufficient stock!"
        
        urgent = [p for p in products if p.get('Stock', 0) == 0]
        low = [p for p in products if 0 < p.get('Stock', 0) <= p.get('Low Stock', 0)]
        
        messages = []
        
        if urgent:
            messages.append(f"🚨 **URGENT:** {len(urgent)} products out of stock!")
            for p in urgent[:3]:
                messages.append(f"  • {p['Product']} - Out of stock")
        
        if low:
            messages.append(f"⚠️ **Low Stock:** {len(low)} products need restocking")
            for p in low[:3]:
                messages.append(f"  • {p['Product']} - Only {p['Stock']} left (Min: {p['Low Stock']})")
        
        if len(products) > 6:
            messages.append(f"\n📋 Showing first 6 of {len(products)} products")
        
        return "\n".join(messages)
    
    @staticmethod
    def get_profit_response(data: Dict) -> str:
        """Generate profit response with insights"""
        message = "📈 **Profit Summary**\n\n"
        
        total_sales = data.get('total_sales', 0)
        total_cogs = data.get('total_cogs', 0)
        gross_profit = data.get('gross_profit', 0)
        total_expenses = data.get('total_expenses', 0)
        net_profit = data.get('net_profit', 0)
        
        gross_margin = (gross_profit / total_sales * 100) if total_sales > 0 else 0
        net_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0
        
        message += f"💰 **Total Sales:** {total_sales:,.0f} Ks\n"
        message += f"📦 **COGS:** {total_cogs:,.0f} Ks\n"
        message += f"📈 **Gross Profit:** {gross_profit:,.0f} Ks ({gross_margin:.1f}%)\n"
        message += f"💸 **Expenses:** {total_expenses:,.0f} Ks\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"🎯 **Net Profit:** {net_profit:,.0f} Ks ({net_margin:.1f}%)"
        
        # Additional insight
        if net_profit > 1000000:
            message += "\n\n🌟 Excellent profit! Keep it up!"
        elif net_profit > 500000:
            message += "\n\n👍 Good profit! Room for improvement."
        elif net_profit > 0:
            message += "\n\n📈 Positive profit! Focus on growth."
        else:
            message += "\n\n⚠️ Negative profit! Review your expenses."
        
        return message