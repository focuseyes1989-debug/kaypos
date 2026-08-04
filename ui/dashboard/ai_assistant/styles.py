# ui/dashboard/ai_assistant/styles.py
"""Theme-aware styles for AI Assistant - Integrated with theme_manager"""

from ui.themes.theme_manager import get_theme_colors, get_current_theme


def _hex_to_rgba(color: str, alpha: float) -> str:
    clean = (color or "#5865f2").strip().lstrip("#")
    if len(clean) != 6:
        clean = "5865f2"
    try:
        red = int(clean[0:2], 16)
        green = int(clean[2:4], 16)
        blue = int(clean[4:6], 16)
    except ValueError:
        red, green, blue = 88, 101, 242
    alpha = max(0.0, min(1.0, alpha))
    return f"rgba({red}, {green}, {blue}, {alpha:.2f})"


def get_widget_style(is_dark):
    """Get main widget style using theme_manager colors"""
    colors = get_theme_colors()
    
    if is_dark:
        return f"""
            QFrame {{
                background-color: {colors.get('bg', '#2f3136')};
                border: 1px solid {colors.get('border', '#40444b')};
                border-radius: 12px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors.get('progress_bg', '#5865f2')};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors.get('icon_hover', '#ffffff')};
            }}
            QLabel {{
                color: {colors.get('text', '#dcddde')};
            }}
            QTabWidget::pane {{
                background: transparent;
            }}
        """
    else:
        return f"""
            QFrame {{
                background-color: {colors.get('bg', '#f8f9fa')};
                border: 1px solid {colors.get('border', '#dee2e6')};
                border-radius: 12px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors.get('progress_bg', '#5865f2')};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors.get('icon_hover', '#212529')};
            }}
            QLabel {{
                color: {colors.get('text', '#212529')};
            }}
            QTabWidget::pane {{
                background: transparent;
            }}
        """


def get_combo_style(is_dark):
    """Get combo box style with larger width - Integrated with theme_manager"""
    colors = get_theme_colors()
    
    if is_dark:
        input_bg = colors.get('card_bg', '#36393f')
        input_border = colors.get('border', '#40444b')
        text_color = colors.get('text', '#dcddde')
        dropdown_color = colors.get('text', '#dcddde')
        hover_bg = colors.get('bg_hover', '#40444b')
    else:
        input_bg = colors.get('card_bg', '#ffffff')
        input_border = colors.get('border', '#ced4da')
        text_color = colors.get('text', '#212529')
        dropdown_color = colors.get('text', '#212529')
        hover_bg = colors.get('bg_hover', '#e9ecef')
    
    return f"""
        QComboBox {{
            background-color: {input_bg};
            border: 1px solid {input_border};
            border-radius: 4px;
            padding: 4px 8px;
            color: {text_color};
            font-size: 9pt;
            min-width: 60px;
            min-height: 26px;
        }}
        QComboBox:hover {{
            border: 1px solid {colors.get('border_hover', '#5865f2')};
        }}
        QComboBox:focus {{
            border: 1px solid {colors.get('border_hover', '#5865f2')};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 16px;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {text_color};
            margin-right: 2px;
        }}
        QComboBox:disabled {{
            color: {colors.get('text_secondary', '#72767d' if is_dark else '#adb5bd')};
        }}
        QComboBox QAbstractItemView {{
            background-color: {input_bg};
            border: 1px solid {input_border};
            border-radius: 4px;
            color: {dropdown_color};
            selection-background-color: {colors.get('progress_bg', '#5865f2')};
            selection-color: white;
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 4px 10px;
            min-height: 24px;
            border: none;
            border-radius: 2px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {hover_bg};
            color: {text_color};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {colors.get('progress_bg', '#5865f2')};
            color: white;
        }}
    """


def get_search_style(is_dark):
    """Get search input style - Integrated with theme_manager"""
    colors = get_theme_colors()
    
    if is_dark:
        input_bg = colors.get('card_bg', '#36393f')
        input_border = colors.get('border', '#40444b')
        text_color = colors.get('text', '#dcddde')
        placeholder_color = "rgba(255, 255, 255, 0.5)"
    else:
        input_bg = colors.get('card_bg', '#ffffff')
        input_border = colors.get('border', '#ced4da')
        text_color = colors.get('text', '#212529')
        placeholder_color = "rgba(0, 0, 0, 0.4)"
    
    return f"""
        QLineEdit {{
            background-color: {input_bg};
            border: 1px solid {input_border};
            border-radius: 4px;
            padding: 6px 12px;
            color: {text_color};
            font-size: 10pt;
            min-height: 30px;
        }}
        QLineEdit:focus {{
            border: 1px solid {colors.get('border_hover', '#5865f2')};
        }}
        QLineEdit::placeholder {{
            color: {placeholder_color};
        }}
        QLineEdit:disabled {{
            color: {colors.get('text_secondary', '#72767d' if is_dark else '#adb5bd')};
        }}
    """


def get_export_btn_style():
    """Get export button style - Integrated with theme_manager"""
    colors = get_theme_colors()
    progress_bg = colors.get('progress_bg', '#5865f2')
    
    return f"""
        QPushButton {{
            padding: 6px 18px;
            border-radius: 4px;
            font-size: 10pt;
            font-weight: 500;
            color: white;
            background-color: {progress_bg};
            border: none;
            min-height: 30px;
        }}
        QPushButton:hover {{
            background-color: #4752c4;
        }}
        QPushButton:pressed {{
            background-color: #3c45a3;
        }}
        QPushButton:disabled {{
            background-color: {colors.get('text_secondary', '#72767d')};
            color: {colors.get('text', '#dcddde')};
        }}
    """


def get_progress_style():
    """Get progress bar style - Integrated with theme_manager"""
    colors = get_theme_colors()
    progress_bg = colors.get('progress_bg', '#5865f2')
    
    return f"""
        QProgressBar {{
            background-color: transparent;
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {progress_bg}, 
                stop:0.5 #9b59b6, 
                stop:1 #e67e22);
            border-radius: 2px;
        }}
    """


def get_tab_style():
    """Get tab widget style - Integrated with theme_manager"""
    colors = get_theme_colors()
    is_dark = get_current_theme() == "Dark"
    
    if is_dark:
        bg = colors.get('bg', '#2f3136')
        text = colors.get('text', '#dcddde')
        text_secondary = colors.get('text_secondary', '#b9bbbe')
    else:
        bg = colors.get('bg', '#f8f9fa')
        text = colors.get('text', '#212529')
        text_secondary = colors.get('text_secondary', '#6c757d')
    
    return f"""
        QTabWidget::pane {{
            border: none;
            background: transparent;
        }}
        QTabBar::tab {{
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 10pt;
            font-weight: 500;
            min-height: 32px;
            color: {text_secondary};
            background: transparent;
        }}
        QTabBar::tab:selected {{
            background: {colors.get('progress_bg', '#5865f2')};
            color: white;
        }}
        QTabBar::tab:hover:!selected {{
            background: {colors.get('bg_hover', '#40444b' if is_dark else '#e9ecef')};
            color: {text};
        }}
    """


def get_scroll_area_style():
    """Get scroll area style"""
    return """
        QScrollArea {
            border: none;
            background: transparent;
        }
    """


def get_header_label_style(is_dark):
    """Get header title style - Integrated with theme_manager"""
    colors = get_theme_colors()
    text_color = colors.get('text', '#ffffff' if is_dark else '#212529')
    return f"""
        font-size: 14pt;
        font-weight: 700;
        background: transparent;
        border: none;
        color: {text_color};
    """


def get_quick_stats_style(is_dark):
    """Get quick stats label style - Integrated with theme_manager"""
    colors = get_theme_colors()
    text_color = colors.get('text', '#ffffff' if is_dark else '#212529')
    return f"""
        font-size: 10pt;
        font-weight: 600;
        color: {text_color};
        background: transparent;
    """


def get_status_badge_style(status_color):
    """Get status badge style"""
    return f"""
        font-size: 9pt;
        color: {status_color};
        font-weight: 600;
        background: transparent;
        border: none;
    """


def get_last_updated_style(is_dark):
    """Get last updated label style - Integrated with theme_manager"""
    colors = get_theme_colors()
    text_secondary = colors.get('text_secondary', 'rgba(255,255,255,0.8)' if is_dark else '#495057')
    return f"""
        font-size: 8pt;
        color: {text_secondary};
        background: transparent;
        border: none;
    """


def get_insight_card_style(is_dark, color):
    """
    Get insight card style - Integrated with theme_manager
    Light theme: ပျော့ပျောင်းတဲ့ အရောင်နုနုတွေကိုသုံးပါ
    """
    colors = get_theme_colors()
    
    if is_dark:
        # Dark theme: transparent background with color overlay
        card_bg = _hex_to_rgba(color, 0.18)
        border_color = _hex_to_rgba(color, 0.34)
        text_color = colors.get('text', '#ffffff')
        detail_color = colors.get('text', 'rgba(255, 255, 255, 0.85)')
        tag_bg = _hex_to_rgba(color, 0.36)
        tag_color = "#ffffff"
    else:
        # Light theme: အရောင်နုနုတွေ (very light pastel colors)
        # color hex ကို ပိုပြီးနုတဲ့ opacity နဲ့ သုံးပါမယ်
        card_bg = _hex_to_rgba(color, 0.08)
        border_color = _hex_to_rgba(color, 0.22)
        text_color = colors.get('text', '#212529')
        detail_color = colors.get('text_secondary', '#495057')
        tag_bg = _hex_to_rgba(color, 0.16)
        tag_color = colors.get('text', '#212529')
    
    return {
        'card_bg': card_bg,
        'border_color': border_color,
        'text_color': text_color,
        'detail_color': detail_color,
        'tag_bg': tag_bg,
        'tag_color': tag_color,
    }


def get_error_card_style(is_dark):
    """Get error card style - Integrated with theme_manager"""
    if is_dark:
        return {
            'bg': "#3d1a1a",
            'border': "#5c2a2a",
            'text': "#ff6b6b"
        }
    else:
        return {
            'bg': "#fde8e8",
            'border': "#f5c6cb",
            'text': "#721c24"
        }


def get_refresh_button_style(is_dark, icon_color):
    """Get refresh button style - Integrated with theme_manager"""
    colors = get_theme_colors()
    
    return f"""
        QPushButton {{
            background-color: transparent;
            border: 1px solid {icon_color};
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {icon_color}30;
            border: 1px solid {colors.get('border_hover', '#5865f2')};
        }}
        QPushButton:pressed {{
            background-color: {colors.get('border_hover', '#5865f2')};
        }}
        QPushButton:disabled {{
            opacity: 0.5;
        }}
    """


def get_refresh_button_emoji_style(is_dark, icon_color):
    """Get refresh button style when using emoji fallback"""
    colors = get_theme_colors()
    
    return f"""
        QPushButton {{
            background-color: transparent;
            border: 1px solid {icon_color};
            border-radius: 6px;
            font-size: 16px;
        }}
        QPushButton:hover {{
            background-color: {icon_color}30;
            border: 1px solid {colors.get('border_hover', '#5865f2')};
        }}
        QPushButton:pressed {{
            background-color: {colors.get('border_hover', '#5865f2')};
            color: white;
        }}
        QPushButton:disabled {{
            opacity: 0.5;
        }}
    """


def get_section_header_style(is_dark):
    """Get section header style - Integrated with theme_manager"""
    colors = get_theme_colors()
    text_color = colors.get('text', '#ffffff' if is_dark else '#212529')
    return f"""
        font-size: 10pt;
        font-weight: 600;
        color: {text_color};
        background: transparent;
        border: none;
        padding: 4px 0px;
    """


# ✅ NEW: Control label style with transparent border
def get_control_label_style(is_dark):
    """Get control label style - transparent border, no background"""
    colors = get_theme_colors()
    text_color = colors.get('text', '#ffffff' if is_dark else '#212529')
    return f"""
        font-size: 10pt;
        font-weight: 500;
        color: {text_color};
        background: transparent;
        border: none;
        padding: 0px;
    """


# ✅ NEW: Control container style with transparent border
def get_control_container_style():
    """Get control container style - transparent border"""
    return """
        QWidget {
            background: transparent;
            border: none;
        }
    """
