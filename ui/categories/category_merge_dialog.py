# ui/categories/category_merge_dialog.py
"""
Category Merge Dialog
✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMessageBox, QFrame,
    QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ui.categories.category_service import CategoryService
from ui.widgets.modern_button import ModernButton
from utils.translations import tr
from utils.language import lang
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager

from loguru import logger


class CategoryMergeDialog(QDialog):
    """Dialog for merging categories - Theme-aware"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.service = CategoryService()
        self.source_categories = []
        self.target_category = None
        
        self.setup_ui()
        self.load_categories()
        
        # Language support
        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
        
        # ✅ Connect theme manager for auto refresh
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """✅ Handle theme change - update UI styles"""
        self._apply_theme_styles()
        # Refresh list and combo styles
        self._refresh_list_style()
        self._refresh_combo_style()
    
    def _apply_theme_styles(self):
        """Apply theme-aware styles to the dialog"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QFrame#separator {{
                background-color: {colors['border']};
                max-height: 1px;
            }}
            QFrame#optionsFrame {{
                background: {colors['bg_hover']};
                border-radius: 6px;
                padding: 8px;
            }}
            QCheckBox {{
                color: {colors['text']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                background: {colors['card_bg']};
                border: 1px solid {colors['input_border']};
            }}
            QCheckBox::indicator:checked {{
                background: #5865f2;
                border-color: #5865f2;
            }}
            QListWidget {{
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid {colors['border']};
                color: {colors['text']};
                background: transparent;
            }}
            QListWidget::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: rgba(88, 101, 242, 0.08);
            }}
            QComboBox {{
                padding: 8px 14px;
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                font-size: 10pt;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors['text_secondary']};
                margin-right: 4px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                background-color: transparent;
                color: {colors['text']};
                padding: 6px 10px;
                border: none;
                border-radius: 1px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
            QScrollBar:vertical {{
                background: {colors['bg']};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-height: 16px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: {colors['bg']};
                height: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-width: 16px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background: transparent;
            }}
        """)
    
    def _refresh_list_style(self):
        """Refresh list widget style after theme change"""
        colors = get_theme_colors()
        self.source_list.setStyleSheet(f"""
            QListWidget {{
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid {colors['border']};
                color: {colors['text']};
                background: transparent;
            }}
            QListWidget::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: rgba(88, 101, 242, 0.08);
            }}
            QScrollBar:vertical {{
                background: {colors['bg']};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-height: 16px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
    
    def _refresh_combo_style(self):
        """Refresh combo box style after theme change"""
        colors = get_theme_colors()
        self.target_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 14px;
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                font-size: 10pt;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors['text_secondary']};
                margin-right: 4px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                background-color: transparent;
                color: {colors['text']};
                padding: 6px 10px;
                border: none;
                border-radius: 1px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """)
    
    def setup_ui(self):
        """Setup the UI"""
        self.setWindowTitle("Merge Categories")
        self.setModal(True)
        self.resize(700, 550)
        self.setMinimumWidth(650)
        
        # Apply theme styles
        self._apply_theme_styles()
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 18)
        
        colors = get_theme_colors()
        
        # Header
        header_label = QLabel("🔀 Merge Categories")
        header_label.setStyleSheet(f"font-size: 16pt; font-weight: 700; color: {colors['text']};")
        main_layout.addWidget(header_label)
        
        desc_label = QLabel(
            "Select categories to merge into a single target category.\n"
            "All products from source categories will be moved to the target category."
        )
        desc_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10pt;")
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)
        
        # Separator
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {colors['border']}; max-height: 1px;")
        main_layout.addWidget(separator)
        
        # Source categories
        source_label = QLabel("Source Categories (select multiple)")
        source_label.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {colors['text']};")
        main_layout.addWidget(source_label)
        
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.source_list.setStyleSheet(f"""
            QListWidget {{
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
                min-height: 150px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid {colors['border']};
                color: {colors['text']};
                background: transparent;
            }}
            QListWidget::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: rgba(88, 101, 242, 0.08);
            }}
        """)
        main_layout.addWidget(self.source_list, 1)
        
        # Buttons to move categories
        move_layout = QHBoxLayout()
        move_layout.setSpacing(10)
        
        self.btn_add_all = ModernButton("Select All", ModernButton.SECONDARY)
        self.btn_add_all.clicked.connect(self.select_all)
        move_layout.addWidget(self.btn_add_all)
        
        self.btn_clear = ModernButton("Clear Selection", ModernButton.TERTIARY)
        self.btn_clear.clicked.connect(self.clear_selection)
        move_layout.addWidget(self.btn_clear)
        
        move_layout.addStretch()
        main_layout.addLayout(move_layout)
        
        # Target category
        target_label = QLabel("Target Category")
        target_label.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {colors['text']};")
        main_layout.addWidget(target_label)
        
        self.target_combo = QComboBox()
        self.target_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 14px;
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                font-size: 10pt;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {colors['text_secondary']};
                margin-right: 4px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                background-color: transparent;
                color: {colors['text']};
                padding: 6px 10px;
                border: none;
                border-radius: 1px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """)
        main_layout.addWidget(self.target_combo)
        
        # Options
        options_frame = QFrame()
        options_frame.setObjectName("optionsFrame")
        options_frame.setStyleSheet(f"""
            QFrame#optionsFrame {{
                background: {colors['bg_hover']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        options_layout = QVBoxLayout(options_frame)
        options_layout.setSpacing(4)
        
        self.delete_sources_check = QCheckBox("Delete source categories after merge")
        self.delete_sources_check.setChecked(True)
        self.delete_sources_check.setStyleSheet(f"""
            QCheckBox {{
                color: {colors['text']};
                font-size: 10pt;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                background: {colors['card_bg']};
                border: 1px solid {colors['input_border']};
            }}
            QCheckBox::indicator:checked {{
                background: #5865f2;
                border-color: #5865f2;
            }}
        """)
        options_layout.addWidget(self.delete_sources_check)
        
        self.preserve_sort_check = QCheckBox("Preserve sort order from source categories")
        self.preserve_sort_check.setChecked(False)
        self.preserve_sort_check.setStyleSheet(f"""
            QCheckBox {{
                color: {colors['text']};
                font-size: 10pt;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                background: {colors['card_bg']};
                border: 1px solid {colors['input_border']};
            }}
            QCheckBox::indicator:checked {{
                background: #5865f2;
                border-color: #5865f2;
            }}
        """)
        options_layout.addWidget(self.preserve_sort_check)
        
        main_layout.addWidget(options_frame)
        
        # Summary
        self.summary_label = QLabel("Selected: 0 categories to merge")
        self.summary_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10pt; padding: 4px;")
        main_layout.addWidget(self.summary_label)
        
        # Connect selection change
        self.source_list.itemSelectionChanged.connect(self.update_summary)
        self.target_combo.currentTextChanged.connect(self.update_summary)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.btn_cancel = ModernButton("✖ Cancel", ModernButton.TERTIARY)
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        button_layout.addStretch()
        
        self.btn_merge = ModernButton("🔀 Merge Categories", ModernButton.PRIMARY)
        self.btn_merge.clicked.connect(self.merge)
        self.btn_merge.setMinimumWidth(150)
        button_layout.addWidget(self.btn_merge)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def load_categories(self):
        """Load categories into the list and combo"""
        try:
            categories, _ = self.service.get_categories(limit=1000)
            
            # Populate source list
            self.source_list.clear()
            for cat in categories:
                if not cat.get('is_system', False):
                    item = QListWidgetItem(f"{cat.get('icon', '📁')} {cat['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, cat['id'])
                    item.setData(Qt.ItemDataRole.UserRole + 1, cat)
                    self.source_list.addItem(item)
            
            # Populate target combo
            self.target_combo.clear()
            for cat in categories:
                self.target_combo.addItem(
                    f"{cat.get('icon', '📁')} {cat['name']} ({cat.get('product_count', 0)} products)",
                    cat['id']
                )
            
            self.update_summary()
            
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load categories: {e}")
    
    def select_all(self):
        """Select all source categories"""
        for i in range(self.source_list.count()):
            self.source_list.item(i).setSelected(True)
    
    def clear_selection(self):
        """Clear selection"""
        self.source_list.clearSelection()
    
    def update_summary(self):
        """Update summary label"""
        selected = self.source_list.selectedItems()
        count = len(selected)
        
        target_text = self.target_combo.currentText()
        target_id = self.target_combo.currentData()
        
        if target_id is None:
            target_name = "No target selected"
        else:
            target_name = target_text or "No target selected"
        
        self.summary_label.setText(
            f"Selected: {count} categories to merge into '{target_name}'"
        )
        
        # Enable/disable merge button
        self.btn_merge.setEnabled(count > 0 and target_id is not None)
    
    def merge(self):
        """Execute the merge operation"""
        selected = self.source_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select source categories to merge.")
            return
        
        target_id = self.target_combo.currentData()
        if target_id is None:
            QMessageBox.warning(self, "No Target", "Please select a target category.")
            return
        
        # Get source IDs
        source_ids = []
        source_names = []
        for item in selected:
            cat_id = item.data(Qt.ItemDataRole.UserRole)
            if cat_id:
                source_ids.append(cat_id)
                cat = item.data(Qt.ItemDataRole.UserRole + 1)
                source_names.append(cat['name'] if cat else str(cat_id))
        
        # Check if target in source
        if target_id in source_ids:
            QMessageBox.warning(self, "Invalid Merge", "Target category cannot be in source list.")
            return
        
        # Confirm
        target = self.service.get_category(target_id)
        if not target:
            QMessageBox.warning(self, "Error", "Target category not found.")
            return
        
        msg = (
            f"Merge {len(source_ids)} categories into '{target['name']}'?\n\n"
            f"Source categories:\n• " + "\n• ".join(source_names) + "\n\n"
            f"All products will be moved to '{target['name']}'."
        )
        
        if self.delete_sources_check.isChecked():
            msg += "\n\nSource categories will be deleted after merge."
        
        reply = QMessageBox.question(
            self,
            "Confirm Merge",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        try:
            result = self.service.merge_categories(source_ids, target_id)
            
            # Show results
            msg = f"Merge completed!\n\n"
            msg += f"Products moved: {result['updated_products']}\n"
            msg += f"Children moved: {result['updated_children']}\n"
            msg += f"Merged: {len(result['merged'])} categories\n"
            
            if result['failed']:
                msg += f"\nFailed: {len(result['failed'])} categories"
                for fail in result['failed'][:5]:
                    msg += f"\n  • {fail.get('name', 'Unknown')}: {fail.get('reason', 'Unknown error')}"
            
            QMessageBox.information(self, "Merge Complete", msg)
            self.accept()
            
        except Exception as e:
            logger.error(f"Merge failed: {e}")
            QMessageBox.critical(self, "Merge Failed", str(e))
    
    def retranslateUi(self):
        """Retranslate UI"""
        is_my = lang.get_current() == "my"
        colors = get_theme_colors()
        
        if is_my:
            self.setWindowTitle("အမျိုးအစားများ ပေါင်းခြင်း")
            self.btn_add_all.setText("အားလုံးရွေးရန်")
            self.btn_clear.setText("ရွေးချယ်မှုဖယ်ရှားရန်")
            self.btn_merge.setText("🔀 ပေါင်းမည်")
            self.btn_cancel.setText("✖ မလုပ်တော့ပါ")
            self.delete_sources_check.setText("ပေါင်းပြီးနောက် ရင်းမြစ်အမျိုးအစားများ ဖျက်ရန်")
            self.preserve_sort_check.setText("ရင်းမြစ်အမျိုးအစားများ၏ စီအစဉ်ကို ထိန်းသိမ်းရန်")
            
            # Update descriptions
            for i in range(self.source_list.count()):
                item = self.source_list.item(i)
                if item:
                    data = item.data(Qt.ItemDataRole.UserRole + 1)
                    if data:
                        item.setText(f"{data.get('icon', '📁')} {data['name']}")
            
            # Update combo items
            for i in range(self.target_combo.count()):
                cat_id = self.target_combo.itemData(i)
                if cat_id:
                    cat = self.service.get_category(cat_id)
                    if cat:
                        self.target_combo.setItemText(
                            i, 
                            f"{cat.get('icon', '📁')} {cat['name']} ({cat.get('product_count', 0)} ပစ္စည်း)"
                        )
            
            self.summary_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10pt; padding: 4px;")
            
        else:
            self.setWindowTitle("Merge Categories")
            self.btn_add_all.setText("Select All")
            self.btn_clear.setText("Clear Selection")
            self.btn_merge.setText("🔀 Merge Categories")
            self.btn_cancel.setText("✖ Cancel")
            self.delete_sources_check.setText("Delete source categories after merge")
            self.preserve_sort_check.setText("Preserve sort order from source categories")
            
            # Update descriptions back to English
            for i in range(self.source_list.count()):
                item = self.source_list.item(i)
                if item:
                    data = item.data(Qt.ItemDataRole.UserRole + 1)
                    if data:
                        item.setText(f"{data.get('icon', '📁')} {data['name']}")
            
            for i in range(self.target_combo.count()):
                cat_id = self.target_combo.itemData(i)
                if cat_id:
                    cat = self.service.get_category(cat_id)
                    if cat:
                        self.target_combo.setItemText(
                            i, 
                            f"{cat.get('icon', '📁')} {cat['name']} ({cat.get('product_count', 0)} products)"
                        )
            
            self.summary_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10pt; padding: 4px;")
        
        # Update summary
        self.update_summary()
    
    def closeEvent(self, event):
        """Handle close event"""
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        event.accept()