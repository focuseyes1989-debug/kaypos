# ui/ai_pages/ai_dashboard/dashboard_utils.py
"""
Utility functions for AI Dashboard
"""

from datetime import datetime, timedelta
from typing import Tuple


class DashboardUtils:
    """Utility functions for dashboard"""
    
    VIBRANT_COLORS = [
        '#E74C3C',  # Red
        '#3498DB',  # Blue
        '#2ECC71',  # Green
        '#F39C12',  # Orange
        '#9B59B6',  # Purple
        '#1ABC9C',  # Teal
        '#E67E22',  # Dark Orange
        '#2C3E50',  # Dark Blue
        '#E74C8B',  # Pink
        '#27AE60',  # Dark Green
        '#2980B9',  # Dark Blue
        '#8E44AD',  # Dark Purple
    ]
    
    @staticmethod
    def get_period_dates(period: str) -> Tuple[str, str]:
        """Get start and end dates for a period"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if period == "Today":
            return today, today
        elif period == "Yesterday":
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            return yesterday, yesterday
        elif period == "This Week":
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            return start_date, today
        elif period == "This Month":
            start_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            return start_date, today
        else:  # Last 30 Days
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            return start_date, today
    
    @staticmethod
    def get_theme_colors():
        """Get theme colors for charts"""
        from ui.themes.theme_manager import get_theme_colors

        colors = get_theme_colors()
        return {
            'bg': colors['bg'],
            'figure_bg': colors['card_bg'],
            'axes_bg': colors['card_bg'],
            'text': colors['text'],
            'text_secondary': colors['text_secondary'],
            'grid': colors['border'],
            'border': colors['border'],
        }
    
    @staticmethod
    def get_vibrant_colors(count: int) -> list:
        """Get vibrant colors for charts"""
        return DashboardUtils.VIBRANT_COLORS[:count]
