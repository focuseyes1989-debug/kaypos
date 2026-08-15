# ui/categories/category_service.py
"""
Category Service - Business logic for category management
"""

import re
import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from loguru import logger

from models.database import connect_db, DBContext
from utils.slug_generator import generate_slug
from utils.image_optimizer import ImageOptimizer
from utils.translations import tr


class CategoryService:
    """Service class for category operations"""
    
    def __init__(self):
        self._cache = {}
        self._cache_timestamp = {}
        self.cache_ttl = 5
        
        # ✅ Initialize category stats on service creation
        try:
            self._ensure_category_columns()
            self._fix_product_category_ids()
            self.update_all_category_stats()
        except Exception as e:
            logger.warning(f"Could not initialize category stats: {e}")
    
    def _ensure_category_columns(self):
        """Ensure all required columns exist in categories table."""
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Check if categories table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
                if not cursor.fetchone():
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        slug TEXT,
                        description TEXT,
                        parent_id INTEGER,
                        icon TEXT,
                        color TEXT,
                        image_path TEXT,
                        status TEXT DEFAULT 'active',
                        is_system INTEGER DEFAULT 0,
                        sort_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        code TEXT,
                        notes TEXT,
                        is_favorite INTEGER DEFAULT 0,
                        group_id INTEGER,
                        FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
                    )
                    """)
                    conn.commit()
                    logger.info("✅ Created categories table")
                    return

            # Get existing columns
            with DBContext() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(categories)")
                existing_cols = [col[1] for col in cursor.fetchall()]
                
                # ✅ Fix: created_at နဲ့ updated_at ကို DEFAULT မပါဘဲ ထည့်ပါ
                # SQLite doesn't support ALTER TABLE ADD COLUMN with DEFAULT CURRENT_TIMESTAMP
                columns_to_add = {
                    'slug': "TEXT",
                    'description': "TEXT",
                    'parent_id': "INTEGER",
                    'icon': "TEXT",
                    'color': "TEXT",
                    'image_path': "TEXT",
                    'status': "TEXT DEFAULT 'active'",
                    'is_system': "INTEGER DEFAULT 0",
                    'sort_order': "INTEGER DEFAULT 0",
                    'code': "TEXT",
                    'notes': "TEXT",
                    'is_favorite': "INTEGER DEFAULT 0",
                    'group_id': "INTEGER"
                }
                
                # ✅ created_at နဲ့ updated_at ကို DEFAULT မပါဘဲ ထည့်ပါ
                # ပြီးမှ data ကို update လုပ်ပါမယ်
                for col, col_type in columns_to_add.items():
                    if col not in existing_cols:
                        try:
                            cursor.execute(f"ALTER TABLE categories ADD COLUMN {col} {col_type}")
                            conn.commit()
                            logger.info(f"✅ Added missing column '{col}' to categories table")
                        except Exception as e:
                            logger.warning(f"Could not add column {col}: {e}")
                
                # ✅ created_at ကို အထူးကိုင်တွယ်ပါ
                if 'created_at' not in existing_cols:
                    try:
                        cursor.execute("ALTER TABLE categories ADD COLUMN created_at TIMESTAMP")
                        conn.commit()
                        logger.info("✅ Added missing column 'created_at' to categories table")
                        # Update existing rows with current timestamp
                        cursor.execute("UPDATE categories SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not add column created_at: {e}")
                
                # ✅ updated_at ကို အထူးကိုင်တွယ်ပါ
                if 'updated_at' not in existing_cols:
                    try:
                        cursor.execute("ALTER TABLE categories ADD COLUMN updated_at TIMESTAMP")
                        conn.commit()
                        logger.info("✅ Added missing column 'updated_at' to categories table")
                        # Update existing rows with current timestamp
                        cursor.execute("UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not add column updated_at: {e}")
                
                # Update slugs
                try:
                    cursor.execute("SELECT id, name FROM categories WHERE slug IS NULL OR slug = ''")
                    rows = cursor.fetchall()
                    if rows:
                        logger.info(f"Updating slugs for {len(rows)} categories...")
                        for cat_id, name in rows:
                            slug = name.lower().strip()
                            slug = slug.replace(' ', '-')
                            slug = slug.replace('(', '')
                            slug = slug.replace(')', '')
                            slug = slug.replace('/', '-')
                            slug = slug.replace('&', 'and')
                            slug = slug.replace("'", '')
                            slug = slug.replace('"', '')
                            slug = re.sub(r'-+', '-', slug)
                            
                            if not slug:
                                slug = f"category-{cat_id}"
                            
                            cursor.execute("SELECT id FROM categories WHERE slug = ? AND id != ?", (slug, cat_id))
                            if cursor.fetchone():
                                slug = f"{slug}-{cat_id}"
                            
                            cursor.execute("UPDATE categories SET slug = ? WHERE id = ?", (slug, cat_id))
                        conn.commit()
                        logger.info(f"✅ Updated slugs for {len(rows)} categories")
                except Exception as e:
                    logger.warning(f"Could not update slugs: {e}")
                
                # Create unique index for slug
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_slug_unique ON categories(slug)")
                    conn.commit()
                    logger.debug("✅ Ensured unique index for category slug")
                except Exception as e:
                    logger.warning(f"Could not create unique index for slug: {e}")
                
                # ✅ Check if products table has category_id column
                try:
                    cursor.execute("PRAGMA table_info(products)")
                    product_cols = [col[1] for col in cursor.fetchall()]
                    
                    if 'category_id' not in product_cols:
                        try:
                            logger.info("Adding category_id column to products table...")
                            cursor.execute("ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL")
                            conn.commit()
                            logger.info("✅ Added category_id column to products table")
                        except Exception as e:
                            logger.warning(f"Could not add category_id column: {e}")
                except Exception as e:
                    logger.warning(f"Could not check products table: {e}")
                
                # ✅ Create category_stats table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_stats (
                        category_id INTEGER PRIMARY KEY,
                        product_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to ensure category columns: {e}")
    
    def _fix_product_category_ids(self):
        """
        ✅ AUTO-FIX: Update product category_id from old category column.
        This runs automatically on service initialization.
        """
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Check if products table has category column and category_id column
                cursor.execute("PRAGMA table_info(products)")
                product_cols = [col[1] for col in cursor.fetchall()]
                
                if 'category' not in product_cols or 'category_id' not in product_cols:
                    logger.debug("Products table missing category or category_id column, skipping fix")
                    return
                
                # ✅ Update products where category_id is NULL but category has value
                cursor.execute("""
                    UPDATE products 
                    SET category_id = (
                        SELECT id FROM categories 
                        WHERE LOWER(categories.name) = LOWER(products.category) 
                        OR categories.slug = products.category
                        LIMIT 1
                    )
                    WHERE category_id IS NULL 
                    AND category IS NOT NULL 
                    AND category != ''
                """)
                conn.commit()
                updated = cursor.rowcount
                
                if updated > 0:
                    logger.info(f"✅ Auto-fixed: Updated {updated} products with category_id from old category column")
                    
                    # ✅ Update category_stats for all categories after fix
                    self.update_all_category_stats()
                else:
                    # Check if there are any products with old category column but no match
                    cursor.execute("""
                        SELECT COUNT(*) FROM products 
                        WHERE category IS NOT NULL 
                        AND category != ''
                        AND category_id IS NULL
                    """)
                    no_match = cursor.fetchone()[0]
                    if no_match > 0:
                        logger.warning(f"⚠️ {no_match} products have category but no matching category found in categories table")
                        logger.warning("Please check if categories exist for these products")
                
        except Exception as e:
            logger.warning(f"Could not fix product category IDs: {e}")

    def _get_cache(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired"""
        if key in self._cache:
            elapsed = (datetime.now() - self._cache_timestamp[key]).total_seconds()
            if elapsed < self.cache_ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_timestamp[key]
        return None

    def _set_cache(self, key: str, value: Any):
        """Set cache item"""
        self._cache[key] = value
        self._cache_timestamp[key] = datetime.now()

    def _clear_cache(self):
        """Clear all cache"""
        self._cache.clear()
        self._cache_timestamp.clear()
        logger.debug("🧹 Category cache cleared")

    # ==================== CRUD Operations ====================
    
    def get_categories(self, 
                      parent_id: Optional[int] = None,
                      status: Optional[str] = None,
                      search: Optional[str] = None,
                      limit: Optional[int] = None,
                      offset: Optional[int] = None,
                      sort_by: str = 'sort_order',
                      sort_order: str = 'ASC') -> Tuple[List[Dict], int]:
        """
        Get categories with filters
        
        Returns:
            Tuple of (categories list, total count)
        """
        # Ensure columns exist first
        self._ensure_category_columns()
        
        cache_key = f"categories_{parent_id}_{status}_{search}_{limit}_{offset}_{sort_by}_{sort_order}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            if isinstance(cached, tuple) and len(cached) == 2:
                return cached
            else:
                self._clear_cache()
        
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # ✅ Query with product count from category_stats
                query = """
                    SELECT 
                        c.id,
                        c.name,
                        COALESCE(c.slug, '') as slug,
                        COALESCE(c.description, '') as description,
                        c.parent_id,
                        p.name as parent_name,
                        COALESCE(c.sort_order, 0) as sort_order,
                        COALESCE(c.color, '#6c5ce7') as color,
                        COALESCE(c.icon, '📁') as icon,
                        c.image_path as image,
                        COALESCE(c.status, 'active') as status,
                        COALESCE(c.code, '') as code,
                        COALESCE(c.notes, '') as notes,
                        COALESCE(c.is_system, 0) as is_system,
                        COALESCE(CAST(c.created_at AS TEXT), '') as created_at,
                        COALESCE(CAST(c.updated_at AS TEXT), '') as updated_at,
                        COALESCE(s.product_count, 0) as product_count
                    FROM categories c
                    LEFT JOIN categories p ON c.parent_id = p.id
                    LEFT JOIN category_stats s ON c.id = s.category_id
                    WHERE 1=1
                """
                params = []
                
                if parent_id is not None:
                    if parent_id == -1:
                        query += " AND c.parent_id IS NULL"
                    else:
                        query += " AND c.parent_id = ?"
                        params.append(parent_id)
                
                if status:
                    query += " AND c.status = ?"
                    params.append(status)
                
                if search:
                    query += " AND (c.name LIKE ? OR c.slug LIKE ? OR c.code LIKE ?)"
                    search_term = f"%{search}%"
                    params.extend([search_term, search_term, search_term])
                
                # Get total count
                count_query = "SELECT COUNT(*) FROM categories c WHERE 1=1"
                count_params = []
                
                if parent_id is not None:
                    if parent_id == -1:
                        count_query += " AND c.parent_id IS NULL"
                    else:
                        count_query += " AND c.parent_id = ?"
                        count_params.append(parent_id)
                
                if status:
                    count_query += " AND c.status = ?"
                    count_params.append(status)
                
                if search:
                    count_query += " AND (c.name LIKE ? OR c.slug LIKE ? OR c.code LIKE ?)"
                    search_term = f"%{search}%"
                    count_params.extend([search_term, search_term, search_term])
                
                cursor.execute(count_query, count_params)
                total = cursor.fetchone()[0]
                
                # Order by
                query += " ORDER BY c.sort_order ASC, c.name ASC"
                
                if limit is not None:
                    query += " LIMIT ?"
                    params.append(limit)
                    if offset is not None:
                        query += " OFFSET ?"
                        params.append(offset)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                categories = []
                for row in rows:
                    # ✅ Convert row to dict manually
                    cat_dict = {
                        'id': row[0],
                        'name': row[1],
                        'slug': row[2],
                        'description': row[3],
                        'parent_id': row[4],
                        'parent_name': row[5],
                        'sort_order': row[6],
                        'color': row[7],
                        'icon': row[8],
                        'image': row[9],
                        'status': row[10],
                        'code': row[11],
                        'notes': row[12],
                        'is_system': bool(row[13]),
                        'created_at': row[14] if row[14] else '',
                        'updated_at': row[15] if row[15] else '',
                        'product_count': row[16] if row[16] is not None else 0
                    }
                    categories.append(cat_dict)
                
                result = (categories, total)
                self._set_cache(cache_key, result)
                return result
                
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return [], 0

    def get_category(self, category_id: int) -> Optional[Dict]:
        """Get a single category by ID"""
        if not category_id:
            return None
            
        self._ensure_category_columns()
        
        cache_key = f"category_{category_id}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        c.id,
                        c.name,
                        COALESCE(c.slug, '') as slug,
                        COALESCE(c.description, '') as description,
                        c.parent_id,
                        p.name as parent_name,
                        COALESCE(c.sort_order, 0) as sort_order,
                        COALESCE(c.color, '#6c5ce7') as color,
                        COALESCE(c.icon, '📁') as icon,
                        c.image_path as image,
                        COALESCE(c.status, 'active') as status,
                        COALESCE(c.code, '') as code,
                        COALESCE(c.notes, '') as notes,
                        COALESCE(c.is_system, 0) as is_system,
                        COALESCE(CAST(c.created_at AS TEXT), '') as created_at,
                        COALESCE(CAST(c.updated_at AS TEXT), '') as updated_at,
                        COALESCE(s.product_count, 0) as product_count
                    FROM categories c
                    LEFT JOIN categories p ON c.parent_id = p.id
                    LEFT JOIN category_stats s ON c.id = s.category_id
                    WHERE c.id = ?
                """
                
                cursor.execute(query, (category_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                cat_dict = {
                    'id': row[0],
                    'name': row[1],
                    'slug': row[2],
                    'description': row[3],
                    'parent_id': row[4],
                    'parent_name': row[5],
                    'sort_order': row[6],
                    'color': row[7],
                    'icon': row[8],
                    'image': row[9],
                    'status': row[10],
                    'code': row[11],
                    'notes': row[12],
                    'is_system': bool(row[13]),
                    'created_at': row[14] if row[14] else '',
                    'updated_at': row[15] if row[15] else '',
                    'product_count': row[16] if row[16] is not None else 0
                }
                
                self._set_cache(cache_key, cat_dict)
                return cat_dict
                
        except Exception as e:
            logger.error(f"Failed to get category {category_id}: {e}")
            return None
    
    def get_category_by_slug(self, slug: str) -> Optional[Dict]:
        """Get a category by slug"""
        self._ensure_category_columns()
        
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM categories WHERE slug = ?", (slug,))
                row = cursor.fetchone()
                if row:
                    return self.get_category(row[0])
                return None
        except Exception as e:
            logger.error(f"Failed to get category by slug: {e}")
            return None
    
    def create_category(self, data: Dict) -> Dict:
        """Create a new category"""
        self._ensure_category_columns()
        
        if not data.get('name'):
            raise ValueError("Category name is required")
        
        slug = data.get('slug')
        if not slug:
            slug = generate_slug(data['name'])
        else:
            slug = generate_slug(slug)
        
        existing = self._find_by_slug_or_code(slug, data.get('code'))
        if existing:
            raise ValueError(f"Category with slug '{slug}' already exists")
        
        code = data.get('code')
        if code:
            existing = self._find_by_slug_or_code(None, code)
            if existing:
                raise ValueError(f"Category with code '{code}' already exists")
        
        with DBContext() as conn:
            cursor = conn.cursor()
            
            if not code:
                cursor.execute("SELECT COUNT(*) FROM categories")
                count = cursor.fetchone()[0]
                code = f"CAT-{count + 1:04d}"
            
            cursor.execute("""
                INSERT INTO categories (
                    name, slug, description, parent_id, sort_order,
                    color, icon, image_path, status, code, notes,
                    is_system, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                data['name'],
                slug,
                data.get('description', ''),
                data.get('parent_id'),
                data.get('sort_order', 0),
                data.get('color', '#6c5ce7'),
                data.get('icon', '📁'),
                data.get('image'),
                data.get('status', 'active'),
                code,
                data.get('notes', ''),
                0
            ))
            
            category_id = cursor.lastrowid
            conn.commit()
            
            self._update_category_stats(category_id)
            self._log_activity(category_id, 'create', f"Created category: {data['name']}")
            self._clear_cache()
            
            return self.get_category(category_id)
    
    def update_category(self, category_id: int, data: Dict) -> Dict:
        """Update an existing category"""
        self._ensure_category_columns()
        
        existing = self.get_category(category_id)
        if not existing:
            raise ValueError(f"Category with ID {category_id} not found")
        
        if existing['is_system']:
            protected_fields = ['name', 'slug', 'status']
            for field in protected_fields:
                if field in data and data[field] != existing.get(field):
                    raise ValueError(f"Cannot change '{field}' of system category")
        
        if 'name' in data and data['name'] != existing['name']:
            new_slug = generate_slug(data['name'])
            if new_slug != existing['slug']:
                duplicate = self._find_by_slug_or_code(new_slug)
                if duplicate and duplicate['id'] != category_id:
                    raise ValueError(f"Category with slug '{new_slug}' already exists")
            data['slug'] = new_slug
        
        if 'code' in data and data['code'] != existing.get('code'):
            duplicate = self._find_by_slug_or_code(None, data['code'])
            if duplicate and duplicate['id'] != category_id:
                raise ValueError(f"Category with code '{data['code']}' already exists")
        
        if 'parent_id' in data and data['parent_id']:
            if data['parent_id'] == category_id:
                raise ValueError("Cannot set a category as its own parent")
            if self._is_circular_reference(category_id, data['parent_id']):
                raise ValueError("Circular parent reference detected")
        
        with DBContext() as conn:
            cursor = conn.cursor()
            
            set_clauses = []
            params = []
            
            updateable_fields = [
                'name', 'slug', 'description', 'parent_id', 'sort_order',
                'color', 'icon', 'image', 'status', 'code', 'notes'
            ]
            
            for field in updateable_fields:
                if field in data:
                    set_clauses.append(f"{field} = ?")
                    params.append(data[field])
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            
            if not set_clauses:
                return existing
            
            query = f"UPDATE categories SET {', '.join(set_clauses)} WHERE id = ?"
            params.append(category_id)
            
            cursor.execute(query, params)
            conn.commit()
            
            self._update_category_stats(category_id)
            self._log_activity(category_id, 'update', f"Updated category: {data.get('name', existing['name'])}")
            self._clear_cache()
            
            return self.get_category(category_id)
    
    def delete_category(self, category_id: int, force: bool = False) -> bool:
        """Delete a category"""
        self._ensure_category_columns()
        
        category = self.get_category(category_id)
        if not category:
            raise ValueError(f"Category with ID {category_id} not found")
        
        if category['is_system']:
            raise ValueError("Cannot delete system category")
        
        if category['product_count'] > 0 and not force:
            raise ValueError(f"Category has {category['product_count']} products. Use force=True to delete and unassign products")
        
        try:
            self._log_activity(category_id, 'delete', f"Deleted category: {category['name']}")
        except Exception as e:
            logger.warning(f"Could not log delete activity: {e}")
        
        with DBContext() as conn:
            cursor = conn.cursor()
            
            if force:
                # ✅ Update products with category_id = None
                cursor.execute("UPDATE products SET category_id = NULL WHERE category_id = ?", (category_id,))
            
            cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            cursor.execute("DELETE FROM category_stats WHERE category_id = ?", (category_id,))
            
            conn.commit()
        
        self._clear_cache()
        return True
    
    def delete_categories(self, category_ids: List[int]) -> Tuple[int, List[Dict]]:
        """Delete multiple categories"""
        if not category_ids:
            return 0, []
        
        deleted_count = 0
        failed = []
        
        for category_id in category_ids:
            try:
                self.delete_category(category_id, force=True)
                deleted_count += 1
            except Exception as e:
                failed.append({
                    'id': category_id,
                    'reason': str(e)
                })
        
        return deleted_count, failed
    
    def merge_categories(self, source_ids: List[int], target_id: int, delete_sources: bool = True) -> Dict:
        """Merge categories"""
        result = {'success': False, 'merged': 0, 'failed': []}
        if not source_ids or not target_id:
            return result
            
        if target_id in source_ids:
            raise ValueError("Target category cannot be one of the source categories.")
        
        self._ensure_category_columns()
        
        target = self.get_category(target_id)
        if not target:
            raise ValueError(f"Target category not found")
        
        if target['is_system']:
            raise ValueError("Cannot merge into system category")
        
        result = {
            'merged': [],
            'failed': [],
            'updated_products': 0,
            'updated_children': 0
        }
        
        with DBContext() as conn:
            cursor = conn.cursor()
            
            for source_id in source_ids:
                source = self.get_category(source_id)
                if not source:
                    result['failed'].append({'id': source_id, 'reason': 'Not found'})
                    continue
                
                if source['is_system']:
                    result['failed'].append({'id': source_id, 'reason': 'Cannot merge system category'})
                    continue
                
                try:
                    # ✅ Update products with category_id
                    cursor.execute("""
                        UPDATE products 
                        SET category_id = ? 
                        WHERE category_id = ?
                    """, (target_id, source_id))
                    result['updated_products'] += cursor.rowcount
                    
                    cursor.execute("""
                        UPDATE categories 
                        SET parent_id = ? 
                        WHERE parent_id = ?
                    """, (target_id, source_id))
                    result['updated_children'] += cursor.rowcount
                    
                    if delete_sources:
                        cursor.execute("DELETE FROM categories WHERE id = ?", (source_id,))
                        cursor.execute("DELETE FROM category_stats WHERE category_id = ?", (source_id,))
                    
                    result['merged'].append({
                        'id': source_id,
                        'name': source['name'],
                        'product_count': source['product_count']
                    })
                    
                except Exception as e:
                    result['failed'].append({
                        'id': source_id,
                        'name': source['name'],
                        'reason': str(e)
                    })
            
            self._update_category_stats(target_id)
            conn.commit()
            
            merged_names = ', '.join([str(s['name']) for s in result['merged']])
            try:
                self._log_activity(
                    target_id, 
                    'merge', 
                    f"Merged categories: {merged_names} into {target['name']}"
                )
            except Exception as e:
                logger.warning(f"Could not log merge activity: {e}")
            
            self._clear_cache()
            result['success'] = True
            return result
    
    # ==================== Statistics ====================
    
    def get_statistics(self) -> Dict:
        """Get category statistics"""
        self._ensure_category_columns()
        
        cache_key = "category_stats_total"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='category_stats'")
                stats_exists = cursor.fetchone() is not None
                
                if stats_exists:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                            SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive,
                            SUM(CASE WHEN status = 'hidden' THEN 1 ELSE 0 END) as hidden,
                            COUNT(CASE WHEN parent_id IS NULL THEN 1 END) as root,
                            COALESCE(SUM(s.product_count), 0) as total_products
                        FROM categories c
                        LEFT JOIN category_stats s ON c.id = s.category_id
                    """)
                else:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                            SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive,
                            SUM(CASE WHEN status = 'hidden' THEN 1 ELSE 0 END) as hidden,
                            COUNT(CASE WHEN parent_id IS NULL THEN 1 END) as root,
                            0 as total_products
                        FROM categories c
                    """)
                
                row = cursor.fetchone()
                stats = {
                    'total': row[0] or 0,
                    'active': row[1] or 0,
                    'inactive': row[2] or 0,
                    'hidden': row[3] or 0,
                    'root': row[4] or 0,
                    'total_products': row[5] or 0
                }
                
                self._set_cache(cache_key, stats)
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {'total': 0, 'active': 0, 'inactive': 0, 'hidden': 0, 'root': 0, 'total_products': 0}
    
    def _update_category_stats(self, category_id: int):
        """Update product count for a category using category_id"""
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Ensure category_stats table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_stats (
                        category_id INTEGER PRIMARY KEY,
                        product_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
                
                # ✅ Count products using category_id
                cursor.execute("""
                    SELECT COUNT(*) FROM products 
                    WHERE category_id = ? AND (sold_by IS NULL OR sold_by != 'Service')
                """, (category_id,))
                product_count = cursor.fetchone()[0]
                
                # ✅ SQLite compatible UPSERT
                cursor.execute("""
                    INSERT INTO category_stats (category_id, product_count, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(category_id) DO UPDATE SET 
                        product_count = excluded.product_count,
                        last_updated = CURRENT_TIMESTAMP
                """, (category_id, product_count))
                
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Could not update category stats: {e}")
    
    def update_all_category_stats(self):
        """Update stats for all categories using category_id"""
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                # Ensure category_stats table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_stats (
                        category_id INTEGER PRIMARY KEY,
                        product_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
                
                # Get all categories
                cursor.execute("SELECT id FROM categories")
                categories = cursor.fetchall()
                
                updated_count = 0
                for (cat_id,) in categories:
                    # ✅ Count products using category_id
                    cursor.execute("""
                        SELECT COUNT(*) FROM products 
                        WHERE category_id = ? AND (sold_by IS NULL OR sold_by != 'Service')
                    """, (cat_id,))
                    product_count = cursor.fetchone()[0]
                    
                    # ✅ SQLite compatible UPSERT
                    cursor.execute("""
                        INSERT INTO category_stats (category_id, product_count, last_updated)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(category_id) DO UPDATE SET 
                            product_count = excluded.product_count,
                            last_updated = CURRENT_TIMESTAMP
                    """, (cat_id, product_count))
                    updated_count += 1
                
                conn.commit()
                self._clear_cache()
                logger.info(f"✅ All category stats updated - {updated_count} categories")
                
        except Exception as e:
            logger.error(f"Failed to update all category stats: {e}")
    
    # ==================== Helper Methods ====================
    
    def _find_by_slug_or_code(self, slug: Optional[str] = None, code: Optional[str] = None) -> Optional[Dict]:
        """Find category by slug or code"""
        self._ensure_category_columns()
        
        if not slug and not code:
            return None
        
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                if slug and code:
                    cursor.execute(
                        "SELECT id FROM categories WHERE slug = ? OR code = ?",
                        (slug, code)
                    )
                elif slug:
                    cursor.execute(
                        "SELECT id FROM categories WHERE slug = ?",
                        (slug,)
                    )
                else:
                    cursor.execute(
                        "SELECT id FROM categories WHERE code = ?",
                        (code,)
                    )
                
                row = cursor.fetchone()
                if row:
                    return self.get_category(row[0])
                return None
                
        except Exception as e:
            logger.error(f"Failed to find category: {e}")
            return None
    
    def _is_circular_reference(self, category_id: int, parent_id: int) -> bool:
        """Check if adding parent would create circular reference"""
        current = parent_id
        visited = set()
        
        while current is not None:
            if current == category_id:
                return True
            if current in visited:
                return True
            visited.add(current)
            
            try:
                with DBContext() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT parent_id FROM categories WHERE id = ?", (current,))
                    row = cursor.fetchone()
                    current = row[0] if row else None
            except Exception:
                return False
        
        return False
    
    def _log_activity(self, category_id: int, action: str, details: str):
        """Log category activity."""
        try:
            with DBContext() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_id INTEGER,
                        action TEXT NOT NULL,
                        details TEXT,
                        user_id INTEGER,
                        username TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
                    )
                """)
                conn.commit()
                
                cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,))
                if not cursor.fetchone():
                    return
                
                cursor.execute("""
                    INSERT INTO category_activity_log (category_id, action, details)
                    VALUES (?, ?, ?)
                """, (category_id, action, details))
                conn.commit()
                
        except sqlite3.IntegrityError as e:
            if "FOREIGN KEY" in str(e):
                logger.debug(f"Foreign key constraint failed for category {category_id}")
            else:
                logger.error(f"Failed to log category activity: {e}")
        except Exception as e:
            logger.error(f"Failed to log category activity: {e}")
    
    # ==================== Import/Export ====================
    
    def export_categories(self, format: str = 'json') -> str:
        """Export categories to JSON or CSV format"""
        self._ensure_category_columns()
        
        categories, _ = self.get_categories()
        
        if format == 'json':
            data = {
                'exported_at': datetime.now().isoformat(),
                'total': len(categories),
                'categories': categories
            }
            return json.dumps(data, indent=2, default=str)
        
        elif format == 'csv':
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            writer.writerow([
                'id', 'name', 'slug', 'description', 'parent_id',
                'sort_order', 'color', 'icon', 'image', 'status',
                'code', 'notes', 'product_count'
            ])
            
            for cat in categories:
                writer.writerow([
                    cat['id'],
                    cat['name'],
                    cat['slug'],
                    cat['description'],
                    cat['parent_id'],
                    cat['sort_order'],
                    cat['color'],
                    cat['icon'],
                    cat['image'],
                    cat['status'],
                    cat['code'],
                    cat['notes'],
                    cat['product_count']
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_categories(self, data: str, format: str = 'json') -> Dict:
        """Import categories from JSON or CSV"""
        self._ensure_category_columns()
        
        result = {
            'imported': 0,
            'updated': 0,
            'failed': [],
            'warnings': []
        }
        
        if format == 'json':
            import json
            parsed = json.loads(data)
            categories = parsed.get('categories', [])
            
            for cat_data in categories:
                try:
                    existing = None
                    if 'id' in cat_data:
                        existing = self.get_category(cat_data['id'])
                    
                    import_data = {k: v for k, v in cat_data.items() 
                                 if k not in ['id', 'created_at', 'updated_at', 'product_count', 'is_system']}
                    
                    if existing:
                        self.update_category(existing['id'], import_data)
                        result['updated'] += 1
                    else:
                        self.create_category(import_data)
                        result['imported'] += 1
                        
                except Exception as e:
                    result['failed'].append({
                        'name': cat_data.get('name', 'Unknown'),
                        'error': str(e)
                    })
        
        elif format == 'csv':
            import csv
            from io import StringIO
            
            reader = csv.DictReader(StringIO(data))
            for row in reader:
                try:
                    if row.get('sort_order'):
                        row['sort_order'] = int(row['sort_order'])
                    if row.get('parent_id'):
                        row['parent_id'] = int(row['parent_id']) if row['parent_id'] else None
                    
                    existing = self._find_by_slug_or_code(row.get('slug'), row.get('code'))
                    
                    import_data = {k: v for k, v in row.items() 
                                 if k not in ['id', 'created_at', 'updated_at', 'product_count'] and v}
                    
                    if existing:
                        self.update_category(existing['id'], import_data)
                        result['updated'] += 1
                    else:
                        self.create_category(import_data)
                        result['imported'] += 1
                        
                except Exception as e:
                    result['failed'].append({
                        'name': row.get('name', 'Unknown'),
                        'error': str(e)
                    })
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self._clear_cache()
        return result
