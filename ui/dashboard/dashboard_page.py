# ui/dashboard/dashboard_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QMessageBox, QFrame, QScrollArea, QGridLayout,
    QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QPainter
from models.database import connect_db
from utils.currency import format_money
from utils.language import lang
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.dashboard.ai_assistant import AIAssistantWidget
from ui.dashboard.dashboard_table import DashboardTable
from ui.dashboard.dashboard_backup import DashboardBackupStatus
from ui.widgets import DateRangeWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from loguru import logger
import os


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
        lang.language_changed.connect(self.retranslateUi)
        theme_manager.theme_changed.connect(self.on_theme_changed)
        
        self.refresh_dashboard()
        self.retranslateUi()
    
    def _load_icon_pixmap(self, icon_name, size=24):
        """Load and color an SVG icon"""
        svg_path = f"assets/icons/{icon_name}.svg"
        png_path = f"assets/icons/{icon_name}.png"
        
        path = svg_path if os.path.exists(svg_path) else (png_path if os.path.exists(png_path) else None)
        if not path:
            return None
        
        try:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
        except Exception as e:
            logger.debug(f"Could not load icon {path}: {e}")
        return None
    
    def _load_colored_icon_pixmap(self, icon_name, size=16, color_hex=None):
        """Load and color an SVG icon with specified color"""
        if color_hex is None:
            is_dark = is_dark_theme()
            color_hex = "#b9bbbe" if is_dark else "#6c757d"
        
        svg_path = f"assets/icons/{icon_name}.svg"
        png_path = f"assets/icons/{icon_name}.png"
        
        path = svg_path if os.path.exists(svg_path) else (png_path if os.path.exists(png_path) else None)
        if not path:
            return None
        
        try:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Color the icon
                colored = scaled.copy()
                painter = QPainter(colored)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(colored.rect(), QColor(color_hex))
                painter.end()
                
                return colored
        except Exception as e:
            logger.debug(f"Could not load icon {path}: {e}")
        return None
    
    def on_theme_changed(self, theme_name):
        logger.debug(f"DashboardPage: Theme changed to {theme_name}")
        colors = get_theme_colors()
        
        for card in self._get_all_cards():
            if hasattr(card, 'update_theme'):
                card.update_theme()
        
        # ✅ Update backup icon and label
        self._update_backup_icon()
        self._update_backup_label_style()
        
        if hasattr(self, 'table_widget'):
            self.table_widget.update_theme()
        
        # ✅ Update splitter handle style
        self._update_splitter_style()
        
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
    
    def _update_backup_icon(self):
        """Update backup icon color based on current theme"""
        if hasattr(self, 'backup_icon'):
            is_dark = is_dark_theme()
            color_hex = "#b9bbbe" if is_dark else "#6c757d"
            
            icon_pixmap = self._load_colored_icon_pixmap("backup", 16, color_hex)
            if icon_pixmap:
                self.backup_icon.setPixmap(icon_pixmap)
                self.backup_icon.setStyleSheet("background: transparent; border: none; padding: 0px;")
            else:
                # Fallback to emoji with color
                self.backup_icon.setText("💾")
                self.backup_icon.setStyleSheet(f"""
                    font-size: 12pt;
                    color: {color_hex};
                    background: transparent;
                    border: none;
                    padding: 0px;
                """)
    
    def _update_backup_label_style(self):
        """Update backup label style based on theme"""
        if hasattr(self, 'backup_label'):
            is_dark = is_dark_theme()
            color_hex = "#b9bbbe" if is_dark else "#6c757d"
            
            self.backup_label.setStyleSheet(f"""
                font-size: 8pt;
                color: {color_hex};
                background: transparent;
                border: none;
                padding: 0px;
            """)
    
    def _update_splitter_style(self):
        """Update splitter handle style based on theme"""
        is_dark = is_dark_theme()
        
        if is_dark:
            handle_color = "#3a3c43"
            handle_hover = "#5865f2"
        else:
            handle_color = "#dee2e6"
            handle_hover = "#5865f2"
        
        if hasattr(self, 'splitter'):
            self.splitter.setStyleSheet(f"""
                QSplitter::handle {{
                    background-color: {handle_color};
                    width: 2px;
                }}
                QSplitter::handle:hover {{
                    background-color: {handle_hover};
                }}
                QSplitter::handle:pressed {{
                    background-color: {handle_hover};
                }}
            """)
    
    def _get_all_cards(self):
        cards = []
        if hasattr(self, 'today_sales_card'):
            cards.append(self.today_sales_card)
        if hasattr(self, 'today_expense_card'):
            cards.append(self.today_expense_card)
        if hasattr(self, 'today_profit_card'):
            cards.append(self.today_profit_card)
        if hasattr(self, 'today_refunds_card'):
            cards.append(self.today_refunds_card)
        if hasattr(self, 'today_discount_card'):
            cards.append(self.today_discount_card)
        if hasattr(self, 'outstanding_card'):
            cards.append(self.outstanding_card)
        if hasattr(self, 'low_stock_card'):
            cards.append(self.low_stock_card)
        if hasattr(self, 'gross_sales_card'):
            cards.append(self.gross_sales_card)
        if hasattr(self, 'net_sales_card'):
            cards.append(self.net_sales_card)
        if hasattr(self, 'gross_profit_card'):
            cards.append(self.gross_profit_card)
        return cards
    
    # ============================================================
    # SETUP UI - 2 Column Layout (4:1 Ratio)
    # ============================================================
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # ============================================================
        # SPLITTER: Left Column (80%) | Right Column (20%) - 4:1 Ratio
        # ============================================================
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        
        # ✅ Apply splitter style
        self._update_splitter_style()
        
        # ---------- LEFT COLUMN ----------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(0, 0, 8, 0)
        
        # 1. Date Range
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.on_date_range_changed)
        left_layout.addWidget(self.date_range)
        
        # 2. Cards (2 rows x 5 cards) - Using SummaryCardWidget
        # Row 1: Today Cards
        today_layout = QHBoxLayout()
        today_layout.setSpacing(8)
        
        self.today_sales_card = SummaryCardWidget(
            title="Today's Sales",
            value="0",
            icon="receipt_long",
            color="#2ecc71",
            icon_is_svg=True
        )
        self.today_sales_card.clicked.connect(self.show_today_sales_detail)
        today_layout.addWidget(self.today_sales_card, 1)
        
        self.today_expense_card = SummaryCardWidget(
            title="Today's Expense",
            value="0",
            icon="money_off",
            color="#e74c3c",
            icon_is_svg=True
        )
        today_layout.addWidget(self.today_expense_card, 1)
        
        self.today_profit_card = SummaryCardWidget(
            title="Today's Profit",
            value="0",
            icon="trending_up",
            color="#2ecc71",
            icon_is_svg=True
        )
        today_layout.addWidget(self.today_profit_card, 1)
        
        self.today_refunds_card = SummaryCardWidget(
            title="Today Refunds",
            value="0",
            icon="currency_exchange",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.today_refunds_card.clicked.connect(self.go_to_refunded_tab)
        today_layout.addWidget(self.today_refunds_card, 1)
        
        self.today_discount_card = SummaryCardWidget(
            title="Today Discount",
            value="0",
            icon="percent_discount",
            color="#f39c12",
            icon_is_svg=True
        )
        self.today_discount_card.clicked.connect(self.go_to_discounted_tab)
        today_layout.addWidget(self.today_discount_card, 1)
        
        left_layout.addLayout(today_layout)
        
        # Row 2: Other Cards
        other_layout = QHBoxLayout()
        other_layout.setSpacing(8)
        
        self.outstanding_card = SummaryCardWidget(
            title="Outstanding Credit",
            value="0",
            icon="credit_card",
            color="#e74c3c",
            icon_is_svg=True
        )
        self.outstanding_card.clicked.connect(self.go_to_outstanding_report)
        other_layout.addWidget(self.outstanding_card, 1)
        
        self.low_stock_card = SummaryCardWidget(
            title="Low Stock Count",
            value="0",
            icon="warning",
            color="#f39c12",
            icon_is_svg=True
        )
        self.low_stock_card.clicked.connect(self.go_to_low_stock_tab)
        other_layout.addWidget(self.low_stock_card, 1)
        
        self.gross_sales_card = SummaryCardWidget(
            title="Gross Sales",
            value="0",
            icon="attach_money",
            color="#3498db",
            icon_is_svg=True
        )
        other_layout.addWidget(self.gross_sales_card, 1)
        
        self.net_sales_card = SummaryCardWidget(
            title="Net Sales",
            value="0",
            icon="bar_chart",
            color="#3498db",
            icon_is_svg=True
        )
        other_layout.addWidget(self.net_sales_card, 1)
        
        self.gross_profit_card = SummaryCardWidget(
            title="Gross Profit",
            value="0",
            icon="savings",
            color="#2ecc71",
            icon_is_svg=True
        )
        other_layout.addWidget(self.gross_profit_card, 1)
        
        left_layout.addLayout(other_layout)
        
        # 3. Sales Performance Table
        self.table_widget = DashboardTable(self)
        self.table_widget.table.cellDoubleClicked.connect(self.on_table_double_click)
        left_layout.addWidget(self.table_widget, 1)
        
        # ============================================================
        # 4. Data Backup - Compact Single Line (Theme-aware)
        # ============================================================
        backup_container = QFrame()
        backup_container.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 2px 0px;
            }
        """)
        backup_layout = QHBoxLayout(backup_container)
        backup_layout.setContentsMargins(0, 2, 0, 2)
        backup_layout.setSpacing(6)
        
        # ✅ Backup icon - theme-aware
        self.backup_icon = QLabel()
        self.backup_icon.setFixedSize(18, 18)
        self.backup_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backup_icon.mousePressEvent = self.open_backup_settings
        
        # Load initial icon with theme color
        is_dark = is_dark_theme()
        icon_color = "#b9bbbe" if is_dark else "#6c757d"
        icon_pixmap = self._load_colored_icon_pixmap("backup", 16, icon_color)
        if icon_pixmap:
            self.backup_icon.setPixmap(icon_pixmap)
            self.backup_icon.setStyleSheet("background: transparent; border: none; padding: 0px;")
        else:
            self.backup_icon.setText("💾")
            self.backup_icon.setStyleSheet(f"""
                font-size: 12pt;
                color: {icon_color};
                background: transparent;
                border: none;
                padding: 0px;
            """)
        backup_layout.addWidget(self.backup_icon)
        
        # ✅ Backup label (single line)
        self.backup_label = QLabel("Last Backup: Checking...")
        self.backup_label.setStyleSheet(f"""
            font-size: 8pt;
            color: {icon_color};
            background: transparent;
            border: none;
            padding: 0px;
        """)
        self.backup_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backup_label.mousePressEvent = self.open_backup_settings
        backup_layout.addWidget(self.backup_label)
        
        backup_layout.addStretch()
        left_layout.addWidget(backup_container)
        
        # ---------- RIGHT COLUMN (AI Assistant - 20%) ----------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(8, 0, 0, 0)
        
        # ✅ AI Assistant - Live Data Analysis
        self.ai_assistant = AIAssistantWidget()
        self.ai_assistant.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self.ai_assistant, 1)
        
        # ---------- Add to Splitter ----------
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        # ✅ 4:1 Ratio - Left 80%, Right 20%
        self.splitter.setSizes([800, 200])
        
        main_layout.addWidget(self.splitter, 1)
        self.setLayout(main_layout)
    
    def on_date_range_changed(self, from_date, to_date):
        self.refresh_dashboard()
    
    # ============================================================
    # ✅ CARD UPDATE METHODS - WITH K, M, B FORMATTING
    # ============================================================
    
    def _update_card_value(self, card, value, symbol=None, is_currency=True, color=None):
        """Update card with K, M, B formatting"""
        if card and hasattr(card, 'set_value'):
            if is_currency and symbol:
                card.set_value(value, currency_symbol=symbol, is_currency=True)
            elif is_currency:
                card.set_value(value, currency_symbol=None, is_currency=True)
            else:
                card.set_value(value, is_currency=False)
            
            if color:
                card.set_color(color)
    
    def _update_card_value_raw(self, card, value, color=None):
        """Update card with raw value (no formatting)"""
        if card and hasattr(card, 'set_value_raw'):
            card.set_value_raw(str(value))
            if color:
                card.set_color(color)
    
    # ============================================================
    # NAVIGATION METHODS
    # ============================================================
    def go_to_refunded_tab(self):
        main_window = self.window()
        if hasattr(main_window, 'switch_to_page'):
            main_window.switch_to_page(4)
        QTimer.singleShot(150, lambda: self._switch_to_refunded_tab(main_window))
    
    def _switch_to_refunded_tab(self, main_window):
        try:
            if hasattr(main_window, 'receipts_page'):
                receipts_page = main_window.receipts_page
                if hasattr(receipts_page, 'tab_widget'):
                    receipts_page.tab_widget.setCurrentIndex(1)
                    if hasattr(receipts_page, 'refund_tab'):
                        receipts_page.refund_tab.load_refunded_sales()
        except Exception as e:
            logger.error(f"Error switching to refunded tab: {e}")

    def go_to_discounted_tab(self):
        main_window = self.window()
        if hasattr(main_window, 'switch_to_page'):
            main_window.switch_to_page(4)
        QTimer.singleShot(150, lambda: self._switch_to_discounted_tab(main_window))
    
    def _switch_to_discounted_tab(self, main_window):
        try:
            if hasattr(main_window, 'receipts_page'):
                receipts_page = main_window.receipts_page
                if hasattr(receipts_page, 'tab_widget'):
                    receipts_page.tab_widget.setCurrentIndex(2)
                    if hasattr(receipts_page, 'discount_tab'):
                        receipts_page.discount_tab.load_discounted_receipts()
        except Exception as e:
            logger.error(f"Error switching to discounted tab: {e}")
    
    def show_today_sales_detail(self):
        today = QDate.currentDate().toString("yyyy-MM-dd")
        QMessageBox.information(self, "Today's Sales", f"Today's sales details will be shown here")
    
    def go_to_outstanding_report(self):
        main_window = self.window()
        if hasattr(main_window, 'open_outstanding_report'):
            main_window.open_outstanding_report()
    
    def go_to_low_stock_tab(self):
        main_window = self.window()
        if hasattr(main_window, 'inventory_page') and main_window.inventory_page:
            if hasattr(main_window, 'switch_to_page'):
                main_window.switch_to_page(3)
                if hasattr(main_window.inventory_page, 'tabs'):
                    main_window.inventory_page.tabs.setCurrentIndex(1)
    
    def on_table_double_click(self, row, column):
        date_item = self.table_widget.table.item(row, 0)
        if date_item:
            from_date = date_item.text()
            to_date = from_date
            QMessageBox.information(self, "Daily Detail", f"Details for {from_date}")
    
    # ============================================================
    # ✅ UPDATE METHODS - WITH K, M, B FORMATTING
    # ============================================================
    
    def update_kpi_cards(self):
        today = QDate.currentDate().toString("yyyy-MM-dd")
        symbol = self._get_currency_symbol()
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(SUM(si.qty * si.price), 0) as gross_sales,
                COALESCE(SUM(COALESCE(s.discount_amount, 0)), 0) as total_discount
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'completed' AND date(s.created_at) = ?
        """, (today,))
        row = cursor.fetchone()
        gross_sales = row[0] if row else 0
        total_discount = row[1] if row else 0
        today_sales = gross_sales - total_discount
        
        self._update_card_value(self.today_sales_card, today_sales, symbol, True, "#2ecc71")
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses 
            WHERE expense_date = ?
        """, (today,))
        today_expense = cursor.fetchone()[0]
        self._update_card_value(self.today_expense_card, today_expense, symbol, True, "#e74c3c")
        
        today_profit = today_sales - today_expense
        profit_color = "#2ecc71" if today_profit >= 0 else "#e74c3c"
        self._update_card_value(self.today_profit_card, today_profit, symbol, True, profit_color)
        
        cursor.execute("""
            SELECT COALESCE(SUM(si.qty * si.price), 0)
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'refunded' AND date(s.created_at) = ?
        """, (today,))
        today_refunds = cursor.fetchone()[0]
        refunds_color = "#e74c3c" if today_refunds > 0 else "#2ecc71"
        self._update_card_value(self.today_refunds_card, today_refunds, symbol, True, refunds_color)
        
        cursor.execute("""
            SELECT COALESCE(SUM(discount_amount), 0) FROM sales 
            WHERE status = 'completed' AND discount_amount > 0 AND date(created_at) = ?
        """, (today,))
        today_discount = cursor.fetchone()[0]
        discount_color = "#f39c12" if today_discount > 0 else "#2ecc71"
        self._update_card_value(self.today_discount_card, today_discount, symbol, True, discount_color)
        
        conn.close()
    
    def update_financial_cards(self, from_date, to_date):
        symbol = self._get_currency_symbol()
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COALESCE(SUM(si.qty * si.price), 0)
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'completed' AND date(s.created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        gross_sales = cursor.fetchone()[0]
        self._update_card_value(self.gross_sales_card, gross_sales, symbol, True, "#3498db")
        
        cursor.execute("""
            SELECT COALESCE(SUM(si.qty * si.price), 0)
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'refunded' AND date(s.created_at) BETWEEN ? AND ?
        """, (from_date, to_date))
        refunds = cursor.fetchone()[0]
        
        net_sales = gross_sales - refunds
        self._update_card_value(self.net_sales_card, net_sales, symbol, True, "#3498db")
        
        cursor.execute("""
            SELECT COALESCE(SUM(products.cost * sale_items.qty), 0)
            FROM sale_items
            JOIN products ON sale_items.product_id = products.id OR (sale_items.product_id IS NULL AND sale_items.product_name = products.name)
            JOIN sales ON sale_items.sale_id = sales.id
            WHERE sales.status='completed' 
              AND date(sales.created_at) BETWEEN ? AND ?
              AND (products.sold_by IS NULL OR products.sold_by != 'Service')
        """, (from_date, to_date))
        cogs = cursor.fetchone()[0]
        
        gross_profit = net_sales - cogs
        profit_color = "#2ecc71" if gross_profit >= 0 else "#e74c3c"
        self._update_card_value(self.gross_profit_card, gross_profit, symbol, True, profit_color)
        
        cursor.execute("""
            WITH customer_debt AS (
                SELECT
                    COALESCE(c.current_balance, 0) AS current_balance,
                    COALESCE((
                        SELECT SUM(cs.balance_amount)
                        FROM credit_sales cs
                        WHERE cs.customer_id = c.id
                          AND cs.balance_amount > 0
                          AND LOWER(COALESCE(cs.status, '')) != 'refunded'
                    ), 0) AS credit_sales_balance
                FROM customers c
                WHERE COALESCE(c.current_balance, 0) > 0
                   OR EXISTS (
                       SELECT 1
                       FROM credit_sales cs
                       WHERE cs.customer_id = c.id
                         AND cs.balance_amount > 0
                         AND LOWER(COALESCE(cs.status, '')) != 'refunded'
                   )
            )
            SELECT COALESCE(SUM(
                CASE
                    WHEN current_balance > credit_sales_balance THEN current_balance
                    ELSE credit_sales_balance
                END
            ), 0)
            FROM customer_debt
        """)
        outstanding = cursor.fetchone()[0]
        outstanding_color = "#e74c3c" if outstanding > 0 else "#2ecc71"
        self._update_card_value(self.outstanding_card, outstanding, symbol, True, outstanding_color)
        
        cursor.execute("""
            SELECT COUNT(*) FROM products 
            WHERE (sold_by IS NULL OR sold_by != 'Service') 
              AND stock > 0 AND stock <= low_stock
        """)
        low_stock_count = cursor.fetchone()[0]
        stock_color = "#f39c12" if low_stock_count > 0 else "#2ecc71"
        self._update_card_value(self.low_stock_card, low_stock_count, None, False, stock_color)
        
        conn.close()
    
    def _get_currency_symbol(self):
        try:
            from utils.currency import get_currency_symbol
            return get_currency_symbol()
        except:
            return "Ks"
    
    def refresh_dashboard(self):
        from_date, to_date = self.date_range.get_from_date(), self.date_range.get_to_date()
        
        self.update_kpi_cards()
        self.update_financial_cards(from_date, to_date)
        self.update_backup_status()
        self.table_widget.populate(from_date, to_date)
        
        if hasattr(self, 'ai_assistant') and self.isVisible():
            self.ai_assistant.load_insights()
    
    def update_backup_status(self):
        main_window = self.window()
        if hasattr(main_window, 'auto_backup_manager'):
            DashboardBackupStatus.update_backup_status(self, main_window.auto_backup_manager)
    
    def open_backup_settings(self, event):
        main_window = self.window()
        if hasattr(main_window, 'open_auto_backup'):
            main_window.open_auto_backup()
    
    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    def retranslateUi(self):
        lang_code = self.get_lang()
        self.date_range.retranslateUi(lang_code)
        
        if lang_code == "my":
            self.today_sales_card.set_title("ယနေ့ရောင်းအား (အသားတင်)")
            self.today_expense_card.set_title("ယနေ့အသုံးစရိတ်")
            self.today_profit_card.set_title("ယနေ့အမြတ်")
            self.today_refunds_card.set_title("ယနေ့ပြန်အမ်းငွေ")
            self.today_discount_card.set_title("ယနေ့လျှော့စျေး")
            self.outstanding_card.set_title("ကျန်အကြွေး")
            self.low_stock_card.set_title("စတော့နည်းနေသောပစ္စည်း")
            self.gross_sales_card.set_title("စုစုပေါင်းရောင်းအား")
            self.net_sales_card.set_title("အသားတင်ရောင်းအား")
            self.gross_profit_card.set_title("အသားတင်အမြတ်")
            
            headers = ["ရက်စွဲ", "စုစုပေါင်းရောင်းအား", "အသားတင်ရောင်းအား",
                       "အသားတင်အမြတ်", "ပြန်အမ်းငွေများ", "လျှော့စျေး"]
        else:
            self.today_sales_card.set_title("Today's Sales (Net)")
            self.today_expense_card.set_title("Today's Expense")
            self.today_profit_card.set_title("Today's Profit")
            self.today_refunds_card.set_title("Today Refunds")
            self.today_discount_card.set_title("Today Discount")
            self.outstanding_card.set_title("Outstanding Credit")
            self.low_stock_card.set_title("Low Stock Count")
            self.gross_sales_card.set_title("Gross Sales")
            self.net_sales_card.set_title("Net Sales")
            self.gross_profit_card.set_title("Gross Profit")
            
            headers = ["Date", "Gross Sales", "Net Sales", "Gross Profit", "Refunds", "Discount"]
        
        self.table_widget.table.setHorizontalHeaderLabels(headers)
        
        from_date, to_date = self.date_range.get_from_date(), self.date_range.get_to_date()
        self.table_widget.populate(from_date, to_date)
        self.update_kpi_cards()
        self.update_financial_cards(from_date, to_date)
        self.update_backup_status()
        
        if hasattr(self, 'ai_assistant') and self.isVisible():
            self.ai_assistant.load_insights()
    
    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_dashboard()
