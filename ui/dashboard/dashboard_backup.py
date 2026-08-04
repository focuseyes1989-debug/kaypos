# ui/dashboard/dashboard_backup.py
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTimer
from datetime import datetime
from loguru import logger
from ui.themes.theme_manager import is_dark_theme


class DashboardBackupStatus:
    """Handle backup status display and updates"""
    
    @staticmethod
    def update_backup_status(parent, backup_manager):
        """Update the backup status display on dashboard (compact single line)"""
        try:
            if not hasattr(parent, 'backup_label'):
                return

            if backup_manager is None:
                is_dark = is_dark_theme()
                color = "#b9bbbe" if is_dark else "#6c757d"
                parent.backup_label.setText("Backup: Manual")
                parent.backup_label.setStyleSheet(f"""
                    font-size: 8pt;
                    color: {color};
                    background: transparent;
                    border: none;
                    padding: 0px;
                """)
                if hasattr(parent, '_update_backup_icon'):
                    parent._update_backup_icon()
                return
            
            last_backup = backup_manager.get_last_backup_time_str()
            is_dark = is_dark_theme()
            
            # Default color based on theme
            default_color = "#b9bbbe" if is_dark else "#6c757d"
            warning_color = "#e67e22" if is_dark else "#d35400"
            success_color = "#27ae60" if is_dark else "#2ecc71"
            danger_color = "#e74c3c" if is_dark else "#c0392b"
            
            # Check if backup exists
            if last_backup and last_backup != "Never":
                # Update label with last backup time
                parent.backup_label.setText(f"Last Backup: {last_backup}")
                
                # Set color based on backup age
                last_time = backup_manager.get_last_backup_time()
                if last_time:
                    days_since = (datetime.now() - last_time).days
                    if days_since > 7:
                        color = warning_color
                    elif days_since > 1:
                        color = warning_color
                    else:
                        color = success_color
                else:
                    color = default_color
            else:
                parent.backup_label.setText("No backup found")
                color = danger_color
            
            # Apply color to label
            parent.backup_label.setStyleSheet(f"""
                font-size: 8pt;
                color: {color};
                background: transparent;
                border: none;
                padding: 0px;
            """)
            
            # ✅ Update backup icon color to match label
            if hasattr(parent, '_update_backup_icon'):
                parent._update_backup_icon()
                
        except Exception as e:
            logger.error(f"Failed to update backup status: {e}")
            if hasattr(parent, 'backup_label'):
                is_dark = is_dark_theme()
                color = "#b9bbbe" if is_dark else "#6c757d"
                parent.backup_label.setText("Backup: Error")
                parent.backup_label.setStyleSheet(f"""
                    font-size: 8pt;
                    color: {color};
                    background: transparent;
                    border: none;
                    padding: 0px;
                """)
