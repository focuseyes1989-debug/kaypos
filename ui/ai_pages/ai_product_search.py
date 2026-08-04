# ui/ai_pages/ai_product_search.py
"""
AI Product Search with Natural Language, Synonyms, and Typo Correction
"""

import re
from difflib import get_close_matches
from typing import List, Dict, Optional
from models.database import connect_db
from loguru import logger


class AIProductSearch:
    """AI-powered product search with NLP capabilities"""
    
    # Myanmar and English synonyms dictionary
    SYNONYMS = {
        # Stationery
        'pen': ['ballpen', 'ballpoint', 'စာရေးတံ', 'ဘောပင်', 'pen', 'ဘောလ်ပင်'],
        'pencil': ['ခဲတံ', 'pencil', 'ရေးခဲတံ'],
        'paper': ['စာရွက်', 'a4', 'a4 paper', 'စာချပ်', 'paper', 'copy paper'],
        'notebook': ['စာအုပ်', 'မှတ်စုစာအုပ်', 'notebook', 'exercise book', 'ကျောင်းစာအုပ်'],
        'file': ['ဖိုင်', 'file', 'folder', 'document file', 'စာရွက်ဖိုင်'],
        'envelope': ['စာအိတ်', 'envelope', 'mail'],
        'sticker': ['စတစ်ကာ', 'sticker', 'label'],
        'ink': ['မင်', 'ink', 'printer ink', 'cartridge', 'ပရင်တာမင်'],
        'toner': ['toner', 'တိုနာ', 'printer toner'],
        
        # Office Supplies
        'stapler': ['ထိုးကိရိယာ', 'stapler', 'စာရွက်ထိုး'],
        'scissors': ['ကတ်ကြေး', 'scissors', 'စာရွက်ဖြတ်'],
        'tape': ['တိပ်', 'tape', 'scotch tape', 'packing tape'],
        'glue': ['ကော်', 'glue', 'adhesive', 'stick glue'],
        'marker': ['မာကာ', 'marker', 'highlight', 'အမှတ်အသား'],
        
        # Common misspellings
        'typo_map': {
            'bolpen': 'ballpen',
            'balpen': 'ballpen',
            'pensil': 'pencil',
            'notbuk': 'notebook',
            'stiker': 'sticker',
            'scisors': 'scissors',
            'tap': 'tape',
            'glu': 'glue',
            'markr': 'marker',
        }
    }
    
    @classmethod
    def search(cls, query: str, limit: int = 20) -> List[Dict]:
        """
        Intelligent product search with:
        - Keyword extraction
        - Synonym matching
        - Typo correction
        - Partial matching
        """
        query_clean = query.strip().lower()
        
        # 1. Check for direct match first (faster)
        direct_results = cls._direct_search(query_clean, limit)
        if direct_results:
            return direct_results
        
        # 2. Expand search with synonyms
        expanded_terms = cls._expand_search_terms(query_clean)
        
        # 3. Typo correction
        corrected_query = cls._correct_typo(query_clean)
        if corrected_query != query_clean:
            expanded_terms.append(corrected_query)
        
        # 4. Search with expanded terms
        results = cls._expanded_search(expanded_terms, limit)
        
        if results:
            return results
        
        # 5. Fallback: fuzzy match
        return cls._fuzzy_search(query_clean, limit)
    
    @classmethod
    def _direct_search(cls, query: str, limit: int) -> List[Dict]:
        """Direct product search"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, name, sku, barcode, price, stock,
                category, description
            FROM products 
            WHERE LOWER(name) = ?
            OR LOWER(sku) = ?
            OR barcode = ?
            LIMIT ?
        """, (query, query, query, limit))
        
        results = cls._format_results(cursor.fetchall())
        conn.close()
        return results
    
    @classmethod
    def _expand_search_terms(cls, query: str) -> List[str]:
        """Expand query with synonyms"""
        terms = [query]
        
        # Check if query matches any synonym group
        for key, synonyms in cls.SYNONYMS.items():
            if query in [s.lower() for s in synonyms]:
                # Add all synonyms from this group
                terms.extend([s.lower() for s in synonyms if s.lower() != query])
                break
        
        # Add partial matches
        for key, synonyms in cls.SYNONYMS.items():
            for syn in synonyms:
                if syn.lower() in query and syn.lower() not in terms:
                    terms.append(syn.lower())
        
        return terms
    
    @classmethod
    def _correct_typo(cls, query: str) -> str:
        """Correct common typos"""
        typo_map = cls.SYNONYMS.get('typo_map', {})
        if query in typo_map:
            return typo_map[query]
        
        # Check if query is close to any known word
        all_words = []
        for synonyms in cls.SYNONYMS.values():
            if isinstance(synonyms, list):
                all_words.extend([s.lower() for s in synonyms if isinstance(s, str)])
        
        matches = get_close_matches(query, all_words, n=1, cutoff=0.8)
        if matches:
            return matches[0]
        
        return query
    
    @classmethod
    def _expanded_search(cls, terms: List[str], limit: int) -> List[Dict]:
        """Search with expanded terms"""
        if not terms:
            return []
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # Build LIKE conditions
        conditions = []
        params = []
        for term in terms:
            conditions.append("LOWER(name) LIKE ?")
            params.append(f"%{term}%")
            conditions.append("LOWER(category) LIKE ?")
            params.append(f"%{term}%")
            conditions.append("LOWER(description) LIKE ?")
            params.append(f"%{term}%")
        
        where_clause = " OR ".join(conditions)
        
        cursor.execute(f"""
            SELECT 
                id, name, sku, barcode, price, stock,
                category, description
            FROM products 
            WHERE {where_clause}
            LIMIT ?
        """, params + [limit])
        
        results = cls._format_results(cursor.fetchall())
        conn.close()
        return results
    
    @classmethod
    def _fuzzy_search(cls, query: str, limit: int) -> List[Dict]:
        """Fuzzy search as last resort"""
        # Get all product names
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, sku, barcode, price, stock, category, description FROM products")
        all_products = cursor.fetchall()
        conn.close()
        
        if not all_products:
            return []
        
        # Find close matches
        names = [p[1] for p in all_products]  # product names
        matches = get_close_matches(query, names, n=limit, cutoff=0.6)
        
        if not matches:
            return []
        
        # Get full product info for matches
        results = []
        for match in matches:
            for p in all_products:
                if p[1] == match:
                    results.append(cls._format_result(p))
                    break
        
        return results
    
    @classmethod
    def _format_results(cls, rows) -> List[Dict]:
        """Format database rows to dict"""
        return [cls._format_result(row) for row in rows]
    
    @classmethod
    def _format_result(cls, row) -> Dict:
        """Format single row to dict"""
        return {
            'id': row[0],
            'name': row[1],
            'sku': row[2],
            'barcode': row[3],
            'price': f"{row[4]:,.0f}" if row[4] else "0",
            'stock': row[5] or 0,
            'category': row[6] or 'Uncategorized',
            'description': row[7] or '',
        }
    
    @classmethod
    def quick_add_to_cart(cls, query: str) -> Optional[Dict]:
        """Quick add product to cart with smart search"""
        results = cls.search(query, limit=1)
        if results:
            return results[0]
        return None