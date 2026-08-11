# ui/settings/settings_page.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox
from PyQt6.QtCore import pyqtSignal
from ui.settings.general_setting import GeneralSettingWidget
from ui.settings.receipt_setting import ReceiptSettingWidget
from ui.settings.restaurant_setting import RestaurantSettingWidget
from ui.settings.regional_setting import RegionalSettingWidget
from ui.settings.backup_reset_setting import BackupResetSettingWidget
from ui.settings.users_setting import UsersSettingWidget
from ui.settings.update_setting import UpdateSettingWidget
from ui.settings.telegram_setting import TelegramSettingWidget
from utils.language import lang
from utils.permissions import PermissionManager, Permission
from loguru import logger


class SettingsPage(QWidget):
    receipt_settings_changed = pyqtSignal()
    general_settings_changed = pyqtSignal()
    currency_changed = pyqtSignal()

    def __init__(self, current_user_role="admin", user_id=None, parent=None):
        super().__init__(parent)
        self.current_user_role = current_user_role
        self.user_id = user_id
        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()

        # General Settings Tab - Always visible
        self.general_tab = GeneralSettingWidget()
        self.tabs.addTab(self.general_tab, "")
        
        # Receipt Settings Tab - Always visible
        self.receipt_tab = ReceiptSettingWidget()
        self.tabs.addTab(self.receipt_tab, "")

        # Restaurant Settings Tab - Always visible
        self.restaurant_tab = RestaurantSettingWidget()
        self.tabs.addTab(self.restaurant_tab, "")
        
        # Regional Settings Tab - Always visible
        self.regional_tab = RegionalSettingWidget()
        self.tabs.addTab(self.regional_tab, "")

        # Update Tab - Always visible (check for updates)
        self.update_tab = UpdateSettingWidget(user_id=user_id)
        self.tabs.addTab(self.update_tab, "")

        # Telegram Tab - Always visible
        self.telegram_tab = TelegramSettingWidget()
        self.tabs.addTab(self.telegram_tab, "")

        # Backup Tab - Only show if user has backup permission
        if self.user_id and PermissionManager.user_has_permission(self.user_id, Permission.BACKUP):
            self.backup_tab = BackupResetSettingWidget(user_id=self.user_id)
            self.tabs.addTab(self.backup_tab, "")
            logger.info(f"Backup tab added - has BACKUP permission")
        else:
            logger.info(f"Backup tab NOT added - user_id={self.user_id}, has BACKUP={PermissionManager.user_has_permission(self.user_id, Permission.BACKUP) if self.user_id else False}")

        # Users Tab - Only show if user has view users permission
        if self.user_id and PermissionManager.user_has_permission(self.user_id, Permission.VIEW_USERS):
            self.users_tab = UsersSettingWidget(user_id=self.user_id)
            self.tabs.addTab(self.users_tab, "")
            logger.info(f"Users tab added - has VIEW_USERS permission")
        else:
            logger.info(f"Users tab NOT added - user_id={self.user_id}, has VIEW_USERS={PermissionManager.user_has_permission(self.user_id, Permission.VIEW_USERS) if self.user_id else False}")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        # Connect signals
        self.receipt_tab.receipt_settings_changed.connect(self.receipt_settings_changed)
        self.general_tab.settings_saved.connect(self.general_settings_changed)
        self.regional_tab.currency_changed.connect(self.currency_changed)

        # Apply permissions to disable tabs based on edit permission
        self.apply_tab_permissions()

        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()

    def apply_tab_permissions(self):
        """Disable tabs if user doesn't have edit permission"""
        if not self.user_id:
            return
        
        # Check if user can edit settings
        can_edit_settings = PermissionManager.user_has_permission(self.user_id, Permission.EDIT_SETTINGS)
        
        if not can_edit_settings:
            # Disable General Settings tab (read-only mode)
            self.general_tab.setEnabled(False)
            self.general_tab.setToolTip("You don't have permission to edit settings")
            
            # Disable Receipt Settings tab
            self.receipt_tab.setEnabled(False)
            self.receipt_tab.setToolTip("You don't have permission to edit settings")

            # Disable Restaurant Settings tab
            self.restaurant_tab.setEnabled(False)
            self.restaurant_tab.setToolTip("You don't have permission to edit settings")
            
            # Disable Regional Settings tab
            self.regional_tab.setEnabled(False)
            self.regional_tab.setToolTip("You don't have permission to edit settings")
            
            # Update tab - always enabled (checking for updates doesn't need permission)
            # Disable Telegram settings tab
            if hasattr(self, 'telegram_tab'):
                self.telegram_tab.setEnabled(False)
                self.telegram_tab.setToolTip("You don't have permission to edit Telegram settings")
            
            # If backup tab exists, disable it too
            if hasattr(self, 'backup_tab'):
                self.backup_tab.setEnabled(False)
                self.backup_tab.setToolTip("You don't have permission to backup/restore")

    def retranslateUi(self):
        # Tab titles list
        tab_titles = []
        
        # Always add first three tabs
        tab_titles.append(("General Settings", "အထွေထွေသတ်မှတ်ချက်များ"))
        tab_titles.append(("Receipt Setting", "ပြေစာသတ်မှတ်ချက်"))
        tab_titles.append(("Regional Settings", "ဒေသဆိုင်ရာသတ်မှတ်ချက်များ"))
        
        if hasattr(self, 'restaurant_tab'):
            tab_titles.insert(2, ("Restaurant Setting", "Restaurant Setting"))

        # Add Update tab
        tab_titles.append(("Update", "အပ်ဒိတ်"))
        
        # Add Telegram tab
        tab_titles.append(("Telegram", "Telegram"))

        # Add Backup tab title if exists
        if hasattr(self, 'backup_tab'):
            tab_titles.append(("Backup & Reset", "Backup နှင့် ပြန်လည်သတ်မှတ်ခြင်း"))
        
        # Add Users tab title if exists
        if hasattr(self, 'users_tab'):
            tab_titles.append(("Users", "အသုံးပြုသူများ"))
        
        # Apply titles to tabs
        for i, (eng, my) in enumerate(tab_titles):
            if i < self.tabs.count():
                self.tabs.setTabText(i, my if lang.get_current() == "my" else eng)

        # Retranslate each tab if they have the method
        if hasattr(self, 'general_tab'):
            self.general_tab.retranslateUi()
        if hasattr(self, 'receipt_tab'):
            self.receipt_tab.retranslateUi()
        if hasattr(self, 'restaurant_tab'):
            self.restaurant_tab.retranslateUi()
        if hasattr(self, 'regional_tab'):
            self.regional_tab.retranslateUi()
        if hasattr(self, 'update_tab'):
            self.update_tab.retranslateUi()
        if hasattr(self, 'telegram_tab'):
            self.telegram_tab.retranslateUi()
        if hasattr(self, 'backup_tab'):
            self.backup_tab.retranslateUi()
        if hasattr(self, 'users_tab'):
            self.users_tab.retranslateUi()

    def showEvent(self, event):
        """Refresh settings when page becomes visible"""
        # Reload settings in each tab
        if hasattr(self, 'general_tab'):
            self.general_tab.load_payment_types()
            self.general_tab.load_tax_settings()
            self.general_tab.load_loyalty_settings()
            self.general_tab.load_discount_settings()
            self.general_tab.load_appearance_settings()
        
        if hasattr(self, 'receipt_tab'):
            self.receipt_tab.load_receipt_settings()

        if hasattr(self, 'restaurant_tab'):
            self.restaurant_tab.load_settings()
            self.restaurant_tab.load_tables()
        
        if hasattr(self, 'regional_tab'):
            self.regional_tab.load_currency_setting()
            self.regional_tab.load_language_setting()
        
        if hasattr(self, 'update_tab'):
            self.update_tab.load_current_version()

        if hasattr(self, 'telegram_tab'):
            self.telegram_tab.load_settings()
        
        super().showEvent(event)
