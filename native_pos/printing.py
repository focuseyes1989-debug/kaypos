"""Machine-local receipt printing preferences using stock Qt controls."""
from PyQt6.QtCore import QSizeF, QMarginsF
from PyQt6.QtGui import QPageSize, QPageLayout
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QComboBox, QPushButton, QDialogButtonBox, QMessageBox
from native_pos.config import load_config, save_config


def printer_host(parent):
    while parent is not None:
        host = getattr(parent, 'host', parent)
        if hasattr(host, 'settings_path'):
            return host
        parent = parent.parent()
    return None


def printer_preferences(parent):
    host = printer_host(parent)
    return load_config(host.settings_path if host else None)


def prepare_printer(values, available=None):
    available = QPrinterInfo.availablePrinterNames() if available is None else available
    name = values.get('receipt_printer', '')
    if name and name not in available:
        raise ValueError('Saved receipt printer is unavailable: ' + name + '. Update Printer settings or choose another printer in Print / PDF.')
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    # Start with Qt's PDF device so an installed default driver's paper limits
    # cannot silently replace a configured roll width before destination choice.
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    if name:
        printer.setPrinterName(name)
        printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
    dpi = values.get('receipt_dpi', 300)
    printer.setResolution(dpi if dpi in (203, 300, 600) else 300)
    paper = values.get('receipt_paper', 'A4')
    page = QPageSize(QPageSize.PageSizeId.A4) if paper not in ('58mm', '80mm') else QPageSize(QSizeF(58 if paper == '58mm' else 80, 297), QPageSize.Unit.Millimeter, paper)
    printer.setPageLayout(QPageLayout(page, QPageLayout.Orientation.Portrait, QMarginsF(3, 3, 3, 3), QPageLayout.Unit.Millimeter))
    return printer


class PrinterSettingsDialog(QDialog):
    def __init__(self, host, parent=None):
        super().__init__(parent); self.host = host
        self.setWindowTitle('Receipt printer · this PC'); self.resize(540, 300)
        self.values = load_config(host.settings_path)
        body = QVBoxLayout(self)
        note = QLabel('These preferences apply to KAY POS Native on this Windows account. Choose the final destination in the standard Print / PDF dialog.'); note.setWordWrap(True); body.addWidget(note)
        form = QFormLayout(); body.addLayout(form)
        self.printer = QComboBox(); form.addRow('Windows printer', self.printer)
        self.paper = QComboBox(); self.paper.addItems(['58mm', '80mm', 'A4']); self.paper.setCurrentText(self.values['receipt_paper']); form.addRow('Receipt paper', self.paper)
        self.dpi = QComboBox()
        for dpi in (203, 300, 600): self.dpi.addItem(str(dpi) + ' dpi', dpi)
        self.dpi.setCurrentIndex(self.dpi.findData(self.values['receipt_dpi'])); form.addRow('Print quality', self.dpi)
        self.drawer = QComboBox(); self.drawer.addItem('POS Server printer', 'server'); self.drawer.addItem('Selected Windows printer on this PC', 'local')
        self.drawer.setCurrentIndex(self.drawer.findData(self.values['drawer_target'])); form.addRow('Cash drawer target', self.drawer)
        self.after_sale = QComboBox()
        self.after_sale.addItem('Show receipt', 'show_receipt')
        self.after_sale.addItem('Show receipt, then ask to open drawer', 'show_receipt_ask_drawer')
        self.after_sale.addItem('Stay on Sales', 'stay_sales')
        self.after_sale.setCurrentIndex(self.after_sale.findData(self.values['after_sale'])); form.addRow('After sale', self.after_sale)
        refresh = QPushButton('Refresh printers'); refresh.clicked.connect(lambda: self.refresh(self.printer.currentData())); form.addRow(refresh)
        note = QLabel('58mm and 80mm use 297mm page lengths with 3mm margins; long receipts continue on another page. Driver-supported paper sizes and printable margins may differ.'); note.setWordWrap(True); body.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); body.addWidget(buttons)
        self.refresh(self.values['receipt_printer'])

    def refresh(self, selected=''):
        self.printer.clear(); self.printer.addItem('Choose in Print / PDF dialog', '')
        names = QPrinterInfo.availablePrinterNames()
        for name in names: self.printer.addItem(name, name)
        if selected and selected not in names: self.printer.addItem(selected + ' (unavailable)', selected)
        self.printer.setCurrentIndex(max(0, self.printer.findData(selected)))

    def save(self):
        if not self.host.session or not self.host.session.can('edit_settings'): return
        values = dict(receipt_printer=self.printer.currentData(), receipt_paper=self.paper.currentText(), receipt_dpi=self.dpi.currentData(), drawer_target=self.drawer.currentData(), after_sale=self.after_sale.currentData())
        try: saved = save_config(values, self.host.settings_path)
        except OSError as exc:
            QMessageBox.warning(self, 'Printer settings', 'Settings could not be saved: ' + str(exc)); return
        self.host.config.update(saved); self.accept()
