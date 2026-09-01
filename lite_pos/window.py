"""Original PyQt6 widget shell for KAY POS Lite Phase 1."""

from __future__ import annotations

import ctypes
import base64
import html
from collections.abc import Callable

from PyQt6.QtCore import QDate, QMarginsF, QObject, QRectF, QSize, QSizeF, QThread, QTime, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QImage, QKeySequence, QPageLayout, QPageSize, QPainter, QPalette, QPixmap, QShortcut
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
    QComboBox, QDateEdit, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel,
    QInputDialog, QLineEdit, QMainWindow, QMessageBox, QPushButton as QtPushButton,
    QStackedWidget, QStyle, QStyleOptionButton, QStylePainter, QSystemTrayIcon,
    QListWidget, QListWidgetItem, QScrollArea, QSpinBox, QStatusBar, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from lite_pos.api import LiteApiClient
from lite_pos.cart import CartError, LiteCart, sold_by_mode
from lite_pos.config import load_config, save_config
from lite_pos.theme import apply_lite_theme, normalize_theme
from lite_pos.settings_center import LiteSettingsCenter


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
    """Native button chrome with consistent text placement."""

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
        # Use one font-metrics baseline for every label. Per-string glyph
        # bounds vary with Myanmar combining marks and made adjacent category
        # buttons appear at different vertical positions.
        left_aligned = bool(self.property("leftAligned"))
        text_rect = option.rect.adjusted(11 if left_aligned else 0, 0, -8 if left_aligned else 0, 0)
        text_rect.translate(0, 1)
        painter.drawText(
            text_rect,
            (Qt.AlignmentFlag.AlignLeft if left_aligned else Qt.AlignmentFlag.AlignHCenter)
            | Qt.AlignmentFlag.AlignVCenter,
            text,
        )


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


class ResponsiveProductGrid(QListWidget):
    """Distribute square product tiles across the full viewport width."""

    preferred_tile_width = 128
    tile_spacing = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tile_extent = 124
        self._refit_pending = False

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refit()

    def fit_item(self, item: QListWidgetItem) -> None:
        item.setSizeHint(QSize(self._tile_extent, self._tile_extent))

    def refit(self) -> None:
        """Debounce resize/layout events into one stable column calculation."""
        if self._refit_pending:
            return
        self._refit_pending = True
        QTimer.singleShot(0, self._run_refit)

    def _run_refit(self) -> None:
        self._refit_pending = False
        self._fit_columns()

    def _fit_columns(self) -> None:
        # Always reserve the vertical scrollbar width. Measuring viewport()
        # directly made the cards wider when the bar disappeared, which could
        # make it reappear and cause a visible resize loop.
        frame = self.frameWidth() * 2
        scrollbar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        available = max(1, self.width() - frame - scrollbar - 2)
        available_height = max(1, self.height() - frame - 2)
        item_count = max(1, self.count())
        max_columns = max(1, available // self.preferred_tile_width)

        # On a large/full-screen display, use both dimensions so the catalogue
        # does not collapse into a strip of tiny tiles along the top. Choose the
        # square size that can show the current page while filling the viewport.
        best_columns = 1
        best_extent = 0
        for candidate in range(1, item_count + 1):
            rows = (item_count + candidate - 1) // candidate
            width_extent = (available - self.tile_spacing * (candidate - 1)) // candidate
            height_extent = (available_height - self.tile_spacing * (rows - 1)) // rows
            extent = min(width_extent, height_extent)
            if extent > best_extent:
                best_columns, best_extent = candidate, extent

        # Small windows remain scrollable and never squeeze products below the
        # normal readable tile size. Larger windows grow the cards to consume
        # otherwise empty width and height.
        columns = best_columns if best_extent >= self.preferred_tile_width else max_columns
        cell = max(72, (available - self.tile_spacing * (columns - 1)) // columns)
        extent = max(68, cell - 2)
        new_grid_size = QSize(cell, cell)
        if self.gridSize() == new_grid_size and self._tile_extent == extent:
            return
        self._tile_extent = extent
        self.setGridSize(new_grid_size)
        for index in range(self.count()):
            self.fit_item(self.item(index))
        self.scheduleDelayedItemsLayout()


class ProductGridTile(QFrame):
    """Square, image-first POS tile with a caption overlay."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.full_name = str(name or "Product")
        self.source_pixmap: QPixmap | None = None
        self.setObjectName("productGridTile")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.image_label = QLabel(self)
        self.image_label.setObjectName("productGridImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("▢")
        self.caption_label = QLabel(self.full_name, self)
        self.caption_label.setObjectName("productGridCaption")
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption_label.setWordWrap(False)
        self.image_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.caption_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("""
            QFrame#productGridTile { background: #7518a4; border: 1px solid #d9d9d9; }
            QLabel#productGridImage { background: #7518a4; color: white; font-size: 17px; }
            QLabel#productGridCaption { background: rgba(55, 55, 55, 185); color: white;
                                        border: 0; padding: 3px 4px; font-size: 12px; }
        """)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.image_label.setGeometry(self.rect())
        caption_height = 38
        self.caption_label.setGeometry(0, max(0, self.height() - caption_height), self.width(), caption_height)
        self.caption_label.setText(self._short_caption(max(1, self.width() - 8)))
        self.caption_label.raise_()
        if self.source_pixmap is not None:
            self._render_product_image()

    def _short_caption(self, available_width: int) -> str:
        metrics = self.caption_label.fontMetrics()
        if metrics.horizontalAdvance(self.full_name) <= available_width:
            return self.full_name
        suffix = " ....."
        text = self.full_name.rstrip()
        while text and metrics.horizontalAdvance(text + suffix) > available_width:
            text = text[:-1].rstrip()
        return (text + suffix) if text else "....."

    def _render_product_image(self) -> None:
        if self.source_pixmap is None:
            return
        self.image_label.setPixmap(self.source_pixmap.scaled(
            max(1, self.image_label.width()), max(1, self.image_label.height()),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def set_product_image(self, pixmap: QPixmap) -> None:
        self.source_pixmap = pixmap
        self.image_label.setText("")
        self.image_label.setStyleSheet("background: white;")
        self._render_product_image()


class LiteSaleDisplay(QWidget):
    """Customer-facing cart display intended for a second monitor."""

    closed = pyqtSignal()

    def __init__(self, shop_name: str = "KAY POS", parent=None):
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("liteSaleDisplay")
        self.setWindowTitle("KAY POS Lite · Sale Display")
        self.setStyleSheet("""
            QWidget#liteSaleDisplay { background: #0d111b; color: #edf2ff; }
            QLabel#displayShop { color: #ffffff; font-size: 28pt; font-weight: 800; }
            QLabel#displayMessage { color: #99a4ba; font-size: 13pt; }
            QLabel#displayTotalCaption { color: #aeb8ca; font-size: 18pt; font-weight: 600; }
            QLabel#displayTotal { color: #ffffff; background: #5365df; border-radius: 18px;
                                  padding: 18px 28px; font-size: 34pt; font-weight: 800; }
            QTableWidget { background: #151c2a; color: #edf2ff; gridline-color: #293348;
                           border: 1px solid #293348; font-size: 15pt; }
            QHeaderView::section { background: #111724; color: #aeb8ca; border: 0;
                                   border-bottom: 1px solid #293348; padding: 10px; font-size: 12pt; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 34, 42, 38)
        layout.setSpacing(18)
        self.shop_label = QLabel(shop_name or "KAY POS", objectName="displayShop")
        self.message_label = QLabel("Your order", objectName="displayMessage")
        layout.addWidget(self.shop_label)
        layout.addWidget(self.message_label)
        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["Item", "Qty", "Price", "Amount"])
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(48)
        self.items_table.horizontalHeader().setMinimumHeight(48)
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.items_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.items_table, 1)
        total_row = QHBoxLayout()
        total_row.addStretch()
        total_row.addWidget(QLabel("TOTAL", objectName="displayTotalCaption"))
        self.total_label = QLabel("0 Ks", objectName="displayTotal")
        self.total_label.setMinimumWidth(310)
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_row.addWidget(self.total_label)
        layout.addLayout(total_row)

    def set_shop_name(self, shop_name: str) -> None:
        self.shop_label.setText(str(shop_name or "KAY POS"))

    def set_cart(self, items: list[dict]) -> None:
        self.items_table.setRowCount(len(items))
        total = 0.0
        for row, item in enumerate(items):
            quantity = int(item.get("qty") or 0)
            price = float(item.get("price") or 0)
            amount = price * quantity
            total += amount
            name = str(item.get("name") or "Item")
            if item.get("variant_label"):
                name += f" · {item['variant_label']}"
            values = (name, f"{quantity:,}", f"{price:,.0f} Ks", f"{amount:,.0f} Ks")
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.items_table.setItem(row, column, cell)
        self.message_label.setText(f"{sum(int(item.get('qty') or 0) for item in items):,} item(s)" if items else "Welcome · Your order will appear here")
        self.total_label.setText(f"{total:,.0f} Ks")

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


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
    def __init__(
        self, total: float, parent=None, customers: list[dict] | None = None,
        print_after_sale: bool = False, open_drawer_after_sale: bool = False,
        payment_types: list[str] | None = None, credit_settings: dict | None = None,
    ):
        super().__init__(parent)
        self.total = float(total)
        self.credit_settings = dict(credit_settings or {})
        self.allow_credit_over_limit = False
        self.setWindowTitle("Checkout")
        self.setFixedWidth(390)
        layout = QVBoxLayout(self)
        self.checkout_title = QLabel(f"Subtotal · {self.total:,.0f} Ks", objectName="title")
        layout.addWidget(self.checkout_title)
        form = QFormLayout()
        self.checkout_form = form
        self.customer = QComboBox()
        self.customer.setEditable(True)
        self.customer.addItem("Walk-in Customer", None)
        for entry in customers or []:
            label = entry.get("name") or "Customer"
            if entry.get("phone"):
                label += f" · {entry.get('phone')}"
            self.customer.addItem(label, entry)
        self.customer_info = QLabel("No customer selected")
        self.customer_info.setWordWrap(True)
        self.payment_type = QComboBox()
        configured_payment_types = [str(value).strip() for value in (payment_types or []) if str(value).strip()]
        configured_payment_types = configured_payment_types or ["Cash"]
        if not any(value.casefold() == "credit" for value in configured_payment_types):
            configured_payment_types.append("Credit")
        self.payment_type.addItems(configured_payment_types)
        self.discount_type = QComboBox()
        self.discount_type.addItem("No Discount", "none")
        self.discount_type.addItem("Amount", "amount")
        self.discount_type.addItem("Percent", "percent")
        self.discount_value = QDoubleSpinBox()
        self.discount_value.setRange(0, self.total)
        self.discount_value.setDecimals(2)
        self.discount_value.setSingleStep(100)
        self.discount_value.setEnabled(False)
        self.discount_label = QLabel("0 Ks")
        self.total_due_label = QLabel(f"{self.total:,.0f} Ks")
        self._last_payable = self.total
        self.payment = QDoubleSpinBox()
        self.payment.setRange(0, 999999999999)
        self.payment.setDecimals(0)
        self.payment.setValue(self.total)
        self.payment.setSingleStep(1000)
        self.change_label = QLabel("0 Ks")
        self.credit_balance_label = QLabel(f"{self.total:,.0f} Ks")
        self.credit_due_date = QDateEdit(QDate.currentDate().addDays(int(self.credit_settings.get("credit_due_days") or 15)))
        self.credit_due_date.setCalendarPopup(True); self.credit_due_date.setDisplayFormat("yyyy-MM-dd")
        self.credit_notes = QTextEdit(); self.credit_notes.setMaximumHeight(65)
        self.print_after_sale = QCheckBox("Print receipt after completing sale")
        self.open_drawer_after_sale = QCheckBox("Open cash drawer after completing sale")
        self.print_after_sale.setChecked(bool(print_after_sale))
        self._drawer_preference = bool(open_drawer_after_sale)
        self.open_drawer_after_sale.setChecked(self._drawer_preference)
        form.addRow("Customer", self.customer)
        form.addRow("Customer Info", self.customer_info)
        form.addRow("Discount Type", self.discount_type)
        form.addRow("Discount Value", self.discount_value)
        form.addRow("Discount", self.discount_label)
        form.addRow("Total Due", self.total_due_label)
        form.addRow("Payment Type", self.payment_type)
        form.addRow("Payment", self.payment)
        form.addRow("Change", self.change_label)
        form.addRow("Balance Due", self.credit_balance_label)
        form.addRow("Due Date", self.credit_due_date)
        form.addRow("Credit Notes", self.credit_notes)
        form.addRow(self.print_after_sale)
        form.addRow(self.open_drawer_after_sale)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Complete Sale")
        buttons.accepted.connect(self._accept_if_paid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.payment.valueChanged.connect(self._update_change)
        self.payment_type.currentTextChanged.connect(self._payment_type_changed)
        self.discount_type.currentIndexChanged.connect(self._discount_changed)
        self.discount_value.valueChanged.connect(self._discount_changed)
        self.open_drawer_after_sale.toggled.connect(self._remember_drawer_preference)
        self.customer.currentIndexChanged.connect(self._customer_changed)
        self._customer_changed()
        self._payment_type_changed(self.payment_type.currentText())

    def discount_amount(self) -> float:
        discount_type = self.discount_type.currentData()
        value = float(self.discount_value.value() or 0)
        if discount_type == "percent":
            return min(self.total, self.total * min(value, 100.0) / 100.0)
        if discount_type == "amount":
            return min(self.total, value)
        return 0.0

    def payable_total(self) -> float:
        return max(0.0, self.total - self.discount_amount())

    def _discount_changed(self, _value=None) -> None:
        discount_type = self.discount_type.currentData()
        self.discount_value.setEnabled(discount_type != "none")
        self.discount_value.setSuffix(" %" if discount_type == "percent" else " Ks" if discount_type == "amount" else "")
        self.discount_value.setMaximum(100 if discount_type == "percent" else self.total)
        if discount_type == "none" and self.discount_value.value():
            self.discount_value.setValue(0)
        payable = self.payable_total()
        discount = self.discount_amount()
        payment_type = self.payment_type.currentText().strip().lower()
        if payment_type != "credit" and abs(self.payment.value() - self._last_payable) < 0.01:
            self.payment.setValue(payable)
        self._last_payable = payable
        self.discount_label.setText(f"{discount:,.0f} Ks")
        self.total_due_label.setText(f"{payable:,.0f} Ks")
        self._update_change()

    def _remember_drawer_preference(self, checked: bool) -> None:
        if self.open_drawer_after_sale.isEnabled():
            self._drawer_preference = bool(checked)

    def _customer_changed(self, _index=0) -> None:
        customer = self.customer.currentData()
        if not customer:
            self.customer_info.setText("No customer selected")
            return
        self.customer_info.setText(
            f"Points: {float(customer.get('points') or 0):,.0f} · "
            f"Outstanding: {float(customer.get('current_balance') or 0):,.0f} Ks · "
            f"Credit Limit: {float(customer.get('credit_limit') or 0):,.0f} Ks · "
            f"Available: {max(0.0, float(customer.get('credit_limit') or 0) - float(customer.get('current_balance') or 0)):,.0f} Ks"
        )

    def selected_customer_id(self) -> int | None:
        customer = self.customer.currentData()
        return int((customer or {}).get("id") or 0) or None

    def _payment_type_changed(self, payment_type: str) -> None:
        normalized_type = payment_type.strip().lower()
        payable = self.payable_total()
        if normalized_type == "credit":
            self.payment.setValue(0)
        elif normalized_type != "cash":
            self.payment.setValue(payable)
        self.payment.setEnabled(normalized_type in {"cash", "credit"})
        self.open_drawer_after_sale.setEnabled(normalized_type == "cash")
        if normalized_type == "cash":
            self.open_drawer_after_sale.setChecked(self._drawer_preference)
        else:
            self.open_drawer_after_sale.setChecked(False)
        is_credit = normalized_type == "credit"
        self.form_label_for(self.payment).setText("Paid Today" if is_credit else "Payment")
        self.form_label_for(self.change_label).setVisible(not is_credit); self.change_label.setVisible(not is_credit)
        for widget in (self.credit_balance_label, self.credit_due_date, self.credit_notes):
            widget.setVisible(is_credit); self.form_label_for(widget).setVisible(is_credit)
        self._update_change()

    def form_label_for(self, widget):
        return self.checkout_form.labelForField(widget)

    def _update_change(self) -> None:
        is_credit = self.payment_type.currentText().strip().lower() == "credit"
        payable = self.payable_total()
        change = 0.0 if is_credit else max(0.0, self.payment.value() - payable)
        self.change_label.setText(f"{change:,.0f} Ks")
        self.credit_balance_label.setText(f"{max(0.0, payable - self.payment.value()):,.0f} Ks")

    def _accept_if_paid(self) -> None:
        is_credit = self.payment_type.currentText().strip().lower() == "credit"
        payable = self.payable_total()
        if is_credit and not self.selected_customer_id():
            QMessageBox.warning(self, "Customer", "Select a customer for a credit sale.")
            return
        if is_credit and self.payment.value() > payable:
            QMessageBox.warning(self, "Credit Sale", "Paid Today cannot exceed the sale total.")
            return
        if is_credit:
            customer = self.customer.currentData() or {}
            limit = float(customer.get("credit_limit") or 0)
            current = float(customer.get("current_balance") or 0)
            balance = max(0.0, payable - self.payment.value())
            exceeded = limit > 0 and current + balance > limit
            if self.credit_settings.get("credit_limit_enabled", True) and exceeded:
                answer = QMessageBox.warning(
                    self, "Credit Limit Warning",
                    f"Credit limit will be exceeded.\n\nLimit: {limit:,.0f} Ks\nCurrent balance: {current:,.0f} Ks\nThis credit: {balance:,.0f} Ks\nNew balance: {current + balance:,.0f} Ks\n\nProceed anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes: return
                self.allow_credit_over_limit = True
        if not is_credit and self.payment.value() < payable:
            QMessageBox.warning(self, "Payment", "Payment is less than the sale total.")
            return
        self.accept()


class ExpenseDialog(QDialog):
    def __init__(self, categories: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Expense")
        self.setMinimumWidth(430)
        form = QFormLayout(self)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(categories)
        self.description = QLineEdit()
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 999999999)
        self.amount.setDecimals(0)
        self.amount.setSuffix(" Ks")
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.payment = QComboBox()
        self.payment.addItems(["Cash", "Card", "Mobile Money", "Bank Transfer"])
        self.reference = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(70)
        form.addRow("Category", self.category)
        form.addRow("Description", self.description)
        form.addRow("Amount", self.amount)
        form.addRow("Expense Date", self.date)
        form.addRow("Payment Method", self.payment)
        form.addRow("Reference No", self.reference)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _validate(self) -> None:
        if not self.category.currentText().strip():
            QMessageBox.warning(self, "Expense", "Category is required.")
            return
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Expense", "Amount must be greater than zero.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "category": self.category.currentText().strip(),
            "description": self.description.text().strip(),
            "amount": self.amount.value(),
            "expense_date": self.date.date().toString("yyyy-MM-dd"),
            "payment_method": self.payment.currentText(),
            "reference_no": self.reference.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class ProductEditorDialog(QDialog):
    def __init__(self, product: dict | None = None, categories: list[str] | None = None, parent=None, existing_pixmap: QPixmap | None = None):
        super().__init__(parent)
        self.product = dict(product or {})
        self.image_path = ""
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.resize(750, 570)
        outer = QVBoxLayout(self)
        content = QHBoxLayout(); outer.addLayout(content, 1)
        left = QVBoxLayout(); self.form = QFormLayout(); form = self.form
        content.addLayout(left, 3)
        self.name = QLineEdit(str(self.product.get("name") or ""))
        self.category = QComboBox(); self.category.setEditable(True); self.category.addItems(categories or [])
        self.category.setCurrentText(str(self.product.get("category") or ""))
        self.description = QTextEdit(str(self.product.get("description") or "")); self.description.setFixedHeight(60)
        self.sold_by = QComboBox(); self.sold_by.addItems(["Each", "Service", "Variants"])
        mode = sold_by_mode(self.product.get("sold_by")); self.sold_by.setCurrentText("Service" if mode == "service" else "Variants" if mode == "variants" else "Each")
        self.sku = QLineEdit(str(self.product.get("sku") or "")); self.barcode = QLineEdit(str(self.product.get("barcode") or ""))
        self.price = QDoubleSpinBox(); self.cost = QDoubleSpinBox()
        for widget in (self.price, self.cost): widget.setRange(0, 999999999999); widget.setDecimals(2)
        self.price.setValue(float(self.product.get("original_price") or self.product.get("price") or 0)); self.cost.setValue(float(self.product.get("cost") or 0))
        self.stock = QSpinBox(); self.stock.setRange(0, 1000000); self.stock.setValue(int(self.product.get("stock") or 0))
        self.low_stock = QSpinBox(); self.low_stock.setRange(0, 1000000); self.low_stock.setValue(int(self.product.get("low_stock") or 0))
        self.unit = QLineEdit(str(self.product.get("base_unit") or self.product.get("unit") or "pcs"))
        self.pack_unit = QLineEdit(str(self.product.get("pack_unit") or "")); self.pack_unit.setPlaceholderText("card / box")
        self.pack_size = QSpinBox(); self.pack_size.setRange(1,100000); self.pack_size.setValue(int(self.product.get("pack_size") or 1))
        self.image_label = QLabel("Keep current image" if product else "No image selected")
        self.image_preview = QLabel("No Image\nSelect an image to preview"); self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.image_preview.setFixedSize(190, 135); self.image_preview.setFrameShape(QFrame.Shape.StyledPanel)
        image_button = QPushButton("Choose Image…"); image_button.clicked.connect(self.choose_image)
        image_row = QHBoxLayout(); image_row.addWidget(self.image_label, 1); image_row.addWidget(image_button)
        for label, widget in (("Sold By",self.sold_by),("Product Name",self.name),("Category",self.category),("Barcode",self.barcode),("SKU",self.sku),("Price",self.price),("Cost",self.cost),("Stock",self.stock),("Low Stock Alert",self.low_stock),("Stock Unit",self.unit),("Pack Name",self.pack_unit),("Qty / Pack",self.pack_size),("Description",self.description)):
            form.addRow(label, widget)
        left.addLayout(form)
        self.mode_note = QLabel(); self.mode_note.setWordWrap(True); self.mode_note.setFrameShape(QFrame.Shape.StyledPanel); self.mode_note.setMargin(10)
        left.addWidget(self.mode_note)
        self.variant_title = QLabel("Variants", objectName="title"); left.addWidget(self.variant_title)
        self.variants = QTableWidget(0, 9); self.variants.setMinimumHeight(190); self.variants.setHorizontalHeaderLabels(["Color","Size","SKU","Barcode","Price","Cost","Stock","Low","Active"])
        self.variants.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); left.addWidget(self.variants, 1)
        actions = QHBoxLayout(); self.add_variant_button = QPushButton("Add Variant"); self.remove_variant_button = QPushButton("Remove Variant"); add=self.add_variant_button; remove=self.remove_variant_button
        add.clicked.connect(self.add_variant); remove.clicked.connect(lambda: self.variants.removeRow(self.variants.currentRow()) if self.variants.currentRow() >= 0 else None)
        actions.addWidget(add); actions.addWidget(remove); actions.addStretch(); left.addLayout(actions)
        image_frame = QFrame(); image_frame.setMaximumWidth(240)
        image_panel = QVBoxLayout(image_frame); image_title = QLabel("Product Image Preview", objectName="title"); image_panel.addWidget(image_title)
        image_panel.addWidget(self.image_preview, 0, Qt.AlignmentFlag.AlignHCenter); image_panel.addLayout(image_row)
        self.product_info = QLabel("Fill in the form to see product details"); self.product_info.setWordWrap(True); self.product_info.setFrameShape(QFrame.Shape.StyledPanel); self.product_info.setMargin(12)
        image_panel.addWidget(self.product_info); image_panel.addStretch(); content.addWidget(image_frame, 0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); outer.addWidget(buttons)
        for variant in self.product.get("variants") or []: self.add_variant(variant)
        self.sold_by.currentTextChanged.connect(self.update_variant_state); self.update_variant_state()
        if existing_pixmap is not None and not existing_pixmap.isNull():
            self.set_existing_image(existing_pixmap)
        elif product:
            self.image_preview.setText("Loading current image…")

    def _show_image_preview(self, pixmap: QPixmap, label: str) -> bool:
        if pixmap.isNull():
            return False
        self.image_preview.setText("")
        self.image_preview.setPixmap(pixmap.scaled(
            186, 131, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self.image_label.setText(label)
        return True

    def set_existing_image(self, pixmap: QPixmap) -> None:
        self._show_image_preview(pixmap, "Current product image")

    def set_existing_image_unavailable(self) -> None:
        if not self.image_path:
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("No current image")

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Product Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.image_path = path; self.image_label.setText(path)
            pixmap=QPixmap(path)
            self._show_image_preview(pixmap, path)

    def add_variant(self, values=None):
        values = values or {}; row = self.variants.rowCount(); self.variants.insertRow(row)
        data = [values.get("color",""),values.get("size",""),values.get("sku",""),values.get("barcode",""),values.get("price",self.price.value()),values.get("cost",self.cost.value()),values.get("stock",0),values.get("low_stock",0),"Yes" if values.get("active",True) else "No"]
        for column, value in enumerate(data): self.variants.setItem(row,column,QTableWidgetItem(str(value)))

    def update_variant_state(self):
        mode=self.sold_by.currentText(); is_each=mode=="Each"; is_service=mode=="Service"; is_variants=mode=="Variants"
        # Match the full KAY POS forms: stock is changed through Stock In/Out,
        # while variant-specific price, barcode and stock live in the grid.
        visibility={self.barcode:is_each or is_service,self.sku:False,self.price:is_each,self.cost:False,self.stock:False,self.low_stock:is_each,self.unit:is_each,self.pack_unit:is_each,self.pack_size:is_each,self.variants:is_variants,self.variant_title:is_variants,self.add_variant_button:is_variants,self.remove_variant_button:is_variants}
        for widget,visible in visibility.items():
            widget.setVisible(visible)
        # QFormLayout labels must be hidden with their field widgets.
        for widget,visible in visibility.items():
            label=self.form.labelForField(widget)
            if label: label.setVisible(visible)
        if is_service:
            self.mode_note.setText("This is a service product (no stock tracking).")
            self.resize(750, 400)
        elif is_variants:
            self.mode_note.setText("Use variants to set size/color, barcode, price and stock.")
            self.resize(750, 605)
        else:
            self.mode_note.setText("Set a low stock alert level and optional pack setup.")
            self.resize(750, 570)

    def validate(self):
        if not self.name.text().strip(): QMessageBox.warning(self,"Product","Product name is required."); return
        if self.sold_by.currentText() == "Variants" and self.variants.rowCount() == 0: QMessageBox.warning(self,"Product","Add at least one variant."); return
        self.accept()

    def values(self):
        variants=[]
        for row in range(self.variants.rowCount()):
            text=lambda col: (self.variants.item(row,col).text().strip() if self.variants.item(row,col) else "")
            variants.append({"color":text(0),"size":text(1),"sku":text(2),"barcode":text(3),"price":float(text(4) or 0),"cost":float(text(5) or 0),"stock":int(float(text(6) or 0)),"low_stock":int(float(text(7) or 0)),"active":text(8).lower() not in {"no","0","false"}})
        return {"name":self.name.text().strip(),"category":self.category.currentText().strip(),"description":self.description.toPlainText().strip(),"sold_by":self.sold_by.currentText(),"sku":self.sku.text().strip() if self.sold_by.currentText()=="Each" else "","barcode":self.barcode.text().strip() if self.sold_by.currentText()!="Variants" else "","price":self.price.value() if self.sold_by.currentText()=="Each" else 0,"cost":self.cost.value() if self.sold_by.currentText()=="Each" else 0,"stock":self.stock.value() if self.sold_by.currentText()=="Each" else 0,"low_stock":self.low_stock.value() if self.sold_by.currentText()=="Each" else 0,"unit":self.unit.text().strip() or "pcs","base_unit":self.unit.text().strip() or "pcs","pack_unit":self.pack_unit.text().strip(),"pack_size":self.pack_size.value(),"variants":variants if self.sold_by.currentText()=="Variants" else []}


class CategoryManagerDialog(QDialog):
    """Manage the full KAY POS category hierarchy through the cashier server."""

    def __init__(self, api: LiteApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.categories: list[dict] = []
        self.editing_id: int | None = None
        self.setWindowTitle("Manage Categories · Parent / Child")
        self.resize(760, 560)
        outer = QVBoxLayout(self)
        heading = QLabel("Manage Categories", objectName="title")
        subtitle = QLabel("Uses the same parent and child category information as KAY POS.", objectName="muted")
        outer.addWidget(heading); outer.addWidget(subtitle)
        body = QHBoxLayout(); outer.addLayout(body, 1)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Category", "Parent", "Products", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(2, 80); self.table.setColumnWidth(3, 90)
        self.table.itemSelectionChanged.connect(self._load_selected)
        body.addWidget(self.table, 3)
        legend = QLabel("Category hierarchy colors", objectName="muted")
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setText('<span style="color:#5969ee">● Parent</span>&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#138a72">● Child</span>&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#d97706">● Sub Child</span>')
        outer.addWidget(legend)
        editor = QFrame(objectName="card"); form = QFormLayout(editor)
        self.name = QLineEdit(); self.parent_category = QComboBox()
        self.description = QTextEdit(); self.description.setMaximumHeight(90)
        self.sort_order = QSpinBox(); self.sort_order.setRange(0, 999999)
        self.status = QComboBox(); self.status.addItems(["active", "inactive"])
        form.addRow("Category Name", self.name)
        form.addRow("Parent Category", self.parent_category)
        form.addRow("Description", self.description)
        form.addRow("Sort Order", self.sort_order)
        form.addRow("Status", self.status)
        new_button = QPushButton("New Category")
        save_button = QPushButton("Save Category", objectName="primary")
        delete_button = QPushButton("Delete Selected")
        new_button.clicked.connect(self._clear_editor)
        save_button.clicked.connect(self._save)
        delete_button.clicked.connect(self._delete)
        form.addRow(new_button); form.addRow(save_button); form.addRow(delete_button)
        body.addWidget(editor, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); outer.addWidget(buttons)
        self.refresh()

    def _ordered_categories(self) -> list[tuple[dict, int]]:
        children: dict[int | None, list[dict]] = {}
        known = {int(category.get("id") or 0) for category in self.categories}
        for category in self.categories:
            parent_id = category.get("parent_id")
            key = int(parent_id) if parent_id and int(parent_id) in known else None
            children.setdefault(key, []).append(category)
        for values in children.values():
            values.sort(key=lambda item: (int(item.get("sort_order") or 0), str(item.get("name") or "").casefold()))
        ordered: list[tuple[dict, int]] = []
        def add(parent_id: int | None, depth: int) -> None:
            for category in children.get(parent_id, []):
                ordered.append((category, depth)); add(int(category.get("id") or 0), depth + 1)
        add(None, 0)
        return ordered

    def refresh(self) -> None:
        try:
            self.categories = self.api.managed_categories()
        except Exception as exc:
            QMessageBox.critical(self, "Categories", str(exc)); return
        self.table.setRowCount(0)
        ordered_categories = self._ordered_categories()
        depths = {int(category.get("id") or 0): depth for category, depth in ordered_categories}
        hierarchy_colors = {0: "#5969ee", 1: "#138a72"}
        for category, depth in ordered_categories:
            row = self.table.rowCount(); self.table.insertRow(row)
            name_item = QTableWidgetItem(f"{'    ' * depth}{'↳ ' if depth else ''}{category.get('name') or ''}")
            name_item.setData(Qt.ItemDataRole.UserRole, int(category.get("id") or 0))
            hierarchy_color = QColor(hierarchy_colors.get(depth, "#d97706"))
            name_item.setForeground(hierarchy_color)
            name_item.setToolTip("Parent category" if depth == 0 else "Child category" if depth == 1 else "Sub-child category")
            parent_item = QTableWidgetItem(str(category.get("parent_name") or "—"))
            parent_id = int(category.get("parent_id") or 0)
            if depth > 0: parent_item.setForeground(QColor(hierarchy_colors.get(depths.get(parent_id, 0), "#d97706")))
            values = [name_item, parent_item, QTableWidgetItem(str(category.get("product_count") or 0)), QTableWidgetItem(str(category.get("status") or "active"))]
            for column, item in enumerate(values): self.table.setItem(row, column, item)
        self._populate_parents()

    def _populate_parents(self) -> None:
        current_parent = self.parent_category.currentData() if self.parent_category.count() else None
        self.parent_category.clear(); self.parent_category.addItem("No Parent (Top Level)", None)
        for category, depth in self._ordered_categories():
            category_id = int(category.get("id") or 0)
            if category_id != self.editing_id:
                self.parent_category.addItem(f"{'    ' * depth}{category.get('name') or ''}", category_id)
        index = self.parent_category.findData(current_parent)
        self.parent_category.setCurrentIndex(max(0, index))

    def _selected_category(self) -> dict | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        category_id = int(item.data(Qt.ItemDataRole.UserRole) or 0) if item else 0
        return next((category for category in self.categories if int(category.get("id") or 0) == category_id), None)

    def _load_selected(self) -> None:
        category = self._selected_category()
        if not category: return
        self.editing_id = int(category.get("id") or 0)
        self.name.setText(str(category.get("name") or ""))
        self.description.setPlainText(str(category.get("description") or ""))
        self.sort_order.setValue(int(category.get("sort_order") or 0))
        self.status.setCurrentText(str(category.get("status") or "active"))
        self._populate_parents()
        index = self.parent_category.findData(category.get("parent_id"))
        self.parent_category.setCurrentIndex(max(0, index))

    def _clear_editor(self) -> None:
        self.editing_id = None; self.table.clearSelection(); self.name.clear(); self.description.clear()
        self.sort_order.setValue(0); self.status.setCurrentText("active"); self._populate_parents(); self.name.setFocus()

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name: QMessageBox.warning(self, "Categories", "Category name is required."); return
        values = {"name": name, "description": self.description.toPlainText().strip(), "parent_id": self.parent_category.currentData(), "sort_order": self.sort_order.value(), "status": self.status.currentText()}
        try:
            self.api.save_category(values, self.editing_id)
            self.refresh(); self._clear_editor()
        except Exception as exc: QMessageBox.critical(self, "Categories", str(exc))

    def _delete(self) -> None:
        category = self._selected_category()
        if not category: QMessageBox.information(self, "Categories", "Select a category first."); return
        if QMessageBox.question(self, "Delete Category", f"Delete '{category.get('name')}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try:
            self.api.delete_category(int(category.get("id") or 0)); self.refresh(); self._clear_editor()
        except Exception as exc: QMessageBox.critical(self, "Categories", str(exc))


class ReceiptDialog(QDialog):
    def __init__(self, receipt: dict, parent=None, refund_callback: Callable[[dict], None] | None = None, settings: dict | None = None):
        super().__init__(parent)
        self.receipt = receipt
        self.settings = dict(settings or {})
        self.refund_callback = refund_callback
        self.setWindowTitle(f"Receipt · {receipt.get('invoice_no') or ''}")
        self.resize(520, 600)
        layout = QVBoxLayout(self)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self._set_document_html(self.preview.document())
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
        multiline = lambda value: escape(str(value or "")).replace("\n", "<br>")
        shop_name = escape(str(self.settings.get("shop_name") or "KAY POS"))
        currency = escape(str(self.settings.get("currency_symbol") or "Ks"))
        logo_data = str(self.settings.get("shop_logo_image") or "").strip()
        logo = '<p style="text-align:center;margin:0 0 4px"><img src="kaypos://receipt/logo" width="72"></p>' if logo_data.startswith("data:image/") else ""
        header = multiline(self.settings.get("receipt_header"))
        footer = multiline(self.settings.get("receipt_footer"))
        footer_message = multiline(self.settings.get("shop_footer_message"))
        rows = "".join(
            f"<tr><td>{escape(str(item.get('product_name') or ''))}</td>"
            f"<td align='right'>{int(item.get('qty') or 0)}</td>"
            f"<td align='right'>{float(item.get('total') or 0):,.0f}</td></tr>"
            for item in self.receipt.get("items") or []
        )
        header_html = f"<p style='text-align:center;margin:3px 0 8px'>{header}</p>" if header else ""
        footer_html = f"<p style='text-align:center;margin:10px 0 3px'>{footer}</p>" if footer else ""
        message_html = f"<p style='text-align:center;font-weight:bold;margin:4px 0'>{footer_message}</p>" if footer_message else ""
        is_credit = str(self.receipt.get("payment_type") or "").casefold() == "credit"
        credit_html = (
            f"<p><b>Credit Paid:</b> {float(self.receipt.get('paid_amount') or self.receipt.get('payment') or 0):,.0f} {currency}<br>"
            f"<b>Balance Due:</b> {float(self.receipt.get('balance_amount') or 0):,.0f} {currency}<br>"
            f"<b>Due Date:</b> {escape(str(self.receipt.get('due_date') or '—'))}</p>"
        ) if is_credit else ""
        return (
            "<div style='font-family:Segoe UI,Myanmar Text;font-size:10pt'>"
            f"{logo}<h2 style='text-align:center;margin:2px 0'>{shop_name}</h2>"
            f"{header_html}"
            f"<p><b>Invoice:</b> {escape(str(self.receipt.get('invoice_no') or ''))}<br>"
            f"<b>Date:</b> {escape(str(self.receipt.get('created_at') or ''))}<br>"
            f"<b>Status:</b> {escape(str(self.receipt.get('status') or 'completed').title())}</p>"
            "<table width='100%' cellspacing='5'><tr><th align='left'>Item</th><th>Qty</th><th>Total</th></tr>"
            f"{rows}</table><hr>"
            f"<h3 style='text-align:right'>Total: {float(self.receipt.get('total') or 0):,.0f} {currency}</h3>"
            f"<p style='text-align:right'>Payment: {float(self.receipt.get('payment') or 0):,.0f} {currency}<br>"
            f"Change: {float(self.receipt.get('change_amount') or 0):,.0f} {currency}</p>"
            f"{credit_html}{footer_html}{message_html}</div>"
        )

    def _set_document_html(self, document) -> None:
        logo_data = str(self.settings.get("shop_logo_image") or "")
        if logo_data.startswith("data:image/") and "," in logo_data:
            try:
                image = QImage.fromData(base64.b64decode(logo_data.split(",", 1)[1]))
                if not image.isNull():
                    from PyQt6.QtGui import QTextDocument
                    document.addResource(QTextDocument.ResourceType.ImageResource, QUrl("kaypos://receipt/logo"), image)
            except Exception:
                pass
        document.setHtml(self._html())

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
            self._set_document_html(document)

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

    def print_receipt_automatic(self) -> None:
        """Print directly to the configured local receipt printer."""
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo

        saved_name = str(load_config().get("receipt_printer_name") or "")
        saved_info = next(
            (info for info in QPrinterInfo.availablePrinters() if info.printerName() == saved_name),
            None,
        )
        if saved_info is None:
            QMessageBox.warning(
                self, "Print Receipt",
                "The configured receipt printer is not installed on this PC. "
                "Select it in Setting Center > Local Printer first.",
            )
            return
        printer = QPrinter(saved_info, QPrinter.PrinterMode.HighResolution)
        document = QTextDocument()
        document.setDocumentMargin(0)
        self._set_document_html(document)
        logical_dpi = 96.0
        logical_width = 72.0 * logical_dpi / 25.4
        document.setTextWidth(logical_width)
        content_height = document.documentLayout().documentSize().height()
        page_height_mm = max(55.0, min(500.0, content_height * 25.4 / logical_dpi + 9.0))
        receipt_page = QPageSize(
            QSizeF(80.0, page_height_mm), QPageSize.Unit.Millimeter,
            "80mm Receipt", QPageSize.SizeMatchPolicy.ExactMatch,
        )
        printer.setPageLayout(QPageLayout(
            receipt_page, QPageLayout.Orientation.Portrait,
            QMarginsF(4.0, 3.0, 4.0, 4.0), QPageLayout.Unit.Millimeter,
        ))
        painter = QPainter(printer)
        if not painter.isActive():
            QMessageBox.critical(self, "Print Receipt", "Could not start the configured printer.")
            return
        scale = printer.resolution() / logical_dpi
        paint_rect = printer.pageLayout().paintRectPixels(printer.resolution())
        painter.translate(paint_rect.left(), paint_rect.top())
        painter.scale(scale, scale)
        document.drawContents(painter, QRectF(0.0, 0.0, logical_width, content_height))
        painter.end()


class ServiceOrderItemDialog(QDialog):
    def __init__(self, parent=None, *, products: list[dict] | None = None, presets: list[dict] | None = None, item: dict | None = None):
        super().__init__(parent)
        self.products = list(products or [])
        self.presets = list(presets or [])
        self.item = dict(item or {})
        self.setWindowTitle("Edit Order Item" if self.item else "Add Order Item")
        self.setMinimumSize(560, 680)
        outer = QVBoxLayout(self); form = QFormLayout()
        self.preset = QComboBox(); self.preset.addItem("No preset / manual", None)
        for preset in self.presets: self.preset.addItem(str(preset.get("name") or "Preset"), preset)
        self.item_type = QComboBox(); self.item_type.addItem("Service", "service"); self.item_type.addItem("Part", "part"); self.item_type.addItem("Custom Charge", "custom")
        self.product = QComboBox(); self.variant = QComboBox()
        self.description = QLineEdit(str(self.item.get("description") or ""))
        self.qty = QDoubleSpinBox(); self.qty.setRange(0.01, 999999); self.qty.setDecimals(2); self.qty.setValue(float(self.item.get("qty") or 1))
        self.unit_price = QDoubleSpinBox(); self.unit_price.setRange(0, 999999999999); self.unit_price.setDecimals(0); self.unit_price.setSuffix(" Ks")
        self.unit_price.setValue(float(self.item.get("unit_price") or 0))
        self.estimated_cost = QDoubleSpinBox(); self.estimated_cost.setRange(0, 999999999999); self.estimated_cost.setDecimals(0); self.estimated_cost.setSuffix(" Ks")
        self.estimated_cost.setValue(float(self.item.get("estimated_cost") or 0))
        self.warranty_days = QSpinBox(); self.warranty_days.setRange(0, 36500); self.warranty_days.setSuffix(" days")
        self.warranty_days.setValue(int(self.item.get("warranty_days") or 0))
        self.pricing_unit = QComboBox()
        for label, value in (("Per Page", "per_page"), ("Per Sheet", "per_sheet"), ("Per Copy", "per_copy"), ("Per Job", "per_job"), ("Per Item", "per_item")):
            self.pricing_unit.addItem(label, value)
        pricing_index = self.pricing_unit.findData(str(self.item.get("pricing_unit") or "per_item")); self.pricing_unit.setCurrentIndex(max(0, pricing_index))
        self.pages_per_copy = QSpinBox(); self.pages_per_copy.setRange(1, 1000000); self.pages_per_copy.setValue(int(self.item.get("pages_per_copy") or 1))
        self.copy_count = QSpinBox(); self.copy_count.setRange(1, 1000000); self.copy_count.setValue(int(self.item.get("copy_count") or 1))
        self.paper_size = QComboBox(); self.paper_size.setEditable(True); self.paper_size.addItems(["", "A4", "A3", "A5", "Letter", "Legal", "4×6 Photo", "5×7 Photo", "Custom"])
        self.paper_size.setCurrentText(str(self.item.get("paper_size") or ""))
        self.paper_type = QComboBox(); self.paper_type.setEditable(True); self.paper_type.addItems(["", "Normal 70gsm", "Normal 80gsm", "Photo Glossy", "Photo Matte", "Sticker", "Card", "Customer Paper"])
        self.paper_type.setCurrentText(str(self.item.get("paper_type") or ""))
        self.color_mode = QComboBox()
        for label, value in (("Not Applicable", "not_applicable"), ("Black & White", "bw"), ("Color", "color"), ("Photo", "photo")): self.color_mode.addItem(label, value)
        self.color_mode.setCurrentIndex(max(0, self.color_mode.findData(str(self.item.get("color_mode") or "not_applicable"))))
        self.print_side = QComboBox()
        for label, value in (("Not Applicable", "not_applicable"), ("Single Side", "single"), ("Double Side", "double")): self.print_side.addItem(label, value)
        self.print_side.setCurrentIndex(max(0, self.print_side.findData(str(self.item.get("print_side") or "not_applicable"))))
        self.finishing = QLineEdit(str(self.item.get("finishing") or "")); self.finishing.setPlaceholderText("Staple, binding, lamination, cutting…")
        self.file_name = QLineEdit(str(self.item.get("file_name") or ""))
        self.total_sheets_label = QLabel("1 sheet", objectName="muted")
        self.line_amount_label = QLabel("0 Ks", objectName="title")
        current_type = str(self.item.get("item_type") or "service")
        index = self.item_type.findData(current_type); self.item_type.setCurrentIndex(max(0, index))
        for label, widget in (("Quick Preset", self.preset), ("Type", self.item_type), ("Product", self.product), ("Variant", self.variant), ("Description", self.description),
                              ("Pricing Unit", self.pricing_unit), ("Pages / Copy", self.pages_per_copy), ("Copies", self.copy_count),
                              ("Paper Size", self.paper_size), ("Paper Type", self.paper_type), ("Color", self.color_mode),
                              ("Print Side", self.print_side), ("Finishing", self.finishing), ("File Name", self.file_name),
                              ("Billable Quantity", self.qty), ("Physical Sheets", self.total_sheets_label),
                              ("Unit Price", self.unit_price), ("Line Amount", self.line_amount_label),
                              ("Estimated Cost", self.estimated_cost), ("Warranty", self.warranty_days)):
            form.addRow(label, widget)
        outer.addLayout(form)
        note = QLabel("Parts stock is checked now but will only be deducted during Phase 5 checkout.", objectName="muted"); note.setWordWrap(True); outer.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate); buttons.rejected.connect(self.reject); outer.addWidget(buttons)
        self.item_type.currentIndexChanged.connect(self._populate_products)
        self.preset.currentIndexChanged.connect(self._apply_preset)
        self.product.currentIndexChanged.connect(self._product_changed)
        self.variant.currentIndexChanged.connect(self._variant_changed)
        self.pricing_unit.currentIndexChanged.connect(self._recalculate_print_totals)
        self.pages_per_copy.valueChanged.connect(self._recalculate_print_totals)
        self.copy_count.valueChanged.connect(self._recalculate_print_totals)
        self.print_side.currentIndexChanged.connect(self._recalculate_print_totals)
        self.qty.valueChanged.connect(self._recalculate_print_totals)
        self.unit_price.valueChanged.connect(self._recalculate_print_totals)
        self._populate_products()
        self._recalculate_print_totals()

    def _apply_preset(self) -> None:
        preset = self.preset.currentData() or {}
        if not preset:
            return
        service_index = self.item_type.findData("service"); self.item_type.setCurrentIndex(max(0, service_index))
        product_id = int(preset.get("product_id") or 0)
        for index in range(self.product.count()):
            product = self.product.itemData(index) or {}
            if int(product.get("id") or 0) == product_id:
                self.product.setCurrentIndex(index); break
        self.description.setText(str(preset.get("description") or preset.get("name") or ""))
        for combo, key in ((self.pricing_unit, "pricing_unit"), (self.color_mode, "color_mode"), (self.print_side, "print_side")):
            index = combo.findData(str(preset.get(key) or ""))
            if index >= 0: combo.setCurrentIndex(index)
        self.pages_per_copy.setValue(int(preset.get("pages_per_copy") or 1)); self.copy_count.setValue(int(preset.get("copy_count") or 1))
        self.paper_size.setCurrentText(str(preset.get("paper_size") or "")); self.paper_type.setCurrentText(str(preset.get("paper_type") or ""))
        self.finishing.setText(str(preset.get("finishing") or "")); self.unit_price.setValue(float(preset.get("unit_price") or 0))
        self._recalculate_print_totals()

    def _populate_products(self) -> None:
        item_type = str(self.item_type.currentData() or "service")
        current_id = int(self.item.get("product_id") or 0)
        self.product.blockSignals(True); self.product.clear()
        if item_type == "custom":
            self.product.addItem("No catalog product", None)
        else:
            for product in self.products:
                mode = sold_by_mode(product.get("sold_by"))
                if (item_type == "service" and mode == "service") or (item_type == "part" and mode != "service"):
                    stock = "Service" if mode == "service" else int(product.get("stock") or 0)
                    self.product.addItem(f"{product.get('name') or 'Product'} · {stock}", product)
        self.product.blockSignals(False)
        if current_id:
            for index in range(self.product.count()):
                data = self.product.itemData(index) or {}
                if int(data.get("id") or 0) == current_id:
                    self.product.setCurrentIndex(index); break
        self._product_changed()

    def _product_changed(self) -> None:
        product = self.product.currentData() or {}
        self.variant.blockSignals(True); self.variant.clear()
        variants = list(product.get("variants") or [])
        for variant in variants:
            label = " / ".join(filter(None, (str(variant.get("color") or ""), str(variant.get("size") or "")))) or f"Variant {variant.get('variant_id') or variant.get('id')}"
            self.variant.addItem(f"{label} · Stock {int(variant.get('stock') or 0)}", variant)
        current_variant = int(self.item.get("variant_id") or 0)
        if current_variant:
            for index in range(self.variant.count()):
                data = self.variant.itemData(index) or {}
                if int(data.get("variant_id") or data.get("id") or 0) == current_variant:
                    self.variant.setCurrentIndex(index); break
        self.variant.blockSignals(False)
        is_custom = str(self.item_type.currentData()) == "custom"
        self.product.setEnabled(not is_custom); self.variant.setVisible(bool(variants) and not is_custom)
        if product and not self.item:
            self.description.setText(str(product.get("name") or ""))
            self.unit_price.setValue(float(product.get("price") or 0))
        self._variant_changed()

    def _variant_changed(self) -> None:
        variant = self.variant.currentData() or {}
        if variant and not self.item:
            self.unit_price.setValue(float(variant.get("price") or self.unit_price.value()))

    def _recalculate_print_totals(self) -> None:
        pages = self.pages_per_copy.value(); copies = self.copy_count.value()
        side = str(self.print_side.currentData() or "not_applicable")
        sheets_per_copy = (pages + 1) // 2 if side == "double" else pages
        total_sheets = sheets_per_copy * copies
        pricing = str(self.pricing_unit.currentData() or "per_item")
        quantities = {"per_page": pages * copies, "per_sheet": total_sheets, "per_copy": copies, "per_job": 1}
        automatic = pricing in quantities
        if automatic:
            self.qty.blockSignals(True); self.qty.setValue(float(quantities[pricing])); self.qty.blockSignals(False)
        self.qty.setEnabled(not automatic)
        self.total_sheets_label.setText(f"{total_sheets:,} sheet(s)")
        self.line_amount_label.setText(f"{self.qty.value() * self.unit_price.value():,.0f} Ks")

    def _validate(self) -> None:
        item_type = str(self.item_type.currentData() or "service")
        if item_type != "custom" and not self.product.currentData():
            QMessageBox.warning(self, "Order Item", "Select a catalog product."); return
        product = self.product.currentData() or {}
        if item_type == "part" and sold_by_mode(product.get("sold_by")) == "variants" and not self.variant.currentData():
            QMessageBox.warning(self, "Order Item", "Select a product variant."); return
        if not self.description.text().strip():
            QMessageBox.warning(self, "Order Item", "Enter a description."); return
        self.accept()

    def values(self) -> dict:
        product = self.product.currentData() or {}
        variant = self.variant.currentData() or {}
        item_type = str(self.item_type.currentData() or "service")
        return {
            "product_id": int(product.get("id") or 0) or None if item_type != "custom" else None,
            "variant_id": int(variant.get("variant_id") or variant.get("id") or 0) or None if item_type != "custom" else None,
            "item_type": item_type, "description": self.description.text().strip(), "qty": self.qty.value(),
            "unit_price": self.unit_price.value(), "estimated_cost": self.estimated_cost.value(),
            "actual_cost": float(self.item.get("actual_cost") or 0), "warranty_days": self.warranty_days.value(),
            "pricing_unit": str(self.pricing_unit.currentData() or "per_item"),
            "pages_per_copy": self.pages_per_copy.value(), "copy_count": self.copy_count.value(),
            "paper_size": self.paper_size.currentText().strip(), "paper_type": self.paper_type.currentText().strip(),
            "color_mode": str(self.color_mode.currentData() or "not_applicable"),
            "print_side": str(self.print_side.currentData() or "not_applicable"),
            "finishing": self.finishing.text().strip(), "file_name": self.file_name.text().strip(),
        }


class ServiceOrderDialog(QDialog):
    """Simple shared job form, intentionally independent from POS checkout."""

    def __init__(self, parent=None, *, order: dict | None = None, customers: list[dict] | None = None):
        super().__init__(parent)
        self.order = dict(order or {})
        self.customers = list(customers or [])
        self.setWindowTitle("Edit Service Order" if self.order else "New Service Order")
        self.setMinimumWidth(560)
        outer = QVBoxLayout(self)
        form = QFormLayout()
        received = str(self.order.get("received_at") or "")
        received_date, received_time = (received[:10], received[11:16]) if received else (QDate.currentDate().toString("yyyy-MM-dd"), QTime.currentTime().toString("HH:mm"))
        self.job_date = QLineEdit(received_date)
        self.job_date.setPlaceholderText("YYYY-MM-DD")
        self.job_time = QLineEdit(received_time)
        self.job_time.setPlaceholderText("HH:MM")
        self.job_title = QLineEdit(str(self.order.get("job_title") or ""))
        self.job_title.setPlaceholderText("Job name")
        self.complaint = QTextEdit(str(self.order.get("complaint") or "")); self.complaint.setMaximumHeight(110)
        self.expected_at = QLineEdit(str(self.order.get("expected_at") or "")); self.expected_at.setPlaceholderText("YYYY-MM-DD HH:MM")
        self.internal_notes = QTextEdit(str(self.order.get("internal_notes") or "")); self.internal_notes.setMaximumHeight(90)
        for label, widget in (
            ("Date", self.job_date), ("Time", self.job_time), ("Job Name", self.job_title),
            ("Details", self.complaint), ("Appointment", self.expected_at), ("Notes", self.internal_notes),
        ):
            form.addRow(label, widget)
        outer.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate); buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _validate(self) -> None:
        if not self.job_title.text().strip():
            QMessageBox.warning(self, "Service Order", "Enter a job title.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "received_at": f"{self.job_date.text().strip()} {self.job_time.text().strip()}".strip(),
            "expected_at": self.expected_at.text().strip(),
            "job_title": self.job_title.text().strip(),
            "complaint": self.complaint.toPlainText().strip(),
            "internal_notes": self.internal_notes.toPlainText().strip(),
        }


class LiteWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KAY POS Lite")
        self.resize(1180, 680)
        self.setMinimumSize(960, 600)
        self.theme_name = normalize_theme(load_config().get("theme"))
        self.api: LiteApiClient | None = None
        self.user: dict = {}
        self.products: list[dict] = []
        self.product_page_size = 50
        self.product_has_more = False
        self.thumbnail_cache: dict[int, QPixmap] = {}
        self.thumbnail_pending: set[int] = set()
        self.product_rows: dict[int, int] = {}
        self.product_grid_items: dict[int, QListWidgetItem] = {}
        self.product_grid_tiles: dict[int, ProductGridTile] = {}
        self.product_view_mode = str(load_config().get("product_view") or "grid")
        self.management_product_rows: dict[int, int] = {}
        self.managed_product_rows: dict[int, int] = {}
        self._page_load_tokens: dict[str, int] = {}
        self.thumbnail_manager = QNetworkAccessManager(self)
        self.thumbnail_timer = QTimer(self)
        self.thumbnail_timer.setSingleShot(True)
        self.thumbnail_timer.setInterval(80)
        self.thumbnail_timer.timeout.connect(self._load_visible_product_thumbnails)
        self.management_thumbnail_timer = QTimer(self)
        self.management_thumbnail_timer.setSingleShot(True)
        self.management_thumbnail_timer.setInterval(80)
        self.management_thumbnail_timer.timeout.connect(self._load_visible_management_thumbnails)
        self.product_management_thumbnail_timer = QTimer(self)
        self.product_management_thumbnail_timer.setSingleShot(True)
        self.product_management_thumbnail_timer.setInterval(80)
        self.product_management_thumbnail_timer.timeout.connect(self._load_visible_managed_product_thumbnails)
        self.selected_category = ""
        self.receipts: list[dict] = []
        self.service_orders_data: list[dict] = []
        self.selected_service_order: dict = {}
        self.last_receipt: dict = {}
        self.receipt_settings: dict = {}
        self.sale_display: LiteSaleDisplay | None = None
        self.history_offset = 0
        self.cart = LiteCart()
        self._threads: set[QThread] = set()
        self._workers: set[TaskWorker] = set()
        self._scan_in_progress = False
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350)
        self.search_timer.timeout.connect(self.load_products)
        self.service_job_timer = QTimer(self)
        self.service_job_timer.setInterval(5000)
        self.service_job_timer.timeout.connect(self._poll_service_jobs)
        self._known_service_job_ids: set[int] | None = None
        self._service_job_polling = False
        self.service_job_tray = QSystemTrayIcon(QApplication.instance().windowIcon(), self)
        self.service_job_tray.setToolTip("KAY POS Service Jobs")
        self.service_job_tray.show()

        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.login_page = QWidget()
        self.login_dialog = self._build_login_dialog()
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
        self._apply_theme_styles()
        self.statusBar().showMessage("Ready")
        self._shortcuts = []
        self._add_shortcut("F11", self.toggle_full_screen)
        self._add_shortcut("Esc", self.exit_full_screen)
        self._add_shortcut("F2", lambda: self._focus_product_search(select_all=True))
        self._add_shortcut("F4", self.open_checkout)
        self._add_shortcut("Ctrl+P", self.print_last_receipt)
        self._add_shortcut("Ctrl+Shift+D", self.open_cash_drawer)
        self._add_shortcut("Ctrl+Shift+P", self.open_printer_settings)

    def _apply_theme_styles(self) -> None:
        if self.theme_name == "Dark":
            foreground, background, border = "#dce3f3", "#20283a", "#36415a"
        else:
            foreground, background, border = "#334155", "#eef1ff", "#c7cefa"
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                color: {foreground};
                background: {background};
                border-top: 1px solid {border};
                padding: 2px 8px;
            }}
            QStatusBar::item {{ border: 0; }}
        """)

    def apply_theme(self, theme_name: str, persist: bool = True) -> str:
        app = QApplication.instance()
        self.theme_name = normalize_theme(theme_name)
        if app is not None:
            self.theme_name = apply_lite_theme(app, self.theme_name)
        self._apply_theme_styles()
        if persist:
            save_config({"theme": self.theme_name})
        return self.theme_name

    def _add_shortcut(self, sequence: str, callback: Callable) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.statusBar().showMessage("Full screen closed")
        else:
            self.showFullScreen()
            self.statusBar().showMessage("Full screen · Press F11 or Esc to exit")

    def exit_full_screen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.statusBar().showMessage("Full screen closed")

    def _build_login_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("Sign in · KAY POS Lite")
        dialog.setModal(True)
        dialog.setFixedSize(470, 380)
        dialog.rejected.connect(self.close)
        body = QVBoxLayout(dialog)
        body.setContentsMargins(30, 24, 30, 24)
        body.setSpacing(10)
        brand = QLabel("KAY POS LITE", objectName="brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Welcome back", objectName="title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Sign in to continue to your KAY POS workspace.", objectName="muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        body.addWidget(brand)
        body.addWidget(title)
        body.addWidget(subtitle)

        config = load_config()
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.server_input = QLineEdit(config["server_url"])
        self.server_input.setMinimumWidth(285)
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
        self.login_status.setMinimumHeight(34)
        self.login_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.addWidget(self.login_status)
        buttons = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.setMinimumWidth(120)
        self.test_button.clicked.connect(self.test_connection)
        self.login_button = QPushButton("Sign In", objectName="primary")
        self.login_button.setMinimumWidth(100)
        self.login_button.clicked.connect(self.login)
        buttons.addWidget(self.test_button)
        buttons.addStretch()
        buttons.addWidget(self.login_button)
        body.addLayout(buttons)
        return dialog

    def show_login_dialog(self) -> None:
        if self.api or self.login_dialog.isVisible():
            return
        self.login_dialog.show()
        screen = QApplication.primaryScreen()
        parent_center = (
            self.frameGeometry().center()
            if self.isVisible()
            else screen.availableGeometry().center() if screen else self.frameGeometry().center()
        )
        dialog_frame = self.login_dialog.frameGeometry()
        dialog_frame.moveCenter(parent_center)
        self.login_dialog.move(dialog_frame.topLeft())
        self.login_dialog.raise_()
        self.login_dialog.activateWindow()
        self.username_input.setFocus()

    def _build_workspace_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        nav = QFrame(objectName="nav")
        nav.setFixedWidth(180)
        # Match the KAY POS Lite tile in Launcher. Keep this stylesheet scoped
        # to the navigation frame so the rest of Lite retains native Qt styling.
        nav.setStyleSheet("""
            QFrame#nav {
                background: #5365df;
                border: 0;
            }
            QFrame#nav QLabel {
                color: #ffffff;
                background: transparent;
            }
            QFrame#nav QLabel#brand {
                font-weight: 800;
            }
            QFrame#nav QPushButton {
                min-height: 38px;
                padding: 0 11px;
                text-align: left;
                color: #eef1ff;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                font-weight: 600;
            }
            QFrame#nav QPushButton:hover {
                color: #ffffff;
                background: #6575e7;
            }
            QFrame#nav QPushButton:checked {
                color: #ffffff;
                background: #3f50c6;
                border-color: #8490ef;
            }
            QFrame#nav QPushButton#signOutButton {
                color: #ffffff;
                background: #4658cd;
                border-color: #7180e8;
            }
            QFrame#nav QPushButton#signOutButton:hover {
                background: #3949b5;
            }
        """)
        menu = QVBoxLayout(nav)
        menu.setContentsMargins(12, 17, 12, 14)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for text in ("Point of Sale", "Service Orders", "Dashboard", "Products", "Sales History", "Expenses", "Inventory", "Customers", "Setting Center"):
            button = QPushButton(text)
            button.setProperty("leftAligned", True)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=text: self._activate_workspace(name))
            self.nav_group.addButton(button)
            self.nav_buttons[text] = button
            menu.addWidget(button)
        menu.addStretch()
        self.identity_label = QLabel("")
        self.identity_label.setWordWrap(True)
        menu.addWidget(self.identity_label)
        logout = QPushButton("Sign Out")
        logout.setObjectName("signOutButton")
        logout.setProperty("leftAligned", True)
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
        current_date = QDate.currentDate()
        month_start = QDate(current_date.year(), current_date.month(), 1)
        self.dashboard_period_label = QLabel("This Month · AI Dashboard metrics")
        summary_top.addWidget(self.dashboard_period_label)
        summary_top.addStretch()
        summary_top.addWidget(QLabel("From"))
        self.dashboard_from = QDateEdit(month_start)
        self.dashboard_from.setCalendarPopup(True)
        self.dashboard_from.setDisplayFormat("yyyy-MM-dd")
        summary_top.addWidget(self.dashboard_from)
        summary_top.addWidget(QLabel("To"))
        self.dashboard_to = QDateEdit(current_date)
        self.dashboard_to.setCalendarPopup(True)
        self.dashboard_to.setDisplayFormat("yyyy-MM-dd")
        summary_top.addWidget(self.dashboard_to)
        dashboard_today = QPushButton("Today")
        dashboard_today.clicked.connect(self._dashboard_today)
        summary_top.addWidget(dashboard_today)
        refresh_summary = QPushButton("Refresh")
        refresh_summary.clicked.connect(self.load_dashboard)
        summary_top.addWidget(refresh_summary)
        card_body.addLayout(summary_top)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        self.dashboard_sales = QLabel("Net Sales\n—", objectName="title")
        self.dashboard_transactions = QLabel("Transactions\n—", objectName="title")
        self.dashboard_gross_profit = QLabel("Gross Profit\n—", objectName="title")
        self.dashboard_expenses = QLabel("Expenses\n—", objectName="title")
        self.dashboard_net_profit = QLabel("Net Profit\n—", objectName="title")
        self.dashboard_refunds = QLabel("Refunds\n—", objectName="title")
        self.dashboard_low_stock = QLabel("Low / Out of Stock\n— / —", objectName="title")
        self.dashboard_credit = QLabel("Outstanding Credit\n—", objectName="title")
        self.dashboard_metrics = (
            self.dashboard_sales, self.dashboard_transactions,
            self.dashboard_gross_profit, self.dashboard_expenses,
            self.dashboard_net_profit, self.dashboard_refunds,
            self.dashboard_low_stock, self.dashboard_credit,
        )
        for index, metric in enumerate(self.dashboard_metrics):
            metric.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metric.setMinimumHeight(72)
            metric.setFrameShape(QFrame.Shape.StyledPanel)
            metrics.addWidget(metric, index // 4, index % 4)
        card_body.addLayout(metrics)
        content_layout.addWidget(card)

        self.dashboard_analytics = QTabWidget()
        self.dashboard_analytics.setMinimumHeight(245)
        sale_categories_page, self.dashboard_sale_categories, self.dashboard_sale_categories_status, self.dashboard_sale_categories_total = self._dashboard_analytics_page(
            ["Sale Category", "Quantity", "Sales"]
        )
        expense_categories_page, self.dashboard_expense_categories, self.dashboard_expense_categories_status, self.dashboard_expense_categories_total = self._dashboard_analytics_page(
            ["Expense Category", "Entries", "Amount"]
        )
        payment_types_page, self.dashboard_payment_types, self.dashboard_payment_types_status, self.dashboard_payment_types_total = self._dashboard_analytics_page(
            ["Payment Type", "Transactions", "Sales"]
        )
        daily_trend_page, self.dashboard_daily_trend, self.dashboard_daily_trend_status, self.dashboard_daily_trend_total = self._dashboard_analytics_page(
            ["Date", "Sales"]
        )
        self.dashboard_analytics.addTab(sale_categories_page, "Sale Categories")
        self.dashboard_analytics.addTab(expense_categories_page, "Expense Categories")
        self.dashboard_analytics.addTab(payment_types_page, "Sales by Payment Type")
        self.dashboard_analytics.addTab(daily_trend_page, "Daily Sales Trend")
        content_layout.addWidget(self.dashboard_analytics, 1)
        self.pos_page = self._build_pos_page()
        self.service_orders_page = self._build_service_orders_page()
        self.product_management_page = self._build_product_management_page()
        self.history_page = self._build_history_page()
        self.expense_page = self._build_expense_page()
        self.management_page = self._build_management_page()
        self.customer_page = self._build_customer_page()
        self.settings_page = LiteSettingsCenter(self)
        self.workspace_stack.addWidget(self.dashboard_page)
        self.workspace_stack.addWidget(self.pos_page)
        self.workspace_stack.addWidget(self.service_orders_page)
        self.workspace_stack.addWidget(self.product_management_page)
        self.workspace_stack.addWidget(self.history_page)
        self.workspace_stack.addWidget(self.expense_page)
        self.workspace_stack.addWidget(self.management_page)
        self.workspace_stack.addWidget(self.customer_page)
        self.workspace_stack.addWidget(self.settings_page)
        self.workspace_pages = {
            "Dashboard": self.dashboard_page,
            "Point of Sale": self.pos_page,
            "Service Orders": self.service_orders_page,
            "Products": self.product_management_page,
            "Sales History": self.history_page,
            "Expenses": self.expense_page,
            "Inventory": self.management_page,
            "Customers": self.customer_page,
            "Setting Center": self.settings_page,
        }
        self.workspace_stack.currentChanged.connect(self._sync_nav_selection)
        self.nav_buttons["Dashboard"].setChecked(True)
        row.addWidget(self.workspace_stack, 1)
        return page

    @staticmethod
    def _dashboard_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(headers)):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        return table

    @classmethod
    def _dashboard_analytics_page(cls, headers: list[str]) -> tuple[QWidget, QTableWidget, QLabel, QLabel]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        table = cls._dashboard_table(headers)
        layout.addWidget(table, 1)
        footer = QFrame()
        footer.setFrameShape(QFrame.Shape.StyledPanel)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 5, 8, 5)
        status = QLabel("0 item(s) loaded")
        total = QLabel("Total · 0 Ks")
        footer_layout.addWidget(status)
        footer_layout.addStretch()
        footer_layout.addWidget(total)
        layout.addWidget(footer)
        return page, table, status, total

    @staticmethod
    def _set_dashboard_footer(status: QLabel, total_label: QLabel, count: int, noun: str, total: float) -> None:
        status.setText(f"{int(count):,} {noun}(s) loaded")
        total_label.setText(f"Total · {float(total or 0):,.0f} Ks")

    @staticmethod
    def _fill_dashboard_table(table: QTableWidget, rows: list[tuple]) -> None:
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_index, column, item)
        table.setUpdatesEnabled(True)
        table.viewport().update()

    def _activate_workspace(self, name: str) -> None:
        page = self.workspace_pages.get(name)
        if page is None:
            return
        self.workspace_stack.setCurrentWidget(page)
        if name == "Point of Sale":
            self._focus_product_search()
        elif name == "Service Orders":
            self.load_service_orders()
        elif name == "Dashboard":
            self.load_dashboard()
        elif name == "Products":
            self.load_product_management()
        elif name == "Sales History":
            self.history_offset = 0
            self.load_history()
        elif name == "Expenses":
            self.load_expenses()
        elif name == "Inventory":
            self.load_management()
        elif name == "Customers":
            self.load_customers()
        elif name == "Setting Center":
            self.settings_page.refresh()

    def _sync_nav_selection(self, _index: int) -> None:
        current = self.workspace_stack.currentWidget()
        for name, page in self.workspace_pages.items():
            if page is current:
                self.nav_buttons[name].setChecked(True)
                break
        if current is self.pos_page:
            self._focus_product_search()

    def _focus_product_search(self, *, select_all: bool = False) -> None:
        """Return scanner input to the POS search box after page/task changes."""
        def focus() -> None:
            if self.workspace_stack.currentWidget() is not self.pos_page:
                return
            self.product_search.setFocus(Qt.FocusReason.OtherFocusReason)
            if select_all:
                self.product_search.selectAll()

        QTimer.singleShot(0, focus)

    def _build_expense_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Expenses", objectName="title"))
        self.expense_search = QLineEdit()
        self.expense_search.setPlaceholderText("Search category, description or reference…")
        self.expense_search.returnPressed.connect(self.load_expenses)
        self.expense_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.expense_to = QDateEdit(QDate.currentDate())
        for editor in (self.expense_from, self.expense_to):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("yyyy-MM-dd")
        refresh = QPushButton("Search / Refresh")
        refresh.clicked.connect(self.load_expenses)
        add = QPushButton("Add Expense")
        add.clicked.connect(self.add_expense)
        top.addWidget(self.expense_search, 1)
        top.addWidget(QLabel("From"))
        top.addWidget(self.expense_from)
        top.addWidget(QLabel("To"))
        top.addWidget(self.expense_to)
        top.addWidget(refresh)
        top.addWidget(add)
        outer.addLayout(top)
        self.expense_table = QTableWidget(0, 7)
        self.expense_table.setHorizontalHeaderLabels([
            "Date", "Expense No", "Category", "Description", "Amount", "Payment", "Reference",
        ])
        self.expense_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.expense_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.expense_table.verticalHeader().setVisible(False)
        self.expense_table.verticalHeader().setDefaultSectionSize(27)
        self.expense_table.horizontalHeader().setFixedHeight(27)
        self.expense_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column, width in {0:95,1:125,2:130,4:110,5:105,6:125}.items():
            self.expense_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive); self.expense_table.setColumnWidth(column,width)
        self.expense_table.verticalScrollBar().valueChanged.connect(self._maybe_load_more_expenses)
        outer.addWidget(self.expense_table, 1)
        bottom = QHBoxLayout()
        self.expense_status = QLabel("", objectName="muted")
        self.expense_total = QLabel("Total · 0 Ks", objectName="title")
        bottom.addWidget(self.expense_status)
        bottom.addStretch()
        bottom.addWidget(self.expense_total)
        outer.addLayout(bottom)
        self.expense_categories: list[str] = []
        self.expense_categories_loaded = False
        self.expense_rows: list[dict] = []
        self.expense_page_size = 50
        self.expense_has_more = False
        return page

    def _build_management_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Inventory", objectName="title"))
        self.management_search = QLineEdit()
        self.management_search.setPlaceholderText("Search product, barcode or SKU…")
        self.management_search.returnPressed.connect(self.load_management)
        refresh = QPushButton("Search / Refresh")
        refresh.clicked.connect(self.load_management)
        top.addStretch()
        top.addWidget(self.management_search, 1)
        top.addWidget(refresh)
        outer.addLayout(top)
        stock_box = QFrame(objectName="card")
        stock_layout = QVBoxLayout(stock_box)
        stock_layout.setContentsMargins(9, 9, 9, 9)
        stock_layout.addWidget(QLabel("Products & Stock"))
        self.stock_table = QTableWidget(0, 5)
        self.stock_table.setHorizontalHeaderLabels(["Image", "Product", "Barcode / SKU", "Stock", "Variants"])
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stock_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.verticalHeader().setDefaultSectionSize(44)
        self.stock_table.setIconSize(QSize(44, 40))
        self.stock_table.setColumnWidth(0, 54)
        self.stock_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in {0:54,2:160,3:85,4:85}.items():
            self.stock_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive); self.stock_table.setColumnWidth(column,width)
        self.stock_table.verticalScrollBar().valueChanged.connect(
            lambda _value: self.management_thumbnail_timer.start()
        )
        stock_layout.addWidget(self.stock_table, 1)
        stock_actions = QHBoxLayout()
        stock_in = QPushButton("Stock In")
        stock_out = QPushButton("Stock Out")
        adjustment = QPushButton("Adjustment")
        transfer = QPushButton("Transfer")
        movements = QPushButton("View Movements")
        stock_in.clicked.connect(lambda: self.adjust_selected_stock(1))
        stock_out.clicked.connect(lambda: self.adjust_selected_stock(-1))
        adjustment.clicked.connect(self.adjust_selected_stock_quantity)
        transfer.clicked.connect(self.transfer_selected_stock)
        movements.clicked.connect(self.view_selected_stock_movements)
        stock_actions.addWidget(stock_in)
        stock_actions.addWidget(stock_out)
        stock_actions.addWidget(adjustment)
        stock_actions.addWidget(transfer)
        stock_actions.addWidget(movements)
        stock_actions.addStretch()
        stock_layout.addLayout(stock_actions)
        outer.addWidget(stock_box, 1)
        return page

    def _build_customer_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Customers", objectName="title"))
        top.addStretch()
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Search customer name or phone…")
        self.customer_search.returnPressed.connect(self.load_customers)
        refresh = QPushButton("Search / Refresh")
        refresh.clicked.connect(self.load_customers)
        top.addWidget(self.customer_search, 1)
        top.addWidget(refresh)
        outer.addLayout(top)
        customer_box = QFrame(objectName="card")
        customer_layout = QVBoxLayout(customer_box)
        customer_layout.setContentsMargins(9, 9, 9, 9)
        self.customer_table = QTableWidget(0, 4)
        self.customer_table.setHorizontalHeaderLabels(["Name", "Phone", "Points", "Balance"])
        self.customer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.customer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.customer_table.verticalHeader().setVisible(False)
        self.customer_table.verticalHeader().setDefaultSectionSize(29)
        self.customer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in {1:150,2:100,3:130}.items():
            self.customer_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive); self.customer_table.setColumnWidth(column,width)
        customer_layout.addWidget(self.customer_table, 1)
        outer.addWidget(customer_box, 1)
        self.customer_status = QLabel("", objectName="muted")
        outer.addWidget(self.customer_status)
        return page

    def _build_service_orders_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page); outer.setContentsMargins(14, 12, 14, 12); outer.setSpacing(8)
        top = QHBoxLayout(); top.addWidget(QLabel("Service Jobs", objectName="title")); top.addStretch()
        self.service_order_presets_button = QPushButton(); self.service_order_presets_button.hide()
        self.service_order_reports_button = QPushButton(); self.service_order_reports_button.hide()
        new_button = QPushButton("New Job", objectName="primary")
        new_button.clicked.connect(self.new_service_order)
        top.addWidget(self.service_order_presets_button); top.addWidget(self.service_order_reports_button); top.addWidget(new_button); outer.addLayout(top)
        filters = QHBoxLayout()
        self.service_order_search = QLineEdit(); self.service_order_search.setPlaceholderText("Search job name, details or notes…")
        self.service_order_search.returnPressed.connect(self.load_service_orders)
        self.service_order_status_filter = QComboBox()
        self.service_order_status_filter.addItem("All", "")
        self.service_order_status_filter.addItem("Not Completed", "received")
        self.service_order_status_filter.addItem("Completed", "completed")
        self.service_order_status_filter.currentIndexChanged.connect(self.load_service_orders)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.load_service_orders)
        filters.addWidget(self.service_order_search, 1); filters.addWidget(self.service_order_status_filter); filters.addWidget(refresh)
        outer.addLayout(filters)

        body = QHBoxLayout()
        list_panel = QFrame(objectName="card"); list_layout = QVBoxLayout(list_panel); list_layout.setContentsMargins(8, 8, 8, 8)
        self.service_order_table = QTableWidget(0, 7)
        self.service_order_table.setHorizontalHeaderLabels(["Date", "Time", "Job Name", "Details", "Appointment", "Status", "Completed By"])
        self.service_order_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.service_order_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.service_order_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.service_order_table.verticalHeader().setVisible(False); self.service_order_table.verticalHeader().setDefaultSectionSize(29)
        self.service_order_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.service_order_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column, width in {0:95, 1:70, 4:135, 5:90, 6:110}.items():
            self.service_order_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive); self.service_order_table.setColumnWidth(column, width)
        self.service_order_table.itemSelectionChanged.connect(self.load_selected_service_order)
        list_layout.addWidget(self.service_order_table, 1)
        self.service_order_list_status = QLabel("", objectName="muted"); list_layout.addWidget(self.service_order_list_status)
        body.addWidget(list_panel, 3)

        detail = QFrame(objectName="card"); detail.setMinimumWidth(340); detail.setMaximumWidth(460)
        detail_layout = QVBoxLayout(detail); detail_layout.setContentsMargins(10, 10, 10, 10)
        self.service_order_detail_title = QLabel("Select a service order", objectName="title"); self.service_order_detail_title.setWordWrap(True)
        self.service_order_detail_summary = QLabel("", objectName="muted"); self.service_order_detail_summary.setWordWrap(True)
        detail_layout.addWidget(self.service_order_detail_title); detail_layout.addWidget(self.service_order_detail_summary)
        detail_layout.addWidget(QLabel("Job Details"))
        self.service_order_items_table = QTableWidget(0, 4)
        self.service_order_items_table.hide()
        self.service_order_items_table.setHorizontalHeaderLabels(["Description", "Type", "Qty", "Amount"])
        self.service_order_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.service_order_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.service_order_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.service_order_items_table.verticalHeader().setVisible(False)
        self.service_order_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in {1:70, 2:45, 3:90}.items():
            self.service_order_items_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive); self.service_order_items_table.setColumnWidth(column, width)
        detail_layout.addStretch(1)
        item_actions = QHBoxLayout()
        self.service_order_add_item_button = QPushButton("Add Item"); self.service_order_add_item_button.clicked.connect(self.add_service_order_item)
        self.service_order_edit_item_button = QPushButton("Edit Item"); self.service_order_edit_item_button.clicked.connect(self.edit_service_order_item)
        self.service_order_remove_item_button = QPushButton("Remove Item"); self.service_order_remove_item_button.clicked.connect(self.remove_service_order_item)
        item_actions.addWidget(self.service_order_add_item_button); item_actions.addWidget(self.service_order_edit_item_button); item_actions.addWidget(self.service_order_remove_item_button); item_actions.addStretch()
        self.service_order_add_item_button.hide(); self.service_order_edit_item_button.hide(); self.service_order_remove_item_button.hide()
        detail_layout.addWidget(QLabel("Activity History"))
        self.service_order_history = QListWidget(); self.service_order_history.setMaximumHeight(125)
        detail_layout.addWidget(self.service_order_history)
        payment_actions = QHBoxLayout()
        self.service_order_deposit_button = QPushButton("Collect Deposit"); self.service_order_deposit_button.clicked.connect(self.collect_service_order_deposit)
        self.service_order_checkout_button = QPushButton("Checkout", objectName="primary"); self.service_order_checkout_button.clicked.connect(self.checkout_selected_service_order)
        self.service_order_job_ticket_button = QPushButton("Job Ticket"); self.service_order_job_ticket_button.clicked.connect(self.print_service_order_job_ticket)
        self.service_order_receipt_button = QPushButton("Receipt"); self.service_order_receipt_button.clicked.connect(self.view_service_order_receipt)
        payment_actions.addWidget(self.service_order_deposit_button); payment_actions.addWidget(self.service_order_checkout_button); payment_actions.addWidget(self.service_order_job_ticket_button); payment_actions.addWidget(self.service_order_receipt_button)
        self.service_order_deposit_button.hide(); self.service_order_checkout_button.hide(); self.service_order_job_ticket_button.hide(); self.service_order_receipt_button.hide()
        return_actions = QHBoxLayout()
        self.service_order_return_button = QPushButton("Add Return Visit"); self.service_order_return_button.clicked.connect(self.add_service_order_return_visit)
        self.service_order_close_return_button = QPushButton("Close Return"); self.service_order_close_return_button.clicked.connect(self.close_service_order_return_visit)
        return_actions.addWidget(self.service_order_return_button); return_actions.addWidget(self.service_order_close_return_button); return_actions.addStretch()
        self.service_order_return_button.hide(); self.service_order_close_return_button.hide()
        actions = QHBoxLayout()
        self.service_order_edit_button = QPushButton("Edit"); self.service_order_edit_button.clicked.connect(self.edit_service_order)
        self.service_order_next_status = QComboBox(); self.service_order_next_status.addItem("Completed", "completed")
        self.service_order_next_status.hide()
        self.service_order_change_button = QPushButton("Complete", objectName="primary"); self.service_order_change_button.clicked.connect(self.complete_selected_service_order)
        actions.addWidget(self.service_order_edit_button); actions.addStretch(); actions.addWidget(self.service_order_change_button)
        detail_layout.addLayout(actions)
        self._set_service_order_actions_enabled(False)
        body.addWidget(detail, 2); outer.addLayout(body, 1)
        return page

    def _build_product_management_page(self) -> QWidget:
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(14,12,14,12); outer.setSpacing(8)
        top = QHBoxLayout(); top.addWidget(QLabel("Products", objectName="title")); top.addStretch()
        self.manage_product_search = QLineEdit(); self.manage_product_search.setPlaceholderText("Search name, SKU or barcode…"); self.manage_product_search.returnPressed.connect(self.load_product_management)
        search = QPushButton("Search / Refresh"); categories = QPushButton("Manage Categories"); add = QPushButton("Add Product"); edit = QPushButton("Edit Product")
        search.clicked.connect(self.load_product_management); categories.clicked.connect(self.manage_categories); add.clicked.connect(self.add_managed_product); edit.clicked.connect(self.edit_managed_product)
        top.addWidget(self.manage_product_search,1); top.addWidget(search); top.addWidget(categories); top.addWidget(add); top.addWidget(edit); outer.addLayout(top)
        self.manage_product_table = QTableWidget(0,9)
        self.manage_product_table.setHorizontalHeaderLabels(["Image","Product","Category","SKU / Barcode","Sold By","Price","Cost","Stock","Low Stock"])
        self.manage_product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.manage_product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.manage_product_table.verticalHeader().setVisible(False); self.manage_product_table.verticalHeader().setDefaultSectionSize(44); self.manage_product_table.setIconSize(QSize(44,40))
        self.manage_product_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        for column,width in {0:54,2:120,3:160,4:90,5:90,6:90,7:75,8:85}.items(): self.manage_product_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive); self.manage_product_table.setColumnWidth(column,width)
        self.manage_product_table.verticalScrollBar().valueChanged.connect(
            lambda _value: self.product_management_thumbnail_timer.start()
        )
        self.manage_product_table.doubleClicked.connect(self.edit_managed_product); outer.addWidget(self.manage_product_table,1)
        self.manage_product_status = QLabel("", objectName="muted"); outer.addWidget(self.manage_product_status)
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
        for column,width in {1:145,3:110,4:70,5:110,6:95}.items():
            self.history_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive); self.history_table.setColumnWidth(column,width)
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
        self.product_search.setToolTip("Scan or enter a barcode / SKU · Press F2 to focus")
        self.product_search.textChanged.connect(lambda: self.search_timer.start())
        self.product_search.returnPressed.connect(self.scan_or_search)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load_products)
        search_row.addWidget(self.product_search, 1)
        self.list_view_button = QPushButton("List")
        self.grid_view_button = QPushButton("Grid")
        self.product_view_group = QButtonGroup(self)
        self.product_view_group.setExclusive(True)
        for button in (self.list_view_button, self.grid_view_button):
            button.setCheckable(True)
            self.product_view_group.addButton(button)
        self.list_view_button.setToolTip("Show products as a compact list")
        self.grid_view_button.setToolTip("Show products as image cards")
        self.list_view_button.clicked.connect(lambda: self.set_product_view("list"))
        self.grid_view_button.clicked.connect(lambda: self.set_product_view("grid"))
        self.list_view_button.setChecked(self.product_view_mode == "list")
        self.grid_view_button.setChecked(self.product_view_mode == "grid")
        search_row.addWidget(self.list_view_button)
        search_row.addWidget(self.grid_view_button)
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
        self.product_table = QTableWidget(0, 6)
        self.product_table.setHorizontalHeaderLabels(["Image", "Product", "Barcode / SKU", "Price", "Stock", "Variants"])
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.product_table.verticalHeader().setVisible(False)
        self.product_table.verticalHeader().setDefaultSectionSize(44)
        self.product_table.horizontalHeader().setFixedHeight(27)
        self.product_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.product_table.setColumnWidth(0, 48)
        self.product_table.setIconSize(QSize(44, 40))
        self.product_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column,width in {2:150,3:90,4:75,5:80}.items():
            self.product_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive); self.product_table.setColumnWidth(column,width)
        self.product_table.clicked.connect(self.add_selected_product)
        self.product_table.verticalScrollBar().valueChanged.connect(self._maybe_load_more_products)
        self.product_table.verticalScrollBar().valueChanged.connect(lambda _value: self.thumbnail_timer.start())
        self.product_grid = ResponsiveProductGrid()
        self.product_grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.product_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.product_grid.setMovement(QListWidget.Movement.Static)
        self.product_grid.setWrapping(True)
        self.product_grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.product_grid.setSpacing(ResponsiveProductGrid.tile_spacing)
        self.product_grid.setUniformItemSizes(True)
        self.product_grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.product_grid.itemClicked.connect(self.add_grid_product)
        self.product_grid.verticalScrollBar().valueChanged.connect(self._maybe_load_more_products)
        self.product_grid.verticalScrollBar().valueChanged.connect(lambda _value: self.thumbnail_timer.start())
        self.product_view_stack = QStackedWidget()
        self.product_view_stack.addWidget(self.product_table)
        self.product_view_stack.addWidget(self.product_grid)
        self.product_view_stack.setCurrentWidget(
            self.product_grid if self.product_view_mode == "grid" else self.product_table
        )
        body.addWidget(self.product_view_stack, 3)

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
        for column,width in {1:55,2:80,3:90}.items():
            self.cart_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive); self.cart_table.setColumnWidth(column,width)
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
        self.checkout_button.setToolTip("Complete the current sale · F4")
        self.checkout_button.setMinimumHeight(46)
        self.checkout_button.setEnabled(False)
        self.checkout_button.clicked.connect(self.open_checkout)
        cart_layout.addWidget(self.checkout_button)
        receipt_actions = QHBoxLayout()
        self.add_expense_button = QPushButton("Add Expense")
        self.add_expense_button.setToolTip("Record a new business expense")
        self.add_expense_button.clicked.connect(self.add_expense)
        self.cash_drawer_button = QPushButton("Cash Drawer")
        self.cash_drawer_button.setToolTip("Open the drawer through this PC's receipt printer (Ctrl+Shift+D)")
        self.cash_drawer_button.clicked.connect(self.open_cash_drawer)
        self.sale_display_button = QPushButton("Sale Display")
        self.sale_display_button.setToolTip("Show the live customer cart full-screen on an extended display")
        self.sale_display_button.clicked.connect(self.toggle_sale_display)
        receipt_actions.addWidget(self.add_expense_button)
        receipt_actions.addWidget(self.cash_drawer_button)
        receipt_actions.addWidget(self.sale_display_button)
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

    def _new_page_load(self, page: str) -> int:
        """Return a generation token so pages can load independently and discard stale replies."""
        token = self._page_load_tokens.get(page, 0) + 1
        self._page_load_tokens[page] = token
        return token

    def _page_load_is_current(self, page: str, token: int) -> bool:
        return self._page_load_tokens.get(page) == token

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
            self.nav_buttons["Setting Center"].setVisible(str(role).casefold() in {"admin", "manager"})
            self.service_order_reports_button.hide()
            self.service_order_presets_button.hide()
            self.identity_label.setText(f"{name}\nRole: {role}")
            self.welcome_label.setText(f"Welcome, {name}. Connected as {role}.")
            self.pages.setCurrentWidget(self.workspace_page)
            self.login_dialog.accept()
            self.showFullScreen()
            self.statusBar().showMessage(f"Connected · {client.server_url}")
            self.workspace_stack.setCurrentWidget(self.pos_page)
            self._focus_product_search()
            # Let Windows assign the POS window to its monitor before opening
            # the customer display on a different screen.
            QTimer.singleShot(250, self.open_sale_display_if_available)
            QTimer.singleShot(100, self.load_categories)
            QTimer.singleShot(120, self.load_receipt_settings)
            self._known_service_job_ids = None
            self.service_job_timer.start()
            QTimer.singleShot(200, self._poll_service_jobs)

        self._run_task(authenticate, accepted, lambda error: self._set_busy(False, error))

    def load_products(self) -> None:
        if not self.api:
            return
        self._product_load_token = self._new_page_load("pos_products")
        self.products = []
        self.product_rows = {}
        self.product_grid_items = {}
        self.product_grid_tiles = {}
        self.product_table.setRowCount(0)
        self.product_grid.clear()
        self.product_has_more = False
        self._load_product_page()

    def load_receipt_settings(self) -> None:
        if not self.api: return
        def loaded(settings):
            self.receipt_settings = dict(settings)
            if self.sale_display:
                self.sale_display.set_shop_name(self.receipt_settings.get("shop_name") or "KAY POS")
        self._run_task(
            self.api.receipt_settings,
            loaded,
            lambda error: self.statusBar().showMessage(f"Could not load receipt settings: {error}"),
        )

    def _load_product_page(self) -> None:
        if not self.api:
            return
        load_token = getattr(self,"_product_load_token",None)
        if load_token is None: load_token=self._new_page_load("pos_products"); self._product_load_token=load_token
        query = self.product_search.text().strip()
        category = self.selected_category
        offset = len(self.products)
        self.catalog_status.setText("Loading…" if offset == 0 else f"Loading more… {offset}")

        def loaded(products):
            if not self._page_load_is_current("pos_products",load_token): return
            if self.product_search.text().strip() != query or self.selected_category != category:
                QTimer.singleShot(100, self.load_products)
                return
            page = list(products)
            start_row = len(self.products)
            self.products.extend(page)
            self.product_table.setUpdatesEnabled(False); self.product_table.blockSignals(True); self.product_table.setRowCount(len(self.products))
            for page_row, product in enumerate(page):
                row = start_row + page_row
                image_item = QTableWidgetItem()
                image_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.product_table.setItem(row, 0, image_item)
                variants = product.get("variants") or []
                mode = sold_by_mode(product.get("sold_by"))
                display_stock = (
                    "Service" if mode == "service"
                    else sum(int(variant.get("stock") or 0) for variant in variants)
                    if mode == "variants" and variants
                    else int(product.get("stock") or 0)
                )
                stock_status = self._product_stock_status(product, display_stock)
                values = (
                    product.get("name") or "",
                    product.get("barcode") or product.get("sku") or "—",
                    f"{float(product.get('price') or 0):,.0f} Ks",
                    str(display_stock),
                    str(len(variants)) if variants else "—",
                )
                for column, value in enumerate(values, start=1):
                    item = QTableWidgetItem(str(value))
                    if column in (3, 4, 5):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if stock_status == "out":
                        item.setBackground(QColor("#f8d7da"))
                        item.setForeground(QColor("#842029"))
                    elif stock_status == "low":
                        item.setBackground(QColor("#fff3cd"))
                        item.setForeground(QColor("#664d03"))
                    self.product_table.setItem(row, column, item)
                self.product_rows[int(product.get("id") or 0)] = row
                grid_item = QListWidgetItem()
                grid_item.setData(Qt.ItemDataRole.UserRole, row)
                self.product_grid.fit_item(grid_item)
                self.product_grid.addItem(grid_item)
                product_id = int(product.get("id") or 0)
                tile = ProductGridTile(product.get("name") or "Product")
                tile.setToolTip(
                    f"{product.get('name') or ''}\n{float(product.get('price') or 0):,.0f} Ks · Stock {display_stock}"
                )
                self.product_grid.setItemWidget(grid_item, tile)
                self.product_grid_items[product_id] = grid_item
                self.product_grid_tiles[product_id] = tile
                if stock_status == "out":
                    image_item.setBackground(QColor("#f8d7da"))
                elif stock_status == "low":
                    image_item.setBackground(QColor("#fff3cd"))
            self.product_has_more = len(page) == self.product_page_size
            self.catalog_status.setText(f"{len(self.products)} products")
            self.product_table.blockSignals(False); self.product_table.setUpdatesEnabled(True); self.product_table.viewport().update()
            self.product_grid.refit()
            self.statusBar().showMessage("Product list ready")
            QTimer.singleShot(0, self._load_visible_product_thumbnails)

        def failed(error):
            self.catalog_status.setText("Could not load products")
            self.statusBar().showMessage(error)

        self._run_task(
            lambda: self.api.products(
                query, limit=self.product_page_size, offset=offset, category=category,
            ),
            loaded, failed,
        )

    @staticmethod
    def _product_stock_status(product: dict, display_stock: int) -> str:
        if sold_by_mode(product.get("sold_by")) == "service":
            return "normal"
        if int(display_stock) <= 0 or product.get("is_out_of_stock"):
            return "out"
        if product.get("is_low_stock"):
            return "low"
        variants = product.get("variants") or []
        if sold_by_mode(product.get("sold_by")) == "variants" and variants:
            if any(
                int(variant.get("stock") or 0) <= int(variant.get("low_stock") or 0)
                for variant in variants
            ):
                return "low"
        elif int(display_stock) <= int(product.get("low_stock") or 0):
            return "low"
        return "normal"

    def _maybe_load_more_products(self, value: int) -> None:
        current = getattr(self, "product_view_stack", None)
        widget = current.currentWidget() if current is not None else self.product_table
        bar = widget.verticalScrollBar()
        if self.product_has_more and value >= max(0, bar.maximum() - 2) and not self._threads:
            self._load_product_page()

    def set_product_view(self, mode: str) -> None:
        """Switch the POS catalogue without changing its search or loaded products."""
        mode = "grid" if str(mode).casefold() == "grid" else "list"
        self.product_view_mode = mode
        self.list_view_button.setChecked(mode == "list")
        self.grid_view_button.setChecked(mode == "grid")
        self.product_view_stack.setCurrentWidget(self.product_grid if mode == "grid" else self.product_table)
        save_config({"product_view": mode})
        QTimer.singleShot(0, self._load_visible_product_thumbnails)

    def add_grid_product(self, item: QListWidgetItem) -> None:
        row = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        if 0 <= row < len(self.products):
            self._add_product_to_cart(self.products[row], None, select_variant=True)

    def _load_visible_product_thumbnails(self) -> None:
        if not self.api or not self.products or not self.product_view_stack.isVisible():
            return
        if self.product_view_stack.currentWidget() is self.product_grid:
            viewport_rect = self.product_grid.viewport().rect()
            visible_rows = [
                index for index in range(self.product_grid.count())
                if self.product_grid.visualItemRect(self.product_grid.item(index)).intersects(viewport_rect)
            ]
            first = min(visible_rows) if visible_rows else 0
            last = max(visible_rows) if visible_rows else min(len(self.products) - 1, 15)
        else:
            viewport = self.product_table.viewport()
            first = self.product_table.rowAt(0)
            last = self.product_table.rowAt(max(0, viewport.height() - 1))
        first = max(0, first if first >= 0 else 0)
        last = min(len(self.products) - 1, last if last >= 0 else first + 15)
        for row in range(max(0, first - 2), min(len(self.products), last + 3)):
            product = self.products[row]
            product_id = int(product.get("id") or 0)
            url_path = str(product.get("thumbnail_url") or "")
            if not product_id or not url_path:
                continue
            cached = self.thumbnail_cache.get(product_id)
            if cached is not None:
                self._apply_product_thumbnail(product_id, cached)
                continue
            if product_id in self.thumbnail_pending:
                continue
            self.thumbnail_pending.add(product_id)
            url = url_path if "://" in url_path else f"{self.api.server_url}/{url_path.lstrip('/')}"
            reply = self.thumbnail_manager.get(QNetworkRequest(QUrl(url)))
            if not self.api.verify_tls:
                reply.sslErrors.connect(lambda _errors, current=reply: current.ignoreSslErrors())
            reply.finished.connect(
                lambda current=reply, pid=product_id: self._thumbnail_finished(pid, current)
            )

    def _load_visible_management_thumbnails(self) -> None:
        products = getattr(self, "management_products", [])
        if not self.api or not products or not self.stock_table.isVisible():
            return
        viewport = self.stock_table.viewport()
        first = self.stock_table.rowAt(0)
        last = self.stock_table.rowAt(max(0, viewport.height() - 1))
        first = max(0, first if first >= 0 else 0)
        last = min(len(products) - 1, last if last >= 0 else first + 15)
        for row in range(max(0, first - 2), min(len(products), last + 3)):
            product = products[row]
            product_id = int(product.get("id") or 0)
            url_path = str(product.get("thumbnail_url") or "")
            if not product_id or not url_path:
                continue
            cached = self.thumbnail_cache.get(product_id)
            if cached is not None:
                self._apply_product_thumbnail(product_id, cached)
                continue
            if product_id in self.thumbnail_pending:
                continue
            self.thumbnail_pending.add(product_id)
            url = url_path if "://" in url_path else f"{self.api.server_url}/{url_path.lstrip('/')}"
            reply = self.thumbnail_manager.get(QNetworkRequest(QUrl(url)))
            if not self.api.verify_tls:
                reply.sslErrors.connect(lambda _errors, current=reply: current.ignoreSslErrors())
            reply.finished.connect(
                lambda current=reply, pid=product_id: self._thumbnail_finished(pid, current)
            )

    def _load_visible_managed_product_thumbnails(self) -> None:
        products = getattr(self, "managed_products", [])
        if not self.api or not products or not self.manage_product_table.isVisible():
            return
        viewport = self.manage_product_table.viewport()
        first = self.manage_product_table.rowAt(0)
        last = self.manage_product_table.rowAt(max(0, viewport.height() - 1))
        first = max(0, first if first >= 0 else 0)
        last = min(len(products) - 1, last if last >= 0 else first + 15)
        for row in range(max(0, first - 2), min(len(products), last + 3)):
            product = products[row]
            product_id = int(product.get("id") or 0)
            url_path = str(product.get("thumbnail_url") or "")
            if not product_id or not url_path:
                continue
            cached = self.thumbnail_cache.get(product_id)
            if cached is not None:
                self._apply_product_thumbnail(product_id, cached)
                continue
            if product_id in self.thumbnail_pending:
                continue
            self.thumbnail_pending.add(product_id)
            url = url_path if "://" in url_path else f"{self.api.server_url}/{url_path.lstrip('/')}"
            reply = self.thumbnail_manager.get(QNetworkRequest(QUrl(url)))
            if not self.api.verify_tls:
                reply.sslErrors.connect(lambda _errors, current=reply: current.ignoreSslErrors())
            reply.finished.connect(
                lambda current=reply, pid=product_id: self._thumbnail_finished(pid, current)
            )

    def _thumbnail_finished(self, product_id: int, reply) -> None:
        self.thumbnail_pending.discard(product_id)
        data = bytes(reply.readAll()) if reply.error() == QNetworkReply.NetworkError.NoError else b""
        reply.deleteLater()
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            return
        pixmap = pixmap.scaled(
            QSize(144, 144), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if len(self.thumbnail_cache) >= 200:
            self.thumbnail_cache.pop(next(iter(self.thumbnail_cache)), None)
        self.thumbnail_cache[product_id] = pixmap
        self._apply_product_thumbnail(product_id, pixmap)

    def _apply_product_thumbnail(self, product_id: int, pixmap: QPixmap) -> None:
        grid_tile = self.product_grid_tiles.get(product_id)
        if grid_tile is not None:
            grid_tile.set_product_image(pixmap)
        for table,rows in (
            (self.product_table,self.product_rows),
            (self.stock_table,self.management_product_rows),
            (self.manage_product_table,self.managed_product_rows),
        ):
            row=rows.get(product_id)
            if row is None and not rows:
                source=(
                    self.products if table is self.product_table
                    else getattr(self, "managed_products", []) if table is self.manage_product_table
                    else getattr(self, "management_products", [])
                )
                rows.update({int(product.get("id") or 0):index for index,product in enumerate(source)})
                row=rows.get(product_id)
            if row is None or row<0 or row>=table.rowCount(): continue
            item=table.item(row,0)
            if item is None:
                item=QTableWidgetItem();item.setTextAlignment(Qt.AlignmentFlag.AlignCenter);table.setItem(row,0,item)
            item.setIcon(QIcon(pixmap))

    def load_categories(self) -> None:
        if not self.api:
            return
        load_token=self._new_page_load("categories")

        def loaded(categories):
            if not self._page_load_is_current("categories",load_token): return
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
        if not self.api or self._scan_in_progress:
            self._focus_product_search(select_all=True)
            return
        code = self.product_search.text().strip()
        if not code:
            self.load_products()
            self._focus_product_search()
            return
        # A scanner can take longer than the search debounce interval. Do not
        # let that background catalogue request suppress or overwrite the scan.
        self.search_timer.stop()
        self._new_page_load("pos_products")
        self._scan_in_progress = True
        self.catalog_status.setText("Scanning…")

        def scanned(product):
            self._scan_in_progress = False
            if not product:
                self.catalog_status.setText("Barcode not found")
                self.statusBar().showMessage(f"No product found for barcode / SKU: {code}")
                self._focus_product_search(select_all=True)
                return
            self.products = [product]
            self.product_has_more = False
            self.product_rows = {int(product.get("id") or 0): 0}
            self.product_grid_items = {}
            self.product_grid_tiles = {}
            self.product_table.setRowCount(1)
            self.product_table.setItem(0, 0, QTableWidgetItem())
            values = (
                product.get("name") or "", product.get("barcode") or product.get("sku") or "—",
                f"{float(product.get('price') or 0):,.0f} Ks", str(int(product.get("stock") or 0)),
                str(len(product.get("variants") or [])) or "—",
            )
            for column, value in enumerate(values, start=1):
                self.product_table.setItem(0, column, QTableWidgetItem(str(value)))
            self.product_grid.clear()
            grid_item = QListWidgetItem()
            grid_item.setData(Qt.ItemDataRole.UserRole, 0)
            self.product_grid.fit_item(grid_item)
            self.product_grid.addItem(grid_item)
            product_id = int(product.get("id") or 0)
            tile = ProductGridTile(product.get("name") or "Product")
            tile.setToolTip(
                f"{product.get('name') or ''}\n{float(product.get('price') or 0):,.0f} Ks · Stock {int(product.get('stock') or 0)}"
            )
            self.product_grid.setItemWidget(grid_item, tile)
            self.product_grid_items[product_id] = grid_item
            self.product_grid_tiles[product_id] = tile
            self.product_grid.refit()
            QTimer.singleShot(0, self._load_visible_product_thumbnails)
            matched_id = product.get("matched_variant_id")
            matched = next((v for v in product.get("variants") or [] if int(v.get("variant_id") or 0) == int(matched_id or 0)), None)
            self._add_product_to_cart(product, matched, select_variant=matched_id is None)
            self.product_search.clear()
            self.catalog_status.setText("Barcode added")
            self._focus_product_search()

        def failed(error):
            self._scan_in_progress = False
            self.catalog_status.setText("Barcode scan failed")
            self.statusBar().showMessage(error)
            self._focus_product_search(select_all=True)

        self._run_task(lambda: self.api.scan_product(code), scanned, failed)

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
        # Catalogue/barcode requests may still be finishing when a scanned item
        # is rendered. They must not leave Checkout permanently disabled.
        self.checkout_button.setEnabled(bool(items))
        if self.sale_display:
            self.sale_display.set_cart(items)

    def toggle_sale_display(self) -> None:
        if self.sale_display:
            self.sale_display.close()
            return
        self._open_sale_display(show_missing_message=True)

    def open_sale_display_if_available(self) -> bool:
        """Open the customer display automatically when a second screen exists."""
        return self._open_sale_display(show_missing_message=False)

    def _open_sale_display(self, show_missing_message: bool) -> bool:
        if self.sale_display:
            return True
        screens = QApplication.screens()
        current_screen = (
            self.windowHandle().screen() if self.windowHandle()
            else QApplication.screenAt(self.frameGeometry().center())
        ) or QApplication.primaryScreen()
        extended_screens = self._sale_display_targets(screens, current_screen)
        if not extended_screens:
            if show_missing_message:
                QMessageBox.information(
                    self, "Sale Display",
                    "No extended display was detected. Connect a second monitor and choose Extend in Windows Display Settings.",
                )
            return False
        screen = extended_screens[0]
        display = LiteSaleDisplay(self.receipt_settings.get("shop_name") or "KAY POS")
        self.sale_display = display
        display.closed.connect(self._sale_display_closed)
        display.set_cart(list(self.cart.items.values()))
        # Create and show the native window on the target monitor before
        # applying fullscreen. On Windows, fullscreening an unseen window can
        # otherwise relocate it to the POS window's monitor.
        display.showNormal()
        display.winId()
        if display.windowHandle():
            display.windowHandle().setScreen(screen)
        display.setGeometry(screen.geometry())
        display.show()
        QTimer.singleShot(0, lambda current=display, target=screen: self._fullscreen_sale_display(current, target))
        self.sale_display_button.setText("Close Display")
        self.statusBar().showMessage(f"Sale Display active · {screen.name()}")
        return True

    @staticmethod
    def _sale_display_targets(screens: list, current_screen) -> list:
        return [screen for screen in screens if screen is not current_screen]

    def _fullscreen_sale_display(self, display: LiteSaleDisplay, screen) -> None:
        if self.sale_display is not display:
            return
        if display.windowHandle():
            display.windowHandle().setScreen(screen)
        display.setGeometry(screen.geometry())
        display.showFullScreen()

    def _sale_display_closed(self) -> None:
        display = self.sale_display
        self.sale_display = None
        self.sale_display_button.setText("Sale Display")
        if display:
            display.deleteLater()
        self.statusBar().showMessage("Sale Display closed")

    def open_checkout(self) -> None:
        if not self.api or not self.cart.items or self._threads:
            return
        if not hasattr(self, "management_customers") or not hasattr(self, "checkout_payment_types") or not hasattr(self, "checkout_credit_settings"):
            self.checkout_button.setEnabled(False)
            self.checkout_button.setText("Loading customers…")

            def checkout_settings_loaded(result):
                customers, payment_types, credit_settings = result
                self.management_customers = list(customers)
                self.checkout_payment_types = list(payment_types)
                self.checkout_credit_settings = dict(credit_settings)
                self.checkout_button.setText("Checkout")
                self.checkout_button.setEnabled(bool(self.cart.items))
                QTimer.singleShot(50, self.open_checkout)

            self._run_task(
                lambda: (
                    getattr(self, "management_customers", None) or self.api.customers("", limit=200),
                    self.api.payment_types(),
                    self.api.credit_settings(),
                ),
                checkout_settings_loaded,
                lambda error: (
                    self.checkout_button.setText("Checkout"),
                    self.checkout_button.setEnabled(bool(self.cart.items)),
                    QMessageBox.critical(self, "Customers", error),
                ),
            )
            return
        preferences = load_config()
        dialog = CheckoutDialog(
            self.cart.total(), self, getattr(self, "management_customers", []),
            print_after_sale=preferences.get("print_receipt_after_sale", False),
            open_drawer_after_sale=preferences.get("open_cash_drawer_after_sale", False),
            payment_types=getattr(self, "checkout_payment_types", []),
            credit_settings=getattr(self, "checkout_credit_settings", {}),
        )
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
        discount_amount = dialog.discount_amount()
        payment_type = dialog.payment_type.currentText()
        customer_id = dialog.selected_customer_id()
        due_date = dialog.credit_due_date.date().toString("yyyy-MM-dd") if payment_type.strip().lower() == "credit" else ""
        credit_notes = dialog.credit_notes.toPlainText().strip() if payment_type.strip().lower() == "credit" else ""
        print_after_sale = dialog.print_after_sale.isChecked()
        open_drawer_after_sale = dialog.open_drawer_after_sale.isChecked()
        save_config({
            "print_receipt_after_sale": print_after_sale,
            "open_cash_drawer_after_sale": dialog._drawer_preference,
        })
        self.checkout_button.setEnabled(False)
        self.checkout_button.setText("Saving sale…")
        self.statusBar().showMessage("Completing sale securely…")

        def completed(receipt):
            self.cart.clear()
            self.render_cart()
            self.checkout_button.setText("Checkout")
            self.last_receipt = dict(receipt)
            self.statusBar().showMessage(f"Sale completed · {receipt.get('invoice_no') or ''}")
            receipt_dialog = ReceiptDialog(receipt, self, settings=self.receipt_settings)
            if print_after_sale:
                QTimer.singleShot(0, receipt_dialog.print_receipt_automatic)
            if open_drawer_after_sale:
                QTimer.singleShot(150, self.open_cash_drawer)
            receipt_dialog.exec()
            QTimer.singleShot(100, self.load_products)

        def failed(error):
            self.checkout_button.setText("Checkout")
            self.checkout_button.setEnabled(bool(self.cart.items))
            self.statusBar().showMessage("Checkout failed")
            QMessageBox.critical(self, "Checkout", error)

        self._run_task(
            lambda: self.api.checkout(
                items, payment, payment_type, customer_id, due_date, credit_notes,
                dialog.allow_credit_over_limit, discount_amount,
            ), completed, failed
        )

    def print_last_receipt(self) -> None:
        if not self.last_receipt:
            QMessageBox.information(self, "Print Receipt", "No completed receipt is available to print yet.")
            return
        ReceiptDialog(self.last_receipt, self, settings=self.receipt_settings).print_receipt()

    def open_cash_drawer(self) -> None:
        if self._threads:
            return
        printer_name = str(load_config().get("receipt_printer_name") or "")
        if not printer_name:
            QMessageBox.information(self, "Cash Drawer", "Select a local receipt printer in Setting Center > Local Printer first.")
            self.open_printer_settings()
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
        """Compatibility entry point that now opens the centralized settings page."""
        self.open_printer_settings()
        return str(load_config().get("receipt_printer_name") or "")

    def open_printer_settings(self) -> None:
        self.pages.setCurrentWidget(self.workspace_page)
        self.workspace_stack.setCurrentWidget(self.settings_page)
        for row in range(self.settings_page.nav.count()):
            if self.settings_page.nav.item(row).text() == "Local Printer":
                self.settings_page.nav.setCurrentRow(row)
                break
        self.settings_page.refresh_local_printers()
        self.statusBar().showMessage("Setting Center · Local Printer")

    def open_sales_history(self) -> None:
        self.workspace_stack.setCurrentWidget(self.history_page)
        self.history_offset = 0
        self.load_history()

    def open_expenses(self) -> None:
        self.workspace_stack.setCurrentWidget(self.expense_page)
        self.load_expenses()

    def load_expenses(self) -> None:
        if not self.api:
            return
        self._expense_load_token=self._new_page_load("expenses")
        self.expense_rows = []
        self.expense_table.setRowCount(0)
        self.expense_has_more = False
        self._load_expense_page()

    def _load_expense_page(self) -> None:
        if not self.api:
            return
        load_token=getattr(self,"_expense_load_token",None)
        if load_token is None: load_token=self._new_page_load("expenses"); self._expense_load_token=load_token
        query = self.expense_search.text().strip()
        from_date = self.expense_from.date().toString("yyyy-MM-dd")
        to_date = self.expense_to.date().toString("yyyy-MM-dd")
        offset = len(self.expense_rows)
        self.expense_status.setText("Loading…" if offset == 0 else f"Loading more… {offset}")

        def loaded(result):
            if not self._page_load_is_current("expenses",load_token): return
            categories, payload = result
            self.expense_categories = list(categories)
            self.expense_categories_loaded = True
            page = list(payload.get("expenses") or [])
            start_row = len(self.expense_rows)
            self.expense_rows.extend(page)
            self.expense_table.setUpdatesEnabled(False); self.expense_table.blockSignals(True); self.expense_table.setRowCount(len(self.expense_rows))
            for page_row, expense in enumerate(page):
                row = start_row + page_row
                values = (
                    expense.get("expense_date") or "", expense.get("expense_no") or "",
                    expense.get("category") or "", expense.get("description") or "",
                    f"{float(expense.get('amount') or 0):,.0f} Ks",
                    expense.get("payment_method") or "", expense.get("reference_no") or "",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column == 4:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.expense_table.setItem(row, column, item)
            self.expense_has_more = len(page) == self.expense_page_size
            self.expense_total.setText(f"Total · {float(payload.get('total') or 0):,.0f} Ks")
            self.expense_status.setText(f"{len(self.expense_rows)} expense(s) loaded")
            self.expense_table.blockSignals(False); self.expense_table.setUpdatesEnabled(True); self.expense_table.viewport().update()

        self._run_task(
            lambda: (
                self.expense_categories or self.api.expense_categories(),
                self.api.expenses(
                    query, from_date, to_date,
                    limit=self.expense_page_size, offset=offset,
                ),
            ),
            loaded,
            lambda error: (
                self.expense_status.setText("Could not load expenses"),
                QMessageBox.critical(self, "Expenses", error),
            ),
        )

    def _maybe_load_more_expenses(self, value: int) -> None:
        bar = self.expense_table.verticalScrollBar()
        if self.expense_has_more and value >= max(0, bar.maximum() - 2) and not self._threads:
            self._load_expense_page()

    def add_expense(self) -> None:
        if not self.api or self._threads:
            return
        if not self.expense_categories_loaded:
            self.add_expense_button.setEnabled(False)
            self.add_expense_button.setText("Loading Categories…")

            def categories_loaded(categories):
                self.expense_categories = list(categories)
                self.expense_categories_loaded = True
                self.add_expense_button.setEnabled(True)
                self.add_expense_button.setText("Add Expense")
                self._show_expense_dialog()

            def categories_failed(error):
                self.add_expense_button.setEnabled(True)
                self.add_expense_button.setText("Add Expense")
                QMessageBox.critical(self, "Expense", error)

            self._run_task(self.api.expense_categories, categories_loaded, categories_failed)
            return
        self._show_expense_dialog()

    def _show_expense_dialog(self) -> None:
        dialog = ExpenseDialog(self.expense_categories, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self.expense_status.setText("Saving expense…")

        def saved(expense):
            self.expense_status.setText(f"Saved · {expense.get('expense_no') or ''}")
            QTimer.singleShot(100, self.load_expenses)
            QTimer.singleShot(200, self.load_dashboard)

        self._run_task(
            lambda: self.api.add_expense(values), saved,
            lambda error: (
                self.expense_status.setText("Could not save expense"),
                QMessageBox.critical(self, "Expense", error),
            ),
        )

    def open_dashboard(self) -> None:
        self.workspace_stack.setCurrentWidget(self.dashboard_page)
        self.load_dashboard()

    def _dashboard_today(self) -> None:
        today = QDate.currentDate()
        self.dashboard_from.setDate(today)
        self.dashboard_to.setDate(today)
        self.load_dashboard()

    def load_dashboard(self) -> None:
        if not self.api:
            return
        load_token=self._new_page_load("dashboard")
        from_date = self.dashboard_from.date().toString("yyyy-MM-dd")
        to_date = self.dashboard_to.date().toString("yyyy-MM-dd")
        if from_date > to_date:
            QMessageBox.warning(self, "Dashboard Date Range", "From date cannot be after To date.")
            return

        def loaded(data):
            if not self._page_load_is_current("dashboard",load_token): return
            current = data.get("today") or {}
            metrics = data.get("dashboard_metrics") or {}
            inventory = data.get("inventory") or {}
            credit = data.get("credit_summary") or {}
            self.dashboard_sales.setText(f"Net Sales\n{float(metrics.get('net_sales', current.get('sales')) or 0):,.0f} Ks")
            self.dashboard_transactions.setText(f"Transactions\n{int(metrics.get('transactions', current.get('transactions')) or 0)}")
            self.dashboard_gross_profit.setText(f"Gross Profit\n{float(metrics.get('gross_profit') or 0):,.0f} Ks")
            self.dashboard_expenses.setText(f"Expenses\n{float(metrics.get('expenses', (data.get('expenses') or {}).get('total')) or 0):,.0f} Ks")
            self.dashboard_net_profit.setText(f"Net Profit\n{float(metrics.get('net_profit', data.get('profit')) or 0):,.0f} Ks")
            self.dashboard_refunds.setText(f"Refunds\n{float(metrics.get('refunds', current.get('refunds')) or 0):,.0f} Ks")
            self.dashboard_low_stock.setText(
                f"Low / Out of Stock\n{int(metrics.get('low_stock', inventory.get('low_stock')) or 0)} / "
                f"{int(metrics.get('out_of_stock', inventory.get('out_of_stock')) or 0)}"
            )
            self.dashboard_credit.setText(f"Outstanding Credit\n{float(metrics.get('outstanding_credit', credit.get('balance')) or 0):,.0f} Ks")
            category_sales = list(data.get("category_sales") or [])
            expense_groups = list(data.get("expense_groups") or [])
            payment_sales = list(data.get("payment_sales") or [])
            sales_by_day = list(data.get("sales_by_day") or [])
            self._fill_dashboard_table(self.dashboard_sale_categories, [
                (row.get("label") or "Uncategorized", f"{float(row.get('qty') or 0):,.2f}", f"{float(row.get('total') or 0):,.0f} Ks")
                for row in category_sales
            ])
            self._fill_dashboard_table(self.dashboard_expense_categories, [
                (row.get("label") or "Uncategorized", f"{int(row.get('count') or 0):,}", f"{float(row.get('total') or 0):,.0f} Ks")
                for row in expense_groups
            ])
            self._fill_dashboard_table(self.dashboard_payment_types, [
                (row.get("label") or "Other", f"{int(row.get('count') or 0):,}", f"{float(row.get('total') or 0):,.0f} Ks")
                for row in payment_sales
            ])
            self._fill_dashboard_table(self.dashboard_daily_trend, [
                (row.get("date") or "", f"{float(row.get('total') or 0):,.0f} Ks")
                for row in sales_by_day
            ])
            self._set_dashboard_footer(
                self.dashboard_sale_categories_status, self.dashboard_sale_categories_total,
                len(category_sales), "category", sum(float(row.get("total") or 0) for row in category_sales),
            )
            self._set_dashboard_footer(
                self.dashboard_expense_categories_status, self.dashboard_expense_categories_total,
                len(expense_groups), "expense category", sum(float(row.get("total") or 0) for row in expense_groups),
            )
            self._set_dashboard_footer(
                self.dashboard_payment_types_status, self.dashboard_payment_types_total,
                len(payment_sales), "payment type", sum(float(row.get("total") or 0) for row in payment_sales),
            )
            self._set_dashboard_footer(
                self.dashboard_daily_trend_status, self.dashboard_daily_trend_total,
                len(sales_by_day), "day", sum(float(row.get("total") or 0) for row in sales_by_day),
            )
            period = data.get("period") or {}
            period_label = str(
                period.get("label")
                or (from_date if from_date == to_date else f"{from_date} to {to_date}")
            )
            self.dashboard_period_label.setText(f"{period_label} · AI Dashboard metrics")
            self.statusBar().showMessage(f"Dashboard refreshed · {period_label}")

        self._run_task(
            lambda: self.api.dashboard_summary(from_date, to_date), loaded,
            lambda error: self.statusBar().showMessage(error),
        )

    def open_management(self) -> None:
        self.workspace_stack.setCurrentWidget(self.management_page)
        self.load_management()

    def load_management(self) -> None:
        if not self.api:
            return
        load_token=self._new_page_load("inventory")
        query = self.management_search.text().strip()

        def loaded(result):
            if not self._page_load_is_current("inventory",load_token): return
            products, suppliers, locations = result
            self.management_products = list(products)
            self.management_suppliers = list(suppliers)
            self.management_locations = list(locations)
            self.management_product_rows={}; self.stock_table.setUpdatesEnabled(False); self.stock_table.blockSignals(True); self.stock_table.setRowCount(len(products))
            for row, product in enumerate(products):
                values = (
                    "", product.get("name") or "", product.get("barcode") or product.get("sku") or "—",
                    str(int(product.get("stock") or 0)), str(len(product.get("variants") or [])) or "—",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column == 0:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.stock_table.setItem(row, column, item)
                self.management_product_rows[int(product.get("id") or 0)]=row
            self.stock_table.blockSignals(False); self.stock_table.setUpdatesEnabled(True); self.stock_table.viewport().update()
            self.statusBar().showMessage(f"{len(products)} products loaded")
            QTimer.singleShot(0, self._load_visible_management_thumbnails)

        self._run_task(
            lambda: (
                self.api.products(query, limit=100), self.api.suppliers(), self.api.stock_locations(),
            ),
            loaded, lambda error: self.statusBar().showMessage(error),
        )

    def load_customers(self) -> None:
        if not self.api:
            return
        load_token=self._new_page_load("customers")
        query = self.customer_search.text().strip()
        self.customer_status.setText("Loading…")

        def loaded(customers):
            if not self._page_load_is_current("customers",load_token): return
            self.management_customers = list(customers)
            self.customer_table.setUpdatesEnabled(False); self.customer_table.blockSignals(True); self.customer_table.setRowCount(len(customers))
            for row, customer in enumerate(customers):
                values = (
                    customer.get("name") or "", customer.get("phone") or "",
                    f"{float(customer.get('points') or 0):,.0f}",
                    f"{float(customer.get('current_balance') or 0):,.0f}",
                )
                for column, value in enumerate(values):
                    self.customer_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.customer_table.blockSignals(False); self.customer_table.setUpdatesEnabled(True); self.customer_table.viewport().update()
            self.customer_status.setText(f"{len(customers)} customer(s) loaded")
            self.statusBar().showMessage(f"{len(customers)} customers loaded")

        self._run_task(
            lambda: self.api.customers(query, limit=200), loaded,
            lambda error: (self.customer_status.setText("Could not load customers"), self.statusBar().showMessage(error)),
        )

    def load_service_orders(self) -> None:
        if not self.api:
            return
        token = self._new_page_load("service_orders")
        query = self.service_order_search.text().strip()
        status = str(self.service_order_status_filter.currentData() or "")
        self.service_order_list_status.setText("Loading…")
        self._set_service_order_actions_enabled(False)

        def loaded(orders):
            if not self._page_load_is_current("service_orders", token):
                return
            self.service_orders_data = list(orders)
            self.selected_service_order = {}
            self.service_order_table.blockSignals(True); self.service_order_table.setUpdatesEnabled(False)
            self.service_order_table.setRowCount(len(orders))
            for row, order in enumerate(orders):
                received = str(order.get("received_at") or "")
                status = str(order.get("status") or "received")
                values = (
                    received[:10], received[11:16], order.get("job_title") or "—", order.get("complaint") or "—",
                    order.get("expected_at") or "—", "Completed" if status == "completed" else "Not Completed",
                    order.get("completed_by") or "—",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, int(order.get("id") or 0))
                    self.service_order_table.setItem(row, column, item)
            self.service_order_table.setUpdatesEnabled(True); self.service_order_table.blockSignals(False)
            self.service_order_list_status.setText(f"{len(orders)} job(s)")
            self._clear_service_order_detail()
            if orders:
                self.service_order_table.selectRow(0)

        self._run_task(
            lambda: self.api.service_orders(query=query, status=status, limit=200), loaded,
            lambda error: (self.service_order_list_status.setText("Could not load service orders"), QMessageBox.critical(self, "Service Orders", error)),
        )

    def load_selected_service_order(self) -> None:
        if not self.api:
            return
        row = self.service_order_table.currentRow()
        item = self.service_order_table.item(row, 0) if row >= 0 else None
        order_id = int(item.data(Qt.ItemDataRole.UserRole) or 0) if item else 0
        if not order_id:
            self._clear_service_order_detail()
            return
        token = self._new_page_load("service_order_detail")
        self.service_order_detail_title.setText("Loading order…")
        self._set_service_order_actions_enabled(False)

        def loaded(order):
            if not self._page_load_is_current("service_order_detail", token):
                return
            self.selected_service_order = dict(order)
            self._show_service_order_detail(order)

        self._run_task(
            lambda: self.api.service_order(order_id), loaded,
            lambda error: (self._clear_service_order_detail(), QMessageBox.critical(self, "Service Order", error)),
        )

    def _show_service_order_detail(self, order: dict) -> None:
        status = str(order.get("status") or "received")
        self.service_order_detail_title.setText(f"{order.get('job_title') or 'Service Job'} · {'Completed' if status == 'completed' else 'Not Completed'}")
        summary = (
            f"Date/Time: {order.get('received_at') or '—'}\n"
            f"Details: {order.get('complaint') or '—'}\n"
            f"Appointment: {order.get('expected_at') or '—'}\n"
            f"Notes: {order.get('internal_notes') or '—'}\n"
            f"Created By: {order.get('created_by') or '—'}\n"
            f"Completed By: {order.get('completed_by') or '—'}"
        )
        self.service_order_detail_summary.setText(summary)
        items = list(order.get("items") or [])
        self.service_order_items_table.setRowCount(len(items))
        for row, line in enumerate(items):
            options = " · ".join(value for value in (
                str(line.get("paper_size") or ""), str(line.get("color_mode") or "").replace("not_applicable", ""),
                str(line.get("print_side") or "").replace("not_applicable", ""), str(line.get("finishing") or ""),
            ) if value)
            description = str(line.get("description") or "") + (f"\n{options}" if options else "")
            values = (description, line.get("item_type") or "", f"{float(line.get('qty') or 0):g}", f"{float(line.get('qty') or 0) * float(line.get('unit_price') or 0):,.0f}")
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(str(value)); table_item.setData(Qt.ItemDataRole.UserRole, int(line.get("id") or 0))
                self.service_order_items_table.setItem(row, column, table_item)
        self.service_order_history.clear()
        for history in order.get("status_history") or []:
            actor = history.get("changed_by") or "User"
            when = history.get("changed_at") or ""
            target = str(history.get("to_status") or "").replace("_", " ").title()
            note = f" · {history.get('note')}" if history.get("note") else ""
            self.service_order_history.addItem(f"{when} · {target} · {actor}{note}")
        for visit in order.get("return_visits") or []:
            self.service_order_history.addItem(
                f"{visit.get('visited_at') or ''} · Return {str(visit.get('status') or 'open').title()} · {visit.get('reason') or ''}"
            )
        self.service_order_next_status.clear()
        if status not in {"completed", "delivered", "cancelled"}:
            self.service_order_next_status.addItem("Completed", "completed")
        self._set_service_order_actions_enabled(True)

    def _clear_service_order_detail(self) -> None:
        self.selected_service_order = {}
        self.service_order_detail_title.setText("Select a job")
        self.service_order_detail_summary.clear(); self.service_order_items_table.setRowCount(0); self.service_order_history.clear()
        self.service_order_next_status.clear(); self._set_service_order_actions_enabled(False)

    def _set_service_order_actions_enabled(self, enabled: bool) -> None:
        closed = str(self.selected_service_order.get("status") or "") in {"completed", "delivered", "cancelled"}
        self.service_order_edit_button.setEnabled(bool(enabled) and not closed)
        self.service_order_add_item_button.setEnabled(bool(enabled) and not closed)
        self.service_order_edit_item_button.setEnabled(bool(enabled) and not closed)
        self.service_order_remove_item_button.setEnabled(bool(enabled) and not closed)
        can_change = bool(enabled) and self.service_order_next_status.count() > 0
        self.service_order_next_status.setEnabled(can_change); self.service_order_change_button.setEnabled(can_change)

    def complete_selected_service_order(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        if QMessageBox.question(self, "Complete Job", "Mark this job as completed?") != QMessageBox.StandardButton.Yes:
            return
        order_id = int(self.selected_service_order.get("id") or 0)
        self.service_order_change_button.setEnabled(False)
        self._run_task(
            lambda: self.api.change_service_order_status(order_id, "completed", "Completed from client PC"),
            lambda order: (setattr(self, "selected_service_order", dict(order)), self._show_service_order_detail(order), self.load_service_orders()),
            lambda error: (self.service_order_change_button.setEnabled(True), QMessageBox.critical(self, "Complete Job", error)),
        )

    def new_service_order(self) -> None:
        self._open_service_order_dialog({})

    def edit_service_order(self) -> None:
        if self.selected_service_order:
            self._open_service_order_dialog(self.selected_service_order)

    def _selected_service_order_item(self) -> dict | None:
        row = self.service_order_items_table.currentRow()
        cell = self.service_order_items_table.item(row, 0) if row >= 0 else None
        item_id = int(cell.data(Qt.ItemDataRole.UserRole) or 0) if cell else 0
        return next((item for item in self.selected_service_order.get("items") or [] if int(item.get("id") or 0) == item_id), None)

    def add_service_order_item(self) -> None:
        if self.selected_service_order:
            self._open_service_order_item_dialog({})

    def edit_service_order_item(self) -> None:
        item = self._selected_service_order_item()
        if not item:
            QMessageBox.information(self, "Order Item", "Select an order item to edit."); return
        self._open_service_order_item_dialog(item)

    def _open_service_order_item_dialog(self, item: dict) -> None:
        if not self.api or not self.selected_service_order:
            return
        order_id = int(self.selected_service_order.get("id") or 0)
        self.statusBar().showMessage("Loading service and parts catalog…")

        def products_loaded(result):
            products, presets = result
            dialog = ServiceOrderItemDialog(self, products=products, presets=presets, item=item)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            values = dialog.values(); self._set_service_order_actions_enabled(False)
            operation = (
                (lambda: self.api.update_service_order_item(order_id, int(item["id"]), values))
                if item else (lambda: self.api.add_service_order_item(order_id, values))
            )
            self._run_task(
                operation, lambda _saved: self._refresh_service_order_detail(order_id),
                lambda error: (self._set_service_order_actions_enabled(True), QMessageBox.critical(self, "Order Item", error)),
            )

        self._run_task(
            lambda: (self.api.products("", limit=100), self.api.print_service_presets()), products_loaded,
            lambda error: QMessageBox.critical(self, "Order Item", f"Could not load products: {error}"),
        )

    def remove_service_order_item(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        item = self._selected_service_order_item()
        if not item:
            QMessageBox.information(self, "Order Item", "Select an order item to remove."); return
        answer = QMessageBox.question(
            self, "Remove Order Item", f"Remove {item.get('description') or 'this item'}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        order_id = int(self.selected_service_order.get("id") or 0)
        self._set_service_order_actions_enabled(False)
        self._run_task(
            lambda: self.api.delete_service_order_item(order_id, int(item.get("id") or 0)),
            lambda _result: self._refresh_service_order_detail(order_id),
            lambda error: (self._set_service_order_actions_enabled(True), QMessageBox.critical(self, "Order Item", error)),
        )

    def _refresh_service_order_detail(self, order_id: int) -> None:
        if not self.api:
            return
        self._run_task(
            lambda: self.api.service_order(order_id),
            lambda order: (setattr(self, "selected_service_order", dict(order)), self._show_service_order_detail(order), self.statusBar().showMessage("Service order items updated")),
            lambda error: QMessageBox.critical(self, "Service Order", error),
        )

    def _open_service_order_dialog(self, order: dict) -> None:
        if not self.api:
            return
        dialog = ServiceOrderDialog(self, order=order)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if order:
            values.pop("received_at", None)
        self.statusBar().showMessage("Saving service job…")

        def saved(saved_order):
            self.statusBar().showMessage(f"Service job {saved_order.get('order_no') or ''} saved")
            self.load_service_orders()

        operation = (
            (lambda: self.api.update_service_order(int(order["id"]), values))
            if order else (lambda: self.api.create_service_order(values))
        )
        self._run_task(operation, saved, lambda error: QMessageBox.critical(self, "Service Job", error))

    def _poll_service_jobs(self) -> None:
        """Notify this workstation when another user adds a shared job."""
        if not self.api or self._service_job_polling:
            return
        self._service_job_polling = True

        def loaded(orders):
            self._service_job_polling = False
            current_ids = {int(row.get("id") or 0) for row in orders}
            if self._known_service_job_ids is None:
                self._known_service_job_ids = current_ids
                return
            new_jobs = [row for row in orders if int(row.get("id") or 0) not in self._known_service_job_ids]
            self._known_service_job_ids |= current_ids
            username = str((self.user or {}).get("username") or "").casefold()
            for job in reversed(new_jobs):
                if str(job.get("created_by") or "").casefold() == username:
                    continue
                title = str(job.get("job_title") or "New Job")
                details = str(job.get("complaint") or "")
                self.service_job_tray.showMessage("New Service Job", f"{title}\n{details}", QSystemTrayIcon.MessageIcon.Information, 8000)
            if new_jobs and self.workspace_stack.currentWidget() is self.service_orders_page:
                self.load_service_orders()

        self._run_task(
            lambda: self.api.service_orders(status="", limit=200), loaded,
            lambda _error: setattr(self, "_service_job_polling", False),
        )

    def change_selected_service_order_status(self) -> None:
        if not self.api or not self.selected_service_order or self.service_order_next_status.count() == 0:
            return
        target = str(self.service_order_next_status.currentData() or "")
        note, accepted = QInputDialog.getMultiLineText(
            self, "Change Service Order Status", f"Change to {target.replace('_', ' ').title()}\nOptional note:", "",
        )
        if not accepted:
            return
        order_id = int(self.selected_service_order.get("id") or 0)
        self._set_service_order_actions_enabled(False)

        def changed(order):
            self.selected_service_order = dict(order); self._show_service_order_detail(order); self.load_service_orders()

        self._run_task(
            lambda: self.api.change_service_order_status(order_id, target, note), changed,
            lambda error: (self._set_service_order_actions_enabled(True), QMessageBox.critical(self, "Service Order", error)),
        )

    def collect_service_order_deposit(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        amount, accepted = QInputDialog.getDouble(self, "Collect Deposit", "Deposit amount (Ks):", 0, 1, 999999999999, 0)
        if not accepted:
            return
        methods = [str(row.get("name") or "") for row in getattr(self, "checkout_payment_types", []) if row.get("name")] or ["Cash"]
        payment_type, accepted = QInputDialog.getItem(self, "Deposit Payment", "Payment type:", methods, 0, False)
        if not accepted:
            return
        reference, accepted = QInputDialog.getText(self, "Deposit Reference", "Reference (optional):")
        if not accepted:
            return
        order_id = int(self.selected_service_order.get("id") or 0); self._set_service_order_actions_enabled(False)
        self._run_task(
            lambda: self.api.record_service_order_deposit(order_id, amount, payment_type, reference),
            lambda order: (setattr(self, "selected_service_order", dict(order)), self._show_service_order_detail(order), self.statusBar().showMessage("Deposit recorded")),
            lambda error: (self._set_service_order_actions_enabled(True), QMessageBox.critical(self, "Deposit", error)),
        )

    def checkout_selected_service_order(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        order = self.selected_service_order
        total = sum(float(item.get("qty") or 0) * float(item.get("unit_price") or 0) for item in order.get("items") or [])
        deposit = float(order.get("deposit_amount") or 0); balance = max(0.0, total - deposit)
        methods = [str(row.get("name") or "") for row in getattr(self, "checkout_payment_types", []) if row.get("name")] or ["Cash", "Credit"]
        payment_type, accepted = QInputDialog.getItem(self, "Service Checkout", f"Total {total:,.0f} Ks · Deposit {deposit:,.0f} Ks · Balance {balance:,.0f} Ks\nPayment type:", methods, 0, False)
        if not accepted:
            return
        payment, accepted = QInputDialog.getDouble(self, "Service Checkout", "Payment received now (Ks):", balance, 0, 999999999999, 0)
        if not accepted:
            return
        answer = QMessageBox.question(
            self, "Complete Service Checkout", f"Create the POS sale and deduct parts stock?\n\nAmount now: {payment:,.0f} Ks",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        order_id = int(order.get("id") or 0); self._set_service_order_actions_enabled(False)

        def completed(saved):
            self.selected_service_order = dict(saved); self._show_service_order_detail(saved)
            receipt = dict(saved.get("receipt") or {})
            if receipt:
                self.last_receipt = receipt
                ReceiptDialog(receipt, self, settings=self.receipt_settings).exec()
            self.load_service_orders(); QTimer.singleShot(150, self.load_products)

        self._run_task(
            lambda: self.api.checkout_service_order(order_id, payment, payment_type), completed,
            lambda error: (self._set_service_order_actions_enabled(True), QMessageBox.critical(self, "Service Checkout", error)),
        )

    def view_service_order_receipt(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        sale_id = int(self.selected_service_order.get("sale_id") or 0)
        if sale_id <= 0:
            return
        self._run_task(
            lambda: self.api.receipt(sale_id),
            lambda receipt: ReceiptDialog(receipt, self, settings=self.receipt_settings).exec(),
            lambda error: QMessageBox.critical(self, "Service Receipt", error),
        )

    def add_service_order_return_visit(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        reason, accepted = QInputDialog.getMultiLineText(self, "Return Visit", "Reason for return visit:")
        if not accepted or not reason.strip():
            return
        order_id = int(self.selected_service_order.get("id") or 0)
        self._run_task(
            lambda: self.api.add_service_order_return_visit(order_id, reason),
            lambda order: (setattr(self, "selected_service_order", dict(order)), self._show_service_order_detail(order)),
            lambda error: QMessageBox.critical(self, "Return Visit", error),
        )

    def close_service_order_return_visit(self) -> None:
        if not self.api or not self.selected_service_order:
            return
        visit = next((row for row in self.selected_service_order.get("return_visits") or [] if str(row.get("status")) == "open"), None)
        if not visit:
            return
        resolution, accepted = QInputDialog.getMultiLineText(self, "Close Return Visit", "Resolution:")
        if not accepted or not resolution.strip():
            return
        order_id = int(self.selected_service_order.get("id") or 0)
        self._run_task(
            lambda: self.api.close_service_order_return_visit(order_id, int(visit.get("id") or 0), resolution),
            lambda order: (setattr(self, "selected_service_order", dict(order)), self._show_service_order_detail(order)),
            lambda error: QMessageBox.critical(self, "Return Visit", error),
        )

    def open_service_order_reports(self) -> None:
        if not self.api:
            return
        today = QDate.currentDate(); start = QDate(today.year(), today.month(), 1)
        self.statusBar().showMessage("Loading service reports…")

        def loaded(result):
            summary, warranties, notifications = result
            dialog = QDialog(self); dialog.setWindowTitle("Service Reports"); dialog.resize(760, 620)
            layout = QVBoxLayout(dialog)
            metrics = QLabel(
                f"Orders: {int(summary.get('orders') or 0):,}    Revenue: {float(summary.get('revenue') or 0):,.0f} Ks    "
                f"Actual Cost: {float(summary.get('actual_cost') or 0):,.0f} Ks    Avg Turnaround: {float(summary.get('average_turnaround_hours') or 0):,.1f} hours",
                objectName="title",
            ); metrics.setWordWrap(True); layout.addWidget(metrics)
            tabs = QTabWidget()
            status_text = QTextEdit(); status_text.setReadOnly(True)
            status_text.setPlainText("\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in (summary.get("status_counts") or {}).items()))
            tech_text = QTextEdit(); tech_text.setReadOnly(True)
            tech_text.setPlainText("\n".join(f"{row.get('technician')}: {row.get('orders')} orders · {row.get('completed')} completed · {float(row.get('revenue') or 0):,.0f} Ks" for row in summary.get("technicians") or []) or "No technician data")
            service_text = QTextEdit(); service_text.setReadOnly(True)
            service_text.setPlainText("\n".join(f"{row.get('name')}: {float(row.get('quantity') or 0):g} units · {int(row.get('sheets') or 0):,} sheets · {float(row.get('revenue') or 0):,.0f} Ks" for row in summary.get("service_types") or []) or "No service data")
            paper_text = QTextEdit(); paper_text.setReadOnly(True)
            paper_text.setPlainText("\n".join(f"{row.get('name')}: {float(row.get('quantity') or 0):g} units · {int(row.get('sheets') or 0):,} sheets · {float(row.get('revenue') or 0):,.0f} Ks" for row in summary.get("paper_sizes") or []) or "No paper data")
            color_text = QTextEdit(); color_text.setReadOnly(True)
            color_text.setPlainText("\n".join(f"{str(row.get('name') or '').replace('_', ' ').title()}: {float(row.get('quantity') or 0):g} units · {int(row.get('sheets') or 0):,} sheets · {float(row.get('revenue') or 0):,.0f} Ks" for row in summary.get("color_modes") or []) or "No color data")
            warranty_text = QTextEdit(); warranty_text.setReadOnly(True)
            warranty_text.setPlainText("\n".join(f"{row.get('warranty_expires_at')} · {row.get('order_no')} · {row.get('customer_name')} · {row.get('description')}" for row in warranties) or "No warranties expiring in 30 days")
            notification_text = QTextEdit(); notification_text.setReadOnly(True)
            notification_text.setPlainText("\n".join(f"{row.get('created_at')} · {row.get('recipient') or 'No phone'} · {row.get('message')}" for row in notifications) or "No pending notifications")
            tabs.addTab(status_text, "Status Summary"); tabs.addTab(service_text, "Service Types"); tabs.addTab(paper_text, "Paper Sizes"); tabs.addTab(color_text, "Color Modes"); tabs.addTab(tech_text, "Operators"); tabs.addTab(warranty_text, "Warranties"); tabs.addTab(notification_text, "Notification Queue")
            layout.addWidget(tabs, 1)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
            self.statusBar().showMessage("Service reports loaded"); dialog.exec()

        from_date = start.toString("yyyy-MM-dd"); to_date = today.toString("yyyy-MM-dd")
        self._run_task(
            lambda: (self.api.service_order_report(from_date, to_date), self.api.service_order_warranties(30), self.api.service_order_notifications("pending")),
            loaded, lambda error: QMessageBox.critical(self, "Service Reports", error),
        )

    def manage_print_service_presets(self) -> None:
        if not self.api:
            return
        def loaded(result):
            products, presets = result
            services = [product for product in products if sold_by_mode(product.get("sold_by")) == "service"]
            dialog = QDialog(self); dialog.setWindowTitle("Print Service Quick Presets"); dialog.resize(720, 470)
            layout = QVBoxLayout(dialog)
            table = QTableWidget(len(presets), 5); table.setHorizontalHeaderLabels(["Preset", "Service Product", "Pricing", "Output", "Price"])
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            products_by_id = {int(product.get("id") or 0): product for product in services}
            for row, preset in enumerate(presets):
                product = products_by_id.get(int(preset.get("product_id") or 0), {})
                values = (preset.get("name") or "", product.get("name") or "Missing product", str(preset.get("pricing_unit") or "").replace("_", " ").title(), f"{preset.get('paper_size') or '—'} · {str(preset.get('color_mode') or '').title()} · {str(preset.get('print_side') or '').title()}", f"{float(preset.get('unit_price') or 0):,.0f} Ks")
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(str(value)); cell.setData(Qt.ItemDataRole.UserRole, int(preset.get("id") or 0)); table.setItem(row, column, cell)
            layout.addWidget(table, 1)
            actions = QHBoxLayout(); add = QPushButton("Add Preset"); edit = QPushButton("Edit Preset"); deactivate = QPushButton("Deactivate")
            actions.addWidget(add); actions.addWidget(edit); actions.addWidget(deactivate); actions.addStretch()
            close = QPushButton("Close"); close.clicked.connect(dialog.accept); actions.addWidget(close); layout.addLayout(actions)
            def selected():
                row = table.currentRow(); return presets[row] if 0 <= row < len(presets) else None
            def open_editor(preset=None):
                editor = ServiceOrderItemDialog(dialog, products=services, item=dict(preset or {}))
                if editor.exec() != QDialog.DialogCode.Accepted: return
                name, accepted = QInputDialog.getText(dialog, "Preset Name", "Preset name:", text=str((preset or {}).get("name") or editor.description.text()))
                if not accepted or not name.strip(): return
                values = editor.values(); values.update({"name": name.strip(), "description": editor.description.text().strip(), "sort_order": int((preset or {}).get("sort_order") or 0), "active": True})
                preset_id = int((preset or {}).get("id") or 0) or None
                self._run_task(lambda: self.api.save_print_service_preset(values, preset_id), lambda _saved: (dialog.accept(), self.manage_print_service_presets()), lambda error: QMessageBox.critical(dialog, "Preset", error))
            add.clicked.connect(lambda: open_editor())
            edit.clicked.connect(lambda: open_editor(selected()) if selected() else QMessageBox.information(dialog, "Preset", "Select a preset to edit."))
            def deactivate_selected():
                preset = selected()
                if not preset: QMessageBox.information(dialog, "Preset", "Select a preset to deactivate."); return
                if QMessageBox.question(dialog, "Deactivate Preset", f"Deactivate {preset.get('name')}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
                self._run_task(lambda: self.api.delete_print_service_preset(int(preset.get("id") or 0)), lambda _result: (dialog.accept(), self.manage_print_service_presets()), lambda error: QMessageBox.critical(dialog, "Preset", error))
            deactivate.clicked.connect(deactivate_selected); table.doubleClicked.connect(lambda _index: open_editor(selected()))
            dialog.exec()
        self._run_task(
            lambda: (self.api.products("", limit=100), self.api.print_service_presets()), loaded,
            lambda error: QMessageBox.critical(self, "Quick Presets", error),
        )

    def print_service_order_job_ticket(self) -> None:
        if not self.selected_service_order:
            return
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
        order = self.selected_service_order
        total = sum(float(item.get("qty") or 0) * float(item.get("unit_price") or 0) for item in order.get("items") or [])
        total_sheets = sum(int(item.get("total_sheets") or 0) for item in order.get("items") or [])
        deposit = float(order.get("deposit_amount") or 0)
        lines = "".join(
            "<tr>"
            f"<td><b>{html.escape(str(item.get('description') or ''))}</b><br><small>{html.escape(str(item.get('file_name') or ''))}</small></td>"
            f"<td>{html.escape(str(item.get('paper_size') or '—'))}<br><small>{html.escape(str(item.get('paper_type') or ''))}</small></td>"
            f"<td>{html.escape(str(item.get('color_mode') or '—')).replace('_', ' ').title()}<br>{html.escape(str(item.get('print_side') or '—')).replace('_', ' ').title()}</td>"
            f"<td>{int(item.get('pages_per_copy') or 1):,} × {int(item.get('copy_count') or 1):,}<br><small>{int(item.get('total_sheets') or 0):,} sheets</small></td>"
            f"<td>{html.escape(str(item.get('finishing') or '—'))}</td>"
            f"<td>{float(item.get('qty') or 0):g} × {float(item.get('unit_price') or 0):,.0f}<br><b>{float(item.get('qty') or 0) * float(item.get('unit_price') or 0):,.0f} Ks</b></td>"
            "</tr>"
            for item in order.get("items") or []
        )
        ticket_html = f"""
            <style>body {{ font-family: sans-serif; font-size: 10pt; }} table {{ border-collapse: collapse; }} th {{ background: #eeeeee; }} th, td {{ padding: 5px; vertical-align: top; }} .right {{ text-align: right; }}</style>
            <h2>KAY POS · PRINT PRODUCTION SLIP</h2><h3>{html.escape(str(order.get('order_no') or ''))} · {html.escape(str(order.get('job_title') or order.get('item_name') or ''))}</h3>
            <p><b>Customer:</b> {html.escape(str(order.get('customer_name') or 'Walk-in'))} · {html.escape(str(order.get('customer_phone') or ''))}<br>
            <b>File:</b> {html.escape(str(order.get('file_source') or '—'))} · {html.escape(str(order.get('file_reference') or ''))}<br>
            <b>Deadline:</b> {html.escape(str(order.get('expected_at') or '—'))} · <b>Operator:</b> {html.escape(str(order.get('assigned_to') or 'Unassigned'))}<br>
            <b>Approval:</b> {html.escape(str(order.get('approval_status') or 'not_required')).replace('_', ' ').title()} · <b>Status:</b> {html.escape(str(order.get('status') or '')).replace('_', ' ').title()}<br>
            <b>Instructions:</b> {html.escape(str(order.get('complaint') or '—'))}</p>
            <table width='100%' border='1'><tr><th>Service / File</th><th>Paper</th><th>Output</th><th>Pages × Copies</th><th>Finishing</th><th>Amount</th></tr>{lines}</table>
            <p class='right'><b>Total sheets:</b> {total_sheets:,}<br><b>Order total:</b> {total:,.0f} Ks<br><b>Deposit:</b> {deposit:,.0f} Ks<br><b>Balance:</b> {max(0.0, total - deposit):,.0f} Ks</p>
            <p><br><b>Production check:</b> File □ &nbsp; Size □ &nbsp; Color □ &nbsp; Sides □ &nbsp; Copies □ &nbsp; Finishing □</p>
            <p><br>Customer approval/signature: ____________________ &nbsp; Operator: ____________________</p>
        """
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            document = QTextDocument(); document.setHtml(ticket_html); document.print(printer)

    def load_product_management(self) -> None:
        if not self.api: return
        load_token=self._new_page_load("products")
        query = self.manage_product_search.text().strip(); self.manage_product_status.setText("Loading…")
        def loaded(result):
            if not self._page_load_is_current("products",load_token): return
            products, categories = result; self.managed_products = list(products); self.managed_categories = list(categories)
            self.managed_product_rows = {}
            self.manage_product_table.setUpdatesEnabled(False); self.manage_product_table.blockSignals(True); self.manage_product_table.setRowCount(len(products))
            for row, product in enumerate(products):
                variants=product.get("variants") or []; mode=sold_by_mode(product.get("sold_by")); stock=sum(int(v.get("stock") or 0) for v in variants) if mode=="variants" else int(product.get("stock") or 0)
                values=("",product.get("name") or "",product.get("category") or "",product.get("barcode") or product.get("sku") or "—",product.get("sold_by") or "Each",f"{float(product.get('price') or 0):,.0f}",f"{float(product.get('cost') or 0):,.0f}",stock,int(product.get("low_stock") or 0))
                for column,value in enumerate(values):
                    item=QTableWidgetItem(str(value));
                    if column==0: item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    cached=self.thumbnail_cache.get(int(product.get("id") or 0)) if column==0 else None
                    if cached is not None: item.setIcon(QIcon(cached))
                    self.manage_product_table.setItem(row,column,item)
                self.managed_product_rows[int(product.get("id") or 0)] = row
            self.manage_product_table.blockSignals(False); self.manage_product_table.setUpdatesEnabled(True); self.manage_product_table.viewport().update()
            self.manage_product_status.setText(f"{len(products)} product(s) loaded")
            QTimer.singleShot(0, self._load_visible_managed_product_thumbnails)
        self._run_task(lambda:(self.api.products(query,limit=100),self.api.categories()),loaded,lambda error:(self.manage_product_status.setText("Could not load products"),QMessageBox.critical(self,"Products",error)))

    def manage_categories(self) -> None:
        if not self.api or self._threads: return
        CategoryManagerDialog(self.api, self).exec()
        self.load_product_management()
        self.load_categories()

    def add_managed_product(self) -> None:
        if not self.api or self._threads: return
        dialog=ProductEditorDialog(categories=getattr(self,"managed_categories",[]),parent=self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self._save_managed_product(dialog,None)

    def edit_managed_product(self) -> None:
        row=self.manage_product_table.currentRow(); products=getattr(self,"managed_products",[])
        if row<0 or row>=len(products): QMessageBox.warning(self,"Products","Select a product row first."); return
        product=products[row]; product_id=int(product.get("id") or 0)
        dialog=ProductEditorDialog(product,getattr(self,"managed_categories",[]),self,existing_pixmap=self.thumbnail_cache.get(product_id))
        self._load_editor_product_image(dialog, product_id)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        self._save_managed_product(dialog,product_id)

    def _load_editor_product_image(self, dialog: ProductEditorDialog, product_id: int) -> None:
        if not self.api or not product_id:
            dialog.set_existing_image_unavailable()
            return
        reply = self.thumbnail_manager.get(QNetworkRequest(QUrl(f"{self.api.server_url}/api/products/{product_id}/image")))
        if not self.api.verify_tls:
            reply.sslErrors.connect(lambda _errors, current=reply: current.ignoreSslErrors())

        def finished():
            data = bytes(reply.readAll()) if reply.error() == QNetworkReply.NetworkError.NoError else b""
            reply.deleteLater()
            pixmap = QPixmap()
            if data and pixmap.loadFromData(data):
                dialog.set_existing_image(pixmap)
            else:
                dialog.set_existing_image_unavailable()

        reply.finished.connect(finished)

    def _save_managed_product(self, dialog: ProductEditorDialog, product_id: int | None) -> None:
        self.manage_product_status.setText("Saving product…")
        def saved(_product):
            self.manage_product_status.setText("Product saved"); self.thumbnail_cache.pop(int((_product or {}).get("id") or product_id or 0),None)
            QTimer.singleShot(100,self.load_product_management); QTimer.singleShot(200,self.load_products)
        self._run_task(lambda:self.api.save_product(dialog.values(),product_id,dialog.image_path),saved,lambda error:(self.manage_product_status.setText("Could not save product"),QMessageBox.critical(self,"Product",error)))

    def _selected_management_product(self) -> dict | None:
        row = self.stock_table.currentRow()
        products = getattr(self, "management_products", [])
        if row < 0 or row >= len(products):
            QMessageBox.warning(self, "Products & Stock", "Select a product row first.")
            return None
        return products[row]

    def adjust_selected_stock_quantity(self) -> None:
        product = self._selected_management_product()
        if not product or not self.api or self._threads:
            return
        if sold_by_mode(product.get("sold_by")) == "service":
            QMessageBox.warning(self, "Adjustment", "Service items do not use stock adjustments.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Stock Adjustment")
        dialog.resize(520, 470)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Stock Adjustment · {product.get('name') or ''}", objectName="title"))
        form = QFormLayout()
        variants = list(product.get("variants") or [])
        variant_combo = None
        if variants:
            variant_combo = QComboBox()
            for entry in variants:
                label = " / ".join(value for value in (entry.get("color") or "", entry.get("size") or "") if value) or "Variant"
                variant_combo.addItem(f"{label} · Stock {int(entry.get('stock') or 0)}", entry)
            form.addRow("Variant", variant_combo)
        old_quantity = QLabel("0")
        new_quantity = QSpinBox()
        new_quantity.setRange(0, 1000000)
        difference = QLabel("0")
        location_only = QCheckBox("Set Location Only (No Stock Change)")
        adjustment_type = QComboBox()
        adjustment_type.addItems(["Add", "Remove"])
        reason = QLineEdit()
        reason.setPlaceholderText("Damage / Counting Error / Return")
        adjusted_by = QLineEdit(str((self.user or {}).get("full_name") or (self.user or {}).get("username") or ""))
        date = QDateEdit(QDate.currentDate())
        date.setCalendarPopup(True)
        date.setDisplayFormat("yyyy-MM-dd")
        location = QComboBox()
        for value in getattr(self, "management_locations", []) or ["Shop"]:
            location.addItem(str(value), str(value))
        notes = QTextEdit()
        notes.setFixedHeight(70)
        form.addRow("Product", QLabel(product.get("name") or ""))
        form.addRow("Old Qty", old_quantity)
        form.addRow("New Qty", new_quantity)
        form.addRow("Difference", difference)
        form.addRow(location_only)
        form.addRow("Type", adjustment_type)
        form.addRow("Reason", reason)
        form.addRow("Adjusted By", adjusted_by)
        form.addRow("Date", date)
        form.addRow("Location", location)
        form.addRow("Notes", notes)
        layout.addLayout(form)

        def current_stock() -> int:
            selected = variant_combo.currentData() if variant_combo else None
            return int((selected or product).get("stock") or 0)

        def refresh_values(_value=0):
            old = current_stock()
            old_quantity.setText(str(old))
            if _value == -1:
                new_quantity.setValue(old)
            delta = new_quantity.value() - old
            difference.setText(f"{delta:+d}")
            adjustment_type.setCurrentText("Add" if delta >= 0 else "Remove")

        new_quantity.valueChanged.connect(refresh_values)
        if variant_combo:
            variant_combo.currentIndexChanged.connect(lambda _index: refresh_values(-1))
            location_only.setEnabled(False)
        refresh_values(-1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not reason.text().strip() or not adjusted_by.text().strip():
            QMessageBox.warning(self, "Adjustment", "Reason and Adjusted By are required.")
            return
        selected_variant = variant_combo.currentData() if variant_combo else None
        values = {
            "product_id": int(product.get("id") or 0),
            "variant_id": int((selected_variant or {}).get("variant_id") or 0) or None,
            "new_quantity": new_quantity.value(), "adjustment_type": adjustment_type.currentText(),
            "reason": reason.text().strip(), "adjusted_by": adjusted_by.text().strip(),
            "transaction_date": date.date().toString("yyyy-MM-dd"),
            "location": location.currentData() or location.currentText(), "notes": notes.toPlainText(),
            "location_only": location_only.isChecked(),
        }
        self._run_task(
            lambda: self.api.set_stock_quantity(values),
            lambda _result: (self.statusBar().showMessage("Stock adjustment recorded"), QTimer.singleShot(100, self.load_management), QTimer.singleShot(200, self.load_products)),
            lambda error: QMessageBox.critical(self, "Adjustment", error),
        )

    def transfer_selected_stock(self) -> None:
        product = self._selected_management_product()
        if not product or not self.api or self._threads:
            return
        if sold_by_mode(product.get("sold_by")) in {"service", "variants"}:
            QMessageBox.warning(self, "Transfer", "Location transfer is available for standard stock products only.")
            return
        product_locations = list(product.get("locations") or [])
        if not product_locations:
            QMessageBox.warning(self, "Transfer", "This product has no location stock to transfer.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Stock Transfer")
        dialog.resize(500, 390)
        layout = QVBoxLayout(dialog)
        reference = f"TRF-{QDate.currentDate().toString('yyyyMMdd')}"
        layout.addWidget(QLabel(f"Stock Transfer · {reference}", objectName="title"))
        form = QFormLayout()
        from_location = QComboBox()
        for entry in product_locations:
            from_location.addItem(
                f"{entry.get('location')} · Stock {int(entry.get('quantity') or 0)}", entry
            )
        to_location = QComboBox()
        for value in getattr(self, "management_locations", []) or ["Shop"]:
            to_location.addItem(str(value), str(value))
        available = QLabel("0")
        quantity = QSpinBox()
        quantity.setRange(1, 1000000)
        reason = QLineEdit()
        reason.setPlaceholderText("Reason for transfer…")
        notes = QTextEdit()
        notes.setFixedHeight(70)
        form.addRow("Product", QLabel(product.get("name") or ""))
        form.addRow("From", from_location)
        form.addRow("To", to_location)
        form.addRow("Available", available)
        form.addRow("Quantity", quantity)
        form.addRow("Reason", reason)
        form.addRow("Date", QLabel(QDate.currentDate().toString("yyyy-MM-dd")))
        form.addRow("Notes", notes)
        layout.addLayout(form)

        def source_changed(_index=0):
            count = int((from_location.currentData() or {}).get("quantity") or 0)
            available.setText(str(count))
            quantity.setMaximum(max(1, count))

        from_location.currentIndexChanged.connect(source_changed)
        source_changed()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source = (from_location.currentData() or {}).get("location") or ""
        destination = to_location.currentData() or to_location.currentText()
        if source == destination or not reason.text().strip():
            QMessageBox.warning(self, "Transfer", "Choose different locations and enter a reason.")
            return
        values = {
            "product_id": int(product.get("id") or 0), "from_location": source,
            "to_location": destination, "quantity": quantity.value(),
            "reason": reason.text().strip(), "reference": reference, "notes": notes.toPlainText(),
        }
        self._run_task(
            lambda: self.api.transfer_stock(values),
            lambda _result: (self.statusBar().showMessage("Stock transfer recorded"), QTimer.singleShot(100, self.load_management), QTimer.singleShot(200, self.load_products)),
            lambda error: QMessageBox.critical(self, "Transfer", error),
        )

    def view_selected_stock_movements(self) -> None:
        product = self._selected_management_product()
        if not product or not self.api or self._threads:
            return
        product_id = int(product.get("id") or 0)

        def loaded(movements):
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Stock Movements · {product.get('name') or ''}")
            dialog.resize(1000, 560)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f"Stock Movements · {product.get('name') or ''}", objectName="title"))
            table = QTableWidget(len(movements), 10)
            table.setHorizontalHeaderLabels(["ID", "Date", "Type", "Qty", "Old", "New", "Location", "Reference", "By", "Reason"])
            table.setColumnHidden(0, True)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
            for row, movement in enumerate(movements):
                variant_label = " / ".join(value for value in (movement.get("color") or "", movement.get("size") or "") if value)
                location_text = movement.get("location") or ""
                if variant_label:
                    location_text = f"{location_text} · {variant_label}" if location_text else variant_label
                values = (
                    movement.get("id") or 0, movement.get("created_at") or "", movement.get("type") or "",
                    movement.get("quantity") or 0, movement.get("old_stock") or 0,
                    movement.get("new_stock") or 0, location_text,
                    movement.get("reference") or "", movement.get("created_by") or "",
                    movement.get("reason") or movement.get("notes") or "",
                )
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(str(value)))
            layout.addWidget(table, 1)
            actions = QHBoxLayout()
            reverse = QPushButton("Reverse Selected")
            close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close.rejected.connect(dialog.reject)
            actions.addWidget(reverse)
            actions.addStretch()
            actions.addWidget(close)
            layout.addLayout(actions)

            def reverse_selected():
                row = table.currentRow()
                if row < 0:
                    QMessageBox.warning(dialog, "Reverse Movement", "Select a movement row first.")
                    return
                movement = movements[row]
                reference = str(movement.get("reference") or "")
                notes = str(movement.get("notes") or "")
                if "[REVERSED]" in notes or reference.endswith("-REV") or reference.startswith("REV-"):
                    QMessageBox.warning(dialog, "Reverse Movement", "This movement cannot be reversed or was already reversed.")
                    return
                reversal_reason, accepted = QInputDialog.getText(
                    dialog, "Reverse Movement", "Reason for reversal:",
                    text="User requested reversal",
                )
                if not accepted or not reversal_reason.strip():
                    return
                answer = QMessageBox.question(
                    dialog, "Confirm Reversal",
                    f"Reverse movement #{movement.get('id')}?\n\n"
                    f"Type: {movement.get('type')}\nQuantity: {movement.get('quantity')}\n"
                    f"Location: {movement.get('location') or '—'}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                movement_id = int(movement.get("id") or 0)
                dialog.accept()

                def reversed_ok(result):
                    QMessageBox.information(self, "Reverse Movement", str(result.get("message") or "Movement reversed successfully."))
                    QTimer.singleShot(100, self.load_management)
                    QTimer.singleShot(200, self.load_products)

                self._run_task(
                    lambda: self.api.reverse_stock_movement(movement_id, reversal_reason),
                    reversed_ok,
                    lambda error: QMessageBox.critical(self, "Reverse Movement", error),
                )

            reverse.clicked.connect(reverse_selected)
            dialog.exec()

        self._run_task(
            lambda: self.api.stock_movements(product_id), loaded,
            lambda error: QMessageBox.critical(self, "Stock Movements", error),
        )

    def adjust_selected_stock(self, direction: int) -> None:
        row = self.stock_table.currentRow()
        products = getattr(self, "management_products", [])
        if row < 0 or row >= len(products) or not self.api or self._threads:
            return
        product = products[row]
        if direction < 0 and not hasattr(self, "management_customers"):
            self.statusBar().showMessage("Loading customers for Stock Out…")
            self._run_task(
                lambda: self.api.customers("", limit=200),
                lambda customers: (
                    setattr(self, "management_customers", list(customers)),
                    QTimer.singleShot(50, lambda: self.adjust_selected_stock(direction)),
                ),
                lambda error: QMessageBox.critical(self, "Stock Out", error),
            )
            return
        variants = list(product.get("variants") or [])
        if sold_by_mode(product.get("sold_by")) == "variants" and not variants:
            QMessageBox.warning(self, "Stock In", "This product has no active variants.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Stock In" if direction > 0 else "Stock Out")
        dialog.resize(720, 520)
        outer = QVBoxLayout(dialog)
        heading = QHBoxLayout()
        heading.addWidget(QLabel("Stock In Details" if direction > 0 else "Stock Out Details", objectName="title"))
        heading.addStretch()
        reference = f"{'SIN' if direction > 0 else 'SOUT'}-{QDate.currentDate().toString('yyyyMMdd')}"
        heading.addWidget(QLabel(reference))
        outer.addLayout(heading)
        body = QHBoxLayout()
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        quantity = QSpinBox()
        quantity.setRange(1, 1000000)
        reason = QLineEdit("Stock received")
        out_reason = QComboBox()
        out_reason.addItems(["Sale", "Damage", "Transfer", "Other"])
        location = QComboBox()
        if direction < 0 and product.get("locations"):
            for entry in product.get("locations") or []:
                location.addItem(
                    f"{entry.get('location') or 'Default'} · Stock {int(entry.get('quantity') or 0)}",
                    entry.get("location") or "Default",
                )
        else:
            locations = getattr(self, "management_locations", []) or ["Shop"]
            for value in locations:
                location.addItem(str(value), str(value))
        product_label = QLabel(product.get("name") or "")
        product_label.setWordWrap(True)
        form.addRow("Product", product_label)
        variant_combo = None
        if variants:
            variant_combo = QComboBox()
            for entry in variants:
                label = " / ".join(
                    value for value in (entry.get("color") or "", entry.get("size") or "") if value
                ) or entry.get("barcode") or entry.get("sku") or f"Variant {entry.get('variant_id')}"
                variant_combo.addItem(
                    f"{label} · Stock {int(entry.get('stock') or 0)}",
                    entry,
                )
            form.addRow("Variant", variant_combo)
        form.addRow("Quantity", quantity)
        unit_label = QLabel(product.get("unit") or "pcs")
        form.addRow("Unit", unit_label)
        supplier = QComboBox()
        supplier.addItem("None", None)
        for entry in getattr(self, "management_suppliers", []):
            supplier.addItem(entry.get("name") or entry.get("company_name") or "Supplier", entry.get("id"))
        unit_cost = QDoubleSpinBox()
        unit_cost.setRange(0, 999999999999)
        unit_cost.setDecimals(2)
        unit_cost.setValue(float(product.get("cost") or 0))
        unit_cost.setGroupSeparatorShown(True)
        total_cost = QLabel("0 Ks")
        total_cost.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        batch_no = QLineEdit(f"BATCH-{QDate.currentDate().toString('yyyyMMdd')}")
        received_by = QLineEdit(str((self.user or {}).get("full_name") or (self.user or {}).get("username") or ""))
        notes = QTextEdit()
        notes.setPlaceholderText("Additional notes or remarks…")
        notes.setFixedHeight(70)
        if direction > 0:
            form.addRow("Supplier", supplier)
            form.addRow("Unit Cost", unit_cost)
            form.addRow("Total Cost", total_cost)
            form.addRow("Batch No", batch_no)
            form.addRow("Received By", received_by)
        else:
            customer = QComboBox()
            customer.addItem("None", None)
            for entry in getattr(self, "management_customers", []):
                customer_label = entry.get("name") or "Customer"
                if entry.get("phone"):
                    customer_label += f" · {entry.get('phone')}"
                customer.addItem(
                    customer_label,
                    entry.get("id"),
                )
            out_date = QDateEdit(QDate.currentDate())
            out_date.setCalendarPopup(True)
            out_date.setDisplayFormat("yyyy-MM-dd")
            out_reference = QLineEdit(f"SOUT-{QDate.currentDate().toString('yyyyMMdd')}")
            issued_by = QLineEdit(str((self.user or {}).get("full_name") or (self.user or {}).get("username") or ""))
            form.addRow("Reason", out_reason)
            form.addRow("Customer", customer)
            form.addRow("Date", out_date)
        form.addRow("Location", location)
        if direction < 0:
            form.addRow("Reference", out_reference)
            form.addRow("Issued By", issued_by)
        form.addRow("Notes", notes)
        body.addWidget(form_widget, 3)
        if direction:
            info_box = QFrame(objectName="card")
            info_layout = QVBoxLayout(info_box)
            image = QLabel("No product image")
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image.setMinimumSize(240, 230)
            image.setFrameShape(QFrame.Shape.StyledPanel)
            product_id = int(product.get("id") or 0)
            if product_id and self.api:
                image.setText("Loading image…")
                # The product table deliberately uses a small cached thumbnail.
                # This detail view requests the original image instead so that
                # enlarging it does not magnify the thumbnail's pixels.
                url = f"{self.api.server_url}/api/products/{product_id}/image"
                reply = self.thumbnail_manager.get(QNetworkRequest(QUrl(url)))
                if not self.api.verify_tls:
                    reply.sslErrors.connect(lambda _errors, current=reply: current.ignoreSslErrors())

                def stock_image_loaded(current=reply, target=image):
                    data = bytes(current.readAll()) if current.error() == QNetworkReply.NetworkError.NoError else b""
                    current.deleteLater()
                    pixmap = QPixmap()
                    if data and pixmap.loadFromData(data) and target:
                        target.setText("")
                        target.setPixmap(pixmap.scaled(240, 230, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    elif target:
                        target.setText("No product image")

                reply.finished.connect(stock_image_loaded)
            info_layout.addWidget(image, 1)
            info = QLabel(
                f"{product.get('name') or ''}\n"
                f"SKU: {product.get('sku') or 'N/A'}\n"
                f"Barcode: {product.get('barcode') or 'N/A'}\n"
                f"Stock: {int(product.get('stock') or 0)}\n"
                f"Cost: {float(product.get('cost') or 0):,.0f} Ks\n"
                f"Type: {product.get('sold_by') or 'Each'}"
            )
            info.setWordWrap(True)
            info_layout.addWidget(info)
            if variant_combo:
                def update_variant_info(_index=0):
                    selected = variant_combo.currentData() or {}
                    info.setText(
                        f"{product.get('name') or ''}\n"
                        f"Variant: {' / '.join(value for value in (selected.get('color') or '', selected.get('size') or '') if value) or '—'}\n"
                        f"SKU: {selected.get('sku') or product.get('sku') or 'N/A'}\n"
                        f"Barcode: {selected.get('barcode') or product.get('barcode') or 'N/A'}\n"
                        f"Variant Stock: {int(selected.get('stock') or 0)}\n"
                        f"Total Stock: {int(product.get('stock') or 0)}\n"
                        f"Cost: {float(product.get('cost') or 0):,.0f} Ks\n"
                        f"Type: {product.get('sold_by') or 'Variants'}"
                    )

                variant_combo.currentIndexChanged.connect(update_variant_info)
                update_variant_info()
            body.addWidget(info_box, 2)
        outer.addLayout(body, 1)
        quantity.valueChanged.connect(lambda value: total_cost.setText(f"{value * unit_cost.value():,.0f} Ks"))
        unit_cost.valueChanged.connect(lambda value: total_cost.setText(f"{quantity.value() * value:,.0f} Ks"))
        total_cost.setText(f"{quantity.value() * unit_cost.value():,.0f} Ks")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if direction > 0 and not received_by.text().strip():
            QMessageBox.warning(self, "Stock In", "Received By is required.")
            return
        if direction < 0 and not issued_by.text().strip():
            QMessageBox.warning(self, "Stock Out", "Issued By is required.")
            return
        selected_variant = variant_combo.currentData() if variant_combo else None
        adjustment = direction * quantity.value()
        self.statusBar().showMessage("Updating stock…")

        def completed(_product):
            self.statusBar().showMessage("Stock updated and movement recorded")
            QTimer.singleShot(100, self.load_management)
            QTimer.singleShot(200, self.load_products)

        self._run_task(
            lambda: self.api.adjust_stock(
                int(product.get("id") or 0), adjustment,
                variant_id=int((selected_variant or {}).get("variant_id") or 0) or None,
                reason=reason.text() if direction > 0 else out_reason.currentText(),
                location=location.currentData() or location.currentText(),
                supplier_id=supplier.currentData() if direction > 0 else None,
                unit_cost=unit_cost.value() if direction > 0 else 0,
                batch_no=batch_no.text() if direction > 0 else "",
                received_by=received_by.text() if direction > 0 else "",
                notes=notes.toPlainText(),
                customer_id=customer.currentData() if direction < 0 else None,
                reference=out_reference.text() if direction < 0 else "",
                issued_by=issued_by.text() if direction < 0 else "",
                transaction_date=out_date.date().toString("yyyy-MM-dd") if direction < 0 else "",
            ),
            completed, lambda error: QMessageBox.critical(self, "Stock", error),
        )

    def search_history(self) -> None:
        self.history_offset = 0
        self.load_history()

    def load_history(self) -> None:
        if not self.api:
            return
        load_token=self._new_page_load("history")
        query = self.history_search.text().strip()
        offset = self.history_offset
        self.history_status.setText("Loading…")

        def loaded(receipts):
            if not self._page_load_is_current("history",load_token): return
            if query != self.history_search.text().strip() or offset != self.history_offset:
                QTimer.singleShot(100, self.load_history)
                return
            self.receipts = list(receipts)
            self.history_table.setUpdatesEnabled(False); self.history_table.blockSignals(True); self.history_table.setRowCount(len(self.receipts))
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
            self.history_table.blockSignals(False); self.history_table.setUpdatesEnabled(True); self.history_table.viewport().update()
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
            ReceiptDialog(receipt, self, self.refund_receipt, self.receipt_settings).exec()

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
            ReceiptDialog(receipt, self, settings=self.receipt_settings).exec()
            QTimer.singleShot(100, self.load_history)
            QTimer.singleShot(200, self.load_products)

        self._run_task(
            lambda: self.api.refund(sale_id, reason), refunded,
            lambda error: (self.history_status.setText("Refund failed"), QMessageBox.critical(self, "Refund", error)),
        )

    def logout(self) -> None:
        if self.sale_display:
            self.sale_display.close()
        close_api = getattr(self.api, "close", None)
        if callable(close_api):
            close_api()
        self.api = None
        self.user = {}
        self.products = []
        self.receipts = []
        self.last_receipt = {}
        self.receipt_settings = {}
        self.expense_categories = []
        self.expense_categories_loaded = False
        self.history_table.setRowCount(0)
        self.cart.clear()
        self.render_cart()
        self.password_input.clear()
        self.pages.setCurrentWidget(self.login_page)
        self.login_status.setText("Signed out.")
        self.statusBar().showMessage("Ready")
        self.hide()
        QTimer.singleShot(0, self.show_login_dialog)

    def closeEvent(self, event) -> None:
        if self._threads:
            QMessageBox.information(self, "KAY POS Lite", "Please wait for the current server request to finish.")
            event.ignore()
            return
        if self.api:
            self.api.close()
        if self.sale_display:
            self.sale_display.close()
        event.accept()
