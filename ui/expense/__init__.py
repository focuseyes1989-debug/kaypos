# ui/expense/__init__.py
"""
Expense UI Components
"""

# Main expense page components
from ui.expense.expense_page import ExpensePage
from ui.expense.expense_cards import ExpenseCards
from ui.expense.expense_filters import ExpenseFilters
from ui.expense.expense_table import ExpenseTable
from ui.expense.expense_export import ExpenseExport
from ui.expense.expense_category_tab import ExpenseCategoryTab

# Category management components
from ui.expense.add_category_dialog import AddCategoryDialog
from ui.expense.edit_category_dialog import EditCategoryDialog
from ui.expense.expense_categories_dialog import ExpenseCategoriesDialog

__all__ = [
    # Main components
    'ExpensePage',
    'ExpenseCards',
    'ExpenseFilters',
    'ExpenseTable',
    'ExpenseExport',
    'ExpenseChartWidget',
    'ExpenseCategoryTab',
    
    # Category management
    'AddCategoryDialog',
    'EditCategoryDialog',
    'ExpenseCategoriesDialog',
]


def __getattr__(name):
    if name == 'ExpenseChartWidget':
        from ui.expense.expense_chart import ExpenseChartWidget
        return ExpenseChartWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
