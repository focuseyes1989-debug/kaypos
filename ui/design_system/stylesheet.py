# ui/design_system/stylesheet.py
"""
Application-wide design-system stylesheet.

This module styles regular Qt widgets so older screens can become visually
consistent without first replacing every widget with a custom component.
"""

from PyQt6.QtWidgets import QApplication, QWidget

from ui.design_system.theme import get_theme


def _px(value: int) -> str:
    return f"{value}px"


def build_design_stylesheet(theme_name: str = "Light") -> str:
    """Build a global stylesheet for common Qt widgets."""
    theme = get_theme()
    dark = theme_name == "Dark"
    colors = theme.get_colors(dark)
    spacing = theme.spacing
    radius = theme.radius
    typo = theme.typography

    table_bg = colors.card_bg
    table_alt = colors.table_alternate
    group_title_bg = colors.bg if not dark else colors.card_bg

    return f"""
        QWidget {{
            font-family: {typo.font_family};
            font-size: {typo.size_medium}pt;
            color: {colors.text};
        }}

        QFrame, QWidget {{
            outline: none;
        }}

        QLabel {{
            color: {colors.text};
            background: transparent;
        }}

        QGroupBox {{
            background-color: {colors.card_bg};
            border: 1px solid {colors.border};
            border-radius: {_px(radius.lg)};
            margin-top: 12px;
            padding: {_px(spacing.xl)} {_px(spacing.lg)} {_px(spacing.lg)} {_px(spacing.lg)};
            font-weight: {typo.weight_semibold};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            top: 1px;
            padding: 0px 6px;
            color: {colors.text_secondary};
            background-color: {group_title_bg};
            font-size: {typo.size_body}pt;
        }}

        QLineEdit, QTextEdit, QPlainTextEdit,
        QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {{
            background-color: {colors.input_bg};
            color: {colors.text};
            border: 1px solid {colors.input_border};
            border-radius: {_px(radius.input)};
            padding: {_px(spacing.input_padding_y)} {_px(spacing.input_padding_x)};
            selection-background-color: {colors.primary};
            selection-color: {colors.text_light};
        }}

        QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
        QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover, QTimeEdit:hover, QDateTimeEdit:hover {{
            border-color: {colors.border_hover};
        }}

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
        QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
            border: 2px solid {colors.input_focus};
        }}

        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
        QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled, QDateTimeEdit:disabled {{
            color: {colors.text_muted};
            background-color: {colors.bg_active};
            border-color: {colors.border};
        }}

        QComboBox {{
            background-color: {colors.input_bg};
            color: {colors.text};
            border: 1px solid {colors.input_border};
            border-radius: {_px(radius.input)};
            padding: {_px(spacing.input_padding_y)} 34px {_px(spacing.input_padding_y)} {_px(spacing.input_padding_x)};
            min-height: 20px;
            selection-background-color: {colors.primary};
            selection-color: {colors.text_light};
        }}

        QComboBox:hover {{
            border-color: {colors.border_hover};
        }}

        QComboBox:focus {{
            border: 2px solid {colors.input_focus};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 28px;
            subcontrol-origin: padding;
            subcontrol-position: center right;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {colors.text_secondary};
            margin-right: 8px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {colors.card_bg};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: {_px(radius.md)};
            padding: {_px(spacing.xs)};
            outline: none;
            selection-background-color: {colors.primary};
            selection-color: {colors.text_light};
        }}

        QComboBox QAbstractItemView::item {{
            min-height: 28px;
            padding: 6px 10px;
            border-radius: {_px(radius.sm)};
        }}

        QPushButton {{
            background-color: {colors.card_bg};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: {_px(radius.button)};
            padding: {_px(spacing.button_padding_y)} {_px(spacing.button_padding_x)};
            min-height: 28px;
            min-width: 72px;
            font-weight: {typo.weight_medium};
        }}

        QPushButton:hover {{
            background-color: {colors.bg_hover};
            border-color: {colors.border_hover};
        }}

        QPushButton:pressed {{
            background-color: {colors.bg_active};
        }}

        QPushButton:disabled {{
            color: {colors.text_muted};
            background-color: {colors.bg_active};
            border-color: {colors.border};
        }}

        QTableWidget, QTableView {{
            background-color: {table_bg};
            alternate-background-color: {table_alt};
            color: {colors.text};
            gridline-color: {colors.border};
            border: 1px solid {colors.border};
            border-radius: {_px(radius.table)};
            selection-background-color: {colors.table_selection};
            selection-color: {colors.text};
        }}

        QTableWidget::item, QTableView::item {{
            padding: 7px 10px;
            border: none;
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {colors.table_selection};
            color: {colors.text};
        }}

        QHeaderView::section {{
            background-color: {colors.table_header};
            color: {colors.text_secondary};
            border: none;
            border-bottom: 1px solid {colors.border};
            padding: 8px 10px;
            font-size: {typo.size_body}pt;
            font-weight: {typo.weight_semibold};
        }}

        QScrollBar:vertical {{
            background: {colors.scrollbar_bg};
            width: 10px;
            margin: 0px;
            border: none;
        }}

        QScrollBar::handle:vertical {{
            background: {colors.scrollbar_handle};
            border-radius: 5px;
            min-height: 28px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {colors.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: transparent;
        }}

        QScrollBar:horizontal {{
            background: {colors.scrollbar_bg};
            height: 10px;
            margin: 0px;
            border: none;
        }}

        QScrollBar::handle:horizontal {{
            background: {colors.scrollbar_handle};
            border-radius: 5px;
            min-width: 28px;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {colors.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: transparent;
        }}

        QTabWidget::pane {{
            border: 1px solid {colors.border};
            border-radius: {_px(radius.lg)};
            background: {colors.card_bg};
        }}

        QTabBar::tab {{
            background: transparent;
            color: {colors.text_secondary};
            padding: 8px 12px;
            margin-right: 2px;
            border-bottom: 2px solid transparent;
            font-weight: {typo.weight_medium};
        }}

        QTabBar::tab:selected {{
            color: {colors.primary};
            border-bottom-color: {colors.primary};
        }}

        QToolTip {{
            background-color: {colors.primary_dark};
            color: {colors.text_light};
            border: none;
            border-radius: {_px(radius.sm)};
            padding: 6px 8px;
        }}
    """


def compose_app_stylesheet(base_stylesheet: str = "", theme_name: str = "Light") -> str:
    """Combine legacy theme stylesheet with design-system defaults."""
    return "\n".join(
        part.strip()
        for part in (base_stylesheet, build_design_stylesheet(theme_name))
        if part and part.strip()
    )


def apply_design_system(app: QApplication | QWidget, theme_name: str = "Light", base_stylesheet: str = "") -> None:
    """Apply design-system styles to a QApplication or widget."""
    app.setStyleSheet(compose_app_stylesheet(base_stylesheet, theme_name))
