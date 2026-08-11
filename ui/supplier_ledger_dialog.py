# ui/supplier_ledger_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox,
    QDateEdit, QMessageBox, QGroupBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor, QPixmap
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.language import lang
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.date_range_widget import DateRangeWidget
from ui.widgets.modern_button import ModernButton
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import os


class SupplierLedgerDialog(QDialog):
    """Supplier Ledger Dialog - Theme-aware with SVG Icons"""
    
    def __init__(self, supplier_id=None, supplier_name=None, parent=None):
        super().__init__(parent)
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name
        self.all_entries = []
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle(f"Supplier Ledger - {supplier_name}" if supplier_name else "Supplier Ledger")
        self.setMinimumSize(1000, 650)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Filter section with DateRangeWidget and ModernButton
        filter_frame = QFrame()
        filter_frame.setObjectName("filter_frame")
        colors = get_theme_colors()
        filter_frame.setStyleSheet(self._get_filter_frame_style(colors))
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(12)
        filter_layout.setContentsMargins(15, 8, 15, 8)
        
        # Date Range Widget
        date_label = QLabel("📅 Date:")
        date_label.setStyleSheet(f"color: {colors['text']}; font-size: 10pt;")
        filter_layout.addWidget(date_label)
        
        self.date_range = DateRangeWidget(self)
        self.date_range.date_range_changed.connect(self.load_ledger)
        filter_layout.addWidget(self.date_range)
        
        # ✅ Refresh button with SVG icon
        self.btn_refresh = ModernButton(" Refresh", ModernButton.SECONDARY)
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_refresh.set_compact(True)
        self.btn_refresh.clicked.connect(self.load_ledger)
        filter_layout.addWidget(self.btn_refresh)
        
        # ✅ Make Payment button with SVG icon
        self.btn_payment = ModernButton(" Make Payment", ModernButton.PRIMARY)
        self.btn_payment.set_icon("payments", size=(16, 16))
        self.btn_payment.set_compact(True)
        self.btn_payment.clicked.connect(self.make_payment)
        filter_layout.addWidget(self.btn_payment)

        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        # Summary cards - Using SummaryCardWidget with SVG icons
        card_layout = QHBoxLayout()
        card_layout.setSpacing(15)
        
        # ✅ Total Purchases Card
        self.total_purchases_card = SummaryCardWidget(
            title="Total Purchases",
            value="0",
            icon="shopping_cart",
            color="#3498db",
            icon_is_svg=True
        )
        self.total_purchases_card.set_icon("shopping_cart", is_svg=True, size=(24, 24))
        card_layout.addWidget(self.total_purchases_card)
        
        # ✅ Total Paid Card
        self.total_paid_card = SummaryCardWidget(
            title="Total Paid",
            value="0",
            icon="payments",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.total_paid_card.set_icon("payments", is_svg=True, size=(24, 24))
        card_layout.addWidget(self.total_paid_card)
        
        # ✅ Balance Card
        self.balance_card = SummaryCardWidget(
            title="Balance",
            value="0",
            icon="analytics",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.balance_card.set_icon("analytics", is_svg=True, size=(24, 24))
        card_layout.addWidget(self.balance_card)
        
        layout.addLayout(card_layout)

        # Ledger table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Reference", "Type", "Debit (Purchase)", "Credit (Payment)", "Balance", "Notes"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # Apply table style
        self._update_table_style(colors)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # Pagination
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        # Buttons - Using ModernButton with SVG icons
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        # ✅ Print button with SVG icon
        self.btn_print = ModernButton(" Print Report", ModernButton.SECONDARY)
        self.btn_print.set_icon("print", size=(16, 16))
        self.btn_print.set_compact(False)
        self.btn_print.clicked.connect(self.print_report)
        btn_layout.addWidget(self.btn_print)
        
        btn_layout.addStretch()
        
        # ✅ Close button with SVG icon
        self.btn_close = ModernButton(" Close", ModernButton.TERTIARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addWidget(button_frame)

        self.setLayout(layout)

        # Apply initial theme
        self._apply_theme()
        
        self.load_ledger()
        self.retranslateUi()
    
    def _load_svg_icon(self, icon_name, size=(16, 16)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        # Try PNG fallback
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
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        return None
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.set_icon("refresh", size=(16, 16))
        if hasattr(self, 'btn_payment'):
            self.btn_payment.set_icon("payments", size=(16, 16))
        if hasattr(self, 'btn_print'):
            self.btn_print.set_icon("print", size=(16, 16))
        if hasattr(self, 'btn_close'):
            self.btn_close.set_icon("close", size=(16, 16))

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_ledger()
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update filter frame
        filter_frame = self.findChild(QFrame, "filter_frame")
        if filter_frame:
            filter_frame.setStyleSheet(self._get_filter_frame_style(colors))
        
        # Update filter labels
        for child in self.findChildren(QLabel):
            if child.parent() and child.parent().objectName() == "filter_frame":
                child.setStyleSheet(f"color: {colors['text']}; font-size: 10pt;")
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update table
        self._update_table_style(colors)
        
        # Update summary cards
        self.total_purchases_card.update_theme()
        self.total_paid_card.update_theme()
        self.balance_card.update_theme()
        
        # Update button icons
        self._update_button_icons()
    
    def _get_filter_frame_style(self, colors):
        return f"""
            QFrame#filter_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _update_table_style(self, colors):
        """Update table style based on theme"""
        is_dark = is_dark_theme()
        
        if is_dark:
            table_style = """
                QTableWidget {
                    background-color: #2f3136;
                    alternate-background-color: #36393f;
                    selection-background-color: #40444b;
                    selection-color: #dcddde;
                    gridline-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    color: #dcddde;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #dcddde;
                }
                QTableWidget::item:selected {
                    background-color: #40444b;
                    color: #dcddde;
                }
                QHeaderView::section {
                    background-color: #202225;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #40444b;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #b9bbbe;
                }
                QTableWidget::item:hover {
                    background-color: #40444b;
                }
            """
        else:
            table_style = """
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    selection-background-color: #e9ecef;
                    selection-color: #212529;
                    gridline-color: #dee2e6;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    color: #212529;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #212529;
                }
                QTableWidget::item:selected {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #2c3e50;
                }
                QTableWidget::item:hover {
                    background-color: #f1f3f5;
                }
            """
        
        self.table.setStyleSheet(table_style)

    def get_lang(self):
        return lang.get_current()

    def retranslateUi(self):
        lang_code = self.get_lang()
        colors = get_theme_colors()
        
        # Update date range widget
        self.date_range.retranslateUi(lang_code)
        
        # Update button icons
        self._update_button_icons()
        
        if lang_code == "my":
            self.setWindowTitle(f"ပေးသွင်းသူစာရင်း - {self.supplier_name}" if self.supplier_name else "ပေးသွင်းသူစာရင်း")
            self.total_purchases_card.set_title("စုစုပေါင်းဝယ်ယူမှု")
            self.total_paid_card.set_title("စုစုပေါင်းပေးချေမှု")
            self.balance_card.set_title("ကျန်ငွေ")
            self.btn_print.setText(" အစီရင်ခံစာထုတ်မည်")
            self.btn_close.setText(" ပိတ်မည်")
            self.btn_refresh.setText(" ပြန်လည်")
            self.btn_payment.setText(" ငွေပေးချေမည်")
            self.table.setHorizontalHeaderLabels([
                "ရက်စွဲ", "ကိုးကားအမှတ်", "အမျိုးအစား",
                "ဝယ်ယူမှု (အကြွေး)", "ငွေပေးချေမှု (အသွေး)", "ကျန်ငွေ", "မှတ်ချက်"
            ])
        else:
            self.setWindowTitle(f"Supplier Ledger - {self.supplier_name}" if self.supplier_name else "Supplier Ledger")
            self.total_purchases_card.set_title("Total Purchases")
            self.total_paid_card.set_title("Total Paid")
            self.balance_card.set_title("Balance")
            self.btn_print.setText(" Print Report")
            self.btn_close.setText(" Close")
            self.btn_refresh.setText(" Refresh")
            self.btn_payment.setText(" Make Payment")
            self.table.setHorizontalHeaderLabels([
                "Date", "Reference", "Type",
                "Debit (Purchase)", "Credit (Payment)", "Balance", "Notes"
            ])
        
        # Update card icons after language change
        self.total_purchases_card.set_icon("shopping_cart", is_svg=True, size=(24, 24))
        self.total_paid_card.set_icon("payments", is_svg=True, size=(24, 24))
        self.balance_card.set_icon("analytics", is_svg=True, size=(24, 24))
        
        # Update table with theme after language change
        self._update_table_style(colors)
        self.load_ledger()

    def on_page_changed(self, page: int, page_size: int):
        """Handle page change - display current page of entries"""
        self.display_entries(page, page_size)

    def display_entries(self, page=1, page_size=25):
        """Display entries for current page with theme-aware styling"""
        if not self.all_entries:
            self.table.setRowCount(0)
            return
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        start = (page - 1) * page_size
        end = start + page_size
        page_entries = self.all_entries[start:end]
        
        symbol = get_currency_symbol()
        self.table.setRowCount(0)
        
        # Calculate running balance up to this point
        running_balance = 0
        for entry in self.all_entries[:start]:
            running_balance += entry['debit'] - entry['credit']
        
        # Color definitions
        if is_dark:
            debit_color = "#3ba55d"  # Green for dark
            credit_color = "#ed4245"  # Red for dark
            balance_positive = "#ed4245"  # Red for dark
            balance_negative = "#3ba55d"  # Green for dark
            balance_zero = "#72767d"  # Gray for dark
            bg_positive = "#2d2d2d"
            bg_negative = "#2d2d2d"
            text_color = "#dcddde"
        else:
            debit_color = "#3498db"  # Blue for light
            credit_color = "#2ecc71"  # Green for light
            balance_positive = "#e74c3c"  # Red for light
            balance_negative = "#2ecc71"  # Green for light
            balance_zero = "#95a5a6"  # Gray for light
            bg_positive = "#fff0f0"
            bg_negative = "#f0fff0"
            text_color = "#212529"
        
        for entry in page_entries:
            running_balance += entry['debit'] - entry['credit']
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Date
            date_item = QTableWidgetItem(entry['date'])
            date_item.setForeground(QColor(text_color))
            self.table.setItem(row, 0, date_item)
            
            # Reference
            ref_item = QTableWidgetItem(entry['reference'])
            ref_item.setForeground(QColor(text_color))
            self.table.setItem(row, 1, ref_item)
            
            # Type
            type_item = QTableWidgetItem(entry['type'])
            if entry['type'] == 'Purchase Order':
                type_item.setForeground(QColor(debit_color))
            else:
                type_item.setForeground(QColor(credit_color))
            self.table.setItem(row, 2, type_item)
            
            # Debit
            debit_item = QTableWidgetItem(format_money(entry['debit'], symbol))
            if entry['debit'] > 0:
                debit_item.setForeground(QColor(debit_color))
            self.table.setItem(row, 3, debit_item)
            
            # Credit
            credit_item = QTableWidgetItem(format_money(entry['credit'], symbol))
            if entry['credit'] > 0:
                credit_item.setForeground(QColor(credit_color))
            self.table.setItem(row, 4, credit_item)
            
            # Balance
            balance_item = QTableWidgetItem(format_money(running_balance, symbol))
            if running_balance > 0:
                balance_item.setForeground(QColor(balance_positive))
                balance_item.setBackground(QColor(bg_positive))
            elif running_balance < 0:
                balance_item.setForeground(QColor(balance_negative))
                balance_item.setBackground(QColor(bg_negative))
            else:
                balance_item.setForeground(QColor(balance_zero))
            self.table.setItem(row, 5, balance_item)
            
            # Notes
            notes_item = QTableWidgetItem(entry['notes'])
            notes_item.setForeground(QColor(text_color))
            self.table.setItem(row, 6, notes_item)

    def load_ledger(self):
        """Load all ledger entries and setup pagination"""
        if not self.supplier_id:
            return

        from_date = self.date_range.get_from_date()
        to_date = self.date_range.get_to_date()

        conn = connect_db()
        cursor = conn.cursor()

        # Get all supplier payments/transactions
        cursor.execute("""
            SELECT 
                sp.payment_date as trans_date,
                sp.reference_no,
                CASE 
                    WHEN sp.payment_type = 'Purchase' THEN 'Purchase Order'
                    WHEN sp.payment_type IN ('Paid', 'Cash', 'Bank Transfer', 'Cheque', 'Mobile Money') THEN 'Payment'
                    ELSE sp.payment_type
                END as trans_type,
                CASE WHEN sp.payment_type = 'Purchase' THEN sp.amount ELSE 0 END as debit,
                CASE WHEN sp.payment_type != 'Purchase' THEN sp.amount ELSE 0 END as credit,
                sp.notes,
                sp.payment_type as original_type
            FROM supplier_payments sp
            WHERE sp.supplier_id = ? AND date(sp.payment_date) BETWEEN ? AND ?
            ORDER BY sp.payment_date
        """, (self.supplier_id, from_date, to_date))
        
        rows = cursor.fetchall()
        
        # If no data in supplier_payments, check purchase_orders table
        if not rows:
            cursor.execute("""
                SELECT 
                    po.order_date,
                    po.po_no,
                    'Purchase Order' as trans_type,
                    po.total_amount as debit,
                    0 as credit,
                    po.notes,
                    po.payment_status
                FROM purchase_orders po
                WHERE po.supplier_id = ? AND date(po.order_date) BETWEEN ? AND ?
                ORDER BY po.order_date
            """, (self.supplier_id, from_date, to_date))
            purchase_rows = cursor.fetchall()
            
            for row in purchase_rows:
                order_date, po_no, trans_type, debit, credit, notes, payment_status = row
                rows.append((order_date, po_no, trans_type, debit, credit, notes, payment_status))
        
        conn.close()

        # Calculate totals
        total_purchases = 0
        total_payments = 0
        entries = []

        for row in rows:
            if len(row) >= 7:
                trans_date, ref_no, trans_type, debit, credit, notes, original_type = row[:7]
            else:
                continue
                
            total_purchases += debit if debit else 0
            total_payments += credit if credit else 0
            entries.append({
                'date': trans_date,
                'reference': ref_no or "",
                'type': trans_type,
                'debit': debit if debit else 0,
                'credit': credit if credit else 0,
                'notes': notes or "",
                'original_type': original_type
            })

        # Sort entries by date
        entries.sort(key=lambda x: x['date'])
        
        # Store all entries for pagination
        self.all_entries = entries
        
        # Setup pagination
        total_items = len(entries)
        self.pagination.set_total_items(total_items, emit_signal=False)
        
        # Display first page
        self.display_entries(1, self.pagination._page_size)

        # Update summary cards
        balance = total_purchases - total_payments
        symbol = get_currency_symbol()
        
        self.total_purchases_card.set_value(format_money(total_purchases, symbol))
        self.total_paid_card.set_value(format_money(total_payments, symbol))
        self.balance_card.set_value(format_money(balance, symbol))
        
        # Update card colors based on balance
        if balance > 0:
            self.balance_card.set_color("#e74c3c")  # Red for positive balance (owe)
        elif balance < 0:
            self.balance_card.set_color("#2ecc71")  # Green for negative balance (overpaid)
        else:
            self.balance_card.set_color("#95a5a6")  # Gray for zero balance

    def make_payment(self):
        """Open payment dialog for this supplier"""
        from ui.supplier_payment_dialog import SupplierPaymentDialog
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN payment_type = 'Purchase' THEN amount ELSE 0 END), 0) as total_purchases,
                COALESCE(SUM(CASE WHEN payment_type != 'Purchase' THEN amount ELSE 0 END), 0) as total_payments
            FROM supplier_payments
            WHERE supplier_id = ?
        """, (self.supplier_id,))
        row = cursor.fetchone()
        
        if not row or (row[0] == 0 and row[1] == 0):
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as total_purchases
                FROM purchase_orders
                WHERE supplier_id = ?
            """, (self.supplier_id,))
            po_row = cursor.fetchone()
            total_purchases = po_row[0] if po_row else 0
            total_payments = 0
        else:
            total_purchases = row[0] if row else 0
            total_payments = row[1] if row else 0
        
        conn.close()
        
        current_balance = total_purchases - total_payments
        
        dialog = SupplierPaymentDialog(self.supplier_id, self.supplier_name, current_balance, self)
        if dialog.exec():
            self.load_ledger()

    def print_report(self):
        """Print all entries (not just current page)"""
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QPageLayout, QPageSize
        from PyQt6.QtWidgets import QFileDialog

        if not self.all_entries:
            lang_code = self.get_lang()
            msg = "No ledger entries to print." if lang_code != "my" else "ပရင့်ထုတ်ရန် စာရင်းမရှိပါ။"
            QMessageBox.warning(self, "No Data" if lang_code != "my" else "ဒေတာမရှိ", msg)
            return

        lang_code = self.get_lang()
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save PDF Report" if lang_code != "my" else "PDF အစီရင်ခံစာ သိမ်းရန်", 
            f"supplier_ledger_{self.supplier_name}.pdf", 
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Error", "Could not start PDF generation.")
            return

        font = QFont("Arial", 9)
        painter.setFont(font)
        fm = QFontMetrics(font)
        
        headers = ["Date", "Reference", "Type", "Debit", "Credit", "Balance", "Notes"]
        col_widths = [100, 120, 100, 100, 100, 100, 180]
        
        y = 30
        x = 20
        row_height = fm.height() + 6
        symbol = get_currency_symbol()

        # Title
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(20, y, f"Supplier Ledger - {self.supplier_name}")
        y += 30
        
        # Date range
        date_font = QFont("Arial", 10)
        painter.setFont(date_font)
        from_date = self.date_range.get_from_date()
        to_date = self.date_range.get_to_date()
        painter.drawText(20, y, f"Period: {from_date} to {to_date}")
        y += 25

        # Headers
        painter.setFont(font)
        for i, header in enumerate(headers):
            painter.drawText(x, y, col_widths[i], row_height, Qt.AlignmentFlag.AlignLeft, header)
            x += col_widths[i]
        
        y += row_height
        x = 20

        # Print all entries with running balance
        running_balance = 0
        for entry in self.all_entries:
            if y + row_height > printer.height() - 50:
                printer.newPage()
                y = 30
                for i, header in enumerate(headers):
                    painter.drawText(x, y, col_widths[i], row_height, Qt.AlignmentFlag.AlignLeft, header)
                    x += col_widths[i]
                y += row_height
                x = 20

            running_balance += entry['debit'] - entry['credit']
            
            painter.drawText(x, y, col_widths[0], row_height, Qt.AlignmentFlag.AlignLeft, entry['date'])
            painter.drawText(x + col_widths[0], y, col_widths[1], row_height, Qt.AlignmentFlag.AlignLeft, entry['reference'])
            painter.drawText(x + col_widths[0] + col_widths[1], y, col_widths[2], row_height, Qt.AlignmentFlag.AlignLeft, entry['type'])
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2], y, col_widths[3], row_height, Qt.AlignmentFlag.AlignLeft, format_money(entry['debit'], symbol))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], y, col_widths[4], row_height, Qt.AlignmentFlag.AlignLeft, format_money(entry['credit'], symbol))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], y, col_widths[5], row_height, Qt.AlignmentFlag.AlignLeft, format_money(running_balance, symbol))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4] + col_widths[5], y, col_widths[6], row_height, Qt.AlignmentFlag.AlignLeft, entry['notes'])
            
            y += row_height
            x = 20

        painter.end()
        
        lang_code = self.get_lang()
        msg = f"PDF saved to:\n{file_path}" if lang_code != "my" else f"PDF သိမ်းဆည်းပြီးပါပြီ:\n{file_path}"
        QMessageBox.information(self, "Export Complete" if lang_code != "my" else "သိမ်းဆည်းပြီးပါပြီ", msg)
    
    def showEvent(self, event):
        """Update button icons when dialog becomes visible"""
        self._update_button_icons()
        super().showEvent(event)