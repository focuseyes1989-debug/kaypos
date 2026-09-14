# ui/design_system/stylesheet.py
"""
Application-wide design-system stylesheet.

This module styles regular Qt widgets so older screens can become visually
consistent without first replacing every widget with a custom component.
"""

from PyQt6.QtWidgets import QApplication, QWidget

from ui.design_system.theme import get_theme
from ui.design_system.metrics import CONTROL_HEIGHT, button_metrics_stylesheet
from ui.design_system.tabs import tab_stylesheet


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

        QScrollArea,
        QScrollArea > QWidget > QWidget,
        QScrollArea QWidget#qt_scrollarea_viewport,
        QStackedWidget,
        QWidget#mainContainer,
        QWidget#mainContent,
        QStackedWidget#workspacePages {{
            background-color: transparent;
            border: none;
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
            border-color: {colors.input_focus};
        }}

        QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {{
            min-height: 22px;
            padding: 6px {_px(spacing.input_padding_x)};
        }}

        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
        QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled, QDateTimeEdit:disabled {{
            color: {colors.text_muted};
            background-color: {colors.bg_active};
            border-color: {colors.border};
        }}

        QComboBox:disabled {{
            color: {colors.text_muted};
            background-color: transparent;
            border-color: {colors.border};
        }}

        QComboBox {{
            background-color: transparent;
            color: {colors.text};
            border: 1px solid {colors.input_border};
            border-radius: {_px(radius.input)};
            padding: 6px 34px 6px {_px(spacing.input_padding_x)};
            min-height: 22px;
            selection-background-color: {colors.primary};
            selection-color: {colors.text_light};
        }}

        QComboBox:hover {{
            border-color: {colors.border_hover};
        }}

        QComboBox:focus {{
            border-color: {colors.input_focus};
        }}

        QComboBox::drop-down {{
            border: none;
            background: transparent;
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
            padding: 6px {_px(spacing.button_padding_x)};
            min-height: {_px(CONTROL_HEIGHT - 10)};
            max-height: {_px(CONTROL_HEIGHT - 10)};
            min-width: 72px;
            font-weight: {typo.weight_medium};
        }}

        QToolButton {{
            min-height: {_px(CONTROL_HEIGHT - 10)};
            max-height: {_px(CONTROL_HEIGHT - 10)};
        }}

        QPushButton:hover {{
            background-color: {colors.bg_hover};
            border-color: {colors.border_hover};
        }}

        QPushButton:pressed {{
            background-color: {colors.bg_active};
        }}

        QPushButton:focus {{
            border-color: {colors.border_focus};
        }}

        QPushButton:disabled {{
            color: {colors.text_muted};
            background-color: {colors.bg_active};
            border-color: {colors.border};
        }}

        QTableWidget, QTableView {{
            background-color: transparent;
            alternate-background-color: transparent;
            color: {colors.text};
            gridline-color: transparent;
            border: 1px solid {colors.border};
            border-radius: {_px(radius.table)};
            selection-background-color: {colors.table_selection};
            selection-color: {colors.text};
        }}

        QTableWidget::viewport, QTableView::viewport {{
            background-color: transparent;
            border-radius: {_px(radius.table)};
        }}

        QTableWidget::item, QTableView::item {{
            padding: 6px 10px;
            border: none;
            border-bottom: 1px solid {colors.border};
            background-color: transparent;
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {colors.table_selection};
            color: {colors.text};
        }}

        QHeaderView::section {{
            background-color: {colors.bg_hover};
            color: {colors.text_secondary};
            border: none;
            border-bottom: 1px solid {colors.border};
            padding: 8px 10px;
            font-size: {typo.size_body}pt;
            font-weight: {typo.weight_semibold};
        }}

        QHeaderView::section:first {{
            border-top-left-radius: {_px(radius.table)};
        }}

        QHeaderView::section:last {{
            border-top-right-radius: {_px(radius.table)};
        }}

        QScrollBar:vertical {{
            background-color: transparent;
            width: 10px;
            margin: 0px;
            border: none;
            border-radius: 0px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {colors.scrollbar_handle};
            border: none;
            border-radius: 3px;
            min-height: 28px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {colors.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            width: 0px;
            border: none;
            background: transparent;
        }}

        QScrollBar:horizontal {{
            background-color: transparent;
            height: 10px;
            margin: 0px;
            border: none;
            border-radius: 0px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {colors.scrollbar_handle};
            border: none;
            border-radius: 3px;
            min-width: 28px;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {colors.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            height: 0px;
            border: none;
            background: transparent;
        }}

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
            border: none;
        }}

        QScrollBar::up-arrow, QScrollBar::down-arrow,
        QScrollBar::left-arrow, QScrollBar::right-arrow {{
            image: none;
            width: 0px;
            height: 0px;
        }}

        QTabWidget::pane {{
            border: none;
            border-radius: 0px;
            background: transparent;
        }}

        QTabWidget,
        QTabBar {{
            background-color: transparent;
            border: none;
        }}

        QTabBar::tab {{
            background: transparent;
            color: {colors.text_secondary};
            padding: 7px 18px;
            margin: 4px 4px 4px 0px;
            border: 1px solid transparent;
            border-radius: {_px(radius.md)};
            font-weight: {typo.weight_medium};
        }}

        QTabBar::tab:selected {{
            color: {colors.primary};
            background: {colors.card_bg};
            border: 1px solid {colors.primary};
            padding: 7px 18px;
            font-weight: {typo.weight_semibold};
        }}

        QTabBar::tab:hover:!selected {{
            background: {colors.bg_hover};
            color: {colors.text};
            border-color: {colors.border};
        }}

        QDialog, QMessageBox {{
            background-color: {colors.bg};
            color: {colors.text};
        }}

        QDialog > QFrame {{
            border-color: {colors.border};
        }}

        QDialogButtonBox {{
            background-color: {colors.card_bg};
            border-top: 1px solid {colors.border};
            padding: 10px 14px;
        }}

        QDialogButtonBox QPushButton,
        QMessageBox QPushButton {{
            min-width: 86px;
            min-height: {_px(CONTROL_HEIGHT - 10)};
            max-height: {_px(CONTROL_HEIGHT - 10)};
            padding: 4px 16px;
            border-radius: {_px(radius.button)};
            font-weight: {typo.weight_semibold};
        }}

        QMessageBox QPushButton#modernMessagePrimary {{
            background-color: {colors.primary};
            color: {colors.text_light};
            border: 1px solid {colors.primary};
        }}

        QMessageBox QPushButton#modernMessagePrimary:hover {{
            background-color: {colors.primary_hover};
            border-color: {colors.primary_hover};
        }}

        QMessageBox QPushButton#modernMessageSecondary {{
            background-color: {colors.card_bg};
            color: {colors.text};
            border: 1px solid {colors.border};
        }}

        QMessageBox QPushButton#modernMessageSecondary:hover {{
            background-color: {colors.bg_hover};
            border-color: {colors.border_hover};
        }}

        QMessageBox QPushButton#modernMessageDanger {{
            background-color: {colors.danger};
            color: {colors.text_light};
            border: 1px solid {colors.danger};
        }}

        QMessageBox QPushButton#modernMessageDanger:hover {{
            background-color: {colors.danger_hover};
            border-color: {colors.danger_hover};
        }}

        QMessageBox QLabel {{
            color: {colors.text};
            background: transparent;
            min-width: 40px;
        }}

        QMessageBox QLabel#qt_msgbox_label {{
            padding: 2px 0px;
            min-height: 38px;
            font-size: 9pt;
            min-width: 280px;
        }}

        QMenu {{
            background-color: {colors.card_bg};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: {_px(radius.lg)};
            padding: 6px;
        }}

        QMenu::item {{
            padding: 8px 26px;
            border-radius: {_px(radius.md)};
        }}

        QMenu::item:selected {{
            background-color: {colors.bg_hover};
            color: {colors.text};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {colors.border};
            margin: 5px 8px;
        }}

        QListWidget, QListView, QTreeWidget, QTreeView {{
            background-color: {colors.card_bg};
            alternate-background-color: {colors.table_alternate};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: {_px(radius.input)};
            outline: none;
        }}

        QListWidget::item, QListView::item,
        QTreeWidget::item, QTreeView::item {{
            min-height: 28px;
            padding: 5px 9px;
            border-radius: {_px(radius.sm)};
        }}

        QListWidget::item:selected, QListView::item:selected,
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {colors.table_selection};
            color: {colors.text};
        }}

        QProgressBar {{
            background-color: {colors.bg_active};
            color: {colors.text};
            border: none;
            border-radius: 4px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background-color: {colors.progress_bg};
            border-radius: 4px;
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
        for part in (base_stylesheet, build_design_stylesheet(theme_name),
                     button_metrics_stylesheet(),
                     button_metrics_stylesheet("QDialogButtonBox QPushButton, QMessageBox QPushButton"),
                     tab_stylesheet(vars(get_theme().get_colors(theme_name == "Dark"))))
        if part and part.strip()
    )


def apply_design_system(app: QApplication | QWidget, theme_name: str = "Light", base_stylesheet: str = "") -> None:
    """Apply design-system styles to a QApplication or widget."""
    app.setStyleSheet(compose_app_stylesheet(base_stylesheet, theme_name))
