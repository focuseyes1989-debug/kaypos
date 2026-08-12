# ui/sales_page/list_view.py

from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QSizePolicy, QFrame, QHBoxLayout,
    QLabel, QVBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.sales_page.product_utils import get_effective_stock, load_thumbnail, clear_layout_widgets
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from ui.widgets.numeric_keypad_dialog import get_numeric_input_value


class ListItemWidget(QFrame):
    """A clean product item displayed in the list view grid (No Favourite)."""
    
    clicked = pyqtSignal(int)
    
    def __init__(self, prod_id, name, price, stock, low_stock, sold_by, image_path, parent=None):
        super().__init__(parent)
        self.setObjectName("ListItemWidget")
        self.prod_id = prod_id
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(55)
        self.setMaximumHeight(75)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        colors = get_theme_colors()
        
        self.img_label = QLabel()
        self.img_label.setFixedSize(40, 40)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setScaledContents(True)
        thumb = load_thumbnail(image_path, 40, prod_id)
        if thumb:
            self.img_label.setPixmap(thumb.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        else:
            self.img_label.setText("📦")
            self.img_label.setFont(QFont("", 16))
        layout.addWidget(self.img_label)
        
        self.name_label = QLabel(name)
        self.name_label.setFont(QFont("", 10, QFont.Weight.Bold))
        self.name_label.setWordWrap(True)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.name_label.setStyleSheet(f"color: {colors['text']};")
        layout.addWidget(self.name_label)
        
        symbol = get_currency_symbol()
        sold_by_mode = str(sold_by or "").lower()
        if sold_by_mode == "service":
            price_text = "Service"
        else:
            price_text = format_money(price, symbol)
        self.price_label = QLabel(price_text)
        self.price_label.setFont(QFont("", 10))
        self.price_label.setMinimumWidth(80)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.price_label.setStyleSheet(f"color: {colors['text_secondary']};")
        layout.addWidget(self.price_label)
        
        if sold_by_mode == "service":
            stock_text = "N/A"
            stock_color = "#3498db"
        elif sold_by_mode == "restaurant":
            stock_text = "Menu"
            stock_color = "#16a085"
        else:
            stock_text = str(stock)
            if stock == 0:
                stock_color = "#e74c3c"
            elif stock <= low_stock:
                stock_color = "#e67e22"
            else:
                stock_color = "#2ecc71"
        self.stock_label = QLabel(stock_text)
        self.stock_label.setFont(QFont("", 9, QFont.Weight.Bold))
        self.stock_label.setStyleSheet(f"color: {stock_color};")
        self.stock_label.setMinimumWidth(35)
        self.stock_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.stock_label)
        
        status_text, status_color = self._get_status(sold_by, stock, low_stock)
        self.status_label = QLabel(status_text)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            f"background-color: {status_color}; color: white; border-radius: 3px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
        )
        self.status_label.setMinimumWidth(50)
        self.status_label.setMaximumWidth(70)
        layout.addWidget(self.status_label)
        
        self._apply_style()
    
    def _apply_style(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QFrame#ListItemWidget {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
            }}
            QFrame#ListItemWidget:hover {{
                border: 2px solid {colors['border_hover']};
                background-color: {colors['card_hover']};
            }}
            QFrame#ListItemWidget QLabel {{
                background-color: transparent;
                color: {colors['text']};
            }}
        """)
        self.style().unpolish(self)
        self.style().polish(self)
    
    @staticmethod
    def _get_status(sold_by, stock, low_stock):
        sold_by_mode = str(sold_by or "").lower()
        if sold_by_mode == "service":
            return "Service", "#3498db"
        if sold_by_mode == "restaurant":
            return "Menu", "#16a085"
        if stock == 0:
            return "Out", "#e74c3c"
        if stock <= low_stock:
            return "Low", "#e67e22"
        return "In", "#2ecc71"
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.prod_id)
        super().mousePressEvent(event)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = event.size().width()
        if width < 350:
            self.status_label.setVisible(False)
            self.stock_label.setVisible(False)
        elif width < 500:
            self.status_label.setVisible(False)
            self.stock_label.setVisible(True)
        else:
            self.status_label.setVisible(True)
            self.stock_label.setVisible(True)


class ListViewWidget(QScrollArea):
    """Scrollable grid list view with fixed 2 columns (No Favourite)."""
    
    product_selected = pyqtSignal(int, str, float, int)
    service_selected = pyqtSignal(int, str, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self._container = QWidget()
        self._container.setStyleSheet("background-color: transparent;")
        
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(8)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)
        
        self.setWidget(self._container)
        
        self._items = []
        self._last_rows = []
        self._cols = 2
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._delayed_populate)
        
        self._is_minimized = False
        
    def populate(self, rows):
        self._last_rows = rows
        self._items.clear()
        clear_layout_widgets(self._grid)
        
        if not rows:
            return
        
        cols = 2
        self._cols = cols
        
        for idx, prod in enumerate(rows):
            prod_id, name, price, stock, low_stock, sold_by, image_path = prod[:7]
            item = ListItemWidget(prod_id, name, price, stock, low_stock, sold_by, image_path)
            item.clicked.connect(self._on_item_clicked)
            
            row = idx // cols
            col = idx % cols
            self._grid.addWidget(item, row, col)
            self._items.append(item)
        
        total = len(rows)
        if total % cols != 0:
            for i in range(cols - (total % cols)):
                spacer = QWidget()
                spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                spacer.setMinimumHeight(55)
                spacer.setMaximumHeight(75)
                spacer.setStyleSheet("background-color: transparent;")
                self._grid.addWidget(spacer, total // cols, (total % cols) + i)
    
    def _delayed_populate(self):
        """Populate after resize delay - only if not minimized"""
        if self._is_minimized:
            return
        if self._last_rows:
            self.populate(self._last_rows)
    
    def _on_item_clicked(self, prod_id):
        """Handle list item click with theme-aware dialogs"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, price, sold_by FROM products WHERE id=?", (prod_id,))
        product = cursor.fetchone()
        stock = get_effective_stock(cursor, prod_id) if product else 0
        conn.close()
        
        if product:
            name, price, sold_by = product
            price = float(price) if price else 0.0
            
            sold_by_mode = str(sold_by or "").lower()
            if sold_by_mode == "service":
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
                if sold_by_mode == "restaurant":
                    self.product_selected.emit(prod_id, name, price, max(int(stock or 0), 999999))
                    return
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
    
    def resizeEvent(self, event):
        """Handle resize events - trigger delayed populate."""
        super().resizeEvent(event)
        width = event.size().width()
        
        if width <= 10 or event.size().height() <= 10:
            self._is_minimized = True
            return
        
        self._is_minimized = False
        self._resize_timer.start(150)
    
    def showEvent(self, event):
        """Handle show event - refresh when window is restored from minimized."""
        super().showEvent(event)
        if self._is_minimized:
            self._is_minimized = False
            if self._last_rows:
                QTimer.singleShot(100, lambda: self.populate(self._last_rows))
    
    def populate_and_store(self, rows):
        self._last_rows = rows
        self.populate(rows)
    
    def update_theme(self):
        if self._last_rows:
            self.populate(self._last_rows)
