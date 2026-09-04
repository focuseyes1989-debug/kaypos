"""Native Qt receipt preview and printer/PDF selection."""
from html import escape
import base64
import binascii

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QImage, QTextDocument
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QMessageBox


def receipt_images(receipt):
    images = {}
    settings = receipt.get('receipt_settings') or {}
    for name, key in [('logo', 'shop_logo_image'), ('qr', 'shop_qr_code_image')]:
        value = settings.get(key) or ''
        if not isinstance(value, str) or len(value) > 12 * 1024 * 1024: continue
        if not value.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,')): continue
        try: data = base64.b64decode(value.split(',', 1)[1], validate=True)
        except (ValueError, binascii.Error): continue
        image = QImage.fromData(data)
        if not image.isNull(): images[name] = image
    return images


def receipt_html(receipt):
    safe = lambda value: escape(str(value if value is not None else ''))
    settings = receipt.get('receipt_settings') or {}
    images = receipt_images(receipt)
    def picture(name, limit):
        if name not in images: return ''
        size = images[name].size(); ratio = min(1, limit / max(size.width(), size.height()))
        return f'<p><img src="native-receipt:{name}" width="{max(1, int(size.width() * ratio))}" height="{max(1, int(size.height() * ratio))}"></p>'
    multiline = lambda value: safe(value).replace('\n', '<br>')
    money = lambda value: f'{float(value or 0):,.2f}'
    rows = ''.join(f'<tr><td>{safe(i.get("product_name"))}</td><td>{safe(i.get("qty"))}</td>'
                   f'<td align="right">{money(i.get("price"))}</td><td align="right">{money(i.get("total"))}</td></tr>'
                   for i in receipt.get('items', []))
    totals = ''.join(f'<p>{label}: <b>{money(receipt[key])}</b></p>' for key, label in
                     [('subtotal', 'Subtotal'), ('discount_amount', 'Discount'), ('tax_amount', 'Tax'),
                      ('total', 'Total'), ('payment', 'Paid'), ('change_amount', 'Change'), ('balance_amount', 'Balance')]
                     if key in receipt)
    return (picture('logo', 180) + f'<h2>{safe(settings.get("shop_name") or "KAY POS")}</h2>'
            f'<p>{multiline(settings.get("shop_address", ""))}<br>{safe(settings.get("shop_phone", ""))}</p>'
            f'<p>{multiline(settings.get("receipt_header", ""))}</p><p>{safe(receipt.get("invoice_no", "Sale review"))}<br>'
            f'{safe(receipt.get("created_at", ""))}<br>{safe(receipt.get("customer_name", ""))}</p>'
            f'<table width="100%" cellpadding="5"><tr><th>Item</th><th>Qty</th><th>Price</th><th>Amount</th></tr>{rows}</table>'
            f'{totals}<p>{safe(receipt.get("payment_type", ""))}<br>Due: {safe(receipt.get("due_date", ""))}<br>'
            f'{safe(receipt.get("credit_notes", ""))}</p>'
            f'<p>{multiline(settings.get("receipt_footer", ""))}<br>{multiline(settings.get("shop_footer_message", ""))}</p>'
            + picture('qr', 180) + f'<p>{safe(settings.get("shop_qr_name", ""))}</p>')


class ReceiptDialog(QDialog):
    def __init__(self, receipt, parent=None, can_print=True):
        super().__init__(parent)
        self.setWindowTitle('Receipt · KAY POS Native')
        self.resize(640, 540)
        layout = QVBoxLayout(self)
        self.document = QTextBrowser()
        for name, image in receipt_images(receipt).items():
            self.document.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl('native-receipt:' + name), image)
        self.document.setHtml(receipt_html(receipt))
        layout.addWidget(self.document)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button = buttons.addButton('Print / PDF…', QDialogButtonBox.ButtonRole.ActionRole)
        button.setEnabled(can_print); button.clicked.connect(self.print_receipt)
        from native_pos.printing import printer_host
        network = buttons.addButton('Network PDF…', QDialogButtonBox.ButtonRole.ActionRole)
        network.setVisible(printer_host(self) is not None); network.setEnabled(can_print); network.clicked.connect(self.network_print)
        buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def network_print(self):
        import tempfile
        from pathlib import Path
        from native_pos.printing import printer_host, printer_preferences, prepare_printer
        from native_pos.network_print import NetworkPrinterDialog
        host = printer_host(self)
        if not host or not host.session.can('print_receipt'): return
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'receipt.pdf'
                printer = prepare_printer(dict(printer_preferences(self), receipt_printer=''), available=[])
                printer.setOutputFileName(str(path)); self.document.document().print(printer)
                data = path.read_bytes()
                if not data.startswith(b'%PDF-'): raise ValueError('Receipt PDF could not be generated')
            NetworkPrinterDialog(host, self, data).exec()
        except (OSError, ValueError) as exc: QMessageBox.warning(self, 'Network receipt', str(exc))

    def print_receipt(self):
        from native_pos.printing import prepare_printer, printer_preferences
        values = printer_preferences(self)
        try: printer = prepare_printer(values)
        except ValueError as exc:
            QMessageBox.information(self, 'Choose receipt printer', str(exc))
            printer = prepare_printer(dict(values, receipt_printer=''))
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.document.document().print(printer)
