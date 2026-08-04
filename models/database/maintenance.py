# models/database/maintenance.py
"""
Database maintenance functions.
"""

import os
import time
import shutil
import sqlite3
from loguru import logger
from datetime import datetime, timedelta
from models.database.connection import DBContext


def rebuild_indexes():
    """Rebuild all indexes for better performance."""
    with DBContext() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        for idx in indexes:
            try:
                cursor.execute(f"REINDEX {idx}")
            except Exception as e:
                logger.warning(f"Failed to reindex {idx}: {e}")
        
        # Analyze for query planner
        cursor.execute("ANALYZE")
        conn.commit()
        logger.info("Database indexes rebuilt and analyzed")


def vacuum_database():
    """Vacuum database to reclaim space and optimize."""
    try:
        with DBContext() as conn:
            conn.execute("VACUUM")
            logger.info("Database vacuum completed successfully")
    except Exception as e:
        logger.error(f"Vacuum failed: {e}")


def auto_vacuum_if_needed():
    """Check if vacuum is needed and run it."""
    try:
        with DBContext() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA freelist_count")
            freelist = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            # If more than 10% of pages are free, run vacuum
            if freelist > page_count * 0.1:
                logger.info(f"Running vacuum (freelist: {freelist}, pages: {page_count})")
                conn.execute("VACUUM")
                logger.info("Vacuum completed")
    except Exception as e:
        logger.error(f"Auto-vacuum check failed: {e}")


def optimize_database():
    """Run database optimization routines."""
    try:
        rebuild_indexes()
        auto_vacuum_if_needed()
        logger.info("Database optimization completed")
    except Exception as e:
        logger.error(f"Optimization failed: {e}")


def backup_database(backup_dir="database/backups"):
    """Create a backup of the database."""
    db_path = "database/pos.db"
    if not os.path.exists(db_path):
        logger.warning("Database file not found, skipping backup")
        return None
    
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{backup_dir}/pos_backup_{timestamp}.db"
    
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def get_database_stats():
    """Get database statistics."""
    try:
        with DBContext() as conn:
            cursor = conn.cursor()
            
            # Get table info
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get row counts
            stats = {}
            total_rows = 0
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]
                    stats[table] = row_count
                    total_rows += row_count
                except:
                    pass
            
            # Get database size
            if os.path.exists("database/pos.db"):
                size_bytes = os.path.getsize("database/pos.db")
                size_mb = size_bytes / (1024 * 1024)
            else:
                size_mb = 0
            
            # Get connection pool stats
            try:
                from models.database.pool import get_pool_stats
                pool_stats = get_pool_stats()
            except:
                pool_stats = None
            
            return {
                'tables': stats,
                'total_rows': total_rows,
                'size_mb': size_mb,
                'pool_stats': pool_stats
            }
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return None


# =============================================================================
# ✅ FIXED: expire_old_points() - Uses expiry_date instead of created_at
# =============================================================================
def expire_old_points():
    """
    Expire loyalty points based on expiry_date.
    
    ✅ FIX: Now correctly uses expiry_date column instead of created_at.
    Previously it only checked expiry_date IS NULL, which meant points with
    expiry_date set would never expire.
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get expiry months from settings (for backward compatibility)
        cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
        row = cursor.fetchone()
        expiry_months = int(row[0]) if row else 12
        
        # ✅ FIX: Use expiry_date directly - expire points where expiry_date is in the past
        # Also handle old data where expiry_date might be NULL (fallback to created_at)
        if expiry_months <= 0:
            # If expiry is disabled (0 = never), skip expiration
            logger.info("Points expiry is disabled (expiry_months = 0)")
            return 0
        
        cutoff = (datetime.now() - timedelta(days=expiry_months * 30)).strftime("%Y-%m-%d")
        
        # ✅ FIX: Main query - expire points where expiry_date is in the past
        cursor.execute("""
            SELECT customer_id, SUM(points) as expired_points
            FROM customer_points_log
            WHERE type = 'earn'
              AND expiry_date IS NOT NULL
              AND date(expiry_date) < date('now')
            GROUP BY customer_id
            HAVING expired_points > 0
        """)
        expired = cursor.fetchall()
        
        # ✅ Also handle old data where expiry_date is NULL (fallback to created_at)
        cursor.execute("""
            SELECT customer_id, SUM(points) as expired_points
            FROM customer_points_log
            WHERE type = 'earn'
              AND expiry_date IS NULL
              AND date(created_at) < ?
            GROUP BY customer_id
            HAVING expired_points > 0
        """, (cutoff,))
        old_expired = cursor.fetchall()
        
        # Combine both results
        all_expired = expired + old_expired
        
        affected = 0
        for cust_id, pts in all_expired:
            # Deduct points from customer
            cursor.execute("UPDATE customers SET points = points - ? WHERE id = ?", (pts, cust_id))
            
            # Log the expiration
            cursor.execute("""
                INSERT INTO customer_points_log (customer_id, points, type, reference, created_at)
                VALUES (?, ?, 'expire', ?, ?)
            """, (cust_id, pts, f"auto_expiry_{today}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            # Update expiry_date on original entries to prevent double expiration
            cursor.execute("""
                UPDATE customer_points_log
                SET expiry_date = ?
                WHERE customer_id = ? 
                  AND type = 'earn' 
                  AND (expiry_date IS NULL OR expiry_date != '')
                  AND (date(expiry_date) < date('now') OR date(created_at) < ?)
            """, (today, cust_id, cutoff))
            
            affected += 1
        
        conn.commit()
        if affected:
            logger.info(f"Expired loyalty points for {affected} customer(s)")
        return affected


# =============================================================================
# ✅ FIXED: expire_points_for_customer() - Uses expiry_date
# =============================================================================
def expire_points_for_customer(customer_id):
    """
    Expire loyalty points for a specific customer based on expiry_date.
    
    ✅ FIX: Now correctly uses expiry_date column instead of created_at.
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get expiry months from settings
        cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
        row = cursor.fetchone()
        expiry_months = int(row[0]) if row else 12
        
        if expiry_months <= 0:
            # If expiry is disabled (0 = never), skip expiration
            logger.debug(f"Points expiry disabled for customer {customer_id}")
            return 0
        
        cutoff = (datetime.now() - timedelta(days=expiry_months * 30)).strftime("%Y-%m-%d")
        
        # ✅ FIX: Primary expiration based on expiry_date
        cursor.execute("""
            SELECT SUM(points) as expired_points
            FROM customer_points_log
            WHERE customer_id = ?
              AND type = 'earn'
              AND expiry_date IS NOT NULL
              AND date(expiry_date) < date('now')
            GROUP BY customer_id
        """, (customer_id,))
        row = cursor.fetchone()
        
        # Also check old data where expiry_date is NULL (fallback to created_at)
        cursor.execute("""
            SELECT SUM(points) as expired_points
            FROM customer_points_log
            WHERE customer_id = ?
              AND type = 'earn'
              AND expiry_date IS NULL
              AND date(created_at) < ?
            GROUP BY customer_id
        """, (customer_id, cutoff))
        old_row = cursor.fetchone()
        
        pts = 0
        if row and row[0]:
            pts += row[0]
        if old_row and old_row[0]:
            pts += old_row[0]
        
        if pts == 0:
            return 0
        
        # Deduct points
        cursor.execute("UPDATE customers SET points = points - ? WHERE id = ?", (pts, customer_id))
        
        # Log the expiration
        cursor.execute("""
            INSERT INTO customer_points_log (customer_id, points, type, reference, created_at)
            VALUES (?, ?, 'expire', ?, ?)
        """, (customer_id, pts, f"auto_expiry_{today}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # Update expiry_date on original entries to prevent double expiration
        cursor.execute("""
            UPDATE customer_points_log
            SET expiry_date = ?
            WHERE customer_id = ? 
              AND type = 'earn' 
              AND (expiry_date IS NULL OR expiry_date != '')
              AND (date(expiry_date) < date('now') OR date(created_at) < ?)
        """, (today, customer_id, cutoff))
        
        conn.commit()
        logger.info(f"Expired {pts} points for customer {customer_id}")
        return pts


def check_and_recover(show_gui=True):
    """Check and recover database inconsistencies."""
    with DBContext() as conn:
        cursor = conn.cursor()
        issues = []
        cursor.execute("""
            SELECT s.id, s.invoice_no, s.created_at
            FROM sales s
            WHERE s.status NOT IN ('completed', 'refunded')
              AND NOT EXISTS (SELECT 1 FROM sale_items WHERE sale_id = s.id)
        """)
        orphan = cursor.fetchall()
        if orphan:
            issues.append(('orphan_sales', orphan))
        cursor.execute("""
            SELECT id, invoice_no, created_at
            FROM sales
            WHERE status NOT IN ('completed', 'refunded')
              AND julianday('now') - julianday(created_at) > 1.0/24
        """)
        stale = cursor.fetchall()
        if stale:
            issues.append(('stale_sales', stale))
        cursor.execute("SELECT id, name, stock FROM products WHERE stock < 0")
        neg_stock = cursor.fetchall()
        if neg_stock:
            issues.append(('neg_stock', neg_stock))
        cursor.execute("SELECT id, name, points FROM customers WHERE points < 0")
        neg_points = cursor.fetchall()
        if neg_points:
            issues.append(('neg_points', neg_points))
    
    if not issues:
        return False
    
    if not show_gui:
        logger.warning(f"Recovery found issues: {issues}")
        return False
    
    from PyQt6.QtWidgets import QMessageBox
    msg = "Database recovery found inconsistencies:\n\n"
    for cat, data in issues:
        if cat == 'orphan_sales':
            msg += f"• {len(data)} sale(s) with no items\n"
        elif cat == 'stale_sales':
            msg += f"• {len(data)} stale sale(s)\n"
        elif cat == 'neg_stock':
            msg += f"• {len(data)} product(s) with negative stock\n"
        elif cat == 'neg_points':
            msg += f"• {len(data)} customer(s) with negative points\n"
    msg += "\nRepair automatically?"
    reply = QMessageBox.question(None, "Database Recovery", msg, 
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if reply != QMessageBox.StandardButton.Yes:
        return False
    
    with DBContext() as conn:
        cursor = conn.cursor()
        try:
            for cat, data in issues:
                if cat in ('orphan_sales', 'stale_sales'):
                    for sid, inv, _ in data:
                        cursor.execute("DELETE FROM sales WHERE id = ?", (sid,))
                        logger.info(f"Deleted {cat[:-7]} sale {inv}")
                elif cat == 'neg_stock':
                    for pid, name, _ in data:
                        cursor.execute("UPDATE products SET stock = 0 WHERE id = ?", (pid,))
                        logger.info(f"Reset negative stock for {name}")
                elif cat == 'neg_points':
                    for cid, name, _ in data:
                        cursor.execute("UPDATE customers SET points = 0 WHERE id = ?", (cid,))
                        logger.info(f"Reset negative points for {name}")
            conn.commit()
            QMessageBox.information(None, "Recovery Complete", "Database repaired.")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Recovery failed: {e}")
            QMessageBox.critical(None, "Recovery Error", f"Could not repair: {e}")
            return False