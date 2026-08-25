# ui/inventory_page/inventory_tabs.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QFrame, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from models.database import connect_db
from utils.translations import tr
from utils.currency import get_currency_symbol, format_money
from utils.excel_exporter import ExcelExporter
from datetime import datetime
import os

from ui.inventory_page.current_stock_tab import CurrentStockTab
from ui.inventory_page.low_stock_tab import LowStockTab
from ui.inventory_page.suppliers_tab import SuppliersTab
from ui.inventory_page.purchase_history_tab import PurchaseHistoryTab
from ui.inventory_page.expiry_tab import ExpiryTab
from ui.inventory_page.logs_tab import LogsTab
from ui.inventory_page.warehouse_dialog import WarehouseDialog
from ui.inventory_page.stock_by_location_tab import StockByLocationTab

# ✅ ModernButton import
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors


class InventoryPage(QWidget):
    def __init__(self, user_role=None, parent=None):
        super().__init__(parent)
        self.user_role = user_role
        self._initializing = True
        
        # ✅ Tab names for retranslation
        self.tab_names = {
            0: "Current Stock",
            1: "Low Stock",
            2: "Suppliers",
            3: "Purchase History",
            4: "Expiry Date",
            5: "Stock Logs",
            6: "Stock by Location"
        }
        
        # ✅ Tab Icons Mapping
        self.tab_icons = {
            0: "inventory",       # inventory.svg
            1: "warning",         # warning.svg
            2: "supplier",        # supplier.svg
            3: "purchase",        # purchase.svg
            4: "calendar",        # calendar.svg
            5: "history",         # history.svg
            6: "location_on"      # location_on.svg
        }
        
        self.setObjectName("inventoryPage")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        # Export and Location button row - ✅ Buttons on the right side
        self.toolbar_card = QFrame()
        self.toolbar_card.setObjectName("inventoryToolbarCard")
        btn_layout = QHBoxLayout(self.toolbar_card)
        btn_layout.setContentsMargins(14, 10, 14, 10)
        btn_layout.setSpacing(8)
        
        # ✅ Add stretch to push buttons to the right
        btn_layout.addStretch()
        
        # ✅ Export Excel button with SVG icon
        self.btn_export_excel = ModernButton(" Export Excel", ModernButton.SECONDARY)
        self.btn_export_excel.set_icon("file_export", size=(16, 16))
        self.btn_export_excel.set_compact(False)
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        btn_layout.addWidget(self.btn_export_excel)
        
        # ✅ Manage Locations button with SVG icon
        self.btn_manage_locations = ModernButton(" Manage Locations", ModernButton.SECONDARY)
        self.btn_manage_locations.set_icon("location_on", size=(16, 16))
        self.btn_manage_locations.set_compact(False)
        self.btn_manage_locations.clicked.connect(self.open_warehouse_dialog)
        btn_layout.addWidget(self.btn_manage_locations)
        
        layout.addWidget(self.toolbar_card)

        # Tabs with colored SVG icons
        self.tabs = QTabWidget()
        self.tabs.setObjectName("inventoryTabs")
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setDocumentMode(True)

        self.current_stock_tab = CurrentStockTab(self)
        self.low_stock_tab = None
        self.suppliers_tab = None
        self.purchase_history_tab = None
        self.expiry_tab = None
        self.logs_tab = None
        self.stock_by_location_tab = None
        self._tab_attributes = {
            0: "current_stock_tab", 1: "low_stock_tab", 2: "suppliers_tab",
            3: "purchase_history_tab", 4: "expiry_tab", 5: "logs_tab",
            6: "stock_by_location_tab",
        }
        self._tab_factories = {
            1: LowStockTab, 2: SuppliersTab, 3: PurchaseHistoryTab,
            4: ExpiryTab, 5: LogsTab, 6: StockByLocationTab,
        }

        # ✅ Add tabs with colored icons
        self.tabs.addTab(self.current_stock_tab, self._load_colored_tab_icon(0), self.tab_names[0])
        for index in range(1, 7):
            placeholder = QLabel("This tab will load when selected.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setObjectName("inventoryTabPlaceholder")
            self.tabs.addTab(placeholder, self._load_colored_tab_icon(index), self.tab_names[index])

        # ✅ Apply tab bar style for dark theme
        self._apply_tab_bar_style()

        layout.addWidget(self.tabs)
        self.setLayout(layout)
        
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self.retranslateUi()
        self._initializing = False

    def _on_theme_changed(self, theme_name):
        """Handle theme change - update tab bar style and icons"""
        self._apply_tab_bar_style()
        self._update_tab_icons_color()
        self._update_button_icons()

    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_export_excel.set_icon("file_export", size=(16, 16))
        self.btn_manage_locations.set_icon("location_on", size=(16, 16))

    def _apply_tab_bar_style(self):
        """✅ Apply tab bar style based on theme - matching sales summary page"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QWidget#inventoryPage {{ background: transparent; }}
            QFrame#inventoryToolbarCard {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QTabWidget#inventoryTabs::pane {{
                border: 1px solid {colors['border']};
                border-radius: 12px;
                background-color: {colors['card_bg']};
                top: -1px;
            }}
            QTabWidget#inventoryTabs QTabBar::tab {{
                background-color: transparent;
                color: {colors['text_secondary']};
                padding: 10px 14px;
                margin: 0 3px 7px 0;
                border: none;
                border-radius: 8px;
                font-weight: 600;
            }}
            QTabWidget#inventoryTabs QTabBar::tab:selected {{
                background-color: {colors['bg_hover']};
                color: {colors['text']};
                border-bottom: 2px solid {colors['progress_bg']};
            }}
            QTabWidget#inventoryTabs QTabBar::tab:hover:!selected {{
                background-color: {colors['card_hover']};
                color: {colors['text']};
            }}
        """)
        
        # ✅ Update tab icons color
        self._update_tab_icons_color()

    def _update_tab_icons_color(self):
        """✅ Update all tab icons color based on theme"""
        is_dark = is_dark_theme()
        
        for index in range(self.tabs.count()):
            icon = self._load_colored_tab_icon(index)
            self.tabs.setTabIcon(index, icon)

    def _load_colored_tab_icon(self, index):
        """✅ Load SVG icon with color based on theme for tabs"""
        icon_name = self.tab_icons.get(index, "")
        if not icon_name:
            return QIcon()
        
        # Try SVG first, then PNG
        paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for path in paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        # Scale to 20x20 for tab icon
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # ✅ Color the icon based on theme
                        is_dark = is_dark_theme()
                        color_hex = "#ffffff" if is_dark else "#495057"
                        
                        # Create colored version
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        
                        return QIcon(colored)
                except Exception as e:
                    print(f"Could not load icon {path}: {e}")
        
        return QIcon()

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

    def get_current_theme(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except:
            return "Light"

    def open_warehouse_dialog(self):
        dialog = WarehouseDialog(self)
        dialog.warehouses_changed.connect(self.refresh_all)
        dialog.exec()

    def on_tab_changed(self, index):
        widget, created = self._ensure_tab_loaded(index)
        if widget is not None and not created and hasattr(widget, "refresh"):
            widget.refresh()

    def _ensure_tab_loaded(self, index):
        attribute = self._tab_attributes.get(index)
        if attribute is None:
            return None, False
        widget = getattr(self, attribute, None)
        if widget is not None:
            return widget, False
        factory = self._tab_factories.get(index)
        if factory is None:
            return None, False
        widget = factory(self)
        old_widget = self.tabs.widget(index)
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index)
        self.tabs.insertTab(index, widget, self._load_colored_tab_icon(index), self.tab_names[index])
        self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        if old_widget is not None:
            old_widget.deleteLater()
        setattr(self, attribute, widget)
        self.retranslateUi(refresh=False)
        return widget, True

    def retranslateUi(self, refresh=True):
        lang = self.get_lang()
        
        # ✅ Tab titles with Myanmar translation
        tab_titles_my = {
            0: "လက်ရှိစတော့",
            1: "စတော့နည်းနေသော",
            2: "ပေးသွင်းသူများ",
            3: "ဝယ်ယူမှုမှတ်တမ်း",
            4: "သက်တမ်းကုန်ရက်",
            5: "စတော့မှတ်တမ်းများ",
            6: "နေရာအလိုက်စတော့"
        }
        
        for i in range(self.tabs.count()):
            if lang == "my":
                self.tabs.setTabText(i, tab_titles_my.get(i, self.tab_names.get(i, "")))
            else:
                self.tabs.setTabText(i, self.tab_names.get(i, ""))
        
        # ✅ Update button texts with SVG icons
        if lang == "my":
            self.btn_export_excel.setText(" Excel ထုတ်မည်")
            self.btn_manage_locations.setText(" နေရာများ စီမံရန်")
        else:
            self.btn_export_excel.setText(" Export Excel")
            self.btn_manage_locations.setText(" Manage Locations")
        
        # ✅ Update button icons
        self._update_button_icons()
        
        # ✅ Update tab icons color for language change
        self._update_tab_icons_color()
        
        if refresh and not self._initializing:
            self.refresh_all()

    def refresh_all(self):
        for attribute in self._tab_attributes.values():
            widget = getattr(self, attribute, None)
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()
        main_window = self.window()
        if hasattr(main_window, 'check_stock_alerts'):
            main_window.check_stock_alerts()

    def export_to_excel(self):
        current_tab = self.tabs.currentIndex()
        widget, _created = self._ensure_tab_loaded(current_tab)
        if widget is not None and hasattr(widget, "export_to_excel"):
            widget.export_to_excel()
    
    def showEvent(self, event):
        """✅ Update tab icons when shown"""
        self._apply_tab_bar_style()
        super().showEvent(event)
