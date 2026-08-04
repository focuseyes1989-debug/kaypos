# ui/customer_page/customer_display_theme.py
from ui.themes.theme_manager import is_dark_theme


def get_display_palette():
    """Theme-aware palette for the customer-facing digital signage display."""
    if is_dark_theme():
        return {
            "window": "#0d1117",
            "window_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d1117, stop:0.55 #111827, stop:1 #172033)",
            "title_bar": "#090d14",
            "title_hover": "#1f2937",
            "title_border": "rgba(255, 255, 255, 0.08)",
            "panel": "#151b26",
            "panel_alt": "#1b2330",
            "panel_soft": "rgba(88, 101, 242, 0.10)",
            "border": "rgba(255, 255, 255, 0.10)",
            "text": "#dbe4f0",
            "title_text": "#ffffff",
            "muted": "#8b98aa",
            "faint": "#5d6b7e",
            "accent": "#5b7cfa",
            "accent_2": "#22d3ee",
            "accent_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b7cfa, stop:1 #22d3ee)",
            "success": "#22c55e",
            "warning": "#fbbf24",
            "danger": "#ef4444",
            "table_header": "#111827",
            "selection": "rgba(91, 124, 250, 0.20)",
            "card_bg": "#151b26",
            "card_border": "rgba(255, 255, 255, 0.10)",
            "shadow": "rgba(0, 0, 0, 0.28)",
        }

    return {
        "window": "#f4f7fb",
        "window_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f8fbff, stop:0.55 #eef4ff, stop:1 #e9f7fb)",
        "title_bar": "#ffffff",
        "title_hover": "#eef2ff",
        "title_border": "rgba(15, 23, 42, 0.10)",
        "panel": "#ffffff",
        "panel_alt": "#f7faff",
        "panel_soft": "rgba(88, 101, 242, 0.08)",
        "border": "rgba(15, 23, 42, 0.10)",
        "text": "#172033",
        "title_text": "#0f172a",
        "muted": "#64748b",
        "faint": "#94a3b8",
        "accent": "#5865f2",
        "accent_2": "#0891b2",
        "accent_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5865f2, stop:1 #0891b2)",
        "success": "#16a34a",
        "warning": "#d97706",
        "danger": "#dc2626",
        "table_header": "#eef2ff",
        "selection": "rgba(88, 101, 242, 0.14)",
        "card_bg": "#ffffff",
        "card_border": "rgba(15, 23, 42, 0.10)",
        "shadow": "rgba(15, 23, 42, 0.08)",
    }


def get_launcher_style():
    """Base stylesheet for customer display, driven by the active app theme."""
    colors = get_display_palette()
    return f"""
        QWidget {{
            background: {colors['window']};
            color: {colors['text']};
            font-family: 'Segoe UI', 'Arial', 'Myanmar Text', 'Noto Sans Myanmar';
        }}

        QGroupBox {{
            background: {colors['panel']};
            border: 1px solid {colors['border']};
            border-radius: 18px;
            margin-top: 12px;
            padding-top: 14px;
            padding-bottom: 10px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 18px;
            padding: 0 10px;
            color: {colors['accent']};
            font-size: 10pt;
            font-weight: 700;
        }}

        QTableWidget {{
            background: {colors['panel']};
            color: {colors['text']};
            gridline-color: transparent;
            border: 1px solid {colors['border']};
            border-radius: 16px;
            font-size: 13pt;
            alternate-background-color: {colors['panel_alt']};
        }}

        QTableWidget::item {{
            padding: 10px 8px;
            border: none;
        }}

        QTableWidget::item:selected {{
            background-color: {colors['selection']};
            color: {colors['title_text']};
        }}

        QHeaderView::section {{
            background: {colors['table_header']};
            color: {colors['muted']};
            padding: 10px 8px;
            border: none;
            font-size: 10pt;
            font-weight: 700;
            text-transform: uppercase;
        }}

        QLabel {{
            color: {colors['text']};
            font-size: 11pt;
        }}

        QSplitter::handle {{
            background: {colors['border']};
            width: 2px;
            border-radius: 1px;
        }}

        QSplitter::handle:hover {{
            background: {colors['accent']};
        }}

        QScrollBar:vertical {{
            background: transparent;
            width: 7px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background: {colors['border']};
            border-radius: 3px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {colors['accent']};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        QFrame {{
            background: transparent;
        }}
    """
