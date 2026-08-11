# ui/products_page/product_table.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QInputDialog, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QColor, QImageReader
from utils.currency import get_currency_symbol, format_money
from models.database import connect_db
from ui.widgets.pagination_widget import PaginationWidget
from ui.product_detail_dialog import ProductDetailDialog
from utils.paths import app_path
from utils.product_image_store import cached_product_image_path
import functools
import os

# ✅ Import theme manager
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors


def _find_image_file(search_dir, filename):
    """Recursively search for an image file in a directory."""
    if not os.path.isdir(search_dir):
        return None
    
    for root, _, files in os.walk(search_dir):
        if filename in files:
            return os.path.join(root, filename)
    
    return None


def resolve_image_path(image_path: str):
    """Resolve image path with fallback."""
    if not image_path:
        return ""
    
    # ✅ If path is already absolute, use it
    if os.path.isabs(image_path):
        if os.path.exists(image_path):
            return image_path
        # If absolute path doesn't exist, try to find relative
        return _find_relative_image(image_path)
    
    # ✅ Try relative paths
    possible_paths = [
        image_path,
        os.path.join('database', 'product_images', os.path.basename(image_path)),
        app_path(image_path),
        app_path('database', 'product_images', os.path.basename(image_path)),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # ✅ Last resort: search in product_images directory
    product_images_dir = app_path('database', 'product_images')
    if os.path.isdir(product_images_dir):
        filename = os.path.basename(image_path)
        found = _find_image_file(product_images_dir, filename)
        if found:
            return found
    
    return image_path


def _find_relative_image(image_path):
    """Try to find an image by its filename in common locations."""
    if not image_path:
        return None
    
    filename = os.path.basename(image_path)
    
    # Search in common locations
    search_dirs = [
        'database/product_images',
        'database/product_images/thumbnails',
        'assets/images/products',
        '.',
    ]
    
    for search_dir in search_dirs:
        full_path = os.path.join(search_dir, filename)
        if os.path.exists(full_path):
            return full_path
    
    return None


@functools.lru_cache(maxsize=200)
def load_thumbnail(image_path: str, size: int = 50, product_id=None):
    """Load product thumbnail with caching"""
    if not image_path and not product_id:
        return None
    
    resolved_path = resolve_image_path(image_path)
    if not resolved_path or not os.path.exists(resolved_path):
        resolved_path = cached_product_image_path(product_id, image_path)
        if not resolved_path or not os.path.exists(resolved_path):
            return None
    
    # Use optimized thumbnail from image_optimizer
    try:
        from utils.image_optimizer import ImageOptimizer
        thumb_path = ImageOptimizer.get_thumbnail_path(resolved_path, (size, size))
        
        if thumb_path and os.path.exists(thumb_path):
            pixmap = QPixmap(thumb_path)
            if not pixmap.isNull():
                return pixmap
    except:
        pass
    
    # Fallback: original method
    reader = QImageReader(resolved_path)
    reader.setScaledSize(QSize(size, size))
    image = reader.read()
    if not image.isNull():
        return QPixmap.fromImage(image)
    return None


def get_product_category(product_id):
    """Get category name for a product"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT category FROM products WHERE id=?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""


def get_product_category_group(product_id):
    """Get category group name for a product"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cg.name 
        FROM products p
        LEFT JOIN categories c ON p.category = c.name
        LEFT JOIN category_groups cg ON c.group_id = cg.id
        WHERE p.id = ?
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""


class ProductTable(QWidget):
    product_selected = pyqtSignal(int, str, float, int)
    service_selected = pyqtSignal(int, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_page = 1
        self.rows_per_page = 50
        self.current_rows = []
        self.setup_ui()
        
        # ✅ Connect theme manager for auto refresh
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        # Column count: ID, Image, Name, Category, Category Group, Barcode, Price, Stock, Sold By, Status
        self.table.setColumnCount(10)
        self.table.setColumnHidden(0, True)  # Hide ID column
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # ❌ REMOVE cellClicked - ဒီနေရာမှာ ဖယ်ရှားလိုက်ပါ
        # self.table.cellClicked.connect(self.on_row_clicked)  <-- ဒီ line ကို ဖယ်ရှားပါ
        
        # ✅ Keep only double click for product detail
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        self.table.verticalHeader().setDefaultSectionSize(60)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # Image
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Category
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Category Group
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Barcode
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Price
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Stock
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Sold By
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)  # Status

        # Set column width for image
        self.table.setColumnWidth(1, 70)
        
        # ✅ NO custom scrollbar style - use PyQt6 default
        # self._apply_scrollbar_style()  <-- ဒီ line ကို ဖယ်ရှားပါ

        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)

        layout.addWidget(self.table)
        layout.addWidget(self.pagination)
        self.setLayout(layout)

    def _on_theme_changed(self, theme_name):
        """✅ Handle theme change - refresh table"""
        # ✅ No style to update - just refresh
        if self.current_rows:
            self.populate_table(self.current_rows)

    def on_cell_double_clicked(self, row, column):
        """Handle double click on product row - show product detail dialog"""
        id_item = self.table.item(row, 0)
        if id_item:
            try:
                product_id = int(id_item.text())
                dialog = ProductDetailDialog(product_id)
                dialog.exec()
            except ValueError:
                pass

    def on_page_changed(self, page: int, page_size: int):
        self.current_page = page
        self.rows_per_page = page_size
        parent = self.parent()
        if parent and hasattr(parent, 'apply_filter'):
            parent.current_page = page
            parent.items_per_page = page_size
            parent.apply_filter()

    # ❌ REMOVE on_row_clicked method entirely - ဒီ method ကို ဖယ်ရှားပါ
    # def on_row_clicked(self, row, column):
    #     ...

    def populate_table(self, rows):
        symbol = get_currency_symbol()
        self.table.setRowCount(0)
        self.current_rows = rows
        
        # Pre-fetch categories and groups for all products
        product_data = []
        for row_data in rows:
            if len(row_data) >= 7:
                prod_id, name, price, stock, low_stock, sold_by, image_path = row_data[:7]
            else:
                continue
            
            category = get_product_category(prod_id)
            category_group = get_product_category_group(prod_id)
            product_data.append({
                'id': prod_id,
                'name': name,
                'price': price,
                'stock': stock,
                'low_stock': low_stock,
                'sold_by': sold_by,
                'image_path': image_path,
                'category': category,
                'category_group': category_group
            })
        
        for data in product_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Column 0: ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(data['id'])))

            # Column 1: Image thumbnail
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setScaledContents(True)
            image_label.setFixedSize(50, 50)
            thumb = load_thumbnail(data['image_path'], 50, data['id'])
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

            # Column 2: Name
            self.table.setItem(row, 2, QTableWidgetItem(data['name']))
            
            # Column 3: Category
            self.table.setItem(row, 3, QTableWidgetItem(data['category']))
            
            # Column 4: Category Group
            self.table.setItem(row, 4, QTableWidgetItem(data['category_group']))
            
            # Column 5: Barcode
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT barcode FROM products WHERE id=?", (data['id'],))
            barcode_data = cursor.fetchone()
            conn.close()
            barcode = barcode_data[0] if barcode_data and barcode_data[0] else ""
            self.table.setItem(row, 5, QTableWidgetItem(barcode))
            
            # Column 6: Price
            if data['sold_by'] and data['sold_by'].lower() == "service":
                price_display = "Service"
            else:
                price_display = format_money(data['price'], symbol)
            self.table.setItem(row, 6, QTableWidgetItem(price_display))

            # Column 7: Stock
            if data['sold_by'] and data['sold_by'].lower() == "service":
                stock_item = QTableWidgetItem("N/A")
            else:
                stock_val = data['stock'] if data['stock'] is not None else 0
                stock_item = QTableWidgetItem(str(stock_val))
                if stock_val == 0:
                    stock_item.setForeground(QColor(231, 76, 60))
                elif stock_val <= (data['low_stock'] if data['low_stock'] else 0):
                    stock_item.setForeground(QColor(230, 126, 34))
            self.table.setItem(row, 7, stock_item)
            
            # Column 8: Sold By
            sold_by_display = data['sold_by'] if data['sold_by'] else "Each"
            self.table.setItem(row, 8, QTableWidgetItem(sold_by_display))

            # Column 9: Status
            if data['sold_by'] and data['sold_by'].lower() == "service":
                status_text = "Service"
                status_color = QColor(52, 152, 219)
            else:
                stock_val = data['stock'] if data['stock'] is not None else 0
                low_val = data['low_stock'] if data['low_stock'] else 0
                if stock_val == 0:
                    status_text = "Out of Stock"
                    status_color = QColor(231, 76, 60)
                elif stock_val <= low_val:
                    status_text = "Low Stock"
                    status_color = QColor(230, 126, 34)
                else:
                    status_text = "In Stock"
                    status_color = QColor(46, 204, 113)
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            self.table.setItem(row, 9, status_item)
        
        # ✅ NO custom scrollbar style - use PyQt6 default
        # self._apply_scrollbar_style()  <-- ဒီ line ကို ဖယ်ရှားပါ

    def get_selected_product_id(self):
        selected = self.table.currentRow()
        if selected >= 0:
            id_item = self.table.item(selected, 0)
            if id_item:
                return int(id_item.text())
        return None

    def get_current_rows(self):
        return self.current_rows

    def set_pagination_total(self, total):
        self.pagination.set_total_items(total, emit_signal=False)

    def get_pagination(self):
        return self.pagination

    def retranslateUi(self):
        from utils.language import lang
        if lang.get_current() == "my":
            headers = ["ID", "ပုံ", "ပစ္စည်းအမည်", "အမျိုးအစား", "အုပ်စု", "ဘားကုဒ်", "စျေးနှုန်း", "ကျန်", "ရောင်းပုံစံ", "အခြေအနေ"]
        else:
            headers = ["ID", "Image", "Name", "Category", "Category Group", "Barcode", "Price", "Stock", "Sold By", "Status"]
        self.table.setHorizontalHeaderLabels(headers)
    
    def showEvent(self, event):
        """✅ Handle show event"""
        super().showEvent(event)
