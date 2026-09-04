"""Stable route IDs matching the main KAY POS page registry."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Route:
    id: int
    title: str
    permission: str
    phase: int

ROUTES = (
    Route(0, 'Dashboard', 'dashboard', 6),
    Route(1, 'Sales Summary', 'sales_summary', 6),
    Route(12, 'Reports', 'reports', 6),
    Route(2, 'Products', 'products', 4),
    Route(9, 'Discounts', 'products', 4),
    Route(8, 'AI Pages', 'ai_pages', 7),
    Route(3, 'Inventory', 'inventory', 4),
    Route(4, 'Receipts', 'receipts', 5),
    Route(5, 'Sales', 'sales', 3),
    Route(10, 'Restaurant', 'sales', 5),
    Route(6, 'Customers', 'customers', 5),
    Route(7, 'Expense', 'expense', 5),
    Route(11, 'Employees', 'employees', 7),
    Route(13, 'Settings', 'settings', 7),
    Route(14, 'Users & Roles', 'users', 7),
    Route(15, 'Activity Log', 'users', 7),
    Route(16, 'ZKTeco Devices', 'settings', 7),
    Route(17, 'Backup / Restore', 'backup', 7),
    Route(18, 'Integrations', 'settings', 7),
)
