# ui/categories/category_form_dialog.py
"""
Category Form Dialog - Add/Edit Category
✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QMessageBox, QWidget,
    QTabWidget, QFrame, QScrollArea, QPushButton, QColorDialog,
    QFileDialog, QCheckBox, QGridLayout, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPixmap, QIcon

from ui.categories.category_service import CategoryService
from ui.widgets.modern_button import ModernButton
from utils.translations import tr
from utils.language import lang
from utils.slug_generator import generate_slug
from utils.image_optimizer import ImageOptimizer
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager

import os
from datetime import datetime
from loguru import logger


class CategoryFormDialog(QDialog):
    """Dialog for adding/editing a category - Theme-aware"""
    
    def __init__(self, category_id: int = None, parent=None):
        super().__init__(parent)
        
        self.category_id = category_id if category_id is not None else None
        self.service = CategoryService()
        self.category = None
        self.image_path = ""
        self.selected_color = "#6c5ce7"
        self.selected_icon = "📁"
        
        # Predefined icons
        self.PREDEFINED_ICONS = [
            "📁", "📂", "📊", "📋", "📝", "📚", "📖", "📕", "📘", "📗",
            "🍔", "🍕", "🌮", "🌯", "🍣", "🍱", "🍜", "🍲", "🍳", "☕",
            "🥤", "🧃", "🍺", "🍷", "🍸", "🍹", "🍾", "🧊", "🍿", "🥨",
            "🏠", "🏢", "🏪", "🏬", "🏫", "🏥", "🏦", "🏨", "🏩", "🏪",
            "👕", "👗", "👔", "👖", "👟", "👠", "👒", "🧢", "🧣", "🧤",
            "💄", "💅", "🧴", "🧹", "🧺", "🧻", "🪣", "🪥", "🪒", "🧼",
            "🔧", "🔨", "⚒️", "🛠️", "⛏️", "🔩", "⚙️", "🧰", "🧲", "🔫"
        ]
        
        self.setup_ui()
        self.load_data()
        
        # Language support
        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
        
        # ✅ Connect theme manager for auto refresh
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """✅ Handle theme change - update UI styles"""
        self._apply_theme_styles()
    
    def setup_ui(self):
        """Setup the UI"""
        is_edit = self.category_id is not None
        
        self.setWindowTitle("Add Category" if not is_edit else "Edit Category")
        self.setModal(True)
        self.resize(750, 650)
        self.setMinimumWidth(700)
        
        # Apply theme styles
        self._apply_theme_styles()
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 18)
        
        # Header
        header_layout = QHBoxLayout()
        
        icon = "📁" if not is_edit else "✏️"
        title = "Add New Category" if not is_edit else "Edit Category"
        title_label = QLabel(f"{icon} {title}")
        title_label.setObjectName("headerTitle")
        title_label.setStyleSheet("font-size: 16pt; font-weight: 700;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        if is_edit:
            badge = QLabel(f"ID: #{self.category_id}")
            badge.setObjectName("idBadge")
            badge.setStyleSheet("""
                background: #5865f2;
                color: white;
                padding: 4px 14px;
                border-radius: 12px;
                font-size: 10pt;
                font-weight: 600;
            """)
            header_layout.addWidget(badge)
        
        main_layout.addLayout(header_layout)
        
        # Main content - Tab widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("formTabs")
        self.tabs.setStyleSheet(self._tab_style())
        
        # Tab 1: Basic Info
        self.setup_basic_tab()
        
        # Tab 2: Appearance
        self.setup_appearance_tab()
        
        # Tab 3: Advanced
        self.setup_advanced_tab()
        
        main_layout.addWidget(self.tabs, 1)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("separator")
        separator.setStyleSheet("max-height: 1px;")
        main_layout.addWidget(separator)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # ✅ Remove emoji from cancel button
        self.btn_cancel = ModernButton("Cancel", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("cancel", size=(16, 16))
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        button_layout.addStretch()
        
        # ✅ Remove emoji from save button
        self.btn_save = ModernButton("Save Category", ModernButton.PRIMARY)
        self.btn_save.set_icon("save", size=(16, 16))
        self.btn_save.clicked.connect(self.save)
        button_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
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
            QLabel#headerTitle {{
                color: {colors['text']};
            }}
            QFrame#separator {{
                background-color: {colors['border']};
            }}
            QTabWidget::pane {{
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 12px;
                background: {colors['card_bg']};
            }}
            QTabBar::tab {{
                padding: 8px 16px;
                border: 1px solid {colors['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                background: {colors['card_bg']};
                margin-right: 2px;
                font-weight: 500;
                color: {colors['text']};
            }}
            QTabBar::tab:selected {{
                background: {colors['card_bg']};
                border-bottom: 2px solid #5865f2;
            }}
            QTabBar::tab:hover {{
                background: {colors['bg_hover']};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QFrame {{
                background: transparent;
            }}
            QGroupBox {{
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: {colors['text']};
            }}
        """)
    
    def _tab_style(self):
        """Get tab style - will be applied in _apply_theme_styles"""
        return ""
    
    def setup_basic_tab(self):
        """Setup the basic info tab"""
        tab = QWidget()
        tab.setObjectName("basicTab")
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Scroll area for long form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        content = QWidget()
        content.setStyleSheet(f"background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        
        # Name
        name_layout = QHBoxLayout()
        name_label = QLabel("Category Name *")
        name_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        name_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter category name...")
        self.name_input.textChanged.connect(self.on_name_changed)
        self.name_input.setStyleSheet(self._input_style(colors))
        name_layout.addWidget(self.name_input, 1)
        content_layout.addLayout(name_layout)
        
        # Slug (auto-generated)
        slug_layout = QHBoxLayout()
        slug_label = QLabel("Slug")
        slug_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        slug_layout.addWidget(slug_label)
        
        self.slug_input = QLineEdit()
        self.slug_input.setPlaceholderText("Auto-generated from name")
        self.slug_input.setStyleSheet(self._input_style(colors))
        slug_layout.addWidget(self.slug_input, 1)
        
        # Regenerate slug button - ✅ Remove emoji, use SVG icon
        btn_regenerate = ModernButton("", ModernButton.SECONDARY)
        btn_regenerate.set_icon("refresh", size=(16, 16))
        btn_regenerate.set_compact(True)
        btn_regenerate.setFixedSize(30, 30)
        btn_regenerate.setToolTip("Regenerate slug from name")
        btn_regenerate.clicked.connect(self.regenerate_slug)
        slug_layout.addWidget(btn_regenerate)
        
        content_layout.addLayout(slug_layout)
        
        # Code
        code_layout = QHBoxLayout()
        code_label = QLabel("Category Code")
        code_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        code_layout.addWidget(code_label)
        
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Auto-generated code")
        self.code_input.setStyleSheet(self._input_style(colors))
        code_layout.addWidget(self.code_input, 1)
        content_layout.addLayout(code_layout)
        
        # Parent Category
        parent_layout = QHBoxLayout()
        parent_label = QLabel("Parent Category")
        parent_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        parent_layout.addWidget(parent_label)
        
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("None (Root Category)", None)
        self.parent_combo.setStyleSheet(self._combobox_style(colors))
        parent_layout.addWidget(self.parent_combo, 1)
        content_layout.addLayout(parent_layout)
        
        # Sort Order
        sort_layout = QHBoxLayout()
        sort_label = QLabel("Sort Order")
        sort_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        sort_layout.addWidget(sort_label)
        
        self.sort_input = QSpinBox()
        self.sort_input.setRange(0, 9999)
        self.sort_input.setValue(0)
        self.sort_input.setStyleSheet(self._spinbox_style(colors))
        sort_layout.addWidget(self.sort_input)
        sort_layout.addStretch()
        content_layout.addLayout(sort_layout)
        
        # Description
        desc_layout = QHBoxLayout()
        desc_label = QLabel("Description")
        desc_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        desc_layout.addWidget(desc_label)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Enter category description...")
        self.desc_input.setMaximumHeight(80)
        self.desc_input.setStyleSheet(self._textarea_style(colors))
        desc_layout.addWidget(self.desc_input, 1)
        content_layout.addLayout(desc_layout)
        
        # Status
        status_layout = QHBoxLayout()
        status_label = QLabel("Status")
        status_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        status_layout.addWidget(status_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Active", "Inactive", "Hidden"])
        self.status_combo.setStyleSheet(self._combobox_style(colors))
        status_layout.addWidget(self.status_combo)
        status_layout.addStretch()
        content_layout.addLayout(status_layout)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        self.tabs.addTab(tab, "📋 Basic Info")
    
    def setup_appearance_tab(self):
        """Setup the appearance tab"""
        tab = QWidget()
        tab.setObjectName("appearanceTab")
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Icon
        icon_layout = QHBoxLayout()
        icon_label = QLabel("Icon")
        icon_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        icon_layout.addWidget(icon_label)
        
        self.icon_preview = QLabel("📁")
        self.icon_preview.setStyleSheet(f"""
            font-size: 32px;
            border: 2px solid {colors['border']};
            border-radius: 8px;
            padding: 8px;
            min-width: 50px;
            min-height: 50px;
            background: {colors['bg']};
        """)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self.icon_preview)
        
        # ✅ Remove emoji, use SVG icon
        self.btn_icon = ModernButton("Choose Icon", ModernButton.SECONDARY)
        self.btn_icon.set_icon("emoji_objects", size=(16, 16))
        self.btn_icon.clicked.connect(self.choose_icon)
        icon_layout.addWidget(self.btn_icon)
        icon_layout.addStretch()
        
        layout.addLayout(icon_layout)
        
        # Color
        color_layout = QHBoxLayout()
        color_label = QLabel("Color")
        color_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        color_layout.addWidget(color_label)
        
        self.color_preview = QLabel()
        self.color_preview.setStyleSheet(f"""
            background-color: {self.selected_color};
            border: 2px solid {colors['border']};
            border-radius: 8px;
            min-width: 50px;
            min-height: 50px;
        """)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_layout.addWidget(self.color_preview)
        
        self.color_hex = QLineEdit()
        self.color_hex.setText(self.selected_color)
        self.color_hex.setMaxLength(7)
        self.color_hex.setFixedWidth(100)
        self.color_hex.textChanged.connect(self.on_color_hex_changed)
        self.color_hex.setStyleSheet(self._input_style(colors))
        color_layout.addWidget(self.color_hex)
        
        # ✅ Remove emoji, use SVG icon
        self.btn_color = ModernButton("Choose Color", ModernButton.SECONDARY)
        self.btn_color.set_icon("color_lens", size=(16, 16))
        self.btn_color.clicked.connect(self.choose_color)
        color_layout.addWidget(self.btn_color)
        color_layout.addStretch()
        
        layout.addLayout(color_layout)
        
        # Image
        image_layout = QHBoxLayout()
        image_label = QLabel("Image")
        image_label.setStyleSheet(f"font-weight: 600; min-width: 120px; color: {colors['text']};")
        image_layout.addWidget(image_label)
        
        self.image_input = QLineEdit()
        self.image_input.setReadOnly(True)
        self.image_input.setStyleSheet(self._input_style(colors))
        image_layout.addWidget(self.image_input, 1)
        
        # ✅ Remove emoji, use SVG icon
        self.btn_browse = ModernButton("Browse Image", ModernButton.SECONDARY)
        self.btn_browse.set_icon("folder_open", size=(16, 16))
        self.btn_browse.clicked.connect(self.browse_image)
        image_layout.addWidget(self.btn_browse)
        
        # ✅ Remove emoji, use SVG icon
        self.btn_clear_image = ModernButton("", ModernButton.TERTIARY)
        self.btn_clear_image.set_icon("close", size=(16, 16))
        self.btn_clear_image.set_compact(True)
        self.btn_clear_image.setFixedSize(30, 30)
        self.btn_clear_image.clicked.connect(self.clear_image)
        image_layout.addWidget(self.btn_clear_image)
        
        layout.addLayout(image_layout)
        
        # Image preview
        self.image_preview = QLabel("No image selected")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumHeight(120)
        self.image_preview.setStyleSheet(f"""
            border: 2px dashed {colors['border']};
            border-radius: 8px;
            background: {colors['bg']};
            color: {colors['text_secondary']};
            font-size: 10pt;
        """)
        layout.addWidget(self.image_preview)
        
        layout.addStretch()
        
        self.tabs.addTab(tab, "🎨 Appearance")
    
    def setup_advanced_tab(self):
        """Setup the advanced tab"""
        tab = QWidget()
        tab.setObjectName("advancedTab")
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Notes
        notes_label = QLabel("Notes")
        notes_label.setStyleSheet(f"font-weight: 600; color: {colors['text']};")
        layout.addWidget(notes_label)
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Internal notes about this category...")
        self.notes_input.setMaximumHeight(120)
        self.notes_input.setStyleSheet(self._textarea_style(colors))
        layout.addWidget(self.notes_input)
        
        # System category info
        self.system_info = QLabel()
        self.system_info.setStyleSheet(f"""
            color: {colors['text_secondary']};
            font-size: 9pt;
            padding: 8px;
            background: {colors['bg']};
            border-radius: 4px;
        """)
        self.system_info.setWordWrap(True)
        layout.addWidget(self.system_info)
        
        # Created/Updated info
        info_frame = QFrame()
        info_frame.setStyleSheet(f"background: {colors['bg']}; border-radius: 6px; padding: 8px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(2)
        
        self.created_label = QLabel("Created: --")
        self.created_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 9pt;")
        info_layout.addWidget(self.created_label)
        
        self.updated_label = QLabel("Updated: --")
        self.updated_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 9pt;")
        info_layout.addWidget(self.updated_label)
        
        layout.addWidget(info_frame)
        layout.addStretch()
        
        self.tabs.addTab(tab, "⚙️ Advanced")
    
    def load_data(self):
        """Load category data for editing"""
        # Load parent categories
        self.load_parents()
        
        if self.category_id:
            self.category = self.service.get_category(self.category_id)
            if self.category:
                self.name_input.setText(self.category['name'])
                self.slug_input.setText(self.category['slug'])
                self.code_input.setText(self.category.get('code', ''))
                self.desc_input.setPlainText(self.category.get('description', ''))
                self.notes_input.setPlainText(self.category.get('notes', ''))
                self.sort_input.setValue(self.category.get('sort_order', 0))
                
                # Parent
                parent_id = self.category.get('parent_id')
                if parent_id:
                    idx = self.parent_combo.findData(parent_id)
                    if idx >= 0:
                        self.parent_combo.setCurrentIndex(idx)
                
                # Status
                status = self.category.get('status', 'active')
                status_map = {'active': 0, 'inactive': 1, 'hidden': 2}
                self.status_combo.setCurrentIndex(status_map.get(status, 0))
                
                # Appearance
                self.selected_icon = self.category.get('icon', '📁')
                self.icon_preview.setText(self.selected_icon)
                
                self.selected_color = self.category.get('color', '#6c5ce7')
                is_dark = is_dark_theme()
                self.color_preview.setStyleSheet(f"""
                    background-color: {self.selected_color};
                    border: 2px solid {colors['border']};
                    border-radius: 8px;
                    min-width: 50px;
                    min-height: 50px;
                """)
                self.color_hex.setText(self.selected_color)
                
                self.image_path = self.category.get('image', '')
                if self.image_path:
                    self.image_input.setText(self.image_path)
                    self.update_image_preview()
                
                # Timestamps
                if self.category.get('created_at'):
                    self.created_label.setText(f"Created: {self.category['created_at']}")
                if self.category.get('updated_at'):
                    self.updated_label.setText(f"Updated: {self.category['updated_at']}")
                
                # System info
                if self.category.get('is_system'):
                    self.system_info.setText("⚠️ This is a system category. Some fields may be read-only.")
                    self.system_info.setStyleSheet("""
                        color: #e67e22;
                        font-size: 9pt;
                        padding: 8px;
                        background: #fef9e7;
                        border-radius: 4px;
                    """)
                else:
                    self.system_info.setText("Standard category - all fields editable.")
        
        # Generate initial slug
        if not self.category_id:
            self.regenerate_slug()
    
    def load_parents(self):
        """Load parent categories into combo box"""
        try:
            categories, _ = self.service.get_categories(limit=1000)
            
            self.parent_combo.blockSignals(True)
            self.parent_combo.clear()
            self.parent_combo.addItem("None (Root Category)", None)
            
            # Build hierarchical options
            def add_category(cat, prefix=''):
                # Skip self if editing
                if self.category_id and cat['id'] == self.category_id:
                    return
                
                self.parent_combo.addItem(f"{prefix}{cat['name']}", cat['id'])
                
                # Add children
                children = [c for c in categories if c['parent_id'] == cat['id']]
                children = sorted(children, key=lambda x: (x.get('sort_order', 0), x['name']))
                for child in children:
                    add_category(child, prefix + '  ')
            
            # Get root categories
            roots = [c for c in categories if c['parent_id'] is None]
            roots = sorted(roots, key=lambda x: (x.get('sort_order', 0), x['name']))
            
            for root in roots:
                add_category(root)
            
            self.parent_combo.blockSignals(False)
            
        except Exception as e:
            logger.error(f"Failed to load parents: {e}")
    
    def choose_icon(self):
        """Open icon picker dialog with theme support"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Choose Icon")
        dialog.setModal(True)
        dialog.resize(600, 400)
        
        # Apply theme to icon picker
        self._apply_theme_to_child_dialog(dialog)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        
        colors = get_theme_colors()
        
        label = QLabel("Select an icon:")
        label.setStyleSheet(f"font-weight: 600; color: {colors['text']};")
        layout.addWidget(label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ 
                background: transparent; 
                border: none; 
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
        
        container = QWidget()
        container.setStyleSheet(f"background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(4)
        grid.setContentsMargins(4, 4, 4, 4)
        
        icon_group = QButtonGroup()
        icon_group.setExclusive(True)
        
        btn_style = f"""
            QPushButton {{
                font-size: 18px;
                border: 2px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['bg']};
                color: {colors['text']};
            }}
            QPushButton:hover {{
                background-color: rgba(88, 101, 242, 0.1);
                border-color: #5865f2;
            }}
            QPushButton:checked {{
                background-color: rgba(88, 101, 242, 0.2);
                border-color: #5865f2;
            }}
        """
        
        for idx, icon in enumerate(self.PREDEFINED_ICONS):
            btn = QPushButton(icon)
            btn.setCheckable(True)
            btn.setFixedSize(44, 44)
            btn.setStyleSheet(btn_style)
            if icon == self.selected_icon:
                btn.setChecked(True)
            icon_group.addButton(btn)
            row = idx // 10
            col = idx % 10
            grid.addWidget(btn, row, col)
        
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        
        # Buttons - ✅ Remove emojis, use SVG icons
        btn_layout = QHBoxLayout()
        
        btn_cancel = ModernButton("Cancel", ModernButton.TERTIARY)
        btn_cancel.set_icon("cancel", size=(16, 16))
        btn_cancel.set_compact(True)
        
        btn_ok = ModernButton("Select", ModernButton.PRIMARY)
        btn_ok.set_icon("check", size=(16, 16))
        btn_ok.set_compact(True)
        
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for btn in icon_group.buttons():
                if btn.isChecked():
                    self.selected_icon = btn.text()
                    self.icon_preview.setText(self.selected_icon)
                    break
    
    def _apply_theme_to_child_dialog(self, dialog):
        """Apply theme to child dialog"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QPushButton {{
                background-color: {colors['input_border']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #5865f2;
                color: white;
            }}
            QPushButton:checked {{
                background-color: #5865f2;
                color: white;
                border-color: #5865f2;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QWidget {{
                background-color: {colors['bg']};
                color: {colors['text']};
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
    
    def choose_color(self):
        """Open color picker dialog"""
        color = QColorDialog.getColor(
            QColor(self.selected_color),
            self,
            "Choose Category Color"
        )
        if color.isValid():
            self.selected_color = color.name()
            is_dark = is_dark_theme()
            self.color_preview.setStyleSheet(f"""
                background-color: {self.selected_color};
                border: 2px solid {colors['border']};
                border-radius: 8px;
                min-width: 50px;
                min-height: 50px;
            """)
            self.color_hex.setText(self.selected_color)
    
    def on_color_hex_changed(self, text: str):
        """Handle color hex input change"""
        if text.startswith('#') and len(text) == 7:
            try:
                QColor(text)  # Validate
                self.selected_color = text
                is_dark = is_dark_theme()
                self.color_preview.setStyleSheet(f"""
                    background-color: {self.selected_color};
                    border: 2px solid {colors['border']};
                    border-radius: 8px;
                    min-width: 50px;
                    min-height: 50px;
                """)
            except:
                pass
    
    def browse_image(self):
        """Browse for image file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Category Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        
        if file_path:
            self.image_path = file_path
            self.image_input.setText(file_path)
            self.update_image_preview()
    
    def clear_image(self):
        """Clear the selected image"""
        self.image_path = ""
        self.image_input.clear()
        self.image_preview.setText("No image selected")
        self.image_preview.setPixmap(QPixmap())
    
    def update_image_preview(self):
        """Update the image preview"""
        if self.image_path and os.path.exists(self.image_path):
            try:
                pixmap = QPixmap(self.image_path)
                if not pixmap.isNull():
                    preview_size = self.image_preview.width() - 40
                    if preview_size > 0:
                        scaled = pixmap.scaled(
                            preview_size, preview_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.image_preview.setPixmap(scaled)
                        self.image_preview.setText("")
                        return
            except Exception as e:
                logger.error(f"Failed to load image preview: {e}")
        
        self.image_preview.setText("No image selected")
        self.image_preview.setPixmap(QPixmap())
    
    def on_name_changed(self, text: str):
        """Auto-generate slug from name"""
        if not self.slug_input.text() or self.slug_input.text() == "":
            self.regenerate_slug()
    
    def regenerate_slug(self):
        """Regenerate slug from name"""
        name = self.name_input.text().strip()
        if name:
            self.slug_input.setText(generate_slug(name))
    
    def save(self):
        """Save the category"""
        # Validate
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Category name is required.")
            self.name_input.setFocus()
            return
        
        # Build data
        data = {
            'name': name,
            'slug': self.slug_input.text().strip() or generate_slug(name),
            'description': self.desc_input.toPlainText().strip(),
            'parent_id': self.parent_combo.currentData(),
            'sort_order': self.sort_input.value(),
            'color': self.selected_color,
            'icon': self.selected_icon,
            'image': self.image_path if self.image_path else None,
            'status': self.status_combo.currentText().lower(),
            'code': self.code_input.text().strip() or None,
            'notes': self.notes_input.toPlainText().strip()
        }
        
        try:
            # Normalize image path
            if data['image'] and os.path.exists(data['image']):
                from utils.image_optimizer import ImageOptimizer
                optimized = ImageOptimizer.optimize_image(
                    data['image'],
                    output_size=(200, 200),
                    quality=80
                )
                if optimized:
                    import shutil
                    category_images_dir = os.path.join('database', 'category_images')
                    os.makedirs(category_images_dir, exist_ok=True)
                    
                    dest_filename = f"cat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.basename(optimized)}"
                    dest_path = os.path.join(category_images_dir, dest_filename)
                    shutil.copy2(optimized, dest_path)
                    data['image'] = dest_path
            
            if self.category_id:
                self.service.update_category(self.category_id, data)
                msg = "Category updated successfully!"
            else:
                self.service.create_category(data)
                msg = "Category created successfully!"
            
            QMessageBox.information(self, "Success", msg)
            self.accept()
            
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.error(f"Failed to save category: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save category: {e}")
    
    # ==================== Helper Styles ====================
    
    def _input_style(self, colors):
        """Get input style with theme colors"""
        is_dark = is_dark_theme()
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit:disabled {{
                background: {colors['bg']};
                color: {colors['text_secondary']};
            }}
            QLineEdit::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
        """
    
    def _textarea_style(self, colors):
        """Get textarea style with theme colors"""
        is_dark = is_dark_theme()
        return f"""
            QTextEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
            }}
            QTextEdit::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
        """
    
    def _combobox_style(self, colors):
        """Get combobox style with theme colors"""
        is_dark = is_dark_theme()
        return f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-width: 100px;
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
        """
    
    def _spinbox_style(self, colors):
        """Get spinbox style with theme colors"""
        is_dark = is_dark_theme()
        return f"""
            QSpinBox {{
                padding: 8px 12px;
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-width: 80px;
            }}
            QSpinBox:focus {{
                border-color: #5865f2;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: transparent;
                border: none;
                color: {colors['text']};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {colors['bg_hover']};
                border-radius: 2px;
            }}
        """
    
    def retranslateUi(self):
        """Retranslate UI"""
        is_my = lang.get_current() == "my"
        
        if is_my:
            if self.category_id:
                self.setWindowTitle("အမျိုးအစား ပြင်ဆင်ရန်")
                self.tabs.setTabText(0, "📋 အခြေခံ")
                self.tabs.setTabText(1, "🎨 အသွင်အပြင်")
                self.tabs.setTabText(2, "⚙️ အဆင့်မြင့်")
                # ✅ Remove emoji from button text
                self.btn_save.setText("သိမ်းမည်")
            else:
                self.setWindowTitle("အမျိုးအစားအသစ် ထည့်ရန်")
                self.tabs.setTabText(0, "📋 အခြေခံ")
                self.tabs.setTabText(1, "🎨 အသွင်အပြင်")
                self.tabs.setTabText(2, "⚙️ အဆင့်မြင့်")
                self.btn_save.setText("သိမ်းမည်")
            
            self.btn_cancel.setText("မလုပ်တော့ပါ")
            self.btn_icon.setText("အိုင်ကွန်ရွေးရန်")
            self.btn_color.setText("အရောင်ရွေးရန်")
            self.btn_browse.setText("ပုံရွေးရန်")
            self.btn_clear_image.setText("")  # Icon only
            
            # Update labels
            self.name_input.setPlaceholderText("အမျိုးအစားအမည် ထည့်ပါ...")
            self.slug_input.setPlaceholderText("အလိုအလျောက်ထွက်မည်")
            self.code_input.setPlaceholderText("အလိုအလျောက်ကုဒ်")
            self.desc_input.setPlaceholderText("အမျိုးအစားဖော်ပြချက် ထည့်ပါ...")
            self.notes_input.setPlaceholderText("အတွင်းမှတ်စုများ...")
            
        else:
            if self.category_id:
                self.setWindowTitle("Edit Category")
                self.tabs.setTabText(0, "📋 Basic Info")
                self.tabs.setTabText(1, "🎨 Appearance")
                self.tabs.setTabText(2, "⚙️ Advanced")
                self.btn_save.setText("Save Category")
            else:
                self.setWindowTitle("Add Category")
                self.tabs.setTabText(0, "📋 Basic Info")
                self.tabs.setTabText(1, "🎨 Appearance")
                self.tabs.setTabText(2, "⚙️ Advanced")
                self.btn_save.setText("Save Category")
            
            self.btn_cancel.setText("Cancel")
            self.btn_icon.setText("Choose Icon")
            self.btn_color.setText("Choose Color")
            self.btn_browse.setText("Browse Image")
            self.btn_clear_image.setText("")  # Icon only
            
            # Update labels
            self.name_input.setPlaceholderText("Enter category name...")
            self.slug_input.setPlaceholderText("Auto-generated from name")
            self.code_input.setPlaceholderText("Auto-generated code")
            self.desc_input.setPlaceholderText("Enter category description...")
            self.notes_input.setPlaceholderText("Internal notes about this category...")
        
        # Update parent combo placeholder
        self.parent_combo.setItemText(0, "None (Root Category)" if not is_my else "မိဘမရှိ (အမြစ်အမျိုးအစား)")
        
        # Update status combo
        if is_my:
            self.status_combo.setItemText(0, "အသက်ဝင်")
            self.status_combo.setItemText(1, "မလှုပ်ရှား")
            self.status_combo.setItemText(2, "ဝှက်ထား")
        else:
            self.status_combo.setItemText(0, "Active")
            self.status_combo.setItemText(1, "Inactive")
            self.status_combo.setItemText(2, "Hidden")
    
    def closeEvent(self, event):
        """Handle close event"""
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        event.accept()
