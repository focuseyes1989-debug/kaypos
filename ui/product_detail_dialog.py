# ui/product_detail_dialog.py
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QTextEdit, QScrollArea, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QPixmap, QColor, QIcon, QFontMetrics
from models.database import connect_db
from utils.paths import app_path
import functools


# ========== IMAGE PATH RESOLVER ==========
def _find_image_file(search_dir, filename):
    """Recursively search for an image file in a directory."""
    if not os.path.isdir(search_dir):
        return None
    
    for root, _, files in os.walk(search_dir):
        if filename in files:
            return os.path.join(root, filename)
    
    return None


def resolve_image_path(image_path: str):
    """Resolve image path with fallback for portable paths."""
    if not image_path:
        return ""
    
    # If path is already absolute, use it
    if os.path.isabs(image_path):
        if os.path.exists(image_path):
            return image_path
        # If absolute path doesn't exist, try to find by filename
        return _find_relative_image(image_path)
    
    # Try relative paths
    possible_paths = [
        image_path,
        os.path.join('database', 'product_images', os.path.basename(image_path)),
        app_path(image_path),
        app_path('database', 'product_images', os.path.basename(image_path)),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Last resort: search in product_images directory
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
        app_path('database', 'product_images'),
    ]
    
    for search_dir in search_dirs:
        full_path = os.path.join(search_dir, filename)
        if os.path.exists(full_path):
            return full_path
    
    return None


@functools.lru_cache(maxsize=200)
def load_product_image(image_path: str, width: int = 400, height: int = 400):
    """Load and scale product image with caching."""
    if not image_path:
        return None
    
    resolved_path = resolve_image_path(image_path)
    if not resolved_path or not os.path.exists(resolved_path):
        return None
    
    pixmap = QPixmap(resolved_path)
    if pixmap.isNull():
        return None
    
    # Scale image maintaining aspect ratio
    return pixmap.scaled(
        width, height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )


# ========== PRODUCT DETAIL DIALOG ==========
class ProductDetailDialog(QDialog):
    def __init__(self, product_id):
        super().__init__()
        self.product_id = product_id
        self.setWindowTitle("Product Details")
        self.setMinimumSize(600, 700)
        self.setModal(True)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))

        # Store product data for later status update
        self.product_data = None
        self.image_label_width = 0
        self.image_label_height = 0

        # Property keys (English)
        self.property_keys = [
            "SKU", "Name", "Category", "Barcode",
            "Price", "Stock", "Low Stock Alert", "Expire Date", "Status", "Description"
        ]
        # Myanmar translations
        self.property_my = [
            "SKU", "ပစ္စည်းအမည်", "အမျိုးအစား", "ဘားကုဒ်",
            "စျေးနှုန်း", "ကျန်ရှိသိုလှောင်မှု", "သတိပေးသိုလှောင်မှု", 
            "သက်တမ်းကုန်ရက်", "အခြေအနေ", "ဖော်ပြချက်"
        ]

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)

        # ----- Product Image -----
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedHeight(250)
        self.image_label.setMinimumHeight(200)
        self.image_label.setStyleSheet("""
            border: 1px solid #ccc; 
            background-color: #fafafa;
            border-radius: 8px;
        """)
        self.image_label.setText("Loading image...")
        main_layout.addWidget(self.image_label)

        # ----- Details Table -----
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #dcdcdc;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: none;
            }
        """)

        self.table.setRowCount(len(self.property_keys))
        self.table_items = []  # store references to left column items for later translation
        
        # Set default row heights
        default_row_height = 35
        description_row_height = 120  # ✅ Description row ကို ပိုမြင့်အောင်
        
        for row, prop in enumerate(self.property_keys):
            item_prop = QTableWidgetItem(prop)
            font = item_prop.font()
            font.setBold(True)
            item_prop.setFont(font)
            self.table.setItem(row, 0, item_prop)
            self.table_items.append(item_prop)
            
            # Set row height
            if prop == "Description":
                # ✅ Description row ကို ပိုမြင့်အောင်သတ်မှတ်
                self.table.setRowHeight(row, description_row_height)
            else:
                self.table.setRowHeight(row, default_row_height)
            
            # Description row အတွက် QTextEdit widget ထည့်
            if prop == "Description":
                # Create a container widget for description
                desc_container = QWidget()
                desc_layout = QVBoxLayout(desc_container)
                desc_layout.setContentsMargins(4, 4, 4, 4)
                desc_layout.setSpacing(0)
                
                self.description_text = QTextEdit()
                self.description_text.setReadOnly(True)
                self.description_text.setStyleSheet("""
                    QTextEdit {
                        border: none;
                        background-color: transparent;
                        font-size: 13px;
                        padding: 4px;
                    }
                """)
                # ✅ Description text ရဲ့ အမြင့်ကို row height နဲ့လိုက်အောင်
                self.description_text.setMaximumHeight(description_row_height - 10)
                self.description_text.setMinimumHeight(40)
                self.description_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                
                desc_layout.addWidget(self.description_text)
                self.table.setCellWidget(row, 1, desc_container)
            else:
                self.table.setItem(row, 1, QTableWidgetItem("-"))

        # ✅ Table row height ကို resize လုပ်နိုင်အောင်
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(default_row_height)

        main_layout.addWidget(self.table)

        # ----- Close Button REMOVED -----
        # Close button ကို ဖယ်ရှားလိုက်ပါပြီ။ Esc key နဲ့ပဲ ပိတ်နိုင်ပါပြီ။

        self.setLayout(main_layout)

        # Load data and apply language
        self.load_product_data()
        self.retranslateUi()

    # ---------- Keyboard shortcut ----------
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        super().keyPressEvent(event)

    # ---------- Language support ----------
    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            lang = row[0] if row else "en"
            conn.close()
        except:
            lang = "en"
        return lang

    def retranslateUi(self):
        lang = self.get_lang()
        if lang == "my":
            # Myanmar (Burmese)
            self.setWindowTitle("ပစ္စည်းအသေးစိတ်")
            for row, text in enumerate(self.property_my):
                self.table_items[row].setText(text)
            self.table.setHorizontalHeaderLabels(["အကြောင်းအရာ", "တန်ဖိုး"])
            # Update image placeholder texts
            current_img_text = self.image_label.text()
            if current_img_text == "Loading image...":
                self.image_label.setText("ပုံတင်နေသည်...")
            elif current_img_text == "Invalid image file":
                self.image_label.setText("ပုံဖိုင်မမှန်ပါ")
            elif current_img_text == "No image available":
                self.image_label.setText("ပုံမရှိပါ")
            elif current_img_text == "Image not found":
                self.image_label.setText("ပုံမတွေ့ပါ")
        else:
            # English
            self.setWindowTitle("Product Details")
            for row, text in enumerate(self.property_keys):
                self.table_items[row].setText(text)
            self.table.setHorizontalHeaderLabels(["Property", "Value"])
            # Restore image placeholder texts
            current_img_text = self.image_label.text()
            if current_img_text == "ပုံတင်နေသည်...":
                self.image_label.setText("Loading image...")
            elif current_img_text == "ပုံဖိုင်မမှန်ပါ":
                self.image_label.setText("Invalid image file")
            elif current_img_text == "ပုံမရှိပါ":
                self.image_label.setText("No image available")
            elif current_img_text == "ပုံမတွေ့ပါ":
                self.image_label.setText("Image not found")

        # Refresh the status value (because it contains translated text)
        self.update_status_value()

    def update_status_value(self):
        """Re-compute and update the status row using current language."""
        if not self.product_data:
            return
        sku, name, category, barcode, price, stock, low_stock, expire_date, image_path, description = self.product_data
        stock_val = int(stock) if stock is not None else 0
        low_val = int(low_stock) if low_stock is not None else 0
        today = QDate.currentDate()
        lang = self.get_lang()

        # Determine status text in current language
        if stock_val == 0:
            status_text = "Out of Stock" if lang != "my" else "ကုန်သွားပြီ"
            status_color = "red"
        elif stock_val <= low_val:
            status_text = "Low Stock" if lang != "my" else "စတော့နည်းနေပြီ"
            status_color = "orange"
        else:
            status_text = "In Stock" if lang != "my" else "ကျန်ရှိသည်"
            status_color = "green"

        if expire_date:
            try:
                expire_qdate = QDate.fromString(expire_date, "yyyy-MM-dd")
                if expire_qdate < today:
                    if lang == "my":
                        status_text += " | သက်တမ်းကုန်ပြီ"
                    else:
                        status_text += " | Expired"
                    status_color = "red"
                elif expire_qdate <= today.addDays(7):
                    if lang == "my":
                        status_text += " | သက်တမ်းနီးပြီ"
                    else:
                        status_text += " | Expiring Soon"
                    if status_color != "red":
                        status_color = "orange"
            except:
                pass

        # Create and style the status item
        status_item = QTableWidgetItem(status_text)
        if status_color == "red":
            status_item.setForeground(QColor(231, 76, 60))
            status_item.setBackground(QColor(255, 240, 240))
        elif status_color == "orange":
            status_item.setForeground(QColor(230, 126, 34))
            status_item.setBackground(QColor(255, 245, 235))
        else:
            status_item.setForeground(QColor(46, 204, 113))
            status_item.setBackground(QColor(240, 255, 240))
        status_item.setFont(self.table.font())
        
        try:
            status_row = self.property_keys.index("Status")
            self.table.setItem(status_row, 1, status_item)
        except ValueError:
            pass

    def load_product_data(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sku, name, category, barcode, price, stock, low_stock,
                       expire_date, image, description
                FROM products WHERE id=?
            """, (self.product_id,))
            product = cursor.fetchone()
            conn.close()

            if not product:
                self.set_table_value("SKU", "Product not found")
                return

            self.product_data = product
            sku, name, category, barcode, price, stock, low_stock, expire_date, image_path, description = product

            stock_val = int(stock) if stock is not None else 0
            low_val = int(low_stock) if low_stock is not None else 0
            price_val = float(price) if price is not None else 0.0

            self.set_table_value("SKU", sku or "-")
            self.set_table_value("Name", name or "-")
            self.set_table_value("Category", category or "-")
            self.set_table_value("Barcode", barcode or "-")
            self.set_table_value("Price", f"{price_val:.2f}")
            self.set_table_value("Stock", str(stock_val))
            self.set_table_value("Low Stock Alert", str(low_val))
            self.set_table_value("Expire Date", expire_date or "None")

            # ✅ Set Description with auto-height adjustment
            if description:
                self.description_text.setPlainText(description)
                # ✅ Description length ပေါ်မူတည်ပြီး row height ကို auto adjust လုပ်
                self.adjust_description_height(description)
            else:
                no_desc = "No description" if self.get_lang() != "my" else "ဖော်ပြချက်မရှိပါ"
                self.description_text.setPlainText(no_desc)
                self.adjust_description_height(no_desc)

            # Load image using the improved resolver
            self.load_image(image_path)
            
            # Status will be set in retranslateUi() -> update_status_value()
        except Exception as e:
            self.set_table_value("SKU", f"Error: {str(e)}")

    def adjust_description_height(self, text):
        """
        ✅ Description text ရဲ့ အရှည်ပေါ်မူတည်ပြီး row height ကို auto adjust လုပ်ပေး
        """
        try:
            # Get description row index
            desc_row = self.property_keys.index("Description")
            
            # Calculate needed height based on text length
            # Base height: 40px, each ~100 characters add 20px
            text_length = len(text)
            
            # Count newlines for better estimation
            newline_count = text.count('\n')
            
            # Estimate height: base + (lines * line_height)
            # Line height ~ 20px, base padding ~ 20px
            estimated_lines = max(1, (text_length // 50) + 1 + newline_count)
            estimated_height = max(40, min(200, estimated_lines * 22 + 20))
            
            # Set row height
            self.table.setRowHeight(desc_row, estimated_height)
            
            # Update QTextEdit height
            self.description_text.setMaximumHeight(estimated_height - 10)
            self.description_text.setMinimumHeight(40)
            
        except Exception as e:
            # Fallback: use default height
            try:
                desc_row = self.property_keys.index("Description")
                self.table.setRowHeight(desc_row, 80)
            except:
                pass

    def set_table_value(self, property_name, value):
        """Set value for a table row (non-description rows)."""
        try:
            row = self.property_keys.index(property_name)
            # Skip description row (handled separately)
            if property_name == "Description":
                return
            self.table.setItem(row, 1, QTableWidgetItem(value))
        except ValueError:
            pass

    def load_image(self, image_path):
        """Load product image with improved path resolution."""
        lang = self.get_lang()
        
        if not image_path:
            self.image_label.setText("No image available" if lang != "my" else "ပုံမရှိပါ")
            return
        
        # Use the improved resolve_image_path function
        resolved_path = resolve_image_path(image_path)
        
        if not resolved_path:
            self.image_label.setText("Image not found" if lang != "my" else "ပုံမတွေ့ပါ")
            return
        
        if os.path.exists(resolved_path):
            try:
                # Load and scale image
                pixmap = QPixmap(resolved_path)
                if not pixmap.isNull():
                    # Get label size
                    label_width = self.image_label.width() - 20
                    label_height = self.image_label.height() - 20
                    
                    # If label size is 0 (not visible yet), use default
                    if label_width <= 0:
                        label_width = 400
                    if label_height <= 0:
                        label_height = 230
                    
                    # Scale image maintaining aspect ratio
                    scaled = pixmap.scaled(
                        label_width,
                        label_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled)
                    self.image_label.setText("")
                    return
                else:
                    self.image_label.setText("Invalid image file" if lang != "my" else "ပုံဖိုင်မမှန်ပါ")
                    return
            except Exception as e:
                print(f"Error loading image: {e}")
                self.image_label.setText("Invalid image file" if lang != "my" else "ပုံဖိုင်မမှန်ပါ")
                return
        else:
            # Try one more time with just the filename
            filename = os.path.basename(image_path)
            product_images_dir = app_path('database', 'product_images')
            found_path = _find_image_file(product_images_dir, filename)
            
            if found_path and os.path.exists(found_path):
                try:
                    pixmap = QPixmap(found_path)
                    if not pixmap.isNull():
                        label_width = self.image_label.width() - 20
                        label_height = self.image_label.height() - 20
                        if label_width <= 0:
                            label_width = 400
                        if label_height <= 0:
                            label_height = 230
                        
                        scaled = pixmap.scaled(
                            label_width,
                            label_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.image_label.setPixmap(scaled)
                        self.image_label.setText("")
                        return
                except:
                    pass
            
            self.image_label.setText("Image not found" if lang != "my" else "ပုံမတွေ့ပါ")

    def resizeEvent(self, event):
        """Handle resize event to update image scaling."""
        super().resizeEvent(event)
        # If there's an image loaded, reload it with new size
        if self.product_data and len(self.product_data) >= 10:
            image_path = self.product_data[8]
            if image_path:
                # Reload image with current size
                self.load_image(image_path)