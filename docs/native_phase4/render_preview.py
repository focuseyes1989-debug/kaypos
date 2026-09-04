"""Offline Phase 4 previews; no server calls and no physical printing."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from native_pos.catalog_dialogs import ProductDialog, PricingDialog
from native_pos.barcode import BarcodeDialog


def main():
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'))
    if families: app.setFont(QFont(families[0], 10))
    output = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as folder:
        window = NativeWindow(NativeTheme(app), Path(folder) / 'config.json')
        with patch.object(window, 'screen') as screen:
            screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728); window._fit_display()
        window.session = Session(1, 'demo.admin', 'Demo Admin', 'Admin', frozenset())
        window.store = ServerStore(Target('Server', server_url='https://offline-preview.invalid'))
        window.populate_routes(); window.route_pages[5].loaded = True
        records = [dict(id=1, name='A4 Copy Paper — 80 gsm', sku='PAPER-A4', barcode='1234567890123', category='Stationery', sold_by='Each',
                        price=12500, cost=9000, stock=24, low_stock=5, pack_size=5, unit='ream', revision='demo', pricing_revision='demo',
                        locations=[dict(id=1, product_id=1, location='Shop', batch_no='PAPER-SEP', quantity=10, expire_date=''),
                                   dict(id=2, product_id=1, location='Warehouse', batch_no='PAPER-SEP', quantity=14, expire_date='')],
                        variants=[], discounts=[dict(id=1, discount_type='percentage', discount_percent=5, manual_price=0, start_date='2026-09-01', end_date='2026-09-30', active=True, note='September offer')],
                        tiers=[dict(id=1, min_qty=5, unit_price=12000, unit_label='ream', unit_multiplier=1, active=True)]),
                   dict(id=2, name='Notebook — A5', sku='NOTE-A5', category='Stationery', sold_by='Each', price=2500, stock=48, low_stock=10),
                   dict(id=3, name='Uniform shirt', sku='SHIRT', category='Clothes', sold_by='Variants', price=0, stock=12, low_stock=3),
                   dict(id=4, name='Printing service', sku='PRINT', category='Services', sold_by='Service', price=500, stock=0, low_stock=0)]
        for route in (2, 9, 3):
            page = window.route_pages[route]; page.loaded = page.ready = True
            page.records = records; page.categories = [{'id': 1, 'name': 'Stationery'}]; page.render()
        window.catalog_session.message = 'Offline sample · Native metadata, discounts and audited inventory'
        window.identity.setText('Demo Admin · Admin\nOffline sample data · minimum 1366 × 768 display')
        window.navigate(2); window.show(); app.processEvents()
        window.grab().save(str(output / 'products-light.png'))
        editor = ProductDialog(records[0], [{'name': 'Stationery'}], window); editor.show(); app.processEvents()
        editor.grab().save(str(output / 'product-editor.png')); editor.close()
        pricing = PricingDialog(records[0], window); pricing.show(); app.processEvents()
        pricing.grab().save(str(output / 'discount-editor.png')); pricing.close()
        barcode = BarcodeDialog(records[0]['name'], records[0]['barcode'], window); barcode.width.setValue(60)
        barcode.show(); app.processEvents(); barcode.grab().save(str(output / 'barcode-preview.png')); barcode.close()
        window.config.update(style='Fusion', palette='Dark'); window.theme.apply(window.config); window.navigate(3)
        app.processEvents(); window.grab().save(str(output / 'inventory-dark.png'))
        window.close(); app.processEvents()


if __name__ == '__main__': main()
