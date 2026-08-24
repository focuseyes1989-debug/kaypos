"""Picture layout, preview, and PDF composition for KAY Printer Agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, QSizeF, Qt
from PyQt6.QtGui import QColor, QImage, QImageReader, QPageSize, QPainter, QPdfWriter, QPixmap, QTransform


PAPER_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
    "4 x 6 in": (101.6, 152.4),
    "5 x 7 in": (127.0, 177.8),
}

PAPER_API_KEYS = {
    "A4": "A4",
    "A5": "A5",
    "Letter": "LETTER",
    "4 x 6 in": "4X6",
    "5 x 7 in": "5X7",
    "Custom Size": "CUSTOM",
}

LAYOUTS = {
    "Full page photo": (1, 1),
    "Two photos": (1, 2),
    "Four photos": (2, 2),
    "Contact sheet (9)": (3, 3),
}

QUALITY_RESOLUTIONS = {"Draft": 150, "Normal": 300, "High": 600}


@dataclass
class PictureItem:
    path: str
    rotation: int = 0

    @property
    def name(self) -> str:
        return Path(self.path).name


def page_size_mm(
    paper: str, orientation: str, custom_width_mm: float = 210.0,
    custom_height_mm: float = 297.0,
) -> tuple[float, float]:
    width, height = (
        (max(20.0, float(custom_width_mm)), max(20.0, float(custom_height_mm)))
        if paper == "Custom Size" else PAPER_SIZES_MM.get(paper, PAPER_SIZES_MM["A4"])
    )
    return (height, width) if orientation.lower() == "landscape" else (width, height)


def paper_api_key(paper: str) -> str:
    return PAPER_API_KEYS.get(paper, "A4")


def layout_capacity(layout: str) -> int:
    columns, rows = LAYOUTS.get(layout, (1, 1))
    return columns * rows


def expanded_pictures(items: list[PictureItem], copies: int) -> list[PictureItem]:
    return [item for item in items for _ in range(max(1, int(copies)))]


def paginate(items: list[PictureItem], layout: str, copies: int = 1) -> list[list[PictureItem]]:
    pictures = expanded_pictures(items, copies)
    capacity = layout_capacity(layout)
    return [pictures[index:index + capacity] for index in range(0, len(pictures), capacity)]


def load_picture(item: PictureItem) -> QImage:
    reader = QImageReader(item.path)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        return image
    rotation = int(item.rotation or 0) % 360
    return image.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation) if rotation else image


def _draw_picture(painter: QPainter, image: QImage, target: QRectF, fit_to_frame: bool) -> None:
    if image.isNull() or target.isEmpty():
        return
    source = QRectF(image.rect())
    image_ratio = source.width() / max(1.0, source.height())
    target_ratio = target.width() / max(1.0, target.height())
    if fit_to_frame:
        if image_ratio > target_ratio:
            source_width = source.height() * target_ratio
            source.setLeft((source.width() - source_width) / 2.0)
            source.setWidth(source_width)
        else:
            source_height = source.width() / target_ratio
            source.setTop((source.height() - source_height) / 2.0)
            source.setHeight(source_height)
        painter.drawImage(target, image, source)
        return
    scale = min(target.width() / source.width(), target.height() / source.height())
    width, height = source.width() * scale, source.height() * scale
    contained = QRectF(
        target.x() + (target.width() - width) / 2.0,
        target.y() + (target.height() - height) / 2.0,
        width,
        height,
    )
    painter.drawImage(contained, image, source)


def render_page(
    painter: QPainter,
    page_rect: QRectF,
    pictures: list[PictureItem],
    *,
    layout: str,
    paper_mm: tuple[float, float],
    margin_mm: float = 5.0,
    fit_to_frame: bool = True,
) -> None:
    painter.fillRect(page_rect, QColor("white"))
    columns, rows = LAYOUTS.get(layout, (1, 1))
    width_mm, height_mm = paper_mm
    x_scale, y_scale = page_rect.width() / width_mm, page_rect.height() / height_mm
    margin_x, margin_y = margin_mm * x_scale, margin_mm * y_scale
    gap_x, gap_y = 3.0 * x_scale, 3.0 * y_scale
    usable_width = max(1.0, page_rect.width() - margin_x * 2 - gap_x * (columns - 1))
    usable_height = max(1.0, page_rect.height() - margin_y * 2 - gap_y * (rows - 1))
    cell_width, cell_height = usable_width / columns, usable_height / rows
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for index, item in enumerate(pictures[:columns * rows]):
        row, column = divmod(index, columns)
        target = QRectF(
            page_rect.x() + margin_x + column * (cell_width + gap_x),
            page_rect.y() + margin_y + row * (cell_height + gap_y),
            cell_width,
            cell_height,
        )
        _draw_picture(painter, load_picture(item), target, fit_to_frame)


def preview_page(
    pictures: list[PictureItem],
    *,
    paper: str,
    orientation: str,
    layout: str,
    margin_mm: float,
    fit_to_frame: bool,
    custom_width_mm: float = 210.0,
    custom_height_mm: float = 297.0,
    borderless: bool = False,
    max_size: QSize = QSize(900, 620),
) -> QPixmap:
    width_mm, height_mm = page_size_mm(paper, orientation, custom_width_mm, custom_height_mm)
    scale = min(max_size.width() / width_mm, max_size.height() / height_mm)
    width, height = max(1, round(width_mm * scale)), max(1, round(height_mm * scale))
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("white"))
    painter = QPainter(pixmap)
    render_page(
        painter, QRectF(0, 0, width, height), pictures,
        layout=layout, paper_mm=(width_mm, height_mm), margin_mm=0.0 if borderless else margin_mm,
        fit_to_frame=fit_to_frame,
    )
    painter.end()
    return pixmap


def export_picture_pdf(
    output_path: str,
    items: list[PictureItem],
    *,
    paper: str,
    orientation: str,
    layout: str,
    copies: int = 1,
    margin_mm: float = 5.0,
    fit_to_frame: bool = True,
    quality: str = "Normal",
    paper_type: str = "Automatic",
    color_mode: str = "Color",
    custom_width_mm: float = 210.0,
    custom_height_mm: float = 297.0,
    borderless: bool = False,
) -> int:
    pages = paginate(items, layout, copies)
    if not pages:
        raise ValueError("Select at least one picture")
    width_mm, height_mm = page_size_mm(paper, orientation, custom_width_mm, custom_height_mm)
    writer = QPdfWriter(output_path)
    writer.setTitle("KAY Print Pictures")
    writer.setResolution(QUALITY_RESOLUTIONS.get(quality, 300))
    writer.setPageSize(QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter, paper))
    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError("Could not create the PDF output file")
    try:
        for page_index, pictures in enumerate(pages):
            if page_index and not writer.newPage():
                raise RuntimeError("Could not create the next PDF page")
            render_page(
                painter, QRectF(0, 0, writer.width(), writer.height()), pictures,
                layout=layout, paper_mm=(width_mm, height_mm),
                margin_mm=0.0 if borderless else margin_mm,
                fit_to_frame=fit_to_frame,
            )
    finally:
        painter.end()
    return len(pages)
