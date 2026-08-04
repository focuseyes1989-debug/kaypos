# ui/cashier_window/__init__.py
"""Cashier Mode Window Package."""

__all__ = [
    "MainCashierWindow",
    "CashierUI",
    "CartWidget",
]


def __getattr__(name):
    if name == "MainCashierWindow":
        from ui.cashier_window.main_cashier_window import MainCashierWindow
        return MainCashierWindow
    if name == "CashierUI":
        from ui.cashier_window.cashier_ui import CashierUI
        return CashierUI
    if name == "CartWidget":
        from ui.cashier_window.cart_widget import CartWidget
        return CartWidget
    raise AttributeError(f"module 'ui.cashier_window' has no attribute {name!r}")

