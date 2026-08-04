# ui/inventory_page/supplier_dialog.py
from PyQt6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QComboBox, QVBoxLayout, QHBoxLayout, QFrame, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from models.database import connect_db
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import os


class SupplierDialog(QDialog):
    """Supplier Information Dialog - Theme-aware with SVG Icons"""
    
    def __init__(self, supplier_id=None, supplier_data=None, parent=None):
        super().__init__(parent)
        self.supplier_id = supplier_id
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle("Supplier Information")
        self.resize(450, 580)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Apply initial theme
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(10)
        form_layout.setHorizontalSpacing(15)

        # Input fields with styling - Theme-aware
        self.name_edit = self._create_line_edit()
        self.contact_edit = self._create_line_edit()
        self.phone_edit = self._create_line_edit()
        self.email_edit = self._create_line_edit()
        self.address_edit = self._create_line_edit()
        self.company_edit = self._create_line_edit()
        self.tax_edit = self._create_line_edit()
        self.website_edit = self._create_line_edit()
        self.bank_edit = self._create_line_edit()
        
        self.payment_terms = self._create_combo_box(["Cash", "Credit 7 Days", "Credit 15 Days", "Credit 30 Days"])
        self.status_combo = self._create_combo_box(["Active", "Inactive"])

        # Labels - Theme-aware
        self.name_label = self._create_label("Supplier Name:")
        self.contact_label = self._create_label("Contact Person:")
        self.phone_label = self._create_label("Phone:")
        self.email_label = self._create_label("Email:")
        self.address_label = self._create_label("Address:")
        self.company_label = self._create_label("Company Name:")
        self.tax_label = self._create_label("Tax Number:")
        self.website_label = self._create_label("Website:")
        self.payment_label = self._create_label("Payment Terms:")
        self.bank_label = self._create_label("Bank Account:")
        self.status_label = self._create_label("Status:")

        form_layout.addRow(self.name_label, self.name_edit)
        form_layout.addRow(self.contact_label, self.contact_edit)
        form_layout.addRow(self.phone_label, self.phone_edit)
        form_layout.addRow(self.email_label, self.email_edit)
        form_layout.addRow(self.address_label, self.address_edit)
        form_layout.addRow(self.company_label, self.company_edit)
        form_layout.addRow(self.tax_label, self.tax_edit)
        form_layout.addRow(self.website_label, self.website_edit)
        form_layout.addRow(self.payment_label, self.payment_terms)
        form_layout.addRow(self.bank_label, self.bank_edit)
        form_layout.addRow(self.status_label, self.status_combo)
        
        layout.addLayout(form_layout)

        # Buttons - Using ModernButton with SVG icons
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style())
        
        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        btn_layout.addStretch()
        
        # ✅ Save button with SVG icon
        self.btn_ok = ModernButton("", ModernButton.PRIMARY)
        self.btn_ok.set_icon("save", size=(16, 16))
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)
        
        # ✅ Cancel button with SVG icon
        self.btn_cancel = ModernButton("", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(16, 16))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addWidget(button_frame)

        self.setLayout(layout)

        if supplier_data:
            self.name_edit.setText(supplier_data.get("name", ""))
            self.contact_edit.setText(supplier_data.get("contact_person", ""))
            self.phone_edit.setText(supplier_data.get("phone", ""))
            self.email_edit.setText(supplier_data.get("email", ""))
            self.address_edit.setText(supplier_data.get("address", ""))
            self.company_edit.setText(supplier_data.get("company_name", ""))
            self.tax_edit.setText(supplier_data.get("tax_number", ""))
            self.website_edit.setText(supplier_data.get("website", ""))
            idx = self.payment_terms.findText(supplier_data.get("payment_terms", "Cash"))
            if idx >= 0:
                self.payment_terms.setCurrentIndex(idx)
            self.bank_edit.setText(supplier_data.get("bank_account", ""))
            idx2 = self.status_combo.findText(supplier_data.get("status", "Active"))
            if idx2 >= 0:
                self.status_combo.setCurrentIndex(idx2)

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
        if hasattr(self, 'btn_ok'):
            self.btn_ok.set_icon("save", size=(16, 16))
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.set_icon("close", size=(16, 16))

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style())
        
        # Update all labels
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update all line edits
        for child in self.findChildren(QLineEdit):
            child.setStyleSheet(self._get_line_edit_style())
        
        # Update combo boxes
        for child in self.findChildren(QComboBox):
            child.setStyleSheet(self._get_combo_box_style())
        
        # Update button icons
        self._update_button_icons()
    
    def _get_button_frame_style(self):
        colors = get_theme_colors()
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _get_label_style(self):
        colors = get_theme_colors()
        return f"font-weight: 600; color: {colors['text']}; font-size: 10pt;"
    
    def _get_line_edit_style(self):
        colors = get_theme_colors()
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """
    
    def _get_combo_box_style(self):
        colors = get_theme_colors()
        return f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 36px;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors['text_secondary']};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """
    
    def _create_line_edit(self, placeholder=""):
        edit = QLineEdit()
        if placeholder:
            edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(self._get_line_edit_style())
        return edit
    
    def _create_combo_box(self, items):
        combo = QComboBox()
        combo.addItems(items)
        combo.setStyleSheet(self._get_combo_box_style())
        return combo
    
    def _create_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(self._get_label_style())
        return label

    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"

    def retranslateUi(self):
        lang = self.get_lang()
        colors = get_theme_colors()
        
        # Update button icons
        self._update_button_icons()
        
        if lang == "my":
            self.setWindowTitle("ပေးသွင်းသူအချက်အလက်" if self.supplier_id is None else "ပေးသွင်းသူပြင်ဆင်ရန်")
            
            self.name_label.setText("ပေးသွင်းသူအမည်:")
            self.contact_label.setText("ဆက်သွယ်ရမည့်သူ:")
            self.phone_label.setText("ဖုန်း:")
            self.email_label.setText("အီးမေး:")
            self.address_label.setText("လိပ်စာ:")
            self.company_label.setText("ကုမ္ပဏီအမည်:")
            self.tax_label.setText("အခွန်အမှတ်:")
            self.website_label.setText("ဝက်ဘ်ဆိုက်:")
            self.payment_label.setText("ငွေပေးချေမှုအခြေအနေ:")
            self.bank_label.setText("ဘဏ်အကောင့်:")
            self.status_label.setText("အခြေအနေ:")
            
            self.payment_terms.setItemText(0, "ငွေသား")
            self.payment_terms.setItemText(1, "ရက် ၇ အတွင်းငွေချေး")
            self.payment_terms.setItemText(2, "ရက် ၁၅ အတွင်းငွေချေး")
            self.payment_terms.setItemText(3, "ရက် ၃၀ အတွင်းငွေချေး")
            self.status_combo.setItemText(0, "သက်ဝင်")
            self.status_combo.setItemText(1, "မသက်ဝင်")
            self.btn_ok.setText(" သိမ်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့")
        else:
            self.setWindowTitle("Supplier Information" if self.supplier_id is None else "Edit Supplier")
            
            self.name_label.setText("Supplier Name:")
            self.contact_label.setText("Contact Person:")
            self.phone_label.setText("Phone:")
            self.email_label.setText("Email:")
            self.address_label.setText("Address:")
            self.company_label.setText("Company Name:")
            self.tax_label.setText("Tax Number:")
            self.website_label.setText("Website:")
            self.payment_label.setText("Payment Terms:")
            self.bank_label.setText("Bank Account:")
            self.status_label.setText("Status:")
            
            self.payment_terms.setItemText(0, "Cash")
            self.payment_terms.setItemText(1, "Credit 7 Days")
            self.payment_terms.setItemText(2, "Credit 15 Days")
            self.payment_terms.setItemText(3, "Credit 30 Days")
            self.status_combo.setItemText(0, "Active")
            self.status_combo.setItemText(1, "Inactive")
            self.btn_ok.setText(" Save")
            self.btn_cancel.setText(" Cancel")
        
        # Update label styles after language change
        for child in self.findChildren(QLabel):
            child.setStyleSheet(self._get_label_style())
        
        # Update input styles
        for child in self.findChildren(QLineEdit):
            child.setStyleSheet(self._get_line_edit_style())
        
        for child in self.findChildren(QComboBox):
            child.setStyleSheet(self._get_combo_box_style())
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style())
        
        # Apply theme after language change
        self._apply_theme()

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "contact_person": self.contact_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "address": self.address_edit.text().strip(),
            "company_name": self.company_edit.text().strip(),
            "tax_number": self.tax_edit.text().strip(),
            "website": self.website_edit.text().strip(),
            "payment_terms": self.payment_terms.currentText(),
            "bank_account": self.bank_edit.text().strip(),
            "status": self.status_combo.currentText()
        }
    
    def showEvent(self, event):
        """Update button icons when dialog becomes visible"""
        self._update_button_icons()
        super().showEvent(event)