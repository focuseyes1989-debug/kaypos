"""Code128 B label document rendered through standard Qt print widgets.

Patterns and encoding match the original KAY barcode dialog; UI stays native.
"""
from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QFont, QFontMetrics, QPageSize, QPainter
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewWidget
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox, QLabel, QPushButton

PATTERNS = [
    '212222','222122','222221','121223','121322','131222','122213','122312','132212','221213','221312','231212',
    '112232','122132','122231','113222','123122','123221','223211','221132','221231','213212','223112','312131',
    '311222','321122','321221','312212','322112','322211','212123','212321','232121','111323','131123','131321',
    '112313','132113','132311','211313','231113','231311','112133','112331','132131','113123','113321','133121',
    '313121','211331','231131','213113','213311','213131','311123','311321','331121','312113','312311','332111',
    '314111','221411','431111','111224','111422','121124','121421','141122','141221','112214','112412','122114',
    '122411','142112','142211','241211','221114','413111','241112','134111','111242','121142','121241','114212',
    '124112','124211','411212','421112','421211','212141','214121','412121','111143','111341','131141','114113',
    '114311','411113','411311','113141','114131','311141','411131','211412','211214','211232','2331112']


def code128(text):
    if not text or any(not 32 <= ord(char) <= 126 for char in text): raise ValueError('Code128 needs a non-empty printable ASCII barcode or SKU')
    values = [104] + [ord(char) - 32 for char in text]
    return values + [(104 + sum(i * v for i, v in enumerate(values[1:], 1))) % 103, 106]


def label_geometry(code, width_mm, height_mm):
    values = code128(code); modules = sum(sum(map(int, PATTERNS[v])) for v in values)
    module_mm = (width_mm - 4) / (modules + 20)  # at least 10 quiet modules each side
    if module_mm < .25: raise ValueError(f'Increase label width to at least {4 + (modules + 20) * .25:.1f} mm for this code')
    if height_mm < 25: raise ValueError('Label height must be at least 25 mm')
    return values, module_mm


def paint_label(painter, name, code, width_mm, height_mm, dpi):
    values, module_mm = label_geometry(code, width_mm, height_mm)
    scale = dpi / 25.4
    painter.save(); painter.scale(scale, scale)
    painter.fillRect(QRectF(0, 0, width_mm, height_mm), Qt.GlobalColor.white)
    painter.setPen(Qt.GlobalColor.black)
    font = QFont(); font.setPixelSize(3); painter.setFont(font)
    metrics = QFontMetrics(font)
    name = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(width_mm - 4))
    painter.drawText(QRectF(2, 1, width_mm - 4, 5), Qt.AlignmentFlag.AlignCenter, name)
    x = 2 + 10 * module_mm
    for value in values:
        for index, width in enumerate(PATTERNS[value]):
            bar_width = int(width) * module_mm
            if index % 2 == 0: painter.fillRect(QRectF(x, 7, bar_width, height_mm - 15), Qt.GlobalColor.black)
            x += bar_width
    painter.drawText(QRectF(2, height_mm - 6, width_mm - 4, 5), Qt.AlignmentFlag.AlignCenter, code)
    painter.restore()


class BarcodeDialog(QDialog):
    def __init__(self, name, code, parent=None):
        super().__init__(parent); code128(code)
        self.name, self.code = name, code
        self.setWindowTitle('Barcode label · Native'); self.resize(820, 560)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.width = QDoubleSpinBox(); self.width.setRange(30, 200); self.width.setSuffix(' mm'); self.width.setValue(50)
        self.height = QDoubleSpinBox(); self.height.setRange(25, 150); self.height.setSuffix(' mm'); self.height.setValue(30)
        self.copies = QSpinBox(); self.copies.setRange(1, 500); self.copies.setValue(1)
        form.addRow('Width', self.width); form.addRow('Height', self.height); form.addRow('Copies', self.copies); layout.addLayout(form)
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution); self.printer.setFullPage(True)
        self.preview = QPrintPreviewWidget(self.printer, self); self.preview.paintRequested.connect(self.paint)
        layout.addWidget(self.preview, 1)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        buttons = QHBoxLayout(); self.print_button = QPushButton('Print / PDF…'); self.print_button.clicked.connect(self.print_label)
        close = QPushButton('Close'); close.clicked.connect(self.reject); buttons.addWidget(self.print_button); buttons.addWidget(close); layout.addLayout(buttons)
        self.width.valueChanged.connect(self.resize_label); self.height.valueChanged.connect(self.resize_label); self.resize_label()

    def resize_label(self):
        self.printer.setPageSize(QPageSize(QSizeF(self.width.value(), self.height.value()), QPageSize.Unit.Millimeter))
        self.printer.setPageMargins(QMarginsF(0, 0, 0, 0)); self.preview.updatePreview()

    def paint(self, printer):
        size = printer.paperRect(QPrinter.Unit.Millimeter)
        try: label_geometry(self.code, size.width(), size.height())
        except ValueError as exc:
            self.status.setText(str(exc)); self.print_button.setEnabled(False); return
        self.print_button.setEnabled(True); self.status.setText('Code128 · one label per page · verify paper size and scaling in your printer driver.')
        painter = QPainter(printer)
        if not painter.isActive(): self.status.setText('Could not start the printer'); return
        try: paint_label(painter, self.name, self.code, size.width(), size.height(), printer.resolution())
        finally: painter.end()

    def print_label(self):
        self.printer.setCopyCount(self.copies.value())
        if QPrintDialog(self.printer, self).exec() == QDialog.DialogCode.Accepted: self.paint(self.printer)
