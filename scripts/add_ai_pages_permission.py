# scripts/add_ai_pages_permission.py
"""
Add AI Pages permission to database
Run this script once to add the permission
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import connect_db
from loguru import logger


def add_ai_pages_permission():
    """Add AI Pages permission to database"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # Check if settings table exists and add permission
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='settings'
        """)
        if cursor.fetchone():
            # Add show_ai_pages setting
            cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value) 
                VALUES ('show_ai_pages', '1')
            """)
            logger.info("Added show_ai_pages setting")
        
        # Check if role_permissions table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='role_permissions'
        """)
        if cursor.fetchone():
            # Add permissions for admin and manager
            cursor.execute("""
                INSERT OR IGNORE INTO role_permissions (role, permission) 
                VALUES ('admin', 'view_ai_pages')
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO role_permissions (role, permission) 
                VALUES ('manager', 'view_ai_pages')
            """)
            logger.info("Added view_ai_pages permission to admin and manager")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ AI Pages permission added successfully!")
        
    except Exception as e:
        logger.error(f"Error adding permission: {e}")


if __name__ == "__main__":
    add_ai_pages_permission()