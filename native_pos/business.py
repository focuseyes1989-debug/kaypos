"""Phase 5 standard-widget pages; all database work stays on the POS server."""
import csv
from datetime import date
from pathlib import Path

from PyQt6.QtCore import QDate, QTimer, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDateEdit, QDialog, QMessageBox, QInputDialog, QFileDialog, QPlainTextEdit)
from native_pos.catalog import CatalogSession
from native_pos.sales import table, fill
from native_pos.receipt import ReceiptDialog
from native_pos.sales_state import CheckoutJournal
from native_pos.business_dialogs import FormDialog, CUSTOMER_FORM, CreditDialog, ChoiceDialog, OrderDialog, KitchenDialog


COLUMNS = {
    'customers': [('name', 'Name'), ('phone', 'Phone'), ('email', 'Email'), ('credit_limit', 'Credit limit'), ('current_balance', 'Balance')],
    'receipts': [('invoice_no', 'Invoice'), ('created_at', 'Date / time'), ('total', 'Total'), ('payment_type', 'Payment'), ('status', 'Status'), ('created_by', 'Cashier')],
    'expenses': [('expense_no', 'Expense'), ('expense_date', 'Date'), ('category', 'Category'), ('description', 'Description'), ('amount', 'Amount'), ('payment_method', 'Method')],
    'restaurant': [('order_no', 'Order'), ('table_name', 'Table'), ('order_type', 'Type'), ('customer_name', 'Customer'), ('total_amount', 'Total'), ('status', 'Status'), ('kitchen_status', 'Kitchen')],
}


def safe_csv(value):
    text = str(value if value is not None else '')
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text


class BusinessPage(QWidget):
    def __init__(self, host, section):
        super().__init__(host); self.host = host; self.section = section; self.loaded = False; self.ready = False
        if getattr(host, 'business_session', None) is None: host.business_session = CatalogSession(host, 'business')
        self.channel = host.business_session; self.api = self.channel.api; self.records = []; self.data = {}; self.offset = 0; self.notice = ''
        self.last_receipt = None
        if section == 'restaurant':
            self.receipt_journal = CheckoutJournal(self.api.server_url + '/native/restaurant-receipt', host.session.user_id,
                Path(host.settings_path).parent if host.settings_path else None)
            try:
                saved = self.receipt_journal.read()
                if not saved:
                    candidate = self.channel.journal.read()
                    if candidate and candidate.get('result', {}).get('receipt'): saved = candidate
                if saved: self.last_receipt = saved['result']['receipt']
            except (OSError, ValueError, KeyError) as exc: self.notice = 'Last receipt file: ' + str(exc)
        body = QVBoxLayout(self); self.status = QLabel('Connect to the updated POS Server to begin.'); self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(self.status)
        filters = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText('Search name / phone' if section == 'customers' else 'Search invoice / category / description')
        self.search.returnPressed.connect(self.refresh); filters.addWidget(self.search, 1)
        self.start = QDateEdit(QDate.currentDate().addDays(1 - QDate.currentDate().day())); self.end = QDateEdit(QDate.currentDate())
        for widget in (self.start, self.end): widget.setDisplayFormat('yyyy-MM-dd'); widget.setCalendarPopup(True)
        if section in {'receipts', 'expenses'}:
            filters.addWidget(QLabel('From')); filters.addWidget(self.start); filters.addWidget(QLabel('To')); filters.addWidget(self.end)
        self.refresh_button = QPushButton('Search / Refresh'); self.refresh_button.clicked.connect(self.refresh); filters.addWidget(self.refresh_button)
        if section == 'restaurant': self.search.setVisible(False)
        body.addLayout(filters)
        self.view = table([label for key, label in COLUMNS[section]]); body.addWidget(self.view, 1)
        self.view.itemSelectionChanged.connect(self.enabled)
        self.actions = []; row = QHBoxLayout(); body.addLayout(row)
        def action(title, permission, callback, selected=True):
            button = QPushButton(title); button.clicked.connect(callback); row.addWidget(button)
            self.actions.append((button, permission, selected)); return button
        if section == 'customers':
            action('New customer', 'add_customer', lambda: self.customer(False), False)
            action('Edit customer', 'edit_customer', lambda: self.customer(True))
            action('Delete unused', 'delete_customer', lambda: self.confirm('customer.delete', 'Delete this unused customer?'))
            action('Credit / payments…', 'credit', self.credit)
        elif section == 'receipts':
            action('Receipt / Print…', 'receipts', self.receipt)
            action('Full refund…', 'refund_receipt', self.refund)
        elif section == 'expenses':
            action('New expense', 'add_expense', lambda: self.expense(False), False)
            action('Edit expense', 'edit_expense', lambda: self.expense(True))
            action('Delete expense', 'delete_expense', lambda: self.confirm('expense.delete', 'Delete this expense?'))
            action('Categories…', 'manage_expense_categories', self.categories, False)
            action('Budgets / comparison…', 'expense', self.budgets, False)
        else:
            action('New order', 'create_sale', lambda: self.order(False), False)
            action('Edit order', 'create_sale', lambda: self.order(True))
            action('Send kitchen', 'create_sale', lambda: self.confirm('restaurant.send', 'Send this saved order to the kitchen?'))
            action('Checkout…', 'create_sale', self.checkout)
            action('Cancel', 'create_sale', self.cancel_order)
            action('Reopen', 'create_sale', lambda: self.confirm('restaurant.reopen', 'Reopen this cancelled order?'))
            row = QHBoxLayout(); body.addLayout(row)
            action('Tables…', 'sales', self.tables, False)
            action('Kitchen…', 'sales', self.kitchen, False)
            action('Last settled receipt…', 'sales', self.last_settled_receipt, False)
        bottom = QHBoxLayout(); self.previous = QPushButton('Previous'); self.next = QPushButton('Next'); self.summary = QLabel()
        self.previous.clicked.connect(lambda: self.fetch(max(0, self.offset - 100))); self.next.clicked.connect(lambda: self.fetch(self.offset + 100))
        self.export_button = QPushButton('Export shown CSV…'); self.export_button.clicked.connect(self.export)
        self.recover_button = QPushButton('Recover pending change'); self.recover_button.clicked.connect(self.channel.recover)
        for widget in (self.previous, self.summary, self.next, self.export_button, self.recover_button): bottom.addWidget(widget)
        body.addLayout(bottom)
        if section == 'restaurant': self.previous.hide(); self.next.hide()
        self.channel.changed.connect(self.enabled); self.channel.saved.connect(self.saved); self.host.runner.idle.connect(self.enabled)
        self.enabled()

    def selected(self):
        index = self.view.currentRow()
        return self.records[index] if 0 <= index < len(self.records) else None

    def enabled(self):
        busy = self.host.runner.busy or self.channel.busy
        editable = self.ready and not busy and not self.channel.pending and not self.channel.error and self.host.session is not None
        for button, permission, selected in self.actions:
            button.setEnabled(bool(editable and self.host.session.can(permission) and (not selected or self.selected())))
        for widget in (self.search, self.start, self.end, self.refresh_button): widget.setEnabled(not busy)
        self.previous.setEnabled(not busy and self.offset > 0); self.next.setEnabled(not busy and len(self.records) == 100)
        self.export_button.setEnabled(not busy and bool(self.records))
        self.recover_button.setEnabled(not busy and bool(self.channel.pending) and not self.channel.error)
        self.status.setText('Recovery file needs attention: ' + self.channel.error if self.channel.error else
            'A business change is unresolved. Recover it before recording another payment, refund or order.' if self.channel.pending and not busy else
            self.channel.message or 'Ready')

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded: QTimer.singleShot(0, self.refresh)

    def refresh(self): self.fetch(0)

    def fetch(self, offset):
        if self.host.runner.busy or self.host.closing: return
        params = dict(section=self.section, query=self.search.text().strip(), offset=offset)
        if self.section in {'receipts', 'expenses'}: params.update(start=self.start.date().toString('yyyy-MM-dd'), end=self.end.date().toString('yyyy-MM-dd'))
        def done(data):
            if data.get('version') != 1: raise ValueError('Update and restart the POS Server for Phase 5')
            self.data = data; self.records = data['records']; self.offset = offset; self.ready = self.loaded = True
            fill(self.view, [[r.get(key, '') for key, label in COLUMNS[self.section]] for r in self.records])
            self.summary.setText(f"{len(self.records)} shown · offset {offset}" + (f" · Filtered total {float(data['total']):,.2f} ({data['count']} expenses)" if 'total' in data else ''))
            self.channel.message = self.notice or 'Loaded · ' + ('Latest 200 open / cancelled orders' if self.section == 'restaurant' else self.section.title())
            if self.records: self.view.selectRow(0)
        self.channel.run(lambda: self.api._request('GET', '/api/native/business', params=params), done, 'Loading ' + self.section + '…')

    def saved(self, result):
        self.loaded = False
        self.notice = result.get('message') or 'Saved'
        if self.isVisible(): QTimer.singleShot(0, self.refresh)
        if self.section == 'restaurant' and result.get('receipt'):
            self.last_receipt = result['receipt']
            try: self.receipt_journal.write(dict(payload={'request_id': result['request_id']}, result={'receipt': self.last_receipt}))
            except OSError as exc: self.notice += ' · Last receipt file could not be saved: ' + str(exc)
            self.last_settled_receipt()

    def last_settled_receipt(self):
        if self.last_receipt: ReceiptDialog(self.last_receipt, self, self.host.session.can('print_receipt')).exec()
        else: QMessageBox.information(self, 'Restaurant receipt', 'No settlement receipt saved for this account on this computer yet.')

    def edit_form(self, operation, title, fields, record=None):
        dialog = FormDialog(title, fields, record, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.channel.submit(operation, dialog.values())

    def confirm(self, operation, message, extra=None):
        record = self.selected()
        if not record: return
        if QMessageBox.question(self, 'Confirm', message) != QMessageBox.StandardButton.Yes: return
        self.channel.submit(operation, dict(id=record['id'], revision=record['revision'], **(extra or {})))

    def customer(self, editing): self.edit_form('customer.save', 'Customer', CUSTOMER_FORM, self.selected() if editing else None)

    def credit(self):
        row = self.selected()
        if not row: return
        def done(data):
            dialog = CreditDialog(data, self.host.session.can('payment_collection'), self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.payment: self.channel.submit('credit.pay', dialog.payment)
        self.channel.run(lambda: self.api._request('GET', '/api/native/business', params=dict(section='credit', record_id=row['id'])), done, 'Loading credit and payments…')

    def receipt(self):
        row = self.selected()
        if row: self.channel.run(lambda: self.api._request('GET', '/api/native/business', params=dict(section='receipts', record_id=row['id'])),
            lambda data: ReceiptDialog(data, self, self.host.session.can('print_receipt')).exec(), 'Loading receipt…')

    def refund(self):
        row = self.selected()
        if not row or row.get('status') == 'refunded': return
        reason, accepted = QInputDialog.getMultiLineText(self, 'Full receipt refund', 'Reason (all receipt items will be refunded)')
        if accepted and reason.strip(): self.confirm('receipt.refund', f"Record full refund for {row['invoice_no']}?\nThe server checks credit status and restores eligible stock.", {'reason': reason.strip()})

    def expense(self, editing):
        names = tuple(r['name'] for r in self.data.get('categories', []) if r.get('is_active'))
        if not names: QMessageBox.information(self, 'Expenses', 'Add an expense category first.'); return
        self.edit_form('expense.save', 'Expense', [('category', 'Category', names, names[0]), ('description', 'Description', 'text', ''),
            ('amount', 'Amount', 'money', 0), ('expense_date', 'Date', 'date', date.today().isoformat()),
            ('payment_method', 'Payment method', 'text', 'Cash'), ('reference_no', 'Reference', 'text', ''), ('notes', 'Notes', 'memo', '')], self.selected() if editing else None)

    def categories(self):
        records = [dict(name='[New category]'), *self.data.get('categories', [])]
        dialog = ChoiceDialog('Expense categories · select to edit / deactivate', records, [('name', 'Category'), ('description', 'Description'), ('is_active', 'Active')], self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected(): return
        row = dialog.selected()
        self.edit_form('expense.category', 'Expense category', [('name', 'Name', 'text', ''), ('description', 'Description', 'memo', ''), ('is_active', 'Active', 'bool', True)], row if row.get('id') else None)

    def budgets(self):
        records = self.data.get('comparison', [])
        dialog = ChoiceDialog('Monthly budget / comparison · ' + self.data.get('month', ''), records,
            [('category', 'Category'), ('budget', 'Budget'), ('actual', 'Actual'), ('previous', 'Previous month')], self)
        actions = QHBoxLayout(); dialog.layout().insertLayout(1, actions)
        edit = QPushButton('New / edit budget…'); edit.setEnabled(self.host.session.can('edit_expense')); actions.addWidget(edit)
        export = QPushButton('Export comparison CSV…'); actions.addWidget(export)
        export.clicked.connect(lambda: self.write_csv(records, ['category', 'budget', 'actual', 'previous']))
        def budget():
            names = tuple(r['name'] for r in self.data.get('categories', []) if r.get('is_active'))
            if not names: return
            selected = dialog.selected() or {}; current = next((r for r in self.data.get('budgets', []) if r['category'] == selected.get('category')), None)
            y, m = map(int, self.data['month'].split('-'))
            form = FormDialog('Monthly expense budget', [('category', 'Category', names, selected.get('category', names[0])),
                ('year', 'Year', 'int', y), ('month', 'Month', 'int', m), ('budget_amount', 'Budget amount', 'money', 0), ('notes', 'Notes', 'memo', '')], current, dialog)
            if form.exec() == QDialog.DialogCode.Accepted:
                dialog.reject(); self.channel.submit('expense.budget', form.values())
        edit.clicked.connect(budget); dialog.exec()

    def order(self, editing):
        row = self.selected() if editing else None
        if editing and not row: return
        def show(data):
            dialog = OrderDialog(self, data, self.data.get('tables', []))
            if dialog.exec() == QDialog.DialogCode.Accepted: self.channel.submit('restaurant.save', dialog.values())
        if row: self.channel.run(lambda: self.api._request('GET', '/api/native/business', params=dict(section='restaurant', record_id=row['id'])), show, 'Loading order…')
        else: show(None)

    def cancel_order(self):
        reason, accepted = QInputDialog.getMultiLineText(self, 'Cancel order', 'Cancellation reason')
        if accepted and reason.strip(): self.confirm('restaurant.cancel', 'Cancel this order and its kitchen tickets?', {'reason': reason.strip()})

    def checkout(self):
        row = self.selected()
        if not row: return
        def reviewed(data):
            quote, payment_types = data
            methods = [p for p in payment_types if p.lower() != 'credit']
            if not methods: methods = ['Cash']
            if self.host.session.can('credit_sale') and quote.get('customer_id'): methods.append('Credit')
            form = FormDialog(f"Settle {row['order_no']} · Total {quote['total']:,.2f}", [
                ('payment_type', 'Payment method', tuple(methods), methods[0]), ('payment', 'Amount received', 'money', quote['total']),
                ('due_date', 'Credit due date', 'date', date.today().isoformat())], parent=self)
            detail = QPlainTextEdit(); detail.setReadOnly(True); detail.setMaximumHeight(170)
            detail.setPlainText('\n'.join(f"{i['product_name']} · {i['qty']} × {i['price']:,.2f}" for i in quote['items']) +
                f"\nSubtotal {quote['subtotal']:,.2f}\nDiscount {quote['discount_amount']:,.2f}\nTax {quote['tax_amount']:,.2f}\nTOTAL {quote['total']:,.2f}")
            form.body.insertWidget(0, detail)
            if form.exec() != QDialog.DialogCode.Accepted: return
            values = form.values()
            if QMessageBox.question(self, 'Confirm settlement', f"Record payment and settle {row['order_no']} for {quote['total']:,.2f}?") != QMessageBox.StandardButton.Yes: return
            self.channel.submit('restaurant.checkout', dict(values, id=quote['id'], revision=quote['revision'], expected_total=quote['total']))
        self.channel.run(lambda: (self.api._request('GET', f"/api/native/business/restaurant/quote/{row['id']}"), self.api.payment_types()), reviewed, 'Checking current prices and stock…')

    def tables(self):
        records = [dict(table_no='[New table]')] if self.host.session.can('edit_settings') else []
        records += [dict(t, occupancy='Occupied' if t.get('occupied') else 'Available' if t.get('active') else 'Inactive') for t in self.data.get('tables', [])]
        dialog = ChoiceDialog('Restaurant tables', records, [('table_no', 'Table'), ('display_name', 'Name'), ('seats', 'Seats'), ('occupancy', 'Status')], self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected() or not self.host.session.can('edit_settings'): return
        row = dialog.selected()
        self.edit_form('restaurant.table', 'Restaurant table', [('table_no', 'Table number', 'text', ''), ('display_name', 'Display name', 'text', ''),
            ('seats', 'Seats', 'int', 4), ('active', 'Active', 'bool', True)], row if row.get('id') else None)

    def kitchen(self):
        records = self.data.get('tickets', [])
        dialog = ChoiceDialog('Kitchen · select a ticket to inspect / advance', records,
            [('ticket_no', 'Ticket'), ('source_name', 'Table / source'), ('order_no', 'Order'), ('status', 'Status'), ('created_at', 'Created')], self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected(): return
        row = dialog.selected()
        detail = KitchenDialog(row, self.host.session.can('create_sale'), self.host.session.can('print_receipt'), self)
        if detail.exec() == QDialog.DialogCode.Accepted and detail.next_status:
            self.channel.submit('restaurant.kitchen', dict(id=row['id'], revision=row['revision'], status=detail.next_status))

    def export(self): self.write_csv(self.records, [key for key, label in COLUMNS[self.section]])

    def write_csv(self, records, columns):
        path, _ = QFileDialog.getSaveFileName(self, 'Export shown rows', self.section + '.csv', 'CSV (*.csv)')
        if not path: return
        try:
            with Path(path).open('w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.writer(stream); writer.writerow(columns)
                writer.writerows([[safe_csv(r.get(k)) for k in columns] for r in records])
        except OSError as exc: QMessageBox.warning(self, 'Export', str(exc))
