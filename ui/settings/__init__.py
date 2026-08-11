# ui/settings/__init__.py
from ui.settings.general_setting import GeneralSettingWidget
from ui.settings.receipt_setting import ReceiptSettingWidget
from ui.settings.restaurant_setting import RestaurantSettingWidget
from ui.settings.regional_setting import RegionalSettingWidget
from ui.settings.backup_reset_setting import BackupResetSettingWidget
from ui.settings.users_setting import UsersSettingWidget
from ui.settings.update_setting import UpdateSettingWidget  # New export
from ui.settings.telegram_setting import TelegramSettingWidget
from ui.settings.youtube_setting import YouTubeSettingWidget
from ui.settings.performance_setting import PerformanceSettingWidget
from ui.settings.settings_page import SettingsPage

__all__ = [
    'GeneralSettingWidget',
    'ReceiptSettingWidget', 
    'RestaurantSettingWidget',
    'RegionalSettingWidget',
    'BackupResetSettingWidget',
    'UsersSettingWidget',
    'UpdateSettingWidget',  # New export
    'TelegramSettingWidget',
    'YouTubeSettingWidget',
    'PerformanceSettingWidget',
    'SettingsPage'
]
