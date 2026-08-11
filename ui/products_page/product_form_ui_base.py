# ui/products_page/product_form_ui_base.py
"""
Base UI class for ProductFormDialog - Contains core setup methods
"""

from PyQt6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget,
    QGridLayout, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from ui.widgets.modern_button import ModernButton
from ui.products_page.product_form_widgets import InfoLabel
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
import os


class ProductFormUIBase:
    """Base UI class with common methods for ProductFormDialog"""
    
    def __init__(self):
        self._is_dark = is_dark_theme()
        self._icon_cache = {}
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change - update styles and icons"""
        self._is_dark = is_dark_theme()
        self._icon_cache = {}
        if hasattr(self, '_dialog'):
            self._update_all_styles()
            self._update_all_icons()
    
    def _get_icon_path(self, icon_name):
        """Get full path for an icon"""
        return f"assets/icons/{icon_name}"
    
    def _get_themed_svg(self, icon_name, colors):
        """Get themed SVG content with current theme colors"""
        icon_path = self._get_icon_path(icon_name)
        
        cache_key = f"{icon_name}_{self._is_dark}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Replace color attributes with theme colors
            color_replacements = {
                '#000000': colors['text'],
                '#000': colors['text'],
                '#333333': colors['text'],
                '#333': colors['text'],
                '#666666': colors['text_secondary'],
                '#666': colors['text_secondary'],
                '#ffffff': colors['text'] if self._is_dark else '#ffffff',
                '#fff': colors['text'] if self._is_dark else '#ffffff',
                '#f0f0f0': colors['card_bg'],
                '#e0e0e0': colors['bg_hover'],
                '#cccccc': colors['border'],
                '#999999': colors['text_secondary'],
            }
            
            for old_color, new_color in color_replacements.items():
                if old_color in svg_content:
                    svg_content = svg_content.replace(old_color, new_color)
            
            import re
            svg_content = re.sub(
                r'fill="[^"]*"',
                lambda m: f'fill="{colors["text"]}"' if m.group() not in ['fill="none"', 'fill="transparent"'] else m.group(),
                svg_content
            )
            svg_content = re.sub(
                r'stroke="[^"]*"',
                lambda m: f'stroke="{colors["text"]}"' if m.group() not in ['stroke="none"', 'stroke="transparent"'] else m.group(),
                svg_content
            )
            
            import base64
            encoded = base64.b64encode(svg_content.encode()).decode()
            self._icon_cache[cache_key] = encoded
            return encoded
            
        except Exception as e:
            print(f"Error loading SVG {icon_name}: {e}")
            return None
    
    def _get_label_text(self, label):
        """Extract text from label (remove HTML tags)"""
        if not label:
            return ""
        text = label.text()
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()
    
    def _create_label_with_icon(self, icon_name, text, colors):
        """Create a label with a themed icon"""
        label = QLabel()
        label.setStyleSheet(f"""
            font-weight: 600; 
            color: {colors['text']}; 
            font-size: 9pt;
            background: transparent;
            border: none;
        """)
        
        svg_content = self._get_themed_svg(icon_name, colors)
        if svg_content:
            label.setText(f'<img src="data:image/svg+xml;base64,{svg_content}" width="16" height="16" style="vertical-align:middle;"> {text}')
        else:
            icon_path = self._get_icon_path(icon_name)
            try:
                icon = QIcon(icon_path)
                pixmap = icon.pixmap(16, 16)
                if not pixmap.isNull():
                    import base64
                    from io import BytesIO
                    buffer = BytesIO()
                    pixmap.save(buffer, "PNG")
                    base64_data = base64.b64encode(buffer.getvalue()).decode()
                    label.setText(f'<img src="data:image/png;base64,{base64_data}" width="16" height="16" style="vertical-align:middle;"> {text}')
                    return label
            except:
                pass
            label.setText(text)
        
        return label
    
    def _create_colored_icon(self, icon_name, color, size=20):
        """Create an icon with specific color"""
        icon_path = self._get_icon_path(icon_name)
        
        try:
            # Try to load as SVG and render with specified color
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Replace all colors with specified color
            import re
            # Replace fill attributes with specified color
            svg_content = re.sub(
                r'fill="[^"]*"',
                f'fill="{color}"',
                svg_content
            )
            # Replace stroke attributes with specified color
            svg_content = re.sub(
                r'stroke="[^"]*"',
                f'stroke="{color}"',
                svg_content
            )
            # Replace any color codes with specified color
            svg_content = re.sub(
                r'#[0-9a-fA-F]{3,6}',
                color,
                svg_content
            )
            
            # Render to pixmap
            renderer = QSvgRenderer(QByteArray(svg_content.encode()))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
            
        except Exception as e:
            print(f"Error creating colored icon {icon_name}: {e}")
            
            # Fallback: try to load as regular icon and colorize
            try:
                icon = QIcon(icon_path)
                pixmap = icon.pixmap(size, size)
                
                # Create a colored version by drawing over
                colored_pixmap = QPixmap(size, size)
                colored_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(colored_pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                
                # Convert color string to QColor
                if color.startswith('#'):
                    color_value = color.lstrip('#')
                    if len(color_value) == 6:
                        r = int(color_value[0:2], 16)
                        g = int(color_value[2:4], 16)
                        b = int(color_value[4:6], 16)
                        painter.fillRect(colored_pixmap.rect(), QColor(r, g, b))
                    else:
                        painter.fillRect(colored_pixmap.rect(), QColor(color))
                else:
                    # Try to use named color
                    painter.fillRect(colored_pixmap.rect(), QColor(color))
                painter.end()
                
                return QIcon(colored_pixmap)
            except:
                return QIcon()
    
    def _get_button_icon_color(self, button_type):
        """Get icon color based on button type and theme"""
        if self._is_dark:
            # Dark theme: always white
            return "#ffffff"
        else:
            # Light theme: different colors based on button type
            if button_type == "speech":
                return "#ffffff"  # White for speech buttons (on colored background)
            elif button_type == "browse":
                return "#6c757d"  # Gray for browse button
            elif button_type == "cancel":
                return "#6c757d"  # Gray for cancel button
            elif button_type == "save":
                return "#ffffff"  # White for save button (on primary background)
            else:
                return "#6c757d"  # Default gray
    
    def _setup_button_icon(self, button, icon_name, button_type="default"):
        """Setup button with appropriate colored icon"""
        if not button:
            return
        
        color = self._get_button_icon_color(button_type)
        colored_icon = self._create_colored_icon(icon_name, color, 20)
        
        if not colored_icon.isNull():
            button.setIcon(colored_icon)
            button.setIconSize(button.sizeHint())
        else:
            # Fallback: try to load original icon
            try:
                icon = QIcon(self._get_icon_path(icon_name))
                button.setIcon(icon)
                button.setIconSize(button.sizeHint())
            except:
                pass
    
    def _update_button_icon(self, button, icon_name, button_type="default"):
        """Update button with appropriate colored icon"""
        if not button:
            return
        
        color = self._get_button_icon_color(button_type)
        colored_icon = self._create_colored_icon(icon_name, color, 20)
        
        if not colored_icon.isNull():
            button.setIcon(colored_icon)
            button.setIconSize(button.sizeHint())
        else:
            try:
                icon = QIcon(self._get_icon_path(icon_name))
                button.setIcon(icon)
                button.setIconSize(button.sizeHint())
            except:
                pass
    
    # ✅ ADD THIS METHOD - Update all icons to match current theme
    def _update_all_icons(self):
        """Update all icons to match current theme"""
        d = self._dialog
        if not d:
            return
        
        # Update label icons - handle missing labels gracefully
        if hasattr(d, 'label_name') and d.label_name:
            self._update_label_icon(d.label_name, "label.svg", self._get_label_text(d.label_name))
        if hasattr(d, 'label_category') and d.label_category:
            self._update_label_icon(d.label_category, "category.svg", self._get_label_text(d.label_category))
        if hasattr(d, 'label_barcode') and d.label_barcode:
            self._update_label_icon(d.label_barcode, "barcode.svg", self._get_label_text(d.label_barcode))
        if hasattr(d, 'label_sold_by') and d.label_sold_by:
            self._update_label_icon(d.label_sold_by, "swap_horiz.svg", self._get_label_text(d.label_sold_by))
        if hasattr(d, 'label_units') and d.label_units:
            self._update_label_icon(d.label_units, "inventory_2.svg", self._get_label_text(d.label_units))
        if hasattr(d, 'label_price') and d.label_price:
            self._update_label_icon(d.label_price, "attach_money.svg", self._get_label_text(d.label_price))
        if hasattr(d, 'label_wholesale') and d.label_wholesale:
            self._update_label_icon(d.label_wholesale, "attach_money.svg", self._get_label_text(d.label_wholesale))
        if hasattr(d, 'label_low_stock') and d.label_low_stock:
            self._update_label_icon(d.label_low_stock, "warning.svg", self._get_label_text(d.label_low_stock))
        if hasattr(d, 'label_variants') and d.label_variants:
            self._update_label_icon(d.label_variants, "inventory_2.svg", self._get_label_text(d.label_variants))
        if hasattr(d, 'label_description') and d.label_description:
            self._update_label_icon(d.label_description, "description.svg", self._get_label_text(d.label_description))
        if hasattr(d, 'label_image') and d.label_image:
            self._update_label_icon(d.label_image, "image.svg", self._get_label_text(d.label_image))
        
        # Update browse button - use browse type
        if hasattr(d, 'btn_browse') and d.btn_browse:
            self._update_button_icon(d.btn_browse, "folder_open.svg", "browse")
        
        # Update cancel button - use cancel type
        if hasattr(d, 'btn_cancel') and d.btn_cancel:
            self._update_button_icon(d.btn_cancel, "close.svg", "cancel")
        
        # Update save button - use save type
        if hasattr(d, 'btn_save') and d.btn_save:
            self._update_button_icon(d.btn_save, "save.svg", "save")
        
        # Update header icon
        product_id = d.product_id if hasattr(d, 'product_id') else None
        icon_name = "edit.svg" if product_id else "add.svg"
        self._update_header_icon(d, icon_name)
    
    def _update_label_icon(self, label, icon_name, text):
        """Update a label with themed icon"""
        if not label:
            return
        
        colors = get_theme_colors()
        icon_path = self._get_icon_path(icon_name)
        
        svg_content = self._get_themed_svg(icon_name, colors)
        if svg_content:
            label.setText(f'<img src="data:image/svg+xml;base64,{svg_content}" width="16" height="16" style="vertical-align:middle;"> {text}')
        else:
            try:
                icon = QIcon(icon_path)
                pixmap = icon.pixmap(16, 16)
                if not pixmap.isNull():
                    import base64
                    from io import BytesIO
                    buffer = BytesIO()
                    pixmap.save(buffer, "PNG")
                    base64_data = base64.b64encode(buffer.getvalue()).decode()
                    label.setText(f'<img src="data:image/png;base64,{base64_data}" width="16" height="16" style="vertical-align:middle;"> {text}')
                    return
            except:
                pass
            label.setText(text)
    
    def _update_header_icon(self, dialog, icon_name):
        """Update header icon"""
        if not dialog:
            return
        for child in dialog.findChildren(QLabel):
            if child.styleSheet() and "color: white" in child.styleSheet():
                colors = get_theme_colors()
                svg_content = self._get_themed_svg(icon_name, colors)
                if svg_content:
                    title_text = self._get_label_text(child)
                    child.setText(f'<img src="data:image/svg+xml;base64,{svg_content}" width="20" height="20" style="vertical-align:middle; filter: brightness(0) invert(1);"> {title_text}')
                break
    
    def _create_lineedit(self, placeholder, colors):
        edit = QLineEdit()
        if placeholder:
            edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(self._get_input_style(colors))
        return edit
    
    def _create_combobox(self, colors):
        combo = QComboBox()
        combo.setStyleSheet(self._get_combobox_style(colors))
        return combo
    
    def _get_input_style(self, colors):
        return f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: transparent;
                color: {colors['text']};
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """
    
    def _get_combobox_style(self, colors):
        return f"""
            QComboBox {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: transparent;
                color: {colors['text']};
                font-size: 10pt;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
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
    
    def _update_all_styles(self):
        """Update all widget styles - override in subclass"""
        pass
