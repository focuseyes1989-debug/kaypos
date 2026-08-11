# ui/products_page/product_form_ui.py
"""
Main UI class for ProductFormDialog - Combines all UI components with SVG icons
"""

from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from ui.widgets.modern_button import ModernButton
from ui.products_page.product_form_ui_panels import ProductFormUIPanels
from ui.products_page.product_form_ui_styles import ProductFormUIStyles
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
import os


class ProductFormUI(ProductFormUIPanels):
    """Main UI setup class for ProductFormDialog - Theme-aware with SVG icons"""
    
    def _load_svg_icon(self, icon_name, size=(16, 16)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        # Try PNG fallback
        png_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(png_path):
            try:
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        return None
    
    def setup_ui(self, dialog, product_id=None):
        """Setup the complete UI for the dialog"""
        self._dialog = dialog
        self._is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        dialog.setWindowTitle("Add Product" if product_id is None else "Edit Product")
        dialog.resize(900, 680)
        dialog.setMinimumWidth(820)
        dialog.setMinimumHeight(620)
        dialog.setMaximumHeight(760)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Setup header
        self._setup_header(main_layout, product_id, colors)
        
        # Setup content
        content_widget = self._setup_content(dialog, colors)
        main_layout.addWidget(content_widget)
        
        # Setup buttons
        self._setup_buttons(dialog, main_layout, colors)
        
        dialog.setLayout(main_layout)
        self._store_references(dialog)
    
    def _setup_header(self, parent_layout, product_id=None, colors=None):
        """Setup the header section - Theme-aware with SVG icons"""
        if colors is None:
            colors = get_theme_colors()
        
        header_frame = QFrame()
        header_frame.setObjectName("header_frame")
        header_frame.setStyleSheet(ProductFormUIStyles.get_header_style())
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 8, 15, 8)
        
        icon_name = "edit" if product_id else "add"
        title_text = "Edit Product" if product_id else "Add New Product"
        
        # ✅ Header with SVG icon
        icon = self._load_svg_icon(icon_name, size=(24, 24))
        title_label = QLabel()
        if icon and not icon.isNull():
            # Create icon display
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(24, 24))
            icon_label.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(icon_label)
            title_label.setText(title_text)
        else:
            title_label.setText(f"{'✏️' if product_id else '➕'} {title_text}")
        
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14pt;
                font-weight: 600;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        if product_id:
            badge = QLabel(f"ID: #{product_id}")
            badge.setStyleSheet("""
                QLabel {
                    background: rgba(255,255,255,0.2);
                    color: white;
                    padding: 2px 12px;
                    border-radius: 10px;
                    font-size: 9pt;
                    font-weight: 500;
                }
            """)
            header_layout.addWidget(badge)
        
        parent_layout.addWidget(header_frame)
    
    def _setup_content(self, dialog, colors):
        """Setup the main content with two columns"""
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        left_panel = self._setup_left_panel(dialog, colors)
        right_panel = self._setup_right_panel(dialog, colors)
        
        content_layout.addWidget(left_panel, 5)
        content_layout.addWidget(right_panel, 2)
        
        return content_widget
    
    def _setup_buttons(self, dialog, parent_layout, colors):
        """Setup the button section using ModernButton with SVG icons"""
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(ProductFormUIStyles.get_button_frame_style(colors))
        
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(12, 5, 12, 5)
        button_layout.addStretch()
        
        # ✅ Cancel button with SVG icon
        dialog.btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        dialog.btn_cancel.set_icon("close", size=(16, 16))
        dialog.btn_cancel.set_compact(True)
        dialog.btn_cancel.setMinimumHeight(28)
        dialog.btn_cancel.setMaximumHeight(32)
        dialog.btn_cancel.setMinimumWidth(80)
        dialog.btn_cancel.setMaximumWidth(120)
        dialog.btn_cancel.setStyleSheet(dialog.btn_cancel.styleSheet() + """
            QPushButton {
                font-size: 9pt;
                padding: 4px 12px;
                border-radius: 6px;
            }
        """)
        
        # ✅ Save button with SVG icon
        dialog.btn_save = ModernButton(" Save", ModernButton.PRIMARY)
        dialog.btn_save.set_icon("save", size=(16, 16))
        dialog.btn_save.set_compact(True)
        dialog.btn_save.setMinimumHeight(28)
        dialog.btn_save.setMaximumHeight(32)
        dialog.btn_save.setMinimumWidth(80)
        dialog.btn_save.setMaximumWidth(120)
        dialog.btn_save.setStyleSheet(dialog.btn_save.styleSheet() + """
            QPushButton {
                font-size: 9pt;
                font-weight: 600;
                padding: 4px 16px;
                border-radius: 6px;
            }
        """)
        dialog.btn_save.setDefault(True)
        
        button_layout.addWidget(dialog.btn_cancel)
        button_layout.addWidget(dialog.btn_save)
        
        parent_layout.addWidget(button_frame)
    
    def _update_all_styles(self):
        """Update all widget styles"""
        d = self._dialog
        if not d:
            return
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        for child in d.findChildren(QWidget):
            if child.objectName() == "left_panel":
                child.setStyleSheet(ProductFormUIStyles.get_left_panel_style(colors))
            elif child.objectName() == "right_panel":
                child.setStyleSheet(ProductFormUIStyles.get_right_panel_style(colors))
            elif child.objectName() == "header_frame":
                child.setStyleSheet(ProductFormUIStyles.get_header_style())
        
        self._update_input_styles(d, colors)
        
        if hasattr(d, 'info_label'):
            d.info_label.setStyleSheet(ProductFormUIStyles.get_info_label_style(colors, is_dark))
        
        if hasattr(d, 'product_details_label'):
            d.product_details_label.setStyleSheet(ProductFormUIStyles.get_details_label_style(colors))
        
        if hasattr(d, 'image_preview'):
            d.image_preview.setStyleSheet(ProductFormUIStyles.get_image_preview_style(colors, is_dark))
        
        for child in d.findChildren(QFrame):
            if child.objectName() == "button_frame":
                child.setStyleSheet(ProductFormUIStyles.get_button_frame_style(colors))
        
        # Update button icons
        if hasattr(d, 'btn_save'):
            d.btn_save.set_icon("save", size=(16, 16))
        if hasattr(d, 'btn_cancel'):
            d.btn_cancel.set_icon("close", size=(16, 16))
        if hasattr(d, 'btn_browse'):
            d.btn_browse.set_icon("folder_open", size=(16, 16))
        if hasattr(d, 'btn_manage_variants'):
            d.btn_manage_variants.set_icon("inventory_2", size=(16, 16))
        if hasattr(d, 'btn_manage_wholesale'):
            d.btn_manage_wholesale.set_icon("attach_money", size=(16, 16))
        if hasattr(d, 'btn_manage_restaurant_options'):
            d.btn_manage_restaurant_options.set_icon("settings", size=(16, 16))
    
    def _update_input_styles(self, dialog, colors):
        """Update input field styles"""
        if hasattr(dialog, 'name_input'):
            dialog.name_input.setStyleSheet(ProductFormUIStyles.get_input_style(colors))
        if hasattr(dialog, 'barcode_input'):
            dialog.barcode_input.setStyleSheet(ProductFormUIStyles.get_input_style(colors))
        if hasattr(dialog, 'image_input'):
            dialog.image_input.setStyleSheet(ProductFormUIStyles.get_readonly_input_style(colors))
        if hasattr(dialog, 'base_unit_input'):
            dialog.base_unit_input.setStyleSheet(ProductFormUIStyles.get_input_style(colors))
        if hasattr(dialog, 'pack_unit_input'):
            dialog.pack_unit_input.setStyleSheet(ProductFormUIStyles.get_input_style(colors))
        if hasattr(dialog, 'pack_size_input'):
            dialog.pack_size_input.setStyleSheet(ProductFormUIStyles.get_spinbox_style(colors))
        if hasattr(dialog, 'price_input'):
            dialog.price_input.setStyleSheet(ProductFormUIStyles.get_spinbox_style(colors))
        if hasattr(dialog, 'low_stock_input'):
            dialog.low_stock_input.setStyleSheet(ProductFormUIStyles.get_spinbox_style(colors))
        if hasattr(dialog, 'description_input'):
            dialog.description_input.setStyleSheet(ProductFormUIStyles.get_textedit_style(colors))
        if hasattr(dialog, 'category_combo'):
            dialog.category_combo.setStyleSheet(ProductFormUIStyles.get_combobox_style(colors))
        if hasattr(dialog, 'sold_by_combo'):
            dialog.sold_by_combo.setStyleSheet(ProductFormUIStyles.get_combobox_style(colors))
        if hasattr(dialog, 'restaurant_modifiers_table'):
            dialog.restaurant_modifiers_table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
        if hasattr(dialog, 'variants_table'):
            dialog.variants_table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
        if hasattr(dialog, 'wholesale_table'):
            dialog.wholesale_table.setStyleSheet(ProductFormUIStyles.get_table_style(colors))
    
    def _store_references(self, dialog):
        """Store references to UI elements in dialog"""
        pass
