# ui/dashboard/ai_assistant/widget.py
"""AI Assistant Widget - Main Class with ModernButton, ModernSearchWidget and SVG Icons"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QComboBox, QMessageBox, QFileDialog, QProgressBar, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor

from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors
from ui.widgets.modern_button import ModernButton
from ui.widgets.search_widget import ModernSearchWidget
from loguru import logger
from datetime import datetime

from .constants import (
    MYANMAR_TEXTS, DATE_RANGES, REFRESH_INTERVALS,
    DEFAULT_REFRESH_INTERVAL, NOTIFICATION_INTERVAL
)
from .utils import (
    get_date_range, get_date_range_days, format_trend, get_myanmar_text,
    get_themed_icon_helper, get_icon_pixmap
)
from .data_loader import (
    get_quick_stats, get_today_yesterday_sales, get_weekly_comparison,
    get_monthly_comparison, get_top_categories, get_top_products,
    get_payment_breakdown, get_stock_alert, get_peak_hour,
    get_repeat_customers, get_forecast
)
from .insight_builder import InsightBuilder
from .export_manager import export_report
from .styles import (
    get_widget_style, get_combo_style, get_progress_style,
    get_scroll_area_style, get_header_label_style,
    get_status_badge_style, get_last_updated_style,
    get_control_label_style, get_control_container_style,
    get_tab_style
)
# ✅ Import chart tab
from .chart_tab import ChartTab


class AIAssistantWidget(QFrame):
    """AI အကြံပြုချက်များ - Advanced Analytics with Auto-Refresh"""
    
    insight_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    # ✅ Tab configuration with SVG icons
    TAB_ICONS = {
        0: "bar_chart",      # Insights
        1: "analytics",      # Charts
        2: "settings"        # Settings
    }
    
    TAB_NAMES = {
        0: "Insights",
        1: "Charts",
        2: "Settings"
    }
    
    TAB_NAMES_MY = {
        0: "ထိုးထွင်းသိမြင်မှုများ",
        1: "ဇယားများ",
        2: "ပြင်ဆင်မှုများ"
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        self._refresh_interval = DEFAULT_REFRESH_INTERVAL
        self._is_loading = False
        self._current_date_range = "Today"
        self._search_text = ""
        self._is_closing = False
        self._has_loaded_once = False
        
        self._insight_builder = InsightBuilder(self._is_dark)
        self._setup_ui()
        self._apply_style()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_insights)
        
        # Notification timer
        self._notification_timer = QTimer(self)
        self._notification_timer.timeout.connect(self._check_notifications)
        
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def closeEvent(self, event):
        self._is_closing = True
        if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
            self.refresh_timer.stop()
        if self._notification_timer.isActive():
            self._notification_timer.stop()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(self._refresh_interval)
        if not self._notification_timer.isActive():
            self._notification_timer.start(NOTIFICATION_INTERVAL)
        if not self._has_loaded_once:
            self._has_loaded_once = True
            QTimer.singleShot(100, self._load_with_animation)

    def hideEvent(self, event):
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        if self._notification_timer.isActive():
            self._notification_timer.stop()
        super().hideEvent(event)
    
    # ============================================================
    # UI SETUP
    # ============================================================
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        
        # ============ HEADER ============
        self._setup_header(layout)
        
        # ============ TOP CONTROL BAR ============
        self._setup_top_controls(layout)
        
        # ============ PROGRESS BAR ============
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setStyleSheet(get_progress_style())
        layout.addWidget(self.progress_bar)
        
        # ============ TAB WIDGET ============
        self._setup_tabs(layout)
        
        # ============ BOTTOM CONTROL BAR ============
        self._setup_bottom_controls(layout)
        
        self.setLayout(layout)
        self._update_ui_colors()
    
    def _setup_header(self, layout):
        """Header with title and status badge only"""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title with SVG icon
        title_icon = get_themed_icon_helper("smart_toy", 20, self._is_dark)
        if title_icon:
            title_icon_label = QLabel()
            title_icon_label.setPixmap(title_icon)
            title_icon_label.setFixedSize(22, 22)
            title_icon_label.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(title_icon_label)
        
        self.title_label = QLabel("AI Assistant")
        self.title_label.setObjectName("title_label")
        header_layout.addWidget(self.title_label)
        
        # Status badge
        self.status_badge = QLabel("● Live")
        header_layout.addWidget(self.status_badge)
        
        # Last updated label
        self.last_updated_label = QLabel("")
        header_layout.addWidget(self.last_updated_label)
        
        header_layout.addStretch()
        layout.addWidget(header_widget)
    
    def _setup_top_controls(self, layout):
        """Top control bar: Date Range + Refresh Interval with SVG icons"""
        control_widget = QWidget()
        control_widget.setStyleSheet(get_control_container_style())
        control_layout = QHBoxLayout(control_widget)
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(0, 4, 0, 4)
        
        # Date Range - with calendar SVG icon
        date_icon = get_themed_icon_helper("calendar", 16, self._is_dark)
        if date_icon:
            date_icon_label = QLabel()
            date_icon_label.setPixmap(date_icon)
            date_icon_label.setFixedSize(18, 18)
            date_icon_label.setStyleSheet("background: transparent; border: none;")
            control_layout.addWidget(date_icon_label)
        
        date_label = QLabel("Period:")
        date_label.setStyleSheet(get_control_label_style(self._is_dark))
        control_layout.addWidget(date_label)
        
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(DATE_RANGES)
        self.date_range_combo.setCurrentText("Today")
        self.date_range_combo.currentTextChanged.connect(self._on_date_range_changed)
        self.date_range_combo.setFixedWidth(150)
        control_layout.addWidget(self.date_range_combo)
        
        control_layout.addStretch()
        
        # Refresh Interval - with clock SVG icon
        interval_icon = get_themed_icon_helper("clock", 16, self._is_dark)
        if interval_icon:
            interval_icon_label = QLabel()
            interval_icon_label.setPixmap(interval_icon)
            interval_icon_label.setFixedSize(18, 18)
            interval_icon_label.setStyleSheet("background: transparent; border: none;")
            control_layout.addWidget(interval_icon_label)
        
        interval_label = QLabel("Auto-refresh:")
        interval_label.setStyleSheet(get_control_label_style(self._is_dark))
        control_layout.addWidget(interval_label)
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(REFRESH_INTERVALS)
        self.interval_combo.setCurrentText("60s")
        self.interval_combo.currentTextChanged.connect(self._on_refresh_interval_changed)
        self.interval_combo.setFixedWidth(75)
        control_layout.addWidget(self.interval_combo)
        
        layout.addWidget(control_widget)
    
    def _setup_bottom_controls(self, layout):
        """Bottom control bar: Search + Export with SVG icons"""
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(0, 4, 0, 0)
        
        # ModernSearchWidget - uses search.svg from assets/icons
        self.search_widget = ModernSearchWidget(
            placeholder="Search products, categories, insights..."
        )
        self.search_widget.search_changed.connect(self._on_search_changed)
        self.search_widget.search_cleared.connect(self._on_search_cleared)
        control_layout.addWidget(self.search_widget, 1)
        
        # ModernButton with file_export.svg from assets/icons
        self.export_btn = ModernButton("Export", ModernButton.PRIMARY)
        self.export_btn.set_compact(False)
        self.export_btn.set_icon("file_export", size=(16, 16))
        self.export_btn.setFixedHeight(30)
        self.export_btn.setFixedWidth(100)
        self.export_btn.clicked.connect(self._export_report)
        control_layout.addWidget(self.export_btn)
        
        control_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(control_layout)
    
    def _setup_tabs(self, layout):
        """Tab widget with SVG icons - Sales Summary style"""
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(get_tab_style())
        
        # ========== Tab 1: Insights ==========
        self.main_tab = QWidget()
        main_tab_layout = QVBoxLayout(self.main_tab)
        main_tab_layout.setContentsMargins(0, 4, 0, 4)
        main_tab_layout.setSpacing(8)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet(get_scroll_area_style())
        
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(0, 4, 0, 4)
        self.content_layout.addStretch()
        
        self.scroll.setWidget(self.content)
        main_tab_layout.addWidget(self.scroll)
        
        # ✅ Add tab with SVG icon
        self.tab_widget.addTab(self.main_tab, self._load_colored_tab_icon(0), self.TAB_NAMES[0])
        
        # ========== Tab 2: Charts ==========
        # ✅ Use ChartTab instead of placeholder
        self.charts_tab = ChartTab(self)
        self.tab_widget.addTab(self.charts_tab, self._load_colored_tab_icon(1), self.TAB_NAMES[1])
        
        # ========== Tab 3: Settings (placeholder) ==========
        self.settings_tab = QWidget()
        settings_layout = QVBoxLayout(self.settings_tab)
        settings_label = QLabel("⚙️ Settings coming soon...")
        settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_label.setStyleSheet("font-size: 12pt; color: #6c757d;")
        settings_layout.addWidget(settings_label)
        
        self.tab_widget.addTab(self.settings_tab, self._load_colored_tab_icon(2), self.TAB_NAMES[2])
        
        # ✅ Apply tab bar style
        self._apply_tab_bar_style()
        
        layout.addWidget(self.tab_widget)
    
    def _apply_tab_bar_style(self):
        """Apply tab bar style based on theme - Sales Summary style"""
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
                QTabBar::tab:selected QLabel {
                    color: #ffffff;
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
                QTabBar::tab:selected QLabel {
                    color: #212529;
                }
            """)
        
        self._update_tab_icons_color()
    
    def _update_tab_icons_color(self):
        """Update all tab icons color based on theme"""
        for index in range(self.tab_widget.count()):
            icon = self._load_colored_tab_icon(index)
            self.tab_widget.setTabIcon(index, icon)
    
    def _load_colored_tab_icon(self, index):
        """Load SVG icon with color based on theme for tabs"""
        icon_name = self.TAB_ICONS.get(index, "")
        if not icon_name:
            return QIcon()
        
        # Use the helper function
        pixmap = get_icon_pixmap(icon_name, 20, None, self._is_dark)
        
        if pixmap:
            return QIcon(pixmap)
        
        # Fallback: Try to load from assets
        paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for path in paths:
            import os
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        color_hex = "#ffffff" if self._is_dark else "#495057"
                        
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        
                        return QIcon(colored)
                except Exception as e:
                    print(f"Could not load icon {path}: {e}")
        
        return QIcon()
    
    # ============================================================
    # THEME & STYLES
    # ============================================================
    
    def _apply_style(self):
        self.setStyleSheet(get_widget_style(self._is_dark))
    
    def _update_ui_colors(self):
        text_color = "#ffffff" if self._is_dark else "#212529"
        text_secondary = "rgba(255,255,255,0.8)" if self._is_dark else "#495057"
        
        # Status badge
        status_text = self.status_badge.text()
        if "Live" in status_text:
            status_color = "#2ecc71"
        elif "Loading" in status_text:
            status_color = "#f39c12"
        elif "Error" in status_text:
            status_color = "#e74c3c"
        else:
            status_color = text_secondary
        
        self.status_badge.setStyleSheet(get_status_badge_style(status_color))
        self.last_updated_label.setStyleSheet(get_last_updated_style(self._is_dark))
        
        # Title
        self.title_label.setStyleSheet(get_header_label_style(self._is_dark))
        
        # Combo boxes
        self.date_range_combo.setStyleSheet(get_combo_style(self._is_dark))
        self.interval_combo.setStyleSheet(get_combo_style(self._is_dark))
        
        self._apply_style()
    
    def _on_theme_changed(self, theme_name):
        if self._is_closing:
            return
        self._is_dark = is_dark_theme()
        self._insight_builder._is_dark = self._is_dark
        
        # Update search widget theme
        if hasattr(self, 'search_widget'):
            self.search_widget._on_theme_changed(theme_name)
        
        # Update export button theme
        if hasattr(self, 'export_btn'):
            self.export_btn._on_theme_changed(theme_name)
        
        # ✅ Update chart tab theme
        if hasattr(self, 'charts_tab'):
            self.charts_tab._on_theme_changed(theme_name)
        
        # ✅ Update tab bar style and icons
        self._apply_tab_bar_style()
        self._update_tab_icons_color()
        
        self._apply_style()
        self._update_ui_colors()
        self.load_insights()
    
    # ============================================================
    # ANIMATIONS
    # ============================================================
    
    def _load_with_animation(self):
        self.load_insights()
        if hasattr(self, 'content'):
            animation = QPropertyAnimation(self.content, b"windowOpacity")
            animation.setDuration(500)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
    
    def _animate_progress(self, target_value):
        current_value = self.progress_bar.value()
        animation = QPropertyAnimation(self.progress_bar, b"value")
        animation.setDuration(300)
        animation.setStartValue(current_value)
        animation.setEndValue(target_value)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
    
    def _reset_progress_bar(self):
        if not self._is_closing and hasattr(self, 'progress_bar') and self.progress_bar:
            try:
                self.progress_bar.setValue(0)
            except RuntimeError:
                pass
    
    # ============================================================
    # INSIGHT DISPLAY HELPERS
    # ============================================================
    
    def _clear_insights(self):
        for i in range(self.content_layout.count() - 1, -1, -1):
            item = self.content_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget.deleteLater()
        
        if self.content_layout.count() == 0:
            self.content_layout.addStretch()
    
    def _add_insight(self, icon_name, text, color, details=None, category=None, trend=None):
        self._insight_builder.create_insight_card(
            icon_name, text, color, details, category, trend, self.content_layout
        )
    
    def _add_section_header(self, title, icon="📌"):
        self._insight_builder.create_section_header(title, icon, self.content_layout)
    
    def _show_error(self, message):
        self._insight_builder.create_error_card(message, self.content_layout)
    
    def _get_myanmar_text(self, key, **kwargs):
        return get_myanmar_text(MYANMAR_TEXTS, key, **kwargs)
    
    # ============================================================
    # MAIN LOAD METHOD
    # ============================================================
    
    def load_insights(self):
        if self._is_loading or self._is_closing:
            return
        
        self._is_loading = True
        self.status_badge.setText("● Loading...")
        self._update_ui_colors()
        self._animate_progress(10)
        
        self._clear_insights()
        
        try:
            symbol = get_currency_symbol()
            from_date, to_date = get_date_range(self.date_range_combo.currentText())
            search_text = self.search_widget.get_text().lower().strip()
            
            # Quick Stats (still fetched but not displayed in header)
            total_sales, total_orders, avg_order = get_quick_stats()
            
            self._animate_progress(20)
            
            # ============================================================
            # 1. TODAY VS YESTERDAY
            # ============================================================
            today_sales, today_discount, yesterday_sales = get_today_yesterday_sales()
            today_net = today_sales - today_discount
            
            sales_change = 0
            if yesterday_sales > 0:
                sales_change = ((today_net - yesterday_sales) / yesterday_sales) * 100
            
            self._animate_progress(30)
            
            if today_net == 0 and yesterday_sales == 0:
                self._add_insight(
                    "bar_chart",
                    self._get_myanmar_text("no_sales"),
                    "#7f8c8d"
                )
            elif sales_change > 15:
                self._add_insight(
                    "trending_up",
                    self._get_myanmar_text("sales_up", change=f"{sales_change:.0f}"),
                    "#2ecc71",
                    f"Today: {format_money(today_net, symbol)} | Yesterday: {format_money(yesterday_sales, symbol)}",
                    trend="↑"
                )
            elif sales_change < -15:
                self._add_insight(
                    "trending_down",
                    self._get_myanmar_text("sales_down", change=f"{abs(sales_change):.0f}"),
                    "#e74c3c",
                    f"Today: {format_money(today_net, symbol)} | Yesterday: {format_money(yesterday_sales, symbol)}",
                    trend="↓"
                )
            else:
                self._add_insight(
                    "bar_chart",
                    self._get_myanmar_text("sales_stable"),
                    "#3498db",
                    f"Today: {format_money(today_net, symbol)} | Yesterday: {format_money(yesterday_sales, symbol)}",
                    trend="→"
                )
            
            # ============================================================
            # 2. PEAK HOUR
            # ============================================================
            peak_hour = get_peak_hour()
            if peak_hour:
                self._add_insight(
                    "clock",
                    self._get_myanmar_text("peak_hour_sales", hour=peak_hour),
                    "#f39c12",
                    "Most active hour for sales today",
                    "Analytics"
                )
            
            # ============================================================
            # 3. REPEAT CUSTOMERS
            # ============================================================
            total_customers, repeat_customers = get_repeat_customers()
            if total_customers > 0 and repeat_customers > 0:
                repeat_pct = (repeat_customers / total_customers) * 100
                self._add_insight(
                    "groups",
                    self._get_myanmar_text("repeat_customers", count=repeat_customers, pct=f"{repeat_pct:.0f}"),
                    "#9b59b6",
                    f"Total customers: {total_customers}",
                    "Customers"
                )
            
            # ============================================================
            # 4. WEEKLY COMPARISON
            # ============================================================
            this_week, last_week = get_weekly_comparison()
            self._animate_progress(50)
            
            weekly_change = 0
            if last_week > 0:
                weekly_change = ((this_week - last_week) / last_week) * 100
            
            if weekly_change > 10:
                self._add_insight(
                    "calendar",
                    self._get_myanmar_text("weekly_up", change=f"{weekly_change:.0f}"),
                    "#2ecc71",
                    f"This week: {format_money(this_week, symbol)} | Last week: {format_money(last_week, symbol)}",
                    "Weekly", "↑"
                )
            elif weekly_change < -10:
                self._add_insight(
                    "calendar",
                    self._get_myanmar_text("weekly_down", change=f"{abs(weekly_change):.0f}"),
                    "#e74c3c",
                    f"This week: {format_money(this_week, symbol)} | Last week: {format_money(last_week, symbol)}",
                    "Weekly", "↓"
                )
            else:
                self._add_insight(
                    "calendar",
                    self._get_myanmar_text("weekly_stable"),
                    "#3498db",
                    f"This week: {format_money(this_week, symbol)} | Last week: {format_money(last_week, symbol)}",
                    "Weekly", "→"
                )
            
            # ============================================================
            # 5. MONTHLY COMPARISON
            # ============================================================
            this_month, last_month = get_monthly_comparison()
            self._animate_progress(60)
            
            monthly_change = 0
            if last_month > 0:
                monthly_change = ((this_month - last_month) / last_month) * 100
            
            if monthly_change > 10:
                self._add_insight(
                    "calendar_month",
                    self._get_myanmar_text("monthly_up", change=f"{monthly_change:.0f}"),
                    "#2ecc71",
                    f"This month: {format_money(this_month, symbol)} | Last month: {format_money(last_month, symbol)}",
                    "Monthly", "↑"
                )
            elif monthly_change < -10:
                self._add_insight(
                    "calendar_month",
                    self._get_myanmar_text("monthly_down", change=f"{abs(monthly_change):.0f}"),
                    "#e74c3c",
                    f"This month: {format_money(this_month, symbol)} | Last month: {format_money(last_month, symbol)}",
                    "Monthly", "↓"
                )
            else:
                self._add_insight(
                    "calendar_month",
                    self._get_myanmar_text("monthly_stable"),
                    "#3498db",
                    f"This month: {format_money(this_month, symbol)} | Last month: {format_money(last_month, symbol)}",
                    "Monthly", "→"
                )
            
            # ============================================================
            # 6. TOP CATEGORIES
            # ============================================================
            top_categories = get_top_categories(from_date, to_date)
            self._animate_progress(70)
            
            if top_categories:
                cat_names = [c[0] for c in top_categories[:3]]
                cat_text = ", ".join(cat_names)
                days = get_date_range_days(self.date_range_combo.currentText())
                self._add_insight(
                    "trophy",
                    f"{self._get_myanmar_text('top_category', days=days)}: {cat_text}",
                    "#9b59b6",
                    f"Top: {format_money(top_categories[0][1], symbol)}",
                    "Categories"
                )
            
            # ============================================================
            # 7. STOCK ALERT
            # ============================================================
            low_stock_count, out_of_stock_count = get_stock_alert()
            self._animate_progress(80)
            
            if low_stock_count > 0 or out_of_stock_count > 0:
                alert_text = []
                if low_stock_count > 0:
                    alert_text.append(f"{low_stock_count} low stock items")
                if out_of_stock_count > 0:
                    alert_text.append(f"{out_of_stock_count} out of stock items")
                self._add_insight(
                    "warning",
                    f"{self._get_myanmar_text('stock_alert')}: {', '.join(alert_text)}",
                    "#f39c12",
                    "Please check inventory for reordering.",
                    "Inventory"
                )
            else:
                self._add_insight(
                    "check_circle",
                    self._get_myanmar_text("stock_ok"),
                    "#27ae60",
                    category="Inventory"
                )
            
            # ============================================================
            # 8. TOP PRODUCTS
            # ============================================================
            top_items = get_top_products(from_date, to_date)
            self._animate_progress(85)
            
            if top_items:
                item_text = ", ".join([f"{t[0]} ({t[2]:.0f})" for t in top_items[:3]])
                self._add_insight(
                    "local_fire_department",
                    self._get_myanmar_text("top_products") + f": {item_text}",
                    "#e67e22",
                    f"Top: {top_items[0][0]} - {format_money(top_items[0][2], symbol)}",
                    "Products"
                )
            
            # ============================================================
            # 9. PAYMENT BREAKDOWN
            # ============================================================
            payments = get_payment_breakdown(from_date, to_date)
            
            if payments:
                total_payments = sum(p[1] for p in payments)
                cash_total = next((p[1] for p in payments if "Cash" in p[0]), 0)
                card_total = next((p[1] for p in payments if "Card" in p[0]), 0)
                mobile_total = next((p[1] for p in payments if "Mobile" in p[0]), 0)
                
                cash_pct = (cash_total / total_payments * 100) if total_payments > 0 else 0
                card_pct = (card_total / total_payments * 100) if total_payments > 0 else 0
                mobile_pct = (mobile_total / total_payments * 100) if total_payments > 0 else 0
                
                self._add_insight(
                    "credit_card",
                    f"Cash: {cash_pct:.0f}% | Card: {card_pct:.0f}% | Mobile: {mobile_pct:.0f}%",
                    "#2ecc71",
                    f"Total payments: {format_money(total_payments, symbol)}",
                    "Payments"
                )
            
            # ============================================================
            # 10. SALES FORECAST
            # ============================================================
            forecast_7d = get_forecast(7)
            forecast_14d = get_forecast(14)
            forecast_30d = get_forecast(30)
            
            if forecast_7d > 0:
                self._add_insight(
                    "analytics",
                    f"{self._get_myanmar_text('forecast_7d')}: {format_money(forecast_7d, symbol)}",
                    "#8e44ad",
                    f"14d: {format_money(forecast_14d, symbol)} | 30d: {format_money(forecast_30d, symbol)}",
                    "Forecast"
                )
            
            self._animate_progress(100)
            self.status_badge.setText("● Live")
            self._update_ui_colors()
            self.last_updated_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
            
            # Filter by search
            if search_text:
                self._filter_insights(search_text)
            
            self.insight_updated.emit({
                'total_sales': total_sales,
                'total_orders': total_orders,
                'avg_order': avg_order,
                'timestamp': datetime.now().isoformat()
            })
            
            # ✅ Update chart tab with new data
            if hasattr(self, 'charts_tab'):
                self.charts_tab.update_data(from_date, to_date)
            
            logger.info("AI Assistant insights loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load AI insights: {e}")
            self._clear_insights()
            self._show_error(f"Failed to load insights: {str(e)}")
            self.status_badge.setText("● Error")
            self._update_ui_colors()
            self.error_occurred.emit(str(e))
        
        finally:
            self._is_loading = False
            if not self._is_closing and hasattr(self, 'progress_bar') and self.progress_bar:
                QTimer.singleShot(1000, self._reset_progress_bar)
    
    def _filter_insights(self, search_text):
        if not search_text:
            return
        
        for i in range(self.content_layout.count() - 1):
            item = self.content_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                labels = widget.findChildren(QLabel)
                visible = False
                for label in labels:
                    if search_text in label.text().lower():
                        visible = True
                        break
                widget.setVisible(visible)
    
    # ============================================================
    # CONTROL METHODS
    # ============================================================
    
    def _on_date_range_changed(self, range_text):
        if self._is_closing:
            return
        self._current_date_range = range_text
        self.load_insights()
    
    def _on_search_changed(self, text):
        self._search_text = text
        if text.strip():
            self._filter_insights(text.lower().strip())
        else:
            for i in range(self.content_layout.count() - 1):
                item = self.content_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setVisible(True)
    
    def _on_search_cleared(self):
        for i in range(self.content_layout.count() - 1):
            item = self.content_layout.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(True)
    
    def _on_refresh_interval_changed(self, interval_text):
        if self._is_closing:
            return
        if interval_text == "Off":
            self.stop_auto_refresh()
            return
        seconds = int(interval_text.replace("s", ""))
        self.set_refresh_interval(seconds * 1000)
    
    def set_refresh_interval(self, milliseconds):
        self._refresh_interval = milliseconds
        self.refresh_timer.stop()
        self.refresh_timer.start(milliseconds)
    
    def stop_auto_refresh(self):
        self.refresh_timer.stop()
        self.status_badge.setText("● Paused")
        self._update_ui_colors()
    
    def start_auto_refresh(self):
        self.refresh_timer.start(self._refresh_interval)
        self.status_badge.setText("● Live")
        self._update_ui_colors()
    
    def _check_notifications(self):
        low_stock, out_of_stock = get_stock_alert()
        if low_stock > 0 or out_of_stock > 0:
            self.status_badge.setText("⚠️ Alert")
            self._update_ui_colors()
    
    # ============================================================
    # EXPORT
    # ============================================================
    
    def _export_report(self):
        if self._is_loading or self._is_closing:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AI Report",
            f"ai_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            from_date, to_date = get_date_range(self.date_range_combo.currentText())
            export_report(from_date, to_date, file_path)
            QMessageBox.information(self, "Export Complete", f"Report exported to:\n{file_path}")
            logger.info(f"AI report exported: {file_path}")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
