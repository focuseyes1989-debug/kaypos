# utils/auto_backup.py
import os
import shutil
from datetime import datetime
from loguru import logger
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from models.database import connect_db


class AutoBackupManager(QObject):
    backup_started = pyqtSignal(str)
    backup_created = pyqtSignal(str)
    backup_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backup_dir = "database/backups"
        self.interval_hours = 24  # Default: every 24 hours
        self.max_backups = 30  # Keep maximum 30 backups
        self.timer = QTimer()
        self.timer.timeout.connect(self.create_backup)
        self.running = False
        
        # Create backup directory if not exists
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Load settings
        self.load_settings()
        
        # Store last backup time
        self.last_backup_time = self.get_last_backup_time()

    def load_settings(self):
        """Load auto backup settings from database"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='auto_backup_enabled'")
            row = cursor.fetchone()
            self.enabled = row[0] == '1' if row else False
            
            cursor.execute("SELECT value FROM settings WHERE key='auto_backup_interval'")
            row = cursor.fetchone()
            if row:
                self.interval_hours = int(row[0])
            
            cursor.execute("SELECT value FROM settings WHERE key='auto_backup_max'")
            row = cursor.fetchone()
            if row:
                self.max_backups = int(row[0])
            
            conn.close()
        except Exception as e:
            logger.error(f"Failed to load auto backup settings: {e}")
            self.enabled = False

    def start(self):
        """Start auto backup timer"""
        if self.enabled:
            # Start timer (interval in milliseconds)
            interval_ms = self.interval_hours * 3600000
            self.timer.start(interval_ms)
            self.running = True
            logger.info(f"Auto backup started - Interval: {self.interval_hours} hours")
            # Create first backup after 5 seconds
            QTimer.singleShot(5000, self.create_backup)

    def stop(self):
        """Stop auto backup timer"""
        self.timer.stop()
        self.running = False
        logger.info("Auto backup stopped")

    def get_last_backup_time(self):
        """Get the timestamp of the most recent backup file"""
        try:
            if not os.path.exists(self.backup_dir):
                return None
            
            backups = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("pos_backup_auto_") and filename.endswith(".db"):
                    file_path = os.path.join(self.backup_dir, filename)
                    # Extract timestamp from filename
                    # Format: pos_backup_auto_20250614_103000.db
                    try:
                        timestamp_str = filename.replace("pos_backup_auto_", "").replace(".db", "")
                        backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        backups.append((backup_time, file_path))
                    except:
                        # If filename parsing fails, use file modification time
                        mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        backups.append((mod_time, file_path))
            
            if backups:
                backups.sort(key=lambda x: x[0], reverse=True)
                return backups[0][0]
            return None
        except Exception as e:
            logger.error(f"Failed to get last backup time: {e}")
            return None

    def get_last_backup_time_str(self):
        """Get formatted last backup time string"""
        last_time = self.get_last_backup_time()
        if last_time:
            return last_time.strftime("%Y-%m-%d %I:%M %p")
        return "No backup yet"

    def create_backup(self):
        """Create a database backup"""
        if not self.enabled:
            return
        
        try:
            db_path = "database/pos.db"
            if not os.path.exists(db_path):
                logger.warning("Database file not found for backup")
                return
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"pos_backup_auto_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            self.backup_started.emit("Auto backup: creating database backup")
            
            # Copy database file
            shutil.copy2(db_path, backup_path)
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            size_mb = file_size / (1024 * 1024)
            
            # Update last backup time
            self.last_backup_time = datetime.now()
            
            logger.info(f"Auto backup created: {backup_filename} ({size_mb:.2f} MB)")
            self.backup_created.emit(f"Backup created: {backup_filename}")
            
            # Clean old backups
            self.clean_old_backups()
            
            # Emit signal to update dashboard
            if hasattr(self.parent(), 'update_backup_status'):
                self.parent().update_backup_status()
            
        except Exception as e:
            logger.error(f"Auto backup failed: {e}")
            self.backup_failed.emit(f"Backup failed: {str(e)}")

    def clean_old_backups(self):
        """Delete old backups exceeding max_backups count"""
        try:
            # Get all backup files
            files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("pos_backup_auto_") and filename.endswith(".db"):
                    file_path = os.path.join(self.backup_dir, filename)
                    files.append((file_path, os.path.getmtime(file_path)))
            
            # Sort by modification time (oldest first)
            files.sort(key=lambda x: x[1])
            
            # Delete old backups
            while len(files) > self.max_backups:
                file_path, _ = files.pop(0)
                os.remove(file_path)
                logger.info(f"Deleted old backup: {os.path.basename(file_path)}")
                
        except Exception as e:
            logger.error(f"Failed to clean old backups: {e}")

    def update_settings(self, enabled, interval_hours, max_backups):
        """Update auto backup settings"""
        self.enabled = enabled
        self.interval_hours = interval_hours
        self.max_backups = max_backups
        
        # Save to database
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                          ("auto_backup_enabled", '1' if enabled else '0'))
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                          ("auto_backup_interval", str(interval_hours)))
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                          ("auto_backup_max", str(max_backups)))
            conn.commit()
            conn.close()
            
            # Restart timer with new interval
            self.stop()
            if enabled:
                self.start()
                
        except Exception as e:
            logger.error(f"Failed to save auto backup settings: {e}")