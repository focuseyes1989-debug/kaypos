# ui/products_page/product_form_ui_panels.py
"""
Panel builders for ProductFormDialog - Left and Right panels
"""

from PyQt6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget,
    QGridLayout, QFrame, QTableWidget, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ui.widgets.modern_button import ModernButton
from ui.products_page.product_form_widgets import InfoLabel
from ui.products_page.product_form_ui_base import ProductFormUIBase
from ui.products_page.product_form_ui_styles import ProductFormUIStyles
from ui.themes.theme_manager import get_theme_colors, is_dark_theme


class ProductFormUIPanels(ProductFormUIBase):
    """Panel builder methods for ProductFormDialog"""
    
    def _setup_left_panel(self, dialog, colors):
        """Setup the left panel with form fields"""
        is_dark = is_dark_theme()
        
        left_panel = QWidget()
        left_panel.setObjectName("left_panel")
        left_panel.setStyleSheet(ProductFormUIStyles.get_left_panel_style(colors))
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(4)
        
        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)
        
        row = 0
        
        # Row 0: Product Name
        row = self._add_name_row(dialog, grid, row, colors)
        
        # Row 1: Category
        row = self._add_category_row(dialog, grid, row, colors)
        
        # Row 2: Barcode
        row = self._add_barcode_row(dialog, grid, row, colors)
        
        # Row 3: Sold By
        row = self._add_sold_by_row(dialog, grid, row, colors)
        
        # Row 4: Price
        row = self._add_price_row(dialog, grid, row, colors)
        
        # Row 5: Low Stock Alert
        row = self._add_low_stock_row(dialog, grid, row, colors)

        # Row 6: Variants
        row = self._add_variants_row(dialog, grid, row, colors)
        
        # Row 7: Description
        row = self._add_description_row(dialog, grid, row, colors)
        
        # Row 8: Product Image
        row = self._add_image_row(dialog, grid, row, colors)
        
        # Row 8: Info label
        dialog.info_label = InfoLabel("Stock notes and information")
        dialog.info_label.setStyleSheet(ProductFormUIStyles.get_info_label_style(colors, is_dark))
        grid.addWidget(QLabel(""), row, 0)
        grid.addWidget(dialog.info_label, row, 1)
        row += 1
        
        # Row 9: Language selection
        row = self._add_language_row(dialog, grid, row, colors)
        
        left_layout.addLayout(grid)
        return left_panel
    
    def _add_name_row(self, dialog, grid, row, colors):
        """Add product name row"""
        dialog.label_name = self._create_label_with_icon("label.svg", "Product Name", colors)
        
        name_widget = QWidget()
        name_layout = QHBoxLayout(name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(4)
        
        dialog.name_input = self._create_lineedit("Enter product name...", colors)
        name_layout.addWidget(dialog.name_input)
        
        dialog.btn_speech = ModernButton("", ModernButton.PRIMARY)
        dialog.btn_speech.setFixedSize(32, 32)
        dialog.btn_speech.set_compact(True)
        # ✅ FIX: Add button_type="speech" as third argument
        self._setup_button_icon(dialog.btn_speech, "speech_to_text.svg", "speech")
        dialog.btn_speech.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1a6e9e;
            }
            QPushButton:checked {
                background-color: #1a6e9e;
            }
        """)
        name_layout.addWidget(dialog.btn_speech)
        
        grid.addWidget(dialog.label_name, row, 0)
        grid.addWidget(name_widget, row, 1)
        return row + 1
    
    def _add_category_row(self, dialog, grid, row, colors):
        """Add category row"""
        dialog.label_category = self._create_label_with_icon("category.svg", "Category", colors)
        dialog.category_combo = self._create_combobox(colors)
        grid.addWidget(dialog.label_category, row, 0)
        grid.addWidget(dialog.category_combo, row, 1)
        return row + 1
    
    def _add_barcode_row(self, dialog, grid, row, colors):
        """Add barcode row"""
        dialog.label_barcode = self._create_label_with_icon("barcode.svg", "Barcode", colors)
        dialog.barcode_input = self._create_lineedit("Scan barcode...", colors)
        dialog.barcode_input.setClearButtonEnabled(True)
        grid.addWidget(dialog.label_barcode, row, 0)
        grid.addWidget(dialog.barcode_input, row, 1)
        return row + 1
    
    def _add_sold_by_row(self, dialog, grid, row, colors):
        """Add sold by row"""
        dialog.label_sold_by = self._create_label_with_icon("swap_horiz.svg", "Sold By", colors)
        dialog.sold_by_combo = QComboBox()
        dialog.sold_by_combo.addItem("Each", "Each")
        dialog.sold_by_combo.addItem("Service", "Service")
        dialog.sold_by_combo.addItem("Variants", "Variants")
        dialog.sold_by_combo.setStyleSheet(ProductFormUIStyles.get_combobox_style(colors))
        grid.addWidget(dialog.label_sold_by, row, 0)
        grid.addWidget(dialog.sold_by_combo, row, 1)
        return row + 1
    
    def _add_price_row(self, dialog, grid, row, colors):
        """Add price row"""
        dialog.label_price = self._create_label_with_icon("attach_money.svg", "Price", colors)
        
        price_widget = QWidget()
        dialog.price_widget = price_widget
        price_layout = QHBoxLayout(price_widget)
        price_layout.setContentsMargins(0, 0, 0, 0)
        price_layout.setSpacing(8)
        
        dialog.price_input = QDoubleSpinBox()
        dialog.price_input.setRange(0, 999999)
        dialog.price_input.setDecimals(0)
        dialog.price_input.setStyleSheet(ProductFormUIStyles.get_spinbox_style(colors))
        price_layout.addWidget(dialog.price_input)
        
        price_label = QLabel("MMK")
        price_label.setStyleSheet(f"color: {colors['text_secondary']}; font-weight: 600; font-size: 10pt;")
        price_layout.addWidget(price_label)
        price_layout.addStretch()
        
        grid.addWidget(dialog.label_price, row, 0)
        grid.addWidget(price_widget, row, 1)
        return row + 1
    
    def _add_low_stock_row(self, dialog, grid, row, colors):
        """Add low stock alert row"""
        dialog.label_low_stock = self._create_label_with_icon("warning.svg", "Low Stock Alert", colors)
        dialog.low_stock_input = QSpinBox()
        dialog.low_stock_input.setRange(0, 999999)
        dialog.low_stock_input.setToolTip("Stock ဘယ်လောက်ကျန်ရင် သတိပေးချက်ပြမလဲ သတ်မှတ်ပါ")
        dialog.low_stock_input.setStyleSheet(ProductFormUIStyles.get_spinbox_style(colors))
        grid.addWidget(dialog.label_low_stock, row, 0)
        grid.addWidget(dialog.low_stock_input, row, 1)
        return row + 1

    def _add_variants_row(self, dialog, grid, row, colors):
        """Add product variants table."""
        dialog.label_variants = self._create_label_with_icon("inventory_2.svg", "Variants", colors)

        variants_widget = QWidget()
        dialog.variants_widget = variants_widget
        variants_layout = QVBoxLayout(variants_widget)
        variants_layout.setContentsMargins(0, 0, 0, 0)
        variants_layout.setSpacing(4)

        dialog.variants_table = QTableWidget(0, 6)
        dialog.variants_table.setHorizontalHeaderLabels(["Size", "Color", "SKU", "Barcode", "Price", "Stock Alert"])
        dialog.variants_table.setMinimumHeight(120)
        dialog.variants_table.setMaximumHeight(150)
        dialog.variants_table.verticalHeader().setVisible(False)
        dialog.variants_table.setAlternatingRowColors(True)
        header = dialog.variants_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        dialog.variants_table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
        dialog.variants_table.setVisible(False)

        dialog.variants_summary_label = QLabel("No variants added")
        dialog.variants_summary_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 9pt;
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 8px 10px;
            }}
        """)
        variants_layout.addWidget(dialog.variants_summary_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addStretch()
        dialog.btn_manage_variants = ModernButton(" Manage Variants", ModernButton.SECONDARY)
        dialog.btn_manage_variants.set_icon("inventory_2", size=(16, 16))
        dialog.btn_manage_variants.set_compact(True)
        dialog.btn_manage_variants.setFixedHeight(30)
        buttons_layout.addWidget(dialog.btn_manage_variants)
        variants_layout.addLayout(buttons_layout)

        grid.addWidget(dialog.label_variants, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(variants_widget, row, 1)
        return row + 1
    
    def _add_description_row(self, dialog, grid, row, colors):
        """Add description row with speech button"""
        dialog.label_description = self._create_label_with_icon("description.svg", "Description", colors)
        
        desc_widget = QWidget()
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(3)
        
        dialog.description_input = QTextEdit()
        dialog.description_input.setMaximumHeight(60)
        dialog.description_input.setPlaceholderText("Enter product description...")
        dialog.description_input.setStyleSheet(ProductFormUIStyles.get_textedit_style(colors))
        desc_layout.addWidget(dialog.description_input)
        
        desc_button_layout = QHBoxLayout()
        desc_button_layout.setContentsMargins(0, 0, 0, 0)
        
        dialog.btn_speech_desc = ModernButton("Speak Description", ModernButton.SECONDARY)
        dialog.btn_speech_desc.setFixedSize(150, 30)
        dialog.btn_speech_desc.set_compact(True)
        # ✅ FIX: Add button_type="speech" as third argument
        self._setup_button_icon(dialog.btn_speech_desc, "speech_to_text.svg", "speech")
        dialog.btn_speech_desc.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 10pt;
                padding: 4px 12px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:checked {
                background-color: #1e8449;
            }
        """)
        
        desc_button_layout.addStretch()
        desc_button_layout.addWidget(dialog.btn_speech_desc)
        desc_layout.addLayout(desc_button_layout)
        
        grid.addWidget(dialog.label_description, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(desc_widget, row, 1)
        return row + 1
    
    def _add_image_row(self, dialog, grid, row, colors):
        """Add product image row"""
        dialog.label_image = self._create_label_with_icon("image.svg", "Product Image", colors)
        
        image_widget = QWidget()
        image_layout = QHBoxLayout(image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(4)
        
        dialog.image_input = QLineEdit()
        dialog.image_input.setReadOnly(True)
        dialog.image_input.setStyleSheet(ProductFormUIStyles.get_readonly_input_style(colors))
        
        dialog.btn_browse = ModernButton("Browse", ModernButton.SECONDARY)
        dialog.btn_browse.set_compact(True)
        # ✅ FIX: Add button_type="browse" as third argument
        self._setup_button_icon(dialog.btn_browse, "folder_open.svg", "browse")
        dialog.btn_browse.setStyleSheet("""
            QPushButton {
                padding: 5px 14px;
                font-size: 10pt;
                min-height: 24px;
            }
        """)
        
        image_layout.addWidget(dialog.image_input)
        image_layout.addWidget(dialog.btn_browse)
        
        grid.addWidget(dialog.label_image, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(image_widget, row, 1)
        return row + 1
    
    def _add_language_row(self, dialog, grid, row, colors):
        """Add language selection row"""
        lang_widget = QWidget()
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 2, 0, 2)
        lang_layout.setSpacing(6)
        
        dialog.language_label = QLabel("Speech Language:")
        dialog.language_label.setStyleSheet(f"font-weight: 500; color: {colors['text']}; font-size: 9pt;")
        
        dialog.language_combo = QComboBox()
        dialog.language_combo.addItem("🇲🇲 မြန်မာ", "my")
        dialog.language_combo.addItem("🇬🇧 English", "en")
        dialog.language_combo.setCurrentIndex(0)
        dialog.language_combo.setStyleSheet(ProductFormUIStyles.get_combobox_style(colors))
        
        lang_layout.addWidget(dialog.language_label)
        lang_layout.addWidget(dialog.language_combo)
        lang_layout.addStretch()
        
        grid.addWidget(QLabel(""), row, 0)
        grid.addWidget(lang_widget, row, 1)
        return row + 1
    
    def _setup_right_panel(self, dialog, colors):
        """Setup the right panel with image preview and info"""
        is_dark = is_dark_theme()
        
        right_panel = QFrame()
        right_panel.setObjectName("right_panel")
        right_panel.setStyleSheet(ProductFormUIStyles.get_right_panel_style(colors))
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        
        # Image title with icon
        image_title = QLabel()
        image_title.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                font-size: 10pt;
                color: {colors['text']};
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        
        svg_content = self._get_themed_svg("image_inset.svg", colors)
        if svg_content:
            image_title.setText(f'<img src="data:image/svg+xml;base64,{svg_content}" width="16" height="16" style="vertical-align:middle;"> Product Image Preview')
        else:
            image_title.setText("🖼️ Product Image Preview")
        right_layout.addWidget(image_title)
        
        # Image preview
        dialog.image_preview = QLabel()
        dialog.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.image_preview.setMinimumHeight(150)
        dialog.image_preview.setMaximumHeight(200)
        dialog.image_preview.setStyleSheet(ProductFormUIStyles.get_image_preview_style(colors, is_dark))
        dialog.image_preview.setText("No Image\n\nSelect an image to preview")
        dialog.image_preview.setWordWrap(True)
        right_layout.addWidget(dialog.image_preview, 1)
        
        # Product info section
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background: {colors['bg_hover']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(4)
        info_layout.setContentsMargins(8, 8, 8, 8)
        
        info_title = QLabel()
        info_title.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                color: {colors['text']};
                font-size: 9pt;
                background: transparent;
                border: none;
            }}
        """)
        
        svg_content = self._get_themed_svg("info.svg", colors)
        if svg_content:
            info_title.setText(f'<img src="data:image/svg+xml;base64,{svg_content}" width="14" height="14" style="vertical-align:middle;"> Product Information')
        else:
            info_title.setText("ℹ️ Product Information")
        info_layout.addWidget(info_title)
        
        dialog.product_details_label = QLabel("Fill in the form to see product details")
        dialog.product_details_label.setStyleSheet(ProductFormUIStyles.get_details_label_style(colors))
        dialog.product_details_label.setWordWrap(True)
        info_layout.addWidget(dialog.product_details_label)
        
        right_layout.addWidget(info_frame)
        right_layout.addStretch()
        
        return right_panel
