# ui/inventory_page/stock_out_dialog.py
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.inventory_page.stock_out_ui import StockOutUI
from ui.inventory_page.stock_out_handlers import StockOutHandlers
from ui.themes.theme_manager import theme_manager, get_theme_colors
import os


class StockOutDialog(QDialog):
    """Main Stock Out Dialog - Entry point - Theme-aware with SVG Icons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI (Theme-aware)
        self.ui = StockOutUI()
        self.ui.setup_ui(self)
        
        # Setup handlers
        self.handlers = StockOutHandlers(self)
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
            self.setWindowTitle("စတော့ထွက်ရန်")
            self.btn_save.setText(" သိမ်းဆည်းမည်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
            self.product_search.setPlaceholderText("ပစ္စည်းအမည် / ဘားကုဒ် / SKU ဖြင့်ရှာရန်...")
            self.so_reason.setItemText(0, "ရောင်းချခြင်း")
            self.so_reason.setItemText(1, "ပျက်စီးခြင်း")
            self.so_reason.setItemText(2, "လွှဲပြောင်းခြင်း")
            self.so_reason.setItemText(3, "အခြား")
            
            index = self.so_location.findData("__NEW__")
            if index >= 0:
                self.so_location.setItemText(index, "+ နေရာအသစ်ထည့်")
        else:
            self.setWindowTitle("Stock Out")
            self.btn_save.setText(" Save Stock Out")
            self.btn_cancel.setText(" Cancel")
            self.product_search.setPlaceholderText("Search product by name, barcode or SKU...")
            self.so_reason.setItemText(0, "Sale")
            self.so_reason.setItemText(1, "Damage")
            self.so_reason.setItemText(2, "Transfer")
            self.so_reason.setItemText(3, "Other")
            
            index = self.so_location.findData("__NEW__")
            if index >= 0:
                self.so_location.setItemText(index, "+ Add New Location")
    
    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        QTimer.singleShot(100, self.focus_search)
        self._update_button_icons()
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.focusWidget() == self.product_search:
                self.handlers.on_search_entered()
                event.accept()
                return
        super().keyPressEvent(event)