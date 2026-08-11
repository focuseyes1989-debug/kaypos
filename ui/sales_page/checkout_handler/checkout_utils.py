# ui/sales_page/checkout_handler/checkout_utils.py
import ctypes
import os
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt, QSizeF, QMarginsF
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QPixmap, QPageLayout, QPageSize
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.receipt_template import build_receipt_text_lines, load_receipt_template_settings
from utils.wholesale_pricing import ensure_wholesale_sale_item_columns
from loguru import logger


def load_customers():
    """Load customers from database"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, points FROM customers ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return rows


def send_cash_drawer_pulse(printer_name):
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


def open_cash_drawer(parent):
    """Open cash drawer using receipt printer from settings"""
    try:
        # Get printer name from settings (same as receipt printer)
        printer_name = get_setting("receipt_printer_name", "")
        
        if not printer_name:
            # Fallback to default printer
            default_printer = QPrinterInfo.defaultPrinter()
            if default_printer.isNull():
                logger.warning("Cash drawer open failed: no printer found")
                QMessageBox.warning(parent, "Cash Drawer", "No printer found. Please open manually.")
                return False
            printer_name = default_printer.printerName()
        
        send_cash_drawer_pulse(printer_name)
        logger.info(f"Cash drawer opened: {printer_name}")
        return True
    except Exception as e:
        logger.error(f"Cash drawer open failed: {e}")
        QMessageBox.warning(parent, "Cash Drawer", f"Failed to open cash drawer: {e}")
        return False


def get_setting(key, default=""):
    """Get setting from database"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default


def get_shop_logo_path():
    """Get shop logo path from database"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='shop_logo'")
        row = cursor.fetchone()
        conn.close()
        if row and row[0] and os.path.exists(row[0]):
            return row[0]
    except Exception as e:
        logger.error(f"Error loading logo: {e}")
    return ""


def build_receipt_text(invoice_no, created_at, total, payment, change, 
                       payment_type, discount_amt, customer_name, items):
    """Build receipt text lines - with proper spacing (compact version)"""
    sale = {
        "invoice_no": invoice_no,
        "created_at": created_at,
        "total": total,
        "payment": payment,
        "change": change,
        "payment_type": payment_type,
        "discount_amt": discount_amt,
        "customer_name": customer_name,
    }
    return build_receipt_text_lines(sale, items)

    lines = []
    symbol = get_currency_symbol()
    
    shop_name = get_setting("shop_name", "ZAY POS")
    receipt_header = get_setting("receipt_header", "")
    receipt_footer = get_setting("receipt_footer", "")
    show_customer_name = get_setting("show_customer_name", "1") == "1"
    footer_message = get_setting("shop_footer_message", "")
    
    # Header section (no extra empty lines)
    lines.append("=" * 32)
    lines.append(shop_name.center(32))
    lines.append("=" * 32)
    
    if receipt_header:
        for line in receipt_header.splitlines():
            if line.strip():
                lines.append(line.strip())
    
    lines.append("-" * 64)
    lines.append(f"Invoice : {invoice_no}")
    lines.append(f"Date    : {created_at}")
    lines.append(f"Payment : {payment_type}")
    if show_customer_name and customer_name:
        lines.append(f"Customer: {customer_name}")
    lines.append("-" * 64)
    
    # Items section
    lines.append("Items".center(32))
    
    for name, qty, price, total_price in items:
        lines.append(name)
        lines.append(f"  x{qty}           {format_money(price, symbol)}")
        # Remove empty line between items (more compact)
        # lines.append("")  # ← ဒီလိုင်းကို ဖယ်ထားပါ
    
    lines.append("-" * 64)
    
    # Totals section
    subtotal = sum(item[3] for item in items)
    discount = discount_amt if discount_amt else 0.0
    
    lines.append(f"{'Subtotal':<20} {format_money(subtotal, symbol):>28}")
    if discount > 0:
        lines.append(f"{'Discount':<20} -{format_money(discount, symbol):>27}")
    lines.append(f"{'Tax':<20} {format_money(0, symbol):>28}")
    lines.append("=" * 48)
    lines.append(f"{'GRAND TOTAL':<20} {format_money(total, symbol):>28}")
    lines.append("=" * 48)
    lines.append(f"{'Payment':<20} {format_money(payment, symbol):>28}")
    lines.append(f"{'Change':<20} {format_money(change, symbol):>28}")
    lines.append("-" * 48)
    
    # Footer section
    if receipt_footer:
        for line in receipt_footer.splitlines():
            if line.strip():
                lines.append(line.strip())
    
    if footer_message:
        for line in footer_message.splitlines():
            if line.strip():
                lines.append(line.strip())
    
    # Thank you message
    thank_you = "THANK YOU"
    padding = (48 - len(thank_you)) // 2
    lines.append(" " * padding + thank_you)
    lines.append("=" * 48)
    
    return lines

def print_receipt(parent, sale_id):
    """Print receipt directly using printer from receipt settings"""
    try:
        # Get sale data
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.invoice_no, s.created_at, s.total, s.payment, s.change_amount,
                   s.payment_type, s.discount_amount, c.name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = ?
        """, (sale_id,))
        sale = cursor.fetchone()
        if not sale:
            conn.close()
            return False
        
        invoice_no, created_at, total, payment, change, payment_type, discount_amt, customer_name = sale
        
        ensure_wholesale_sale_item_columns(cursor)
        conn.commit()
        cursor.execute("""
            SELECT product_name, qty, price, total,
                   COALESCE(wholesale_regular_price, 0),
                   COALESCE(wholesale_savings, 0),
                   COALESCE(wholesale_tier_min_qty, 0),
                   COALESCE(wholesale_unit_label, '')
            FROM sale_items
            WHERE sale_id = ?
        """, (sale_id,))
        items = cursor.fetchall()
        conn.close()
        
        # Build receipt text
        lines = build_receipt_text(invoice_no, created_at, total, payment, change, 
                                   payment_type, discount_amt, customer_name, items)
        
        # Get printer from receipt settings
        printer_name = get_setting("receipt_printer_name", "")
        
        if not printer_name:
            default_printer = QPrinterInfo.defaultPrinter()
            if default_printer.isNull():
                QMessageBox.warning(parent, "Print Error", "No printer found. Please check Receipt Settings.")
                return False
            printer_name = default_printer.printerName()
            logger.info(f"Using default printer: {printer_name}")
        else:
            logger.info(f"Using receipt printer from settings: {printer_name}")
        
        # Setup printer
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(printer_name)
        
        # Get paper size from settings
        paper_index = int(get_setting("receipt_paper_size", "0"))
        
        # Paper sizes
        paper_sizes = {
            0: (80.0, 297.0),   # 80mm
            1: (58.0, 297.0),   # 58mm
            2: None,            # A4
        }
        
        paper_size = paper_sizes.get(paper_index)
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
            QMarginsF(2, 2, 2, 2),  # ✅ margins 2mm
            QPageLayout.Unit.Millimeter,
        )
        printer.setPageLayout(page_layout)
        
        # Get print quality
        quality_dpi = int(get_setting("receipt_print_quality", "203"))
        printer.setResolution(quality_dpi)
        
        # Print
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.warning(parent, "Print Error", "Cannot start printer.")
            return False
        
        try:
            # ✅ Use Tahoma font (like receipt_dialog)
            font = QFont("Tahoma", 8)
            painter.setFont(font)
            fm = QFontMetrics(font)
            
            # ✅ Line height from receipt_dialog
            line_height = fm.height() + 26
            y = 20
            x = 10
            
            # Draw logo (CENTERED)
            template_settings = load_receipt_template_settings()
            logo_path = get_shop_logo_path()
            if template_settings.get("receipt_show_logo", "1") == "1" and logo_path:
                logo = QPixmap(logo_path)
                if not logo.isNull():
                    # Calculate text width for centering
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
            
            # Draw text lines
            for line in lines:
                painter.drawText(x, y, line)
                y += line_height
            
        finally:
            painter.end()
        
        logger.info(f"Receipt printed: {invoice_no} on {printer_name}")
        return True
        
    except Exception as e:
        logger.error(f"Print failed: {e}")
        QMessageBox.warning(parent, "Print Error", f"Failed to print: {e}")
        return False
