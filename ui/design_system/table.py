# ui/design_system/table.py
"""
Modern Table component with consistent styling, sorting, and selection
"""

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QVBoxLayout,
    QLabel, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSortFilterProxyModel
from PyQt6.QtGui import QColor, QFont
from ui.design_system.theme import get_theme, get_theme_colors, is_dark_theme

class ModernTable(QTableWidget):
    """
    Modern table with consistent styling, sorting, and selection behavior
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._setup_behavior()
        
        # Track selection
        self._selected_row = -1
        self._selected_rows = []
    
    def _setup_style(self):
        """Apply theme-aware styling"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        theme = get_theme()
        
        if is_dark:
            bg = "#2f3136"
            alt_bg = "#36393f"
            header_bg = "#202225"
            header_text = "#b9bbbe"
            border = "#40444b"
            selection_bg = "#40444b"
            selection_color = "#dcddde"
            grid_color = "#40444b"
            text_color = "#dcddde"
            hover_bg = "#40444b"
        else:
            bg = "#ffffff"
            alt_bg = "#f8f9fa"
            header_bg = "#f8f9fa"
            header_text = "#2c3e50"
            border = "#dee2e6"
            selection_bg = "#e9ecef"
            selection_color = "#212529"
            grid_color = "#dee2e6"
            text_color = "#212529"
            hover_bg = "#f1f3f5"
        
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg};
                alternate-background-color: {alt_bg};
                gridline-color: {grid_color};
                border: 1px solid {border};
                border-radius: {theme.radius.table}px;
                color: {text_color};
                font-size: {theme.typography.size_medium}pt;
                font-family: {theme.typography.font_family};
                outline: none;
                spacing: 0px;
            }}
            QTableWidget::item {{
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid {border};
                color: {text_color};
                background: transparent;
            }}
            QTableWidget::item:selected {{
                background-color: {selection_bg};
                color: {selection_color};
            }}
            QTableWidget::item:hover:!selected {{
                background-color: {hover_bg};
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid {border};
                font-weight: {theme.typography.weight_semibold};
                font-size: {theme.typography.size_small}pt;
                text-transform: uppercase;
                letter-spacing: 0.3px;
                font-family: {theme.typography.font_family};
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QTableWidget QTableCornerButton::section {{
                background-color: {header_bg};
                border: none;
                border-bottom: 1px solid {border};
            }}
            QScrollBar:vertical {{
                background: {colors.scrollbar_bg if not is_dark else colors.bg};
                width: 8px;
                border-radius: 4px;
                margin: 1px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors.scrollbar_handle};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors.scrollbar_handle_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {colors.scrollbar_bg if not is_dark else colors.bg};
                height: 8px;
                border-radius: 4px;
                margin: 1px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors.scrollbar_handle};
                border-radius: 4px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {colors.scrollbar_handle_hover};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
                width: 0px;
            }}
        """)
    
    def _setup_behavior(self):
        """Setup table behavior"""
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setWordWrap(True)
        
        # Row height
        self.verticalHeader().setDefaultSectionSize(44)
        self.verticalHeader().setVisible(False)
        
        # Selection tracking
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _on_selection_changed(self):
        """Track selection changes"""
        self._selected_rows = sorted(set(index.row() for index in self.selectedIndexes()))
        self._selected_row = self._selected_rows[0] if self._selected_rows else -1
    
    def get_selected_rows(self) -> list:
        """Get list of selected row indices"""
        return self._selected_rows
    
    def get_selected_row(self) -> int:
        """Get the first selected row index"""
        return self._selected_row
    
    def get_selected_item(self, column: int = 0, row: int = None):
        """Get the selected item in a specific column"""
        if row is None:
            row = self._selected_row
        if row >= 0:
            return self.item(row, column)
        return None
    
    def get_selected_value(self, column: int = 0, row: int = None) -> str:
        """Get the text value of the selected item in a specific column"""
        item = self.get_selected_item(column, row)
        return item.text() if item else ""
    
    def get_selected_ids(self, column: int = 0) -> list:
        """Get IDs from selected rows in a specific column"""
        ids = []
        for row in self._selected_rows:
            item = self.item(row, column)
            if item:
                try:
                    ids.append(int(item.text()))
                except ValueError:
                    ids.append(item.text())
        return ids
    
    def select_row(self, row: int):
        """Select a specific row"""
        if 0 <= row < self.rowCount():
            self.selectRow(row)
            self._selected_row = row
    
    def clear_selection(self):
        """Clear all selections"""
        self.clearSelection()
        self._selected_rows = []
        self._selected_row = -1
    
    def set_loading(self, loading: bool):
        """Show/hide loading state"""
        self.setEnabled(not loading)
        # Could add a loading indicator here
    
    def set_empty_message(self, message: str):
        """Show empty state message"""
        # This would be implemented with a overlay widget
        pass
    
    def resize_columns_to_contents(self):
        """Resize all columns to fit contents"""
        for i in range(self.columnCount()):
            self.resizeColumnToContents(i)
    
    def retranslate_headers(self, headers: list):
        """Update column headers with new translations"""
        for i, header in enumerate(headers):
            if i < self.columnCount():
                self.setHorizontalHeaderItem(i, QTableWidgetItem(header))
    
    def update_theme(self):
        """Update theme when theme changes"""
        self._setup_style()

class ModernTableContainer(QWidget):
    """Container widget for table with header and optional controls"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header with title and actions
        self.header_layout = QVBoxLayout()
        self.header_layout.setSpacing(4)
        layout.addLayout(self.header_layout)
        
        # Title
        self.title_label = QLabel()
        self.title_label.setStyleSheet("""
            font-size: 12pt;
            font-weight: 600;
            padding: 0px 4px;
        """)
        self.header_layout.addWidget(self.title_label)
        
        # Table
        self.table = ModernTable()
        layout.addWidget(self.table)
    
    def set_title(self, title: str):
        """Set table title"""
        self.title_label.setText(title)
    
    def get_table(self) -> ModernTable:
        """Get the table widget"""
        return self.table
    
    def update_theme(self):
        """Update theme for all children"""
        self.table.update_theme()
