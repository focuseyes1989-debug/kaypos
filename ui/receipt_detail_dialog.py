# ui/receipt_detail_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.wholesale_pricing import ensure_wholesale_sale_item_columns
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import os


class ReceiptDetailDialog(QDialog):
    def __init__(self, sale_id, parent=None, is_credit=False):
        if isinstance(parent, bool):
            is_credit = parent
            parent = None
        super().__init__(parent)
        self.sale_id = sale_id
        self.is_credit = is_credit
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle("Receipt Details")
        self.setMinimumSize(820, 550)
        self.setModal(True)
        
        # Set window icon
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Load sale data based on type
        if is_credit:
            sale, items = self._load_credit_sale_data()
        else:
            sale, items = self._load_sale_data()

        if not sale:
            main_layout.addWidget(QLabel("Sale not found."))
            self.setLayout(main_layout)
            return

        symbol = get_currency_symbol()
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Color definitions
        text_color = "#dcddde" if is_dark else "#212529"
        green_color = "#3ba55d" if is_dark else "#28a745"
        red_color = "#ed4245" if is_dark else "#dc3545"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        # ✅ Primary color - fallback to #5865f2 if not in colors
        primary_color = colors.get('primary', '#5865f2')

        # Header info with larger font
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)
        
        header_font = QFont()
        header_font.setPointSize(11)
        
        # Title with SVG icon concept
        title_layout = QHBoxLayout()
        
        # Icon label
        icon_label = QLabel()
        icon = self._load_svg_icon("receipt", size=(24, 24))
        if icon and not icon.isNull():
            icon_label.setPixmap(icon.pixmap(24, 24))
            icon_label.setStyleSheet("background: transparent; border: none;")
        else:
            icon_label.setText("🧾")
            icon_label.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        title_layout.addWidget(icon_label)
        
        title_label = QLabel("Receipt Details")
        title_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {colors['text']}; background: transparent; border: none;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # Badge for credit/regular
        badge_text = "Credit" if is_credit else "Sale"
        badge = QLabel(badge_text)
        badge_color = primary_color if not is_credit else '#9b59b6'
        badge.setStyleSheet(f"""
            background-color: {badge_color};
            color: white;
            padding: 4px 14px;
            border-radius: 12px;
            font-size: 10pt;
            font-weight: 600;
        """)
        title_layout.addWidget(badge)
        
        info_layout.addLayout(title_layout)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {colors['border']}; max-height: 1px;")
        info_layout.addWidget(sep)
        
        if is_credit:
            # Credit sale data structure
            # invoice_no, sale_date, total_amount, paid_amount, change_amount, 
            # customer_name, payment_type, balance_amount, status, due_date
            invoice_no, sale_date, total_amount, paid_amount, change_amount, customer_name, payment_type, balance_amount, status, due_date = sale
            
            # Create info grid
            info_grid_layout = QHBoxLayout()
            
            # Left column
            left_layout = QVBoxLayout()
            left_layout.setSpacing(4)
            left_layout.addWidget(self._create_label(f"📄 Invoice: {invoice_no}", header_font, colors))
            left_layout.addWidget(self._create_label(f"📅 Date: {sale_date}", header_font, colors))
            left_layout.addWidget(self._create_label(f"💰 Total: {format_money(total_amount, symbol)}", header_font, colors))
            info_grid_layout.addLayout(left_layout)
            
            # Right column
            right_layout = QVBoxLayout()
            right_layout.setSpacing(4)
            
            # Status with color
            status_label = self._create_label(f"📌 Status: {status}", header_font, colors)
            if status == "paid":
                status_label.setStyleSheet(f"color: {green_color}; font-weight: bold; font-size: 11pt;")
            elif status == "overdue" or (due_date and balance_amount > 0 and QDate.fromString(due_date, "yyyy-MM-dd") < QDate.currentDate()):
                status_label.setStyleSheet(f"color: {red_color}; font-weight: bold; font-size: 11pt;")
                if status != "overdue":
                    status_label.setText(f"📌 Status: Overdue")
            elif status == "pending" or status == "partial":
                status_label.setStyleSheet(f"color: {orange_color}; font-weight: bold; font-size: 11pt;")
            right_layout.addWidget(status_label)
            
            right_layout.addWidget(self._create_label(f"💳 Payment: Credit", header_font, colors))
            right_layout.addWidget(self._create_label(f"⏰ Due Date: {due_date if due_date else 'N/A'}", header_font, colors))
            right_layout.addWidget(self._create_label(f"💰 Balance: {format_money(balance_amount, symbol)}", header_font, colors))
            
            if customer_name:
                info_grid_layout.addWidget(self._create_label(f"👤 Customer: {customer_name}", header_font, colors))
            
            info_layout.addLayout(info_grid_layout)
            
            # Paid amount
            paid_label = self._create_label(f"💵 Paid: {format_money(paid_amount, symbol)}", header_font, colors)
            if paid_amount > 0:
                paid_label.setStyleSheet(f"color: {green_color}; font-weight: bold; font-size: 11pt;")
            info_layout.addWidget(paid_label)
            
        else:
            # Regular sale data structure
            invoice_no, created_at, total, payment, change_amount, customer_name, payment_type = sale
            
            # Create info grid
            info_grid_layout = QHBoxLayout()
            
            # Left column
            left_layout = QVBoxLayout()
            left_layout.setSpacing(4)
            left_layout.addWidget(self._create_label(f"📄 Invoice: {invoice_no}", header_font, colors))
            left_layout.addWidget(self._create_label(f"📅 Date: {created_at}", header_font, colors))
            left_layout.addWidget(self._create_label(f"💰 Total: {format_money(total, symbol)}", header_font, colors))
            info_grid_layout.addLayout(left_layout)
            
            # Right column
            right_layout = QVBoxLayout()
            right_layout.setSpacing(4)
            right_layout.addWidget(self._create_label(f"💳 Payment: {payment_type if payment_type else 'Cash'}", header_font, colors))
            right_layout.addWidget(self._create_label(f"💵 Paid: {format_money(payment, symbol)}", header_font, colors))
            right_layout.addWidget(self._create_label(f"🔄 Change: {format_money(change_amount, symbol)}", header_font, colors))
            info_grid_layout.addLayout(right_layout)
            
            if customer_name:
                info_grid_layout.addWidget(self._create_label(f"👤 Customer: {customer_name}", header_font, colors))
            
            info_layout.addLayout(info_grid_layout)
        
        main_layout.addWidget(info_frame)

        # Items table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["Product", "Qty", "Price", "Total", "Wholesale Saving"])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        
        # Apply table style
        self._apply_table_style(colors)
        
        # Set larger font for table
        table_font = QFont()
        table_font.setPointSize(10)
        self.items_table.setFont(table_font)
        self.items_table.verticalHeader().setDefaultSectionSize(35)

        # Populate items
        self.items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            name = item[0]
            qty = item[1]
            price = item[2]
            total = item[3]
            regular_price = float(item[4] or 0) if len(item) > 4 else 0
            wholesale_savings = float(item[5] or 0) if len(item) > 5 else 0
            tier_min_qty = int(item[6] or 0) if len(item) > 6 else 0
            unit_label = item[7] if len(item) > 7 else ""

            # Product
            name_item = QTableWidgetItem(name)
            name_item.setForeground(QColor(text_color))
            self.items_table.setItem(row, 0, name_item)
            
            # Qty
            qty_item = QTableWidgetItem(str(qty))
            qty_item.setForeground(QColor(text_color))
            self.items_table.setItem(row, 1, qty_item)
            
            # Price
            price_item = QTableWidgetItem(format_money(price, symbol))
            price_item.setForeground(QColor(text_color))
            self.items_table.setItem(row, 2, price_item)
            
            # Total
            total_item = QTableWidgetItem(format_money(total, symbol))
            total_item.setForeground(QColor(green_color))
            self.items_table.setItem(row, 3, total_item)

            # Wholesale saving
            if regular_price > float(price or 0) and wholesale_savings > 0:
                tier_label = f"{tier_min_qty}+ {unit_label}".strip() if tier_min_qty else "Applied"
                saving_text = (
                    f"{tier_label} | Regular {format_money(regular_price, symbol)} | "
                    f"Saved {format_money(wholesale_savings, symbol)}"
                )
                saving_item = QTableWidgetItem(saving_text)
                saving_item.setForeground(QColor(green_color))
            else:
                saving_item = QTableWidgetItem("-")
                saving_item.setForeground(QColor(text_color))
            self.items_table.setItem(row, 4, saving_item)

        main_layout.addWidget(self.items_table)

        # Totals section
        subtotal = sum(item[3] for item in items)
        totals_layout = QHBoxLayout()
        totals_layout.setSpacing(15)
        totals_layout.addStretch()
        
        totals_font = QFont()
        totals_font.setPointSize(12)
        totals_font.setBold(True)
        
        if is_credit:
            totals_layout.addWidget(self._create_label(f"Subtotal: {format_money(subtotal, symbol)}", totals_font, colors))
            totals_layout.addWidget(self._create_label(f"Total: {format_money(total_amount, symbol)}", totals_font, colors))
            
            paid_label = self._create_label(f"Paid: {format_money(paid_amount, symbol)}", totals_font, colors)
            paid_label.setStyleSheet(f"color: {green_color}; font-weight: bold; font-size: 12pt;")
            totals_layout.addWidget(paid_label)
            
            balance_label = self._create_label(f"Balance: {format_money(balance_amount, symbol)}", totals_font, colors)
            if balance_amount > 0:
                balance_label.setStyleSheet(f"color: {red_color}; font-weight: bold; font-size: 12pt;")
            else:
                balance_label.setStyleSheet(f"color: {green_color}; font-weight: bold; font-size: 12pt;")
            totals_layout.addWidget(balance_label)
        else:
            totals_layout.addWidget(self._create_label(f"Subtotal: {format_money(subtotal, symbol)}", totals_font, colors))
            totals_layout.addWidget(self._create_label(f"Total: {format_money(total, symbol)}", totals_font, colors))
            totals_layout.addWidget(self._create_label(f"Payment: {format_money(payment, symbol)}", totals_font, colors))
            totals_layout.addWidget(self._create_label(f"Change: {format_money(change_amount, symbol)}", totals_font, colors))
        
        main_layout.addLayout(totals_layout)

        # Close button with SVG icon
        btn_close = ModernButton(" Close", ModernButton.TERTIARY)
        btn_close.set_icon("close", size=(16, 16))
        btn_close.set_compact(False)
        btn_close.setFixedSize(120, 35)
        btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)
        
        # Apply initial theme
        self._apply_theme()
    
    def _load_svg_icon(self, icon_name, size=(20, 20)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                from PyQt6.QtGui import QPixmap
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        # Try PNG fallback
        png_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(png_path):
            try:
                from PyQt6.QtGui import QPixmap
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        return None
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update table style
        self._apply_table_style(colors)
        
        # Update button
        for child in self.findChildren(ModernButton):
            child.update_theme()
            child.set_icon("close", size=(16, 16))
    
    def _apply_table_style(self, colors):
        """Apply theme-aware table styling"""
        is_dark = is_dark_theme()
        
        if is_dark:
            table_style = """
                QTableWidget {
                    background-color: #2f3136;
                    alternate-background-color: #36393f;
                    selection-background-color: #40444b;
                    selection-color: #dcddde;
                    gridline-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    color: #dcddde;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #dcddde;
                }
                QTableWidget::item:selected {
                    background-color: #40444b;
                    color: #dcddde;
                }
                QHeaderView::section {
                    background-color: #202225;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #40444b;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #b9bbbe;
                }
                QTableWidget::item:hover {
                    background-color: #40444b;
                }
            """
        else:
            table_style = """
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    selection-background-color: #e9ecef;
                    selection-color: #212529;
                    gridline-color: #dee2e6;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    color: #212529;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #212529;
                }
                QTableWidget::item:selected {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #2c3e50;
                }
                QTableWidget::item:hover {
                    background-color: #f1f3f5;
                }
            """
        
        self.items_table.setStyleSheet(table_style)

    def _load_sale_data(self):
        """Load regular sale data"""
        conn = connect_db()
        cursor = conn.cursor()
        ensure_wholesale_sale_item_columns(cursor)
        conn.commit()
        
        cursor.execute("""
            SELECT s.invoice_no, s.created_at, s.total, s.payment, s.change_amount,
                   c.name, s.payment_type
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = ?
        """, (self.sale_id,))
        sale = cursor.fetchone()
        
        if not sale:
            conn.close()
            return None, []

        # Fetch sale items
        cursor.execute("""
            SELECT product_name, qty, price, total,
                   COALESCE(wholesale_regular_price, 0),
                   COALESCE(wholesale_savings, 0),
                   COALESCE(wholesale_tier_min_qty, 0),
                   COALESCE(wholesale_unit_label, '')
            FROM sale_items
            WHERE sale_id = ?
        """, (self.sale_id,))
        items = cursor.fetchall()
        conn.close()
        
        return sale, items

    def _load_credit_sale_data(self):
        """Load credit sale data from credit_sales table"""
        conn = connect_db()
        cursor = conn.cursor()
        ensure_wholesale_sale_item_columns(cursor)
        conn.commit()
        
        # Get credit sale directly from credit_sales table
        cursor.execute("""
            SELECT cs.invoice_no, cs.sale_date, cs.total_amount, cs.paid_amount,
                   0 as change_amount, c.name, 'Credit' as payment_type,
                   cs.balance_amount, cs.status, cs.due_date
            FROM credit_sales cs
            LEFT JOIN customers c ON cs.customer_id = c.id
            WHERE cs.id = ?
        """, (self.sale_id,))
        sale = cursor.fetchone()
        
        if not sale:
            conn.close()
            return None, []

        # Get items - try from sale_items via sale_id
        items = []
        
        # Check if there's a linked sale
        cursor.execute("SELECT sale_id FROM credit_sales WHERE id = ?", (self.sale_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            # Get items from sale_items using sale_id
            cursor.execute("""
                SELECT product_name, qty, price, total,
                       COALESCE(wholesale_regular_price, 0),
                       COALESCE(wholesale_savings, 0),
                       COALESCE(wholesale_tier_min_qty, 0),
                       COALESCE(wholesale_unit_label, '')
                FROM sale_items
                WHERE sale_id = ?
            """, (result[0],))
            items = cursor.fetchall()
        
        # If no items found, try to get from credit_sale_items if exists
        if not items:
            try:
                cursor.execute("""
                    SELECT product_name, quantity, price, total
                    FROM credit_sale_items
                    WHERE credit_sale_id = ?
                """, (self.sale_id,))
                items = cursor.fetchall()
            except:
                pass
        
        # If still no items, create a placeholder
        if not items:
            # Get total amount and create a single item
            total_amount = sale[2] if sale else 0
            if total_amount > 0:
                items = [("Credit Sale Total", 1, total_amount, total_amount)]
        
        conn.close()
        return sale, items

    def _create_label(self, text, font, colors=None):
        """Create a themed label"""
        label = QLabel(text)
        label.setFont(font)
        if colors:
            label.setStyleSheet(f"color: {colors['text']}; background: transparent; border: none;")
        else:
            label.setStyleSheet("background: transparent; border: none;")
        return label
    
    def showEvent(self, event):
        """Handle show event - apply theme"""
        self._apply_theme()
        super().showEvent(event)
