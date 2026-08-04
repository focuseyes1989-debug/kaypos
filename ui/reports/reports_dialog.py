# ui/reports/reports_dialog.py
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from ui.reports.base_report_dialog import BaseReportDialog
from ui.reports.sales_report import SalesReportTab
from ui.reports.expense_report import ExpenseReportTab
from ui.reports.profit_loss_report import ProfitLossReportTab
from ui.reports.financial_summary import FinancialSummaryTab
from ui.themes.theme_manager import theme_manager, is_dark_theme
from utils.language import lang
from loguru import logger
import os


class ReportsDialog(BaseReportDialog):
    def __init__(self, parent=None):
        self.current_tab = 0
        self._is_loading = False
        self._pending_refresh = False
        self._default_tab_index = 0
        self._is_dark = is_dark_theme()
        
        # ✅ Tab icons mapping - Must be defined before super().__init__()
        self.tab_icons = {
            0: "bar_chart",      # Sales Report - bar_chart.svg
            1: "money_off",      # Expense Report - money_off.svg
            2: "analytics",      # Profit & Loss - analytics.svg
            3: "dashboard"       # Financial Summary - dashboard.svg
        }
        
        super().__init__(parent)
        self.setWindowTitle("Reports")
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self.retranslateUi()
        lang.language_changed.connect(self.retranslateUi)
        
        # Setup tabs after everything is initialized
        QTimer.singleShot(100, self._init_tabs)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._update_tab_icons()
        self._apply_tab_bar_style()
    
    def _apply_tab_bar_style(self):
        """Apply tab bar style based on theme"""
        is_dark = is_dark_theme()
        
        if is_dark:
            self.tabs.setStyleSheet("""
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
            self.tabs.setStyleSheet("""
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
    
    def _load_colored_tab_icon(self, index):
        """Load SVG icon with color based on theme for tabs"""
        icon_name = self.tab_icons.get(index, "")
        if not icon_name:
            return QIcon()
        
        is_dark = is_dark_theme()
        color_hex = "#ffffff" if is_dark else "#495057"
        
        # Try SVG first, then PNG
        paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for path in paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        # Scale to 20x20 for tab icon
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Color the icon based on theme
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        
                        return QIcon(colored)
                except Exception as e:
                    print(f"Could not load icon {path}: {e}")
        
        return QIcon()
    
    def _update_tab_icons(self):
        """Update all tab icons color based on theme"""
        for index in range(self.tabs.count()):
            icon = self._load_colored_tab_icon(index)
            self.tabs.setTabIcon(index, icon)
    
    def _init_tabs(self):
        """Initialize tabs after dialog is shown"""
        from_date, to_date = self.get_date_range()
        self.set_buttons_enabled(False)
        
        # Load all tabs in background
        self.sales_tab.refresh(from_date, to_date)
        self.expense_tab.refresh(from_date, to_date)
        self.pl_tab.refresh(from_date, to_date)
        self.summary_tab.refresh(from_date, to_date)
        
        # Update tab icons
        self._update_tab_icons()
        
        # Check if all loaded after 500ms
        QTimer.singleShot(500, self._check_all_loaded)
    
    def _check_all_loaded(self):
        """Check if all tabs are loaded"""
        loading = False
        for tab in [self.sales_tab, self.expense_tab, self.pl_tab, self.summary_tab]:
            if hasattr(tab, '_is_loading') and tab._is_loading:
                loading = True
                break
        
        if not loading:
            self.set_buttons_enabled(True)
            
            if self._default_tab_index > 0:
                self.tabs.setCurrentIndex(self._default_tab_index)
        else:
            QTimer.singleShot(500, self._check_all_loaded)
    
    def setup_tabs(self):
        """Setup tabs - called by base class"""
        self.sales_tab = SalesReportTab(self)
        self.tabs.addTab(self.sales_tab, self._load_colored_tab_icon(0), "Sales Report")
        
        self.expense_tab = ExpenseReportTab(self)
        self.tabs.addTab(self.expense_tab, self._load_colored_tab_icon(1), "Expense Report")
        
        self.pl_tab = ProfitLossReportTab(self)
        self.tabs.addTab(self.pl_tab, self._load_colored_tab_icon(2), "Profit & Loss")
        
        self.summary_tab = FinancialSummaryTab(self)
        self.tabs.addTab(self.summary_tab, self._load_colored_tab_icon(3), "Financial Summary")
        
        self.tabs.currentChanged.connect(self.on_tab_changed_debounced)
        
        # Apply tab bar style
        self._apply_tab_bar_style()
    
    def set_default_tab(self, index):
        """Set default tab index"""
        self._default_tab_index = index
        if hasattr(self, 'tabs') and self.tabs.count() > index:
            self.tabs.setCurrentIndex(index)
    
    def on_tab_changed_debounced(self, index):
        """Handle tab change with debounce"""
        if self._is_loading:
            return
        
        self.current_tab = index
        QTimer.singleShot(50, self._refresh_current_tab_safe)
    
    def _refresh_current_tab_safe(self):
        """Refresh current tab safely"""
        if self._is_loading:
            return
        
        self._is_loading = True
        self._pending_refresh = False
        
        from_date, to_date = self.get_date_range()
        current_index = self.tabs.currentIndex()
        
        if current_index == 0:
            if self.sales_tab.table.rowCount() == 0:
                self.sales_tab.refresh(from_date, to_date)
            else:
                self._is_loading = False
                self.set_buttons_enabled(True)
        elif current_index == 1:
            if self.expense_tab.table.rowCount() == 0:
                self.expense_tab.refresh(from_date, to_date)
            else:
                self._is_loading = False
                self.set_buttons_enabled(True)
        elif current_index == 2:
            if self.pl_tab.table.rowCount() == 0:
                self.pl_tab.refresh(from_date, to_date)
            else:
                self._is_loading = False
                self.set_buttons_enabled(True)
        elif current_index == 3:
            if self.summary_tab.sales_category_table.rowCount() == 0:
                self.summary_tab.refresh(from_date, to_date)
            else:
                self._is_loading = False
                self.set_buttons_enabled(True)
    
    def refresh_current_tab(self):
        """Force refresh current tab"""
        if self._is_loading:
            self._pending_refresh = True
            return
        
        self.set_buttons_enabled(False)
        from_date, to_date = self.get_date_range()
        current_index = self.tabs.currentIndex()
        
        self._is_loading = True
        
        if current_index == 0:
            self.sales_tab.refresh(from_date, to_date)
        elif current_index == 1:
            self.expense_tab.refresh(from_date, to_date)
        elif current_index == 2:
            self.pl_tab.refresh(from_date, to_date)
        elif current_index == 3:
            self.summary_tab.refresh(from_date, to_date)
    
    def export_current_report(self):
        from_date, to_date = self.get_date_range()
        current_index = self.tabs.currentIndex()
        
        if current_index == 0:
            self.sales_tab.export(from_date, to_date)
        elif current_index == 1:
            self.expense_tab.export(from_date, to_date)
        elif current_index == 2:
            self.pl_tab.export(from_date, to_date)
        elif current_index == 3:
            self.summary_tab.export(from_date, to_date)
    
    def on_refresh_complete(self):
        """Called when a tab finishes refreshing"""
        self._is_loading = False
        
        loading = False
        for tab in [self.sales_tab, self.expense_tab, self.pl_tab, self.summary_tab]:
            if hasattr(tab, '_is_loading') and tab._is_loading:
                loading = True
                break
        
        if not loading:
            self.set_buttons_enabled(True)
            
            if self._pending_refresh:
                self._pending_refresh = False
                QTimer.singleShot(100, self.refresh_current_tab)
    
    def on_refresh_error(self, error_msg):
        logger.error(f"Report error: {error_msg}")
        QMessageBox.warning(self, "Error", f"Failed to load report: {error_msg}")
        self._is_loading = False
        self.set_buttons_enabled(True)
    
    def retranslateUi(self):
        lang = self.get_lang()
        
        # Update button texts
        if lang == "my":
            self.setWindowTitle("အစီရင်ခံစာများ")
            self.btn_export.setText(" Excel ထုတ်မည်")
            self.btn_close.setText(" ပိတ်မည်")
            self.btn_refresh.setText(" ပြန်လည်")
            
            if self.tabs.count() > 0:
                self.tabs.setTabText(0, "ရောင်းအားအစီရင်ခံစာ")
                self.tabs.setTabText(1, "အသုံးစရိတ်အစီရင်ခံစာ")
                self.tabs.setTabText(2, "အမြတ်အစွန်းအစီရင်ခံစာ")
                self.tabs.setTabText(3, "ဘဏ္ဍာရေးအကျဉ်းချုပ်")
        else:
            self.setWindowTitle("Reports")
            self.btn_export.setText(" Export Excel")
            self.btn_close.setText(" Close")
            self.btn_refresh.setText(" Refresh")
            
            if self.tabs.count() > 0:
                self.tabs.setTabText(0, "Sales Report")
                self.tabs.setTabText(1, "Expense Report")
                self.tabs.setTabText(2, "Profit & Loss")
                self.tabs.setTabText(3, "Financial Summary")
        
        # Update button icons
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_close.set_icon("close", size=(16, 16))
        
        # Update tab icons after language change
        self._update_tab_icons()
        self._apply_tab_bar_style()
        
        # Retranslate tab content
        if hasattr(self, 'sales_tab') and hasattr(self.sales_tab, 'retranslateUi'):
            self.sales_tab.retranslateUi()
        if hasattr(self, 'expense_tab') and hasattr(self.expense_tab, 'retranslateUi'):
            self.expense_tab.retranslateUi()
        if hasattr(self, 'pl_tab') and hasattr(self.pl_tab, 'retranslateUi'):
            self.pl_tab.retranslateUi()
        if hasattr(self, 'summary_tab') and hasattr(self.summary_tab, 'retranslateUi'):
            self.summary_tab.retranslateUi()
    
    def showEvent(self, event):
        """Handle show event - update tab icons"""
        self._update_tab_icons()
        self._apply_tab_bar_style()
        super().showEvent(event)