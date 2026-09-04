"""Standard Qt editors for the Phase 4 catalog and inventory workflows."""
import base64
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel, QFileDialog,
    QDialogButtonBox, QMessageBox, QScrollArea)
from lite_pos.cart import sold_by_mode


def numeric(value=0, integer=False):
    widget = QSpinBox() if integer else QDoubleSpinBox()
    widget.setRange(0, 1000000 if integer else 999999999999)
    if not integer: widget.setDecimals(2); widget.setGroupSeparatorShown(True)
    widget.setValue(int(value or 0) if integer else float(value or 0))
    return widget


class RecordGrid(QWidget):
    def __init__(self, fields, records=(), parent=None):
        super().__init__(parent); self.fields = fields
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(fields) + 1)
        self.table.setHorizontalHeaderLabels(['ID'] + [f[1] for f in fields]); self.table.hideColumn(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setMinimumHeight(160); layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        add = QPushButton('Add row'); remove = QPushButton('Remove selected row')
        add.clicked.connect(lambda: self.add({})); remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()) if self.table.currentRow() >= 0 else None)
        buttons.addWidget(add); buttons.addWidget(remove); buttons.addStretch(); layout.addLayout(buttons)
        for record in records: self.add(record)

    def add(self, record):
        row = self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(record.get('id') or record.get('variant_id') or 0)))
        for column, (key, label, kind, default) in enumerate(self.fields, 1):
            value = record.get(key, default)
            if kind in ('money', 'int', 'signed_money'):
                widget = numeric(value, kind == 'int')
                if kind == 'signed_money': widget.setMinimum(-999999999); widget.setValue(float(value or 0))
            elif kind == 'bool':
                widget = QCheckBox(); widget.setChecked(bool(value))
            elif kind == 'date':
                widget = QDateEdit(); widget.setCalendarPopup(True); widget.setDisplayFormat('yyyy-MM-dd')
                widget.setDate(QDate.fromString(str(value), 'yyyy-MM-dd'))
            elif isinstance(kind, tuple):
                widget = QComboBox(); widget.addItems(kind); widget.setCurrentText(str(value))
            else:
                widget = QLineEdit(str(value if value is not None else ''))
                widget.setReadOnly(kind == 'readonly')
            widget.setMinimumWidth(85 if kind != 'date' else 110)
            self.table.setCellWidget(row, column, widget)
        self.table.resizeColumnsToContents()

    def records(self):
        result = []
        for row in range(self.table.rowCount()):
            record = {'id': int(self.table.item(row, 0).text())}
            for column, (key, _label, kind, _default) in enumerate(self.fields, 1):
                widget = self.table.cellWidget(row, column)
                if kind in ('money', 'int', 'signed_money'): value = widget.value()
                elif kind == 'bool': value = widget.isChecked()
                elif kind == 'date': value = widget.date().toString('yyyy-MM-dd')
                elif isinstance(kind, tuple): value = widget.currentText()
                else: value = widget.text().strip()
                record[key] = value
            result.append(record)
        return result


class Editor(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.resize(850, 550)
        self.body = QVBoxLayout(self)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate); self.buttons.rejected.connect(self.reject)

    def finish(self): self.body.addWidget(self.buttons)
    def validate(self):
        try: self.values()
        except (ValueError, OSError) as exc: QMessageBox.warning(self, self.windowTitle(), str(exc)); return
        self.accept()


class ProductDialog(Editor):
    def __init__(self, product, categories, parent=None):
        super().__init__('Product · Native', parent)
        self.product = deepcopy(product or {}); self.image_path = ''
        tabs = QTabWidget(); self.body.addWidget(tabs, 1)
        general = QWidget(); form = QFormLayout(general); self.fields = {}
        for key, label in [('name', 'Name'), ('sku', 'SKU'), ('barcode', 'Barcode'),
                           ('unit', 'Stock unit'), ('pack_unit', 'Pack name')]:
            self.fields[key] = QLineEdit(str(self.product.get(key) or ('pcs' if key == 'unit' else '')))
            form.addRow(label, self.fields[key])
        self.category = QComboBox(); self.category.addItem('')
        self.category.addItems([c['name'] for c in categories]); self.category.setCurrentText(str(self.product.get('category') or ''))
        form.insertRow(1, 'Category', self.category)
        self.mode = QComboBox(); self.mode.addItems(['Each', 'Variants', 'Service', 'Restaurant'])
        self.mode.setCurrentText(sold_by_mode(self.product.get('sold_by')).title()); self.mode.setEnabled(not bool(self.product))
        form.insertRow(2, 'Sold by', self.mode)
        for key, label, integer in [('price', 'Regular price', False), ('cost', 'Cost', False), ('low_stock', 'Low stock alert', True), ('pack_size', 'Units per pack', True)]:
            self.fields[key] = numeric(self.product.get(key, 1 if key == 'pack_size' else 0), integer)
            if key == 'pack_size': self.fields[key].setMinimum(1)
            form.addRow(label, self.fields[key])
        self.description = QPlainTextEdit(str(self.product.get('description') or '')); self.description.setMaximumHeight(70)
        form.addRow('Description', self.description)
        note = QLabel('Stock is maintained in Inventory. Existing variant IDs and stock are retained when editing.'); note.setWordWrap(True)
        form.addRow(note)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(general); tabs.addTab(scroll, 'General')
        self.variants = RecordGrid([
            ('color', 'Color', 'text', ''), ('size', 'Size', 'text', ''), ('sku', 'SKU', 'text', ''), ('barcode', 'Barcode', 'text', ''),
            ('price', 'Price', 'money', 0), ('cost', 'Cost', 'money', 0), ('stock', 'Stock (read only)', 'readonly', 0),
            ('low_stock', 'Low stock', 'int', 0), ('active', 'Active', 'bool', True)], self.product.get('variants', []))
        tabs.addTab(self.variants, 'Variants')
        image = QWidget(); image_layout = QVBoxLayout(image)
        self.image_note = QLabel('Current image retained' if self.product.get('image_filename') or self.product.get('image') else 'No image selected')
        self.preview = QLabel(); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button = QPushButton('Choose image…'); button.clicked.connect(self.choose_image)
        image_layout.addWidget(self.image_note); image_layout.addWidget(self.preview, 1); image_layout.addWidget(button)
        tabs.addTab(image, 'Image')
        from utils.restaurant_modifiers import normalize_modifiers
        self.modifiers = RecordGrid([('group', 'Group', 'text', 'Options'), ('name', 'Option', 'text', ''),
            ('type', 'Type', ('choice', 'note'), 'note'), ('price_delta', 'Price change', 'signed_money', 0)],
            normalize_modifiers(self.product.get('restaurant_modifiers')))
        modifier_tab = tabs.addTab(self.modifiers, 'Restaurant modifiers')
        def mode_changed():
            variants = self.mode.currentText() == 'Variants'; tabs.setTabEnabled(1, variants)
            tabs.setTabEnabled(modifier_tab, self.mode.currentText() == 'Restaurant')
            for key in ('price', 'cost'): self.fields[key].setEnabled(not variants)
        self.mode.currentTextChanged.connect(mode_changed); mode_changed(); self.finish()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Product image', '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path: return
        if Path(path).stat().st_size > 8 * 1024 * 1024:
            QMessageBox.warning(self, 'Image', 'Maximum image size is 8 MB'); return
        pixmap = QPixmap(path)
        if pixmap.isNull(): QMessageBox.warning(self, 'Image', 'Cannot read this image'); return
        self.image_path = path; self.image_note.setText(Path(path).name)
        self.preview.setPixmap(pixmap.scaled(560, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def values(self):
        values = {'id': self.product.get('id'), 'revision': self.product.get('revision')}
        for key, widget in self.fields.items(): values[key] = widget.value() if hasattr(widget, 'value') else widget.text().strip()
        if not values['name']: raise ValueError('Product name is required')
        values.update(category=self.category.currentText(), sold_by=self.mode.currentText(), base_unit=values['unit'],
                      description=self.description.toPlainText(), variants=self.variants.records() if self.mode.currentText() == 'Variants' else [])
        if values['sold_by'] == 'Variants' and not values['variants']: raise ValueError('Add at least one variant')
        if values['sold_by'] == 'Restaurant': values['restaurant_modifiers'] = self.modifiers.records()
        if self.image_path: values['image_base64'] = base64.b64encode(Path(self.image_path).read_bytes()).decode('ascii')
        return values


class PricingDialog(Editor):
    def __init__(self, product, parent=None):
        super().__init__('Discounts / wholesale · ' + product['name'], parent); self.product = product
        tabs = QTabWidget(); self.body.addWidget(tabs, 1)
        today = QDate.currentDate().toString('yyyy-MM-dd')
        discounts = [dict(row, discount_type='Fixed price' if row.get('discount_type') == 'manual_price' else 'Percent')
                     for row in product.get('discounts', [])]
        self.discounts = RecordGrid([
            ('discount_type', 'Type', ('Percent', 'Fixed price'), 'Percent'),
            ('discount_percent', 'Percent', 'money', 0), ('manual_price', 'Fixed price', 'money', 0),
            ('start_date', 'Start', 'date', today), ('end_date', 'End', 'date', today),
            ('active', 'Active', 'bool', True), ('note', 'Note', 'text', '')], discounts)
        self.tiers = RecordGrid([
            ('min_qty', 'Minimum qty', 'int', 1), ('unit_price', 'Unit price', 'money', 0),
            ('unit_label', 'Unit label', 'text', ''), ('unit_multiplier', 'Unit multiplier', 'int', 1),
            ('barcode', 'Tier barcode', 'text', ''), ('active', 'Active', 'bool', True), ('note', 'Note', 'text', '')], product.get('tiers', []))
        tabs.addTab(self.discounts, 'Product discounts'); tabs.addTab(self.tiers, 'Wholesale tiers')
        note = QLabel('Percent reduces the regular price. Fixed price sets the sale price. Wholesale pricing starts at the minimum quantity.\nRemoving a row deletes that pricing rule when you save. Existing expiry rules are retained.')
        note.setWordWrap(True); self.body.addWidget(note); self.finish()

    def values(self):
        discounts = self.discounts.records(); tiers = self.tiers.records()
        for row in discounts:
            row['discount_type'] = 'manual_price' if row['discount_type'] == 'Fixed price' else 'percentage'
            if row['discount_percent'] > 100: raise ValueError('Percent must be 0–100')
            if row['end_date'] < row['start_date']: raise ValueError('End date must follow start date')
        for row in tiers:
            if row['min_qty'] < 1 or row['unit_price'] <= 0: raise ValueError('Wholesale quantity and price must be positive')
        return dict(product_id=self.product['id'], pricing_revision=self.product['pricing_revision'], discounts=discounts, tiers=tiers)


class StockDialog(Editor):
    def __init__(self, product, operation, actor, parent=None):
        super().__init__(operation.replace('stock.', 'Stock ').title() + ' · ' + product['name'], parent)
        self.product = product; self.operation = operation; form = QFormLayout(); self.body.addLayout(form)
        form.addRow('Recorded by', QLabel(actor)); form.addRow('Total product stock', QLabel(str(product.get('stock', 0))))
        self.variant = QComboBox(); self.variant.addItem('Standard product', None)
        if sold_by_mode(product.get('sold_by')) == 'variants':
            self.variant.clear()
            for v in product.get('variants', []):
                if v.get('active', 1): self.variant.addItem(f'{v.get("color", "")} / {v.get("size", "")} · Stock {v.get("stock", 0)}', v['id'])
        form.addRow('Variant', self.variant)
        locations = list(dict.fromkeys(['Shop'] + [row.get('location') or 'Shop' for row in product.get('locations', [])]))
        self.location = QComboBox(); self.location.setEditable(True); self.location.addItems(locations)
        self.destination = QLineEdit(); form.addRow('Location / from', self.location)
        if operation == 'stock.transfer': form.addRow('To location', self.destination)
        self.quantity = numeric(product.get('stock', 0) if operation == 'stock.set' else 1, True)
        if operation != 'stock.set': self.quantity.setMinimum(1)
        form.addRow('Counted total' if operation == 'stock.set' else 'Quantity', self.quantity)
        self.cost = numeric(product.get('cost', 0)); self.batch = QLineEdit(); self.expiry = QLineEdit()
        def selected_variant():
            record = next((v for v in product.get('variants', []) if v['id'] == self.variant.currentData()), product)
            if operation == 'stock.set': self.quantity.setValue(int(record.get('stock') or 0))
            if operation == 'stock.in': self.cost.setValue(float(record.get('cost') or 0))
        self.variant.currentIndexChanged.connect(selected_variant); selected_variant()
        self.expiry.setPlaceholderText('YYYY-MM-DD or leave blank')
        if operation == 'stock.in':
            form.addRow('Unit cost', self.cost); form.addRow('Batch', self.batch); form.addRow('Expiry date', self.expiry)
        self.reason = QLineEdit(); self.reference = QLineEdit(); self.notes = QPlainTextEdit(); self.notes.setMaximumHeight(80)
        form.addRow('Reason', self.reason); form.addRow('Reference', self.reference); form.addRow('Notes', self.notes)
        note = QLabel('Stock Out uses the selected location. Adjustment sets the product/variant total; its difference is added to or removed from the selected location.')
        note.setWordWrap(True); self.body.addWidget(note); self.body.addStretch(); self.finish()

    def values(self):
        if not self.reason.text().strip(): raise ValueError('Reason is required')
        location = self.location.currentText().strip()
        if not location: raise ValueError('Location required')
        if self.operation == 'stock.transfer' and (not self.destination.text().strip() or self.destination.text().strip() == location):
            raise ValueError('Choose two different locations')
        if self.expiry.text().strip():
            from datetime import date
            date.fromisoformat(self.expiry.text().strip())
        return dict(product_id=self.product['id'], stock_revision=self.product['stock_revision'], variant_id=self.variant.currentData(),
                    location=location, to_location=self.destination.text().strip(), quantity=self.quantity.value(), unit_cost=self.cost.value(),
                    batch_no=self.batch.text().strip(), expire_date=self.expiry.text().strip(), reason=self.reason.text().strip(),
                    reference=self.reference.text().strip(), notes=self.notes.toPlainText())


class CategoryDialog(Editor):
    def __init__(self, categories, parent=None):
        super().__init__('Categories · Native', parent); self.categories = categories; self.operation = 'category.save'
        form = QFormLayout(); self.body.addLayout(form)
        self.selection = QComboBox(); self.selection.addItem('New category', None)
        for row in categories: self.selection.addItem(row['name'], row)
        self.name = QLineEdit(); self.description = QPlainTextEdit()
        self.parent_category = QComboBox(); self.parent_category.addItem('No parent', None)
        for row in categories: self.parent_category.addItem(row['name'], row['id'])
        form.addRow('Category', self.selection); form.addRow('Name', self.name); form.addRow('Parent', self.parent_category); form.addRow('Description', self.description)
        self.selection.currentIndexChanged.connect(self.selected)
        self.delete = QPushButton('Delete selected empty category'); self.delete.clicked.connect(self.delete_selected)
        self.body.addWidget(self.delete); self.body.addStretch(); self.finish()

    def selected(self):
        record = self.selection.currentData() or {}
        self.name.setText(record.get('name', '')); self.description.setPlainText(record.get('description') or '')
        self.parent_category.setCurrentIndex(max(0, self.parent_category.findData(record.get('parent_id'))))

    def delete_selected(self):
        if not self.selection.currentData(): return
        if QMessageBox.question(self, 'Delete category', 'Delete this empty category?') == QMessageBox.StandardButton.Yes:
            self.operation = 'category.delete'; self.accept()

    def values(self):
        row = self.selection.currentData() or {}
        if not self.name.text().strip(): raise ValueError('Category name required')
        return dict(id=row.get('id'), revision=row.get('revision'), name=self.name.text().strip(),
                    parent_id=self.parent_category.currentData(), description=self.description.toPlainText())
