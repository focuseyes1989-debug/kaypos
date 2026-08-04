# ui/ai_pages/ai_analytics.py
"""
Query analytics for AI Chat
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any
from loguru import logger


class AIAnalytics:
    """Track and analyze AI queries"""
    
    def __init__(self):
        self.queries = []
        self.intent_counts = Counter()
        self.daily_queries = defaultdict(int)
        self.monthly_queries = defaultdict(int)
        self.response_times = []
        self.error_count = 0
        self.total_queries = 0
        self.unique_users = set()
    
    def log_query(self, query: str, intent: str, success: bool, response_time: float, user_id: str = None):
        """Log a query for analytics"""
        self.queries.append({
            'query': query,
            'intent': intent,
            'success': success,
            'response_time': response_time,
            'timestamp': datetime.now()
        })
        
        self.intent_counts[intent] += 1
        self.daily_queries[datetime.now().date()] += 1
        self.monthly_queries[datetime.now().strftime("%Y-%m")] += 1
        self.total_queries += 1
        self.response_times.append(response_time)
        
        if not success:
            self.error_count += 1
        
        if user_id:
            self.unique_users.add(user_id)
    
    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        avg_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        error_rate = (self.error_count / self.total_queries * 100) if self.total_queries > 0 else 0
        
        return {
            'total_queries': self.total_queries,
            'unique_users': len(self.unique_users),
            'error_rate': f"{error_rate:.1f}%",
            'avg_response_time': f"{avg_time:.2f}s",
            'popular_intents': self.get_popular_intents(5),
            'daily_avg': self.get_daily_average(7),
        }
    
    def get_popular_intents(self, limit: int = 5) -> List[tuple]:
        """Get most popular intents"""
        return self.intent_counts.most_common(limit)
    
    def get_daily_average(self, days: int = 7) -> float:
        """Get average daily queries for last N days"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [q for q in self.queries if q['timestamp'] > cutoff]
        return len(recent) / days if days > 0 else 0
    
    def get_weekly_trend(self) -> Dict:
        """Get weekly query trend"""
        trend = defaultdict(int)
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            trend[date.strftime("%A")] = self.daily_queries.get(date.date(), 0)
        return dict(trend)
    
    def get_suggestions(self) -> List[str]:
        """Get suggestions for improving AI"""
        suggestions = []
        
        # Check for common failures
        failed_queries = [q['query'] for q in self.queries if not q['success']]
        if failed_queries:
            common_failures = Counter(failed_queries).most_common(3)
            if common_failures:
                suggestions.append(
                    f"🔍 Consider adding support for: {', '.join([f'\"{q}\"' for q, _ in common_failures])}"
                )
        
        # Check response time
        if self.response_times:
            avg_time = sum(self.response_times) / len(self.response_times)
            if avg_time > 2.0:
                suggestions.append(f"⚡ Response time is {avg_time:.1f}s - consider optimizing queries")
            elif avg_time > 1.0:
                suggestions.append(f"⏱️ Response time is {avg_time:.1f}s - good, can be better")
        
        # Check query volume
        if self.total_queries > 0:
            daily_avg = self.get_daily_average(7)
            if daily_avg < 5:
                suggestions.append("📢 Low query volume - consider promoting AI features")
        
        # Check error rate
        if self.total_queries > 0:
            error_rate = (self.error_count / self.total_queries * 100)
            if error_rate > 10:
                suggestions.append(f"⚠️ Error rate is {error_rate:.1f}% - review error handling")
        
        return suggestions
    
    def clear(self):
        """Clear analytics data"""
        self.queries.clear()
        self.intent_counts.clear()
        self.daily_queries.clear()
        self.monthly_queries.clear()
        self.response_times.clear()
        self.error_count = 0
        self.total_queries = 0
        self.unique_users.clear()
        logger.info("Analytics cleared")