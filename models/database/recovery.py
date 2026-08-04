# models/database/recovery.py
"""
Database recovery and error handling
"""

import os
import shutil
import sqlite3
import sys
import subprocess
from datetime import datetime
from loguru import logger
from typing import Optional, Dict, List, Tuple


class DatabaseRecovery:
    """Database recovery and error handling"""
    
    def __init__(self, db_path: str = "database/pos.db"):
        self.db_path = db_path
        self.backup_dir = "database/backups"
        self.recovery_dir = "database/recovery"
        
    def check_database_health(self) -> Dict:
        """
        Check database health and return status
        
        Returns:
            Dict with health status and issues
        """
        result = {
            'healthy': False,
            'issues': [],
            'can_repair': False,
            'recommendation': None
        }
        
        # Check if database exists
        if not os.path.exists(self.db_path):
            result['issues'].append("Database file does not exist")
            result['recommendation'] = "create_new"
            return result
        
        # Check file size
        try:
            size = os.path.getsize(self.db_path)
            if size == 0:
                result['issues'].append("Database file is empty")
                result['recommendation'] = "restore_backup"
                return result
            if size < 1024:  # Less than 1KB - likely corrupted
                result['issues'].append("Database file is too small, may be corrupted")
                result['recommendation'] = "restore_backup"
        except Exception as e:
            result['issues'].append(f"Cannot read database file: {e}")
            result['recommendation'] = "restore_backup"
            return result
        
        # Check disk space
        try:
            db_dir = os.path.dirname(self.db_path)
            stat = os.statvfs(db_dir)
            free_space = stat.f_bavail * stat.f_frsize
            if free_space < 10 * 1024 * 1024:  # Less than 10MB
                result['issues'].append(f"Insufficient disk space: {free_space / (1024*1024):.1f} MB free")
                result['recommendation'] = "free_space"
        except:
            pass
        
        # Check if database is readable
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
        except sqlite3.DatabaseError as e:
            error_msg = str(e)
            if "database disk image is malformed" in error_msg:
                result['issues'].append("Database is corrupted (malformed)")
                result['recommendation'] = "repair_or_restore"
            elif "disk I/O error" in error_msg:
                result['issues'].append("Disk I/O error")
                result['recommendation'] = "check_disk"
            else:
                result['issues'].append(f"Database error: {error_msg}")
                result['recommendation'] = "restore_backup"
            return result
        except Exception as e:
            result['issues'].append(f"Connection error: {e}")
            result['recommendation'] = "restore_backup"
            return result
        
        # Check integrity
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result_check = cursor.fetchone()
            conn.close()
            
            if result_check and result_check[0] != 'ok':
                result['issues'].append(f"Integrity check failed: {result_check[0]}")
                result['recommendation'] = "repair_or_restore"
            else:
                result['healthy'] = True
                result['can_repair'] = True
        except Exception as e:
            result['issues'].append(f"Integrity check error: {e}")
            result['recommendation'] = "restore_backup"
        
        # Check if we have backups
        if result['recommendation'] in ['restore_backup', 'repair_or_restore']:
            backups = self.get_available_backups()
            if backups:
                result['can_repair'] = True
        
        return result
    
    def get_available_backups(self) -> List[Dict]:
        """Get list of available backups"""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        backup_files = [f for f in os.listdir(self.backup_dir) 
                       if f.startswith("pos_backup_") and f.endswith(".db")]
        
        for file in backup_files:
            file_path = os.path.join(self.backup_dir, file)
            try:
                stat = os.stat(file_path)
                # Extract timestamp from filename
                timestamp_str = file.replace("pos_backup_", "").replace(".db", "")
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except:
                    timestamp = datetime.fromtimestamp(stat.st_mtime)
                
                # Check if backup is valid
                try:
                    conn = sqlite3.connect(file_path, timeout=2)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    conn.close()
                    valid = True
                except:
                    valid = False
                
                backups.append({
                    'filename': file,
                    'path': file_path,
                    'size': stat.st_size,
                    'size_mb': stat.st_size / (1024 * 1024),
                    'timestamp': timestamp,
                    'created': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    'valid': valid
                })
            except:
                pass
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups
    
    def restore_backup(self, backup_path: str) -> Tuple[bool, str]:
        """
        Restore from backup with better error handling
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not os.path.exists(backup_path):
            return False, f"Backup file not found: {backup_path}"
        
        # Validate backup
        try:
            conn = sqlite3.connect(backup_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
        except Exception as e:
            return False, f"Invalid backup file: {e}"
        
        try:
            # Create recovery directory
            os.makedirs(self.recovery_dir, exist_ok=True)
            
            # Close all connections
            try:
                from models.database.pool import close_all_connections
                close_all_connections()
            except:
                pass
            
            # Backup current database before restoring
            if os.path.exists(self.db_path):
                recovery_path = os.path.join(
                    self.recovery_dir,
                    f"corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                )
                try:
                    shutil.copy2(self.db_path, recovery_path)
                    logger.info(f"Backed up corrupted database to: {recovery_path}")
                except:
                    pass
            
            # Remove sidecar files first
            for ext in ['-wal', '-shm']:
                sidecar = self.db_path + ext
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                        logger.info(f"Removed sidecar file: {sidecar}")
                    except:
                        pass
            
            # Copy backup to database location
            shutil.copy2(backup_path, self.db_path)
            
            # Verify restoration
            try:
                conn = sqlite3.connect(self.db_path, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
                cursor.fetchone()
                conn.close()
                return True, f"Database restored successfully from {os.path.basename(backup_path)}"
            except Exception as e:
                return False, f"Restoration verification failed: {e}"
            
        except Exception as e:
            return False, f"Restore failed: {e}"
    
    def repair_database(self) -> Tuple[bool, str]:
        """
        Attempt to repair the database using SQLite's recovery
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Create backup of corrupted database
            corrupt_backup = os.path.join(
                self.recovery_dir,
                f"corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            os.makedirs(self.recovery_dir, exist_ok=True)
            
            if os.path.exists(self.db_path):
                try:
                    shutil.copy2(self.db_path, corrupt_backup)
                    logger.info(f"Backed up corrupt database to: {corrupt_backup}")
                except:
                    pass
            
            # Try to repair using SQLite
            temp_db = self.db_path + ".recovered"
            
            # Try using sqlite3 command line tool
            try:
                result = subprocess.run(
                    ['sqlite3', self.db_path, '.recover', temp_db],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    logger.warning(f"SQLite recover failed: {result.stderr}")
                    # Try alternative method
                    return self._repair_with_dump()
            except Exception as e:
                logger.warning(f"SQLite recover error: {e}")
                return self._repair_with_dump()
            
            # Check if recovered file exists and is valid
            if not os.path.exists(temp_db) or os.path.getsize(temp_db) == 0:
                return False, "Recovery produced empty file"
            
            # Validate recovered database
            try:
                conn = sqlite3.connect(temp_db, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
                cursor.fetchone()
                conn.close()
            except Exception as e:
                return False, f"Recovered database is invalid: {e}"
            
            # Replace original with recovered
            try:
                shutil.copy2(temp_db, self.db_path)
                os.remove(temp_db)
            except:
                pass
            
            return True, "Database repaired successfully (some data may be lost)"
            
        except Exception as e:
            return False, f"Repair failed: {e}"
    
    def _repair_with_dump(self) -> Tuple[bool, str]:
        """
        Alternative repair method using .dump and .restore
        """
        try:
            dump_file = self.db_path + ".dump"
            
            # Dump database
            result = subprocess.run(
                ['sqlite3', self.db_path, '.dump'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                return False, "Dump failed"
            
            # Write dump to file
            with open(dump_file, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            
            # Create new database from dump
            new_db = self.db_path + ".new"
            subprocess.run(
                ['sqlite3', new_db, '.read', dump_file],
                capture_output=True,
                timeout=120
            )
            
            # Validate new database
            try:
                conn = sqlite3.connect(new_db, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
                cursor.fetchone()
                conn.close()
            except Exception as e:
                return False, f"New database is invalid: {e}"
            
            # Replace original
            shutil.copy2(new_db, self.db_path)
            os.remove(new_db)
            os.remove(dump_file)
            
            return True, "Database repaired using dump/restore method"
            
        except Exception as e:
            return False, f"Alternative repair failed: {e}"
    
    def create_emergency_db(self) -> Tuple[bool, str]:
        """
        Create a new empty database
        """
        try:
            # Close all connections
            try:
                from models.database.pool import close_all_connections
                close_all_connections()
            except:
                pass
            
            # Backup existing if exists
            if os.path.exists(self.db_path):
                backup_path = os.path.join(
                    self.recovery_dir,
                    f"emergency_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                )
                os.makedirs(self.recovery_dir, exist_ok=True)
                try:
                    shutil.copy2(self.db_path, backup_path)
                except:
                    pass
            
            # Remove sidecar files
            for ext in ['-wal', '-shm']:
                sidecar = self.db_path + ext
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except:
                        pass
            
            # Remove old database
            if os.path.exists(self.db_path):
                try:
                    os.remove(self.db_path)
                except:
                    pass
            
            # Create new database
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
            
            # Run migrations
            from models.database.migrations import run_migrations
            run_migrations()
            
            # Create tables
            from models.database.tables import create_tables
            create_tables()
            
            return True, "New database created successfully"
            
        except Exception as e:
            return False, f"Failed to create emergency database: {e}"
    
    def auto_recover(self) -> Tuple[bool, str]:
        """
        Attempt automatic recovery with multiple strategies
        """
        # Check health
        health = self.check_database_health()
        
        if health['healthy']:
            return True, "Database is healthy"
        
        logger.warning(f"Database issues found: {health['issues']}")
        logger.warning(f"Recommendation: {health['recommendation']}")
        
        # Strategy 1: Try to get a valid backup
        backups = self.get_available_backups()
        valid_backups = [b for b in backups if b['valid']]
        
        if valid_backups:
            logger.info(f"Found {len(valid_backups)} valid backups")
            # Try each backup from newest to oldest
            for backup in valid_backups:
                logger.info(f"Trying backup: {backup['created']} ({backup['size_mb']:.1f} MB)")
                success, message = self.restore_backup(backup['path'])
                if success:
                    return True, f"Restored from backup: {backup['created']}"
                else:
                    logger.warning(f"Backup restore failed: {message}")
        
        # Strategy 2: Try repair
        logger.info("Attempting database repair...")
        success, message = self.repair_database()
        if success:
            return True, "Database repaired"
        else:
            logger.warning(f"Repair failed: {message}")
        
        # Strategy 3: Try to create new database
        logger.info("Creating new database...")
        success, message = self.create_emergency_db()
        if success:
            return True, "Created new database"
        
        return False, "All recovery attempts failed"
    
    def get_recovery_status(self) -> Dict:
        """
        Get detailed recovery status for user display
        """
        health = self.check_database_health()
        backups = self.get_available_backups()
        
        return {
            'healthy': health['healthy'],
            'issues': health['issues'],
            'has_backups': len(backups) > 0,
            'backup_count': len(backups),
            'latest_backup': backups[0] if backups else None,
            'recommendation': health.get('recommendation', 'unknown'),
            'can_auto_recover': health.get('can_repair', False) or len(backups) > 0
        }