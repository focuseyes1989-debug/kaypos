# models/database/auto_fix.py
"""
Auto database fix for common migration issues.
Runs automatically on application startup.
"""

import sqlite3
import os
import re
from loguru import logger
from models.database.connection import DBContext


def fix_missing_category_columns():
    """
    Fix missing category columns (slug, updated_at, etc.)
    This runs automatically on startup.
    """
    db_path = "database/pos.db"
    
    if not os.path.exists(db_path):
        logger.info("Database not found, skipping auto-fix")
        return False
    
    try:
        with DBContext() as conn:
            cursor = conn.cursor()
            
            # Check if categories table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
            if not cursor.fetchone():
                logger.info("Categories table not found, skipping auto-fix")
                return False
            
            # Get existing columns
            cursor.execute("PRAGMA table_info(categories)")
            existing_cols = [col[1] for col in cursor.fetchall()]
            
            logger.info(f"Categories table columns: {existing_cols}")
            
            fixed_anything = False
            
            # ✅ FIX 1: Add slug column (without UNIQUE constraint)
            if 'slug' not in existing_cols:
                try:
                    logger.info("Adding slug column...")
                    cursor.execute("ALTER TABLE categories ADD COLUMN slug TEXT")
                    conn.commit()
                    logger.info("✅ Added slug column")
                    fixed_anything = True
                except Exception as e:
                    logger.warning(f"Could not add slug column: {e}")
            
            # ✅ FIX 2: Add updated_at column (without DEFAULT)
            if 'updated_at' not in existing_cols:
                try:
                    logger.info("Adding updated_at column...")
                    cursor.execute("ALTER TABLE categories ADD COLUMN updated_at TIMESTAMP")
                    conn.commit()
                    logger.info("✅ Added updated_at column")
                    fixed_anything = True
                except Exception as e:
                    logger.warning(f"Could not add updated_at column: {e}")
            
            # ✅ FIX 3: Add other missing columns
            other_columns = {
                'description': 'TEXT',
                'parent_id': 'INTEGER',
                'sort_order': 'INTEGER DEFAULT 0',
                'color': 'TEXT DEFAULT "#6c5ce7"',
                'icon': 'TEXT DEFAULT "📁"',
                'image': 'TEXT',
                'status': 'TEXT DEFAULT "active"',
                'code': 'TEXT',
                'notes': 'TEXT',
                'is_system': 'INTEGER DEFAULT 0',
                'is_favorite': 'INTEGER DEFAULT 0',
                'group_id': 'INTEGER'
            }
            
            for col, col_type in other_columns.items():
                if col not in existing_cols:
                    try:
                        logger.info(f"Adding column {col}...")
                        cursor.execute(f"ALTER TABLE categories ADD COLUMN {col} {col_type}")
                        conn.commit()
                        logger.info(f"✅ Added column {col}")
                        fixed_anything = True
                    except Exception as e:
                        logger.warning(f"Could not add column {col}: {e}")
            
            # ✅ FIX 4: Update slugs for existing categories
            if 'slug' in existing_cols or 'slug' in [c for c in other_columns.keys()]:
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
                            
                            # Handle duplicates
                            cursor.execute("SELECT id FROM categories WHERE slug = ? AND id != ?", (slug, cat_id))
                            if cursor.fetchone():
                                slug = f"{slug}-{cat_id}"
                            
                            cursor.execute("UPDATE categories SET slug = ? WHERE id = ?", (slug, cat_id))
                        conn.commit()
                        logger.info(f"✅ Updated slugs for {len(rows)} categories")
                        fixed_anything = True
                except Exception as e:
                    logger.warning(f"Could not update slugs: {e}")
            
            # ✅ FIX 5: Create unique index for slug
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_slug_unique ON categories(slug)")
                conn.commit()
                logger.info("✅ Created unique index for slug")
            except Exception as e:
                logger.warning(f"Could not create unique index for slug: {e}")
            
            if fixed_anything:
                logger.info("✅ Database auto-fix completed successfully!")
            else:
                logger.info("ℹ️ No fixes needed - database is up to date")
            
            return True
            
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        return False


def fix_category_activity_log():
    """
    Fix category_activity_log table foreign key constraint.
    """
    try:
        with DBContext() as conn:
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='category_activity_log'")
            if cursor.fetchone():
                # Check foreign key definition
                cursor.execute("PRAGMA foreign_key_list(category_activity_log)")
                fks = cursor.fetchall()
                
                # If foreign key exists with RESTRICT, recreate with SET NULL
                for fk in fks:
                    if fk[2] == 'categories' and fk[3] == 'category_id':
                        if fk[4] != 'SET NULL':
                            logger.info("Recreating category_activity_log with ON DELETE SET NULL...")
                            cursor.execute("DROP TABLE IF EXISTS category_activity_log")
                            cursor.execute("""
                                CREATE TABLE category_activity_log (
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
                            logger.info("✅ Recreated category_activity_log with ON DELETE SET NULL")
                            return True
            else:
                # Create table if not exists
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
                logger.info("✅ Created category_activity_log table")
                return True
            
    except Exception as e:
        logger.warning(f"Could not fix category_activity_log: {e}")
    
    return False


def run_auto_fix():
    """
    Run all auto-fix functions.
    """
    logger.info("=" * 60)
    logger.info("🔧 RUNNING AUTO DATABASE FIX")
    logger.info("=" * 60)
    
    try:
        # Fix category columns
        logger.info("Step 1: Fixing missing category columns...")
        fix_missing_category_columns()
        
        # Fix activity log
        logger.info("Step 2: Fixing category activity log...")
        fix_category_activity_log()
        
        logger.info("=" * 60)
        logger.info("✅ AUTO DATABASE FIX COMPLETED")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        return False