# ui/dashboard/dashboard_table.py
from PyQt6.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from models.database import connect_db
from utils.currency import format_money
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from loguru import logger


class DashboardTable(QFrame):
    """Dashboard Sales Performance Table"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_label = QLabel("📋 Sales Performance")
        header_label.setStyleSheet("""
            font-size: 12pt;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        layout.addWidget(header_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "Gross Sales", "Net Sales", "Gross Profit", "Refunds", "Discount"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(55)
        
        self._update_table_style()
        
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def _apply_style(self):
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
    
    def _update_table_style(self):
        is_dark = is_dark_theme()
        
        if is_dark:
            table_style = """
                QTableWidget {
                    background-color: #2f3136;
                    alternate-background-color: #36393f;
                    selection-background-color: #40444b;
                    selection-color: #dcddde;
                    gridline-color: transparent;
                    border: 1px solid #40444b;
                    border-radius: 10px;
                    color: #dcddde;
                    spacing: 4px;
                }
                QTableWidget::item {
                    padding: 6px 10px;
                    border: none;
                    border-bottom: 1px solid #40444b;
                    color: #dcddde;
                    background-color: transparent;
                }
                QTableWidget::item:selected {
                    background-color: #36393f;
                    color: #dcddde;
                    border-radius: 4px;
                }
                QTableWidget::item:hover {
                    background-color: #40444b;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #202225;
                    padding: 6px 10px;
                    border: none;
                    border-bottom: 2px solid #40444b;
                    font-weight: 600;
                    font-size: 9pt;
                    color: #b9bbbe;
                }
                QScrollBar:vertical {
                    background: #2f3136;
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #40444b;
                    border-radius: 3px;
                    min-height: 16px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                    border: none;
                    background: transparent;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: transparent;
                }
                QScrollBar:horizontal {
                    background: #2f3136;
                    height: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background: #40444b;
                    border-radius: 3px;
                    min-width: 16px;
                }
                QScrollBar::handle:horizontal:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                    border: none;
                    background: transparent;
                }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                    background: transparent;
                }
            """
        else:
            table_style = """
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f8f9fa;
                    selection-background-color: #e9ecef;
                    selection-color: #212529;
                    gridline-color: transparent;
                    border: 1px solid #dee2e6;
                    border-radius: 10px;
                    color: #212529;
                    spacing: 4px;
                }
                QTableWidget::item {
                    padding: 6px 10px;
                    border: none;
                    border-bottom: 1px solid #f1f3f5;
                    color: #212529;
                    background-color: transparent;
                }
                QTableWidget::item:selected {
                    background-color: #f8f9fa;
                    color: #212529;
                    border-radius: 4px;
                }
                QTableWidget::item:hover {
                    background-color: #f1f3f5;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 6px 10px;
                    border: none;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                    font-size: 9pt;
                    color: #2c3e50;
                }
                QScrollBar:vertical {
                    background: #f8f9fa;
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #ced4da;
                    border-radius: 3px;
                    min-height: 16px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                    border: none;
                    background: transparent;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: transparent;
                }
                QScrollBar:horizontal {
                    background: #f8f9fa;
                    height: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background: #ced4da;
                    border-radius: 3px;
                    min-width: 16px;
                }
                QScrollBar::handle:horizontal:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                    border: none;
                    background: transparent;
                }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                    background: transparent;
                }
            """
        
        self.table.setStyleSheet(table_style)
    
    def populate(self, from_date, to_date):
        """Populate table with data"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                date(s.created_at) as sale_date,
                COALESCE(SUM(si.qty * si.price), 0) as daily_gross,
                COALESCE(SUM(CASE WHEN s.status='refunded' THEN si.qty * si.price ELSE 0 END), 0) as daily_refunds,
                COALESCE(SUM(CASE WHEN s.status='completed' THEN COALESCE(s.discount_amount, 0) ELSE 0 END), 0) as daily_discount
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE date(s.created_at) BETWEEN ? AND ?
            GROUP BY date(s.created_at)
            ORDER BY sale_date DESC
        """, (from_date, to_date))
        rows = cursor.fetchall()
        
        self.table.setRowCount(0)
        symbol = self._get_currency_symbol()
        
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        
        total_gross = 0
        total_net = 0
        total_profit = 0
        total_refunds = 0
        total_discount = 0
        
        for row in rows:
            sale_date, daily_gross, daily_refunds, daily_discount = row
            sale_date_text = sale_date.isoformat() if hasattr(sale_date, "isoformat") else str(sale_date)
            daily_net = daily_gross - daily_refunds
            
            cursor.execute("""
                SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
                FROM sale_items
                JOIN products ON sale_items.product_id = products.id OR (sale_items.product_id IS NULL AND sale_items.product_name = products.name)
                JOIN sales ON sale_items.sale_id = sales.id
                WHERE date(sales.created_at) = ? 
                  AND sales.status='completed'
                  AND (products.sold_by IS NULL OR products.sold_by != 'Service')
            """, (sale_date,))
            daily_cogs = cursor.fetchone()[0]
            daily_profit = daily_net - daily_cogs
            
            total_gross += daily_gross
            total_net += daily_net
            total_profit += daily_profit
            total_refunds += daily_refunds
            total_discount += daily_discount
            
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 55)
            
            # Date
            date_item = QTableWidgetItem(sale_date_text)
            date_item.setForeground(QColor(text_color))
            font = date_item.font()
            font.setBold(True)
            font.setPointSize(9)
            date_item.setFont(font)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 0, date_item)
            
            # Gross Sales
            gross_item = QTableWidgetItem(format_money(daily_gross, symbol))
            gross_item.setForeground(QColor(text_color))
            gross_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 1, gross_item)
            
            # Net Sales - Green
            net_item = QTableWidgetItem(format_money(daily_net, symbol))
            net_item.setForeground(QColor(46, 204, 113) if is_dark else QColor(39, 174, 96))
            net_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = net_item.font()
            font.setBold(True)
            net_item.setFont(font)
            self.table.setItem(r, 2, net_item)
            
            # Gross Profit
            profit_item = QTableWidgetItem(format_money(daily_profit, symbol))
            if daily_profit >= 0:
                profit_item.setForeground(QColor(46, 204, 113) if is_dark else QColor(39, 174, 96))
            else:
                profit_item.setForeground(QColor(231, 76, 60))
            profit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 3, profit_item)
            
            # Refunds
            refunds_item = QTableWidgetItem(format_money(daily_refunds, symbol))
            if daily_refunds > 0:
                refunds_item.setForeground(QColor(231, 76, 60))
            else:
                refunds_item.setForeground(QColor(text_color))
            refunds_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 4, refunds_item)
            
            # Discount
            discount_item = QTableWidgetItem(format_money(daily_discount, symbol))
            if daily_discount > 0:
                discount_item.setForeground(QColor(243, 156, 18))
            else:
                discount_item.setForeground(QColor(text_color))
            discount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 5, discount_item)
        
        # TOTAL row
        if rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 55)
            
            lang = self.parent_page.get_lang() if self.parent_page else "en"
            total_label = "TOTAL" if lang != "my" else "စုစုပေါင်း"
            total_item = QTableWidgetItem(total_label)
            total_item.setForeground(QColor(text_color))
            font = total_item.font()
            font.setBold(True)
            font.setPointSize(10)
            total_item.setFont(font)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 0, total_item)
            
            total_items = [
                QTableWidgetItem(format_money(total_gross, symbol)),
                QTableWidgetItem(format_money(total_net, symbol)),
                QTableWidgetItem(format_money(total_profit, symbol)),
                QTableWidgetItem(format_money(total_refunds, symbol)),
                QTableWidgetItem(format_money(total_discount, symbol))
            ]
            
            for col, item in enumerate(total_items, start=1):
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor(text_color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, col, item)
        
        conn.close()
        self._update_table_style()
    
    def _get_currency_symbol(self):
        try:
            from utils.currency import get_currency_symbol
            return get_currency_symbol()
        except:
            return "Ks"
    
    def update_theme(self):
        self._update_table_style()
    
    def cell_double_clicked(self, row, column):
        """Handle cell double click - emit to parent"""
        if self.parent_page and hasattr(self.parent_page, 'on_table_double_click'):
            self.parent_page.on_table_double_click(row, column)
