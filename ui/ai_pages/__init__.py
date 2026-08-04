# ui/ai_pages/__init__.py
"""
AI Pages Module
"""

from ui.ai_pages.ai_pages_page import AIPagesPage
from ui.ai_pages.ai_chat_room import AIChatRoom
from ui.ai_pages.ai_chat_worker import QueryWorker
from ui.ai_pages.ai_chat_widgets import CopyableMessageFrame
from ui.ai_pages.ai_query_handlers import QueryHandlers
from ui.ai_pages.ai_cache import QueryCache, _query_cache, get_cache_stats, clear_cache

# Phase 1
from ui.ai_pages.ai_nlp_processor import NLProcessor
from ui.ai_pages.ai_response_templates import ResponseTemplates
from ui.ai_pages.ai_error_handler import AIErrorHandler
from ui.ai_pages.ai_analytics import AIAnalytics
from ui.ai_pages.ai_enhanced_worker import EnhancedQueryWorker
from ui.ai_pages.ai_product_search import AIProductSearch
from ui.ai_pages.ai_troubleshooter import AITroubleshooter
from ui.ai_pages.ai_settings_assistant import AISettingsAssistant

# 🆕 Phase 2 - AI Analytics & Dashboard
from ui.ai_pages.ai_dashboard import AIDashboard
from ui.ai_pages.ai_dashboard.dashboard_data import get_dashboard_data_sync


__all__ = [
    # Core
    'AIPagesPage',
    'AIChatRoom',
    'QueryWorker',
    'CopyableMessageFrame',
    'QueryHandlers',
    'QueryCache',
    '_query_cache',
    'get_cache_stats',
    'clear_cache',
    
    # Phase 1
    'NLProcessor',
    'ResponseTemplates',
    'AIErrorHandler',
    'AIAnalytics',
    'EnhancedQueryWorker',
    'AIProductSearch',
    'AITroubleshooter',
    'AISettingsAssistant',
    
    # 🆕 Phase 2
    'AIDashboard',
    'get_dashboard_data_sync',
]