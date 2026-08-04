# ui/ai_pages/ai_dashboard/dashboard_cards.py
"""
KPI Cards for AI Dashboard
"""

from PyQt6.QtWidgets import QGridLayout, QSizePolicy, QWidget
from ui.widgets.summary_card_widget import SummaryCardWidget


class DashboardCards:
    """KPI cards manager"""
    
    CARD_CONFIGS = [
        {
            'id': 'total_sales',
            'title': 'Total Sales',
            'icon': 'trending_up',
            'color': '#5865f2',
            'gradient_colors': ['#5865f2', '#4752c4'],
            'row': 0, 'col': 0,
            'is_currency': True
        },
        {
            'id': 'transactions',
            'title': 'Transactions',
            'icon': 'receipt_long',
            'color': '#2ecc71',
            'gradient_colors': ['#2ecc71', '#27ae60'],
            'row': 0, 'col': 1,
            'is_currency': False
        },
        {
            'id': 'avg_sale',
            'title': 'Average Sale',
            'icon': 'bar_chart',
            'color': '#f39c12',
            'gradient_colors': ['#f39c12', '#e67e22'],
            'row': 0, 'col': 2,
            'is_currency': True
        },
        {
            'id': 'gross_profit',
            'title': 'Gross Profit',
            'icon': 'savings',
            'color': '#e74c3c',
            'gradient_colors': ['#e74c3c', '#c0392b'],
            'row': 0, 'col': 3,
            'is_currency': True
        },
        {
            'id': 'expenses',
            'title': 'Expenses',
            'icon': 'money_off',
            'color': '#e67e22',
            'gradient_colors': ['#e67e22', '#d35400'],
            'row': 0, 'col': 4,
            'is_currency': True
        },
        {
            'id': 'net_profit',
            'title': 'Net Profit',
            'icon': 'currency_exchange',
            'color': '#9b59b6',
            'gradient_colors': ['#9b59b6', '#8e44ad'],
            'row': 0, 'col': 5,
            'is_currency': True
        },
    ]
    
    def __init__(self, parent):
        self.parent = parent
        self.layout = None
        self.card_widgets = {}
        self.container = None
    
    def setup(self):
        """Setup cards layout"""
        self.container = QWidget()
        self.container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.container.setStyleSheet("background-color: transparent;")
        
        self.layout = QGridLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.layout.setHorizontalSpacing(8)
        self.layout.setVerticalSpacing(8)
        
        # 6 columns equal width
        for i in range(6):
            self.layout.setColumnStretch(i, 1)
        
        self.create_cards()
        return self.container
    
    def create_cards(self):
        """Create all KPI cards"""
        for config in self.CARD_CONFIGS:
            card = SummaryCardWidget(
                title=config['title'],
                value="Loading...",
                icon=config['icon'],
                color=config['color'],
                gradient_colors=config['gradient_colors'],
                icon_is_svg=True,
                parent=self.parent
            )
            
            if config['is_currency']:
                card.set_value(0, currency_symbol="Ks", is_currency=True)
            else:
                card.set_value(0, is_currency=False)
            
            self.layout.addWidget(card, config['row'], config['col'])
            self.card_widgets[config['id']] = card
    
    def update_cards(self, sales_data, expense_data):
        """Update cards with real data"""
        if not sales_data:
            self.update_cards_zero()
            return
        
        try:
            transactions = sales_data[0] if sales_data[0] is not None else 0
            total_sales = float(sales_data[1]) if sales_data[1] is not None else 0
            avg_sale = float(sales_data[3]) if sales_data[3] is not None else 0
            total_profit = float(sales_data[4]) if sales_data[4] is not None else 0
            
            expense_total = float(expense_data[1]) if expense_data and expense_data[1] is not None else 0
            net_profit = total_sales - expense_total
            
            card_updates = {
                'total_sales': (total_sales, True),
                'transactions': (transactions, False),
                'avg_sale': (avg_sale, True),
                'gross_profit': (total_profit, True),
                'expenses': (expense_total, True),
                'net_profit': (net_profit, True),
            }
            
            for card_id, (value, is_currency) in card_updates.items():
                if card_id in self.card_widgets:
                    if is_currency:
                        self.card_widgets[card_id].set_value(value, currency_symbol="Ks", is_currency=True)
                    else:
                        self.card_widgets[card_id].set_value(value, is_currency=False)
            
            self.update_container_height()
            
        except Exception as e:
            self.update_cards_zero()
    
    def update_cards_zero(self):
        """Update cards with zero values"""
        card_updates = {
            'total_sales': (0, True),
            'transactions': (0, False),
            'avg_sale': (0, True),
            'gross_profit': (0, True),
            'expenses': (0, True),
            'net_profit': (0, True),
        }
        
        for card_id, (value, is_currency) in card_updates.items():
            if card_id in self.card_widgets:
                if is_currency:
                    self.card_widgets[card_id].set_value(value, currency_symbol="Ks", is_currency=True)
                else:
                    self.card_widgets[card_id].set_value(value, is_currency=False)
        
        self.update_container_height()
    
    def update_container_height(self):
        """Update card container height based on number of rows"""
        if not self.container or not self.layout:
            return
        
        rows = 0
        for i in range(self.layout.rowCount()):
            if self.layout.itemAtPosition(i, 0) is not None:
                rows += 1
        
        card_height = 90
        spacing = 8
        total_height = rows * (card_height + spacing) + spacing
        
        self.container.setMinimumHeight(total_height)
        self.container.setMaximumHeight(total_height + 10)
    
    def update_theme(self):
        """Update theme for all cards"""
        for card in self.card_widgets.values():
            if hasattr(card, 'update_theme'):
                card.update_theme()