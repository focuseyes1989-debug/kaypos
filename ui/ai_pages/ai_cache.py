# ui/ai_pages/ai_cache.py

"""
Query caching for AI Chat
"""

from datetime import datetime, timedelta
from collections import OrderedDict
from loguru import logger


class QueryCache:
    """LRU Cache for query results"""
    
    def __init__(self, max_size=20, ttl_seconds=60):
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._total_queries = 0
    
    def get(self, key):
        """Get cached result"""
        self._total_queries += 1
        
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self.ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return data
            else:
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key, value):
        """Cache a result"""
        if len(self._cache) >= self.max_size:
            # Remove oldest
            self._cache.popitem(last=False)
        
        self._cache[key] = (value, datetime.now())
        logger.debug(f"Cache set: {key}")
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._total_queries = 0
        logger.info("Cache cleared")
    
    def get_stats(self):
        """Get cache statistics"""
        total = self._hits + self._misses
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'total_queries': self._total_queries,
            'hit_rate': f"{(self._hits/total*100):.1f}%" if total > 0 else "0%",
            'ttl_seconds': self.ttl.seconds
        }


# Global cache instance
_query_cache = QueryCache(max_size=20, ttl_seconds=60)


def get_cache_stats():
    """Get cache statistics for display"""
    return _query_cache.get_stats()


def clear_cache():
    """Clear the cache"""
    _query_cache.clear()