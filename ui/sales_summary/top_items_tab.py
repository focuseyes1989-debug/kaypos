# ui/sales_summary/top_items_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QTabWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from models.database import connect_db
from utils.currency import format_money
from utils.language import lang
from utils.system_theme import system_theme
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import platform
import logging
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
plt.rcParams["font.weight"] = "normal"
plt.rcParams["axes.titleweight"] = "normal"
plt.rcParams["axes.labelweight"] = "normal"

# ✅ Import theme manager
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors


class TopItemsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.full_data = []
        self.current_theme = "Light"
        
        # Setup Myanmar font for matplotlib
        self._setup_myanmar_font()
        
        layout = QVBoxLayout()
        
        # Tab widget for Chart and Table views
        self.view_tabs = QTabWidget()
        
        # Chart tab
        self.chart_tab = QWidget()
        chart_layout = QVBoxLayout()
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)
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
        
        # ✅ Connect theme manager signal for auto refresh
        theme_manager.theme_changed.connect(self.on_theme_manager_changed)
        
        # Load current theme
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
    
    def _setup_myanmar_font(self):
        """Setup Myanmar font for matplotlib with proper encoding"""
        try:
            # Common Myanmar font paths for different OS
            font_paths = []
            
            if platform.system() == "Windows":
                font_paths = [
                    "C:/Windows/Fonts/Padauk.ttf",
                    "C:/Windows/Fonts/NotoSansMyanmar-Regular.ttf",
                    "C:/Windows/Fonts/MyanmarText.ttf",
                    "C:/Windows/Fonts/Pyidaungsu.ttf",
                    "C:/Windows/Fonts/MyanmarSans.ttf",
                    "C:/Windows/Fonts/mmrtext.ttf",
                ]
            elif platform.system() == "Darwin":  # macOS
                font_paths = [
                    "/Library/Fonts/Padauk.ttf",
                    "/System/Library/Fonts/Supplemental/NotoSansMyanmar.ttf",
                ]
            else:  # Linux
                font_paths = [
                    "/usr/share/fonts/truetype/padauk/Padauk.ttf",
                    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
                    "/usr/share/fonts/truetype/myanmar/Padauk.ttf",
                    "/usr/local/share/fonts/Padauk.ttf",
                ]
            
            # Try to find and load Myanmar font
            loaded = False
            for path in font_paths:
                if os.path.exists(path):
                    try:
                        fm.fontManager.addfont(path)
                        prop = fm.FontProperties(fname=path)
                        font_name = prop.get_name()
                        plt.rcParams['font.family'] = font_name
                        plt.rcParams['font.size'] = 9
                        print(f"Loaded Myanmar font: {path} (name: {font_name})")
                        loaded = True
                        break
                    except Exception as e:
                        print(f"Failed to load font {path}: {e}")
            
            if not loaded:
                font_list = fm.findSystemFonts(fontpaths=None, fontext='ttf')
                myanmar_fonts = []
                for f in font_list:
                    f_lower = f.lower()
                    if any(name in f_lower for name in ['padauk', 'myanmar', 'notosansmyanmar', 'pyidaungsu', 'mmrtext']):
                        myanmar_fonts.append(f)
                
                if myanmar_fonts:
                    try:
                        fm.fontManager.addfont(myanmar_fonts[0])
                        prop = fm.FontProperties(fname=myanmar_fonts[0])
                        font_name = prop.get_name()
                        plt.rcParams['font.family'] = font_name
                        plt.rcParams['font.size'] = 9
                        print(f"Loaded Myanmar font: {myanmar_fonts[0]} (name: {font_name})")
                        loaded = True
                    except Exception as e:
                        print(f"Failed to load font: {e}")
            
            if not loaded:
                plt.rcParams['font.family'] = 'sans-serif'
                plt.rcParams['font.size'] = 9
                print("Using default font for charts")
                
        except Exception as e:
            print(f"Could not setup Myanmar font: {e}")
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.size'] = 9
    
    def get_theme_colors(self):
        """Get theme colors for chart"""
        theme = self.current_theme.lower()
        
        if theme == "dark":
            return {
                'bg_color': '#2f3136',
                'text_color': '#ffffff',
                'grid_color': '#40444b',
                'bar_colors': plt.cm.viridis,
                'axis_color': '#b9bbbe'
            }
        elif theme == "light gray":
            return {
                'bg_color': '#f0f0f0',
                'text_color': '#333333',
                'grid_color': '#d0d0d0',
                'bar_colors': plt.cm.viridis,
                'axis_color': '#666666'
            }
        elif theme == "ubuntu":
            return {
                'bg_color': '#f6f6f6',
                'text_color': '#333333',
                'grid_color': '#dddddd',
                'bar_colors': plt.cm.Oranges,
                'axis_color': '#666666'
            }
        elif theme == "ubuntu dark":
            return {
                'bg_color': '#2c2c2c',
                'text_color': '#ffffff',
                'grid_color': '#404040',
                'bar_colors': plt.cm.Oranges_r,
                'axis_color': '#b0b0b0'
            }
        elif theme == "windows xp":
            return {
                'bg_color': '#d4d0c8',
                'text_color': '#000000',
                'grid_color': '#b0a8a0',
                'bar_colors': plt.cm.Set3,
                'axis_color': '#000000'
            }
        elif theme == "pyqt6 dark":
            return {
                'bg_color': '#1e1e1e',
                'text_color': '#ffffff',
                'grid_color': '#3c3c3c',
                'bar_colors': plt.cm.Purples_r,
                'axis_color': '#999999'
            }
        elif theme == "pyqt6 light":
            return {
                'bg_color': '#fafafa',
                'text_color': '#000000',
                'grid_color': '#d0d0d0',
                'bar_colors': plt.cm.Blues,
                'axis_color': '#666666'
            }
        else:  # Light (default)
            return {
                'bg_color': '#ffffff',
                'text_color': '#212529',
                'grid_color': '#dee2e6',
                'bar_colors': plt.cm.viridis,
                'axis_color': '#495057'
            }
    
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
        """Update the chart with current data - sorted descending with theme colors"""
        self.figure.clear()
        
        # Get theme colors
        colors = self.get_theme_colors()
        
        # Create subplot with theme background
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(colors['bg_color'])
        self.figure.patch.set_facecolor(colors['bg_color'])
        
        # ✅ Check if no data available
        if not self.full_data:
            # Display "No Data Available" message
            lang_code = lang.get_current()
            if lang_code == "my":
                message = "ဒေတာမရှိပါ"
            else:
                message = "No Data Available"
            
            ax.text(0.5, 0.5, message, 
                   ha='center', va='center', 
                   fontsize=16, fontweight='normal',
                   color=colors['text_color'],
                   transform=ax.transAxes)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')  # Hide axes
            
            # Adjust layout and redraw
            self.figure.tight_layout(pad=2.0)
            self.canvas.draw()
            return
        
        # Extract data - already sorted descending from query
        names = [row[0] for row in self.full_data]
        values = [row[1] for row in self.full_data]
        
        # Get language
        lang_code = lang.get_current()
        
        # Create horizontal bar chart
        # Reverse to show highest at top
        names_rev = names[::-1]
        values_rev = values[::-1]
        
        # Use theme color map
        color_map = colors['bar_colors']
        bar_colors = color_map([i/len(values_rev) for i in range(len(values_rev))])
        
        # Create bars
        bars = ax.barh(names_rev, values_rev, color=bar_colors, height=0.7)
        
        # Add value labels at the end of bars
        for bar, value in zip(bars, values_rev):
            width = bar.get_width()
            if lang_code == "my":
                label = f"{format_money(value)}"
            else:
                label = f"{format_money(value)}"
            
            ax.text(width * 1.02, bar.get_y() + bar.get_height()/2, label,
                   ha='left', va='center', fontsize=8, fontweight='normal',
                   color=colors['text_color'])
        
        # Set labels and title with theme colors
        if lang_code == "my":
            ax.set_xlabel("အသားတင်ရောင်းအား (ကျပ်)", fontsize=10, fontweight='normal', color=colors['text_color'])
            ax.set_ylabel("ပစ္စည်းအမည်", fontsize=10, fontweight='normal', color=colors['text_color'])
            ax.set_title("ထိပ်ဆုံးရောင်းအားရှိပစ္စည်း ၂၀", fontsize=12, fontweight='normal', color=colors['text_color'])
        else:
            ax.set_xlabel("Net Sales", fontsize=10, fontweight='normal', color=colors['text_color'])
            ax.set_ylabel("Product Name", fontsize=10, fontweight='normal', color=colors['text_color'])
            ax.set_title("Top 20 Sales by Item (Net)", fontsize=12, fontweight='normal', color=colors['text_color'])
        
        # Set tick colors
        ax.tick_params(axis='y', labelsize=8, colors=colors['text_color'])
        ax.tick_params(axis='x', labelsize=9, colors=colors['text_color'])
        
        # Format x-axis as currency
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format_money(x) if x > 0 else ''))
        
        # Add grid with theme color
        ax.grid(axis='x', alpha=0.3, linestyle='--', color=colors['grid_color'])
        ax.set_axisbelow(True)
        
        # Set x-axis limit with some padding
        max_value = max(values) if values else 0
        ax.set_xlim(0, max_value * 1.25 if max_value > 0 else 10)
        
        # Set spine colors
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(colors['grid_color'])
        ax.spines['bottom'].set_color(colors['grid_color'])
        
        # Adjust layout with more space for y-axis labels
        self.figure.tight_layout(pad=2.0)
        
        # Redraw canvas
        self.canvas.draw()
    
    def retranslateUi(self):
        """Retranslate UI"""
        lang_code = lang.get_current()
        if lang_code == "my":
            self.view_tabs.setTabText(0, "ဇယား")
            self.view_tabs.setTabText(1, "စာရင်း")
        else:
            self.view_tabs.setTabText(0, "Chart")
            self.view_tabs.setTabText(1, "Table")
        
        # Update table
        self._update_table(lang_code)
        self.update_chart()
    
    def showEvent(self, event):
        """Handle show event - update chart with current theme"""
        self.current_theme = self._get_current_theme()
        self.update_chart()
        super().showEvent(event)


# ✅ EXPORT - Import လုပ်လို့ရအောင်
__all__ = ['TopItemsTab']
