"""Small theme-aware style helpers for legacy dialogs during UI migration."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout

from ui.widgets.modern_button import ModernButton


STANDARD_CLOSE_BUTTON_SIZE = (112, 38)


def create_standard_close_button(dialog, text="Close"):
    """Create the single-action footer button used by modern dialogs."""
    button = ModernButton(text, ModernButton.SECONDARY)
    button.set_icon("close", size=(15, 15))
    button.set_compact(False)
    button.setFixedSize(*STANDARD_CLOSE_BUTTON_SIZE)
    button.clicked.connect(dialog.accept)
    return button


def add_standard_close_footer(layout, dialog, text="Close"):
    """Add a consistently sized Close action at the bottom-right."""
    footer = QHBoxLayout()
    footer.setContentsMargins(0, 8, 0, 0)
    footer.setSpacing(0)
    footer.addStretch(1)
    button = create_standard_close_button(dialog, text)
    footer.addWidget(button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.addLayout(footer)
    return button


def modern_table_stylesheet(colors, selector="QTableWidget"):
    return f"""
        {selector} {{
            background-color: {colors['card_bg']};
            alternate-background-color: {colors['table_alt']};
            color: {colors['text']};
            border: 1px solid {colors['border']};
            border-radius: 12px;
            gridline-color: transparent;
            outline: none;
        }}
        {selector}::item {{
            padding: 8px 12px;
            border-bottom: 1px solid {colors['border']};
        }}
        {selector}::item:selected, {selector}::item:hover {{
            background-color: {colors['bg_hover']};
            color: {colors['text']};
        }}
        QHeaderView::section {{
            background-color: {colors['card_bg']};
            color: {colors['text_secondary']};
            padding: 10px 12px;
            border: none;
            border-bottom: 1px solid {colors['border']};
            font-size: 9pt;
            font-weight: 600;
        }}
    """


def modern_panel_stylesheet(colors, object_name):
    return f"""
        QFrame#{object_name} {{
            background-color: {colors['card_bg']};
            border: 1px solid {colors['border']};
            border-radius: 11px;
        }}
    """
