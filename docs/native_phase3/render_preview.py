"""Render an offline fixture at the minimum supported Windows work area."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow


def main():
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families: app.setFont(QFont(families[0], 10))
    with tempfile.TemporaryDirectory() as folder:
        window = NativeWindow(NativeTheme(app), Path(folder) / 'config.json')
        with patch.object(window, 'screen') as screen:
            screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728)
            window._fit_display()
        window.session = Session(1, 'demo.cashier', 'Demo Cashier', 'Admin', frozenset())
        window.store = ServerStore(Target('Server', server_url='https://offline-preview.invalid'))
        window.populate_routes(); page = window.route_pages[5]
        page.loaded = page.ready = True
        products = [dict(id=1, name='A4 Copy Paper — 80 gsm', price=12500, stock=24),
                    dict(id=2, name='Notebook — A5', price=2500, stock=48),
                    dict(id=3, name='Black ink cartridge', price=32500, stock=8),
                    dict(id=4, name='Printing service', price=500, stock=0, sold_by='Service')]
        page.display_products(products)
        page.add_product(products[0]); page.add_product(products[1]); page.add_product(products[1])
        page.payment_type.addItems(['Card', 'Mobile Money', 'Credit'])
        page.payment.setValue(20000)
        page.set_message('Offline sample · final prices, wholesale discounts and tax are calculated by the server at review.')
        window.identity.setText('Demo Cashier · Admin\nServer connection · offline sample data')
        window.show(); app.processEvents()
        output = Path(__file__).resolve().parent
        window.grab().save(str(output / 'sales-light.png'))
        window.config.update(style='Fusion', palette='Dark'); window.theme.apply(window.config)
        app.processEvents(); window.grab().save(str(output / 'sales-dark.png'))
        page.cart.clear(); window.close(); app.processEvents()


if __name__ == '__main__': main()
