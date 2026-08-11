from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QPixmap

from loguru import logger

from models.database import connect_db, safe_initialize_postgres_pilot_database
from utils.db_compat import is_postgres_backend
from ui.themes.theme_manager import get_theme_colors, theme_manager
from ui.widgets.action_toolbar import ActionToolbar
from ui.widgets.modern_button import ModernButton


class DiscountPage(QWidget):
    """Product discount campaigns by product, date range, and percentage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_discount_id = None
        self.selected_discount_kind = None
        self._products = []
        self._ensure_table()
        self._setup_ui()
        self.load_products()
        self.load_discounts()
        theme_manager.theme_changed.connect(self.update_theme)

    def _ensure_table(self):
        if is_postgres_backend():
            safe_initialize_postgres_pilot_database()
            return

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                discount_percent REAL NOT NULL DEFAULT 0,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_discounts_product ON product_discounts(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_discounts_dates ON product_discounts(start_date, end_date)")
        cursor.execute("PRAGMA table_info(product_discounts)")
        discount_columns = {row[1] for row in cursor.fetchall()}
        for column, definition in {
            "discount_type": "TEXT DEFAULT 'percentage'",
            "manual_price": "REAL DEFAULT 0",
        }.items():
            if column not in discount_columns:
                cursor.execute(f"ALTER TABLE product_discounts ADD COLUMN {column} {definition}")
        cursor.execute("PRAGMA table_info(product_locations)")
        pl_columns = {row[1] for row in cursor.fetchall()}
        for column, definition in {
            "expiry_discount_enabled": "INTEGER DEFAULT 0",
            "expiry_discount_percent": "REAL DEFAULT 0",
            "expiry_discount_start_date": "TEXT",
            "expiry_discount_end_date": "TEXT",
            "clearance_note": "TEXT",
        }.items():
            if column not in pl_columns:
                cursor.execute(f"ALTER TABLE product_locations ADD COLUMN {column} {definition}")
        conn.commit()
        conn.close()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search product or note...")
        self.search_input.textChanged.connect(self.load_discounts)
        top.addWidget(self.search_input, 1)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active Now", "Scheduled", "Expired", "Disabled"])
        self.status_filter.currentTextChanged.connect(self.load_discounts)
        top.addWidget(self.status_filter)

        self.action_toolbar = ActionToolbar(self)
        self.btn_add = self.action_toolbar.add_primary(" Add", self.add_discount, "add", width=86, stretch=False)
        self.btn_edit = self.action_toolbar.add_primary(" Edit", self.edit_discount, "edit", ModernButton.SECONDARY, width=86, stretch=False)
        self.btn_edit.setEnabled(False)
        self.action_delete = self.action_toolbar.add_more_action("Delete", self.delete_discount, "delete", enabled=False)
        self.action_toggle = self.action_toolbar.add_more_action("Enable / Disable", self.toggle_discount, "active", enabled=False)
        self.action_toolbar.finalize()
        top.addWidget(self.action_toolbar, 0)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Type", "Product", "SKU", "Discount", "Start", "End", "Status", "Note"
        ])
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        layout.addWidget(self.table)
        self.update_theme()

    def update_theme(self, *_):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {colors.get('bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
            }}
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {{
                background-color: {colors.get('card_bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 5px;
                padding: 6px 8px;
            }}
            QTableWidget {{
                background-color: {colors.get('card_bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
                gridline-color: {colors.get('border', '#dee2e6')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 6px;
            }}
        """)
        if hasattr(self, "action_toolbar"):
            self.action_toolbar.update_theme()

    def load_products(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, COALESCE(sku, ''), COALESCE(price, 0)
            FROM products
            WHERE sold_by IS NULL OR sold_by != 'Service'
            ORDER BY name
        """)
        self._products = cursor.fetchall()
        conn.close()

    def load_discounts(self):
        search = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        status = self.status_filter.currentText() if hasattr(self, "status_filter") else "All"
        today = QDate.currentDate().toString("yyyy-MM-dd")

        query = """
            SELECT d.id, p.name, COALESCE(p.sku, ''), d.discount_percent,
                   COALESCE(d.discount_type, 'percentage'), COALESCE(d.manual_price, 0),
                   d.start_date, d.end_date, d.active, COALESCE(d.note, '')
            FROM product_discounts d
            JOIN products p ON p.id = d.product_id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.sku, '')) LIKE ? OR LOWER(COALESCE(d.note, '')) LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        if status == "Active Now":
            query += " AND d.active = 1 AND d.start_date <= ? AND d.end_date >= ?"
            params.extend([today, today])
        elif status == "Scheduled":
            query += " AND d.active = 1 AND d.start_date > ?"
            params.append(today)
        elif status == "Expired":
            query += " AND d.end_date < ?"
            params.append(today)
        elif status == "Disabled":
            query += " AND d.active = 0"
        query += " ORDER BY d.active DESC, d.start_date DESC, p.name"

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(query, params)
        promo_rows = cursor.fetchall()
        expiry_query = """
            SELECT pl.id, p.name, COALESCE(p.sku, ''), pl.expiry_discount_percent,
                   COALESCE(pl.expiry_discount_start_date, '') as start_date,
                   COALESCE(NULLIF(pl.expiry_discount_end_date, ''), pl.expire_date, '') as end_date,
                   COALESCE(pl.expiry_discount_enabled, 0), COALESCE(pl.clearance_note, ''),
                   COALESCE(pl.batch_no, ''), COALESCE(pl.location, '')
            FROM product_locations pl
            JOIN products p ON p.id = pl.product_id
            WHERE COALESCE(pl.expiry_discount_enabled, 0) = 1
              AND COALESCE(pl.expiry_discount_percent, 0) > 0
        """
        expiry_params = []
        if search:
            expiry_query += """
              AND (
                LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.sku, '')) LIKE ?
                OR LOWER(COALESCE(pl.clearance_note, '')) LIKE ?
                OR LOWER(COALESCE(pl.batch_no, '')) LIKE ?
                OR LOWER(COALESCE(pl.location, '')) LIKE ?
              )
            """
            like = f"%{search}%"
            expiry_params.extend([like, like, like, like, like])
        if status == "Active Now":
            expiry_query += """
              AND (pl.expiry_discount_start_date IS NULL OR pl.expiry_discount_start_date = '' OR date(pl.expiry_discount_start_date) <= date('now'))
              AND (
                COALESCE(NULLIF(pl.expiry_discount_end_date, ''), pl.expire_date, '') = ''
                OR date(COALESCE(NULLIF(pl.expiry_discount_end_date, ''), pl.expire_date)) >= date('now')
              )
            """
        elif status == "Scheduled":
            expiry_query += " AND pl.expiry_discount_start_date IS NOT NULL AND pl.expiry_discount_start_date != '' AND date(pl.expiry_discount_start_date) > date('now')"
        elif status == "Expired":
            expiry_query += """
              AND COALESCE(NULLIF(pl.expiry_discount_end_date, ''), pl.expire_date, '') != ''
              AND date(COALESCE(NULLIF(pl.expiry_discount_end_date, ''), pl.expire_date)) < date('now')
            """
        elif status == "Disabled":
            expiry_query += " AND 1 = 0"
        expiry_query += " ORDER BY pl.expire_date ASC, p.name"
        cursor.execute(expiry_query, expiry_params)
        expiry_rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(0)
        for row in promo_rows:
            discount_id, product, sku, percent, discount_type, manual_price, start, end, active, note = row
            status_text = self._status_text(active, start, end)
            discount_text = f"{percent:g}%" if discount_type != "manual_price" else f"Manual: {manual_price:g}"
            r = self.table.rowCount()
            self.table.insertRow(r)
            values = [f"P:{discount_id}", "Product", product, sku or "-", discount_text, start, end, status_text, note]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, ("product", discount_id))
                self.table.setItem(r, c, item)

        today = QDate.currentDate().toString("yyyy-MM-dd")
        for row in expiry_rows:
            loc_id, product, sku, percent, start, end, active, note, batch_no, location = row
            if start and start > today:
                status_text = "Scheduled"
            elif end and end < today:
                status_text = "Expired"
            else:
                status_text = "Active"
            detail_note = note or "Expiry clearance"
            if batch_no:
                detail_note = f"{detail_note} | Batch: {batch_no}"
            if location:
                detail_note = f"{detail_note} | Location: {location}"
            r = self.table.rowCount()
            self.table.insertRow(r)
            values = [f"E:{loc_id}", "Expiry", product, sku or "-", f"{percent:g}%", start or "-", end or "-", status_text, detail_note]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, ("expiry", loc_id))
                self.table.setItem(r, c, item)
        self._on_selection_changed()

    def _status_text(self, active, start, end):
        today = QDate.currentDate().toString("yyyy-MM-dd")
        if not active:
            return "Disabled"
        if start > today:
            return "Scheduled"
        if end < today:
            return "Expired"
        return "Active"

    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        has_selection = bool(selected)
        self.selected_discount_id = None
        self.selected_discount_kind = None
        if has_selection:
            row = selected[0].row()
            item = self.table.item(row, 0)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, tuple):
                    self.selected_discount_kind, self.selected_discount_id = data
        can_edit = has_selection and self.selected_discount_kind == "product"
        self.btn_edit.setEnabled(can_edit)
        self.action_delete.setEnabled(can_edit)
        self.action_toggle.setEnabled(can_edit)

    def add_discount(self):
        self._open_dialog()

    def edit_discount(self):
        if not self.selected_discount_id or self.selected_discount_kind != "product":
            QMessageBox.warning(self, "No Selection", "Please select a discount.")
            return
        self._open_dialog(self.selected_discount_id)

    def _open_dialog(self, discount_id=None):
        data = self._get_discount(discount_id) if discount_id else None
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Discount" if discount_id else "Add Discount")
        dialog.setModal(True)
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        body = QHBoxLayout()
        body.setSpacing(14)
        layout.addLayout(body, 1)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by product name, SKU, or barcode...")
        product_combo = QComboBox()
        product_combo.setMinimumWidth(300)

        image_preview = QLabel()
        image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_preview.setMinimumSize(240, 240)
        image_preview.setScaledContents(True)
        image_preview.setWordWrap(True)
        product_details = QLabel("Select a product to view details")
        product_details.setWordWrap(True)

        def populate_products(filter_text=""):
            current_id = product_combo.currentData()
            product_combo.blockSignals(True)
            product_combo.clear()
            needle = filter_text.strip().lower()
            for product_id, name, sku, price in self._products:
                details = self._get_product_details(product_id)
                barcode = str(details.get("barcode", "")).lower()
                haystack = f"{name} {sku} {barcode}".lower()
                if needle and needle not in haystack:
                    continue
                product_combo.addItem(f"{name} ({sku or 'No SKU'})", product_id)
            if current_id:
                idx = product_combo.findData(current_id)
                if idx >= 0:
                    product_combo.setCurrentIndex(idx)
            product_combo.blockSignals(False)
            update_product_preview()

        def update_product_preview():
            product_id = product_combo.currentData()
            details = self._get_product_details(product_id)
            if not details:
                image_preview.setText("No Image\n\nSelect a product to preview")
                image_preview.setPixmap(QPixmap())
                product_details.setText("Select a product to view details")
                return
            image_path = details.get("image") or ""
            if image_path:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    image_preview.setPixmap(pixmap.scaled(
                        image_preview.width() - 16,
                        image_preview.height() - 16,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ))
                else:
                    image_preview.setText("Image not available")
                    image_preview.setPixmap(QPixmap())
            else:
                image_preview.setText("No Image Available")
                image_preview.setPixmap(QPixmap())
            product_details.setText(
                f"Name: {details.get('name', '-')}\n"
                f"SKU: {details.get('sku') or '-'}\n"
                f"Barcode: {details.get('barcode') or '-'}\n"
                f"Category: {details.get('category') or '-'}\n"
                f"Price: {details.get('price') or 0:g}\n"
                f"Stock: {details.get('stock') or 0}"
            )
            if "manual_price" in locals() and manual_price.value() <= 0:
                manual_price.setValue(float(details.get("price") or 0))

        discount_mode = QComboBox()
        discount_mode.addItem("Percentage", "percentage")
        discount_mode.addItem("Manual Price", "manual_price")

        percent = QDoubleSpinBox()
        percent.setRange(0.01, 100.0)
        percent.setDecimals(2)
        percent.setSuffix(" %")
        percent.setValue(10.0)
        manual_price = QDoubleSpinBox()
        manual_price.setRange(0.0, 999999999.0)
        manual_price.setDecimals(2)
        manual_price.setPrefix(f"{self._currency_symbol()} ")
        manual_price.setValue(0.0)

        def update_discount_inputs():
            is_manual = discount_mode.currentData() == "manual_price"
            percent.setVisible(not is_manual)
            manual_price.setVisible(is_manual)
            form.labelForField(percent).setVisible(not is_manual)
            form.labelForField(manual_price).setVisible(is_manual)

        discount_mode.currentIndexChanged.connect(update_discount_inputs)
        start_date = QDateEdit()
        start_date.setCalendarPopup(True)
        start_date.setDisplayFormat("yyyy-MM-dd")
        start_date.setDate(QDate.currentDate())
        end_date = QDateEdit()
        end_date.setCalendarPopup(True)
        end_date.setDisplayFormat("yyyy-MM-dd")
        end_date.setDate(QDate.currentDate().addDays(7))
        active = QCheckBox("Enabled")
        active.setChecked(True)
        note = QLineEdit()
        note.setPlaceholderText("Campaign note, e.g. Weekend promo")

        form.addRow("Search:", search_input)
        form.addRow("Product:", product_combo)
        form.addRow("Discount Type:", discount_mode)
        form.addRow("Percentage:", percent)
        form.addRow("Manual Price:", manual_price)
        form.addRow("Start Date:", start_date)
        form.addRow("End Date:", end_date)
        form.addRow("", active)
        form.addRow("Note:", note)
        left_layout.addLayout(form)
        left_layout.addStretch()
        body.addWidget(left_panel, 2)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        title = QLabel("Product Image")
        title.setStyleSheet("font-weight: 600;")
        right_layout.addWidget(title)
        right_layout.addWidget(image_preview, 1)
        info_title = QLabel("Product Information")
        info_title.setStyleSheet("font-weight: 600;")
        right_layout.addWidget(info_title)
        right_layout.addWidget(product_details)
        body.addWidget(right_panel, 1)

        search_input.textChanged.connect(populate_products)
        product_combo.currentIndexChanged.connect(update_product_preview)
        populate_products()

        if data:
            _id, product_id, discount_percent, dtype, saved_manual_price, start, end, enabled, note_text = data
            idx = product_combo.findData(product_id)
            if idx >= 0:
                product_combo.setCurrentIndex(idx)
            percent.setValue(float(discount_percent or 0))
            mode_idx = discount_mode.findData(dtype or "percentage")
            discount_mode.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
            manual_price.setValue(float(saved_manual_price or 0))
            start_qdate = QDate.fromString(start, "yyyy-MM-dd")
            end_qdate = QDate.fromString(end, "yyyy-MM-dd")
            if start_qdate.isValid():
                start_date.setDate(start_qdate)
            if end_qdate.isValid():
                end_date.setDate(end_qdate)
            active.setChecked(bool(enabled))
            note.setText(note_text or "")
            update_product_preview()
        update_discount_inputs()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        self._style_discount_dialog(dialog, image_preview, product_details)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not product_combo.currentData():
            QMessageBox.warning(self, "No Product", "Please select a product.")
            return
        if end_date.date() < start_date.date():
            QMessageBox.warning(self, "Invalid Date", "End date must be after start date.")
            return
        if discount_mode.currentData() == "manual_price" and manual_price.value() <= 0:
            QMessageBox.warning(self, "Invalid Price", "Manual price must be greater than zero.")
            return
        details = self._get_product_details(product_combo.currentData())
        current_price = float(details.get("price") or 0)
        if discount_mode.currentData() == "manual_price" and current_price > 0 and manual_price.value() >= current_price:
            QMessageBox.warning(self, "Invalid Price", "Manual price must be lower than the product price.")
            return
        self._save_discount(
            discount_id,
            product_combo.currentData(),
            percent.value(),
            discount_mode.currentData(),
            manual_price.value(),
            start_date.date().toString("yyyy-MM-dd"),
            end_date.date().toString("yyyy-MM-dd"),
            active.isChecked(),
            note.text().strip(),
        )

    def _get_product_details(self, product_id):
        if not product_id:
            return {}
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, COALESCE(sku, ''), COALESCE(barcode, ''), COALESCE(category, ''),
                   COALESCE(price, 0), COALESCE(stock, 0), COALESCE(image, '')
            FROM products
            WHERE id = ?
        """, (product_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {}
        name, sku, barcode, category, price, stock, image = row
        return {
            "name": name,
            "sku": sku,
            "barcode": barcode,
            "category": category,
            "price": float(price or 0),
            "stock": int(stock or 0),
            "image": image,
        }

    def _currency_symbol(self):
        try:
            from utils.currency import get_currency_symbol
            return get_currency_symbol()
        except Exception:
            return "Ks"

    def _style_discount_dialog(self, dialog, image_preview, product_details):
        colors = get_theme_colors()
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.get('bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
            }}
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 6px;
            }}
            QLabel {{
                color: {colors.get('text', '#212529')};
                background: transparent;
                border: none;
            }}
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {{
                background-color: {colors.get('card_bg', '#ffffff')};
                color: {colors.get('text', '#212529')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 5px;
                padding: 6px 8px;
            }}
            QCheckBox {{
                color: {colors.get('text', '#212529')};
                background: transparent;
                border: none;
            }}
        """)
        image_preview.setStyleSheet(f"""
            QLabel {{
                background-color: {colors.get('bg_hover', '#f8f9fa')};
                color: {colors.get('text_secondary', '#6c757d')};
                border: 1px dashed {colors.get('border', '#dee2e6')};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        product_details.setStyleSheet(f"""
            QLabel {{
                color: {colors.get('text_secondary', '#6c757d')};
                line-height: 1.4;
                padding: 2px;
            }}
        """)

    def _get_discount(self, discount_id):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, product_id, discount_percent, COALESCE(discount_type, 'percentage'),
                   COALESCE(manual_price, 0), start_date, end_date, active, COALESCE(note, '')
            FROM product_discounts
            WHERE id = ?
        """, (discount_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def _save_discount(self, discount_id, product_id, percent, discount_type, manual_price, start, end, active, note):
        if discount_type != "manual_price":
            manual_price = 0
        conn = connect_db()
        cursor = conn.cursor()
        if discount_id:
            cursor.execute("""
                UPDATE product_discounts
                SET product_id = ?, discount_percent = ?, start_date = ?, end_date = ?,
                    active = ?, note = ?, discount_type = ?, manual_price = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (product_id, percent, start, end, 1 if active else 0, note, discount_type, manual_price, discount_id))
        else:
            cursor.execute("""
                INSERT INTO product_discounts
                (product_id, discount_percent, start_date, end_date, active, note, discount_type, manual_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, percent, start, end, 1 if active else 0, note, discount_type, manual_price))
        conn.commit()
        conn.close()
        self.load_discounts()

    def delete_discount(self):
        if not self.selected_discount_id or self.selected_discount_kind != "product":
            return
        reply = QMessageBox.question(
            self, "Delete Discount", "Delete selected discount?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM product_discounts WHERE id = ?", (self.selected_discount_id,))
        conn.commit()
        conn.close()
        self.load_discounts()

    def toggle_discount(self):
        if not self.selected_discount_id or self.selected_discount_kind != "product":
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE product_discounts
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (self.selected_discount_id,))
        conn.commit()
        conn.close()
        self.load_discounts()
