# app/config.py
"""
Application configuration.
"""

import sys
from utils.paths import (
    get_app_root,
    app_path,
    get_db_path,
    get_log_dir,
    get_assets_dir,
    get_backup_dir,
    get_temp_dir,
    get_product_images_dir
)


class AppConfig:
    """Application configuration."""
    
    # ========== Paths - Using properties ==========
    
    @property
    def DB_PATH(self):
        """Get database path."""
        return get_db_path()
    
    @property
    def LOG_DIR(self):
        """Get log directory."""
        return get_log_dir()
    
    @property
    def ASSETS_DIR(self):
        """Get assets directory."""
        return get_assets_dir()
    
    @property
    def BACKUP_DIR(self):
        """Get backup directory."""
        return get_backup_dir()
    
    @property
    def TEMP_DIR(self):
        """Get temp directory."""
        return get_temp_dir()
    
    @property
    def PRODUCT_IMAGES_DIR(self):
        """Get product images directory."""
        return get_product_images_dir()
    
    # ========== Version ==========
    
    @staticmethod
    def get_app_version():
        """Get application version."""
        try:
            from updater.version_manager import VersionManager
            return VersionManager().get_current_version()
        except:
            return "1.0.0"


# ========== Singleton instance ==========
config = AppConfig()