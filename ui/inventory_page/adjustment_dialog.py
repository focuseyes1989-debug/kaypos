# ui/inventory_page/adjustment_dialog.py
from typing import Any
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.inventory_page.adjustment_ui import AdjustmentUI
from ui.inventory_page.adjustment_handlers import AdjustmentHandlers
from ui.themes.theme_manager import theme_manager, get_theme_colors
import os


class AdjustmentDialog(QDialog):
    """Main Adjustment Dialog - Entry point - Theme-aware with SVG Icons"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.btn_save: Any = None
        self.btn_cancel: Any = None
        self.product_search: Any = None
        self.adj_product: Any = None
        self.adj_new_qty: Any = None
        self.adj_old_qty: Any = None
        self.adj_diff: Any = None
        self.adj_location_only: Any = None
        self.adj_type: Any = None
        self.adj_reason: Any = None
        self.adj_notes: Any = None
        self.adj_staff: Any = None
        self.adj_date: Any = None
        self.adj_location: Any = None
        self.adj_no: Any = None
        self.image_preview: Any = None
        self.product_info_label: Any = None
        self.product_details_label: Any = None
        self.current_stock_label: Any = None
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI (Theme-aware)
        self.ui = AdjustmentUI()
        self.ui.setup_ui(self)
        
        # Setup handlers
        self.handlers = AdjustmentHandlers(self)
        self.handlers.setup_signals()
        
        # Load data
        self.handlers.load_products()
        self.handlers.load_locations()
        
        # Connect theme change for dialog
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Retranslate UI
        self.retranslateUi()
        
        # Focus on search field when dialog opens
        QTimer.singleShot(100, self.focus_search)
        
        # Initial diff update
        self.handlers.update_diff()
    
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
            self.setWindowTitle("စတော့ပြင်ဆင်ချက်")
            self.btn_save.setText(" ပြင်ဆင်မည်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
            self.product_search.setPlaceholderText("ပစ္စည်းအမည် / ဘားကုဒ် / SKU ရိုက်ထည့်ပါ...")
            self.adj_type.setItemText(0, "ပေါင်းထည့်")
            self.adj_type.setItemText(1, "ဖယ်ရှား")
            
            index = self.adj_location.findData("__NEW__")
            if index >= 0:
                self.adj_location.setItemText(index, "+ နေရာအသစ်ထည့်")
            
            self.adj_reason.setPlaceholderText("ပျက်စီးမှု / ရေတွက်မှားမှု / ပြန်အမ်း")
            self.adj_notes.setPlaceholderText("မှတ်ချက်များ...")
        else:
            self.setWindowTitle("Stock Adjustment")
            self.btn_save.setText(" Apply Adjustment")
            self.btn_cancel.setText(" Cancel")
            self.product_search.setPlaceholderText("Type product name, barcode or SKU...")
            self.adj_type.setItemText(0, "Add")
            self.adj_type.setItemText(1, "Remove")
            
            index = self.adj_location.findData("__NEW__")
            if index >= 0:
                self.adj_location.setItemText(index, "+ Add New Location")
            
            self.adj_reason.setPlaceholderText("Damage / Counting Error / Return")
            self.adj_notes.setPlaceholderText("Additional notes...")
    
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