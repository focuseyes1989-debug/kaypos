"""Lazy UI exports for ZAY POS."""

__all__ = [
    "CustomerDisplayWindow",
    "ReceiptDialog",
    "ReceiptDetailDialog",
    "ProductFormDialog",
    "StockInDialog",
    "LoadingDialog",
]


def __getattr__(name):
    if name == "CustomerDisplayWindow":
        from ui.customer_page.customer_display import CustomerDisplayWindow
        return CustomerDisplayWindow
    if name == "ReceiptDialog":
        from ui.receipt_dialog import ReceiptDialog
        return ReceiptDialog
    if name == "ReceiptDetailDialog":
        from ui.receipt_detail_dialog import ReceiptDetailDialog
        return ReceiptDetailDialog
    if name == "ProductFormDialog":
        from ui.products_page.product_form_dialog import ProductFormDialog
        return ProductFormDialog
    if name == "StockInDialog":
        from ui.inventory_page.stock_in_dialog import StockInDialog
        return StockInDialog
    if name == "LoadingDialog":
        from ui.loading_dialog import LoadingDialog
        return LoadingDialog
    raise AttributeError(f"module 'ui' has no attribute {name!r}")
