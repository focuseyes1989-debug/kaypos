# ui/products_page/product_form_handlers.py
from PyQt6.QtWidgets import (
    QMessageBox, QFileDialog, QTableWidgetItem, QDialog, QVBoxLayout,
    QHBoxLayout, QTableWidget, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon
from models.database import connect_db
from utils.translations import tr
from utils.language import lang
from utils.paths import app_path
from utils.image_optimizer import ImageOptimizer
from ui.widgets.modern_button import ModernButton
from ui.products_page.product_form_ui_styles import ProductFormUIStyles
from ui.themes.theme_manager import get_theme_colors
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
        d.language_combo.currentIndexChanged.connect(self.on_language_changed)
        d.barcode_input.returnPressed.connect(self.on_barcode_entered)
        if hasattr(d, "btn_manage_variants"):
            d.btn_manage_variants.clicked.connect(self.open_variants_dialog)
        
        # Speech buttons
        self.setup_speech_buttons()

    def ensure_variant_schema(self):
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
        conn.commit()
        conn.close()
    
    def setup_speech_buttons(self):
        """Setup speech-to-text functionality"""
        from utils.speech_to_text import SpeechButton
        
        d = self.dialog
        language = d.language_combo.currentData()
        
        # Speech button for product name
        self.speech_handler_name = SpeechButton(
            parent=d,
            text_input=d.name_input,
            duration=4,
            language=language
        )
        d.btn_speech.clicked.connect(self.speech_handler_name.toggle_recording)
        
        # Speech button for description
        self.speech_handler_desc = SpeechButton(
            parent=d,
            text_input=d.description_input,
            duration=6,
            language=language
        )
        d.btn_speech_desc.clicked.connect(self.speech_handler_desc.toggle_recording)
    
    def load_categories(self):
        """Load categories from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        rows = cursor.fetchall()
        
        d = self.dialog
        d.category_combo.clear()
        for (name,) in rows:
            d.category_combo.addItem(name)
        conn.close()
    
    def load_product_data(self):
        """Load product data for editing"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, category, barcode, description, sold_by, price,
                   low_stock, image
            FROM products WHERE id=?
        """, (self.dialog.product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            d = self.dialog
            d.name_input.setText(row[0])
            
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
            
            # Update image preview
            self.update_image_preview()
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

        actions = QHBoxLayout()
        actions.addStretch()
        btn_add = ModernButton(" Add Variant", ModernButton.PRIMARY)
        btn_add.set_icon("add", size=(16, 16))
        btn_add.set_compact(True)
        btn_remove = ModernButton(" Remove Selected", ModernButton.TERTIARY)
        btn_remove.set_icon("remove", size=(16, 16))
        btn_remove.set_compact(True)
        btn_add.clicked.connect(lambda: self._add_variant_row_to_table(table))
        btn_remove.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        actions.addWidget(btn_add)
        actions.addWidget(btn_remove)
        layout.addLayout(actions)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        btn_cancel.set_icon("close", size=(16, 16))
        btn_cancel.set_compact(True)
        btn_ok = ModernButton(" Save Variants", ModernButton.PRIMARY)
        btn_ok.set_icon("save", size=(16, 16))
        btn_ok.set_compact(True)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_ok)
        layout.addLayout(buttons)

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

    def get_sold_by_mode(self):
        data = self.dialog.sold_by_combo.currentData()
        return data or self.dialog.sold_by_combo.currentText()
    
    def toggle_service_fields(self, *_):
        """Toggle fields based on sold by selection"""
        d = self.dialog
        is_service = self.is_service_selected()
        is_variants = self.is_variants_selected()

        d.label_barcode.setVisible(not is_variants)
        d.barcode_input.setVisible(not is_variants)
        d.barcode_input.setEnabled(not is_variants)

        d.label_price.setVisible(not is_service)
        d.label_price.setVisible(not is_service and not is_variants)
        d.price_widget.setVisible(not is_service and not is_variants)
        d.price_input.setEnabled(not is_service and not is_variants)

        d.label_low_stock.setVisible(not is_service and not is_variants)
        d.low_stock_input.setVisible(not is_service and not is_variants)
        d.low_stock_input.setEnabled(not is_service and not is_variants)

        has_variants_ui = hasattr(d, "variants_widget")
        if has_variants_ui:
            d.label_variants.setVisible(is_variants)
            d.variants_widget.setVisible(is_variants)
        
        if is_service:
            d.price_input.setValue(0.0)
            d.low_stock_input.setValue(0)
            d.info_label.setText("This is a service product (no stock tracking)")
            d.info_label.setStyleSheet("color: #e67e22; font-size: 9pt; padding: 6px 12px; background: #fef9e7; border-radius: 4px;")
        elif is_variants:
            d.info_label.setText("Use variants to set size/color barcode, price, and stock.")
            d.info_label.setStyleSheet("color: #5865f2; font-size: 9pt; padding: 6px 12px; background: #ebf5fb; border-radius: 4px;")
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
            d.barcode_input.setStyleSheet("border: 2px solid #27ae60; border-radius: 6px; padding: 10px 12px;")
            QTimer.singleShot(300, lambda: d.barcode_input.setStyleSheet("""
                QLineEdit {
                    padding: 10px 12px;
                    border: 1px solid #dfe6e9;
                    border-radius: 6px;
                    background: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border-color: #5865f2;
                }
            """))
    
    def on_language_changed(self):
        """Handle language selection change"""
        d = self.dialog
        language = d.language_combo.currentData()
        
        if hasattr(self, 'speech_handler_name'):
            self.speech_handler_name.set_language(language)
        
        if hasattr(self, 'speech_handler_desc'):
            self.speech_handler_desc.set_language(language)
        
        self.update_speech_tooltips(language)
    
    def update_speech_tooltips(self, language):
        """Update speech button tooltips"""
        d = self.dialog
        lang_text = "မြန်မာ" if language == "my" else "English"
        
        if language == "my":
            d.btn_speech.setToolTip(f"ပစ္စည်းအမည် အသံဖြင့်ရိုက်ရန် ({lang_text})")
            d.btn_speech_desc.setToolTip(f"ဖော်ပြချက် အသံဖြင့်ရိုက်ရန် ({lang_text})")
        else:
            d.btn_speech.setToolTip(f"Speak product name ({lang_text})")
            d.btn_speech_desc.setToolTip(f"Speak description ({lang_text})")
    
    def update_product_details(self):
        """Update the product details preview"""
        d = self.dialog
        name = d.name_input.text().strip()
        category = d.category_combo.currentText()
        price = d.price_input.value()
        sold_by = d.sold_by_combo.currentText()
        low_stock = d.low_stock_input.value()
        if self.is_service_selected():
            price_line = "<span style='color:#5d6d7e;'>Price:</span> <b>Manual at sale</b><br>"
            stock_line = "<span style='color:#5d6d7e;'>Stock:</span> <b>Not tracked</b>"
        elif self.is_variants_selected():
            variant_count = d.variants_table.rowCount() if hasattr(d, "variants_table") else 0
            price_line = "<span style='color:#5d6d7e;'>Price:</span> <b>By variant</b><br>"
            stock_line = f"<span style='color:#5d6d7e;'>Variants:</span> <b>{variant_count}</b>"
        else:
            price_line = f"<span style='color:#5d6d7e;'>Price:</span> <b style='color:#27ae60;'>{price:,.0f} MMK</b><br>"
            stock_line = f"<span style='color:#5d6d7e;'>Low Stock Alert:</span> <b>{low_stock}</b>"
        
        details = f"""
<b style='font-size:11pt;'>{name or 'Product Name'}</b><br>
<span style='color:#5d6d7e;'>Category:</span> <b>{category or 'Not set'}</b><br>
{price_line}
<span style='color:#5d6d7e;'>Sold By:</span> <b>{sold_by}</b><br>
{stock_line}
        """
        d.product_details_label.setText(details)
    
    def save(self):
        """Save product"""
        d = self.dialog
        is_service = self.is_service_selected()
        is_variants = self.is_variants_selected()
        
        # Validate
        name = d.name_input.text().strip()
        if not name:
            QMessageBox.warning(d, tr("error"), tr("product_name_required"))
            d.name_input.setFocus()
            return
        
        # Check barcode
        barcode = "" if is_service or is_variants else d.barcode_input.text().strip()
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
            conn.close()
            
            if existing:
                QMessageBox.warning(d, tr("duplicate_barcode"), tr("barcode_exists").format(barcode=barcode))
                d.barcode_input.setFocus()
                d.barcode_input.selectAll()
                return

        variants = self._collect_variants() if is_variants else []
        if variants is None:
            return
        if is_variants and not variants:
            QMessageBox.warning(d, tr("error"), "Please add at least one variant.")
            return
        seen_variant_barcodes = set()
        seen_variant_skus = set()
        for variant in variants:
            v_barcode = variant["barcode"]
            v_sku = variant["sku"]
            if v_barcode:
                if v_barcode == barcode or v_barcode in seen_variant_barcodes:
                    QMessageBox.warning(d, tr("duplicate_barcode"), f"Duplicate variant barcode: {v_barcode}")
                    return
                seen_variant_barcodes.add(v_barcode)
            if v_sku:
                if v_sku in seen_variant_skus:
                    QMessageBox.warning(d, tr("error"), f"Duplicate variant SKU: {v_sku}")
                    return
                seen_variant_skus.add(v_sku)
        if seen_variant_barcodes:
            conn = connect_db()
            cursor = conn.cursor()
            product_id = d.product_id if d.product_id else -1
            placeholders = ",".join(["?"] * len(seen_variant_barcodes))
            values = list(seen_variant_barcodes)
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
            conn.close()
            if duplicate:
                QMessageBox.warning(d, tr("duplicate_barcode"), f"Barcode already exists: {duplicate[0]}")
                return
        
        # Process image
        image_path = self.normalize_product_image_path(self.image_path)
        
        # Save to database
        conn = connect_db()
        cursor = conn.cursor()
        
        if d.product_id is None:
            sku = self.generate_sku()
            cursor.execute("""
                INSERT INTO products (name, category, description, sold_by, price, cost, sku,
                                      barcode, stock, low_stock, expire_date, image)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                d.category_combo.currentText(),
                d.description_input.toPlainText(),
                self.get_sold_by_mode(),
                0.0 if (is_service or is_variants) else d.price_input.value(),
                0.0,  # cost
                sku,
                barcode,
                0,
                0 if (is_service or is_variants) else d.low_stock_input.value(),
                None,  # expire_date
                image_path
            ))
            product_id = cursor.lastrowid
            msg = tr("product_saved")
        else:
            cursor.execute("""
                UPDATE products SET name=?, category=?, barcode=?, description=?, sold_by=?,
                price=?, low_stock=?, image=?
                WHERE id=?
            """, (
                name,
                d.category_combo.currentText(),
                barcode,
                d.description_input.toPlainText(),
                self.get_sold_by_mode(),
                0.0 if (is_service or is_variants) else d.price_input.value(),
                0 if (is_service or is_variants) else d.low_stock_input.value(),
                image_path,
                d.product_id
            ))
            product_id = d.product_id
            msg = tr("product_updated")
        
        if is_variants:
            self._save_variants(cursor, product_id, variants)
        elif is_service or d.product_id is not None:
            cursor.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        
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
