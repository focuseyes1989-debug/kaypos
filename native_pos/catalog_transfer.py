"""Native metadata CSV round trips. Stock is deliberately a separate audited operation."""
import csv
import json
import math
from pathlib import Path

FIELDS = ['id', 'revision', 'name', 'category', 'description', 'sold_by', 'price', 'cost', 'sku', 'barcode',
          'low_stock', 'unit', 'base_unit', 'pack_unit', 'pack_size', 'variants_json']


def csv_text(value):
    text = str(value if value is not None else '')
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r', "'")) else text


def write_products(path, records):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader()
        for product in records:
            values = {key: csv_text(product.get(key, '')) for key in FIELDS}
            values['variants_json'] = json.dumps(product.get('variants', []), ensure_ascii=False, default=str)
            writer.writerow(values)


def read_products(path):
    if Path(path).stat().st_size > 8 * 1024 * 1024: raise ValueError('CSV must be at most 8 MB')
    records, errors = [], []
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not {'name', 'sold_by'}.issubset(reader.fieldnames or []): raise ValueError('CSV needs name and sold_by columns. Export a Native page for the full template.')
        for line, row in enumerate(reader, 2):
            if line > 201: raise ValueError('Import at most 200 products per file')
            try:
                if None in row: raise ValueError('Too many CSV columns')
                values = {key: str(value or '')[1:] if str(value or '').startswith("'") else str(value or '') for key, value in row.items()}
                if not values['name'].strip(): raise ValueError('Name is required')
                if values['sold_by'] not in {'Each', 'Service', 'Variants'}: raise ValueError('sold_by must be Each, Service or Variants')
                for key in ('id', 'low_stock', 'pack_size'):
                    raw = values.get(key, '') or (1 if key == 'pack_size' else 0)
                    values[key] = int(raw)
                    if values[key] < (1 if key == 'pack_size' else 0): raise ValueError('Invalid ' + key)
                for key in ('price', 'cost'):
                    values[key] = float(values.get(key) or 0)
                    if not math.isfinite(values[key]) or values[key] < 0: raise ValueError('Invalid ' + key)
                values['variants'] = json.loads(values.pop('variants_json', '') or '[]')
                if not isinstance(values['variants'], list) or any(not isinstance(v, dict) for v in values['variants']): raise ValueError('variants_json must be a list of variant objects')
                if values['id'] and not values.get('revision'): raise ValueError('Existing products require the exported revision')
                records.append(values)
            except (ValueError, TypeError, KeyError) as exc: errors.append(f'Row {line}: {exc}')
    if errors: raise ValueError('\n'.join(errors[:20]))
    if not records: raise ValueError('CSV contains no products')
    return records
