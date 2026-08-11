# fix_database.py
"""
Direct database fix script - Run this to fix missing columns
"""

import sqlite3
import os
import sys
from datetime import datetime


def fix_database():
    """Fix missing columns in database"""
    
    db_path = "database/pos.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    print(f"📂 Database found: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if categories table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
        if not cursor.fetchone():
            print("❌ Categories table does not exist")
            conn.close()
            return False
        
        # Check columns
        cursor.execute("PRAGMA table_info(categories)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print(f"📋 Existing columns: {', '.join(columns)}")
        
        # Add missing columns
        columns_to_add = {
            'slug': 'TEXT UNIQUE',
            'parent_id': 'INTEGER',
            'sort_order': 'INTEGER DEFAULT 0',
            'color': 'TEXT DEFAULT "#6c5ce7"',
            'icon': 'TEXT DEFAULT "📁"',
            'image': 'TEXT',
            'status': 'TEXT DEFAULT "active"',
            'code': 'TEXT',
            'notes': 'TEXT',
            'is_system': 'INTEGER DEFAULT 0',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        for col, col_type in columns_to_add.items():
            if col not in columns:
                try:
                    print(f"➕ Adding column: {col}")
                    cursor.execute(f"ALTER TABLE categories ADD COLUMN {col} {col_type}")
                    conn.commit()
                    print(f"✅ Added column: {col}")
                except Exception as e:
                    print(f"⚠️ Could not add column {col}: {e}")
        
        # Update slugs for existing categories
        cursor.execute("SELECT id, name FROM categories WHERE slug IS NULL")
        rows = cursor.fetchall()
        
        if rows:
            print(f"📝 Updating {len(rows)} categories with slugs...")
            
            for cat_id, name in rows:
                # Generate slug from name
                slug = name.lower().strip()
                slug = slug.replace(' ', '-')
                slug = slug.replace('(', '')
                slug = slug.replace(')', '')
                slug = slug.replace('/', '-')
                slug = slug.replace('&', 'and')
                
                # Check for duplicates
                cursor.execute("SELECT id FROM categories WHERE slug = ?", (slug,))
                if cursor.fetchone():
                    slug = f"{slug}-{cat_id}"
                
                cursor.execute(
                    "UPDATE categories SET slug = ? WHERE id = ?",
                    (slug, cat_id)
                )
            
            conn.commit()
            print(f"✅ Updated slugs for {len(rows)} categories")
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id)",
            "CREATE INDEX IF NOT EXISTS idx_categories_status ON categories(status)",
            "CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug)",
            "CREATE INDEX IF NOT EXISTS idx_categories_sort ON categories(sort_order)",
            "CREATE INDEX IF NOT EXISTS idx_categories_code ON categories(code)"
        ]
        
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
                conn.commit()
                print(f"✅ Created index: {idx_sql.split('ON')[1].strip()}")
            except Exception as e:
                print(f"⚠️ Could not create index: {e}")
        
        # Verify
        cursor.execute("PRAGMA table_info(categories)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"✅ Final columns: {', '.join(columns)}")
        
        conn.close()
        print("✅ Database fix completed!")
        return True
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("ZAY POS Database Fix Tool")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = fix_database()
    
    if success:
        print("\n✅ Database fixed successfully!")
        print("You can now restart the application.")
    else:
        print("\n❌ Database fix failed.")
        print("Please contact support for assistance.")
    
    input("\nPress Enter to exit...")