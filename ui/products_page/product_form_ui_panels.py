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
        left_layout.setContentsMargins(10, 8, 10, 8)
        left_layout.setSpacing(2)
        
        grid = QGridLayout()
        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnMinimumWidth(0, 130)
        
        row = 0

        row = self._add_section_header(grid, row, "Basic")
        row = self._add_sold_by_row(dialog, grid, row, colors)
        
        row = self._add_name_row(dialog, grid, row, colors)
        row = self._add_category_row(dialog, grid, row, colors)
        row = self._add_barcode_row(dialog, grid, row, colors)

        row = self._add_section_header(grid, row, "Sales & Stock")
        row = self._add_price_row(dialog, grid, row, colors)
        row = self._add_low_stock_row(dialog, grid, row, colors)
        row = self._add_unit_conversion_row(dialog, grid, row, colors)
        row = self._add_wholesale_row(dialog, grid, row, colors)
        row = self._add_restaurant_options_row(dialog, grid, row, colors)

        row = self._add_section_header(grid, row, "Optional")
        row = self._add_variants_row(dialog, grid, row, colors)
        row = self._add_description_row(dialog, grid, row, colors)
        
        dialog.info_label = InfoLabel("Stock notes and information")
        dialog.info_label.setStyleSheet(ProductFormUIStyles.get_info_label_style(colors, is_dark))
        grid.addWidget(QLabel(""), row, 0)
        grid.addWidget(dialog.info_label, row, 1)
        row += 1
        
        left_layout.addLayout(grid)
        return left_panel

    def _add_section_header(self, grid, row, text):
        """Add a compact section label."""
        label = QLabel(text.upper())
        label.setStyleSheet(ProductFormUIStyles.get_section_label_style(get_theme_colors()))
        grid.addWidget(label, row, 0, 1, 2)
        return row + 1
    
    def _add_name_row(self, dialog, grid, row, colors):
        """Add product name row."""
        dialog.label_name = self._create_label_with_icon("label.svg", "Product Name", colors)
        dialog.name_input = self._create_lineedit("Enter product name...", colors)

        grid.addWidget(dialog.label_name, row, 0)
        grid.addWidget(dialog.name_input, row, 1)
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
        dialog.sold_by_combo.addItem("Restaurant", "Restaurant")
        dialog.sold_by_combo.setStyleSheet(ProductFormUIStyles.get_combobox_style(colors))
        grid.addWidget(dialog.label_sold_by, row, 0)
        grid.addWidget(dialog.sold_by_combo, row, 1)
        return row + 1

    def _add_restaurant_options_row(self, dialog, grid, row, colors):
        """Add restaurant modifier controls."""
        dialog.label_restaurant_options = self._create_label_with_icon("receipt_long.svg", "Restaurant Options", colors)

        restaurant_widget = QWidget()
        dialog.restaurant_options_widget = restaurant_widget
        restaurant_layout = QVBoxLayout(restaurant_widget)
        restaurant_layout.setContentsMargins(0, 0, 0, 0)
        restaurant_layout.setSpacing(4)

        dialog.restaurant_modifiers_table = QTableWidget(0, 4)
        dialog.restaurant_modifiers_table.setHorizontalHeaderLabels(["Group", "Option", "Type", "Price +"])
        dialog.restaurant_modifiers_table.setVisible(False)
        dialog.restaurant_modifiers_table.verticalHeader().setVisible(False)
        header = dialog.restaurant_modifiers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        dialog.restaurant_summary_label = QLabel("Restaurant modifiers not set")
        dialog.restaurant_summary_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 9pt;
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 9px;
            }}
        """)
        restaurant_layout.addWidget(dialog.restaurant_summary_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addStretch()
        dialog.btn_manage_restaurant_options = ModernButton(" Manage", ModernButton.SECONDARY)
        dialog.btn_manage_restaurant_options.set_icon("settings", size=(16, 16))
        dialog.btn_manage_restaurant_options.set_compact(True)
        dialog.btn_manage_restaurant_options.setMinimumSize(104, 34)
        dialog.btn_manage_restaurant_options.setFixedHeight(34)
        dialog.btn_manage_restaurant_options.setStyleSheet(dialog.btn_manage_restaurant_options.styleSheet() + """
            QPushButton {
                padding: 3px 12px;
                font-size: 9.5pt;
            }
        """)
        buttons_layout.addWidget(dialog.btn_manage_restaurant_options)
        restaurant_layout.addLayout(buttons_layout)

        grid.addWidget(dialog.label_restaurant_options, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(restaurant_widget, row, 1)
        return row + 1

    def _add_unit_conversion_row(self, dialog, grid, row, colors):
        """Add base/pack unit conversion controls."""
        dialog.label_units = self._create_label_with_icon("inventory_2.svg", "Pack Setup", colors)

        units_widget = QWidget()
        dialog.units_widget = units_widget
        units_layout = QGridLayout(units_widget)
        units_layout.setContentsMargins(0, 0, 0, 0)
        units_layout.setHorizontalSpacing(8)
        units_layout.setVerticalSpacing(2)

        base_hint = QLabel("Stock unit")
        pack_hint = QLabel("Pack name")
        size_hint = QLabel("Qty/pack")
        for col, hint in enumerate((base_hint, pack_hint, size_hint)):
            hint.setStyleSheet(ProductFormUIStyles.get_field_hint_style(colors))
            units_layout.addWidget(hint, 0, col)

        dialog.base_unit_input = self._create_lineedit("bottle / pcs", colors)
        dialog.base_unit_input.setText("pcs")
        dialog.base_unit_input.setToolTip("Smallest counted stock unit, e.g. bottle/pcs.")
        units_layout.addWidget(dialog.base_unit_input, 1, 0)

        dialog.pack_unit_input = self._create_lineedit("card / box", colors)
        dialog.pack_unit_input.setToolTip("Optional larger unit bought or sold as a pack.")
        units_layout.addWidget(dialog.pack_unit_input, 1, 1)

        dialog.pack_size_input = QSpinBox()
        dialog.pack_size_input.setRange(1, 999999)
        dialog.pack_size_input.setValue(1)
        dialog.pack_size_input.setToolTip("How many base units are inside one pack.")
        dialog.pack_size_input.setStyleSheet(ProductFormUIStyles.get_spinbox_style(colors))
        units_layout.addWidget(dialog.pack_size_input, 1, 2)
        units_layout.setColumnStretch(0, 2)
        units_layout.setColumnStretch(1, 2)
        units_layout.setColumnStretch(2, 1)

        grid.addWidget(dialog.label_units, row, 0)
        grid.addWidget(units_widget, row, 1)
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

    def _add_wholesale_row(self, dialog, grid, row, colors):
        """Add wholesale price tier controls."""
        dialog.label_wholesale = self._create_label_with_icon("attach_money.svg", "Wholesale", colors)

        wholesale_widget = QWidget()
        dialog.wholesale_widget = wholesale_widget
        wholesale_layout = QVBoxLayout(wholesale_widget)
        wholesale_layout.setContentsMargins(0, 0, 0, 0)
        wholesale_layout.setSpacing(4)

        dialog.wholesale_table = QTableWidget(0, 6)
        dialog.wholesale_table.setHorizontalHeaderLabels(["Min Qty", "Unit", "Unit Qty", "Barcode", "Unit Price", "Note"])
        dialog.wholesale_table.setVisible(False)
        dialog.wholesale_table.verticalHeader().setVisible(False)
        header = dialog.wholesale_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        dialog.wholesale_summary_label = QLabel("Pack/wholesale barcode not set")
        dialog.wholesale_summary_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 9pt;
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 9px;
            }}
        """)
        wholesale_layout.addWidget(dialog.wholesale_summary_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addStretch()
        dialog.btn_manage_wholesale = ModernButton(" Manage", ModernButton.SECONDARY)
        dialog.btn_manage_wholesale.set_icon("attach_money", size=(16, 16))
        dialog.btn_manage_wholesale.set_compact(True)
        dialog.btn_manage_wholesale.setMinimumSize(104, 34)
        dialog.btn_manage_wholesale.setFixedHeight(34)
        dialog.btn_manage_wholesale.setStyleSheet(dialog.btn_manage_wholesale.styleSheet() + """
            QPushButton {
                padding: 3px 12px;
                font-size: 9.5pt;
            }
        """)
        buttons_layout.addWidget(dialog.btn_manage_wholesale)
        wholesale_layout.addLayout(buttons_layout)

        grid.addWidget(dialog.label_wholesale, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(wholesale_widget, row, 1)
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

        dialog.variants_summary_label = QLabel("Variants not set")
        dialog.variants_summary_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 9pt;
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 9px;
            }}
        """)
        variants_layout.addWidget(dialog.variants_summary_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addStretch()
        dialog.btn_manage_variants = ModernButton(" Manage", ModernButton.SECONDARY)
        dialog.btn_manage_variants.set_icon("inventory_2", size=(16, 16))
        dialog.btn_manage_variants.set_compact(True)
        dialog.btn_manage_variants.setMinimumSize(104, 34)
        dialog.btn_manage_variants.setFixedHeight(34)
        dialog.btn_manage_variants.setStyleSheet(dialog.btn_manage_variants.styleSheet() + """
            QPushButton {
                padding: 3px 12px;
                font-size: 9.5pt;
            }
        """)
        buttons_layout.addWidget(dialog.btn_manage_variants)
        variants_layout.addLayout(buttons_layout)

        grid.addWidget(dialog.label_variants, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(variants_widget, row, 1)
        return row + 1
    
    def _add_description_row(self, dialog, grid, row, colors):
        """Add description row."""
        dialog.label_description = self._create_label_with_icon("description.svg", "Description", colors)

        dialog.description_input = QTextEdit()
        dialog.description_input.setMaximumHeight(48)
        dialog.description_input.setPlaceholderText("Enter product description...")
        dialog.description_input.setStyleSheet(ProductFormUIStyles.get_textedit_style(colors))

        grid.addWidget(dialog.label_description, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(dialog.description_input, row, 1)
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
                padding: 3px 12px;
                font-size: 10pt;
                min-height: 0px;
            }
        """)
        dialog.btn_browse.setMinimumSize(112, 34)
        dialog.btn_browse.setFixedHeight(34)
        
        image_layout.addWidget(dialog.image_input)
        image_layout.addWidget(dialog.btn_browse)
        
        grid.addWidget(dialog.label_image, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(image_widget, row, 1)
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
        dialog.image_preview.setMinimumHeight(130)
        dialog.image_preview.setMaximumHeight(170)
        dialog.image_preview.setStyleSheet(ProductFormUIStyles.get_image_preview_style(colors, is_dark))
        dialog.image_preview.setText("No Image\n\nSelect an image to preview")
        dialog.image_preview.setWordWrap(True)
        right_layout.addWidget(dialog.image_preview, 1)

        self._add_image_picker_to_panel(dialog, right_layout, colors)
        
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

    def _add_image_picker_to_panel(self, dialog, layout, colors):
        """Add compact image file controls below the preview."""
        dialog.label_image = QLabel("Product Image")
        dialog.label_image.setStyleSheet(ProductFormUIStyles.get_label_style(colors))
        layout.addWidget(dialog.label_image)

        image_widget = QWidget()
        image_layout = QHBoxLayout(image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(6)

        dialog.image_input = QLineEdit()
        dialog.image_input.setReadOnly(True)
        dialog.image_input.setPlaceholderText("No image selected")
        dialog.image_input.setStyleSheet(ProductFormUIStyles.get_readonly_input_style(colors))

        dialog.btn_browse = ModernButton("Browse", ModernButton.SECONDARY)
        dialog.btn_browse.set_compact(True)
        dialog.btn_browse.setMinimumSize(112, 34)
        dialog.btn_browse.setFixedHeight(34)
        self._setup_button_icon(dialog.btn_browse, "folder_open.svg", "browse")
        dialog.btn_browse.setStyleSheet(dialog.btn_browse.styleSheet() + """
            QPushButton {
                padding: 3px 12px;
                font-size: 9.5pt;
            }
        """)

        image_layout.addWidget(dialog.image_input, 1)
        image_layout.addWidget(dialog.btn_browse)
        layout.addWidget(image_widget)
