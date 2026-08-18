# ui/products_page/__init__.py
"""Products page UI components"""

from ui.products_page.products_page import ProductsPage
from ui.products_page.product_form_dialog import ProductFormDialog
from ui.products_page.product_ai_chat_panel import ProductAIChatDialog, ProductAIChatPanel
from ui.products_page.product_form_ui import ProductFormUI
from ui.products_page.product_form_handlers import ProductFormHandlers
from ui.products_page.product_form_widgets import FormHeaderFrame, InfoLabel, StatusBadge
from ui.products_page.manage_categories_dialog import ManageCategoriesDialog
from ui.products_page.manage_category_groups_dialog import ManageCategoryGroupsDialog
from ui.products_page.manage_category_groups_ui import CategoryGroupsUI
from ui.products_page.manage_category_groups_handlers import CategoryGroupsHandlers

__all__ = [
    'ProductsPage',
    'ProductFormDialog',
    'ProductAIChatPanel',
    'ProductAIChatDialog',
    'ProductFormUI',
    'ProductFormHandlers',
    'FormHeaderFrame',
    'InfoLabel',
    'StatusBadge',
    'ManageCategoriesDialog',
    'ManageCategoryGroupsDialog',
    'CategoryGroupsUI',
    'CategoryGroupsHandlers',
]
