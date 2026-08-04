# ui/sales_page/product_utils.py
import os
import functools
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QImageReader, QPixmap
from utils.paths import app_path
from utils.performance import get_performance_settings


def resolve_image_path(image_path: str):
    """Resolve image path to absolute path using app_path for relative paths."""
    if not image_path:
        return ""
    if os.path.isabs(image_path):
        return image_path
    return app_path(image_path)


@functools.lru_cache(maxsize=100)
def load_thumbnail(image_path: str, size: int = 50):
    """
    Load and cache product image thumbnail.
    Supports both relative and absolute paths.
    Will try multiple path resolutions if the image is not found.
    """
    if not image_path:
        return None

    performance = get_performance_settings()
    if performance.thumbnail_quality == "low":
        size = max(24, min(size, int(size * 0.75)))

    resolved_path = resolve_image_path(image_path)

    if not resolved_path or not os.path.exists(resolved_path):
        if not os.path.isabs(image_path):
            alt_path = os.path.join(os.getcwd(), image_path)
            if os.path.exists(alt_path):
                resolved_path = alt_path
            else:
                filename = os.path.basename(image_path)
                db_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                alt_path2 = os.path.join(db_dir, 'database', 'product_images', filename)
                if os.path.exists(alt_path2):
                    resolved_path = alt_path2
                else:
                    alt_path3 = app_path(os.path.join('database', 'product_images', filename))
                    if os.path.exists(alt_path3):
                        resolved_path = alt_path3

    if not resolved_path or not os.path.exists(resolved_path):
        return None

    reader = QImageReader(resolved_path)
    reader.setScaledSize(QSize(size, size))
    image = reader.read()
    if not image.isNull():
        return QPixmap.fromImage(image)
    return None


def clear_layout_widgets(layout):
    """Remove child widgets without detaching them as temporary top-level windows."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.hide()
            widget.deleteLater()
