"""Read-only Native analytics with receipt-level discounts and consistent snapshots."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import math

from server.native_catalog import CatalogRepository


VIEWS = {
    'dashboard': ('overview', 'daily', 'items'),
    'summary': ('overview', 'daily', 'hourly', 'items', 'wholesale', 'categories', 'parents', 'groups', 'payments', 'returns'),
    'reports': ('financial', 'monthly', 'invoices', 'expenses', 'credit', 'inventory', 'movements'),
}
PERMISSION = {'dashboard': 'dashboard', 'summary': 'sales_summary', 'reports': 'reports'}
MAX_ROWS = 20000
NOTES = [
    'Completed sales exclude refunded and deleted receipts. Refunds are shown separately using the original sale date; they are not subtracted twice.',
    'Net sales = item gross less the receipt discount, counted once. Invoice total can include tax or other adjustments.',
    'COGS uses recorded item cost, including zero cost. Missing cost uses current variant/product cost and is flagged as estimated. Categories reflect current assignments.',
    'Receipt counts can overlap across product/category groups. The last item receives any discount rounding remainder so group amounts reconcile.',
    'Item gross uses the actual sold unit price, so product promotions and wholesale pricing are already included.',
]


def clean(value):
    if isinstance(value, dict): return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [clean(item) for item in value]
    if isinstance(value, Decimal): value = float(value)
    if isinstance(value, float) and not math.isfinite(value): raise ValueError('A report amount is not finite; check source records')
    if isinstance(value, (date, datetime)): return value.isoformat()
    return value


def report_table(key, title, columns, rows):
    return dict(key=key, title=title, columns=[dict(key=k, label=label, kind=kind) for k, label, kind in columns], rows=rows)


SALES_COLUMNS = [('label', 'Name', 'text'), ('quantity', 'Quantity', 'number'), ('transactions', 'Receipts', 'integer'),
    ('gross', 'Item gross', 'money'), ('discount', 'Allocated discount', 'money'), ('net', 'Net sales', 'money'),
    ('cogs', 'COGS', 'money'), ('item_profit', 'Net less COGS', 'money'), ('estimated_lines', 'Estimated cost lines', 'integer')]
DAILY_COLUMNS = [('label', 'Date', 'text'), ('transactions', 'Receipts', 'integer'), ('gross', 'Item gross', 'money'),
    ('discount', 'Discount', 'money'), ('net', 'Net sales', 'money'), ('invoice_total', 'Invoice total', 'money'),
    ('cogs', 'COGS', 'money'), ('expenses', 'Expenses', 'money'), ('net_profit', 'Invoice profit', 'money'), ('refunds', 'Refund invoices', 'money')]


class ReportRepository(CatalogRepository):
    def limited(self, c, sql, args=()):
        rows = self.rows(c, sql + f' LIMIT {MAX_ROWS + 1}', args)
        if len(rows) > MAX_ROWS: raise ValueError(f'Report exceeds {MAX_ROWS:,} rows. Choose a shorter date range; no partial totals were returned.')
        return rows

    def can(self, c, user, permission):
        try: self.authorize(c, user, [permission]); return True
        except PermissionError: return False

    def cte(self, c):
        item_columns = self.columns(c, 'sale_items')
        item_cost = 'si.cost' if 'cost' in item_columns else 'NULL'
        variant = 'si.variant_id' if 'variant_id' in item_columns else 'NULL'
        wholesale = 'COALESCE(si.wholesale_savings,0)' if 'wholesale_savings' in item_columns else '0'
        tier = 'COALESCE(si.wholesale_tier_min_qty,0)' if 'wholesale_tier_min_qty' in item_columns else '0'
        group_join = 'LEFT JOIN category_groups cg ON cg.id=cat.group_id' if 'group_id' in self.columns(c, 'categories') and self.columns(c, 'category_groups') else ''
        group_name = "COALESCE(cg.name,'Ungrouped')" if group_join else "'Ungrouped'"
        return f'''WITH window_sales AS (
            SELECT * FROM sales WHERE created_at>=? AND created_at<? AND status IN ('completed','refunded')
        ), sale_gross AS (
            SELECT si.sale_id,SUM(COALESCE(si.qty,0)*COALESCE(si.price,0)) AS gross,COUNT(*) AS line_count
            FROM sale_items si JOIN window_sales s ON s.id=si.sale_id GROUP BY si.sale_id
        ), raw_lines AS (
            SELECT s.id AS sale_id,s.invoice_no,s.created_at,s.status,COALESCE(s.payment_type,'Other') AS payment_type,
                COALESCE(s.discount_amount,0) AS header_discount,si.id AS line_id,si.product_id,
                COALESCE(si.product_name,'[Receipt without items]') AS product_name,
                COALESCE(cat.name,p.category,'Uncategorized') AS category,
                COALESCE(parent.name,cat.name,p.category,'Uncategorized') AS parent_category,
                {group_name} AS category_group,
                COALESCE(si.qty,0) AS quantity,COALESCE(si.qty,0)*COALESCE(si.price,0) AS gross,
                COALESCE(si.qty,0)*COALESCE({item_cost},pv.cost,p.cost,0) AS cogs,
                CASE WHEN si.id IS NOT NULL AND {item_cost} IS NULL THEN 1 ELSE 0 END AS estimated_lines,
                {wholesale} AS wholesale_savings,{tier} AS wholesale_tier,
                CASE WHEN si.id IS NULL THEN COALESCE(s.discount_amount,0)
                     WHEN COALESCE(sg.gross,0)<>0 THEN COALESCE(s.discount_amount,0)*COALESCE(si.qty,0)*COALESCE(si.price,0)/sg.gross
                     ELSE COALESCE(s.discount_amount,0)*1.0/sg.line_count END AS raw_discount
            FROM window_sales s LEFT JOIN sale_items si ON si.sale_id=s.id
            LEFT JOIN sale_gross sg ON sg.sale_id=s.id
            LEFT JOIN products p ON p.id=COALESCE(si.product_id,(SELECT p2.id FROM products p2 WHERE p2.name=si.product_name ORDER BY p2.id DESC LIMIT 1))
            LEFT JOIN product_variants pv ON pv.id={variant} AND pv.product_id=p.id
            LEFT JOIN categories cat ON cat.id=COALESCE(p.category_id,(SELECT c2.id FROM categories c2 WHERE c2.name=p.category ORDER BY c2.id DESC LIMIT 1))
            LEFT JOIN categories parent ON parent.id=cat.parent_id {group_join}
        ), distributed AS (
            SELECT raw_lines.*,ROUND(CAST(raw_discount AS NUMERIC),2) AS rounded_discount,
                ROW_NUMBER() OVER (PARTITION BY sale_id ORDER BY line_id) AS position,
                COUNT(*) OVER (PARTITION BY sale_id) AS line_count FROM raw_lines
        ), lines AS (
            SELECT distributed.*,CASE WHEN position=line_count THEN header_discount-
                (SUM(rounded_discount) OVER (PARTITION BY sale_id)-rounded_discount)
                ELSE rounded_discount END AS discount FROM distributed
        ) '''

    def metrics(self, c, start, until, expenses=True):
        c.execute('''SELECT COUNT(*),COALESCE(SUM(total),0),COALESCE(SUM(discount_amount),0)
            FROM sales WHERE status='completed' AND created_at>=? AND created_at<?''', (start, until))
        transactions, invoice, discount = c.fetchone()
        c.execute(self.cte(c) + "SELECT COALESCE(SUM(gross),0),COALESCE(SUM(quantity),0),COALESCE(SUM(cogs),0),COALESCE(SUM(estimated_lines),0),SUM(CASE WHEN line_id IS NULL THEN 1 ELSE 0 END) FROM lines WHERE status='completed'", (start, until))
        gross, quantity, cogs, estimates, missing = c.fetchone()
        c.execute("SELECT COUNT(*),COALESCE(SUM(total),0) FROM sales WHERE status='refunded' AND created_at>=? AND created_at<?", (start, until))
        refund_count, refunds = c.fetchone()
        expense = 0
        if expenses:
            c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date>=? AND expense_date<?', (start, until)); expense = c.fetchone()[0]
        invoice, discount, gross, cogs, expense, refunds = map(float, (invoice, discount, gross, cogs, expense, refunds))
        result = dict(transactions=transactions, invoice_total=invoice, gross=gross, discount=discount, net=gross-discount,
            invoice_adjustments=invoice-(gross-discount), quantity=quantity, cogs=cogs, estimated_lines=estimates,
            missing_item_receipts=missing or 0, gross_profit=invoice-cogs, expenses=expense, net_profit=invoice-cogs-expense,
            refund_count=refund_count, refunds=refunds, average_invoice=invoice/transactions if transactions else 0,
            margin=(invoice-cogs-expense)/invoice*100 if invoice else 0)
        if not expenses:
            for key in ('expenses', 'net_profit', 'margin'): result.pop(key)
        return result

    def grouped(self, c, start, until, group, status='completed'):
        columns = {'items': 'product_name', 'categories': 'category', 'parents': 'parent_category', 'groups': 'category_group',
            'payments': 'payment_type', 'daily': 'SUBSTR(CAST(created_at AS TEXT),1,10)',
            'hourly': 'SUBSTR(CAST(created_at AS TEXT),12,2)', 'wholesale': 'product_name'}
        field = columns[group]
        where = " AND wholesale_savings>0" if group == 'wholesale' else ''
        sql = self.cte(c) + f'''SELECT {field} AS label,SUM(quantity) AS quantity,COUNT(DISTINCT sale_id) AS transactions,
            SUM(gross) AS gross,SUM(discount) AS discount,SUM(gross-discount) AS net,SUM(cogs) AS cogs,
            SUM(gross-discount-cogs) AS item_profit,SUM(estimated_lines) AS estimated_lines,
            SUM(wholesale_savings) AS wholesale_savings FROM lines WHERE status=?{where}
            GROUP BY {field} ORDER BY {'label' if group in {'daily','hourly'} else 'net DESC,label'}'''
        return self.limited(c, sql, (start, until, status))

    def daily(self, c, start, until, monthly=False, expenses=True):
        length = 7 if monthly else 10
        bucket = f'SUBSTR(CAST(created_at AS TEXT),1,{length})'
        headers = self.limited(c, f'''SELECT {bucket} AS label,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS transactions,
            SUM(CASE WHEN status='completed' THEN COALESCE(total,0) ELSE 0 END) AS invoice_total,
            SUM(CASE WHEN status='completed' THEN COALESCE(discount_amount,0) ELSE 0 END) AS discount,
            SUM(CASE WHEN status='refunded' THEN COALESCE(total,0) ELSE 0 END) AS refunds
            FROM sales WHERE status IN ('completed','refunded') AND created_at>=? AND created_at<?
            GROUP BY {bucket} ORDER BY label''', (start, until))
        result = {r['label']: dict(r, gross=0, cogs=0, expenses=0) for r in headers}
        rows = self.rows(c, self.cte(c) + f"SELECT {bucket} AS label,SUM(gross) AS gross,SUM(cogs) AS cogs FROM lines WHERE status='completed' GROUP BY {bucket}", (start, until))
        for row in rows: result[row['label']].update(gross=row['gross'], cogs=row['cogs'])
        if expenses:
            bucket = f'SUBSTR(CAST(expense_date AS TEXT),1,{length})'
            for row in self.rows(c, f'SELECT {bucket} AS label,SUM(amount) AS expenses FROM expenses WHERE expense_date>=? AND expense_date<? GROUP BY {bucket}', (start, until)):
                result.setdefault(row['label'], dict(label=row['label'], transactions=0, invoice_total=0, discount=0, refunds=0, gross=0, cogs=0))['expenses'] = row['expenses']
        for row in result.values():
            row['net'] = float(row['gross'])-float(row['discount'])
            row['net_profit'] = float(row['invoice_total'])-float(row['cogs'])-float(row.get('expenses') or 0)
        return [result[key] for key in sorted(result)]

    def inventory(self, c):
        rows = self.limited(c, '''SELECT p.id,p.name AS label,p.category,p.sold_by,p.stock AS master_stock,
            COALESCE(p.low_stock,0) AS low_stock,COALESCE(p.cost,0) AS unit_cost,
            CASE WHEN LOWER(COALESCE(p.sold_by,'')) IN ('variant','variants') THEN COALESCE(v.quantity,0)
                 WHEN l.product_id IS NOT NULL THEN l.quantity ELSE COALESCE(p.stock,0) END AS quantity,
            CASE WHEN LOWER(COALESCE(p.sold_by,'')) IN ('variant','variants') THEN COALESCE(v.value,0)
                 WHEN l.product_id IS NOT NULL THEN l.quantity*COALESCE(p.cost,0) ELSE COALESCE(p.stock,0)*COALESCE(p.cost,0) END AS value,
            COALESCE(l.quantity,0) AS location_stock
            FROM products p
            LEFT JOIN (SELECT product_id,SUM(quantity) AS quantity FROM product_locations GROUP BY product_id) l ON l.product_id=p.id
            LEFT JOIN (SELECT pv.product_id,SUM(COALESCE(pv.stock,0)) AS quantity,SUM(COALESCE(pv.stock,0)*COALESCE(pv.cost,p2.cost,0)) AS value
                FROM product_variants pv JOIN products p2 ON p2.id=pv.product_id GROUP BY pv.product_id) v ON v.product_id=p.id
            WHERE LOWER(COALESCE(p.sold_by,'')) NOT IN ('service','services','restaurant') ORDER BY p.name,p.id''')
        for row in rows:
            row['status'] = 'Out of stock' if row['quantity'] <= 0 else 'Low stock' if row['quantity'] <= row['low_stock'] else 'In stock'
            row['difference'] = row['quantity'] - (row['master_stock'] or 0)
        return rows

    def credit(self, c):
        return self.limited(c, '''SELECT c.name AS label,c.phone,COALESCE(c.current_balance,0) AS customer_balance,
            COALESCE(cs.balance,0) AS invoice_balance,COALESCE(c.credit_limit,0) AS credit_limit,
            CASE WHEN COALESCE(c.current_balance,0)>COALESCE(cs.balance,0) THEN COALESCE(c.current_balance,0)
                 ELSE COALESCE(cs.balance,0) END AS outstanding
            FROM customers c LEFT JOIN (SELECT customer_id,SUM(balance_amount) AS balance FROM credit_sales
                WHERE COALESCE(status,'')<>'refunded' AND balance_amount>0 GROUP BY customer_id) cs ON cs.customer_id=c.id
            WHERE COALESCE(c.current_balance,0)>0 OR COALESCE(cs.balance,0)>0 ORDER BY outstanding DESC,c.id''')

    def read(self, user, section, view, start, end):
        if section not in VIEWS or view not in VIEWS[section]: raise ValueError('Unknown report')
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last or (last-first).days > 3660: raise ValueError('Choose a valid date range of at most ten years')
        until = (last+timedelta(days=1)).isoformat()
        previous_end = first-timedelta(days=1); previous_start = previous_end-(last-first)
        conn = self.connect(); c = conn.cursor()
        try:
            if self.pg(): c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            else: c.execute('PRAGMA query_only=ON'); c.execute('BEGIN')
            required = [PERMISSION[section]]
            if view in {'inventory', 'movements'}: required.append('inventory')
            if view == 'credit': required.append('credit')
            self.authorize(c, user, required)
            c.execute("SELECT key,value FROM settings WHERE key IN ('currency_symbol','currency')")
            currency_settings = dict(c.fetchall())
            currency = currency_settings.get('currency_symbol') or currency_settings.get('currency') or 'Ks'
            result = dict(version=1, section=section, view=view, start=start, end=end, currency=currency,
                as_of=datetime.now().isoformat(timespec='seconds'), notes=list(NOTES), tables=[])
            tables = result['tables']
            financial = section != 'summary'
            daily_columns = DAILY_COLUMNS if financial else [col for col in DAILY_COLUMNS if col[0] not in {'expenses', 'net_profit'}]
            if view not in {'credit', 'inventory', 'movements'}:
                result['metrics'] = self.metrics(c, start, until, financial)
                missing = result['metrics']['missing_item_receipts']
                if missing: result['notes'].insert(0, f'{missing} completed receipts have no item rows. Item sales and COGS are incomplete for those receipts; review the source invoices.')
                if result['metrics']['estimated_lines']: result['notes'].append('Estimated cost lines use current cost where available; unavailable cost contributes zero. Review these lines before relying on profit totals.')
            if view in {'overview', 'financial'}:
                previous = self.metrics(c, previous_start.isoformat(), first.isoformat(), financial)
                result['previous_period'] = dict(start=previous_start.isoformat(), end=previous_end.isoformat())
                comparison = [dict(label=k.replace('_',' ').title(), current=result['metrics'][k], previous=previous[k],
                    change=float(result['metrics'][k])-float(previous[k]), percent=(float(result['metrics'][k])-float(previous[k]))/abs(float(previous[k]))*100 if previous[k] else None)
                    for k in ('gross', 'discount', 'net', 'invoice_total', 'transactions', 'cogs', 'refunds', *(['expenses', 'net_profit'] if financial else []))]
                tables.append(report_table('comparison', 'Previous period comparison', [('label','Metric','text'), ('current','Current','number'),
                    ('previous','Previous','number'), ('change','Change','number'), ('percent','Change %','percent')], comparison))
                tables.append(report_table('daily', 'Daily totals', daily_columns, self.daily(c, start, until, expenses=financial)))
                if section == 'dashboard':
                    snapshot = {}
                    if self.can(c, user, 'inventory'):
                        inventory = self.inventory(c); snapshot.update(stock_value=sum(float(r['value']) for r in inventory),
                            low_stock=sum(r['status']=='Low stock' for r in inventory), out_of_stock=sum(r['status']=='Out of stock' for r in inventory))
                    if self.can(c, user, 'credit'): snapshot['outstanding_credit'] = sum(float(r['outstanding']) for r in self.credit(c))
                    result['snapshot'] = snapshot
                    result['notes'].append('Stock and outstanding credit cards are current snapshots, independent of the selected dates.')
                    tables.append(report_table('top', 'Top 10 products by net sales', SALES_COLUMNS, self.grouped(c, start, until, 'items')[:10]))
            elif view in {'daily', 'monthly'}:
                tables.append(report_table(view, 'Monthly totals' if view=='monthly' else 'Daily totals', daily_columns,
                    self.daily(c, start, until, view=='monthly', financial)))
            elif view in {'items', 'wholesale', 'categories', 'parents', 'groups', 'payments', 'hourly', 'returns'}:
                group = 'items' if view == 'returns' else view
                if view == 'payments': result['notes'].append('Payment-type amounts are sales grouped by payment type, not cash collected. Credit collection transactions are available in Reports / Credit.')
                columns = list(SALES_COLUMNS)
                if view == 'wholesale':
                    columns.append(('wholesale_savings', 'Wholesale savings', 'money'))
                    result['notes'].append('Wholesale rows require savings recorded at sale time. Older receipts without this audit field cannot be reconstructed from current prices.')
                    if 'wholesale_savings' not in self.columns(c, 'sale_items'): result['notes'].append('Wholesale savings were not recorded in this database schema; this table is empty.')
                tables.append(report_table(view, view.title(), columns, self.grouped(c, start, until, group, 'refunded' if view=='returns' else 'completed')))
            elif view == 'invoices':
                rows = self.limited(c, '''SELECT s.id,s.invoice_no AS label,s.created_at,COALESCE(c.name,'Walk-in') AS customer,
                    s.status,s.payment_type,s.total,s.discount_amount,s.created_by FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
                    WHERE s.status IN ('completed','refunded') AND s.created_at>=? AND s.created_at<? ORDER BY s.created_at,s.id''', (start, until))
                tables.append(report_table(view, 'Sales invoices', [('label','Invoice','text'),('created_at','Date','text'),('customer','Customer','text'),
                    ('status','Status','text'),('payment_type','Payment type','text'),('total','Invoice total','money'),('discount_amount','Discount','money'),('created_by','Cashier','text')], rows))
            elif view == 'expenses':
                grouped = self.limited(c, 'SELECT category AS label,COUNT(*) AS transactions,SUM(amount) AS amount FROM expenses WHERE expense_date>=? AND expense_date<? GROUP BY category ORDER BY amount DESC,category', (start, until))
                tables.append(report_table('categories', 'Expense categories', [('label','Category','text'),('transactions','Entries','integer'),('amount','Amount','money')], grouped))
                rows = self.limited(c, 'SELECT expense_no AS label,expense_date,category,description,amount,payment_method,reference_no,created_by FROM expenses WHERE expense_date>=? AND expense_date<? ORDER BY expense_date,id', (start, until))
                tables.append(report_table('expenses', 'Expense entries', [('label','Expense','text'),('expense_date','Date','text'),('category','Category','text'),('description','Description','text'),('amount','Amount','money'),('payment_method','Method','text'),('reference_no','Reference','text'),('created_by','Created by','text')], rows))
            elif view == 'credit':
                rows = self.credit(c); result['snapshot'] = dict(outstanding_credit=sum(float(r['outstanding']) for r in rows))
                tables.append(report_table('outstanding', 'Current outstanding credit', [('label','Customer','text'),('phone','Phone','text'),('customer_balance','Customer balance','money'),
                    ('invoice_balance','Invoice balances','money'),('outstanding','Outstanding (greater balance)','money'),('credit_limit','Credit limit','money')], rows))
                payments = self.limited(c, '''SELECT cp.payment_date AS label,c.name AS customer,cs.invoice_no,cp.amount,cp.payment_method,cp.reference_no,cp.note
                    FROM credit_payments cp LEFT JOIN customers c ON c.id=cp.customer_id LEFT JOIN credit_sales cs ON cs.id=cp.credit_sale_id
                    WHERE cp.payment_date>=? AND cp.payment_date<? ORDER BY cp.payment_date,cp.id''', (start, until))
                tables.append(report_table('payments', 'Credit collections / refunds in selected dates', [('label','Date','text'),('customer','Customer','text'),('invoice_no','Invoice','text'),('amount','Amount','money'),('payment_method','Method','text'),('reference_no','Reference','text'),('note','Note','text')], payments))
                result['notes'].append('Outstanding is the current greater customer/invoice balance, matching the existing Dashboard safeguard. It is not a historical closing balance. Collection rows use payment dates; initial sale deposits remain on invoices.')
            elif view == 'inventory':
                rows = self.inventory(c); result['snapshot'] = dict(stock_value=sum(float(r['value']) for r in rows))
                tables.append(report_table(view, 'Current inventory valuation', [('label','Product','text'),('category','Category','text'),('sold_by','Mode','text'),
                    ('quantity','Available stock','number'),('master_stock','Product stock','number'),('difference','Stock difference','number'),('value','Cost value','money'),('status','Status','text')], rows))
                result['notes'].append('Inventory is current, not historical. Location balances take precedence for Each products; all variant balances are included for Variants. Service and Restaurant items are excluded. Stock differences need reconciliation.')
            else:
                rows = self.limited(c, '''SELECT sm.created_at AS label,p.name AS product,sm.type,sm.quantity,sm.old_stock,sm.new_stock,
                    sm.location,sm.reason,sm.reference,sm.created_by FROM stock_movements sm LEFT JOIN products p ON p.id=sm.product_id
                    WHERE sm.created_at>=? AND sm.created_at<? ORDER BY sm.created_at,sm.id''', (start, until))
                tables.append(report_table(view, 'Inventory movements', [('label','Date','text'),('product','Product','text'),('type','Type','text'),('quantity','Quantity','number'),
                    ('old_stock','Before','number'),('new_stock','After','number'),('location','Location','text'),('reason','Reason','text'),('reference','Reference','text'),('created_by','Actor','text')], rows))
            if financial: result['notes'].append('Invoice profit = completed invoice total − COGS − expenses. It includes invoice tax/adjustments, as in the existing financial reports; it is not a tax-exclusive accounting statement.')
            return clean(result)
        finally: conn.rollback(); conn.close()


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    repo = repository or ReportRepository()

    @app.get('/api/native/reports')
    def reports(section: str, view: str, start: str, end: str, user=Depends(current_user)):
        try: return repo.read(user, section, view, start, end)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, OverflowError) as exc: raise HTTPException(400, str(exc)) from exc
