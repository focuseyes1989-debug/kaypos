# models/database/connection.py
"""
Database connection management with pooling.
"""

import os
import sys
import sqlite3
from loguru import logger
import models.database.pool as pool_module
from utils.db_compat import database_url, database_urls, is_postgres_backend

# 🔥 Dynamic database path
def get_db_path():
    """Get the correct database path."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    db_dir = os.path.join(base_dir, 'database')
    
    try:
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"✅ Database directory: {db_dir}")
        
        # Test write permissions
        test_file = os.path.join(db_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.debug("✅ Database directory is writable")
        
    except Exception as e:
        logger.error(f"❌ Failed to create database directory: {e}")
        # Fallback to AppData
        appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ZAY_POS')
        os.makedirs(appdata_dir, exist_ok=True)
        db_dir = appdata_dir
        logger.info(f"✅ Using fallback database directory: {db_dir}")
    
    db_path = os.path.join(db_dir, 'pos.db')
    logger.info(f"📂 Database path: {db_path}")
    
    return db_path

DB_NAME = get_db_path()

def connect_db():
    """
    Return a pooled connection.
    """
    try:
        # ✅ Ensure pool is initialized
        return pool_module.get_pool().get_connection()
    except Exception as e:
        logger.error(f"❌ Failed to get database connection: {e}")
        # 🔥 Try direct connection as fallback
        try:
            logger.info("Attempting direct connection...")
            if is_postgres_backend():
                from models.database.postgres_adapter import connect_postgres

                urls = database_urls()
                if not urls:
                    raise RuntimeError(
                        "ZAY_POS_DB_BACKEND=postgres requires ZAY_POS_DATABASE_URL or DATABASE_URL."
                    )
                last_error = None
                for index, url in enumerate(urls):
                    try:
                        conn = connect_postgres(url)
                        conn.execute("SELECT 1").fetchone()
                        logger.info(
                            "Created direct PostgreSQL connection"
                            + (" to fallback database" if index else "")
                        )
                        return conn
                    except Exception as exc:
                        last_error = exc
                        logger.warning(f"Direct PostgreSQL connection attempt failed: {exc}")
                raise last_error
            conn = sqlite3.connect(DB_NAME, timeout=60, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout=60000")
            logger.info("✅ Created direct connection (fallback)")
            return conn
        except Exception as e2:
            logger.error(f"❌ Fallback connection also failed: {e2}")
            raise


def close_all_connections():
    """Close all pooled database connections."""
    if pool_module._pool:
        pool_module._pool.close_all()


def release_connection(conn):
    """Explicitly return a connection to the pool."""
    if hasattr(conn, 'close'):
        conn.close()


class DBContext:
    """Context manager for database connections."""
    def __enter__(self):
        self.conn = connect_db()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


def get_connection_with_health_check():
    """Get a healthy connection."""
    from models.database.pool import is_connection_healthy
    conn = connect_db()
    if not is_connection_healthy(conn):
        conn.close()
        return connect_db()
    return conn


def verify_database_integrity():
    """Verify database integrity."""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        if is_postgres_backend():
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            return bool(result)
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        return result[0] == 'ok' if result else False
    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        return False
