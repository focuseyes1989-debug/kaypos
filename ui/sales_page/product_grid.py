# ui/sales_page/product_grid.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox,
    QApplication, QFrame, QGridLayout, QSizePolicy,
    QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QColor, QFont
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.search_widget import SearchWidget
from ui.widgets.combo_box_widget import ComboBoxWidget
from ui.widgets.numeric_keypad_dialog import get_numeric_input_value
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from ui.sales_page.product_utils import load_thumbnail
from ui.sales_page.grid_view import GridViewWidget
from ui.sales_page.list_view import ListViewWidget
from ui.sales_page.category_slider import CategorySlider
from utils.performance import get_performance_settings
from loguru import logger


class ProductGrid(QWidget):
    product_selected = pyqtSignal(int, str, float, int)
    service_selected = pyqtSignal(int, str, float)
    barcode_scanned = pyqtSignal(str)

    VIEW_TABLE = 0
    VIEW_LIST = 1
    VIEW_GRID = 2
    VIEW_MODERN_GRID = 3
    
    VIEW_NAMES = {
        VIEW_TABLE: "Table View",
        VIEW_LIST: "List View",
        VIEW_GRID: "Grid View",
        VIEW_MODERN_GRID: "Modern Grid"
    }

    def __init__(self, parent=None, use_modern_combos: bool = False):
        super().__init__(parent)
        self.use_modern_combos = use_modern_combos
        self._performance_settings = get_performance_settings()
        self.current_page = 1
        self.rows_per_page = self._performance_settings.product_page_size
        self._current_view = self.VIEW_GRID
        self._last_rows = []
        self._selected_group = ""
        self._selected_category = ""
        self._discount_filter = "all"
        self._grid_lazy_page = 1
        self._grid_lazy_page_size = 50
        self._grid_lazy_total = 0
        self._grid_lazy_loading = False
        self._grid_lazy_has_more = False
        self._product_loading_active = False
        self._product_loading_uses_overlay = False
        self._search_filter_timer = QTimer(self)
        self._search_filter_timer.setSingleShot(True)
        self._search_filter_timer.timeout.connect(self._apply_search_filter)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.setLayout(layout)

        # ── Top bar ──────────────────────────────────────────────────────
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        self.search_widget = SearchWidget("Search by name / barcode / SKU...")
        self.search_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_widget.setMinimumWidth(220)
        self.search_widget.setMaximumWidth(16777215)
        self.search_widget.search_changed.connect(self.schedule_search_filter)
        self.search_widget.search_cleared.connect(self.schedule_search_filter)
        self.search_input = self.search_widget.search_input
        self.search_input.returnPressed.connect(self.scan_barcode)

        combo_class = ComboBoxWidget if self.use_modern_combos else QComboBox

        self.category_combo = combo_class("All Categories") if self.use_modern_combos else combo_class()
        self.category_combo.addItem("All Categories")
        self.category_combo.currentTextChanged.connect(self.on_category_combo_changed)
        self.category_combo.setFixedWidth(180)  # ✅ Width ချဲ့ထားပါ

        self.discount_filter_combo = combo_class("All Products") if self.use_modern_combos else combo_class()
        self.discount_filter_combo.addItem("All Products", "all")
        self.discount_filter_combo.addItem("Discount Products", "discount")
        self.discount_filter_combo.currentIndexChanged.connect(self.on_discount_filter_changed)
        self.discount_filter_combo.setFixedWidth(150)

        self.view_label = QLabel("View:")
        self.view_combo = combo_class("View") if self.use_modern_combos else combo_class()
        self.view_combo.addItem("Grid", self.VIEW_GRID)
        self.view_combo.addItem("Modern Grid", self.VIEW_MODERN_GRID)
        self.view_combo.addItem("List", self.VIEW_LIST)
        self.view_combo.addItem("Table", self.VIEW_TABLE)
        self.view_combo.setCurrentIndex(0)
        self.view_combo.currentIndexChanged.connect(self.on_view_changed)
        self.view_combo.setFixedWidth(140)

        search_layout.addWidget(self.search_widget, stretch=1)
        search_layout.addWidget(self.category_combo)
        search_layout.addWidget(self.discount_filter_combo)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # ── Category Slider ──────────────────────────────────
        self.category_slider = CategorySlider()
        self.category_slider.category_selected.connect(self.on_category_slider_selected)
        self.category_slider.group_selected.connect(self.on_group_slider_selected)
        layout.addWidget(self.category_slider)

        # ── Stacked widget ──────────────────────────────────────────────
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Table view
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setColumnHidden(0, True)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self.on_row_clicked)
        self.table.verticalHeader().setDefaultSectionSize(50)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(1, 60)
        self.table.setHorizontalHeaderLabels(["ID", "Image", "Name", "Price", "Stock", "Status"])
        self.stack.addWidget(self.table)

        # List view
        self.list_view = ListViewWidget()
        self.list_view.product_selected.connect(self.product_selected)
        self.list_view.service_selected.connect(self.service_selected)
        self.stack.addWidget(self.list_view)

        # Grid view
        self.grid_view = GridViewWidget()
        self.grid_view.product_selected.connect(self.product_selected)
        self.grid_view.service_selected.connect(self.service_selected)
        self.grid_view.favourite_toggled.connect(self.on_favourite_toggled)
        self.stack.addWidget(self.grid_view)

        # Modern grid view
        self.modern_grid_view = GridViewWidget(card_style="modern")
        self.modern_grid_view.product_selected.connect(self.product_selected)
        self.modern_grid_view.service_selected.connect(self.service_selected)
        self.modern_grid_view.favourite_toggled.connect(self.on_favourite_toggled)
        self.stack.addWidget(self.modern_grid_view)
        self.stack.setCurrentIndex(self._current_view)

        # ── Pagination ──────────────────────────────────────────────────
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        pagination_layout.setSpacing(8)
        pagination_layout.addWidget(self.view_label)
        pagination_layout.addWidget(self.view_combo)
        pagination_layout.addWidget(self.pagination, stretch=1)
        layout.addLayout(pagination_layout)

        self.load_categories()
        self.load_products(page_size=self.rows_per_page)

    def apply_performance_settings(self, settings=None):
        self._performance_settings = settings or get_performance_settings(refresh=True)
        self.rows_per_page = self._performance_settings.product_page_size
        self.pagination.set_current_page(1, emit_signal=False)
        self.load_products(1, self.rows_per_page, show_progress=False)

    def _main_window(self):
        parent = self.window()
        return parent if parent is not self else None

    def _show_product_loading(self, message: str, progress: int | None = None, overlay: bool = True) -> None:
        main_window = self._main_window()
        self._product_loading_active = True
        self._product_loading_uses_overlay = False
        if overlay and hasattr(main_window, "show_loading"):
            self._product_loading_uses_overlay = True
            main_window.show_loading(message, progress)
            return
        status_bar = getattr(main_window, "status_bar", None)
        if status_bar and hasattr(status_bar, "begin_background_activity"):
            status_bar.begin_background_activity("product_grid_loading", message)
        app = QApplication.instance()
        if app:
            app.processEvents()

    def _update_product_loading(self, message: str, progress: int | None = None) -> None:
        main_window = self._main_window()
        if self._product_loading_uses_overlay and hasattr(main_window, "update_loading"):
            main_window.update_loading(message, progress)
        status_bar = getattr(main_window, "status_bar", None)
        if status_bar and hasattr(status_bar, "begin_background_activity"):
            status_bar.begin_background_activity("product_grid_loading", message)
        app = QApplication.instance()
        if app:
            app.processEvents()

    def _hide_product_loading(self) -> None:
        if not self._product_loading_active:
            return
        main_window = self._main_window()
        if self._product_loading_uses_overlay and hasattr(main_window, "hide_loading"):
            main_window.hide_loading()
        status_bar = getattr(main_window, "status_bar", None)
        if status_bar and hasattr(status_bar, "end_background_activity"):
            status_bar.end_background_activity("product_grid_loading")
        self._product_loading_active = False
        self._product_loading_uses_overlay = False
        self._switch_view(self._current_view)

    def on_category_combo_changed(self, text):
        """Handle category combo change."""
        if text == "All Categories" or text == "အားလုံး":
            self._selected_category = ""
            self._selected_group = ""
            self.category_slider.set_selected_category("")
        self.reset_and_filter(show_progress=False)

    def on_discount_filter_changed(self, *_):
        """Show all products or only products with an active discount."""
        self._discount_filter = self.discount_filter_combo.currentData() or "all"
        self.pagination.set_current_page(1, emit_signal=False)
        self.load_products(show_progress=False)

    def on_favourite_toggled(self, prod_id, is_favourite):
        """Handle favourite toggle from grid view."""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET is_favourite = ? WHERE id = ?",
            (1 if is_favourite else 0, prod_id)
        )
        conn.commit()
        conn.close()
        if self._current_view in (self.VIEW_GRID, self.VIEW_MODERN_GRID):
            self.load_products(self.current_page, self.rows_per_page, show_progress=False)
        else:
            self.load_products(self.current_page, self.rows_per_page, show_progress=False)

    def on_view_changed(self, index):
        view = self.view_combo.currentData()
        self._switch_view(view)

    def _switch_view(self, view: int):
        if self._current_view == view:
            self.stack.setCurrentIndex(view)
            self.pagination.setVisible(True)
            return
        
        self._current_view = view
        
        self.view_combo.blockSignals(True)
        for i in range(self.view_combo.count()):
            if self.view_combo.itemData(i) == view:
                self.view_combo.setCurrentIndex(i)
                break
        self.view_combo.blockSignals(False)
        
        self.stack.setCurrentIndex(view)
        self.pagination.setVisible(True)
        
        if view in (self.VIEW_GRID, self.VIEW_MODERN_GRID):
            self.pagination.set_current_page(1, emit_signal=False)
            self.load_products(1, self.rows_per_page, show_progress=False)
        elif view == self.VIEW_LIST:
            self.pagination.set_current_page(1, emit_signal=False)
            self.load_products(1, self.rows_per_page, show_progress=False)
        else:
            self.pagination.set_current_page(1, emit_signal=False)
            self.load_products(1, self.rows_per_page, show_progress=False)

    def on_category_slider_selected(self, category_name):
        """Handle category selection from the slider."""
        logger.debug(f"Category selected from slider: {category_name}")
        
        self._selected_group = ""
        self._selected_category = category_name if category_name != "" else ""
        
        self.category_combo.blockSignals(True)
        if category_name == "":
            self.category_combo.setCurrentIndex(0)
        else:
            found = False
            for i in range(self.category_combo.count()):
                item_text = self.category_combo.itemText(i)
                # ✅ Remove emoji and indentation before comparing
                clean_text = self._clean_category_display_text(item_text)
                if clean_text == category_name:
                    self.category_combo.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)
        
        self.pagination.set_current_page(1, emit_signal=False)
        self.load_products(show_progress=False)

    def on_group_slider_selected(self, group_name):
        """Handle group selection from the slider."""
        logger.debug(f"Group selected from slider: {group_name}")
        
        self._selected_group = group_name
        self._selected_category = ""
        
        self.category_combo.blockSignals(True)
        self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)
        
        self.pagination.set_current_page(1, emit_signal=False)
        self.load_products(show_progress=False)

    def _clean_category_display_text(self, text):
        """Remove emojis and indentation from display text to get clean category name"""
        import re
        # Remove emojis (📁, 📄, etc.)
        clean = re.sub(r'[📁📄📂🔹🔸]', '', text)
        # Remove indentation spaces
        clean = clean.strip()
        return clean

    def load_categories(self):
        """
        Load categories with indentation for parent-child hierarchy.
        ✅ Parent categories: 📁, Child categories: 📄 with indentation
        """
        conn = connect_db()
        cursor = conn.cursor()
        
        # Get all categories with parent info
        cursor.execute("""
            SELECT id, name, parent_id 
            FROM categories 
            ORDER BY COALESCE(parent_id, 0), name
        """)
        rows = cursor.fetchall()
        conn.close()
        
        self.category_combo.blockSignals(True)
        current = self.category_combo.currentText()
        self.category_combo.clear()
        self.category_combo.addItem("All Categories")
        
        if not rows:
            self.category_combo.blockSignals(False)
            return
        
        # Build category hierarchy
        category_dict = {}
        for row in rows:
            cat_id, name, parent_id = row
            category_dict[cat_id] = {
                'name': name,
                'parent_id': parent_id,
                'children': []
            }
        
        # Build parent-child relationships
        root_categories = []
        for cat_id, data in category_dict.items():
            if data['parent_id'] is None:
                root_categories.append(cat_id)
            else:
                parent = category_dict.get(data['parent_id'])
                if parent:
                    parent['children'].append(cat_id)
        
        # Sort root categories by name
        root_categories.sort(key=lambda x: category_dict[x]['name'])
        
        # Add categories with indentation
        def add_category_with_indent(cat_id, indent=0):
            data = category_dict[cat_id]
            prefix = "  " * indent
            
            # Parent ကို 📁, Child ကို 📄 နဲ့ ခွဲပြမယ်
            if indent == 0:
                display_name = f"📁 {data['name']}"
            else:
                display_name = f"{prefix}📄 {data['name']}"
            
            self.category_combo.addItem(display_name, cat_id)
            
            # Add children with more indentation
            children = sorted(data['children'], key=lambda x: category_dict[x]['name'])
            for child_id in children:
                add_category_with_indent(child_id, indent + 1)
        
        for root_id in root_categories:
            add_category_with_indent(root_id)
        
        # Restore selection
        idx = self.category_combo.findText(current)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setCurrentIndex(0)
        
        self.category_combo.blockSignals(False)
        
        # Load category slider data
        self._load_category_slider_data()

    def _load_category_slider_data(self):
        """Load category data for slider"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.name,
                c.group_id,
                cg.name as group_name,
                c.is_favorite
            FROM categories c
            LEFT JOIN category_groups cg ON c.group_id = cg.id
            ORDER BY 
                CASE WHEN cg.id IS NULL THEN 1 ELSE 0 END,
                cg.sort_order,
                c.name
        """)
        rows = cursor.fetchall()
        
        cursor.execute("""
            SELECT id, name, description, is_favorite
            FROM category_groups
            WHERE is_active = 1
            ORDER BY sort_order, name
        """)
        groups = cursor.fetchall()
        conn.close()
        
        category_data = []
        for row in rows:
            cat_name, group_id, group_name, is_favorite = row
            category_data.append((cat_name, group_id, group_name, is_favorite))
        
        self.category_slider.load_categories(category_data, groups)

    def _get_category_tree_ids(self, category_id):
        """
        ✅ Get all category IDs in the tree (parent + all children)
        """
        category_ids = [category_id]
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            
            # Recursive query to get all child categories
            cursor.execute("""
                WITH RECURSIVE category_tree AS (
                    SELECT id FROM categories WHERE id = ?
                    UNION ALL
                    SELECT c.id FROM categories c
                    INNER JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree
            """, (category_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                if row[0] not in category_ids:
                    category_ids.append(row[0])
                    
        except Exception as e:
            logger.error(f"Failed to get category tree: {e}")
            # Fallback: just use the parent category ID
            return [category_id]
        
        return category_ids

    def _active_discount_exists_sql(self) -> str:
        return """
            EXISTS (
                SELECT 1
                FROM product_discounts pd
                WHERE pd.product_id = p.id
                  AND COALESCE(pd.active, 1) = 1
                  AND (
                    COALESCE(pd.discount_percent, 0) > 0
                    OR (
                        COALESCE(pd.discount_type, 'percentage') = 'manual_price'
                        AND COALESCE(pd.manual_price, 0) > 0
                    )
                  )
                  AND (pd.start_date IS NULL OR pd.start_date = '' OR date(pd.start_date) <= date('now'))
                  AND (pd.end_date IS NULL OR pd.end_date = '' OR date(pd.end_date) >= date('now'))
            )
        """

    def load_products(self, page=1, page_size=None, append_grid=False, show_progress=False):
        """
        Load products with group and category filtering support.
        ✅ FIXED: Supports parent categories - shows products from all child categories
        ✅ Uses indentation for category display
        """
        if page_size is None:
            page_size = self._performance_settings.product_page_size
        self.current_page = page
        self.rows_per_page = page_size
        is_grid_view = self._current_view in (self.VIEW_GRID, self.VIEW_MODERN_GRID)
        should_show_progress = show_progress and is_grid_view
        if should_show_progress:
            message = "Loading more products..." if append_grid else "Loading product grid..."
            self._show_product_loading(message, 8 if not append_grid else None, overlay=not append_grid)
        if self._current_view in (self.VIEW_GRID, self.VIEW_MODERN_GRID):
            self._grid_lazy_loading = True
        search_text = self.search_input.text().strip().lower()
        
        selected_category_text = self.category_combo.currentText()
        
        use_category = False
        selected_category_ids = []  # ✅ List of category IDs (parent + children)
        
        # Check if a category is selected (not "All Categories")
        if selected_category_text not in ["All Categories", "အားလုံး"]:
            # ✅ Clean the display text to get actual category name
            clean_name = self._clean_category_display_text(selected_category_text)
            
            # ✅ Get category ID from database
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (clean_name,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                parent_id = row[0]
                use_category = True
                
                # ✅ Get all child category IDs (including the parent itself)
                selected_category_ids = self._get_category_tree_ids(parent_id)
                logger.debug(f"Found category tree IDs for '{clean_name}': {selected_category_ids}")
            else:
                logger.warning(f"Category '{clean_name}' not found in database")
        
        use_group = self._selected_group != ""
        
        logger.debug(f"Loading products - Group: {self._selected_group}, Category IDs: {selected_category_ids}, Search: {search_text}")

        conn = connect_db()
        cursor = conn.cursor()
        self._ensure_discount_columns(cursor)
        conn.commit()

        # ── Count query ──────────────────────────────────────────────────
        count_params = []
        count_where = []
        
        if use_group:
            # ✅ Filter by group using category_id
            count_where.append("""
                p.category_id IN (
                    SELECT c.id FROM categories c
                    WHERE c.group_id = (
                        SELECT id FROM category_groups WHERE name = ?
                    )
                )
            """)
            count_params.append(self._selected_group)
            logger.debug(f"Filtering by group: {self._selected_group}")
            
        elif use_category and selected_category_ids:
            # ✅ Filter by category IDs (parent + all children)
            placeholders = ','.join(['?'] * len(selected_category_ids))
            count_where.append(f"p.category_id IN ({placeholders})")
            count_params.extend(selected_category_ids)
            logger.debug(f"Filtering by category IDs: {selected_category_ids}")
        
        if search_text:
            like = f'%{search_text}%'
            count_where.append("(LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ? OR LOWER(p.barcode) LIKE ?)")
            count_params.extend([like, like, like])

        if self._discount_filter == "discount":
            count_where.append(self._active_discount_exists_sql())

        count_sql = "SELECT COUNT(*) FROM products p"
        if count_where:
            count_sql += " WHERE " + " AND ".join(count_where)
        cursor.execute(count_sql, count_params)
        total_items = cursor.fetchone()[0]
        self.pagination.set_total_items(total_items, emit_signal=False)
        if should_show_progress:
            self._update_product_loading(f"Found {total_items} products. Loading cards...", 35 if not append_grid else None)

        # ── Select query ─────────────────────────────────────────────────
        offset = (page - 1) * page_size
        select_params = []
        where_clauses = []
        
        if use_group:
            # ✅ Filter by group using category_id
            where_clauses.append("""
                p.category_id IN (
                    SELECT c.id FROM categories c
                    WHERE c.group_id = (
                        SELECT id FROM category_groups WHERE name = ?
                    )
                )
            """)
            select_params.append(self._selected_group)
            logger.debug(f"SELECT filter by group: {self._selected_group}")
            
        elif use_category and selected_category_ids:
            # ✅ Filter by category IDs (parent + all children)
            placeholders = ','.join(['?'] * len(selected_category_ids))
            where_clauses.append(f"p.category_id IN ({placeholders})")
            select_params.extend(selected_category_ids)
            logger.debug(f"SELECT filter by category IDs: {selected_category_ids}")
        
        if search_text:
            like = f'%{search_text}%'
            where_clauses.append("(LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ? OR LOWER(p.barcode) LIKE ?)")
            select_params.extend([like, like, like])

        if self._discount_filter == "discount":
            where_clauses.append(self._active_discount_exists_sql())

        select_sql = """
            SELECT 
                p.id, p.name, p.price, p.stock, p.low_stock, p.sold_by, p.image,
                p.is_favourite, COALESCE(c.name, p.category, '') as category_name,
                COALESCE((
                    SELECT MAX(COALESCE(pd.discount_percent, 0))
                    FROM product_discounts pd
                    WHERE pd.product_id = p.id
                      AND COALESCE(pd.active, 1) = 1
                      AND COALESCE(pd.discount_percent, 0) > 0
                      AND (pd.start_date IS NULL OR pd.start_date = '' OR date(pd.start_date) <= date('now'))
                      AND (pd.end_date IS NULL OR pd.end_date = '' OR date(pd.end_date) >= date('now'))
                ), 0) as active_discount_percent,
                COALESCE((
                    SELECT COALESCE(pd.discount_type, 'percentage')
                    FROM product_discounts pd
                    WHERE pd.product_id = p.id
                      AND COALESCE(pd.active, 1) = 1
                      AND (
                        COALESCE(pd.discount_percent, 0) > 0
                        OR (COALESCE(pd.discount_type, 'percentage') = 'manual_price' AND COALESCE(pd.manual_price, 0) > 0)
                      )
                      AND (pd.start_date IS NULL OR pd.start_date = '' OR date(pd.start_date) <= date('now'))
                      AND (pd.end_date IS NULL OR pd.end_date = '' OR date(pd.end_date) >= date('now'))
                    ORDER BY
                      CASE
                        WHEN COALESCE(pd.discount_type, 'percentage') = 'manual_price' AND COALESCE(pd.manual_price, 0) > 0
                        THEN 1000000 - COALESCE(pd.manual_price, 0)
                        ELSE COALESCE(pd.discount_percent, 0)
                      END DESC,
                      pd.end_date ASC
                    LIMIT 1
                ), 'percentage') as active_discount_type,
                COALESCE((
                    SELECT COALESCE(pd.manual_price, 0)
                    FROM product_discounts pd
                    WHERE pd.product_id = p.id
                      AND COALESCE(pd.active, 1) = 1
                      AND COALESCE(pd.discount_type, 'percentage') = 'manual_price'
                      AND COALESCE(pd.manual_price, 0) > 0
                      AND (pd.start_date IS NULL OR pd.start_date = '' OR date(pd.start_date) <= date('now'))
                      AND (pd.end_date IS NULL OR pd.end_date = '' OR date(pd.end_date) >= date('now'))
                    ORDER BY pd.manual_price ASC, pd.end_date ASC
                    LIMIT 1
                ), 0) as active_manual_price
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
        """
        if where_clauses:
            select_sql += " WHERE " + " AND ".join(where_clauses)
        
        select_sql += " ORDER BY p.is_favourite DESC, p.name LIMIT ? OFFSET ?"
        cursor.execute(select_sql, select_params + [page_size, offset])
        rows = cursor.fetchall()
        conn.close()
        if should_show_progress:
            loaded_so_far = (len(self._last_rows) if append_grid else 0) + len(rows)
            progress = 35 if total_items <= 0 else min(85, 35 + int((loaded_so_far / max(1, total_items)) * 50))
            self._update_product_loading(f"Rendering products {loaded_so_far}/{total_items}...", progress if not append_grid else None)

        logger.debug(f"Found {len(rows)} products")

        if self._current_view in (self.VIEW_GRID, self.VIEW_MODERN_GRID):
            self.stack.setCurrentIndex(self._current_view)
            self._grid_lazy_page = page
            self._grid_lazy_page_size = page_size
            self._grid_lazy_total = total_items
            loaded_count = len(rows)
            self._grid_lazy_has_more = False
            self._grid_lazy_loading = False

            self._last_rows = rows
            active_grid = self.modern_grid_view if self._current_view == self.VIEW_MODERN_GRID else self.grid_view
            active_grid.populate_and_store(rows)

            active_grid.set_lazy_state(
                loading=False,
                has_more=False
            )
            loaded_text = loaded_count if total_items else 0
            if should_show_progress:
                self._update_product_loading(f"Product grid loaded {loaded_text}/{total_items}.", 100 if not append_grid else None)
                QTimer.singleShot(150, self._hide_product_loading)
        elif self._current_view == self.VIEW_LIST:
            self._last_rows = rows
            self.list_view.populate_and_store(rows)
        else:
            self._last_rows = rows
            self.populate_table(rows)

    def load_next_grid_page(self):
        """Load the next grid batch when the user scrolls near the bottom."""
        return

    def _load_more_if_grid_needs_fill(self):
        """Keep loading while the grid has no scrollbar but more products exist."""
        return

    def on_page_changed(self, page: int, page_size: int):
        self.load_products(page, page_size, show_progress=False)

    def schedule_search_filter(self, *_):
        """Debounce search typing without showing the grid loading progress."""
        self._search_filter_timer.start(self._performance_settings.search_debounce_ms)

    def _apply_search_filter(self):
        self.reset_and_filter(show_progress=False)

    def reset_and_filter(self, show_progress=False):
        """Reset and apply filters."""
        if self._selected_group and self.search_input.text().strip():
            pass
        elif not self._selected_group:
            self._selected_category = ""
            self.pagination.set_current_page(1, emit_signal=False)
        self.load_products(show_progress=show_progress)

    def populate_table(self, rows):
        symbol = get_currency_symbol()
        self.table.setRowCount(0)
        for prod in rows:
            prod_id, name, price, stock, low_stock, sold_by, image_path = prod[:7]
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(prod_id)))

            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setScaledContents(True)
            image_label.setFixedSize(40, 40)
            thumb = load_thumbnail(image_path, 40)
            if thumb:
                image_label.setPixmap(thumb)
            else:
                image_label.setText("No img")
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(image_label)
            self.table.setCellWidget(row, 1, container)

            self.table.setItem(row, 2, QTableWidgetItem(name))
            if sold_by and sold_by.lower() == "service":
                price_display = "Service"
            else:
                price_display = format_money(price, symbol)
            self.table.setItem(row, 3, QTableWidgetItem(price_display))

            if sold_by and sold_by.lower() == "service":
                stock_item = QTableWidgetItem("N/A")
            else:
                stock_item = QTableWidgetItem(str(stock))
                if stock == 0:
                    stock_item.setForeground(QColor(231, 76, 60))
                elif stock <= low_stock:
                    stock_item.setForeground(QColor(230, 126, 34))
            self.table.setItem(row, 4, stock_item)

            if sold_by and sold_by.lower() == "service":
                status_text = "Service"
                status_color = QColor(52, 152, 219)
            else:
                if stock == 0:
                    status_text = "Out"
                    status_color = QColor(231, 76, 60)
                elif stock <= low_stock:
                    status_text = "Low"
                    status_color = QColor(230, 126, 34)
                else:
                    status_text = "In"
                    status_color = QColor(46, 204, 113)
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            self.table.setItem(row, 5, status_item)

    def _ensure_discount_columns(self, cursor):
        try:
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("PRAGMA table_info(product_discounts)")
            columns = {row[1] for row in cursor.fetchall()}
            if not columns:
                return
            for column, definition in {
                "discount_type": "TEXT DEFAULT 'percentage'",
                "manual_price": "REAL DEFAULT 0",
            }.items():
                if column not in columns:
                    cursor.execute(f"ALTER TABLE product_discounts ADD COLUMN {column} {definition}")
        except Exception:
            pass

    def on_row_clicked(self, row, column):
        """Handle table row click with theme-aware dialogs"""
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        try:
            prod_id = int(id_item.text())
        except Exception:
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, price, stock, sold_by FROM products WHERE id=?", (prod_id,))
        product = cursor.fetchone()
        conn.close()
        
        if product:
            name, price, stock, sold_by = product
            price = float(price) if price else 0.0
            
            if sold_by and sold_by.lower() == "service":
                # ✅ FIXED: max value increased from 1,000,000 to 999,999,999
                manual_price, ok = get_numeric_input_value(
                    self,
                    "Service Price",
                    f"Enter price for {name}:",
                    0,
                    decimals=2,
                    minimum=0,
                    maximum=999999999,
                )
                if ok:
                    self.service_selected.emit(prod_id, name, manual_price)
            else:
                if stock <= 0:
                    self._show_message("Out of Stock", f"{name} is out of stock.", QMessageBox.Icon.Warning)
                    return
                self.product_selected.emit(prod_id, name, price, stock)
    
    def _show_message(self, title, text, icon=QMessageBox.Icon.Information):
        """Show theme-aware message box"""
        is_dark = is_dark_theme()
        
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        if is_dark:
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2f3136;
                    color: #dcddde;
                }
                QMessageBox QLabel {
                    color: #dcddde;
                }
                QMessageBox QPushButton {
                    background-color: #5865f2;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #4752c4;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #3c45a3;
                }
            """)
        else:
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #ffffff;
                    color: #212529;
                }
                QMessageBox QLabel {
                    color: #212529;
                }
                QMessageBox QPushButton {
                    background-color: #5865f2;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #4752c4;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #3c45a3;
                }
            """)
        
        msg.exec()

    def scan_barcode(self):
        if self._search_filter_timer.isActive():
            self._search_filter_timer.stop()
        keyword = self.search_input.text().strip()
        if keyword:
            self.barcode_scanned.emit(keyword)
        self.search_input.clear()
        self.search_input.setFocus()

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def update_theme(self):
        if hasattr(self, "search_widget"):
            self.search_widget.apply_modern_style()
        self.grid_view.update_theme()
        self.modern_grid_view.update_theme()
        self.list_view.update_theme()
        self.category_slider.update_theme()
        colors = get_theme_colors()

        if self.use_modern_combos:
            for combo in (self.category_combo, self.discount_filter_combo, self.view_combo):
                if hasattr(combo, "apply_theme"):
                    combo.apply_theme()
            return
        
        self.view_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox:hover {{
                border: 1px solid {colors['border_hover']};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                color: {colors['text']};
                selection-background-color: {colors['border_hover']};
            }}
        """)
        
        self.category_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox:hover {{
                border: 1px solid {colors['border_hover']};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                color: {colors['text']};
                selection-background-color: {colors['border_hover']};
            }}
        """)
        self.discount_filter_combo.setStyleSheet(self.category_combo.styleSheet())

    def retranslateUi(self):
        from utils.language import lang
        current_discount_filter = self._discount_filter
        if lang.get_current() == "my":
            self.search_input.setPlaceholderText("ပစ္စည်းအမည် / ဘားကုဒ် / SKU ဖြင့် ရှာရန်...")
            self.view_label.setText("မြင်ကွင်း:")
            self.table.setHorizontalHeaderLabels(["ID", "ပုံ", "ပစ္စည်းအမည်", "စျေးနှုန်း", "ကျန်", "အခြေအနေ"])
            
            self.view_combo.blockSignals(True)
            self.view_combo.clear()
            self.view_combo.addItem("ကဒ်", self.VIEW_GRID)
            self.view_combo.addItem("မော်ဒန် ကဒ်", self.VIEW_MODERN_GRID)
            self.view_combo.addItem("စာရင်း", self.VIEW_LIST)
            self.view_combo.addItem("ဇယား", self.VIEW_TABLE)
            for i in range(self.view_combo.count()):
                if self.view_combo.itemData(i) == self._current_view:
                    self.view_combo.setCurrentIndex(i)
                    break
            self.view_combo.blockSignals(False)
            
            # ✅ Reload categories with Myanmmar language
            self.load_categories()
            
            # Update combo item texts for Myanmar
            self.category_combo.blockSignals(True)
            current = self.category_combo.currentText()
            # Keep the items as they are (they have icons and indentation)
            # Just update "All Categories" to "အားလုံး"
            if self.category_combo.count() > 0:
                self.category_combo.setItemText(0, "အားလုံး")
            idx = self.category_combo.findText(current)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setCurrentIndex(0)
            self.category_combo.blockSignals(False)

            self.discount_filter_combo.blockSignals(True)
            self.discount_filter_combo.clear()
            self.discount_filter_combo.addItem("အားလုံး", "all")
            self.discount_filter_combo.addItem("လျော့စျေးရှိ", "discount")
            index = self.discount_filter_combo.findData(current_discount_filter)
            self.discount_filter_combo.setCurrentIndex(index if index >= 0 else 0)
            self.discount_filter_combo.blockSignals(False)
            
        else:
            self.search_input.setPlaceholderText("Search by name / barcode / SKU...")
            self.view_label.setText("View:")
            self.table.setHorizontalHeaderLabels(["ID", "Image", "Name", "Price", "Stock", "Status"])
            
            self.view_combo.blockSignals(True)
            self.view_combo.clear()
            self.view_combo.addItem("Grid", self.VIEW_GRID)
            self.view_combo.addItem("Modern Grid", self.VIEW_MODERN_GRID)
            self.view_combo.addItem("List", self.VIEW_LIST)
            self.view_combo.addItem("Table", self.VIEW_TABLE)
            for i in range(self.view_combo.count()):
                if self.view_combo.itemData(i) == self._current_view:
                    self.view_combo.setCurrentIndex(i)
                    break
            self.view_combo.blockSignals(False)
            
            # ✅ Reload categories with English language
            self.load_categories()
            
            # Update combo item texts for English
            self.category_combo.blockSignals(True)
            current = self.category_combo.currentText()
            if self.category_combo.count() > 0:
                self.category_combo.setItemText(0, "All Categories")
            idx = self.category_combo.findText(current)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setCurrentIndex(0)
            self.category_combo.blockSignals(False)

            self.discount_filter_combo.blockSignals(True)
            self.discount_filter_combo.clear()
            self.discount_filter_combo.addItem("All Products", "all")
            self.discount_filter_combo.addItem("Discount Products", "discount")
            index = self.discount_filter_combo.findData(current_discount_filter)
            self.discount_filter_combo.setCurrentIndex(index if index >= 0 else 0)
            self.discount_filter_combo.blockSignals(False)
