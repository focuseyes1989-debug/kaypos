# ui/customer_page/customer_display.py
import os

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from models.database import connect_db
from utils.receipt_images import resolve_receipt_image_path
from .customer_display_cart import CartDisplayWidget
from .customer_display_theme import get_display_palette, get_launcher_style
from .customer_display_utils import set_default_geometry, show_on_customer_monitor_fullscreen


class CustomerDisplayWindow(QWidget):
    """Local customer display with shop information and the current cart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.is_maximized = False

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumSize(640, 420)
        self.setup_ui()
        self.apply_theme_style()
        set_default_geometry(self)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_display)
        self.refresh_timer.start(500)

        self.load_shop_info()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(10)

        self.header_frame = QFrame()
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(64, 46)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.logo_label)

        shop_text_layout = QVBoxLayout()
        shop_text_layout.setContentsMargins(0, 0, 0, 0)
        shop_text_layout.setSpacing(2)
        self.shop_name_label = QLabel("ZAY POS")
        self.shop_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.shop_detail_label = QLabel("")
        self.shop_detail_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.shop_detail_label.setWordWrap(True)
        shop_text_layout.addWidget(self.shop_name_label)
        shop_text_layout.addWidget(self.shop_detail_label)
        header_layout.addLayout(shop_text_layout, 1)
        root.addWidget(self.header_frame)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)

        self.cart_frame = QFrame()
        self.cart_frame.setMinimumWidth(300)
        self.cart_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cart_layout = QVBoxLayout(self.cart_frame)
        cart_layout.setContentsMargins(10, 10, 10, 10)
        cart_layout.setSpacing(0)
        self.cart_display = CartDisplayWidget(self)
        cart_layout.addWidget(self.cart_display)
        columns.addWidget(self.cart_frame, 3)

        root.addLayout(columns, 1)

    def apply_theme_style(self):
        colors = get_display_palette()
        self.setStyleSheet(get_launcher_style())
        self.header_frame.setStyleSheet(f"""
            QFrame {{
                background: {colors['panel']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
        """)
        self.logo_label.setStyleSheet(f"""
            background: transparent;
            color: {colors['muted']};
            border: none;
            border-radius: 4px;
            font-size: 9pt;
            font-weight: 800;
        """)
        self.shop_name_label.setStyleSheet(f"""
            color: {colors['title_text']};
            font-size: 15pt;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        self.shop_detail_label.setStyleSheet(f"""
            color: {colors['muted']};
            font-size: 10.5pt;
            font-weight: 650;
            background: transparent;
            border: none;
        """)
        panel_style = f"""
            QFrame {{
                background: {colors['panel_alt']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
        """
        self.cart_frame.setStyleSheet(panel_style)
        if self.cart_display:
            self.cart_display.apply_theme_style()

    def _settings(self):
        values = {}
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value
                FROM settings
                WHERE key IN (
                    'shop_name', 'shop_address', 'shop_phone', 'shop_logo'
                )
            """)
            values = dict(cursor.fetchall())
            conn.close()
        except Exception:
            pass
        return values

    def load_shop_info(self):
        settings = self._settings()
        shop_name = settings.get("shop_name") or "ZAY POS"
        address = settings.get("shop_address") or ""
        phone = settings.get("shop_phone") or ""
        details = " | ".join([part for part in (address, phone) if part])
        self.shop_name_label.setText(shop_name)
        self.shop_detail_label.setText(details)

        logo_path = resolve_receipt_image_path("logo") or settings.get("shop_logo") or ""
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap.scaled(
                    60,
                    42,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                self.logo_label.setText("")
                return
        self.logo_label.setPixmap(QPixmap())
        self.logo_label.setText("Logo")

    def refresh_display(self):
        if not self.parent_window or not hasattr(self.parent_window, "cart_widget"):
            return
        self.cart_display.update_display(self.parent_window.cart_widget.get_cart())

    def toggle_maximize(self):
        self.is_maximized = not self.is_maximized
        if self.is_maximized:
            show_on_customer_monitor_fullscreen(self)
        else:
            self.showNormal()
            set_default_geometry(self)

    def close_display(self):
        self.refresh_timer.stop()
        self.close()
        if self.parent_window and hasattr(self.parent_window, "customer_display_closed"):
            self.parent_window.customer_display_closed()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.isFullScreen():
            show_on_customer_monitor_fullscreen(self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_display()
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_maximize()
        super().keyPressEvent(event)

    def retranslateUi(self):
        if hasattr(self, "cart_display"):
            self.cart_display.retranslate_ui()
