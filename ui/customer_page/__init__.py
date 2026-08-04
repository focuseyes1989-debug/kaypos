# ui/customer_page/__init__.py
from ui.customer_page.customers_page import CustomersPage
from ui.customer_page.customer_display import CustomerDisplayWindow
from ui.customer_page.customer_ledger_dialog import CustomerLedgerDialog
from ui.customer_page.credit_sale_dialog import CreditSaleDialog
from ui.customer_page.credit_payment_dialog import CreditPaymentDialog
from ui.customer_page.outstanding_report_dialog import OutstandingReportDialog
from ui.customer_page.add_edit_customer_dialog import AddEditCustomerDialog

# Customer display sub-modules
from ui.customer_page.customer_display_title_bar import TitleBar
from ui.customer_page.customer_display_theme import get_display_palette, get_launcher_style
from ui.customer_page.customer_display_cart import CartDisplayWidget
from ui.customer_page.customer_display_shop import ShopInfoWidget
from ui.customer_page.customer_display_utils import (
    load_qr_info,
    set_default_geometry,
    move_to_secondary_monitor,
    show_on_customer_monitor_fullscreen,
)

__all__ = [
    'CustomersPage',
    'CustomerDisplayWindow',
    'CustomerLedgerDialog',
    'CreditSaleDialog',
    'CreditPaymentDialog',
    'OutstandingReportDialog',
    'AddEditCustomerDialog',
    # Sub-modules
    'TitleBar',
    'get_display_palette',
    'get_launcher_style',
    'CartDisplayWidget',
    'ShopInfoWidget',
    'load_qr_info',
    'set_default_geometry',
    'move_to_secondary_monitor',
    'show_on_customer_monitor_fullscreen',
]
