# ui/print_barcode_dialog.py
from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QFont, QFontMetrics, QImage, QPainter, QPageLayout, QPageSize, QPixmap, QColor, QIcon
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QFrame,
    QWidget,
    QGridLayout
)

from utils.translations import tr
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme, get_icon_path
import os


# ============================================================
# ✅ SVG ICON HELPER
# ============================================================

def load_svg_icon(icon_name, size=(20, 20), color_hex=None):
    """
    Load SVG icon from assets/icons folder with optional color.
    
    Args:
        icon_name: Name of the SVG file (without extension)
        size: Tuple of (width, height)
        color_hex: Hex color code for the icon (optional)
    
    Returns:
        QPixmap or None
    """
    try:
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QByteArray
        import re
        
        # Get icon path using theme_manager
        icon_path = get_icon_path(icon_name)
        
        if icon_path and os.path.exists(icon_path):
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # If color is provided, replace fill colors
            if color_hex:
                svg_content = re.sub(r'fill="[^"]*"', '', svg_content)
                svg_content = re.sub(r'fill:\s*[^;"]+', '', svg_content)
                svg_content = svg_content.replace('<svg', f'<svg fill="{color_hex}"', 1)
            
            byte_array = QByteArray(svg_content.encode('utf-8'))
            renderer = QSvgRenderer(byte_array)
            
            if renderer.isValid():
                pixmap = QPixmap(size[0], size[1])
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap
    except Exception as e:
        pass
    
    # Fallback: Try PNG
    png_path = f"assets/icons/{icon_name}.png"
    if os.path.exists(png_path):
        try:
            pixmap = QPixmap(png_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    size[0], size[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                return scaled
        except Exception as e:
            pass
    
    return None


def get_icon_color(is_dark):
    """Get icon color based on theme"""
    return "#b9bbbe" if is_dark else "#6c757d"


# ============================================================
# ✅ ICON LABEL CLASS
# ============================================================

class IconLabel(QLabel):
    """Label with SVG icon support"""
    
    def __init__(self, icon_name, size=(18, 18), text="", parent=None):
        super().__init__(text, parent)
        self._icon_name = icon_name
        self._icon_size = size
        self._is_dark = is_dark_theme()
        self._load_icon()
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        self._is_dark = is_dark_theme()
        self._load_icon()
    
    def _load_icon(self):
        color = get_icon_color(self._is_dark)
        pixmap = load_svg_icon(self._icon_name, self._icon_size, color)
        if pixmap:
            self.setPixmap(pixmap)
            self.setText("")
            self.setStyleSheet("background: transparent; border: none; padding: 0px; margin: 0px;")
        else:
            # Fallback to emoji
            emoji_map = {
                "barcode": "🏷️",
                "print": "🖨️",
                "aspect_ratio": "📐",
                "counter": "🔢",
                "high_quality": "🔍",
                "preview": "🖼️",
                "file_png": "💾",
                "save": "💾",
                "close": "✖",
                "settings": "⚙️",
                "refresh": "🔄",
                "receipt_long": "📋",
                "package": "📦",
            }
            self.setText(emoji_map.get(self._icon_name, "📌"))
            self.setPixmap(QPixmap())
            self.setStyleSheet(f"""
                font-size: 14px;
                color: {color};
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            """)


CODE128_PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232", "2331112",
]


class PrintBarcodeDialog(QDialog):
    """Print Code128 product labels - Modern Theme-aware Design with SVG Icons and ModernButton"""

    PRESETS = [
        ("40 x 30 mm", 40.0, 30.0),
        ("50 x 30 mm", 50.0, 30.0),
        ("58 x 40 mm", 58.0, 40.0),
        ("70 x 50 mm", 70.0, 50.0),
        ("Custom", 0.0, 0.0),
    ]

    def __init__(self, product_id, product_name, barcode_number, parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.product_name = str(product_name or "")
        self.barcode_number = str(barcode_number or "").strip()
        self._is_dark = is_dark_theme()

        self.setWindowTitle(tr("print_barcode_title") + f" - {self.product_name}")
        self.setMinimumSize(600, 650)
        self.setModal(True)

        # ✅ Connect theme change signal
        theme_manager.theme_changed.connect(self._on_theme_changed)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ============================================================
        # HEADER - Simple title without background
        # ============================================================
        header_frame = QFrame()
        header_frame.setObjectName("header_frame")
        header_frame.setStyleSheet(self._get_header_style())
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 4, 0, 4)
        
        # ✅ Title with SVG icon
        title_icon = IconLabel("barcode", size=(20, 20))
        header_layout.addWidget(title_icon)
        
        title_label = QLabel("Print Barcode")
        title_label.setStyleSheet(self._get_title_style())
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Product ID badge
        badge = QLabel(f"ID: #{self.product_id}")
        badge.setStyleSheet(self._get_badge_style())
        header_layout.addWidget(badge)
        
        main_layout.addWidget(header_frame)

        # ============================================================
        # PRODUCT INFO - Modern card style
        # ============================================================
        info_frame = QFrame()
        info_frame.setObjectName("info_frame")
        info_frame.setStyleSheet(self._get_info_frame_style())
        
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(20)
        
        # ✅ Product icon
        product_icon = IconLabel("package", size=(16, 16))
        info_layout.addWidget(product_icon)
        
        product_label = QLabel(self.product_name)
        product_label.setStyleSheet(self._get_info_label_style())
        info_layout.addWidget(product_label)
        
        info_layout.addStretch()
        
        # ✅ Barcode icon
        barcode_icon = IconLabel("barcode", size=(16, 16))
        info_layout.addWidget(barcode_icon)
        
        barcode_label = QLabel(self.barcode_number)
        barcode_label.setStyleSheet(self._get_info_label_style())
        info_layout.addWidget(barcode_label)
        
        main_layout.addWidget(info_frame)

        # ============================================================
        # FORM - Two column layout like Product Form
        # ============================================================
        form_widget = QWidget()
        form_widget.setObjectName("form_widget")
        form_widget.setStyleSheet(self._get_form_widget_style())
        
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(15, 15, 15, 15)
        form_layout.setSpacing(8)

        # Grid layout for form fields
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setHorizontalSpacing(15)
        grid.setContentsMargins(0, 0, 0, 0)

        row = 0

        # Printer
        label_printer = self._create_label_with_icon("print", "Printer:")
        self.printer_combo = QComboBox()
        self._load_printers()
        self.printer_combo.setStyleSheet(self._get_combobox_style())
        grid.addWidget(label_printer, row, 0)
        grid.addWidget(self.printer_combo, row, 1)
        row += 1

        # Label Size
        label_size = self._create_label_with_icon("aspect_ratio", "Label Size:")
        self.preset_combo = QComboBox()
        for label, _width, _height in self.PRESETS:
            self.preset_combo.addItem(label)
        self.preset_combo.setCurrentIndex(1)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.preset_combo.setStyleSheet(self._get_combobox_style())
        grid.addWidget(label_size, row, 0)
        grid.addWidget(self.preset_combo, row, 1)
        row += 1

        # Dimensions
        label_dim = self._create_label_with_icon("aspect_ratio", "Dimensions:")
        dim_widget = QWidget()
        dim_layout = QHBoxLayout(dim_widget)
        dim_layout.setContentsMargins(0, 0, 0, 0)
        dim_layout.setSpacing(6)

        dim_layout.addWidget(QLabel("W:"))
        self.width_spin = self._make_mm_spin(20.0, 120.0, 50.0)
        self.width_spin.valueChanged.connect(self._mark_custom_size)
        self.width_spin.valueChanged.connect(self.update_preview)
        self.width_spin.setStyleSheet(self._get_spinbox_style())
        dim_layout.addWidget(self.width_spin)

        dim_layout.addWidget(QLabel("H:"))
        self.height_spin = self._make_mm_spin(15.0, 80.0, 30.0)
        self.height_spin.valueChanged.connect(self._mark_custom_size)
        self.height_spin.valueChanged.connect(self.update_preview)
        self.height_spin.setStyleSheet(self._get_spinbox_style())
        dim_layout.addWidget(self.height_spin)

        grid.addWidget(label_dim, row, 0)
        grid.addWidget(dim_widget, row, 1)
        row += 1

        # Margin
        label_margin = self._create_label_with_icon("aspect_ratio", "Margin:")
        self.margin_spin = self._make_mm_spin(0.0, 8.0, 2.0)
        self.margin_spin.valueChanged.connect(self.update_preview)
        self.margin_spin.setStyleSheet(self._get_spinbox_style())
        grid.addWidget(label_margin, row, 0)
        grid.addWidget(self.margin_spin, row, 1)
        row += 1

        # Print Quality
        label_quality = self._create_label_with_icon("high_quality", "Print Quality:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("203 dpi (Standard)", 203)
        self.quality_combo.addItem("300 dpi (High)", 300)
        self.quality_combo.addItem("600 dpi (Best)", 600)
        self.quality_combo.currentIndexChanged.connect(self.update_preview)
        self.quality_combo.setStyleSheet(self._get_combobox_style())
        grid.addWidget(label_quality, row, 0)
        grid.addWidget(self.quality_combo, row, 1)
        row += 1

        # Quantity
        label_qty = self._create_label_with_icon("counter", "Quantity:")
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 500)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(self._get_spinbox_style())
        grid.addWidget(label_qty, row, 0)
        grid.addWidget(self.qty_spin, row, 1)
        row += 1

        # Checkboxes in a row
        check_layout = QHBoxLayout()
        check_layout.setSpacing(15)

        self.show_name_check = QCheckBox("Print product name")
        self.show_name_check.setChecked(True)
        self.show_name_check.toggled.connect(self.update_preview)
        self.show_name_check.setStyleSheet(self._get_checkbox_style())

        self.show_number_check = QCheckBox("Print barcode number")
        self.show_number_check.setChecked(True)
        self.show_number_check.toggled.connect(self.update_preview)
        self.show_number_check.setStyleSheet(self._get_checkbox_style())

        check_layout.addWidget(self.show_name_check)
        check_layout.addWidget(self.show_number_check)
        check_layout.addStretch()

        grid.addWidget(QLabel(""), row, 0)
        grid.addLayout(check_layout, row, 1)
        row += 1

        form_layout.addLayout(grid)
        main_layout.addWidget(form_widget)

        # ============================================================
        # PREVIEW
        # ============================================================
        preview_frame = QFrame()
        preview_frame.setObjectName("preview_frame")
        preview_frame.setStyleSheet(self._get_preview_frame_style())

        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(10, 8, 10, 8)
        preview_layout.setSpacing(4)

        # ✅ Preview title with SVG icon
        preview_title_layout = QHBoxLayout()
        preview_icon = IconLabel("preview", size=(16, 16))
        preview_title_layout.addWidget(preview_icon)
        
        preview_title = QLabel("Barcode Preview")
        preview_title.setObjectName("preview_title")
        preview_title.setStyleSheet(self._get_preview_title_style())
        preview_title_layout.addWidget(preview_title)
        preview_title_layout.addStretch()
        
        preview_layout.addLayout(preview_title_layout)

        self.preview_label = QLabel()
        self.preview_label.setMinimumHeight(160)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(self._get_preview_label_style())
        preview_layout.addWidget(self.preview_label, 1)

        main_layout.addWidget(preview_frame, 1)

        # ============================================================
        # HINT - Modern info style
        # ============================================================
        hint = QLabel(
            "Bluetooth label printer ကို Windows Settings > Bluetooth & devices > Printers ထဲမှာ "
            "printer အဖြစ် pair/add လုပ်ထားရပါမယ်။"
        )
        hint.setObjectName("hint_label")
        hint.setWordWrap(True)
        hint.setStyleSheet(self._get_hint_style())
        main_layout.addWidget(hint)

        # ============================================================
        # BUTTONS - ModernButton with SVG icons
        # ============================================================
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style())

        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(12, 8, 12, 8)
        button_layout.setSpacing(8)

        # ✅ Preview button - ModernButton SECONDARY with preview icon
        self.btn_preview = ModernButton("Preview", ModernButton.SECONDARY)
        self.btn_preview.set_compact(True)
        self.btn_preview.set_icon("preview", size=(16, 16))
        self.btn_preview.clicked.connect(self.update_preview)
        button_layout.addWidget(self.btn_preview)

        # ✅ Save PNG button - ModernButton SECONDARY with file_png icon
        self.btn_save_png = ModernButton("Save PNG", ModernButton.SECONDARY)
        self.btn_save_png.set_compact(True)
        self.btn_save_png.set_icon("file_png", size=(16, 16))
        self.btn_save_png.clicked.connect(self.save_png)
        button_layout.addWidget(self.btn_save_png)

        button_layout.addStretch()

        # ✅ Print button - ModernButton PRIMARY with print icon
        self.btn_print = ModernButton("Print", ModernButton.PRIMARY)
        self.btn_print.set_compact(True)
        self.btn_print.set_icon("print", size=(16, 16))
        self.btn_print.clicked.connect(self.print_barcode)
        button_layout.addWidget(self.btn_print)

        # ✅ Close button - ModernButton TERTIARY with close icon
        self.btn_close = ModernButton("Close", ModernButton.TERTIARY)
        self.btn_close.set_compact(True)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_close)

        main_layout.addWidget(button_frame)

        self._updating_preset = False
        self._apply_preset()
        self.update_preview()

        # Apply initial theme
        self._apply_theme()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self.update_preview()
        
        # ✅ Update ModernButton icons
        for btn in [self.btn_preview, self.btn_save_png, self.btn_print, self.btn_close]:
            if btn and hasattr(btn, '_on_theme_changed'):
                btn._on_theme_changed(theme_name)

    def _apply_theme(self):
        """Apply current theme to all widgets"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update frames
        for child in self.findChildren(QFrame):
            if child.objectName() == "info_frame":
                child.setStyleSheet(self._get_info_frame_style())
            elif child.objectName() == "form_widget":
                child.setStyleSheet(self._get_form_widget_style())
            elif child.objectName() == "preview_frame":
                child.setStyleSheet(self._get_preview_frame_style())
            elif child.objectName() == "button_frame":
                child.setStyleSheet(self._get_button_frame_style())
        
        # Update labels
        for child in self.findChildren(QLabel):
            if child.objectName() == "preview_title":
                child.setStyleSheet(self._get_preview_title_style())
            elif child.objectName() == "hint_label":
                child.setStyleSheet(self._get_hint_style())
        
        # Update preview label
        self.preview_label.setStyleSheet(self._get_preview_label_style())

    def _make_mm_spin(self, minimum, maximum, value):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(" mm")
        spin.setValue(value)
        return spin

    def _load_printers(self):
        printers = QPrinterInfo.availablePrinters()
        default_printer = QPrinterInfo.defaultPrinter()
        default_name = default_printer.printerName() if not default_printer.isNull() else ""

        for info in printers:
            name = info.printerName()
            self.printer_combo.addItem(name, name)
            if name == default_name:
                self.printer_combo.setCurrentIndex(self.printer_combo.count() - 1)

        if not printers:
            self.printer_combo.addItem("No printer found", "")
            self.printer_combo.setEnabled(False)

    def _apply_preset(self):
        index = self.preset_combo.currentIndex()
        if index < 0:
            return
        _label, width, height = self.PRESETS[index]
        if width <= 0 or height <= 0:
            return

        self._updating_preset = True
        try:
            self.width_spin.setValue(width)
            self.height_spin.setValue(height)
        finally:
            self._updating_preset = False
        self.update_preview()

    def _mark_custom_size(self):
        if self._updating_preset:
            return
        custom_index = self.preset_combo.count() - 1
        if self.preset_combo.currentIndex() != custom_index:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(custom_index)
            self.preset_combo.blockSignals(False)

    def _code128_values(self, text):
        if not text:
            raise ValueError("Barcode is empty.")

        values = [104]  # Start Code B
        for ch in text:
            code = ord(ch)
            if code < 32 or code > 126:
                raise ValueError("Code128 supports printable ASCII barcode values only.")
            values.append(code - 32)

        checksum = values[0]
        for index, value in enumerate(values[1:], start=1):
            checksum += value * index
        values.append(checksum % 103)
        values.append(106)  # Stop
        return values

    def _barcode_module_count(self, values):
        return sum(sum(int(part) for part in CODE128_PATTERNS[value]) for value in values)

    def _draw_code128(self, painter, text, rect):
        values = self._code128_values(text)
        total_modules = self._barcode_module_count(values)
        module_width = rect.width() / total_modules
        x = rect.left()

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)

        for value in values:
            pattern = CODE128_PATTERNS[value]
            draw_bar = True
            for width_char in pattern:
                width = int(width_char) * module_width
                if draw_bar:
                    painter.drawRect(QRectF(x, rect.top(), width, rect.height()))
                x += width
                draw_bar = not draw_bar
        painter.restore()

    def _paint_label(self, painter, target_rect):
        painter.fillRect(target_rect, Qt.GlobalColor.white)

        label_width = self.width_spin.value()
        label_height = self.height_spin.value()
        margin_px = min(
            target_rect.width() * 0.25,
            max(0.0, self.margin_spin.value() * (target_rect.width() / label_width)),
        )
        content = target_rect.adjusted(margin_px, margin_px, -margin_px, -margin_px)

        y = content.top()
        if self.show_name_check.isChecked():
            name_font = self._make_label_font()
            name_font.setPixelSize(max(10, int(target_rect.height() * 0.11)))
            name_font.setBold(True)
            painter.setFont(name_font)
            metrics = QFontMetrics(name_font)
            name_height = metrics.height() + 2
            product_name = metrics.elidedText(self.product_name, Qt.TextElideMode.ElideRight, int(content.width()))
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(
                QRectF(content.left(), y, content.width(), name_height),
                Qt.AlignmentFlag.AlignCenter,
                product_name,
            )
            y += name_height + max(2, target_rect.height() * 0.025)

        number_height = 0
        if self.show_number_check.isChecked():
            number_font = self._make_label_font()
            number_font.setPixelSize(max(9, int(target_rect.height() * 0.10)))
            number_height = QFontMetrics(number_font).height() + 2
        else:
            number_font = None

        bottom_reserved = number_height + max(2, target_rect.height() * 0.02) if number_height else 0
        barcode_rect = QRectF(
            content.left(),
            y,
            content.width(),
            max(8.0, content.bottom() - y - bottom_reserved),
        )
        self._draw_code128(painter, self.barcode_number, barcode_rect)

        if number_height and number_font:
            painter.setFont(number_font)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(
                QRectF(content.left(), barcode_rect.bottom() + 2, content.width(), number_height),
                Qt.AlignmentFlag.AlignCenter,
                self.barcode_number,
            )

    def _make_label_font(self):
        font = QFont("Myanmar Text")
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font

    def selected_dpi(self):
        return int(self.quality_combo.currentData() or 203)

    def render_label_pixmap(self, dpi=None):
        if dpi is None:
            dpi = self.selected_dpi()
        width_px = max(160, int(self.width_spin.value() * dpi / 25.4))
        height_px = max(100, int(self.height_spin.value() * dpi / 25.4))
        image = QImage(width_px, height_px, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        try:
            self._paint_label(painter, QRectF(0, 0, width_px, height_px))
        finally:
            painter.end()
        return QPixmap.fromImage(image)

    def update_preview(self):
        try:
            pixmap = self.render_label_pixmap()
        except Exception as exc:
            self.preview_label.setText(f"{tr('barcode_generate_error')}: {exc}")
            return

        preview_width = self.preview_label.width() - 20
        if preview_width < 40:
            preview_width = 440
        
        self.preview_label.setPixmap(
            pixmap.scaled(
                preview_width,
                160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def _configure_printer(self, printer):
        label_width = self.width_spin.value()
        label_height = self.height_spin.value()
        page_size = QPageSize(
            QSizeF(label_width, label_height),
            QPageSize.Unit.Millimeter,
            f"{label_width:g}x{label_height:g}mm Label",
        )
        page_layout = QPageLayout(
            page_size,
            QPageLayout.Orientation.Portrait,
            QMarginsF(0, 0, 0, 0),
            QPageLayout.Unit.Millimeter,
        )
        accepted = printer.setPageLayout(page_layout)
        printer.setFullPage(True)
        printer.setResolution(self.selected_dpi())
        return accepted

    def _target_rect_for_printer(self, printer, page_rect):
        px_per_mm = printer.resolution() / 25.4
        desired_width = self.width_spin.value() * px_per_mm
        desired_height = self.height_spin.value() * px_per_mm
        return QRectF(
            0,
            0,
            min(page_rect.width(), desired_width),
            min(page_rect.height(), desired_height),
        )

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Barcode Label",
            f"{self.barcode_number}.png",
            "PNG Images (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"

        pixmap = self.render_label_pixmap(dpi=self.selected_dpi())
        if pixmap.save(path, "PNG"):
            QMessageBox.information(self, "Save PNG", f"Saved:\n{path}")
        else:
            QMessageBox.warning(self, "Save PNG", "Could not save barcode label PNG.")

    def print_barcode(self):
        printer_name = self.printer_combo.currentData()
        if not printer_name:
            QMessageBox.warning(self, tr("print"), "No printer found. Please add/pair a printer in Windows first.")
            return

        quantity = self.qty_spin.value()
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(printer_name)
        page_size_accepted = self._configure_printer(printer)

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(
                self,
                tr("print"),
                f"{tr('printer_start_error')}\n\nPrinter: {printer_name}",
            )
            return

        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            if page_rect.width() <= 0 or page_rect.height() <= 0:
                raise RuntimeError("Printer returned an invalid label page size.")

            target_rect = self._target_rect_for_printer(printer, page_rect)
            for index in range(quantity):
                if index > 0:
                    printer.newPage()
                self._paint_label(painter, target_rect)
        except Exception as exc:
            painter.end()
            QMessageBox.critical(self, tr("print"), f"{tr('barcode_generate_error')}: {exc}")
            return

        painter.end()
        note = ""
        if not page_size_accepted:
            note = (
                "\n\nNote: Printer driver did not accept the custom label page size. "
                "If the printer feeds too much paper, set the same label size in Windows printer preferences."
            )
        QMessageBox.information(
            self,
            tr("print"),
            f"{tr('barcode_print_success').format(quantity)}\nPrinter: {printer_name}{note}",
        )

    # ============================================================
    # STYLE METHODS - Theme-aware
    # ============================================================

    def _get_header_style(self):
        """Header background - none, transparent"""
        return """
            QFrame#header_frame {
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """

    def _get_title_style(self):
        colors = get_theme_colors()
        return f"""
            QLabel {{
                color: {colors['text']};
                font-size: 14pt;
                font-weight: 600;
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """

    def _get_badge_style(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            return f"""
                QLabel {{
                    background: {colors['bg_hover']};
                    color: {colors['text']};
                    padding: 2px 12px;
                    border-radius: 10px;
                    font-size: 9pt;
                    font-weight: 500;
                    border: 1px solid {colors['border']};
                }}
            """
        else:
            return """
                QLabel {
                    background: #e9ecef;
                    color: #495057;
                    padding: 2px 12px;
                    border-radius: 10px;
                    font-size: 9pt;
                    font-weight: 500;
                    border: none;
                }
            """

    def _get_info_frame_style(self):
        colors = get_theme_colors()
        return f"""
            QFrame#info_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """

    def _get_info_label_style(self):
        colors = get_theme_colors()
        return f"""
            QLabel {{
                color: {colors['text']};
                font-size: 10pt;
                font-weight: 500;
                background: transparent;
                border: none;
                padding: 4px 0px;
            }}
        """

    def _get_form_widget_style(self):
        colors = get_theme_colors()
        return f"""
            QWidget#form_widget {{
                background: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
        """

    def _get_preview_frame_style(self):
        colors = get_theme_colors()
        return f"""
            QFrame#preview_frame {{
                background: {colors['bg_hover']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
        """

    def _get_preview_title_style(self):
        colors = get_theme_colors()
        return f"""
            QLabel#preview_title {{
                font-weight: 600;
                font-size: 10pt;
                color: {colors['text']};
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """

    def _get_preview_label_style(self):
        colors = get_theme_colors()
        border_color = colors['border']
        bg_color = colors['bg_hover']
        text_color = colors['text_secondary']
        
        return f"""
            QLabel {{
                background: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 10px;
                padding: 10px;
                font-size: 10pt;
                color: {text_color};
            }}
        """

    def _get_button_frame_style(self):
        colors = get_theme_colors()
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 3px;
            }}
        """

    def _get_hint_style(self):
        colors = get_theme_colors()
        return f"""
            QLabel#hint_label {{
                color: {colors['text_secondary']};
                font-size: 9pt;
                background: transparent;
                border: none;
                padding: 2px 0px;
            }}
        """

    def _create_label(self, text):
        colors = get_theme_colors()
        label = QLabel(text)
        label.setStyleSheet(f"font-weight: 600; color: {colors['text']}; font-size: 9pt;")
        return label

    def _create_label_with_icon(self, icon_name, text):
        """Create a label with SVG icon and text"""
        colors = get_theme_colors()
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        icon = IconLabel(icon_name, size=(14, 14))
        layout.addWidget(icon)
        
        label = QLabel(text)
        label.setStyleSheet(f"""
            font-weight: 600;
            color: {colors['text']};
            font-size: 9pt;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        layout.addWidget(label)
        layout.addStretch()
        
        return container

    def _get_combobox_style(self):
        colors = get_theme_colors()
        return f"""
            QComboBox {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 28px;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 8px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """

    def _get_spinbox_style(self):
        colors = get_theme_colors()
        return f"""
            QDoubleSpinBox, QSpinBox {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 28px;
                min-width: 80px;
            }}
            QDoubleSpinBox:focus, QSpinBox:focus {{
                border-color: #5865f2;
            }}
            QDoubleSpinBox::up-button, QSpinBox::up-button,
            QDoubleSpinBox::down-button, QSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 16px;
            }}
            QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 2px;
            }}
        """

    def _get_checkbox_style(self):
        colors = get_theme_colors()
        return f"""
            QCheckBox {{
                color: {colors['text']};
                font-size: 9pt;
                spacing: 6px;
                background: transparent;
                border: none;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: #5865f2;
                border: 1px solid #5865f2;
                border-radius: 3px;
            }}
        """