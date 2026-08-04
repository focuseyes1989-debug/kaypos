# ui/products_page/product_form_dialog.py
from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.products_page.product_form_ui import ProductFormUI
from ui.products_page.product_form_handlers import ProductFormHandlers
from ui.themes.theme_manager import theme_manager, get_theme_colors
import os


class ProductFormDialog(QDialog):
    """Main Product Form Dialog - Entry point - Theme-aware with SVG Icons"""
    
    def __init__(self, product_id=None, parent=None):
        super().__init__(parent)
        
        self.product_id = product_id
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI (Theme-aware)
        self.ui = ProductFormUI()
        self.ui.setup_ui(self, product_id)
        
        # Setup handlers
        self.handlers = ProductFormHandlers(self)
        self.handlers.setup_signals()
        
        # Load data
        self.handlers.load_categories()
        if self.product_id:
            self.handlers.load_product_data()
        
        # Connect theme change for dialog
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Retranslate UI
        self.retranslateUi()
        
        # Focus on name field when dialog opens
        QTimer.singleShot(100, self.focus_name)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change - update dialog style"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        # Update button icons
        self._update_button_icons()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        if hasattr(self, 'btn_save'):
            self.btn_save.set_icon("save", size=(16, 16))
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.set_icon("close", size=(16, 16))
        if hasattr(self, 'btn_speech'):
            self.btn_speech.set_icon("speech_to_text", size=(16, 16))
        if hasattr(self, 'btn_speech_desc'):
            self.btn_speech_desc.set_icon("speech_to_text", size=(16, 16))
        if hasattr(self, 'btn_browse'):
            self.btn_browse.set_icon("folder_open", size=(16, 16))
        if hasattr(self, 'btn_manage_variants'):
            self.btn_manage_variants.set_icon("inventory_2", size=(16, 16))
    
    def focus_name(self):
        """Focus on name field"""
        self.name_input.setFocus()
        self.name_input.selectAll()
    
    def show_message(self, title, message):
        """Show a warning message"""
        QMessageBox.warning(self, title, message)
    
    def retranslateUi(self):
        """Retranslate UI for language change"""
        is_edit = self.product_id is not None
        lang_code = self.handlers.get_lang()
        colors = get_theme_colors()
        
        # Update button icons
        self._update_button_icons()
        
        if lang_code == "my":
            self.setWindowTitle("ပစ္စည်းအသစ်ထည့်ရန်" if not is_edit else "ပစ္စည်းပြင်ရန်")
            self.label_name.setText("ပစ္စည်းအမည်")
            self.label_category.setText("အမျိုးအစား")
            self.label_barcode.setText("ဘားကုဒ်")
            self.label_description.setText("ဖော်ပြချက်")
            self.label_sold_by.setText("ရောင်းချပုံ")
            self.label_price.setText("ဈေးနှုန်း")
            self.label_low_stock.setText("အနိမ့်ဆုံးစတော့သတိပေး")
            self.label_image.setText("ပစ္စည်းပုံ")
            self.btn_browse.setText(" ပုံရွေးရန်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
            self.btn_save.setText(" သိမ်းဆည်းမည်")
            self.btn_speech_desc.setText(" အသံဖြင့်ရိုက်ရန်")
            self.sold_by_combo.setItemText(0, "အလုံး")
            self.sold_by_combo.setItemText(1, "ဝန်ဆောင်မှု")
            self.sold_by_combo.setItemText(2, "အမျိုးကွဲများ")
            self.language_label.setText("အသံဘာသာစကား:")
            self.name_input.setPlaceholderText("ပစ္စည်းအမည်ထည့်ပါ...")
            self.barcode_input.setPlaceholderText("ဘားကုဒ်စကင်ဖတ်ပါ...")
            self.info_label.setText("📌 ပစ္စည်းစတော့အကြောင်း မှတ်ချက်")
        else:
            self.setWindowTitle("Add Product" if not is_edit else "Edit Product")
            self.label_name.setText("Product Name")
            self.label_category.setText("Category")
            self.label_barcode.setText("Barcode")
            self.label_description.setText("Description")
            self.label_sold_by.setText("Sold By")
            self.label_price.setText("Price")
            self.label_low_stock.setText("Low Stock Alert")
            self.label_image.setText("Product Image")
            self.btn_browse.setText(" Browse Image")
            self.btn_cancel.setText(" Cancel")
            self.btn_save.setText(" Save Product")
            self.btn_speech_desc.setText(" Speak Description")
            self.sold_by_combo.setItemText(0, "Each")
            self.sold_by_combo.setItemText(1, "Service")
            self.sold_by_combo.setItemText(2, "Variants")
            self.language_label.setText("Speech Language:")
            self.name_input.setPlaceholderText("Enter product name...")
            self.barcode_input.setPlaceholderText("Scan barcode...")
            self.info_label.setText("📌 Stock notes and information")
        
        # Update speech tooltips
        current_lang = self.language_combo.currentData()
        self.handlers.update_speech_tooltips(current_lang)
        
        # Update sold by info
        self.handlers.toggle_service_fields()
        
        # Apply theme after language change
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme-aware styles to dialog"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        self._update_button_icons()
    
    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        QTimer.singleShot(100, self.focus_name)
        self._update_button_icons()
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.focusWidget() == self.barcode_input:
                self.handlers.on_barcode_entered()
                event.accept()
                return
        super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        """Filter events for barcode input field"""
        if obj == self.barcode_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                return False
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return True
        return super().eventFilter(obj, event)
