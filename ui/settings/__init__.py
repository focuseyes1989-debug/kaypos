"""Settings package exports.

Widgets are imported lazily so optional integrations do not block unrelated
settings dialogs. For example, opening Database settings should not require the
Telegram dependencies to be installed.
"""

_EXPORTS = {
    "GeneralSettingWidget": ("ui.settings.general_setting", "GeneralSettingWidget"),
    "ReceiptSettingWidget": ("ui.settings.receipt_setting", "ReceiptSettingWidget"),
    "RestaurantSettingWidget": ("ui.settings.restaurant_setting", "RestaurantSettingWidget"),
    "RegionalSettingWidget": ("ui.settings.regional_setting", "RegionalSettingWidget"),
    "BackupResetSettingWidget": ("ui.settings.backup_reset_setting", "BackupResetSettingWidget"),
    "UsersSettingWidget": ("ui.settings.users_setting", "UsersSettingWidget"),
    "UpdateSettingWidget": ("ui.settings.update_setting", "UpdateSettingWidget"),
    "TelegramSettingWidget": ("ui.settings.telegram_setting", "TelegramSettingWidget"),
    "DatabaseConnectionSettingWidget": (
        "ui.settings.database_connection_setting",
        "DatabaseConnectionSettingWidget",
    ),
    "YouTubeSettingWidget": ("ui.settings.youtube_setting", "YouTubeSettingWidget"),
    "PerformanceSettingWidget": ("ui.settings.performance_setting", "PerformanceSettingWidget"),
    "SettingsPage": ("ui.settings.settings_page", "SettingsPage"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = _EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value

__all__ = [
    'GeneralSettingWidget',
    'ReceiptSettingWidget', 
    'RestaurantSettingWidget',
    'RegionalSettingWidget',
    'BackupResetSettingWidget',
    'UsersSettingWidget',
    'UpdateSettingWidget',  # New export
    'TelegramSettingWidget',
    'DatabaseConnectionSettingWidget',
    'YouTubeSettingWidget',
    'PerformanceSettingWidget',
    'SettingsPage'
]
