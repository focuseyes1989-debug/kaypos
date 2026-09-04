"""Lazy AI exports: parser imports must not initialize UI or a database."""
from importlib import import_module

_EXPORTS = {
    'AIPagesPage': 'ai_pages_page', 'AIChatRoom': 'ai_chat_room', 'QueryWorker': 'ai_chat_worker',
    'CopyableMessageFrame': 'ai_chat_widgets', 'QueryHandlers': 'ai_query_handlers',
    'QueryCache': 'ai_cache', '_query_cache': 'ai_cache', 'get_cache_stats': 'ai_cache', 'clear_cache': 'ai_cache',
    'NLProcessor': 'ai_nlp_processor', 'ResponseTemplates': 'ai_response_templates',
    'AIErrorHandler': 'ai_error_handler', 'AIAnalytics': 'ai_analytics', 'EnhancedQueryWorker': 'ai_enhanced_worker',
    'AIProductSearch': 'ai_product_search', 'AITroubleshooter': 'ai_troubleshooter', 'AISettingsAssistant': 'ai_settings_assistant',
    'AIDashboard': 'ai_dashboard', 'get_dashboard_data_sync': 'ai_dashboard.dashboard_data',
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS: raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = getattr(import_module('.' + _EXPORTS[name], __name__), name)
    globals()[name] = value
    return value
