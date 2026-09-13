"""One tab treatment for both shared widgets and legacy named tab sets."""

from ui.design_system.metrics import CARD_RADIUS


def tab_stylesheet(colors, object_name=""):
    widget = "QTabWidget" + (f"#{object_name}" if object_name else "")
    tab = f"{widget} QTabBar::tab"
    hover_bg = colors.get("card_hover", colors.get("bg_hover", colors["card_bg"]))
    return f"""
        {widget},
        {widget} QTabBar {{
            background-color: transparent;
            border: none;
        }}
        {widget}::pane {{
            background-color: transparent;
            border: none;
            border-radius: 0px;
            top: 0px;
        }}
        {widget}::tab-bar {{
            left: 0px;
        }}
        {tab} {{
            background: transparent; color: {colors['text_secondary']};
            border: 1px solid transparent;
            border-radius: {CARD_RADIUS}px;
            padding: 7px 18px;
            margin: 4px 4px 4px 0px;
            min-height: 22px; font-size: 9pt; font-weight: 600;
        }}
        {tab}:selected {{
            background: {colors['card_bg']}; color: {colors['progress_bg']};
            border: 1px solid {colors['progress_bg']};
            padding: 7px 18px;
            font-weight: 700;
        }}
        {tab}:hover:!selected {{
            background: {hover_bg};
            color: {colors['text']};
            border-color: {colors['border']};
        }}
        {tab}:disabled {{ color: {colors['text_secondary']}; }}
    """
