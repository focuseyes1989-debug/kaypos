# ui/sales_summary/items_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from models.database import connect_db
from utils.currency import format_money, get_currency_symbol
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.search_widget import ModernSearchWidget
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import get_theme_colors, get_icon_with_color, theme_manager
from ui.design_system.dialog_styles import add_standard_close_footer, modern_table_stylesheet
from loguru import logger


class ItemsTab(QWidget):
    """Sales by Items Tab - with product detail view on double click"""
    
    # Signal to notify parent about product selection
    product_selected = pyqtSignal(str)  # product_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.full_data = []
        self.filtered_data = []
        self.current_page = 1
        self.page_size = 25
        
        layout = QVBoxLayout()
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_widget = ModernSearchWidget("Search product name...")
        self.search_widget.search_changed.connect(self.on_search_changed)
        search_layout.addWidget(self.search_widget)
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)  # 9 columns
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Enable double click on table cells
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table)
        
        # Pagination
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)
        
        self.setLayout(layout)
    
    def get_main_window(self):
        """Get the main window instance"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'status_bar'):
                return parent
            parent = parent.parent()
        return None
    
    def show_status_message(self, message, timeout=3000):
        """Show message in status bar if available"""
        main_window = self.get_main_window()
        if main_window and hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(message, timeout)
        else:
            # Fallback: log the message
            logger.info(message)
    
    def on_cell_double_clicked(self, row, column):
        """Handle double click on table cell."""
        # Only respond to double click on Product Name column (column 0)
        if column == 0:
            product_name_item = self.table.item(row, 0)
            if product_name_item:
                product_name = product_name_item.text()
                self.show_product_receipts(product_name)
    
    def show_product_receipts(self, product_name):
        """
        Show receipts for a specific product.
        ✅ FIXED: Search ALL sales, not just current date range
        """
        # Show loading message
        lang = self.get_lang()
        msg = f"Loading receipts for: {product_name}..." if lang != "my" else f"{product_name} အတွက် ပြေစာများ ရှာဖွေနေသည်..."
        self.show_status_message(msg, 3000)
        
        try:
            from ui.receipt_detail_dialog import ReceiptDetailDialog
            
            conn = connect_db()
            cursor = conn.cursor()
            
            # ✅ FIXED: No date range filter - search ALL sales
            # First try: Exact match (case-insensitive)
            cursor.execute("""
                SELECT DISTINCT s.id, s.invoice_no, s.created_at, s.total
                FROM sales s
                JOIN sale_items si ON s.id = si.sale_id
                WHERE s.status = 'completed'
                  AND LOWER(si.product_name) = LOWER(?)
                ORDER BY s.created_at DESC
            """, (product_name,))
            
            sales = cursor.fetchall()
            
            # If no results, try LIKE with wildcards (partial match)
            if not sales:
                logger.info(f"No exact match for '{product_name}', trying LIKE search...")
                cursor.execute("""
                    SELECT DISTINCT s.id, s.invoice_no, s.created_at, s.total
                    FROM sales s
                    JOIN sale_items si ON s.id = si.sale_id
                    WHERE s.status = 'completed'
                      AND LOWER(si.product_name) LIKE LOWER(?)
                    ORDER BY s.created_at DESC
                """, (f'%{product_name}%',))
                
                sales = cursor.fetchall()
            
            # If still no results, try exact match (case-sensitive fallback)
            if not sales:
                cursor.execute("""
                    SELECT DISTINCT s.id, s.invoice_no, s.created_at, s.total
                    FROM sales s
                    JOIN sale_items si ON s.id = si.sale_id
                    WHERE s.status = 'completed'
                      AND si.product_name = ?
                    ORDER BY s.created_at DESC
                """, (product_name,))
                
                sales = cursor.fetchall()
            
            # If still no results, get similar products
            if not sales:
                cursor.execute("""
                    SELECT DISTINCT si.product_name
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    WHERE s.status = 'completed'
                      AND LOWER(si.product_name) LIKE LOWER(?)
                    LIMIT 10
                """, (f'%{product_name}%',))
                
                similar_products = cursor.fetchall()
                similar_names = [p[0] for p in similar_products]
                
                conn.close()
                
                if similar_names:
                    lang = self.get_lang()
                    if lang == "my":
                        msg = f"'{product_name}' အတွက် ပြေစာမရှိပါ။ ဤအမည်များနှင့် ဆင်တူသော ပစ္စည်းများရှိပါသည်:\n\n" + "\n".join([f"• {name}" for name in similar_names[:5]])
                    else:
                        msg = f"No receipts found for '{product_name}'. Similar products found:\n\n" + "\n".join([f"• {name}" for name in similar_names[:5]])
                    QMessageBox.information(self, "No Receipts", msg)
                    self.show_status_message(f"No receipts found for: {product_name}", 3000)
                    return
                
                conn.close()
                msg = f"No receipts found for: {product_name}" if lang != "my" else f"{product_name} အတွက် ပြေစာမရှိပါ"
                QMessageBox.information(self, "No Receipts", msg)
                self.show_status_message(msg, 3000)
                return
            
            conn.close()
            
            # Show all receipts for this product in a dialog
            self._show_product_receipts_dialog(product_name, sales)
            
        except Exception as e:
            logger.error(f"Error showing product receipts: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load receipts: {e}")
    
    def _show_product_receipts_dialog(self, product_name, sales):
        """
        Show a dialog with all receipts for a product.
        
        Args:
            product_name: Name of the product
            sales: List of sales tuples (id, invoice_no, created_at, total)
        """
        from PyQt6.QtWidgets import QDialog, QFrame, QSizePolicy
        
        symbol = get_currency_symbol()
        lang = self.get_lang()
        
        dialog = QDialog(self)
        if lang == "my":
            dialog.setWindowTitle(f"{product_name} အတွက် ပြေစာများ")
            invoice_header = "ပြေစာအမှတ်"
            date_header = "ရက်စွဲ"
            total_header = "စုစုပေါင်း"
            view_header = "ကြည့်ရန်"
            close_text = "ပိတ်မည်"
        else:
            dialog.setWindowTitle(f"Receipts for: {product_name}")
            invoice_header = "Invoice No"
            date_header = "Date"
            total_header = "Total"
            view_header = "View"
            close_text = "Close"
        
        dialog.resize(820, 520)
        dialog.setMinimumSize(720, 460)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)

        header_card = QFrame()
        header_card.setObjectName("receiptHistoryHeader")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(12)

        icon_badge = QLabel()
        icon_badge.setObjectName("receiptIconBadge")
        icon_badge.setFixedSize(44, 44)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_badge)

        heading_layout = QVBoxLayout()
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(3)
        title_label = QLabel(product_name)
        title_label.setObjectName("receiptHistoryTitle")
        subtitle_label = QLabel(
            "Receipts containing this product"
            if lang != "my" else "ဤပစ္စည်းပါဝင်သော ပြေစာများ"
        )
        subtitle_label.setObjectName("receiptHistorySubtitle")
        heading_layout.addWidget(title_label)
        heading_layout.addWidget(subtitle_label)
        header_layout.addLayout(heading_layout, 1)

        info_label = QLabel(
            f"{len(sales)} RECEIPTS"
            if lang != "my" else f"ပြေစာ {len(sales)} ခု"
        )
        info_label.setObjectName("receiptCountPill")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setMinimumWidth(100)
        info_label.setFixedHeight(30)
        header_layout.addWidget(info_label)
        layout.addWidget(header_card)
        
        # Table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([invoice_header, date_header, total_header, view_header])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(54)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        # Account for the shared modern-table horizontal cell padding so the
        # 92px action button still has room to center without clipping.
        table.setColumnWidth(3, 144)
        
        # Populate table
        for sale in sales:
            sale_id, invoice_no, created_at, total = sale
            row = table.rowCount()
            table.insertRow(row)
            
            # Invoice No
            inv_item = QTableWidgetItem(invoice_no)
            table.setItem(row, 0, inv_item)
            
            # Date
            date_item = QTableWidgetItem(str(created_at)[:16] if created_at else "")
            table.setItem(row, 1, date_item)
            
            # Total
            total_item = QTableWidgetItem(format_money(total, symbol))
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, 2, total_item)
            
            # View button
            btn_view = ModernButton("View" if lang != "my" else "ကြည့်မည်", ModernButton.SECONDARY)
            btn_view.set_icon("visibility", size=(15, 15))
            btn_view.set_compact(True)
            btn_view.setFixedSize(92, 34)
            btn_view.clicked.connect(lambda _, sid=sale_id: self._open_receipt_detail(sid))
            button_cell = QWidget()
            button_cell.setStyleSheet("background: transparent; border: none;")
            button_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            button_layout = QHBoxLayout(button_cell)
            button_layout.setContentsMargins(4, 0, 4, 0)
            button_layout.addWidget(btn_view, alignment=Qt.AlignmentFlag.AlignCenter)
            table.setCellWidget(row, 3, button_cell)
        
        layout.addWidget(table)
        
        btn_close = add_standard_close_footer(layout, dialog, close_text)

        def apply_dialog_theme(*_):
            colors = get_theme_colors()
            icon_badge.setPixmap(
                get_icon_with_color("receipt_long", "#ffffff", (22, 22)).pixmap(22, 22)
            )
            inv_color = QColor(colors['progress_bg'])
            total_color = QColor(colors['success'])
            for row_index in range(table.rowCount()):
                if table.item(row_index, 0):
                    table.item(row_index, 0).setForeground(inv_color)
                if table.item(row_index, 2):
                    table.item(row_index, 2).setForeground(total_color)
            dialog.setStyleSheet(f"""
                QDialog {{ background-color: {colors['bg']}; color: {colors['text']}; }}
                QFrame#receiptHistoryHeader {{
                    background-color: {colors['card_bg']};
                    border: 1px solid {colors['border']};
                    border-radius: 12px;
                }}
                QLabel#receiptIconBadge {{
                    background-color: {colors['progress_bg']};
                    border: none;
                    border-radius: 11px;
                }}
                QLabel#receiptHistoryTitle {{
                    color: {colors['text']};
                    font-size: 16px;
                    font-weight: 700;
                    background: transparent;
                }}
                QLabel#receiptHistorySubtitle {{
                    color: {colors['text_secondary']};
                    font-size: 10px;
                    background: transparent;
                }}
                QLabel#receiptCountPill {{
                    color: {colors['progress_bg']};
                    background-color: {colors['bg_hover']};
                    border: 1px solid {colors['border']};
                    border-radius: 8px;
                    font-size: 9px;
                    font-weight: 700;
                    padding: 0 10px;
                }}
            """ + modern_table_stylesheet(colors))

        theme_manager.theme_changed.connect(apply_dialog_theme)
        dialog.finished.connect(
            lambda _result: theme_manager.theme_changed.disconnect(apply_dialog_theme)
        )
        apply_dialog_theme()
        
        dialog.exec()
    
    def _open_receipt_detail(self, sale_id):
        """
        Open receipt detail dialog for a specific sale.
        
        Args:
            sale_id: ID of the sale to view
        """
        try:
            from ui.receipt_detail_dialog import ReceiptDetailDialog
            dialog = ReceiptDetailDialog(sale_id)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening receipt detail: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open receipt: {e}")
    
    def on_search_changed(self, text):
        """Handle search text change - reset to page 1 and filter"""
        self.current_page = 1
        self.filter_data()
    
    def filter_data(self):
        """Filter the full data based on search text"""
        search_text = self.search_widget.get_text().lower().strip()
        
        if not search_text:
            self.filtered_data = self.full_data.copy()
        else:
            self.filtered_data = [row for row in self.full_data if search_text in row[0].lower()]
        
        # Update pagination with filtered data count
        self.pagination.set_total_items(len(self.filtered_data))
        self.display_current_page()
    
    def display_current_page(self):
        """Display the current page of data"""
        symbol = get_currency_symbol()
        lang_code = self.parent_page.get_lang() if self.parent_page else "en"
        
        # Calculate start and end indices for current page
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.filtered_data))
        page_data = self.filtered_data[start_idx:end_idx]
        
        # Calculate max net sales for progress bar scaling
        max_sales = max([row[5] for row in self.filtered_data]) if self.filtered_data else 0
        
        self.table.setRowCount(0)
        for row_data in page_data:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            product_name = row_data[0]
            category = row_data[1] if row_data[1] else "Uncategorized"
            total_qty = row_data[2]
            gross_sales = row_data[3]  # Gross Sales (price * qty)
            discount = row_data[4]     # Discount amount
            net_sales = row_data[5]    # Net Sales (after discount) - from sales.total
            cogs = row_data[6]
            gross_profit = row_data[7]
            
            # Calculate percentage for progress bar (relative to max net sales)
            percentage = (net_sales / max_sales * 100) if max_sales > 0 else 0
            
            # Product Name - Make it look clickable
            product_item = QTableWidgetItem(product_name)
            product_item.setToolTip("Double click to view receipts for this product")
            self.table.setItem(r, 0, product_item)
            
            # Category
            self.table.setItem(r, 1, QTableWidgetItem(category))
            
            # Items Sold
            qty_item = QTableWidgetItem(str(total_qty))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 2, qty_item)
            
            # Gross Sales (price * qty - before discount)
            gross_item = QTableWidgetItem(format_money(gross_sales, symbol))
            gross_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if gross_sales > 0:
                gross_item.setForeground(QColor(52, 152, 219))
            self.table.setItem(r, 3, gross_item)
            
            # Discount Amount
            discount_item = QTableWidgetItem(format_money(discount, symbol))
            discount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if discount > 0:
                discount_item.setForeground(QColor(231, 76, 60))  # Red
            else:
                discount_item.setForeground(QColor(149, 165, 166))  # Gray
            self.table.setItem(r, 4, discount_item)
            
            # Net Sales (after discount) - from sales.total
            sales_item = QTableWidgetItem(format_money(net_sales, symbol))
            sales_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if net_sales > 0:
                sales_item.setForeground(QColor(46, 204, 113))
            self.table.setItem(r, 5, sales_item)
            
            # Cost of Goods
            cogs_item = QTableWidgetItem(format_money(cogs, symbol))
            cogs_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if cogs > 0:
                cogs_item.setForeground(QColor(231, 76, 60))
            self.table.setItem(r, 6, cogs_item)
            
            # Gross Profit
            profit_item = QTableWidgetItem(format_money(gross_profit, symbol))
            profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if gross_profit > 0:
                profit_item.setForeground(QColor(46, 204, 113))
            elif gross_profit < 0:
                profit_item.setForeground(QColor(231, 76, 60))
            self.table.setItem(r, 7, profit_item)
            
            # Progress Bar
            progress_widget = QWidget()
            progress_layout = QHBoxLayout(progress_widget)
            progress_layout.setContentsMargins(5, 2, 5, 2)
            progress_layout.setSpacing(0)
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(int(percentage))
            progress_bar.setFormat("")
            progress_bar.setTextVisible(False)
            
            if percentage >= 80:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #e74c3c;
                        border-radius: 3px;
                    }
                """)
            elif percentage >= 50:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #f39c12;
                        border-radius: 3px;
                    }
                """)
            else:
                progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #2ecc71;
                        border-radius: 3px;
                    }
                """)
            
            progress_layout.addWidget(progress_bar)
            self.table.setCellWidget(r, 8, progress_widget)
            
            self.table.setRowHeight(r, 50)
        
        # Set headers based on language
        if lang_code == "my":
            self.table.setHorizontalHeaderLabels([
                "ပစ္စည်းအမည်", "အမျိုးအစား", "ရောင်းရသည့်အရေအတွက်",
                "စုစုပေါင်းရောင်းအား (အကြမ်း)", "လျှော့စျေး", 
                "အသားတင်ရောင်းအား", "ကုန်ကျစရိတ်", 
                "အသားတင်အမြတ်", "တိုးတက်မှု"
            ])
        else:
            self.table.setHorizontalHeaderLabels([
                "Product Name", "Category", "Items Sold", "Gross Sales", 
                "Discount", "Net Sales", "Cost of Goods", 
                "Gross Profit", "Progress"
            ])
    
    def on_page_changed(self, page, page_size):
        """Handle page change from pagination widget"""
        self.current_page = page
        self.page_size = page_size
        self.display_current_page()
    
    def load(self, from_date, to_date):
        """Load data from database"""
        symbol = get_currency_symbol()
        conn = connect_db()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                si.product_name,
                COALESCE(p.category, 'Uncategorized') as category,
                COALESCE(SUM(si.qty), 0) as total_qty,
                COALESCE(SUM(si.price * si.qty), 0) as gross_sales,
                COALESCE(SUM(s.discount_amount), 0) as total_discount,
                COALESCE(SUM(si.total) - SUM(s.discount_amount), 0) as net_sales,
                COALESCE(SUM(p.cost * si.qty), 0) as cogs,
                COALESCE(SUM(si.total) - SUM(s.discount_amount) - SUM(p.cost * si.qty), 0) as gross_profit
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_id = p.id OR (si.product_id IS NULL AND si.product_name = p.name)
            WHERE s.status = 'completed' AND date(s.created_at) BETWEEN ? AND ?
            GROUP BY si.product_name, COALESCE(p.category, 'Uncategorized')
            ORDER BY net_sales DESC
        """
        
        cursor.execute(query, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        
        self.full_data = [list(row) for row in rows]
        
        # Reset to page 1
        self.current_page = 1
        self.filter_data()
    
    def get_lang(self):
        """Get current language"""
        from utils.language import lang
        return lang.get_current()
    
    def retranslateUi(self):
        """Retranslate UI"""
        lang_code = self.get_lang()
        if lang_code == "my":
            self.search_widget.retranslateUi("my")
        else:
            self.search_widget.retranslateUi("en")
        
        # Refresh display with new headers
        self.display_current_page()
