from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QMessageBox, QCheckBox, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.auto_backup import AutoBackupManager
import os
from datetime import datetime


class AutoBackupDialog(QDialog):
    def __init__(self, backup_manager, parent=None):
        super().__init__(parent)
        self.backup_manager = backup_manager
        self.setWindowTitle("Auto Backup Settings")
        self.setMinimumSize(800, 500)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Settings group
        settings_group = QGroupBox("Backup Settings")
        settings_layout = QFormLayout()
        settings_layout.setVerticalSpacing(12)

        # Enable auto backup
        self.enable_check = QCheckBox("Enable Automatic Backup")
        settings_layout.addRow("", self.enable_check)

        # Backup interval
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 168)  # 1 hour to 7 days
        self.interval_spin.setSuffix(" hours")
        self.interval_spin.setToolTip("How often to create backup (1-168 hours)")
        settings_layout.addRow("Backup Interval:", self.interval_spin)

        # Max backups to keep
        self.max_backups_spin = QSpinBox()
        self.max_backups_spin.setRange(5, 100)
        self.max_backups_spin.setToolTip("Maximum number of backup files to keep")
        settings_layout.addRow("Max Backups to Keep:", self.max_backups_spin)

        # Backup location
        location_layout = QHBoxLayout()
        self.backup_location_label = QLabel("database/backups")
        self.btn_open_folder = QPushButton("Open Backup Folder")
        self.btn_open_folder.clicked.connect(self.open_backup_folder)
        location_layout.addWidget(self.backup_location_label)
        location_layout.addWidget(self.btn_open_folder)
        settings_layout.addRow("Backup Location:", location_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Backup history
        history_group = QGroupBox("Backup History")
        history_layout = QVBoxLayout()

        self.backup_table = QTableWidget()
        self.backup_table.setColumnCount(4)
        self.backup_table.setHorizontalHeaderLabels(["File Name", "Date", "Size", "Actions"])
        self.backup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.backup_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.backup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.backup_table.setColumnWidth(3, 132)
        self.backup_table.verticalHeader().setDefaultSectionSize(44)
        self.backup_table.verticalHeader().setMinimumSectionSize(40)
        history_layout.addWidget(self.backup_table)

        btn_layout = QHBoxLayout()
        self.btn_create_now = QPushButton("Create Backup Now")
        self.btn_create_now.clicked.connect(self.create_backup_now)
        self.btn_restore = QPushButton("Restore Selected")
        self.btn_restore.clicked.connect(self.restore_backup)
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.clicked.connect(self.delete_backup)
        btn_layout.addWidget(self.btn_create_now)
        btn_layout.addWidget(self.btn_restore)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        history_layout.addLayout(btn_layout)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        # Buttons
        btn_dialog_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_dialog_layout.addWidget(self.btn_save)
        btn_dialog_layout.addWidget(self.btn_close)
        layout.addLayout(btn_dialog_layout)

        self.setLayout(layout)
        self.load_settings()
        self.load_backup_history()
        self.retranslateUi()

    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"

    def retranslateUi(self):
        lang = self.get_lang()
        if lang == "my":
            self.setWindowTitle("အလိုအလျောက် Backup ပြုလုပ်ခြင်း")
            self.enable_check.setText("အလိုအလျောက် Backup ပြုလုပ်မည်")
            self.interval_spin.setSuffix(" နာရီ")
            self.btn_open_folder.setText("Backup ဖိုင်တွဲဖွင့်ရန်")
            self.btn_create_now.setText("ယခု Backup ပြုလုပ်ရန်")
            self.btn_restore.setText("ရွေးထားသော Backup ကို Restore လုပ်ရန်")
            self.btn_delete.setText("ရွေးထားသော Backup ကိုဖျက်ရန်")
            self.btn_save.setText("သိမ်းဆည်းမည်")
            self.btn_close.setText("ပိတ်မည်")
            self.backup_table.setHorizontalHeaderLabels(["ဖိုင်အမည်", "ရက်စွဲ", "အရွယ်အစား", "လုပ်ဆောင်ချက်"])
        else:
            self.setWindowTitle("Auto Backup Settings")
            self.enable_check.setText("Enable Automatic Backup")
            self.interval_spin.setSuffix(" hours")
            self.btn_open_folder.setText("Open Backup Folder")
            self.btn_create_now.setText("Create Backup Now")
            self.btn_restore.setText("Restore Selected")
            self.btn_delete.setText("Delete Selected")
            self.btn_save.setText("Save Settings")
            self.btn_close.setText("Close")
            self.backup_table.setHorizontalHeaderLabels(["File Name", "Date", "Size", "Actions"])
        self.backup_table.setColumnWidth(3, 132)

    def load_settings(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='auto_backup_enabled'")
            row = cursor.fetchone()
            self.enable_check.setChecked(row[0] == '1' if row else False)
            
            cursor.execute("SELECT value FROM settings WHERE key='auto_backup_interval'")
            row = cursor.fetchone()
            self.interval_spin.setValue(int(row[0]) if row else 24)
            
            cursor.execute("SELECT value FROM settings WHERE key='auto_backup_max'")
            row = cursor.fetchone()
            self.max_backups_spin.setValue(int(row[0]) if row else 30)
            
            conn.close()
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def save_settings(self):
        enabled = self.enable_check.isChecked()
        interval = self.interval_spin.value()
        max_backups = self.max_backups_spin.value()
        
        self.backup_manager.update_settings(enabled, interval, max_backups)
        
        lang = self.get_lang()
        msg = "Auto backup settings saved!" if lang != "my" else "အလိုအလျောက် Backup သတ်မှတ်ချက်များ သိမ်းဆည်းပြီးပါပြီ။"
        QMessageBox.information(self, "Success", msg)

    def load_backup_history(self):
        backup_dir = "database/backups"
        self.backup_table.setRowCount(0)
        
        if not os.path.exists(backup_dir):
            return
        
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith(".db"):
                file_path = os.path.join(backup_dir, filename)
                stat = os.stat(file_path)
                size_mb = stat.st_size / (1024 * 1024)
                backups.append({
                    'name': filename,
                    'path': file_path,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    'size': f"{size_mb:.2f} MB"
                })
        
        # Sort by date (newest first)
        backups.sort(key=lambda x: x['date'], reverse=True)
        
        for backup in backups:
            row = self.backup_table.rowCount()
            self.backup_table.insertRow(row)
            self.backup_table.setItem(row, 0, QTableWidgetItem(backup['name']))
            self.backup_table.setItem(row, 1, QTableWidgetItem(backup['date']))
            self.backup_table.setItem(row, 2, QTableWidgetItem(backup['size']))
            
            # Restore button
            btn_restore = QPushButton("Restore")
            btn_restore.setMinimumSize(96, 30)
            btn_restore.setMaximumHeight(32)
            btn_restore.clicked.connect(lambda checked, path=backup['path']: self.restore_specific_backup(path))
            action_cell = QWidget()
            action_layout = QHBoxLayout(action_cell)
            action_layout.setContentsMargins(6, 4, 6, 4)
            action_layout.addStretch()
            action_layout.addWidget(btn_restore)
            action_layout.addStretch()
            self.backup_table.setRowHeight(row, 44)
            self.backup_table.setCellWidget(row, 3, action_cell)

    def create_backup_now(self):
        self.backup_manager.create_backup()
        self.load_backup_history()
        
        lang = self.get_lang()
        msg = "Backup created successfully!" if lang != "my" else "Backup အောင်မြင်စွာ ပြုလုပ်ပြီးပါပြီ။"
        QMessageBox.information(self, "Success", msg)

    def get_selected_backup(self):
        current_row = self.backup_table.currentRow()
        if current_row >= 0:
            name_item = self.backup_table.item(current_row, 0)
            if name_item:
                return os.path.join("database/backups", name_item.text())
        return None

    def restore_backup(self):
        backup_path = self.get_selected_backup()
        if not backup_path:
            lang = self.get_lang()
            msg = "Please select a backup to restore." if lang != "my" else "ကျေးဇူးပြု၍ Restore လုပ်ရန် Backup ဖိုင်တစ်ခုရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        self.restore_specific_backup(backup_path)

    def restore_specific_backup(self, backup_path):
        lang = self.get_lang()
        msg = f"Restore backup '{os.path.basename(backup_path)}'?\n\nYour current database will be overwritten.\nThe application will close after restore." if lang != "my" else f"Backup '{os.path.basename(backup_path)}' ကို Restore လုပ်မည်လား?\n\nလက်ရှိ database ကို ဖျက်ပြီး အစားထိုးမည်။\nRestore ပြီးပါက application ပိတ်သွားပါမည်။"
        
        reply = QMessageBox.question(self, "Confirm Restore", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db_path = "database/pos.db"
                shutil.copy2(backup_path, db_path)
                QMessageBox.information(self, "Restore Complete", "Database restored. Application will now close.")
                import sys
                sys.exit(0)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Restore failed: {e}")

    def delete_backup(self):
        backup_path = self.get_selected_backup()
        if not backup_path:
            lang = self.get_lang()
            msg = "Please select a backup to delete." if lang != "my" else "ကျေးဇူးပြု၍ ဖျက်ရန် Backup ဖိုင်တစ်ခုရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        lang = self.get_lang()
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{os.path.basename(backup_path)}' permanently?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(backup_path)
                self.load_backup_history()
                msg = "Backup deleted successfully!" if lang != "my" else "Backup ဖိုင်ဖျက်ပြီးပါပြီ။"
                QMessageBox.information(self, "Success", msg)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Delete failed: {e}")

    def open_backup_folder(self):
        import subprocess
        import sys
        backup_dir = os.path.abspath("database/backups")
        if sys.platform == 'win32':
            os.startfile(backup_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', backup_dir])
        else:
            subprocess.run(['xdg-open', backup_dir])
