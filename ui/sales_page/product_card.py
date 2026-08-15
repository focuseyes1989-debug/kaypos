# ui/sales_page/product_card.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPainterPath, QIcon
from utils.currency import get_currency_symbol, format_money
from ui.sales_page.product_utils import load_thumbnail
from ui.themes.theme_manager import get_theme_colors
import os


class ProductCard(QFrame):
    """A clickable card widget displaying one product in grid view."""

    clicked = pyqtSignal(int)   # emits prod_id

    # Status colours (same as list view)
    COLOR_OUT   = "#e74c3c"
    COLOR_LOW   = "#e67e22"
    COLOR_OK    = "#2ecc71"
    COLOR_SVC   = "#3498db"

    def __init__(self, prod_id, name, price, stock, low_stock, sold_by, image_path, parent=None):
        super().__init__(parent)
        self.setObjectName("ProductCard")
        self.prod_id  = prod_id
        self.sold_by  = sold_by
        self.stock    = stock
        self.low_stock = low_stock

        # Card size - responsive
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(220)
        self.setMaximumHeight(250)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- Image ---
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setFixedHeight(120)
        self.img_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        thumb = load_thumbnail(image_path, 120, prod_id)
        if thumb:
            scaled_thumb = thumb.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
            rounded_thumb = self._get_rounded_pixmap(scaled_thumb, radius=8)
            self.img_label.setPixmap(rounded_thumb)
        else:
            self.img_label.setText("📦")
            self.img_label.setFont(QFont("", 36))
        layout.addWidget(self.img_label)

        # --- Name ---
        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFont(QFont("", 10, QFont.Weight.Bold))
        self.name_label.setMaximumHeight(45)
        layout.addWidget(self.name_label)

        # --- Price ---
        symbol = get_currency_symbol()
        if sold_by and sold_by.lower() == "service":
            price_text = "Service"
        else:
            price_text = format_money(price, symbol)
        self.price_label = QLabel(price_text)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.price_label.setFont(QFont("", 10))
        layout.addWidget(self.price_label)

        # --- Status badge (with stock count) ---
        status_text, status_color = self._get_status(sold_by, stock, low_stock)
        
        if sold_by and sold_by.lower() == "service":
            badge_text = "Service"
        else:
            badge_text = f"{status_text} ({stock})"
        
        self.badge = QLabel(badge_text)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(
            f"background-color: {status_color}; color: white; border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(self.badge)

        # Apply theme-aware style
        self._apply_card_style()

    def _get_rounded_pixmap(self, src_pixmap, radius=8):
        """Image ရဲ့ ထောင့်တွေကို သတ်မှတ်ထားတဲ့ radius အတိုင်း လုံးပေးသော Method"""
        if src_pixmap.isNull():
            return src_pixmap
            
        target = QPixmap(src_pixmap.size())
        target.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        path = QPainterPath()
        rect = QRectF(0, 0, src_pixmap.width(), src_pixmap.height())
        path.addRoundedRect(rect, radius, radius)
        
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src_pixmap)
        painter.end()
        
        return target

    def _apply_card_style(self):
        """Apply card style that adapts to current theme from ThemeManager."""
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QFrame#ProductCard {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
                padding: 4px;
            }}
            QFrame#ProductCard:hover {{
                border: 2px solid {colors['border_hover']};
                background-color: {colors['card_hover']};
            }}
            QFrame#ProductCard QLabel {{
                background-color: transparent;
                color: {colors['text']};
            }}
        """)
        
        self.style().unpolish(self)
        self.style().polish(self)

    @staticmethod
    def _get_status(sold_by, stock, low_stock):
        if sold_by and sold_by.lower() == "service":
            return "Service", ProductCard.COLOR_SVC
        if stock <= 0:
            return "Out of Stock", ProductCard.COLOR_OUT
        if stock <= low_stock:
            return "Low Stock", ProductCard.COLOR_LOW
        return "In Stock", ProductCard.COLOR_OK

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            press_pos = getattr(self, "_press_pos", None)
            self._press_pos = None
            if press_pos is not None and (event.pos() - press_pos).manhattanLength() <= 10:
                self.clicked.emit(self.prod_id)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def update_theme(self):
        """Update card style when theme changes."""
        self._apply_card_style()


# =============================================================================
# FavouriteProductCard - Grid View Only
# =============================================================================

class FavouriteProductCard(ProductCard):
    """ProductCard with favourite star toggle - Grid View Only."""
    
    favourite_toggled = pyqtSignal(int, bool)
    
    def __init__(self, prod_id, name, price, stock, low_stock, sold_by, image_path, is_favourite=False, parent=None):
        self._is_favourite = is_favourite
        super().__init__(prod_id, name, price, stock, low_stock, sold_by, image_path, parent)
        
        # ✅ Favourite Star Button - Using SVG icon
        self.fav_btn = QPushButton(self)
        self.fav_btn.setFixedSize(35, 35)
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
        """)
        self.fav_btn.clicked.connect(self.toggle_favourite)
        
        # ✅ Set SVG icon
        self._update_fav_icon()
        
        # Position button (top-right corner)
        self.fav_btn.move(self.width() - 50, 4)
        self.fav_btn.raise_()
    
    def _load_svg_icon(self, icon_name, size=24):
        """Load SVG icon from assets/icons folder"""
        icon_paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        # Scale to desired size
                        scaled = pixmap.scaled(
                            size, size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        return QIcon(scaled)
                except Exception:
                    pass
        return None
    
    def _get_fav_icon(self, is_favourite):
        """Get favourite icon based on state"""
        icon_name = "favorite" if is_favourite else "favorite_border"
        return self._load_svg_icon(icon_name)
    
    def _update_fav_icon(self):
        """Update the favourite button icon"""
        icon = self._get_fav_icon(self._is_favourite)
        if icon and not icon.isNull():
            self.fav_btn.setIcon(icon)
            self.fav_btn.setIconSize(self.fav_btn.size())
        else:
            # Fallback to emoji if SVG not found
            self.fav_btn.setText("★" if self._is_favourite else "☆")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #f1c40f;
                    font-size: 24px;
                    font-weight: bold;
                    padding: 0px;
                }
            """)
    
    def toggle_favourite(self):
        self._is_favourite = not self._is_favourite
        self._update_fav_icon()
        self.favourite_toggled.emit(self.prod_id, self._is_favourite)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fav_btn.move(self.width() - 50, 4)
        self.fav_btn.raise_()
