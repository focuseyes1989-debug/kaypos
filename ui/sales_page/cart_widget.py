"""Sales page cart using the same card-style UI as cashier mode."""

from typing import Any, Dict, List

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QMouseEvent, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.sales_page.product_utils import load_thumbnail
from ui.themes.theme_manager import get_theme_colors, is_dark_theme

from ui.cashier_window.cart_widget import (
    CartItemWidget as CashierCartItemWidget,
    CartWidget as CashierCartWidget,
    delete_cart_backup,
    load_cart_from_file,
    save_cart_to_file,
)


class _CartSelectionProxy:
    """Compatibility shim for existing SalesPage shortcuts that used table.currentRow()."""

    def __init__(self, owner: "CartWidget"):
        self._owner = owner

    def currentRow(self) -> int:
        return self._owner.selected_row

    def setToolTip(self, text: str) -> None:
        self._owner.setToolTip(text)


class CartItemWidget(CashierCartItemWidget):
    """Cashier cart item with lightweight row selection for SalesPage shortcuts."""

    THUMBNAIL_SIZE = 44

    def _setup_ui(self):
        self.setFixedHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.image_label = QLabel()
        self.image_label.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            background-color: rgba(128, 128, 128, 0.12);
            border: none;
            border-radius: 7px;
        """)
        layout.addWidget(self.image_label)

        middle_layout = QVBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(2)

        self.name_label = QLabel(self.item["name"])
        self.name_label.setFixedHeight(20)
        self.name_label.setStyleSheet("font-size: 9.5pt; font-weight: 600; background: transparent; border: none;")
        middle_layout.addWidget(self.name_label)

        qty_row = QHBoxLayout()
        qty_row.setContentsMargins(0, 0, 0, 0)
        qty_row.setSpacing(4)
        self.qty_label = QLabel(str(self.item["qty"]))
        self.qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qty_label.setFixedSize(24, 20)
        self.qty_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qty_label.mousePressEvent = self._on_qty_clicked
        qty_row.addWidget(self.qty_label)

        self.x_label = QLabel("x")
        qty_row.addWidget(self.x_label)

        symbol = get_currency_symbol()
        self.price_label = QLabel(format_money(self.item["price"], symbol))
        qty_row.addWidget(self.price_label)
        qty_row.addStretch()
        middle_layout.addLayout(qty_row)
        layout.addLayout(middle_layout, stretch=1)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        total = self.item["price"] * self.item["qty"]
        self.total_label = QLabel(format_money(total, symbol))
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.total_label.setFixedHeight(20)
        right_layout.addWidget(self.total_label)

        location = self.item.get("location")
        location_text = str(location) if location and not self.item.get("is_service", False) else "N/A" if self.item.get("is_service", False) else "-"
        self.location_label = QLabel(location_text)
        self.location_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.location_label.setFixedHeight(18)
        right_layout.addWidget(self.location_label)

        layout.addLayout(right_layout)
        self._update_thumbnail()

    def _resolve_image_path(self) -> str:
        image_path = str(self.item.get("image") or self.item.get("image_path") or "").strip()
        if image_path:
            return image_path
        product_id = self.item.get("id")
        if not product_id:
            return ""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT image FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            conn.close()
            return str(row[0] or "") if row else ""
        except Exception:
            return ""

    def _rounded_pixmap(self, pixmap: QPixmap, radius: int = 7) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        target = QPixmap(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return target

    def _update_thumbnail(self) -> None:
        thumb = load_thumbnail(self._resolve_image_path(), self.THUMBNAIL_SIZE)
        if thumb:
            scaled = thumb.scaled(
                self.THUMBNAIL_SIZE,
                self.THUMBNAIL_SIZE,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(self._rounded_pixmap(scaled))
            self.image_label.setText("")
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Img")
            self.image_label.setStyleSheet("""
                color: #8a8f98;
                font-size: 8pt;
                background-color: rgba(128, 128, 128, 0.12);
                border: none;
                border-radius: 7px;
            """)

    def _apply_theme(self):
        colors = get_theme_colors()
        text = colors.get("text", "#212529")
        secondary = colors.get("text_secondary", "#6c757d")
        card_bg = colors.get("card_bg", "#ffffff")
        hover_bg = "#3a3d44" if is_dark_theme() else "#f8f9fa"
        accent = "#5865f2"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border-radius: 6px;
                margin: 1px 0px;
                border: none;
            }}
            QFrame:hover {{
                background-color: {hover_bg};
            }}
        """)
        self.name_label.setStyleSheet(f"font-size: 9.5pt; font-weight: 600; color: {text}; background: transparent; border: none;")
        self.qty_label.setStyleSheet(f"""
            font-size: 9pt;
            font-weight: bold;
            background: transparent;
            color: {accent};
            border: 1px solid {accent};
            border-radius: 4px;
            padding: 0px 2px;
        """)
        self.x_label.setStyleSheet(f"font-size: 8pt; color: {secondary}; background: transparent; border: none;")
        self.price_label.setStyleSheet(f"font-size: 8.5pt; color: {secondary}; background: transparent; border: none;")
        self.total_label.setStyleSheet(f"font-size: 10pt; font-weight: 700; color: {accent}; background: transparent; border: none;")
        self.location_label.setStyleSheet(f"font-size: 8pt; color: {secondary}; background: transparent; border: none;")

    def update_theme(self):
        self._is_dark = is_dark_theme()
        self._apply_theme()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        parent = self.parent()
        while parent is not None and not isinstance(parent, CartWidget):
            parent = parent.parent()
        if isinstance(parent, CartWidget):
            parent.select_row(self.row)
        super().mousePressEvent(event)


class CartWidget(CashierCartWidget):
    """Sales cart that shares the cashier window card layout and theme behavior."""

    def __init__(self, parent=None):
        self.selected_row = -1
        super().__init__(parent)
        self.table = _CartSelectionProxy(self)
        self.subtotal_label.setText("Grand Total")

    def select_row(self, row: int) -> None:
        self.selected_row = row if 0 <= row < len(self.cart) else -1

    def _sales_page(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "totals_widget") and hasattr(parent, "payment_widget"):
                return parent
            parent = parent.parent()
        return None

    def _image_for_product(self, product_id) -> str:
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT image FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            conn.close()
            return str(row[0] or "") if row else ""
        except Exception:
            return ""

    def _ensure_item_images(self) -> None:
        for item in self.cart:
            if item.get("image") or item.get("is_service"):
                continue
            item["image"] = self._image_for_product(item.get("id"))

    def refresh_table(self):
        """Refresh the cart display with SalesPage-aware selectable item widgets."""
        self._ensure_item_images()
        for widget in self._item_widgets:
            self.items_layout.removeWidget(widget)
            widget.deleteLater()
        self._item_widgets.clear()

        if not self.cart:
            self.selected_row = -1
            self._show_empty_state(True)
            self._update_subtotal()
            self.cart_changed.emit()
            save_cart_to_file(self.cart)
            return

        self._show_empty_state(False)
        self.selected_row = min(self.selected_row, len(self.cart) - 1)

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

    def _update_subtotal(self):
        """Sales cart footer shows Grand Total instead of raw subtotal."""
        total_items = sum(item.get("qty", 0) for item in self.cart)
        self.count_badge.setText(str(total_items))
        self.update_grand_total()
        self.update_change()

    def update_grand_total(self, grand_total=None):
        parent = self._sales_page()
        if grand_total is None and parent and hasattr(parent, "totals_widget"):
            grand_total = parent.totals_widget.get_current_grand_total()
        if grand_total is None:
            grand_total = self.compute_subtotal()
        symbol = get_currency_symbol()
        self.subtotal_label.setText("Grand Total")
        self.subtotal_value.setText(format_money(float(grand_total or 0), symbol))
        self.update_change()

    def update_change(self):
        parent = self._sales_page()
        symbol = get_currency_symbol()
        grand_total = 0.0
        payment = 0.0
        if parent and hasattr(parent, "totals_widget"):
            grand_total = parent.totals_widget.get_current_grand_total()
        if parent and hasattr(parent, "payment_widget"):
            payment = parent.payment_widget.get_payment_amount()
        change = float(payment or 0) - float(grand_total or 0)
        if change >= 0:
            self.change_value.setText(format_money(change, symbol))
            self.change_value.setStyleSheet(
                "font-size: 13pt; font-weight: bold; color: #27ae60; background: transparent; border: none;"
            )
        else:
            self.change_value.setText(f"-{format_money(abs(change), symbol)}")
            self.change_value.setStyleSheet(
                "font-size: 13pt; font-weight: bold; color: #e74c3c; background: transparent; border: none;"
            )

    def clear(self):
        """Clear cart and reset Sale Page controls to a new-sale default state."""
        super().clear()
        parent = self._sales_page()
        if not parent:
            return
        if hasattr(parent, "totals_widget"):
            parent.totals_widget.discount_checkbox.setChecked(False)
            parent.totals_widget.points_use_check.setChecked(False)
            parent.totals_widget.update_totals()
        if hasattr(parent, "payment_widget"):
            parent.payment_widget.reset_manual_override()
            parent.payment_widget.reset_to_default()
        if hasattr(parent, "options_widget"):
            parent.options_widget.set_payment_type("Cash")
        if hasattr(parent, "payment_widget"):
            parent.payment_widget.setEnabled(True)
        if hasattr(parent, "customer_combo"):
            parent.customer_combo.setCurrentIndex(0)
        if hasattr(parent, "checkout_handler"):
            parent.checkout_handler.selected_customer_id = None
            parent.checkout_handler._credit_info_shown = False
            parent.checkout_handler.update_credit_radio_state()
        if hasattr(parent, "product_grid"):
            parent.product_grid.focus_search()

    def retranslateUi(self):
        super().retranslateUi()
        self.subtotal_label.setText("Grand Total")

    def update_theme(self):
        super().update_theme()
        self.subtotal_label.setText("Grand Total")
        self.update_grand_total()

    def get_cart(self) -> List[Dict[str, Any]]:
        return self.cart
