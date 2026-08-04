# ui/receipt_dialog.py
import os
import ctypes
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDialogButtonBox, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, QByteArray, QIODevice, QBuffer, QSizeF, QMarginsF, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPainter, QFontMetrics, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrinterInfo
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.receipt_template import build_receipt_html, build_receipt_text_lines


class ReceiptDialog(QDialog):
    PAPER_SIZES = {
        0: (80.0, 297.0),
        1: (58.0, 297.0),
        2: None,
    }

    def __init__(self, sale_id: int, parent=None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.cash_drawer_opened = False
        self.setWindowTitle("Receipt")
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setMinimumSize(550, 650)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Paper size selection
        paper_layout = QHBoxLayout()
        paper_layout.addWidget(QLabel("Paper Size:"))
        self.paper_combo = QComboBox()
        self.paper_combo.addItems(["80mm", "58mm", "A4"])
        self.paper_combo.setCurrentIndex(self.load_paper_setting())
        self.paper_combo.currentIndexChanged.connect(self.save_paper_setting)
        paper_layout.addWidget(self.paper_combo)
        paper_layout.addStretch()
        layout.addLayout(paper_layout)

        # Receipt display (HTML preview)
        self.receipt_display = QTextEdit()
        self.receipt_display.setReadOnly(True)
        self.receipt_display.setFont(QFont("Courier New", 9))
        self.receipt_display.setStyleSheet("QTextEdit { background-color: #ffffff; color: #000000; }")
        layout.addWidget(self.receipt_display)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Print button
        self.btn_print = QPushButton("🖨️ Print")
        self.btn_print.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.btn_print.clicked.connect(self.print_receipt)
        button_layout.addWidget(self.btn_print)
        
        button_layout.addStretch()
        
        # Close & New Sale button (without cash drawer)
        self.btn_close_new_sale = QPushButton("🗑️ Close & New Sale")
        self.btn_close_new_sale.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.btn_close_new_sale.clicked.connect(self.close_without_drawer)
        button_layout.addWidget(self.btn_close_new_sale)
        
        # Close & Open Cash Drawer button
        self.btn_close_open_drawer = QPushButton("💰 Close & Open Drawer")
        self.btn_close_open_drawer.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.btn_close_open_drawer.clicked.connect(self.close_with_drawer)
        button_layout.addWidget(self.btn_close_open_drawer)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.load_receipt()

    def load_paper_setting(self) -> int:
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='receipt_paper_size'")
            row = cursor.fetchone()
            conn.close()
            if row and row[0] in ("0", "1", "2"):
                return int(row[0])
        except:
            pass
        return 0

    def save_paper_setting(self, index: int):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                           ("receipt_paper_size", str(index)))
            conn.commit()
            conn.close()
        except:
            pass

    def get_setting(self, key, default=""):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else default
        except Exception:
            return default

    def selected_printer_name(self):
        saved_name = self.get_setting("receipt_printer_name", "").strip()
        if saved_name:
            return saved_name

        default_printer = QPrinterInfo.defaultPrinter()
        if default_printer.isNull():
            return ""
        return default_printer.printerName()

    def receipt_print_quality(self):
        value = self.get_setting("receipt_print_quality", "203")
        try:
            return int(value)
        except (TypeError, ValueError):
            return 203

    def configure_receipt_printer(self, printer):
        paper_index = self.paper_combo.currentIndex()
        paper_size = self.PAPER_SIZES.get(paper_index)
        if paper_size is None:
            page_size = QPageSize(QPageSize.PageSizeId.A4)
        else:
            width_mm, height_mm = paper_size
            page_size = QPageSize(
                QSizeF(width_mm, height_mm),
                QPageSize.Unit.Millimeter,
                f"{width_mm:g}mm Receipt",
            )

        page_layout = QPageLayout(
            page_size,
            QPageLayout.Orientation.Portrait,
            QMarginsF(2, 2, 2, 2),
            QPageLayout.Unit.Millimeter,
        )
        accepted = printer.setPageLayout(page_layout)
        printer.setResolution(self.receipt_print_quality())
        return accepted

    def load_receipt(self):
        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.invoice_no, s.created_at, s.total, s.payment, s.change_amount,
                   s.payment_type, s.discount_amount, c.name, s.customer_id
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = ?
        """, (self.sale_id,))
        sale = cursor.fetchone()
        if not sale:
            self.receipt_display.setPlainText("Sale not found.")
            conn.close()
            return

        invoice_no, created_at, total, payment, change, payment_type, discount_amt, customer_name, customer_id = sale

        cursor.execute("""
            SELECT product_name, qty, price, total
            FROM sale_items
            WHERE sale_id = ?
        """, (self.sale_id,))
        items = cursor.fetchall()

        # Load business settings
        cursor.execute("SELECT value FROM settings WHERE key='shop_name'")
        row = cursor.fetchone()
        shop_name = row[0] if row else "ZAY POS"
        
        cursor.execute("SELECT value FROM settings WHERE key='shop_phone'")
        row = cursor.fetchone()
        shop_phone = row[0] if row else ""
        
        cursor.execute("SELECT value FROM settings WHERE key='shop_address'")
        row = cursor.fetchone()
        shop_address = row[0] if row else ""
        
        cursor.execute("SELECT value FROM settings WHERE key='shop_footer_message'")
        row = cursor.fetchone()
        footer_message = row[0] if row else ""

        cursor.execute("SELECT value FROM settings WHERE key='receipt_header'")
        row = cursor.fetchone()
        receipt_header = row[0] if row else ""

        cursor.execute("SELECT value FROM settings WHERE key='receipt_footer'")
        row = cursor.fetchone()
        receipt_footer = row[0] if row else ""

        cursor.execute("SELECT value FROM settings WHERE key='show_customer_name'")
        row = cursor.fetchone()
        show_customer_name = (row[0] == '1') if row else True

        cursor.execute("SELECT value FROM settings WHERE key='shop_logo'")
        row = cursor.fetchone()
        logo_path = row[0] if row else ""

        conn.close()

        sale_data = {
            "invoice_no": invoice_no,
            "created_at": created_at,
            "total": total,
            "payment": payment,
            "change": change,
            "payment_type": payment_type,
            "discount_amt": discount_amt,
            "customer_name": customer_name,
        }
        self.receipt_display.setHtml(build_receipt_html(sale_data, items))
        return

        symbol = get_currency_symbol()

        def format_multiline_html(text):
            if not text:
                return ""
            return text.replace("\n", "<br>").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Build business info section
        business_info = ""
        if shop_name:
            business_info += f'<div class="shop-name">{shop_name}</div>'
        if shop_phone:
            business_info += f'<div class="shop-phone">📞 {shop_phone}</div>'
        if shop_address:
            business_info += f'<div class="shop-address">📍 {format_multiline_html(shop_address)}</div>'

        # Payment and Change cards
        payment_card = f"""
        <div style="background: #f0f0f0; border-radius: 8px; padding: 10px; margin: 5px; text-align: center; flex: 1;">
            <div style="color: #555; font-size: 10pt;">Payment</div>
            <div style="color: #2c3e50; font-size: 16pt; font-weight: bold;">{format_money(payment, symbol)}</div>
        </div>
        """
        change_card = f"""
        <div style="background: #f0f0f0; border-radius: 8px; padding: 10px; margin: 5px; text-align: center; flex: 1;">
            <div style="color: #555; font-size: 10pt;">Change</div>
            <div style="color: #e67e22; font-size: 16pt; font-weight: bold;">{format_money(change, symbol)}</div>
        </div>
        """

        html = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                font-size: 9pt;
                margin: 0;
                padding: 10px;
                background-color: #ffffff;
                color: #000000;
            }}
            .header {{ text-align: center; margin-bottom: 10px; }}
            .logo {{ max-width: 120px; max-height: 80px; display: block; margin-left: auto; margin-right: auto; }}
            .shop-name {{ font-size: 14pt; font-weight: bold; margin-top: 5px; margin-bottom: 5px; color: #2c3e50; }}
            .shop-phone {{ font-size: 9pt; color: #555; }}
            .shop-address {{ font-size: 9pt; color: #555; white-space: pre-wrap; }}
            .divider {{ border-top: 1px dashed #aaa; margin: 8px 0; }}
            .item {{ margin: 2px 0; }}
            .item-name {{ font-weight: bold; }}
            .item-details {{ margin-left: 8px; }}
            .total-line {{ font-weight: bold; margin-top: 4px; }}
            .footer {{ text-align: center; margin-top: 8px; white-space: pre-wrap; }}
            .card-container {{ display: flex; justify-content: space-between; gap: 10px; margin: 10px 0; }}
        </style>
        </head>
        <body>
        <div class="header">
        """
        
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, "PNG")
                buffer.close()
                b64_data = byte_array.toBase64().data().decode()
                html += f'<img class="logo" src="data:image/png;base64,{b64_data}" />'

        html += business_info
        if receipt_header:
            html += f'<div class="header-text" style="white-space: pre-wrap;">{format_multiline_html(receipt_header)}</div>'
        html += f"""
        </div>
        <div class="divider"></div>
        <div>Invoice: {invoice_no}</div>
        <div>Date: {created_at}</div>
        <div>Payment Type: {payment_type}</div>
        """
        if show_customer_name and customer_name:
            html += f'<div>Customer: {customer_name}</div>'
        html += '<div class="divider"></div>'
        
        for name, qty, price, total_price in items:
            html += f"""
            <div class="item">
                <div class="item-name">{name}</div>
                <div class="item-details">{qty} x {format_money(price, symbol)} = {format_money(total_price, symbol)}</div>
            </div>
            """
        
        html += '<div class="divider"></div>'
        subtotal = sum(item[3] for item in items)
        discount = discount_amt if discount_amt else 0.0
        html += f"""
        <div>Subtotal: {format_money(subtotal, symbol)}</div>
        <div>Discount: -{format_money(discount, symbol)}</div>
        <div>Tax: 0</div>
        <div class="total-line">Grand Total: {format_money(total, symbol)}</div>
        <div class="card-container">
            {payment_card}
            {change_card}
        </div>
        """
        if receipt_footer:
            html += f'<div class="footer">{format_multiline_html(receipt_footer)}</div>'
        if footer_message:
            html += f'<div class="footer" style="margin-top: 5px;">{format_multiline_html(footer_message)}</div>'
        html += """
        <div class="divider"></div>
        <div class="header">THANK YOU</div>
        </body>
        </html>
        """
        self.receipt_display.setHtml(html)

    def build_text_lines(self):
        lines = []
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.invoice_no, s.created_at, s.total, s.payment, s.change_amount,
                   s.payment_type, s.discount_amount, c.name, s.customer_id
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = ?
        """, (self.sale_id,))
        sale = cursor.fetchone()
        if not sale:
            conn.close()
            return ["Sale not found"]

        invoice_no, created_at, total, payment, change, payment_type, discount_amt, customer_name, customer_id = sale

        cursor.execute("SELECT product_name, qty, price, total FROM sale_items WHERE sale_id=?", (self.sale_id,))
        items = cursor.fetchall()

        conn.close()
        sale_data = {
            "invoice_no": invoice_no,
            "created_at": created_at,
            "total": total,
            "payment": payment,
            "change": change,
            "payment_type": payment_type,
            "discount_amt": discount_amt,
            "customer_name": customer_name,
        }
        return build_receipt_text_lines(sale_data, items)

        cursor.execute("SELECT value FROM settings WHERE key='shop_name'")
        row = cursor.fetchone()
        shop_name = row[0] if row else "ZAY POS"

        cursor.execute("SELECT value FROM settings WHERE key='receipt_header'")
        row = cursor.fetchone()
        receipt_header = row[0] if row else ""

        cursor.execute("SELECT value FROM settings WHERE key='receipt_footer'")
        row = cursor.fetchone()
        receipt_footer = row[0] if row else ""

        cursor.execute("SELECT value FROM settings WHERE key='show_customer_name'")
        row = cursor.fetchone()
        show_customer_name = (row[0] == '1') if row else True

        conn.close()

        symbol = get_currency_symbol()

        lines.append("=" * 20)
        lines.append(shop_name)
        if receipt_header:
            lines.extend([line for line in receipt_header.splitlines() if line.strip() != ""])
        lines.append("=" * 20)
        lines.append(f"Invoice: {invoice_no}")
        lines.append(f"Date: {created_at}")
        lines.append(f"Payment: {payment_type}")
        if show_customer_name and customer_name:
            lines.append(f"Customer: {customer_name}")
        lines.append("-" * 32)

        for name, qty, price, total_price in items:
            lines.append(name)
            lines.append(f"  {qty} x {format_money(price, symbol)} = {format_money(total_price, symbol)}")

        lines.append("-" * 32)
        subtotal = sum(item[3] for item in items)
        discount = discount_amt if discount_amt else 0.0
        lines.append(f"Subtotal: {format_money(subtotal, symbol)}")
        lines.append(f"Discount: -{format_money(discount, symbol)}")
        lines.append(f"Tax: 0")
        lines.append(f"Grand Total: {format_money(total, symbol)}")
        lines.append(f"Payment: {format_money(payment, symbol)}")
        lines.append(f"Change: {format_money(change, symbol)}")
        lines.append("-" * 32)
        if receipt_footer:
            lines.extend([line for line in receipt_footer.splitlines() if line.strip() != ""])
        lines.append("THANK YOU")
        return lines

    def get_shop_logo_path(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='shop_logo'")
            row = cursor.fetchone()
            conn.close()
            logo_path = row[0] if row else ""
            if logo_path and os.path.exists(logo_path):
                return logo_path
        except Exception:
            pass
        return ""

    def _send_cash_drawer_pulse(self, printer_name):
        """Send ESC/POS drawer kick command to a Windows printer queue."""
        drawer_kick_command = b"\x1b\x70\x00\x19\xfa"
        winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)

        class DOC_INFO_1(ctypes.Structure):
            _fields_ = [
                ("pDocName", ctypes.c_wchar_p),
                ("pOutputFile", ctypes.c_wchar_p),
                ("pDatatype", ctypes.c_wchar_p),
            ]

        h_printer = ctypes.c_void_p()
        if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(h_printer), None):
            raise ctypes.WinError(ctypes.get_last_error())

        try:
            doc_info = DOC_INFO_1("Open Cash Drawer", None, "RAW")
            if not winspool.StartDocPrinterW(h_printer, 1, ctypes.byref(doc_info)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not winspool.StartPagePrinter(h_printer):
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    written = ctypes.c_ulong(0)
                    buffer = ctypes.create_string_buffer(drawer_kick_command)
                    if not winspool.WritePrinter(
                        h_printer,
                        buffer,
                        len(drawer_kick_command),
                        ctypes.byref(written),
                    ):
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    winspool.EndPagePrinter(h_printer)
            finally:
                winspool.EndDocPrinter(h_printer)
        finally:
            winspool.ClosePrinter(h_printer)

    def _send_cash_drawer_command(self):
        """Open cash drawer using receipt printer settings."""
        use_receipt_printer = self.get_setting("receipt_cash_drawer_use_receipt_printer", "1") == "1"
        if use_receipt_printer:
            printer_name = self.selected_printer_name()
        else:
            default_printer = QPrinterInfo.defaultPrinter()
            if default_printer.isNull():
                return False
            printer_name = default_printer.printerName()

        if not printer_name:
            return False
        try:
            self._send_cash_drawer_pulse(printer_name)
            return True
        except Exception as e:
            print(f"Cash drawer open failed: {e}")
            return False

    def print_receipt(self):
        lines = self.build_text_lines()
        if not lines:
            QMessageBox.warning(self, "Print Error", "No receipt data.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer_name = self.selected_printer_name()
        if not printer_name:
            QMessageBox.warning(self, "Print Error", "No receipt printer found. Please check Receipt Settings.")
            return
        printer.setPrinterName(printer_name)

        try:
            page_size_accepted = self.configure_receipt_printer(printer)
        except Exception as e:
            page_size_accepted = False
            print(f"Custom page size failed: {e}")

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Print Error", "Cannot start painter. Check printer.")
            return

        try:
            font = QFont("Tahoma", 8)
            painter.setFont(font)
            fm = QFontMetrics(font)
            line_height = fm.height() + 26
            y = 20

            logo_path = self.get_shop_logo_path()
            if logo_path:
                logo = QPixmap(logo_path)
                if not logo.isNull():
                    text_width = max(fm.horizontalAdvance("=" * 32), fm.horizontalAdvance("W" * 24))
                    max_logo_width = text_width
                    max_logo_height = line_height * 4
                    scaled_logo = logo.scaled(
                        max_logo_width,
                        max_logo_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    logo_x = 10 + max(0, (text_width - scaled_logo.width()) // 2)
                    painter.drawPixmap(logo_x, y, scaled_logo)
                    y += scaled_logo.height() + line_height

            for line in lines:
                painter.drawText(10, y, line)
                y += line_height
        except Exception as e:
            QMessageBox.critical(self, "Print Error", f"Error while drawing: {e}")
        finally:
            painter.end()

        note = ""
        if not page_size_accepted:
            note = "\n\nNote: Printer driver did not accept the custom paper size. Check Windows printer preferences if paper feed is not correct."
        QMessageBox.information(self, "Print", f"Receipt sent to printer.\nPrinter: {printer_name}{note}")

    def close_without_drawer(self):
        """Close dialog without opening cash drawer"""
        self.cash_drawer_opened = False
        self.done(QDialog.DialogCode.Accepted)

    def close_with_drawer(self):
        """Close dialog and open cash drawer"""
        self.cash_drawer_opened = True
        
        # Try to open cash drawer using the same method as SalesPage
        success = self._send_cash_drawer_command()
        
        if success:
            QMessageBox.information(self, "Cash Drawer", "Cash drawer opened successfully!")
        else:
            QMessageBox.information(
                self, 
                "Cash Drawer", 
                "Please open the cash drawer manually."
            )
        
        self.done(QDialog.DialogCode.Accepted)

    def closeEvent(self, event):
        """Handle close event"""
        self.done(QDialog.DialogCode.Rejected)
        event.accept()


# Export the class for import
__all__ = ['ReceiptDialog']
