"""Render real Native widgets from disposable fixture data; no network or printers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tempfile
from unittest.mock import Mock, patch

from PyQt6.QtCore import QEventLoop, QTimer, QRect
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication
from native_pos.business_dialogs import CreditDialog, OrderDialog, MenuLineDialog
from native_pos.catalog_dialogs import ProductDialog
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from tests.test_native_pos_phase5 import BusinessDatabaseTests


def main():
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'))
    if families: app.setFont(QFont(families[0], 10))
    output = Path(__file__).resolve().parent
    fixture = BusinessDatabaseTests(); fixture.setUp()
    try:
        fixture.command('customer.save', dict(name='Aung Aung', phone='09 123 456 789', credit_limit=500000))
        fixture.command('customer.save', dict(name='Mya Mya', phone='09 456 789 012', credit_limit=300000))
        fixture.credit_sale(payment=50)
        fixture.command('expense.save', dict(category='Rent', amount=150000, expense_date='2026-09-04', description='September shop rental', payment_method='Bank transfer'))
        fixture.command('expense.budget', dict(category='Rent', year=2026, month=9, budget_amount=200000))
        fixture.command('restaurant.table', dict(table_no='T1', display_name='Table 1', seats=4))
        fixture.command('restaurant.table', dict(table_no='T2', display_name='Table 2', seats=6))
        order = fixture.new_order(table_id=1, customer_id=1)
        fixture.command('restaurant.send', order)
        with tempfile.TemporaryDirectory() as folder:
            window = NativeWindow(NativeTheme(app), Path(folder) / 'config.json')
            with patch.object(window, 'screen') as screen:
                screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728); window._fit_display()
            window.session = Session(1, 'cashier', 'Demo Admin', 'Admin', frozenset())
            window.store = ServerStore(Target('Server', server_url='https://offline-preview.invalid'))
            api = Mock(); api.server_url = 'https://offline-preview.invalid'
            api._request.side_effect = lambda method, path, params: fixture.repo.read(fixture.user, **params)
            window.store.client = api; window.populate_routes()
            for page in window.route_pages.values():
                if hasattr(page, 'loaded'): page.loaded = True
            window.identity.setText('Demo Admin · Admin\nOffline fixture data · minimum 1366 × 768 display')
            window.show(); app.processEvents()
            for route, filename in [(6, 'customers-light.png'), (4, 'receipts-light.png'), (7, 'expenses-light.png'), (10, 'restaurant-light.png')]:
                page = window.route_pages[route]; window.navigate(route); page.refresh()
                loop = QEventLoop(); window.runner.idle.connect(loop.quit); QTimer.singleShot(5000, loop.quit); loop.exec()
                app.processEvents(); window.grab().save(str(output / filename))
            credit = CreditDialog(fixture.repo.read(fixture.user, 'credit', 1), True, window)
            credit.show(); app.processEvents(); credit.grab().save(str(output / 'credit-dialog.png')); credit.close()
            restaurant = window.route_pages[10]
            editor = OrderDialog(restaurant, fixture.repo.read(fixture.user, 'restaurant', order['id']), restaurant.data['tables'])
            editor.show(); app.processEvents(); editor.grab().save(str(output / 'order-dialog.png')); editor.close()
            line = MenuLineDialog(fixture.repo.menu_product(fixture.user, 4), window)
            line.show(); app.processEvents(); line.grab().save(str(output / 'modifiers-dialog.png')); line.close()
            window.config.update(style='Fusion', palette='Dark'); window.theme.apply(window.config)
            app.processEvents(); window.grab().save(str(output / 'restaurant-dark.png'))
            window.close(); app.processEvents()
    finally: fixture.doCleanups()


if __name__ == '__main__': main()
