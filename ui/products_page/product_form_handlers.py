# ui/products_page/product_form_handlers.py
from PyQt6.QtWidgets import (
    QMessageBox, QFileDialog, QTableWidgetItem, QDialog, QVBoxLayout,
    QHBoxLayout, QTableWidget, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon
from models.database import connect_db
from utils.db_compat import is_postgres_backend
from utils.translations import tr
from utils.language import lang
from utils.paths import app_path
from utils.image_optimizer import ImageOptimizer
from ui.widgets.modern_button import ModernButton
from ui.products_page.product_form_ui_styles import ProductFormUIStyles
from ui.themes.theme_manager import get_theme_colors
from utils.wholesale_pricing import ensure_wholesale_schema, get_price_tiers, save_price_tiers
from utils.unit_conversion import ensure_unit_conversion_schema, normalize_unit_settings
from utils.restaurant_modifiers import (
    DEFAULT_RESTAURANT_MODIFIERS,
    dumps_modifiers,
    ensure_restaurant_modifier_schema,
    normalize_modifiers,
)
import os
import uuid


class ProductFormHandlers:
    """Event handlers for ProductFormDialog"""
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.image_path = ""
    
    def setup_signals(self):
        """Connect all signals"""
        d = self.dialog
        self.ensure_variant_schema()
        d.btn_save.clicked.connect(self.save)
        d.btn_cancel.clicked.connect(d.reject)
        d.btn_browse.clicked.connect(self.select_image)
        d.sold_by_combo.currentTextChanged.connect(self.toggle_service_fields)
        d.barcode_input.returnPressed.connect(self.on_barcode_entered)
        if hasattr(d, "base_unit_input"):
            d.base_unit_input.textChanged.connect(self.update_product_details)
            d.pack_unit_input.textChanged.connect(self.update_product_details)
            d.pack_size_input.valueChanged.connect(self.update_product_details)
        if hasattr(d, "btn_manage_variants"):
            d.btn_manage_variants.clicked.connect(self.open_variants_dialog)
        if hasattr(d, "btn_manage_wholesale"):
            d.btn_manage_wholesale.clicked.connect(self.open_wholesale_dialog)
        if hasattr(d, "btn_manage_restaurant_options"):
            d.btn_manage_restaurant_options.clicked.connect(self.open_restaurant_modifiers_dialog)

    def ensure_variant_schema(self):
        if is_postgres_backend():
            from models.database import safe_initialize_postgres_pilot_database

            safe_initialize_postgres_pilot_database()
            return

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                size TEXT,
                color TEXT,
                sku TEXT,
                barcode TEXT,
                price REAL DEFAULT 0,
                cost REAL DEFAULT 0,
                stock INTEGER DEFAULT 0,
                low_stock INTEGER DEFAULT 0,
                image TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("PRAGMA table_info(sale_items)")
        sale_cols = [c[1] for c in cursor.fetchall()]
        if "variant_id" not in sale_cols:
            try:
                cursor.execute("ALTER TABLE sale_items ADD COLUMN variant_id INTEGER")
            except Exception:
                pass
        ensure_wholesale_schema(cursor)
        ensure_unit_conversion_schema(cursor)
        ensure_restaurant_modifier_schema(cursor)
        conn.commit()
        conn.close()
    
    def load_categories(self):
        """Load categories from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        rows = cursor.fetchall()
        
        d = self.dialog
        d.category_combo.clear()
        for cat_id, name in rows:
            d.category_combo.addItem(name, cat_id)
        conn.close()
    
    def load_product_data(self):
        """Load product data for editing"""
        conn = connect_db()
        cursor = conn.cursor()
        ensure_unit_conversion_schema(cursor)
        ensure_restaurant_modifier_schema(cursor)
        cursor.execute("""
            SELECT name, category, barcode, description, sold_by, price,
                   low_stock, image, category_id, base_unit, pack_unit, pack_size,
                   restaurant_modifiers
            FROM products WHERE id=?
        """, (self.dialog.product_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if row:
            d = self.dialog
            d.name_input.setText(row[0])
            
            idx = d.category_combo.findData(row[8]) if len(row) > 8 and row[8] else -1
            if idx < 0:
                idx = d.category_combo.findText(row[1])
            if idx >= 0:
                d.category_combo.setCurrentIndex(idx)
            
            d.barcode_input.setText(row[2] or "")
            d.description_input.setPlainText(row[3])
            sold_by = row[4] or "Each"
            idx = d.sold_by_combo.findData(sold_by)
            d.sold_by_combo.setCurrentIndex(idx if idx >= 0 else 0)
            d.price_input.setValue(float(row[5]))
            d.low_stock_input.setValue(int(row[6]) if row[6] else 0)
            self.image_path = row[7] or ""
            d.image_input.setText(row[7] or "")
            units = normalize_unit_settings(row[9] if len(row) > 9 else None, row[10] if len(row) > 10 else None, row[11] if len(row) > 11 else None)
            if hasattr(d, "base_unit_input"):
                d.base_unit_input.setText(units["base_unit"])
                d.pack_unit_input.setText(units["pack_unit"])
                d.pack_size_input.setValue(units["pack_size"])
            if hasattr(d, "restaurant_modifiers_table"):
                self.set_restaurant_modifiers(normalize_modifiers(row[12] if len(row) > 12 else ""))
            
            # Update image preview
            self.update_image_preview()
            self.load_wholesale_tiers()
            self.load_variants()
            if hasattr(d, "variants_table") and d.variants_table.rowCount() > 0:
                idx = d.sold_by_combo.findData("Variants")
                if idx >= 0:
                    d.sold_by_combo.setCurrentIndex(idx)
            self.toggle_service_fields()

    def add_variant_row(self, values=None):
        """Add a size/color variant row."""
        d = self.dialog
        row = d.variants_table.rowCount()
        d.variants_table.insertRow(row)
        if not isinstance(values, dict):
            values = {}
        sku = values.get("sku", "") or self.generate_variant_sku(row + 1)
        price = values.get("price", "")
        if price not in (None, ""):
            try:
                price = f"{float(price):g}"
            except (TypeError, ValueError):
                price = str(price)
        defaults = [
            values.get("size", ""),
            values.get("color", ""),
            sku,
            values.get("barcode", ""),
            str(price if price not in (None, 0, "0") else ""),
            str(values.get("low_stock", "")),
        ]
        for col, text in enumerate(defaults):
            item = QTableWidgetItem(str(text))
            if col in (4, 5):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            d.variants_table.setItem(row, col, item)
        self.update_variants_summary()

    def generate_variant_sku(self, row_number: int) -> str:
        """Generate a readable variant SKU for the current product."""
        name = self.dialog.name_input.text().strip() or "VAR"
        base = "".join(ch for ch in name.upper().replace(" ", "-") if ch.isalnum() or ch == "-")
        base = base[:16].strip("-") or "VAR"
        product_id = self.dialog.product_id or "NEW"
        return f"{base}-{product_id}-{row_number:02d}"

    def remove_selected_variant_row(self):
        d = self.dialog
        row = d.variants_table.currentRow()
        if row >= 0:
            d.variants_table.removeRow(row)
            self.update_variants_summary()

    def update_variants_summary(self):
        d = self.dialog
        if not hasattr(d, "variants_summary_label") or not hasattr(d, "variants_table"):
            return
        count = d.variants_table.rowCount()
        d.variants_summary_label.setText(f"{count} variant{'s' if count != 1 else ''} added" if count else "No variants added")

    def add_wholesale_row(self, values=None):
        """Add a wholesale price tier row."""
        d = self.dialog
        row = d.wholesale_table.rowCount()
        d.wholesale_table.insertRow(row)
        if not isinstance(values, dict):
            values = {}
        defaults = [
            str(values.get("min_qty", "")),
            values.get("unit_label", ""),
            str(values.get("unit_multiplier", "")),
            values.get("barcode", ""),
            str(values.get("unit_price", "")),
            values.get("note", ""),
        ]
        for col, text in enumerate(defaults):
            item = QTableWidgetItem(str(text))
            if col in (0, 2, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            d.wholesale_table.setItem(row, col, item)
        self.update_wholesale_summary()

    def update_wholesale_summary(self):
        d = self.dialog
        if not hasattr(d, "wholesale_summary_label") or not hasattr(d, "wholesale_table"):
            return
        count = d.wholesale_table.rowCount()
        d.wholesale_summary_label.setText(f"{count} wholesale tier{'s' if count != 1 else ''} added" if count else "No wholesale tiers")

    def _copy_wholesale_rows(self, source, target):
        target.setRowCount(0)
        for row in range(source.rowCount()):
            target.insertRow(row)
            for col in range(source.columnCount()):
                item = source.item(row, col)
                new_item = QTableWidgetItem(item.text() if item else "")
                if col in (0, 2, 4):
                    new_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                target.setItem(row, col, new_item)

    def _add_wholesale_row_to_table(self, table):
        row = table.rowCount()
        table.insertRow(row)
        defaults = ["6", "pcs", "6", "", "", ""]
        for col, text in enumerate(defaults):
            item = QTableWidgetItem(text)
            if col in (0, 2, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, col, item)

    def open_wholesale_dialog(self):
        d = self.dialog
        colors = get_theme_colors()
        dialog = QDialog(d)
        dialog.setWindowTitle("Manage Wholesale Price Tiers")
        dialog.resize(860, 440)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {colors['bg']};
                color: {colors['text']};
            }}
        """)
        layout = QVBoxLayout(dialog)

        info = QLabel("Set unit price by quantity. Optional barcode adds a whole unit, e.g. pack barcode adds 12 pcs.")
        info.setStyleSheet(f"color: {colors['text_secondary']}; background: transparent; padding: 4px;")
        layout.addWidget(info)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Min Qty", "Unit", "Unit Qty", "Barcode", "Unit Price", "Note"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._copy_wholesale_rows(d.wholesale_table, table)
        layout.addWidget(table)

        button_row = QHBoxLayout()
        btn_add = ModernButton(" Add Tier", ModernButton.PRIMARY)
        btn_add.set_icon("add", size=(16, 16))
        btn_add.set_compact(True)
        btn_remove = ModernButton(" Remove Selected", ModernButton.TERTIARY)
        btn_remove.set_icon("remove", size=(16, 16))
        btn_remove.set_compact(True)
        btn_add.clicked.connect(lambda: self._add_wholesale_row_to_table(table))
        btn_remove.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        btn_cancel.set_icon("close", size=(16, 16))
        btn_cancel.set_compact(True)
        btn_ok = ModernButton(" Save Tiers", ModernButton.PRIMARY)
        btn_ok.set_icon("save", size=(16, 16))
        btn_ok.set_compact(True)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)
        button_row.addWidget(btn_add)
        button_row.addWidget(btn_remove)
        button_row.addStretch()
        button_row.addWidget(btn_cancel)
        button_row.addWidget(btn_ok)
        layout.addLayout(button_row)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._copy_wholesale_rows(table, d.wholesale_table)
            self.update_wholesale_summary()

    def load_wholesale_tiers(self):
        d = self.dialog
        if not hasattr(d, "wholesale_table") or not d.product_id:
            return
        d.wholesale_table.setRowCount(0)
        conn = connect_db()
        cursor = conn.cursor()
        tiers = get_price_tiers(cursor, d.product_id)
        conn.close()
        for tier in tiers:
            if int(tier.get("active", 1)) != 1:
                continue
            self.add_wholesale_row({
                "min_qty": tier["min_qty"],
                "unit_label": tier["unit_label"],
                "unit_multiplier": tier["unit_multiplier"],
                "barcode": tier.get("barcode", ""),
                "unit_price": f"{tier['unit_price']:g}",
                "note": tier["note"],
            })

    def add_restaurant_modifier_row(self, values=None):
        d = self.dialog
        if not hasattr(d, "restaurant_modifiers_table"):
            return
        row = d.restaurant_modifiers_table.rowCount()
        d.restaurant_modifiers_table.insertRow(row)
        if not isinstance(values, dict):
            values = {}
        defaults = [
            values.get("group", "Taste"),
            values.get("name", ""),
            values.get("type", "note"),
            str(values.get("price_delta", "") if values.get("price_delta", 0) else ""),
        ]
        for col, text in enumerate(defaults):
            item = QTableWidgetItem(str(text))
            if col == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            d.restaurant_modifiers_table.setItem(row, col, item)
        self.update_restaurant_modifiers_summary()

    def set_restaurant_modifiers(self, modifiers):
        d = self.dialog
        if not hasattr(d, "restaurant_modifiers_table"):
            return
        d.restaurant_modifiers_table.setRowCount(0)
        for modifier in normalize_modifiers(modifiers):
            self.add_restaurant_modifier_row(modifier)
        self.update_restaurant_modifiers_summary()

    def update_restaurant_modifiers_summary(self):
        d = self.dialog
        if not hasattr(d, "restaurant_summary_label") or not hasattr(d, "restaurant_modifiers_table"):
            return
        modifiers = self._collect_restaurant_modifiers(show_errors=False)
        count = len(modifiers or [])
        if count:
            groups = sorted({modifier["group"] for modifier in modifiers})
            d.restaurant_summary_label.setText(f"{count} option{'s' if count != 1 else ''}: {', '.join(groups)}")
        else:
            d.restaurant_summary_label.setText("Restaurant modifiers not set")

    def _copy_restaurant_modifier_rows(self, source, target):
        target.setRowCount(0)
        for row in range(source.rowCount()):
            target.insertRow(row)
            for col in range(source.columnCount()):
                item = source.item(row, col)
                new_item = QTableWidgetItem(item.text() if item else "")
                if col == 3:
                    new_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                target.setItem(row, col, new_item)

    def _add_default_restaurant_rows_to_table(self, table, defaults=True):
        if defaults:
            source = DEFAULT_RESTAURANT_MODIFIERS
        else:
            source = [{"group": "Taste", "name": "", "type": "note", "price_delta": 0}]
        for values in source:
            row = table.rowCount()
            table.insertRow(row)
            defaults = [
                values.get("group", "Taste"),
                values.get("name", ""),
                values.get("type", "note"),
                str(values.get("price_delta", "") if values.get("price_delta", 0) else ""),
            ]
            for col, text in enumerate(defaults):
                item = QTableWidgetItem(str(text))
                if col == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, col, item)

    def open_restaurant_modifiers_dialog(self):
        d = self.dialog
        colors = get_theme_colors()
        dialog = QDialog(d)
        dialog.setWindowTitle("Manage Restaurant Modifiers")
        dialog.resize(720, 420)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {colors['bg']};
                color: {colors['text']};
            }}
        """)
        layout = QVBoxLayout(dialog)

        info = QLabel("Type: choice = one option per group, note = optional cooking instruction.")
        info.setStyleSheet(f"color: {colors['text_secondary']}; background: transparent; padding: 4px;")
        layout.addWidget(info)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Group", "Option", "Type", "Price +"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._copy_restaurant_modifier_rows(d.restaurant_modifiers_table, table)
        if table.rowCount() == 0:
            self._add_default_restaurant_rows_to_table(table)
        layout.addWidget(table)

        button_row = QHBoxLayout()
        btn_add_default = ModernButton(" Defaults", ModernButton.SECONDARY)
        btn_add_default.set_text_only(True)
        btn_add_default.set_compact(True)
        btn_add = ModernButton(" Add Row", ModernButton.PRIMARY)
        btn_add.set_icon("add", size=(16, 16))
        btn_add.set_compact(True)
        btn_remove = ModernButton(" Remove Selected", ModernButton.TERTIARY)
        btn_remove.set_icon("remove", size=(16, 16))
        btn_remove.set_compact(True)
        btn_add_default.clicked.connect(lambda: self._add_default_restaurant_rows_to_table(table, defaults=True))
        btn_add.clicked.connect(lambda: self._add_default_restaurant_rows_to_table(table, defaults=False))
        btn_remove.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        btn_cancel.set_icon("close", size=(16, 16))
        btn_cancel.set_compact(True)
        btn_ok = ModernButton(" Save Options", ModernButton.PRIMARY)
        btn_ok.set_icon("save", size=(16, 16))
        btn_ok.set_compact(True)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)
        button_row.addWidget(btn_add_default)
        button_row.addWidget(btn_add)
        button_row.addWidget(btn_remove)
        button_row.addStretch()
        button_row.addWidget(btn_cancel)
        button_row.addWidget(btn_ok)
        layout.addLayout(button_row)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._copy_restaurant_modifier_rows(table, d.restaurant_modifiers_table)
            self.update_restaurant_modifiers_summary()

    def _collect_wholesale_tiers(self):
        d = self.dialog
        tiers = []
        if not hasattr(d, "wholesale_table"):
            return tiers
        seen_min_qty = set()
        seen_barcodes = set()
        for row in range(d.wholesale_table.rowCount()):
            def text(col):
                item = d.wholesale_table.item(row, col)
                return item.text().strip() if item else ""
            if not any(text(col) for col in range(d.wholesale_table.columnCount())):
                continue
            try:
                min_qty = int(float(text(0).replace(",", ""))) if text(0) else 1
                unit_multiplier = int(float(text(2).replace(",", ""))) if text(2) else min_qty
                unit_price = float(text(4).replace(",", "")) if text(4) else 0.0
            except ValueError:
                QMessageBox.warning(d, tr("error"), f"Invalid wholesale number at row {row + 1}.")
                return None
            if min_qty < 2:
                QMessageBox.warning(d, tr("error"), f"Wholesale min qty must be at least 2 at row {row + 1}.")
                return None
            if min_qty in seen_min_qty:
                QMessageBox.warning(d, tr("error"), f"Duplicate wholesale min qty: {min_qty}")
                return None
            unit_barcode = text(3)
            if unit_barcode:
                if unit_barcode in seen_barcodes:
                    QMessageBox.warning(d, tr("duplicate_barcode"), f"Duplicate wholesale barcode: {unit_barcode}")
                    return None
                seen_barcodes.add(unit_barcode)
            seen_min_qty.add(min_qty)
            tiers.append({
                "min_qty": min_qty,
                "unit_label": text(1) or "pcs",
                "unit_multiplier": max(1, unit_multiplier),
                "barcode": unit_barcode,
                "unit_price": unit_price,
                "note": text(5),
                "active": 1,
            })
        return sorted(tiers, key=lambda tier: tier["min_qty"])

    def _collect_restaurant_modifiers(self, show_errors=True):
        d = self.dialog
        modifiers = []
        if not hasattr(d, "restaurant_modifiers_table"):
            return modifiers
        seen = set()
        for row in range(d.restaurant_modifiers_table.rowCount()):
            def text(col):
                item = d.restaurant_modifiers_table.item(row, col)
                return item.text().strip() if item else ""
            if not any(text(col) for col in range(d.restaurant_modifiers_table.columnCount())):
                continue
            group = text(0) or "Options"
            name = text(1)
            mod_type = (text(2) or "note").lower()
            if not name:
                if show_errors:
                    QMessageBox.warning(d, tr("error"), f"Restaurant modifier option is required on row {row + 1}.")
                return None
            if mod_type not in {"choice", "note"}:
                if show_errors:
                    QMessageBox.warning(d, tr("error"), f"Type must be choice or note on row {row + 1}.")
                return None
            try:
                price_delta = float(text(3).replace(",", "")) if text(3) else 0.0
            except ValueError:
                if show_errors:
                    QMessageBox.warning(d, tr("error"), f"Price + must be a number on row {row + 1}.")
                return None
            key = (group.lower(), name.lower())
            if key in seen:
                if show_errors:
                    QMessageBox.warning(d, tr("error"), f"Duplicate restaurant option: {group} / {name}")
                return None
            seen.add(key)
            modifiers.append({
                "group": group,
                "name": name,
                "type": mod_type,
                "price_delta": price_delta,
            })
        return modifiers

    def _copy_table_rows(self, source, target):
        target.setRowCount(0)
        for row in range(source.rowCount()):
            target.insertRow(row)
            for col in range(source.columnCount()):
                item = source.item(row, col)
                new_item = QTableWidgetItem(item.text() if item else "")
                if col in (4, 5):
                    new_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                target.setItem(row, col, new_item)

    def _add_variant_row_to_table(self, table):
        row = table.rowCount()
        table.insertRow(row)
        defaults = ["", "", self.generate_variant_sku(row + 1), "", "", ""]
        for col, text in enumerate(defaults):
            item = QTableWidgetItem(text)
            if col in (4, 5):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, col, item)

    def open_variants_dialog(self):
        d = self.dialog
        colors = get_theme_colors()
        dialog = QDialog(d)
        dialog.setWindowTitle("Manage Variants")
        dialog.resize(760, 420)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {colors['bg']};
                color: {colors['text']};
            }}
        """)
        layout = QVBoxLayout(dialog)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Size", "Color", "SKU", "Barcode", "Price", "Stock Alert"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._copy_table_rows(d.variants_table, table)
        layout.addWidget(table)

        button_row = QHBoxLayout()
        btn_add = ModernButton(" Add Variant", ModernButton.PRIMARY)
        btn_add.set_icon("add", size=(16, 16))
        btn_add.set_compact(True)
        btn_remove = ModernButton(" Remove Selected", ModernButton.TERTIARY)
        btn_remove.set_icon("remove", size=(16, 16))
        btn_remove.set_compact(True)
        btn_add.clicked.connect(lambda: self._add_variant_row_to_table(table))
        btn_remove.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        btn_cancel.set_icon("close", size=(16, 16))
        btn_cancel.set_compact(True)
        btn_ok = ModernButton(" Save Variants", ModernButton.PRIMARY)
        btn_ok.set_icon("save", size=(16, 16))
        btn_ok.set_compact(True)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)
        button_row.addWidget(btn_add)
        button_row.addWidget(btn_remove)
        button_row.addStretch()
        button_row.addWidget(btn_cancel)
        button_row.addWidget(btn_ok)
        layout.addLayout(button_row)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._copy_table_rows(table, d.variants_table)
            self.update_variants_summary()

    def load_variants(self):
        """Load product variants into the editor."""
        d = self.dialog
        if not hasattr(d, "variants_table") or not d.product_id:
            return
        d.variants_table.setRowCount(0)
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT size, color, sku, barcode, price, low_stock
            FROM product_variants
            WHERE product_id = ?
            ORDER BY size, color, id
        """, (d.product_id,))
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            self.add_variant_row({
                "size": row[0] or "",
                "color": row[1] or "",
                "sku": row[2] or "",
                "barcode": row[3] or "",
                "price": row[4] or "",
                "low_stock": row[5] or 0,
            })

    def _collect_variants(self):
        d = self.dialog
        variants = []
        if not hasattr(d, "variants_table"):
            return variants
        for row in range(d.variants_table.rowCount()):
            def text(col):
                item = d.variants_table.item(row, col)
                return item.text().strip() if item else ""
            size = text(0)
            color = text(1)
            sku = text(2)
            barcode = text(3)
            price_text = text(4)
            low_stock_text = text(5)
            if not any([size, color, sku, barcode, price_text, low_stock_text]):
                continue
            try:
                price = float(price_text.replace(",", "")) if price_text else 0.0
                low_stock = int(float(low_stock_text.replace(",", ""))) if low_stock_text else 0
            except ValueError:
                QMessageBox.warning(d, tr("error"), f"Invalid variant number at row {row + 1}.")
                return None
            variants.append({
                "size": size,
                "color": color,
                "sku": sku,
                "barcode": barcode,
                "price": price,
                "cost": 0.0,
                "stock": 0,
                "low_stock": max(0, low_stock),
                "image": self.normalize_product_image_path(self.image_path),
                "active": 1,
            })
        return variants

    def _save_variants(self, cursor, product_id, variants):
        cursor.execute("""
            SELECT sku, barcode, stock
            FROM product_variants
            WHERE product_id = ?
        """, (product_id,))
        existing_stock = {}
        for sku, barcode, stock in cursor.fetchall():
            if sku:
                existing_stock[("sku", sku)] = int(stock or 0)
            if barcode:
                existing_stock[("barcode", barcode)] = int(stock or 0)
        cursor.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        for variant in variants:
            variant_stock = 0
            if variant["sku"] and ("sku", variant["sku"]) in existing_stock:
                variant_stock = existing_stock[("sku", variant["sku"])]
            elif variant["barcode"] and ("barcode", variant["barcode"]) in existing_stock:
                variant_stock = existing_stock[("barcode", variant["barcode"])]
            cursor.execute("""
                INSERT INTO product_variants
                (product_id, size, color, sku, barcode, price, cost, stock, low_stock, image, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_id,
                variant["size"],
                variant["color"],
                variant["sku"],
                variant["barcode"],
                variant["price"],
                variant["cost"],
                variant_stock,
                variant["low_stock"],
                variant["image"],
                variant["active"],
            ))
        if variants:
            cursor.execute("SELECT COALESCE(SUM(stock), 0) FROM product_variants WHERE product_id = ? AND COALESCE(active, 1) = 1", (product_id,))
            total_stock = int(cursor.fetchone()[0] or 0)
            cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (total_stock, product_id))
    
    def select_image(self):
        """Select product image"""
        d = self.dialog
        file_name, _ = QFileDialog.getOpenFileName(
            d, tr("select_product_image"), "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_name:
            self.image_path = file_name
            d.image_input.setText(file_name)
            self.update_image_preview()
    
    def update_image_preview(self):
        """Update the image preview label"""
        d = self.dialog
        if self.image_path and os.path.exists(self.image_path):
            try:
                pixmap = QPixmap(self.image_path)
                if not pixmap.isNull():
                    preview_width = d.image_preview.width() - 40
                    preview_height = d.image_preview.height() - 40
                    
                    if preview_width > 0 and preview_height > 0:
                        scaled_pixmap = pixmap.scaled(
                            preview_width,
                            preview_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        d.image_preview.setPixmap(scaled_pixmap)
                        d.image_preview.setText("")
                    return
            except Exception:
                pass
        
        d.image_preview.setText("No Image\n\nSelect an image to preview")
        d.image_preview.setPixmap(QPixmap())
    
    def normalize_product_image_path(self, image_path):
        """Normalize and optimize image path"""
        if not image_path:
            return ""
        if not os.path.exists(image_path):
            return image_path
        
        optimized_path = ImageOptimizer.optimize_image(
            image_path,
            output_size=(400, 400),
            quality=80,
            output_format='JPEG'
        )
        if optimized_path:
            filename = os.path.basename(optimized_path)
            relative_path = os.path.join('database', 'product_images', filename)
            return relative_path
        return image_path
    
    def generate_sku(self):
        """Generate a new SKU"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products ORDER BY id DESC LIMIT 1")
        last = cursor.fetchone()
        conn.close()
        next_id = last[0] + 1 if last else 1
        return f"ITM-{next_id:05d}"
    
    def is_service_selected(self):
        """Check if service is selected"""
        return self.get_sold_by_mode() == "Service"

    def is_variants_selected(self):
        """Check if variants mode is selected."""
        return self.get_sold_by_mode() == "Variants"

    def is_restaurant_selected(self):
        """Check if restaurant menu mode is selected."""
        return self.get_sold_by_mode() == "Restaurant"

    def get_sold_by_mode(self):
        data = self.dialog.sold_by_combo.currentData()
        return data or self.dialog.sold_by_combo.currentText()
    
    def toggle_service_fields(self, *_):
        """Toggle fields based on sold by selection"""
        d = self.dialog
        is_service = self.is_service_selected()
        is_variants = self.is_variants_selected()
        is_restaurant = self.is_restaurant_selected()

        d.label_barcode.setVisible(not is_variants and not is_restaurant)
        d.barcode_input.setVisible(not is_variants and not is_restaurant)
        d.barcode_input.setEnabled(not is_variants and not is_restaurant)

        d.label_price.setVisible(not is_service and not is_variants)
        d.price_widget.setVisible(not is_service and not is_variants)
        d.price_input.setEnabled(not is_service and not is_variants)

        d.label_low_stock.setVisible(not is_service and not is_variants and not is_restaurant)
        d.low_stock_input.setVisible(not is_service and not is_variants and not is_restaurant)
        d.low_stock_input.setEnabled(not is_service and not is_variants and not is_restaurant)

        has_variants_ui = hasattr(d, "variants_widget")
        if has_variants_ui:
            d.label_variants.setVisible(is_variants)
            d.variants_widget.setVisible(is_variants)
        has_wholesale_ui = hasattr(d, "wholesale_widget")
        if has_wholesale_ui:
            d.label_wholesale.setVisible(not is_service and not is_variants and not is_restaurant)
            d.wholesale_widget.setVisible(not is_service and not is_variants and not is_restaurant)
        has_units_ui = hasattr(d, "units_widget")
        if has_units_ui:
            d.label_units.setVisible(not is_service and not is_variants and not is_restaurant)
            d.units_widget.setVisible(not is_service and not is_variants and not is_restaurant)
        has_restaurant_ui = hasattr(d, "restaurant_options_widget")
        if has_restaurant_ui:
            d.label_restaurant_options.setVisible(is_restaurant)
            d.restaurant_options_widget.setVisible(is_restaurant)
        
        if is_service:
            d.price_input.setValue(0.0)
            d.low_stock_input.setValue(0)
            d.info_label.setText("This is a service product (no stock tracking)")
            d.info_label.setStyleSheet("color: #e67e22; font-size: 9pt; padding: 6px 12px; background: #fef9e7; border-radius: 4px;")
        elif is_variants:
            d.info_label.setText("Use variants to set size/color barcode, price, and stock.")
            d.info_label.setStyleSheet("color: #5865f2; font-size: 9pt; padding: 6px 12px; background: #ebf5fb; border-radius: 4px;")
        elif is_restaurant:
            d.info_label.setText("Restaurant menu item: fixed price with cooking modifiers.")
            d.info_label.setStyleSheet("color: #16a085; font-size: 9pt; padding: 6px 12px; background: #eafaf1; border-radius: 4px;")
            if hasattr(d, "restaurant_modifiers_table") and d.restaurant_modifiers_table.rowCount() == 0:
                self.set_restaurant_modifiers(DEFAULT_RESTAURANT_MODIFIERS)
        else:
            d.info_label.setText("Set low stock alert level to get notifications")
            d.info_label.setStyleSheet("color: #5865f2; font-size: 9pt; padding: 6px 12px; background: #ebf5fb; border-radius: 4px;")
    
    def on_barcode_entered(self):
        """Handle barcode entry"""
        d = self.dialog
        barcode = d.barcode_input.text().strip()
        
        if barcode:
            conn = connect_db()
            cursor = conn.cursor()
            product_id = d.product_id if d.product_id else -1
            cursor.execute(
                "SELECT id, name FROM products WHERE barcode = ? AND id != ?",
                (barcode, product_id)
            )
            existing = cursor.fetchone()
            conn.close()
            
            if existing:
                QMessageBox.warning(
                    d,
                    tr("duplicate_barcode"),
                    tr("barcode_exists_for_product").format(barcode=barcode, product=existing[1])
                )
                d.barcode_input.selectAll()
                return
            
            d.barcode_input.setFocus()
            d.barcode_input.selectAll()
            colors = get_theme_colors()
            d.barcode_input.setStyleSheet(f"""
                QLineEdit {{
                    padding: 6px 10px;
                    border: 2px solid #27ae60;
                    border-radius: 6px;
                    background: transparent;
                    color: {colors['text']};
                    font-size: 10pt;
                }}
                QLineEdit::placeholder {{
                    color: {colors['text_secondary']};
                }}
            """)
            QTimer.singleShot(
                300,
                lambda: d.barcode_input.setStyleSheet(
                    ProductFormUIStyles.get_input_style(get_theme_colors())
                )
            )
    
    def update_product_details(self):
        """Update the product details preview"""
        d = self.dialog
        name = d.name_input.text().strip()
        category = d.category_combo.currentText()
        price = d.price_input.value()
        sold_by = d.sold_by_combo.currentText()
        low_stock = d.low_stock_input.value()
        base_unit = d.base_unit_input.text().strip() if hasattr(d, "base_unit_input") else "pcs"
        pack_unit = d.pack_unit_input.text().strip() if hasattr(d, "pack_unit_input") else ""
        pack_size = d.pack_size_input.value() if hasattr(d, "pack_size_input") else 1
        unit_line = ""
        if pack_unit and pack_size > 1 and not (self.is_service_selected() or self.is_variants_selected()):
            unit_line = f"<span style='color:#5d6d7e;'>Pack:</span> <b>1 {pack_unit} = {pack_size} {base_unit or 'pcs'}</b><br>"
        if self.is_service_selected():
            price_line = "<span style='color:#5d6d7e;'>Price:</span> <b>Manual at sale</b><br>"
            stock_line = "<span style='color:#5d6d7e;'>Stock:</span> <b>Not tracked</b>"
        elif self.is_variants_selected():
            variant_count = d.variants_table.rowCount() if hasattr(d, "variants_table") else 0
            price_line = "<span style='color:#5d6d7e;'>Price:</span> <b>By variant</b><br>"
            stock_line = f"<span style='color:#5d6d7e;'>Variants:</span> <b>{variant_count}</b>"
        elif self.is_restaurant_selected():
            modifier_count = len(self._collect_restaurant_modifiers(show_errors=False) or [])
            price_line = f"<span style='color:#5d6d7e;'>Menu Price:</span> <b style='color:#27ae60;'>{price:,.0f} MMK</b><br>"
            stock_line = f"<span style='color:#5d6d7e;'>Modifiers:</span> <b>{modifier_count}</b>"
        else:
            price_line = f"<span style='color:#5d6d7e;'>Price:</span> <b style='color:#27ae60;'>{price:,.0f} MMK</b><br>"
            stock_line = f"<span style='color:#5d6d7e;'>Low Stock Alert:</span> <b>{low_stock}</b>"
        
        details = f"""
<b style='font-size:11pt;'>{name or 'Product Name'}</b><br>
<span style='color:#5d6d7e;'>Category:</span> <b>{category or 'Not set'}</b><br>
{price_line}
<span style='color:#5d6d7e;'>Sold By:</span> <b>{sold_by}</b><br>
{unit_line}
{stock_line}
        """
        d.product_details_label.setText(details)
    
    def save(self):
        """Save product"""
        d = self.dialog
        is_service = self.is_service_selected()
        is_variants = self.is_variants_selected()
        is_restaurant = self.is_restaurant_selected()
        
        # Validate
        name = d.name_input.text().strip()
        if not name:
            QMessageBox.warning(d, tr("error"), tr("product_name_required"))
            d.name_input.setFocus()
            return
        
        # Check barcode
        barcode = "" if is_service or is_variants or is_restaurant else d.barcode_input.text().strip()
        if barcode:
            conn = connect_db()
            cursor = conn.cursor()
            product_id = d.product_id if d.product_id else -1
            cursor.execute(
                "SELECT id FROM products WHERE barcode = ? AND id != ?",
                (barcode, product_id)
            )
            existing = cursor.fetchone()
            if not existing:
                cursor.execute("""
                    SELECT product_id FROM product_variants
                    WHERE barcode = ? AND product_id != ?
                """, (barcode, product_id))
                existing = cursor.fetchone()
            if not existing:
                ensure_wholesale_schema(cursor)
                cursor.execute("""
                    SELECT product_id FROM product_price_tiers
                    WHERE barcode = ? AND product_id != ?
                """, (barcode, product_id))
                existing = cursor.fetchone()
            conn.close()
            
            if existing:
                QMessageBox.warning(d, tr("duplicate_barcode"), tr("barcode_exists").format(barcode=barcode))
                d.barcode_input.setFocus()
                d.barcode_input.selectAll()
                return

        variants = self._collect_variants() if is_variants else []
        if variants is None:
            return
        wholesale_tiers = [] if (is_service or is_variants or is_restaurant) else self._collect_wholesale_tiers()
        if wholesale_tiers is None:
            return
        restaurant_modifiers = self._collect_restaurant_modifiers() if is_restaurant else []
        if restaurant_modifiers is None:
            return
        if is_variants and not variants:
            QMessageBox.warning(d, tr("error"), "Please add at least one variant.")
            return
        wholesale_barcodes = {tier["barcode"] for tier in wholesale_tiers if tier.get("barcode")}
        if barcode and barcode in wholesale_barcodes:
            QMessageBox.warning(d, tr("duplicate_barcode"), f"Wholesale barcode duplicates product barcode: {barcode}")
            return
        seen_variant_barcodes = set()
        seen_variant_skus = set()
        for variant in variants:
            v_barcode = variant["barcode"]
            v_sku = variant["sku"]
            if v_barcode:
                if v_barcode == barcode or v_barcode in seen_variant_barcodes or v_barcode in wholesale_barcodes:
                    QMessageBox.warning(d, tr("duplicate_barcode"), f"Duplicate variant barcode: {v_barcode}")
                    return
                seen_variant_barcodes.add(v_barcode)
            if v_sku:
                if v_sku in seen_variant_skus:
                    QMessageBox.warning(d, tr("error"), f"Duplicate variant SKU: {v_sku}")
                    return
                seen_variant_skus.add(v_sku)
        barcodes_to_check = set(seen_variant_barcodes) | wholesale_barcodes
        if barcodes_to_check:
            conn = connect_db()
            cursor = conn.cursor()
            product_id = d.product_id if d.product_id else -1
            placeholders = ",".join(["?"] * len(barcodes_to_check))
            values = list(barcodes_to_check)
            cursor.execute(
                f"SELECT barcode FROM products WHERE barcode IN ({placeholders}) AND id != ?",
                values + [product_id],
            )
            duplicate = cursor.fetchone()
            if not duplicate:
                cursor.execute(
                    f"SELECT barcode FROM product_variants WHERE barcode IN ({placeholders}) AND product_id != ?",
                    values + [product_id],
                )
                duplicate = cursor.fetchone()
            if not duplicate:
                ensure_wholesale_schema(cursor)
                cursor.execute(
                    f"SELECT barcode FROM product_price_tiers WHERE barcode IN ({placeholders}) AND product_id != ?",
                    values + [product_id],
                )
                duplicate = cursor.fetchone()
            conn.close()
            if duplicate:
                QMessageBox.warning(d, tr("duplicate_barcode"), f"Barcode already exists: {duplicate[0]}")
                return
        
        # Process image
        image_path = self.normalize_product_image_path(self.image_path)
        category_name = d.category_combo.currentText()
        category_id = d.category_combo.currentData()
        units = normalize_unit_settings(
            d.base_unit_input.text() if hasattr(d, "base_unit_input") else None,
            d.pack_unit_input.text() if hasattr(d, "pack_unit_input") else None,
            d.pack_size_input.value() if hasattr(d, "pack_size_input") else None,
        )
        if is_service or is_variants or is_restaurant:
            units = normalize_unit_settings()
        if not category_id and category_name:
            lookup_conn = connect_db()
            lookup_cursor = lookup_conn.cursor()
            lookup_cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            category_row = lookup_cursor.fetchone()
            lookup_conn.close()
            category_id = category_row[0] if category_row else None
        
        # Save to database
        conn = connect_db()
        cursor = conn.cursor()
        ensure_unit_conversion_schema(cursor)
        ensure_restaurant_modifier_schema(cursor)
        
        if d.product_id is None:
            sku = self.generate_sku()
            cursor.execute("""
                INSERT INTO products (name, category, description, sold_by, price, cost, sku,
                                      barcode, stock, low_stock, expire_date, image, category_id,
                                      base_unit, pack_unit, pack_size, restaurant_modifiers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                category_name,
                d.description_input.toPlainText(),
                self.get_sold_by_mode(),
                0.0 if (is_service or is_variants) else d.price_input.value(),
                0.0,  # cost
                sku,
                barcode,
                0,
                0 if (is_service or is_variants or is_restaurant) else d.low_stock_input.value(),
                None,  # expire_date
                image_path,
                category_id,
                units["base_unit"],
                units["pack_unit"],
                units["pack_size"],
                dumps_modifiers(restaurant_modifiers),
            ))
            product_id = cursor.lastrowid
            msg = tr("product_saved")
        else:
            cursor.execute("""
                UPDATE products SET name=?, category=?, category_id=?, barcode=?, description=?, sold_by=?,
                price=?, low_stock=?, image=?, base_unit=?, pack_unit=?, pack_size=?, restaurant_modifiers=?
                WHERE id=?
            """, (
                name,
                category_name,
                category_id,
                barcode,
                d.description_input.toPlainText(),
                self.get_sold_by_mode(),
                0.0 if (is_service or is_variants) else d.price_input.value(),
                0 if (is_service or is_variants or is_restaurant) else d.low_stock_input.value(),
                image_path,
                units["base_unit"],
                units["pack_unit"],
                units["pack_size"],
                dumps_modifiers(restaurant_modifiers),
                d.product_id
            ))
            product_id = d.product_id
            msg = tr("product_updated")
        
        if is_variants:
            self._save_variants(cursor, product_id, variants)
        elif is_service or d.product_id is not None:
            cursor.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        save_price_tiers(cursor, product_id, [] if is_restaurant else wholesale_tiers)
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(d, tr("success"), msg)
        d.accept()
    
    def get_lang(self):
        """Get current language"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
