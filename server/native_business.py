"""Recoverable Phase 5 operations on the existing POS tables.

Each command, its audit, and its recovery receipt share one database transaction.
The repository accepts dependencies so tests never initialize a production database.
"""
from datetime import date, datetime, timedelta
import json
from uuid import UUID, uuid4

from server.native_catalog import CatalogRepository, digest, number, flag


CUSTOMER_FIELDS = ('name', 'phone', 'email', 'address', 'remarks', 'credit_limit')
READ_PERMISSIONS = {'customers': ['customers'], 'credit': ['customers', 'credit'],
                    'receipts': ['receipts'], 'expenses': ['expense'], 'restaurant': ['sales']}


def day(value):
    return date.fromisoformat(str(value)).isoformat()


def money(value, minimum=0):
    amount = number(value, minimum=minimum)
    if abs(amount - round(amount, 2)) > .0000001: raise ValueError('Use at most two decimal places for money')
    return round(amount, 2)


class BusinessRepository(CatalogRepository):
    def __init__(self, service=None, restaurant=None):
        super().__init__(service)
        self._restaurant = restaurant

    @property
    def restaurant_service(self):
        if self._restaurant is None:
            from utils import restaurant_service
            self._restaurant = restaurant_service
        return self._restaurant

    def record(self, c, table, record_id):
        rows = self.rows(c, f'SELECT * FROM {table} WHERE id=?', (int(record_id),))
        if not rows: raise ValueError('Record no longer exists. Refresh the page.')
        row = rows[0]; row['revision'] = digest(row)
        return row

    def required(self, operation, v):
        mapping = {
            'customer.save': ['customers', 'edit_customer' if v.get('id') else 'add_customer'],
            'customer.delete': ['customers', 'delete_customer'],
            'credit.pay': ['customers', 'credit', 'payment_collection'],
            'receipt.refund': ['receipts', 'refund_receipt'],
            'expense.save': ['expense', 'edit_expense' if v.get('id') else 'add_expense'],
            'expense.delete': ['expense', 'delete_expense'],
            'expense.category': ['expense', 'manage_expense_categories'],
            'expense.budget': ['expense', 'edit_expense'],
            'restaurant.table': ['sales', 'edit_settings'],
            'restaurant.save': ['sales', 'create_sale'],
            'restaurant.send': ['sales', 'create_sale'],
            'restaurant.kitchen': ['sales', 'create_sale'],
            'restaurant.cancel': ['sales', 'create_sale'],
            'restaurant.reopen': ['sales', 'create_sale'],
            'restaurant.checkout': ['sales', 'create_sale'],
        }
        if operation not in mapping: raise ValueError('Unsupported business operation')
        return mapping[operation]

    def command(self, user, request_id, operation, values):
        UUID(request_id)
        fingerprint = digest([operation, values]); required = self.required(operation, values)
        conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, required)
            c.execute('''CREATE TABLE IF NOT EXISTS native_business_requests (
                request_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, operation TEXT NOT NULL,
                payload_hash TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)''')
            if operation.startswith('restaurant.'): self.restaurant_service.ensure_restaurant_schema(c)
            conn.commit()
            if not self.pg(): c.execute('BEGIN IMMEDIATE')
            c.execute('''INSERT INTO native_business_requests (request_id,user_id,operation,payload_hash,created_at)
                VALUES (?,?,?,?,?) ON CONFLICT (request_id) DO NOTHING''',
                      (request_id, user['id'], operation, fingerprint, datetime.now().isoformat()))
            c.execute('SELECT user_id,payload_hash,result_json FROM native_business_requests WHERE request_id=?', (request_id,))
            owner, prior, saved = c.fetchone()
            if owner != user['id'] or prior != fingerprint: raise ValueError('Request ID belongs to another change')
            if saved: conn.rollback(); return json.loads(saved)
            # Native and legacy writers use these same tables. Serialize multi-table
            # balance/refund edits, including absent-row checks and table occupancy.
            if self.pg():
                tables = ('products, product_variants, product_locations, customers, sales, sale_items, credit_sales, credit_payments'
                          if operation.startswith(('credit.', 'receipt.', 'restaurant.')) else
                          'customers, sales, credit_sales' if operation.startswith('customer.') else
                          'expenses, expense_categories, expense_budgets')
                c.execute(f'LOCK TABLE {tables} IN SHARE ROW EXCLUSIVE MODE')
                if operation.startswith('restaurant.'):
                    c.execute('LOCK TABLE restaurant_tables, restaurant_orders, restaurant_kitchen_tickets IN SHARE ROW EXCLUSIVE MODE')
            self.authorize(c, user, required)
            if operation.startswith('customer.'): result = self.customer(c, operation, values)
            elif operation == 'credit.pay': result = self.pay(c, values, user, request_id)
            elif operation == 'receipt.refund': result = self.refund(c, values, user, request_id)
            elif operation.startswith('expense.'): result = self.expense(c, operation, values, user)
            else: result = self.restaurant(conn, c, operation, values, user)
            result = dict(result, request_id=request_id, operation=operation)
            c.execute('UPDATE native_business_requests SET result_json=? WHERE request_id=?',
                      (json.dumps(result, default=str), request_id))
            conn.commit(); return result
        except Exception:
            conn.rollback(); raise
        finally: conn.close()

    def read(self, user, section, record_id=0, query='', start='', end='', offset=0):
        if section not in READ_PERMISSIONS: raise ValueError('Unknown business page')
        offset = number(offset, True, maximum=10000000)
        conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, READ_PERMISSIONS[section])
            if section == 'restaurant':
                self.restaurant_service.ensure_restaurant_schema(c); conn.commit()
                if record_id:
                    row = self.record(c, 'restaurant_orders', record_id)
                    row['cart'] = json.loads(row['cart_json']); return row
                tables = self.rows(c, 'SELECT * FROM restaurant_tables ORDER BY sort_order,table_no')
                occupied = {r['table_id'] for r in self.rows(c, "SELECT DISTINCT table_id FROM restaurant_orders WHERE status='open' AND table_id IS NOT NULL")}
                for row in tables:
                    row['revision'] = digest(row); row['occupied'] = row['id'] in occupied
                orders = self.rows(c, "SELECT * FROM restaurant_orders WHERE status IN ('open','cancelled') ORDER BY CASE WHEN status='open' THEN 0 ELSE 1 END,id DESC LIMIT 200")
                table_names = {t['id']: t.get('display_name') or t['table_no'] for t in tables}
                for row in orders:
                    row['revision'] = digest(row); row['table_name'] = table_names.get(row['table_id'], 'Takeaway')
                tickets = self.rows(c, "SELECT * FROM restaurant_kitchen_tickets WHERE status IN ('sent','preparing','ready') ORDER BY id LIMIT 200")
                for row in tickets:
                    row['revision'] = digest(row)
                    order = self.record(c, 'restaurant_orders', row['order_id'])
                    row['order_no'] = order['order_no']; row['source_name'] = table_names.get(order['table_id'], 'Takeaway')
                    row['items'] = self.restaurant_service._load_ticket_items(c, row['id'])
                return dict(version=1, records=orders, tables=tables, tickets=tickets)
            if section == 'customers':
                if record_id: return self.record(c, 'customers', record_id)
                rows = self.rows(c, '''SELECT * FROM customers WHERE LOWER(name) LIKE ? OR COALESCE(phone,'') LIKE ?
                    ORDER BY name,id LIMIT 100 OFFSET ?''', ('%' + query.lower() + '%', '%' + query + '%', offset))
                for row in rows: row['revision'] = digest(row)
                return dict(version=1, records=rows)
            if section == 'credit':
                customer = self.record(c, 'customers', record_id)
                rows = self.rows(c, 'SELECT * FROM credit_sales WHERE customer_id=? ORDER BY id DESC', (record_id,))
                for row in rows: row['revision'] = digest(row)
                payments = self.rows(c, 'SELECT * FROM credit_payments WHERE customer_id=? ORDER BY id DESC LIMIT 500', (record_id,))
                return dict(customer=customer, records=rows, payments=payments)
            if section == 'receipts' and record_id:
                receipt = self.service._get_receipt_from_cursor(c, record_id)
                receipt['revision'] = self.record(c, 'sales', record_id)['revision']
                credits = self.rows(c, 'SELECT * FROM credit_sales WHERE sale_id=?', (record_id,))
                if credits: receipt.update({k: credits[0].get(k) for k in ('paid_amount', 'balance_amount', 'due_date')})
                return receipt
            table = 'sales' if section == 'receipts' else 'expenses'
            field = 'created_at' if section == 'receipts' else 'expense_date'
            where = []; args = []
            if section == 'receipts': where.append("COALESCE(status,'completed')<>'deleted'")
            if start: where.append(f'{field}>=?'); args.append(day(start))
            if end: where.append(f'{field}<?'); args.append((date.fromisoformat(day(end)) + timedelta(days=1)).isoformat())
            if start and end and start > end: raise ValueError('Start date must be before end date')
            search_fields = ('invoice_no', 'payment_type') if section == 'receipts' else ('category', 'description', 'reference_no')
            where.append('(' + ' OR '.join(f"LOWER(COALESCE({f},'')) LIKE ?" for f in search_fields) + ')')
            args.extend(['%' + query.lower() + '%'] * len(search_fields))
            if section == 'receipts':
                where[-1] = '(' + where[-1] + ' OR customer_id IN (SELECT id FROM customers WHERE LOWER(name) LIKE ?))'
                args.append('%' + query.lower() + '%')
            clause = ' AND '.join(where)
            rows = self.rows(c, f'SELECT * FROM {table} WHERE {clause} ORDER BY id DESC LIMIT 100 OFFSET ?', (*args, offset))
            for row in rows: row['revision'] = digest(row)
            result = dict(version=1, records=rows)
            if section == 'expenses':
                c.execute(f'SELECT COALESCE(SUM(amount),0),COUNT(*) FROM expenses WHERE {clause}', args)
                result['total'], result['count'] = c.fetchone()
                result['categories'] = self.rows(c, 'SELECT * FROM expense_categories ORDER BY name')
                for row in result['categories']: row['revision'] = digest(row)
                month = date.fromisoformat(day(start)) if start else date.today()
                first = month.replace(day=1); next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
                previous = (first - timedelta(days=1)).replace(day=1)
                budgets = self.rows(c, 'SELECT * FROM expense_budgets WHERE year=? AND month=? ORDER BY category', (month.year, month.month))
                for row in budgets: row['revision'] = digest(row)
                result['budgets'] = budgets
                current = {r['category']: r['actual'] for r in self.rows(c, 'SELECT category,SUM(amount) AS actual FROM expenses WHERE expense_date>=? AND expense_date<? GROUP BY category', (first.isoformat(), next_month.isoformat()))}
                prior = {r['category']: r['actual'] for r in self.rows(c, 'SELECT category,SUM(amount) AS actual FROM expenses WHERE expense_date>=? AND expense_date<? GROUP BY category', (previous.isoformat(), first.isoformat()))}
                result['comparison'] = [dict(category=k, actual=current.get(k, 0), previous=prior.get(k, 0),
                    budget=next((r['budget_amount'] for r in budgets if r['category'] == k), 0)) for k in sorted(set(current) | set(prior) | {r['category'] for r in budgets})]
                result['month'] = first.isoformat()[:7]
            return result
        finally: conn.close()

    def customer(self, c, operation, v):
        old = self.record(c, 'customers', v['id']) if v.get('id') else None
        if old: self.check_revision(old, v)
        if operation == 'customer.delete':
            if not old: raise ValueError('Choose a customer')
            for table in ('sales', 'credit_sales', 'credit_payments', 'customer_points_log', 'credit_adjustments', 'restaurant_orders'):
                if 'customer_id' in self.columns(c, table):
                    c.execute(f'SELECT id FROM {table} WHERE customer_id=? LIMIT 1', (old['id'],))
                    if c.fetchone(): raise ValueError('Customer has transaction history and cannot be deleted')
            if any(float(old.get(k) or 0) for k in ('current_balance', 'credit_balance', 'points', 'total_spent', 'total_visit')):
                raise ValueError('Customer has balances or history')
            c.execute('DELETE FROM customers WHERE id=?', (old['id'],)); return {'message': 'Unused customer deleted'}
        data = {k: str(v.get(k) or '').strip() for k in CUSTOMER_FIELDS if k != 'credit_limit'}
        if not data['name']: raise ValueError('Customer name is required')
        data['credit_limit'] = number(v.get('credit_limit'))
        if old: self.update(c, 'customers', old['id'], data); record_id = old['id']
        else: record_id = self.insert(c, 'customers', dict(data, current_balance=0, credit_balance=0, total_credit=0, points=0, total_visit=0, total_spent=0))
        return dict(message='Customer saved', customer_id=record_id)

    def pay(self, c, v, user, request_id):
        credit = self.record(c, 'credit_sales', v['id']); self.check_revision(credit, v)
        if credit['status'] == 'refunded': raise ValueError('Sale has been refunded')
        amount = money(v.get('amount'), minimum=0.01); balance = float(credit['balance_amount'])
        if amount > balance: raise ValueError('Payment exceeds the outstanding balance')
        customer = self.record(c, 'customers', credit['customer_id'])
        if float(customer.get('current_balance') or 0) + .005 < amount:
            raise ValueError('Customer balance is inconsistent. Reconcile it before collecting payment.')
        paid = round(float(credit['paid_amount']) + amount, 2); remaining = round(balance - amount, 2)
        self.update(c, 'credit_sales', credit['id'], dict(paid_amount=paid, balance_amount=remaining, status='paid' if remaining == 0 else 'partial'))
        self.update(c, 'customers', customer['id'], {'current_balance': round(float(customer['current_balance']) - amount, 2)})
        payment_id = self.insert(c, 'credit_payments', dict(credit_sale_id=credit['id'], customer_id=customer['id'], amount=amount,
            payment_date=day(v.get('payment_date') or date.today()), payment_method=str(v.get('payment_method') or 'Cash'),
            reference_no=str(v.get('reference_no') or ''), note=f"{v.get('note') or ''} [Native: {request_id}; {user['username']}]") )
        return dict(message=f'Payment collected; remaining {remaining:,.2f}', payment_id=payment_id, balance=remaining)

    def refund(self, c, v, user, request_id):
        sale = self.record(c, 'sales', v['id']); self.check_revision(sale, v)
        if str(sale.get('status')).lower() != 'completed': raise ValueError('Receipt already refunded or not completed')
        reason = str(v.get('reason') or '').strip()
        if not reason: raise ValueError('Refund reason is required')
        credits = self.rows(c, 'SELECT * FROM credit_sales WHERE sale_id=?', (sale['id'],))
        if not credits and str(sale.get('payment_type')).lower() == 'credit':
            credits = self.rows(c, 'SELECT * FROM credit_sales WHERE invoice_no=? AND customer_id=?', (sale['invoice_no'], sale['customer_id']))
        if len(credits) > 1: raise ValueError('Duplicate credit records need reconciliation')
        credit = credits[0] if credits else None
        if str(sale.get('payment_type')).lower() == 'credit' and not credit: raise ValueError('Credit record is missing; reconcile before refund')
        if credit and (credit['status'] == 'refunded' or (float(credit['paid_amount']) > 0 and float(credit['balance_amount']) > .005)):
            raise ValueError('A partially paid or refunded credit receipt cannot be refunded. Follow the existing POS credit workflow.')
        items = self.rows(c, 'SELECT * FROM sale_items WHERE sale_id=? ORDER BY product_id,id', (sale['id'],))
        if not items: raise ValueError('Receipt items are missing')
        for item in items:
            product = self.record(c, 'products', item['product_id'])
            if self.service._sold_by_mode(product.get('sold_by')) in {'service', 'restaurant'}: continue
            qty = number(item['qty'], True, minimum=1); before = int(product.get('stock') or 0)
            if item.get('variant_id'):
                variant = self.record(c, 'product_variants', item['variant_id'])
                if variant['product_id'] != product['id']: raise ValueError('Variant does not match the receipt')
                self.update(c, 'product_variants', variant['id'], dict(stock=int(variant['stock'] or 0) + qty, updated_at=datetime.now().isoformat()))
            else:
                self.add_location(c, product['id'], str(item.get('location') or 'Shop'), qty, item.get('batch_no'), item.get('expire_date'))
            self.update(c, 'products', product['id'], dict(stock=before + qty, last_updated=datetime.now().isoformat()))
            self.insert(c, 'stock_movements', dict(product_id=product['id'], variant_id=item.get('variant_id'), type='refund', quantity=qty,
                old_stock=before, new_stock=before + qty, reason=reason, reference=sale['invoice_no'], created_by=user['username'],
                location=item.get('location') or 'Shop', notes=f'Native full refund {request_id}'))
        if credit:
            customer = self.record(c, 'customers', credit['customer_id']); balance = float(credit['balance_amount'])
            if float(customer.get('current_balance') or 0) + .005 < balance: raise ValueError('Customer credit balance needs reconciliation')
            self.update(c, 'customers', customer['id'], dict(current_balance=round(float(customer.get('current_balance') or 0) - balance, 2),
                credit_balance=max(0, float(customer.get('credit_balance') or 0) - balance)))
            self.update(c, 'credit_sales', credit['id'], dict(status='refunded', balance_amount=0, notes=f"{credit.get('notes') or ''}\nRefund: {reason}"))
            if float(credit['paid_amount']) > 0:
                self.insert(c, 'credit_payments', dict(credit_sale_id=credit['id'], customer_id=customer['id'], amount=-float(credit['paid_amount']),
                    payment_date=date.today().isoformat(), payment_method='refund', reference_no=sale['invoice_no'], note=f"{reason} [Native: {request_id}; {user['username']}]") )
            self.insert(c, 'credit_adjustments', dict(customer_id=customer['id'], credit_sale_id=credit['id'], amount=-float(credit['total_amount']),
                adjustment_type='refund', reason=reason, reference_no=sale['invoice_no'], created_by=user['username']))
        if sale.get('customer_id'):
            # Preserve the original receipt refund loyalty/statistics rule.
            c.execute("SELECT value FROM settings WHERE key='loyalty_points_per_dollar'")
            setting = c.fetchone(); earned = int(float(sale['total']) * float(setting[0] or 0)) if setting else 0
            customer = self.record(c, 'customers', sale['customer_id'])
            self.update(c, 'customers', customer['id'], dict(total_visit=max(0, int(customer.get('total_visit') or 0) - 1),
                total_spent=max(0, float(customer.get('total_spent') or 0) - float(sale['total'])), points=max(0, int(customer.get('points') or 0) - earned)))
        self.update(c, 'sales', sale['id'], {'status': 'refunded'})
        cash_return = float(credit['paid_amount']) if credit else float(sale['total'])
        return dict(message=f'Full refund recorded · return {cash_return:,.2f} to customer', sale_id=sale['id'], cash_return=cash_return,
                    reason=reason, actor=user['username'])

    def expense(self, c, operation, v, user):
        table = {'expense.category': 'expense_categories', 'expense.budget': 'expense_budgets'}.get(operation, 'expenses')
        old = self.record(c, table, v['id']) if v.get('id') else None
        if old: self.check_revision(old, v)
        if operation == 'expense.delete':
            if not old: raise ValueError('Choose an expense')
            c.execute('DELETE FROM expenses WHERE id=?', (old['id'],)); return dict(message='Expense deleted (audit retained in Native request log)', deleted=old, actor=user['username'])
        if operation == 'expense.category':
            name = str(v.get('name') or '').strip()
            if not name: raise ValueError('Category name is required')
            c.execute('SELECT id FROM expense_categories WHERE LOWER(name)=LOWER(?) AND id<>?', (name, v.get('id') or 0))
            if c.fetchone(): raise ValueError('Category already exists')
            data = dict(name=name, description=str(v.get('description') or ''), is_active=flag(v.get('is_active', True)))
            if old and name != old['name']:
                c.execute('SELECT id FROM expense_budgets WHERE category=? LIMIT 1', (name,))
                if c.fetchone(): raise ValueError('Target category has budgets')
                c.execute('UPDATE expenses SET category=? WHERE category=?', (name, old['name']))
                c.execute('UPDATE expense_budgets SET category=? WHERE category=?', (name, old['name']))
        else:
            category = str(v.get('category') or '').strip()
            c.execute('SELECT id FROM expense_categories WHERE name=? AND is_active=1', (category,))
            if not c.fetchone(): raise ValueError('Select an active expense category')
            if operation == 'expense.budget':
                year = number(v.get('year'), True, minimum=2000, maximum=2200); month = number(v.get('month'), True, minimum=1, maximum=12)
                c.execute('SELECT id FROM expense_budgets WHERE category=? AND year=? AND month=? AND id<>?', (category, year, month, v.get('id') or 0))
                if c.fetchone(): raise ValueError('Budget exists. Refresh and edit it.')
                data = dict(category=category, year=year, month=month, budget_amount=number(v.get('budget_amount')), notes=str(v.get('notes') or ''), updated_at=datetime.now().isoformat())
            else:
                data = {k: str(v.get(k) or '') for k in ('description', 'payment_method', 'reference_no', 'notes')}
                data.update(category=category, amount=money(v.get('amount'), minimum=.01), expense_date=day(v['expense_date']))
                if not old: data.update(expense_no='EXP' + datetime.now().strftime('%Y%m%d%H%M%S%f'), created_by=user['username'])
        if old: self.update(c, table, old['id'], data); record_id = old['id']
        else: record_id = self.insert(c, table, data)
        return dict(message='Saved', id=record_id)

    def priced_cart(self, conn, c, cart):
        if not isinstance(cart, list) or not 1 <= len(cart) <= 100: raise ValueError('An order needs 1–100 lines')
        from utils.restaurant_modifiers import normalize_modifiers
        items = []; adjustments = []; result = []; line_ids = set()
        for line in cart:
            product = self.record(c, 'products', line.get('product_id') or line.get('id'))
            qty = number(line.get('qty'), True, minimum=1, maximum=100000)
            chosen = normalize_modifiers(line.get('restaurant_modifiers') or [])
            available = normalize_modifiers(product.get('restaurant_modifiers') or [])
            modifiers = []; choices = set(); seen = set()
            for selected in chosen:
                match = next((m for m in available if m['name'] == selected['name'] and m['group'] == selected['group']), None)
                if not match: raise ValueError('Modifier is no longer available. Edit the order.')
                key = (match['group'], match['name'])
                if key in seen or (match['type'] == 'choice' and match['group'] in choices): raise ValueError('Choose only one option per modifier group')
                seen.add(key)
                if match['type'] == 'choice': choices.add(match['group'])
                modifiers.append(match)
            variant_id = int(line.get('variant_id') or 0) or None
            if self.service._sold_by_mode(product['sold_by']) == 'variants' and not variant_id: raise ValueError('Choose a variant')
            variant_label = ''
            if variant_id:
                variant = self.record(c, 'product_variants', variant_id)
                variant_label = ' / '.join(str(variant.get(k) or '') for k in ('color', 'size')).strip(' /')
            manual = (line.get('manual_price') if line.get('manual_price') is not None else line.get('price')) if self.service._sold_by_mode(product['sold_by']) == 'service' else None
            items.append(dict(product_id=product['id'], qty=qty, variant_id=variant_id, manual_price=manual))
            adjustments.append(sum(float(m['price_delta']) for m in modifiers))
            line_id = str(line.get('restaurant_line_id') or uuid4().hex)
            if line_id in line_ids: raise ValueError('Duplicate order line')
            line_ids.add(line_id)
            note = str(line.get('note') or line.get('kitchen_note') or '')
            names = [m['name'] for m in modifiers]
            mode = self.service._sold_by_mode(product['sold_by'])
            result.append(dict(id=product['id'], base_name=product['name'], name=product['name'] + (f' ({variant_label})' if variant_label else '') + (f" ({', '.join(names)})" if names else ''), qty=qty, variant_id=variant_id, variant_label=variant_label,
                manual_price=manual, restaurant_modifiers=modifiers, restaurant_line_id=line_id, note=note, kitchen_note=note,
                is_service=mode in {'service', 'restaurant'}, is_restaurant=mode == 'restaurant', modifier_key='|'.join(sorted(names)), location=None))
        quote = self.service.create_sale(items=items, payment=0, preview_only=True, _connection=conn, _price_adjustments=adjustments,
                                         _item_labels=[r['name'] for r in result])
        # Quote allocations may split a line across batches. Reprice each line for
        # display; final checkout always quotes the complete cart again.
        for row, item, adjustment in zip(result, items, adjustments):
            priced = self.service.create_sale(items=[item], payment=0, preview_only=True, _connection=conn, _price_adjustments=[adjustment])
            row['price'] = priced['items'][0]['price']; row['original_price'] = row['price'] - adjustment
        return result, items, adjustments, quote

    def quote_order(self, user, record_id):
        conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, ['sales', 'create_sale'])
            order = self.record(c, 'restaurant_orders', record_id)
            if order['status'] != 'open': raise ValueError('Only open orders can be settled')
            cart, items, adjustments, quote = self.priced_cart(conn, c, json.loads(order['cart_json']))
            return dict(quote, revision=order['revision'], id=order['id'], customer_id=order.get('customer_id'))
        finally: conn.rollback(); conn.close()

    def menu_product(self, user, product_id):
        conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, ['sales'])
            product = self.record(c, 'products', product_id)
            product.pop('image_data', None)
            product['variants'] = self.rows(c, 'SELECT * FROM product_variants WHERE product_id=? AND active=1 ORDER BY id', (product_id,))
            return product
        finally: conn.close()

    def restaurant(self, conn, c, operation, v, user):
        rs = self.restaurant_service
        if operation == 'restaurant.table':
            old = self.record(c, 'restaurant_tables', v['id']) if v.get('id') else None
            if old: self.check_revision(old, v)
            name = str(v.get('table_no') or '').strip()
            if not name: raise ValueError('Table number is required')
            c.execute('SELECT id FROM restaurant_tables WHERE table_no=? AND id<>?', (name, v.get('id') or 0))
            if c.fetchone(): raise ValueError('Table number already exists')
            active = flag(v.get('active', True))
            if old and not active:
                c.execute("SELECT id FROM restaurant_orders WHERE table_id=? AND status='open'", (old['id'],))
                if c.fetchone(): raise ValueError('Table has an open order')
            data = dict(table_no=name, display_name=str(v.get('display_name') or name), seats=number(v.get('seats', 4), True, minimum=1, maximum=100), active=active)
            if old: self.update(c, 'restaurant_tables', old['id'], data)
            else: self.insert(c, 'restaurant_tables', data)
            return {'message': 'Table saved'}
        if operation == 'restaurant.kitchen':
            ticket = self.record(c, 'restaurant_kitchen_tickets', v['id']); self.check_revision(ticket, v)
            status = v.get('status')
            if status not in {'preparing', 'ready', 'served'}: raise ValueError('Invalid kitchen status')
            allowed = {'sent': 'preparing', 'preparing': 'ready', 'ready': 'served'}
            if allowed.get(ticket['status']) != status: raise ValueError('Kitchen status changed; refresh first')
            self.update(c, 'restaurant_kitchen_tickets', ticket['id'], dict(status=status, updated_at=datetime.now().isoformat(),
                **({'completed_at': datetime.now().isoformat()} if status == 'served' else {})))
            timestamp = rs._kitchen_item_timestamp_assignments(status)
            c.execute(f"UPDATE restaurant_kitchen_ticket_items SET status=?,updated_at=CURRENT_TIMESTAMP{timestamp} WHERE ticket_id=? AND status<>'cancelled'", (status, ticket['id']))
            rs._sync_order_item_kitchen_statuses(c, ticket['id']); rs._sync_order_kitchen_status(c, ticket['order_id'])
            return {'message': 'Kitchen status updated'}
        old = self.record(c, 'restaurant_orders', v['id']) if v.get('id') else None
        if old: self.check_revision(old, v)
        if operation not in {'restaurant.save', 'restaurant.reopen'} and (not old or old['status'] != 'open'):
            raise ValueError('Select an open order')
        if operation == 'restaurant.save':
            if old and old['status'] != 'open': raise ValueError('Only open orders can be edited')
            table_id = int(v.get('table_id') or 0) or None
            self.available_table(c, table_id, old['id'] if old else 0)
            cart, items, adjustments, quote = self.priced_cart(conn, c, v.get('cart'))
            if old and old.get('kitchen_status') != 'draft':
                by_line = {line['restaurant_line_id']: line for line in cart}
                for prior_line in json.loads(old['cart_json']):
                    new_line = by_line.get(prior_line.get('restaurant_line_id'))
                    def identity(line):
                        return [line.get('id'), line.get('variant_id'), line.get('note') or line.get('kitchen_note') or '',
                                sorted((m.get('group'), m.get('name')) for m in line.get('restaurant_modifiers') or [])]
                    if not new_line or new_line['qty'] < prior_line['qty'] or identity(new_line) != identity(prior_line):
                        raise ValueError('Sent items cannot be removed or replaced here. Add items or increase quantity; cancel the whole order to replace it.')
            customer_id = int(v.get('customer_id') or 0) or None
            customer = self.record(c, 'customers', customer_id) if customer_id else {}
            data = dict(table_id=table_id, order_type='Dine-in' if table_id else 'Takeaway', cart_json=json.dumps(cart, ensure_ascii=False),
                customer_id=customer_id, customer_name=customer.get('name') or '', note=str(v.get('note') or ''), total_amount=quote['total'],
                item_count=sum(i['qty'] for i in cart), updated_at=datetime.now().isoformat())
            if old: self.update(c, 'restaurant_orders', old['id'], data); record_id = old['id']
            else:
                data.update(order_no='RO' + datetime.now().strftime('%Y%m%d%H%M%S%f'), status='open', kitchen_status='draft')
                record_id = self.insert(c, 'restaurant_orders', data)
            rs._sync_order_items(c, record_id, cart)
            return dict(message='Order saved', id=record_id)
        if operation == 'restaurant.reopen':
            if not old or old['status'] != 'cancelled' or old.get('sale_id'): raise ValueError('Only cancelled, unsettled orders can reopen')
            self.available_table(c, old.get('table_id'), old['id'])
            self.update(c, 'restaurant_orders', old['id'], dict(status='open', kitchen_status='draft', cancelled_at=None, updated_at=datetime.now().isoformat()))
            return {'message': 'Order reopened; review before sending to kitchen'}
        if operation == 'restaurant.cancel':
            reason = str(v.get('reason') or '').strip()
            if not reason: raise ValueError('Cancellation reason required')
            self.update(c, 'restaurant_orders', old['id'], dict(status='cancelled', kitchen_status='cancelled', cancelled_at=datetime.now().isoformat(),
                note=f"{old.get('note') or ''}\nCancelled by {user['username']}: {reason}", updated_at=datetime.now().isoformat()))
            c.execute("UPDATE restaurant_kitchen_tickets SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE order_id=?", (old['id'],))
            c.execute("UPDATE restaurant_kitchen_ticket_items SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE ticket_id IN (SELECT id FROM restaurant_kitchen_tickets WHERE order_id=?)", (old['id'],))
            return {'message': 'Order cancelled; kitchen tickets cancelled'}
        if operation == 'restaurant.send':
            ticket_id = rs._create_kitchen_ticket(c, old['id'])
            if ticket_id:
                rs._sync_order_item_kitchen_statuses(c, ticket_id)
                self.update(c, 'restaurant_orders', old['id'], dict(kitchen_status='sent', sent_to_kitchen_at=datetime.now().isoformat(), updated_at=datetime.now().isoformat()))
            return dict(message='Kitchen ticket saved' if ticket_id else 'No new items to send', ticket_id=ticket_id)
        if operation == 'restaurant.checkout':
            cart, items, adjustments, quote = self.priced_cart(conn, c, json.loads(old['cart_json']))
            if v.get('payment_type') == 'Credit': self.authorize(c, user, ['credit_sale'])
            receipt = self.service.create_sale(items=items, payment=number(v.get('payment')), payment_type=str(v.get('payment_type') or 'Cash'),
                customer_id=old.get('customer_id'), due_date=str(v.get('due_date') or ''), credit_notes=str(old.get('note') or ''),
                created_by=user['username'], expected_total=money(v['expected_total']), _connection=conn, _price_adjustments=adjustments,
                _item_labels=[r['name'] for r in cart])
            self.update(c, 'restaurant_orders', old['id'], dict(status='settled', settled_at=datetime.now().isoformat(), sale_id=receipt['id'],
                invoice_no=receipt['invoice_no'], settled_total=receipt['total'], total_amount=receipt['total'], payment_amount=receipt['payment'],
                change_amount=receipt['change_amount'], payment_type=receipt['payment_type'], updated_at=datetime.now().isoformat()))
            return dict(message='Order settled', receipt=receipt)
        raise ValueError('Unsupported restaurant action')

    def available_table(self, c, table_id, order_id):
        if not table_id: return
        table = self.record(c, 'restaurant_tables', table_id)
        if not table.get('active'): raise ValueError('Table is inactive')
        c.execute("SELECT id FROM restaurant_orders WHERE table_id=? AND status='open' AND id<>?", (table_id, order_id))
        if c.fetchone(): raise ValueError('Table already has an open order')


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException, Query
    from pydantic import BaseModel, Field
    repo = repository or BusinessRepository()
    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str = Field(max_length=40)
        values: dict

    @app.get('/api/native/business')
    def business(section: str, record_id: int = 0, query: str = '', start: str = '', end: str = '', offset: int = Query(default=0, ge=0), user=Depends(current_user)):
        try: return repo.read(user, section, record_id, query, start, end, offset)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: raise HTTPException(400, str(exc)) from exc

    @app.get('/api/native/business/restaurant/quote/{order_id}')
    def quote(order_id: int, user=Depends(current_user)):
        try: return repo.quote_order(user, order_id)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: raise HTTPException(400, str(exc)) from exc

    @app.get('/api/native/business/restaurant/product/{product_id}')
    def product(product_id: int, user=Depends(current_user)):
        try: return repo.menu_product(user, product_id)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: raise HTTPException(400, str(exc)) from exc

    @app.post('/api/native/business/commands')
    def command(payload: Command, user=Depends(current_user)):
        try: return {'result': repo.command(user, payload.request_id, payload.operation, payload.values)}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: return {'rejected': str(exc)}
