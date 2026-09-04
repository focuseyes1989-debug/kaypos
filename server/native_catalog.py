"""Transactional Native catalog/inventory commands over the existing POS schema.

No desktop UI imports. Dependencies are injectable for isolated database tests.
"""
import base64
from datetime import date, datetime
import hashlib
import io
import json
import math
import re
from uuid import UUID


PRODUCT_FIELDS = ('name', 'category', 'description', 'sold_by', 'price', 'cost', 'sku',
                  'barcode', 'low_stock', 'unit', 'base_unit', 'pack_unit', 'pack_size')
VARIANT_FIELDS = ('color', 'size', 'sku', 'barcode', 'price', 'cost', 'low_stock', 'active')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def number(value, integer=False, minimum=0, maximum=999999999999):
    result = float(value or 0)
    if not math.isfinite(result) or not minimum <= result <= maximum or (integer and result != int(result)):
        raise ValueError('Invalid quantity or amount')
    return int(result) if integer else result


def flag(value):
    if value not in (True, False, 0, 1): raise ValueError('Active must be true or false')
    return int(bool(value))


class CatalogRepository:
    def __init__(self, service=None):
        if service is None:
            from server import cashier_service as service
        self.service = service
        self.connect = service.connect_db
        self.pg = service.is_postgres_backend

    def rows(self, cursor, sql, args=()):
        cursor.execute(sql, args)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def columns(self, cursor, table):
        return self.service._table_columns(cursor, table)

    def insert(self, cursor, table, values):
        return self.service._execute_dynamic_insert(cursor, table, values)

    def update(self, cursor, table, record_id, values):
        values = {k: v for k, v in values.items() if k in self.columns(cursor, table)}
        if not values: raise ValueError('Server schema needs an update')
        cursor.execute(f'UPDATE {table} SET ' + ', '.join(f'{key}=?' for key in values) + ' WHERE id=?',
                       (*values.values(), record_id))
        if cursor.rowcount != 1: raise ValueError('Record no longer exists')

    def authorize(self, cursor, user, permissions):
        cursor.execute('''SELECT u.role,u.permissions,r.permissions,u.is_active,u.force_password_change
            FROM users u LEFT JOIN user_roles r ON r.name=u.role WHERE u.id=?''', (user['id'],))
        row = cursor.fetchone()
        if not row or not row[3] or row[4]: raise PermissionError('Account inactive or password change required')
        granted = {p.strip() for value in row[1:3] for p in str(value or '').split(',') if p.strip()}
        if str(row[0]).lower() != 'admin' and not set(permissions).issubset(granted):
            raise PermissionError('Required permissions: ' + ', '.join(permissions))

    def detail(self, cursor, product_id):
        columns = sorted(set(self.columns(cursor, 'products')) - {'image_data'})
        rows = self.rows(cursor, f'SELECT {", ".join(columns)} FROM products WHERE id=?', (product_id,))
        if not rows: raise ValueError('Product no longer exists')
        product = rows[0]
        for key, table in [('variants', 'product_variants'), ('locations', 'product_locations'),
                           ('discounts', 'product_discounts'), ('tiers', 'product_price_tiers')]:
            product[key] = self.rows(cursor, f'SELECT * FROM {table} WHERE product_id=? ORDER BY id', (product_id,)) if self.columns(cursor, table) else []
        metadata = {k: product.get(k) for k in PRODUCT_FIELDS}
        metadata['variants'] = [{k: row.get(k) for k in ('id', *VARIANT_FIELDS)} for row in product['variants']]
        metadata['image_filename'] = product.get('image_filename')
        metadata['restaurant_modifiers'] = product.get('restaurant_modifiers')
        product['revision'] = digest(metadata)
        product['stock_revision'] = digest([product.get('stock'), product.get('cost'), product['variants'], product['locations']])
        product['pricing_revision'] = digest([product['discounts'], product['tiers'], product['locations']])
        return product

    def read(self, user, section, product_id=None):
        conn = self.connect()
        try:
            c = conn.cursor(); self.authorize(c, user, ['inventory' if section in {'inventory', 'history'} else 'products'])
            if section == 'history' and product_id:
                rows = self.rows(c, 'SELECT * FROM stock_movements WHERE product_id=? ORDER BY id DESC LIMIT 200', (product_id,))
                for row in rows:
                    matches = re.findall(r'\[Native request: ([0-9a-f-]{36})\]', str(row.get('notes') or ''))
                    row['native_request_id'] = matches[-1] if matches else ''
                return {'movements': rows}
            if product_id: return self.detail(c, product_id)
            categories = self.rows(c, 'SELECT * FROM categories ORDER BY name')
            for row in categories: row['revision'] = digest(row)
            return {'version': 1, 'categories': categories}
        finally: conn.close()

    def command(self, user, request_id, operation, values):
        UUID(request_id)
        for key in ('rows', 'variants', 'discounts', 'tiers'):
            if key in values and (not isinstance(values[key], list) or any(not isinstance(row, dict) for row in values[key])):
                raise ValueError(key + ' must be a list of records')
        required = {
            'product.save': ['products', 'edit_product' if values.get('id') else 'add_product'],
            'product.delete': ['products', 'delete_product'],
            'products.import': ['products', *(['edit_product'] if any(r.get('id') for r in values.get('rows', [])) else []),
                                *(['add_product'] if any(not r.get('id') for r in values.get('rows', [])) else [])],
            'category.save': ['products', 'edit_product'], 'category.delete': ['products', 'delete_product'],
            'pricing.save': ['products', 'edit_product'],
            'stock.in': ['inventory', 'stock_in'], 'stock.out': ['inventory', 'stock_out'],
            'stock.set': ['inventory', 'adjustment'], 'stock.transfer': ['inventory', 'stock_in', 'stock_out'],
            'stock.reverse': ['inventory', 'adjustment'],
        }.get(operation)
        if not required: raise ValueError('Unsupported catalog operation')
        fingerprint = digest([operation, values])
        conn = self.connect(); c = conn.cursor()
        try:
            self.authorize(c, user, required)
            c.execute('''CREATE TABLE IF NOT EXISTS native_catalog_requests (
                request_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, operation TEXT NOT NULL,
                payload_hash TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)''')
            conn.commit()
            if not self.pg(): c.execute('BEGIN IMMEDIATE')
            c.execute('''INSERT INTO native_catalog_requests (request_id,user_id,operation,payload_hash,created_at)
                VALUES (?,?,?,?,?) ON CONFLICT (request_id) DO NOTHING''',
                (request_id, user['id'], operation, fingerprint, datetime.now().isoformat()))
            c.execute('SELECT user_id,payload_hash,result_json FROM native_catalog_requests WHERE request_id=?', (request_id,))
            owner, saved_hash, saved = c.fetchone()
            if owner != user['id'] or fingerprint != saved_hash: raise ValueError('Request ID belongs to a different change')
            if saved:
                conn.rollback(); return json.loads(saved)
            product_id = int(values.get('id') or values.get('product_id') or 0)
            if self.pg():
                # Serialize Native metadata/code edits; stock locks match Native Sales.
                if operation.startswith(('product.', 'products.', 'category.')):
                    c.execute('LOCK TABLE products, product_variants, categories IN EXCLUSIVE MODE')
                elif product_id:
                    c.execute('SELECT id FROM products WHERE id=? FOR UPDATE', (product_id,))
            # Database sequences are initialized by server setup/restore, never
            # reset during an interactive command while another cashier writes.
            if operation.startswith('category.'):
                result = self.category(c, operation, values)
            elif operation == 'products.import':
                rows = values.get('rows') or []
                if not 1 <= len(rows) <= 200: raise ValueError('Import 1–200 products per file')
                imported = []
                for index, row in enumerate(rows, 2):
                    try: imported.append(self.save_product(c, row)['product_id'])
                    except (ValueError, KeyError, TypeError) as exc: raise ValueError(f'CSV row {index}: {exc}') from exc
                result = {'message': f'{len(imported)} products imported', 'product_ids': imported}
            elif operation == 'product.save':
                result = self.save_product(c, values)
            elif operation == 'product.delete':
                result = self.delete_product(c, values)
            elif operation == 'pricing.save':
                result = self.pricing(c, values)
            elif operation == 'stock.reverse':
                result = self.reverse(c, values, user['username'], request_id)
            else:
                result = self.stock(c, operation, values, user['username'], request_id)
            result = dict(result, operation=operation, request_id=request_id)
            c.execute('UPDATE native_catalog_requests SET result_json=? WHERE request_id=?',
                      (json.dumps(result, default=str), request_id))
            conn.commit(); return result
        except Exception:
            conn.rollback(); raise
        finally: conn.close()

    def check_revision(self, current, values, key='revision'):
        if values.get(key) != current[key]: raise ValueError('Record changed. Refresh and review your changes again.')

    def save_product(self, c, values):
        product_id = int(values.get('id') or 0)
        previous = self.detail(c, product_id) if product_id else None
        if previous: self.check_revision(previous, values)
        name = str(values.get('name') or '').strip()
        mode = str(values.get('sold_by') or 'Each')
        if not name or len(name) > 300 or mode not in {'Each', 'Variants', 'Service', 'Restaurant'}: raise ValueError('Valid product name and sold-by mode required')
        if previous and self.service._sold_by_mode(previous['sold_by']) != mode.lower():
            raise ValueError('Existing product mode cannot be changed; create a separate product')
        data = {k: str(values.get(k) or '').strip() for k in PRODUCT_FIELDS if k not in {'price', 'cost', 'low_stock', 'pack_size'}}
        data.update(name=name, sold_by=mode, price=number(values.get('price')), cost=number(values.get('cost')),
                    low_stock=number(values.get('low_stock'), True, maximum=1000000),
                    pack_size=number(values.get('pack_size') or 1, True, minimum=1, maximum=1000000))
        data['unit'] = data['unit'] or 'pcs'; data['base_unit'] = data['base_unit'] or data['unit']
        if mode == 'Restaurant' and 'restaurant_modifiers' in values:
            from utils.restaurant_modifiers import normalize_modifiers
            if 'restaurant_modifiers' not in self.columns(c, 'products'): raise ValueError('Update the server restaurant schema first')
            modifiers = normalize_modifiers(values['restaurant_modifiers'])
            keys = [(m['group'], m['name']) for m in modifiers]
            if len(keys) != len(set(keys)): raise ValueError('Modifier names must be unique within a group')
            for m in modifiers:
                if not math.isfinite(m['price_delta']) or data['price'] + m['price_delta'] < 0: raise ValueError('Invalid modifier price')
            data['restaurant_modifiers'] = json.dumps(modifiers, ensure_ascii=False)
        if data['category']:
            c.execute('SELECT id FROM categories WHERE name=?', (data['category'],)); category = c.fetchone()
            if not category: raise ValueError('Select an existing category')
            data['category_id'] = category[0]
        else: data['category_id'] = None
        variants = list(values.get('variants') or []) if mode == 'Variants' else []
        if mode == 'Variants' and not variants: raise ValueError('Add at least one variant')
        seen = set()
        for record in [data, *variants]:
            for key in ('barcode', 'sku'):
                code = str(record.get(key) or '').strip()
                if not code: continue
                if code in seen: raise ValueError('Barcode/SKU values must be unique')
                seen.add(code)
                for table in ('products', 'product_variants'):
                    own = 'id' if table == 'products' else 'product_id'
                    c.execute(f'SELECT id FROM {table} WHERE (barcode=? OR sku=?) AND {own}<>? LIMIT 1', (code, code, product_id))
                    if c.fetchone(): raise ValueError('Barcode/SKU already exists: ' + code)
        if values.get('image_base64'):
            from PIL import Image
            raw = base64.b64decode(values['image_base64'], validate=True)
            if len(raw) > 8 * 1024 * 1024: raise ValueError('Image must be at most 8 MB')
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    fmt = image.format; image.verify()
            except (OSError, ValueError) as exc: raise ValueError('Cannot read the selected image') from exc
            mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp', 'BMP': 'image/bmp'}.get(fmt)
            if not mime: raise ValueError('Use PNG, JPEG, WEBP or BMP')
            if 'image_data' not in self.columns(c, 'products'): raise ValueError('Update server image schema first')
            data.update(image_data=raw, image='', image_mime=mime, image_filename=f'native-{digest(values)[:16]}.{fmt.lower()}')
        if previous:
            data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.update(c, 'products', product_id, data)
        else:
            product_id = self.insert(c, 'products', dict(data, stock=0))
        old_variants = {v['id']: v for v in previous['variants']} if previous else {}
        used = set()
        for variant in variants:
            variant_id = int(variant.get('id') or variant.get('variant_id') or 0)
            if variant_id and (variant_id not in old_variants or variant_id in used): raise ValueError('Invalid or repeated variant ID')
            used.add(variant_id)
            data = {k: str(variant.get(k) or '').strip() for k in ('color', 'size', 'sku', 'barcode')}
            data.update(price=number(variant.get('price')), cost=number(variant.get('cost')),
                        low_stock=number(variant.get('low_stock'), True), active=flag(variant.get('active', True)))
            if variant_id:
                if not data['active'] and old_variants[variant_id]['stock']: raise ValueError('Zero variant stock before deactivating it')
                self.update(c, 'product_variants', variant_id, data)
            else: self.insert(c, 'product_variants', dict(data, product_id=product_id, stock=0))
        for variant_id, old in old_variants.items():
            if variant_id not in used:
                if old['stock']: raise ValueError('Cannot remove a stocked variant')
                self.update(c, 'product_variants', variant_id, {'active': 0})
        return {'product_id': product_id, 'message': 'Product saved. Existing stock and variant IDs retained.'}

    def delete_product(self, c, values):
        product_id = int(values['id']); product = self.detail(c, product_id); self.check_revision(product, values)
        if product.get('stock') or any(v.get('stock') for v in product['variants']): raise ValueError('Cannot delete a stocked product')
        if self.pg():
            c.execute("SELECT table_name FROM information_schema.columns WHERE table_schema=CURRENT_SCHEMA() AND column_name='product_id'")
        else: c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in c.fetchall()]
        dependents = {'product_variants', 'product_locations', 'product_discounts', 'product_price_tiers'}
        from utils.db_compat import quote_identifier
        for table in tables:
            table = quote_identifier(table)
            if table in dependents or 'product_id' not in self.columns(c, table): continue
            c.execute(f'SELECT 1 FROM {table} WHERE product_id=? LIMIT 1', (product_id,))
            if c.fetchone(): raise ValueError('Product has history in ' + table + '; it cannot be deleted')
        if any(row.get('quantity') for row in product['locations']): raise ValueError('Location stock must be zero')
        for table in dependents:
            if self.columns(c, table): c.execute(f'DELETE FROM {table} WHERE product_id=?', (product_id,))
        c.execute('DELETE FROM products WHERE id=?', (product_id,))
        return {'message': 'Unused product deleted', 'product_id': product_id}

    def category(self, c, operation, values):
        record_id = int(values.get('id') or 0)
        rows = self.rows(c, 'SELECT * FROM categories ORDER BY id'); by_id = {row['id']: row for row in rows}
        previous = by_id.get(record_id)
        if record_id:
            if not previous or digest(previous) != values.get('revision'): raise ValueError('Category changed; refresh first')
            if previous.get('is_system'): raise ValueError('System categories cannot be changed here')
        if operation == 'category.delete':
            if not previous: raise ValueError('Select a category')
            c.execute('SELECT 1 FROM products WHERE category=? LIMIT 1', (previous['name'],))
            if c.fetchone() or any(row.get('parent_id') == record_id for row in rows): raise ValueError('Category still contains products or child categories')
            if 'category_id' in self.columns(c, 'products'):
                c.execute('SELECT 1 FROM products WHERE category_id=? LIMIT 1', (record_id,))
                if c.fetchone(): raise ValueError('Category still contains products')
            c.execute('DELETE FROM categories WHERE id=?', (record_id,))
            return {'message': 'Category deleted'}
        name = str(values.get('name') or '').strip(); parent = int(values.get('parent_id') or 0) or None
        if not name or len(name) > 200: raise ValueError('Category name is required (maximum 200 characters)')
        if any(row['name'].strip().casefold() == name.casefold() and row['id'] != record_id for row in rows): raise ValueError('Category name already exists')
        seen = {record_id} if record_id else set(); ancestor = parent
        while ancestor:
            if ancestor in seen or ancestor not in by_id: raise ValueError('Invalid category parent or hierarchy cycle')
            seen.add(ancestor); ancestor = by_id[ancestor].get('parent_id')
        data = dict(name=name, parent_id=parent, description=str(values.get('description') or ''), status=previous.get('status', 'active') if previous else 'active')
        if record_id:
            self.update(c, 'categories', record_id, data)
            c.execute('UPDATE products SET category=? WHERE category=?', (name, previous['name']))
        else: record_id = self.insert(c, 'categories', data)
        return {'message': 'Category saved', 'category_id': record_id}

    def pricing(self, c, values):
        product_id = int(values['product_id']); product = self.detail(c, product_id)
        self.check_revision(product, values, 'pricing_revision')
        if self.service._sold_by_mode(product['sold_by']) != 'each': raise ValueError('Product discounts/wholesale tiers apply to Each products')
        for key, table in [('discounts', 'product_discounts'), ('tiers', 'product_price_tiers')]:
            if not self.columns(c, table): raise ValueError('Update the server discount/wholesale schema first')
            if key == 'discounts' and not {'discount_type', 'manual_price'}.issubset(self.columns(c, table)):
                raise ValueError('Update the server product discount schema first')
            existing = {r['id'] for r in product[key]}; retained = set()
            for row in values.get(key, []):
                record_id = int(row.get('id') or 0)
                if record_id and (record_id not in existing or record_id in retained): raise ValueError('Invalid pricing record')
                retained.add(record_id)
                if key == 'discounts':
                    start = date.fromisoformat(row['start_date']); end = date.fromisoformat(row['end_date'])
                    if end < start: raise ValueError('Discount end date precedes start date')
                    mode = row.get('discount_type', 'percentage')
                    if mode not in {'percentage', 'manual_price'}: raise ValueError('Invalid discount type')
                    data = dict(discount_type=mode, discount_percent=number(row.get('discount_percent'), maximum=100),
                                manual_price=number(row.get('manual_price')), start_date=str(start), end_date=str(end))
                else:
                    data = dict(min_qty=number(row.get('min_qty'), True, 1, 1000000), unit_price=number(row.get('unit_price'), minimum=0.01),
                                unit_label=str(row.get('unit_label') or ''), unit_multiplier=number(row.get('unit_multiplier') or 1, True, 1),
                                barcode=str(row.get('barcode') or ''))
                data.update(note=str(row.get('note') or ''), active=flag(row.get('active', True)))
                if record_id: self.update(c, table, record_id, data)
                else: self.insert(c, table, dict(data, product_id=product_id))
            for record_id in existing - retained: c.execute(f'DELETE FROM {table} WHERE id=?', (record_id,))
        return {'message': 'Discounts and wholesale tiers saved', 'product_id': product_id}

    def stock(self, c, operation, values, actor, request_id):
        product_id = int(values['product_id']); product = self.detail(c, product_id)
        self.check_revision(product, values, 'stock_revision')
        mode = self.service._sold_by_mode(product['sold_by'])
        if mode in {'service', 'restaurant'}: raise ValueError('Services and restaurant menu items do not track stock')
        reason = str(values.get('reason') or '').strip()
        if not reason: raise ValueError('Reason required')
        quantity = number(values.get('quantity'), True, 0 if operation == 'stock.set' else 1, 1000000)
        variant_id = int(values.get('variant_id') or 0) or None
        variant = next((v for v in product['variants'] if v['id'] == variant_id and v.get('active', 1)), None)
        if mode == 'variants' and not variant: raise ValueError('Select an active variant')
        if mode != 'variants' and variant_id: raise ValueError('This product has no selectable variants')
        old_master = int(product.get('stock') or 0); old = int(variant.get('stock') or 0) if variant else old_master
        if variant and sum(int(v.get('stock') or 0) for v in product['variants']) != old_master:
            raise ValueError('Master/variant stock differs. Reconcile in the existing POS before changing stock.')
        location = str(values.get('location') or 'Shop').strip(); destination = str(values.get('to_location') or '').strip()
        if operation == 'stock.transfer' and (variant or not destination or destination == location): raise ValueError('Choose two different locations for an Each product')
        difference = quantity - old if operation == 'stock.set' else -quantity if operation == 'stock.out' else quantity
        if operation == 'stock.transfer': difference = 0
        if old + difference < 0: raise ValueError('Insufficient stock')
        if not variant:
            locations = product['locations']
            if not locations and old_master:
                self.insert(c, 'product_locations', dict(product_id=product_id, location='Shop', quantity=old_master, batch_no='', expire_date=''))
            elif sum(int(row.get('quantity') or 0) for row in locations) != old_master:
                raise ValueError('Master/location stock differs. Reconcile in the existing POS before changing stock.')
            if difference < 0 or operation == 'stock.transfer':
                needed = -difference if difference < 0 else quantity
                rows = self.rows(c, '''SELECT * FROM product_locations WHERE product_id=? AND location=? AND quantity>0
                    ORDER BY CASE WHEN expire_date IS NULL OR expire_date='' THEN 1 ELSE 0 END, expire_date, id''', (product_id, location))
                if sum(int(row['quantity']) for row in rows) < needed: raise ValueError('Insufficient stock in ' + location)
                for row in rows:
                    take = min(needed, int(row['quantity']))
                    if not take: continue
                    self.update(c, 'product_locations', row['id'], {'quantity': int(row['quantity']) - take, 'last_updated': datetime.now().isoformat()})
                    if operation == 'stock.transfer': self.add_location(c, product_id, destination, take, row.get('batch_no'), row.get('expire_date'))
                    needed -= take
                    if not needed: break
            elif difference > 0:
                expiry = str(values.get('expire_date') or '')
                if expiry: date.fromisoformat(expiry)
                self.add_location(c, product_id, location, difference, str(values.get('batch_no') or ''), expiry)
        if variant:
            self.update(c, 'product_variants', variant_id, {'stock': old + difference, 'updated_at': datetime.now().isoformat()})
        cost = float(product.get('cost') or 0)
        if operation == 'stock.in':
            unit_cost = number(values.get('unit_cost'))
            cost = (old_master * cost + quantity * unit_cost) / (old_master + quantity)
            if variant: self.update(c, 'product_variants', variant_id, {'cost': unit_cost})
        self.update(c, 'products', product_id, {'stock': old_master + difference, 'cost': cost, 'last_updated': datetime.now().isoformat()})
        reference = str(values.get('reference') or request_id)
        movement = dict(product_id=product_id, variant_id=variant_id, quantity=abs(difference), old_stock=old, new_stock=old + difference,
                        reason=reason, reference=reference, created_by=actor, location='Variant' if variant else location,
                        notes=str(values.get('notes') or '') + f' [Native request: {request_id}]', created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        if operation == 'stock.transfer':
            for kind, place in [('out', location), ('in', destination)]:
                self.insert(c, 'stock_movements', dict(movement, type=kind, quantity=quantity, location=place,
                            reason=f'Transfer {location} → {destination}: {reason}'))
        else: self.insert(c, 'stock_movements', dict(movement, type={'stock.in': 'stock_in', 'stock.out': 'stock_out', 'stock.set': 'adjustment'}[operation]))
        return {'message': 'Stock change saved', 'product_id': product_id,
                'before': self.stock_snapshot(product), 'after': self.stock_snapshot(self.detail(c, product_id))}

    def stock_snapshot(self, product):
        return dict(stock=product.get('stock'), cost=product.get('cost'), locations=product['locations'],
                    variants=[{key: row.get(key) for key in ('id', 'stock', 'cost')} for row in product['variants']])

    def reverse(self, c, values, actor, request_id):
        product_id = int(values['product_id']); product = self.detail(c, product_id)
        self.check_revision(product, values, 'stock_revision')
        original_id = str(values.get('original_request_id') or ''); UUID(original_id)
        reason = str(values.get('reason') or '').strip()
        if not reason: raise ValueError('Reversal reason required')
        c.execute('SELECT operation,result_json FROM native_catalog_requests WHERE request_id=?', (original_id,))
        row = c.fetchone()
        if not row or row[0] not in {'stock.in', 'stock.out', 'stock.set', 'stock.transfer'} or not row[1]:
            raise ValueError('Only confirmed Native stock operations can be reversed here')
        original = json.loads(row[1])
        if original.get('product_id') != product_id: raise ValueError('Movement belongs to another product')
        c.execute('''CREATE TABLE IF NOT EXISTS native_catalog_reversals (
            original_request_id TEXT PRIMARY KEY, reversal_request_id TEXT NOT NULL)''')
        c.execute('SELECT 1 FROM native_catalog_reversals WHERE original_request_id=?', (original_id,))
        if c.fetchone(): raise ValueError('This operation has already been reversed')
        if digest(self.stock_snapshot(product)) != digest(original['after']):
            raise ValueError('Stock, costs or batches changed after this operation. Use a reviewed adjustment instead.')
        before = original['before']
        self.update(c, 'products', product_id, {'stock': before['stock'], 'cost': before['cost'], 'last_updated': datetime.now().isoformat()})
        for variant in before['variants']:
            self.update(c, 'product_variants', variant['id'], {'stock': variant['stock'], 'cost': variant['cost'], 'updated_at': datetime.now().isoformat()})
        c.execute('DELETE FROM product_locations WHERE product_id=?', (product_id,))
        for location in before['locations']: self.insert(c, 'product_locations', location)
        self.insert(c, 'stock_movements', dict(product_id=product_id, type='adjustment', quantity=abs(int(product['stock']) - int(before['stock'])),
                    old_stock=product['stock'], new_stock=before['stock'], created_by=actor, reason='Reversal: ' + reason,
                    reference='REV-' + original_id, notes='Reversed Native operation ' + original_id, location='Native reversal',
                    created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        c.execute('INSERT INTO native_catalog_reversals VALUES (?,?)', (original_id, request_id))
        return {'message': 'Native stock operation reversed; original history retained', 'product_id': product_id}

    def add_location(self, c, product_id, location, quantity, batch, expiry):
        c.execute('''SELECT id,quantity FROM product_locations WHERE product_id=? AND location=?
            AND COALESCE(batch_no,'')=? AND COALESCE(expire_date,'')=? ORDER BY id LIMIT 1''', (product_id, location, batch or '', expiry or ''))
        row = c.fetchone()
        if row: self.update(c, 'product_locations', row[0], {'quantity': int(row[1]) + quantity, 'last_updated': datetime.now().isoformat()})
        else: self.insert(c, 'product_locations', dict(product_id=product_id, location=location, quantity=quantity,
                                                      batch_no=batch or '', expire_date=expiry or '', last_updated=datetime.now().isoformat()))


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException, Query
    from pydantic import BaseModel, Field
    repo = repository or CatalogRepository()

    class Command(BaseModel):
        request_id: str = Field(min_length=36, max_length=36)
        operation: str = Field(max_length=40)
        values: dict

    @app.get('/api/native/catalog')
    def catalog(section: str = 'products', product_id: int | None = Query(default=None, gt=0), user=Depends(current_user)):
        try: return repo.read(user, section, product_id)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc

    @app.post('/api/native/catalog/commands')
    def command(payload: Command, user=Depends(current_user)):
        try: return {'result': repo.command(user, payload.request_id, payload.operation, payload.values)}
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc: return {'rejected': str(exc)}
