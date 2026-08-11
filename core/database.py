# core/database.py
"""
Database initialization and management.
"""

import os
import time
from loguru import logger
from PyQt6.QtWidgets import QMessageBox

from models.database import (
    create_tables,
    check_and_run_migrations,
    get_migration_status,
    get_database_stats,
    optimize_database,
    check_and_recover,
    connect_db,
    safe_initialize_database,
    initialize_database_with_fallback
)
from models.database.recovery import DatabaseRecovery
from models.database.auto_fix import run_auto_fix
from utils.db_compat import database_url, is_postgres_backend


def initialize_database(db_path: str) -> dict:
    """
    Initialize database with comprehensive error handling and recovery.
    
    Returns:
        dict: Database status
    """
    logger.info("=" * 60)
    logger.info("DATABASE INITIALIZATION")
    logger.info("=" * 60)
    
    try:
        if is_postgres_backend():
            logger.info("PostgreSQL backend selected; initializing app schema")
            if not database_url():
                raise RuntimeError("ZAY_POS_DATABASE_URL or DATABASE_URL is required for PostgreSQL backend.")
            if not safe_initialize_database():
                raise RuntimeError("PostgreSQL schema initialization failed")

            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            return {
                "backend": "postgres",
                "mode": "postgres_app",
                "current_version": "postgres-app",
                "applied": [],
                "pending": [],
            }

        db_dir = os.path.dirname(db_path)
        
        # Ensure directory exists
        try:
            os.makedirs(db_dir, exist_ok=True)
            test_file = os.path.join(db_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"✅ Database directory is writable: {os.path.abspath(db_dir)}")
        except Exception as e:
            logger.error(f"❌ Database directory not writable: {e}")
            appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ZAY_POS')
            os.makedirs(appdata_dir, exist_ok=True)
            db_dir = appdata_dir
            db_path = os.path.join(db_dir, 'pos.db')
            logger.info(f"✅ Using fallback database directory: {db_dir}")
        
        is_new_db = not os.path.exists(db_path)
        if is_new_db:
            logger.info("📝 New database detected. Creating initial database...")
        else:
            logger.info(f"📂 Existing database found: {db_path}")
        
        # Step 1: Safe initialization
        logger.info("Step 1: Attempting safe database initialization...")
        try:
            if safe_initialize_database():
                logger.info("✅ Safe initialization successful")
            else:
                logger.warning("Safe initialization failed, trying fallback...")
                if initialize_database_with_fallback():
                    logger.info("✅ Fallback initialization successful")
                else:
                    raise RuntimeError("All initialization methods failed")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Initialization failed: {error_msg}")
            
            # Try auto-fix
            logger.info("🔧 Running auto-fix...")
            if run_auto_fix():
                logger.info("✅ Auto-fix completed. Retrying initialization...")
                if initialize_database_with_fallback():
                    logger.info("✅ Database initialized after auto-fix")
                else:
                    raise RuntimeError("Database initialization failed after auto-fix")
            else:
                raise
        
        # Step 2: Test connection
        logger.info("Step 2: Testing database connection...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                conn.close()
                logger.info("✅ Database connection successful")
                break
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise RuntimeError(f"Database connection failed: {e}")
        
        # Step 3: Create tables
        logger.info("Step 3: Creating/verifying database tables...")
        create_tables()
        logger.info("✅ Database tables created/verified.")
        
        # Step 4: Run migrations
        logger.info("Step 4: Checking for pending migrations...")
        try:
            check_and_run_migrations()
            logger.info("✅ Migrations check completed.")
        except Exception as e:
            logger.error(f"❌ MIGRATION FAILED: {e}")
            logger.exception(e)
            raise RuntimeError(f"Database migration failed: {e}")
        
        # ============================================================
        # 🔥 STEP 4.5: AUTO-UPDATE AI PAGES PERMISSION
        # ============================================================
        logger.info("Step 4.5: Checking AI Pages permission...")
        try:
            from utils.permissions import update_role_permissions_in_db
            update_role_permissions_in_db()
            logger.info("✅ AI Pages permission auto-updated successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not auto-update AI Pages permission: {e}")
            # Don't raise error - app should still work
        
        # Step 5: Get status
        logger.info("Step 5: Getting database status...")
        status = None
        try:
            status = get_migration_status()
            if status:
                logger.info(f"📊 App Version    : {status.get('app_version', 'Unknown')}")
                logger.info(f"📊 DB Version     : {status['current_version']}")
                logger.info(f"📊 Applied        : {len(status['applied'])} migrations")
                logger.info(f"📊 Pending        : {len(status['pending'])} migrations")
                if status.get('last_updated'):
                    logger.info(f"📊 Last Updated   : {status['last_updated']}")
            else:
                logger.warning("Could not get migration status")
        except Exception as e:
            logger.warning(f"Could not get migration status: {e}")
        
        # Step 6: Crash recovery
        logger.info("Step 6: Running crash recovery check...")
        try:
            if check_and_recover(show_gui=False):
                logger.info("✅ Crash recovery actions performed.")
        except Exception as e:
            logger.error(f"Crash recovery check failed: {e}")
        
        # Step 7: Optimize
        logger.info("Step 7: Optimizing database...")
        try:
            stats = get_database_stats()
            if stats and stats.get('size_mb', 0) > 100:
                logger.info("Database is large, running optimization...")
                optimize_database()
        except Exception as e:
            logger.debug(f"Database optimization skipped: {e}")
        
        logger.info("=" * 60)
        logger.info("✅ DATABASE INITIALIZATION COMPLETE")
        logger.info("=" * 60)
        
        return status
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ DATABASE INITIALIZATION FAILED: {error_msg}")
        logger.exception(e)
        logger.info("=" * 60)
        logger.info("❌ DATABASE INITIALIZATION FAILED - APPLICATION WILL NOT START")
        logger.info("=" * 60)
        raise
