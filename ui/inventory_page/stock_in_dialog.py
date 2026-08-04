# ui/inventory_page/stock_in_dialog.py
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.inventory_page.stock_in_ui import StockInUI
from ui.inventory_page.stock_in_handlers import StockInHandlers
from ui.themes.theme_manager import theme_manager, get_theme_colors
import os


class StockInDialog(QDialog):
    """Main Stock In Dialog - Entry point - Theme-aware with SVG Icons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI (Theme-aware)
        self.ui = StockInUI()
        self.ui.setup_ui(self)
        
        # Setup handlers
        self.handlers = StockInHandlers(self)
        self.handlers.setup_signals()
        
        # Load data
        self.handlers.load_dropdowns()
        self.handlers.load_locations()
        
        # Connect theme change for dialog
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Retranslate UI
        self.retranslateUi()
        
        # Focus on search field when dialog opens
        QTimer.singleShot(100, self.focus_search)
        
        # Initial total update
        self.handlers.update_total()
    
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
    
    def set_product(self, product_id, product_name=None):
        """Set the product to be pre-selected in the dialog"""
        self.handlers.set_product(product_id, product_name)
    
    def focus_search(self):
        """Focus on search field"""
        self.product_search.setFocus()
        self.product_search.selectAll()
    
    def retranslateUi(self):
        """Retranslate UI for language change"""
        lang = self.handlers.get_lang()
        
        # Update button icons
        self._update_button_icons()
        
        if lang == "my":
            self.setWindowTitle("စတော့ဝင်ရန်")
            self.btn_save.setText(" သိမ်းဆည်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
            self.product_search.setPlaceholderText("ပစ္စည်းအမည် / ဘားကုဒ် / SKU ရိုက်ထည့်ပါ...")
            self.si_payment_status.setItemText(0, "ပေးပြီး")
            self.si_payment_status.setItemText(1, "မပေးရသေး")
            self.si_payment_status.setItemText(2, "တစ်ပိုင်းပေးပြီး")
            
            index = self.si_location.findData("__NEW__")
            if index >= 0:
                self.si_location.setItemText(index, "+ နေရာအသစ်ထည့်")
                
            self.si_batch_no.setPlaceholderText("BATCH-YYYYMMDDXXXX")
            self.si_po_no.setPlaceholderText("PO-YYYYMMDDXXXX")
            
            self.product_details_label.setText("ပစ္စည်းအသေးစိတ်ကြည့်ရန် ရွေးချယ်ပါ")
            self.image_preview.setText("📷 ပုံမရှိပါ\n\nပစ္စည်းတစ်ခုရွေးချယ်ပါ")
        else:
            self.setWindowTitle("Stock In")
            self.btn_save.setText(" Save Stock In")
            self.btn_cancel.setText(" Cancel")
            self.product_search.setPlaceholderText("Type product name, barcode or SKU...")
            self.si_payment_status.setItemText(0, "Paid")
            self.si_payment_status.setItemText(1, "Unpaid")
            self.si_payment_status.setItemText(2, "Partial")
            
            index = self.si_location.findData("__NEW__")
            if index >= 0:
                self.si_location.setItemText(index, "+ Add New Location")
                
            self.si_batch_no.setPlaceholderText("BATCH-YYYYMMDDXXXX")
            self.si_po_no.setPlaceholderText("PO-YYYYMMDDXXXX")
    
    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        QTimer.singleShot(100, self.focus_search)
        self._update_button_icons()
    
    def resizeEvent(self, event):
        """Handle resize event to update image preview"""
        super().resizeEvent(event)
        self.handlers.update_product_info()
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.focusWidget() == self.product_search:
                self.handlers.on_search_entered()
                event.accept()
                return
        super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        """Filter events for search input field"""
        if obj == self.product_search and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                return False
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return True
        return super().eventFilter(obj, event)