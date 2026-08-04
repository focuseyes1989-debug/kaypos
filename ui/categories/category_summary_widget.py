# ui/categories/category_summary_widget.py

"""
Category Summary Widget - Displays category statistics in summary cards
✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
✅ SVG Icons - Assets/icons ထဲက SVG icons များကို သုံးမယ်
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.categories.category_service import CategoryService
from utils.language import lang

from loguru import logger
import os


class CategorySummaryWidget(QWidget):
    """Widget that displays category statistics using SummaryCardWidget"""
    
    card_clicked = pyqtSignal(str)  # Emits card type ('total', 'active', etc.)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.service = CategoryService()
        self.cards = {}
        
        self.setup_ui()
        self.load_statistics()
        
        # Language support
        lang.language_changed.connect(self.retranslateUi)
    
    def setup_ui(self):
        """Setup the summary cards layout"""
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Define card configurations
        # (key, title, icon_name, color, gradient_colors)
        card_configs = [
            ('total', 'Total', 'folder.svg', '#3498db', ['#3498db', '#2980b9']),
            ('active', 'Active', 'check_circle.svg', '#2ecc71', ['#2ecc71', '#27ae60']),
            ('inactive', 'Inactive', 'cancel.svg', '#e74c3c', ['#e74c3c', '#c0392b']),
            ('hidden', 'Hidden', 'visibility_off.svg', '#95a5a6', ['#95a5a6', '#7f8c8d']),
            ('products', 'Products', 'inventory.svg', '#f39c12', ['#f39c12', '#e67e22'])
        ]
        
        for key, title, icon_name, color, gradients in card_configs:
            # ✅ Create card with icon
            card = SummaryCardWidget(
                title=title,
                value="0",
                icon=icon_name,
                color=color,
                gradient_colors=gradients,
                icon_is_svg=True,  # Tell card it's an SVG
                parent=self
            )
            
            # Store reference to card
            self.cards[key] = card
            
            # Connect click signal
            card.clicked.connect(lambda k=key: self.card_clicked.emit(k))
            
            layout.addWidget(card, 1)
        
        self.setLayout(layout)
    
    def load_statistics(self):
        """Load and display category statistics"""
        try:
            stats = self.service.get_statistics()
            
            self.cards['total'].set_value(str(stats['total']))
            self.cards['active'].set_value(str(stats['active']))
            self.cards['inactive'].set_value(str(stats['inactive']))
            self.cards['hidden'].set_value(str(stats['hidden']))
            self.cards['products'].set_value(str(stats['total_products']))
            
        except Exception as e:
            logger.error(f"Failed to load category statistics: {e}")
    
    def refresh(self):
        """Refresh statistics"""
        self.load_statistics()
    
    def retranslateUi(self):
        """Retranslate UI"""
        is_my = lang.get_current() == "my"
        
        translations = {
            'total': ('Total', 'စုစုပေါင်း'),
            'active': ('Active', 'အသက်ဝင်'),
            'inactive': ('Inactive', 'မလှုပ်ရှား'),
            'hidden': ('Hidden', 'ဝှက်ထား'),
            'products': ('Products', 'ပစ္စည်းများ')
        }
        
        for key, (en, my) in translations.items():
            if key in self.cards:
                self.cards[key].set_title(my if is_my else en)