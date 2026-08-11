# ui/sales_summary/top_items_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen
from models.database import connect_db
from utils.currency import format_money
from utils.language import lang
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
        
        # Tab widget for Chart and Table views
        self.view_tabs = QTabWidget()
        
        # Chart tab
        self.chart_tab = QWidget()
        chart_layout = QVBoxLayout()
        self.figure = None
        self.canvas = None
        self.chart_widget = _TopItemsBarChart(self)
        chart_layout.addWidget(self.chart_widget)
        self.chart_tab.setLayout(chart_layout)
        self.view_tabs.addTab(self.chart_tab, "Chart")
        
        # Table tab (without refresh button)
        self.table_tab = QWidget()
        table_layout = QVBoxLayout()
        
        # ✅ Table with PyQt6 default style - no custom styling
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # ✅ Use PyQt6 default selection behavior
        # No custom selection mode - use default
        # No custom focus policy - use default
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # ✅ NO style sheet applied - use PyQt6 default
        # self.table.setStyleSheet("")  # Not needed
        
        table_layout.addWidget(self.table)
        
        self.table_tab.setLayout(table_layout)
        self.view_tabs.addTab(self.table_tab, "Table")
        
        layout.addWidget(self.view_tabs)
        self.setLayout(layout)
        
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
        """Load data and update both table and chart"""
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
        
        # Update table
        self._update_table(lang_code)
        
        # Update chart
        self.update_chart()
    
    def _update_table(self, lang_code):
        """Update the table view"""
        self.table.setRowCount(0)
        for row_data in self.full_data:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(row_data[0]))
            self.table.setItem(r, 1, QTableWidgetItem(format_money(row_data[1])))
        
        if lang_code == "my":
            self.table.setHorizontalHeaderLabels(["ပစ္စည်းအမည်", "အသားတင်ရောင်းအား"])
        else:
            self.table.setHorizontalHeaderLabels(["Product Name", "Net Sales"])
    
    def update_chart(self):
        """Update the chart with current data."""
        if hasattr(self, "chart_widget"):
            self.chart_widget.set_data(self.full_data)
    
    def retranslateUi(self):
        """Retranslate UI"""
        lang_code = lang.get_current()
        if lang_code == "my":
            self.view_tabs.setTabText(0, "Chart")
            self.view_tabs.setTabText(1, "Table")
        else:
            self.view_tabs.setTabText(0, "Chart")
            self.view_tabs.setTabText(1, "Table")
        
        self._update_table(lang_code)
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
        self.setMinimumHeight(420)

    def set_data(self, data):
        self._data = [(str(name or ""), float(value or 0)) for name, value in data]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = get_theme_colors()
        text_color = QColor(colors.get("text", "#212529"))
        muted_color = QColor(colors.get("text_secondary", "#6c757d"))
        bar_color = QColor(colors.get("primary", "#5865f2"))
        grid_color = QColor(colors.get("border", "#dee2e6"))

        rect = self.rect().adjusted(18, 18, -18, -18)
        painter.fillRect(self.rect(), QColor(colors.get("card_bg", colors.get("bg", "#ffffff"))))

        title_font = QFont(self.font())
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(rect.left(), rect.top(), rect.width(), 24, Qt.AlignmentFlag.AlignLeft, "Top 20 Sales by Item")

        chart_rect = rect.adjusted(0, 38, 0, 0)
        if not self._data:
            painter.setFont(self.font())
            painter.setPen(muted_color)
            painter.drawText(chart_rect, Qt.AlignmentFlag.AlignCenter, "No Data Available")
            return

        max_value = max(value for _, value in self._data) or 1
        row_height = max(24, min(38, chart_rect.height() // max(1, len(self._data))))
        label_width = min(260, max(150, chart_rect.width() // 3))
        bar_area_left = chart_rect.left() + label_width + 12
        bar_area_width = max(80, chart_rect.right() - bar_area_left - 100)

        painter.setFont(self.font())
        for index, (name, value) in enumerate(self._data[:20]):
            y = chart_rect.top() + index * row_height
            if y + row_height > chart_rect.bottom():
                break

            painter.setPen(text_color)
            elided_name = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, label_width)
            painter.drawText(chart_rect.left(), y, label_width, row_height, Qt.AlignmentFlag.AlignVCenter, elided_name)

            bar_width = int((value / max_value) * bar_area_width)
            bar_rect = QRectF(bar_area_left, y + 7, max(3, bar_width), max(8, row_height - 14))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_color)
            painter.drawRoundedRect(bar_rect, 4, 4)

            painter.setPen(QPen(grid_color, 1))
            painter.drawLine(bar_area_left, y + row_height - 1, chart_rect.right(), y + row_height - 1)

            painter.setPen(text_color)
            painter.drawText(
                bar_area_left + bar_width + 8,
                y,
                92,
                row_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                format_money(value),
            )


__all__ = ['TopItemsTab']

