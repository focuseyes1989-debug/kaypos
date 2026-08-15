# models/database/__init__.py

"""
Database module with connection pooling and ORM-like functionality.
"""

import sqlite3
import os
from typing import Optional, List, Tuple, Any
from loguru import logger
from models.database.auto_fix import run_auto_fix, fix_missing_category_columns
from utils.db_compat import is_postgres_backend

# Connection
from models.database.connection import connect_db, DBContext, release_connection, close_all_connections
from models.database.pool import ConnectionPool, get_pool_stats

# Queries
from models.database.queries import (
    get_products, get_product, add_product, update_product, delete_product,
    get_sales, get_sale, add_sale, update_sale, delete_sale, get_sale_items,
    get_customers, get_customer, add_customer, update_customer, delete_customer,
    get_expenses, get_expense, add_expense, update_expense, delete_expense,
    get_settings, update_setting, get_setting
)

# Tables
from models.database.tables import create_tables, ensure_schema

# Maintenance
from models.database.maintenance import (
    optimize_database, vacuum_database, get_database_stats,
    rebuild_indexes, backup_database, expire_old_points, 
    expire_points_for_customer, check_and_recover
)

# Migrations
from models.database.migrations import (
    run_migrations, 
    rollback_to_version, 
    get_migration_status, 
    fix_missing_columns,
    check_and_run_migrations,
    get_app_version,
    set_app_version
)

# Indexes
from models.database.indexes import (
    create_optimized_indexes,
    drop_optimized_indexes,
    analyze_query_performance,
    create_suggested_indexes,
    get_index_usage_stats
)

# Health
from models.database.health import check_database_health

# Auto Maintenance
from models.database.auto_maintenance import (
    start_auto_maintenance,
    stop_auto_maintenance
)

# Recovery
from models.database.recovery import DatabaseRecovery


# ============================================================================
# 🔥 SAFE DATABASE INITIALIZATION
# ============================================================================

def safe_initialize_database() -> bool:
    """
    Safely initialize database with error handling
    
    Returns:
        bool: True if successful
    """
    try:
        logger.info("Initializing database...")
        if is_postgres_backend():
            return safe_initialize_postgres_app_database()
        
        # Check if database exists and is accessible
        db_path = "database/pos.db"
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        # Try to create tables
        try:
            create_tables()
            logger.info("✅ Database tables created/verified")
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            
            # Try to fix missing columns
            try:
                fix_missing_columns()
                logger.info("✅ Fixed missing columns")
            except Exception as e2:
                logger.error(f"❌ Failed to fix columns: {e2}")
                
                # Try emergency recovery
                try:
                    recovery = DatabaseRecovery()
                    success, message = recovery.auto_recover()
                    if success:
                        logger.info(f"✅ {message}")
                        return True
                except Exception as e3:
                    logger.error(f"❌ Emergency recovery failed: {e3}")
                
                return False
        
        # ✅ Update category stats after tables are created
        if False:
            logger.info("✅ Category stats updated after initialization")
        if False:
            logger.warning("Category stats update deferred")
        
        # ✅ RUN AUTO-FIX for category columns
        if False:
            logger.info("✅ Auto-fix completed")
        if False:
            logger.warning("Auto-fix deferred")
        
        # ✅ Check and run migrations
        try:
            check_and_run_migrations()
        except Exception as e:
            logger.warning(f"Migration warning: {e}")

        try:
            from models.database.stock_audit import clamp_all_location_stock_to_master
            fixed = clamp_all_location_stock_to_master("Startup")
            if fixed:
                logger.info(f"Clamped stale location stock for {len(fixed)} product(s)")
        except Exception as e:
            logger.warning(f"Could not clamp stale location stock: {e}")
        
        # ✅ AUTO-UPDATE: AI Pages Permission
        try:
            from utils.permissions import update_role_permissions_in_db
            update_role_permissions_in_db()
            logger.info("✅ AI Pages permission auto-updated")
        except Exception as e:
            logger.warning(f"Could not auto-update AI Pages permission: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


def safe_initialize_postgres_app_database() -> bool:
    """Initialize the PostgreSQL app schema.

    SQLite remains supported, but PostgreSQL mode should create all core POS
    tables used by retail, inventory, credit, expenses, and Restaurant Mode.
    """
    try:
        from models.database.postgres_schema import ensure_postgres_app_schema

        with DBContext() as conn:
            cursor = conn.cursor()
            ensure_postgres_app_schema(cursor)
            conn.commit()
        try:
            from models.database.stock_audit import clamp_all_location_stock_to_master
            fixed = clamp_all_location_stock_to_master("Startup")
            if fixed:
                logger.info(f"Clamped stale PostgreSQL location stock for {len(fixed)} product(s)")
        except Exception as exc:
            logger.warning(f"Could not clamp PostgreSQL location stock: {exc}")
        logger.info("PostgreSQL app schema created/verified")
        return True
    except Exception as exc:
        logger.error(f"PostgreSQL schema initialization failed: {exc}")
        return False


def safe_initialize_postgres_pilot_database() -> bool:
    """Backward-compatible wrapper for older Restaurant smoke-test code."""
    return safe_initialize_postgres_app_database()


def initialize_database_with_fallback():
    """
    Initialize database with fallback options
    """
    # First attempt
    if safe_initialize_database():
        return True
    
    # Second attempt: Try to fix schema
    try:
        from models.database.connection import DBContext
        
        with DBContext() as conn:
            cursor = conn.cursor()
            
            # Check if categories table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
            if cursor.fetchone():
                # Check columns
                cursor.execute("PRAGMA table_info(categories)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'slug' not in columns:
                    logger.info("Adding missing slug column...")
                    cursor.execute("ALTER TABLE categories ADD COLUMN slug TEXT UNIQUE")
                    conn.commit()
                    
                    # Update slugs
                    cursor.execute("""
                        UPDATE categories SET 
                        slug = LOWER(REPLACE(REPLACE(REPLACE(REPLACE(
                            TRIM(name), ' ', '-'), '(', ''), ')', ''), '/', '-'))
                        WHERE slug IS NULL
                    """)
                    conn.commit()
                    
                    # Handle duplicates
                    cursor.execute("""
                        UPDATE categories SET slug = slug || '-' || id 
                        WHERE slug IN (SELECT slug FROM categories GROUP BY slug HAVING COUNT(*) > 1)
                    """)
                    conn.commit()
                    
                    logger.info("✅ Added slug column and updated data")
                    return True
    except Exception as e:
        logger.error(f"❌ Fallback fix failed: {e}")
    
    return False


# Backward compatibility
def get_current_schema_version():
    """Get current database schema version (backward compatibility)."""
    status = get_migration_status()
    return status['current_version'] if status else "0.0.0"


__all__ = [
    # Connection
    'connect_db', 'DBContext', 'release_connection', 'close_all_connections',
    'ConnectionPool', 'get_pool_stats',
    
    # Queries
    'get_products', 'get_product', 'add_product', 'update_product', 'delete_product',
    'get_sales', 'get_sale', 'add_sale', 'update_sale', 'delete_sale', 'get_sale_items',
    'get_customers', 'get_customer', 'add_customer', 'update_customer', 'delete_customer',
    'get_expenses', 'get_expense', 'add_expense', 'update_expense', 'delete_expense',
    'get_settings', 'update_setting', 'get_setting',
    
    # Tables
    'create_tables', 'ensure_schema',
    
    # Maintenance
    'optimize_database', 'vacuum_database', 'get_database_stats',
    'rebuild_indexes', 'backup_database',
    'expire_old_points', 'expire_points_for_customer', 'check_and_recover',
    
    # Migrations
    'run_migrations', 'rollback_to_version', 'get_migration_status', 
    'fix_missing_columns', 'get_current_schema_version',
    'check_and_run_migrations',
    'get_app_version',
    'set_app_version',
    
    # Indexes
    'create_optimized_indexes', 'drop_optimized_indexes',
    'analyze_query_performance', 'create_suggested_indexes',
    'get_index_usage_stats',
    
    # Health
    'check_database_health',
    
    # Auto Maintenance
    'start_auto_maintenance', 'stop_auto_maintenance',
    
    # 🔥 Added
    'DatabaseManager',
    'safe_initialize_database',
    'safe_initialize_postgres_app_database',
    'safe_initialize_postgres_pilot_database',
    'initialize_database_with_fallback',
    'DatabaseRecovery',
    
    'run_auto_fix',
    'fix_missing_category_columns',
]
