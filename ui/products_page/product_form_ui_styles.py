# ui/products_page/product_form_ui_styles.py
"""
Style definitions for ProductFormDialog
"""

from ui.themes.theme_manager import get_theme_colors, is_dark_theme


class ProductFormUIStyles:
    """Style definitions for ProductFormDialog"""
    
    @staticmethod
    def get_header_style():
        return """
            QFrame#header_frame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5865f2, stop:1 #4752c4);
                border-radius: 8px;
                padding: 5px;
            }
        """
    
    @staticmethod
    def get_left_panel_style(colors):
        return f"""
            QWidget#left_panel {{
                background: transparent;
                border-radius: 8px;
            }}
        """
    
    @staticmethod
    def get_right_panel_style(colors):
        return f"""
            QFrame#right_panel {{
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
        """
    
    @staticmethod
    def get_button_frame_style(colors):
        return f"""
            QFrame#button_frame {{
                background: transparent;
                border-radius: 8px;
                padding: 3px;
            }}
        """
    
    @staticmethod
    def get_input_style(colors):
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
    
    @staticmethod
    def get_readonly_input_style(colors):
        return f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: transparent;
                color: {colors['text_secondary']};
                font-size: 10pt;
            }}
        """
    
    @staticmethod
    def get_combobox_style(colors):
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
    
    @staticmethod
    def get_spinbox_style(colors):
        return f"""
            QSpinBox, QDoubleSpinBox {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: transparent;
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
    
    @staticmethod
    def get_textedit_style(colors):
        return f"""
            QTextEdit {{
                padding: 6px 10px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: transparent;
                color: {colors['text']};
                font-size: 10pt;
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
            }}
            QTextEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """
    
    @staticmethod
    def get_info_label_style(colors, is_dark):
        if is_dark:
            return """
                QLabel {
                    color: #f39c12;
                    font-size: 9pt;
                    padding: 6px 12px;
                    background: rgba(44, 44, 44, 0.7);
                    border-radius: 4px;
                    font-weight: 500;
                }
            """
        else:
            return """
                QLabel {
                    color: #5865f2;
                    font-size: 9pt;
                    padding: 6px 12px;
                    background: rgba(235, 245, 251, 0.7);
                    border-radius: 4px;
                    font-weight: 500;
                }
            """

    @staticmethod
    def get_section_label_style(colors):
        return f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 8.5pt;
                font-weight: 700;
                letter-spacing: 0px;
                background: transparent;
                border: none;
                padding: 6px 0px 2px 0px;
            }}
        """

    @staticmethod
    def get_field_hint_style(colors):
        return f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 8pt;
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """
    
    @staticmethod
    def get_details_label_style(colors):
        return f"""
            QLabel {{
                color: {colors['text_secondary']};
                font-size: 8pt;
                line-height: 1.5;
                background: transparent;
                border: none;
            }}
        """
    
    @staticmethod
    def get_image_preview_style(colors, is_dark):
        return f"""
            QLabel {{
                background: transparent;
                border: 2px dashed {colors['border']};
                border-radius: 10px;
                padding: 10px;
                font-size: 10pt;
                color: {colors['text_secondary']};
            }}
        """
    
    @staticmethod
    def get_label_style(colors):
        return f"""
            QLabel {{
                font-weight: 600;
                color: {colors['text']};
                font-size: 9pt;
                background: transparent;
                border: none;
            }}
        """

    @staticmethod
    def get_table_style(colors):
        return f"""
            QTableWidget {{
                background: transparent;
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                gridline-color: {colors['border']};
                selection-background-color: #5865f2;
                selection-color: white;
            }}
            QHeaderView::section {{
                background: {colors['bg_hover']};
                color: {colors['text']};
                border: none;
                border-right: 1px solid {colors['border']};
                padding: 4px 6px;
                font-weight: 600;
                font-size: 8.5pt;
            }}
            QTableWidget::item {{
                padding: 3px 5px;
            }}
            QTableWidget QLineEdit {{
                background: {colors['card_bg']};
                color: {colors['text']};
                border: 1px solid #5865f2;
                border-radius: 4px;
                padding: 3px 5px;
                selection-background-color: #5865f2;
                selection-color: white;
            }}
        """
