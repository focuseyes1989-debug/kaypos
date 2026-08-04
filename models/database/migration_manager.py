# models/database/migration_manager.py
"""
Advanced database migration manager with rollback support.
"""

import os
import sqlite3
import re
from loguru import logger
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

# ✅ Bug #3 Fixed: Add packaging.version for proper version sorting
try:
    from packaging.version import Version
except ImportError:
    # Fallback for older Python versions
    class Version:
        def __init__(self, version):
            self.version = version
            self.parts = [int(x) for x in version.split('.')]
        
        def __lt__(self, other):
            return self.parts < other.parts
        
        def __eq__(self, other):
            return self.parts == other.parts
        
        def __gt__(self, other):
            return self.parts > other.parts

DB_NAME = "database/pos.db"
MIGRATION_TABLE = "migration_history"
APP_METADATA_TABLE = "app_metadata"


class MigrationStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Migration:
    """Migration definition."""
    version: str
    name: str
    description: str
    up_sql: str
    down_sql: Optional[str] = None
    dependencies: List[str] = None
    requires_restart: bool = False
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class MigrationManager:
    """Handle database migrations with rollback support."""
    
    def __init__(self, db_path: str = DB_NAME):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Connect to database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.isolation_level = 'DEFERRED'
        self.cursor = self.conn.cursor()
        self._ensure_migration_table()
        self._ensure_app_metadata_table()
        
    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()
            
    def _ensure_migration_table(self):
        """
        Create migration history table if not exists.
        
        ✅ Bug #4 Fixed: Use id as PRIMARY KEY only, no UNIQUE constraint
        """
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rolled_back_at TIMESTAMP,
                executed_by TEXT,
                execution_time REAL,
                error_message TEXT
            )
        """)
        
        # ✅ Bug #4 Fixed: Add indexes for faster queries
        self.cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_migration_version 
            ON {MIGRATION_TABLE}(version)
        """)
        self.cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_migration_status 
            ON {MIGRATION_TABLE}(status)
        """)
        self.cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_migration_applied_at 
            ON {MIGRATION_TABLE}(applied_at DESC)
        """)
        
        self.conn.commit()
    
    def _ensure_app_metadata_table(self):
        """
        Create app_metadata table for tracking application and database versions.
        
        ✅ Bug #4 Fixed: Add app_metadata table for version tracking
        """
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {APP_METADATA_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_version TEXT NOT NULL,
                db_version TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        """)
        
        # Insert initial record if table is empty
        self.cursor.execute(f"SELECT COUNT(*) FROM {APP_METADATA_TABLE}")
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute(f"""
                INSERT INTO {APP_METADATA_TABLE} (app_version, db_version, notes)
                VALUES (?, ?, ?)
            """, ("1.0.0", "0.0.0", "Initial database creation"))
            self.conn.commit()
            logger.info("App metadata table initialized")
        
        self.conn.commit()
    
    def get_app_metadata(self) -> Dict:
        """Get current app metadata."""
        self.cursor.execute(f"""
            SELECT app_version, db_version, updated_at, notes
            FROM {APP_METADATA_TABLE}
            ORDER BY id DESC
            LIMIT 1
        """)
        row = self.cursor.fetchone()
        if row:
            return {
                'app_version': row[0],
                'db_version': row[1],
                'updated_at': row[2],
                'notes': row[3]
            }
        return None
    
    def update_app_metadata(self, app_version: str, db_version: str, notes: str = ""):
        """Update app metadata."""
        self.cursor.execute(f"""
            INSERT INTO {APP_METADATA_TABLE} (app_version, db_version, notes)
            VALUES (?, ?, ?)
        """, (app_version, db_version, notes))
        self.conn.commit()
        logger.info(f"App metadata updated: app_version={app_version}, db_version={db_version}")
    
    def get_applied_migrations(self) -> List[str]:
        """
        Get list of successfully applied migrations.
        
        ✅ Bug #4 Fixed: Get latest status per version
        """
        self.cursor.execute(f"""
            SELECT DISTINCT version 
            FROM {MIGRATION_TABLE} 
            WHERE status = 'applied'
            ORDER BY id
        """)
        return [row[0] for row in self.cursor.fetchall()]
    
    def get_migration_history(self, version: str = None) -> List[Dict]:
        """
        Get full migration history for a version.
        
        ✅ Bug #4 Fixed: Get complete history
        """
        query = f"""
            SELECT id, version, name, description, status, 
                   applied_at, rolled_back_at, executed_by, 
                   execution_time, error_message
            FROM {MIGRATION_TABLE}
        """
        params = []
        
        if version:
            query += " WHERE version = ?"
            params.append(version)
        
        query += " ORDER BY id DESC"
        
        self.cursor.execute(query, params)
        columns = ['id', 'version', 'name', 'description', 'status', 
                   'applied_at', 'rolled_back_at', 'executed_by', 
                   'execution_time', 'error_message']
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
    
    def mark_migration_applied(self, migration: Migration, execution_time: float = 0):
        """
        Mark migration as applied.
        
        ✅ Bug #4 Fixed: Insert new record instead of update
        """
        self.cursor.execute(f"""
            INSERT INTO {MIGRATION_TABLE} 
            (version, name, description, status, execution_time)
            VALUES (?, ?, ?, ?, ?)
        """, (migration.version, migration.name, migration.description, 
              MigrationStatus.APPLIED.value, execution_time))
        self.conn.commit()
        logger.info(f"Migration applied: {migration.version} - {migration.name}")
        
    def mark_migration_failed(self, migration: Migration, error: str):
        """
        Mark migration as failed.
        
        ✅ Bug #4 Fixed: Insert new record instead of update
        """
        self.cursor.execute(f"""
            INSERT INTO {MIGRATION_TABLE} 
            (version, name, description, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (migration.version, migration.name, migration.description,
              MigrationStatus.FAILED.value, error))
        self.conn.commit()
        logger.error(f"Migration failed: {migration.version} - {error}")
        
    def mark_migration_rolled_back(self, migration: Migration):
        """
        Mark migration as rolled back.
        
        ✅ Bug #4 Fixed: Insert new record instead of update
        """
        self.cursor.execute(f"""
            INSERT INTO {MIGRATION_TABLE} 
            (version, name, description, status, rolled_back_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (migration.version, migration.name, migration.description,
              MigrationStatus.ROLLED_BACK.value))
        self.conn.commit()
        logger.info(f"Migration rolled back: {migration.version} - {migration.name}")
    
    # ============================================================
    # ✅ FIX: get_failed_migrations method (was missing)
    # ============================================================
    def get_failed_migrations(self) -> List[Dict]:
        """
        Get list of failed migrations.
        
        Returns:
            List[Dict]: List of failed migrations with details
        """
        try:
            self.cursor.execute(f"""
                SELECT version, name, error_message, applied_at
                FROM {MIGRATION_TABLE}
                WHERE status = 'failed'
                ORDER BY id DESC
            """)
            columns = ['version', 'name', 'error', 'applied_at']
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get failed migrations: {e}")
            return []
    
    def column_exists(self, table: str, column: str) -> bool:
        """Check if column exists."""
        try:
            self.cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in self.cursor.fetchall()]
            return column in columns
        except Exception:
            return False
            
    def table_exists(self, table: str) -> bool:
        """Check if table exists."""
        try:
            self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table,))
            return self.cursor.fetchone() is not None
        except Exception:
            return False
    
    def safe_add_column(self, table: str, column: str, column_def: str) -> bool:
        """
        Safely add column if not exists.
        
        ✅ FIX: Handle UNIQUE constraint separately (SQLite doesn't support ALTER TABLE ADD COLUMN with UNIQUE)
        """
        if not self.column_exists(table, column):
            try:
                # ✅ Handle UNIQUE constraint separately
                if 'UNIQUE' in column_def.upper():
                    # Remove UNIQUE from column definition
                    clean_def = column_def.replace('UNIQUE', '').strip()
                    sql = f"ALTER TABLE {table} ADD COLUMN {column} {clean_def}"
                    self.cursor.execute(sql)
                    self.conn.commit()
                    logger.info(f"Added column {column} to {table}")
                    
                    # Create unique index separately
                    try:
                        idx_name = f"idx_{table}_{column}_unique"
                        self.cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                        self.conn.commit()
                        logger.info(f"Created unique index for {column} on {table}")
                    except Exception as idx_e:
                        logger.warning(f"Could not create unique index for {column}: {idx_e}")
                    return True
                else:
                    sql = f"ALTER TABLE {table} ADD COLUMN {column} {column_def}"
                    self.cursor.execute(sql)
                    self.conn.commit()
                    logger.info(f"Added column {column} to {table}")
                    return True
            except Exception as e:
                logger.warning(f"Could not add column {column} to {table}: {e}")
                return False
        return False
    
    def safe_add_setting(self, key: str, default_value: str) -> bool:
        """
        Safely add setting if not exists.
        
        ✅ Bug #2 Fixed: Check if settings table exists first
        """
        if not self.table_exists("settings"):
            logger.warning(f"Settings table does not exist yet, skipping setting: {key}")
            return False
        
        try:
            self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            if not self.cursor.fetchone():
                self.cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                                  (key, default_value))
                self.conn.commit()
                logger.info(f"Added setting: {key}")
                return True
        except Exception as e:
            logger.warning(f"Could not add setting {key}: {e}")
            return False
        
        return False
    
    def _execute_sql(self, sql: str) -> bool:
        """Execute SQL with error handling."""
        try:
            if sql and sql.strip() and sql.strip() != "SELECT 1;":
                # Split into individual statements for better error handling
                statements = sql.split(';')
                for stmt in statements:
                    stmt = stmt.strip()
                    if stmt and stmt != "SELECT 1":
                        try:
                            self.cursor.execute(stmt)
                        except Exception as e:
                            # If it's a duplicate column error, continue
                            if "duplicate column" in str(e).lower():
                                logger.warning(f"Skipped duplicate column: {e}")
                                continue
                            raise
            return True
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise
    
    def _sort_migrations(self, migrations: List[Migration]) -> List[Migration]:
        """
        Sort migrations by version using proper semantic versioning.
        
        ✅ Bug #3 Fixed: Use packaging.version.Version for correct sorting
        """
        return sorted(migrations, key=lambda m: Version(m.version))
    
    def run_migration(self, migration: Migration) -> Tuple[bool, Optional[str]]:
        """Run a single migration."""
        # ✅ Bug #4 Fixed: Check if already applied (latest status)
        self.cursor.execute(f"""
            SELECT status FROM {MIGRATION_TABLE}
            WHERE version = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, (migration.version,))
        
        row = self.cursor.fetchone()
        if row and row[0] == MigrationStatus.APPLIED.value:
            logger.debug(f"Migration {migration.version} already applied")
            return True, None
        
        # Check dependencies
        for dep in migration.dependencies:
            self.cursor.execute(f"""
                SELECT status FROM {MIGRATION_TABLE}
                WHERE version = ? 
                ORDER BY id DESC 
                LIMIT 1
            """, (dep,))
            row = self.cursor.fetchone()
            if not row or row[0] != MigrationStatus.APPLIED.value:
                error = f"Migration {migration.version} depends on {dep} which is not applied"
                logger.error(error)
                return False, error
        
        start_time = datetime.now()
        
        try:
            logger.info(f"Running migration: {migration.version} - {migration.name}")
            
            # Start transaction
            self.conn.execute("BEGIN TRANSACTION")
            
            # Execute up migration
            if migration.up_sql and migration.up_sql.strip():
                self._execute_sql(migration.up_sql)
            
            # Mark as applied
            execution_time = (datetime.now() - start_time).total_seconds()
            self.mark_migration_applied(migration, execution_time)
            
            # ✅ Bug #4 Fixed: Update app_metadata
            metadata = self.get_app_metadata()
            if metadata:
                self.update_app_metadata(
                    app_version=metadata['app_version'],
                    db_version=migration.version,
                    notes=f"Migration applied: {migration.version} - {migration.name}"
                )
            
            self.conn.commit()
            return True, None
            
        except Exception as e:
            error_msg = str(e)
            self.conn.rollback()
            self.mark_migration_failed(migration, error_msg)
            logger.error(f"Migration {migration.version} failed: {error_msg}")
            return False, error_msg
    
    def rollback_migration(self, migration: Migration) -> Tuple[bool, Optional[str]]:
        """Rollback a single migration."""
        if not migration.down_sql:
            return False, "No down migration available"
        
        # ✅ Bug #4 Fixed: Check if applied (latest status)
        self.cursor.execute(f"""
            SELECT status FROM {MIGRATION_TABLE}
            WHERE version = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, (migration.version,))
        
        row = self.cursor.fetchone()
        if not row or row[0] != MigrationStatus.APPLIED.value:
            return False, "Migration not applied"
            
        try:
            logger.info(f"Rolling back: {migration.version} - {migration.name}")
            
            self.conn.execute("BEGIN TRANSACTION")
            
            if migration.down_sql and migration.down_sql.strip():
                self._execute_sql(migration.down_sql)
            
            self.mark_migration_rolled_back(migration)
            
            # ✅ Bug #4 Fixed: Update app_metadata
            metadata = self.get_app_metadata()
            if metadata:
                # Find previous applied version
                self.cursor.execute(f"""
                    SELECT version FROM {MIGRATION_TABLE}
                    WHERE status = 'applied'
                    ORDER BY id DESC
                    LIMIT 1
                """)
                prev_row = self.cursor.fetchone()
                prev_version = prev_row[0] if prev_row else "0.0.0"
                
                self.update_app_metadata(
                    app_version=metadata['app_version'],
                    db_version=prev_version,
                    notes=f"Rolled back: {migration.version} - {migration.name}"
                )
            
            self.conn.commit()
            return True, None
            
        except Exception as e:
            error_msg = str(e)
            self.conn.rollback()
            logger.error(f"Rollback failed: {error_msg}")
            return False, error_msg
    
    def run_migrations(self, migrations: List[Migration], 
                      target_version: Optional[str] = None,
                      app_version: Optional[str] = None) -> Dict:
        """
        Run all pending migrations.
        
        ✅ Bug #4 Fixed: Add app_version parameter
        """
        results = {
            'applied': [],
            'failed': [],
            'skipped': [],
            'app_version': app_version,
            'db_version': target_version
        }
        
        # ✅ Bug #3 Fixed: Sort migrations by version properly
        sorted_migrations = self._sort_migrations(migrations)
        
        # ✅ Bug #4 Fixed: Get current app version
        if not app_version:
            metadata = self.get_app_metadata()
            if metadata:
                app_version = metadata['app_version']
            else:
                app_version = "1.0.0"
        
        for migration in sorted_migrations:
            # Check if we've reached target version
            if target_version:
                if Version(migration.version) > Version(target_version):
                    results['skipped'].append(migration.version)
                    continue
                
            success, error = self.run_migration(migration)
            if success:
                results['applied'].append(migration.version)
            else:
                results['failed'].append({
                    'version': migration.version,
                    'error': error
                })
                # Stop on failure if critical
                break
        
        # ✅ Bug #4 Fixed: Final metadata update
        if results['applied']:
            metadata = self.get_app_metadata()
            if metadata:
                self.update_app_metadata(
                    app_version=app_version,
                    db_version=results['applied'][-1],
                    notes=f"Auto migration completed: {len(results['applied'])} migrations applied"
                )
        
        return results
    
    def rollback_to_version(self, migrations: List[Migration], 
                           target_version: str) -> Dict:
        """Rollback to a specific version."""
        results = {
            'rolled_back': [],
            'failed': []
        }
        
        # ✅ Bug #3 Fixed: Sort migrations in reverse order properly
        sorted_migrations = self._sort_migrations(migrations)
        
        # Get migrations to rollback (reverse order)
        to_rollback = [
            m for m in reversed(sorted_migrations)
            if m.version in self.get_applied_migrations() 
            and Version(m.version) > Version(target_version)
        ]
        
        for migration in to_rollback:
            success, error = self.rollback_migration(migration)
            if success:
                results['rolled_back'].append(migration.version)
            else:
                results['failed'].append({
                    'version': migration.version,
                    'error': error
                })
                break
                
        return results
    
    def get_migration_status(self, migrations: List[Migration]) -> Dict:
        """Get detailed migration status."""
        applied = self.get_applied_migrations()
        failed = self.get_failed_migrations()
        
        # ✅ Bug #3 Fixed: Use proper version sorting
        sorted_migrations = self._sort_migrations(migrations)
        
        # ✅ Bug #4 Fixed: Get app metadata
        metadata = self.get_app_metadata()
        
        status = {
            'current_version': max(applied, key=lambda v: Version(v)) if applied else "0.0.0",
            'applied': applied,
            'failed': [f['version'] for f in failed],
            'pending': [],
            'total': len(sorted_migrations),
            'app_version': metadata['app_version'] if metadata else "Unknown",
            'last_updated': metadata['updated_at'] if metadata else None
        }
        
        for m in sorted_migrations:
            if m.version not in applied and m.version not in [f['version'] for f in failed]:
                status['pending'].append(m.version)
                
        return status


# ✅ Bug #3 Fixed: Helper function for version comparison
def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.
    
    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2
    """
    v1 = Version(version1)
    v2 = Version(version2)
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def get_latest_version(versions: List[str]) -> Optional[str]:
    """
    Get the latest version from a list of version strings.
    """
    if not versions:
        return None
    return max(versions, key=lambda v: Version(v))