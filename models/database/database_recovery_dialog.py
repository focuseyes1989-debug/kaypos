# models/database/auto_backup.py
"""
Automatic database backup on startup
"""

import os
import shutil
from datetime import datetime
from loguru import logger


def auto_backup_on_startup(db_path: str = "database/pos.db", max_backups: int = 30):
    """
    Create automatic backup on application startup
    
    Args:
        db_path: Path to database
        max_backups: Maximum number of backups to keep
    """
    if not os.path.exists(db_path):
        logger.warning("Database file not found, skipping backup")
        return
    
    backup_dir = "database/backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"pos_backup_{timestamp}.db")
    
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Auto backup created: {backup_path}")
    except Exception as e:
        logger.error(f"Auto backup failed: {e}")
        return
    
    # Clean old backups
    try:
        backup_files = [f for f in os.listdir(backup_dir) 
                       if f.startswith("pos_backup_") and f.endswith(".db")]
        backup_files.sort()
        
        while len(backup_files) > max_backups:
            old_file = backup_files.pop(0)
            old_path = os.path.join(backup_dir, old_file)
            try:
                os.remove(old_path)
                logger.info(f"Removed old backup: {old_file}")
            except:
                pass
    except Exception as e:
        logger.error(f"Failed to clean old backups: {e}")