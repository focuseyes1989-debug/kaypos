"""Native Products, Discounts and Inventory pages sharing one recoverable command channel."""
from copy import deepcopy
import csv
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton,
    QLabel, QPlainTextEdit, QMessageBox, QDialog, QDialogButtonBox, QFileDialog, QCheckBox, QSplitter, QInputDialog)
from lite_pos.cart import sold_by_mode
from native_pos.sales import table, fill
from native_pos.sales_state import CheckoutJournal
from native_pos.catalog_dialogs import ProductDialog, PricingDialog, StockDialog, CategoryDialog


class CatalogSession(QObject):
    changed = pyqtSignal()
    saved = pyqtSignal(object)

    def __init__(self, host, namespace='catalog'):
        super().__init__(host); self.host = host; self.api = host.store.client
        self.namespace = namespace
        directory = Path(host.settings_path).parent if host.settings_path else None
        from native_pos.protected_journal import ProtectedJournal
        journal_class = ProtectedJournal if namespace in ('admin', 'operations', 'files', 'telegram', 'cloud_config') else CheckoutJournal
        self.journal = journal_class(self.api.server_url + '/native/' + namespace, host.session.user_id, directory)
        self.pending = None; self.error = ''; self.message = ''; self.busy = False
        try:
            saved = self.journal.read()
            if saved and not saved.get('result'): self.pending = saved
            elif saved: self.message = saved['result'].get('message', 'Last catalog change confirmed')
        except (OSError, ValueError) as exc: self.error = str(exc)

    def run(self, operation, success, message):
        if self.host.runner.busy or self.host.closing: return False
        self.busy = True; self.message = message; self.changed.emit()
        self.host.logout_action.setEnabled(False); self.host.refresh_action.setEnabled(False)
        def done(value=None, error=None):
            self.busy = False
            try:
                if error: self.message = error
                else: success(value)
            except Exception as exc: self.message = str(exc)
            finally:
                self.host.logout_action.setEnabled(True); self.host.refresh_action.setEnabled(True); self.changed.emit()
        self.host.runner.start(operation, lambda result: done(value=result), lambda error: done(error=error))
        return True

    def submit(self, operation, values):
        if self.pending or self.error or self.host.runner.busy: return
        pending = {'payload': {'request_id': str(uuid4()), 'operation': operation, 'values': deepcopy(values)}}
        try: self.journal.write(pending)
        except OSError as exc:
            self.message = 'Change was not sent: cannot save recovery record. ' + str(exc); self.changed.emit(); return
        self.pending = pending; self.recover()

    def recover(self):
        if not self.pending or self.error: return
        payload = deepcopy(self.pending['payload'])
        self.run(lambda: self.api._request('POST', '/api/native/' + self.namespace + '/commands', json=payload), self.result,
                 'Saving / recovering change…')

    def result(self, response):
        if response.get('rejected'):
            self.journal.clear(); self.pending = None
            self.message = 'Change was not saved: ' + response['rejected']; return
        result = response.get('result')
        if not result or result.get('request_id') != self.pending['payload']['request_id']:
            raise ValueError('Incomplete response. Recover this change before making another edit.')
        self.journal.write(dict(self.pending, result=result)); self.pending = None
        sales = self.host.route_pages.get(5)
        if hasattr(sales, 'loaded'): sales.loaded = False
        self.message = result.get('message') or 'Saved'; self.saved.emit(result)


class CatalogPage(QWidget):
    def __init__(self, host, section):
        super().__init__(host); self.host = host; self.section = section
        if getattr(host, 'catalog_session', None) is None: host.catalog_session = CatalogSession(host)
        self.channel = host.catalog_session; self.api = self.channel.api
        self.ready = self.loaded = False; self.records = []; self.visible_records = []; self.categories = []; self.offset = 0
        layout = QVBoxLayout(self)
        self.status = QLabel('Connect to the updated POS Server to begin.'); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        filters = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText('Product name / SKU / barcode')
        self.search.returnPressed.connect(self.refresh)
        self.category = QComboBox(); self.category.addItem('All categories', ''); self.category.activated.connect(self.refresh)
        self.refresh_button = QPushButton('Search / Refresh'); self.refresh_button.clicked.connect(self.refresh)
        self.low = QCheckBox('Low stock (this page)'); self.low.toggled.connect(self.render)
        for widget in (self.search, self.category, self.refresh_button, self.low): filters.addWidget(widget)
        layout.addLayout(filters)
        split = QSplitter(Qt.Orientation.Vertical)
        self.table = table(['Product', 'SKU / barcode', 'Category', 'Mode', 'Price', 'Stock', 'Low alert'])
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.doubleClicked.connect(lambda: self.edit() if self.section == 'products' else self.pricing() if self.section == 'discounts' else self.show_detail())
        self.summary = QPlainTextEdit(); self.summary.setReadOnly(True); self.summary.setMaximumHeight(145)
        split.addWidget(self.table); split.addWidget(self.summary); split.setStretchFactor(0, 1); layout.addWidget(split, 1)
        self.action_buttons = []
        actions = QHBoxLayout()
        def action(label, permission, callback, selected=True):
            button = QPushButton(label); button.clicked.connect(callback); actions.addWidget(button)
            self.action_buttons.append((button, permission, selected))
            return button
        if section == 'products':
            action('New product', 'add_product', self.new_product, False)
            action('Edit product', 'edit_product', self.edit)
            action('Delete unused', 'delete_product', self.delete_product)
            action('Categories…', 'edit_product', self.manage_categories, False)
            action('Import CSV…', 'add_product', self.import_csv, False)
            action('Barcode label…', 'products', self.barcode)
        elif section == 'discounts': action('Edit discounts / wholesale…', 'edit_product', self.pricing)
        else:
            action('Stock In…', 'stock_in', lambda: self.stock('stock.in'))
            action('Stock Out…', 'stock_out', lambda: self.stock('stock.out'))
            action('Set counted stock…', 'adjustment', lambda: self.stock('stock.set'))
            action('Transfer…', 'stock_in', lambda: self.stock('stock.transfer'))
            action('Movement history', 'inventory', self.history)
        action('Details', 'inventory' if section == 'inventory' else 'products', self.show_detail)
        layout.addLayout(actions)
        bottom = QHBoxLayout()
        self.previous = QPushButton('Previous'); self.previous.clicked.connect(lambda: self.fetch(max(0, self.offset - 60)))
        self.next = QPushButton('Next'); self.next.clicked.connect(lambda: self.fetch(self.offset + 60))
        self.page_label = QLabel()
        export = QPushButton('Export metadata CSV…' if section == 'products' else 'Export page CSV…'); export.clicked.connect(self.export)
        self.recover_button = QPushButton('Recover pending change'); self.recover_button.clicked.connect(self.channel.recover)
        for widget in (self.previous, self.page_label, self.next, export, self.recover_button): bottom.addWidget(widget)
        layout.addLayout(bottom)
        self.channel.changed.connect(self.update_enabled); self.channel.saved.connect(self.changed)
        self.host.runner.idle.connect(self.update_enabled)
        self.update_enabled()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded: QTimer.singleShot(0, self.refresh)

    def permission(self): return 'inventory' if self.section == 'inventory' else 'products'

    def update_enabled(self):
        busy = self.host.runner.busy or self.channel.busy
        editable = self.ready and not busy and not self.channel.pending and not self.channel.error
        selected = self.selected()
        for button, permission, needs_selection in self.action_buttons:
            button.setEnabled(editable and self.host.session is not None and self.host.session.can(permission) and (bool(selected) or not needs_selection))
            if button.text() == 'Transfer…' and self.host.session and not self.host.session.can('stock_out'): button.setEnabled(False)
        for widget in (self.search, self.category, self.refresh_button): widget.setEnabled(not busy)
        self.previous.setEnabled(not busy and self.offset > 0); self.next.setEnabled(not busy and len(self.records) == 60)
        self.recover_button.setEnabled(bool(self.channel.pending) and not busy and not self.channel.error)
        if self.channel.error: self.status.setText('Recovery file needs attention: ' + self.channel.error)
        elif self.channel.pending and not busy:
            self.status.setText('A catalog/stock change is unresolved. Recover it before another edit. Do not repeat it in another POS.')
        else: self.status.setText(self.channel.message or 'Products / Inventory connected')

    def refresh(self):
        if self.host.runner.busy or self.host.closing: return
        self.loaded = True
        if not self.ready:
            section = self.permission()
            def initialize():
                try: return self.api._request('GET', '/api/native/catalog', params={'section': section})
                except Exception as exc: raise RuntimeError('Update/restart the POS Server and check permissions/connection. ' + str(exc)) from exc
            def initialized(data):
                if data.get('version') != 1: raise ValueError('Native catalog server version is unsupported')
                self.categories = data['categories']; self.ready = True
                self.category.clear(); self.category.addItem('All categories', '')
                for row in self.categories: self.category.addItem(row['name'], row['name'])
                QTimer.singleShot(0, lambda: self.fetch(0))
            self.channel.run(initialize, initialized, 'Connecting to Native catalog…')
        else: self.fetch(0)

    def fetch(self, offset):
        query, category = self.search.text(), self.category.currentData() or ''
        def done(records):
            self.records = records; self.offset = offset; self.channel.message = 'Choose a product to view or edit.'; self.render()
        self.channel.run(lambda: self.api.products(query, 60, offset, category), done, 'Loading products…')

    def render(self):
        self.visible_records = [p for p in self.records if not self.low.isChecked() or
                                (sold_by_mode(p.get('sold_by')) != 'service' and int(p.get('stock') or 0) <= int(p.get('low_stock') or 0))]
        fill(self.table, [(p.get('name', ''), p.get('sku') or p.get('barcode') or '', p.get('category', ''), p.get('sold_by', 'Each'),
                          f'{float(p.get("price") or 0):,.2f}', p.get('stock', 0), p.get('low_stock', 0)) for p in self.visible_records])
        self.page_label.setText(f'Offset {self.offset} · {len(self.visible_records)} shown / {len(self.records)} loaded')
        if self.visible_records: self.table.selectRow(0)
        else: self.summary.clear()
        self.update_enabled()

    def selected(self):
        row = self.table.currentRow()
        return self.visible_records[row] if 0 <= row < len(self.visible_records) else None

    def selection_changed(self):
        product = self.selected()
        if product:
            places = '\n'.join(f'{v.get("location", "")} · Batch {v.get("batch_no", "")} · Qty {v.get("quantity", 0)} · Expiry {v.get("expire_date", "")}' for v in product.get('locations', []))
            self.summary.setPlainText(f'{product.get("name", "")}\n{product.get("description", "")}\n{places}')
        self.update_enabled()

    def detail(self, callback):
        product = self.selected()
        if not product: return
        product_id = product['id']; section = self.permission()
        def done(data):
            if not self.host.closing: callback(data)
        self.channel.run(lambda: self.api._request('GET', '/api/native/catalog', params={'section': section, 'product_id': product_id}), done, 'Reading current product and stock…')

    def open_editor(self, dialog, operation):
        if self.channel.pending or self.channel.error or self.host.closing: return
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        try: values = dialog.values()
        except (ValueError, OSError) as exc:
            self.channel.message = str(exc); self.channel.changed.emit(); return
        self.channel.submit(getattr(dialog, 'operation', operation), values)

    def new_product(self):
        if self.host.session.can('add_product'): self.open_editor(ProductDialog(None, self.categories, self), 'product.save')

    def edit(self):
        if self.host.session.can('edit_product'): self.detail(lambda p: self.open_editor(ProductDialog(p, self.categories, self), 'product.save'))

    def delete_product(self):
        def confirm(product):
            if QMessageBox.question(self, 'Delete unused product', f'Delete {product["name"]}? Products with stock or history cannot be deleted.') == QMessageBox.StandardButton.Yes:
                self.channel.submit('product.delete', {'id': product['id'], 'revision': product['revision']})
        self.detail(confirm)

    def manage_categories(self):
        def done(data):
            self.categories = data['categories']
            dialog = CategoryDialog(self.categories, self); dialog.delete.setEnabled(self.host.session.can('delete_product'))
            self.open_editor(dialog, 'category.save')
        self.channel.run(lambda: self.api._request('GET', '/api/native/catalog'), done, 'Loading categories…')

    def pricing(self):
        if not self.host.session.can('edit_product'): return
        def done(product):
            if sold_by_mode(product.get('sold_by')) != 'each':
                self.channel.message = 'Product discounts and wholesale tiers apply to Each products.'; return
            self.open_editor(PricingDialog(product, self), 'pricing.save')
        self.detail(done)

    def stock(self, operation):
        def done(product):
            mode = sold_by_mode(product.get('sold_by'))
            if mode == 'service' or (mode == 'variants' and operation == 'stock.transfer'):
                self.channel.message = 'This operation is not available for this product mode.'; return
            self.open_editor(StockDialog(product, operation, self.host.session.username, self), operation)
        self.detail(done)

    def show_detail(self):
        def done(product):
            lines = [f'{product["name"]} · ID {product["id"]}', f'Regular price: {product.get("price", 0)} · Cost: {product.get("cost", 0)} · Stock: {product.get("stock", 0)}']
            for key in ('variants', 'locations', 'discounts', 'tiers'):
                lines.append('\n' + key.title())
                for row in product.get(key, []): lines.append(' · '.join(f'{k}: {v}' for k, v in row.items() if v not in (None, '')))
            dialog = QDialog(self); dialog.setWindowTitle('Product details'); dialog.resize(850, 530)
            layout = QVBoxLayout(dialog); text = QPlainTextEdit('\n'.join(lines)); text.setReadOnly(True); layout.addWidget(text)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons); dialog.exec()
        self.detail(done)

    def history(self):
        product = self.selected()
        if not product: return
        product_id = product['id']
        def done(response):
            if self.host.closing: return
            rows = response['movements']
            dialog = QDialog(self); dialog.setWindowTitle('Stock movement history · latest 200'); dialog.resize(1050, 530)
            layout = QVBoxLayout(dialog); view = table(['Date', 'Type', 'Qty', 'Before', 'After', 'Location', 'By', 'Reason', 'Reference'])
            fill(view, [(r.get('created_at'), r.get('type'), r.get('quantity'), r.get('old_stock'), r.get('new_stock'), r.get('location'),
                         r.get('created_by'), r.get('reason'), r.get('reference')) for r in rows]); layout.addWidget(view)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject)
            reverse = buttons.addButton('Reverse selected Native operation…', QDialogButtonBox.ButtonRole.ActionRole)
            reverse.setEnabled(self.host.session.can('adjustment'))
            def reverse_selected():
                index = view.currentRow()
                if not 0 <= index < len(rows): return
                original = rows[index].get('native_request_id')
                if not original:
                    QMessageBox.information(dialog, 'Reversal', 'Use the existing POS for legacy movement reversals.'); return
                reason, accepted = QInputDialog.getText(dialog, 'Reverse Native operation', 'Reason (the entire operation, including both transfer entries, will be reversed):')
                if not accepted or not reason.strip(): return
                dialog.accept()
                def ready(product):
                    self.channel.submit('stock.reverse', dict(product_id=product_id, stock_revision=product['stock_revision'],
                                                             original_request_id=original, reason=reason.strip()))
                self.channel.run(lambda: self.api._request('GET', '/api/native/catalog', params={'section': 'inventory', 'product_id': product_id}), ready, 'Checking current stock before reversal…')
            reverse.clicked.connect(reverse_selected); layout.addWidget(buttons); dialog.exec()
        self.channel.run(lambda: self.api._request('GET', '/api/native/catalog', params={'section': 'history', 'product_id': product_id}), done, 'Loading movement history…')

    def barcode(self):
        from native_pos.barcode import BarcodeDialog
        def done(product):
            name = product['name']; code = str(product.get('barcode') or product.get('sku') or '')
            if sold_by_mode(product.get('sold_by')) == 'variants':
                variants = [v for v in product.get('variants', []) if v.get('active', 1)]
                if not variants: self.channel.message = 'No active variants available'; return
                labels = [f'{i+1}. {v.get("color", "")} / {v.get("size", "")} · {v.get("barcode") or v.get("sku") or "No code"}' for i, v in enumerate(variants)]
                chosen, accepted = QInputDialog.getItem(self, 'Variant label', 'Variant', labels, 0, False)
                if not accepted: return
                variant = variants[labels.index(chosen)]; code = str(variant.get('barcode') or variant.get('sku') or '')
                name += ' / ' + str(variant.get('color') or '') + ' / ' + str(variant.get('size') or '')
            try: BarcodeDialog(name, code, self).exec()
            except ValueError as exc: self.channel.message = str(exc)
        self.detail(done)

    def import_csv(self):
        from native_pos.catalog_transfer import read_products
        path, _ = QFileDialog.getOpenFileName(self, 'Import Native product metadata', '', 'CSV (*.csv)')
        if not path: return
        try:
            records = read_products(path)
            for record in records:
                if not self.host.session.can('edit_product' if record.get('id') else 'add_product'):
                    raise ValueError('Your account does not have permission for every product in this file')
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'CSV import', str(exc)); return
        dialog = QDialog(self); dialog.setWindowTitle('Review CSV import'); dialog.resize(850, 540)
        layout = QVBoxLayout(dialog)
        note = QLabel(f'{len(records)} products. Existing IDs update metadata; blank IDs create products with zero stock.\nStock is not imported. The entire file rolls back if any row fails server validation.')
        note.setWordWrap(True); layout.addWidget(note)
        view = table(['Product', 'Action', 'Mode', 'Category', 'Regular price'])
        fill(view, [(r['name'], f'Update #{r["id"]}' if r.get('id') else 'Create', r['sold_by'], r.get('category', ''), r['price']) for r in records]); layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton('Import reviewed products', QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.channel.submit('products.import', {'rows': records})

    def changed(self, result):
        self.loaded = False
        if result.get('operation', '').startswith('category.'): self.ready = False
        if self.isVisible() and not self.host.closing: QTimer.singleShot(0, self.refresh)

    def export(self):
        if not self.visible_records: return
        path, _ = QFileDialog.getSaveFileName(self, 'Export displayed page', f'{self.section}.csv', 'CSV (*.csv)')
        if not path: return
        if self.section == 'products':
            from native_pos.catalog_transfer import write_products
            ids = [r['id'] for r in self.visible_records]
            def operation():
                return [self.api._request('GET', '/api/native/catalog', params={'product_id': product_id}) for product_id in ids]
            def done(records):
                write_products(path, records)
                self.channel.message = f'{len(records)} product metadata rows exported. Stock is excluded from import.'
            self.channel.run(operation, done, 'Reading product metadata for CSV export…'); return
        def safe(value):
            text = str(value or '')
            return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.writer(stream); fields = ['id', 'name', 'sku', 'barcode', 'category', 'sold_by', 'price', 'stock', 'low_stock']
                writer.writerow(fields)
                for record in self.visible_records: writer.writerow([safe(record.get(key)) for key in fields])
            self.channel.message = 'Displayed page exported to ' + path
        except OSError as exc: self.channel.message = str(exc)
        self.channel.changed.emit()
