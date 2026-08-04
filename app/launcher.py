# app/launcher.py
"""
Launcher detection and management.
"""

import os
import sys
import time
import json
import subprocess
from loguru import logger


def is_running_from_launcher() -> bool:
    """Check if the application was started by the launcher."""
    marker_file = os.path.join(os.path.dirname(sys.executable), '.launcher_ran')
    if os.path.exists(marker_file):
        return True
    
    if '--from-launcher' in sys.argv:
        return True
    
    if os.environ.get('ZAY_LAUNCHER', '0') == '1':
        return True
    
    return False


def find_launcher() -> str:
    """Find the launcher executable."""
    if not getattr(sys, 'frozen', False):
        return None
    
    app_dir = os.path.dirname(sys.executable)
    
    launcher_names = [
        'ZAY_POS_Launcher.exe',
        'launcher.exe',
        'ZAY_Launcher.exe'
    ]
    
    for name in launcher_names:
        launcher_path = os.path.join(app_dir, name)
        if os.path.exists(launcher_path):
            return launcher_path
    
    parent_dir = os.path.dirname(app_dir)
    for name in launcher_names:
        launcher_path = os.path.join(parent_dir, name)
        if os.path.exists(launcher_path):
            return launcher_path
    
    return None


def should_run_launcher() -> bool:
    """Determine if we should run the launcher."""
    if is_running_from_launcher():
        logger.info("Running from launcher, skipping launcher check")
        return False
    
    if not getattr(sys, 'frozen', False):
        logger.info("Running as script, skipping launcher")
        return False
    
    if not find_launcher():
        logger.info("Launcher not found, starting directly")
        return False
    
    metadata_file = os.path.join(os.path.dirname(sys.executable), 'update_metadata.json')
    need_update_check = True
    
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                data = json.load(f)
            last_check = data.get('last_check', 0)
            current_time = time.time()
            
            if current_time - last_check < 86400:  # 24 hours
                need_update_check = False
                logger.info(f"Last update check was {int((current_time - last_check) / 3600)} hours ago")
        except:
            pass
    
    if need_update_check:
        logger.info("Running launcher for update check")
        return True
    
    launcher_marker = os.path.join(os.path.dirname(sys.executable), '.launcher_ran')
    if os.path.exists(launcher_marker):
        try:
            mtime = os.path.getmtime(launcher_marker)
            if time.time() - mtime < 3600:
                logger.info("Launcher ran recently, skipping")
                return False
        except:
            pass
    
    return True


def run_launcher_and_exit() -> None:
    """Run the launcher and exit current process."""
    launcher_path = find_launcher()
    if not launcher_path:
        logger.error("Launcher not found")
        return
    
    try:
        logger.info(f"🚀 Starting launcher: {launcher_path}")
        
        marker_file = os.path.join(os.path.dirname(sys.executable), '.launcher_ran')
        with open(marker_file, 'w') as f:
            f.write(str(time.time()))
        
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(
                [launcher_path],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            subprocess.Popen([launcher_path])
        
        logger.info("✅ Launcher started successfully")
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, lambda: sys.exit(0))
        
    except Exception as e:
        logger.error(f"Failed to start launcher: {e}")