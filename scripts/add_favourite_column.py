# scripts/add_favourite_column.py
"""
Standalone script to add is_favourite column to products table.
Run this if you want to add the column without running full migrations.
"""

import sqlite3
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database.connection import DB_NAME

def add_favourite_column():
    """Add is_favourite column to products table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_favourite' not in columns:
            print("📝 Adding is_favourite column to products table...")
            cursor.execute("ALTER TABLE products ADD COLUMN is_favourite INTEGER DEFAULT 0")
            conn.commit()
            print("✅ Added is_favourite column to products table")
        else:
            print("ℹ️ is_favourite column already exists")
        
        # Create index for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_favourite ON products(is_favourite)")
        conn.commit()
        print("✅ Created index on is_favourite column")
        
    except Exception as e:
        print(f"❌ Error adding column: {e}")
        conn.rollback()
    finally:
        conn.close()

def verify_column():
    """Verify the column was added successfully."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_favourite' in columns:
            print("✅ is_favourite column verified")
            
            # Check data type
            for col in cursor.fetchall():
                if col[1] == 'is_favourite':
                    print(f"   Type: {col[2]}, Default: {col[4]}")
        else:
            print("❌ is_favourite column not found")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("FAVOURITE PRODUCTS MIGRATION")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists(DB_NAME):
        print(f"❌ Database not found: {DB_NAME}")
        sys.exit(1)
    
    add_favourite_column()
    verify_column()
    
    print("\n" + "=" * 50)
    print("Migration completed!")
    print("=" * 50)