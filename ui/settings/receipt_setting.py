# ui/settings/receipt_setting.py (အပိုင်း - Logo & QR Code Group)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QFileDialog, QTextEdit, QCheckBox, QScrollArea, QFrame,
    QMessageBox, QFormLayout, QGridLayout, QSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from models.database import connect_db
from ui.themes.theme_manager import get_theme_colors
from utils.language import lang
from utils.receipt_template import (
    DEFAULT_RECEIPT_TEMPLATE,
    build_receipt_text_lines,
    load_receipt_template_settings,
    sample_receipt_data,
    save_receipt_template_settings,
)
from utils.receipt_images import clear_receipt_image, resolve_receipt_image_path, save_receipt_image
from ui.widgets.modern_button import ModernButton
import os


class ReceiptSettingWidget(QWidget):
    receipt_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_receipt_settings()

    def _create_action_button(self, text, icon_name, style=ModernButton.SECONDARY, min_width=96):
        button = ModernButton(text, style)
        button.set_icon(icon_name, size=(15, 15))
        button.set_dense(True)
        button.setMinimumWidth(min_width)
        button.setCheckable(False)
        button.setAutoExclusive(False)
        return button

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(16)
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)
        left_column = QWidget()
        right_column = QWidget()
        self.left_column = left_column
        self.right_column = right_column
        left_column.setMinimumWidth(440)
        right_column.setMinimumWidth(440)
        left_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QVBoxLayout(left_column)
        right_layout = QVBoxLayout(right_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(20)
        right_layout.setSpacing(20)

        # ========== BUSINESS INFORMATION GROUP ==========
        business_group = QGroupBox("Business Information")
        self.business_group = business_group
        business_layout = QFormLayout()
        business_layout.setVerticalSpacing(15)

        # Shop Name
        self.shop_name_label = QLabel()
        self.shop_name_edit = QLineEdit()
        self.shop_name_edit.setPlaceholderText("Enter your shop name")
        self.shop_name_edit.textChanged.connect(self.update_template_preview)
        business_layout.addRow(self.shop_name_label, self.shop_name_edit)

        # Shop Phone
        self.shop_phone_label = QLabel()
        self.shop_phone_edit = QLineEdit()
        self.shop_phone_edit.setPlaceholderText("e.g., 09-123456789")
        self.shop_phone_edit.textChanged.connect(self.update_template_preview)
        business_layout.addRow(self.shop_phone_label, self.shop_phone_edit)

        # Shop Address
        self.shop_address_label = QLabel()
        self.shop_address_edit = QTextEdit()
        self.shop_address_edit.setMaximumHeight(60)
        self.shop_address_edit.setPlaceholderText("Enter your shop address")
        self.shop_address_edit.textChanged.connect(self.update_template_preview)
        business_layout.addRow(self.shop_address_label, self.shop_address_edit)

        business_group.setLayout(business_layout)

        # ========== LOGO & QR CODE GROUP ==========
        logo_group = QGroupBox("Logo & QR Code")
        self.logo_group = logo_group
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(12)
        
        # Logo & QR section (side by side)
        logo_section = QHBoxLayout()
        logo_section.setSpacing(20)
        logo_section.setAlignment(Qt.AlignmentFlag.AlignTop)  # ✅ Align to top
        
        # ===== LOGO (Left) =====
        logo_widget = QWidget()
        logo_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        logo_widget_layout = QVBoxLayout(logo_widget)
        logo_widget_layout.setSpacing(5)
        logo_widget_layout.setContentsMargins(0, 0, 0, 0)
        
        self.logo_preview_label = QLabel("Logo Preview")
        self.logo_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_widget_layout.addWidget(self.logo_preview_label)
        
        # ✅ Fixed size container for logo
        self.logo_preview_container = QFrame()
        self.logo_preview_container.setMinimumWidth(220)
        self.logo_preview_container.setFixedHeight(120)
        self.logo_preview_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.logo_preview_container.setStyleSheet("""
            border: 1px solid #ced4da; 
            border-radius: 4px; 
            background-color: #f8f9fa;
        """)
        logo_preview_layout = QVBoxLayout(self.logo_preview_container)
        logo_preview_layout.setContentsMargins(5, 5, 5, 5)
        logo_preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # ✅ Center content
        
        self.logo_preview = QLabel()
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setMinimumSize(200, 100)
        self.logo_preview.setMaximumSize(200, 100)
        self.logo_preview.setStyleSheet("background-color: transparent;")
        self.logo_preview.setText("No logo")
        logo_preview_layout.addWidget(self.logo_preview)
        
        logo_widget_layout.addWidget(self.logo_preview_container)
        logo_name_spacer = QWidget()
        logo_name_spacer.setFixedHeight(28)
        logo_widget_layout.addWidget(logo_name_spacer)
        
        # Logo path and browse button
        logo_row = QHBoxLayout()
        self.logo_path_edit = QLineEdit()
        self.logo_path_edit.setReadOnly(True)
        self.logo_path_edit.setPlaceholderText("No logo selected")
        logo_row.addWidget(self.logo_path_edit)
        self.btn_browse_logo = self._create_action_button("Browse", "image", min_width=96)
        self.btn_browse_logo.clicked.connect(lambda: self.select_image("logo"))
        logo_row.addWidget(self.btn_browse_logo)
        self.btn_clear_logo = self._create_action_button("Clear", "delete", min_width=86)
        self.btn_clear_logo.clicked.connect(lambda: self.clear_image("logo"))
        logo_row.addWidget(self.btn_clear_logo)
        logo_widget_layout.addLayout(logo_row)
        
        logo_section.addWidget(logo_widget, 1)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setFixedWidth(2)
        separator.setFixedHeight(180)  # ✅ Fixed height to match container
        separator.hide()
        
        # ===== QR CODE (Right) =====
        qr_widget = QWidget()
        qr_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        qr_widget_layout = QVBoxLayout(qr_widget)
        qr_widget_layout.setSpacing(5)
        qr_widget_layout.setContentsMargins(0, 0, 0, 0)
        
        self.qr_preview_label = QLabel("QR Code Preview")
        self.qr_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_widget_layout.addWidget(self.qr_preview_label)
        
        # ✅ Fixed size container for QR
        self.qr_preview_container = QFrame()
        self.qr_preview_container.setMinimumWidth(220)
        self.qr_preview_container.setFixedHeight(120)
        self.qr_preview_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.qr_preview_container.setStyleSheet("""
            border: 1px solid #ced4da; 
            border-radius: 4px; 
            background-color: #f8f9fa;
        """)
        qr_preview_layout = QVBoxLayout(self.qr_preview_container)
        qr_preview_layout.setContentsMargins(5, 5, 5, 5)
        qr_preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # ✅ Center content
        
        self.qr_preview = QLabel()
        self.qr_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_preview.setMinimumSize(200, 100)
        self.qr_preview.setMaximumSize(200, 100)
        self.qr_preview.setStyleSheet("background-color: transparent;")
        self.qr_preview.setText("No QR code")
        qr_preview_layout.addWidget(self.qr_preview)
        
        qr_widget_layout.addWidget(self.qr_preview_container)
        
        # QR Name
        qr_name_row = QHBoxLayout()
        self.qr_name_label = QLabel("QR Name:")
        self.qr_name_edit = QLineEdit()
        self.qr_name_edit.setPlaceholderText("e.g., KBZ Pay, Wave Pay, AYA Pay")
        qr_name_row.addWidget(self.qr_name_label)
        qr_name_row.addWidget(self.qr_name_edit)
        qr_widget_layout.addLayout(qr_name_row)
        
        # QR path and browse button
        qr_row = QHBoxLayout()
        self.qr_path_edit = QLineEdit()
        self.qr_path_edit.setReadOnly(True)
        self.qr_path_edit.setPlaceholderText("No QR code selected")
        qr_row.addWidget(self.qr_path_edit)
        self.btn_browse_qr = self._create_action_button("Browse QR", "image", min_width=116)
        self.btn_browse_qr.clicked.connect(lambda: self.select_image("qr"))
        qr_row.addWidget(self.btn_browse_qr)
        self.btn_clear_qr = self._create_action_button("Clear", "delete", min_width=86)
        self.btn_clear_qr.clicked.connect(lambda: self.clear_image("qr"))
        qr_row.addWidget(self.btn_clear_qr)
        qr_widget_layout.addLayout(qr_row)
        
        logo_section.addWidget(qr_widget, 1)
        logo_layout.addLayout(logo_section)
        
        logo_group.setLayout(logo_layout)
        left_layout.addWidget(logo_group)
        left_layout.addWidget(business_group)

        # ========== RECEIPT HEADER/FOOTER GROUP ==========
        receipt_group = QGroupBox("Header & Footer")
        self.receipt_group = receipt_group
        receipt_layout = QFormLayout()
        receipt_layout.setVerticalSpacing(12)

        # Receipt Header
        self.header_label = QLabel()
        self.receipt_header = QTextEdit()
        self.receipt_header.setMaximumHeight(80)
        self.receipt_header.setPlaceholderText("Header message (e.g., Thank you for shopping!)")
        self.receipt_header.textChanged.connect(self.update_template_preview)
        receipt_layout.addRow(self.header_label, self.receipt_header)

        # Footer Message
        self.footer_label = QLabel()
        self.receipt_footer = QTextEdit()
        self.receipt_footer.setMaximumHeight(80)
        self.receipt_footer.setPlaceholderText("Footer message (e.g., Visit us again!)")
        self.receipt_footer.textChanged.connect(self.update_template_preview)
        receipt_layout.addRow(self.footer_label, self.receipt_footer)

        # Show customer name on receipt
        self.show_customer_check = QCheckBox()
        self.show_customer_check.toggled.connect(self.update_template_preview)
        receipt_layout.addRow("", self.show_customer_check)

        receipt_group.setLayout(receipt_layout)
        left_layout.addWidget(receipt_group)

        # ========== TEMPLATE EDITOR GROUP ==========
        template_group = QGroupBox("Receipt Template Editor")
        self.template_group = template_group
        template_layout = QVBoxLayout()
        template_layout.setSpacing(10)

        self.template_checks = {}
        checks_grid = QGridLayout()
        checks_grid.setHorizontalSpacing(12)
        checks_grid.setVerticalSpacing(6)
        template_options = [
            ("receipt_show_logo", "Logo"),
            ("receipt_show_shop_phone", "Shop phone"),
            ("receipt_show_shop_address", "Shop address"),
            ("receipt_show_invoice", "Invoice/date"),
            ("receipt_show_payment_type", "Payment type"),
            ("receipt_show_customer", "Customer"),
            ("receipt_show_item_prices", "Item prices"),
            ("receipt_show_subtotal", "Subtotal"),
            ("receipt_show_discount", "Discount"),
            ("receipt_show_tax", "Tax"),
            ("receipt_show_payment_change", "Payment/change"),
            ("receipt_show_thank_you", "Thank-you"),
        ]
        for index, (key, text) in enumerate(template_options):
            check = QCheckBox(text)
            check.toggled.connect(self.update_template_preview)
            self.template_checks[key] = check
            checks_grid.addWidget(check, index // 3, index % 3)
        template_layout.addLayout(checks_grid)

        template_form = QFormLayout()
        self.thank_you_edit = QLineEdit()
        self.thank_you_edit.setPlaceholderText("THANK YOU")
        self.thank_you_edit.textChanged.connect(self.update_template_preview)
        template_form.addRow("Thank-you Text:", self.thank_you_edit)

        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(24, 64)
        self.line_width_spin.setValue(32)
        self.line_width_spin.valueChanged.connect(self.update_template_preview)
        template_form.addRow("Line Width:", self.line_width_spin)
        template_layout.addLayout(template_form)

        self.template_preview = QTextEdit()
        self.template_preview.setReadOnly(True)
        self.template_preview.setMinimumHeight(220)
        self.template_preview.setFontFamily("Courier New")
        self.template_preview.setStyleSheet("QTextEdit { background: #ffffff; color: #111111; }")
        template_layout.addWidget(QLabel("Live Preview:"))
        template_layout.addWidget(self.template_preview)

        self.btn_template_reset = self._create_action_button("Reset Template", "undo", min_width=140)
        self.btn_template_reset.clicked.connect(self.reset_template_defaults)
        template_layout.addWidget(self.btn_template_reset, alignment=Qt.AlignmentFlag.AlignRight)

        template_group.setLayout(template_layout)

        right_layout.addWidget(template_group)

        left_layout.addStretch()
        right_layout.addStretch()
        columns_layout.addWidget(left_column, 1)
        columns_layout.addWidget(right_column, 1)
        content_layout.addLayout(columns_layout)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("receiptSettingsFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.addStretch()

        # Save button
        self.btn_save = self._create_action_button("", "save", ModernButton.PRIMARY, min_width=200)
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setMinimumHeight(36)
        footer_layout.addWidget(self.btn_save)

        layout.addWidget(footer)
        self.setLayout(layout)
        self.retranslateUi()
        self.update_theme()

    def set_visible_sections(self, sections):
        """Show only selected receipt groups when embedded in Settings Center."""
        visible = set(sections or [])
        group_map = {
            "branding": self.logo_group,
            "business": self.business_group,
            "text": self.receipt_group,
            "template": self.template_group,
        }
        for key, group in group_map.items():
            group.setVisible(key in visible)

        self.left_column.setVisible(any(key in visible for key in ("branding", "business", "text")))
        self.right_column.setVisible("template" in visible)

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.business_group.setTitle("Business Information")
            self.logo_group.setTitle("Logo & QR Code")
            self.receipt_group.setTitle("Header & Footer")
            self.template_group.setTitle("Receipt Template Editor")
            self.shop_name_label.setText("ဆိုင်အမည်:")
            self.shop_phone_label.setText("ဖုန်းနံပါတ်:")
            self.shop_address_label.setText("လိပ်စာ:")
            self.logo_preview_label.setText("ဆိုင်အမှတ်တံဆိပ် အကြိုကြည့်ရန်")
            self.btn_browse_logo.setText("ပုံရွေးရန်")
            self.btn_clear_logo.setText("ရှင်းရန်")
            self.qr_preview_label.setText("QR Code အကြိုကြည့်ရန်")
            self.qr_name_label.setText("QR အမည်:")
            self.btn_browse_qr.setText("QR ပုံရွေးရန်")
            self.btn_clear_qr.setText("ရှင်းရန်")
            self.header_label.setText("ပြေစာအပေါ်ပိုင်း:")
            self.footer_label.setText("ပြေစာအောက်ပိုင်း:")
            self.show_customer_check.setText("ပြေစာတွင်ဝယ်ယူသူအမည်ပြရန်")
            self.btn_save.setText("သိမ်းဆည်းမည်")
        else:
            self.business_group.setTitle("Business Information")
            self.logo_group.setTitle("Logo & QR Code")
            self.receipt_group.setTitle("Header & Footer")
            self.template_group.setTitle("Receipt Template Editor")
            self.shop_name_label.setText("Shop Name:")
            self.shop_phone_label.setText("Phone Number:")
            self.shop_address_label.setText("Address:")
            self.logo_preview_label.setText("Logo Preview")
            self.btn_browse_logo.setText("Browse")
            self.btn_clear_logo.setText("Clear")
            self.qr_preview_label.setText("QR Code Preview")
            self.qr_name_label.setText("QR Name:")
            self.btn_browse_qr.setText("Browse QR")
            self.btn_clear_qr.setText("Clear")
            self.header_label.setText("Receipt Header:")
            self.footer_label.setText("Receipt Footer:")
            self.show_customer_check.setText("Show Customer Name on Receipt")
            self.btn_save.setText("Save Receipt Settings")

        self.btn_template_reset.setText("Reset Template")
        for button in (
            self.btn_browse_logo,
            self.btn_clear_logo,
            self.btn_browse_qr,
            self.btn_clear_qr,
            self.btn_template_reset,
            self.btn_save,
        ):
            button.update_theme()

    def update_theme(self, theme_name=None):
        colors = get_theme_colors(theme_name)
        border = colors.get("border", "#ced4da")
        panel = colors.get("card_bg", "#f8f9fa")
        text_secondary = colors.get("text_secondary", "#6c757d")
        for container in (self.logo_preview_container, self.qr_preview_container):
            container.setStyleSheet(f"""
                border: 1px solid {border};
                border-radius: 4px;
                background-color: {panel};
            """)
        for preview in (self.logo_preview, self.qr_preview):
            preview.setStyleSheet(f"background-color: transparent; color: {text_secondary};")
        for button in (
            self.btn_browse_logo,
            self.btn_clear_logo,
            self.btn_browse_qr,
            self.btn_clear_qr,
            self.btn_template_reset,
            self.btn_save,
        ):
            button.update_theme()

    def load_receipt_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        
        # Load shop info
        cursor.execute("SELECT value FROM settings WHERE key='shop_name'")
        row = cursor.fetchone()
        self.shop_name_edit.setText(row[0] if row else "")
        
        cursor.execute("SELECT value FROM settings WHERE key='shop_phone'")
        row = cursor.fetchone()
        self.shop_phone_edit.setText(row[0] if row else "")
        
        cursor.execute("SELECT value FROM settings WHERE key='shop_address'")
        row = cursor.fetchone()
        self.shop_address_edit.setPlainText(row[0] if row else "")
        
        # Load logo
        logo_path = resolve_receipt_image_path("logo")
        self.logo_path_edit.setText(logo_path)
        if logo_path and os.path.exists(logo_path):
            self.update_logo_preview(logo_path)
        else:
            self.reset_image_preview("logo")
        
        # Load QR Code
        qr_path = resolve_receipt_image_path("qr")
        self.qr_path_edit.setText(qr_path)
        if qr_path and os.path.exists(qr_path):
            self.update_qr_preview(qr_path)
        else:
            self.reset_image_preview("qr")
        
        # Load QR Name
        cursor.execute("SELECT value FROM settings WHERE key='shop_qr_name'")
        row = cursor.fetchone()
        self.qr_name_edit.setText(row[0] if row else "")

        # Load receipt settings
        cursor.execute("SELECT value FROM settings WHERE key='receipt_header'")
        row = cursor.fetchone()
        self.receipt_header.setPlainText(row[0] if row else "")
        
        cursor.execute("SELECT value FROM settings WHERE key='receipt_footer'")
        row = cursor.fetchone()
        self.receipt_footer.setPlainText(row[0] if row else "")
        
        cursor.execute("SELECT value FROM settings WHERE key='show_customer_name'")
        row = cursor.fetchone()
        self.show_customer_check.setChecked(row[0] == '1' if row else True)

        conn.close()
        self.load_template_settings()

    def save_settings(self):
        try:
            logo_path = self.logo_path_edit.text().strip()
            if logo_path and os.path.exists(logo_path):
                self.logo_path_edit.setText(save_receipt_image("logo", logo_path))
            qr_path = self.qr_path_edit.text().strip()
            if qr_path and os.path.exists(qr_path):
                self.qr_path_edit.setText(save_receipt_image("qr", qr_path))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save image to database: {e}")
            return

        conn = connect_db()
        cursor = conn.cursor()
        
        # Save business info
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("shop_name", self.shop_name_edit.text()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("shop_phone", self.shop_phone_edit.text()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("shop_address", self.shop_address_edit.toPlainText()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("shop_logo", self.logo_path_edit.text()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("shop_qr_code", self.qr_path_edit.text()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("shop_qr_name", self.qr_name_edit.text()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("receipt_header", self.receipt_header.toPlainText()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("receipt_footer", self.receipt_footer.toPlainText()))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("show_customer_name", '1' if self.show_customer_check.isChecked() else '0'))
        conn.commit()
        conn.close()
        save_receipt_template_settings(self.collect_template_settings())
        
        msg = "ပြေစာသတ်မှတ်ချက်များ သိမ်းဆည်းပြီးပါပြီ။" if lang.get_current() == "my" else "Receipt settings saved."
        QMessageBox.information(self, "Saved", msg)
        
        # Emit signal to notify that receipt settings have changed
        self.receipt_settings_changed.emit()

    def load_template_settings(self):
        settings = load_receipt_template_settings()
        for key, check in getattr(self, "template_checks", {}).items():
            check.blockSignals(True)
            check.setChecked(settings.get(key, DEFAULT_RECEIPT_TEMPLATE.get(key, "1")) == "1")
            check.blockSignals(False)

        self.thank_you_edit.blockSignals(True)
        self.thank_you_edit.setText(settings.get("receipt_thank_you_text", "THANK YOU"))
        self.thank_you_edit.blockSignals(False)

        self.line_width_spin.blockSignals(True)
        try:
            self.line_width_spin.setValue(int(settings.get("receipt_line_width", "32") or 32))
        except ValueError:
            self.line_width_spin.setValue(32)
        self.line_width_spin.blockSignals(False)
        self.update_template_preview()

    def collect_template_settings(self):
        settings = {}
        for key, check in getattr(self, "template_checks", {}).items():
            settings[key] = "1" if check.isChecked() else "0"
        settings["receipt_thank_you_text"] = self.thank_you_edit.text().strip() or "THANK YOU"
        settings["receipt_line_width"] = str(self.line_width_spin.value())
        return settings

    def reset_template_defaults(self):
        for key, check in getattr(self, "template_checks", {}).items():
            check.setChecked(DEFAULT_RECEIPT_TEMPLATE.get(key, "1") == "1")
        self.thank_you_edit.setText(DEFAULT_RECEIPT_TEMPLATE["receipt_thank_you_text"])
        self.line_width_spin.setValue(int(DEFAULT_RECEIPT_TEMPLATE["receipt_line_width"]))
        self.update_template_preview()

    def update_template_preview(self):
        if not hasattr(self, "template_preview"):
            return
        sale, items = sample_receipt_data()
        shop_settings = {
            "shop_name": self.shop_name_edit.text() or "ZAY POS",
            "shop_phone": self.shop_phone_edit.text(),
            "shop_address": self.shop_address_edit.toPlainText(),
            "shop_footer_message": "",
            "shop_logo": self.logo_path_edit.text(),
            "receipt_header": self.receipt_header.toPlainText(),
            "receipt_footer": self.receipt_footer.toPlainText(),
            "show_customer_name": "1" if self.show_customer_check.isChecked() else "0",
        }
        lines = build_receipt_text_lines(sale, items, self.collect_template_settings(), shop_settings)
        self.template_preview.setPlainText("\n".join(lines))

    def select_image(self, image_type):
        """Select image for logo or QR code"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            f"Select {image_type.title()}", 
            "", 
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            try:
                dest_path = save_receipt_image(image_type, file_path)
                if image_type == "logo":
                    self.logo_path_edit.setText(dest_path)
                    self.update_logo_preview(dest_path)
                    self.update_template_preview()
                else:  # qr
                    self.qr_path_edit.setText(dest_path)
                    self.update_qr_preview(dest_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not save image: {e}")

    def clear_image(self, image_type):
        """Clear logo or QR code selection and database image data."""
        try:
            clear_receipt_image(image_type, remove_file=True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not clear image: {e}")
            return

        if image_type == "logo":
            self.logo_path_edit.clear()
            self.update_template_preview()
        else:
            self.qr_path_edit.clear()
        self.reset_image_preview(image_type)

    def reset_image_preview(self, image_type):
        """Reset preview label to its empty state."""
        if image_type == "logo":
            self.logo_preview.setPixmap(QPixmap())
            self.logo_preview.setText("No logo")
        else:
            self.qr_preview.setPixmap(QPixmap())
            self.qr_preview.setText("No QR code")

    def update_logo_preview(self, image_path):
        """Update logo preview with fixed size and centered"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # Scale to fit inside 200x100 with aspect ratio preserved
            scaled = pixmap.scaled(
                200, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_preview.setPixmap(scaled)
            self.logo_preview.setText("")
        else:
            self.logo_preview.setText("Preview not available")
            self.logo_preview.setPixmap(QPixmap())

    def update_qr_preview(self, image_path):
        """Update QR preview with fixed size and centered"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # Scale to fit inside 200x100 with aspect ratio preserved
            scaled = pixmap.scaled(
                200, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.qr_preview.setPixmap(scaled)
            self.qr_preview.setText("")
        else:
            self.qr_preview.setText("Preview not available")
            self.qr_preview.setPixmap(QPixmap())
