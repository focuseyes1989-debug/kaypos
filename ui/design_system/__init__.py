# ui/design_system/__init__.py
"""
Design System for ZAY POS
Centralized UI component library with theme support
"""

from ui.design_system.theme import Theme, get_theme, get_theme_colors, is_dark_theme
from ui.design_system.buttons import PrimaryButton, SecondaryButton, DangerButton, SuccessButton, WarningButton
from ui.design_system.table import ModernTable
from ui.design_system.search import SearchLineEdit
from ui.design_system.combobox import PrimaryComboBox
from ui.design_system.dialog import PrimaryDialog
from ui.design_system.header import PageHeader
from ui.design_system.card import StatCard
from ui.design_system.stylesheet import (
    apply_design_system,
    build_design_stylesheet,
    compose_app_stylesheet,
)

__all__ = [
    # Theme
    'Theme',
    'get_theme',
    'get_theme_colors',
    'is_dark_theme',
    # Buttons
    'PrimaryButton',
    'SecondaryButton',
    'DangerButton',
    'SuccessButton',
    'WarningButton',
    # Components
    'ModernTable',
    'SearchLineEdit',
    'PrimaryComboBox',
    'PrimaryDialog',
    'PageHeader',
    'StatCard',
    'apply_design_system',
    'build_design_stylesheet',
    'compose_app_stylesheet',
]
