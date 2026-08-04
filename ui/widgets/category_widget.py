# ui/widgets/category_widget.py
"""
Category Widgets for displaying and managing categories in various UI components.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QMenu, QMessageBox, QApplication, QLineEdit,
    QListWidget, QListWidgetItem, QComboBox, QScrollArea,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPixmap, QPainter, QBrush, QPen, QFont, QAction

from loguru import logger

from ui.categories.category_service import CategoryService
from ui.widgets.modern_button import ModernButton
from ui.widgets.search_widget import ModernSearchWidget


# ============================================================================
# CATEGORY BADGE
# ============================================================================

class CategoryBadge(QLabel):
    """Small badge for displaying category name with color"""
    
    def __init__(self, category_name: str, color: str = "#6c5ce7", 
                 icon: str = None, parent=None):
        super().__init__(category_name, parent)
        self.category_name = category_name
        self.color = color
        self.icon = icon
        self.setup_ui()
    
    def setup_ui(self):
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_text = f"{self.icon} " if self.icon else ""
        self.setText(f"{icon_text}{self.category_name}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color}20;
                color: {self.color};
                border: 1px solid {self.color}40;
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 8pt;
                font-weight: 500;
            }}
        """)
        self.setFixedHeight(24)
        self.setMinimumWidth(40)
    
    def set_color(self, color: str):
        """Update badge color"""
        self.color = color
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color}20;
                color: {self.color};
                border: 1px solid {self.color}40;
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 8pt;
                font-weight: 500;
            }}
        """)


# ============================================================================
# CATEGORY CHIP
# ============================================================================

class CategoryChip(QFrame):
    """Chip-style widget for category selection"""
    
    clicked = pyqtSignal(int)
    removed = pyqtSignal(int)
    
    def __init__(self, category_id: int, name: str, color: str = "#6c5ce7", 
                 icon: str = "📁", removable: bool = False, parent=None):
        super().__init__(parent)
        self.category_id = category_id
        self.name = name
        self.color = color
        self.icon = icon
        self.removable = removable
        self._is_selected = False
        
        self.setup_ui()
    
    def setup_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color}20;
                border: 1px solid {self.color}40;
                border-radius: 14px;
                padding: 2px 2px;
            }}
            QFrame:hover {{
                background-color: {self.color}30;
                border-color: {self.color}60;
            }}
            QFrame[selected="true"] {{
                background-color: {self.color}40;
                border-color: {self.color};
            }}
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # Icon
        self.icon_label = QLabel(self.icon)
        self.icon_label.setStyleSheet("font-size: 12px; background: transparent; border: none;")
        layout.addWidget(self.icon_label)
        
        # Name
        self.name_label = QLabel(self.name)
        self.name_label.setStyleSheet(f"""
            color: {self.color};
            font-size: 9pt;
            font-weight: 500;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.name_label)
        
        # Remove button
        if self.removable:
            self.remove_btn = QLabel("✕")
            self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.remove_btn.setStyleSheet("""
                color: #6c757d;
                font-size: 10px;
                background: transparent;
                border: none;
                padding: 0px 2px;
            """)
            self.remove_btn.mousePressEvent = self._on_remove_clicked
            layout.addWidget(self.remove_btn)
        
        self.setLayout(layout)
    
    def _on_remove_clicked(self, event):
        self.removed.emit(self.category_id)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.category_id)
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """Set selected state"""
        self._is_selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


# ============================================================================
# CATEGORY SELECTOR WIDGET
# ============================================================================

class CategorySelectorWidget(QWidget):
    """Widget for selecting categories with search and chips"""
    
    category_selected = pyqtSignal(int)
    category_removed = pyqtSignal(int)
    categories_changed = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = CategoryService()
        self.selected_categories = []
        self.all_categories = []
        self.max_selection = None
        
        self.setup_ui()
        self.load_categories()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search bar with modern widget
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        
        self.search_input = ModernSearchWidget("Search categories...")
        self.search_input.search_changed.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input, 1)
        
        self.btn_add = ModernButton("➕ Add", ModernButton.PRIMARY)
        self.btn_add.set_compact(True)
        self.btn_add.clicked.connect(self._show_category_menu)
        search_layout.addWidget(self.btn_add)
        
        main_layout.addLayout(search_layout)
        
        # Selected chips container
        self.chips_container = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 4, 0, 4)
        self.chips_layout.setSpacing(6)
        self.chips_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.chips_container.setVisible(False)
        
        main_layout.addWidget(self.chips_container)
        
        # Search results
        self.results_list = QListWidget()
        self.results_list.setVisible(False)
        self.results_list.setMaximumHeight(150)
        self.results_list.itemClicked.connect(self._on_result_clicked)
        self.results_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 4px;
                background: white;
            }
            QListWidget::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #5865f2;
                color: white;
            }
        """)
        main_layout.addWidget(self.results_list)
        
        self.setLayout(main_layout)
    
    def load_categories(self):
        """Load categories from database"""
        try:
            self.all_categories, _ = self.service.get_categories(status='active', limit=1000)
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            self.all_categories = []
    
    def _on_search_changed(self, text: str):
        """Handle search text change"""
        if not text.strip():
            self.results_list.setVisible(False)
            return
        
        # Filter categories
        search_text = text.lower().strip()
        results = []
        selected_ids = [c['id'] for c in self.selected_categories]
        
        for cat in self.all_categories:
            if cat['id'] in selected_ids:
                continue
            if search_text in cat['name'].lower():
                results.append(cat)
        
        # Show results
        self.results_list.clear()
        for cat in results[:10]:
            item = QListWidgetItem(f"{cat.get('icon', '📁')} {cat['name']}")
            item.setData(Qt.ItemDataRole.UserRole, cat['id'])
            self.results_list.addItem(item)
        
        self.results_list.setVisible(len(results) > 0)
    
    def _on_result_clicked(self, item):
        """Handle category selection from results"""
        cat_id = item.data(Qt.ItemDataRole.UserRole)
        self.add_category(cat_id)
        self.search_input.clear_search()
        self.results_list.setVisible(False)
    
    def _show_category_menu(self):
        """Show category selection menu"""
        if self.max_selection and len(self.selected_categories) >= self.max_selection:
            QMessageBox.information(
                self, 
                "Maximum Selection", 
                f"You can select up to {self.max_selection} categories."
            )
            return
        
        menu = QMenu(self)
        
        # Show all available categories
        selected_ids = [c['id'] for c in self.selected_categories]
        available = [c for c in self.all_categories if c['id'] not in selected_ids]
        
        if not available:
            action = QAction("No categories available", self)
            action.setEnabled(False)
            menu.addAction(action)
        else:
            for cat in available[:20]:
                action = QAction(f"{cat.get('icon', '📁')} {cat['name']}", self)
                action.setData(cat['id'])
                action.triggered.connect(lambda checked, cid=cat['id']: self.add_category(cid))
                menu.addAction(action)
        
        menu.exec(self.btn_add.mapToGlobal(self.btn_add.rect().bottomLeft()))
    
    def add_category(self, category_id: int):
        """Add a category to selection"""
        if category_id in [c['id'] for c in self.selected_categories]:
            return
        
        if self.max_selection and len(self.selected_categories) >= self.max_selection:
            QMessageBox.information(
                self, 
                "Maximum Selection", 
                f"You can select up to {self.max_selection} categories."
            )
            return
        
        cat = self.service.get_category(category_id)
        if not cat:
            return
        
        self.selected_categories.append(cat)
        self._update_chips()
        self.categories_changed.emit(self.selected_categories)
        self.category_selected.emit(category_id)
    
    def remove_category(self, category_id: int):
        """Remove a category from selection"""
        self.selected_categories = [c for c in self.selected_categories if c['id'] != category_id]
        self._update_chips()
        self.categories_changed.emit(self.selected_categories)
        self.category_removed.emit(category_id)
    
    def _update_chips(self):
        """Update chips display"""
        # Clear existing chips
        for i in reversed(range(self.chips_layout.count())):
            widget = self.chips_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Add new chips
        for cat in self.selected_categories:
            chip = CategoryChip(
                cat['id'],
                cat['name'],
                cat.get('color', '#6c5ce7'),
                cat.get('icon', '📁'),
                removable=True
            )
            chip.clicked.connect(self._on_chip_clicked)
            chip.removed.connect(self.remove_category)
            self.chips_layout.addWidget(chip)
        
        self.chips_layout.addStretch()
        self.chips_container.setVisible(len(self.selected_categories) > 0)
    
    def _on_chip_clicked(self, category_id: int):
        """Handle chip click"""
        pass
    
    def set_selected_categories(self, category_ids: list):
        """Set selected categories by IDs"""
        self.selected_categories = []
        for cat_id in category_ids:
            cat = self.service.get_category(cat_id)
            if cat:
                self.selected_categories.append(cat)
        self._update_chips()
        self.categories_changed.emit(self.selected_categories)
    
    def get_selected_ids(self) -> list:
        """Get selected category IDs"""
        return [c['id'] for c in self.selected_categories]
    
    def get_selected_names(self) -> list:
        """Get selected category names"""
        return [c['name'] for c in self.selected_categories]
    
    def set_max_selection(self, max_count: int):
        """Set maximum number of categories that can be selected"""
        self.max_selection = max_count
    
    def clear_selection(self):
        """Clear all selected categories"""
        self.selected_categories = []
        self._update_chips()
        self.categories_changed.emit([])


# ============================================================================
# CATEGORY DROPDOWN
# ============================================================================

class CategoryDropDown(QComboBox):
    """Category dropdown with hierarchy support"""
    
    category_selected = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = CategoryService()
        self.category_map = {}
        self._loading = False
        
        self.setup_ui()
        self.load_categories()
    
    def setup_ui(self):
        self.setStyleSheet("""
            QComboBox {
                padding: 6px 12px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 10pt;
                background: white;
                min-height: 32px;
            }
            QComboBox:focus {
                border-color: #5865f2;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #5865f2;
                selection-color: white;
            }
        """)
        
        self.currentIndexChanged.connect(self._on_selection_changed)
    
    def load_categories(self):
        """Load categories into dropdown"""
        if self._loading:
            return
        
        self._loading = True
        self.clear()
        self.category_map = {}
        
        self.addItem("None", None)
        
        try:
            options = self.service.get_category_options()
            for opt in options:
                prefix = "  " * opt.get('level', 0)
                self.addItem(f"{prefix}{opt['name']}", opt['id'])
                self.category_map[opt['id']] = opt
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
        
        self._loading = False
    
    def _on_selection_changed(self, index):
        """Handle selection change"""
        if self._loading:
            return
        cat_id = self.currentData()
        if cat_id:
            self.category_selected.emit(cat_id)
    
    def set_selected_category(self, category_id: int):
        """Set selected category by ID"""
        for i in range(self.count()):
            if self.itemData(i) == category_id:
                self.setCurrentIndex(i)
                return
    
    def get_selected_id(self) -> int:
        """Get selected category ID"""
        return self.currentData()
    
    def refresh(self):
        """Refresh categories"""
        self.load_categories()


# ============================================================================
# CATEGORY TREE WIDGET
# ============================================================================

class CategoryTreeWidget(QWidget):
    """Widget for displaying category hierarchy tree"""
    
    category_selected = pyqtSignal(int)
    category_expanded = pyqtSignal(int)
    category_collapsed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = CategoryService()
        self.tree_data = []
        self.node_widgets = {}
        self.expanded_nodes = set()
        
        self.setup_ui()
        self.load_tree()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
                padding: 6px 12px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("📂 Categories")
        title.setStyleSheet("font-weight: 600; font-size: 10pt;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.btn_refresh = ModernButton("🔄", ModernButton.TERTIARY)
        self.btn_refresh.set_compact(True)
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.clicked.connect(self.load_tree)
        header_layout.addWidget(self.btn_refresh)
        
        layout.addWidget(header)
        
        # Scroll area
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        self.tree_container = QWidget()
        self.tree_layout = QVBoxLayout(self.tree_container)
        self.tree_layout.setContentsMargins(4, 4, 4, 4)
        self.tree_layout.setSpacing(2)
        self.tree_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self.tree_container)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
    
    def load_tree(self):
        """Load category tree"""
        # Clear existing
        self.node_widgets = {}
        for i in reversed(range(self.tree_layout.count())):
            widget = self.tree_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        try:
            tree = self.service.get_category_tree()
            self.tree_data = tree
            
            if not tree:
                empty_label = QLabel("No categories found")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setStyleSheet("color: #6c757d; padding: 20px;")
                self.tree_layout.addWidget(empty_label)
                return
            
            for node in tree:
                self._add_tree_node(self.tree_layout, node)
            
        except Exception as e:
            logger.error(f"Failed to load category tree: {e}")
            error_label = QLabel(f"Error loading categories: {e}")
            error_label.setStyleSheet("color: #dc3545; padding: 10px;")
            self.tree_layout.addWidget(error_label)
    
    def _add_tree_node(self, parent_layout, node, level=0):
        """Add a tree node recursively"""
        # Node widget
        node_widget = QFrame()
        node_widget.setStyleSheet("""
            QFrame {
                border-radius: 4px;
                padding: 2px;
            }
            QFrame:hover {
                background-color: #f0f0f0;
            }
        """)
        node_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        
        node_layout = QHBoxLayout(node_widget)
        node_layout.setContentsMargins(level * 20 + 8, 4, 8, 4)
        node_layout.setSpacing(6)
        
        # Expand/collapse button
        has_children = len(node.get('children', [])) > 0
        if has_children:
            expand_btn = QPushButton("▾")
            expand_btn.setFixedSize(18, 18)
            expand_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 10px;
                    color: #6c757d;
                }
                QPushButton:hover {
                    color: #212529;
                }
            """)
            expand_btn.clicked.connect(lambda checked, n=node: self._toggle_node(n))
            node_layout.addWidget(expand_btn)
            node_widget.expand_btn = expand_btn
        else:
            spacer = QWidget()
            spacer.setFixedSize(18, 18)
            node_layout.addWidget(spacer)
        
        # Icon
        icon_label = QLabel(node.get('icon', '📁'))
        icon_label.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        node_layout.addWidget(icon_label)
        
        # Name with color
        name_label = QLabel(node['name'])
        color = node.get('color', '#6c5ce7')
        name_label.setStyleSheet(f"""
            color: {color};
            font-weight: 500;
            font-size: 10pt;
            background: transparent;
            border: none;
        """)
        node_layout.addWidget(name_label)
        
        # Product count
        if node.get('product_count', 0) > 0:
            count_label = QLabel(f"({node['product_count']})")
            count_label.setStyleSheet("""
                color: #6c757d;
                font-size: 8pt;
                background: transparent;
                border: none;
            """)
            node_layout.addWidget(count_label)
        
        node_layout.addStretch()
        
        # Click to select
        node_widget.mousePressEvent = lambda event, nid=node['id']: self.category_selected.emit(nid)
        
        parent_layout.addWidget(node_widget)
        self.node_widgets[node['id']] = node_widget
        
        # Children container
        if has_children:
            children_container = QWidget()
            children_layout = QVBoxLayout(children_container)
            children_layout.setContentsMargins(0, 0, 0, 0)
            children_layout.setSpacing(2)
            children_container.setVisible(False)
            
            for child in node['children']:
                self._add_tree_node(children_layout, child, level + 1)
            
            parent_layout.addWidget(children_container)
            node_widget.children_container = children_container
    
    def _toggle_node(self, node):
        """Toggle node expansion"""
        node_widget = self.node_widgets.get(node['id'])
        if not node_widget or not hasattr(node_widget, 'children_container'):
            return
        
        container = node_widget.children_container
        is_visible = container.isVisible()
        container.setVisible(not is_visible)
        
        # Update button
        if hasattr(node_widget, 'expand_btn'):
            node_widget.expand_btn.setText("▸" if is_visible else "▾")
        
        if not is_visible:
            self.category_expanded.emit(node['id'])
        else:
            self.category_collapsed.emit(node['id'])
    
    def expand_all(self):
        """Expand all nodes"""
        for node_id, widget in self.node_widgets.items():
            if hasattr(widget, 'children_container'):
                widget.children_container.setVisible(True)
                if hasattr(widget, 'expand_btn'):
                    widget.expand_btn.setText("▾")
        self.expanded_nodes = set(self.node_widgets.keys())
    
    def collapse_all(self):
        """Collapse all nodes"""
        for node_id, widget in self.node_widgets.items():
            if hasattr(widget, 'children_container'):
                widget.children_container.setVisible(False)
                if hasattr(widget, 'expand_btn'):
                    widget.expand_btn.setText("▸")
        self.expanded_nodes.clear()


# ============================================================================
# CATEGORY HIERARCHY WIDGET
# ============================================================================

class CategoryHierarchyWidget(QWidget):
    """Widget for displaying category hierarchy as breadcrumbs"""
    
    category_selected = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = CategoryService()
        self.current_category_id = None
        self.breadcrumbs = []
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.breadcrumb_layout = QHBoxLayout()
        self.breadcrumb_layout.setSpacing(4)
        self.breadcrumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(self.breadcrumb_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_category(self, category_id: int):
        """Set current category and update breadcrumbs"""
        self.current_category_id = category_id
        self._update_breadcrumbs()
    
    def _update_breadcrumbs(self):
        """Update breadcrumb display"""
        # Clear existing
        for i in reversed(range(self.breadcrumb_layout.count())):
            widget = self.breadcrumb_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        if not self.current_category_id:
            return
        
        # Build hierarchy
        hierarchy = []
        current_id = self.current_category_id
        
        while current_id:
            cat = self.service.get_category(current_id)
            if not cat:
                break
            hierarchy.insert(0, cat)
            current_id = cat.get('parent_id')
        
        self.breadcrumbs = hierarchy
        
        # Create breadcrumb items
        for i, cat in enumerate(hierarchy):
            # Breadcrumb item
            item = QPushButton(f"{cat.get('icon', '📁')} {cat['name']}")
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {cat.get('color', '#6c5ce7')};
                    font-size: 9pt;
                    font-weight: 500;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{
                    background-color: #f0f0f0;
                    border-radius: 4px;
                }}
                QPushButton:last {{
                    font-weight: 700;
                }}
            """)
            item.clicked.connect(lambda checked, cid=cat['id']: self.category_selected.emit(cid))
            self.breadcrumb_layout.addWidget(item)
            
            # Separator
            if i < len(hierarchy) - 1:
                sep = QLabel("›")
                sep.setStyleSheet("color: #6c757d; font-size: 10pt;")
                self.breadcrumb_layout.addWidget(sep)


# ============================================================================
# CATEGORY FILTER WIDGET
# ============================================================================

class CategoryFilterWidget(QWidget):
    """Widget for filtering categories"""
    
    filter_changed = pyqtSignal(str, str)  # status, parent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = CategoryService()
        
        self.setup_ui()
        self.load_filters()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Status filter
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active", "Inactive", "Hidden"])
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)
        self.status_filter.setStyleSheet("""
            QComboBox {
                padding: 4px 10px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 9pt;
                min-width: 100px;
            }
        """)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.status_filter)
        
        # Parent filter
        self.parent_filter = QComboBox()
        self.parent_filter.addItem("All Parents")
        self.parent_filter.currentTextChanged.connect(self._on_filter_changed)
        self.parent_filter.setStyleSheet("""
            QComboBox {
                padding: 4px 10px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 9pt;
                min-width: 130px;
            }
        """)
        layout.addWidget(QLabel("Parent:"))
        layout.addWidget(self.parent_filter)
        
        layout.addStretch()
        
        self.setLayout(layout)
    
    def load_filters(self):
        """Load parent filter options"""
        try:
            categories, _ = self.service.get_categories(limit=1000)
            
            self.parent_filter.blockSignals(True)
            current = self.parent_filter.currentText()
            self.parent_filter.clear()
            self.parent_filter.addItem("All Parents")
            self.parent_filter.addItem("No Parent")
            
            cat_names = sorted(set(c['name'] for c in categories if c['name']))
            for name in cat_names:
                self.parent_filter.addItem(name)
            
            idx = self.parent_filter.findText(current)
            if idx >= 0:
                self.parent_filter.setCurrentIndex(idx)
            else:
                self.parent_filter.setCurrentIndex(0)
            
            self.parent_filter.blockSignals(False)
        except Exception as e:
            logger.error(f"Failed to load parent filter: {e}")
    
    def _on_filter_changed(self):
        status = self.status_filter.currentText().lower()
        parent = self.parent_filter.currentText()
        if parent == "All Parents":
            parent = None
        elif parent == "No Parent":
            parent = "none"
        self.filter_changed.emit(status, parent)
    
    def get_filters(self) -> dict:
        """Get current filter values"""
        return {
            'status': self.status_filter.currentText().lower(),
            'parent': self.parent_filter.currentText()
        }
    
    def reset_filters(self):
        """Reset all filters to default"""
        self.status_filter.setCurrentIndex(0)
        self.parent_filter.setCurrentIndex(0)


# ============================================================================
# CATEGORY INFO WIDGET
# ============================================================================

class CategoryInfoWidget(QWidget):
    """Widget for displaying category information"""
    
    def __init__(self, category_id: int = None, parent=None):
        super().__init__(parent)
        self.service = CategoryService()
        self.category_id = category_id
        self.category = None
        
        self.setup_ui()
        if category_id:
            self.load_category(category_id)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header with icon and name
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setSpacing(12)
        
        self.icon_label = QLabel("📁")
        self.icon_label.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(self.icon_label)
        
        name_layout = QVBoxLayout()
        name_layout.setSpacing(2)
        
        self.name_label = QLabel("Category Name")
        self.name_label.setStyleSheet("font-size: 14pt; font-weight: 700;")
        name_layout.addWidget(self.name_label)
        
        self.slug_label = QLabel("slug")
        self.slug_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        name_layout.addWidget(self.slug_label)
        
        header_layout.addLayout(name_layout)
        header_layout.addStretch()
        
        self.status_badge = QLabel("Active")
        self.status_badge.setStyleSheet("""
            QLabel {
                background: #27ae60;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: 500;
            }
        """)
        header_layout.addWidget(self.status_badge)
        
        layout.addWidget(self.header_frame)
        
        # Details
        details_frame = QFrame()
        details_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setSpacing(6)
        
        # Description
        self.desc_label = QLabel("No description")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #495057;")
        details_layout.addWidget(self.desc_label)
        
        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        self.products_label = QLabel("📦 Products: 0")
        self.products_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        stats_layout.addWidget(self.products_label)
        
        self.children_label = QLabel("📂 Children: 0")
        self.children_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        stats_layout.addWidget(self.children_label)
        
        stats_layout.addStretch()
        details_layout.addLayout(stats_layout)
        
        # Parent
        parent_layout = QHBoxLayout()
        parent_layout.setSpacing(6)
        parent_label = QLabel("Parent:")
        parent_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        parent_layout.addWidget(parent_label)
        
        self.parent_label = QLabel("None")
        self.parent_label.setStyleSheet("color: #495057; font-size: 9pt;")
        parent_layout.addWidget(self.parent_label)
        parent_layout.addStretch()
        details_layout.addLayout(parent_layout)
        
        # Color
        color_layout = QHBoxLayout()
        color_layout.setSpacing(6)
        color_label = QLabel("Color:")
        color_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        color_layout.addWidget(color_label)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(16, 16)
        self.color_preview.setStyleSheet("border-radius: 8px;")
        color_layout.addWidget(self.color_preview)
        
        self.color_hex_label = QLabel("#6c5ce7")
        self.color_hex_label.setStyleSheet("color: #495057; font-size: 9pt;")
        color_layout.addWidget(self.color_hex_label)
        color_layout.addStretch()
        details_layout.addLayout(color_layout)
        
        layout.addWidget(details_frame)
        
        self.setLayout(layout)
    
    def load_category(self, category_id: int):
        """Load category data"""
        self.category_id = category_id
        self.category = self.service.get_category(category_id)
        
        if not self.category:
            self.name_label.setText("Category not found")
            return
        
        # Update UI
        self.icon_label.setText(self.category.get('icon', '📁'))
        self.name_label.setText(self.category['name'])
        self.slug_label.setText(f"slug: {self.category.get('slug', '')}")
        
        # Status
        status = self.category.get('status', 'active')
        status_colors = {
            'active': '#27ae60',
            'inactive': '#dc3545',
            'hidden': '#6c757d'
        }
        self.status_badge.setText(status.capitalize())
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background: {status_colors.get(status, '#6c757d')};
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: 500;
            }}
        """)
        
        # Description
        self.desc_label.setText(self.category.get('description', 'No description'))
        
        # Products
        self.products_label.setText(f"📦 Products: {self.category.get('product_count', 0)}")
        
        # Children (would need to count children)
        # For now, just show 0
        self.children_label.setText("📂 Children: 0")
        
        # Parent
        parent_name = self.category.get('parent_name')
        self.parent_label.setText(parent_name if parent_name else "None")
        
        # Color
        color = self.category.get('color', '#6c5ce7')
        self.color_preview.setStyleSheet(f"border-radius: 8px; background-color: {color};")
        self.color_hex_label.setText(color)