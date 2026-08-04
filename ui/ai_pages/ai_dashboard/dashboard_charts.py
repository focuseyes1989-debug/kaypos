# ui/ai_pages/ai_dashboard/dashboard_charts.py
"""
Charts for AI Dashboard with Myanmar Font Support
"""

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
import warnings
import logging

# Import DashboardUtils
from ui.ai_pages.ai_dashboard.dashboard_utils import DashboardUtils

# Suppress all matplotlib font warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib.font_manager")
logging.getLogger('matplotlib').setLevel(logging.ERROR)
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

# Matplotlib အတွက် မြန်မာ Font Config
plt.rcParams['font.sans-serif'] = ['Pyidaungsu', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
# Suppress font weight warnings
plt.rcParams['font.weight'] = 'normal'
plt.rcParams['axes.titleweight'] = 'normal'
plt.rcParams['axes.labelweight'] = 'normal'


class DashboardCharts:
    """Chart manager for dashboard"""
    
    def __init__(self, parent):
        self.parent = parent
        self.sales_figure = None
        self.sales_canvas = None
        self.category_figure = None
        self.category_canvas = None
        self.sales_frame = None
        self.category_frame = None
    
    def setup(self, colors):
        """Setup charts"""
        charts_container = QFrame()
        charts_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        charts_container.setMinimumHeight(280)
        charts_container.setStyleSheet("background-color: transparent;")
        
        charts_layout = QHBoxLayout(charts_container)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setSpacing(12)
        
        # Sales Chart (2/3)
        self.sales_frame, self.sales_figure, self.sales_canvas = self._create_chart_frame(
            "trending_up", "Daily Sales Trend", colors, (8, 2.8), 200
        )
        charts_layout.addWidget(self.sales_frame, 2)
        
        # Category Chart (1/3)
        self.category_frame, self.category_figure, self.category_canvas = self._create_chart_frame(
            "bar_chart", "Sales by Category", colors, (4, 2.8), 200
        )
        charts_layout.addWidget(self.category_frame, 1)
        
        return charts_container
    
    def _create_chart_frame(self, icon_name, title, colors, figsize, min_height):
        """Create a chart frame with title"""
        from ui.ai_pages.ai_dashboard.dashboard_icons import DashboardIcons
        
        frame = QFrame()
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 6px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        
        # Title with icon
        title_layout = QHBoxLayout()
        title_layout.setSpacing(6)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # Icon Size 24x24
        title_icon = DashboardIcons.create_svg_icon(icon_name, (24, 24))
        title_icon.setFixedSize(24, 24)
        title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_icon.setStyleSheet("""
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """)
        title_layout.addWidget(title_icon)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {colors.get('text', '#2d3436')};
            background-color: transparent;
            margin: 0px;
            padding: 0px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        figure = Figure(figsize=figsize, dpi=100)
        canvas = FigureCanvas(figure)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas.setMinimumHeight(min_height)
        layout.addWidget(canvas)
        
        return frame, figure, canvas
    
    def update_sales_chart(self, daily_data):
        """Update sales chart"""
        if not self.sales_figure:
            return
        
        theme = DashboardUtils.get_theme_colors()
        
        self.sales_figure.clear()
        self.sales_figure.patch.set_facecolor(theme['figure_bg'])
        self.sales_figure.subplots_adjust(left=0.08, right=0.95, top=0.88, bottom=0.18)
        
        ax = self.sales_figure.add_subplot(111)
        ax.set_facecolor(theme['axes_bg'])
        ax.set_title('Daily Sales Trend', fontsize=10, fontweight='normal', color=theme['text'])
        
        if daily_data and len(daily_data) > 0:
            dates = [d[0] for d in daily_data]
            sales = [float(d[2]) for d in daily_data]
            
            bars = ax.bar(dates, sales, width=0.7, color='#3498DB', alpha=0.85,
                         edgecolor='#3498DB', linewidth=0, capstyle='round')
            
            if sales:
                max_val = max(sales) if sales else 1
                for bar, val in zip(bars, sales):
                    if val > 0 and max_val > 0:
                        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02 * max_val,
                               f'{val:,.0f}', ha='center', va='bottom', fontsize=7,
                               color=theme['text_secondary'], weight='normal')
            
            ax.set_ylabel('Sales (Ks)', fontsize=8, color=theme['text_secondary'])
            ax.tick_params(colors=theme['text_secondary'], labelsize=7)
            
            if len(dates) > 10:
                ax.tick_params(axis='x', rotation=45)
            
            if len(dates) > 15:
                step = max(1, len(dates) // 10)
                xticks = dates[::step]
                ax.set_xticks(xticks)
                ax.set_xticklabels(xticks, rotation=45, ha='right')
        else:
            ax.text(0.5, 0.5, 'No Data Available', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12, color=theme['text_secondary'])
        
        for spine in ax.spines.values():
            spine.set_color(theme['border'])
        
        self.sales_figure.tight_layout()
        self.sales_canvas.draw()
    
    def update_category_chart(self, category_data):
        """Update category chart - Myanmar text support with Pyidaungsu only"""
        if not self.category_figure:
            return
        
        theme = DashboardUtils.get_theme_colors()
        colors = DashboardUtils.get_vibrant_colors(8)
        
        # Myanmar Font Properties - Pyidaungsu သာ သုံးပါ
        mm_font = FontProperties(family=['Pyidaungsu'], size=10)
        mm_font_bold = FontProperties(family=['Pyidaungsu'], size=9)
        # Fallback font
        fallback_font = FontProperties(family=['DejaVu Sans'], size=10)

        self.category_figure.clear()
        self.category_figure.patch.set_facecolor(theme['figure_bg'])
        self.category_figure.subplots_adjust(left=0.28, right=0.92, top=0.88, bottom=0.12)
        
        ax = self.category_figure.add_subplot(111)
        ax.set_facecolor(theme['axes_bg'])
        ax.set_title('Sales by Category', fontsize=10, fontweight='normal', color=theme['text'])
        
        if category_data and len(category_data) > 0:
            categories = [c[0] or 'Uncategorized' for c in category_data]
            totals = [float(c[2]) for c in category_data]
            
            filtered = [(cat, val) for cat, val in zip(categories, totals) if val > 0]
            
            if filtered:
                sorted_data = sorted(filtered, key=lambda x: x[1], reverse=True)
                cats, vals = zip(*sorted_data)
                
                bars = ax.barh(cats, vals, color=colors[:len(cats)], alpha=0.85,
                              edgecolor=colors[:len(cats)], linewidth=0, height=0.65)
                
                # Category names with Pyidaungsu font
                ax.set_yticks(range(len(cats)))
                try:
                    ax.set_yticklabels(cats, fontproperties=mm_font, color=theme['text_secondary'])
                except:
                    ax.set_yticklabels(cats, fontproperties=fallback_font, color=theme['text_secondary'])
                
                max_val = max(vals) if vals else 1
                for bar, val in zip(bars, vals):
                    try:
                        ax.text(bar.get_width() + (max_val * 0.01), bar.get_y() + bar.get_height()/2,
                               f'  {val:,.0f} Ks', ha='left', va='center',
                               color=theme['text_secondary'], fontproperties=mm_font_bold)
                    except:
                        ax.text(bar.get_width() + (max_val * 0.01), bar.get_y() + bar.get_height()/2,
                               f'  {val:,.0f} Ks', ha='left', va='center',
                               color=theme['text_secondary'], fontproperties=fallback_font)
                
                total = sum(vals)
                for bar, val in zip(bars, vals):
                    pct = (val / total * 100) if total > 0 else 0
                    if pct > 8:
                        try:
                            ax.text(bar.get_width() * 0.35, bar.get_y() + bar.get_height()/2,
                                   f'{pct:.1f}%', ha='center', va='center',
                                   color='white', fontproperties=mm_font_bold)
                        except:
                            ax.text(bar.get_width() * 0.35, bar.get_y() + bar.get_height()/2,
                                   f'{pct:.1f}%', ha='center', va='center',
                                   color='white', fontproperties=fallback_font)
                
                ax.set_xlabel('Sales (Ks)', fontsize=9, color=theme['text_secondary'])
                ax.tick_params(colors=theme['text_secondary'], labelsize=8)
                ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, 'No Data Available', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12, color=theme['text_secondary'])
        
        for spine in ax.spines.values():
            spine.set_color(theme['border'])
        
        self.category_figure.tight_layout()
        self.category_canvas.draw()
    
    def update_theme(self):
        """Update charts theme"""
        from ui.themes.theme_manager import get_theme_colors

        colors = get_theme_colors()
        frame_style = f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-radius: 12px;
                padding: 6px;
            }}
        """
        for frame in (self.sales_frame, self.category_frame):
            if frame:
                frame.setStyleSheet(frame_style)
        if self.sales_canvas:
            self.sales_canvas.draw_idle()
        if self.category_canvas:
            self.category_canvas.draw_idle()
