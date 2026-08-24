# ui/ai_pages/ai_dashboard/dashboard_widget.py
"""
Main Dashboard Widget - AI Sales Dashboard
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QApplication, QSizePolicy,
    QSpacerItem, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPalette, QFont
from loguru import logger
from datetime import datetime

from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from ui.widgets.modern_button import ModernButton
from ui.widgets.date_range_widget import DateRangeWidget
from utils.currency import format_money

from ui.ai_pages.ai_dashboard.dashboard_icons import DashboardIcons
from ui.ai_pages.ai_dashboard.dashboard_cards import DashboardCards
from ui.ai_pages.ai_dashboard.dashboard_charts import DashboardCharts
from ui.ai_pages.ai_dashboard.dashboard_data import DashboardData, get_dashboard_data_sync


class AIDashboard(QWidget):
    """AI Sales Dashboard with real-time analytics"""
    
    refresh_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loading = False
        self._setup_ui()
        QTimer.singleShot(200, self._load_data)
    
    def _setup_ui(self):
        colors = get_theme_colors()
        bg_color = colors.get('bg', '#f5f6fa')
        
        # Main layout: header/cards stay fixed, lower dashboard content scrolls.
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 12, 20, 12)
        main_layout.setSpacing(10)

        # ============================================================
        # HEADER
        # ============================================================
        header = self._create_header(colors)
        main_layout.addWidget(header)

        # ============================================================
        # KPI CARDS
        # ============================================================
        self.cards = DashboardCards(self)
        cards_container = self.cards.setup()
        main_layout.addWidget(cards_container)
        
        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {bg_color};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {colors.get('input_bg', '#f0f0f0')};
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {colors.get('border', '#c0c0c0')};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {colors.get('text_secondary', '#888888')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: transparent;
            }}
        """)
        
        # Content
        self.scroll_content = QWidget()
        self.scroll_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_content.setStyleSheet(f"background-color: {bg_color};")
        
        content_layout = QVBoxLayout(self.scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        # ============================================================
        # CHARTS
        # ============================================================
        self.charts = DashboardCharts(self)
        charts_container = self.charts.setup(colors)
        content_layout.addWidget(charts_container)
        
        # ============================================================
        # BOTTOM SECTION
        # ============================================================
        bottom = self._create_bottom_section(colors)
        content_layout.addWidget(bottom)
        
        # Spacer
        content_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum))
        
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

    def _apply_header_theme(self, colors):
        if hasattr(self, "header_frame"):
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.get('card_bg', '#ffffff')};
                    border-radius: 12px;
                    padding: 4px 16px;
                }}
            """)
        if hasattr(self, "header_title_label"):
            self.header_title_label.setStyleSheet(f"""
                font-size: 15pt;
                font-weight: bold;
                color: {colors.get('text', '#2d3436')};
                background-color: transparent;
                padding: 0px;
                margin: 0px;
            """)
        if hasattr(self, "status_label"):
            self.status_label.setStyleSheet(f"""
                font-size: 10pt;
                font-weight: 500;
                color: {colors.get('text_secondary', '#636e72')};
                background-color: transparent;
                padding: 0px;
                margin: 0px;
            """)

    def _apply_bottom_theme(self, colors):
        frame_style = f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dbe1ee')};
                border-radius: 12px;
            }}
        """
        for frame_name in ("activity_frame", "insights_frame"):
            frame = getattr(self, frame_name, None)
            if frame:
                frame.setStyleSheet(frame_style)
        title_style = f"""
            font-size: 11pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """
        for label_name in ("activity_title_label", "insights_title_label"):
            label = getattr(self, label_name, None)
            if label:
                label.setStyleSheet(title_style)
        if hasattr(self, "insights_label"):
            self.insights_label.setStyleSheet(f"""
                font-size: 9.5pt;
                line-height: 1.4;
                color: {colors.get('text_secondary', '#636e72')};
                background: transparent;
                border: none;
                padding: 2px 0px;
            """)
        if hasattr(self, "activity_table"):
            self._apply_activity_table_theme(colors)

    def _apply_activity_table_theme(self, colors):
        table_bg = colors.get('card_bg', '#ffffff')
        row_bg = colors.get('card_bg', '#ffffff')
        row_alt = colors.get('table_alt', colors.get('bg', '#f7f8fc'))
        text = colors.get('text', '#172033')
        muted = colors.get('text_secondary', '#667085')
        border = colors.get('border', '#dbe1ee')
        hover = colors.get('bg_hover', '#e9edfa')

        self.activity_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {table_bg};
                border: 1px solid {border};
                border-radius: 10px;
                gridline-color: transparent;
                color: {text};
                font-size: 9.5pt;
                alternate-background-color: {row_alt};
                selection-background-color: {hover};
                selection-color: {text};
                outline: none;
            }}
            QHeaderView::section {{
                background-color: {table_bg};
                color: {muted};
                border: none;
                border-bottom: 1px solid {border};
                padding: 9px 10px;
                font-size: 8.5pt;
                font-weight: 600;
            }}
            QTableWidget::item {{
                background-color: {row_bg};
                border: none;
                border-bottom: 1px solid {border};
                padding: 7px 10px;
            }}
            QTableWidget::item:hover {{
                background-color: {hover};
            }}
            QScrollBar:vertical {{
                background: {table_bg};
                width: 8px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {muted}; }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
    
    def _create_header(self, colors):
        """Create header section"""
        header = QFrame()
        self.header_frame = header
        header.setFixedHeight(55)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(0)
        
        # ====== Title Section (Left) ======
        title_layout = QHBoxLayout()
        # Icon နဲ့ Title ကြား အကွာအဝေးကို နည်းနိုင်သမျှနည်းအောင် 4px သို့ 6px သာထားပါ
        title_layout.setSpacing(6) 
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # Dashboard Icon
        title_icon = DashboardIcons.create_svg_icon("dashboard", (22, 22))
        title_icon.setFixedSize(22, 22)
        title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_icon.setStyleSheet("""
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """)
        title_layout.addWidget(title_icon)
        
        # Title Text
        title_label = QLabel("AI Sales Dashboard")
        self.header_title_label = title_label
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title_label)
        
        # Title Layout ကို Main Layout ထဲ သို့ ထည့်ပါ
        layout.addLayout(title_layout)
        
        # ====== Title နဲ့ ညာဘက် Menu များကြား အကွာအဝေးအတွက် Stretch ထည့်ပါ ======
        layout.addStretch(1) 
        
        # ====== Status Section (Right) ======
        status_layout = QHBoxLayout()
        status_layout.setSpacing(6) # Icon နဲ့ Ready စာသားကြား လှလှပပ ကွာစေရန်
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        # Status Icon (24x24 Size အပြည့်)
        status_icon = DashboardIcons.create_svg_icon("check_circle", (24, 24))
        status_icon.setFixedSize(24, 24)
        status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_icon.setStyleSheet("""
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """)
        status_layout.addWidget(status_icon)
        
        # Status Label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        status_layout.addWidget(self.status_label)
        
        layout.addLayout(status_layout)
        layout.addSpacing(12)
        
        # ====== Shared Date Range Widget ======
        self.date_range = DateRangeWidget(self)
        self.date_range.setMinimumWidth(260)
        self.date_range.setMaximumWidth(390)
        self.date_range.date_range_changed.connect(self._on_date_range_changed)
        layout.addWidget(self.date_range)
        layout.addSpacing(8)
        
        # ====== Refresh Button ======
        refresh_btn = ModernButton("", ModernButton.TERTIARY)
        self.refresh_btn = refresh_btn
        refresh_btn.set_compact(True)
        refresh_btn.setFixedSize(32, 30)
        refresh_btn.set_icon("refresh", size=(16, 16))
        refresh_btn.setToolTip("Refresh Data")
        refresh_btn.clicked.connect(self._load_data)
        layout.addWidget(refresh_btn)
        
        self._apply_header_theme(colors)
        return header
    
    def _create_bottom_section(self, colors):
        """Create bottom section (Activity + Insights)"""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        container.setFixedHeight(340)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Activity
        activity_frame = QFrame()
        self.activity_frame = activity_frame
        activity_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        activity_layout = QVBoxLayout(activity_frame)
        activity_layout.setContentsMargins(12, 8, 12, 10)
        activity_layout.setSpacing(8)
        
        # Activity title
        act_title_layout = QHBoxLayout()
        act_title_layout.setSpacing(6)
        act_title_layout.setContentsMargins(0, 0, 0, 0)
        
        act_icon = DashboardIcons.create_svg_icon("history", (24, 24))
        act_icon.setFixedSize(24, 24)
        act_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        act_icon.setStyleSheet("""
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """)
        act_title_layout.addWidget(act_icon)
        
        act_title = QLabel("Recent Activity")
        self.activity_title_label = act_title
        act_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        act_title_layout.addWidget(act_title)
        act_title_layout.addStretch()
        
        activity_layout.addLayout(act_title_layout)
        
        self.activity_table = QTableWidget(0, 4)
        self.activity_table.setHorizontalHeaderLabels(["Invoice", "Time", "Amount", "Status"])
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.activity_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.activity_table.setShowGrid(False)
        self.activity_table.setAlternatingRowColors(False)
        self.activity_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.activity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.activity_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.activity_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.activity_table.setColumnWidth(1, 120)
        self.activity_table.setColumnWidth(2, 130)
        self.activity_table.setColumnWidth(3, 80)
        self._apply_activity_table_theme(colors)
        activity_layout.addWidget(self.activity_table, 1)
        
        layout.addWidget(activity_frame, 1)
        
        # Insights (Simplified Clean Card Design)
        insights_frame = QFrame()
        self.insights_frame = insights_frame
        insights_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        insights_layout = QVBoxLayout(insights_frame)
        insights_layout.setContentsMargins(10, 8, 10, 8)
        insights_layout.setSpacing(6)
        
        # Insights title
        ins_title_layout = QHBoxLayout()
        ins_title_layout.setSpacing(6)
        ins_title_layout.setContentsMargins(0, 0, 0, 0)
        
        ins_icon = DashboardIcons.create_svg_icon("lightbulb", (24, 24))
        ins_icon.setFixedSize(24, 24)
        ins_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ins_icon.setStyleSheet("""
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """)
        ins_title_layout.addWidget(ins_icon)
        
        ins_title = QLabel("AI Insights")
        self.insights_title_label = ins_title
        ins_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        ins_title_layout.addWidget(ins_title)
        ins_title_layout.addStretch()
        
        insights_layout.addLayout(ins_title_layout)
        
        # Simple & Clean text area
        self.insights_label = QLabel("Loading insights...")
        self.insights_label.setWordWrap(True)
        self.insights_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        insights_layout.addWidget(self.insights_label, 1)
        
        layout.addWidget(insights_frame, 1)
        self._apply_bottom_theme(colors)
        return container
    
    # ================================================================
    # DATA LOADING
    # ================================================================
    
    def _load_data(self):
        """Load dashboard data"""
        if self._is_loading:
            return
        
        self._is_loading = True
        self.status_label.setText("Loading...")
        QApplication.processEvents()
        
        try:
            start_date = self.date_range.get_from_date()
            end_date = self.date_range.get_to_date()
            
            # Load data
            (
                sales_data, daily_data, category_data, recent_sales,
                expense_data, payment_data, expense_category_data,
            ) = DashboardData.get_sales_data(start_date, end_date)
            
            # Update cards
            if sales_data:
                self.cards.update_cards(sales_data, expense_data)
            else:
                self.cards.update_cards_zero()
            
            # Update charts
            if hasattr(self, 'charts'):
                self.charts.update_sales_chart(daily_data)
                self.charts.update_category_chart(category_data)
                self.charts.update_payment_chart(payment_data)
                self.charts.update_expense_chart(expense_category_data)
            
            # Update activity
            self._update_activity(recent_sales)
            
            # Update insights
            self._update_insights(sales_data, expense_data, len(daily_data))
            
            self.status_label.setText("Ready")
            
        except Exception as e:
            logger.error(f"Failed to load dashboard: {e}")
            self.status_label.setText("Error")
            self.cards.update_cards_zero()
            self.insights_label.setText(f"❌ Failed to load data")
        
        finally:
            self._is_loading = False
    
    def _update_activity(self, recent_sales):
        """Update recent activity list."""
        table = self.activity_table
        table.setRowCount(0)

        colors = get_theme_colors()
        text_color = colors.get('text', '#172033')
        muted_color = colors.get('text_secondary', '#667085')
        amount_color = colors.get('progress_bg', '#6675f5')
        success_color = colors.get('success', '#2ecc71')

        if not recent_sales:
            table.setRowCount(1)
            item = QTableWidgetItem("No recent activity")
            item.setForeground(QColor(muted_color))
            table.setItem(0, 0, item)
            table.setSpan(0, 0, 1, 4)
            table.setRowHeight(0, 42)
            return

        for row_idx, sale in enumerate(recent_sales):
            sale_type, invoice_no, amount, created_at = sale
            table.insertRow(row_idx)
            table.setRowHeight(row_idx, 42)

            invoice_item = QTableWidgetItem(str(invoice_no or sale_type or "Sale"))
            invoice_item.setForeground(QColor(text_color))
            invoice_item.setFont(QFont("", 10, QFont.Weight.Normal))
            table.setItem(row_idx, 0, invoice_item)

            time_item = QTableWidgetItem(self._format_activity_time(created_at))
            time_item.setForeground(QColor(muted_color))
            table.setItem(row_idx, 1, time_item)

            amount_item = QTableWidgetItem(format_money(float(amount or 0)))
            amount_item.setForeground(QColor(amount_color))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amount_item.setFont(QFont("", 10, QFont.Weight.Normal))
            table.setItem(row_idx, 2, amount_item)

            status_item = QTableWidgetItem("Paid")
            status_item.setForeground(QColor(success_color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFont(QFont("", 9, QFont.Weight.Normal))
            table.setItem(row_idx, 3, status_item)

    def _format_activity_time(self, value):
        """Format activity timestamp for compact display."""
        if not value:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%d %b, %H:%M")

        text = str(value)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text[:19], fmt).strftime("%d %b, %H:%M")
            except ValueError:
                continue
        return text[:16]
    
    def _update_insights(self, sales_data, expense_data, days_count):
        """Update AI insights"""
        if not sales_data:
            self.insights_label.setText("No data available for insights.")
            return
        
        try:
            transactions = sales_data[0] if sales_data[0] is not None else 0
            total_sales = float(sales_data[1]) if sales_data[1] is not None else 0
            total_profit = float(sales_data[4]) if sales_data[4] is not None else 0
            
            insights = []
            
            if total_sales > 1000000:
                insights.append("🚀 Excellent sales performance!")
            elif total_sales > 500000:
                insights.append("📈 Good sales performance!")
            elif total_sales > 100000:
                insights.append("📊 Solid sales performance.")
            else:
                insights.append("💪 Keep going! Sales can improve.")
            
            if total_sales > 0 and total_profit > 0:
                profit_margin = (total_profit / total_sales * 100)
                if profit_margin > 30:
                    insights.append(f"💰 Healthy profit margin: {profit_margin:.1f}%")
                elif profit_margin > 15:
                    insights.append(f"📈 Profit margin: {profit_margin:.1f}% - Good!")
                else:
                    insights.append(f"📊 Profit margin: {profit_margin:.1f}% - Room for improvement")
            
            if transactions > 0 and days_count > 0:
                avg_daily = transactions / days_count
                insights.append(f"📋 Average: {avg_daily:.1f} transactions/day")
            
            if insights:
                self.insights_label.setText("\n".join([f"• {i}" for i in insights[:3]]))
            else:
                self.insights_label.setText("Dashboard ready. Check back for insights.")
                
        except Exception as e:
            self.insights_label.setText("Dashboard ready.")
    
    # ================================================================
    # PUBLIC METHODS
    # ================================================================
    
    def _on_date_range_changed(self, _from_date, _to_date):
        """Reload every dashboard card and chart for the selected dates."""
        self._load_data()
    
    def refresh(self):
        """Refresh dashboard"""
        self._load_data()
    
    def update_theme(self):
        """Update theme"""
        colors = get_theme_colors()
        bg_color = colors.get('bg', '#f5f6fa')
        
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {bg_color};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {colors.get('input_bg', '#f0f0f0')};
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {colors.get('border', '#c0c0c0')};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {colors.get('text_secondary', '#888888')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: transparent;
            }}
        """)
        
        self.scroll_content.setStyleSheet(f"background-color: {bg_color};")
        self._apply_header_theme(colors)
        self._apply_bottom_theme(colors)
        self.cards.update_theme()
        
        if hasattr(self, 'charts') and self.charts:
            self.charts.update_theme()
        
        # Clear icon cache and reload
        DashboardIcons.clear_cache()
        self._load_data()
    
    def refresh_icons(self):
        """Refresh all icons in dashboard"""
        DashboardIcons.clear_cache()
        # Reload UI to show updated icons
        self._load_data()


# Export
__all__ = ['AIDashboard', 'get_dashboard_data_sync']

