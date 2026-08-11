# ui/sales_page/product_utils.py
import os
import functools
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QImageReader, QPixmap
from utils.paths import app_path, get_product_images_dir
from utils.performance import get_performance_settings
from utils.product_image_store import cached_product_image_path


def resolve_image_path(image_path: str):
    """Resolve product image paths saved in older and newer formats."""
    if not image_path:
        return ""

    raw_path = str(image_path).strip().strip('"')
    if not raw_path:
        return ""

    normalized = raw_path.replace("\\", os.sep).replace("/", os.sep)
    filename = os.path.basename(normalized)
    candidates = []

    if os.path.isabs(normalized):
        candidates.append(normalized)
        if filename:
            candidates.append(os.path.join(get_product_images_dir(), filename))
    else:
        candidates.extend([
            app_path(normalized),
            os.path.join(os.getcwd(), normalized),
        ])
        if filename:
            candidates.append(os.path.join(get_product_images_dir(), filename))
        if normalized.startswith(f"product_images{os.sep}"):
            candidates.append(app_path("database", normalized))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate

    return candidates[0] if candidates else ""


@functools.lru_cache(maxsize=100)
def load_thumbnail(image_path: str, size: int = 50, product_id=None):
    """
    Load and cache product image thumbnail.
    Supports both relative and absolute paths.
    Will try multiple path resolutions if the image is not found.
    """
    if not image_path and not product_id:
        return None

    performance = get_performance_settings()
    if performance.thumbnail_quality == "low":
        size = max(24, min(size, int(size * 0.75)))

    resolved_path = resolve_image_path(image_path)

    if not resolved_path or not os.path.exists(resolved_path):
        resolved_path = cached_product_image_path(product_id, image_path)
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
