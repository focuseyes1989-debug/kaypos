from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QMessageBox, QFormLayout, QComboBox, QCheckBox, QFrame
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtPrintSupport import QPrinterInfo

from models.database import connect_db
from ui.widgets.modern_button import ModernButton
from utils.language import lang


class PrintSettingWidget(QWidget):
    print_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_print_settings()

    def _create_action_button(self, text, icon_name, style=ModernButton.SECONDARY, min_width=96):
        button = ModernButton(text, style)
        button.set_icon(icon_name, size=(15, 15))
        button.set_dense(True)
        button.setMinimumWidth(min_width)
        button.setCheckable(False)
        button.setAutoExclusive(False)
        return button

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.printer_group = QGroupBox("Printer")
        printer_layout = QFormLayout()
        printer_layout.setVerticalSpacing(12)

        printer_row = QHBoxLayout()
        self.receipt_printer_label = QLabel()
        self.printer_combo = QComboBox()
        printer_row.addWidget(self.printer_combo, 1)
        self.btn_refresh_printers = self._create_action_button("Refresh", "refresh", min_width=104)
        self.btn_refresh_printers.clicked.connect(lambda: self.load_printers())
        printer_row.addWidget(self.btn_refresh_printers)
        printer_layout.addRow(self.receipt_printer_label, printer_row)

        self.receipt_paper_label = QLabel()
        self.receipt_paper_combo = QComboBox()
        self.receipt_paper_combo.addItems(["80mm", "58mm", "A4"])
        printer_layout.addRow(self.receipt_paper_label, self.receipt_paper_combo)

        self.receipt_quality_label = QLabel()
        self.receipt_quality_combo = QComboBox()
        self.receipt_quality_combo.addItem("203 dpi (Standard)", "203")
        self.receipt_quality_combo.addItem("300 dpi (High)", "300")
        self.receipt_quality_combo.addItem("600 dpi (Best)", "600")
        printer_layout.addRow(self.receipt_quality_label, self.receipt_quality_combo)

        self.cash_drawer_printer_check = QCheckBox()
        self.cash_drawer_printer_check.setChecked(True)
        printer_layout.addRow("", self.cash_drawer_printer_check)

        self.printer_group.setLayout(printer_layout)
        layout.addWidget(self.printer_group)
        layout.addStretch()

        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.addStretch()

        self.btn_save = self._create_action_button("", "save", ModernButton.PRIMARY, min_width=180)
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setMinimumHeight(36)
        footer_layout.addWidget(self.btn_save)
        layout.addWidget(footer)

        self.retranslateUi()

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.printer_group.setTitle("Printer")
            self.btn_save.setText("သိမ်းဆည်းမည်")
        else:
            self.printer_group.setTitle("Printer")
            self.btn_save.setText("Save Print Settings")

        self.receipt_printer_label.setText("Receipt Printer:")
        self.receipt_paper_label.setText("Paper Size:")
        self.receipt_quality_label.setText("Print Quality:")
        self.btn_refresh_printers.setText("Refresh")
        self.cash_drawer_printer_check.setText("Use receipt printer for cash drawer")
        for button in (self.btn_refresh_printers, self.btn_save):
            button.update_theme()

    def load_printers(self, selected_name=None):
        if selected_name is None:
            selected_name = self.printer_combo.currentData() if hasattr(self, "printer_combo") else ""
        selected_name = selected_name or ""

        self.printer_combo.blockSignals(True)
        self.printer_combo.clear()
        self.printer_combo.addItem("Windows default printer", "")

        printer_names = []
        default_printer = QPrinterInfo.defaultPrinter()
        default_name = default_printer.printerName() if not default_printer.isNull() else ""
        for info in QPrinterInfo.availablePrinters():
            name = info.printerName()
            printer_names.append(name)
            suffix = " (default)" if name == default_name else ""
            self.printer_combo.addItem(f"{name}{suffix}", name)

        if selected_name and selected_name not in printer_names:
            self.printer_combo.addItem(f"{selected_name} (not found)", selected_name)

        target_index = self.printer_combo.findData(selected_name)
        if target_index >= 0:
            self.printer_combo.setCurrentIndex(target_index)
        self.printer_combo.blockSignals(False)

    def load_print_settings(self):
        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key='receipt_printer_name'")
        row = cursor.fetchone()
        self.load_printers(row[0] if row else "")

        cursor.execute("SELECT value FROM settings WHERE key='receipt_paper_size'")
        row = cursor.fetchone()
        if row and row[0] in ("0", "1", "2"):
            self.receipt_paper_combo.setCurrentIndex(int(row[0]))

        cursor.execute("SELECT value FROM settings WHERE key='receipt_print_quality'")
        row = cursor.fetchone()
        quality_index = self.receipt_quality_combo.findData(row[0] if row else "203")
        if quality_index >= 0:
            self.receipt_quality_combo.setCurrentIndex(quality_index)

        cursor.execute("SELECT value FROM settings WHERE key='receipt_cash_drawer_use_receipt_printer'")
        row = cursor.fetchone()
        self.cash_drawer_printer_check.setChecked(row[0] == '1' if row else True)
        conn.close()

    def save_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("receipt_printer_name", self.printer_combo.currentData() or ""),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("receipt_paper_size", str(self.receipt_paper_combo.currentIndex())),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("receipt_print_quality", self.receipt_quality_combo.currentData() or "203"),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (
                "receipt_cash_drawer_use_receipt_printer",
                '1' if self.cash_drawer_printer_check.isChecked() else '0',
            ),
        )
        conn.commit()
        conn.close()

        msg = "Print settings saved."
        if lang.get_current() == "my":
            msg = "Print သတ်မှတ်ချက်များ သိမ်းဆည်းပြီးပါပြီ။"
        QMessageBox.information(self, "Saved", msg)
        self.print_settings_changed.emit()
