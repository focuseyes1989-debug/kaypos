"""Loopback-only Windows printer bridge for KAY POS Touch.

Run on each cashier PC. The configured Touch origin and pairing key are required
for every request. Windows printing is dispatched to the Qt GUI thread.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import math
import os
import secrets
import sqlite3
import threading
from contextlib import closing
from concurrent.futures import Future, TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PORT = 17861
MAX_BODY = 3_000_000


def normalize_origin(value):
    parts = urlsplit(str(value).strip())
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Enter the Touch website address, for example https://192.168.110.112:8000')
    if parts.scheme == 'http' and parts.hostname not in ('localhost', '127.0.0.1'):
        raise ValueError('Use the HTTPS address of your Touch website')
    return f'{parts.scheme}://{parts.netloc}'


def config_dir():
    path = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'KAY POS' / 'Touch Print Bridge'
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_job(path, payload):
    if path not in ('/print', '/drawer') or not isinstance(payload, dict):
        raise ValueError('Unknown print operation')
    if not isinstance(payload.get('printer'), str) or not payload['printer'].strip():
        raise ValueError('Select a local printer first')
    key = payload.get('request_key', '')
    if not isinstance(key, str) or not 8 <= len(key) <= 180:
        raise ValueError('Invalid job key')
    if path == '/print':
        if str(payload.get('dpi', '203')) not in ('203', '300', '600'):
            raise ValueError('Invalid printer resolution')
        if payload.get('paper') not in ('58', '80', 'a4'):
            raise ValueError('Select 58mm, 80mm or A4 paper')
        receipt = payload.get('receipt')
        if not isinstance(receipt, dict) or not isinstance(receipt.get('items'), list) or len(receipt['items']) > 1000:
            raise ValueError('Invalid receipt items (maximum 1000)')
        if any(not isinstance(item, dict) for item in receipt['items']):
            raise ValueError('Invalid receipt item')
        if not isinstance(receipt.get('receipt_settings', {}), dict):
            raise ValueError('Invalid receipt settings')


class JobLedger:
    """Persist before dispatch: an interrupted/uncertain job is never replayed."""
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, digest TEXT, status TEXT, detail TEXT)')

    def run(self, origin, path, payload, dispatch):
        validate_job(path, payload)
        key = origin + ':' + path + ':' + payload['request_key']
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.lock, closing(sqlite3.connect(self.path)) as db, db:
            existing = db.execute('SELECT digest,status,detail FROM jobs WHERE key=?', (key,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError('This job key was already used with different receipt data')
                if existing[1] == 'sent':
                    return {'status': 'sent', 'duplicate': True}
                raise ValueError('Previous job outcome is uncertain or failed. Check the printer before a manual retry.')
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (key, digest, 'pending', ''))
        try:
            result = dispatch(path, payload)
        except Exception as exc:
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('UPDATE jobs SET status=?,detail=? WHERE key=?', ('failed', str(exc), key))
            raise
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE jobs SET status=? WHERE key=?', ('sent', key))
        return result


def handler_factory(origin, token, dispatch, ledger):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Pairing keys and receipt data must never enter HTTP logs.

        def allowed(self, auth=True):
            host = self.headers.get('Host', '')
            if host != f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') != origin:
                self.reply(403, {'error': 'Touch website is not paired with this bridge'}, cors=False)
                return False
            if auth and not hmac.compare_digest(self.headers.get('X-Kay-Bridge-Key', ''), token):
                self.reply(401, {'error': 'Pairing key does not match. Copy it from the local bridge.'})
                return False
            return True

        def reply(self, code, body, cors=True):
            data = json.dumps(body).encode()
            self.send_response(code)
            if cors:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_OPTIONS(self):
            if not self.allowed(auth=False):
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Kay-Bridge-Key')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Vary', 'Origin')
            self.end_headers()

        def do_GET(self):
            if not self.allowed():
                return
            if self.path != '/printers':
                self.reply(404, {'error': 'Not found'})
                return
            try:
                self.reply(200, dispatch('/printers', {}))
            except Exception as exc:
                self.reply(503, {'error': str(exc)})

        def do_POST(self):
            if not self.allowed():
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_BODY or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Expected a JSON receipt under 3 MB')
                self.connection.settimeout(10)
                payload = json.loads(self.rfile.read(size))
                self.reply(200, ledger.run(origin, self.path, payload, dispatch))
            except Exception as exc:
                self.reply(400, {'error': str(exc)})
    return Handler


def receipt_document(receipt, paid, width_mm, a4=False):
    from PyQt6.QtGui import QTextDocument, QFont, QImage
    from PyQt6.QtCore import QUrl, QByteArray
    def num(value):
        try:
            result = float(value or 0)
            return result if math.isfinite(result) else 0
        except (TypeError, ValueError):
            return 0
    def money(value):
        return f'{num(value):,.2f}'.rstrip('0').rstrip('.')
    def esc(value):
        return html.escape(str(value or '')).replace('\n', '<br>')
    settings = receipt.get('receipt_settings') or {}
    doc = QTextDocument()
    doc.setDefaultFont(QFont('Myanmar Text', 10 if a4 or width_mm > 50 else 9))
    doc.setDocumentMargin(0)
    def picture(key, width):
        import base64
        value = settings.get(key, '')
        if not isinstance(value, str) or not value.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,')):
            return ''
        try:
            image = QImage.fromData(QByteArray(base64.b64decode(value.split(',', 1)[1], validate=True)))
            if image.isNull() or image.width() * image.height() > 16_000_000:
                return ''
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(key), image)
            return f'<img src="{key}" width="{width}" height="{max(1, round(width * image.height() / image.width()))}"><br>'
        except ValueError:
            return ''
    items = receipt.get('items', [])
    total = num(receipt.get('total'))
    subtotal = num(receipt.get('subtotal', sum(num(i.get('total', num(i.get('qty')) * num(i.get('price')))) for i in items)))
    discount = num(receipt.get('discount_amount'))
    tax = num(receipt.get('tax_amount', receipt.get('tax', max(0, total-subtotal+discount))))
    payment = num(paid if paid is not None else receipt.get('paid_amount', receipt.get('payment')))
    rows = [('Subtotal', subtotal), ('Discount', discount), ('Tax', tax), ('Total', total), ('Paid', payment), ('Change', max(0, payment-total))]
    if str(receipt.get('payment_type')).lower() == 'credit' or num(receipt.get('balance_amount')) > 0:
        rows.append(('Credit balance', num(receipt.get('balance_amount', max(0, total-payment)))))
    title = 'REFUNDED RECEIPT' if str(receipt.get('status')).lower() == 'refunded' else 'RECEIPT'
    header_text = '<br>'.join(esc(settings[key]) for key in ('shop_phone', 'shop_address', 'receipt_header') if settings.get(key))
    body = f'<div align="center">{picture("shop_logo_image",90)}<b>{esc(settings.get("shop_name", "KAY POS"))}</b><br>{header_text + "<br>" if header_text else ""}<b>{title}</b></div><hr>'
    body += f'{esc(receipt.get("invoice_no"))}<br>{esc(receipt.get("created_at"))}<br>{esc(receipt.get("payment_type", "Cash"))}<br>'
    if settings.get('show_customer_name') not in ('0', False):
        body += esc(receipt.get('customer_name') or 'Walk-in Customer') + '<br>'
    body += '<hr><table width="100%" cellspacing="0" cellpadding="3"><tr><th align="left">Item / Qty × Price</th><th align="right">Amount</th></tr>'
    for item in items:
        body += f'<tr><td width="60%">{esc(item.get("product_name") or item.get("name") or "Item")}<br>{money(item.get("qty"))} × {money(item.get("price"))}</td><td align="right">{money(item.get("total", num(item.get("qty"))*num(item.get("price"))))}</td></tr>'
    body += '</table><hr><table width="100%">'
    for label, value in rows:
        body += f'<tr><td>{label}</td><td align="right"><b>{money(value)} {esc(settings.get("currency_symbol", "Ks"))}</b></td></tr>'
    body += '</table><hr><div align="center">' + picture('shop_qr_code_image', 105)
    body += '<br>'.join(esc(settings[key]) for key in ('shop_qr_name', 'receipt_footer', 'shop_footer_message') if settings.get(key))
    body += '<br>' + esc(settings.get('receipt_thank_you_text') or 'Thank you.') + '</div>'
    doc.setHtml(body)
    doc.setTextWidth(width_mm * 96 / 25.4)
    return doc


def print_receipt(payload):
    from PyQt6.QtCore import QMarginsF, QSizeF, QRectF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPainter
    from PyQt6.QtPrintSupport import QPrinter
    paper = payload['paper']
    width = {'58': 58, '80': 80, 'a4': 210}[paper]
    margin = 12 if paper == 'a4' else 5 if paper == '58' else 4
    doc = receipt_document(payload['receipt'], payload.get('paid'), width-2*margin, paper == 'a4')
    height = 297 if paper == 'a4' else max(55, min(500, math.ceil(doc.size().height()*25.4/96 + 8)))
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(payload['printer'])
    printer.setResolution(int(payload.get('dpi', 203 if paper != 'a4' else 300)))
    page = QPageSize(QSizeF(width, height), QPageSize.Unit.Millimeter, 'KAY Receipt', QPageSize.SizeMatchPolicy.ExactMatch)
    if not printer.setPageLayout(QPageLayout(page, QPageLayout.Orientation.Portrait, QMarginsF(margin, 3 if paper != 'a4' else 12, margin, 4 if paper != 'a4' else 12), QPageLayout.Unit.Millimeter)):
        raise ValueError('Printer driver rejected this paper size. Check printer paper settings.')
    rect = printer.pageLayout().paintRectPixels(printer.resolution())
    scale = printer.resolution()/96
    page_height = rect.height()/scale
    doc.setPageSize(QSizeF(rect.width()/scale, page_height))
    painter = QPainter(printer)
    if not painter.isActive():
        raise ValueError('Could not start the selected printer')
    try:
        pages = max(1, math.ceil(doc.size().height()/page_height))
        for index in range(pages):
            if index and not printer.newPage():
                raise ValueError('Printer failed while starting the next receipt page')
            painter.save()
            painter.scale(scale, scale)
            painter.setClipRect(QRectF(0, 0, rect.width()/scale, page_height))
            painter.translate(0, -index*page_height)
            doc.drawContents(painter, QRectF(0, index*page_height, rect.width()/scale, page_height))
            painter.restore()
    finally:
        painter.end()
    if printer.printerState() == QPrinter.PrinterState.Error:
        raise ValueError('Windows reported a print error')


def open_drawer(printer_name):
    import ctypes
    from ctypes import wintypes
    spool = ctypes.WinDLL('winspool.drv', use_last_error=True)
    spool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    spool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    spool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    spool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    for name in ('EndPagePrinter', 'EndDocPrinter', 'ClosePrinter'):
        getattr(spool, name).argtypes = [wintypes.HANDLE]
    class Doc(ctypes.Structure):
        _fields_ = [('name', wintypes.LPWSTR), ('output', wintypes.LPWSTR), ('datatype', wintypes.LPWSTR)]
    handle = wintypes.HANDLE()
    if not spool.OpenPrinterW(printer_name, ctypes.byref(handle), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = Doc('KAY Touch - Cash Drawer', None, 'RAW')
        if not spool.StartDocPrinterW(handle, 1, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not spool.StartPagePrinter(handle):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                command = ctypes.create_string_buffer(b'\x1b\x70\x00\x19\xfa')
                written = wintypes.DWORD()
                if not spool.WritePrinter(handle, command, 5, ctypes.byref(written)) or written.value != 5:
                    raise ValueError('Windows could not send the drawer command')
            finally:
                spool.EndPagePrinter(handle)
        finally:
            spool.EndDocPrinter(handle)
    finally:
        spool.ClosePrinter(handle)


def main():
    import sys
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
    from PyQt6.QtPrintSupport import QPrinterInfo
    app = QApplication(sys.argv)
    if len(sys.argv) == 3 and sys.argv[1] == '--check':
        doc = receipt_document({'items': [], 'total': 0}, 0, 72)
        Path(sys.argv[2]).write_text(json.dumps({'ok': doc.size().height() > 0, 'printer_count': len(QPrinterInfo.availablePrinterNames())}))
        return
    class Dispatcher(QObject):
        requested = pyqtSignal(object)
        def __init__(self):
            super().__init__()
            self.requested.connect(self.work)
        def call(self, path, payload):
            future = Future()
            self.requested.emit((path, payload, future))
            try:
                return future.result(timeout=45)
            except TimeoutError:
                future.cancel()
                raise ValueError('Printer response timed out. Check the queue before retrying.')
        def work(self, job):
            path, payload, future = job
            if not future.set_running_or_notify_cancel():
                return
            try:
                names = list(QPrinterInfo.availablePrinterNames())
                if path == '/printers':
                    result = {'printers': names, 'computer': os.getenv('COMPUTERNAME', 'Local PC')}
                else:
                    if payload['printer'] not in names:
                        raise ValueError('Selected printer is not installed on this PC. Refresh Printers.')
                    if path == '/print':
                        print_receipt(payload)
                    else:
                        open_drawer(payload['printer'])
                    result = {'status': 'sent'}
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
    dispatcher = Dispatcher()
    directory = config_dir()
    try:
        config = json.loads((directory/'bridge.json').read_text())
    except (OSError, ValueError):
        config = {}
    key = str(config.get('key') or secrets.token_urlsafe(32))
    window = QWidget()
    window.setWindowTitle('KAY Touch Local Print Bridge')
    window.resize(540, 260)
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel('Keep this bridge running on the PC connected to your printer.'))
    layout.addWidget(QLabel('Touch website address'))
    origin_input = QLineEdit(config.get('origin', 'https://192.168.110.112:8000'))
    layout.addWidget(origin_input)
    layout.addWidget(QLabel('Pairing key — copy into Touch → Printer → Local bridge setup'))
    key_input = QLineEdit(key)
    key_input.setReadOnly(True)
    layout.addWidget(key_input)
    copy = QPushButton('Copy pairing key')
    copy.clicked.connect(lambda: app.clipboard().setText(key))
    layout.addWidget(copy)
    start = QPushButton('Start local bridge')
    layout.addWidget(start)
    status = QLabel('Stopped')
    status.setWordWrap(True)
    layout.addWidget(status)
    servers = []
    def begin():
        try:
            origin = normalize_origin(origin_input.text())
            server = ThreadingHTTPServer(('127.0.0.1', PORT), handler_factory(origin, key, dispatcher.call, JobLedger(directory/'jobs.db')))
            server.daemon_threads = True
            servers.append(server)
            (directory/'bridge.json').write_text(json.dumps({'origin': origin, 'key': key}))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            start.setEnabled(False)
            origin_input.setReadOnly(True)
            status.setText(f'Ready · {len(QPrinterInfo.availablePrinterNames())} local printers · Keep this window open or minimized.')
        except Exception as exc:
            status.setText(str(exc))
    start.clicked.connect(begin)
    def stop():
        for server in servers:
            server.shutdown()
            server.server_close()
    app.aboutToQuit.connect(stop)
    window.show()
    if config.get('origin'):
        QTimer.singleShot(0, begin)
    sys.exit(app.exec())


if __name__ == '__main__':
    import sys
    try:
        main()
    except Exception:
        if len(sys.argv) == 3 and sys.argv[1] == '--check':
            import traceback
            Path(sys.argv[2]).write_text(json.dumps({'ok': False, 'error': traceback.format_exc()}))
            sys.exit(1)
        raise
