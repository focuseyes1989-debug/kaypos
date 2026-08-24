# ui/cashier_window/cart_widget.py
"""
Cashier Mode - Mobile Style Cart Widget
Mobile App ပုံစံအတိုင်း သုံးရလွယ်ကူသော ဈေးခြင်း
"""

import json
import os
from typing import List, Dict, Any, Optional, cast

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QApplication, QSpacerItem, QMenu, QDialog, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialogButtonBox, QAbstractSpinBox, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, Qt, QPropertyAnimation, QEasingCurve, QDate
from PyQt6.QtGui import QAction, QFont, QColor, QPalette, QMouseEvent, QPixmap, QPainter

from utils.currency import get_currency_symbol, format_money
from models.database import connect_db
from loguru import logger
from ui.themes.theme_manager import (
    get_theme_colors,
    is_dark_theme,
    register_theme_callback,
    unregister_theme_callback,
    get_current_theme,
    get_icon_with_color,
)
from ui.widgets.modern_button import ModernButton
from ui.widgets.numeric_keypad_dialog import NumericKeypadDialog, get_numeric_input_value
from ui.sales_page.product_utils import effective_stock_sql, get_effective_stock
from utils.wholesale_pricing import ensure_wholesale_schema, get_best_price_tier, get_price_tier_by_barcode

# Backup file path
CART_BACKUP_FILE = "temp/cart_backup.json"

def save_cart_to_file(cart):
    try:
        os.makedirs("temp", exist_ok=True)
        with open(CART_BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(cart, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save cart backup: {e}")

def load_cart_from_file():
    try:
        if os.path.exists(CART_BACKUP_FILE):
            with open(CART_BACKUP_FILE, 'r', encoding='utf-8') as f:
                cart = json.load(f)
                valid_cart = []
                for item in cart:
                    if all(k in item for k in ('id', 'name', 'price', 'qty', 'is_service')):
                        item['qty'] = max(1, int(item['qty']))
                        valid_cart.append(item)
                return valid_cart
    except Exception as e:
        logger.error(f"Failed to load cart backup: {e}")
    return []

def delete_cart_backup():
    try:
        if os.path.exists(CART_BACKUP_FILE):
            os.remove(CART_BACKUP_FILE)
    except Exception as e:
        logger.error(f"Failed to delete cart backup: {e}")


# ============================================================
# ✅ SIMPLE QUANTITY DIALOG - THEME AWARE
# ============================================================
class QuantityDialog(QDialog):
    """Simple quantity dialog with theme support"""
    
    def __init__(self, product_name: str, current_qty: int, max_qty: int, parent=None):
        super().__init__(parent)
        self.product_name = product_name
        self.current_qty = current_qty
        self.max_qty = max_qty
        self.result_qty = current_qty
        
        self._setup_ui()
        self._apply_theme()
        
        register_theme_callback(self._on_theme_changed)
        self.destroyed.connect(lambda *_: unregister_theme_callback(self._on_theme_changed))
    
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Update Quantity")
        self.setModal(True)
        self.setFixedSize(320, 150)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)
        
        # Label
        self.label = QLabel(f"Quantity for {self.product_name}:")
        self.label.setStyleSheet("font-size: 10pt;")
        layout.addWidget(self.label)
        
        # Spin Box
        self.spin_box = QSpinBox()
        self.spin_box.setRange(1, self.max_qty)
        self.spin_box.setValue(self.current_qty)
        self.spin_box.setFixedHeight(36)
        self.spin_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_box.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self._setup_quantity_keypad_action()
        layout.addWidget(self.spin_box)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setFixedHeight(32)
        self.ok_btn.setMinimumWidth(80)
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
    
    def _apply_theme(self):
        """Apply theme to dialog"""
        is_dark = is_dark_theme()
        
        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2f3136;
                }
                QLabel {
                    color: #dcddde;
                    background-color: transparent;
                }
                QSpinBox {
                    background-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 4px;
                    color: #dcddde;
                }
                QSpinBox:focus {
                    border: 1px solid #5865f2;
                }
                QPushButton {
                    background-color: #40444b;
                    color: #dcddde;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
                }
                QPushButton:hover {
                    background-color: #5865f2;
                    color: white;
                }
                QPushButton#ok_btn {
                    background-color: #5865f2;
                    color: white;
                }
                QPushButton#ok_btn:hover {
                    background-color: #4752c4;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                }
                QLabel {
                    color: #2e3338;
                    background-color: transparent;
                }
                QSpinBox {
                    background-color: #ffffff;
                    border: 1px solid #d0d3d9;
                    border-radius: 4px;
                    color: #2e3338;
                }
                QSpinBox:focus {
                    border: 1px solid #5865f2;
                }
                QPushButton {
                    background-color: #ebedef;
                    color: #2e3338;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
                }
                QPushButton:hover {
                    background-color: #5865f2;
                    color: white;
                }
                QPushButton#ok_btn {
                    background-color: #5865f2;
                    color: white;
                }
                QPushButton#ok_btn:hover {
                    background-color: #4752c4;
                }
            """)
        
        self.ok_btn.setObjectName("ok_btn")
    
    def _on_ok_clicked(self):
        """Handle OK button click"""
        self.result_qty = self.spin_box.value()
        self.accept()

    def _setup_quantity_keypad_action(self):
        colors = get_theme_colors()
        icon = get_icon_with_color("keyboard", colors.get("text_secondary", "#6c757d"), (18, 18))
        self.quantity_keypad_action = self.spin_box.lineEdit().addAction(
            icon,
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self.quantity_keypad_action.triggered.connect(self._open_quantity_keypad)

    def _open_quantity_keypad(self):
        dialog = NumericKeypadDialog(
            "Quantity",
            self.spin_box.value(),
            self,
            decimals=0,
            minimum=1,
            maximum=self.max_qty,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.result_qty = int(dialog.value())
            self.spin_box.setValue(self.result_qty)
            self.accept()
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._apply_theme()
        if hasattr(self, "quantity_keypad_action"):
            colors = get_theme_colors()
            self.quantity_keypad_action.setIcon(
                get_icon_with_color("keyboard", colors.get("text_secondary", "#6c757d"), (18, 18))
            )
    
    def get_quantity(self) -> int:
        """Get the selected quantity"""
        return self.result_qty


class CartItemWidget(QFrame):
    """Individual cart item widget - Mobile style card"""
    
    qty_changed = pyqtSignal(int, int)  # row, new_qty
    remove_requested = pyqtSignal(int)  # row
    location_change_requested = pyqtSignal(int)  # row
    
    def __init__(self, row: int, item: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.row = row
        self.item = item
        self._is_dark = is_dark_theme()
        
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(72)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        self._setup_ui()
        self._apply_theme()
        
        register_theme_callback(self._on_theme_changed)
        self.destroyed.connect(lambda *_: unregister_theme_callback(self._on_theme_changed))
    
    def _setup_ui(self):
        """Setup the item UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)
        
        # Product Name
        self.name_label = QLabel(self.item["name"])
        self.name_label.setStyleSheet("""
            font-size: 10pt;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.name_label)
        
        # qty x price | amount
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(6)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout = QHBoxLayout()
        left_layout.setSpacing(4)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Qty label (clickable)
        self.qty_label = QLabel(str(self.item["qty"]))
        self.qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qty_label.setFixedWidth(24)
        self.qty_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qty_label.setStyleSheet("""
            font-size: 10pt;
            font-weight: bold;
            background: transparent;
            color: #5865f2;
            border: 1px solid #5865f2;
            border-radius: 4px;
            padding: 0px 2px;
        """)
        self.qty_label.mousePressEvent = self._on_qty_clicked
        left_layout.addWidget(self.qty_label)
        
        self.x_label = QLabel("×")
        self.x_label.setStyleSheet("""
            font-size: 8pt;
            background: transparent;
            border: none;
            padding: 0 2px;
        """)
        left_layout.addWidget(self.x_label)
        
        symbol = get_currency_symbol()
        self.price_label = QLabel(format_money(self.item["price"], symbol))
        self.price_label.setStyleSheet("""
            font-size: 9pt;
            background: transparent;
            border: none;
        """)
        left_layout.addWidget(self.price_label)

        if self.item.get("wholesale_tier_id"):
            min_qty = self.item.get("wholesale_min_qty") or ""
            unit_label = self.item.get("wholesale_unit_label") or "qty"
            self.wholesale_label = QLabel(f"Wholesale {min_qty}+ {unit_label}")
            self.wholesale_label.setStyleSheet("""
                font-size: 8pt;
                color: #16a085;
                background: transparent;
                border: none;
            """)
            left_layout.addWidget(self.wholesale_label)

        discount_percent = float(
            self.item.get("expiry_discount_percent")
            or self.item.get("promo_discount_percent")
            or 0
        )
        if discount_percent > 0:
            original_price = float(self.item.get("original_price") or self.item["price"])
            source = "Expiry" if self.item.get("expiry_discount_enabled") else "Promo"
            self.discount_label = QLabel(f"{source} -{discount_percent:g}% ({format_money(original_price, symbol)})")
            self.discount_label.setStyleSheet("""
                font-size: 8pt;
                color: #e67e22;
                background: transparent;
                border: none;
            """)
            left_layout.addWidget(self.discount_label)
        
        row2_layout.addLayout(left_layout)
        row2_layout.addStretch()
        
        total = self.item["price"] * self.item["qty"]
        self.total_label = QLabel(format_money(total, symbol))
        self.total_label.setStyleSheet("""
            font-size: 10pt;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        row2_layout.addWidget(self.total_label)
        
        layout.addLayout(row2_layout)

        location = self.item.get("location")
        location_text = str(location) if location and not self.item.get("is_service", False) else "N/A" if self.item.get("is_service", False) else "-"
        self.location_label = QLabel(f"Location: {location_text}")
        self.location_label.setStyleSheet("""
            font-size: 8.5pt;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.location_label)
    
    def _show_context_menu(self, position):
        """Show context menu on right-click with theme support"""
        menu = QMenu(self)
        is_dark = is_dark_theme()
        
        if is_dark:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2f3136;
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item {
                    background-color: transparent;
                    padding: 6px 24px;
                    color: #dcddde;
                    border-radius: 4px;
                }
                QMenu::item:selected {
                    background-color: #5865f2;
                    color: white;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #40444b;
                    margin: 4px 8px;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #d0d3d9;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item {
                    background-color: transparent;
                    padding: 6px 24px;
                    color: #2e3338;
                    border-radius: 4px;
                }
                QMenu::item:selected {
                    background-color: #5865f2;
                    color: white;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #d0d3d9;
                    margin: 4px 8px;
                }
            """)
        
        from typing import cast

        info_action = cast(QAction, menu.addAction(f"📦 {self.item['name']}"))
        info_action.setEnabled(False)
        menu.addSeparator()
        if not self.item.get("is_service", False) and not self.item.get("variant_id"):
            location_action = cast(QAction, menu.addAction("Change Location/Batch"))
            location_action.triggered.connect(lambda: self.location_change_requested.emit(self.row))
            menu.addSeparator()
        delete_action = cast(QAction, menu.addAction("🗑️ Delete"))
        delete_action.triggered.connect(self._on_delete_clicked)
        menu.exec(self.mapToGlobal(position))
    
    def _show_themed_message_box(self, title, message, icon=QMessageBox.Icon.Question):
        """Show a themed message box"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        
        is_dark = is_dark_theme()
        
        if is_dark:
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2f3136;
                }
                QMessageBox QLabel {
                    color: #dcddde;
                    background-color: transparent;
                }
                QMessageBox QPushButton {
                    background-color: #40444b;
                    color: #dcddde;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5865f2;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes {
                    background-color: #ed4245;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes:hover {
                    background-color: #c03537;
                }
            """)
        else:
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #ffffff;
                }
                QMessageBox QLabel {
                    color: #2e3338;
                    background-color: transparent;
                }
                QMessageBox QPushButton {
                    background-color: #ebedef;
                    color: #2e3338;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5865f2;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes {
                    background-color: #dc3545;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes:hover {
                    background-color: #c82333;
                }
            """)
        
        return msg_box
    
    def _on_delete_clicked(self):
        """Handle delete from context menu"""
        msg_box = self._show_themed_message_box(
            "Confirm Delete",
            f"Remove '{self.item['name']}' from cart?",
            QMessageBox.Icon.Question
        )
        
        yes_button = msg_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
        no_button = msg_box.addButton("No", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(no_button)
        msg_box.exec()
        
        if msg_box.clickedButton() == yes_button:
            self.remove_requested.emit(self.row)
    
    def _on_qty_clicked(self, ev: Optional[QMouseEvent] = None):
        """Handle click on qty label - show simple quantity dialog"""
        if ev is None:
            return

        current_qty = self.item["qty"]
        is_service = self.item.get("is_service", False)
        max_qty = 999999
        
        if not is_service:
            conn = connect_db()
            cursor = conn.cursor()
            location_id = self.item.get("location_id")
            if location_id:
                cursor.execute(
                    "SELECT quantity FROM product_locations WHERE id = ? AND product_id = ?",
                    (location_id, self.item["id"]),
                )
                result = cursor.fetchone()
                max_qty = int(result[0] or 0) if result else 0
            elif self.item.get("variant_id"):
                cursor.execute(
                    "SELECT stock FROM product_variants WHERE id = ? AND product_id = ?",
                    (self.item["variant_id"], self.item["id"]),
                )
                result = cursor.fetchone()
                max_qty = int(result[0] or 0) if result else 0
            else:
                max_qty = get_effective_stock(cursor, int(self.item["id"]))
            conn.close()
        
        # ✅ Simple Quantity Dialog
        dialog = QuantityDialog(self.item["name"], current_qty, max_qty, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_qty = dialog.get_quantity()
            if new_qty != current_qty:
                self.item["qty"] = new_qty
                self.qty_label.setText(str(new_qty))
                self._update_total()
                self.qty_changed.emit(self.row, new_qty)
    
    def _update_total(self):
        """Update total display"""
        symbol = get_currency_symbol()
        total = self.item["price"] * self.item["qty"]
        self.total_label.setText(format_money(total, symbol))
    
    def update_qty(self, qty: int):
        """Update quantity externally"""
        self.item["qty"] = qty
        self.qty_label.setText(str(qty))
        self._update_total()
    
    def _apply_theme(self):
        """Apply theme colors"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors['card_bg']};
                    border-radius: 6px;
                    margin: 1px 0px;
                    border: none;
                }}
                QFrame:hover {{
                    background-color: #3a3d44;
                }}
            """)
            self.name_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: 600;
                color: #dcddde;
                background: transparent;
                border: none;
            """)
            self.price_label.setStyleSheet("""
                font-size: 9pt;
                color: #888;
                background: transparent;
                border: none;
            """)
            self.x_label.setStyleSheet("""
                font-size: 8pt;
                color: #888;
                background: transparent;
                border: none;
                padding: 0 2px;
            """)
            self.qty_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: bold;
                background: transparent;
                color: #5865f2;
                border: 1px solid #5865f2;
                border-radius: 4px;
                padding: 0px 2px;
            """)
            self.total_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: 600;
                color: #5865f2;
                background: transparent;
                border: none;
            """)
            self.location_label.setStyleSheet("""
                font-size: 8.5pt;
                color: #888;
                background: transparent;
                border: none;
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors['card_bg']};
                    border-radius: 6px;
                    margin: 1px 0px;
                    border: none;
                }}
                QFrame:hover {{
                    background-color: #f8f9fa;
                }}
            """)
            self.name_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: 600;
                color: #212529;
                background: transparent;
                border: none;
            """)
            self.price_label.setStyleSheet("""
                font-size: 9pt;
                color: #888;
                background: transparent;
                border: none;
            """)
            self.x_label.setStyleSheet("""
                font-size: 8pt;
                color: #999;
                background: transparent;
                border: none;
                padding: 0 2px;
            """)
            self.qty_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: bold;
                background: transparent;
                color: #5865f2;
                border: 1px solid #5865f2;
                border-radius: 4px;
                padding: 0px 2px;
            """)
            self.total_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: 600;
                color: #5865f2;
                background: transparent;
                border: none;
            """)
            self.location_label.setStyleSheet("""
                font-size: 8.5pt;
                color: #777;
                background: transparent;
                border: none;
            """)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
    
    def update_theme(self):
        """Update theme"""
        self._is_dark = is_dark_theme()
        self._apply_theme()


class CartWidget(QWidget):
    """Mobile-style cart widget with card items"""
    
    cart_changed = pyqtSignal()

    def _load_icon_pixmap(self, icon_name: str, size: int = 24) -> QPixmap:
        colors = get_theme_colors()
        color_hex = colors.get("text", "#212529")
        for icon_path in (f"assets/icons/{icon_name}.svg", f"assets/icons/{icon_name}.png"):
            if not os.path.exists(icon_path):
                continue
            pixmap = QPixmap(icon_path)
            if pixmap.isNull():
                continue
            scaled = pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            colored = scaled.copy()
            painter = QPainter(colored)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(colored.rect(), QColor(color_hex))
            painter.end()
            return colored
        return QPixmap()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cart: List[Dict[str, Any]] = []
        self._item_widgets: List[CartItemWidget] = []
        self._is_dark = is_dark_theme()
        
        self._setup_ui()
        self._apply_theme()
        
        register_theme_callback(self._on_theme_changed)
        self.destroyed.connect(lambda *_: unregister_theme_callback(self._on_theme_changed))
    
    def _setup_ui(self):
        """Setup the cart UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        self.header = QFrame()
        self.header.setFixedHeight(50)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        self.title_icon = QLabel()
        self.title_icon.setFixedSize(22, 22)
        self.title_icon.setScaledContents(True)
        header_layout.addWidget(self.title_icon)
        
        self.title_label = QLabel("Cart")
        self.title_label.setStyleSheet("""
            font-size: 12pt;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        self.title_label.setText("Cart")
        header_layout.addWidget(self.title_label)
        
        self.count_badge = QLabel("0")
        self.count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_badge.setFixedHeight(22)
        self.count_badge.setMinimumWidth(22)
        self.count_badge.setStyleSheet("""
            background-color: #6675f5;
            color: white;
            border-radius: 11px;
            padding: 1px 7px;
            font-size: 9pt;
            font-weight: bold;
            border: none;
        """)
        header_layout.addWidget(self.count_badge)
        header_layout.addStretch()

        self.clear_btn = ModernButton("", ModernButton.PRIMARY)
        self.clear_btn.set_icon("delete", (18, 18))
        self.clear_btn.setToolTip("Clear all items")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.set_compact(True)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        header_layout.addWidget(self.clear_btn)
        main_layout.addWidget(self.header)
        
        # Separator
        self.sep = QFrame()
        self.sep.setFixedHeight(1)
        self.sep.setStyleSheet("border: none;")
        main_layout.addWidget(self.sep)
        
        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5865f2;
            }
        """)
        
        self.items_container = QWidget()
        self.items_container.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(4, 6, 4, 6)
        self.items_layout.setSpacing(5)
        self.items_layout.addStretch()
        
        self.scroll_area.setWidget(self.items_container)
        main_layout.addWidget(self.scroll_area, stretch=1)
        
        # Empty state
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)
        
        self.empty_icon = QLabel()
        self.empty_icon.setText("")
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon.setFixedSize(24, 24)
        self.empty_icon.setScaledContents(True)
        self.empty_icon.setStyleSheet("background: transparent; border: none;")
        empty_layout.addWidget(self.empty_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.empty_label = QLabel("Cart is empty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("""
            font-size: 12pt;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        empty_layout.addWidget(self.empty_label)
        
        self.empty_sub_label = QLabel("Add products to start selling")
        self.empty_sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_sub_label.setStyleSheet("""
            font-size: 9pt;
            background: transparent;
            border: none;
        """)
        empty_layout.addWidget(self.empty_sub_label)
        
        self.empty_action_btn = QLabel("Browse Products")
        self.empty_action_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_action_btn.setStyleSheet("background: transparent; border: none;")
        empty_layout.addWidget(self.empty_action_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(self.empty_widget)
        
        # Footer: Subtotal and change
        self.footer = QFrame()
        self.footer.setFixedHeight(72)
        self.footer.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(12, 7, 12, 7)
        footer_layout.setSpacing(10)

        total_group = QWidget()
        total_group.setStyleSheet("background: transparent; border: none;")
        total_layout = QVBoxLayout(total_group)
        total_layout.setContentsMargins(0, 0, 0, 0)
        total_layout.setSpacing(1)

        change_group = QWidget()
        change_group.setStyleSheet("background: transparent; border: none;")
        change_layout = QVBoxLayout(change_group)
        change_layout.setContentsMargins(0, 0, 0, 0)
        change_layout.setSpacing(1)
        
        self.subtotal_label = QLabel("Grand Total")
        self.subtotal_label.setStyleSheet("""
            font-size: 10pt;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        self.subtotal_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        total_layout.addWidget(self.subtotal_label)
        
        self.subtotal_value = QLabel("0.00")
        self.subtotal_value.setStyleSheet("""
            font-size: 13pt;
            font-weight: bold;
            color: #6675f5;
            background: transparent;
            border: none;
        """)
        self.subtotal_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        total_layout.addWidget(self.subtotal_value)

        self.change_label = QLabel("Change")
        self.change_label.setStyleSheet("""
            font-size: 10pt;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        change_layout.addWidget(self.change_label)

        self.change_value = QLabel("0.00")
        self.change_value.setStyleSheet("""
            font-size: 13pt;
            font-weight: bold;
            color: #27ae60;
            background: transparent;
            border: none;
        """)
        self.change_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        change_layout.addWidget(self.change_value)

        footer_layout.addWidget(total_group, 1)
        footer_layout.addWidget(change_group, 1)
        
        main_layout.addWidget(self.footer)
        self._show_empty_state(True)
    
    def _apply_theme(self):
        """Apply theme colors"""
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        accent = colors.get("progress_bg", "#6675f5")
        secondary = colors.get("text_secondary", "#aab4c8")
        border = colors.get("border", "#293348")
        
        if is_dark:
            self.title_icon.setPixmap(self._load_icon_pixmap("shopping_cart", 22))
            self.empty_icon.setPixmap(self._load_icon_pixmap("shopping_cart", 24))
            self.sep.setStyleSheet(f"background-color: {border}; border: none;")
            self.title_label.setStyleSheet(f"""
                font-size: 12pt;
                font-weight: bold;
                color: {accent};
                background: transparent;
                border: none;
            """)
            self.empty_label.setStyleSheet(f"""
                font-size: 12pt;
                font-weight: 600;
                color: {secondary};
                background: transparent;
                border: none;
            """)
            self.empty_sub_label.setStyleSheet(f"""
                font-size: 9pt;
                color: {secondary};
                background: transparent;
                border: none;
            """)
            self.empty_action_btn.setStyleSheet(f"""
                font-size: 9pt;
                font-weight: 600;
                color: {accent};
                background: transparent;
                border: none;
            """)
            self.subtotal_label.setStyleSheet(f"""
                font-size: 10pt;
                font-weight: 600;
                color: {secondary};
                background: transparent;
                border: none;
            """)
            self.change_label.setStyleSheet(f"""
                font-size: 10pt;
                font-weight: 600;
                color: {secondary};
                background: transparent;
                border: none;
            """)
        else:
            self.title_icon.setPixmap(self._load_icon_pixmap("shopping_cart", 22))
            self.empty_icon.setPixmap(self._load_icon_pixmap("shopping_cart", 24))
            self.sep.setStyleSheet("background-color: #e0e0e0; border: none;")
            self.title_label.setStyleSheet("""
                font-size: 12pt;
                font-weight: bold;
                color: #5865f2;
                background: transparent;
                border: none;
            """)
            self.empty_label.setStyleSheet("""
                font-size: 12pt;
                font-weight: 600;
                color: #999;
                background: transparent;
                border: none;
            """)
            self.empty_sub_label.setStyleSheet("""
                font-size: 9pt;
                color: #bbb;
                background: transparent;
                border: none;
            """)
            self.empty_action_btn.setStyleSheet("""
                font-size: 9pt;
                font-weight: 600;
                color: #5865f2;
                background: transparent;
                border: none;
            """)
            self.subtotal_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: 600;
                color: #666;
                background: transparent;
                border: none;
            """)
            self.change_label.setStyleSheet("""
                font-size: 10pt;
                font-weight: 600;
                color: #666;
                background: transparent;
                border: none;
            """)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        for widget in self._item_widgets:
            widget.update_theme()
        self.clear_btn.update_theme()
    
    def _on_clear_clicked(self):
        """Handle clear cart button click"""
        if not self.cart:
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Clear Cart")
        msg_box.setText("Remove all items from cart?")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        
        is_dark = is_dark_theme()
        if is_dark:
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2f3136;
                }
                QMessageBox QLabel {
                    color: #dcddde;
                    background-color: transparent;
                }
                QMessageBox QPushButton {
                    background-color: #40444b;
                    color: #dcddde;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5865f2;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes {
                    background-color: #ed4245;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes:hover {
                    background-color: #c03537;
                }
            """)
        else:
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #ffffff;
                }
                QMessageBox QLabel {
                    color: #2e3338;
                    background-color: transparent;
                }
                QMessageBox QPushButton {
                    background-color: #ebedef;
                    color: #2e3338;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5865f2;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes {
                    background-color: #dc3545;
                    color: white;
                }
                QMessageBox QPushButton#qt_msgbox_buttonbox_yes:hover {
                    background-color: #c82333;
                }
            """)
        
        yes_button = msg_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
        no_button = msg_box.addButton("No", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(no_button)
        msg_box.exec()
        
        if msg_box.clickedButton() == yes_button:
            self.clear()
    
    def _show_empty_state(self, empty: bool):
        """Show or hide empty state"""
        self.scroll_area.setVisible(not empty)
        self.empty_widget.setVisible(empty)
    
    def _get_active_variants(self, product_id: int) -> List[Dict[str, Any]]:
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, size, color, sku, barcode, price, stock, low_stock, image
                FROM product_variants
                WHERE product_id = ? AND COALESCE(active, 1) = 1
                ORDER BY size, color, id
            """, (product_id,))
            rows = cursor.fetchall()
        finally:
            conn.close()
        return [
            {
                "variant_id": row[0],
                "size": row[1] or "",
                "color": row[2] or "",
                "sku": row[3] or "",
                "barcode": row[4] or "",
                "price": float(row[5] or 0),
                "stock": int(row[6] or 0),
                "low_stock": int(row[7] or 0),
                "image": row[8] or "",
            }
            for row in rows
        ]

    def _variant_label(self, variant: Dict[str, Any]) -> str:
        parts = [str(variant.get("color") or "").strip(), str(variant.get("size") or "").strip()]
        return " / ".join([part for part in parts if part])

    def _select_variant(self, product_name: str, variants: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Variant - {product_name}")
        dialog.resize(560, 320)
        layout = QVBoxLayout(dialog)
        label = QLabel(product_name)
        label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        layout.addWidget(label)

        table = QTableWidget(len(variants), 6)
        table.setHorizontalHeaderLabels(["Size", "Color", "SKU", "Barcode", "Price", "Stock"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        symbol = get_currency_symbol()
        for row, variant in enumerate(variants):
            values = [
                variant.get("size", ""),
                variant.get("color", ""),
                variant.get("sku", ""),
                variant.get("barcode", ""),
                format_money(variant.get("price", 0), symbol),
                str(variant.get("stock", 0)),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, col, item)
        if variants:
            table.selectRow(0)
        table.itemDoubleClicked.connect(lambda *_: dialog.accept())
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        row = table.currentRow()
        if row < 0:
            return None
        return variants[row]

    def _add_variant_product(self, product_id: int, name: str, base_price: float, variant: Dict[str, Any]):
        variant_id = variant["variant_id"]
        stock_available = int(variant.get("stock") or 0)
        if stock_available < 1:
            QMessageBox.warning(self, "Out of Stock", f"{name} ({self._variant_label(variant)}) is out of stock.")
            return
        unit_price = float(variant.get("price") or base_price or 0)
        original_price = unit_price
        discount_info = self._get_best_discount(product_id, None)
        discount_percent = float(discount_info.get("percent", 0))
        if discount_info.get("source") == "promo" and discount_info.get("type") == "manual_price":
            manual_price = float(discount_info.get("manual_price") or 0)
            if manual_price > 0 and manual_price < unit_price:
                discount_percent = ((unit_price - manual_price) / unit_price) * 100.0 if unit_price > 0 else 0.0
                unit_price = manual_price
        elif discount_percent > 0:
            unit_price = max(0.0, unit_price * (1 - min(discount_percent, 100) / 100.0))
        display_name = name
        variant_label = self._variant_label(variant)
        if variant_label:
            display_name = f"{name} - {variant_label}"
        for item in self.cart:
            if item["id"] == product_id and item.get("variant_id") == variant_id and not item.get("is_service", False):
                new_qty = item["qty"] + 1
                if new_qty > stock_available:
                    QMessageBox.warning(self, "Stock Insufficient", f"Only {stock_available} left.")
                    return
                item["qty"] = new_qty
                self.refresh_table()
                return
        self.cart.append({
            "id": product_id,
            "variant_id": variant_id,
            "variant_size": variant.get("size", ""),
            "variant_color": variant.get("color", ""),
            "variant_sku": variant.get("sku", ""),
            "variant_barcode": variant.get("barcode", ""),
            "name": display_name,
            "base_name": name,
            "price": unit_price,
            "original_price": original_price,
            "qty": 1,
            "is_service": False,
            "location": variant_label or "Variant",
            "location_id": None,
            "image": variant.get("image") or "",
            "promo_discount_enabled": discount_info.get("source") == "promo",
            "promo_discount_percent": discount_percent if discount_info.get("source") == "promo" else 0,
            "discount_source": discount_info.get("source", ""),
        })
        self.refresh_table()

    def _get_wholesale_tier(self, product_id: int, qty: int) -> Optional[Dict[str, Any]]:
        conn = connect_db()
        cursor = conn.cursor()
        try:
            ensure_wholesale_schema(cursor)
            return get_best_price_tier(cursor, product_id, qty)
        except Exception as e:
            logger.debug(f"Wholesale tier lookup failed for product {product_id}: {e}")
            return None
        finally:
            conn.close()

    def _apply_wholesale_price(self, item: Dict[str, Any]) -> None:
        if item.get("is_service", False) or item.get("variant_id"):
            return
        product_id = int(item.get("id") or 0)
        qty = int(item.get("qty") or 0)
        if product_id <= 0 or qty <= 0:
            return

        regular_price = float(
            item.get("price_before_wholesale")
            or item.get("base_unit_price")
            or item.get("original_price")
            or item.get("price")
            or 0
        )
        item["price_before_wholesale"] = regular_price
        tier = self._get_wholesale_tier(product_id, qty)
        if tier and float(tier.get("unit_price") or 0) > 0:
            item["price"] = float(tier["unit_price"])
            item["wholesale_tier_id"] = tier.get("id")
            item["wholesale_min_qty"] = tier.get("min_qty")
            item["wholesale_unit_label"] = tier.get("unit_label") or ""
            item["wholesale_unit_multiplier"] = tier.get("unit_multiplier") or tier.get("min_qty")
            item["wholesale_note"] = tier.get("note") or ""
        else:
            item["price"] = regular_price
            for key in (
                "wholesale_tier_id",
                "wholesale_min_qty",
                "wholesale_unit_label",
                "wholesale_unit_multiplier",
                "wholesale_note",
            ):
                item.pop(key, None)

    def _apply_wholesale_prices(self) -> None:
        for item in self.cart:
            self._apply_wholesale_price(item)

    def _add_product_quantity(self, product_id: int, name: str, price: float, stock_available: int, quantity: int) -> None:
        quantity = max(1, int(quantity or 1))
        for item in self.cart:
            if item["id"] == product_id and not item.get("variant_id") and not item.get("is_service", False):
                new_qty = item["qty"] + quantity
                if new_qty > stock_available:
                    QMessageBox.warning(self, "Stock Insufficient", f"Only {stock_available} left.")
                    return
                item["qty"] = new_qty
                self._apply_wholesale_price(item)
                self.refresh_table()
                return
        if stock_available < quantity:
            QMessageBox.warning(self, "Out of Stock", f"Only {stock_available} left for {name}.")
            return
        self.add_product(product_id, name, price, stock_available)
        if self.cart and self.cart[-1].get("id") == product_id and not self.cart[-1].get("variant_id"):
            self.cart[-1]["qty"] = quantity
            self._apply_wholesale_price(self.cart[-1])
            self.refresh_table()

    def add_product(self, product_id: int, name: str, price: float, stock_available: int):
        """Add a regular product"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(sold_by, 'Each') FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        if row and str(row[0] or "").lower() == "restaurant":
            self.add_restaurant_product(product_id, name, price, [])
            return

        variants = self._get_active_variants(product_id)
        if variants:
            variant = self._select_variant(name, variants)
            if not variant:
                return
            self._add_variant_product(product_id, name, price, variant)
            return

        location_info = self._get_best_location(product_id)
        discount_info = self._get_best_discount(product_id, location_info)
        location = location_info.get("location") if location_info else None
        unit_price = float(price)
        discount_percent = float(discount_info.get("percent", 0))
        if discount_info.get("source") == "promo" and discount_info.get("type") == "manual_price":
            manual_price = float(discount_info.get("manual_price") or 0)
            if manual_price > 0 and manual_price < unit_price:
                discount_percent = ((unit_price - manual_price) / unit_price) * 100.0 if unit_price > 0 else 0.0
                unit_price = manual_price
        elif discount_percent > 0:
            unit_price = max(0.0, unit_price * (1 - min(discount_percent, 100) / 100.0))

        current_location_id = None
        for item in self.cart:
            same_product = item["id"] == product_id and not item.get("variant_id") and not item.get("is_service", False)
            same_location = item.get("location_id") == current_location_id
            if same_product and same_location:
                new_qty = item["qty"] + 1
                if new_qty > stock_available:
                    QMessageBox.warning(self, "Stock Insufficient", f"Only {stock_available} left.")
                    return
                item["qty"] = new_qty
                self._apply_wholesale_price(item)
                self.refresh_table()
                return
        if stock_available < 1:
            QMessageBox.warning(self, "Out of Stock", f"{name} is out of stock.")
            return
        self.cart.append({
            "id": product_id,
            "name": name,
            "price": unit_price,
            "price_before_wholesale": unit_price,
            "base_unit_price": float(price),
            "original_price": float(price),
            "qty": 1,
            "is_service": False,
            "location": "Auto FIFO" if location_info else location,
            "location_id": None,
            "batch_no": location_info.get("batch_no") if location_info else "",
            "expire_date": location_info.get("expire_date") if location_info else "",
            "expiry_discount_enabled": discount_info.get("source") == "expiry",
            "expiry_discount_percent": discount_percent,
            "expiry_discount_start_date": location_info.get("expiry_discount_start_date") if location_info else "",
            "expiry_discount_end_date": location_info.get("expiry_discount_end_date") if location_info else "",
            "promo_discount_enabled": discount_info.get("source") == "promo",
            "promo_discount_percent": discount_percent if discount_info.get("source") == "promo" else 0,
            "discount_source": discount_info.get("source", ""),
            "clearance_note": location_info.get("clearance_note", "") if location_info else "",
        })
        self.refresh_table()
    
    def add_service(self, product_id: int, name: str, manual_price: float):
        """Add a service product"""
        for item in self.cart:
            if item["id"] == product_id and item.get("is_service", False):
                item["qty"] += 1
                self.refresh_table()
                return
        self.cart.append({
            "id": product_id,
            "name": name,
            "price": manual_price,
            "qty": 1,
            "is_service": True,
            "location": None
        })
        self._apply_wholesale_price(self.cart[-1])
        self.refresh_table()

    def add_restaurant_product(self, product_id: int, name: str, price: float, modifiers=None, kitchen_note=""):
        """Add a restaurant menu item with its selected cooking modifiers."""
        modifiers = modifiers or []
        kitchen_note = str(kitchen_note or "").strip()
        modifier_names = [str(mod.get("name") or "").strip() for mod in modifiers if str(mod.get("name") or "").strip()]
        modifier_key = "|".join(sorted(modifier_names))
        price_delta = sum(float(mod.get("price_delta") or 0) for mod in modifiers)
        unit_price = float(price or 0) + price_delta
        display_name = name
        if modifier_names:
            display_name = f"{name} ({', '.join(modifier_names)})"

        for item in self.cart:
            same_item = (
                item["id"] == product_id
                and item.get("is_restaurant", False)
                and item.get("modifier_key", "") == modifier_key
                and str(item.get("kitchen_note") or "").strip() == kitchen_note
            )
            if same_item:
                item["qty"] += 1
                self.refresh_table()
                return

        self.cart.append({
            "id": product_id,
            "name": display_name,
            "base_name": name,
            "price": unit_price,
            "original_price": float(price or 0),
            "qty": 1,
            "is_service": True,
            "is_restaurant": True,
            "restaurant_modifiers": modifiers,
            "modifier_key": modifier_key,
            "kitchen_note": kitchen_note,
            "location": None,
        })
        self.refresh_table()
    
    def _get_best_location(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get best location for product (FIFO)"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, location, quantity, expire_date, batch_no,
                   COALESCE(expiry_discount_enabled, 0),
                   COALESCE(expiry_discount_percent, 0),
                   COALESCE(expiry_discount_start_date, ''),
                   COALESCE(expiry_discount_end_date, ''),
                   COALESCE(clearance_note, '')
                FROM product_locations 
                WHERE product_id = ? AND quantity > 0
                ORDER BY expire_date ASC, last_updated ASC
            """, (product_id,))
            row = cursor.fetchone()
        except Exception:
            cursor.execute("""
                SELECT id, location, quantity, expire_date, batch_no, 0, 0, '', '', ''
                FROM product_locations 
                WHERE product_id = ? AND quantity > 0
                ORDER BY expire_date ASC, last_updated ASC
            """, (product_id,))
            row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        loc_id, location, _qty, expire_date, batch_no, discount_enabled, discount_percent, discount_start, discount_end, clearance_note = row
        return {
            "id": loc_id,
            "location": location,
            "expire_date": expire_date or "",
            "batch_no": batch_no or "",
            "expiry_discount_enabled": bool(discount_enabled),
            "expiry_discount_percent": float(discount_percent or 0),
            "expiry_discount_start_date": discount_start or "",
            "expiry_discount_end_date": discount_end or "",
            "clearance_note": clearance_note or "",
        }

    def _get_location_options(self, product_id: int) -> List[Dict[str, Any]]:
        """Get selectable location/batch rows for manual cart override."""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            try:
                cursor.execute("""
                    SELECT id, location, quantity, expire_date, batch_no,
                           COALESCE(expiry_discount_enabled, 0),
                           COALESCE(expiry_discount_percent, 0),
                           COALESCE(expiry_discount_start_date, ''),
                           COALESCE(expiry_discount_end_date, ''),
                           COALESCE(clearance_note, '')
                    FROM product_locations
                    WHERE product_id = ? AND quantity > 0
                    ORDER BY
                        CASE WHEN expire_date IS NULL OR expire_date = '' THEN 1 ELSE 0 END,
                        expire_date ASC,
                        last_updated ASC,
                        id ASC
                """, (product_id,))
            except Exception:
                cursor.execute("""
                    SELECT id, location, quantity, expire_date, batch_no, 0, 0, '', '', ''
                    FROM product_locations
                    WHERE product_id = ? AND quantity > 0
                    ORDER BY
                        CASE WHEN expire_date IS NULL OR expire_date = '' THEN 1 ELSE 0 END,
                        expire_date ASC,
                        last_updated ASC,
                        id ASC
                """, (product_id,))
            rows = cursor.fetchall()
        finally:
            conn.close()

        options = []
        for row in rows:
            loc_id, location, qty, expire_date, batch_no, discount_enabled, discount_percent, discount_start, discount_end, clearance_note = row
            options.append({
                "id": loc_id,
                "location": location or "",
                "quantity": int(qty or 0),
                "expire_date": expire_date or "",
                "batch_no": batch_no or "",
                "expiry_discount_enabled": bool(discount_enabled),
                "expiry_discount_percent": float(discount_percent or 0),
                "expiry_discount_start_date": discount_start or "",
                "expiry_discount_end_date": discount_end or "",
                "clearance_note": clearance_note or "",
            })
        return options

    def change_item_location(self, row: int):
        """Let the cashier override FIFO with an exact location/batch."""
        if row < 0 or row >= len(self.cart):
            return

        item = self.cart[row]
        if item.get("is_service", False) or item.get("variant_id"):
            QMessageBox.information(self, "Location", "This item does not use location stock.")
            return

        options = self._get_location_options(int(item["id"]))
        if not options:
            QMessageBox.information(self, "Location", "No location stock is available for this product.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Change Location/Batch")
        dialog.setModal(True)
        dialog.resize(560, 340)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        hint = QLabel("Default uses Auto FIFO. Select a row only when you need a specific location or batch.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        table = QTableWidget(len(options) + 1, 5)
        table.setHorizontalHeaderLabels(["Mode", "Location", "Batch", "Expiry", "Available"])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        auto_item = QTableWidgetItem("Auto FIFO")
        auto_item.setData(Qt.ItemDataRole.UserRole, None)
        table.setItem(0, 0, auto_item)
        table.setItem(0, 1, QTableWidgetItem("System selects by expiry/FIFO"))
        table.setItem(0, 2, QTableWidgetItem("-"))
        table.setItem(0, 3, QTableWidgetItem("-"))
        table.setItem(0, 4, QTableWidgetItem("-"))

        selected_row = 0
        current_location_id = item.get("location_id")
        for index, option in enumerate(options, start=1):
            mode_item = QTableWidgetItem("Manual")
            mode_item.setData(Qt.ItemDataRole.UserRole, option["id"])
            table.setItem(index, 0, mode_item)
            table.setItem(index, 1, QTableWidgetItem(option["location"] or "-"))
            table.setItem(index, 2, QTableWidgetItem(option["batch_no"] or "-"))
            table.setItem(index, 3, QTableWidgetItem(option["expire_date"] or "-"))
            table.setItem(index, 4, QTableWidgetItem(str(option["quantity"])))
            if current_location_id == option["id"]:
                selected_row = index

        table.selectRow(selected_row)
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_items = table.selectedItems()
        if not selected_items:
            return
        selected = table.item(table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)

        if selected is None:
            best = self._get_best_location(int(item["id"]))
            item["location_id"] = None
            item["location"] = "Auto FIFO" if best else ""
            item["batch_no"] = best.get("batch_no") if best else ""
            item["expire_date"] = best.get("expire_date") if best else ""
            item["expiry_discount_enabled"] = bool(best and best.get("expiry_discount_enabled"))
            item["expiry_discount_percent"] = float(best.get("expiry_discount_percent", 0) if best else 0)
            item["expiry_discount_start_date"] = best.get("expiry_discount_start_date", "") if best else ""
            item["expiry_discount_end_date"] = best.get("expiry_discount_end_date", "") if best else ""
            item["clearance_note"] = best.get("clearance_note", "") if best else ""
        else:
            option = next((opt for opt in options if opt["id"] == selected), None)
            if not option:
                return
            if option["quantity"] < int(item.get("qty") or 0):
                QMessageBox.warning(
                    self,
                    "Stock Insufficient",
                    f"Only {option['quantity']} available in the selected location/batch.",
                )
                return
            item["location_id"] = option["id"]
            item["location"] = option["location"]
            item["batch_no"] = option["batch_no"]
            item["expire_date"] = option["expire_date"]
            item["expiry_discount_enabled"] = option["expiry_discount_enabled"]
            item["expiry_discount_percent"] = option["expiry_discount_percent"]
            item["expiry_discount_start_date"] = option["expiry_discount_start_date"]
            item["expiry_discount_end_date"] = option["expiry_discount_end_date"]
            item["clearance_note"] = option["clearance_note"]

        discount_info = self._get_best_discount(int(item["id"]), item if item.get("location_id") else self._get_best_location(int(item["id"])))
        original_price = float(item.get("original_price") or item.get("base_unit_price") or item.get("price") or 0)
        item["price"] = original_price
        discount_percent = float(discount_info.get("percent", 0))
        if discount_info.get("source") == "promo" and discount_info.get("type") == "manual_price":
            manual_price = float(discount_info.get("manual_price") or 0)
            if manual_price > 0 and manual_price < original_price:
                discount_percent = ((original_price - manual_price) / original_price) * 100.0 if original_price > 0 else 0.0
                item["price"] = manual_price
        elif discount_percent > 0:
            item["price"] = max(0.0, original_price * (1 - min(discount_percent, 100) / 100.0))
        item["expiry_discount_enabled"] = discount_info.get("source") == "expiry"
        item["expiry_discount_percent"] = discount_percent if discount_info.get("source") == "expiry" else 0
        item["promo_discount_enabled"] = discount_info.get("source") == "promo"
        item["promo_discount_percent"] = discount_percent if discount_info.get("source") == "promo" else 0
        item["discount_source"] = discount_info.get("source", "")
        item["price_before_wholesale"] = item["price"]

        self._apply_wholesale_price(item)
        self.refresh_table()

    def _get_active_product_discount(self, product_id: int) -> Dict[str, Any]:
        conn = connect_db()
        cursor = conn.cursor()
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
            for column, definition in {
                "discount_type": "TEXT DEFAULT 'percentage'",
                "manual_price": "REAL DEFAULT 0",
            }.items():
                if column not in columns:
                    cursor.execute(f"ALTER TABLE product_discounts ADD COLUMN {column} {definition}")
            cursor.execute("""
                SELECT discount_percent, COALESCE(note, ''), COALESCE(discount_type, 'percentage'),
                       COALESCE(manual_price, 0)
                FROM product_discounts
                WHERE product_id = ?
                  AND active = 1
                  AND date(start_date) <= date('now')
                  AND date(end_date) >= date('now')
                ORDER BY
                    CASE
                        WHEN COALESCE(discount_type, 'percentage') = 'manual_price' THEN 999999999 - COALESCE(manual_price, 0)
                        ELSE discount_percent
                    END DESC,
                    end_date ASC
                LIMIT 1
            """, (product_id,))
            row = cursor.fetchone()
        except Exception:
            row = None
        finally:
            conn.close()
        if not row:
            return {"percent": 0.0, "source": "", "note": "", "type": "percentage", "manual_price": 0.0}
        return {
            "percent": float(row[0] or 0),
            "source": "promo",
            "note": row[1] or "",
            "type": row[2] or "percentage",
            "manual_price": float(row[3] or 0),
        }

    def _get_best_discount(self, product_id: int, location_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        promo = self._get_active_product_discount(product_id)
        expiry_percent = float(location_info.get("expiry_discount_percent", 0) if location_info else 0)
        expiry_enabled = bool(location_info and location_info.get("expiry_discount_enabled"))
        if expiry_enabled:
            today = QDate.currentDate().toString("yyyy-MM-dd")
            start = location_info.get("expiry_discount_start_date") or ""
            end = location_info.get("expiry_discount_end_date") or location_info.get("expire_date") or ""
            if (start and start > today) or (end and end < today):
                expiry_enabled = False
        if expiry_enabled and expiry_percent >= float(promo.get("percent", 0)):
            return {"percent": expiry_percent, "source": "expiry", "note": location_info.get("clearance_note", "")}
        return promo
    
    def add_product_by_barcode(self, keyword: str):
        """Add product by barcode/SKU"""
        keyword = str(keyword or "").strip()
        if keyword.upper().startswith("ZAYBATCH:"):
            try:
                location_id = int(keyword.split(":", 1)[1])
            except (ValueError, IndexError):
                QMessageBox.warning(self, "Invalid Label", "Invalid clearance label.")
                return
            self.add_product_from_location(location_id)
            return

        conn = connect_db()
        cursor = conn.cursor()
        try:
            tier = get_price_tier_by_barcode(cursor, keyword)
        except Exception:
            tier = None
        if tier:
            stock_expr = effective_stock_sql("p")
            cursor.execute(f"""
                SELECT p.id, p.name, p.price, {stock_expr} as stock, p.sold_by
                FROM products p
                WHERE p.id = ?
            """, (tier["product_id"],))
            product = cursor.fetchone()
            conn.close()
            if not product:
                QMessageBox.warning(self, "Not Found", "Wholesale unit product was not found.")
                return
            pid, name, price, stock, sold_by = product
            if sold_by and str(sold_by).lower().startswith("service"):
                QMessageBox.warning(self, "Invalid Unit", "Service products cannot use wholesale unit barcodes.")
                return
            quantity = int(tier.get("unit_multiplier") or tier.get("min_qty") or 1)
            self._add_product_quantity(int(pid), str(name), float(price or 0), int(stock or 0), quantity)
            return
        cursor.execute("""
            SELECT p.id, p.name, p.price, p.sold_by,
                   v.id, v.size, v.color, v.sku, v.barcode, v.price, v.stock, v.low_stock, v.image
            FROM product_variants v
            JOIN products p ON p.id = v.product_id
            WHERE COALESCE(v.active, 1) = 1
              AND (v.barcode = ? OR v.sku = ?)
            LIMIT 1
        """, (keyword, keyword))
        variant_row = cursor.fetchone()
        if variant_row:
            conn.close()
            pid, name, base_price, sold_by, variant_id, size, color, sku, v_barcode, v_price, stock, low_stock, image = variant_row
            if sold_by and str(sold_by).lower() == "service":
                self.add_service(pid, name, float(v_price or base_price or 0))
                return
            self._add_variant_product(pid, name, float(base_price or 0), {
                "variant_id": variant_id,
                "size": size or "",
                "color": color or "",
                "sku": sku or "",
                "barcode": v_barcode or "",
                "price": float(v_price or base_price or 0),
                "stock": int(stock or 0),
                "low_stock": int(low_stock or 0),
                "image": image or "",
            })
            return
        stock_expr = effective_stock_sql("p")
        cursor.execute(f"""
            SELECT p.id, p.name, p.price, {stock_expr} as stock, p.sold_by
            FROM products p
            WHERE p.barcode=? OR p.sku=? OR p.name LIKE ?
        """, (keyword, keyword, f'%{keyword}%'))
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            QApplication.beep()
            QMessageBox.warning(self, "Not Found", "Product Not Found")
            return
        
        pid, name, price, stock, sold_by = product
        price = float(price) if price else 0.0
        
        if sold_by and sold_by.lower() == "service":
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
                self.add_service(pid, name, manual_price)
        else:
            if stock <= 0:
                QMessageBox.warning(self, "Out of Stock", f"{name} is out of stock.")
                return
            self.add_product(pid, name, price, stock)

    def add_product_from_location(self, location_id: int):
        """Add a product from an exact product_locations batch label."""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            try:
                cursor.execute("""
                    SELECT
                        pl.id,
                        pl.product_id,
                        p.name,
                        p.price,
                        p.stock,
                        p.sold_by,
                        pl.location,
                        pl.batch_no,
                        pl.expire_date,
                        pl.quantity,
                        COALESCE(pl.expiry_discount_enabled, 0),
                        COALESCE(pl.expiry_discount_percent, 0),
                        COALESCE(pl.expiry_discount_start_date, ''),
                        COALESCE(pl.expiry_discount_end_date, ''),
                        COALESCE(pl.clearance_note, '')
                    FROM product_locations pl
                    JOIN products p ON p.id = pl.product_id
                    WHERE pl.id = ?
                """, (location_id,))
            except Exception:
                cursor.execute("""
                    SELECT
                        pl.id, pl.product_id, p.name, p.price, p.stock, p.sold_by,
                        pl.location, pl.batch_no, pl.expire_date, pl.quantity,
                        COALESCE(pl.expiry_discount_enabled, 0),
                        COALESCE(pl.expiry_discount_percent, 0),
                        '', '',
                        COALESCE(pl.clearance_note, '')
                    FROM product_locations pl
                    JOIN products p ON p.id = pl.product_id
                    WHERE pl.id = ?
                """, (location_id,))
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            QMessageBox.warning(self, "Not Found", "Clearance batch was not found.")
            return

        (
            loc_id, product_id, name, price, stock, sold_by, location, batch_no,
            expire_date, batch_qty, discount_enabled, discount_percent,
            discount_start, discount_end, clearance_note
        ) = row

        if sold_by and str(sold_by).lower() == "service":
            QMessageBox.warning(self, "Invalid Label", "Service products cannot use batch labels.")
            return
        if batch_qty <= 0:
            QMessageBox.warning(self, "Out of Stock", f"{name} is out of stock for this batch.")
            return

        for item in self.cart:
            if item["id"] == product_id and item.get("location_id") == loc_id and not item.get("is_service", False):
                new_qty = item["qty"] + 1
                if new_qty > batch_qty:
                    QMessageBox.warning(self, "Stock Insufficient", f"Only {batch_qty} left in this batch.")
                    return
                item["qty"] = new_qty
                self._apply_wholesale_price(item)
                self.refresh_table()
                return

        original_price = float(price or 0)
        discount_percent = float(discount_percent or 0)
        discount_enabled = bool(discount_enabled)
        today = QDate.currentDate().toString("yyyy-MM-dd")
        if discount_enabled and ((discount_start and discount_start > today) or (discount_end and discount_end < today)):
            discount_enabled = False
        unit_price = original_price
        if discount_enabled and discount_percent > 0:
            unit_price = max(0.0, original_price * (1 - min(discount_percent, 100) / 100.0))

        self.cart.append({
            "id": product_id,
            "name": name,
            "price": unit_price,
            "price_before_wholesale": unit_price,
            "base_unit_price": original_price,
            "original_price": original_price,
            "qty": 1,
            "is_service": False,
            "location": location,
            "location_id": loc_id,
            "batch_no": batch_no or "",
            "expire_date": expire_date or "",
            "expiry_discount_enabled": discount_enabled,
            "expiry_discount_percent": discount_percent,
            "expiry_discount_start_date": discount_start or "",
            "expiry_discount_end_date": discount_end or "",
            "clearance_note": clearance_note or "",
        })
        self._apply_wholesale_price(self.cart[-1])
        self.refresh_table()
    
    def refresh_table(self):
        """Refresh the cart display"""
        self._apply_wholesale_prices()
        for widget in self._item_widgets:
            self.items_layout.removeWidget(widget)
            widget.deleteLater()
        self._item_widgets.clear()
        
        if not self.cart:
            self._show_empty_state(True)
            self._update_subtotal()
            self.cart_changed.emit()
            save_cart_to_file(self.cart)
            return
        
        self._show_empty_state(False)
        
        for row, item in enumerate(self.cart):
            item_widget = CartItemWidget(row, item, self)
            item_widget.qty_changed.connect(self._on_qty_changed)
            item_widget.remove_requested.connect(self._on_remove_requested)
            item_widget.location_change_requested.connect(self.change_item_location)
            self.items_layout.insertWidget(self.items_layout.count() - 1, item_widget)
            self._item_widgets.append(item_widget)
        
        self._update_subtotal()
        self.cart_changed.emit()
        save_cart_to_file(self.cart)
    
    def _on_qty_changed(self, row: int, new_qty: int):
        """Handle quantity change from item widget"""
        if 0 <= row < len(self.cart):
            self.cart[row]["qty"] = new_qty
            self._apply_wholesale_price(self.cart[row])
            self._update_subtotal()
            self.cart_changed.emit()
            save_cart_to_file(self.cart)
    
    def _on_remove_requested(self, row: int):
        """Handle remove request from item widget"""
        if 0 <= row < len(self.cart):
            del self.cart[row]
            self.refresh_table()
    
    def _update_subtotal(self):
        """Refresh cart count and show a safe total until TotalsWidget recalculates."""
        subtotal = self.compute_subtotal()
        self.update_grand_total(subtotal)

        total_items = sum(item.get("qty", 0) for item in self.cart)
        self.count_badge.setText(str(total_items))
        self.update_change()

    def update_grand_total(self, grand_total: float):
        """Display the authoritative total calculated by TotalsWidget."""
        symbol = get_currency_symbol()
        try:
            value = float(grand_total or 0)
        except (TypeError, ValueError):
            value = 0.0
        self.subtotal_value.setText(format_money(value, symbol))

    def update_change(self):
        parent = self.parent()
        symbol = get_currency_symbol()
        grand_total = 0.0
        payment = 0.0
        if parent and hasattr(parent, "totals_widget"):
            grand_total = parent.totals_widget.get_current_grand_total()
        if parent and hasattr(parent, "payment_widget"):
            payment = parent.payment_widget.get_payment_amount()
        change = payment - grand_total
        if change >= 0:
            self.change_value.setText(format_money(change, symbol))
            self.change_value.setStyleSheet("font-size: 13pt; font-weight: bold; color: #27ae60; background: transparent; border: none;")
        else:
            self.change_value.setText(f"-{format_money(abs(change), symbol)}")
            self.change_value.setStyleSheet("font-size: 13pt; font-weight: bold; color: #e74c3c; background: transparent; border: none;")
    
    def update_qty(self, row: int, value: int):
        """Update quantity externally"""
        if 0 <= row < len(self.cart):
            if value <= 0:
                self._on_remove_requested(row)
            else:
                self.cart[row]["qty"] = value
                self._apply_wholesale_price(self.cart[row])
                if row < len(self._item_widgets):
                    self._item_widgets[row].update_qty(value)
                self._update_subtotal()
                self.cart_changed.emit()
                save_cart_to_file(self.cart)
    
    def remove_item(self, row: int):
        """Remove item by row"""
        if 0 <= row < len(self.cart):
            del self.cart[row]
            self.refresh_table()
    
    def clear(self):
        """Clear all items"""
        self.cart.clear()
        self.refresh_table()
        delete_cart_backup()
    
    def get_cart(self) -> List[Dict[str, Any]]:
        """Get cart items"""
        return self.cart
    
    def compute_subtotal(self) -> float:
        """Compute subtotal"""
        return sum(item["price"] * item["qty"] for item in self.cart)
    
    def update_theme(self):
        """Update theme"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        for widget in self._item_widgets:
            widget.update_theme()
        self.clear_btn.update_theme()
    
    def retranslateUi(self):
        """Update language"""
        from utils.language import lang
        if lang.get_current() == "my":
            self.title_label.setText("ဈေးခြင်း")
            self.empty_label.setText("ဈေးခြင်းထဲတွင် ပစ္စည်းမရှိပါ")
            self.empty_sub_label.setText("ပစ္စည်းများထည့်ရန် နှိပ်ပါ")
            self.subtotal_label.setText("ကြားဖြတ်စုစု")
            self.change_label.setText("ပြန်အမ်း")
            self.clear_btn.setToolTip("အားလုံးဖျက်မည်")
            self.empty_action_btn.setText("ပစ္စည်းများရှာရန်")
        else:
            self.title_label.setText("Cart")
            self.empty_label.setText("Cart is empty")
            self.empty_sub_label.setText("Add products to start selling")
            self.subtotal_label.setText("Grand Total")
            self.change_label.setText("Change")
            self.clear_btn.setToolTip("Clear all items")
            self.empty_action_btn.setText("Browse Products")
        if lang.get_current() != "my":
            self.title_label.setText("Cart")
