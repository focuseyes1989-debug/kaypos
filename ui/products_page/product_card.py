# ui/products_page/product_card.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import pyqtSignal, QDate
from PyQt6.QtGui import QPixmap
from utils.currency import get_currency_symbol, format_money
from models.database import connect_db
from ui.widgets.summary_card_widget import SummaryCardWidget
from loguru import logger
import os


class ProductCards(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
        self.card_widgets = {}
        self.setup_cards()

    def setup_cards(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # ✅ Card definitions with SVG icon names
        card_definitions = [
            ("Total Cost", "total_cost", "attach_money", "#2ecc71"),
            ("Out of Stock", "out_stock", "warning", "#e74c3c"),
            ("Low Stock", "low_stock", "inventory_2", "#f39c12"),
            ("Expiring ≤7 Days", "expiring_soon", "clock", "#3498db"),
            ("Expired", "expired", "close", "#95a5a6")
        ]

        for title, key, icon_name, color in card_definitions:
            card = SummaryCardWidget(
                title=title,
                value="0",
                icon=icon_name,
                color=color,
                icon_is_svg=True  # ✅ Use SVG icon
            )
            # Set fixed height for consistency
            card.card.setFixedHeight(85)
            card.card.setMinimumWidth(130)
            
            # Store reference
            self.card_widgets[key] = card
            self.cards[key] = card.value_label
            
            # Connect click event
            card.clicked.connect(lambda k=key: self.on_card_clicked(k))
            
            layout.addWidget(card, 1)

        self.setLayout(layout)

    def on_card_clicked(self, key):
        parent = self.parent()
        if parent and hasattr(parent, 'on_card_filter'):
            parent.on_card_filter(key)
        
        # If Total Cost card is clicked, show category cost dialog
        if key == "total_cost":
            from ui.products_page.category_cost_dialog import CategoryCostDialog
            dialog = CategoryCostDialog(parent)
            dialog.exec()

    def update_cards(self):
        symbol = get_currency_symbol()
        conn = connect_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COALESCE(SUM(COALESCE(cost, 0) * COALESCE(stock, 0)), 0)
                FROM products
                WHERE sold_by IS NULL OR sold_by != 'Service'
            """)
            total_cost_sum = cursor.fetchone()[0] or 0
            self.cards["total_cost"].setText(format_money(total_cost_sum, symbol))

            # Out of Stock
            cursor.execute("SELECT COUNT(*) FROM products WHERE (sold_by IS NULL OR sold_by != 'Service') AND COALESCE(stock, 0) = 0")
            self.cards["out_stock"].setText(str(cursor.fetchone()[0]))

            # Low Stock (stock > 0 and stock <= low_stock)
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE (sold_by IS NULL OR sold_by != 'Service') 
                  AND COALESCE(stock, 0) > 0 
                  AND COALESCE(stock, 0) <= COALESCE(low_stock, 0)
            """)
            self.cards["low_stock"].setText(str(cursor.fetchone()[0]))

            # Expiring Soon (7 days)
            today = QDate.currentDate()
            today_str = today.toString("yyyy-MM-dd")
            week_later_str = today.addDays(7).toString("yyyy-MM-dd")
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE expire_date IS NOT NULL 
                  AND expire_date >= ? AND expire_date <= ?
            """, (today_str, week_later_str))
            self.cards["expiring_soon"].setText(str(cursor.fetchone()[0]))

            # Expired
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE expire_date IS NOT NULL AND expire_date < ?
            """, (today_str,))
            self.cards["expired"].setText(str(cursor.fetchone()[0]))

        except Exception as e:
            logger.error(f"Error updating cards: {e}")
        finally:
            conn.close()

    def retranslateUi(self):
        translations = {
            "total_cost": ("စုစုပေါင်းကုန်ကျငွေ", "Total Cost"),
            "out_stock": ("ကုန်သွားပြီ", "Out of Stock"),
            "low_stock": ("စတော့နည်းနေပြီ", "Low Stock"),
            "expiring_soon": ("၇ ရက်အတွင်းသက်တမ်းကုန်မည်", "Expiring ≤7 Days"),
            "expired": ("သက်တမ်းကုန်သွားပြီ", "Expired")
        }
        from utils.language import lang
        lang_code = lang.get_current()
        for key, (my_text, en_text) in translations.items():
            if key in self.card_widgets:
                self.card_widgets[key].set_title(my_text if lang_code == "my" else en_text)
