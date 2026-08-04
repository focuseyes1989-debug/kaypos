# ui/dashboard/ai_assistant/chart_tab.py
"""Chart Tab for AI Assistant - Sales charts and visualizations"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from typing import Optional

from ui.themes.theme_manager import is_dark_theme, get_theme_colors
from utils.currency import get_currency_symbol, format_money
from .data_loader import (
    get_top_products, get_top_categories, get_payment_breakdown,
    get_today_yesterday_sales, get_weekly_comparison, get_monthly_comparison
)
from .utils import get_date_range, get_themed_icon_helper
from .styles import get_section_header_style

import math


class ChartTab(QWidget):
    """Charts and visualizations for sales data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        self._parent = parent
        self._from_date = ""
        self._to_date = ""
        
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        """Setup the chart tab UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # Header
        header_label = QLabel("📊 Sales Charts & Analytics")
        header_label.setStyleSheet(get_section_header_style(self._is_dark))
        header_label.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Scroll area for charts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #5865f2;
                border-radius: 2px;
                min-height: 20px;
            }
        """)
        
        # Content widget
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(12)
        self.content_layout.setContentsMargins(0, 0, 0, 8)
        self.content_layout.addStretch()
        
        scroll.setWidget(self.content)
        layout.addWidget(scroll)
    
    def _apply_style(self):
        """Apply theme styles"""
        colors = get_theme_colors()
        bg_color = colors.get('bg', '#2f3136' if self._is_dark else '#f8f9fa')
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {colors.get('text', '#ffffff' if self._is_dark else '#212529')};
            }}
        """)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_style()
        self.update_data(self._from_date, self._to_date)
    
    def update_data(self, from_date, to_date):
        """Update charts with new data"""
        self._from_date = from_date
        self._to_date = to_date
        
        # Clear existing content
        for i in range(self.content_layout.count() - 1, -1, -1):
            item = self.content_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        
        # Add charts
        self._add_sales_comparison_chart()
        self._add_top_products_chart()
        self._add_top_categories_chart()
        self._add_payment_breakdown_chart()
        
        # Add stretch at the end
        self.content_layout.addStretch()
    
    # ============================================================
    # CHART DRAWING METHODS
    # ============================================================
    
    def _add_sales_comparison_chart(self):
        """Add daily sales comparison chart (Today vs Yesterday)"""
        today_sales, _, yesterday_sales = get_today_yesterday_sales()
        today_net = today_sales
        
        if today_net == 0 and yesterday_sales == 0:
            return
        
        container = self._create_chart_container("📈 Daily Sales Comparison")
        layout = container.layout()
        if layout is not None:
            # Create bar chart widget
            chart_widget = _BarChartWidget(
                ["Yesterday", "Today"],
                [yesterday_sales, today_net],
                ["#95a5a6", "#5865f2"],
                self._is_dark
            )
            chart_widget.setMinimumHeight(150)
            layout.addWidget(chart_widget)
        
        self.content_layout.insertWidget(self.content_layout.count() - 1, container)
    
    def _add_top_products_chart(self):
        """Add top products horizontal bar chart"""
        if not self._from_date or not self._to_date:
            return
        
        products = get_top_products(self._from_date, self._to_date)
        if not products:
            return
        
        container = self._create_chart_container("🏆 Top Products by Sales")
        layout = container.layout()
        if layout is not None:
            # Take top 5
            top_products = products[:5]
            names = [p[0][:20] + "..." if len(p[0]) > 20 else p[0] for p in top_products]
            values = [p[2] for p in top_products]
            
            chart_widget = _HorizontalBarChart(
                names,
                values,
                ["#5865f2", "#9b59b6", "#e67e22", "#2ecc71", "#e74c3c"],
                self._is_dark
            )
            chart_widget.setMinimumHeight(200)
            layout.addWidget(chart_widget)
        
        self.content_layout.insertWidget(self.content_layout.count() - 1, container)
    
    def _add_top_categories_chart(self):
        """Add top categories pie chart"""
        if not self._from_date or not self._to_date:
            return
        
        categories = get_top_categories(self._from_date, self._to_date)
        if not categories:
            return
        
        container = self._create_chart_container("📊 Top Categories")
        layout = container.layout()
        if layout is not None:
            top_cats = categories[:4]
            names = [c[0] for c in top_cats]
            values = [c[1] for c in top_cats]
            
            # If there are more categories, group as "Others"
            if len(categories) > 4:
                others_sum = sum(c[1] for c in categories[4:])
                if others_sum > 0:
                    names.append("Others")
                    values.append(others_sum)
            
            chart_widget = _PieChartWidget(
                names,
                values,
                ["#5865f2", "#2ecc71", "#e67e22", "#9b59b6", "#95a5a6"],
                self._is_dark
            )
            chart_widget.setMinimumHeight(200)
            layout.addWidget(chart_widget)
        
        self.content_layout.insertWidget(self.content_layout.count() - 1, container)
    
    def _add_payment_breakdown_chart(self):
        """Add payment breakdown chart"""
        if not self._from_date or not self._to_date:
            return
        
        payments = get_payment_breakdown(self._from_date, self._to_date)
        if not payments:
            return
        
        container = self._create_chart_container("💳 Payment Breakdown")
        layout = container.layout()
        if layout is not None:
            names = [p[0] for p in payments]
            values = [p[1] for p in payments]
            
            chart_widget = _PieChartWidget(
                names,
                values,
                ["#2ecc71", "#3498db", "#f39c12", "#e74c3c", "#9b59b6"],
                self._is_dark
            )
            chart_widget.setMinimumHeight(180)
            layout.addWidget(chart_widget)
        
        self.content_layout.insertWidget(self.content_layout.count() - 1, container)
    
    def _create_chart_container(self, title):
        """Create a styled container for charts"""
        colors = get_theme_colors()
        
        container = QFrame()
        if self._is_dark:
            container.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.get('card_bg', '#36393f')};
                    border: 1px solid {colors.get('border', '#40444b')};
                    border-radius: 8px;
                    padding: 8px;
                }}
            """)
        else:
            container.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.get('card_bg', '#ffffff')};
                    border: 1px solid {colors.get('border', '#dee2e6')};
                    border-radius: 8px;
                    padding: 8px;
                }}
            """)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 6, 8, 6)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(get_section_header_style(self._is_dark))
        layout.addWidget(title_label)
        
        return container


# ============================================================
# CUSTOM CHART WIDGETS
# ============================================================

class _BarChartWidget(QWidget):
    """Simple bar chart widget"""
    
    def __init__(self, labels, values, colors, is_dark, parent=None):
        super().__init__(parent)
        self._labels = labels
        self._values = values
        self._colors = colors
        self._is_dark = is_dark
        self._padding = 40
        
        self.setMinimumHeight(120)
        # Prevent recursive repaint
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width() - self._padding * 2
        height = self.height() - self._padding - 30
        
        if width <= 0 or height <= 0 or len(self._values) == 0:
            painter.end()
            return
        
        # Find max value
        max_val = max(self._values) if self._values else 1
        if max_val == 0:
            max_val = 1
        
        colors = get_theme_colors()
        text_color = colors.get('text', '#ffffff' if self._is_dark else '#212529')
        text_color_sec = colors.get('text_secondary', '#72767d' if self._is_dark else '#6c757d')
        
        bar_width = min(width / len(self._values) * 0.6, 60)
        bar_spacing = (width - bar_width * len(self._values)) / (len(self._values) + 1)
        
        painter.setPen(QPen(QColor(text_color_sec), 1))
        
        # Draw grid lines
        for i in range(5):
            y = self._padding + height - (i / 4) * height
            painter.drawLine(int(self._padding - 5), int(y), int(self._padding + width), int(y))
        
        # Draw bars
        for i, (label, value, color) in enumerate(zip(self._labels, self._values, self._colors)):
            x = self._padding + bar_spacing + i * (bar_width + bar_spacing)
            bar_height = (value / max_val) * height * 0.85
            
            # Bar
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor(color), 1))
            painter.drawRoundedRect(
                int(x), 
                int(self._padding + height - bar_height), 
                int(bar_width), 
                int(bar_height),
                3, 3
            )
            
            # Value label
            painter.setPen(QPen(QColor(text_color)))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            
            if self._is_dark:
                painter.setPen(QPen(QColor("#ffffff")))
            else:
                painter.setPen(QPen(QColor("#212529")))
            
            # Format value
            if value >= 1000000:
                val_text = f"{value/1000000:.1f}M"
            elif value >= 1000:
                val_text = f"{value/1000:.1f}K"
            else:
                val_text = f"{value:.0f}"
            
            painter.drawText(
                int(x), 
                int(self._padding + height - bar_height - 12),
                int(bar_width),
                20,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                val_text
            )
            
            # Label
            painter.setPen(QPen(QColor(text_color_sec)))
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(
                int(x),
                int(self._padding + height + 5),
                int(bar_width),
                20,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label
            )
        
        painter.end()


class _HorizontalBarChart(QWidget):
    """Horizontal bar chart for top products"""
    
    def __init__(self, labels, values, colors, is_dark, parent=None):
        super().__init__(parent)
        self._labels = labels
        self._values = values
        self._colors = colors
        self._is_dark = is_dark
        
        self.setMinimumHeight(180)
        # Prevent recursive repaint
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width() - 20
        height = self.height() - 20
        
        if width <= 0 or height <= 0 or len(self._values) == 0:
            painter.end()
            return
        
        max_val = max(self._values) if self._values else 1
        if max_val == 0:
            max_val = 1
        
        colors = get_theme_colors()
        text_color = colors.get('text', '#ffffff' if self._is_dark else '#212529')
        text_color_sec = colors.get('text_secondary', '#72767d' if self._is_dark else '#6c757d')
        
        num_items = len(self._values)
        bar_height = min((height - 20) / num_items, 30)
        bar_spacing = min((height - 20 - bar_height * num_items) / (num_items + 1), 8)
        
        label_width = max(80, min(120, width * 0.35))
        chart_width = width - label_width - 40
        
        painter.setPen(QPen(QColor(text_color_sec), 0.5))
        
        for i, (label, value, color) in enumerate(zip(self._labels, self._values, self._colors)):
            y = 10 + bar_spacing + i * (bar_height + bar_spacing)
            bar_length = (value / max_val) * chart_width
            
            # Label
            painter.setPen(QPen(QColor(text_color)))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(
                5, int(y), 
                int(label_width - 5), int(bar_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                label
            )
            
            # Bar
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor(color), 1))
            painter.drawRoundedRect(
                int(label_width + 10),
                int(y),
                int(bar_length),
                int(bar_height),
                3, 3
            )
            
            # Value
            painter.setPen(QPen(QColor(text_color_sec)))
            font.setPointSize(7)
            painter.setFont(font)
            
            if value >= 1000000:
                val_text = f"{value/1000000:.1f}M"
            elif value >= 1000:
                val_text = f"{value/1000:.1f}K"
            else:
                val_text = f"{value:.0f}"
            
            painter.drawText(
                int(label_width + 15 + bar_length),
                int(y),
                int(60),
                int(bar_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                val_text
            )
        
        painter.end()


class _PieChartWidget(QWidget):
    """Simple pie/donut chart widget"""
    
    def __init__(self, labels, values, colors, is_dark, parent=None):
        super().__init__(parent)
        self._labels = labels
        self._values = values
        self._colors = colors
        self._is_dark = is_dark
        self._legend_height = 20
        
        self.setMinimumHeight(160)
        # Prevent recursive repaint
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        if width <= 0 or height <= 0 or len(self._values) == 0:
            painter.end()
            return
        
        total = sum(self._values)
        if total == 0:
            painter.end()
            return
        
        colors = get_theme_colors()
        text_color = colors.get('text', '#ffffff' if self._is_dark else '#212529')
        text_color_sec = colors.get('text_secondary', '#72767d' if self._is_dark else '#6c757d')
        
        # Get background color safely
        bg_color = colors.get('bg')
        if bg_color is None:
            bg_color = '#2f3136' if self._is_dark else '#f8f9fa'
        
        # Calculate pie size and position
        legend_width = min(120, width * 0.3)
        pie_size = min(height - 30, width - legend_width - 40)
        pie_x = (width - legend_width - pie_size) // 2
        pie_y = (height - pie_size) // 2
        
        # Draw pie
        start_angle = -90
        for i, (label, value, color) in enumerate(zip(self._labels, self._values, self._colors)):
            angle = (value / total) * 360
            
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor(color), 1))
            painter.drawPie(
                int(pie_x), int(pie_y),
                int(pie_size), int(pie_size),
                int(start_angle * 16),
                int(angle * 16)
            )
            start_angle += angle
        
        # Draw center hole for donut
        hole_radius = pie_size * 0.30
        painter.setBrush(QBrush(QColor(bg_color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(pie_x + pie_size/2 - hole_radius/2),
            int(pie_y + pie_size/2 - hole_radius/2),
            int(hole_radius),
            int(hole_radius)
        )
        
        # Draw total in center
        painter.setPen(QPen(QColor(text_color)))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        
        total_text = f"{total:,.0f}"
        painter.drawText(
            int(pie_x + pie_size/2 - 30),
            int(pie_y + pie_size/2 - 10),
            60, 20,
            Qt.AlignmentFlag.AlignCenter,
            total_text
        )
        
        painter.setPen(QPen(QColor(text_color_sec)))
        font.setPointSize(6)
        painter.setFont(font)
        painter.drawText(
            int(pie_x + pie_size/2 - 30),
            int(pie_y + pie_size/2 + 5),
            60, 15,
            Qt.AlignmentFlag.AlignCenter,
            "Total"
        )
        
        # Draw legend
        legend_x = pie_x + pie_size + 15
        legend_y = pie_y + 10
        
        for i, (label, value, color) in enumerate(zip(self._labels, self._values, self._colors)):
            item_height = 22
            y_pos = legend_y + i * item_height
            
            # Color box
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor(color), 1))
            painter.drawRoundedRect(
                int(legend_x), int(y_pos),
                12, 12,
                2, 2
            )
            
            # Label
            painter.setPen(QPen(QColor(text_color)))
            font.setPointSize(7)
            painter.setFont(font)
            
            label_text = label[:15] + "..." if len(label) > 15 else label
            pct = (value / total) * 100
            
            painter.drawText(
                int(legend_x + 18), int(y_pos),
                int(legend_width - 20), 12,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{label_text} ({pct:.0f}%)"
            )
        
        painter.end()