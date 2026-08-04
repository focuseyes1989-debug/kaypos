# utils/paths.py
"""
Path utilities for application.
Supports both development and PyInstaller frozen executables.
"""

import os
import sys
from typing import Optional


# ============================================================================
# CORE PATH FUNCTIONS
# ============================================================================

def get_app_root() -> str:
    """
    Return the writable application root for source and PyInstaller runs.
    
    Returns:
        str: Application root directory path
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_path(*parts: str) -> str:
    """
    Join parts with the application root directory.
    
    Args:
        *parts: Path parts to join
    
    Returns:
        str: Full path joined with app root
    """
    return os.path.join(get_app_root(), *parts)


def app_relative_path(path: str) -> str:
    """
    Convert an absolute path to a relative path from the application root.
    
    Args:
        path: Absolute path to convert
    
    Returns:
        str: Relative path from app root
    """
    return os.path.relpath(path, get_app_root()).replace("\\", "/")


# ============================================================================
# DATABASE PATHS
# ============================================================================

def get_db_path() -> str:
    """
    Get database file path.
    
    Returns:
        str: Full path to database file
    """
    return app_path('database', 'pos.db')


def get_db_dir() -> str:
    """
    Get database directory path.
    
    Returns:
        str: Database directory path
    """
    return app_path('database')


def get_backup_dir() -> str:
    """
    Get backup directory path.
    
    Returns:
        str: Backup directory path
    """
    return app_path('database', 'backups')


def get_recovery_dir() -> str:
    """
    Get recovery directory path.
    
    Returns:
        str: Recovery directory path
    """
    return app_path('database', 'recovery')


# ============================================================================
# LOG PATHS
# ============================================================================

def get_log_dir() -> str:
    """
    Get log directory path.
    
    Returns:
        str: Log directory path
    """
    return app_path('logs')


def get_log_path(filename: Optional[str] = None) -> str:
    """
    Get log file path.
    
    Args:
        filename: Optional log filename (default: zaypos_{date}.log)
    
    Returns:
        str: Full log file path
    """
    if filename:
        return os.path.join(get_log_dir(), filename)
    return get_log_dir()


# ============================================================================
# ASSETS PATHS
# ============================================================================

def get_assets_dir() -> str:
    """
    Get assets directory path.
    
    Returns:
        str: Assets directory path
    """
    return app_path('assets')


def get_fonts_dir() -> str:
    """
    Get fonts directory path.
    
    Returns:
        str: Fonts directory path
    """
    return app_path('assets', 'fonts')


def get_icons_dir() -> str:
    """
    Get icons directory path.
    
    Returns:
        str: Icons directory path
    """
    return app_path('assets', 'icons')


def get_images_dir() -> str:
    """
    Get images directory path.
    
    Returns:
        str: Images directory path
    """
    return app_path('assets', 'images')


# ============================================================================
# PRODUCT IMAGES PATHS
# ============================================================================

def get_product_images_dir() -> str:
    """
    Get product images directory path.
    
    Returns:
        str: Product images directory path
    """
    return app_path('database', 'product_images')


def get_product_thumbnails_dir() -> str:
    """
    Get product thumbnails directory path.
    
    Returns:
        str: Product thumbnails directory path
    """
    return app_path('database', 'product_images', 'thumbnails')


# ============================================================================
# TEMP PATHS
# ============================================================================

def get_temp_dir() -> str:
    """
    Get temporary directory path.
    
    Returns:
        str: Temp directory path
    """
    return app_path('temp')


def get_temp_file(filename: str) -> str:
    """
    Get temporary file path.
    
    Args:
        filename: Temporary filename
    
    Returns:
        str: Full temp file path
    """
    return os.path.join(get_temp_dir(), filename)


# ============================================================================
# ATTACHMENTS PATHS
# ============================================================================

def get_attachments_dir() -> str:
    """
    Get attachments directory path.
    
    Returns:
        str: Attachments directory path
    """
    return app_path('attachments')


# ============================================================================
# BACKUP PATHS
# ============================================================================

def get_backup_path(filename: Optional[str] = None) -> str:
    """
    Get backup file path.
    
    Args:
        filename: Optional backup filename
    
    Returns:
        str: Full backup file path
    """
    if filename:
        return os.path.join(get_backup_dir(), filename)
    return get_backup_dir()


# ============================================================================
# RESOURCES PATHS
# ============================================================================

def get_resources_dir() -> str:
    """
    Get resources directory path.
    
    Returns:
        str: Resources directory path
    """
    return app_path('resources')


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def ensure_directories():
    """
    Ensure all required directories exist.
    Creates directories if they don't exist.
    """
    directories = [
        get_db_dir(),
        get_backup_dir(),
        get_recovery_dir(),
        get_log_dir(),
        get_temp_dir(),
        get_attachments_dir(),
        get_product_images_dir(),
        get_product_thumbnails_dir(),
        get_fonts_dir(),
        get_icons_dir(),
        get_images_dir(),
        get_resources_dir(),
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Could not create directory {directory}: {e}")


def is_frozen() -> bool:
    """
    Check if running as frozen executable.
    
    Returns:
        bool: True if running as EXE
    """
    return getattr(sys, "frozen", False)


def get_platform() -> str:
    """
    Get current platform.
    
    Returns:
        str: Platform name ('windows', 'linux', 'darwin')
    """
    if sys.platform == 'win32':
        return 'windows'
    elif sys.platform == 'darwin':
        return 'darwin'
    else:
        return 'linux'


# ============================================================================
# BACKWARD COMPATIBILITY - Old API
# ============================================================================

# These are kept for backward compatibility with existing code

def get_db_path_old():
    """Legacy: Use get_db_path() instead."""
    return get_db_path()


def get_log_dir_old():
    """Legacy: Use get_log_dir() instead."""
    return get_log_dir()


def get_assets_dir_old():
    """Legacy: Use get_assets_dir() instead."""
    return get_assets_dir()


# ============================================================================
# PRINT CONFIGURATION (for debugging)
# ============================================================================

def print_paths():
    """
    Print all paths for debugging.
    """
    print("=" * 60)
    print("ZAY POS PATH CONFIGURATION")
    print("=" * 60)
    print(f"App Root       : {get_app_root()}")
    print(f"Frozen         : {is_frozen()}")
    print(f"Platform       : {get_platform()}")
    print("-" * 60)
    print(f"Database       : {get_db_path()}")
    print(f"Backup Dir     : {get_backup_dir()}")
    print(f"Recovery Dir   : {get_recovery_dir()}")
    print(f"Log Dir        : {get_log_dir()}")
    print(f"Temp Dir       : {get_temp_dir()}")
    print(f"Attachments    : {get_attachments_dir()}")
    print(f"Assets Dir     : {get_assets_dir()}")
    print(f"Fonts Dir      : {get_fonts_dir()}")
    print(f"Icons Dir      : {get_icons_dir()}")
    print(f"Images Dir     : {get_images_dir()}")
    print(f"Product Images : {get_product_images_dir()}")
    print(f"Thumbnails     : {get_product_thumbnails_dir()}")
    print(f"Resources Dir  : {get_resources_dir()}")
    print("=" * 60)


# ============================================================================
# AUTO-INITIALIZATION
# ============================================================================

# Ensure directories exist when module is imported
if not is_frozen():
    # Only create directories when running as script (not in EXE)
    # For EXE, directories are created during bootstrap
    pass

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Core
    'get_app_root',
    'app_path',
    'app_relative_path',
    'is_frozen',
    'get_platform',
    
    # Database
    'get_db_path',
    'get_db_dir',
    'get_backup_dir',
    'get_recovery_dir',
    
    # Logs
    'get_log_dir',
    'get_log_path',
    
    # Assets
    'get_assets_dir',
    'get_fonts_dir',
    'get_icons_dir',
    'get_images_dir',
    
    # Product Images
    'get_product_images_dir',
    'get_product_thumbnails_dir',
    
    # Temp
    'get_temp_dir',
    'get_temp_file',
    
    # Attachments
    'get_attachments_dir',
    
    # Backup
    'get_backup_path',
    
    # Resources
    'get_resources_dir',
    
    # Utilities
    'ensure_directories',
    'print_paths',
]