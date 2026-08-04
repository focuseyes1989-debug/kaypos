# ui/reports/base_report_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QDateEdit, QMessageBox, QFileDialog, QProgressBar,
    QTabWidget, QWidget, QFrame, QTableWidget, QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QThread, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets import (
    DateRangeWidget,
    ToastNotificationWidget,
    LoadingSpinnerWidget,
    SummaryCardWidget
)
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors
from datetime import datetime
from loguru import logger
import csv
import os


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(dict)


class BaseReportWorker(QObject):
    """Base worker for report generation"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(dict)
    
    def __init__(self, from_date, to_date):
        super().__init__()
        self.from_date = from_date
        self.to_date = to_date
    
    def run(self):
        raise NotImplementedError("Subclasses must implement run()")


class BaseReportDialog(QDialog):
    """Base class for all report dialogs - Theme-aware with SVG Icons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1000, 700)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setModal(True)
        self._is_dark = is_dark_theme()
        
        # Thread management
        self.threads = []
        self.workers = []
        
        # Main layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        
        # ========== Date Range and Export Button Row ==========
        date_export_layout = QHBoxLayout()
        date_export_layout.setSpacing(10)
        
        # DateRangeWidget
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.on_date_range_changed)
        date_export_layout.addWidget(self.date_range, 1)
        
        # ✅ Export button with SVG icon
        self.btn_export = ModernButton(" Export Excel", ModernButton.PRIMARY)
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_export.set_compact(False)
        self.btn_export.clicked.connect(self.export_current_report)
        date_export_layout.addWidget(self.btn_export)
        
        # ✅ Refresh button with SVG icon
        self.btn_refresh = ModernButton(" Refresh", ModernButton.SECONDARY)
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_refresh.set_compact(False)
        self.btn_refresh.clicked.connect(self.refresh_current_tab)
        date_export_layout.addWidget(self.btn_refresh)
        
        self.main_layout.addLayout(date_export_layout)
        
        # ========== Action Buttons ==========
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        # Close button with SVG icon
        self.btn_close = ModernButton(" Close", ModernButton.TERTIARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        btn_layout.addStretch()
        self.main_layout.addLayout(btn_layout)
        
        # ========== Loading Spinner ==========
        self.spinner = LoadingSpinnerWidget("Loading...")
        self.spinner.hide()
        self.main_layout.addWidget(self.spinner)
        
        # ========== Toast Notification ==========
        self.toast = ToastNotificationWidget(self)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Setup tabs
        self.setup_tabs()
        
        self.setLayout(self.main_layout)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self.on_theme_changed)
        
        # Apply initial theme
        self._apply_theme()
        
        # Refresh current tab after dialog is shown
        QTimer.singleShot(100, self.refresh_current_tab)
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update tab widget style
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
            """)
    
    def on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_close.set_icon("close", size=(16, 16))
    
    def on_date_range_changed(self, from_date, to_date):
        """Handle date range change - auto refresh"""
        self.refresh_current_tab()
    
    def get_date_range(self):
        """Get date range from DateRangeWidget"""
        return self.date_range.get_from_date(), self.date_range.get_to_date()
    
    def get_theme(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except:
            return "Light"
    
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
    
    def get_currency_symbol(self):
        return get_currency_symbol()
    
    # Summary Card ကို ဖန်တီးရန် နည်းလမ်းသစ် (with SVG icon support)
    def create_summary_card(self, title, value="0", icon="", color="#3498db", icon_is_svg=False):
        """Create a SummaryCardWidget with gradient design"""
        card = SummaryCardWidget(
            title=title,
            value=value,
            icon=icon,
            color=color,
            icon_is_svg=icon_is_svg
        )
        # Set SVG icon if provided
        if icon_is_svg and icon:
            card.set_icon(icon, is_svg=True, size=(24, 24))
        
        # Compact size
        card.card.setFixedHeight(85)
        card.card.setMinimumWidth(130)
        return card
    
    def update_summary_card(self, card, value, symbol=None):
        """Update SummaryCardWidget value"""
        if symbol:
            card.set_value(format_money(value, symbol))
        else:
            card.set_value(str(value))
    
    def set_buttons_enabled(self, enabled):
        self.btn_export.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
        self.btn_close.setEnabled(enabled)
    
    def cleanup_threads(self):
        for thread in self.threads[:]:
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(2000)
            except (RuntimeError, AttributeError):
                pass
        self.threads.clear()
        self.workers.clear()
    
    def closeEvent(self, event):
        self.cleanup_threads()
        event.accept()
    
    def showEvent(self, event):
        super().showEvent(event)
        # Update button icons when shown
        self._update_button_icons()
    
    def setup_tabs(self):
        """Override this method to add tabs"""
        pass
    
    def refresh_current_tab(self):
        """Override this method to refresh current tab"""
        pass
    
    def export_current_report(self):
        """Override this method to export current report"""
        pass
    
    def retranslateUi(self):
        """Override this method to update UI text when language changes"""
        pass