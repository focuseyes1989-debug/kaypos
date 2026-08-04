# ui/customer_page/customer_display_cart.py
import os
from functools import lru_cache

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QImageReader, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from models.database import connect_db
from utils.paths import app_path
from utils.currency import get_currency_symbol, format_money
from utils.translations import tr
from .customer_display_theme import get_display_palette


@lru_cache(maxsize=100)
def _load_thumbnail(image_path, size):
    if not image_path:
        return None
    resolved_path = image_path if os.path.isabs(image_path) else app_path(image_path)
    if not resolved_path or not os.path.exists(resolved_path):
        filename = os.path.basename(image_path)
        candidates = [
            os.path.join(os.getcwd(), image_path),
            app_path(os.path.join("database", "product_images", filename)),
            os.path.join(os.getcwd(), "database", "product_images", filename),
        ]
        resolved_path = next((path for path in candidates if path and os.path.exists(path)), "")
    if not resolved_path or not os.path.exists(resolved_path):
        return None
    reader = QImageReader(resolved_path)
    reader.setScaledSize(QSize(size, size))
    image = reader.read()
    if image.isNull():
        return None
    return QPixmap.fromImage(image)


class CartDisplayWidget(QWidget):
    """Simple card-style cart for the customer display."""

    THUMBNAIL_SIZE = 46

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._setup_ui()
        self.apply_theme_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(tr("your_cart"))
        header.addWidget(self.title_label)
        header.addStretch()
        self.count_badge = QLabel("0")
        self.count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.count_badge)
        layout.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        self.items_layout.addStretch()
        self.scroll_area.setWidget(self.items_container)
        layout.addWidget(self.scroll_area, 1)

        self.empty_label = QLabel("Cart is empty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label, 1)

        self.total_frame = QFrame()
        self.total_frame.setMinimumHeight(118)
        total_layout = QVBoxLayout(self.total_frame)
        total_layout.setContentsMargins(14, 10, 14, 12)
        total_layout.setSpacing(6)

        subtotal_row = QHBoxLayout()
        self.subtotal_label = QLabel(tr("subtotal"))
        self.subtotal_value = QLabel("0")
        self.subtotal_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        subtotal_row.addWidget(self.subtotal_label)
        subtotal_row.addStretch()
        subtotal_row.addWidget(self.subtotal_value)
        total_layout.addLayout(subtotal_row)

        discount_row = QHBoxLayout()
        self.discount_label = QLabel(tr("discount"))
        self.discount_value = QLabel("0")
        self.discount_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        discount_row.addWidget(self.discount_label)
        discount_row.addStretch()
        discount_row.addWidget(self.discount_value)
        total_layout.addLayout(discount_row)

        grand_row = QHBoxLayout()
        self.grand_label = QLabel("Grand Total")
        self.grand_value = QLabel("0")
        self.grand_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        grand_row.addWidget(self.grand_label)
        grand_row.addStretch()
        grand_row.addWidget(self.grand_value)
        total_layout.addLayout(grand_row)
        layout.addWidget(self.total_frame)

    def apply_theme_style(self):
        colors = get_display_palette()
        self.setStyleSheet("background: transparent;")
        self.title_label.setStyleSheet(f"""
            color: {colors['title_text']};
            font-size: 18pt;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        self.count_badge.setStyleSheet(f"""
            background: {colors['accent']};
            color: white;
            border-radius: 13px;
            min-width: 26px;
            min-height: 26px;
            padding: 2px 8px;
            font-size: 10pt;
            font-weight: 800;
            border: none;
        """)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['border']};
                border-radius: 3px;
                min-height: 24px;
            }}
        """)
        self.items_container.setStyleSheet("background: transparent;")
        self.empty_label.setStyleSheet(f"""
            color: {colors['muted']};
            font-size: 15pt;
            font-weight: 700;
            background: transparent;
            border: none;
        """)
        self.total_frame.setStyleSheet(f"""
            QFrame {{
                background: {colors['panel']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
        """)
        label_style = f"color: {colors['muted']}; font-size: 11pt; font-weight: 700; background: transparent; border: none;"
        value_style = f"color: {colors['text']}; font-size: 12pt; font-weight: 800; background: transparent; border: none;"
        self.subtotal_label.setStyleSheet(label_style)
        self.discount_label.setStyleSheet(label_style)
        self.subtotal_value.setStyleSheet(value_style)
        self.discount_value.setStyleSheet(value_style)
        self.grand_label.setStyleSheet(f"color: {colors['title_text']}; font-size: 13pt; font-weight: 800; background: transparent; border: none;")
        self.grand_value.setStyleSheet(f"color: {colors['success']}; font-size: 16pt; font-weight: 900; background: transparent; border: none;")
        for widget in self._items:
            self._style_item_card(widget)

    def _style_item_card(self, frame):
        colors = get_display_palette()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {colors['panel']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        for label in frame.findChildren(QLabel):
            role = label.property("role")
            if role == "name":
                label.setStyleSheet(f"color: {colors['title_text']}; font-size: 11.5pt; font-weight: 800; background: transparent; border: none;")
            elif role == "meta":
                label.setStyleSheet(f"color: {colors['muted']}; font-size: 9.5pt; font-weight: 650; background: transparent; border: none;")
            elif role == "total":
                label.setStyleSheet(f"color: {colors['success']}; font-size: 12pt; font-weight: 900; background: transparent; border: none;")
            elif role == "image":
                label.setStyleSheet(f"""
                    background: {colors['panel_alt']};
                    color: {colors['muted']};
                    border: none;
                    border-radius: 7px;
                    font-size: 8pt;
                    font-weight: 700;
                """)

    def _image_for_product(self, product_id):
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

    def _resolve_image_path(self, item):
        image_path = str(item.get("image") or item.get("image_path") or "").strip()
        if image_path:
            return image_path
        return self._image_for_product(item.get("id"))

    def _rounded_pixmap(self, pixmap, radius=7):
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

    def _make_item_card(self, item):
        symbol = get_currency_symbol()
        qty = int(item.get("qty", 0) or 0)
        price = float(item.get("price", 0) or 0)
        total = qty * price

        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        image_label = QLabel()
        image_label.setProperty("role", "image")
        image_label.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb = _load_thumbnail(self._resolve_image_path(item), self.THUMBNAIL_SIZE)
        if thumb:
            scaled = thumb.scaled(
                self.THUMBNAIL_SIZE,
                self.THUMBNAIL_SIZE,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image_label.setPixmap(self._rounded_pixmap(scaled))
        else:
            image_label.setText("Img")
        layout.addWidget(image_label)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(3)
        name = QLabel(str(item.get("name", "")))
        name.setProperty("role", "name")
        name.setWordWrap(True)
        left.addWidget(name)
        meta = QLabel(f"{qty} x {format_money(price, symbol)}")
        meta.setProperty("role", "meta")
        left.addWidget(meta)
        layout.addLayout(left, 1)

        total_label = QLabel(format_money(total, symbol))
        total_label.setProperty("role", "total")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(total_label)
        self._style_item_card(frame)
        return frame

    def update_display(self, cart_items):
        for widget in self._items:
            self.items_layout.removeWidget(widget)
            widget.deleteLater()
        self._items.clear()

        subtotal = 0.0
        total_items = 0
        for item in cart_items:
            card = self._make_item_card(item)
            self.items_layout.insertWidget(self.items_layout.count() - 1, card)
            self._items.append(card)
            qty = int(item.get("qty", 0) or 0)
            subtotal += float(item.get("price", 0) or 0) * qty
            total_items += qty

        self.scroll_area.setVisible(bool(cart_items))
        self.empty_label.setVisible(not bool(cart_items))
        self.count_badge.setText(str(total_items))
        self._update_totals(subtotal)

    def _update_totals(self, subtotal):
        symbol = get_currency_symbol()
        total_discount = 0.0
        grand_total = subtotal
        parent_window = getattr(self.parent(), "parent_window", None)
        if parent_window and hasattr(parent_window, "totals_widget"):
            total_discount = (
                parent_window.totals_widget.compute_regular_discount(subtotal)
                + parent_window.totals_widget.compute_points_discount(subtotal)
            )
            grand_total = subtotal - total_discount
            if getattr(parent_window, "tax_enabled", False) and hasattr(parent_window, "tax_rate"):
                grand_total += grand_total * (parent_window.tax_rate / 100.0)

        self.subtotal_value.setText(format_money(subtotal, symbol))
        self.discount_value.setText(f"-{format_money(total_discount, symbol)}" if total_discount else format_money(0, symbol))
        self.grand_value.setText(format_money(grand_total, symbol))

    def update_customer_name(self, _customer_id):
        # The new simple display keeps customer information out of the cart header.
        return

    def retranslate_ui(self):
        self.title_label.setText(tr("your_cart"))
        self.subtotal_label.setText(tr("subtotal"))
        self.discount_label.setText(tr("discount"))
