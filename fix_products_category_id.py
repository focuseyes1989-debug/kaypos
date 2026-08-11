# fix_products_category_id.py
import sqlite3
import os

db_path = "database/pos.db"

def fix_products_category_id():
    """Fix products table by adding category_id column and updating it."""
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Check if category_id column exists
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'category_id' not in columns:
            print("Adding category_id column to products table...")
            cursor.execute("ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL")
            conn.commit()
            print("✅ Added category_id column")
        else:
            print("✅ category_id column already exists")
        
        # 2. Update category_id from old category column
        cursor.execute("""
            UPDATE products 
            SET category_id = (
                SELECT id FROM categories 
                WHERE LOWER(categories.name) = LOWER(products.category) 
                OR categories.slug = products.category
                LIMIT 1
            )
            WHERE category_id IS NULL AND category IS NOT NULL AND category != ''
        """)
        conn.commit()
        updated = cursor.rowcount
        print(f"✅ Updated {updated} products with category_id from old category column")
        
        # 3. Update category_stats for all categories
        cursor.execute("SELECT id FROM categories")
        categories = cursor.fetchall()
        
        for (cat_id,) in categories:
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE category_id = ? AND (sold_by IS NULL OR sold_by != 'Service')
            """, (cat_id,))
            count = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO category_stats (category_id, product_count, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(category_id) DO UPDATE SET 
                    product_count = excluded.product_count,
                    last_updated = CURRENT_TIMESTAMP
            """, (cat_id, count))
        
        conn.commit()
        print(f"✅ Updated category_stats for {len(categories)} categories")
        
        # 4. Verify results
        cursor.execute("""
            SELECT 
                c.id,
                c.name,
                COALESCE(s.product_count, 0) as product_count,
                (SELECT COUNT(*) FROM products WHERE category_id = c.id) as actual_count
            FROM categories c
            LEFT JOIN category_stats s ON c.id = s.category_id
            ORDER BY c.name
        """)
        results = cursor.fetchall()
        
        print("\n" + "=" * 60)
        print("CATEGORY PRODUCT COUNTS")
        print("=" * 60)
        for cat_id, name, stats_count, actual_count in results:
            print(f"{name:20} | Stats: {stats_count:3} | Actual: {actual_count:3}")
        print("=" * 60)
        
        conn.close()
        print("\n✅ Fix completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        conn.close()

if __name__ == "__main__":
    fix_products_category_id()