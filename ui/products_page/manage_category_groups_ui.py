# ui/products_page/manage_category_groups_ui.py
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QCheckBox, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import get_theme_colors, is_dark_theme


class CategoryGroupsUI:
    """UI setup class for CategoryGroupsDialog"""
    
    def __init__(self):
        self.table_widget = None
        self.search_input = None
        self.show_favorites_only = None
        self.total_label = None
        self.favorites_label = None
        self.count_badge = None
        self.status_label = None
        self.btn_add = None
        self.btn_edit = None
        self.btn_delete = None
        self.btn_manage_categories = None
        self.btn_quick_add = None
    
    def setup_ui(self, dialog):
        """Setup the complete UI"""
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 18)
        
        # Header
        self._create_header(dialog, main_layout)
        
        # Search bar
        self._create_search_bar(dialog, main_layout)
        
        # Stats bar
        self._create_stats_bar(dialog, main_layout)
        
        # Table
        self._create_table(dialog, main_layout)
        
        # Action buttons
        self._create_action_buttons(dialog, main_layout)
        
        # Status bar
        self._create_status_bar(dialog, main_layout)
    
    def _create_header(self, dialog, parent_layout):
        """Create header section"""
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📁 Category Groups")
        title_label.setObjectName("headerTitle")
        title_label.setStyleSheet("font-size: 16pt; font-weight: 600;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Count badge
        dialog.count_badge = QLabel("0")
        dialog.count_badge.setObjectName("countBadge")
        dialog.count_badge.setStyleSheet("""
            background: #5865f2;
            color: white;
            padding: 4px 16px;
            border-radius: 12px;
            font-size: 10pt;
            font-weight: 600;
            min-width: 30px;
            text-align: center;
        """)
        header_layout.addWidget(dialog.count_badge)
        self.count_badge = dialog.count_badge
        
        parent_layout.addLayout(header_layout)
    
    def _create_search_bar(self, dialog, parent_layout):
        """Create search bar with filter"""
        search_widget = QWidget()
        search_widget.setObjectName("searchWidget")
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        # Search icon
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 14px;")
        search_layout.addWidget(search_icon)
        
        # Search input
        dialog.search_input = QLineEdit()
        dialog.search_input.setPlaceholderText("Search groups...")
        dialog.search_input.setObjectName("searchInput")
        dialog.search_input.setClearButtonEnabled(True)
        search_layout.addWidget(dialog.search_input, 1)
        self.search_input = dialog.search_input
        
        # Favorites filter
        dialog.show_favorites_only = QCheckBox("⭐")
        dialog.show_favorites_only.setObjectName("favoritesFilter")
        dialog.show_favorites_only.setToolTip("Show favorites only")
        dialog.show_favorites_only.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                spacing: 2px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
        """)
        search_layout.addWidget(dialog.show_favorites_only)
        self.show_favorites_only = dialog.show_favorites_only
        
        parent_layout.addWidget(search_widget)
    
    def _create_stats_bar(self, dialog, parent_layout):
        """Create statistics bar"""
        stats_widget = QWidget()
        stats_widget.setObjectName("statsWidget")
        stats_widget.setStyleSheet("""
            QWidget#statsWidget {
                background: rgba(88, 101, 242, 0.08);
                border-radius: 8px;
                padding: 4px;
            }
        """)
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setContentsMargins(12, 6, 12, 6)
        stats_layout.setSpacing(20)
        
        dialog.total_label = QLabel("📊 Total: 0")
        dialog.total_label.setObjectName("statLabel")
        dialog.total_label.setStyleSheet("font-weight: 500; font-size: 10pt;")
        stats_layout.addWidget(dialog.total_label)
        self.total_label = dialog.total_label
        
        dialog.favorites_label = QLabel("⭐ Favorites: 0")
        dialog.favorites_label.setObjectName("statLabel")
        dialog.favorites_label.setStyleSheet("font-weight: 500; font-size: 10pt;")
        stats_layout.addWidget(dialog.favorites_label)
        self.favorites_label = dialog.favorites_label
        
        stats_layout.addStretch()
        
        # Quick add button
        dialog.btn_quick_add = ModernButton("➕ Add Group", ModernButton.PRIMARY)
        dialog.btn_quick_add.set_compact(True)
        dialog.btn_quick_add.setFixedHeight(28)
        stats_layout.addWidget(dialog.btn_quick_add)
        self.btn_quick_add = dialog.btn_quick_add
        
        parent_layout.addWidget(stats_widget)
    
    def _create_table(self, dialog, parent_layout):
        """Create table widget"""
        dialog.table_widget = QTableWidget()
        dialog.table_widget.setObjectName("groupsTable")
        dialog.table_widget.setColumnCount(5)
        dialog.table_widget.setHorizontalHeaderLabels(["Icon", "Name", "Description", "Categories", "Fav"])
        dialog.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        dialog.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        dialog.table_widget.setAlternatingRowColors(True)
        dialog.table_widget.setShowGrid(False)
        
        # Column widths
        dialog.table_widget.setColumnWidth(0, 60)
        dialog.table_widget.setColumnWidth(1, 180)
        dialog.table_widget.setColumnWidth(2, 200)
        dialog.table_widget.setColumnWidth(3, 100)
        dialog.table_widget.setColumnWidth(4, 60)
        
        parent_layout.addWidget(dialog.table_widget, 1)
        self.table_widget = dialog.table_widget
    
    def _create_action_buttons(self, dialog, parent_layout):
        """Create action buttons"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        dialog.btn_add = ModernButton("➕ Add Group", ModernButton.PRIMARY)
        dialog.btn_add.set_compact(False)
        dialog.btn_add.setMinimumHeight(34)
        dialog.btn_add.setMinimumWidth(120)
        button_layout.addWidget(dialog.btn_add)
        self.btn_add = dialog.btn_add
        
        dialog.btn_edit = ModernButton("✏️ Edit", ModernButton.SECONDARY)
        dialog.btn_edit.set_compact(False)
        dialog.btn_edit.setMinimumHeight(34)
        dialog.btn_edit.setMinimumWidth(100)
        button_layout.addWidget(dialog.btn_edit)
        self.btn_edit = dialog.btn_edit
        
        dialog.btn_delete = ModernButton("🗑️ Delete", ModernButton.TERTIARY)
        dialog.btn_delete.set_compact(False)
        dialog.btn_delete.setMinimumHeight(34)
        dialog.btn_delete.setMinimumWidth(100)
        button_layout.addWidget(dialog.btn_delete)
        self.btn_delete = dialog.btn_delete
        
        button_layout.addStretch()
        
        dialog.btn_manage_categories = ModernButton("📂 Categories", ModernButton.PRIMARY)
        dialog.btn_manage_categories.set_compact(False)
        dialog.btn_manage_categories.setMinimumHeight(34)
        dialog.btn_manage_categories.setMinimumWidth(120)
        dialog.btn_manage_categories.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        button_layout.addWidget(dialog.btn_manage_categories)
        self.btn_manage_categories = dialog.btn_manage_categories
        
        parent_layout.addLayout(button_layout)
    
    def _create_status_bar(self, dialog, parent_layout):
        """Create status bar"""
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_bar.setStyleSheet("QFrame#statusBar { background: transparent; border: none; padding: 2px; }")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(4, 2, 4, 2)
        
        dialog.status_label = QLabel("Ready")
        dialog.status_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
        status_layout.addWidget(dialog.status_label)
        self.status_label = dialog.status_label
        
        status_layout.addStretch()
        
        shortcut_hint = QLabel("ESC: Close | F: Search | Delete: Remove")
        shortcut_hint.setStyleSheet("color: #95a5a6; font-size: 8pt;")
        status_layout.addWidget(shortcut_hint)
        
        parent_layout.addWidget(status_bar)
    
    def retranslate_ui(self):
        """Retranslate UI elements"""
        from utils.language import lang
        is_my = lang.get_current() == "my"
        
        if self.table_widget:
            if is_my:
                self.table_widget.setHorizontalHeaderLabels([
                    "အိုင်ကွန်", "အမည်", "ဖော်ပြချက်", "အမျိုးအစား", "ကြယ်"
                ])
            else:
                self.table_widget.setHorizontalHeaderLabels([
                    "Icon", "Name", "Description", "Categories", "Fav"
                ])
        
        if self.btn_add:
            self.btn_add.setText("➕ Add Group" if not is_my else "➕ အုပ်စုအသစ်")
        if self.btn_edit:
            self.btn_edit.setText("✏️ Edit" if not is_my else "✏️ ပြင်မည်")
        if self.btn_delete:
            self.btn_delete.setText("🗑️ Delete" if not is_my else "🗑️ ဖျက်မည်")
        if self.btn_manage_categories:
            self.btn_manage_categories.setText("📂 Categories" if not is_my else "📂 အမျိုးအစားများ")
        if self.btn_quick_add:
            self.btn_quick_add.setText("➕ Add Group" if not is_my else "➕ အုပ်စုအသစ်")
        if self.search_input:
            self.search_input.setPlaceholderText("Search groups..." if not is_my else "အုပ်စုရှာရန်...")
        if self.show_favorites_only:
            self.show_favorites_only.setToolTip("Show favorites only" if not is_my else "အနှစ်သက်ဆုံးများသာ ပြရန်")
    
    def apply_theme(self, dialog):
        """Apply theme colors to UI"""
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        # Table scrollbar style
        scrollbar_style = f"""
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
            }}
        """
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QLabel#headerTitle {{
                color: {colors['text']};
            }}
            QLabel#countBadge {{
                background: #5865f2;
                color: white;
            }}
            QLineEdit#searchInput {{
                background-color: {'#40444b' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QLineEdit#searchInput:focus {{
                border-color: #5865f2;
            }}
            QLineEdit#searchInput::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
            QCheckBox#favoritesFilter {{
                color: #f1c40f;
            }}
            QCheckBox#favoritesFilter::indicator {{
                background-color: {'#40444b' if is_dark else '#ffffff'};
                border: 1px solid {colors['input_border']};
                border-radius: 4px;
                width: 20px;
                height: 20px;
            }}
            QCheckBox#favoritesFilter::indicator:checked {{
                background-color: #f1c40f;
                border-color: #f1c40f;
            }}
            QTableWidget#groupsTable {{
                background-color: {'#2f3136' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 2px;
                outline: none;
                gridline-color: transparent;
            }}
            QTableWidget#groupsTable::item {{
                padding: 10px 12px;
                border: none;
                color: {colors['text']};
            }}
            QTableWidget#groupsTable::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
            QTableWidget#groupsTable::item:hover:!selected {{
                background-color: rgba(88, 101, 242, 0.05);
            }}
            QHeaderView::section {{
                background: {'#202225' if is_dark else '#f8f9fa'};
                color: {colors['text']};
                border: none;
                border-bottom: 2px solid {colors['border']};
                padding: 10px 12px;
                font-weight: 600;
                font-size: 10pt;
            }}
            QWidget#statsWidget {{
                background-color: rgba(88, 101, 242, 0.08);
                border-radius: 8px;
            }}
            QLabel#statLabel {{
                color: {colors['text_secondary']};
            }}
            QWidget#searchWidget {{
                background: transparent;
            }}
            QFrame#statusBar {{
                background: transparent;
            }}
            QFrame#statusBar QLabel {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
            {scrollbar_style}
        """)