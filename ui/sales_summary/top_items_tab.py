# ui/sales_summary/top_items_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor
from models.database import connect_db
from utils.currency import format_money
from utils.system_theme import system_theme
# ✅ Import theme manager
from ui.themes.theme_manager import theme_manager, get_theme_colors


class TopItemsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.full_data = []
        self.current_theme = "Light"
        self._chart_enabled = True
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.figure = None
        self.canvas = None
        self.chart_widget = _TopItemsBarChart(self)
        self.chart_widget.setObjectName("topItemsChart")
        self.chart_scroll = QScrollArea()
        self.chart_scroll.setObjectName("topItemsChartScroll")
        self.chart_scroll.setWidgetResizable(True)
        self.chart_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chart_scroll.setAutoFillBackground(False)
        self.chart_scroll.viewport().setAutoFillBackground(False)
        self.chart_scroll.viewport().setStyleSheet("background: transparent; border: none;")
        self.chart_scroll.setWidget(self.chart_widget)
        layout.addWidget(self.chart_scroll)
        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget#topItemsChart {
                background: transparent;
                border: none;
            }
            QScrollArea#topItemsChartScroll,
            QScrollArea#topItemsChartScroll QWidget#qt_scrollarea_viewport {
                background: transparent;
                border: none;
            }
        """)
        
        # Connect theme change signal from system_theme
        system_theme.theme_changed.connect(self.on_theme_changed)
        theme_manager.theme_changed.connect(self.on_theme_manager_changed)
        self.current_theme = self._get_current_theme()

    def _get_current_theme(self):
        """Get current theme from database"""
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except:
            return "Light"
    
    def on_theme_changed(self, theme_name):
        """Handle theme change from system_theme"""
        self.current_theme = theme_name
        # ✅ No style to update - just update chart
        self.update_chart()
    
    def on_theme_manager_changed(self, theme_name):
        """✅ Handle theme change from theme_manager - auto refresh chart and table"""
        self.current_theme = theme_name
        # ✅ No style to update - just update chart
        self.update_chart()
    
    def load(self, from_date, to_date, lang_code):
        """Load data and update the chart."""
        conn = connect_db()
        cursor = conn.cursor()
        
        # ✅ FIX: Use same calculation as ItemsTab
        cursor.execute("""
            SELECT 
                si.product_name,
                COALESCE(SUM(si.total) - SUM(s.discount_amount), 0) as net_sales
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.status = 'completed' AND date(s.created_at) BETWEEN ? AND ?
            GROUP BY si.product_name
            ORDER BY net_sales DESC
            LIMIT 20
        """, (from_date, to_date))
        rows = cursor.fetchall()
        conn.close()
        
        # Sort by net sales descending (already sorted from query)
        self.full_data = [list(row) for row in rows]
        
        # Update current theme
        self.current_theme = self._get_current_theme()
        
        # Update chart
        self.update_chart()
    
    def update_chart(self):
        """Update the chart with current data."""
        if hasattr(self, "chart_widget"):
            self.chart_widget.set_data(self.full_data)
    
    def retranslateUi(self):
        """Retranslate UI"""
        self.update_chart()
    
    def showEvent(self, event):
        """Handle show event - update chart with current theme"""
        self.current_theme = self._get_current_theme()
        self.update_chart()
        super().showEvent(event)


class _TopItemsBarChart(QWidget):
    """Lightweight Qt chart for top item sales."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self.setMinimumHeight(180)

    def set_data(self, data):
        self._data = [(str(name or ""), float(value or 0)) for name, value in data]
        self.setMinimumHeight(max(180, 76 + min(20, len(self._data)) * 32))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = get_theme_colors()
        muted_color = QColor(colors.get("text_secondary", "#6c757d"))
        value_color = QColor(colors.get("text_secondary", "#6c757d"))
        palette = [
            QColor("#dc4765"),
            QColor("#df8b28"),
            QColor("#2fc879"),
        ]

        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.transparent))
        chart_rect = self.rect().adjusted(14, 14, -14, -14)
        if not self._data:
            painter.setFont(self.font())
            painter.setPen(muted_color)
            painter.drawText(chart_rect, Qt.AlignmentFlag.AlignCenter, "No Data Available")
            return

        max_value = max(value for _, value in self._data) or 1
        row_height = 27
        bar_height = 13
        value_width = 108
        label_width = min(150, max(110, chart_rect.width() // 4))
        bar_left = chart_rect.left() + label_width + 12
        bar_area_width = max(80, chart_rect.right() - bar_left - value_width - 10)

        painter.setFont(self.font())
        for index, (name, value) in enumerate(self._data[:20]):
            y = chart_rect.top() + index * row_height
            if y + bar_height > chart_rect.bottom():
                break

            painter.setPen(QColor(colors.get("text", "#212529")))
            label = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, label_width)
            painter.drawText(
                chart_rect.left(),
                y,
                label_width,
                row_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

            bar_width = int((value / max_value) * bar_area_width)
            bar_rect = QRectF(bar_left, y + (row_height - bar_height) / 2, max(4, bar_width), bar_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette[index % len(palette)])
            painter.drawRoundedRect(bar_rect, 3, 3)

            painter.setPen(value_color)
            painter.drawText(
                int(bar_rect.right()) + 8,
                y,
                value_width,
                bar_height + 6,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                format_money(value),
            )


__all__ = ['TopItemsTab']

