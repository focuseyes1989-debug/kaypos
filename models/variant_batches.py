"""Variant-specific batch ledger. All writes belong to the caller's transaction.

Legacy product_locations rows cannot be assigned to a variant reliably. They are
left untouched; unallocated variant balances become explicitly unknown openings.
"""
from datetime import datetime
from uuid import uuid4


def ensure_schema(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS variant_stock_batches (
        product_id INTEGER NOT NULL, variant_id INTEGER NOT NULL,
        location TEXT NOT NULL, batch_no TEXT NOT NULL, expire_date TEXT NOT NULL DEFAULT '',
        quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
        expiry_unknown INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(product_id, variant_id, location, batch_no, expire_date),
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY(variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
    )""")
    cursor.execute('''CREATE TABLE IF NOT EXISTS variant_batch_changes (
        movement_id INTEGER NOT NULL, product_id INTEGER NOT NULL, variant_id INTEGER NOT NULL,
        location TEXT NOT NULL, batch_no TEXT NOT NULL, expire_date TEXT NOT NULL,
        delta INTEGER NOT NULL, expiry_unknown INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(movement_id) REFERENCES stock_movements(id) ON DELETE CASCADE
    )''')


def receive(cursor, product_id, variant_id, quantity, location, batch_no='', expire_date='', unknown=False):
    ensure_schema(cursor)
    if quantity < 0:
        raise ValueError('Received batch quantity cannot be negative')
    if expire_date:
        if datetime.strptime(expire_date, '%Y-%m-%d').strftime('%Y-%m-%d') != expire_date:
            raise ValueError('Invalid expiry date')
    batch_no = batch_no or ('BATCH-' + uuid4().hex)
    cursor.execute("""INSERT INTO variant_stock_batches
        (product_id,variant_id,location,batch_no,expire_date,quantity,expiry_unknown)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(product_id,variant_id,location,batch_no,expire_date)
        DO UPDATE SET quantity=variant_stock_batches.quantity+excluded.quantity""",
        (product_id,variant_id,location or 'Variant',batch_no,expire_date or '',quantity,int(unknown)))
    return batch_no


def reconcile(cursor, product_id, variant_id, stock):
    """Materialize only a missing legacy opening; never guess historical dates."""
    ensure_schema(cursor)
    cursor.execute('SELECT COALESCE(SUM(quantity),0) FROM variant_stock_batches WHERE product_id=? AND variant_id=?', (product_id,variant_id))
    tracked = int(cursor.fetchone()[0])
    if tracked > stock:
        raise ValueError('Variant batch stock differs from total stock. Review legacy stock changes before continuing.')
    if tracked < stock:
        receive(cursor, product_id, variant_id, stock-tracked, 'Legacy / unassigned', 'LEGACY-OPENING', '', True)


def allocate(cursor, product_id, variant_id, stock, quantity, location=None, preview=False):
    reconcile(cursor,product_id,variant_id,stock)
    params=[product_id,variant_id]
    condition=''
    if location:
        condition=' AND location=?';params.append(location)
    cursor.execute('''SELECT location,batch_no,expire_date,quantity,expiry_unknown
        FROM variant_stock_batches WHERE product_id=? AND variant_id=? AND quantity>0'''+condition+'''
        ORDER BY CASE WHEN expire_date='' THEN 1 ELSE 0 END,expire_date,batch_no,location''',params)
    rows=cursor.fetchall()
    if sum(int(row[3]) for row in rows)<quantity:
        raise ValueError('Insufficient variant batch stock in the selected location')
    allocations=[];remaining=quantity
    for place,batch,expiry,available,unknown in rows:
        if not remaining:break
        take=min(remaining,int(available));remaining-=take
        if not preview:
            cursor.execute('''UPDATE variant_stock_batches SET quantity=quantity-?
                WHERE product_id=? AND variant_id=? AND location=? AND batch_no=? AND expire_date=?''',
                (take,product_id,variant_id,place,batch,expiry))
        allocations.append(dict(qty=take,variant_id=variant_id,location_id=None,
                                location=place,batch_no=batch,expire_date=expiry,expiry_unknown=unknown))
    return allocations


def restore(cursor, product_id, variant_id, stock, quantity, location='', batch_no='', expire_date=''):
    reconcile(cursor,product_id,variant_id,stock)
    receive(cursor,product_id,variant_id,quantity,location or 'Legacy / unassigned',
            batch_no or 'LEGACY-RETURN',expire_date or '',not bool(batch_no))


def list_batches(cursor, product_id):
    ensure_schema(cursor)
    cursor.execute('''SELECT variant_id,location,batch_no,expire_date,quantity,expiry_unknown
        FROM variant_stock_batches WHERE product_id=? AND quantity>0
        ORDER BY variant_id,CASE WHEN expire_date='' THEN 1 ELSE 0 END,expire_date,batch_no''',(product_id,))
    return [dict(zip(['variant_id','location','batch_no','expire_date','quantity','expiry_unknown'],row)) for row in cursor.fetchall()]


def record_change(cursor,movement_id,product_id,variant_id,changes):
    ensure_schema(cursor)
    for change in changes:
        cursor.execute('INSERT INTO variant_batch_changes VALUES(?,?,?,?,?,?,?,?)',
            (movement_id,product_id,variant_id,change['location'],change['batch_no'],change.get('expire_date') or '',change['delta'],int(change.get('expiry_unknown') or 0)))


def reverse_change(cursor,movement_id,product_id,variant_id):
    ensure_schema(cursor)
    cursor.execute('SELECT location,batch_no,expire_date,delta,expiry_unknown FROM variant_batch_changes WHERE movement_id=? AND product_id=? AND variant_id=?',(movement_id,product_id,variant_id))
    changes=cursor.fetchall()
    if not changes:
        cursor.execute('SELECT COUNT(*) FROM variant_stock_batches WHERE product_id=? AND variant_id=?',(product_id,variant_id))
        if cursor.fetchone()[0]:
            raise ValueError('This legacy movement has no variant batch allocation. Use a reviewed stock adjustment instead.')
        return False
    for place,batch,expiry,delta,unknown in changes:
        if delta>0:
            cursor.execute('SELECT quantity FROM variant_stock_batches WHERE product_id=? AND variant_id=? AND location=? AND batch_no=? AND expire_date=?',(product_id,variant_id,place,batch,expiry))
            row=cursor.fetchone()
            if not row or row[0]<delta:raise ValueError('The original variant batch has insufficient stock to reverse this movement')
    for place,batch,expiry,delta,unknown in changes:
        if delta>0:
            cursor.execute('UPDATE variant_stock_batches SET quantity=quantity-? WHERE product_id=? AND variant_id=? AND location=? AND batch_no=? AND expire_date=?',(delta,product_id,variant_id,place,batch,expiry))
        else:
            receive(cursor,product_id,variant_id,-delta,place,batch,expiry,unknown)
    return True

