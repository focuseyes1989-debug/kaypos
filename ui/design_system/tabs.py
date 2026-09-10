"""One tab treatment for both shared widgets and legacy named tab sets."""

from ui.design_system.metrics import CARD_RADIUS


def tab_stylesheet(colors, object_name=""):
    widget = "QTabWidget" + (f"#{object_name}" if object_name else "")
    tab = f"{widget} QTabBar::tab"
    return f"""
        {widget}::pane {{
            background-color: {colors['card_bg']};
            border: 1px solid {colors['border']}; border-radius: {CARD_RADIUS}px;
        }}
        {tab} {{
            background: transparent; color: {colors['text_secondary']};
            border: none; border-bottom: 2px solid transparent; border-radius: 0px;
            padding: 8px 12px; margin: 0px 2px 0px 0px;
            min-height: 20px; font-size: 9pt; font-weight: 500;
        }}
        {tab}:selected {{
            background: {colors['bg_hover']}; color: {colors['text']};
            border-bottom: 2px solid {colors['progress_bg']};
        }}
        {tab}:hover:!selected {{ background: {colors['bg_hover']}; }}
        {tab}:disabled {{ color: {colors['text_secondary']}; }}
    """
