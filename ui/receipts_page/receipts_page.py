# ui/receipts_page/receipts_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QMessageBox, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QIcon, QPainter
from ui.receipts_page.receipts_tab import ReceiptsTab
from ui.receipts_page.refund_tab import RefundTab
from ui.receipts_page.discount_tab import DiscountTab
from ui.receipts_page.credit_tab import CreditTab
from utils.permissions import PermissionManager, Permission
from utils.language import lang
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.widgets.date_range_widget import DateRangeWidget
from ui.widgets.toast_notification_widget import ToastNotificationWidget
from ui.widgets.modern_button import ModernButton
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from loguru import logger
import os


class ReceiptsPage(QWidget):
    """Receipts Page - Sales Summary Style Design with SVG Icons"""
    
    date_range_changed = pyqtSignal(str, str)
    
    def __init__(self, user_id=None, user_role=None, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_role = user_role
        self._is_dark = is_dark_theme()
        
        self._tab_icons = {}
        self._current_from_date = None
        self._current_to_date = None
        
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.toast = ToastNotificationWidget(self)

        # ========== Filter Row ==========
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.on_date_range_changed)
        filter_layout.addWidget(self.date_range)

        filter_layout.addStretch()
        
        self.btn_export_excel = ModernButton(" Export Excel", ModernButton.PRIMARY)
        self.btn_export_excel.set_icon("file_export", size=(16, 16))
        self.btn_export_excel.set_compact(False)
        self.btn_export_excel.clicked.connect(self.export_all_tabs)
        filter_layout.addWidget(self.btn_export_excel)

        main_layout.addLayout(filter_layout)

        # ========== Summary Cards ==========
        card_layout = QHBoxLayout()
        card_layout.setSpacing(12)

        self.total_receipts_card = SummaryCardWidget(
            title="Total Receipts",
            value="0",
            icon="receipt",
            color="#3498db",
            icon_is_svg=True
        )
        card_layout.addWidget(self.total_receipts_card)

        self.total_sales_card = SummaryCardWidget(
            title="Total Sales",
            value="0",
            icon="attach_money",
            color="#2ecc71",
            icon_is_svg=True
        )
        card_layout.addWidget(self.total_sales_card)

        self.total_discount_card = SummaryCardWidget(
            title="Total Discount",
            value="0",
            icon="percent_discount",
            color="#e74c3c",
            icon_is_svg=True
        )
        card_layout.addWidget(self.total_discount_card)

        self.total_refund_card = SummaryCardWidget(
            title="Total Refund",
            value="0",
            icon="swap_horiz",
            color="#f39c12",
            icon_is_svg=True
        )
        card_layout.addWidget(self.total_refund_card)

        self.total_credit_card = SummaryCardWidget(
            title="Total Credit",
            value="0",
            icon="credit_card",
            color="#9b59b6",
            icon_is_svg=True
        )
        card_layout.addWidget(self.total_credit_card)

        card_layout.addStretch()
        main_layout.addLayout(card_layout)

        # ========== Tabs ==========
        self.tab_widget = QTabWidget()
        
        self.tab_names = {
            0: "Receipts",
            1: "Refunded",
            2: "Discounted",
            3: "Credit"
        }
        
        self.tab_icons = {
            0: "receipt",
            1: "swap_horiz",
            2: "percent_discount",
            3: "credit_card"
        }
        
        self.receipts_tab = ReceiptsTab(user_id, user_role, self)
        self.refund_tab = RefundTab(user_id, user_role, self)
        self.discount_tab = DiscountTab(user_id, user_role, self)
        self.credit_tab = CreditTab(user_id, user_role, self)
        
        self._setup_tabs()
        self._update_tab_widget_style()
        self.apply_permissions()
        
        main_layout.addWidget(self.tab_widget)

        self.setLayout(main_layout)

        lang.language_changed.connect(self.retranslateUi)
        theme_manager.theme_changed.connect(self.on_theme_changed)
        
        self.load_all_tabs()
        self.retranslateUi()
    
    def _setup_tabs(self):
        self.tab_widget.addTab(self.receipts_tab, "Receipts")
        self.tab_widget.addTab(self.refund_tab, "Refunded")
        self.tab_widget.addTab(self.discount_tab, "Discounted")
        self.tab_widget.addTab(self.credit_tab, "Credit")
        self._update_tab_icons()
    
    def _get_theme_icon_color(self):
        return "#b9bbbe" if self._is_dark else "#495057"
    
    def _load_svg_icon(self, icon_name, color_hex=None):
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        20, 20,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    if color_hex:
                        colored_pixmap = self._recolor_pixmap(scaled, color_hex)
                        if colored_pixmap:
                            return QIcon(colored_pixmap)
                    return QIcon(scaled)
            except Exception as e:
                logger.debug(f"Could not load SVG {svg_path}: {e}")
        
        png_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(png_path):
            try:
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        20, 20,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    if color_hex:
                        colored_pixmap = self._recolor_pixmap(scaled, color_hex)
                        if colored_pixmap:
                            return QIcon(colored_pixmap)
                    return QIcon(scaled)
            except Exception as e:
                logger.debug(f"Could not load PNG {png_path}: {e}")
        
        return None
    
    def _recolor_pixmap(self, pixmap, color_hex):
        try:
            if pixmap.isNull():
                return None
            colored = pixmap.copy()
            painter = QPainter(colored)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(colored.rect(), QColor(color_hex))
            painter.end()
            return colored
        except Exception as e:
            logger.debug(f"Could not recolor icon: {e}")
            return None
    
    def _update_tab_icons(self):
        icon_color = self._get_theme_icon_color()
        for idx, icon_name in enumerate(["receipt", "swap_horiz", "percent_discount", "credit_card"]):
            icon = self._load_svg_icon(icon_name, icon_color)
            if icon:
                self.tab_widget.setTabIcon(idx, icon)
    
    def _update_tab_widget_style(self):
        is_dark = is_dark_theme()
        
        if is_dark:
            self.tab_widget.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    background-color: #2f3136;
                }
                QTabBar::tab {
                    background-color: #2f3136;
                    color: #b9bbbe;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border: none;
                }
                QTabBar::tab:selected {
                    background-color: #40444b;
                    color: #ffffff;
                }
                QTabBar::tab:hover {
                    background-color: #36393f;
                    color: #ffffff;
                }
                QTabBar::tab:!selected {
                    background-color: #202225;
                    color: #72767d;
                }
                QTabBar::tab QIcon {
                    margin-right: 6px;
                }
            """)
        else:
            self.tab_widget.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background-color: #f8f9fa;
                    color: #495057;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border: 1px solid #dee2e6;
                    border-bottom: none;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: #212529;
                    border-bottom: 2px solid #5865f2;
                }
                QTabBar::tab:hover {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QTabBar::tab QIcon {
                    margin-right: 6px;
                }
            """)
    
    def _on_theme_changed(self, theme_name):
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_tab_icons()
    
    def _apply_theme(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {colors['bg']};
            }}
        """)
        self._update_tab_widget_style()
    
    def on_theme_changed(self, theme_name):
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_tab_icons()
        self.update_card_theme()
        for tab in [self.receipts_tab, self.refund_tab, self.discount_tab, self.credit_tab]:
            if hasattr(tab, '_on_theme_changed'):
                tab._on_theme_changed(theme_name)
    
    def update_card_theme(self):
        for card in [self.total_receipts_card, self.total_sales_card, 
                     self.total_discount_card, self.total_refund_card,
                     self.total_credit_card]:
            if hasattr(card, 'update_theme'):
                card.update_theme()
    
    def on_date_range_changed(self, from_date, to_date):
        self._current_from_date = from_date
        self._current_to_date = to_date
        self.date_range_changed.emit(from_date, to_date)
        self.load_all_tabs()
    
    def apply_permissions(self):
        if self.user_id:
            if not PermissionManager.user_has_permission(self.user_id, Permission.REFUND_RECEIPT):
                index = self.tab_widget.indexOf(self.refund_tab)
                if index >= 0:
                    self.tab_widget.setTabEnabled(index, False)
            
            if not PermissionManager.user_has_permission(self.user_id, Permission.EDIT_SETTINGS):
                index = self.tab_widget.indexOf(self.discount_tab)
                if index >= 0:
                    self.tab_widget.setTabEnabled(index, False)
            
            if not PermissionManager.user_has_permission(self.user_id, Permission.VIEW_CREDIT):
                index = self.tab_widget.indexOf(self.credit_tab)
                if index >= 0:
                    self.tab_widget.setTabEnabled(index, False)
    
    def retranslateUi(self):
        lang_code = lang.get_current()
        
        self.date_range.retranslateUi(lang_code)
        self._update_tab_icons()
        
        if lang_code == "my":
            self.tab_widget.setTabText(0, "ပြေစာများ")
            self.tab_widget.setTabText(1, "ပြန်အမ်းပြီး")
            self.tab_widget.setTabText(2, "လျှော့စျေး")
            self.tab_widget.setTabText(3, "အကြွေး")
            
            self.total_receipts_card.set_title("စုစုပေါင်းပြေစာ")
            self.total_sales_card.set_title("စုစုပေါင်းရောင်းအား")
            self.total_discount_card.set_title("စုစုပေါင်းလျှော့စျေး")
            self.total_refund_card.set_title("စုစုပေါင်းပြန်အမ်း")
            self.total_credit_card.set_title("စုစုပေါင်းအကြွေး")
            self.btn_export_excel.setText(" Excel ထုတ်မည်")
        else:
            self.tab_widget.setTabText(0, "Receipts")
            self.tab_widget.setTabText(1, "Refunded")
            self.tab_widget.setTabText(2, "Discounted")
            self.tab_widget.setTabText(3, "Credit")
            
            self.total_receipts_card.set_title("Total Receipts")
            self.total_sales_card.set_title("Total Sales")
            self.total_discount_card.set_title("Total Discount")
            self.total_refund_card.set_title("Total Refund")
            self.total_credit_card.set_title("Total Credit")
            self.btn_export_excel.setText(" Export Excel")
        
        self.btn_export_excel.set_icon("file_export", size=(16, 16))
        
        if hasattr(self.receipts_tab, 'retranslateUi'):
            self.receipts_tab.retranslateUi()
        if hasattr(self.refund_tab, 'retranslateUi'):
            self.refund_tab.retranslateUi()
        if hasattr(self.discount_tab, 'retranslateUi'):
            self.discount_tab.retranslateUi()
        if hasattr(self.credit_tab, 'retranslateUi'):
            self.credit_tab.retranslateUi()
        
        self._apply_theme()
        self.load_all_tabs()
    
    # ============================================================
    # ✅ FIXED: update_summary_cards() - Using sale_items for totals
    # ============================================================
    def load_all_tabs(self):
        from_date, to_date = self.date_range.get_from_date(), self.date_range.get_to_date()
        
        self.receipts_tab.load_sales(from_date, to_date)
        self.refund_tab.load_refunded_sales(from_date, to_date)
        self.discount_tab.load_discounted_receipts(from_date, to_date)
        self.credit_tab.load_credit_receipts(from_date, to_date)
        
        self.update_summary_cards(from_date, to_date)
    
    def update_summary_cards(self, from_date, to_date):
        """Update summary cards - ✅ FIXED: Using sale_items for accurate totals"""
        try:
            symbol = get_currency_symbol()
            conn = connect_db()
            cursor = conn.cursor()
            
            # Total Receipts
            cursor.execute("""
                SELECT COUNT(*) 
                FROM sales 
                WHERE status = 'completed' 
                AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_receipts = cursor.fetchone()[0]
            
            # ✅ Total Sales - from sale_items (most accurate)
            cursor.execute("""
                SELECT COALESCE(SUM(si.qty * si.price), 0) 
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'completed' 
                AND date(s.created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_sales = cursor.fetchone()[0]
            
            # Total Discount
            cursor.execute("""
                SELECT COALESCE(SUM(discount_amount), 0) 
                FROM sales 
                WHERE status = 'completed' 
                AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_discount = cursor.fetchone()[0]
            
            # Total Refund
            cursor.execute("""
                SELECT COALESCE(SUM(total), 0) 
                FROM sales 
                WHERE status = 'refunded' 
                AND date(created_at) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_refund = cursor.fetchone()[0]
            
            # Total Credit
            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) 
                FROM credit_sales 
                WHERE date(sale_date) BETWEEN ? AND ?
            """, (from_date, to_date))
            total_credit = cursor.fetchone()[0]
            
            conn.close()
            
            self.total_receipts_card.set_value(str(total_receipts))
            self.total_sales_card.set_value(format_money(total_sales, symbol))
            self.total_discount_card.set_value(format_money(total_discount, symbol))
            self.total_refund_card.set_value(format_money(total_refund, symbol))
            self.total_credit_card.set_value(format_money(total_credit, symbol))
            
        except Exception as e:
            logger.error(f"Error updating summary cards: {e}")
    
    def get_current_date_range(self):
        return self.date_range.get_from_date(), self.date_range.get_to_date()
    
    def export_all_tabs(self):
        current_tab_index = self.tab_widget.currentIndex()
        
        if current_tab_index == 0:
            self.receipts_tab.export_receipt_list()
        elif current_tab_index == 1:
            self.refund_tab.export_to_excel()
        elif current_tab_index == 2:
            self.discount_tab.export_to_excel()
        elif current_tab_index == 3:
            self.credit_tab.export_to_excel()
    
    def refresh_all(self):
        self.load_all_tabs()
    
    def showEvent(self, event):
        super().showEvent(event)
        self.load_all_tabs()