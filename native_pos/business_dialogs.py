"""Stock Qt forms for customers, payments, expenses and restaurant orders."""
from copy import deepcopy
import json
from uuid import uuid4

from PyQt6 import sip
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget,
    QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QCheckBox, QPushButton, QLabel,
    QMessageBox, QDialogButtonBox, QTabWidget, QScrollArea, QInputDialog, QTextBrowser)
from native_pos.catalog_dialogs import Editor, numeric
from native_pos.sales import table, fill
from utils.restaurant_modifiers import normalize_modifiers


class FormDialog(Editor):
    """Small typed forms; IDs/revisions stay outside editable controls."""
    def __init__(self, title, fields, record=None, parent=None):
        super().__init__(title, parent); self.record = deepcopy(record or {}); self.fields = {}; self.kinds = {}
        self.resize(640, 500)
        contents = QWidget(); form = QFormLayout(contents); self.form = form
        for key, label, kind, default in fields:
            value = self.record.get(key, default)
            if kind == 'money' or kind == 'int': widget = numeric(value or 0, kind == 'int')
            elif kind == 'date':
                widget = QDateEdit(); widget.setCalendarPopup(True); widget.setDisplayFormat('yyyy-MM-dd')
                parsed = QDate.fromString(str(value or '')[:10], 'yyyy-MM-dd'); widget.setDate(parsed if parsed.isValid() else QDate.currentDate())
            elif kind == 'bool': widget = QCheckBox(); widget.setChecked(bool(value))
            elif isinstance(kind, (tuple, list)):
                widget = QComboBox(); widget.addItems(list(kind)); widget.setCurrentText(str(value or ''))
            elif kind == 'memo': widget = QPlainTextEdit(str(value or '')); widget.setMaximumHeight(90)
            else: widget = QLineEdit(str(value or ''))
            self.fields[key] = widget; self.kinds[key] = kind; form.addRow(label, widget)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(contents); self.body.addWidget(scroll, 1)
        self.finish()

    def values(self):
        result = {k: self.record[k] for k in ('id', 'revision') if k in self.record}
        for key, widget in self.fields.items():
            kind = self.kinds[key]
            if kind in ('money', 'int'): value = widget.value()
            elif kind == 'date': value = widget.date().toString('yyyy-MM-dd')
            elif kind == 'bool': value = widget.isChecked()
            elif isinstance(kind, (tuple, list)): value = widget.currentText()
            elif kind == 'memo': value = widget.toPlainText().strip()
            else: value = widget.text().strip()
            result[key] = value
        return result


CUSTOMER_FORM = [(k, label, 'memo' if k in {'remarks', 'address'} else 'money' if k == 'credit_limit' else 'text', '')
    for k, label in [('name', 'Name'), ('phone', 'Phone'), ('email', 'Email'), ('address', 'Address'),
                     ('remarks', 'Remarks'), ('credit_limit', 'Credit limit (0 = unlimited)')]]


class CreditDialog(QDialog):
    def __init__(self, data, can_collect, parent=None):
        super().__init__(parent); self.setWindowTitle('Customer credit / payment history'); self.resize(930, 570)
        self.data = data; self.payment = None
        body = QVBoxLayout(self); customer = data['customer']
        title = QLabel(f"{customer['name']} · Balance {float(customer.get('current_balance') or 0):,.2f} · Credit limit {float(customer.get('credit_limit') or 0):,.2f}")
        title.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(title)
        tabs = QTabWidget(); body.addWidget(tabs, 1)
        self.credits = table(['Invoice', 'Date', 'Total', 'Paid', 'Balance', 'Due', 'Status'])
        fill(self.credits, [[r.get(k, '') for k in ('invoice_no', 'sale_date', 'total_amount', 'paid_amount', 'balance_amount', 'due_date', 'status')] for r in data['records']])
        tabs.addTab(self.credits, 'Credit sales')
        payments = table(['Date', 'Invoice', 'Amount', 'Method', 'Reference', 'Note / actor'])
        invoices = {r['id']: r.get('invoice_no') for r in data['records']}
        fill(payments, [[r.get('payment_date', ''), invoices.get(r['credit_sale_id'], ''), *[r.get(k, '') for k in ('amount', 'payment_method', 'reference_no', 'note')]] for r in data['payments']])
        tabs.addTab(payments, 'Payments (latest 500)')
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject)
        collect = buttons.addButton('Collect payment…', QDialogButtonBox.ButtonRole.ActionRole); collect.clicked.connect(self.collect)
        collect.setEnabled(can_collect); body.addWidget(buttons)

    def collect(self):
        index = self.credits.currentRow()
        if not 0 <= index < len(self.data['records']): return
        credit = self.data['records'][index]
        if credit['status'] == 'refunded' or float(credit['balance_amount']) <= 0: return
        dialog = FormDialog(f"Collect · {credit['invoice_no']} · Due {float(credit['balance_amount']):,.2f}", [
            ('amount', 'Amount received', 'money', credit['balance_amount']), ('payment_date', 'Payment date', 'date', ''),
            ('payment_method', 'Payment method', 'text', 'Cash'), ('reference_no', 'Reference', 'text', ''), ('note', 'Note', 'memo', '')], parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        values = dialog.values()
        if not 0 < values['amount'] <= float(credit['balance_amount']):
            QMessageBox.warning(self, 'Payment', 'Enter an amount above zero and at most the remaining balance.'); return
        if QMessageBox.question(self, 'Confirm payment', f"Record {values['amount']:,.2f} received for {credit['invoice_no']}?") != QMessageBox.StandardButton.Yes: return
        self.payment = dict(values, id=credit['id'], revision=credit['revision']); self.accept()


class ChoiceDialog(QDialog):
    def __init__(self, title, records, columns, parent=None):
        super().__init__(parent); self.resize(900, 500); self.setWindowTitle(title); self.records = records
        body = QVBoxLayout(self); self.view = table([label for key, label in columns]); body.addWidget(self.view)
        fill(self.view, [[r.get(key, '') for key, label in columns] for r in records])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); body.addWidget(buttons)
        self.view.doubleClicked.connect(self.accept)
        if records: self.view.selectRow(0)

    def selected(self):
        row = self.view.currentRow()
        return self.records[row] if 0 <= row < len(self.records) else None


class KitchenDialog(QDialog):
    def __init__(self, ticket, can_update, can_print, parent=None):
        super().__init__(parent); self.resize(650, 540); self.setWindowTitle('Kitchen ticket'); self.next_status = None
        body = QVBoxLayout(self); self.document = QTextBrowser(); body.addWidget(self.document, 1)
        lines = ['KITCHEN TICKET', str(ticket['ticket_no']), f"Order: {ticket.get('order_no', '')}",
            f"Source: {ticket.get('source_name', '')}", f"Status: {ticket['status']}", '']
        for item in ticket.get('items', []):
            lines += [f"{item.get('quantity')} × {item.get('product_name')}", str(item.get('modifier_summary') or ''), str(item.get('note') or ''), '']
        self.document.setPlainText('\n'.join(lines))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); body.addWidget(buttons)
        self.print_button = buttons.addButton('Print / PDF…', QDialogButtonBox.ButtonRole.ActionRole)
        self.print_button.setEnabled(can_print); self.print_button.clicked.connect(self.print_ticket)
        status = {'sent': 'preparing', 'preparing': 'ready', 'ready': 'served'}.get(ticket['status'])
        if can_update and status:
            advance = buttons.addButton('Mark ' + status, QDialogButtonBox.ButtonRole.ActionRole)
            def change():
                if QMessageBox.question(self, 'Kitchen status', f'Mark this ticket as {status}?') == QMessageBox.StandardButton.Yes:
                    self.next_status = status; self.accept()
            advance.clicked.connect(change)

    def print_ticket(self):
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.document.document().print(printer)


class MenuLineDialog(FormDialog):
    def __init__(self, product, parent=None):
        self.product = product
        super().__init__(product['name'], [('qty', 'Quantity', 'int', 1), ('note', 'Kitchen note', 'memo', '')], parent=parent)
        self.variant = QComboBox(); self.variant.addItem('Choose variant', None)
        for v in product.get('variants', []): self.variant.addItem(f"{v.get('color') or ''} {v.get('size') or ''} · {v.get('price') or product.get('price')}", v['id'])
        if str(product.get('sold_by')).lower() == 'variants': self.form.addRow('Variant', self.variant)
        else: self.variant.hide()
        self.manual = numeric(product.get('price') or 0)
        if str(product.get('sold_by')).lower() == 'service': self.form.addRow('Service unit price', self.manual)
        else: self.manual.hide()
        self.modifiers = []
        for modifier in normalize_modifiers(product.get('restaurant_modifiers')):
            check = QCheckBox(f"{modifier['group']}: {modifier['name']} ({modifier['price_delta']:+,.2f})")
            self.form.addRow(check); self.modifiers.append((check, modifier))

    def values(self):
        value = super().values()
        if value['qty'] < 1: raise ValueError('Quantity must be positive')
        mode = str(self.product.get('sold_by')).lower()
        if mode == 'variants' and not self.variant.currentData(): raise ValueError('Choose a variant')
        chosen = [m for check, m in self.modifiers if check.isChecked()]
        groups = [m['group'] for m in chosen if m['type'] == 'choice']
        if len(set(groups)) != len(groups): raise ValueError('Select one choice per group')
        return dict(value, id=self.product['id'], name=self.product['name'], variant_id=self.variant.currentData() if mode == 'variants' else None,
            variant_label=self.variant.currentText().split(' · ')[0] if mode == 'variants' else '',
            manual_price=self.manual.value() if mode == 'service' else None, restaurant_modifiers=chosen, restaurant_line_id=uuid4().hex)


class OrderDialog(Editor):
    def __init__(self, page, record, tables):
        super().__init__('Restaurant order · Save before kitchen / checkout', page); self.resize(1000, 590)
        self.page = page; self.record = deepcopy(record or {}); self.cart = deepcopy(self.record.get('cart') or json.loads(self.record.get('cart_json') or '[]'))
        top = QHBoxLayout(); self.table_choice = QComboBox(); self.table_choice.addItem('Takeaway', None)
        for t in tables:
            if t.get('active'): self.table_choice.addItem(str(t.get('display_name') or t['table_no']), t['id'])
        self.table_choice.setCurrentIndex(max(0, self.table_choice.findData(self.record.get('table_id'))))
        top.addWidget(self.table_choice); self.customer = QComboBox(); self.customer.addItem('No customer', None)
        if self.record.get('customer_id'):
            self.customer.addItem(self.record.get('customer_name') or str(self.record['customer_id']), self.record['customer_id']); self.customer.setCurrentIndex(1)
        top.addWidget(self.customer); self.customer_search = QLineEdit(); self.customer_search.setPlaceholderText('Find customer')
        top.addWidget(self.customer_search); find_customer = QPushButton('Find'); find_customer.clicked.connect(self.find_customer); top.addWidget(find_customer)
        self.body.addLayout(top)
        search = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText('Search menu / product name or code')
        self.search.returnPressed.connect(self.find_products); search.addWidget(self.search)
        button = QPushButton('Find / add product…'); button.clicked.connect(self.find_products); search.addWidget(button); self.body.addLayout(search)
        self.lines = table(['Product', 'Qty', 'Variant', 'Modifiers', 'Note']); self.body.addWidget(self.lines, 1)
        remove = QPushButton('Remove selected line'); remove.clicked.connect(self.remove); self.body.addWidget(remove)
        quantity = QPushButton('Change selected quantity…'); quantity.clicked.connect(self.quantity); self.body.addWidget(quantity)
        self.note = QLineEdit(str(self.record.get('note') or '')); self.note.setPlaceholderText('Order note'); self.body.addWidget(self.note)
        self.finish(); self.render()

    def render(self):
        fill(self.lines, [(r.get('name') or r.get('base_name') or r.get('id'), r['qty'], r.get('variant_label') or r.get('variant_id') or '',
            ', '.join(m['name'] for m in normalize_modifiers(r.get('restaurant_modifiers'))), r.get('note') or '') for r in self.cart])

    def remove(self):
        index = self.lines.currentRow()
        if 0 <= index < len(self.cart): self.cart.pop(index); self.render()

    def quantity(self):
        index = self.lines.currentRow()
        if not 0 <= index < len(self.cart): return
        quantity, accepted = QInputDialog.getInt(self, 'Order quantity', 'Quantity', int(self.cart[index]['qty']), 1, 100000)
        if accepted: self.cart[index]['qty'] = quantity; self.render()

    def find_customer(self):
        query = self.customer_search.text()
        def done(records):
            if sip.isdeleted(self) or not self.isVisible(): return
            self.customer.clear(); self.customer.addItem('No customer', None)
            for row in records: self.customer.addItem(row['name'], row['id'])
        self.page.channel.run(lambda: self.page.api.customers(query, 100), done, 'Finding customers…')

    def find_products(self):
        query = self.search.text()
        def found(records):
            if sip.isdeleted(self) or not self.isVisible(): return
            dialog = ChoiceDialog('Products · first 100 results; refine your search', records, [('name', 'Product'), ('sold_by', 'Mode'), ('price', 'Price')], self)
            if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected(): return
            product_id = dialog.selected()['id']
            def detail(product):
                if sip.isdeleted(self) or not self.isVisible(): return
                editor = MenuLineDialog(product, self)
                if editor.exec() == QDialog.DialogCode.Accepted: self.cart.append(editor.values()); self.render()
            self.page.channel.run(lambda: self.page.api._request('GET', f'/api/native/business/restaurant/product/{product_id}'), detail, 'Loading menu options…')
        self.page.channel.run(lambda: self.page.api.products(query, 100, 0, ''), found, 'Finding menu products…')

    def values(self):
        if not self.cart: raise ValueError('Add at least one item')
        return dict({k: self.record[k] for k in ('id', 'revision') if k in self.record}, cart=deepcopy(self.cart),
                    table_id=self.table_choice.currentData(), customer_id=self.customer.currentData(), note=self.note.text().strip())
