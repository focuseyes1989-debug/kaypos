# ui/dashboard/__init__.py
from ui.dashboard.dashboard_page import DashboardPage
from ui.dashboard.modern_card import ModernSummaryCard
from ui.dashboard.ai_assistant import AIAssistantWidget
from ui.dashboard.dashboard_table import DashboardTable
from ui.dashboard.dashboard_backup import DashboardBackupStatus
from ui.dashboard.dashboard_cards import DashboardCards, BackupStatusCard
from ui.dashboard.dashboard_dialogs import DiscountedSalesDialog, RefundedSalesDialog
from ui.dashboard.dashboard_export import DashboardExport
from ui.dashboard.dashboard_filters import DashboardFilters

# ✅ Import from ai_assistant folder
from ui.dashboard.ai_assistant import AIAssistantWidget

__all__ = [
    'DashboardPage',
    'ModernSummaryCard',
    'AIAssistantWidget',
    'DashboardTable',
    'DashboardBackupStatus',
    'DashboardCards',
    'BackupStatusCard',
    'DiscountedSalesDialog',
    'RefundedSalesDialog',
    'DashboardExport',
    'DashboardFilters'
]