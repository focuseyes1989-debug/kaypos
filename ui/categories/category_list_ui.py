# ui/categories/category_list_ui.py
"""
Category List UI - UI setup and layout
✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
✅ SVG Icons - Buttons များမှာ emoji အစား SVG icons များကို သုံးမယ်
✅ ModernButton - နှင့် တွဲဖက်အသုံးပြုထား
"""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QComboBox, QFrame, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.widgets.modern_button import ModernButton
from ui.widgets.pagination_widget import PaginationWidget
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager


class CategoryListUI:
    """UI setup for Category List Dialog - Theme-aware with SVG icons and ModernButton"""
    
    def setup_ui(self):
        """Setup the UI with theme-aware styling"""
        # Theme colors ကို ယူပါ
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        self._setup_header(main_layout, colors)
        
        # Summary Widget
        self._setup_summary(main_layout)
        
        # Search and filter bar
        self._setup_search_bar(main_layout, colors)
        
        # Table
        self._setup_table(main_layout, colors)
        
        # Pagination + Status Bar
        self._setup_pagination_status(main_layout, colors)
        
        # Action buttons
        self._setup_action_buttons(main_layout, colors)
        
        self.setLayout(main_layout)
        
        # ✅ Connect theme change signal
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Theme ပြောင်းတဲ့အခါ UI ကို update လုပ်မယ်"""
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
        
        # Update table content (refresh display)
        self._refresh_table_display()
    
    def _update_header_style(self, colors):
        """Update header style"""
        for child in self.findChildren(QLabel):
            if child.text() == "📂 Categories":
                child.setStyleSheet(f"""
                    font-size: 18pt; 
                    font-weight: 700; 
                    color: {colors['text']};
                """)
    
    def _update_search_bar_style(self, colors):
        """Update search bar style"""
        if hasattr(self, 'search_input'):
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    padding: 10px 16px;
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    font-size: 10pt;
                    background: {colors['card_bg']};
                    color: {colors['text']};
                }}
                QLineEdit:focus {{
                    border-color: #5865f2;
                }}
                QLineEdit:hover {{
                    border-color: {colors['border_hover']};
                }}
                QLineEdit::placeholder {{
                    color: {colors['text_secondary']};
                }}
            """)
        
        # ComboBox styles
        for combo in [self.status_filter, self.parent_filter]:
            if hasattr(self, combo.objectName()):
                combo.setStyleSheet(self._combobox_style(colors))
    
    def _update_table_style(self, colors):
        """Update table style"""
        if hasattr(self, 'table'):
            self.table.setStyleSheet(self._table_style(colors))
    
    def _update_pagination_status_style(self, colors):
        """Update pagination status style"""
        if hasattr(self, 'status_label'):
            self.status_label.setStyleSheet(f"""
                color: {colors['text_secondary']};
                font-size: 10pt;
                padding: 4px 0;
                font-weight: 500;
            """)
        
        if hasattr(self, 'selection_label'):
            self.selection_label.setStyleSheet(f"""
                color: {colors['text_secondary']};
                font-size: 10pt;
                padding: 4px 0;
            """)
        
        separator = self.findChild(QLabel, "separator")
        if separator:
            separator.setStyleSheet(f"color: {colors['border']}; font-size: 10pt;")
    
    def _update_action_buttons_style(self, colors):
        """Update action buttons container style"""
        container = self.findChild(QWidget, "action_container")
        if container:
            container.setStyleSheet(f"""
                QWidget {{
                    background: {colors['bg_hover']};
                    border-radius: 12px;
                }}
            """)
    
    def _refresh_table_display(self):
        """Refresh table display with current data"""
        if hasattr(self, 'load_categories'):
            self.load_categories()
    
    def _setup_header(self, parent_layout, colors):
        """Setup header with theme-aware styling"""
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📂 Categories")
        title_label.setStyleSheet(f"""
            font-size: 18pt; 
            font-weight: 700; 
            color: {colors['text']};
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        parent_layout.addLayout(header_layout)
    
    def _setup_summary(self, parent_layout):
        """Setup summary widget"""
        from ui.categories.category_summary_widget import CategorySummaryWidget
        self.summary_widget = CategorySummaryWidget(self)
        self.summary_widget.card_clicked.connect(self.on_summary_card_clicked)
        parent_layout.addWidget(self.summary_widget)
    
    def _setup_search_bar(self, parent_layout, colors):
        """Setup search and filter bar with theme-aware styling and ModernButton"""
        search_widget = QWidget()
        search_widget.setStyleSheet("QWidget { background: transparent; }")
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search categories...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px 16px;
                border: 1px solid {colors['border']};
                border-radius: 10px;
                font-size: 10pt;
                background: {colors['card_bg']};
                color: {colors['text']};
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit:hover {{
                border-color: {colors['border_hover']};
            }}
            QLineEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """)
        search_layout.addWidget(self.search_input, 2)
        
        # Status filter
        self.status_filter = QComboBox()
        self.status_filter.addItems(['All', 'Active', 'Inactive', 'Hidden'])
        self.status_filter.currentTextChanged.connect(self.on_filter_changed)
        self.status_filter.setStyleSheet(self._combobox_style(colors))
        search_layout.addWidget(self.status_filter)
        
        # Parent filter
        self.parent_filter = QComboBox()
        self.parent_filter.addItem('📂 All Parents')
        self.parent_filter.currentTextChanged.connect(self.on_filter_changed)
        self.parent_filter.setStyleSheet(self._combobox_style(colors))
        search_layout.addWidget(self.parent_filter)
        
        # ✅ Add button with ModernButton and SVG icon
        self.btn_add = ModernButton("Add Category", ModernButton.PRIMARY)
        self.btn_add.set_icon("add", size=(16, 16))
        self.btn_add.setMinimumWidth(140)
        self.btn_add.clicked.connect(self.add_category)
        search_layout.addWidget(self.btn_add)
        
        parent_layout.addWidget(search_widget)
    
    def _setup_table(self, parent_layout, colors):
        """Setup the category table with theme-aware styling"""
        table_container = QWidget()
        table_container.setStyleSheet(f"""
            QWidget {{
                background: {colors['card_bg']};
                border-radius: 12px;
                border: 1px solid {colors['border']};
            }}
        """)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Parent", "Products", "Status"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        
        # Apply table style
        self.table.setStyleSheet(self._table_style(colors))
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(0, 0)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 120)
        
        # Hide ID column
        self.table.setColumnHidden(0, True)
        
        # Connect selection change
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        
        table_layout.addWidget(self.table)
        parent_layout.addWidget(table_container, 1)
    
    def _setup_pagination_status(self, parent_layout, colors):
        """Setup pagination and status bar with theme-aware styling"""
        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; }")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(12)
        
        # Status info
        status_container = QWidget()
        status_container.setStyleSheet("background: transparent;")
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(16)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"""
            color: {colors['text_secondary']};
            font-size: 10pt;
            padding: 4px 0;
            font-weight: 500;
        """)
        status_layout.addWidget(self.status_label)
        
        separator = QLabel("|")
        separator.setObjectName("separator")
        separator.setStyleSheet(f"color: {colors['border']}; font-size: 10pt;")
        status_layout.addWidget(separator)
        
        self.selection_label = QLabel("☐ 0 selected")
        self.selection_label.setStyleSheet(f"""
            color: {colors['text_secondary']};
            font-size: 10pt;
            padding: 4px 0;
        """)
        status_layout.addWidget(self.selection_label)
        
        layout.addWidget(status_container)
        layout.addStretch()
        
        # Pagination
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)
        
        parent_layout.addWidget(container)
    
    def _setup_action_buttons(self, parent_layout, colors):
        """Setup action buttons with theme-aware styling and ModernButton with SVG icons"""
        button_container = QWidget()
        button_container.setObjectName("action_container")
        button_container.setStyleSheet(f"""
            QWidget {{
                background: {colors['bg_hover']};
                border-radius: 12px;
            }}
        """)
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(12, 10, 12, 10)
        button_layout.setSpacing(10)
        
        # ✅ Left actions with ModernButton and SVG icons
        self.btn_edit = ModernButton("Edit", ModernButton.SECONDARY)
        self.btn_edit.set_icon("edit", size=(16, 16))
        self.btn_edit.setMinimumWidth(100)
        self.btn_edit.clicked.connect(self.edit_category)
        button_layout.addWidget(self.btn_edit)
        
        self.btn_delete = ModernButton("Delete", ModernButton.TERTIARY)
        self.btn_delete.set_icon("delete", size=(16, 16))
        self.btn_delete.setMinimumWidth(100)
        self.btn_delete.clicked.connect(self.delete_category)
        button_layout.addWidget(self.btn_delete)
        
        self.btn_merge = ModernButton("Merge", ModernButton.SECONDARY)
        self.btn_merge.set_icon("merge", size=(16, 16))
        self.btn_merge.setMinimumWidth(100)
        self.btn_merge.clicked.connect(self.merge_categories)
        button_layout.addWidget(self.btn_merge)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background-color: {colors['border']}; max-width: 1px;")
        sep.setFixedWidth(1)
        button_layout.addWidget(sep)
        
        button_layout.addStretch()
        
        # ✅ Right actions with ModernButton and SVG icons
        self.btn_export = ModernButton("Export", ModernButton.SECONDARY)
        self.btn_export.set_icon("file_export", size=(16, 16))
        self.btn_export.setMinimumWidth(100)
        self.btn_export.clicked.connect(self.export_categories)
        button_layout.addWidget(self.btn_export)
        
        self.btn_import = ModernButton("Import", ModernButton.SECONDARY)
        self.btn_import.set_icon("upload_file", size=(16, 16))
        self.btn_import.setMinimumWidth(100)
        self.btn_import.clicked.connect(self.import_categories)
        button_layout.addWidget(self.btn_import)
        
        parent_layout.addWidget(button_container)
    
    # ==================== Helper Styles ====================
    
    def _combobox_style(self, colors):
        """Get combobox style with theme-aware colors"""
        return f"""
            QComboBox {{
                padding: 10px 16px;
                border: 1px solid {colors['border']};
                border-radius: 10px;
                font-size: 10pt;
                min-width: 130px;
                background: {colors['card_bg']};
                color: {colors['text']};
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox:hover {{
                border-color: {colors['border_hover']};
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
        """
    
    def _table_style(self, colors):
        """Get table style with theme-aware colors"""
        is_dark = is_dark_theme()
        
        # Dark theme için alternatif renkler
        if is_dark:
            alt_bg = "#36393f"
            header_bg = "#202225"
            header_text = "#b9bbbe"
            border_color = "#40444b"
            grid_color = "#40444b"
            selection_bg = "#40444b"
            selection_color = "#dcddde"
            hover_bg = "#40444b"
        else:
            alt_bg = "#f8f9fa"
            header_bg = "#f1f3f5"
            header_text = "#495057"
            border_color = "#dee2e6"
            grid_color = "#dee2e6"
            selection_bg = "#e9ecef"
            selection_color = "#212529"
            hover_bg = "#f1f3f5"
        
        return f"""
            QTableWidget {{
                border: none;
                background: {colors['card_bg']};
                gridline-color: {grid_color};
                outline: none;
                font-size: 10pt;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                color: {colors['text']};
            }}
            QTableWidget::item {{
                padding: 10px 14px;
                border: none;
                border-bottom: 1px solid {border_color};
                background: transparent;
                color: {colors['text']};
            }}
            QTableWidget::item:selected {{
                background-color: {selection_bg};
                color: {selection_color};
            }}
            QTableWidget::item:hover:!selected {{
                background-color: {hover_bg};
            }}
            QHeaderView::section {{
                background: {header_bg};
                padding: 10px 14px;
                border: none;
                border-bottom: 1px solid {border_color};
                font-weight: 600;
                color: {header_text};
                font-size: 9pt;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QTableWidget QTableCornerButton::section {{
                background: {header_bg};
                border: none;
                border-bottom: 1px solid {border_color};
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 8px;
                border-radius: 4px;
                margin: 1px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['border']};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors['border_hover']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: transparent;
                height: 8px;
                border-radius: 4px;
                margin: 1px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors['border']};
                border-radius: 4px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {colors['border_hover']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
                width: 0px;
            }}
        """