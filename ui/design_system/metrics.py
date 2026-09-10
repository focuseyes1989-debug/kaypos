"""Shared logical-pixel metrics for desktop components, independent of DPI."""

CONTROL_HEIGHT = 38
COMPACT_HEIGHT = 32
CONTROL_RADIUS = 6
CARD_RADIUS = 8
CARD_HEIGHT = 96
CARD_PROGRESS_HEIGHT = 116
CARD_MIN_WIDTH = 140
CARD_PADDING = 10
DIALOG_PADDING = 16
GAP = 8
TABLE_ROW_HEIGHT = 38
ICON_SIZE = 16
SCROLLBAR_WIDTH = 10
SCROLLBAR_MIN_HANDLE = 28


def button_metrics_stylesheet(selector="QPushButton", *, compact=False):
    # Qt QSS min-height describes the content box, not the outer widget.
    height = COMPACT_HEIGHT if compact else CONTROL_HEIGHT
    return f"""{selector} {{
        min-height: {height - 10}px;
        padding: 4px 12px;
        border-radius: {CONTROL_RADIUS}px;
        font-size: 9pt;
    }}"""
