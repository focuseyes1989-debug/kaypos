"""Server-backed sales workspace made exclusively from standard Qt widgets."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLabel, QSplitter, QDoubleSpinBox, QDateEdit, QInputDialog, QMessageBox,
    QDialog, QDialogButtonBox, QTextBrowser,
)

from lite_pos.cart import LiteCart, sold_by_mode
from native_pos.receipt import ReceiptDialog, receipt_html
from native_pos.sales_state import CheckoutJournal


def money_input():
    field = QDoubleSpinBox()
    field.setRange(0, 999999999999); field.setDecimals(2); field.setGroupSeparatorShown(True)
    field.setSuffix(' Ks')
    return field


def table(headers):
    view = QTableWidget(0, len(headers)); view.setHorizontalHeaderLabels(headers)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.verticalHeader().hide()
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    return view


def fill(view, rows):
    view.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            view.setItem(row, column, QTableWidgetItem(str(value)))


class SalesPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host; self.api = host.store.client; self.session = host.session
        self.cart = LiteCart(); self.products = []; self.offset = 0
        self.loaded = self.loading = self.ready = False
        self.pending = None; self.last_receipt = None; self.journal_error = ''
        directory = Path(host.settings_path).parent if host.settings_path else None
        self.journal = CheckoutJournal(self.api.server_url, self.session.user_id, directory)
        try:
            saved = self.journal.read()
            if saved:
                if saved.get('receipt'):
                    self.last_receipt = saved['receipt']
                else:
                    self.pending = saved
                    self.cart.items = saved.get('cart', {})
        except (OSError, ValueError) as exc:
            self.journal_error = str(exc)
        self._build()
        self.render_cart()

    def _build(self):
        layout = QVBoxLayout(self)
        self.message = QLabel('Load products to begin. F2: search · F4: barcode · F9: review sale')
        self.message.setWordWrap(True); self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message)
        self.controls = QWidget(); body = QVBoxLayout(self.controls); body.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(); body.addWidget(split, 1)
        left = QWidget(); catalog = QVBoxLayout(left); catalog.setContentsMargins(0, 0, 4, 0)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search products (F2)')
        self.search.returnPressed.connect(self.refresh)
        self.category = QComboBox(); self.category.addItem('All categories', '')
        self.category.activated.connect(self.refresh)
        search_button = QPushButton('Search'); search_button.clicked.connect(self.refresh)
        row = QHBoxLayout(); row.addWidget(self.search, 1); row.addWidget(search_button); catalog.addLayout(row)
        catalog.addWidget(self.category)
        self.barcode = QLineEdit(); self.barcode.setPlaceholderText('Scan barcode / SKU then Enter (F4)')
        self.barcode.returnPressed.connect(self.scan); catalog.addWidget(self.barcode)
        self.product_table = table(['Product', 'Price', 'Stock'])
        self.product_table.doubleClicked.connect(self.add_selected); catalog.addWidget(self.product_table, 1)
        row = QHBoxLayout()
        self.previous = QPushButton('Previous'); self.previous.clicked.connect(lambda: self.fetch_products(max(0, self.offset - 60)))
        self.next = QPushButton('Next'); self.next.clicked.connect(lambda: self.fetch_products(self.offset + 60))
        add = QPushButton('Add selected'); add.clicked.connect(self.add_selected)
        for button in (self.previous, self.next, add): row.addWidget(button)
        catalog.addLayout(row); split.addWidget(left)
        right = QWidget(); cart_layout = QVBoxLayout(right); cart_layout.setContentsMargins(4, 0, 0, 0)
        self.cart_table = table(['Cart', 'Qty', 'Price', 'Amount']); cart_layout.addWidget(self.cart_table, 1)
        row = QHBoxLayout()
        for label, action in [('−', lambda: self.change(-1)), ('+', lambda: self.change(1)),
                              ('Quantity…', self.set_quantity), ('Remove', self.remove), ('Clear', self.clear_cart)]:
            button = QPushButton(label); button.clicked.connect(action); row.addWidget(button)
        cart_layout.addLayout(row)
        self.estimate = QLabel(); self.estimate.setWordWrap(True); cart_layout.addWidget(self.estimate)
        form = QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.customer_query = QLineEdit(); self.customer_query.setPlaceholderText('Customer name / phone')
        self.customer_query.returnPressed.connect(self.find_customers)
        find = QPushButton('Find'); find.clicked.connect(self.find_customers)
        customer_row = QHBoxLayout(); customer_row.addWidget(self.customer_query, 1); customer_row.addWidget(find)
        form.addRow('Customer search', customer_row)
        self.customer = QComboBox(); self.customer.addItem('Walk-in customer', None); form.addRow('Customer', self.customer)
        self.discount = money_input()
        self.discount_type = QComboBox(); self.discount_type.addItems(['Amount', 'Percent'])
        discount_row = QHBoxLayout(); discount_row.addWidget(self.discount_type); discount_row.addWidget(self.discount, 1)
        form.addRow('Discount', discount_row)
        self.discount_type.currentTextChanged.connect(self.discount_mode)
        self.payment_type = QComboBox(); self.payment_type.addItem('Cash'); form.addRow('Payment type', self.payment_type)
        self.payment = money_input(); form.addRow('Paid / credit deposit', self.payment)
        self.due_date = QDateEdit(QDate.currentDate().addDays(15)); self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat('yyyy-MM-dd'); form.addRow('Credit due date', self.due_date)
        self.notes = QLineEdit(); self.notes.setMaxLength(2000); form.addRow('Credit notes', self.notes)
        self.payment_type.currentTextChanged.connect(self.credit_mode)
        self.credit_form = form; self.credit_mode(); cart_layout.addLayout(form)
        self.checkout_button = QPushButton('Review sale (F9)'); self.checkout_button.clicked.connect(self.review)
        cart_layout.addWidget(self.checkout_button); split.addWidget(right); split.setSizes([440, 580])
        layout.addWidget(self.controls, 1)
        actions = QHBoxLayout()
        self.reload_button = QPushButton('Connect / Refresh'); self.reload_button.clicked.connect(self.initialize)
        self.recover_button = QPushButton('Recover pending checkout'); self.recover_button.clicked.connect(self.recover)
        self.receipt_button = QPushButton('Last receipt'); self.receipt_button.clicked.connect(self.show_receipt)
        self.drawer_button = QPushButton('Open cash drawer…'); self.drawer_button.clicked.connect(self.open_drawer)
        for button in (self.reload_button, self.recover_button, self.receipt_button, self.drawer_button): actions.addWidget(button)
        layout.addLayout(actions)
        for key, action in [('F2', self.search.setFocus), ('F4', self.barcode.setFocus), ('F9', self.review)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); shortcut.activated.connect(action)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded and not self.loading:
            QTimer.singleShot(0, self.initialize)

    def credit_mode(self):
        credit = self.payment_type.currentText().casefold() == 'credit'
        self.credit_form.setRowVisible(self.due_date, credit)
        self.credit_form.setRowVisible(self.notes, credit)

    def discount_mode(self):
        percent = self.discount_type.currentText() == 'Percent'
        self.discount.setValue(0)
        self.discount.setMaximum(100 if percent else 999999999999)
        self.discount.setSuffix(' %' if percent else ' Ks')

    def set_message(self, text):
        self.message.setText(text)

    def update_enabled(self):
        busy = self.loading or self.host.runner.busy
        allowed = self.session.can('create_sale')
        self.controls.setEnabled(self.ready and allowed and not busy and not self.pending and not self.journal_error)
        self.reload_button.setEnabled(not busy)
        self.recover_button.setEnabled(bool(self.pending) and self.ready and not busy and not self.journal_error)
        self.receipt_button.setEnabled(bool(self.last_receipt) and not busy)
        self.drawer_button.setEnabled(self.ready and allowed and not busy and not self.pending)
        if self.journal_error:
            self.set_message('Checkout recovery file needs attention: ' + self.journal_error)
        elif self.pending and not busy:
            self.set_message('Checkout result is unknown. Recover this request before starting another sale. Do not re-enter it in another POS.')

    def run(self, operation, success, message):
        if self.host.runner.busy or self.host.closing:
            return False
        self.loading = True; self.set_message(message); self.update_enabled()
        self.host.logout_action.setEnabled(False); self.host.refresh_action.setEnabled(False)
        def done(value=None, error=None):
            self.loading = False
            try:
                if error:
                    self.set_message(error)
                else:
                    success(value)
            except Exception as exc:
                self.set_message(str(exc))
            finally:
                self.host.logout_action.setEnabled(True); self.host.refresh_action.setEnabled(True)
                self.update_enabled()
        self.host.runner.start(operation, lambda value: done(value=value), lambda error: done(error=error))
        return True

    def initialize(self):
        if self.host.runner.busy or self.host.closing:
            return
        self.loaded = True
        if not self.session.can('create_sale'):
            self.set_message('This account can view Sales but cannot create sales.'); self.update_enabled(); return
        def operation():
            try:
                capabilities = self.api._request('GET', '/api/native/sales/capabilities')
            except Exception as exc:
                raise RuntimeError('Native checkout unavailable. Update/restart the POS Server, check the connection and sale permissions. ' + str(exc)) from exc
            if capabilities.get('version') != 1:
                raise ValueError('Update the POS Server for Native checkout support.')
            return self.api.products(limit=60), self.api.categories(), self.api.payment_types()
        def loaded(result):
            products, categories, payments = result
            self.ready = True
            self.category.clear(); self.category.addItem('All categories', '')
            for category in categories: self.category.addItem(category, category)
            previous = self.payment_type.currentText()
            self.payment_type.clear()
            self.payment_type.addItems(list(dict.fromkeys(['Cash'] + [p for p in payments if p.casefold() != 'credit'] +
                                                        (['Credit'] if self.session.can('credit_sale') else []))))
            self.payment_type.setCurrentText(previous)
            self.offset = 0; self.search.clear(); self.display_products(products)
            self.set_message('Connected. Prices below are estimates; Review sale calculates final server prices and tax.')
        self.run(operation, loaded, 'Connecting to sales server…')

    def refresh(self):
        if self.ready: self.fetch_products(0)
        else: self.initialize()

    def fetch_products(self, offset):
        query, category = self.search.text(), self.category.currentData() or ''
        def done(products):
            self.offset = offset; self.display_products(products); self.set_message(f'Products {offset + 1}–{offset + len(products)}')
        self.run(lambda: self.api.products(query, 60, offset, category), done, 'Loading products…')

    def display_products(self, products):
        self.products = products
        fill(self.product_table, [(p.get('name', ''), f'{float(p.get("price") or 0):,.2f}',
                                  'Service' if sold_by_mode(p.get('sold_by')) == 'service' else p.get('stock', 0)) for p in products])
        self.previous.setEnabled(self.offset > 0); self.next.setEnabled(len(products) == 60)

    def scan(self):
        code = self.barcode.text().strip()
        if not code or self.pending or not self.ready: return
        def done(product):
            if not product: self.set_message('Barcode / SKU not found.'); return
            self.add_product(product); self.barcode.clear(); self.barcode.setFocus()
        self.run(lambda: self.api.scan_product(code), done, 'Looking up barcode…')

    def add_selected(self):
        row = self.product_table.currentRow()
        if 0 <= row < len(self.products): self.add_product(self.products[row])

    def add_product(self, product):
        if self.pending: return
        if sold_by_mode(product.get('sold_by')) == 'restaurant':
            self.set_message('Open Restaurant to choose menu modifiers and save this order.'); return
        product = dict(product); variant = None
        variants = product.get('variants') or []
        if variants or sold_by_mode(product.get('sold_by')) == 'variants':
            if not variants:
                self.set_message('No active variants available.'); return
            variant = next((v for v in variants if v.get('variant_id') == product.get('matched_variant_id')), None)
            if not variant:
                options = [f'{n + 1}. {v.get("color", "")} / {v.get("size", "")} · {float(v.get("price") or product.get("price") or 0):,.2f} · Stock {v.get("stock", 0)}'
                           for n, v in enumerate(variants)]
                chosen, accepted = QInputDialog.getItem(self, 'Select variant', product.get('name', ''), options, 0, False)
                if not accepted: return
                variant = variants[options.index(chosen)]
        if sold_by_mode(product.get('sold_by')) == 'service':
            price, accepted = QInputDialog.getDouble(self, 'Service price', product.get('name', ''), float(product.get('price') or 0), 0, 999999999, 2)
            if not accepted: return
            product['price'] = price
        try:
            self.cart.add(product, variant); self.render_cart(); self.set_message('Added ' + product.get('name', ''))
        except ValueError as exc: self.set_message(str(exc))

    def selected_key(self):
        keys = list(self.cart.items); row = self.cart_table.currentRow()
        return keys[row] if 0 <= row < len(keys) else None

    def change(self, delta):
        if self.pending: return
        key = self.selected_key()
        try:
            self.cart.change(key, delta); self.render_cart()
        except ValueError as exc: self.set_message(str(exc))

    def set_quantity(self):
        key = self.selected_key()
        if key:
            item = self.cart.items[key]
            value, accepted = QInputDialog.getInt(self, 'Quantity', item['name'], item['qty'], 1, 1000000)
            if accepted: self.change(value - item['qty'])

    def remove(self):
        key = self.selected_key()
        if key: self.change(-self.cart.items[key]['qty'])

    def clear_cart(self):
        if not self.cart.items or self.pending: return
        if QMessageBox.question(self, 'Clear cart', 'Remove all items from this cart?') == QMessageBox.StandardButton.Yes:
            self.cart.clear(); self.render_cart()

    def render_cart(self):
        row = self.cart_table.currentRow()
        fill(self.cart_table, [(i['name'] + (' / ' + i['variant_label'] if i.get('variant_label') else ''), i['qty'],
                               f'{i["price"]:,.2f}', f'{i["price"] * i["qty"]:,.2f}') for i in self.cart.items.values()])
        if self.cart.items: self.cart_table.selectRow(max(0, min(row, len(self.cart.items) - 1)))
        self.estimate.setText(f'{self.cart.count()} item(s) · Estimated subtotal: {self.cart.total():,.2f} Ks\nFinal discounts, wholesale prices and tax are calculated at review.')
        self.update_enabled()

    def find_customers(self):
        query = self.customer_query.text()
        def done(customers):
            self.customer.clear(); self.customer.addItem('Walk-in customer', None)
            for customer in customers:
                self.customer.addItem(f'{customer.get("name", "")} · {customer.get("phone", "")} (#{customer["id"]})', customer['id'])
            if len(customers) == 1: self.customer.setCurrentIndex(1)
            self.set_message(f'{len(customers)} customer(s) found. Narrow the search if needed.')
        self.run(lambda: self.api.customers(query), done, 'Finding customers…')

    def payload(self):
        credit = self.payment_type.currentText().casefold() == 'credit'
        return dict(items=[dict(product_id=i['product_id'], variant_id=i['variant_id'], qty=i['qty'],
                                manual_price=i['price'] if i['is_service'] else None) for i in self.cart.items.values()],
                    payment=self.payment.value(), payment_type=self.payment_type.currentText(), sale_mode='Credit' if credit else 'Cash',
                    customer_id=self.customer.currentData(),
                    discount_amount=self.discount.value() if self.discount_type.currentText() == 'Amount' else 0,
                    discount_percent=self.discount.value() if self.discount_type.currentText() == 'Percent' else 0, points_used=0,
                    due_date=self.due_date.date().toString('yyyy-MM-dd') if credit else '', credit_notes=self.notes.text() if credit else '',
                    allow_credit_over_limit=False)

    def review(self):
        if not self.controls.isEnabled() or not self.cart.items: return
        payload = self.payload()
        if payload['sale_mode'] == 'Credit' and not payload['customer_id']:
            self.set_message('Select a customer for credit sales.'); return
        self.run(lambda: self.api._request('POST', '/api/native/sales/quote', json=payload),
                 lambda result: self.confirm_quote(payload, result['quote']), 'Checking server prices, tax and stock…')

    def confirm_quote(self, payload, quote):
        if self.host.closing: return
        dialog = QDialog(self); dialog.setWindowTitle('Review sale · nothing saved yet'); dialog.resize(630, 530)
        layout = QVBoxLayout(dialog); browser = QTextBrowser(); browser.setHtml(receipt_html(quote)); layout.addWidget(browser)
        form = QFormLayout(); paid = money_input(); paid.setValue(payload['payment'])
        credit = payload['sale_mode'] == 'Credit'
        if not credit and not payload['payment']: paid.setValue(quote['total'])
        form.addRow('Credit deposit' if credit else 'Amount paid', paid); layout.addLayout(form)
        info = QLabel(); layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        confirm = buttons.addButton('Confirm sale', QDialogButtonBox.ButtonRole.AcceptRole)
        layout.addWidget(buttons)
        def validate():
            value = paid.value(); total = float(quote['total'])
            valid = 0 <= value <= total if credit else value + 0.00001 >= total
            confirm.setEnabled(valid)
            info.setText(f'{"Balance" if credit else "Change"}: {abs(total - value):,.2f} Ks' if valid else 'Check the amount paid.')
        paid.valueChanged.connect(validate); validate()
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        payload.update(payment=paid.value(), request_id=str(uuid4()), expected_total=quote['total'])
        pending = dict(payload=payload, cart=deepcopy(self.cart.items))
        try:
            self.journal.write(pending)
        except OSError as exc:
            self.set_message('Checkout was not sent: cannot save recovery file. ' + str(exc)); return
        self.pending = pending
        self.recover()

    def recover(self):
        if not self.pending or self.host.runner.busy: return
        payload = deepcopy(self.pending['payload'])
        self.run(lambda: self.api._request('POST', '/api/native/sales', json=payload), self.checkout_result,
                 'Resolving checkout… Keep this request until the server confirms the result.')

    def checkout_result(self, result):
        if result.get('rejected'):
            self.journal.clear(); self.pending = None
            self.set_message('Sale was not saved: ' + result['rejected']); return
        receipt = result.get('receipt')
        if not receipt or not receipt.get('id'):
            raise ValueError('No complete receipt returned. Recover the pending checkout.')
        saved = dict(self.pending, receipt=receipt)
        self.journal.write(saved)
        self.last_receipt = receipt; self.pending = None; self.cart.clear()
        self.discount.setValue(0); self.payment.setValue(0); self.notes.clear(); self.customer.setCurrentIndex(0)
        self.render_cart(); self.set_message('Sale saved: ' + str(receipt.get('invoice_no', receipt['id'])))
        if not self.host.closing: self.after_sale()

    def after_sale(self):
        from native_pos.config import load_config
        action = load_config(self.host.settings_path)['after_sale']
        if action == 'stay_sales': return
        self.show_receipt()
        if action == 'show_receipt_ask_drawer' and not self.host.closing:
            self.open_drawer()

    def show_receipt(self):
        if self.last_receipt:
            ReceiptDialog(self.last_receipt, self, self.session.can('print_receipt')).exec()

    def open_drawer(self):
        if not self.ready or self.pending or self.host.runner.busy or not self.session.can('create_sale'): return
        from native_pos.config import load_config
        from native_pos.cash_drawer import authorized_local_drawer
        config = load_config(self.host.settings_path)
        if config['drawer_target'] == 'local':
            name = config['receipt_printer']
            if not name:
                QMessageBox.information(self, 'Local cash drawer', 'Select a Windows receipt printer in Settings first.'); return
            if QMessageBox.question(self, 'Local cash drawer', f'Open the drawer attached to {name} on THIS PC?') != QMessageBox.StandardButton.Yes: return
            self.run(lambda: authorized_local_drawer(self.api, name), lambda result: self.set_message(result['message']), 'Sending local drawer pulse…')
            return
        if QMessageBox.question(self, 'Server cash drawer',
                                'Open the drawer attached to the POS SERVER printer?') != QMessageBox.StandardButton.Yes:
            return
        self.run(lambda: self.api._request('POST', '/api/native/cashdrawer/open'),
                 lambda result: self.set_message(str(result.get('message') or 'Server cash drawer command sent.')),
                 'Opening server cash drawer…')

    def can_leave(self):
        if self.pending or not self.cart.items:
            return True  # Pending checkout is durable and restored for this account.
        return QMessageBox.question(self, 'Unsaved cart', 'Discard this cart and leave?') == QMessageBox.StandardButton.Yes
