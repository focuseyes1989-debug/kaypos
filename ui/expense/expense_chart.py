"""Simple native Qt charts for the Expense page.

The visual language matches AI Dashboard charts: a quiet card, compact
controls, rounded bars, short labels and no Matplotlib toolbar.
"""

from PyQt6.QtCore import QDate, QRectF, Qt
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models.database import connect_db
from ui.ai_pages.ai_dashboard.dashboard_charts import _DailySalesChart, _HorizontalValueChart
from ui.themes.theme_manager import get_theme_colors, theme_manager
from utils.currency import format_money


class _MonthlyExpenseChart(_DailySalesChart):
    """AI Dashboard-style bars sized sensibly for a small number of months."""

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self._palette()
        painter.fillRect(self.rect(), palette["bg"])
        rect = self.rect().adjusted(12, 10, -12, -12)
        self._draw_title(painter, rect, palette)
        chart_rect = rect.adjusted(0, 42, 0, -22)

        data = [(label, value) for label, value in self._data[-12:] if value >= 0]
        if not data:
            self._draw_empty(painter, chart_rect, palette)
            return

        max_value = max(value for _, value in data) or 1
        gap = 18
        bar_width = min(72, max(24, (chart_rect.width() - gap * (len(data) - 1)) / len(data)))
        content_width = bar_width * len(data) + gap * (len(data) - 1)
        start_x = chart_rect.left() + max(0, (chart_rect.width() - content_width) / 2)

        painter.setPen(QPen(palette["grid"], 1))
        for index in range(4):
            y = chart_rect.top() + chart_rect.height() * index / 3
            painter.drawLine(chart_rect.left(), int(y), chart_rect.right(), int(y))

        for index, (label, value) in enumerate(data):
            x = start_x + index * (bar_width + gap)
            height = (value / max_value) * max(1, chart_rect.height() - 28)
            y = chart_rect.bottom() - height
            color = palette["primary"] if index == len(data) - 1 else palette["accent"]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(2, height)), 4, 4)

            painter.setPen(palette["muted"])
            painter.drawText(
                int(x - 18), int(max(chart_rect.top(), y - 20)), int(bar_width + 36), 17,
                Qt.AlignmentFlag.AlignCenter, format_money(value),
            )
            month_label = str(label)[2:] if len(str(label)) == 7 else str(label)
            painter.drawText(
                int(x - 6), chart_rect.bottom() + 5, int(bar_width + 12), 17,
                Qt.AlignmentFlag.AlignCenter, month_label,
            )


class ExpenseChartWidget(QWidget):
    """Filtered expense charts using the same widgets as AI Dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self._from_date = None
        self._to_date = None
        self._category = "All Categories"
        self._search_text = ""
        self._setup_ui()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        self.load_chart()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(10)

        controls = QHBoxLayout()
        controls.setContentsMargins(2, 0, 2, 0)
        controls.setSpacing(8)
        self.chart_type_label = QLabel("View:")
        controls.addWidget(self.chart_type_label)

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Expenses by Category", "Monthly Trend"])
        self.chart_type_combo.setMinimumWidth(180)
        self.chart_type_combo.currentIndexChanged.connect(self.load_chart)
        controls.addWidget(self.chart_type_combo)

        self.date_info_label = QLabel()
        controls.addWidget(self.date_info_label)
        controls.addStretch()

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setFixedHeight(32)
        self.btn_refresh.clicked.connect(self.load_chart)
        controls.addWidget(self.btn_refresh)
        root.addLayout(controls)

        self.chart_frame = QFrame()
        self.chart_frame.setMinimumHeight(430)
        frame_layout = QVBoxLayout(self.chart_frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)

        self.category_chart = _HorizontalValueChart("danger", "warning")
        self.category_chart.set_title("Expenses by Category")
        self.trend_chart = _MonthlyExpenseChart()
        self.trend_chart.set_title("Monthly Expense Trend")
        frame_layout.addWidget(self.category_chart)
        frame_layout.addWidget(self.trend_chart)
        self.trend_chart.hide()
        root.addWidget(self.chart_frame, 1)
        self._apply_style()

    def _apply_style(self):
        colors = get_theme_colors()
        self.chart_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#dde2e8')};
                border-radius: 8px;
            }}
        """)
        self.date_info_label.setStyleSheet(
            f"color: {colors.get('text_secondary', '#6c757d')}; font-size: 10pt;"
        )

    def _on_theme_changed(self, _theme_name):
        self._apply_style()
        self.category_chart.update()
        self.trend_chart.update()

    def set_date_range(self, from_date, to_date):
        self._from_date = from_date
        self._to_date = to_date

    def set_filters(self, category="All Categories", search_text=""):
        self._category = category or "All Categories"
        self._search_text = (search_text or "").strip().lower()

    def get_date_range(self):
        if self._from_date and self._to_date:
            return self._from_date, self._to_date
        today = QDate.currentDate()
        return today.addDays(-30).toString("yyyy-MM-dd"), today.toString("yyyy-MM-dd")

    def _where_clause(self, from_date, to_date):
        clauses = ["expense_date BETWEEN ? AND ?"]
        params = [from_date, to_date]
        if self._category != "All Categories":
            clauses.append("category = ?")
            params.append(self._category)
        if self._search_text:
            clauses.append(
                "(LOWER(COALESCE(description, '')) LIKE ? "
                "OR LOWER(COALESCE(reference_no, '')) LIKE ?)"
            )
            term = f"%{self._search_text}%"
            params.extend([term, term])
        return " AND ".join(clauses), params

    def get_expense_data(self, from_date, to_date):
        where_sql, params = self._where_clause(from_date, to_date)
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT COALESCE(category, 'Uncategorized'), COALESCE(SUM(amount), 0) AS total
                FROM expenses
                WHERE {where_sql}
                GROUP BY category
                ORDER BY total DESC
            """, params)
            return [(category, float(amount or 0)) for category, amount in cursor.fetchall() if amount and amount > 0]
        finally:
            conn.close()

    def get_monthly_data(self, from_date, to_date):
        where_sql, params = self._where_clause(from_date, to_date)
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT SUBSTR(expense_date, 1, 7) AS month, COALESCE(SUM(amount), 0) AS total
                FROM expenses
                WHERE {where_sql}
                GROUP BY SUBSTR(expense_date, 1, 7)
                ORDER BY month
            """, params)
            return [(month, float(amount or 0)) for month, amount in cursor.fetchall() if month]
        finally:
            conn.close()

    def load_chart(self, *_args):
        from_date, to_date = self.get_date_range()
        self.date_info_label.setText(f"{from_date}  —  {to_date}")
        show_categories = self.chart_type_combo.currentIndex() == 0
        self.category_chart.setVisible(show_categories)
        self.trend_chart.setVisible(not show_categories)
        if show_categories:
            self.category_chart.set_data(self.get_expense_data(from_date, to_date))
        else:
            self.trend_chart.set_data(self.get_monthly_data(from_date, to_date))

    def refresh(self):
        self.load_chart()

    def retranslateUi(self):
        self.chart_type_label.setText("View:")
        self.btn_refresh.setText("Refresh")
