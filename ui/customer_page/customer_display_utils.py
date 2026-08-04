# ui/customer_page/customer_display_utils.py
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from .customer_display_theme import get_display_palette
from utils.translations import tr


def load_qr_info(qr_preview, qr_name_label, qr_group):
    """Load QR Code information from database"""
    try:
        from models.database import connect_db
        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key='shop_qr_code'")
        row = cursor.fetchone()
        if row and row[0] and os.path.exists(row[0]):
            update_qr_preview(qr_preview, row[0])
            qr_group.setVisible(True)
        else:
            qr_preview.setText(f"📱 {tr('no_qr_code')}")
            qr_group.setVisible(False)

        cursor.execute("SELECT value FROM settings WHERE key='shop_qr_name'")
        row = cursor.fetchone()
        if row and row[0]:
            qr_name_label.setText(row[0])
            qr_group.setVisible(True)
        else:
            qr_name_label.setText("")
            qr_group.setVisible(False)

        conn.close()
    except Exception:
        pass


def update_qr_preview(qr_preview, image_path):
    """Update QR code preview - BIGGER size"""
    try:
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            colors = get_display_palette()
            scaled = pixmap.scaled(220, 110, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            qr_preview.setPixmap(scaled)
            qr_preview.setStyleSheet(f"""
                border: 2px solid {colors['selection']};
                border-radius: 6px;
                background: {colors['title_bar']};
                padding: 4px;
            """)
        else:
            qr_preview.setText(f"❌ {tr('invalid_image')}")
    except:
        pass


def set_default_geometry(window):
    screen = QApplication.primaryScreen()
    if screen:
        geometry = screen.availableGeometry()
        width = int(geometry.width() * 0.65)
        height = int(geometry.height() * 0.65)
        x = (geometry.width() - width) // 2
        y = (geometry.height() - height) // 2
        window.setGeometry(x, y, width, height)


def move_to_secondary_monitor(window):
    app = QApplication.instance()
    screens = app.screens()

    if len(screens) > 1 and not window.is_maximized:
        screen = screens[1]
        geometry = screen.geometry()
        width = int(geometry.width() * 0.65)
        height = int(geometry.height() * 0.65)
        x = geometry.x() + (geometry.width() - width) // 2
        y = geometry.y() + (geometry.height() - height) // 2
        window.setGeometry(x, y, width, height)


def show_on_customer_monitor_fullscreen(window):
    app = QApplication.instance()
    if not app:
        window.showFullScreen()
        return

    screens = app.screens()
    target_screen = screens[1] if len(screens) > 1 else app.primaryScreen()
    if not target_screen:
        window.showFullScreen()
        return

    window.windowHandle().setScreen(target_screen) if window.windowHandle() else None
    window.setGeometry(target_screen.geometry())
    window.is_maximized = True
    window.showFullScreen()
