"""Render database records onto the four legacy A4 border-pass templates."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QFontDatabase, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen


A4_WIDTH_POINTS = 595.2756
A4_HEIGHT_POINTS = 841.8898
PAGE_NUMBERS = (1, 2, 3, 4)
_FORM_FONT_FAMILY = None
WINDOWS_MYANMAR_FONT_FAMILIES = ("Myanmar Text",)
DEFAULT_FORM_FONT_POINTS = 13

# Coordinates migrated from the proven legacy client. Values are A4 PDF points
# with the origin at the bottom-left, matching the original ReportLab output.
PAGE_COORDINATES = {
    1: {
        "car_number": (300, 473), "nrc_and_number": (300, 398),
        "phone_number": (300, 362), "driver_name_and_age": (300, 435),
        "kind_and_type_of_car": (300, 513), "address": (300, 324),
    },
    2: {
        "car_number": (330, 579), "driver_name_and_age": (330, 552),
        "kind_of_car": (330, 607), "type_of_car": (330, 635),
        "nrc_number": (60, 720), "engine_number": (330, 523),
        "frame_number": (330, 494),
    },
    3: {
        "car_number": (390, 741), "driver_name_and_age": (200, 710),
        "kind_and_type_of_car": (140, 741),
    },
    4: {
        "car_number": (390, 742), "driver_name_and_age": (180, 702),
        "kind_and_type_of_car": (120, 742), "driver_name_2": (80, 400),
        "age_2": (210, 400),
    },
}


def _joined(*values, separator=" ") -> str:
    return separator.join(str(value).strip() for value in values if str(value or "").strip())


def compose_form_fields(record: dict) -> dict[str, str]:
    driver = str(record.get("driver_name") or "").strip()
    age = str(record.get("age") or "").strip()
    return {
        "car_number": str(record.get("car_number") or "").strip(),
        "driver_name_and_age": _joined(driver, f"({age})" if age else ""),
        "driver_name_2": driver,
        "age_2": age,
        "kind_of_car": str(record.get("kind_of_car") or "").strip(),
        "type_of_car": str(record.get("type_of_car") or "").strip(),
        "kind_and_type_of_car": _joined(record.get("kind_of_car"), record.get("type_of_car")),
        "nrc_number": str(record.get("nrc_number") or "").strip(),
        "nrc_and_number": _joined(record.get("nrc_place"), record.get("nrc_number")),
        "phone_number": str(record.get("phone_number") or "").strip(),
        "address": str(record.get("address") or "").strip(),
        "engine_number": str(record.get("engine_number") or "").strip(),
        "frame_number": str(record.get("frame_number") or "").strip(),
    }


def templates_directory() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    root = Path(frozen_root) if frozen_root else Path(__file__).resolve().parents[1]
    return root / "assets" / "car_images"


def form_font_family() -> str:
    global _FORM_FONT_FAMILY
    if _FORM_FONT_FAMILY:
        return _FORM_FONT_FAMILY

    # Myanmar Text is included with Windows 10/11. Prefer the native Windows
    # face so completed forms match other Myanmar text on the user's PC.
    installed_families = {family.casefold(): family for family in QFontDatabase.families()}
    for preferred_family in WINDOWS_MYANMAR_FONT_FAMILIES:
        installed_name = installed_families.get(preferred_family.casefold())
        if installed_name:
            _FORM_FONT_FAMILY = installed_name
            return _FORM_FONT_FAMILY

    # Packaged builds and stripped-down environments may not expose Windows
    # system fonts, so keep the bundled font as a reliable Myanmar fallback.
    root = templates_directory().parent
    font_path = root / "fonts" / "NotoSansMyanmar-Regular.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path)) if font_path.is_file() else -1
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    _FORM_FONT_FAMILY = families[0] if families else "Arial"
    return _FORM_FONT_FAMILY


def template_path(page_number: int) -> Path:
    page_number = int(page_number)
    if page_number not in PAGE_NUMBERS:
        raise ValueError(f"Unknown form page: {page_number}")
    path = templates_directory() / f"{page_number}.jpg"
    if not path.is_file():
        raise FileNotFoundError(f"Form template was not found: {path}")
    return path


def render_form_page(
    record: dict,
    page_number: int,
    font_family=None,
    font_points=DEFAULT_FORM_FONT_POINTS,
) -> QImage:
    image = QImage(str(template_path(page_number)))
    if image.isNull():
        raise RuntimeError(f"Could not load form template page {page_number}.")
    fields = compose_form_fields(record)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(QPen(Qt.GlobalColor.black))
        font = QFont(font_family or form_font_family())
        font.setWeight(QFont.Weight.Bold)
        font.setPixelSize(max(12, round(float(font_points) * image.width() / A4_WIDTH_POINTS)))
        painter.setFont(font)
        for field, (x_points, y_points) in PAGE_COORDINATES[int(page_number)].items():
            text = fields.get(field, "")
            if not text:
                continue
            x = float(x_points) * image.width() / A4_WIDTH_POINTS
            y = image.height() - float(y_points) * image.height() / A4_HEIGHT_POINTS
            if int(page_number) == 4 and field == "driver_name_2":
                # Keep long driver names inside the name column. The next
                # column (Age) begins at x=210 A4 points.
                right_margin_points = 4
                width_points = PAGE_COORDINATES[4]["age_2"][0] - x_points - right_margin_points
                width = float(width_points) * image.width() / A4_WIDTH_POINTS
                metrics = painter.fontMetrics()
                text_rect = QRectF(x, y - metrics.ascent(), width, metrics.lineSpacing() * 3)
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    text,
                )
            else:
                painter.drawText(QPointF(x, y), text)
    finally:
        painter.end()
    return image


def export_filled_pdf(record: dict, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    writer = QPdfWriter(str(output_path))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError(f"Could not create PDF: {output_path}")
    try:
        for index, page_number in enumerate(PAGE_NUMBERS):
            if index and not writer.newPage():
                raise RuntimeError("Could not create the next PDF page.")
            image = render_form_page(record, page_number)
            painter.drawImage(QRectF(painter.viewport()), image)
    finally:
        painter.end()
    return output_path


def save_filled_page(record: dict, page_number: int, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    if not render_form_page(record, page_number).save(str(output_path)):
        raise RuntimeError(f"Could not save filled form image: {output_path}")
    return output_path
