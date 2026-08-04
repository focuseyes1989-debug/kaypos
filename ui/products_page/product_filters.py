# ui/products_page/product_filters.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QComboBox, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QIcon
from models.database import connect_db
from ui.widgets.search_widget import ModernSearchWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import os


class ProductFilters(QWidget):
    filter_changed = pyqtSignal()
    barcode_scanned = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # ✅ Theme tracking
        self._is_dark = is_dark_theme()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.setLayout(layout)

        # ✅ Search Widget
        self.search_widget = ModernSearchWidget("Search by name / barcode / SKU...")
        self.search_widget.search_changed.connect(self._on_filter_changed)
        self.search_widget.search_cleared.connect(self._on_filter_changed)
        self.search_widget.setFixedWidth(280)
        layout.addWidget(self.search_widget)

        # ✅ Category Container
        category_container = QWidget()
        category_container.setObjectName("categoryContainer")
        category_container.setStyleSheet("background: transparent;")
        category_layout = QHBoxLayout(category_container)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(2)

        # ✅ Category Label - Theme aware
        self.category_label = QLabel("Category:")
        self.category_label.setObjectName("categoryLabel")
        self._update_label_style()
        category_layout.addWidget(self.category_label)

        # ✅ Category Combo Box - Theme aware
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("categoryCombo")
        self.category_combo.addItem("All Categories")
        self.category_combo.currentTextChanged.connect(self._on_filter_changed)
        self.category_combo.setFixedWidth(180)  # ✅ 130 ကနေ 160 ကိုပြောင်းပါ
        self.category_combo.setFixedHeight(32)
        self._update_combo_style()
        category_layout.addWidget(self.category_combo)

        layout.addWidget(category_container)
        layout.addStretch()

        # ✅ Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._update_label_style()
        self._update_combo_style()
        # Update search widget too
        self.search_widget._on_theme_changed(theme_name)

    def _update_label_style(self):
        """Update category label style based on theme"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        text_color = colors['text']
        
        self.category_label.setStyleSheet(f"""
            QLabel#categoryLabel {{
                font-weight: 500;
                font-size: 10pt;
                padding: 0px 2px 0px 2px;
                color: {text_color};
                background: transparent;
                border: none;
            }}
        """)

    def _update_combo_style(self):
        """Update combo box style based on theme"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            bg_color = "#40444b"
            border_color = "#40444b"
            border_focus = "#5865f2"
            text_color = "#dcddde"
            hover_bg = "#36393f"
            popup_bg = "#2f3136"
            popup_border = "#40444b"
            popup_hover = "#40444b"
            popup_selected = "#5865f2"
            arrow_color = "#b9bbbe"
        else:
            bg_color = "#ffffff"
            border_color = "#ced4da"
            border_focus = "#5865f2"
            text_color = "#212529"
            hover_bg = "#e9ecef"
            popup_bg = "#ffffff"
            popup_border = "#ced4da"
            popup_hover = "#e9ecef"
            popup_selected = "#5865f2"
            arrow_color = "#495057"
        
        self.category_combo.setStyleSheet(f"""
            QComboBox#categoryCombo {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 2px 4px 2px 10px;
                color: {text_color};
                font-size: 10pt;
                min-height: 28px;
                max-height: 32px;
            }}
            QComboBox#categoryCombo:focus {{
                border: 1px solid {border_focus};
            }}
            QComboBox#categoryCombo::drop-down {{
                border: none;
                background: transparent;
                width: 20px;
            }}
            QComboBox#categoryCombo::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {arrow_color};
                margin-right: 6px;
            }}
            
            /* ✅ Popup (Dropdown) */
            QComboBox#categoryCombo QAbstractItemView {{
                background-color: {popup_bg} !important;
                border: 1px solid {popup_border} !important;
                border-radius: 4px !important;
                color: {text_color} !important;
                selection-background-color: {popup_selected} !important;
                selection-color: white !important;
                outline: none !important;
                padding: 4px !important;
            }}
            
            /* ✅ Popup Items */
            QComboBox#categoryCombo QAbstractItemView::item {{
                background-color: transparent !important;
                color: {text_color} !important;
                padding: 6px 12px !important;
                border: none !important;
                border-radius: 2px !important;
                min-height: 24px !important;
            }}
            
            /* ✅ Popup Item - Hover */
            QComboBox#categoryCombo QAbstractItemView::item:hover {{
                background-color: {popup_hover} !important;
                color: {text_color} !important;
            }}
            
            /* ✅ Popup Item - Selected */
            QComboBox#categoryCombo QAbstractItemView::item:selected {{
                background-color: {popup_selected} !important;
                color: white !important;
            }}
        """)

    def _on_filter_changed(self):
        self.filter_changed.emit()

    def get_search_text(self) -> str:
        return self.search_widget.get_text().lower()

    def get_category(self) -> str:
        return self.category_combo.currentText()

    def load_categories(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        rows = cursor.fetchall()
        self.category_combo.blockSignals(True)
        current = self.category_combo.currentText()
        self.category_combo.clear()
        self.category_combo.addItem("All Categories")
        for (name,) in rows:
            self.category_combo.addItem(name)
        idx = self.category_combo.findText(current)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)
        conn.close()

    def reset(self):
        """Reset search and category to default (all products)"""
        self.search_widget.clear_search()
        self.category_combo.setCurrentIndex(0)

    def focus_search(self):
        self.search_widget.focus_search()

    def retranslateUi(self):
        from utils.language import lang
        colors = get_theme_colors()
        text_color = colors['text']
        
        if lang.get_current() == "my":
            self.search_widget.retranslateUi("my")
            self.search_widget.set_placeholder_text("ပစ္စည်းအမည် / ဘားကုဒ် / SKU ဖြင့် ရှာရန်...")
            self.category_label.setText("အမျိုးအစား:")
            if self.category_combo.count() > 0:
                self.category_combo.setItemText(0, "အားလုံး")
        else:
            self.search_widget.retranslateUi("en")
            self.search_widget.set_placeholder_text("Search by name / barcode / SKU...")
            self.category_label.setText("Category:")
            if self.category_combo.count() > 0:
                self.category_combo.setItemText(0, "All Categories")
        
        # ✅ Update label style after language change (keep theme colors)
        self._update_label_style()
        self._update_combo_style()