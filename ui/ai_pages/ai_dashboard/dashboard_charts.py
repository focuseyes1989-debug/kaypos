"""Qt chart widgets for the AI Dashboard."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ui.themes.theme_manager import get_theme_colors
from utils.currency import format_money


class DashboardCharts:
    """Chart manager for dashboard."""

    def __init__(self, parent):
        self.parent = parent
        self.sales_frame = None
        self.category_frame = None
        self.sales_chart = None
        self.category_chart = None

    def setup(self, colors):
        charts_container = QFrame()
        charts_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        charts_container.setFixedHeight(300)
        charts_container.setStyleSheet("background-color: transparent;")

        charts_layout = QHBoxLayout(charts_container)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setSpacing(12)

        self.sales_frame, self.sales_chart = self._create_chart_frame(
            "Daily Sales Trend",
            _DailySalesChart(),
            colors,
        )
        charts_layout.addWidget(self.sales_frame, 2)

        self.category_frame, self.category_chart = self._create_chart_frame(
            "Sales by Category",
            _HorizontalValueChart(),
            colors,
        )
        charts_layout.addWidget(self.category_frame, 1)

        return charts_container

    def _create_chart_frame(self, title, chart_widget, colors):
        frame = QFrame()
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_frame_style(frame, colors)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        chart_widget.set_title(title)
        layout.addWidget(chart_widget)

        return frame, chart_widget

    def update_sales_chart(self, daily_data):
        if self.sales_chart:
            rows = [(row[0], float(row[2] or 0)) for row in daily_data or []]
            self.sales_chart.set_data(rows)

    def update_category_chart(self, category_data):
        if self.category_chart:
            rows = [(row[0] or "Uncategorized", float(row[2] or 0)) for row in category_data or []]
            self.category_chart.set_data(rows)

    def update_theme(self):
        colors = get_theme_colors()
        for frame in (self.sales_frame, self.category_frame):
            if frame:
                self._apply_frame_style(frame, colors)
        for chart in (self.sales_chart, self.category_chart):
            if chart:
                chart.update()

    def _apply_frame_style(self, frame, colors):
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dde2e8')};
                border-radius: 8px;
            }}
        """)


class _BaseChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._data = []
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_title(self, title):
        self._title = title

    def set_data(self, data):
        self._data = data
        self.update()

    def _palette(self):
        colors = get_theme_colors()
        return {
            "bg": QColor(colors.get("card_bg", colors.get("bg", "#ffffff"))),
            "text": QColor(colors.get("text", "#212529")),
            "muted": QColor(colors.get("text_secondary", "#6c757d")),
            "primary": QColor(colors.get("primary", "#5865f2")),
            "accent": QColor(colors.get("success", "#2ecc71")),
            "grid": QColor(colors.get("border", "#dde2e8")),
        }

    def _draw_title(self, painter, rect, palette):
        title_font = QFont(self.font())
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(palette["text"])
        painter.drawText(rect.left(), rect.top(), rect.width(), 24, Qt.AlignmentFlag.AlignLeft, self._title)

    def _draw_empty(self, painter, rect, palette):
        painter.setFont(self.font())
        painter.setPen(palette["muted"])
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Data Available")


class _DailySalesChart(_BaseChart):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        palette = self._palette()
        painter.fillRect(self.rect(), palette["bg"])
        rect = self.rect().adjusted(12, 10, -12, -12)
        self._draw_title(painter, rect, palette)

        chart_rect = rect.adjusted(0, 42, 0, -18)
        if not self._data:
            self._draw_empty(painter, chart_rect, palette)
            return

        data = self._data[-14:]
        max_value = max(value for _, value in data) or 1
        gap = 6
        bar_width = max(8, (chart_rect.width() - gap * (len(data) - 1)) / max(1, len(data)))

        painter.setPen(QPen(palette["grid"], 1))
        for i in range(4):
            y = chart_rect.top() + (chart_rect.height() * i / 3)
            painter.drawLine(chart_rect.left(), int(y), chart_rect.right(), int(y))

        for index, (label, value) in enumerate(data):
            x = chart_rect.left() + index * (bar_width + gap)
            height = (value / max_value) * max(1, chart_rect.height() - 22)
            y = chart_rect.bottom() - height

            color = palette["primary"] if index == len(data) - 1 else palette["accent"]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, bar_width, height), 4, 4)

            if value > 0 and bar_width > 22:
                painter.setPen(palette["muted"])
                painter.drawText(int(x - 8), int(y - 18), int(bar_width + 16), 16, Qt.AlignmentFlag.AlignCenter, format_money(value))

            painter.setPen(palette["muted"])
            short_label = str(label)[5:] if len(str(label)) >= 10 else str(label)
            painter.drawText(int(x - 4), chart_rect.bottom() + 4, int(bar_width + 8), 16, Qt.AlignmentFlag.AlignCenter, short_label)


class _HorizontalValueChart(_BaseChart):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        palette = self._palette()
        painter.fillRect(self.rect(), palette["bg"])
        rect = self.rect().adjusted(12, 10, -12, -12)
        self._draw_title(painter, rect, palette)

        chart_rect = rect.adjusted(0, 42, 0, 0)
        data = [(name, value) for name, value in self._data[:8] if value > 0]
        if not data:
            self._draw_empty(painter, chart_rect, palette)
            return

        max_value = max(value for _, value in data) or 1
        row_height = max(24, min(36, chart_rect.height() // max(1, len(data))))
        label_width = min(150, max(90, chart_rect.width() // 3))
        bar_left = chart_rect.left() + label_width + 10
        bar_width_max = max(50, chart_rect.right() - bar_left - 74)

        painter.setFont(self.font())
        for index, (name, value) in enumerate(data):
            y = chart_rect.top() + index * row_height
            if y + row_height > chart_rect.bottom():
                break

            painter.setPen(palette["text"])
            label = painter.fontMetrics().elidedText(str(name), Qt.TextElideMode.ElideRight, label_width)
            painter.drawText(chart_rect.left(), y, label_width, row_height, Qt.AlignmentFlag.AlignVCenter, label)

            width = int((value / max_value) * bar_width_max)
            color = palette["primary"] if index % 2 == 0 else palette["accent"]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(bar_left, y + 7, max(3, width), max(8, row_height - 14)), 4, 4)

            painter.setPen(palette["muted"])
            painter.drawText(bar_left + width + 8, y, 70, row_height, Qt.AlignmentFlag.AlignVCenter, format_money(value))
