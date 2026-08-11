# updater/version_manager.py
"""
Version management for ZAY POS.
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class VersionInfo:
    """Version information for the application."""
    version: str
    release_date: str
    release_notes: str
    download_url: str
    file_size: int
    file_hash: str
    mandatory: bool = False
    min_required_version: str = "1.0.0"
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class CurrentVersion:
    """Current application version information."""
    version: str
    build_date: str
    build_number: int
    db_version: str


class VersionManager:
    """Handle version comparison and management."""
    
    VERSION_FILE = "version.txt"
    UPDATE_METADATA_FILE = "update_metadata.json"
    _cached_version: Optional[str] = None
    _cached_version_path: Optional[str] = None
    _cached_version_mtime: Optional[float] = None
    
    def __init__(self):
        self.current_version = None
        if not self.current_version:
            self._load_current_version()
    
    def _get_version_file_path(self) -> str:
        """Get the path to version.txt."""
        # Check if running as EXE
        if getattr(sys, 'frozen', False):
            # Running as compiled EXE
            return os.path.join(os.path.dirname(sys.executable), self.VERSION_FILE)
        else:
            # Running as Python script
            # Try multiple locations
            possible_paths = [
                os.path.join(os.path.dirname(__file__), '..', self.VERSION_FILE),
                os.path.join(os.getcwd(), self.VERSION_FILE),
                os.path.join(os.path.dirname(sys.executable), self.VERSION_FILE),
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    return path
            
            # Default to the first path
            return possible_paths[0]
    
    def _load_current_version(self):
        """Load current version from version.txt."""
        try:
            version_file = self._get_version_file_path()
            try:
                version_mtime = os.path.getmtime(version_file)
            except OSError:
                version_mtime = None

            if (
                self.__class__._cached_version
                and self.__class__._cached_version_path == version_file
                and self.__class__._cached_version_mtime == version_mtime
            ):
                self.current_version = self.__class__._cached_version
                return
            
            logger.info(f"Looking for version file: {version_file}")
            
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.debug(f"Version file loaded ({len(content)} chars)")
                    
                    # ✅ Try multiple patterns to find version
                    patterns = [
                        r'ProductVersion\s*=\s*["\']([\d.]+)["\']',
                        r'FileVersion\s*=\s*["\']([\d.]+)["\']',
                        r'version\s*=\s*["\']([\d.]+)["\']',
                        r'"version"\s*:\s*"([\d.]+)"',
                        r'Version\s*[:=]\s*([\d.]+)',
                        r'v([\d.]+)',
                        r'([\d]+\.[\d]+\.[\d]+)'
                    ]
                    
                    found_version = None
                    for pattern in patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            found_version = match.group(1)
                            logger.info(f"Found version using pattern '{pattern}': {found_version}")
                            break
                    
                    if found_version:
                        self.current_version = found_version
                    else:
                        logger.warning("Could not parse version from file, using default")
                        self.current_version = "1.0.0"
            else:
                logger.warning(f"Version file not found: {version_file}")
                self.current_version = "1.0.0"
                
            logger.info(f"Current version: {self.current_version}")
            self.__class__._cached_version = self.current_version
            self.__class__._cached_version_path = version_file
            self.__class__._cached_version_mtime = version_mtime
                
        except Exception as e:
            logger.error(f"Failed to load version: {e}")
            self.current_version = "1.0.0"
    
    def get_current_version(self) -> str:
        """Get current application version."""
        # ✅ Reload version each time to ensure it's up to date
        if not self.current_version:
            self._load_current_version()
        return self.current_version
    
    def update_version(self, new_version: str) -> bool:
        """Update the version file with new version."""
        try:
            version_file = self._get_version_file_path()
            logger.info(f"Updating version file: {version_file} to {new_version}")
            
            # ✅ Ensure directory exists
            os.makedirs(os.path.dirname(version_file), exist_ok=True)
            
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # ✅ Update version in file
                updated = False
                
                # Update ProductVersion
                content, count1 = re.subn(
                    r'(ProductVersion\s*=\s*["\'])[\d.]+(["\'])',
                    f'\\1{new_version}\\2',
                    content
                )
                if count1 > 0:
                    updated = True
                    logger.info(f"Updated ProductVersion: {count1} occurrence(s)")
                
                # Update FileVersion
                content, count2 = re.subn(
                    r'(FileVersion\s*=\s*["\'])[\d.]+(["\'])',
                    f'\\1{new_version}\\2',
                    content
                )
                if count2 > 0:
                    updated = True
                    logger.info(f"Updated FileVersion: {count2} occurrence(s)")
                
                # Update generic version
                content, count3 = re.subn(
                    r'(version\s*=\s*["\'])[\d.]+(["\'])',
                    f'\\1{new_version}\\2',
                    content,
                    flags=re.IGNORECASE
                )
                if count3 > 0:
                    updated = True
                    logger.info(f"Updated generic version: {count3} occurrence(s)")
                
                # ✅ If not updated, add a new version line
                if not updated:
                    logger.warning("Could not update version in file, adding new line")
                    content += f'\nProductVersion = "{new_version}"\n'
                    updated = True
                
                if updated:
                    with open(version_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.current_version = new_version
                    self.__class__._cached_version = new_version
                    self.__class__._cached_version_path = version_file
                    self.__class__._cached_version_mtime = os.path.getmtime(version_file)
                    logger.info(f"✅ Version updated to: {new_version}")
                    return True
                else:
                    logger.warning("Could not update version in file")
                    return False
            else:
                # ✅ Create new version file
                logger.warning(f"Version file not found, creating: {version_file}")
                version_content = f'''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'ProductVersion', u'{new_version}'),
            StringStruct(u'FileVersion', u'{new_version}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
                with open(version_file, 'w', encoding='utf-8') as f:
                    f.write(version_content)
                self.current_version = new_version
                self.__class__._cached_version = new_version
                self.__class__._cached_version_path = version_file
                self.__class__._cached_version_mtime = os.path.getmtime(version_file)
                logger.info(f"✅ Created version file with version: {new_version}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update version: {e}")
            return False
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if v1 < v2
            0 if v1 == v2
            1 if v1 > v2
        """
        def normalize(v):
            return [int(x) for x in v.split('.')]
        
        try:
            v1_parts = normalize(v1)
            v2_parts = normalize(v2)
        except:
            # If parsing fails, do string comparison
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            a = v1_parts[i] if i < len(v1_parts) else 0
            b = v2_parts[i] if i < len(v2_parts) else 0
            if a < b:
                return -1
            elif a > b:
                return 1
        return 0
    
    def is_update_available(self, latest_version: str) -> bool:
        """Check if update is available."""
        return self.compare_versions(self.current_version, latest_version) < 0
    
    def get_update_metadata_path(self) -> str:
        """Get path to update metadata file."""
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), self.UPDATE_METADATA_FILE)
        else:
            return os.path.join(os.path.dirname(__file__), '..', self.UPDATE_METADATA_FILE)
    
    def save_update_metadata(self, metadata: Dict):
        """Save update metadata."""
        path = self.get_update_metadata_path()
        try:
            with open(path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Update metadata saved to: {path}")
        except Exception as e:
            logger.error(f"Failed to save update metadata: {e}")
    
    def load_update_metadata(self) -> Dict:
        """Load update metadata."""
        path = self.get_update_metadata_path()
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load update metadata: {e}")
        return {}
    
    def get_db_version(self) -> str:
        """Get current database version from app_metadata."""
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT db_version FROM app_metadata 
                ORDER BY id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "0.0.0"
        except Exception as e:
            logger.error(f"Failed to get DB version: {e}")
            return "0.0.0"
