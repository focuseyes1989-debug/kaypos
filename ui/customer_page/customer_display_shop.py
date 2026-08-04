# ui/customer_page/customer_display_shop.py
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout

from models.database import connect_db
from utils.translations import tr
from .customer_display_theme import get_display_palette


class ShopInfoWidget:
    """Shop information and logo cards for the customer display."""

    def __init__(self, parent):
        self.parent = parent
        self.logo_group = None
        self.shop_group = None
        self.setup_ui()

    def _card_style(self, colors):
        return f"""
            QGroupBox {{
                background: {colors['panel']};
                border: 1px solid {colors['border']};
                border-radius: 20px;
                margin-top: 12px;
                padding-top: 18px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 18px;
                padding: 0 10px;
                color: {colors['accent']};
                font-size: 10.5pt;
                font-weight: 800;
            }}
        """

    def setup_ui(self):
        colors = get_display_palette()

        self.logo_group = QGroupBox("Store")
        logo_layout = QVBoxLayout(self.logo_group)
        logo_layout.setContentsMargins(18, 16, 18, 18)
        logo_layout.setSpacing(10)

        self.parent.logo_preview = QLabel()
        self.parent.logo_preview.setFixedHeight(92)
        self.parent.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.parent.logo_preview.setText(tr("no_logo"))
        logo_layout.addWidget(self.parent.logo_preview)

        self.shop_group = QGroupBox("Shop Information")
        shop_layout = QGridLayout(self.shop_group)
        shop_layout.setVerticalSpacing(12)
        shop_layout.setHorizontalSpacing(14)
        shop_layout.setContentsMargins(18, 16, 18, 18)

        self.name_label = QLabel("Name")
        self.phone_label = QLabel("Phone")
        self.address_label = QLabel("Address")

        self.parent.shop_name_display = QLabel("ZAY POS")
        self.parent.shop_phone_display = QLabel("-")
        self.parent.shop_address_display = QLabel("-")
        self.parent.shop_address_display.setWordWrap(True)

        shop_layout.addWidget(self.name_label, 0, 0)
        shop_layout.addWidget(self.parent.shop_name_display, 0, 1)
        shop_layout.addWidget(self.phone_label, 1, 0)
        shop_layout.addWidget(self.parent.shop_phone_display, 1, 1)
        shop_layout.addWidget(self.address_label, 2, 0)
        shop_layout.addWidget(self.parent.shop_address_display, 2, 1)

        self.apply_theme_style()

    def apply_theme_style(self):
        colors = get_display_palette()
        self.logo_group.setStyleSheet(self._card_style(colors))
        self.shop_group.setStyleSheet(self._card_style(colors))

        self.parent.logo_preview.setStyleSheet(f"""
            border: 1px dashed {colors['border']};
            border-radius: 16px;
            background: {colors['panel_alt']};
            color: {colors['muted']};
            font-size: 11pt;
            font-weight: 700;
        """)

        label_style = f"""
            color: {colors['muted']};
            font-size: 10pt;
            font-weight: 800;
            background: transparent;
            border: none;
        """
        value_style = f"""
            color: {colors['text']};
            font-size: 11.5pt;
            font-weight: 650;
            background: transparent;
            border: none;
        """
        self.name_label.setStyleSheet(label_style)
        self.phone_label.setStyleSheet(label_style)
        self.address_label.setStyleSheet(label_style)
        self.parent.shop_name_display.setStyleSheet(f"""
            color: {colors['title_text']};
            font-size: 16pt;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        self.parent.shop_phone_display.setStyleSheet(value_style)
        self.parent.shop_address_display.setStyleSheet(value_style)

    def load_shop_info(self):
        """Load shop information from database."""
        try:
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM settings WHERE key='shop_name'")
            row = cursor.fetchone()
            if row:
                self.parent.shop_name_display.setText(row[0])

            cursor.execute("SELECT value FROM settings WHERE key='shop_phone'")
            row = cursor.fetchone()
            if row:
                self.parent.shop_phone_display.setText(row[0])

            cursor.execute("SELECT value FROM settings WHERE key='shop_address'")
            row = cursor.fetchone()
            if row:
                self.parent.shop_address_display.setText(row[0])

            cursor.execute("SELECT value FROM settings WHERE key='shop_logo'")
            row = cursor.fetchone()
            if row and row[0] and os.path.exists(row[0]):
                self.update_logo_preview(row[0])

            conn.close()
        except Exception:
            pass

    def update_logo_preview(self, image_path):
        """Update logo preview."""
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                colors = get_display_palette()
                scaled = pixmap.scaled(
                    220,
                    82,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.parent.logo_preview.setPixmap(scaled)
                self.parent.logo_preview.setStyleSheet(f"""
                    border: 1px solid {colors['border']};
                    border-radius: 16px;
                    background: {colors['panel_alt']};
                    padding: 6px;
                """)
            else:
                self.parent.logo_preview.setText(tr("invalid_image"))
        except Exception:
            pass
