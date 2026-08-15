# ui/categories/category_list_dialog.py
"""
Main Category Management Dialog
✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
✅ FIX: Theme ပြောင်းတာနဲ့ ချက်ချင်း refresh ဖြစ်မယ်
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QPushButton, QMessageBox, QMenu, QComboBox, QFrame,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QAction, QPixmap, QIcon, QFont

from models.database import connect_db
from ui.categories.category_service import CategoryService
from ui.categories.category_form_dialog import CategoryFormDialog
from ui.categories.category_merge_dialog import CategoryMergeDialog
from ui.categories.category_summary_widget import CategorySummaryWidget
from ui.categories.category_list_ui import CategoryListUI
from ui.categories.category_list_table import CategoryListTable
from ui.categories.category_list_actions import CategoryListActions
from ui.widgets.modern_button import ModernButton
from ui.widgets.pagination_widget import PaginationWidget
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager
from utils.translations import tr
from utils.language import lang
from utils.excel_exporter import ExcelExporter

from loguru import logger
from datetime import datetime
from typing import List, Optional, Dict


class CategoryListDialog(QDialog):
    """Main dialog for managing categories - Theme-aware"""
    
    categories_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        # ✅ FIX: Call QDialog.__init__ directly
        QDialog.__init__(self, parent)
        
        # Initialize attributes
        self.service = CategoryService()
        self.categories = []
        self.current_page = 1
        self.page_size = 20
        self.filter_status = 'all'
        self.search_text = ''
        
        # Setup window
        self.setWindowTitle("Manage Categories")
        self.setModal(True)
        self.resize(950, 720)
        self.setMinimumWidth(800)
        self.setMinimumHeight(550)
        
        # Enable minimize/maximize buttons
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI
        self.setup_ui()
        self._configure_filter_data()
        
        # Load data
        self.load_categories()
        self.update_statistics()
        
        # Language support
        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
        
    # ==================== Theme Handling ====================
    
    def _on_theme_changed(self, theme_name):
        """
        Theme ပြောင်းတဲ့အခါ UI ကို update လုပ်မယ်
        ✅ FIX: ချက်ချင်း refresh ဖြစ်အောင် load_categories() ကိုခေါ်မယ်
        """
        logger.debug(f"CategoryListDialog: Theme changed to {theme_name}, refreshing...")
        
        # Update UI styles
        colors = get_theme_colors()
        
        # Update header
        self._update_header_style(colors)
        
        # Update search bar
        self._update_search_bar_style(colors)
        
        # Update table
        self._update_table_style(colors)
        
        # Update pagination status
        self._update_pagination_status_style(colors)
        
        # Update action buttons container
        self._update_action_buttons_style(colors)
        
        # ✅ FIX: Reload categories to refresh table display with new theme colors
        self.load_categories()
        
        # ✅ FIX: Update summary widget
        if hasattr(self, 'summary_widget'):
            self.summary_widget.refresh()
    
    # ==================== Data Loading ====================
    
    def load_categories(self):
        """Load categories from database"""
        try:
            self.load_parent_filter()
            
            status_filter = None if self.filter_status == 'all' else self.filter_status
            parent_filter = self._get_parent_filter()
            
            self.categories, total = self.service.get_categories(
                status=status_filter,
                parent_id=parent_filter,
                search=self.search_text if self.search_text else None,
                limit=self.page_size,
                offset=(self.current_page - 1) * self.page_size
            )
            
            self.pagination.set_total_items(total, emit_signal=False)
            self.populate_table(self.categories)
            self.update_selection_label()
            
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load categories: {e}")
    
    def load_parent_filter(self):
        """Load parent filter options"""
        try:
            categories, _ = self.service.get_categories(limit=1000)
            self.parent_filter.blockSignals(True)
            
            current_data = self.parent_filter.currentData()
            self.parent_filter.clear()
            all_parents_label, no_parent_label = self._parent_filter_labels()
            self.parent_filter.addItem(all_parents_label, None)
            self.parent_filter.addItem(no_parent_label, -1)
            
            # Add category names with icons
            for cat in sorted(categories, key=lambda item: (item.get('sort_order', 0), item.get('name') or '')):
                name = cat.get('name')
                if not name:
                    continue
                icon = cat.get('icon') or '📁'
                self.parent_filter.addItem(f"{icon} {name}", cat.get('id'))
            
            idx = self.parent_filter.findData(current_data)
            self.parent_filter.setCurrentIndex(idx if idx >= 0 else 0)
            self.parent_filter.blockSignals(False)
            
        except Exception as e:
            logger.error(f"Failed to load parent filter: {e}")
    
    def _get_parent_filter(self):
        """Get parent filter value"""
        return self.parent_filter.currentData()

    def _parent_filter_labels(self):
        if lang.get_current() == "my":
            return "📂 မိဘအားလုံး", "📁 မိဘမရှိ"
        return "📂 All Parents", "📁 No Parent"

    def _configure_filter_data(self):
        """Keep filter values stable when display text is translated."""
        for index, value in enumerate(("all", "active", "inactive", "hidden")):
            self.status_filter.setItemData(index, value)
        self.filter_status = self.status_filter.currentData() or "all"
    
    def update_statistics(self):
        """Update statistics"""
        if hasattr(self, 'summary_widget'):
            self.summary_widget.refresh()
    
    def update_selection_label(self):
        """Update selection label"""
        selected = len(self.table.selectedIndexes())
        if selected > 0:
            rows = set(idx.row() for idx in self.table.selectedIndexes())
            selected_count = len(rows)
            self.selection_label.setText(f"☑️ {selected_count} selected")
            if hasattr(self, "btn_edit"):
                self.btn_edit.setEnabled(selected_count == 1)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setEnabled(selected_count >= 1)
        else:
            self.selection_label.setText("☐ 0 selected")
            if hasattr(self, "btn_edit"):
                self.btn_edit.setEnabled(False)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setEnabled(False)
    
    # ==================== Event Handlers ====================
    
    def on_summary_card_clicked(self, card_type: str):
        """Handle click on summary card"""
        status_map = {
            'total': 'all',
            'active': 'active',
            'inactive': 'inactive',
            'hidden': 'hidden'
        }
        
        if card_type in status_map:
            status = status_map[card_type]
            if status == 'all':
                self.status_filter.setCurrentIndex(0)
            elif status == 'active':
                self.status_filter.setCurrentIndex(1)
            elif status == 'inactive':
                self.status_filter.setCurrentIndex(2)
            elif status == 'hidden':
                self.status_filter.setCurrentIndex(3)
            self.filter_status = status
            self.load_categories()
        elif card_type == 'products':
            self.search_input.setText("")
            self.status_filter.setCurrentIndex(0)
            QMessageBox.information(self, "Products", 
                "Categories with products are shown in the list.\n"
                "You can manage products from the Products section.")
    
    def on_page_changed(self, page: int, page_size: int):
        """Handle page change"""
        self.current_page = page
        self.page_size = page_size
        self.load_categories()
    
    def on_search_changed(self, text: str):
        """Handle search text change"""
        self.search_text = text.strip()
        self.current_page = 1
        self.load_categories()
    
    def on_filter_changed(self):
        """Handle filter change"""
        self.filter_status = self.status_filter.currentData() or "all"
        self.current_page = 1
        self.load_categories()
    
    def on_selection_changed(self):
        """Handle selection change"""
        self.update_selection_label()
    
    # ==================== Retranslate ====================
    
    def retranslateUi(self):
        """Retranslate UI"""
        is_my = lang.get_current() == "my"
        
        if is_my:
            self.setWindowTitle("အမျိုးအစားများ စီမံခန့်ခွဲခြင်း")
            if hasattr(self, "title_label"):
                self.title_label.setText("📂 အမျိုးအစားများ")
            if hasattr(self, "subtitle_label"):
                self.subtitle_label.setText("Parent/Child အမျိုးအစားများဖြင့် ပစ္စည်းများကို စနစ်တကျခွဲထားပါ။")
            self.search_input.setPlaceholderText("🔍 အမျိုးအစားရှာရန်...")
            self.btn_add.setText("➕ အမျိုးအစားအသစ်")
            self.btn_edit.setText("✏️ ပြင်မည်")
            self.btn_delete.setText("🗑️ ဖျက်မည်")
            self.btn_merge.setText("🔀 ပေါင်းမည်")
            self.btn_export.setText("📤 ထုတ်မည်")
            self.btn_import.setText("📥 သွင်းမည်")
            
            self.table.setHorizontalHeaderLabels([
                "ID", "အမည်", "မိဘ", "ပစ္စည်း", "အခြေအနေ"
            ])
            
            self.status_filter.setItemText(0, "အားလုံး")
            self.status_filter.setItemText(1, "အသက်ဝင်")
            self.status_filter.setItemText(2, "မလှုပ်ရှား")
            self.status_filter.setItemText(3, "ဝှက်ထား")
            
            self.parent_filter.setItemText(0, "📂 မိဘအားလုံး")
            self.parent_filter.setItemText(1, "📁 မိဘမရှိ")
            
        else:
            self.setWindowTitle("Manage Categories")
            if hasattr(self, "title_label"):
                self.title_label.setText("📂 Categories")
            if hasattr(self, "subtitle_label"):
                self.subtitle_label.setText("Organize products into parent and child categories.")
            self.search_input.setPlaceholderText("🔍 Search categories...")
            self.btn_add.setText("➕ Add Category")
            self.btn_edit.setText("✏️ Edit")
            self.btn_delete.setText("🗑️ Delete")
            self.btn_merge.setText("🔀 Merge")
            self.btn_export.setText("📤 Export")
            self.btn_import.setText("📥 Import")
            
            self.table.setHorizontalHeaderLabels([
                "ID", "Name", "Parent", "Products", "Status"
            ])
            
            self.status_filter.setItemText(0, "All")
            self.status_filter.setItemText(1, "Active")
            self.status_filter.setItemText(2, "Inactive")
            self.status_filter.setItemText(3, "Hidden")
            
            self.parent_filter.setItemText(0, "📂 All Parents")
            self.parent_filter.setItemText(1, "📁 No Parent")

        self._update_control_tooltips(is_my)
        
        # ✅ Retranslate summary widget
        if hasattr(self, 'summary_widget'):
            self.summary_widget.retranslateUi()
        
        # ✅ Refresh table with new language
        self.load_categories()

    def _update_control_tooltips(self, is_my):
        if is_my:
            self.status_filter.setToolTip("အခြေအနေအလိုက် စစ်ထုတ်ရန်")
            self.parent_filter.setToolTip("Parent category တစ်ခုအောက်ရှိ child များကို ကြည့်ရန်")
            self.btn_add.setToolTip("အမျိုးအစားအသစ်ထည့်ရန်")
            self.btn_edit.setToolTip("ရွေးထားသောအမျိုးအစားကိုပြင်ရန်")
            self.btn_delete.setToolTip("ရွေးထားသောအမျိုးအစားကိုဖျက်ရန်")
            self.btn_merge.setToolTip("အမျိုးအစားများကို တစ်ခုထဲပေါင်းရန်")
            self.btn_export.setToolTip("အမျိုးအစားများ export ထုတ်ရန်")
            self.btn_import.setToolTip("အမျိုးအစားများ import သွင်းရန်")
        else:
            self.status_filter.setToolTip("Filter categories by status")
            self.parent_filter.setToolTip("Show all categories or only children under one parent")
            self.btn_add.setToolTip("Create a new category")
            self.btn_edit.setToolTip("Edit the selected category")
            self.btn_delete.setToolTip("Delete the selected category")
            self.btn_merge.setToolTip("Merge multiple categories into one")
            self.btn_export.setToolTip("Export categories")
            self.btn_import.setToolTip("Import categories")


def _attach_category_list_helpers():
    """Attach pure-Python helper methods without PyQt multiple inheritance."""
    for mixin in (CategoryListUI, CategoryListTable, CategoryListActions):
        for name, value in mixin.__dict__.items():
            if name.startswith("__") or hasattr(CategoryListDialog, name):
                continue
            setattr(CategoryListDialog, name, value)


_attach_category_list_helpers()
