# ui/expense/expense_chart.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from datetime import datetime
import numpy as np
import os
import logging
import warnings
from utils.matplotlib_fonts import configure_myanmar_matplotlib_font

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
configure_myanmar_matplotlib_font()

# ✅ Import theme
from ui.themes.theme_manager import theme_manager, is_dark_theme


class ExpenseChartWidget(QWidget):
    """Expense chart widget with multiple chart types"""
    
    # ✅ Bright, vibrant colors
    VIBRANT_COLORS = [
        '#E74C3C',  # Red
        '#3498DB',  # Blue
        '#2ECC71',  # Green
        '#F39C12',  # Orange
        '#9B59B6',  # Purple
        '#1ABC9C',  # Teal
        '#E67E22',  # Dark Orange
        '#2C3E50',  # Dark Blue
        '#E74C8B',  # Pink
        '#27AE60',  # Dark Green
        '#2980B9',  # Dark Blue
        '#8E44AD',  # Dark Purple
        '#16A085',  # Dark Teal
        '#D35400',  # Burnt Orange
        '#C0392B',  # Dark Red
        '#6C3483',  # Deep Purple
        '#1A5276',  # Navy
        '#1E8449',  # Forest Green
        '#B7950B',  # Gold
        '#943126',  # Maroon
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_chart_type = "pie"
        self._from_date = None
        self._to_date = None
        self.parent_page = parent
        
        # Connect theme change
        theme_manager.theme_changed.connect(self.on_theme_changed)
        
        # Set matplotlib style based on theme
        self.setup_ui()
        self.load_chart()
    
    def on_theme_changed(self, theme_name):
        """✅ Handle theme change - update tab icon and chart"""
        self._update_tab_icon()
        self.load_chart()
    
    def _update_tab_icon(self):
        """✅ Update tab icon color based on theme"""
        if self.parent_page and hasattr(self.parent_page, 'tab_widget'):
            # Find this tab index
            for idx in range(self.parent_page.tab_widget.count()):
                if self.parent_page.tab_widget.widget(idx) == self:
                    # Load colored icon
                    icon = self._load_colored_tab_icon()
                    self.parent_page.tab_widget.setTabIcon(idx, icon)
                    break
    
    def _load_colored_tab_icon(self):
        """✅ Load SVG icon with color based on theme"""
        is_dark = is_dark_theme()
        color_hex = "#ffffff" if is_dark else "#495057"
        
        # Try SVG first
        paths = [
            "assets/icons/analytics.svg",
            "assets/icons/analytics.png",
        ]
        
        for path in paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Color the icon
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        
                        return QIcon(colored)
                except Exception as e:
                    print(f"Could not load icon {path}: {e}")
        
        return QIcon()
    
    def set_date_range(self, from_date, to_date):
        """Set date range from parent page"""
        self._from_date = from_date
        self._to_date = to_date
    
    def get_date_range(self):
        """Get date range from parent page or default"""
        if self._from_date and self._to_date:
            return self._from_date, self._to_date
        
        # Fallback to last 30 days
        today = QDate.currentDate()
        return today.addDays(-30).toString("yyyy-MM-dd"), today.toString("yyyy-MM-dd")
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ========== Chart Controls ==========
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(0, 8, 0, 8)  # ✅ Added margin
        
        # Chart type selector
        control_layout.addWidget(QLabel("Chart Type:"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Pie Chart", "Bar Chart", "Monthly Trend", "Category Comparison"])
        self.chart_type_combo.currentTextChanged.connect(self.on_chart_type_changed)
        control_layout.addWidget(self.chart_type_combo)
        
        # Date info label
        self.date_info_label = QLabel("Date: Loading...")
        self.date_info_label.setStyleSheet("color: #6c757d; font-size: 10pt;")
        control_layout.addWidget(self.date_info_label)
        
        control_layout.addStretch()
        
        # Refresh button
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.load_chart)
        control_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(control_layout)
        
        # ========== Matplotlib Figure ==========
        is_dark = is_dark_theme()
        self.fig = Figure(figsize=(8, 5), dpi=100, facecolor='#2f3136' if is_dark else 'white')
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumHeight(400)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        self.setLayout(layout)
        
        # ✅ Apply tab icon
        self._update_tab_icon()
    
    def is_dark_theme(self):
        """Check if dark theme is active"""
        return is_dark_theme()
    
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
    
    def on_chart_type_changed(self, chart_type):
        self.current_chart_type = chart_type.lower().replace(" ", "_")
        self.load_chart()
    
    def load_chart(self):
        """Load the appropriate chart based on selection"""
        from_date, to_date = self.get_date_range()
        
        # Update date info
        lang = self.get_lang()
        if lang == "my":
            self.date_info_label.setText(f"ရက်စွဲ: {from_date} မှ {to_date} ထိ")
        else:
            self.date_info_label.setText(f"Date: {from_date} to {to_date}")
        
        if self.current_chart_type == "pie_chart":
            self.draw_pie_chart(from_date, to_date)
        elif self.current_chart_type == "bar_chart":
            self.draw_bar_chart(from_date, to_date)
        elif self.current_chart_type == "monthly_trend":
            self.draw_monthly_trend(from_date, to_date)
        elif self.current_chart_type == "category_comparison":
            self.draw_category_comparison(from_date, to_date)
        else:
            self.draw_pie_chart(from_date, to_date)
    
    def get_expense_data(self, from_date, to_date):
        """Get expense data grouped by category"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
        """, (from_date, to_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        categories = []
        amounts = []
        
        for cat, amt in rows:
            if amt > 0:
                categories.append(cat or "Uncategorized")
                amounts.append(amt)
        
        return categories, amounts
    
    def get_monthly_data(self, from_date, to_date):
        """Get monthly expense data"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT strftime('%Y-%m', expense_date) as month,
                   COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m', expense_date)
            ORDER BY month
        """, (from_date, to_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        months = []
        amounts = []
        
        for month, amt in rows:
            months.append(month)
            amounts.append(amt)
        
        return months, amounts
    
    def get_category_monthly_data(self, from_date, to_date):
        """Get category-wise monthly data for comparison"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, strftime('%Y-%m', expense_date) as month,
                   COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category, strftime('%Y-%m', expense_date)
            ORDER BY month, total DESC
        """, (from_date, to_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows
    
    def draw_pie_chart(self, from_date, to_date):
        """Draw pie chart of expenses by category"""
        categories, amounts = self.get_expense_data(from_date, to_date)
        
        if not categories or sum(amounts) == 0:
            self.show_no_data_message("No expense data available for this period")
            return
        
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        colors = self.VIBRANT_COLORS[:len(categories)]
        total = sum(amounts)
        symbol = get_currency_symbol()
        explode = [0.03 if amt/total < 0.05 else 0 for amt in amounts]
        
        wedges, texts, autotexts = ax.pie(
            amounts,
            labels=None,
            autopct=lambda pct: f'{pct:.1f}%' if pct > 2 else '',
            startangle=90,
            colors=colors,
            explode=explode,
            wedgeprops={'edgecolor': 'white', 'linewidth': 2, 'alpha': 0.9}
        )
        
        is_dark = self.is_dark_theme()
        for autotext in autotexts:
            if is_dark:
                autotext.set_color('white')
            else:
                autotext.set_color('black')
            autotext.set_fontsize(10)
            autotext.set_fontweight('normal')
        
        legend_labels = [f"{cat}: {format_money(amt, symbol)} ({amt/total*100:.1f}%)" 
                        for cat, amt in zip(categories, amounts)]
        
        legend = ax.legend(wedges, legend_labels, 
                          loc='center left', 
                          bbox_to_anchor=(1, 0.5),
                          fontsize=9,
                          framealpha=0.9,
                          facecolor='white' if not is_dark else '#2f3136',
                          edgecolor='#dee2e6' if not is_dark else '#40444b')
        
        if is_dark:
            for text in legend.get_texts():
                text.set_color('white')
        else:
            for text in legend.get_texts():
                text.set_color('black')
        
        lang = self.get_lang()
        if lang == "my":
            title = f"အသုံးစရိတ်ခွဲခြမ်းစိတ်ဖြာချက် ({from_date} - {to_date})"
        else:
            title = f"Expense Breakdown ({from_date} - {to_date})"
        ax.set_title(title, fontsize=14, fontweight='normal', pad=20)
        
        self.apply_theme_to_axes(ax)
        self.fig.tight_layout()
        self.canvas.draw()
    
    def draw_bar_chart(self, from_date, to_date):
        """Draw bar chart of expenses by category"""
        categories, amounts = self.get_expense_data(from_date, to_date)
        
        if not categories or sum(amounts) == 0:
            self.show_no_data_message("No expense data available for this period")
            return
        
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        colors = self.VIBRANT_COLORS[:len(categories)]
        y_pos = np.arange(len(categories))
        bars = ax.barh(y_pos, amounts, color=colors, alpha=0.85, edgecolor='white', linewidth=1)
        
        symbol = get_currency_symbol()
        is_dark = self.is_dark_theme()
        
        for i, (bar, amt) in enumerate(zip(bars, amounts)):
            ax.text(amt, bar.get_y() + bar.get_height()/2, 
                   f'  {format_money(amt, symbol)}',
                   va='center', 
                   fontsize=10, 
                   fontweight='normal',
                   color='white' if is_dark else '#2c3e50')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories, fontsize=10)
        ax.set_ylabel('')
        
        lang = self.get_lang()
        ax.set_xlabel('Amount' if lang != 'my' else 'ပမာဏ', fontsize=11, fontweight='normal')
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        
        if lang == "my":
            title = f"အမျိုးအစားအလိုက် အသုံးစရိတ် ({from_date} - {to_date})"
        else:
            title = f"Expenses by Category ({from_date} - {to_date})"
        ax.set_title(title, fontsize=14, fontweight='normal', pad=20)
        
        self.apply_theme_to_axes(ax)
        self.fig.tight_layout()
        self.canvas.draw()
    
    def draw_monthly_trend(self, from_date, to_date):
        """Draw monthly trend line chart"""
        months, amounts = self.get_monthly_data(from_date, to_date)
        
        if not months or sum(amounts) == 0:
            self.show_no_data_message("No monthly data available for this period")
            return
        
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        symbol = get_currency_symbol()
        is_dark = self.is_dark_theme()
        
        ax.plot(months, amounts, marker='o', linewidth=3, markersize=10, 
                color='#3498DB', markerfacecolor='#2980B9', markeredgecolor='white', markeredgewidth=2)
        
        for month, amt in zip(months, amounts):
            ax.annotate(format_money(amt, symbol), 
                       (month, amt), 
                       textcoords="offset points", 
                       xytext=(0, 12), 
                       ha='center', 
                       fontsize=10, 
                       fontweight='normal',
                       color='white' if is_dark else '#2c3e50')
        
        ax.fill_between(months, 0, amounts, alpha=0.25, color='#3498DB')
        ax.set_xticklabels(months, rotation=45, ha='right', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        lang = self.get_lang()
        ax.set_xlabel('Month' if lang != 'my' else 'လ', fontsize=11, fontweight='normal')
        ax.set_ylabel('Amount' if lang != 'my' else 'ပမာဏ', fontsize=11, fontweight='normal')
        
        if lang == "my":
            title = f"လစဉ် အသုံးစရိတ် လမ်းကြောင်း ({from_date} - {to_date})"
        else:
            title = f"Monthly Expense Trend ({from_date} - {to_date})"
        ax.set_title(title, fontsize=14, fontweight='normal', pad=20)
        
        self.apply_theme_to_axes(ax)
        self.fig.tight_layout()
        self.canvas.draw()
    
    def draw_category_comparison(self, from_date, to_date):
        """Draw stacked bar chart comparing categories over months"""
        data = self.get_category_monthly_data(from_date, to_date)
        
        if not data:
            self.show_no_data_message("No data available for comparison")
            return
        
        months = sorted(set(row[1] for row in data))
        categories = {}
        
        for cat, month, amt in data:
            if amt > 0:
                if cat not in categories:
                    categories[cat] = {}
                categories[cat][month] = amt
        
        if not categories:
            self.show_no_data_message("No data available for comparison")
            return
        
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        bottom = np.zeros(len(months))
        colors = self.VIBRANT_COLORS[:len(categories)]
        symbol = get_currency_symbol()
        is_dark = self.is_dark_theme()
        
        for idx, (cat, cat_data) in enumerate(categories.items()):
            amounts = [cat_data.get(month, 0) for month in months]
            bars = ax.bar(months, amounts, bottom=bottom, label=cat, 
                         color=colors[idx % len(colors)], 
                         alpha=0.85, 
                         edgecolor='white', 
                         linewidth=1)
            bottom += np.array(amounts)
        
        ax.set_xticklabels(months, rotation=45, ha='right', fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        lang = self.get_lang()
        ax.set_xlabel('Month' if lang != 'my' else 'လ', fontsize=11, fontweight='normal')
        ax.set_ylabel('Amount' if lang != 'my' else 'ပမာဏ', fontsize=11, fontweight='normal')
        
        legend = ax.legend(loc='center left', 
                          bbox_to_anchor=(1, 0.5), 
                          fontsize=9,
                          framealpha=0.9,
                          facecolor='white' if not is_dark else '#2f3136',
                          edgecolor='#dee2e6' if not is_dark else '#40444b')
        
        if is_dark:
            for text in legend.get_texts():
                text.set_color('white')
        else:
            for text in legend.get_texts():
                text.set_color('black')
        
        if lang == "my":
            title = f"အမျိုးအစားအလိုက် လစဉ် နှိုင်းယှဉ်ချက် ({from_date} - {to_date})"
        else:
            title = f"Monthly Category Comparison ({from_date} - {to_date})"
        ax.set_title(title, fontsize=14, fontweight='normal', pad=20)
        
        self.apply_theme_to_axes(ax)
        self.fig.tight_layout()
        self.canvas.draw()
    
    def apply_theme_to_axes(self, ax):
        """Apply current theme to axes"""
        is_dark = self.is_dark_theme()
        
        if is_dark:
            self.fig.patch.set_facecolor('#2f3136')
            ax.set_facecolor('#2f3136')
            ax.tick_params(colors='#dcddde')
            ax.xaxis.label.set_color('#dcddde')
            ax.yaxis.label.set_color('#dcddde')
            ax.title.set_color('#ffffff')
            ax.spines['bottom'].set_color('#40444b')
            ax.spines['top'].set_color('#40444b')
            ax.spines['left'].set_color('#40444b')
            ax.spines['right'].set_color('#40444b')
        else:
            self.fig.patch.set_facecolor('white')
            ax.set_facecolor('#f8f9fa')
            ax.tick_params(colors='#212529')
            ax.xaxis.label.set_color('#212529')
            ax.yaxis.label.set_color('#212529')
            ax.title.set_color('#212529')
            ax.spines['bottom'].set_color('#dee2e6')
            ax.spines['top'].set_color('#dee2e6')
            ax.spines['left'].set_color('#dee2e6')
            ax.spines['right'].set_color('#dee2e6')
    
    def show_no_data_message(self, message):
        """Show a message when no data is available"""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        is_dark = self.is_dark_theme()
        
        ax.text(0.5, 0.5, message,
               ha='center', va='center', fontsize=14, fontweight='normal',
               color='white' if is_dark else '#e74c3c')
        ax.set_xticks([])
        ax.set_yticks([])
        
        for spine in ax.spines.values():
            spine.set_visible(False)
        
        self.apply_theme_to_axes(ax)
        self.fig.tight_layout()
        self.canvas.draw()
    
    def refresh(self):
        """Refresh the chart"""
        self.load_chart()
    
    def retranslateUi(self):
        """Retranslate UI elements"""
        lang = self.get_lang()
        
        self.chart_type_combo.blockSignals(True)
        current = self.chart_type_combo.currentText()
        self.chart_type_combo.clear()
        if lang == "my":
            self.chart_type_combo.addItems(["အဝိုင်းပုံဇယား", "ဘားပုံဇယား", "လစဉ်လမ်းကြောင်း", "အမျိုးအစားနှိုင်းယှဉ်"])
        else:
            self.chart_type_combo.addItems(["Pie Chart", "Bar Chart", "Monthly Trend", "Category Comparison"])
        idx = self.chart_type_combo.findText(current)
        if idx >= 0:
            self.chart_type_combo.setCurrentIndex(idx)
        self.chart_type_combo.blockSignals(False)
        
        self.btn_refresh.setText("🔄 Refresh" if lang != "my" else "🔄 ပြန်လည်")
        
        # ✅ Update tab icon on language change
        self._update_tab_icon()
        
        self.load_chart()
    
    def showEvent(self, event):
        """Update tab icon when shown"""
        self._update_tab_icon()
        super().showEvent(event)
