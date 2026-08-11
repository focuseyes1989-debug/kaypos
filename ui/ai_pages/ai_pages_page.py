# ui/ai_pages/ai_pages_page.py
"""
AI Pages - AI ဆိုင်ရာ စာမျက်နှာများ
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QLineEdit, QComboBox, QTextEdit, QSplitter,
    QTabWidget, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QColor, QIcon, QPainter
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from ui.ai_pages.ai_chat_room import AIChatRoom
from ui.widgets.modern_button import ModernButton
from utils.translations import tr
from loguru import logger
import os
from datetime import datetime, timedelta

# 🆕 Phase 2 Imports
from ui.ai_pages.ai_dashboard import AIDashboard


class AIPagesPage(QWidget):
    """
    AI Pages - AI ဆိုင်ရာ စာမျက်နှာများ
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        colors = get_theme_colors()
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ============================================================
        # TAB WIDGET
        # ============================================================
        self.tabs = QTabWidget()
        self._apply_tab_style()
        
        # ============================================================
        # TAB 1: AI Dashboard 🆕
        # ============================================================
        self.dashboard = AIDashboard()
        dashboard_icon = self._load_colored_icon("dashboard")
        self.tabs.addTab(self.dashboard, dashboard_icon, "Dashboard")
        
        # ============================================================
        # TAB 2: AI Chat Room
        # ============================================================
        self.chat_room = AIChatRoom()
        chat_icon = self._load_colored_icon("chat")
        self.tabs.addTab(self.chat_room, chat_icon, "AI Chat")
        
        # ============================================================
        # TAB 3: AI Analytics 🆕
        # ============================================================
        self.analytics_tab = self._create_analytics_tab()
        analytics_icon = self._load_colored_icon("analytics")
        self.tabs.addTab(self.analytics_tab, analytics_icon, "Analytics")
        
        # ============================================================
        # TAB 4: AI Tools
        # ============================================================
        self.tools_tab = self._create_tools_tab()
        tools_icon = self._load_colored_icon("smart_toy")
        self.tabs.addTab(self.tools_tab, tools_icon, "AI Tools")
        
        main_layout.addWidget(self.tabs)
        
        # Connect theme change
        from ui.themes.theme_manager import theme_manager
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _format_ks(self, value):
        try:
            return f"{float(value):,.0f} Ks"
        except (TypeError, ValueError):
            return "0 Ks"
    
    def _load_colored_icon(self, icon_name, size=20):
        """
        Load SVG icon with color based on theme
        
        Args:
            icon_name: Name of the SVG file (without extension)
            size: Icon size in pixels
        
        Returns:
            QIcon: Colored icon
        """
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        png_path = f"assets/icons/{icon_name}.png"
        
        icon_path = None
        if os.path.exists(svg_path):
            icon_path = svg_path
        elif os.path.exists(png_path):
            icon_path = png_path
        else:
            # Fallback to emoji
            return QIcon()
        
        try:
            pixmap = QPixmap(icon_path)
            if pixmap.isNull():
                return QIcon()
            
            # Scale to desired size
            scaled = pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Get theme color
            is_dark = is_dark_theme()
            color_hex = "#ffffff" if is_dark else "#495057"
            
            # Colorize the icon
            colored = scaled.copy()
            painter = QPainter(colored)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(colored.rect(), QColor(color_hex))
            painter.end()
            
            return QIcon(colored)
            
        except Exception as e:
            logger.warning(f"Could not load icon {icon_name}: {e}")
            return QIcon()
    
    def _update_tab_icons(self):
        """Update all tab icons when theme changes"""
        # Update Dashboard tab icon
        dashboard_icon = self._load_colored_icon("dashboard")
        self.tabs.setTabIcon(0, dashboard_icon)
        
        # Update Chat tab icon
        chat_icon = self._load_colored_icon("chat")
        self.tabs.setTabIcon(1, chat_icon)
        
        # Update Analytics tab icon
        analytics_icon = self._load_colored_icon("analytics")
        self.tabs.setTabIcon(2, analytics_icon)
        
        # Update Tools tab icon
        tools_icon = self._load_colored_icon("smart_toy")
        self.tabs.setTabIcon(3, tools_icon)
    
    def _apply_tab_style(self):
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
                QTabBar::tab {
                    padding-left: 8px;
                    padding-right: 16px;
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
                QTabBar::tab {
                    padding-left: 8px;
                    padding-right: 16px;
                }
            """)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._apply_tab_style()
        self._update_tab_icons()
        self.update_theme()
    
    def _create_analytics_tab(self):
        """🆕 Create analytics tab with all analytics features"""
        colors = get_theme_colors()
        
        widget = QWidget()
        widget.setObjectName("analyticsTab")
        widget.setStyleSheet(f"""
            QWidget#analyticsTab {{
                background-color: {colors.get('bg', '#f5f6fa')};
            }}
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        
        # ============================================================
        # HEADER
        # ============================================================
        header_frame = QFrame()
        header_frame.setObjectName("analyticsHeader")
        header_frame.setStyleSheet(f"""
            QFrame#analyticsHeader {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 8px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(12)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(3)
        
        title_label = QLabel("📊 AI Analytics & Reports")
        title_label.setStyleSheet(f"""
            font-size: 17pt;
            font-weight: 700;
            color: {colors.get('text', '#2d3436')};
            background: transparent;
        """)
        title_label.setText("AI Analytics")
        subtitle_label = QLabel("Customer, inventory, sales, and retention signals in one operational view")
        subtitle_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {colors.get('text_secondary', '#636e72')};
            background: transparent;
        """)
        title_stack.addWidget(title_label)
        title_stack.addWidget(subtitle_label)
        header_layout.addLayout(title_stack, stretch=1)
        
        header_layout.addStretch()

        self.analytics_status_label = QLabel("Not refreshed yet")
        self.analytics_status_label.setStyleSheet(f"""
            font-size: 9pt;
            color: {colors.get('text_secondary', '#636e72')};
            background: transparent;
        """)
        header_layout.addWidget(self.analytics_status_label)

        refresh_all_btn = ModernButton("Refresh All", ModernButton.SECONDARY)
        refresh_all_btn.set_icon("refresh", size=(16, 16))
        refresh_all_btn.setCheckable(False)
        refresh_all_btn.setAutoExclusive(False)
        refresh_all_btn.setFixedSize(124, 36)
        refresh_all_btn.clicked.connect(self._refresh_all_analytics)
        self.analytics_refresh_all_btn = refresh_all_btn
        header_layout.addWidget(self.analytics_refresh_all_btn)
        
        # Export button
        export_btn = ModernButton("📥 Export", ModernButton.PRIMARY)
        export_btn.setText("Export")
        export_btn.set_icon("file_export", size=(16, 16))
        export_btn.setCheckable(False)
        export_btn.setAutoExclusive(False)
        export_btn.setFixedSize(120, 36)
        export_btn.clicked.connect(self._export_analytics)
        self.analytics_export_btn = export_btn
        header_layout.addWidget(self.analytics_export_btn)
        
        layout.addWidget(header_frame)

        self.analytics_metric_grid = QGridLayout()
        self.analytics_metric_grid.setSpacing(12)
        self.analytics_metric_grid.setContentsMargins(0, 0, 0, 0)
        self.analytics_metric_labels = {}
        metrics = [
            ("sales", "Total Sales", "0 Ks", "#5865f2"),
            ("transactions", "Transactions", "0", "#1abc9c"),
            ("avg_ticket", "Avg Ticket", "0 Ks", "#faa81a"),
            ("profit", "Profit", "0 Ks", "#3ba55c"),
            ("stock_alerts", "Stock Alerts", "0", "#ed4245"),
            ("churn", "At-risk Customers", "0", "#9b59b6"),
        ]
        for index, (key, title, value, accent) in enumerate(metrics):
            row = index // 3
            col = index % 3
            self.analytics_metric_grid.addWidget(
                self._create_analytics_metric_card(key, title, value, accent),
                row,
                col
            )
            self.analytics_metric_grid.setColumnStretch(col, 1)
        layout.addLayout(self.analytics_metric_grid)
        
        # ============================================================
        # ANALYTICS GRID
        # ============================================================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        grid_layout = QGridLayout(scroll_content)
        grid_layout.setSpacing(14)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        
        # Customer Insights
        insights_frame = self._create_insights_widget()
        grid_layout.addWidget(insights_frame, 0, 0)
        
        # Inventory Recommendations
        inventory_frame = self._create_inventory_widget()
        grid_layout.addWidget(inventory_frame, 0, 1)
        
        # Sales Analytics
        sales_frame = self._create_sales_analytics_widget()
        grid_layout.addWidget(sales_frame, 1, 0, 1, 2)
        
        # Churn Risk Customers
        churn_frame = self._create_churn_widget()
        grid_layout.addWidget(churn_frame, 2, 0, 1, 2)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget

    def _create_analytics_metric_card(self, key, title, value, accent):
        colors = get_theme_colors()
        frame = QFrame()
        frame.setObjectName("analyticsMetricCard")
        frame.setMinimumHeight(92)
        frame.setStyleSheet(f"""
            QFrame#analyticsMetricCard {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-left: 4px solid {accent};
                border-radius: 8px;
            }}
        """)

        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"""
            font-size: 18pt;
            font-weight: 800;
            color: {colors.get('text', '#212529')};
            background: transparent;
        """)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 9pt;
            font-weight: 600;
            color: {colors.get('text_secondary', '#6c757d')};
            background: transparent;
        """)
        card_layout.addWidget(value_label)
        card_layout.addWidget(title_label)
        self.analytics_metric_labels[key] = value_label
        return frame

    def _style_analytics_card(self, frame: QFrame, min_height: int = 220):
        colors = get_theme_colors()
        frame.setObjectName("analyticsCard")
        frame.setMinimumHeight(min_height)
        frame.setStyleSheet(f"""
            QFrame#analyticsCard {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 8px;
            }}
        """)

    def _style_analytics_title(self, label: QLabel):
        colors = get_theme_colors()
        label.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: 700;
            color: {colors.get('text', '#2d3436')};
            background: transparent;
        """)

    def _style_analytics_body(self, label: QLabel, min_height: int = 120):
        colors = get_theme_colors()
        label.setMinimumHeight(min_height)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setStyleSheet(f"""
            QLabel {{
                font-size: 10pt;
                line-height: 1.35;
                color: {colors.get('text_secondary', '#636e72')};
                background-color: {colors.get('input_bg', '#f8f9fa')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 6px;
                padding: 10px;
            }}
        """)

    def _style_analytics_action(self, button: ModernButton, icon_name: str = "refresh"):
        button.setText("Refresh")
        button.set_icon(icon_name, size=(15, 15))
        button.set_button_style(ModernButton.SECONDARY)
        button.setCheckable(False)
        button.setAutoExclusive(False)
        button.setFixedHeight(32)
        button.setMinimumWidth(104)

    def _set_analytics_metric(self, key, value):
        if hasattr(self, 'analytics_metric_labels') and key in self.analytics_metric_labels:
            self.analytics_metric_labels[key].setText(str(value))

    def _mark_analytics_refreshed(self):
        if hasattr(self, 'analytics_status_label'):
            self.analytics_status_label.setText(f"Updated {datetime.now().strftime('%H:%M')}")

    def _refresh_all_analytics(self):
        self._refresh_customer_segments()
        self._refresh_inventory_recommendations()
        self._refresh_sales_analytics()
        self._refresh_churn_customers()
        self._mark_analytics_refreshed()
    
    def _create_insights_widget(self):
        """Create customer insights widget"""
        colors = get_theme_colors()
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 12px 16px;
            }}
        """)
        self._style_analytics_card(frame)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        title = QLabel("👥 Customer Segments")
        title.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
        """)
        title.setText("Customer Segments")
        self._style_analytics_title(title)
        layout.addWidget(title)
        
        self.customer_segments_label = QLabel("Loading segments...")
        self.customer_segments_label.setWordWrap(True)
        self.customer_segments_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {colors.get('text_secondary', '#636e72')};
            padding: 8px;
            background-color: {colors.get('input_bg', '#f8f9fa')};
            border-radius: 6px;
        """)
        self._style_analytics_body(self.customer_segments_label)
        layout.addWidget(self.customer_segments_label)
        
        refresh_btn = ModernButton("🔄 Refresh", ModernButton.TERTIARY)
        refresh_btn.set_compact(True)
        self._style_analytics_action(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_customer_segments)
        layout.addWidget(refresh_btn)
        
        # Load initial data
        self._refresh_customer_segments()
        
        return frame
    
    def _create_inventory_widget(self):
        """Create inventory recommendations widget"""
        colors = get_theme_colors()
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 12px 16px;
            }}
        """)
        self._style_analytics_card(frame)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        title = QLabel("📦 Reorder Recommendations")
        title.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
        """)
        title.setText("Reorder Recommendations")
        self._style_analytics_title(title)
        layout.addWidget(title)
        
        self.inventory_label = QLabel("Loading recommendations...")
        self.inventory_label.setWordWrap(True)
        self.inventory_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {colors.get('text_secondary', '#636e72')};
            padding: 8px;
            background-color: {colors.get('input_bg', '#f8f9fa')};
            border-radius: 6px;
        """)
        self._style_analytics_body(self.inventory_label)
        layout.addWidget(self.inventory_label)
        
        refresh_btn = ModernButton("🔄 Refresh", ModernButton.TERTIARY)
        refresh_btn.set_compact(True)
        self._style_analytics_action(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_inventory_recommendations)
        layout.addWidget(refresh_btn)
        
        # Load initial data
        self._refresh_inventory_recommendations()
        
        return frame
    
    def _create_sales_analytics_widget(self):
        """Create sales analytics widget"""
        colors = get_theme_colors()
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 12px 16px;
            }}
        """)
        self._style_analytics_card(frame, min_height=260)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        title = QLabel("📈 Sales Analytics")
        title.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
        """)
        title.setText("Sales Analytics")
        self._style_analytics_title(title)
        layout.addWidget(title)
        
        self.sales_analytics_label = QLabel("Loading sales analytics...")
        self.sales_analytics_label.setWordWrap(True)
        self.sales_analytics_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {colors.get('text_secondary', '#636e72')};
            padding: 8px;
            background-color: {colors.get('input_bg', '#f8f9fa')};
            border-radius: 6px;
        """)
        self._style_analytics_body(self.sales_analytics_label, min_height=150)
        layout.addWidget(self.sales_analytics_label)
        
        # Period selector
        period_layout = QHBoxLayout()
        period_label = QLabel("Period:")
        period_label.setStyleSheet(f"color: {colors.get('text_secondary', '#636e72')}; font-size: 9pt; font-weight: 600;")
        period_layout.addWidget(period_label)
        
        self.analytics_period = QComboBox()
        self.analytics_period.addItems(["Today", "This Week", "This Month", "Last 30 Days"])
        self.analytics_period.setStyleSheet(f"""
            QComboBox {{
                padding: 5px 10px;
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 4px;
                font-size: 9pt;
                background-color: {colors.get('input_bg', '#f8f9fa')};
                color: {colors.get('text', '#2d3436')};
                min-height: 24px;
            }}
            QComboBox:hover {{
                border-color: #5865f2;
            }}
        """)
        self.analytics_period.currentIndexChanged.connect(self._refresh_sales_analytics)
        period_layout.addWidget(self.analytics_period)
        period_layout.addStretch()
        layout.addLayout(period_layout)
        
        refresh_btn = ModernButton("🔄 Refresh", ModernButton.TERTIARY)
        refresh_btn.set_compact(True)
        self._style_analytics_action(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_sales_analytics)
        layout.addWidget(refresh_btn)
        
        # Load initial data
        self._refresh_sales_analytics()
        
        return frame
    
    def _create_churn_widget(self):
        """Create churn risk widget"""
        colors = get_theme_colors()
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 12px 16px;
            }}
        """)
        self._style_analytics_card(frame, min_height=220)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        title = QLabel("⚠️ At-Risk Customers")
        title.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
        """)
        title.setText("At-Risk Customers")
        self._style_analytics_title(title)
        layout.addWidget(title)
        
        self.churn_label = QLabel("Loading at-risk customers...")
        self.churn_label.setWordWrap(True)
        self.churn_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {colors.get('text_secondary', '#636e72')};
            padding: 8px;
            background-color: {colors.get('input_bg', '#f8f9fa')};
            border-radius: 6px;
        """)
        self._style_analytics_body(self.churn_label, min_height=120)
        layout.addWidget(self.churn_label)
        
        refresh_btn = ModernButton("🔄 Refresh", ModernButton.TERTIARY)
        refresh_btn.set_compact(True)
        self._style_analytics_action(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_churn_customers)
        layout.addWidget(refresh_btn)
        
        # Load initial data
        self._refresh_churn_customers()
        
        return frame
    
    def _refresh_customer_segments(self):
        """Refresh customer segments"""
        try:
            from ui.ai_pages.ai_customer_insights import AICustomerInsights
            
            segments = AICustomerInsights.get_customer_segments()
            
            if segments:
                text = ""
                for seg in segments:
                    emoji = {
                        'VIP': '👑',
                        'Regular': '⭐',
                        'Occasional': '📋',
                        'New': '🆕'
                    }.get(seg['name'], '•')
                    text += f"{emoji} {seg['label']}: {seg['count']} customers\n"
                    
                    # Show top customers in this segment
                    if seg['customers']:
                        names = [c['name'][:15] for c in seg['customers'][:2]]
                        if names:
                            text += f"   └─ {', '.join(names)}\n"
                    text += "\n"
                
                self.customer_segments_label.setText(text)
            else:
                self.customer_segments_label.setText("📋 No customer data available yet.\nStart making sales to see customer insights!")
            self._mark_analytics_refreshed()
                
        except Exception as e:
            logger.error(f"Failed to refresh customer segments: {e}")
            self.customer_segments_label.setText(f"❌ Error loading: {str(e)[:100]}")
    
    def _refresh_inventory_recommendations(self):
        """Refresh inventory recommendations"""
        try:
            from ui.ai_pages.ai_inventory_recommendation import AIInventoryRecommendation
            
            recommendations = AIInventoryRecommendation.get_reorder_recommendations()
            self._set_analytics_metric("stock_alerts", len(recommendations))
            
            if recommendations:
                text = ""
                priority_emojis = {
                    'critical': '🚨',
                    'high': '🔴',
                    'medium': '🟡',
                    'low': '🟢'
                }
                
                # Show only top 5
                for rec in recommendations[:5]:
                    emoji = priority_emojis.get(rec['priority'], '📦')
                    text += f"{emoji} **{rec['name']}**: {rec['stock']} left → Order {rec['recommended_qty']}\n"
                    text += f"   └─ {rec['supplier_name']} | {rec['days_remaining']:.0f} days left\n"
                
                if len(recommendations) > 5:
                    text += f"\n... and {len(recommendations) - 5} more items"
                
                self.inventory_label.setText(text)
            else:
                self.inventory_label.setText("✅ All products have sufficient stock!\nNo reorder recommendations at this time.")
            self._mark_analytics_refreshed()
                
        except Exception as e:
            logger.error(f"Failed to refresh inventory: {e}")
            self.inventory_label.setText(f"❌ Error loading: {str(e)[:100]}")
    
    def _refresh_sales_analytics(self):
        """Refresh sales analytics"""
        try:
            from ui.ai_pages.ai_report_generator import AIReportGenerator
            
            period = self.analytics_period.currentText()
            today = datetime.now().strftime("%Y-%m-%d")
            
            if period == "Today":
                start_date = today
                end_date = today
            elif period == "This Week":
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                end_date = today
            elif period == "This Month":
                start_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")
                end_date = today
            else:  # Last 30 Days
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                end_date = today
            
            report = AIReportGenerator.generate_sales_report(start_date, end_date)
            
            if report and report.get('summary'):
                summary = report['summary']
                self._set_analytics_metric("sales", self._format_ks(summary.get('total_sales', 0)))
                self._set_analytics_metric("transactions", summary.get('total_transactions', 0))
                self._set_analytics_metric("avg_ticket", self._format_ks(summary.get('avg_transaction', 0)))
                self._set_analytics_metric("profit", self._format_ks(summary.get('total_profit', 0)))
                text = f"📊 **{period} Sales Summary**\n\n"
                text += f"💰 Total Sales: **{summary['total_sales']:,.0f} Ks**\n"
                text += f"📋 Transactions: {summary['total_transactions']}\n"
                text += f"📈 Avg Transaction: {summary['avg_transaction']:,.0f} Ks\n"
                text += f"🎯 Total Profit: **{summary['total_profit']:,.0f} Ks**\n"
                
                # Payment types
                if report.get('payment_types'):
                    text += "\n💳 **Payment Methods:**\n"
                    for p in report['payment_types']:
                        pct = (p['total'] / summary['total_sales'] * 100) if summary['total_sales'] > 0 else 0
                        text += f"   • {p['type']}: {pct:.1f}% ({p['total']:,.0f} Ks)\n"
                
                # Top products
                if report.get('top_products'):
                    text += "\n🏆 **Top Products:**\n"
                    for p in report['top_products'][:3]:
                        text += f"   • {p['name']}: {p['revenue']:,.0f} Ks ({p['qty']} sold)\n"
                
                self.sales_analytics_label.setText(text)
            else:
                self._set_analytics_metric("sales", "0 Ks")
                self._set_analytics_metric("transactions", "0")
                self._set_analytics_metric("avg_ticket", "0 Ks")
                self._set_analytics_metric("profit", "0 Ks")
                self.sales_analytics_label.setText(f"📋 No sales data for {period}")
            self._mark_analytics_refreshed()
                
        except Exception as e:
            logger.error(f"Failed to refresh sales analytics: {e}")
            self.sales_analytics_label.setText(f"❌ Error loading: {str(e)[:100]}")
    
    def _refresh_churn_customers(self):
        """Refresh churn risk customers"""
        try:
            from ui.ai_pages.ai_customer_insights import AICustomerInsights
            
            churn_customers = AICustomerInsights.get_churn_risk_customers(90)
            self._set_analytics_metric("churn", len(churn_customers))
            
            if churn_customers:
                text = "⚠️ Customers at risk of churning (90+ days inactive):\n\n"
                for c in churn_customers[:5]:
                    text += f"• {c['name']}: {c['days_inactive']} days inactive"
                    if c['total_orders'] > 0:
                        text += f" | {c['total_orders']} orders"
                    text += f" | {c['total_spent']:,.0f} Ks\n"
                
                if len(churn_customers) > 5:
                    text += f"\n... and {len(churn_customers) - 5} more customers"
                
                self.churn_label.setText(text)
            else:
                self.churn_label.setText("✅ No customers at risk of churning!\nAll customers are active.")
            self._mark_analytics_refreshed()
                
        except Exception as e:
            logger.error(f"Failed to refresh churn customers: {e}")
            self.churn_label.setText(f"❌ Error loading: {str(e)[:100]}")
    
    def _export_analytics(self):
        """Export analytics data"""
        try:
            from ui.ai_pages.ai_report_generator import AIReportGenerator
            
            # Get export options
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Analytics",
                f"analytics_report_{datetime.now().strftime('%Y%m%d')}.csv",
                "CSV Files (*.csv);;JSON Files (*.json)"
            )
            
            if not file_path:
                return
            
            # Generate report
            today = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            report = AIReportGenerator.generate_sales_report(start_date, today)
            
            if not report:
                QMessageBox.warning(self, "Export Error", "No data available to export.")
                return
            
            if file_path.endswith('.csv'):
                # Export to CSV
                if report.get('daily'):
                    success = AIReportGenerator.export_to_csv(
                        report['daily'],
                        file_path,
                        ['date', 'transactions', 'total_sales']
                    )
                    if success:
                        QMessageBox.information(self, "Export Complete", 
                            f"✅ Report exported to:\n{file_path}")
                    else:
                        QMessageBox.warning(self, "Export Error", "Failed to export CSV.")
                        
            elif file_path.endswith('.json'):
                success = AIReportGenerator.export_to_json(report, file_path)
                if success:
                    QMessageBox.information(self, "Export Complete", 
                        f"✅ Report exported to:\n{file_path}")
                else:
                    QMessageBox.warning(self, "Export Error", "Failed to export JSON.")
            
            else:
                QMessageBox.warning(self, "Export Error", "Unsupported file format.")
                
        except Exception as e:
            logger.error(f"Failed to export analytics: {e}")
            QMessageBox.critical(self, "Export Error", f"❌ Failed to export: {str(e)}")
    
    def _create_tools_tab(self):
        """Create the tools tab"""
        colors = get_theme_colors()
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # ============================================================
        # HEADER
        # ============================================================
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 16px 20px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)
        
        title_label = QLabel("🤖 AI Tools")
        title_label.setStyleSheet(f"""
            font-size: 18pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        desc_label = QLabel("AI ကိရိယာများဖြင့် သင်၏ အလုပ်များကို မြန်ဆန်စေပါ")
        desc_label.setStyleSheet(f"""
            font-size: 11pt;
            color: {colors.get('text_secondary', '#636e72')};
        """)
        header_layout.addWidget(desc_label)
        
        layout.addWidget(header_frame)
        
        # ============================================================
        # TOOLS GRID
        # ============================================================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        grid_layout = QGridLayout(scroll_content)
        grid_layout.setSpacing(16)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # AI Tools
        tools = [
            {
                "icon": "📝",
                "title": "AI Product Description",
                "desc": "Product အတွက် AI ဖြင့် ဖော်ပြချက်များ ရေးသားပါ",
                "color": "#5865f2"
            },
            {
                "icon": "📊",
                "title": "AI Sales Analysis",
                "desc": "Sales data ကို AI ဖြင့် ခွဲခြမ်းစိတ်ဖြာပါ",
                "color": "#ed4245"
            },
            {
                "icon": "📈",
                "title": "AI Price Prediction",
                "desc": "AI ဖြင့် ဈေးနှုန်းခန့်မှန်းချက်များ ရယူပါ",
                "color": "#faa81a"
            },
            {
                "icon": "🖼️",
                "title": "AI Image Generator",
                "desc": "Product Image များကို AI ဖြင့် ဖန်တီးပါ",
                "color": "#9b59b6"
            },
            {
                "icon": "📋",
                "title": "AI Report Summary",
                "desc": "Reports များကို AI ဖြင့် အနှစ်ချုပ်ပါ",
                "color": "#1abc9c"
            },
            {
                "icon": "💬",
                "title": "AI Chat Assistant",
                "desc": "Business အကူအညီအတွက် AI Chat ကို မေးမြန်းပါ",
                "color": "#3ba55c"
            },
        ]
        
        row = 0
        col = 0
        for tool in tools:
            card = self._create_tool_card(tool)
            grid_layout.addWidget(card, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_tool_card(self, tool_data):
        """Create a tool card widget"""
        colors = get_theme_colors()
        
        hover_bg = colors.get('hover_bg', '#f0f0f0')
        card_bg = colors.get('card_bg', '#ffffff')
        border_color = colors.get('border', '#e0e0e0')
        text_color = colors.get('text', '#2d3436')
        text_secondary = colors.get('text_secondary', '#636e72')
        
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border-radius: 12px;
                border: 1px solid {border_color};
                padding: 16px;
            }}
            QFrame:hover {{
                border-color: {tool_data['color']};
                background-color: {hover_bg};
            }}
        """)
        card.setFixedHeight(140)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Icon
        icon_label = QLabel(tool_data['icon'])
        icon_label.setStyleSheet("""
            font-size: 28pt;
            background: transparent;
        """)
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(tool_data['title'])
        title_label.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            color: {text_color};
            background: transparent;
        """)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(tool_data['desc'])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"""
            font-size: 9pt;
            color: {text_secondary};
            background: transparent;
        """)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # Click event
        card.mousePressEvent = lambda event, t=tool_data: self._on_tool_clicked(t)
        
        return card
    
    def _on_tool_clicked(self, tool_data):
        """Handle tool card click"""
        logger.info(f"AI Tool clicked: {tool_data['title']}")
        
        # If Chat Assistant is clicked, switch to chat tab (index 1)
        if tool_data['title'] == "AI Chat Assistant":
            self.tabs.setCurrentIndex(1)
            return
        
        # If Sales Analysis is clicked, switch to analytics tab (index 2)
        if tool_data['title'] == "AI Sales Analysis":
            self.tabs.setCurrentIndex(2)
            return
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Coming Soon")
        msg.setText(f"{tool_data['icon']} {tool_data['title']}\n\n{tool_data['desc']}\n\nThis feature is coming soon!")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
    
    def _create_tools_tab(self):
        """Create the tools tab with usable AI shortcuts."""
        colors = get_theme_colors()

        widget = QWidget()
        widget.setObjectName("aiToolsTab")
        widget.setStyleSheet(f"""
            QWidget#aiToolsTab {{
                background-color: {colors.get('bg', '#f5f6fa')};
            }}
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header_frame = QFrame()
        header_frame.setObjectName("AIToolsHeader")
        header_frame.setStyleSheet(f"""
            QFrame#AIToolsHeader {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 8px;
            }}
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(4)

        title_label = QLabel("AI Tools")
        title_label.setStyleSheet(f"""
            font-size: 18pt;
            font-weight: 700;
            color: {colors.get('text', '#212529')};
            background: transparent;
        """)
        header_layout.addWidget(title_label)

        desc_label = QLabel("Quick actions for the AI features that are ready to use in this POS.")
        desc_label.setStyleSheet(f"""
            font-size: 10pt;
            color: {colors.get('text_secondary', '#6c757d')};
            background: transparent;
        """)
        header_layout.addWidget(desc_label)
        layout.addWidget(header_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self.tools_scroll_content = QWidget()
        self.tools_scroll_content.setStyleSheet("background-color: transparent;")
        self.tools_grid_layout = QGridLayout(self.tools_scroll_content)
        self.tools_grid_layout.setSpacing(14)
        self.tools_grid_layout.setContentsMargins(0, 0, 0, 0)
        self._populate_tools_grid()

        scroll.setWidget(self.tools_scroll_content)
        layout.addWidget(scroll)

        return widget

    def _get_ai_tools(self):
        return [
            {
                "icon": "chat",
                "title": "AI Chat Assistant",
                "desc": "Ask about sales, customers, products, stock, and credit.",
                "action": "Open Chat",
                "color": "#5865f2",
                "target_tab": 1,
            },
            {
                "icon": "dashboard",
                "title": "AI Dashboard",
                "desc": "Open KPI cards, trend charts, and daily business signals.",
                "action": "Open Dashboard",
                "color": "#3ba55d",
                "target_tab": 0,
            },
            {
                "icon": "analytics",
                "title": "Sales Analytics",
                "desc": "Review sales patterns, segments, inventory tips, and churn risk.",
                "action": "Open Analytics",
                "color": "#ed4245",
                "target_tab": 2,
            },
            {
                "icon": "inventory_2",
                "title": "Inventory Suggestions",
                "desc": "Run low stock and reorder recommendation assistant.",
                "action": "Run /inventory",
                "color": "#faa81a",
                "chat_command": "/inventory",
            },
            {
                "icon": "groups",
                "title": "Customer Insights",
                "desc": "Find customer groups, purchase behavior, and loyalty chances.",
                "action": "Run /customers",
                "color": "#1abc9c",
                "chat_command": "/customers",
            },
            {
                "icon": "search",
                "title": "Product Search",
                "desc": "Start natural language product search in the AI chat.",
                "action": "Search Products",
                "color": "#9b59b6",
                "chat_prompt": "search ",
            },
        ]

    def _populate_tools_grid(self):
        if not hasattr(self, 'tools_grid_layout'):
            return

        while self.tools_grid_layout.count():
            item = self.tools_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index, tool in enumerate(self._get_ai_tools()):
            row = index // 3
            col = index % 3
            self.tools_grid_layout.addWidget(self._create_tool_card(tool), row, col)

        for col in range(3):
            self.tools_grid_layout.setColumnStretch(col, 1)

    def _create_tool_card(self, tool_data):
        """Create a modern clickable tool card."""
        colors = get_theme_colors()
        is_dark = is_dark_theme()

        card_bg = colors.get('card_bg', '#ffffff')
        hover_bg = colors.get('bg_hover', '#f8f9fa')
        border_color = colors.get('border', '#dee2e6')
        text_color = colors.get('text', '#212529')
        text_secondary = colors.get('text_secondary', '#6c757d')
        accent = tool_data['color']

        card = QFrame()
        card.setObjectName("AIToolCard")
        card.setMinimumHeight(168)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame#AIToolCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-left: 4px solid {accent};
                border-radius: 8px;
            }}
            QFrame#AIToolCard:hover {{
                background-color: {hover_bg};
                border-color: {accent};
                border-left: 4px solid {accent};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {accent}22;
            border-radius: 8px;
            border: 1px solid {accent}55;
        """)
        icon = self._load_colored_icon(tool_data['icon'], size=22)
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(QSize(22, 22)))
        top_layout.addWidget(icon_label)
        top_layout.addStretch()

        action_label = QLabel(tool_data['action'])
        action_label.setStyleSheet(f"""
            color: {accent};
            font-size: 9pt;
            font-weight: 600;
            background: transparent;
        """)
        top_layout.addWidget(action_label)
        layout.addLayout(top_layout)

        title_label = QLabel(tool_data['title'])
        title_label.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: 700;
            color: {text_color};
            background: transparent;
        """)
        layout.addWidget(title_label)

        desc_label = QLabel(tool_data['desc'])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"""
            font-size: 9.5pt;
            line-height: 1.25;
            color: {text_secondary};
            background: transparent;
        """)
        layout.addWidget(desc_label)
        layout.addStretch()

        card.mousePressEvent = lambda event, t=tool_data: self._on_tool_clicked(t)
        return card

    def _on_tool_clicked(self, tool_data):
        """Handle tool card click."""
        logger.info(f"AI Tool clicked: {tool_data['title']}")

        if 'target_tab' in tool_data:
            self.tabs.setCurrentIndex(tool_data['target_tab'])
            return

        if tool_data.get('chat_command'):
            self.tabs.setCurrentIndex(1)
            self.chat_room.input_field.setPlainText(tool_data['chat_command'])
            self.chat_room._send_message()
            return

        if tool_data.get('chat_prompt'):
            self.tabs.setCurrentIndex(1)
            self.chat_room.input_field.setPlainText(tool_data['chat_prompt'])
            self.chat_room.input_field.setFocus()
            return

    def _rebuild_themed_tabs(self):
        if not hasattr(self, 'tabs'):
            return

        current_index = self.tabs.currentIndex()

        analytics_icon = self._load_colored_icon("analytics")
        old_analytics = getattr(self, 'analytics_tab', None)
        self.analytics_tab = self._create_analytics_tab()
        self.tabs.removeTab(2)
        self.tabs.insertTab(2, self.analytics_tab, analytics_icon, "Analytics")
        if old_analytics:
            old_analytics.deleteLater()

        tools_icon = self._load_colored_icon("smart_toy")
        old_tools = getattr(self, 'tools_tab', None)
        self.tools_tab = self._create_tools_tab()
        self.tabs.removeTab(3)
        self.tabs.insertTab(3, self.tools_tab, tools_icon, "AI Tools")
        if old_tools:
            old_tools.deleteLater()

        self.tabs.setCurrentIndex(min(current_index, self.tabs.count() - 1))

    def update_theme(self):
        """Update theme for AI Pages"""
        colors = get_theme_colors()
        bg_color = colors.get('bg', '#f5f6fa')
        self.setStyleSheet(f"background-color: {bg_color};")
        
        # Apply tab style
        self._apply_tab_style()
        
        # Update tab icons
        self._update_tab_icons()
        
        # Update dashboard
        if hasattr(self, 'dashboard'):
            self.dashboard.update_theme()
        
        # Update chat room
        if hasattr(self, 'chat_room'):
            self.chat_room.update_theme()

        self._rebuild_themed_tabs()
        
        # Update all ModernButtons
        for button in self.findChildren(ModernButton):
            button.update_theme()
    
    def refresh(self):
        """Refresh AI Pages data"""
        logger.info("AI Pages refreshed")
        if hasattr(self, 'dashboard'):
            self.dashboard.refresh()
        if hasattr(self, 'chat_room'):
            self.chat_room.refresh()
