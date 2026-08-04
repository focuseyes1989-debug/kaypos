# ui/inventory_page/stock_transfer_dialog.py
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.inventory_page.stock_transfer_ui import StockTransferUI
from ui.inventory_page.stock_transfer_handlers import StockTransferHandlers
from ui.themes.theme_manager import theme_manager, get_theme_colors
import os


class StockTransferDialog(QDialog):
    """Main Stock Transfer Dialog - Entry point - Theme-aware with SVG Icons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI (Theme-aware)
        self.ui = StockTransferUI()
        self.ui.setup_ui(self)
        
        # Setup handlers
        self.handlers = StockTransferHandlers(self)
        self.handlers.setup_signals()
        
        # Load data
        self.handlers.load_locations()
        self.handlers.load_products()
        
        # Connect theme change for dialog
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Retranslate UI
        self.retranslateUi()
        
        # Focus on search field when dialog opens
        QTimer.singleShot(100, self.focus_search)
    
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
        if hasattr(self, 'btn_transfer'):
            self.btn_transfer.set_icon("swap_horiz", size=(16, 16))
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
            self.setWindowTitle("စတော့လွှဲပြောင်းခြင်း")
            self.btn_transfer.setText(" လွှဲပြောင်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
            self.product_search.setPlaceholderText("ပစ္စည်းအမည် / ဘားကုဒ် / SKU ဖြင့်ရှာရန်...")
            self.st_reason.setPlaceholderText("လွှဲပြောင်းရသည့်အကြောင်းပြချက်...")
            self.st_notes.setPlaceholderText("မှတ်ချက်များ...")
        else:
            self.setWindowTitle("Stock Transfer")
            self.btn_transfer.setText(" Transfer Stock")
            self.btn_cancel.setText(" Cancel")
            self.product_search.setPlaceholderText("Search product by name, barcode or SKU...")
            self.st_reason.setPlaceholderText("Reason for transfer...")
            self.st_notes.setPlaceholderText("Additional notes...")
    
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