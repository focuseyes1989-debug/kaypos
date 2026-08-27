"""Persistent printer and manual page-sequence settings for car forms."""

from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes

from PyQt6.QtCore import QSettings, QRectF, Qt
from PyQt6.QtGui import QPageLayout, QPageSize, QPainter
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
)

from car_client.form_templates import PAGE_NUMBERS, render_form_page


SETTINGS_PREFIX = "form_print"


def parse_page_sequence(value: str) -> list[int]:
    """Parse a sequence such as ``1,1,2,3,4`` and reject unknown pages."""
    tokens = [token for token in re.split(r"[\s,;]+", str(value or "").strip()) if token]
    if not tokens:
        raise ValueError("Enter at least one page number, for example: 1,2,3,4")
    if any(not token.isdigit() or int(token) not in PAGE_NUMBERS for token in tokens):
        raise ValueError("Only page numbers 1, 2, 3 and 4 are allowed.")
    if len(tokens) > 100:
        raise ValueError("A print sequence can contain at most 100 pages.")
    return [int(token) for token in tokens]


def saved_printer_name(settings: QSettings | None = None) -> str:
    settings = settings or QSettings("KAY POS", "Car Management Client")
    return str(settings.value(f"{SETTINGS_PREFIX}/printer", "") or "").strip()


def available_printer_names() -> list[str]:
    """List printer queue names without opening vendor status monitors."""
    if sys.platform != "win32":
        return list(QPrinterInfo.availablePrinterNames())

    class PRINTER_INFO_4W(ctypes.Structure):
        _fields_ = [
            ("pPrinterName", wintypes.LPWSTR),
            ("pServerName", wintypes.LPWSTR),
            ("Attributes", wintypes.DWORD),
        ]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    enum_printers = winspool.EnumPrintersW
    enum_printers.argtypes = [
        wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, wintypes.LPBYTE,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    needed = wintypes.DWORD(0)
    returned = wintypes.DWORD(0)
    flags = 0x00000002 | 0x00000004  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    enum_printers(flags, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if not needed.value:
        return []
    buffer = (ctypes.c_byte * needed.value)()
    if not enum_printers(
        flags, None, 4, ctypes.cast(buffer, wintypes.LPBYTE), needed.value,
        ctypes.byref(needed), ctypes.byref(returned),
    ):
        return []
    entries = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_4W))
    return sorted(
        {str(entries[index].pPrinterName or "").strip() for index in range(returned.value)} - {""},
        key=str.casefold,
    )


def default_printer_name() -> str:
    if sys.platform != "win32":
        return str(QPrinterInfo.defaultPrinterName() or "")
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    needed = wintypes.DWORD(0)
    winspool.GetDefaultPrinterW(None, ctypes.byref(needed))
    if not needed.value:
        return ""
    buffer = ctypes.create_unicode_buffer(needed.value)
    return buffer.value if winspool.GetDefaultPrinterW(buffer, ctypes.byref(needed)) else ""


def automatic_print_ready(settings: QSettings | None = None) -> tuple[bool, str]:
    """Check readiness without claiming a queued job."""
    name = saved_printer_name(settings)
    if not name:
        return False, "Select and save a printer before enabling automatic printing."
    available = set(available_printer_names())
    if name not in available:
        return False, f"Saved printer is unavailable: {name}"
    return True, name


def print_record_pages(record: dict, pages, copies=1, settings: QSettings | None = None, printer_name_override="") -> str:
    """Send a queue job to the saved Windows printer without opening a dialog."""
    settings = settings or QSettings("KAY POS", "Car Management Client")
    pages = parse_page_sequence(",".join(str(page) for page in pages))
    printer_name = str(printer_name_override or saved_printer_name(settings)).strip()
    if printer_name not in set(available_printer_names()):
        raise RuntimeError(f"Selected printer is unavailable: {printer_name or 'None'}")
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(printer_name)
    printer.setCopyCount(max(1, min(int(copies or 1), 99)))
    saved_size = int(settings.value(f"{SETTINGS_PREFIX}/page_size", int(QPageSize.PageSizeId.A4.value)))
    saved_orientation = int(settings.value(f"{SETTINGS_PREFIX}/orientation", int(QPageLayout.Orientation.Portrait.value)))
    saved_resolution = int(settings.value(f"{SETTINGS_PREFIX}/resolution", 0))
    try:
        printer.setPageSize(QPageSize(QPageSize.PageSizeId(saved_size)))
    except ValueError:
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    try:
        printer.setPageOrientation(QPageLayout.Orientation(saved_orientation))
    except ValueError:
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    if saved_resolution > 0:
        printer.setResolution(saved_resolution)
    printer.setColorMode(
        QPrinter.ColorMode.GrayScale
        if str(settings.value(f"{SETTINGS_PREFIX}/color", "color")) == "grayscale"
        else QPrinter.ColorMode.Color
    )
    printer.setDuplex({
        "long": QPrinter.DuplexMode.DuplexLongSide,
        "short": QPrinter.DuplexMode.DuplexShortSide,
    }.get(str(settings.value(f"{SETTINGS_PREFIX}/duplex", "none")), QPrinter.DuplexMode.DuplexNone))
    painter = QPainter(printer)
    if not painter.isActive():
        raise RuntimeError("Windows could not start the saved printer job.")
    try:
        for index, page_number in enumerate(pages):
            if index and not printer.newPage():
                raise RuntimeError("The printer could not create the next page.")
            image = render_form_page(record, page_number)
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            scaled = image.size().scaled(page_rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(
                page_rect.x() + (page_rect.width() - scaled.width()) / 2,
                page_rect.y() + (page_rect.height() - scaled.height()) / 2,
                scaled.width(), scaled.height(),
            )
            painter.drawImage(target, image)
    finally:
        painter.end()
    return printer_name


class FormPrintSettingsDialog(QDialog):
    def __init__(self, record: dict | None, parent=None, settings: QSettings | None = None, embedded=False):
        super().__init__(parent)
        self.record = record or {}
        self.embedded = embedded
        self.settings = settings or QSettings("KAY POS", "Car Management Client")
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        self.setWindowTitle("Car Form Print Settings")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        title = QLabel("Print Forms")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        layout.addWidget(title)
        help_text = QLabel(
            "Enter pages in the exact order required. Repeated pages are supported, "
            "for example: 1,1,2,3,4,2,3,2,3,4"
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.pages_edit = QLineEdit()
        self.pages_edit.setPlaceholderText("1,2,3,4")
        form.addRow("Page sequence", self.pages_edit)

        self.printer_combo = QComboBox()
        available_names = available_printer_names()
        for name in available_names:
            self.printer_combo.addItem(name)
        form.addRow("Printer", self.printer_combo)

        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 99)
        form.addRow("Copies", self.copies_spin)

        self.color_combo = QComboBox()
        self.color_combo.addItem("Color", "color")
        self.color_combo.addItem("Grayscale", "grayscale")
        form.addRow("Color mode", self.color_combo)

        self.duplex_combo = QComboBox()
        self.duplex_combo.addItem("One-sided", "none")
        self.duplex_combo.addItem("Two-sided · Long edge", "long")
        self.duplex_combo.addItem("Two-sided · Short edge", "short")
        form.addRow("Duplex", self.duplex_combo)
        layout.addLayout(form)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.print_progress = QProgressBar()
        self.print_progress.setRange(0, 100)
        self.print_progress.setValue(0)
        self.print_progress.setTextVisible(True)
        self.print_progress.setFormat("Ready")
        self.print_progress.hide()
        layout.addWidget(self.print_progress)
        actions = QHBoxLayout()
        self.save_button = QPushButton("Save Settings")
        self.preferences_button = QPushButton("Printer Preferences")
        self.print_button = QPushButton("Print")
        self.print_button.setObjectName("primary")
        close_button = QPushButton("Close")
        actions.addWidget(self.save_button)
        actions.addWidget(self.preferences_button)
        actions.addStretch()
        actions.addWidget(close_button)
        actions.addWidget(self.print_button)
        layout.addLayout(actions)

        self.save_button.clicked.connect(self.save_settings)
        self.preferences_button.clicked.connect(self.open_printer_preferences)
        self.print_button.clicked.connect(self.print_forms)
        close_button.clicked.connect(self.reject)
        if embedded:
            close_button.hide()
            self.print_button.hide()
            self.status.setText("Settings saved here are used when printing a selected car record from Auto Fill Forms.")
        self._load_settings(available_names)

    def _key(self, name: str) -> str:
        return f"{SETTINGS_PREFIX}/{name}"

    def _load_settings(self, available_names: list[str]) -> None:
        self.preference_resolution = int(self.settings.value(self._key("resolution"), 0))
        self.preference_page_size = int(self.settings.value(self._key("page_size"), int(QPageSize.PageSizeId.A4.value)))
        self.preference_orientation = int(self.settings.value(self._key("orientation"), int(QPageLayout.Orientation.Portrait.value)))
        self.pages_edit.setText(str(self.settings.value(self._key("pages"), "1,2,3,4")))
        self.copies_spin.setValue(int(self.settings.value(self._key("copies"), 1)))
        saved_printer = str(self.settings.value(self._key("printer"), ""))
        if saved_printer and saved_printer not in available_names:
            self.printer_combo.addItem(f"{saved_printer} (Unavailable)", saved_printer)
        if saved_printer:
            for index in range(self.printer_combo.count()):
                name = self.printer_combo.itemData(index) or self.printer_combo.itemText(index)
                if name == saved_printer:
                    self.printer_combo.setCurrentIndex(index)
                    break
        elif default_printer_name():
            self.printer_combo.setCurrentText(default_printer_name())
        self._select_data(self.color_combo, str(self.settings.value(self._key("color"), "color")))
        self._select_data(self.duplex_combo, str(self.settings.value(self._key("duplex"), "none")))
        if not available_names:
            self.status.setText("No Windows printer is currently available.")
            self.print_button.setEnabled(False)

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _printer_name(self) -> str:
        return str(self.printer_combo.currentData() or self.printer_combo.currentText()).strip()

    def save_settings(self, show_message=True) -> bool:
        try:
            pages = parse_page_sequence(self.pages_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Page Sequence", str(exc))
            return False
        self.pages_edit.setText(",".join(map(str, pages)))
        self.settings.setValue(self._key("pages"), self.pages_edit.text())
        self.settings.setValue(self._key("printer"), self._printer_name())
        self.settings.setValue(self._key("copies"), self.copies_spin.value())
        self.settings.setValue(self._key("color"), self.color_combo.currentData())
        self.settings.setValue(self._key("duplex"), self.duplex_combo.currentData())
        self.settings.setValue(self._key("resolution"), getattr(self, "preference_resolution", 0))
        self.settings.setValue(self._key("page_size"), getattr(self, "preference_page_size", int(QPageSize.PageSizeId.A4.value)))
        self.settings.setValue(self._key("orientation"), getattr(self, "preference_orientation", int(QPageLayout.Orientation.Portrait.value)))
        self.settings.sync()
        self.status.setText("Print settings saved for the next app session.")
        if show_message:
            QMessageBox.information(self, "Print Settings", "Printer and page sequence settings were saved.")
        return True

    def open_printer_preferences(self) -> None:
        try:
            printer = self._configured_printer()
        except Exception as exc:
            QMessageBox.warning(self, "Printer Preferences", str(exc))
            return
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Printer Preferences")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.printer_combo.setCurrentText(printer.printerName())
        self.copies_spin.setValue(max(1, printer.copyCount()))
        self._select_data(self.color_combo, "grayscale" if printer.colorMode() == QPrinter.ColorMode.GrayScale else "color")
        duplex_value = {
            QPrinter.DuplexMode.DuplexLongSide: "long",
            QPrinter.DuplexMode.DuplexShortSide: "short",
        }.get(printer.duplex(), "none")
        self._select_data(self.duplex_combo, duplex_value)
        self.preference_resolution = printer.resolution()
        self.preference_page_size = int(printer.pageLayout().pageSize().id().value)
        self.preference_orientation = int(printer.pageLayout().orientation().value)
        self.save_settings(show_message=False)
        self.status.setText("Windows printer preferences captured and saved.")

    def _configured_printer(self) -> QPrinter:
        printer_name = self._printer_name()
        available_names = set(available_printer_names())
        if not printer_name or printer_name not in available_names:
            raise RuntimeError("The selected printer is not currently available.")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(printer_name)
        printer.setCopyCount(self.copies_spin.value())
        saved_size = int(self.settings.value(self._key("page_size"), int(QPageSize.PageSizeId.A4.value)))
        saved_orientation = int(self.settings.value(self._key("orientation"), int(QPageLayout.Orientation.Portrait.value)))
        saved_resolution = int(self.settings.value(self._key("resolution"), 0))
        try:
            printer.setPageSize(QPageSize(QPageSize.PageSizeId(saved_size)))
        except ValueError:
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        try:
            printer.setPageOrientation(QPageLayout.Orientation(saved_orientation))
        except ValueError:
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        if saved_resolution > 0:
            printer.setResolution(saved_resolution)
        printer.setColorMode(
            QPrinter.ColorMode.GrayScale
            if self.color_combo.currentData() == "grayscale"
            else QPrinter.ColorMode.Color
        )
        duplex = {
            "long": QPrinter.DuplexMode.DuplexLongSide,
            "short": QPrinter.DuplexMode.DuplexShortSide,
        }.get(self.duplex_combo.currentData(), QPrinter.DuplexMode.DuplexNone)
        printer.setDuplex(duplex)
        return printer

    def _set_print_busy(self, busy: bool, total_pages=0) -> None:
        self.print_button.setEnabled(not busy)
        self.print_button.setText("Printing..." if busy else "Print")
        self.save_button.setEnabled(not busy)
        self.preferences_button.setEnabled(not busy)
        self.pages_edit.setEnabled(not busy)
        self.printer_combo.setEnabled(not busy)
        self.copies_spin.setEnabled(not busy)
        self.color_combo.setEnabled(not busy)
        self.duplex_combo.setEnabled(not busy)
        if busy:
            self.print_progress.setRange(0, max(1, int(total_pages)))
            self.print_progress.setValue(0)
            self.print_progress.setFormat("Preparing print job...")
            self.print_progress.show()
        QApplication.processEvents()

    def print_forms(self) -> None:
        busy_started = False
        try:
            pages = parse_page_sequence(self.pages_edit.text())
            printer = self._configured_printer()
            if not self.save_settings(show_message=False):
                return
            self._set_print_busy(True, len(pages))
            busy_started = True
            self.status.setText(f"Preparing {len(pages)} page(s) for {self._printer_name()}...")
            QApplication.processEvents()
            painter = QPainter(printer)
            if not painter.isActive():
                raise RuntimeError("Windows could not start the selected printer job.")
            try:
                for index, page_number in enumerate(pages):
                    if index and not printer.newPage():
                        raise RuntimeError("The printer could not create the next page.")
                    image = render_form_page(self.record, page_number)
                    page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                    scaled = image.size().scaled(page_rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
                    target = QRectF(
                        page_rect.x() + (page_rect.width() - scaled.width()) / 2,
                        page_rect.y() + (page_rect.height() - scaled.height()) / 2,
                        scaled.width(),
                        scaled.height(),
                    )
                    painter.drawImage(target, image)
                    completed = index + 1
                    self.print_progress.setValue(completed)
                    self.print_progress.setFormat(f"Printing page {completed} of {len(pages)} · %p%")
                    self.status.setText(f"Printing page {completed} of {len(pages)}...")
                    QApplication.processEvents()
            finally:
                painter.end()
        except Exception as exc:
            if busy_started:
                self.print_progress.setFormat("Print failed")
                self.status.setText(f"Print failed: {exc}")
            QMessageBox.critical(self, "Could Not Print Forms", str(exc))
            return
        finally:
            if busy_started:
                self._set_print_busy(False)
        self.print_progress.setValue(len(pages))
        self.print_progress.setFormat("Completed · 100%")
        self.status.setText(f"Completed — sent {len(pages)} page(s) to {self._printer_name()}.")
        QMessageBox.information(
            self,
            "Print Job Sent",
            f"Sent {len(pages)} page(s) to {self._printer_name()}.\nSequence: {','.join(map(str, pages))}",
        )
