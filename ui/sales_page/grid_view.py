# ui/sales_page/grid_view.py

from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QSizePolicy, QMessageBox,
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect,
    QScroller, QScrollerProperties
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect, QEvent, QPoint
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen, QBrush, QMouseEvent, QTransform, QPainterPath
from models.database import connect_db
from ui.sales_page.product_card import FavouriteProductCard
from ui.sales_page.product_utils import clear_layout_widgets, load_thumbnail, resolve_image_path
from ui.themes.theme_manager import is_dark_theme, get_theme_colors
from ui.widgets.numeric_keypad_dialog import get_numeric_input_value
from utils.currency import get_currency_symbol, format_money
from typing import List, Tuple, Any
from loguru import logger


class GridViewWidget(QScrollArea):
    """
    Responsive scrollable grid of product cards with auto-adjusting spacing.
    """

    product_selected = pyqtSignal(int, str, float, int)
    service_selected = pyqtSignal(int, str, float)
    favourite_toggled = pyqtSignal(int, bool)
    near_bottom = pyqtSignal()

    def __init__(self, parent=None, card_style: str = "classic"):
        super().__init__(parent)
        self._card_style = card_style
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._enable_touch_scrolling()
        
        # ✅ Scroll Bar Style - Same as dark_theme.py and light_theme.py
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #40444b;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5865f2;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #40444b;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #5865f2;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        
        self._grid = QGridLayout(self._container)
        # ✅ Card များ အပေါ်ဘက်သို့ စုစည်းနေစေရန် Alignment ပေးထားပါသည်
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self._container)

        self._cards: List[QWidget] = []
        self._cols = 5
        self._last_rows: List[Any] = []
        self._loading_more = False
        self._has_more = False
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._delayed_populate)
        
        self._is_minimized = False
        self._is_dark = is_dark_theme()
        self._drag_start_pos: QPoint | None = None
        self._drag_start_scroll = 0
        self._drag_scrolling = False
        
        from ui.themes.theme_manager import theme_manager
        theme_manager.theme_changed.connect(self._on_theme_changed)

        scrollbar = self.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.valueChanged.connect(self._on_scroll_value_changed)

    def _enable_touch_scrolling(self) -> None:
        """Enable finger drag and kinetic scrolling for touchscreen product grids."""
        viewport = self.viewport()
        if viewport is None:
            return

        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        viewport.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        QScroller.grabGesture(viewport, QScroller.ScrollerGestureType.TouchGesture)
        QScroller.grabGesture(viewport, QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        scroller = QScroller.scroller(viewport)
        properties = scroller.scrollerProperties()
        properties.setScrollMetric(
            QScrollerProperties.ScrollMetric.VerticalOvershootPolicy,
            QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
        )
        properties.setScrollMetric(
            QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy,
            QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
        )
        properties.setScrollMetric(
            QScrollerProperties.ScrollMetric.FrameRate,
            QScrollerProperties.FrameRates.Fps60,
        )
        properties.setScrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance, 0.006)
        properties.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.08)
        properties.setScrollMetric(QScrollerProperties.ScrollMetric.MaximumClickThroughVelocity, 0.01)
        scroller.setScrollerProperties(properties)

    def _on_theme_changed(self, theme_name: str) -> None:
        self._is_dark = is_dark_theme()
        if self._last_rows:
            self.populate(self._last_rows)

    def _get_responsive_sizes(self, width: int) -> Tuple[int, int, int, int, int]:
        """
        Dynamically calculate card size, spacing, and margins based on available width.
        Returns: (card_width, card_height, h_spacing, v_spacing, margins)
        """
        # Base dimensions
        if self._card_style == "modern":
            card_width = max(150, min(178, int(width * 0.17)))
            card_height = int(card_width * 1.14)
        else:
            card_width = max(110, min(160, int(width * 0.15)))
            card_height = int(card_width * 1.15)
        
        # ✅ Space များကို Screen Size ပေါ်မူတည်ပြီး Auto တွက်ချက်ခြင်း
        h_spacing = max(4, min(16, int(width * 0.008)))
        v_spacing = max(4, min(12, int(width * 0.006)))
        margins = max(6, min(20, int(width * 0.01)))
        if self._card_style == "modern":
            h_spacing = max(12, min(16, h_spacing))
            v_spacing = max(6, min(8, v_spacing))
            margins = max(8, min(14, margins))
        
        return card_width, card_height, h_spacing, v_spacing, margins

    def _calculate_columns(self, width: int) -> int:
        """Calculate columns based on available width - fully responsive"""
        card_width, _, h_spacing, _, margins = self._get_responsive_sizes(width)
        available_width = width - (margins * 2)
        
        cols = max(1, available_width // (card_width + h_spacing))
        return int(cols)

    def _update_responsive_layout(self, width: int) -> None:
        """Update grid spacing and margins auto-adjustingly"""
        _, _, h_spacing, v_spacing, margins = self._get_responsive_sizes(width)
        # ✅ Auto တွက်ချက်ထားသော Spacing များကို Layout တွင် အစားထိုးခြင်း
        self._grid.setHorizontalSpacing(h_spacing)
        self._grid.setVerticalSpacing(v_spacing)
        self._grid.setContentsMargins(margins, margins, margins, margins)

    def populate(self, rows: List[Any]) -> None:
        self._last_rows = rows
        self._cards.clear()
        self._loading_more = False
        clear_layout_widgets(self._grid)

        if not rows:
            self._show_empty_state()
            return

        viewport = self.viewport()
        width = viewport.width() if viewport else self.width()
        
        self._update_responsive_layout(width)
        cols = self._calculate_columns(width)
        self._cols = cols
        
        card_width, card_height, _, _, _ = self._get_responsive_sizes(width)
        
        for i in reversed(range(self._grid.count())):
            item = self._grid.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        
        for idx, prod in enumerate(rows):
            prod_id, name, price, stock, low_stock, sold_by, image_path = prod[:7]
            is_favourite = prod[7] if len(prod) > 7 else False
            
            category_name = prod[8] if len(prod) > 8 else ""
            discount_percent = prod[9] if len(prod) > 9 else 0
            discount_type = prod[10] if len(prod) > 10 else "percentage"
            manual_price = prod[11] if len(prod) > 11 else 0
            if self._card_style == "modern":
                card = ModernProductCard(
                    prod_id, name, price, stock, low_stock,
                    sold_by, image_path, category_name, discount_percent,
                    discount_type, manual_price,
                    is_favourite, self._is_dark,
                    card_width, card_height
                )
            else:
                card = LoyverseProductCard(
                    prod_id, name, price, stock, low_stock,
                    sold_by, image_path, is_favourite, self._is_dark,
                    discount_percent, discount_type, manual_price,
                    card_width, card_height
                )
            card.clicked.connect(self._on_card_clicked)
            card.installEventFilter(self)
            card.favourite_toggled.connect(self.favourite_toggled.emit)
            
            row = idx // cols
            col = idx % cols
            # ✅ Alignment ကို Center သတ်မှတ်ထားသဖြင့် Spacing များ ညီညာစွာ ခွဲဝေပါမည်
            self._grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)
            self._cards.append(card)

        # ✅ Stretch Ratio ကို ညီအောင် ထားရှိခြင်း
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)

    def append_rows(self, rows: List[Any]) -> None:
        """Append another product batch without rebuilding existing cards."""
        if not rows:
            self._loading_more = False
            return

        if not self._last_rows:
            self.populate(rows)
            return

        viewport = self.viewport()
        width = viewport.width() if viewport else self.width()
        self._update_responsive_layout(width)
        cols = self._calculate_columns(width)
        self._cols = cols
        card_width, card_height, _, _, _ = self._get_responsive_sizes(width)

        start_idx = len(self._last_rows)
        self._last_rows.extend(rows)

        for offset, prod in enumerate(rows):
            idx = start_idx + offset
            prod_id, name, price, stock, low_stock, sold_by, image_path = prod[:7]
            is_favourite = prod[7] if len(prod) > 7 else False

            category_name = prod[8] if len(prod) > 8 else ""
            discount_percent = prod[9] if len(prod) > 9 else 0
            discount_type = prod[10] if len(prod) > 10 else "percentage"
            manual_price = prod[11] if len(prod) > 11 else 0
            if self._card_style == "modern":
                card = ModernProductCard(
                    prod_id, name, price, stock, low_stock,
                    sold_by, image_path, category_name, discount_percent,
                    discount_type, manual_price,
                    is_favourite, self._is_dark,
                    card_width, card_height
                )
            else:
                card = LoyverseProductCard(
                    prod_id, name, price, stock, low_stock,
                    sold_by, image_path, is_favourite, self._is_dark,
                    discount_percent, discount_type, manual_price,
                    card_width, card_height
                )
            card.clicked.connect(self._on_card_clicked)
            card.installEventFilter(self)
            card.favourite_toggled.connect(self.favourite_toggled.emit)

            row = idx // cols
            col = idx % cols
            self._grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)
            self._cards.append(card)

        for c in range(cols):
            self._grid.setColumnStretch(c, 1)

        self._loading_more = False

    def set_lazy_state(self, loading: bool = False, has_more: bool = False) -> None:
        self._loading_more = loading
        self._has_more = has_more

    def eventFilter(self, obj, event) -> bool:
        cards = getattr(self, "_cards", ())
        if obj in cards:
            event_type = event.type()

            if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = event.globalPosition().toPoint()
                self._drag_start_scroll = self.verticalScrollBar().value()
                self._drag_scrolling = False
                return False

            if event_type == QEvent.Type.MouseMove and self._drag_start_pos is not None:
                current_pos = event.globalPosition().toPoint()
                delta = current_pos - self._drag_start_pos
                if self._drag_scrolling or abs(delta.y()) > 10:
                    self._drag_scrolling = True
                    self.verticalScrollBar().setValue(self._drag_start_scroll - delta.y())
                    return True

            if event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                was_dragging = self._drag_scrolling
                self._drag_start_pos = None
                self._drag_scrolling = False
                if was_dragging:
                    return True

        return super().eventFilter(obj, event)

    def _on_scroll_value_changed(self, value: int) -> None:
        if self._loading_more or not self._has_more:
            return

        scrollbar = self.verticalScrollBar()
        if scrollbar is None:
            return

        if scrollbar.maximum() - value <= 240:
            self._loading_more = True
            self.near_bottom.emit()

    def _show_empty_state(self) -> None:
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)
        
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        text_color = colors.get('text', '#ffffff' if is_dark else '#212529')
        text_secondary = colors.get('text_secondary', '#72767d' if is_dark else '#6c757d')
        
        icon_label = QLabel("📦")
        icon_label.setStyleSheet(f"""
            font-size: 36px;
            color: {text_secondary};
            background: transparent;
            border: none;
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_label)
        
        title_label = QLabel("No Products Found")
        title_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {text_color};
            background: transparent;
            border: none;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title_label)
        
        desc_label = QLabel("Try adjusting your search or filters")
        desc_label.setStyleSheet(f"""
            font-size: 11px;
            color: {text_secondary};
            background: transparent;
            border: none;
        """)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(desc_label)
        
        self._grid.addWidget(empty_widget, 0, 0, 1, self._cols)

    def _delayed_populate(self) -> None:
        if self._is_minimized:
            return
        if self._last_rows:
            self.populate(self._last_rows)

    def _on_card_clicked(self, prod_id: int) -> None:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, price, stock, sold_by FROM products WHERE id=?", (prod_id,))
        product = cursor.fetchone()
        conn.close()
        
        if product:
            name, price, stock, sold_by = product
            price = float(price) if price else 0.0
            
            sold_by_mode = str(sold_by or "").lower()
            if sold_by_mode == "service":
                manual_price, ok = self._show_service_price_dialog(name)
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
    
    def _show_service_price_dialog(self, product_name: str) -> Tuple[float, bool]:
        return get_numeric_input_value(
            self,
            "Service Price",
            f"Enter price for {product_name}:",
            0,
            decimals=2,
            minimum=0,
            maximum=999999999,
        )
    
    def _show_message(self, title: str, text: str, icon: QMessageBox.Icon = QMessageBox.Icon.Information) -> None:
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
                    border-radius: 8px;
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
            """)
        else:
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #ffffff;
                    color: #212529;
                    border-radius: 8px;
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
            """)
        
        msg.exec()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = event.size().width()
        height = event.size().height()
        
        if width <= 10 or height <= 10:
            self._is_minimized = True
            return
        
        self._is_minimized = False
        
        # ✅ Responsive Layout ကို Dynamic အလိုက် ချက်ချင်း update လုပ်ခြင်း
        self._update_responsive_layout(width)
        
        new_cols = self._calculate_columns(width)
        if new_cols != self._cols or self._last_rows:
            self._resize_timer.start(100)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._is_minimized:
            self._is_minimized = False
            if self._last_rows:
                QTimer.singleShot(100, lambda: self.populate(self._last_rows))

    def populate_and_store(self, rows: List[Any]) -> None:
        self._last_rows = rows
        self.populate(rows)

    def update_theme(self) -> None:
        self._is_dark = is_dark_theme()
        if self._last_rows:
            self.populate(self._last_rows)


class LoyverseProductCard(QWidget):
    """
    Responsive product card.
    """
    
    clicked = pyqtSignal(int)
    favourite_toggled = pyqtSignal(int, bool)

    def __init__(self, prod_id: int, name: str, price: float, stock: int, 
                 low_stock: int, sold_by: str, image_path: str, 
                 is_favourite: bool = False, is_dark: bool = False,
                 discount_percent: float = 0, discount_type: str = "percentage",
                 manual_price: float = 0,
                 card_width: int = 135, card_height: int = 155, parent=None):
        super().__init__(parent)
        
        self._prod_id = prod_id
        self._name = name
        self._price = price
        self._stock = stock
        self._low_stock = low_stock
        self._sold_by = sold_by
        self._is_favourite = is_favourite
        self._is_dark = is_dark
        self._image_path = image_path
        self._discount_percent = float(discount_percent or 0)
        self._discount_type = discount_type or "percentage"
        self._manual_price = float(manual_price or 0)
        self._card_width = card_width
        self._card_height = card_height
        
        self.setFixedSize(card_width, card_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._setup_ui()
        self._apply_theme()
        self._load_image()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        padding = max(4, min(6, self._card_width // 30))
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(0)
        
        image_height = self._card_height - 30
        self.image_frame = QFrame()
        self.image_frame.setFixedHeight(image_height)
        self.image_frame.setStyleSheet("""
            QFrame {
                border-radius: 6px;
                background-color: #f0f0f0;
            }
        """)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background: transparent; border: none;")
        
        image_layout = QVBoxLayout(self.image_frame)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self.image_label)
        
        overlay_height = max(36, min(44, self._card_height // 4))
        self.overlay_widget = QFrame(self.image_frame)
        self.overlay_widget.setFixedHeight(overlay_height)
        self.overlay_widget.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.65);
                border-radius: 0 0 6px 6px;
                border: none;
            }
        """)
        
        overlay_layout = QVBoxLayout(self.overlay_widget)
        overlay_layout.setContentsMargins(4, 2, 4, 2)
        
        font_size = max(10, min(12, self._card_width // 12))
        self.overlay_name_label = QLabel(self._name)
        self.overlay_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_name_label.setWordWrap(True)
        self.overlay_name_label.setStyleSheet(f"""
            font-size: {font_size}px;
            font-weight: 400;
            color: {'#cfd4da' if int(self._stock or 0) <= 0 and not (self._sold_by and str(self._sold_by).lower() == 'service') else 'white'};
            background: transparent;
            border: none;
        """)
        overlay_layout.addWidget(self.overlay_name_label)
        
        self.overlay_widget.setParent(self.image_frame)
        self.overlay_widget.move(0, self.image_frame.height() - self.overlay_widget.height())
        
        layout.addWidget(self.image_frame)

        self.discount_badge = QLabel(self._discount_badge_text(), self.image_frame)
        self.discount_badge.setObjectName("classicDiscountBadge")
        self.discount_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_width = max(50, min(self.image_frame.width() - 22, int(self._card_width * (0.48 if self._discount_type == "manual_price" else 0.32))))
        self.discount_badge.setFixedSize(badge_width, 22)
        self.discount_badge.move(0, 0)
        self.discount_badge.setVisible(self._has_discount_badge())
        self._apply_discount_badge_style()

        self.stock_badge = QLabel("Out of Stock", self.image_frame)
        self.stock_badge.setObjectName("classicStockBadge")
        self.stock_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stock_badge.setFixedSize(max(82, int(self._card_width * 0.70)), 24)
        self.stock_badge.move(
            (self.image_frame.width() - self.stock_badge.width()) // 2,
            max(8, (image_height - self.stock_badge.height()) // 2)
        )
        self.stock_badge.setVisible(self._is_out_of_stock())
        self._apply_stock_badge_style()
        
        fav_size = max(28, min(34, self._card_width // 5))
        self.fav_button = QWidget(self.image_frame)
        self.fav_button.setFixedSize(fav_size, fav_size)
        self.fav_button.move(self.image_frame.width() - fav_size - 4, 4)
        self.fav_button.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        
        self.fav_label = ClickableLabel(self.fav_button)
        self.fav_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fav_label.setGeometry(0, 0, fav_size, fav_size)
        fav_font_size = max(18, min(22, self._card_width // 6))
        self.fav_label.setStyleSheet(f"""
            font-size: {fav_font_size}px;
            background: transparent;
            border: none;
        """)
        self.fav_label.clicked.connect(self._toggle_favourite)
        
        self._update_favourite_display()

    def _apply_theme(self) -> None:
        colors = get_theme_colors()
        
        if self._is_dark:
            card_bg = colors.get('card_bg', '#2f3136')
            border_color = colors.get('border', '#40444b')
            hover_border = '#5865f2'
        else:
            card_bg = colors.get('card_bg', '#ffffff')
            border_color = colors.get('border', '#e0e0e0')
            hover_border = '#5865f2'
        
        self.setObjectName("LoyverseProductCard")
        
        self.setStyleSheet(f"""
            QWidget#LoyverseProductCard {{
                background-color: {card_bg};
                border-radius: 8px;
                border: 2px solid {border_color};
            }}
            QWidget#LoyverseProductCard:hover {{
                border: 2px solid {hover_border};
            }}
        """)
        if hasattr(self, "discount_badge"):
            self.discount_badge.setVisible(self._has_discount_badge())
            self._apply_discount_badge_style()
        if hasattr(self, "stock_badge"):
            self.stock_badge.setVisible(self._is_out_of_stock())
            self._apply_stock_badge_style()

    def _load_image(self) -> None:
        if self._image_path:
            try:
                image_size = self.image_frame.height() - 4
                pixmap = load_thumbnail(str(self._image_path), max(40, image_size))
                if pixmap and not pixmap.isNull():
                    scaled = pixmap.scaled(
                        image_size, image_size,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    if self._is_out_of_stock():
                        dimmed = QPixmap(scaled.size())
                        dimmed.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(dimmed)
                        painter.drawPixmap(0, 0, scaled)
                        painter.fillRect(dimmed.rect(), QColor(255, 255, 255, 170))
                        painter.end()
                        scaled = dimmed
                    self.image_label.setPixmap(scaled)
                    self._update_overlay_position()
                    return
            except Exception:
                pass
        
        emoji_size = max(20, min(30, self._card_width // 5))
        self.image_label.setText("📦")
        self.image_label.setStyleSheet(f"""
            font-size: {emoji_size}px;
            color: #c0c0c0;
            background: transparent;
            border: none;
        """)
        self._update_overlay_position()

    def _has_discount_badge(self) -> bool:
        if self._discount_type == "manual_price":
            return self._manual_price > 0
        return self._discount_percent > 0

    def _is_out_of_stock(self) -> bool:
        sold_by_mode = str(self._sold_by or "").lower()
        return sold_by_mode not in ("service", "restaurant") and int(self._stock or 0) <= 0

    def _discount_badge_text(self) -> str:
        if self._discount_type == "manual_price" and self._manual_price > 0:
            return format_money(self._manual_price, get_currency_symbol())
        return f"{self._discount_percent:g}% Off"

    def _apply_discount_badge_style(self) -> None:
        if not hasattr(self, "discount_badge"):
            return
        self.discount_badge.setStyleSheet("""
            QLabel {
                background-color: #ffe15a;
                color: #1f1f1f;
                border: none;
                border-top-left-radius: 6px;
                border-bottom-right-radius: 8px;
                font-size: 10px;
                font-weight: 700;
            }
        """)

    def _apply_stock_badge_style(self) -> None:
        if not hasattr(self, "stock_badge"):
            return
        self.stock_badge.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #343a40;
                border: none;
                font-size: 11px;
                font-weight: 800;
            }
        """)

    def _update_overlay_position(self) -> None:
        if hasattr(self, 'overlay_widget'):
            self.overlay_widget.move(0, self.image_frame.height() - self.overlay_widget.height())
            self.overlay_widget.setFixedWidth(self.image_frame.width())

        if hasattr(self, 'discount_badge'):
            self.discount_badge.move(0, 0)

        if hasattr(self, 'stock_badge'):
            self.stock_badge.move(
                (self.image_frame.width() - self.stock_badge.width()) // 2,
                max(8, (self.image_frame.height() - self.stock_badge.height()) // 2)
            )
        
        if hasattr(self, 'fav_button'):
            fav_size = self.fav_button.width()
            self.fav_button.move(self.image_frame.width() - fav_size - 4, 4)

    def _update_favourite_display(self) -> None:
        fav_size = self.fav_label.width()
        font_size = max(18, min(22, int(fav_size * 0.72)))
        
        if self._is_favourite:
            self.fav_label.setText("★")
            self.fav_label.setStyleSheet(f"""
                font-size: {font_size}px;
                color: #f5a623;
                background: transparent;
                border: none;
            """)
        else:
            self.fav_label.setText("☆")
            self.fav_label.setStyleSheet(f"""
                font-size: {font_size}px;
                color: rgba(255, 255, 255, 0.8);
                background: transparent;
                border: none;
            """)

    def _toggle_favourite(self) -> None:
        self._is_favourite = not self._is_favourite
        self._update_favourite_display()
        self.favourite_toggled.emit(self._prod_id, self._is_favourite)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_overlay_position()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.fav_button.geometry().contains(event.pos()):
                event.accept()
                return
            self._press_pos = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            press_pos = getattr(self, "_press_pos", None)
            self._press_pos = None
            if press_pos is not None and (event.pos() - press_pos).manhattanLength() <= 10:
                self.clicked.emit(self._prod_id)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def update_theme(self) -> None:
        self._is_dark = is_dark_theme()
        self._apply_theme()


class ModernProductCard(QWidget):
    clicked = pyqtSignal(int)
    favourite_toggled = pyqtSignal(int, bool)

    def __init__(self, prod_id: int, name: str, price: float, stock: int,
                 low_stock: int, sold_by: str, image_path: str, category_name: str = "",
                 discount_percent: float = 0,
                 discount_type: str = "percentage", manual_price: float = 0,
                 is_favourite: bool = False, is_dark: bool = False,
                 card_width: int = 220, card_height: int = 300, parent=None):
        super().__init__(parent)
        self._prod_id = prod_id
        self._name = name
        self._price = float(price or 0)
        self._stock = int(stock or 0)
        self._low_stock = int(low_stock or 0)
        self._sold_by = sold_by
        self._image_path = image_path
        self._category_name = category_name
        self._discount_percent = float(discount_percent or 0)
        self._discount_type = discount_type or "percentage"
        self._manual_price = float(manual_price or 0)
        self._is_favourite = is_favourite
        self._is_dark = is_dark
        self._card_width = card_width
        self._card_height = card_height
        self._card_radius = max(14, int(self._card_width * 0.08))
        self._image_radius = max(12, int(self._card_width * 0.07))

        self.setObjectName("ModernProductCard")
        self.setFixedSize(card_width, card_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self._apply_theme()
        self._load_image()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        pad = max(10, int(self._card_width * 0.06))
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(7)

        self.image_frame = QFrame()
        self.image_frame.setObjectName("modernImageFrame")
        image_h = int(self._card_width * 0.72)
        image_w = self._card_width - (pad * 2)
        self.image_frame.setFixedSize(image_w, image_h)
        image_layout = QVBoxLayout(self.image_frame)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setFixedSize(image_w, image_h)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background: transparent; border: none;")
        image_layout.addWidget(self.image_label)
        layout.addWidget(self.image_frame)

        self.discount_badge = QLabel(self._discount_badge_text(), self.image_frame)
        self.discount_badge.setObjectName("modernDiscountBadge")
        self.discount_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_width = max(52, min(self.image_frame.width() - 24, int(self._card_width * (0.48 if self._discount_type == "manual_price" else 0.28))))
        self.discount_badge.setFixedSize(badge_width, 22)
        self.discount_badge.move(0, 0)
        self.discount_badge.setVisible(self._has_discount_badge())

        self.stock_badge = QLabel("Out of Stock", self.image_frame)
        self.stock_badge.setObjectName("modernStockBadge")
        self.stock_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stock_badge.setFixedSize(max(88, int(self._card_width * 0.70)), 24)
        self.stock_badge.move(
            (self.image_frame.width() - self.stock_badge.width()) // 2,
            max(8, (image_h - self.stock_badge.height()) // 2)
        )
        self.stock_badge.setVisible(self._is_out_of_stock())

        self.fav_button = QWidget(self.image_frame)
        fav_size = max(26, int(self._card_width * 0.18))
        self.fav_button.setObjectName("modernFavouriteButton")
        self.fav_button.setFixedSize(fav_size, fav_size)
        self.fav_button.move(self.image_frame.width() - fav_size + 1, -1)

        self.fav_label = ClickableLabel(self.fav_button)
        self.fav_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fav_label.setGeometry(0, 0, fav_size, fav_size)
        self.fav_label.clicked.connect(self._toggle_favourite)
        self._update_favourite_display()

        name_font = max(11, min(14, self._card_width // 14))
        self.name_label = QLabel(self._name)
        self.name_label.setWordWrap(True)
        self.name_label.setFixedHeight(name_font * 2 + 12)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.name_label.setStyleSheet(f"font-size: {name_font}px; font-weight: 600; background: transparent; border: none;")
        layout.addWidget(self.name_label)

        self._apply_shadow()

    def _status_text(self) -> str:
        if self._category_name:
            return str(self._category_name)
        sold_by_mode = str(self._sold_by or "").lower()
        if sold_by_mode == "service":
            return "Service"
        if sold_by_mode == "restaurant":
            return "Menu"
        if self._stock <= 0:
            return "Out"
        if self._stock <= self._low_stock:
            return "Low"
        return "In Stock"

    def _is_out_of_stock(self) -> bool:
        sold_by_mode = str(self._sold_by or "").lower()
        return sold_by_mode not in ("service", "restaurant") and self._stock <= 0

    def _has_discount_badge(self) -> bool:
        if self._discount_type == "manual_price":
            return self._manual_price > 0
        return self._discount_percent > 0

    def _discount_badge_text(self) -> str:
        if self._discount_type == "manual_price" and self._manual_price > 0:
            return format_money(self._manual_price, get_currency_symbol())
        return f"{self._discount_percent:g}% Off"

    def _apply_theme(self) -> None:
        colors = get_theme_colors()
        card_bg = "#fbfaf7" if not self._is_dark else "#252a2d"
        text = colors.get("text", "#212529")
        image_bg = "#f4f2ed" if not self._is_dark else "#30363a"
        card_border = "#ebe6dc" if not self._is_dark else "#3d464b"
        hover_border = "#22c55e" if not self._is_dark else "#37d67a"
        badge_bg = "#ffe15a"
        badge_text = "#1f1f1f"
        stock_text = colors.get("text_secondary", "#6c757d")

        self.setStyleSheet(f"""
            QWidget#ModernProductCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: {self._card_radius}px;
            }}
            QWidget#ModernProductCard:hover {{
                border-color: {hover_border};
            }}
            QFrame#modernImageFrame {{
                background-color: {image_bg};
                border: none;
                border-radius: {self._image_radius}px;
            }}
            QLabel#modernDiscountBadge {{
                background-color: {badge_bg};
                color: {badge_text};
                border: none;
                border-top-left-radius: {self._image_radius}px;
                border-bottom-right-radius: 8px;
                font-size: 10px;
                font-weight: 700;
            }}
            QWidget#modernFavouriteButton {{
                background: transparent;
                border: none;
            }}
            QLabel#modernStockBadge {{
                background: transparent;
                color: {stock_text};
                border: none;
                font-size: 11px;
                font-weight: 800;
            }}
        """)
        self.name_label.setStyleSheet(self.name_label.styleSheet() + f" color: {text};")
        if self._is_out_of_stock():
            muted = colors.get("text_secondary", "#6c757d")
            self.name_label.setStyleSheet(self.name_label.styleSheet() + f" color: {muted};")
        self._update_favourite_display()
        self._apply_shadow()

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18 if not self._is_dark else 22)
        shadow.setXOffset(0)
        shadow.setYOffset(7)
        shadow.setColor(QColor(0, 0, 0, 26 if not self._is_dark else 84))
        self.setGraphicsEffect(shadow)

    def _rounded_pixmap(self, pixmap: QPixmap, width: int, height: int) -> QPixmap:
        rounded = QPixmap(width, height)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, self._image_radius, self._image_radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
        if self._is_out_of_stock():
            painter.fillRect(0, 0, width, height, QColor(255, 255, 255, 165) if not self._is_dark else QColor(0, 0, 0, 150))
        painter.end()
        return rounded

    def _load_image(self) -> None:
        try:
            image_w = max(80, self.image_label.width() or self.image_frame.width())
            image_h = max(80, self.image_label.height() or self.image_frame.height())
            pixmap = load_thumbnail(str(self._image_path or ""), int(max(image_w, image_h)))
            if (not pixmap or pixmap.isNull()) and self._image_path:
                resolved_path = resolve_image_path(str(self._image_path))
                direct_pixmap = QPixmap(resolved_path)
                if not direct_pixmap.isNull():
                    pixmap = direct_pixmap
            if pixmap and not pixmap.isNull():
                self.image_label.setText("")
                self.image_label.setPixmap(self._rounded_pixmap(
                    pixmap,
                    int(image_w),
                    int(image_h)
                ))
                return
        except Exception as exc:
            logger.warning(f"Modern grid image load failed for product {self._prod_id}: {exc}")
        self.image_label.setText("Image")
        self.image_label.setStyleSheet("font-size: 13px; color: #adb5bd; background: transparent; border: none;")

    def _emit_clicked(self) -> None:
        self.clicked.emit(self._prod_id)

    def _update_overlay_position(self) -> None:
        if hasattr(self, "stock_badge"):
            self.stock_badge.move(
                (self.image_frame.width() - self.stock_badge.width()) // 2,
                max(8, (self.image_frame.height() - self.stock_badge.height()) // 2)
            )
        if hasattr(self, "fav_button"):
            fav_size = self.fav_button.width()
            self.fav_button.move(self.image_frame.width() - fav_size + 1, -1)

    def _update_favourite_display(self) -> None:
        if not hasattr(self, "fav_label"):
            return
        fav_size = max(18, self.fav_label.width())
        font_size = max(17, int(fav_size * 0.68))
        if self._is_favourite:
            star = "★"
            color = "#f5a623"
        else:
            star = "☆"
            color = "#7a7f86" if not self._is_dark else "#d7dbe3"
        self.fav_label.setText(star)
        self.fav_label.setStyleSheet(f"""
            font-size: {font_size}px;
            color: {color};
            background: transparent;
            border: none;
        """)

    def _toggle_favourite(self) -> None:
        self._is_favourite = not self._is_favourite
        self._update_favourite_display()
        self.favourite_toggled.emit(self._prod_id, self._is_favourite)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            image_pos = self.image_frame.mapFrom(self, event.pos())
            if self.image_frame.rect().contains(image_pos) and self.fav_button.geometry().contains(image_pos):
                event.accept()
                return
            self._press_pos = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            press_pos = getattr(self, "_press_pos", None)
            self._press_pos = None
            if press_pos is not None and (event.pos() - press_pos).manhattanLength() <= 10:
                self.clicked.emit(self._prod_id)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_overlay_position()

    def update_theme(self) -> None:
        self._is_dark = is_dark_theme()
        self._apply_theme()


class ClickableLabel(QLabel):
    """Custom QLabel that emits a clicked signal"""
    
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)
