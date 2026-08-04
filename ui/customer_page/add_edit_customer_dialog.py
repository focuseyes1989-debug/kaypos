# ui/customer_page/add_edit_customer_dialog.py
"""
Add/Edit Customer Dialog - Product Form Dialog ပုံစံအတိုင်း
✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
✅ SVG Icons ကိုအသုံးပြုထားပါတယ်
"""

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QTextEdit,
    QDialogButtonBox, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from utils.currency import get_currency_symbol
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from utils.language import lang
import os


class AddEditCustomerDialog(QDialog):
    """Add/Edit Customer Dialog - Theme-aware - Product Form Dialog ပုံစံ"""

    def __init__(self, customer_data=None, language="en", parent=None):
        super().__init__(parent)
        self.customer_data = customer_data
        self.language = language
        self._is_dark = is_dark_theme()
        self.setMinimumWidth(500)
        self.setMaximumWidth(600)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))

        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        # Setup UI
        self.setup_ui()

        # Load data if editing
        if customer_data:
            self.load_data(customer_data)

        # Retranslate UI
        self.retranslateUi()

        # Focus on name field when dialog opens
        QTimer.singleShot(100, self.focus_name)

    def _on_theme_changed(self, theme_name):
        """Handle theme change - update dialog style"""
        self._is_dark = is_dark_theme()
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        self._apply_theme()

    def focus_name(self):
        """Focus on name field"""
        if hasattr(self, 'name_edit'):
            self.name_edit.setFocus()
            self.name_edit.selectAll()

    def _load_svg_icon(self, icon_name, size=(20, 20)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                from PyQt6.QtGui import QPixmap
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
                from PyQt6.QtGui import QPixmap
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

    def setup_ui(self):
        """Setup the UI with theme-aware styling"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()

        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with SVG icon
        header_layout = QHBoxLayout()
        
        # Icon using SVG
        icon_label = QLabel()
        icon = self._load_svg_icon("person", size=(24, 24))
        if icon and not icon.isNull():
            icon_label.setPixmap(icon.pixmap(24, 24))
            icon_label.setStyleSheet("background: transparent; border: none;")
        else:
            icon_label.setText("👤")
            icon_label.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        header_layout.addWidget(icon_label)
        
        self.header_label = QLabel("Customer")
        self.header_label.setObjectName("headerTitle")
        self.header_label.setStyleSheet(f"""
            font-size: 16pt; 
            font-weight: 700; 
            color: {colors['text']};
        """)
        header_layout.addWidget(self.header_label)

        header_layout.addStretch()

        if self.customer_data:
            badge = QLabel(f"ID: #{self.customer_data.get('id', '')}")
            badge.setObjectName("idBadge")
            badge.setStyleSheet("""
                background: #5865f2;
                color: white;
                padding: 4px 14px;
                border-radius: 12px;
                font-size: 10pt;
                font-weight: 600;
            """)
            header_layout.addWidget(badge)

        main_layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {colors['border']}; max-height: 1px;")
        main_layout.addWidget(separator)

        # Form layout
        form_widget = QWidget()
        form_widget.setStyleSheet(f"background: transparent;")
        form_layout = QFormLayout(form_widget)
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(15)

        # Labels with theme-aware styling
        self.lbl_name = self._create_label()
        self.name_edit = self._create_line_edit()
        self.name_edit.textChanged.connect(self.on_name_changed)

        self.lbl_phone = self._create_label()
        self.phone_edit = self._create_line_edit()

        self.lbl_email = self._create_label()
        self.email_edit = self._create_line_edit()

        self.lbl_address = self._create_label()
        self.address_edit = self._create_line_edit()

        self.lbl_credit_limit = self._create_label()
        self.credit_limit_edit = self._create_double_spinbox()

        self.lbl_remarks = self._create_label()
        self.remarks_edit = self._create_text_edit()

        form_layout.addRow(self.lbl_name, self.name_edit)
        form_layout.addRow(self.lbl_phone, self.phone_edit)
        form_layout.addRow(self.lbl_email, self.email_edit)
        form_layout.addRow(self.lbl_address, self.address_edit)
        form_layout.addRow(self.lbl_credit_limit, self.credit_limit_edit)
        form_layout.addRow(self.lbl_remarks, self.remarks_edit)

        # Add info label at bottom
        self.info_label = QLabel("📌 Fill in all required fields (*)")
        self.info_label.setStyleSheet(f"""
            color: {colors['text_secondary']};
            font-size: 9pt;
            padding: 4px 0;
            font-style: italic;
        """)
        form_layout.addRow("", self.info_label)

        main_layout.addWidget(form_widget)

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet(f"background-color: {colors['border']}; max-height: 1px;")
        main_layout.addWidget(separator2)

        # Buttons - Using ModernButton with SVG icons
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))

        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 10, 15, 10)

        # ✅ Cancel button with SVG icon
        self.btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_cancel.setMinimumHeight(34)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()

        # ✅ Save button with SVG icon
        self.btn_ok = ModernButton(" Save", ModernButton.PRIMARY)
        self.btn_ok.set_icon("save", size=(16, 16))
        self.btn_ok.setMinimumHeight(34)
        self.btn_ok.setMinimumWidth(120)
        self.btn_ok.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)

        main_layout.addWidget(button_frame)

        self.setLayout(main_layout)

        # Apply initial theme
        self._apply_theme()

    def load_data(self, customer_data):
        """Load customer data into fields"""
        self.name_edit.setText(customer_data.get("name", ""))
        self.phone_edit.setText(customer_data.get("phone", ""))
        self.email_edit.setText(customer_data.get("email", ""))
        self.address_edit.setText(customer_data.get("address", ""))
        self.credit_limit_edit.setValue(customer_data.get("credit_limit", 0))
        self.remarks_edit.setPlainText(customer_data.get("remarks", ""))

    def on_name_changed(self, text):
        """Handle name change - update badge if needed"""
        pass

    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()

        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)

        # Update labels
        for child in self.findChildren(QLabel):
            if child.objectName() != "headerTitle" and child.objectName() != "idBadge":
                child.setStyleSheet(self._get_label_style())

        # Update line edits
        for child in self.findChildren(QLineEdit):
            child.setStyleSheet(self._get_line_edit_style())

        # Update spin box
        if hasattr(self, 'credit_limit_edit'):
            self.credit_limit_edit.setStyleSheet(self._get_spinbox_style())

        # Update text edit
        if hasattr(self, 'remarks_edit'):
            self.remarks_edit.setStyleSheet(self._get_text_edit_style())

        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))

        # Update info label
        if hasattr(self, 'info_label'):
            self.info_label.setStyleSheet(f"""
                color: {colors['text_secondary']};
                font-size: 9pt;
                padding: 4px 0;
                font-style: italic;
            """)

        # Update button icons
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_ok.set_icon("save", size=(16, 16))

    def _get_label_style(self):
        colors = get_theme_colors()
        return f"""
            font-weight: 600; 
            color: {colors['text']}; 
            font-size: 10pt;
            min-width: 100px;
        """

    def _get_line_edit_style(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        return f"""
            QLineEdit {{
                padding: 9px 14px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
                border-width: 2px;
            }}
            QLineEdit::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
        """

    def _get_spinbox_style(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        return f"""
            QDoubleSpinBox {{
                padding: 9px 14px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 34px;
                max-height: 34px;
            }}
            QDoubleSpinBox:focus {{
                border-color: #5865f2;
                border-width: 2px;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 20px;
                height: 14px;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 3px;
            }}
            QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
                background-color: #5865f2;
                border-radius: 3px;
            }}
        """

    def _get_text_edit_style(self):
        colors = get_theme_colors()
        return f"""
            QTextEdit {{
                padding: 9px 14px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
                border-width: 2px;
            }}
            QTextEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """

    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 10px;
                padding: 5px;
            }}
        """

    def _create_label(self):
        label = QLabel()
        label.setStyleSheet(self._get_label_style())
        return label

    def _create_line_edit(self):
        edit = QLineEdit()
        edit.setStyleSheet(self._get_line_edit_style())
        return edit

    def _create_double_spinbox(self):
        spin = QDoubleSpinBox()
        spin.setRange(0, 999999999)
        spin.setDecimals(0)
        symbol = get_currency_symbol()
        spin.setPrefix(f"{symbol} ")
        spin.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        spin.setStyleSheet(self._get_spinbox_style())
        return spin

    def _create_text_edit(self):
        edit = QTextEdit()
        edit.setMaximumHeight(80)
        edit.setStyleSheet(self._get_text_edit_style())
        return edit

    def retranslateUi(self):
        """Retranslate UI - Product Form Dialog ပုံစံ"""
        colors = get_theme_colors()
        is_edit = self.customer_data is not None

        # Get current language
        try:
            lang_code = lang.get_current()
        except:
            lang_code = self.language

        if lang_code == "my":
            self.setWindowTitle("ဝယ်ယူသူပြင်ဆင်ရန်" if is_edit else "ဝယ်ယူသူအသစ်ထည့်ရန်")
            self.lbl_name.setText("👤 အမည် *")
            self.lbl_phone.setText("📞 ဖုန်း")
            self.lbl_email.setText("📧 အီးမေး")
            self.lbl_address.setText("📍 လိပ်စာ")
            self.lbl_credit_limit.setText("💰 ခရက်ဒစ်ကန့်သတ်ချက်")
            self.lbl_remarks.setText("📝 မှတ်ချက်")
            self.btn_ok.setText(" သိမ်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
            self.info_label.setText("📌 * ပါသောနေရာများကို ဖြည့်သွင်းရန် လိုအပ်ပါသည်။")

            # Placeholders
            self.name_edit.setPlaceholderText("ဝယ်ယူသူအမည် ထည့်ပါ...")
            self.phone_edit.setPlaceholderText("ဖုန်းနံပါတ် ထည့်ပါ...")
            self.email_edit.setPlaceholderText("အီးမေးလ် ထည့်ပါ...")
            self.address_edit.setPlaceholderText("လိပ်စာ ထည့်ပါ...")
            self.remarks_edit.setPlaceholderText("မှတ်ချက်များ ထည့်ပါ...")

        else:
            self.setWindowTitle("Edit Customer" if is_edit else "Add Customer")
            self.lbl_name.setText("👤 Name *")
            self.lbl_phone.setText("📞 Phone")
            self.lbl_email.setText("📧 Email")
            self.lbl_address.setText("📍 Address")
            self.lbl_credit_limit.setText("💰 Credit Limit")
            self.lbl_remarks.setText("📝 Remarks")
            self.btn_ok.setText(" Save")
            self.btn_cancel.setText(" Cancel")
            self.info_label.setText("📌 * Required fields must be filled.")

            # Placeholders
            self.name_edit.setPlaceholderText("Enter customer name...")
            self.phone_edit.setPlaceholderText("Enter phone number...")
            self.email_edit.setPlaceholderText("Enter email address...")
            self.address_edit.setPlaceholderText("Enter address...")
            self.remarks_edit.setPlaceholderText("Enter remarks...")

        # Update button icons after language change
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_ok.set_icon("save", size=(16, 16))

        # Update header text
        if hasattr(self, 'header_label'):
            if lang_code == "my":
                self.header_label.setText("ဝယ်ယူသူ" if not is_edit else "ဝယ်ယူသူပြင်ဆင်ရန်")
            else:
                self.header_label.setText("Customer" if not is_edit else "Edit Customer")

        # Update label styles after language change
        for child in self.findChildren(QLabel):
            if child.objectName() != "headerTitle" and child.objectName() != "idBadge":
                child.setStyleSheet(self._get_label_style())

        # Update input styles
        for child in self.findChildren(QLineEdit):
            child.setStyleSheet(self._get_line_edit_style())

        if hasattr(self, 'credit_limit_edit'):
            self.credit_limit_edit.setStyleSheet(self._get_spinbox_style())

        if hasattr(self, 'remarks_edit'):
            self.remarks_edit.setStyleSheet(self._get_text_edit_style())

        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))

        # Update info label
        if hasattr(self, 'info_label'):
            self.info_label.setStyleSheet(f"""
                color: {colors['text_secondary']};
                font-size: 9pt;
                padding: 4px 0;
                font-style: italic;
            """)

        # Update header title style
        if hasattr(self, 'header_label'):
            self.header_label.setStyleSheet(f"""
                font-size: 16pt; 
                font-weight: 700; 
                color: {colors['text']};
            """)

    def accept(self):
        """Validate and accept"""
        # Validate name
        name = self.name_edit.text().strip()
        if not name:
            lang_code = self.language
            try:
                lang_code = lang.get_current()
            except:
                pass

            if lang_code == "my":
                QMessageBox.warning(self, "အမှား", "ကျေးဇူးပြုပြီး ဝယ်ယူသူအမည် ထည့်ပါ။")
            else:
                QMessageBox.warning(self, "Error", "Please enter customer name.")
            self.name_edit.setFocus()
            return

        super().accept()

    def get_data(self):
        """Get customer data from form"""
        return {
            "name": self.name_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "address": self.address_edit.text().strip(),
            "credit_limit": self.credit_limit_edit.value(),
            "remarks": self.remarks_edit.toPlainText().strip()
        }

    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        QTimer.singleShot(100, self.focus_name)

    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # If focus is on name_edit, move to next field
            if self.focusWidget() == self.name_edit:
                self.phone_edit.setFocus()
                event.accept()
                return
            elif self.focusWidget() == self.phone_edit:
                self.email_edit.setFocus()
                event.accept()
                return
            elif self.focusWidget() == self.email_edit:
                self.address_edit.setFocus()
                event.accept()
                return
            elif self.focusWidget() == self.address_edit:
                self.credit_limit_edit.setFocus()
                event.accept()
                return
            elif self.focusWidget() == self.credit_limit_edit:
                self.remarks_edit.setFocus()
                event.accept()
                return
            elif self.focusWidget() == self.remarks_edit:
                self.accept()
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle close event"""
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        event.accept()