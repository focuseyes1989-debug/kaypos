# ui/inventory_page/stock_in_ui.py
from PyQt6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, 
    QDateEdit, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, 
    QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QPixmap, QIcon
from ui.widgets.modern_button import ModernButton
from ui.inventory_page.stock_in_widgets import StockInfoLabel, HeaderFrame
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import os


class StockInUI:
    """UI setup class for StockInDialog - Theme-aware with SVG Icons"""
    
    def __init__(self):
        self.current_stock_label = None
        self.stock_in_no = None
        self._is_dark = is_dark_theme()
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
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
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change - update styles"""
        self._is_dark = is_dark_theme()
        if hasattr(self, '_dialog'):
            self._update_all_styles()
            self._update_button_icons()
    
    def _update_button_icons(self):
        """Update button icons"""
        d = self._dialog
        if not d:
            return
        if hasattr(d, 'btn_save'):
            d.btn_save.set_icon("save", size=(16, 16))
        if hasattr(d, 'btn_cancel'):
            d.btn_cancel.set_icon("close", size=(16, 16))
    
    def _update_all_styles(self):
        """Update all widget styles"""
        d = self._dialog
        if not d:
            return
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Update left panel
        for child in d.findChildren(QWidget):
            if child.objectName() == "left_panel":
                child.setStyleSheet(self._get_left_panel_style(colors))
            elif child.objectName() == "right_panel":
                child.setStyleSheet(self._get_right_panel_style(colors))
        
        # Update input fields
        self._update_input_styles(d, colors)
        
        # Update product details
        if hasattr(d, 'product_details_label'):
            d.product_details_label.setStyleSheet(self._get_details_label_style(colors))
        
        # Update image preview
        if hasattr(d, 'image_preview'):
            d.image_preview.setStyleSheet(self._get_image_preview_style(colors, is_dark))
        
        # Update button frame
        for child in d.findChildren(QFrame):
            if child.objectName() == "button_frame":
                child.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update button icons
        self._update_button_icons()
    
    def setup_ui(self, dialog):
        """Setup the complete UI for the dialog"""
        self._dialog = dialog
        self._is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        dialog.setWindowTitle("Stock In")
        dialog.resize(950, 720)
        dialog.setMinimumWidth(900)
        dialog.setMinimumHeight(650)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Setup header
        self._setup_header(main_layout)
        
        # Setup content (left panel + right panel)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        left_panel = self._setup_left_panel(dialog, colors)
        right_panel = self._setup_right_panel(dialog, colors)
        
        content_layout.addWidget(left_panel, 2)
        content_layout.addWidget(right_panel, 1)
        
        main_layout.addLayout(content_layout)
        
        # Setup buttons
        self._setup_buttons(dialog, main_layout, colors)
        
        dialog.setLayout(main_layout)
        
        # Store references to UI elements
        self._store_references(dialog)
    
    def _setup_header(self, parent_layout):
        """Setup the header section"""
        header_frame = HeaderFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # ✅ Header with SVG icon
        icon = self._load_svg_icon("inventory", size=(24, 24))
        if icon and not icon.isNull():
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(24, 24))
            icon_label.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(icon_label)
        
        title_label = QLabel(" Stock In")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16pt;
                font-weight: 600;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Stock In Number
        no_label = QLabel("No:")
        no_label.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 500; font-size: 10pt;")
        header_layout.addWidget(no_label)
        
        from datetime import datetime
        self.stock_in_no = QLineEdit()
        self.stock_in_no.setReadOnly(True)
        self.stock_in_no.setText(f"SIN-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.stock_in_no.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.15);
                color: white;
                border: 1px solid rgba(255,255,255,0.25);
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: 600;
                font-size: 10pt;
                min-width: 160px;
            }
        """)
        header_layout.addWidget(self.stock_in_no)
        
        parent_layout.addWidget(header_frame)
    
    def _get_left_panel_style(self, colors):
        """Get left panel style"""
        return f"""
            QWidget#left_panel {{
                background: {colors['bg_hover']};
                border-radius: 8px;
            }}
        """
    
    def _get_right_panel_style(self, colors):
        """Get right panel style"""
        return f"""
            QFrame#right_panel {{
                background: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
        """
    
    def _setup_left_panel(self, dialog, colors):
        """Setup the left panel with form fields"""
        left_panel = QWidget()
        left_panel.setObjectName("left_panel")
        left_panel.setStyleSheet(self._get_left_panel_style(colors))
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(8)
        
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(15)
        grid.setContentsMargins(0, 0, 0, 0)
        
        row = 0
        
        # Row 0: Search
        search_label = self._create_label("🔍 Search", colors)
        dialog.product_search = self._create_search_input(colors)
        grid.addWidget(search_label, row, 0)
        grid.addWidget(dialog.product_search, row, 1)
        row += 1
        
        # Row 1: Product
        product_label = self._create_label("📋 Product", colors)
        product_widget = QWidget()
        product_layout = QHBoxLayout(product_widget)
        product_layout.setContentsMargins(0, 0, 0, 0)
        product_layout.setSpacing(10)
        
        dialog.si_product = self._create_combobox(colors)
        dialog.si_product.setMinimumWidth(200)
        product_layout.addWidget(dialog.si_product)
        
        self.current_stock_label = StockInfoLabel()
        product_layout.addWidget(self.current_stock_label)
        product_layout.addStretch()
        
        grid.addWidget(product_label, row, 0)
        grid.addWidget(product_widget, row, 1)
        row += 1

        # Row 2: Variant (shown only for variant products)
        dialog.variant_label = self._create_label("Variant", colors)
        dialog.si_variant = self._create_combobox(colors)
        dialog.variant_label.setVisible(False)
        dialog.si_variant.setVisible(False)
        grid.addWidget(dialog.variant_label, row, 0)
        grid.addWidget(dialog.si_variant, row, 1)
        row += 1
        
        # Row 3: Supplier | PO No
        supplier_label = self._create_label("🏢 Supplier", colors)
        dialog.si_supplier = self._create_combobox(colors)
        po_label = self._create_label("📄 PO No", colors)
        dialog.si_po_no = self._create_lineedit("PO-YYYYMMDDXXXX", colors)
        grid.addWidget(supplier_label, row, 0)
        grid.addWidget(dialog.si_supplier, row, 1)
        row += 1
        
        # Row 3: Quantity | Unit Cost
        qty_label = self._create_label("🔢 Quantity", colors)
        dialog.si_qty = self._create_spinbox(colors)
        unit_cost_label = self._create_label("💰 Unit Cost", colors)
        dialog.si_unit_cost = self._create_double_spinbox(colors)
        grid.addWidget(qty_label, row, 0)
        grid.addWidget(dialog.si_qty, row, 1)
        row += 1
        
        # Row 4: Unit Cost (display) | Total Cost
        total_label = self._create_label("💵 Total Cost", colors)
        cost_widget = self._create_cost_widget(dialog, colors)
        dialog.si_total_cost, total_widget = self._create_total_widget(colors)
        grid.addWidget(unit_cost_label, row, 0)
        grid.addWidget(cost_widget, row, 1)
        row += 1
        
        # Row 5: Total Cost (display)
        grid.addWidget(total_label, row, 0)
        grid.addWidget(total_widget, row, 1)
        row += 1
        
        # Row 6: Batch No | Expiry
        batch_label = self._create_label("📦 Batch No", colors)
        dialog.si_batch_no = self._create_lineedit("BATCH-YYYYMMDDXXXX", colors)
        expiry_label = self._create_label("📅 Expiry Date", colors)
        dialog.si_expiry = self._create_date_edit(colors)
        grid.addWidget(batch_label, row, 0)
        grid.addWidget(dialog.si_batch_no, row, 1)
        row += 1
        
        # Row 7: Received By | Date
        received_label = self._create_label("👤 Received By", colors)
        dialog.si_received_by = self._create_lineedit("", colors)
        date_label = self._create_label("📆 Date", colors)
        dialog.si_date = self._create_date_edit(colors, QDate.currentDate())
        grid.addWidget(received_label, row, 0)
        grid.addWidget(dialog.si_received_by, row, 1)
        row += 1
        
        # Row 8: Location | Payment Status
        location_label = self._create_label("📍 Location", colors)
        dialog.si_location = self._create_location_combobox(colors)
        payment_label = self._create_label("💳 Payment Status", colors)
        dialog.si_payment_status = self._create_payment_combobox(colors)
        grid.addWidget(location_label, row, 0)
        grid.addWidget(dialog.si_location, row, 1)
        row += 1
        
        # Row 9: Notes
        notes_label = self._create_label("📝 Notes", colors)
        dialog.si_notes = self._create_text_edit(colors)
        grid.addWidget(notes_label, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(dialog.si_notes, row, 1)
        row += 1
        
        left_layout.addLayout(grid)
        return left_panel
    
    def _setup_right_panel(self, dialog, colors):
        """Setup the right panel with image preview"""
        right_panel = QFrame()
        right_panel.setObjectName("right_panel")
        right_panel.setStyleSheet(self._get_right_panel_style(colors))
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(10)
        
        # Image title
        image_title = QLabel("🖼️ Product Image")
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
        right_layout.addWidget(image_title)
        
        # Image preview
        dialog.image_preview = QLabel()
        dialog.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.image_preview.setMinimumHeight(250)
        dialog.image_preview.setMaximumHeight(350)
        dialog.image_preview.setStyleSheet(self._get_image_preview_style(colors, self._is_dark))
        dialog.image_preview.setText("📷 No Image\n\nSelect a product to preview")
        dialog.image_preview.setWordWrap(True)
        right_layout.addWidget(dialog.image_preview, 1)
        
        # Product info section
        info_frame = QFrame()
        info_frame.setStyleSheet("background: transparent; border: none; padding: 0px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(5)
        info_layout.setContentsMargins(0, 10, 0, 5)
        
        dialog.product_info_label = QLabel("ℹ️ Product Information")
        dialog.product_info_label.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                color: {colors['text']};
                font-size: 10pt;
                background: transparent;
                border: none;
            }}
        """)
        info_layout.addWidget(dialog.product_info_label)
        
        dialog.product_details_label = QLabel("Select a product to view details")
        dialog.product_details_label.setStyleSheet(self._get_details_label_style(colors))
        dialog.product_details_label.setWordWrap(True)
        info_layout.addWidget(dialog.product_details_label)
        
        right_layout.addWidget(info_frame)
        right_layout.addStretch()
        
        return right_panel
    
    def _setup_buttons(self, dialog, parent_layout, colors):
        """Setup the button section"""
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(12)
        button_layout.setContentsMargins(15, 8, 15, 8)
        button_layout.addStretch()
        
        # ✅ Save button with SVG icon
        dialog.btn_save = ModernButton(" Save Stock In", ModernButton.PRIMARY)
        dialog.btn_save.set_icon("save", size=(16, 16))
        dialog.btn_save.set_compact(False)
        dialog.btn_save.setMinimumHeight(32)
        dialog.btn_save.setMinimumWidth(140)
        dialog.btn_save.setStyleSheet(dialog.btn_save.styleSheet() + """
            QPushButton {
                font-size: 10pt;
                font-weight: 600;
                padding: 8px 24px;
                border-radius: 6px;
            }
        """)
        
        # ✅ Cancel button with SVG icon
        dialog.btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        dialog.btn_cancel.set_icon("close", size=(16, 16))
        dialog.btn_cancel.set_compact(False)
        dialog.btn_cancel.setMinimumHeight(32)
        dialog.btn_cancel.setMinimumWidth(120)
        dialog.btn_cancel.setStyleSheet(dialog.btn_cancel.styleSheet() + """
            QPushButton {
                font-size: 10pt;
                padding: 8px 20px;
                border-radius: 6px;
            }
        """)
        
        button_layout.addWidget(dialog.btn_cancel)
        button_layout.addWidget(dialog.btn_save)
        
        parent_layout.addWidget(button_frame)
    
    def _store_references(self, dialog):
        """Store references to UI elements in dialog"""
        dialog.stock_in_no = self.stock_in_no
        dialog.current_stock_label = self.current_stock_label
    
    # ===== Helper methods for creating widgets =====
    
    def _create_label(self, text, colors):
        label = QLabel(text)
        label.setStyleSheet(f"font-weight: 600; color: {colors['text']}; font-size: 10pt;")
        return label
    
    def _get_input_style(self, colors):
        return f"""
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTextEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder, QTextEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """
    
    def _create_search_input(self, colors):
        search = QLineEdit()
        search.setPlaceholderText("Type product name, barcode or SKU...")
        search.setStyleSheet(self._get_input_style(colors))
        return search
    
    def _create_combobox(self, colors):
        combo = QComboBox()
        combo.setStyleSheet(self._get_combobox_style(colors))
        return combo
    
    def _get_combobox_style(self, colors):
        return f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 8px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """
    
    def _create_lineedit(self, placeholder, colors):
        edit = QLineEdit()
        if placeholder:
            edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(self._get_input_style(colors))
        return edit
    
    def _create_spinbox(self, colors):
        spin = QSpinBox()
        spin.setRange(1, 999999)
        spin.setStyleSheet(self._get_spinbox_style(colors))
        return spin
    
    def _create_double_spinbox(self, colors):
        spin = QDoubleSpinBox()
        spin.setRange(0, 1000000)
        spin.setDecimals(0)
        spin.setStyleSheet(self._get_spinbox_style(colors))
        return spin
    
    def _get_spinbox_style(self, colors):
        return f"""
            QSpinBox, QDoubleSpinBox {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-width: 100px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #5865f2;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 16px;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 2px;
            }}
        """
    
    def _create_cost_widget(self, dialog, colors):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        layout.addWidget(dialog.si_unit_cost)
        cost_label = QLabel("MMK")
        cost_label.setStyleSheet(f"color: {colors['text_secondary']};")
        layout.addWidget(cost_label)
        layout.addStretch()
        return widget
    
    def _create_total_widget(self, colors):
        total_label = QLabel("0")
        total_label.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                color: #27ae60;
                font-size: 16pt;
                padding: 8px 16px;
                background: #e8f8f5;
                border-radius: 6px;
                border: 1px solid #a3e4d7;
                min-width: 150px;
            }}
        """)
        
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        layout.addWidget(total_label)
        total_text = QLabel("MMK")
        total_text.setStyleSheet(f"color: {colors['text_secondary']};")
        layout.addWidget(total_text)
        layout.addStretch()
        return total_label, widget
    
    def _create_date_edit(self, colors, default_date=None):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        if default_date:
            date_edit.setDate(default_date)
        else:
            date_edit.setDate(QDate.currentDate().addYears(1))
        date_edit.setStyleSheet(self._get_input_style(colors))
        date_edit.setDisplayFormat("yyyy-MM-dd")
        return date_edit
    
    def _create_location_combobox(self, colors):
        combo = QComboBox()
        combo.addItem("None", None)
        combo.addItem("+ Add New Location", "__NEW__")
        combo.setStyleSheet(self._get_combobox_style(colors))
        return combo
    
    def _create_payment_combobox(self, colors):
        combo = QComboBox()
        combo.addItems(["Paid", "Unpaid", "Partial"])
        combo.setStyleSheet(self._get_combobox_style(colors))
        return combo
    
    def _create_text_edit(self, colors):
        edit = QTextEdit()
        edit.setMaximumHeight(70)
        edit.setPlaceholderText("Additional notes or remarks...")
        edit.setStyleSheet(self._get_input_style(colors))
        return edit
    
    def _get_details_label_style(self, colors):
        return f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 9pt;
                line-height: 1.6;
                background: transparent;
                border: none;
            }}
        """
    
    def _get_image_preview_style(self, colors, is_dark):
        border_color = colors['border']
        bg_color = colors['bg_hover']
        text_color = colors['text_secondary']
        
        return f"""
            QLabel {{
                background: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 12px;
                padding: 10px;
                font-size: 11pt;
                color: {text_color};
            }}
        """
    
    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _update_input_styles(self, dialog, colors):
        """Update input field styles"""
        # Search input
        if hasattr(dialog, 'product_search'):
            dialog.product_search.setStyleSheet(self._get_input_style(colors))
        
        # Combo boxes
        if hasattr(dialog, 'si_product'):
            dialog.si_product.setStyleSheet(self._get_combobox_style(colors))
        if hasattr(dialog, 'si_supplier'):
            dialog.si_supplier.setStyleSheet(self._get_combobox_style(colors))
        if hasattr(dialog, 'si_location'):
            dialog.si_location.setStyleSheet(self._get_combobox_style(colors))
        if hasattr(dialog, 'si_payment_status'):
            dialog.si_payment_status.setStyleSheet(self._get_combobox_style(colors))
        
        # Spin boxes
        if hasattr(dialog, 'si_qty'):
            dialog.si_qty.setStyleSheet(self._get_spinbox_style(colors))
        if hasattr(dialog, 'si_unit_cost'):
            dialog.si_unit_cost.setStyleSheet(self._get_spinbox_style(colors))
        
        # Date edits
        if hasattr(dialog, 'si_expiry'):
            dialog.si_expiry.setStyleSheet(self._get_input_style(colors))
        if hasattr(dialog, 'si_date'):
            dialog.si_date.setStyleSheet(self._get_input_style(colors))
        
        # Text edits
        if hasattr(dialog, 'si_notes'):
            dialog.si_notes.setStyleSheet(self._get_input_style(colors))
        
        # Line edits
        if hasattr(dialog, 'si_batch_no'):
            dialog.si_batch_no.setStyleSheet(self._get_input_style(colors))
        if hasattr(dialog, 'si_po_no'):
            dialog.si_po_no.setStyleSheet(self._get_input_style(colors))
        if hasattr(dialog, 'si_received_by'):
            dialog.si_received_by.setStyleSheet(self._get_input_style(colors))
