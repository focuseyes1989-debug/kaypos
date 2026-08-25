"""Original PyQt6 widget shell for KAY POS Lite Phase 1."""

from __future__ import annotations

import ctypes
from collections.abc import Callable

from PyQt6.QtCore import QMarginsF, QObject, QPointF, QRectF, QSizeF, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPageLayout, QPageSize, QPainter, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QFrame, QHeaderView, QHBoxLayout, QLabel,
    QInputDialog, QLineEdit, QMainWindow, QMessageBox, QPushButton as QtPushButton,
    QStackedWidget, QStyle, QStyleOptionButton, QStylePainter,
    QScrollArea, QSpinBox, QStatusBar, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from lite_pos.api import LiteApiClient
from lite_pos.cart import CartError, LiteCart, sold_by_mode
from lite_pos.config import load_config, save_config


def open_local_cash_drawer(printer_name: str) -> None:
    """Send the ESC/POS drawer pulse through a printer installed on this PC."""
    printer_name = str(printer_name or "").strip()
    if not printer_name:
        raise ValueError("Select a local receipt printer first.")
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [
            ("pDocName", ctypes.c_wchar_p),
            ("pOutputFile", ctypes.c_wchar_p),
            ("pDatatype", ctypes.c_wchar_p),
        ]

    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(handle), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = DOC_INFO_1("KAY POS Lite - Open Cash Drawer", None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not winspool.StartPagePrinter(handle):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                command = b"\x1b\x70\x00\x19\xfa"
                written = ctypes.c_ulong(0)
                buffer = ctypes.create_string_buffer(command)
                if not winspool.WritePrinter(handle, buffer, len(command), ctypes.byref(written)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                winspool.EndPagePrinter(handle)
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


class QPushButton(QtPushButton):
    """Native button chrome with text painted at the exact rectangle center."""

    def paintEvent(self, _event) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""
        painter = QStylePainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        color_group = (
            QPalette.ColorGroup.Active if self.isEnabled()
            else QPalette.ColorGroup.Disabled
        )
        painter.setPen(option.palette.color(color_group, QPalette.ColorRole.ButtonText))
        # Center the visible glyph pixels, not the font's asymmetric
        # ascent/descent box (important for Segoe UI and Myanmar fonts).
        bounds = painter.fontMetrics().tightBoundingRect(text)
        center = option.rect.center()
        origin = QPointF(
            center.x() - (bounds.width() / 2.0) - bounds.left(),
            center.y() - (bounds.height() / 2.0) - bounds.top(),
        )
        painter.drawText(origin, text)


class HorizontalWheelScrollArea(QScrollArea):
    """Scroll a single-row control strip horizontally with the mouse wheel."""

    def wheelEvent(self, event) -> None:
        delta = event.pixelDelta().y() or event.pixelDelta().x()
        if not delta:
            delta = event.angleDelta().y() or event.angleDelta().x()
        if delta:
            bar = self.horizontalScrollBar()
            step = delta if event.pixelDelta().isNull() is False else delta // 2
            bar.setValue(bar.value() - step)
            event.accept()
            return
        super().wheelEvent(event)


class TaskWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, operation: Callable):
        super().__init__()
        self.operation = operation

    def run(self):
        try:
            self.succeeded.emit(self.operation())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class CheckoutDialog(QDialog):
    def __init__(self, total: float, parent=None):
        super().__init__(parent)
        self.total = float(total)
        self.setWindowTitle("Checkout")
        self.setFixedWidth(390)
        layout = QVBoxLayout(self)
        title = QLabel(f"Total · {self.total:,.0f} Ks", objectName="title")
        layout.addWidget(title)
        form = QFormLayout()
        self.payment_type = QComboBox()
        self.payment_type.addItems(["Cash", "Card", "Mobile Money"])
        self.payment = QDoubleSpinBox()
        self.payment.setRange(0, 999999999999)
        self.payment.setDecimals(0)
        self.payment.setValue(self.total)
        self.payment.setSingleStep(1000)
        self.change_label = QLabel("0 Ks")
        form.addRow("Payment Type", self.payment_type)
        form.addRow("Payment", self.payment)
        form.addRow("Change", self.change_label)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Complete Sale")
        buttons.accepted.connect(self._accept_if_paid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.payment.valueChanged.connect(self._update_change)
        self.payment_type.currentTextChanged.connect(self._payment_type_changed)
        self._update_change()

    def _payment_type_changed(self, payment_type: str) -> None:
        if payment_type != "Cash":
            self.payment.setValue(self.total)
        self.payment.setEnabled(payment_type == "Cash")
        self._update_change()

    def _update_change(self) -> None:
        change = max(0.0, self.payment.value() - self.total)
        self.change_label.setText(f"{change:,.0f} Ks")

    def _accept_if_paid(self) -> None:
        if self.payment.value() < self.total:
            QMessageBox.warning(self, "Payment", "Payment is less than the sale total.")
            return
        self.accept()


class ReceiptDialog(QDialog):
    def __init__(self, receipt: dict, parent=None, refund_callback: Callable[[dict], None] | None = None):
        super().__init__(parent)
        self.receipt = receipt
        self.refund_callback = refund_callback
        self.setWindowTitle(f"Receipt · {receipt.get('invoice_no') or ''}")
        self.resize(520, 600)
        layout = QVBoxLayout(self)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setHtml(self._html())
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        print_button = buttons.addButton("Print Receipt", QDialogButtonBox.ButtonRole.ActionRole)
        print_button.clicked.connect(self.print_receipt)
        status = str(receipt.get("status") or "completed").lower()
        payment_type = str(receipt.get("payment_type") or "").lower()
        if refund_callback is not None and status == "completed" and payment_type != "credit":
            refund_button = buttons.addButton("Refund Receipt", QDialogButtonBox.ButtonRole.ActionRole)
            refund_button.clicked.connect(self.request_refund)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def request_refund(self) -> None:
        callback = self.refund_callback
        if callback is None:
            return
        self.accept()
        QTimer.singleShot(0, lambda: callback(self.receipt))

    def _html(self) -> str:
        from html import escape
        rows = "".join(
            f"<tr><td>{escape(str(item.get('product_name') or ''))}</td>"
            f"<td align='right'>{int(item.get('qty') or 0)}</td>"
            f"<td align='right'>{float(item.get('total') or 0):,.0f}</td></tr>"
            for item in self.receipt.get("items") or []
        )
        return (
            "<div style='font-family:Segoe UI,Myanmar Text;font-size:10pt'>"
            "<h2 style='text-align:center'>KAY POS</h2>"
            f"<p><b>Invoice:</b> {escape(str(self.receipt.get('invoice_no') or ''))}<br>"
            f"<b>Date:</b> {escape(str(self.receipt.get('created_at') or ''))}<br>"
            f"<b>Status:</b> {escape(str(self.receipt.get('status') or 'completed').title())}</p>"
            "<table width='100%' cellspacing='5'><tr><th align='left'>Item</th><th>Qty</th><th>Total</th></tr>"
            f"{rows}</table><hr>"
            f"<h3 style='text-align:right'>Total: {float(self.receipt.get('total') or 0):,.0f} Ks</h3>"
            f"<p style='text-align:right'>Payment: {float(self.receipt.get('payment') or 0):,.0f} Ks<br>"
            f"Change: {float(self.receipt.get('change_amount') or 0):,.0f} Ks</p></div>"
        )

    def print_receipt(self) -> None:
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo

        saved_name = load_config().get("receipt_printer_name") or ""
        saved_info = next(
            (info for info in QPrinterInfo.availablePrinters() if info.printerName() == saved_name),
            None,
        )
        printer = (
            QPrinter(saved_info, QPrinter.PrinterMode.HighResolution)
            if saved_info is not None else QPrinter(QPrinter.PrinterMode.HighResolution)
        )
        # GA-E200I is an 80 mm roll printer. Give the Windows dialog a compact
        # initial receipt page instead of inheriting an A4/very-long roll page.
        initial_page = QPageSize(
            QSizeF(80.0, 120.0), QPageSize.Unit.Millimeter,
            "80mm Receipt", QPageSize.SizeMatchPolicy.ExactMatch,
        )
        printer.setPageLayout(QPageLayout(
            initial_page, QPageLayout.Orientation.Portrait,
            QMarginsF(4.0, 3.0, 4.0, 4.0), QPageLayout.Unit.Millimeter,
        ))
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            document = QTextDocument()
            document.setDocumentMargin(0)
            document.setHtml(self._html())

            # QTextDocument lays text out in 96-DPI logical pixels. Measure the
            # rendered content first, then make the roll page only that tall.
            logical_dpi = 96.0
            printable_width_mm = 72.0
            logical_width = printable_width_mm * logical_dpi / 25.4
            document.setTextWidth(logical_width)
            content_height = document.documentLayout().documentSize().height()
            content_height_mm = content_height * 25.4 / logical_dpi
            page_height_mm = max(55.0, min(500.0, content_height_mm + 9.0))
            receipt_page = QPageSize(
                QSizeF(80.0, page_height_mm), QPageSize.Unit.Millimeter,
                "80mm Receipt", QPageSize.SizeMatchPolicy.ExactMatch,
            )
            printer.setPageLayout(QPageLayout(
                receipt_page, QPageLayout.Orientation.Portrait,
                QMarginsF(4.0, 3.0, 4.0, 4.0), QPageLayout.Unit.Millimeter,
            ))

            # Draw the document ourselves. QTextDocument.print() paginates and
            # adds a page number, which can make roll drivers feed to page end.
            painter = QPainter(printer)
            if not painter.isActive():
                QMessageBox.critical(self, "Print Receipt", "Could not start the selected printer.")
                return
            scale = printer.resolution() / logical_dpi
            paint_rect = printer.pageLayout().paintRectPixels(printer.resolution())
            painter.translate(paint_rect.left(), paint_rect.top())
            painter.scale(scale, scale)
            document.drawContents(
                painter,
                QRectF(0.0, 0.0, logical_width, content_height),
            )
            painter.end()


class LiteWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KAY POS Lite")
        self.resize(1180, 680)
        self.setMinimumSize(960, 600)
        self.api: LiteApiClient | None = None
        self.user: dict = {}
        self.products: list[dict] = []
        self.selected_category = ""
        self.receipts: list[dict] = []
        self.last_receipt: dict = {}
        self.history_offset = 0
        self.cart = LiteCart()
        self._threads: set[QThread] = set()
        self._workers: set[TaskWorker] = set()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350)
        self.search_timer.timeout.connect(self.load_products)

        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.login_page = self._build_login_page()
        self.workspace_page = self._build_workspace_page()
        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.workspace_page)
        # Keep the Lite edition on the operating system's native Qt style.
        # StyledPanel supplies a native group boundary without custom CSS.
        for frame in self.findChildren(QFrame):
            if frame.objectName() in {"card", "nav"}:
                frame.setFrameShape(QFrame.Shape.StyledPanel)
                frame.setFrameShadow(QFrame.Shadow.Plain)
        status = QStatusBar()
        self.setStatusBar(status)
        self.statusBar().showMessage("Ready")
        self._shortcuts = []
        self._add_shortcut("Ctrl+P", self.print_last_receipt)
        self._add_shortcut("Ctrl+Shift+D", self.open_cash_drawer)
        self._add_shortcut("Ctrl+Shift+P", self.configure_receipt_printer)

    def _add_shortcut(self, sequence: str, callback: Callable) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addStretch()
        card = QFrame(objectName="card")
        card.setMaximumWidth(440)
        body = QVBoxLayout(card)
        body.setContentsMargins(28, 24, 28, 24)
        body.setSpacing(10)
        brand = QLabel("KAY POS LITE", objectName="brand")
        title = QLabel("Sign in", objectName="title")
        subtitle = QLabel("Connect to your existing KAY POS Server and PostgreSQL data.", objectName="muted")
        subtitle.setWordWrap(True)
        body.addWidget(brand)
        body.addWidget(title)
        body.addWidget(subtitle)

        config = load_config()
        form = QFormLayout()
        self.server_input = QLineEdit(config["server_url"])
        self.server_input.setPlaceholderText("https://192.168.1.10:8000")
        self.username_input = QLineEdit(config["remember_username"])
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.login)
        form.addRow("Server URL", self.server_input)
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)
        body.addLayout(form)
        self.insecure_check = QCheckBox("Allow self-signed HTTPS certificate")
        self.insecure_check.setChecked(config["insecure_tls"])
        body.addWidget(self.insecure_check)
        self.login_status = QLabel("", objectName="muted")
        self.login_status.setWordWrap(True)
        body.addWidget(self.login_status)
        buttons = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        self.login_button = QPushButton("Sign In", objectName="primary")
        self.login_button.clicked.connect(self.login)
        buttons.addWidget(self.test_button)
        buttons.addStretch()
        buttons.addWidget(self.login_button)
        body.addLayout(buttons)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()
        return page

    def _build_workspace_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        nav = QFrame(objectName="nav")
        nav.setFixedWidth(180)
        menu = QVBoxLayout(nav)
        menu.setContentsMargins(12, 17, 12, 14)
        menu.addWidget(QLabel("KAY POS LITE", objectName="brand"))
        menu.addSpacing(14)
        for text in ("Dashboard", "Point of Sale", "Sales History", "Stock & Customers"):
            button = QPushButton(text)
            if text == "Dashboard":
                button.clicked.connect(self.open_dashboard)
            elif text == "Point of Sale":
                button.clicked.connect(lambda: self.workspace_stack.setCurrentWidget(self.pos_page))
            elif text == "Sales History":
                button.clicked.connect(self.open_sales_history)
            else:
                button.clicked.connect(self.open_management)
            menu.addWidget(button)
        menu.addStretch()
        self.identity_label = QLabel("")
        self.identity_label.setWordWrap(True)
        menu.addWidget(self.identity_label)
        logout = QPushButton("Sign Out")
        logout.clicked.connect(self.logout)
        menu.addWidget(logout)
        row.addWidget(nav)

        self.workspace_stack = QStackedWidget()
        self.dashboard_page = QWidget()
        content_layout = QVBoxLayout(self.dashboard_page)
        content_layout.setContentsMargins(22, 20, 22, 18)
        title = QLabel("Lite Workspace", objectName="title")
        self.welcome_label = QLabel("")
        self.welcome_label.setObjectName("muted")
        content_layout.addWidget(title)
        content_layout.addWidget(self.welcome_label)
        content_layout.addSpacing(12)
        card = QFrame(objectName="card")
        card_body = QVBoxLayout(card)
        card_body.setContentsMargins(18, 16, 18, 16)
        summary_top = QHBoxLayout()
        summary_top.addWidget(QLabel("Today · PostgreSQL live summary"))
        summary_top.addStretch()
        refresh_summary = QPushButton("Refresh")
        refresh_summary.clicked.connect(self.load_dashboard)
        summary_top.addWidget(refresh_summary)
        card_body.addLayout(summary_top)
        metrics = QHBoxLayout()
        self.dashboard_sales = QLabel("Sales\n—", objectName="title")
        self.dashboard_transactions = QLabel("Transactions\n—", objectName="title")
        self.dashboard_refunds = QLabel("Refunds\n—", objectName="title")
        self.dashboard_low_stock = QLabel("Low Stock\n—", objectName="title")
        for metric in (self.dashboard_sales, self.dashboard_transactions, self.dashboard_refunds, self.dashboard_low_stock):
            metric.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metrics.addWidget(metric, 1)
        card_body.addLayout(metrics)
        content_layout.addWidget(card)
        content_layout.addStretch()
        self.pos_page = self._build_pos_page()
        self.history_page = self._build_history_page()
        self.management_page = self._build_management_page()
        self.workspace_stack.addWidget(self.dashboard_page)
        self.workspace_stack.addWidget(self.pos_page)
        self.workspace_stack.addWidget(self.history_page)
        self.workspace_stack.addWidget(self.management_page)
        row.addWidget(self.workspace_stack, 1)
        return page

    def _build_management_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Stock & Customers", objectName="title"))
        self.management_search = QLineEdit()
        self.management_search.setPlaceholderText("Search products and customers…")
        self.management_search.returnPressed.connect(self.load_management)
        refresh = QPushButton("Search / Refresh")
        refresh.clicked.connect(self.load_management)
        top.addStretch()
        top.addWidget(self.management_search, 1)
        top.addWidget(refresh)
        outer.addLayout(top)
        tables = QHBoxLayout()
        stock_box = QFrame(objectName="card")
        stock_layout = QVBoxLayout(stock_box)
        stock_layout.setContentsMargins(9, 9, 9, 9)
        stock_layout.addWidget(QLabel("Products & Stock"))
        self.stock_table = QTableWidget(0, 4)
        self.stock_table.setHorizontalHeaderLabels(["Product", "Barcode / SKU", "Stock", "Variants"])
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stock_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.verticalHeader().setDefaultSectionSize(29)
        self.stock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.stock_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        stock_layout.addWidget(self.stock_table, 1)
        stock_actions = QHBoxLayout()
        stock_in = QPushButton("Stock In")
        stock_out = QPushButton("Stock Out")
        stock_in.clicked.connect(lambda: self.adjust_selected_stock(1))
        stock_out.clicked.connect(lambda: self.adjust_selected_stock(-1))
        stock_actions.addWidget(stock_in)
        stock_actions.addWidget(stock_out)
        stock_actions.addStretch()
        stock_layout.addLayout(stock_actions)
        tables.addWidget(stock_box, 3)

        customer_box = QFrame(objectName="card")
        customer_layout = QVBoxLayout(customer_box)
        customer_layout.setContentsMargins(9, 9, 9, 9)
        customer_layout.addWidget(QLabel("Customers"))
        self.customer_table = QTableWidget(0, 4)
        self.customer_table.setHorizontalHeaderLabels(["Name", "Phone", "Points", "Balance"])
        self.customer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.customer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.customer_table.verticalHeader().setVisible(False)
        self.customer_table.verticalHeader().setDefaultSectionSize(29)
        self.customer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.customer_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        customer_layout.addWidget(self.customer_table, 1)
        tables.addWidget(customer_box, 2)
        outer.addLayout(tables, 1)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Sales History", objectName="title"))
        top.addStretch()
        self.history_status = QLabel("", objectName="muted")
        top.addWidget(self.history_status)
        outer.addLayout(top)
        filters = QHBoxLayout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search invoice, customer or payment type…")
        self.history_search.returnPressed.connect(self.search_history)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_history)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load_history)
        filters.addWidget(self.history_search, 1)
        filters.addWidget(search_button)
        filters.addWidget(refresh)
        outer.addLayout(filters)
        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels([
            "Invoice", "Date", "Customer", "Payment", "Items", "Total", "Status",
        ])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(27)
        self.history_table.horizontalHeader().setFixedHeight(27)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (1, 3, 4, 5, 6):
            self.history_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.doubleClicked.connect(self.view_selected_receipt)
        outer.addWidget(self.history_table, 1)
        actions = QHBoxLayout()
        view = QPushButton("View / Reprint")
        refund = QPushButton("Full Refund")
        self.history_prev = QPushButton("Previous")
        self.history_next = QPushButton("Next")
        view.clicked.connect(self.view_selected_receipt)
        refund.clicked.connect(self.refund_selected_sale)
        self.history_prev.clicked.connect(lambda: self.change_history_page(-50))
        self.history_next.clicked.connect(lambda: self.change_history_page(50))
        actions.addWidget(view)
        actions.addWidget(refund)
        actions.addStretch()
        actions.addWidget(self.history_prev)
        actions.addWidget(self.history_next)
        outer.addLayout(actions)
        return page

    def _build_pos_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(QLabel("Point of Sale", objectName="title"))
        heading.addStretch()
        self.catalog_status = QLabel("0 products", objectName="muted")
        heading.addWidget(self.catalog_status)
        outer.addLayout(heading)

        search_row = QHBoxLayout()
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Search name, SKU or barcode…")
        self.product_search.textChanged.connect(lambda: self.search_timer.start())
        self.product_search.returnPressed.connect(self.scan_or_search)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load_products)
        search_row.addWidget(self.product_search, 1)
        search_row.addWidget(refresh)
        outer.addLayout(search_row)

        category_row = QHBoxLayout()
        category_row.setSpacing(0)
        self.category_scroll = HorizontalWheelScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setFixedHeight(34)
        self.category_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.category_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.category_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.category_container = QWidget()
        self.category_layout = QHBoxLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 1, 0, 1)
        self.category_layout.setSpacing(6)
        self.category_layout.addStretch()
        self.category_scroll.setWidget(self.category_container)
        category_row.addWidget(self.category_scroll, 1)
        outer.addLayout(category_row)

        body = QHBoxLayout()
        self.product_table = QTableWidget(0, 5)
        self.product_table.setHorizontalHeaderLabels(["Product", "Barcode / SKU", "Price", "Stock", "Variants"])
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.product_table.verticalHeader().setVisible(False)
        self.product_table.verticalHeader().setDefaultSectionSize(27)
        self.product_table.horizontalHeader().setFixedHeight(27)
        self.product_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.product_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.product_table.doubleClicked.connect(self.add_selected_product)
        body.addWidget(self.product_table, 3)

        cart_panel = QFrame(objectName="card")
        cart_panel.setMinimumWidth(300)
        cart_panel.setMaximumWidth(390)
        cart_layout = QVBoxLayout(cart_panel)
        cart_layout.setContentsMargins(10, 10, 10, 10)
        cart_layout.setSpacing(7)
        cart_top = QHBoxLayout()
        cart_top.addWidget(QLabel("Current Cart"))
        cart_top.addStretch()
        self.cart_count_label = QLabel("0 items", objectName="muted")
        cart_top.addWidget(self.cart_count_label)
        cart_layout.addLayout(cart_top)
        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["Item", "Qty", "Price", "Total"])
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(30)
        self.cart_table.horizontalHeader().setFixedHeight(27)
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            self.cart_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        cart_layout.addWidget(self.cart_table, 1)
        controls = QHBoxLayout()
        decrease = QPushButton("−")
        increase = QPushButton("+")
        remove = QPushButton("Remove")
        clear = QPushButton("Clear")
        decrease.clicked.connect(lambda: self.change_cart_quantity(-1))
        increase.clicked.connect(lambda: self.change_cart_quantity(1))
        remove.clicked.connect(self.remove_cart_item)
        clear.clicked.connect(self.clear_cart)
        for button in (decrease, increase, remove, clear):
            controls.addWidget(button)
        cart_layout.addLayout(controls)
        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total"))
        total_row.addStretch()
        self.cart_total_label = QLabel("0 Ks", objectName="title")
        total_row.addWidget(self.cart_total_label)
        cart_layout.addLayout(total_row)
        self.checkout_button = QPushButton("Checkout", objectName="primary")
        self.checkout_button.setEnabled(False)
        self.checkout_button.clicked.connect(self.open_checkout)
        cart_layout.addWidget(self.checkout_button)
        receipt_actions = QHBoxLayout()
        self.print_receipt_button = QPushButton("Print Receipt")
        self.print_receipt_button.setEnabled(False)
        self.print_receipt_button.setToolTip("Print the last receipt (Ctrl+P)")
        self.print_receipt_button.clicked.connect(self.print_last_receipt)
        self.cash_drawer_button = QPushButton("Cash Drawer")
        self.cash_drawer_button.setToolTip("Open the drawer through this PC's receipt printer (Ctrl+Shift+D)")
        self.cash_drawer_button.clicked.connect(self.open_cash_drawer)
        printer_setup = QPushButton("Printer…")
        printer_setup.setToolTip("Select local receipt printer (Ctrl+Shift+P)")
        printer_setup.clicked.connect(self.configure_receipt_printer)
        receipt_actions.addWidget(self.print_receipt_button)
        receipt_actions.addWidget(self.cash_drawer_button)
        receipt_actions.addWidget(printer_setup)
        cart_layout.addLayout(receipt_actions)
        body.addWidget(cart_panel, 2)
        outer.addLayout(body, 1)
        return page

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.login_button.setDisabled(busy)
        self.test_button.setDisabled(busy)
        self.login_status.setText(message)

    def _run_task(self, operation: Callable, success: Callable, failure: Callable[[str], None]) -> None:
        thread = QThread(self)
        worker = TaskWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(success)
        worker.failed.connect(failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: self._workers.discard(worker))
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._threads.discard(thread))
        self._threads.add(thread)
        # A moved QObject is not owned by QThread. Keep a Python reference until
        # its finished signal fires or it may be collected before run() starts.
        self._workers.add(worker)
        thread.start()

    def _new_api(self) -> LiteApiClient:
        return LiteApiClient(self.server_input.text(), self.insecure_check.isChecked())

    def test_connection(self) -> None:
        self._set_busy(True, "Testing server connection…")
        client = self._new_api()
        def connected(_data):
            self.server_input.setText(client.server_url)
            save_config({
                "server_url": client.server_url,
                "insecure_tls": self.insecure_check.isChecked(),
                "remember_username": self.username_input.text().strip(),
            })
            self._set_busy(False, "Server is connected and ready.")
            self.statusBar().showMessage("Server connected")

        self._run_task(client.health, connected, lambda error: self._set_busy(False, error))

    def login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.login_status.setText("Username and password are required.")
            return
        self._set_busy(True, "Signing in…")
        client = self._new_api()

        def authenticate():
            user = client.login(username, password)
            confirmed = client.current_user()
            return confirmed or user

        def accepted(user):
            self.api = client
            self.user = dict(user)
            save_config({
                "server_url": client.server_url,
                "insecure_tls": self.insecure_check.isChecked(),
                "remember_username": username,
            })
            self.password_input.clear()
            self._set_busy(False, "")
            name = self.user.get("full_name") or self.user.get("username") or "User"
            role = self.user.get("role") or "User"
            self.identity_label.setText(f"{name}\nRole: {role}")
            self.welcome_label.setText(f"Welcome, {name}. Connected as {role}.")
            self.pages.setCurrentWidget(self.workspace_page)
            self.statusBar().showMessage(f"Connected · {client.server_url}")
            self.workspace_stack.setCurrentWidget(self.pos_page)
            QTimer.singleShot(100, self.load_categories)

        self._run_task(authenticate, accepted, lambda error: self._set_busy(False, error))

    def load_products(self) -> None:
        if not self.api or self._threads:
            return
        query = self.product_search.text().strip()
        category = self.selected_category
        self.catalog_status.setText("Loading…")

        def loaded(products):
            if self.product_search.text().strip() != query or self.selected_category != category:
                QTimer.singleShot(100, self.load_products)
                return
            self.products = list(products)
            self.product_table.setRowCount(len(self.products))
            for row, product in enumerate(self.products):
                variants = product.get("variants") or []
                mode = sold_by_mode(product.get("sold_by"))
                display_stock = (
                    "Service" if mode == "service"
                    else sum(int(variant.get("stock") or 0) for variant in variants)
                    if mode == "variants" and variants
                    else int(product.get("stock") or 0)
                )
                values = (
                    product.get("name") or "",
                    product.get("barcode") or product.get("sku") or "—",
                    f"{float(product.get('price') or 0):,.0f} Ks",
                    str(display_stock),
                    str(len(variants)) if variants else "—",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column in (2, 3, 4):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.product_table.setItem(row, column, item)
            self.catalog_status.setText(f"{len(self.products)} products")
            self.statusBar().showMessage("Product list ready")

        def failed(error):
            self.catalog_status.setText("Could not load products")
            self.statusBar().showMessage(error)

        self._run_task(lambda: self.api.products(query, limit=60, category=category), loaded, failed)

    def load_categories(self) -> None:
        if not self.api:
            return
        if self._threads:
            QTimer.singleShot(100, self.load_categories)
            return

        def loaded(categories):
            self._render_categories(categories)
            QTimer.singleShot(100, self.load_products)

        self._run_task(self.api.categories, loaded, lambda error: self.statusBar().showMessage(error))

    def _render_categories(self, categories: list[str]) -> None:
        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        for label, value in [("All", ""), *((name, name) for name in categories)]:
            button = QPushButton(label)
            button.setObjectName("categoryButton")
            button.setCheckable(True)
            button.setChecked(value == self.selected_category)
            button.clicked.connect(lambda _checked=False, category=value: self.select_category(category))
            self.category_group.addButton(button)
            self.category_layout.addWidget(button)
        self.category_layout.addStretch()
        self.category_container.adjustSize()

    def select_category(self, category: str) -> None:
        if self.selected_category == category:
            return
        self.selected_category = category
        self.load_products()

    def scan_or_search(self) -> None:
        if not self.api or self._threads:
            return
        code = self.product_search.text().strip()
        if not code:
            self.load_products()
            return
        self.catalog_status.setText("Scanning…")

        def scanned(product):
            if not product:
                self.load_products()
                return
            self.products = [product]
            self.product_table.setRowCount(1)
            values = (
                product.get("name") or "", product.get("barcode") or product.get("sku") or "—",
                f"{float(product.get('price') or 0):,.0f} Ks", str(int(product.get("stock") or 0)),
                str(len(product.get("variants") or [])) or "—",
            )
            for column, value in enumerate(values):
                self.product_table.setItem(0, column, QTableWidgetItem(str(value)))
            matched_id = product.get("matched_variant_id")
            matched = next((v for v in product.get("variants") or [] if int(v.get("variant_id") or 0) == int(matched_id or 0)), None)
            self._add_product_to_cart(product, matched, select_variant=matched_id is None)
            self.product_search.clear()
            self.catalog_status.setText("Barcode added")

        self._run_task(lambda: self.api.scan_product(code), scanned, lambda error: self.statusBar().showMessage(error))

    def add_selected_product(self) -> None:
        row = self.product_table.currentRow()
        if row < 0 or row >= len(self.products):
            return
        self._add_product_to_cart(self.products[row], None, select_variant=True)

    def _select_variant(self, product: dict) -> dict | None:
        variants = list(product.get("variants") or [])
        if not variants:
            return None
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Variant · {product.get('name') or ''}")
        dialog.resize(620, 340)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(variants), 5)
        table.setHorizontalHeaderLabels(["Color", "Size", "Barcode / SKU", "Price", "Stock"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for row, variant in enumerate(variants):
            values = (
                variant.get("color") or "—", variant.get("size") or "—",
                variant.get("barcode") or variant.get("sku") or "—",
                f"{float(variant.get('price') or product.get('price') or 0):,.0f} Ks",
                str(int(variant.get("stock") or 0)),
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        if variants:
            table.selectRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        table.doubleClicked.connect(lambda: dialog.accept())
        layout.addWidget(table)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted or table.currentRow() < 0:
            return {}
        return variants[table.currentRow()]

    def _add_product_to_cart(self, product: dict, variant: dict | None, *, select_variant: bool) -> None:
        variants = product.get("variants") or []
        mode = sold_by_mode(product.get("sold_by"))
        if mode == "variants" and not variants:
            QMessageBox.warning(self, "Variants", "This product has no active variants to sell.")
            return
        if variants and select_variant:
            variant = self._select_variant(product)
            if variant == {}:
                return
        if mode == "variants" and not variant:
            QMessageBox.warning(self, "Variants", "Select a variant before adding this product.")
            return
        product_for_cart = product
        if mode == "service":
            price, accepted = QInputDialog.getDouble(
                self,
                "Service Price",
                f"Enter price for {product.get('name') or 'service'}:",
                float(product.get("price") or 0),
                0,
                999999999,
                2,
            )
            if not accepted:
                return
            product_for_cart = dict(product)
            product_for_cart["price"] = float(price)
        try:
            self.cart.add(product_for_cart, variant)
            self.render_cart()
            self.statusBar().showMessage(f"Added {product.get('name') or 'product'}")
        except CartError as exc:
            QMessageBox.warning(self, "Stock", str(exc))

    def _selected_cart_key(self) -> str:
        row = self.cart_table.currentRow()
        keys = list(self.cart.items)
        return keys[row] if 0 <= row < len(keys) else ""

    def change_cart_quantity(self, delta: int) -> None:
        key = self._selected_cart_key()
        if not key:
            return
        try:
            self.cart.change(key, delta)
            self.render_cart()
        except CartError as exc:
            QMessageBox.warning(self, "Stock", str(exc))

    def remove_cart_item(self) -> None:
        key = self._selected_cart_key()
        if key:
            self.cart.items.pop(key, None)
            self.render_cart()

    def clear_cart(self) -> None:
        self.cart.clear()
        self.render_cart()

    def render_cart(self) -> None:
        items = list(self.cart.items.values())
        self.cart_table.setRowCount(len(items))
        for row, item in enumerate(items):
            name = item["name"] + (f"\n{item['variant_label']}" if item.get("variant_label") else "")
            values = (name, str(item["qty"]), f"{item['price']:,.0f}", f"{item['price'] * item['qty']:,.0f}")
            for column, value in enumerate(values):
                self.cart_table.setItem(row, column, QTableWidgetItem(value))
        self.cart_count_label.setText(f"{self.cart.count()} items")
        self.cart_total_label.setText(f"{self.cart.total():,.0f} Ks")
        self.checkout_button.setEnabled(bool(items) and not self._threads)

    def open_checkout(self) -> None:
        if not self.api or not self.cart.items or self._threads:
            return
        dialog = CheckoutDialog(self.cart.total(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        items = [
            {
                "product_id": item["product_id"], "variant_id": item.get("variant_id"),
                "qty": item["qty"], "manual_price": item["price"] if item.get("is_service") else None,
            }
            for item in self.cart.items.values()
        ]
        payment = dialog.payment.value()
        payment_type = dialog.payment_type.currentText()
        self.checkout_button.setEnabled(False)
        self.checkout_button.setText("Saving sale…")
        self.statusBar().showMessage("Completing sale securely…")

        def completed(receipt):
            self.cart.clear()
            self.render_cart()
            self.checkout_button.setText("Checkout")
            self.last_receipt = dict(receipt)
            self.print_receipt_button.setEnabled(True)
            self.statusBar().showMessage(f"Sale completed · {receipt.get('invoice_no') or ''}")
            ReceiptDialog(receipt, self).exec()
            QTimer.singleShot(100, self.load_products)

        def failed(error):
            self.checkout_button.setText("Checkout")
            self.checkout_button.setEnabled(bool(self.cart.items))
            self.statusBar().showMessage("Checkout failed")
            QMessageBox.critical(self, "Checkout", error)

        self._run_task(lambda: self.api.checkout(items, payment, payment_type), completed, failed)

    def print_last_receipt(self) -> None:
        if not self.last_receipt:
            QMessageBox.information(self, "Print Receipt", "No completed receipt is available to print yet.")
            return
        ReceiptDialog(self.last_receipt, self).print_receipt()

    def open_cash_drawer(self) -> None:
        if self._threads:
            return
        printer_name = str(load_config().get("receipt_printer_name") or "")
        if not printer_name:
            printer_name = self.configure_receipt_printer()
            if not printer_name:
                return
        self.cash_drawer_button.setEnabled(False)
        self.statusBar().showMessage("Opening cash drawer…")

        def opened(_result):
            self.cash_drawer_button.setEnabled(True)
            self.statusBar().showMessage(f"Cash drawer opened · {printer_name}")

        def failed(error):
            self.cash_drawer_button.setEnabled(True)
            self.statusBar().showMessage("Could not open cash drawer")
            QMessageBox.warning(self, "Cash Drawer", error)

        self._run_task(lambda: open_local_cash_drawer(printer_name), opened, failed)

    def configure_receipt_printer(self) -> str:
        from PyQt6.QtPrintSupport import QPrinterInfo

        names = QPrinterInfo.availablePrinterNames()
        if not names:
            QMessageBox.warning(
                self, "Receipt Printer",
                "No Windows printers are installed on this PC. Install the GA-E200I driver first.",
            )
            return ""
        current = str(load_config().get("receipt_printer_name") or "")
        current_index = names.index(current) if current in names else 0
        selected, accepted = QInputDialog.getItem(
            self, "Local Receipt Printer", "Printer:", names, current_index, False,
        )
        if not accepted or not selected:
            return ""
        save_config({"receipt_printer_name": selected})
        self.statusBar().showMessage(f"Local receipt printer · {selected}")
        return str(selected)

    def open_sales_history(self) -> None:
        self.workspace_stack.setCurrentWidget(self.history_page)
        self.history_offset = 0
        self.load_history()

    def open_dashboard(self) -> None:
        self.workspace_stack.setCurrentWidget(self.dashboard_page)
        self.load_dashboard()

    def load_dashboard(self) -> None:
        if not self.api:
            return
        if self._threads:
            QTimer.singleShot(150, self.load_dashboard)
            return
        from datetime import date
        today = date.today().isoformat()

        def loaded(data):
            current = data.get("today") or {}
            self.dashboard_sales.setText(f"Sales\n{float(current.get('sales') or 0):,.0f} Ks")
            self.dashboard_transactions.setText(f"Transactions\n{int(current.get('transactions') or 0)}")
            self.dashboard_refunds.setText(f"Refunds\n{float(current.get('refunds') or 0):,.0f} Ks")
            self.dashboard_low_stock.setText(f"Low Stock\n{int((data.get('inventory') or {}).get('low_stock') or 0)}")
            self.statusBar().showMessage("Today’s summary refreshed")

        self._run_task(
            lambda: self.api.dashboard_summary(today), loaded,
            lambda error: self.statusBar().showMessage(error),
        )

    def open_management(self) -> None:
        self.workspace_stack.setCurrentWidget(self.management_page)
        self.load_management()

    def load_management(self) -> None:
        if not self.api:
            return
        if self._threads:
            QTimer.singleShot(150, self.load_management)
            return
        query = self.management_search.text().strip()

        def loaded(result):
            products, customers = result
            self.management_products = list(products)
            self.stock_table.setRowCount(len(products))
            for row, product in enumerate(products):
                values = (
                    product.get("name") or "", product.get("barcode") or product.get("sku") or "—",
                    str(int(product.get("stock") or 0)), str(len(product.get("variants") or [])) or "—",
                )
                for column, value in enumerate(values):
                    self.stock_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.customer_table.setRowCount(len(customers))
            for row, customer in enumerate(customers):
                values = (
                    customer.get("name") or "", customer.get("phone") or "",
                    f"{float(customer.get('points') or 0):,.0f}",
                    f"{float(customer.get('current_balance') or 0):,.0f}",
                )
                for column, value in enumerate(values):
                    self.customer_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.statusBar().showMessage(f"{len(products)} products · {len(customers)} customers")

        self._run_task(
            lambda: (self.api.products(query, limit=100), self.api.customers(query, limit=100)),
            loaded, lambda error: self.statusBar().showMessage(error),
        )

    def adjust_selected_stock(self, direction: int) -> None:
        row = self.stock_table.currentRow()
        products = getattr(self, "management_products", [])
        if row < 0 or row >= len(products) or not self.api or self._threads:
            return
        product = products[row]
        variant = None
        if product.get("variants"):
            variant = self._select_variant(product)
            if variant == {}:
                return
        dialog = QDialog(self)
        dialog.setWindowTitle("Stock In" if direction > 0 else "Stock Out")
        form = QFormLayout(dialog)
        quantity = QSpinBox()
        quantity.setRange(1, 1000000)
        reason = QLineEdit("Stock received" if direction > 0 else "Stock adjustment")
        location = QLineEdit("Shop")
        form.addRow("Product", QLabel(product.get("name") or ""))
        if variant:
            form.addRow("Variant", QLabel(" / ".join(x for x in (variant.get("color") or "", variant.get("size") or "") if x)))
        form.addRow("Quantity", quantity)
        form.addRow("Reason", reason)
        form.addRow("Location", location)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        adjustment = direction * quantity.value()
        self.statusBar().showMessage("Updating stock…")

        def completed(_product):
            self.statusBar().showMessage("Stock updated and movement recorded")
            QTimer.singleShot(100, self.load_management)
            QTimer.singleShot(200, self.load_products)

        self._run_task(
            lambda: self.api.adjust_stock(
                int(product.get("id") or 0), adjustment,
                variant_id=int((variant or {}).get("variant_id") or 0) or None,
                reason=reason.text(), location=location.text(),
            ),
            completed, lambda error: QMessageBox.critical(self, "Stock", error),
        )

    def search_history(self) -> None:
        self.history_offset = 0
        self.load_history()

    def load_history(self) -> None:
        if not self.api:
            return
        if self._threads:
            QTimer.singleShot(150, self.load_history)
            return
        query = self.history_search.text().strip()
        offset = self.history_offset
        self.history_status.setText("Loading…")

        def loaded(receipts):
            if query != self.history_search.text().strip() or offset != self.history_offset:
                QTimer.singleShot(100, self.load_history)
                return
            self.receipts = list(receipts)
            self.history_table.setRowCount(len(self.receipts))
            for row, receipt in enumerate(self.receipts):
                values = (
                    receipt.get("invoice_no") or "",
                    str(receipt.get("created_at") or ""),
                    receipt.get("customer_name") or "Walk-in Customer",
                    receipt.get("payment_type") or "",
                    str(int(receipt.get("item_count") or 0)),
                    f"{float(receipt.get('total') or 0):,.0f} Ks",
                    receipt.get("status") or "completed",
                )
                for column, value in enumerate(values):
                    self.history_table.setItem(row, column, QTableWidgetItem(str(value)))
            page_number = offset // 50 + 1
            self.history_status.setText(f"Page {page_number} · {len(self.receipts)} receipts")
            self.history_prev.setEnabled(offset > 0)
            self.history_next.setEnabled(len(self.receipts) == 50)

        self._run_task(
            lambda: self.api.receipts(query, limit=50, offset=offset),
            loaded,
            lambda error: (self.history_status.setText("Could not load"), self.statusBar().showMessage(error)),
        )

    def change_history_page(self, delta: int) -> None:
        self.history_offset = max(0, self.history_offset + int(delta))
        self.load_history()

    def _selected_receipt_summary(self) -> dict | None:
        row = self.history_table.currentRow()
        return self.receipts[row] if 0 <= row < len(self.receipts) else None

    def view_selected_receipt(self) -> None:
        summary = self._selected_receipt_summary()
        if not summary or not self.api or self._threads:
            return
        sale_id = int(summary.get("id") or 0)
        self.history_status.setText("Loading receipt…")

        def loaded(receipt):
            self.history_status.setText("")
            self.last_receipt = dict(receipt)
            self.print_receipt_button.setEnabled(True)
            ReceiptDialog(receipt, self, self.refund_receipt).exec()

        self._run_task(
            lambda: self.api.receipt(sale_id), loaded,
            lambda error: QMessageBox.critical(self, "Receipt", error),
        )

    def refund_selected_sale(self) -> None:
        summary = self._selected_receipt_summary()
        if not summary:
            return
        self.refund_receipt(summary)

    def refund_receipt(self, summary: dict) -> None:
        """Refund one complete receipt selected from history or its detail dialog."""
        if not summary or not self.api or self._threads:
            return
        if str(summary.get("status") or "").lower() == "refunded":
            QMessageBox.information(self, "Refund", "This sale has already been refunded.")
            return
        if str(summary.get("payment_type") or "").lower() == "credit":
            QMessageBox.warning(self, "Refund", "Credit sales must be refunded from the full POS credit workflow.")
            return
        invoice = str(summary.get("invoice_no") or "")
        answer = QMessageBox.question(
            self, "Full Refund",
            f"Refund the complete sale {invoice}?\n\nAll item stock will be restored.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        reason, accepted = QInputDialog.getText(self, "Refund Reason", "Reason:", text="Customer return")
        if not accepted or not reason.strip():
            return
        sale_id = int(summary.get("id") or 0)
        self.history_status.setText("Refunding…")

        def refunded(receipt):
            self.history_status.setText("Refund completed")
            QMessageBox.information(self, "Refund", f"{invoice} was refunded and stock was restored.")
            ReceiptDialog(receipt, self).exec()
            QTimer.singleShot(100, self.load_history)
            QTimer.singleShot(200, self.load_products)

        self._run_task(
            lambda: self.api.refund(sale_id, reason), refunded,
            lambda error: (self.history_status.setText("Refund failed"), QMessageBox.critical(self, "Refund", error)),
        )

    def logout(self) -> None:
        if self.api:
            self.api.close()
        self.api = None
        self.user = {}
        self.products = []
        self.receipts = []
        self.last_receipt = {}
        self.print_receipt_button.setEnabled(False)
        self.history_table.setRowCount(0)
        self.cart.clear()
        self.render_cart()
        self.password_input.clear()
        self.pages.setCurrentWidget(self.login_page)
        self.login_status.setText("Signed out.")
        self.statusBar().showMessage("Ready")

    def closeEvent(self, event) -> None:
        if self._threads:
            QMessageBox.information(self, "KAY POS Lite", "Please wait for the current server request to finish.")
            event.ignore()
            return
        if self.api:
            self.api.close()
        event.accept()
