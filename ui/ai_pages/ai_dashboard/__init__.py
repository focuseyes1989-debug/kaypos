# ui/ai_pages/ai_dashboard/__init__.py
"""
AI Dashboard Module
"""

from ui.ai_pages.ai_dashboard.dashboard_widget import AIDashboard
from ui.ai_pages.ai_dashboard.dashboard_data import get_dashboard_data_sync

__all__ = [
    'AIDashboard',
    'get_dashboard_data_sync',
]