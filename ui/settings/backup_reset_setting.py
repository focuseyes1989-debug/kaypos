# ui/backup_reset_setting.py - Updated with better error handling

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QMessageBox, QFileDialog, QInputDialog, QProgressBar,
    QDialog, QLineEdit, QTextEdit, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from models.database import connect_db, close_all_connections
from utils.language import lang
from utils.permissions import PermissionManager, Permission
from utils.db_compat import is_postgres_backend, table_columns, table_exists
from loguru import logger
import os
import sys
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
import time


# ========== DATABASE PATH FIX ==========
def get_db_path():
    """Get database path for both development and packaged EXE."""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        return os.path.join(os.path.dirname(sys.executable), 'database', 'pos.db')
    else:
        # Running as Python script
        return "database/pos.db"


DB_PATH = get_db_path()
PRODUCT_IMAGES_DIR = os.path.join(os.path.dirname(DB_PATH), 'product_images')
BACKUP_DB_NAME = "pos.db"
BACKUP_IMAGES_DIR = "product_images"
POSTGRES_RESTORE_TABLES = [
    "app_metadata",
    "settings",
    "migrations",
    "migration_history",
    "category_groups",
    "categories",
    "category_stats",
    "category_activity_log",
    "customers",
    "payment_types",
    "locations",
    "products",
    "product_discounts",
    "product_variants",
    "product_locations",
    "sales",
    "sale_items",
    "cash_drawer",
    "payments",
    "credit_sales",
    "credit_payments",
    "credit_adjustments",
    "credit_transactions",
    "expense_categories",
    "expenses",
    "expense_budgets",
    "expense_notification_settings",
    "expense_alerts_log",
    "expense_attachments",
    "expiry_alerts_log",
    "user_roles",
    "users",
]
POSTGRES_COLUMN_ALIASES = {
    "payment_types": {"is_active": "active"},
}

# Log the path for debugging
logger.info(f"Database path: {DB_PATH}")
logger.info(f"Product images path: {PRODUCT_IMAGES_DIR}")


def _database_sidecar_paths(db_path):
    return (f"{db_path}-wal", f"{db_path}-shm")


def _ensure_database_exists():
    """Ensure database directory and file exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    if not os.path.exists(DB_PATH):
        logger.info("Database file not found, creating new database...")
        from models.database import create_tables
        create_tables()
        logger.info("Database created successfully.")
        return True
    return False


def _force_close_all_connections():
    """Force close all database connections and wait for release."""
    logger.info("Force closing all database connections...")
    
    # Close all connections from pool
    close_all_connections()
    
    # Wait for connections to be released
    time.sleep(0.5)
    
    # Garbage collection
    import gc
    gc.collect()
    
    # Try to close any remaining connections
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=1)
            conn.close()
        except:
            pass
    
    # Wait again
    time.sleep(0.3)
    
    logger.info("All connections closed.")


def _wait_for_file_release(file_path, max_wait=5):
    """Wait for a file to be released by the OS."""
    for i in range(max_wait * 10):
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
            return True
        except PermissionError:
            time.sleep(0.1)
            continue
        except FileNotFoundError:
            return True
    return False


def _backup_database_file(source_path, backup_path):
    if not os.path.exists(source_path):
        logger.warning(f"Source database not found: {source_path}")
        os.makedirs(os.path.dirname(source_path), exist_ok=True)
        from models.database import create_tables
        create_tables()
        logger.info("Created new database for backup.")

    backup_dir = os.path.dirname(os.path.abspath(backup_path))
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)

    source = sqlite3.connect(source_path)
    try:
        source.execute("PRAGMA wal_checkpoint(FULL)")
        dest = sqlite3.connect(backup_path)
        try:
            source.backup(dest)
            dest.commit()
        finally:
            dest.close()
    finally:
        source.close()


def _ensure_backup_extension(file_path):
    if os.path.splitext(file_path)[1]:
        return file_path
    return f"{file_path}.zaybackup"


def _make_path_portable(image_path, product_images_dir):
    """
    Convert an absolute image path to a portable relative path.
    
    Args:
        image_path: Original image path from database
        product_images_dir: Directory where product images are stored
    
    Returns:
        Portable relative path (e.g., "database/product_images/abc123.jpg")
    """
    if not image_path:
        return image_path
    
    # If already relative, keep it
    if not os.path.isabs(image_path):
        # Check if it's already in the correct format
        if 'product_images' in image_path or 'database/product_images' in image_path:
            return image_path
        # Otherwise, try to make it relative
        return os.path.join('database', 'product_images', os.path.basename(image_path))
    
    # Convert absolute to relative
    try:
        # Check if image is in product_images directory
        if os.path.dirname(image_path) == product_images_dir:
            # Just use filename
            return os.path.join('database', 'product_images', os.path.basename(image_path))
        
        # Check if image is inside product_images_dir (subfolders)
        if product_images_dir in image_path:
            rel_path = os.path.relpath(image_path, os.path.dirname(product_images_dir))
            return rel_path.replace('\\', '/')
        
        # Image is outside product_images_dir - copy it during restore
        # For now, just use the filename
        return os.path.join('database', 'product_images', os.path.basename(image_path))
        
    except Exception as e:
        logger.warning(f"Could not make path portable: {image_path} -> {e}")
        return image_path


def _fix_image_paths_in_db(db_path, product_images_dir):
    """
    Fix image paths in database to be relative (portable).
    This ensures images work on any computer after restore.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all products with image paths
        cursor.execute("SELECT id, image FROM products WHERE image IS NOT NULL AND image != ''")
        products = cursor.fetchall()
        
        updated_count = 0
        for product_id, image_path in products:
            if not image_path:
                continue
            
            # Convert to relative path
            relative_path = _make_path_portable(image_path, product_images_dir)
            
            if relative_path != image_path:
                cursor.execute("UPDATE products SET image = ? WHERE id = ?", (relative_path, product_id))
                updated_count += 1
        
        if updated_count > 0:
            conn.commit()
            logger.info(f"Fixed {updated_count} image paths to portable format")
        
        conn.close()
        return updated_count
        
    except Exception as e:
        logger.error(f"Failed to fix image paths: {e}")
        return 0


def _create_backup_package(backup_path, db_path=DB_PATH, product_images_dir=PRODUCT_IMAGES_DIR):
    """Create backup package with portable image paths."""
    backup_path = _ensure_backup_extension(backup_path)

    if os.path.splitext(backup_path)[1].lower() == ".db":
        _backup_database_file(db_path, backup_path)
        return backup_path

    backup_dir = os.path.dirname(os.path.abspath(backup_path))
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_db = os.path.join(tmp_dir, BACKUP_DB_NAME)
        _backup_database_file(db_path, temp_db)

        # Fix: Update image paths in database to relative paths BEFORE backup
        _fix_image_paths_in_db(temp_db, product_images_dir)

        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_db, BACKUP_DB_NAME)

            if os.path.isdir(product_images_dir):
                for root, _, files in os.walk(product_images_dir):
                    for filename in files:
                        source = os.path.join(root, filename)
                        relative = os.path.relpath(source, product_images_dir)
                        archive.write(source, os.path.join(BACKUP_IMAGES_DIR, relative))

    return backup_path


def _find_image_file(search_dir, filename):
    """
    Recursively search for an image file in a directory.
    
    Args:
        search_dir: Directory to search in
        filename: Filename to find
    
    Returns:
        Full path to the file if found, None otherwise
    """
    if not os.path.isdir(search_dir):
        return None
    
    for root, _, files in os.walk(search_dir):
        if filename in files:
            return os.path.join(root, filename)
    
    return None


def _fix_image_paths_for_restore(db_path, product_images_dir):
    """
    Fix image paths in database for the new computer.
    Keep relative paths as-is (they work with app_path()).
    Only fix absolute paths that don't exist.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, image FROM products WHERE image IS NOT NULL AND image != ''")
        products = cursor.fetchall()
        
        updated_count = 0
        for product_id, image_path in products:
            if not image_path:
                continue
            
            # Get just the filename
            filename = os.path.basename(image_path)
            
            # Case 1: Path is relative - keep it as is
            if not os.path.isabs(image_path):
                # Check if image exists in product_images_dir
                expected_path = os.path.join(product_images_dir, filename)
                
                # If image doesn't exist at expected path, try to find it
                if not os.path.exists(expected_path):
                    found_path = _find_image_file(product_images_dir, filename)
                    if found_path:
                        # Update to absolute path since we found it
                        cursor.execute("UPDATE products SET image = ? WHERE id = ?", (found_path, product_id))
                        updated_count += 1
                        logger.info(f"Found missing image '{filename}' at: {found_path}")
                    else:
                        logger.warning(f"Image file not found: {filename}")
                # else: file exists, keep relative path
                continue
            
            # Case 2: Path is absolute and file exists - keep it
            if os.path.exists(image_path):
                continue
            
            # Case 3: Path is absolute but file doesn't exist - try to find it
            found_path = _find_image_file(product_images_dir, filename)
            if found_path:
                cursor.execute("UPDATE products SET image = ? WHERE id = ?", (found_path, product_id))
                updated_count += 1
                logger.info(f"Fixed missing image path for product {product_id}: {found_path}")
            else:
                # Try relative path as fallback
                rel_path = os.path.join('database', 'product_images', filename).replace('\\', '/')
                # Check if the file exists in product_images_dir
                if os.path.exists(os.path.join(product_images_dir, filename)):
                    cursor.execute("UPDATE products SET image = ? WHERE id = ?", (rel_path, product_id))
                    updated_count += 1
                    logger.info(f"Using relative path: {rel_path}")
                else:
                    logger.warning(f"Image file not found: {filename}")
        
        if updated_count > 0:
            conn.commit()
            logger.info(f"Fixed {updated_count} image paths for current computer")
        
        conn.close()
        return updated_count
        
    except Exception as e:
        logger.error(f"Failed to fix image paths for restore: {e}")
        return 0


def _verify_image_paths(db_path, product_images_dir):
    """
    Verify all image paths in database exist on disk.
    Logs warnings for missing images.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, image FROM products WHERE image IS NOT NULL AND image != ''")
        products = cursor.fetchall()
        conn.close()
        
        missing_count = 0
        for product_id, name, image_path in products:
            if not image_path:
                continue
            
            # Check if path exists (absolute or relative)
            if not os.path.exists(image_path):
                # Try relative path resolution
                from utils.paths import app_path
                resolved = app_path(image_path)
                if not os.path.exists(resolved):
                    logger.warning(f"Missing image for product '{name}': {image_path}")
                    missing_count += 1
                else:
                    # Update to absolute path
                    try:
                        conn2 = sqlite3.connect(db_path)
                        cursor2 = conn2.cursor()
                        cursor2.execute("UPDATE products SET image = ? WHERE id = ?", (resolved, product_id))
                        conn2.commit()
                        conn2.close()
                        logger.info(f"Fixed image path for '{name}': {resolved}")
                    except Exception as e:
                        logger.error(f"Failed to update image path: {e}")
        
        if missing_count > 0:
            logger.warning(f"Found {missing_count} products with missing images")
        else:
            logger.info("All product images verified")
        
        return missing_count
        
    except Exception as e:
        logger.error(f"Image verification failed: {e}")
        return -1


# ============================================================
# ✅ FIXED: Better validation and recovery
# ============================================================

def _validate_database_file(file_path, allow_empty=False):
    """
    Validate database file with better error handling.
    
    Args:
        file_path: Path to database file
        allow_empty: If True, allow empty database (no tables)
    
    Returns:
        bool: True if valid
    
    Raises:
        Exception: If validation fails
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        if allow_empty:
            return True
        raise sqlite3.DatabaseError("Database file is empty")
    
    # Check if it's a valid SQLite database
    try:
        conn = sqlite3.connect(file_path, timeout=5)
        cursor = conn.cursor()
        
        # Check integrity
        try:
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if result and result[0].lower() != "ok":
                # Try to recover
                logger.warning(f"Integrity check failed: {result[0]}")
                # Still continue if we have tables
        except Exception as e:
            logger.warning(f"Integrity check error: {e}")
        
        # Check if there are tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not tables:
            if allow_empty:
                conn.close()
                return True
            raise sqlite3.DatabaseError("Database has no tables")
        
        # Check essential tables
        table_names = [t[0] for t in tables]
        essential_tables = ['settings', 'users', 'products']
        missing_tables = [t for t in essential_tables if t not in table_names]
        
        if missing_tables:
            logger.warning(f"Missing essential tables: {missing_tables}")
            # Still allow restore if it has some data
        
        conn.close()
        return True
        
    except sqlite3.DatabaseError as e:
        error_msg = str(e).lower()
        if "malformed" in error_msg:
            # Try to recover using .dump
            logger.warning("Database is malformed, attempting recovery...")
            recovered = _recover_malformed_database(file_path)
            if recovered:
                return True
            raise sqlite3.DatabaseError(f"Invalid database file: {e}")
        raise
    except Exception as e:
        raise Exception(f"Failed to validate database: {str(e)}")


def _recover_malformed_database(file_path):
    """
    Attempt to recover a malformed database using .dump.
    
    Returns:
        bool: True if recovery successful
    """
    try:
        # Create backup of malformed database
        backup_path = file_path + ".malformed"
        shutil.copy2(file_path, backup_path)
        logger.info(f"Backed up malformed database to: {backup_path}")
        
        # Try to dump and restore
        dump_path = file_path + ".dump"
        
        # Dump database
        import subprocess
        result = subprocess.run(
            ['sqlite3', file_path, '.dump'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.warning("Dump failed")
            return False
        
        # Write dump to file
        with open(dump_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        # Create new database from dump
        new_db = file_path + ".new"
        subprocess.run(
            ['sqlite3', new_db, '.read', dump_path],
            capture_output=True,
            timeout=120
        )
        
        # Check if new database is valid
        try:
            conn = sqlite3.connect(new_db, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            if cursor.fetchone():
                conn.close()
                # Replace original with recovered
                shutil.copy2(new_db, file_path)
                os.remove(new_db)
                os.remove(dump_path)
                logger.info("Database recovered successfully")
                return True
            conn.close()
        except:
            pass
        
        return False
        
    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        return False


def _restore_database_file(backup_path, db_path=DB_PATH):
    """
    Restore database file with better error handling.
    
    Args:
        backup_path: Path to backup file
        db_path: Target database path
    
    Returns:
        bool: True if successful
    
    Raises:
        Exception: If restore fails
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError("Backup file not found.")
    
    # Validate backup - allow empty
    try:
        _validate_database_file(backup_path, allow_empty=True)
    except Exception as e:
        logger.warning(f"Backup validation warning: {e}")
        # Continue anyway - try to restore
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Force close connections
    _force_close_all_connections()
    
    if os.path.exists(db_path):
        _wait_for_file_release(db_path, max_wait=5)
    
    # Backup current database if exists
    if os.path.exists(db_path):
        temp_backup = os.path.join(os.path.dirname(db_path), "pos_backup_before_restore.db")
        try:
            _backup_database_file(db_path, temp_backup)
            logger.info(f"Created backup of current database at: {temp_backup}")
        except Exception as e:
            logger.warning(f"Could not create backup of current database: {e}")
    
    # Remove WAL sidecar files with retry
    for sidecar in _database_sidecar_paths(db_path):
        if os.path.exists(sidecar):
            try:
                os.remove(sidecar)
                logger.info(f"Removed sidecar file: {sidecar}")
            except PermissionError:
                logger.warning(f"Could not remove sidecar file (in use), retrying...: {sidecar}")
                time.sleep(1)
                try:
                    os.remove(sidecar)
                    logger.info(f"Removed sidecar file after retry: {sidecar}")
                except Exception as e:
                    logger.warning(f"Could not remove sidecar file: {e}")
    
    # Copy backup to target with retry
    retry_count = 5
    last_error = None
    
    for i in range(retry_count):
        try:
            # First try: direct copy
            shutil.copy2(backup_path, db_path)
            logger.info(f"Restored database from: {backup_path} to: {db_path}")
            
            # Verify the restored database
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                conn.close()
                logger.info(f"Restored database verified: {table_count} tables found")
                return True
            except Exception as e:
                logger.error(f"Restored database verification failed: {e}")
                # If verification fails, try to repair
                _recover_malformed_database(db_path)
            
            return True
            
        except PermissionError as e:
            last_error = e
            if i < retry_count - 1:
                logger.warning(f"Copy failed (attempt {i+1}/{retry_count}), retrying...")
                time.sleep(1)
                _force_close_all_connections()
            else:
                raise PermissionError(f"Could not restore database: {e}")
        except Exception as e:
            last_error = e
            if i < retry_count - 1:
                logger.warning(f"Copy failed (attempt {i+1}/{retry_count}): {e}")
                time.sleep(1)
            else:
                raise
    
    # Remove any WAL sidecar files that might have been created during copy
    for sidecar in _database_sidecar_paths(db_path):
        if os.path.exists(sidecar):
            try:
                os.remove(sidecar)
                logger.info(f"Removed sidecar file after restore: {sidecar}")
            except:
                pass
    
    if last_error:
        raise last_error


def _extract_backup_database(backup_path, tmp_dir):
    if zipfile.is_zipfile(backup_path):
        with zipfile.ZipFile(backup_path, "r") as archive:
            names = set(archive.namelist())
            db_member = BACKUP_DB_NAME if BACKUP_DB_NAME in names else None
            if not db_member:
                db_candidates = [name for name in names if name.lower().endswith(".db")]
                db_member = db_candidates[0] if db_candidates else None
            if not db_member:
                raise FileNotFoundError("Backup package does not contain a database file.")
            archive.extractall(tmp_dir)
            return os.path.join(tmp_dir, db_member), os.path.join(tmp_dir, BACKUP_IMAGES_DIR)

    extracted_db = os.path.join(tmp_dir, BACKUP_DB_NAME)
    shutil.copy2(backup_path, extracted_db)
    return extracted_db, None


def _copy_extracted_images(extracted_images, product_images_dir):
    os.makedirs(product_images_dir, exist_ok=True)
    if not extracted_images or not os.path.isdir(extracted_images):
        return 0

    copied = 0
    for root, _, files in os.walk(extracted_images):
        for filename in files:
            src = os.path.join(root, filename)
            rel = os.path.relpath(src, extracted_images)
            dst = os.path.join(product_images_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    logger.info(f"Restored {copied} product image(s)")
    return copied


def _sqlite_table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _reset_postgres_sequence(cursor, table_name):
    if "id" not in table_columns(cursor, table_name):
        return
    cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table_name,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return
    cursor.execute(
        f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1, false)",
        (row[0],),
    )


def _import_sqlite_table_to_postgres(sqlite_cursor, pg_cursor, table_name):
    sqlite_cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    if not sqlite_cursor.fetchone() or not table_exists(pg_cursor, table_name):
        return 0

    source_columns = _sqlite_table_columns(sqlite_cursor, table_name)
    target_columns = table_columns(pg_cursor, table_name)
    aliases = POSTGRES_COLUMN_ALIASES.get(table_name, {})
    column_pairs = [
        (source_column, aliases.get(source_column, source_column))
        for source_column in source_columns
    ]
    column_pairs = [
        (source_column, target_column)
        for source_column, target_column in column_pairs
        if target_column in target_columns
    ]
    if table_name == "categories":
        column_pairs = [
            (source_column, target_column)
            for source_column, target_column in column_pairs
            if target_column != "parent_id"
        ]
    if not column_pairs:
        return 0

    order_clause = " ORDER BY id" if "id" in source_columns else ""
    sqlite_cursor.execute(f"SELECT * FROM {table_name}{order_clause}")
    rows = sqlite_cursor.fetchall()
    if not rows:
        return 0

    target_column_names = [target_column for _, target_column in column_pairs]
    source_indexes = [source_columns.index(source_column) for source_column, _ in column_pairs]
    values = [tuple(row[index] for index in source_indexes) for row in rows]
    placeholders = ", ".join(["%s"] * len(target_column_names))
    pg_cursor.executemany(
        f"INSERT INTO {table_name} ({', '.join(target_column_names)}) VALUES ({placeholders})",
        values,
    )
    logger.info(f"Imported {len(values)} row(s) into PostgreSQL table: {table_name}")
    return len(values)


def _restore_postgres_category_parent_links(sqlite_cursor, pg_cursor):
    if not table_exists(pg_cursor, "categories") or "parent_id" not in table_columns(pg_cursor, "categories"):
        return 0
    sqlite_cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
    )
    if not sqlite_cursor.fetchone():
        return 0

    source_columns = _sqlite_table_columns(sqlite_cursor, "categories")
    if "id" not in source_columns or "parent_id" not in source_columns:
        return 0

    sqlite_cursor.execute("SELECT id, parent_id FROM categories WHERE parent_id IS NOT NULL")
    rows = sqlite_cursor.fetchall()
    if not rows:
        return 0

    sqlite_cursor.execute("SELECT id FROM categories")
    source_ids = {row[0] for row in sqlite_cursor.fetchall()}
    restored = 0
    skipped = 0
    for category_id, parent_id in rows:
        if parent_id in source_ids and parent_id != category_id:
            pg_cursor.execute(
                "UPDATE categories SET parent_id = ? WHERE id = ?",
                (parent_id, category_id),
            )
            restored += 1
        else:
            skipped += 1

    if skipped:
        logger.warning(f"Skipped {skipped} orphan category parent link(s) during PostgreSQL restore")
    if restored:
        logger.info(f"Restored {restored} category parent link(s)")
    return restored


def _restore_backup_package_to_postgres(backup_path, product_images_dir=PRODUCT_IMAGES_DIR):
    """Restore a legacy SQLite backup package into the PostgreSQL pilot schema."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    from models.database import connect_db, safe_initialize_postgres_pilot_database

    _force_close_all_connections()
    if not safe_initialize_postgres_pilot_database():
        raise RuntimeError("PostgreSQL schema initialization failed before restore.")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        source_db, extracted_images = _extract_backup_database(backup_path, tmp_dir)
        _validate_database_file(source_db, allow_empty=True)
        _fix_image_paths_for_restore(source_db, product_images_dir)

        sqlite_conn = sqlite3.connect(source_db)
        pg_conn = connect_db()
        try:
            sqlite_cursor = sqlite_conn.cursor()
            pg_cursor = pg_conn.cursor()

            restore_tables = [
                table for table in POSTGRES_RESTORE_TABLES
                if table_exists(pg_cursor, table)
            ]
            if restore_tables:
                pg_cursor.execute(
                    f"TRUNCATE TABLE {', '.join(restore_tables)} RESTART IDENTITY CASCADE"
                )

            imported = {}
            for table in POSTGRES_RESTORE_TABLES:
                imported[table] = _import_sqlite_table_to_postgres(
                    sqlite_cursor,
                    pg_cursor,
                    table,
                )

            _restore_postgres_category_parent_links(sqlite_cursor, pg_cursor)

            for table in POSTGRES_RESTORE_TABLES:
                if table_exists(pg_cursor, table):
                    _reset_postgres_sequence(pg_cursor, table)

            pg_conn.commit()
            logger.info(f"PostgreSQL restore imported rows: {imported}")
        except Exception:
            try:
                pg_conn.rollback()
            except Exception:
                pass
            raise
        finally:
            sqlite_conn.close()
            pg_conn.close()

        _copy_extracted_images(extracted_images, product_images_dir)


def _restore_backup_package(backup_path, db_path=DB_PATH, product_images_dir=PRODUCT_IMAGES_DIR):
    """Restore backup package and fix image paths."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    if is_postgres_backend():
        _restore_backup_package_to_postgres(backup_path, product_images_dir)
        return
    
    # Step 1: Force close ALL connections
    logger.info("Step 1: Closing all database connections...")
    _force_close_all_connections()
    
    # Step 2: Wait for file to be released
    if os.path.exists(db_path):
        logger.info("Step 2: Waiting for file release...")
        if not _wait_for_file_release(db_path, max_wait=5):
            logger.warning("Could not release database file, but continuing...")
    
    # Step 3: Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Step 4: Remove sidecar files first
    logger.info("Step 3: Removing sidecar files...")
    for sidecar in _database_sidecar_paths(db_path):
        if os.path.exists(sidecar):
            try:
                os.remove(sidecar)
                logger.info(f"Removed sidecar file: {sidecar}")
            except PermissionError:
                logger.warning(f"Could not remove sidecar file (in use): {sidecar}")
                time.sleep(0.5)
                try:
                    os.remove(sidecar)
                    logger.info(f"Removed sidecar file after retry: {sidecar}")
                except Exception as e:
                    logger.warning(f"Could not remove sidecar file: {e}")
    
    # Step 5: Restore from backup
    logger.info("Step 4: Restoring from backup...")
    
    if zipfile.is_zipfile(backup_path):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with zipfile.ZipFile(backup_path, "r") as archive:
                names = set(archive.namelist())
                if BACKUP_DB_NAME not in names:
                    raise FileNotFoundError("Backup package does not contain pos.db.")
                archive.extractall(tmp_dir)

            extracted_db = os.path.join(tmp_dir, BACKUP_DB_NAME)
            
            if not os.path.exists(extracted_db):
                raise FileNotFoundError(f"Extracted database not found: {extracted_db}")
            
            # Validate with allow_empty=True
            try:
                _validate_database_file(extracted_db, allow_empty=True)
            except Exception as e:
                logger.warning(f"Extracted database validation warning: {e}")
                # Try to recover
                _recover_malformed_database(extracted_db)
            
            # Fix: Update image paths for new computer BEFORE restore
            _fix_image_paths_for_restore(extracted_db, product_images_dir)
            
            # Restore database
            _restore_database_file(extracted_db, db_path)

            extracted_images = os.path.join(tmp_dir, BACKUP_IMAGES_DIR)
            if os.path.isdir(extracted_images):
                # Ensure product_images directory exists
                os.makedirs(product_images_dir, exist_ok=True)
                
                # Copy images with overwrite
                for root, _, files in os.walk(extracted_images):
                    for filename in files:
                        src = os.path.join(root, filename)
                        rel = os.path.relpath(src, extracted_images)
                        dst = os.path.join(product_images_dir, rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        logger.info(f"Restored image: {rel}")
            else:
                os.makedirs(product_images_dir, exist_ok=True)
    else:
        # Validate with allow_empty=True
        try:
            _validate_database_file(backup_path, allow_empty=True)
        except Exception as e:
            logger.warning(f"Backup validation warning: {e}")
            # Try to recover
            _recover_malformed_database(backup_path)
        
        _fix_image_paths_for_restore(backup_path, product_images_dir)
        _restore_database_file(backup_path, db_path)
    
    # Step 6: Final image path verification and fixing
    logger.info("Step 5: Verifying and fixing image paths...")
    _verify_image_paths(db_path, product_images_dir)
    
    # Step 7: Verify restore
    logger.info("Step 6: Verifying restore...")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            count = cursor.fetchone()[0]
            conn.close()
            logger.info(f"Restore verified: {count} tables found")
        except Exception as e:
            logger.error(f"Restore verification failed: {e}")
            # Try to recover
            _recover_malformed_database(db_path)
    
    logger.info("Restore completed successfully!")


# ========== WORKER THREADS ==========

class BackupWorker(QThread):
    """Worker thread for backup operation with progress."""
    progress = pyqtSignal(int, str)  # value, status
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, backup_path):
        super().__init__()
        self.backup_path = backup_path
        
    def run(self):
        try:
            self.progress.emit(5, "Checking database...")
            _ensure_database_exists()
            
            self.progress.emit(10, "Preparing backup...")
            time.sleep(0.1)
            
            self.progress.emit(20, "Creating database backup...")
            
            # Create backup with progress
            _create_backup_package(self.backup_path)
            
            self.progress.emit(90, "Finalizing...")
            time.sleep(0.1)
            
            self.progress.emit(100, "Backup completed!")
            self.finished.emit(True, self.backup_path)
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            self.finished.emit(False, str(e))


class RestoreWorker(QThread):
    """Worker thread for restore operation with progress."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, restore_path):
        super().__init__()
        self.restore_path = restore_path
        
    def run(self):
        try:
            self.progress.emit(5, "Validating backup file...")
            
            if not os.path.exists(self.restore_path):
                raise FileNotFoundError("Backup file not found")
            
            self.progress.emit(10, "Closing database connections...")
            _force_close_all_connections()
            time.sleep(0.5)
            
            self.progress.emit(15, "Removing sidecar files...")
            for sidecar in _database_sidecar_paths(DB_PATH):
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except:
                        pass
            
            self.progress.emit(20, "Restoring database...")
            
            # Restore with progress
            _restore_backup_package(self.restore_path)
            
            self.progress.emit(90, "Verifying restore...")
            time.sleep(0.2)
            
            # Verify after restore
            if os.path.exists(DB_PATH):
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=5)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                    count = cursor.fetchone()[0]
                    conn.close()
                    logger.info(f"Restore verified: {count} tables found")
                except Exception as e:
                    logger.error(f"Verification failed: {e}")
                    # Try to recover
                    _recover_malformed_database(DB_PATH)
            
            self.progress.emit(100, "Restore completed!")
            self.finished.emit(True, "Restore completed successfully")
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            self.finished.emit(False, str(e))


class FactoryResetWorker(QThread):
    """Worker thread for factory reset with detailed progress."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, backup_path):
        super().__init__()
        self.backup_path = backup_path
        
    def run(self):
        try:
            # Step 1: Check database
            self.progress.emit(5, "Checking database...")
            _ensure_database_exists()
            time.sleep(0.1)
            
            # Step 2: Close connections
            self.progress.emit(8, "Closing database connections...")
            _force_close_all_connections()
            time.sleep(0.2)
            
            # Step 3: Create backup
            self.progress.emit(10, "Creating backup...")
            _create_backup_package(self.backup_path)
            self.progress.emit(25, "Backup created")
            time.sleep(0.1)
            
            # Step 4: Connect to database
            self.progress.emit(30, "Connecting to database...")
            conn = None
            for i in range(3):
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=5)
                    break
                except sqlite3.OperationalError:
                    if i < 2:
                        time.sleep(0.5)
                        _force_close_all_connections()
                    else:
                        raise
            
            if conn is None:
                raise Exception("Could not connect to database")
            
            cursor = conn.cursor()
            
            # Step 5: Clear tables
            self.progress.emit(35, "Clearing data...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            total_tables = len(tables)
            for i, (table_name,) in enumerate(tables):
                if table_name not in ['sqlite_sequence', 'migration_history', 'app_metadata']:
                    cursor.execute(f"DELETE FROM {table_name}")
                progress_value = 35 + int((i / max(total_tables, 1)) * 25)
                self.progress.emit(progress_value, f"Clearing: {table_name}")
                QApplication.processEvents()
            
            # Step 6: Reset settings
            self.progress.emit(60, "Resetting settings...")
            default_settings = [
                ('tax_rate', '0'), ('tax_enabled', '0'),
                ('loyalty_points_per_dollar', '0'), ('loyalty_min_points_for_reward', '100'),
                ('loyalty_reward_discount', '5'), ('discount_enabled', '0'),
                ('discount_type', 'percentage'), ('discount_value', '0'),
                ('currency', 'Kyats (Ks)'),
                ('shop_name', 'ZAY POS'), ('shop_logo', ''),
                ('shop_phone', ''), ('shop_address', ''), ('shop_footer_message', ''),
                ('customer_display_youtube_url', ''),
                ('performance_low_end_mode', '1'),
                ('performance_product_page_size', '25'),
                ('performance_search_debounce_ms', '450'),
                ('performance_thumbnail_quality', 'low'),
                ('performance_customer_display_youtube_enabled', '0'),
                ('receipt_header', ''), ('receipt_footer', ''), ('show_customer_name', '1'),
                ('language', 'en'), ('theme', 'Light'),
                ('points_expiry_months', '12'), ('points_dollar_value', '0.01'),
                ('follow_system_theme', '1'),
                ('auto_backup_enabled', '0'), ('auto_backup_interval', '24'), ('auto_backup_max', '30'),
                ('credit_due_days', '15'), ('credit_limit_enabled', 'true')
            ]
            
            cursor.execute("DELETE FROM settings")
            for key, val in default_settings:
                cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, val))
            
            # Step 7: Reset users
            self.progress.emit(68, "Resetting users...")
            cursor.execute("DELETE FROM users")
            import hashlib
            salt = os.urandom(32).hex()
            password_hash = hashlib.pbkdf2_hmac('sha256', 'admin'.encode(), bytes.fromhex(salt), 100000).hex()
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, full_name, salt, force_password_change, is_active) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("admin", password_hash, "Admin", "Administrator", salt, 0, 1))
            
            # Step 8: Reset user roles
            self.progress.emit(73, "Resetting user roles...")
            cursor.execute("DELETE FROM user_roles")
            default_roles = [
                ('Admin', 'Full access to every page and action',
                 'dashboard,sales,create_sale,edit_sale,delete_sale,refund_sale,sales_summary,products,add_product,edit_product,delete_product,ai_pages,inventory,stock_in,stock_out,adjustment,receipts,print_receipt,refund_receipt,customers,add_customer,edit_customer,delete_customer,expense,add_expense,edit_expense,delete_expense,manage_expense_categories,reports,credit,credit_sale,payment_collection,users,add_user,edit_user,delete_user,settings,edit_settings,backup,restore,factory_reset',
                 1),
                ('Manager', 'Manage daily operations without user deletion, restore, or factory reset',
                 'dashboard,sales,create_sale,edit_sale,refund_sale,sales_summary,products,add_product,edit_product,delete_product,ai_pages,inventory,stock_in,stock_out,adjustment,receipts,print_receipt,refund_receipt,customers,add_customer,edit_customer,expense,add_expense,edit_expense,delete_expense,manage_expense_categories,reports,credit,credit_sale,payment_collection,settings,backup',
                 0),
                ('Cashier', 'Process sales, print receipts, refund receipts, and manage sale customers',
                 'sales,create_sale,receipts,print_receipt,refund_receipt,customers,add_customer,credit,credit_sale,payment_collection',
                 0),
                ('Viewer', 'Read-only access to dashboards, lists, receipts, reports, and credit',
                 'dashboard,sales_summary,products,inventory,receipts,customers,reports,credit',
                 0),
            ]
            for name, desc, perms, is_system in default_roles:
                cursor.execute("""
                    INSERT INTO user_roles (name, description, permissions, is_system)
                    VALUES (?, ?, ?, ?)
                """, (name, desc, perms, is_system))
            
            # Step 9: Reset categories
            self.progress.emit(78, "Resetting categories...")
            cursor.execute("DELETE FROM categories")
            cursor.execute("INSERT INTO categories (name, slug) VALUES ('General', 'general')")
            
            # Step 10: Reset payment types
            self.progress.emit(82, "Resetting payment types...")
            cursor.execute("DELETE FROM payment_types")
            cursor.executemany("INSERT INTO payment_types (name, is_active) VALUES (?, 1)", 
                               [("Cash",), ("Card",), ("Mobile Money",)])
            
            # Step 11: Reset expense categories
            self.progress.emit(86, "Resetting expense categories...")
            cursor.execute("DELETE FROM expense_categories")
            default_expense_categories = [
                ('Rent', 'Office/Shop rent', 1),
                ('Utilities', 'Electricity, Water, Internet', 1),
                ('Salaries', 'Employee salaries', 1),
                ('Marketing', 'Advertising, Promotion', 1),
                ('Maintenance', 'Equipment repair', 1),
                ('Transport', 'Delivery, Fuel', 1),
                ('Office Supplies', 'Stationery, Printing', 1),
                ('Taxes', 'Government taxes', 1),
                ('Other', 'Miscellaneous expenses', 1)
            ]
            for name, description, is_active in default_expense_categories:
                cursor.execute("""
                    INSERT INTO expense_categories (name, description, is_active) 
                    VALUES (?, ?, ?)
                """, (name, description, is_active))
            
            conn.commit()
            conn.close()
            
            # Step 12: Clean temporary files
            self.progress.emit(92, "Cleaning temporary files...")
            temp_dirs = ["temp", "logs", "attachments", "database/backups"]
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except:
                            pass
            
            self.progress.emit(100, "Reset completed!")
            self.finished.emit(True, self.backup_path)
            
        except Exception as e:
            logger.error(f"Factory reset failed: {e}")
            self.finished.emit(False, str(e))


# ========== PROGRESS DIALOG ==========

class ProgressDialog(QDialog):
    """Progress dialog with status and progress bar."""
    
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(450, 180)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | 
                           Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Status label
        self.status_label = QLabel("Starting...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12pt;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                height: 25px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Cancel button (optional)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.setEnabled(False)  # Disabled by default
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def update_progress(self, value, status):
        """Update progress bar and status."""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
        QApplication.processEvents()


class BackupResetSettingWidget(QWidget):
    def __init__(self, user_id=None, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.worker = None
        self.progress_dialog = None
        self.setup_ui()
        self.apply_permissions()

    def apply_permissions(self):
        if self.user_id:
            if not PermissionManager.user_has_permission(self.user_id, Permission.BACKUP):
                self.btn_backup.setEnabled(False)
                self.btn_backup.setToolTip("You don't have permission to backup database")
                self.btn_restore.setEnabled(False)
                self.btn_restore.setToolTip("You don't have permission to restore database")
            
            if not PermissionManager.user_has_permission(self.user_id, Permission.FACTORY_RESET):
                self.btn_reset.setEnabled(False)
                self.btn_reset.setToolTip("You don't have permission to perform factory reset")

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.backup_group = QGroupBox()
        backup_layout = QVBoxLayout()
        self.backup_desc = QLabel()
        self.backup_desc.setWordWrap(True)
        backup_layout.addWidget(self.backup_desc)
        self.btn_backup = QPushButton()
        self.btn_backup.clicked.connect(self.backup_database)
        backup_layout.addWidget(self.btn_backup)
        self.btn_restore = QPushButton()
        self.btn_restore.clicked.connect(self.restore_database)
        backup_layout.addWidget(self.btn_restore)
        self.backup_group.setLayout(backup_layout)
        left_layout.addWidget(self.backup_group)
        left_layout.addStretch()

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.reset_group = QGroupBox()
        reset_layout = QVBoxLayout()
        self.reset_desc = QLabel()
        self.reset_desc.setWordWrap(True)
        reset_layout.addWidget(self.reset_desc)
        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self.start_factory_reset)
        reset_layout.addWidget(self.btn_reset)
        self.reset_group.setLayout(reset_layout)
        right_layout.addWidget(self.reset_group)
        right_layout.addStretch()

        columns_layout.addWidget(left_column)
        columns_layout.addWidget(right_column)
        layout.addLayout(columns_layout)
        self.setLayout(layout)
        self.retranslateUi()

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.backup_group.setTitle("Database Backup")
            self.backup_desc.setText("သင်၏ database ကို backup ဖိုင်အဖြစ် သိမ်းဆည်းရန်။")
            self.btn_backup.setText("Backup ပြုလုပ်မည်")
            self.btn_restore.setText("Restore ပြုလုပ်မည်")
            self.reset_group.setTitle("စက်ရုံပြန်လည်သတ်မှတ်ခြင်း")
            self.reset_desc.setText(
                "⚠️ သတိပေးချက် ⚠️\n\n"
                "ဤလုပ်ဆောင်ချက်သည် အောက်ပါအချက်များအားလုံးကို အပြီးတိုင်ဖျက်ပစ်မည်:\n"
                "• ရောင်းအားမှတ်တမ်းများ\n"
                "• ဝယ်ယူသူများ\n"
                "• ပေးသွင်းသူများ\n"
                "• စတော့ပြောင်းလဲမှုများ\n"
                "• ပစ္စည်းများ\n"
                "• အသုံးစရိတ်များ\n\n"
                "**Backup ဖိုင်အလိုအလျောက် သိမ်းဆည်းပေးမည်။**\n"
                "ဤလုပ်ဆောင်ချက်ကို နောက်ပြန်မလှန်နိုင်ပါ။"
            )
            self.btn_reset.setText("စက်ရုံပြန်လည်သတ်မှတ်ခြင်း လုပ်ဆောင်ရန်")
        else:
            self.backup_group.setTitle("Database Backup")
            self.backup_desc.setText("Save a backup copy of your current database.")
            self.btn_backup.setText("Perform Backup")
            self.btn_restore.setText("Perform Restore")
            self.reset_group.setTitle("Factory Reset")
            self.reset_desc.setText(
                "⚠️ WARNING ⚠️\n\n"
                "This will permanently delete ALL:\n"
                "• Sales history\n"
                "• Customers\n"
                "• Suppliers\n"
                "• Stock movements\n"
                "• Products\n"
                "• Expenses\n\n"
                "**A backup will be automatically created before reset.**\n"
                "This action CANNOT be undone!"
            )
            self.btn_reset.setText("Perform Factory Reset")

    def _show_progress_dialog(self, title):
        """Show progress dialog."""
        self.progress_dialog = ProgressDialog(title, self)
        self.progress_dialog.show()
        QApplication.processEvents()
        return self.progress_dialog

    def _close_progress_dialog(self):
        """Close progress dialog."""
        if self.progress_dialog:
            self.progress_dialog.accept()
            self.progress_dialog = None
        QApplication.processEvents()

    def _on_backup_progress(self, value, status):
        """Update backup progress."""
        if self.progress_dialog:
            self.progress_dialog.update_progress(value, status)

    def _on_backup_finished(self, success, result):
        """Handle backup completion."""
        self._close_progress_dialog()
        self.btn_backup.setEnabled(True)
        
        if success:
            msg = f"Backup saved to:\n{result}" if lang.get_current() != "my" else f"Backup ဖိုင်ကို ဤနေရာတွင် သိမ်းဆည်းပြီးပါပြီ:\n{result}"
            QMessageBox.information(self, "Backup Complete" if lang.get_current() != "my" else "Backup ပြီးပါပြီ", msg)
        else:
            QMessageBox.critical(self, "Error", f"Backup failed: {result}")

    def _on_restore_progress(self, value, status):
        """Update restore progress."""
        if self.progress_dialog:
            self.progress_dialog.update_progress(value, status)

    def _on_restore_finished(self, success, result):
        """Handle restore completion."""
        self._close_progress_dialog()
        self.btn_restore.setEnabled(True)
        
        if success:
            # Verify database after restore
            try:
                from models.database import connect_db
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM settings")
                count = cursor.fetchone()[0]
                conn.close()
                logger.info(f"Database verified after restore: {count} settings found")
            except Exception as e:
                logger.error(f"Database verification failed: {e}")
                # Try to recover
                from models.database.recovery import DatabaseRecovery
                recovery = DatabaseRecovery()
                recovery.auto_recover()
            
            QMessageBox.information(
                self,
                "Restore Complete" if lang.get_current() != "my" else "Restore ပြီးပါပြီ",
                "Database restored successfully.\n\nThe application will now close.\nPlease restart manually."
                if lang.get_current() != "my" else
                "Database ပြန်လည် restore ပြီးပါပြီ။\n\nApplication ပိတ်သွားပါမည်။\nကျေးဇူးပြု၍ ပြန်ဖွင့်ပါ။"
            )
            import sys
            sys.exit(0)
        else:
            QMessageBox.critical(self, "Error", f"Restore failed: {result}")

    def _on_reset_progress(self, value, status):
        """Update reset progress."""
        if self.progress_dialog:
            self.progress_dialog.update_progress(value, status)

    def _on_reset_finished(self, success, result):
        """Handle factory reset completion."""
        self._close_progress_dialog()
        self.btn_reset.setEnabled(True)
        
        if success:
            backup_dialog = BackupInfoDialog(result, self)
            backup_dialog.exec()
            import sys
            sys.exit(0)
        else:
            QMessageBox.critical(self, "Factory Reset Failed", f"Error: {result}")

    def backup_database(self):
        """Create a database backup."""
        _ensure_database_exists()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"pos_backup_{timestamp}.zaybackup"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Backup Database" if lang.get_current() != "my" else "Database Backup သိမ်းရန်",
            default_filename,
            "ZAY POS Backup (*.zaybackup);;Database Files (*.db)"
        )
        if not file_path:
            return
        
        # Disable button
        self.btn_backup.setEnabled(False)
        
        # Show progress dialog
        self._show_progress_dialog("Backing up database...")
        
        # Start worker
        self.worker = BackupWorker(file_path)
        self.worker.progress.connect(self._on_backup_progress)
        self.worker.finished.connect(self._on_backup_finished)
        self.worker.start()

    def restore_database(self):
        """Restore database from backup."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Database" if lang.get_current() != "my" else "Database Backup ဖိုင်ရွေးရန်",
            "",
            "ZAY POS Backup (*.zaybackup);;Database Files (*.db);;Zip Files (*.zip)"
        )
        if not file_path:
            return
        
        confirm_msg = (
            "Are you sure you want to restore this backup?\n"
            "Your current database will be overwritten and all recent changes may be lost.\n"
            "The application will close after restore. Please restart manually."
            if lang.get_current() != "my" else
            "ဤ backup ဖိုင်ကို ပြန်လည် restore လုပ်မည်လား?\n"
            "လက်ရှိ database အဟောင်း ပျက်သွားမည်။\n"
            "Restore ပြီးပါက application ပိတ်သွားမည်။ ကျေးဇူးပြု၍ ပြန်ဖွင့်ပါ။"
        )
        reply = QMessageBox.question(
            self,
            "Confirm Restore" if lang.get_current() != "my" else "Restore လုပ်ရန်အတည်ပြုပါ",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Disable button
        self.btn_restore.setEnabled(False)
        
        # Show progress dialog
        self._show_progress_dialog("Restoring database...")
        
        # Start worker
        self.worker = RestoreWorker(file_path)
        self.worker.progress.connect(self._on_restore_progress)
        self.worker.finished.connect(self._on_restore_finished)
        self.worker.start()

    def start_factory_reset(self):
        """Start factory reset process with confirmation and backup."""
        if self.user_id and not PermissionManager.user_has_permission(self.user_id, Permission.FACTORY_RESET):
            QMessageBox.warning(self, "Access Denied", "You don't have permission to perform factory reset.")
            return
        
        _ensure_database_exists()
        
        confirm_dialog = ConfirmResetDialog(self)
        if confirm_dialog.exec() != QDialog.DialogCode.Accepted or not confirm_dialog.confirmed:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"factory_reset_backup_{timestamp}.zaybackup"
        backup_dir = "database/backups"
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Disable button
        self.btn_reset.setEnabled(False)
        
        # Show progress dialog
        self._show_progress_dialog("Factory reset in progress...")
        
        # Start worker
        self.worker = FactoryResetWorker(backup_path)
        self.worker.progress.connect(self._on_reset_progress)
        self.worker.finished.connect(self._on_reset_finished)
        self.worker.start()


# ========== DIALOGS ==========

class BackupInfoDialog(QDialog):
    def __init__(self, backup_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Backup Created")
        self.setMinimumSize(500, 350)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        title_layout = QHBoxLayout()
        icon_label = QLabel("✅")
        icon_label.setStyleSheet("font-size: 48pt;")
        title_layout.addWidget(icon_label)
        
        self.title_text = QLabel("Factory Reset Completed Successfully!")
        self.title_text.setStyleSheet("font-size: 14pt; font-weight: bold; color: #27ae60;")
        title_layout.addWidget(self.title_text)
        layout.addLayout(title_layout)
        
        info_group = QGroupBox("Backup Information")
        info_layout = QVBoxLayout()
        backup_label = QLabel("Backup saved at:")
        backup_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(backup_label)
        backup_path_label = QLabel(backup_path)
        backup_path_label.setWordWrap(True)
        backup_path_label.setStyleSheet("color: #3498db; font-family: monospace;")
        info_layout.addWidget(backup_path_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        instruction_group = QGroupBox("What to do next?")
        instruction_layout = QVBoxLayout()
        instructions = QLabel(
            "1. The application will now close.\n"
            "2. Please restart the application manually.\n"
            "3. Login with: admin / admin\n"
            "4. Your backup is saved in the database/backups folder.\n"
            "5. To restore, use the Restore button in Backup & Reset settings."
        )
        instructions.setWordWrap(True)
        instruction_layout.addWidget(instructions)
        instruction_group.setLayout(instruction_layout)
        layout.addWidget(instruction_group)
        
        btn_layout = QHBoxLayout()
        self.btn_open_folder = QPushButton("Open Backup Folder")
        self.btn_open_folder.clicked.connect(lambda: self.open_folder(os.path.dirname(backup_path)))
        self.btn_close = QPushButton("Close Application")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_open_folder)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.retranslateUi()
    
    def open_folder(self, path):
        import subprocess
        import sys
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
    
    def retranslateUi(self):
        lang_code = self.get_lang()
        if lang_code == "my":
            self.setWindowTitle("Backup ဖိုင်သိမ်းဆည်းပြီးပါပြီ")
            self.title_text.setText("Factory Reset အောင်မြင်စွာ ပြီးဆုံးပါပြီ!")
            self.btn_open_folder.setText("Backup ဖိုင်တွဲဖွင့်ရန်")
            self.btn_close.setText("Application ပိတ်ရန်")
    
    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"


class ConfirmResetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Factory Reset")
        self.setMinimumSize(500, 450)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        self.confirmed = False
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        warning_layout = QHBoxLayout()
        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet("font-size: 48pt;")
        warning_layout.addWidget(warning_icon)
        
        self.warning_text = QLabel("WARNING: This action cannot be undone!")
        self.warning_text.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e74c3c;")
        warning_layout.addWidget(self.warning_text)
        layout.addLayout(warning_layout)
        
        delete_group = QGroupBox("The following data will be PERMANENTLY DELETED:")
        delete_layout = QVBoxLayout()
        delete_items = [
            "• All sales records and receipts",
            "• All customer data and points",
            "• All supplier information",
            "• All product inventory",
            "• All stock movements",
            "• All expenses and budgets",
            "• All credit sales and payments",
            "• All purchase orders"
        ]
        for item in delete_items:
            delete_layout.addWidget(QLabel(item))
        delete_group.setLayout(delete_layout)
        layout.addWidget(delete_group)
        
        keep_group = QGroupBox("The following will be preserved:")
        keep_layout = QVBoxLayout()
        keep_items = [
            "✓ A backup will be created before reset",
            "✓ User accounts (only admin will remain)",
            "✓ System settings (reset to defaults)",
            "✓ Categories and payment types (reset to defaults)"
        ]
        for item in keep_items:
            keep_layout.addWidget(QLabel(item))
        keep_group.setLayout(keep_layout)
        layout.addWidget(keep_group)
        
        confirm_layout = QVBoxLayout()
        confirm_label = QLabel("Type 'RESET ALL' to confirm:")
        confirm_label.setStyleSheet("font-weight: bold;")
        confirm_layout.addWidget(confirm_label)
        
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("RESET ALL")
        confirm_layout.addWidget(self.confirm_input)
        layout.addLayout(confirm_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_confirm = QPushButton("Confirm Reset")
        self.btn_confirm.setStyleSheet("background-color: #e74c3c; color: white;")
        self.btn_confirm.clicked.connect(self.check_confirmation)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.retranslateUi()
    
    def check_confirmation(self):
        if self.confirm_input.text() == "RESET ALL":
            self.confirmed = True
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Input", "Please type 'RESET ALL' to confirm.")
    
    def retranslateUi(self):
        lang_code = self.get_lang()
        if lang_code == "my":
            self.setWindowTitle("Factory Reset အတည်ပြုရန်")
            self.warning_text.setText("သတိပေးချက်: ဤလုပ်ဆောင်ချက်ကို နောက်ပြန်မလှန်နိုင်ပါ!")
            self.btn_cancel.setText("မလုပ်တော့")
            self.btn_confirm.setText("အတည်ပြုဖျက်မည်")
    
    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
